# Metadata Review Confirm NFO Write-Back Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade `Confirm Task` so it warns the user, writes the current review-task album metadata back to local `album.nfo`, and only then marks the review task as `confirmed`.

**Architecture:** Keep the existing `POST /metadata/review-tasks/<task_id>/confirm` route as the only finalization entrypoint. Move NFO-specific business logic into a small frontend helper module that can build, merge, and write `album.nfo` data from the current database state. Add a daemon command plus watcher-side short TTL suppression so the daemon ignores the exact `.nfo` path that the web layer just wrote.

**Tech Stack:** Flask, Peewee, `unittest`, watchdog event queue, multiprocessing connection IPC, existing `supysonic.nfo.nfo.NfoHandler`

---

### Task 1: Lock the confirm prompt contract

**Files:**
- Modify: `tests/frontend/test_metadata_review_workspace.py`
- Modify: `supysonic/templates/metadata-review-task.html`

**Step 1: Write the failing test**

Add a workspace test that renders `GET /metadata/review-tasks/<task_id>` and asserts the page source contains all of the following:

- the `Confirm Task` button
- a confirm-only warning message that mentions `album.nfo`
- a confirm branch in the inline script that can cancel the request before `fetch(...)`

Suggested assertion target strings:

```python
self.assertIn("Confirm Task", rv.data)
self.assertIn("album.nfo", rv.data)
self.assertIn("window.confirm", rv.data)
self.assertIn("button.dataset.reviewTaskLabel === 'confirm'", rv.data)
```

**Step 2: Run test to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace.MetadataReviewWorkspaceTestCase.test_review_workspace_confirm_button_includes_nfo_write_warning
```

Expected: `FAIL` because the current template submits confirm immediately with no warning.

**Step 3: Write the minimal implementation**

In `supysonic/templates/metadata-review-task.html`, add a confirm-only guard before the `fetch(...)` call:

```javascript
const confirmWritebackMessage = 'Confirm this review task and write the current metadata to album.nfo?';

if (button.dataset.reviewTaskLabel === 'confirm') {
  const shouldContinue = window.confirm(confirmWritebackMessage);
  if (!shouldContinue) {
    return;
  }
}
```

Keep the `dismiss` path unchanged.

**Step 4: Re-run the same test**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace.MetadataReviewWorkspaceTestCase.test_review_workspace_confirm_button_includes_nfo_write_warning
```

Expected: `OK`.

### Task 2: Add a focused metadata NFO helper module

**Files:**
- Create: `supysonic/frontend/metadata_nfo.py`
- Create: `tests/frontend/test_metadata_review_nfo.py`

**Step 1: Write the failing tests for path resolution and payload generation**

Create tests that cover:

- `getReviewAlbumNfoPath(album)` resolves `<track.folder.path>/album.nfo`
- `getReviewAlbumNfoPath(album)` raises a clear `ValueError` when the album has no tracks or no folder path
- `buildReviewAlbumNfoData(album)` returns a scanner-compatible `album` dict with sorted tracks

Suggested API:

```python
def getReviewAlbumNfoPath(album):
  ...


def buildReviewAlbumNfoData(album):
  ...
```

Suggested expected payload shape:

```python
{
  "album": {
    "title": "Review Album",
    "year": "2024",
    "albumartist": "Review Artist",
    "artist": "Review Artist",
    "track": [
      {
        "title": "First Track",
        "cdnum": 1,
        "position": 1,
        "artist": "Review Artist",
      }
    ],
  }
}
```

**Step 2: Run the new test file to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_nfo
```

Expected: `ERROR` because the module and tests do not exist yet.

**Step 3: Write the minimal helper implementation**

Create `supysonic/frontend/metadata_nfo.py` with focused helpers:

```python
import os

from ..db import Track


def getReviewAlbumTracks(album):
  return list(album.tracks.order_by(Track.disc, Track.number, Track.title))


def getReviewAlbumNfoPath(album):
  tracks = getReviewAlbumTracks(album)
  if not tracks or tracks[0].folder is None or not tracks[0].folder.path:
    raise ValueError("album folder not found")
  return os.path.join(tracks[0].folder.path, "album.nfo")


def buildReviewAlbumNfoData(album):
  tracks = getReviewAlbumTracks(album)
  return {
    "album": {
      "title": album.name,
      "year": album.year or "",
      "albumartist": album.artist.get_artist_name(),
      "artist": album.artist.get_artist_name(),
      "track": [
        {
          "title": track.title,
          "cdnum": track.disc,
          "position": track.number,
          "artist": track.artist.get_artist_name(),
        }
        for track in tracks
      ],
    }
  }
```

Keep the helper deliberately small and free of route logic.

**Step 4: Re-run the test file**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_nfo
```

Expected: path and payload tests pass, merge/write tests still pending.

### Task 3: Preserve unknown NFO fields while overriding review-owned fields

**Files:**
- Modify: `supysonic/frontend/metadata_nfo.py`
- Modify: `tests/frontend/test_metadata_review_nfo.py`

**Step 1: Write the failing merge tests**

Add tests that prove:

- unknown album-level fields survive an update
- unknown top-level or track-level content survives if it is outside the review-owned keys
- review-owned fields are overwritten from current DB state
- the outgoing `track` list is rebuilt from current DB order

Suggested API:

```python
def mergeReviewAlbumNfo(existingData, reviewData):
  ...
```

Suggested assertions:

```python
self.assertEqual(merged["album"]["studio"], "Unknown Field")
self.assertEqual(merged["album"]["title"], "Updated Album")
self.assertEqual(merged["album"]["track"][0]["title"], "Updated Track")
```

**Step 2: Run the test file to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_nfo
```

Expected: `FAIL` because merge behavior is not implemented yet.

**Step 3: Write the minimal merge implementation**

In `supysonic/frontend/metadata_nfo.py`, add an owned-key merge that keeps unknown fields:

```python
def mergeReviewAlbumNfo(existingData, reviewData):
  base = existingData.copy() if existingData else {}
  baseAlbum = dict(base.get("album", {}))
  reviewAlbum = reviewData["album"]

  for key in ("title", "year", "albumartist", "artist", "track"):
    baseAlbum[key] = reviewAlbum[key]

  base["album"] = baseAlbum
  return base
```

Do not try to do clever per-track diffing. The review task already owns the current track list view.

**Step 4: Re-run the test file**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_nfo
```

Expected: merge tests pass.

### Task 4: Add daemon command support for temporary NFO suppression

**Files:**
- Modify: `supysonic/daemon/client.py`
- Modify: `supysonic/daemon/server.py`
- Modify: `supysonic/watcher.py`
- Create: `tests/base/test_watcher_nfo_ignore.py`

**Step 1: Write the failing watcher suppression tests**

Add tests around a small public API that can be called without spinning up the full daemon:

- suppressed `.nfo` path is ignored during TTL
- same path starts working again after TTL expires
- another `.nfo` path is not ignored

Suggested queue API:

```python
queue = ScannerProcessingQueue(delay=1)
queue.suppress_nfo_path("/music/Album/album.nfo", ttl=5)
```

**Step 2: Run the new watcher test file to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_watcher_nfo_ignore
```

Expected: `ERROR` because the file and API do not exist yet.

**Step 3: Add the minimal suppression implementation**

In `supysonic/watcher.py`, extend `ScannerProcessingQueue`:

```python
class ScannerProcessingQueue(Thread):
  def __init__(self, delay):
    ...
    self.__suppressedNfoPaths = {}

  def suppress_nfo_path(self, path, ttl):
    with self.__cond:
      self.__suppressedNfoPaths[path] = time.time() + ttl

  def __is_suppressed_nfo_path(self, path):
    expiresAt = self.__suppressedNfoPaths.get(path)
    if expiresAt is None:
      return False
    if expiresAt < time.time():
      del self.__suppressedNfoPaths[path]
      return False
    return True

  def put(self, path, operation, **kwargs):
    if operation & FLAG_NFO and self.__is_suppressed_nfo_path(path):
      return
    ...
```

Expose a thin watcher-level passthrough as needed:

```python
def suppress_nfo_path(self, path, ttl):
  self.__queue.suppress_nfo_path(path, ttl)
```

In `supysonic/daemon/client.py`, add:

```python
class SuppressNfoPathCommand(DaemonCommand):
  def __init__(self, path, ttl):
    self.__path = path
    self.__ttl = ttl

  def apply(self, connection, daemon):
    if daemon.watcher is not None:
      daemon.watcher.suppress_nfo_path(self.__path, self.__ttl)
```

And add a client method:

```python
def suppress_nfo_path(self, path, ttl):
  with self.__get_connection() as c:
    c.send(SuppressNfoPathCommand(path, ttl))
```

**Step 4: Re-run the watcher test file**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_watcher_nfo_ignore
```

Expected: `OK`.

### Task 5: Add the actual NFO write-back service

**Files:**
- Modify: `supysonic/frontend/metadata_nfo.py`
- Modify: `tests/frontend/test_metadata_review_nfo.py`

**Step 1: Write the failing write-back tests**

Add tests that prove:

- a missing `album.nfo` is created
- an existing `album.nfo` is updated in place
- unknown fields remain after update
- daemon suppression is registered before writing
- daemon suppression failure aborts the write

Suggested API:

```python
def writeReviewAlbumNfo(task, daemonClient, suppressTtl):
  ...
```

**Step 2: Run the test file to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_nfo
```

Expected: `FAIL`.

**Step 3: Write the minimal service implementation**

Implement the service in this order:

```python
from ..nfo.nfo import NfoHandler


def writeReviewAlbumNfo(task, daemonClient, suppressTtl):
  nfoPath = getReviewAlbumNfoPath(task.album)
  reviewData = buildReviewAlbumNfoData(task.album)
  existingData = NfoHandler.read(nfoPath) if os.path.exists(nfoPath) else {}
  mergedData = mergeReviewAlbumNfo(existingData, reviewData)
  daemonClient.suppress_nfo_path(nfoPath, suppressTtl)
  NfoHandler.write(mergedData, output_path=nfoPath, pretty=True)
  return nfoPath
```

If `NfoHandler.write(...)` returns a falsey error signal, raise `RuntimeError("failed to write album.nfo")`.

**Step 4: Re-run the test file**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_nfo
```

Expected: `OK`.

### Task 6: Wire the confirm route so write-back happens before status change

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Modify: `tests/frontend/test_metadata_review_actions.py`

**Step 1: Write the failing confirm-route tests**

Add route tests that prove:

- successful confirm writes `album.nfo` before the task becomes `confirmed`
- write failure leaves the task `pending`
- the JSON error message is explicit enough for the existing feedback banner

Suggested assertions:

```python
self.assertEqual(rv.status_code, 200)
self.assertEqual(rv.json["task_status"], "confirmed")
self.assertEqual(AlbumReviewTask.get_by_id(self.task.id).status, "confirmed")
```

and on failure:

```python
self.assertEqual(rv.status_code, 500)
self.assertEqual(rv.json["status"], "error")
self.assertIn("album.nfo", rv.json["message"])
self.assertEqual(AlbumReviewTask.get_by_id(self.task.id).status, "pending")
```

**Step 2: Run the targeted test to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_actions.MetadataReviewActionsTestCase.test_review_task_confirm_writes_album_nfo_before_confirming
```

Expected: `FAIL` because confirm currently only updates task status.

**Step 3: Write the minimal route integration**

In `supysonic/frontend/metadata.py`, integrate the helper before calling `confirmMetadataReviewTask(task)`:

```python
from .metadata_nfo import writeReviewAlbumNfo
from ..daemon.client import DaemonClient


@frontend.route("/metadata/review-tasks/<task_id>/confirm", methods=["POST"])
def confirm_metadata_review_task(task_id):
  ...
  nfoPath = writeReviewAlbumNfo(
    task,
    daemonClient=DaemonClient(),
    suppressTtl=max(2, current_app.config["DAEMON_WAIT_DELAY"] + 2),
  )
  confirmMetadataReviewTask(task)
  ...
```

If the project config does not expose `DAEMON_WAIT_DELAY` directly, compute the TTL from `get_current_config().DAEMON["wait_delay"] + 2` instead.

Return a JSON error response when write-back fails:

```python
return {"status": "error", "message": f"Failed to write album.nfo: {exc}"}, 500
```

**Step 4: Re-run the route tests**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_actions
```

Expected: `OK`.

### Task 7: Extend metadata logging for confirm write-back success and failure

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Modify: `tests/frontend/test_metadata_review_actions.py`

**Step 1: Write the failing logging assertions**

Extend confirm tests so they assert that metadata logging records:

- `event=review_task_confirm`
- `result=success` or `result=failure`
- `task_id=<uuid>`
- `album_id=<uuid>`
- `nfo_path=<full path>` on success
- `failure_reason=...` on failure

**Step 2: Run the affected confirm tests to verify they fail**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_actions
```

Expected: `FAIL` until the new logging fields exist.

**Step 3: Add the minimal logging fields**

Keep the existing event name and expand the payload:

```python
logMetadataEvent(
  logging.INFO,
  "review_task_confirm",
  result="success",
  task_id=task.id,
  album_id=task.album.id,
  nfo_path=nfoPath,
  writeback=True,
  from_status=previous_status,
  to_status=task.status,
)
```

For failures, log:

```python
logMetadataEvent(
  logging.ERROR,
  "review_task_confirm",
  result="failure",
  task_id=task.id,
  album_id=task.album.id,
  failure_reason=str(exc),
)
```

**Step 4: Re-run the confirm tests**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_actions
```

Expected: `OK`.

### Task 8: Run full affected verification

**Files:**
- No code changes

**Step 1: Run focused frontend coverage**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace tests.frontend.test_metadata_review_actions tests.frontend.test_metadata_review_nfo
```

Expected: `OK`.

**Step 2: Run watcher and scanner-adjacent coverage**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_watcher_nfo_ignore tests.base.test_scanner_helpers tests.base.test_scanner_nfo_trace
```

Expected: `OK`.

**Step 3: Run broader metadata regression**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_inbox tests.frontend.test_metadata_review_workspace tests.frontend.test_metadata_review_actions tests.frontend.test_metadata_form tests.frontend.test_device_cover
```

Expected: `OK`.

**Step 4: Run whitespace and patch hygiene check**

Run:
```bash
git diff --check -- "supysonic/templates/metadata-review-task.html" "supysonic/frontend/metadata.py" "supysonic/frontend/metadata_nfo.py" "supysonic/daemon/client.py" "supysonic/daemon/server.py" "supysonic/watcher.py" "tests/frontend/test_metadata_review_workspace.py" "tests/frontend/test_metadata_review_actions.py" "tests/frontend/test_metadata_review_nfo.py" "tests/base/test_watcher_nfo_ignore.py"
```

Expected: no output.

---

## Notes

- Keep `.nfo` business logic in `supysonic/frontend/metadata_nfo.py`; do not spread it across routes.
- Do not expand the write-back scope beyond the review-owned fields in this change.
- Keep unknown `album.nfo` fields intact by replacing only the owned album keys.
- Keep the watcher suppression file-scoped; do not unschedule or reschedule entire folders for this workflow.
- If `DaemonClient()` is unavailable, fail the confirm request clearly instead of writing the file without suppression.
