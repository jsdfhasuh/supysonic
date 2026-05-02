# Supysonic / Emosonic Logging System Completion Plan v3

> Version: 3.0  
> Goal: Turn the logging plan into an implementation execution package.  
> Audience: local development engineer implementing the logging system.  
> Scope: Phase 2 Web observability completion + Phase 3 daemon logging integration.  
> Primary rule: do not change product behavior while adding logging, except the explicitly approved access-log privacy change.

---

# 0. What v3 Adds Beyond v2

This version adds execution-level detail:

- exact implementation dependency graph
- exact PR / commit split
- per-file change checklist
- test migration matrix
- event registry
- field registry
- helper code skeletons
- failure injection guidance
- rollout / rollback checklist
- review checklist
- security review checklist
- compatibility assertions
- known current tests that must be updated
- concrete code locations verified in the current repo

---

# 1. Fixed Decisions

These decisions are final.

## 1.1 `api.log`

`api.log` records:

- failures
- exceptions
- important actions

`api.log` does not record normal successful read requests.

## 1.2 `emo.log`

`emo.log` does not record full `queueSongIds`.

For queue events, only record summary:

```text
queue_size
current_index
position_ms
session_id
source_client_id
target_client_id
queue_type
result
reason
```

## 1.3 Request correlation

All HTTP requests get a request id.

- inbound `X-Request-ID` should be preserved after sanitization
- otherwise generate one
- response returns `X-Request-ID`
- `access.log` includes `request_id`
- `api.log` includes the same `request_id`
- WebSocket message logs use payload `requestId` as `client_request_id`

## 1.4 Format

New / changed logs use key=value.

```text
<domain> event=<event> key=value key=value
```

## 1.5 Access query privacy

`access.log` must not store raw query strings.

Use:

```text
query_keys=c,id,s,t,u
```

Never:

```text
/rest/getSong?id=...&u=...&t=...&s=...
```

---

# 2. Verified Current Code Locations

These locations should be treated as the current implementation anchors.

## 2.1 Logging manager

```text
supysonic/logging_manager.py
```

Current responsibilities:

- builds file handlers
- applies prefix routing
- configures Web logging
- registers access logging
- currently logs access in old mixed format
- currently logs raw query string

## 2.2 API global errors

```text
supysonic/api/errors.py
```

Current global handlers:

- `ValueError`
- `BadRequestKeyError`
- Peewee `DoesNotExist`
- 500
- unknown method route

Important: API logging should hook into these handlers as well as endpoint-specific failure points.

## 2.3 Scanner orchestration

```text
supysonic/scanner.py
supysonic/scanner_func/scanner_runtime.py
supysonic/scanner_func/scanner_folder.py
```

Important verified lifecycle points:

- `Scanner.run()` calls `runScanner(self, logger)`
- `runScanner(...)` handles queued folders and summary
- `scanFolder(...)` logs "Scanning folder %s" and calls:
  - `scanner.handle_folder_start(folder)`
  - `_scanFolderEntries`
  - `_removeDeletedFolders`
  - `_removeDeletedTracks`
  - `_refreshFolderCovers`
  - `scanner.handle_folder_end(folder)`

## 2.4 Daemon

```text
supysonic/daemon/__init__.py
supysonic/daemon/server.py
```

Important verified lifecycle points:

- daemon has manual `setup_logging(config)`
- `Daemon.run()` creates Listener
- `Daemon.run()` starts watcher
- `Daemon.run()` starts listener thread
- `Daemon.start_scan(...)` creates / queues scanner
- `Daemon.terminate()` stops scanner, watcher, jukebox

## 2.5 Watcher

```text
supysonic/watcher.py
```

Important verified lifecycle points:

- `SupysonicWatcherEventHandler` handles filesystem events
- `ScannerProcessingQueue.put(...)` schedules delayed processing
- `ScannerProcessingQueue.__run(...)` drains queued events
- `SupysonicWatcher.start()` schedules all root folders and starts observer
- `SupysonicWatcher.stop()` stops observer and queue

## 2.6 API media and scan

```text
supysonic/api/media.py
supysonic/api/scan.py
```

Important verified high-value endpoints:

- `/stream`
- `/download`
- `/getCoverArt`
- `/getLyrics`
- `/startScan`
- `/getScanStatus`

## 2.7 Current access tests

```text
tests/base/test_access_logging.py
```

Current tests assert old behavior:

- `[ACCESS:REST]`
- raw query string appears in `access.log`
- `[ACCESS:WEB]`
- socket `[ACCESS:SOCKET]`

These tests must be updated to the new key=value and no raw query behavior.

## 2.8 Current logging manager tests

```text
tests/base/test_logging_manager.py
```

Current tests expect exactly six Web files:

```text
access.log
api.log
emo.log
scanner.log
supysonic.log
task.log
```

After Phase 3, daemon categories may add extra files only when daemon logging is configured. Web logging should still create the six Web files unless intentionally changed.

---

# 3. Implementation Dependency Graph

Implement in this order.

```text
A. logging_utils.format_log_event
   ↓
B. request_id helper + access key=value format
   ↓
C. update access tests
   ↓
D. API logging helpers
   ↓
E. API auth/error/media/scan logs
   ↓
F. Emo logging helpers
   ↓
G. Emo ws/client/http logs
   ↓
H. Scanner lifecycle logs
   ↓
I. Task manager key=value cleanup
   ↓
J. config.sample + docs for Phase 2
   ↓
K. generic category logging refactor
   ↓
L. configure_daemon_logging
   ↓
M. daemon config migration
   ↓
N. replace daemon setup_logging
   ↓
O. daemon lifecycle logs
   ↓
P. watcher logs
   ↓
Q. daemon/watcher/scanner integration tests
   ↓
R. full regression
```

Do not start daemon integration before Phase 2 focused tests pass.

---

# 4. Recommended PR and Commit Split

## PR 1: Web Observability Completion

### Commit 1

```text
Add shared key=value logging utility
```

Files:

```text
supysonic/logging_utils.py
tests/base/test_logging_utils.py
```

### Commit 2

```text
Add request_id correlation and safe access logs
```

Files:

```text
supysonic/logging_manager.py
tests/base/test_access_logging.py
```

### Commit 3

```text
Add API logging helpers and auth/error logs
```

Files:

```text
supysonic/api/__init__.py
supysonic/api/errors.py
tests/api/test_api_logging.py
```

### Commit 4

```text
Add high-value API failure/action logs
```

Files:

```text
supysonic/api/browse.py
supysonic/api/media.py
supysonic/api/scan.py
tests/api/test_api_logging.py
```

### Commit 5

```text
Expand Emosonic websocket business logs
```

Files:

```text
supysonic/emo/ws.py
tests/base/test_emo_logging.py
```

### Commit 6

```text
Normalize HTTP Emo client logs
```

Files:

```text
supysonic/emo/__init__.py
supysonic/emo/client.py
tests/base/test_emo_logging.py
```

### Commit 7

```text
Expand scanner and task lifecycle logs
```

Files:

```text
supysonic/scanner_func/scanner_runtime.py
supysonic/scanner_func/scanner_folder.py
supysonic/TaskManger.py
tests/base/test_scanner_logging.py
tests/base/test_task_manager.py
```

### Commit 8

```text
Update Web logging config sample and docs
```

Files:

```text
config.sample
docs/plans/...
```

## PR 2: Daemon Logging Integration

### Commit 1

```text
Refactor logging manager for shared category logging
```

Files:

```text
supysonic/logging_manager.py
tests/base/test_logging_manager.py
```

### Commit 2

```text
Add daemon logging configuration
```

Files:

```text
supysonic/config.py
supysonic/logging_manager.py
tests/base/test_daemon_logging.py
```

### Commit 3

```text
Switch daemon setup_logging to logging_manager
```

Files:

```text
supysonic/daemon/__init__.py
tests/base/test_daemon_logging.py
```

### Commit 4

```text
Add daemon lifecycle logs
```

Files:

```text
supysonic/daemon/__init__.py
supysonic/daemon/server.py
tests/base/test_daemon_logging.py
```

### Commit 5

```text
Add watcher lifecycle and scheduling logs
```

Files:

```text
supysonic/watcher.py
tests/base/test_daemon_logging.py
```

### Commit 6

```text
Update daemon config sample and docs
```

Files:

```text
config.sample
docs/plans/...
```

---

# 5. Event Registry

Use this as the canonical list of event names.

## 5.1 access

```text
access event=request
```

Fields:

```text
type
request_id
remote
method
path
status
bytes
duration
query_keys
```

## 5.2 api

```text
api event=auth_failure
api event=bad_request
api event=entity_not_found
api event=unknown_method
api event=server_error
api event=get_songs_item_failed
api event=media_stream_failed
api event=transcode_started
api event=download_failed
api event=cover_art_failed
api event=lyrics_external_failed
api event=scan_requested
api event=scan_request_failed
api event=scan_status_failed
```

## 5.3 emo

```text
emo event=socket_connect
emo event=socket_disconnect
emo event=bad_message
emo event=unauthorized_action
emo event=auth_login
emo event=device_register
emo event=session_subscribe
emo event=session_unsubscribe
emo event=control_forward
emo event=playback_update
emo event=queue_local_get
emo event=queue_local_set
emo event=queue_session_sync
emo event=queue_ready_complete
emo event=unsupported_action
emo event=upload_log_failed
emo event=view_log_failed
emo event=download_log_failed
```

## 5.4 scanner

```text
scanner event=run_start
scanner event=run_stopped
scanner event=run_end
scanner event=folder_start
scanner event=folder_end
scanner event=folder_skip
scanner event=metadata_stage_start
scanner event=metadata_stage_end
scanner event=review_tasks_created
```

## 5.5 task

```text
task event=submitted
task event=started
task event=completed
task event=failed
```

## 5.6 daemon

```text
daemon event=start
daemon event=listening
daemon event=unknown_command
daemon event=scan_requested
daemon event=scan_queued
daemon event=scan_started
daemon event=stop
daemon event=terminate_begin
daemon event=terminate_scanner_stop
daemon event=terminate_watcher_stop
daemon event=terminate_jukebox_stop
daemon event=terminate_end
daemon event=crash
```

## 5.7 watcher

```text
watcher event=start
watcher event=stop
watcher event=folder_watch_added
watcher event=folder_watch_removed
watcher event=file_event_queued
watcher event=scan_scheduled
watcher event=queue_processing_start
watcher event=item_scan
watcher event=item_remove
watcher event=item_move
watcher event=cover_scan
watcher event=nfo_scan
watcher event=cover_scan_start
watcher event=cover_scan_end
watcher event=metadata_missing_summary
watcher event=error
```

---

# 6. Field Registry

Use these field names consistently.

## 6.1 General

```text
event
result
reason
error
error_type
duration
request_id
client_request_id
remote
path
route
method
status
bytes
query_keys
```

## 6.2 User / client

```text
user
client
client_id
source_client_id
target_client_id
device_name
roles
sid
session_id
```

## 6.3 API entities

```text
entity
id
track_id
album_id
artist_id
folder_id
cover_id
playlist_id
param
```

## 6.4 Media

```text
src
dst
bitrate
format
mimetype
size
```

## 6.5 Queue / playback

```text
queue_size
queue_type
current_index
position_ms
state
action
```

## 6.6 Scanner

```text
trigger
queued_folders
folder
scanned
existing_tracks
added_artists
added_albums
added_tracks
deleted_artists
deleted_albums
deleted_tracks
errors
stage
count
force
follow_symlinks
```

## 6.7 Daemon / watcher

```text
socket
watcher
log_level
signal
folders
source
delay
op
pending
src_path
```

---

# 7. Code Skeletons

## 7.1 `supysonic/logging_utils.py`

```python
import shlex

SENSITIVE_FIELD_NAMES = {
    "password",
    "pass",
    "passwd",
    "p",
    "token",
    "access_token",
    "refresh_token",
    "salt",
    "s",
    "t",
    "authorization",
    "cookie",
    "session",
}

def _is_sensitive_key(key):
    return str(key).lower() in SENSITIVE_FIELD_NAMES

def _normalize_value(value):
    if value is None:
        return "-"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return ",".join(_normalize_value(v) for v in value) or "-"
    if isinstance(value, dict):
        return "<dict>"
    text = str(value)
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    if text == "":
        return "-"
    return text

def _quote_if_needed(text):
    if any(ch.isspace() for ch in text) or "=" in text or '"' in text or "'" in text:
        return shlex.quote(text)
    return text

def sanitize_log_field(key, value):
    if _is_sensitive_key(key):
        return "***"
    return _quote_if_needed(_normalize_value(value))

def format_log_event(domain, event, **fields):
    parts = [str(domain), f"event={sanitize_log_field('event', event)}"]
    for key, value in fields.items():
        parts.append(f"{key}={sanitize_log_field(key, value)}")
    return " ".join(parts)
```

Notes:

- Developer may adjust quoting implementation.
- Tests define the final expected escaping.

## 7.2 Request ID helper

In `logging_manager.py`:

```python
import uuid

def _sanitize_request_id(value):
    value = (value or "").strip()
    value = value.replace("\r", "").replace("\n", "")
    value = value[:128]
    return value or uuid.uuid4().hex[:12]

def _get_or_create_request_id():
    return _sanitize_request_id(request.headers.get("X-Request-ID"))
```

## 7.3 API helper

In `api/__init__.py`:

```python
from flask import g
from ..logging_utils import format_log_event

def get_request_id():
    return getattr(g, "supysonic_request_id", "-")

def get_api_log_context():
    user = getattr(getattr(request, "user", None), "name", "-")
    client_obj = getattr(request, "client", None)
    client = getattr(client_obj, "client_name", None)
    if client is None:
        client = request.values.get("c", "-")
    return {
        "request_id": get_request_id(),
        "route": request.path,
        "user": user,
        "client": client,
        "remote": request.remote_addr or "-",
    }

def log_api_event(level, event, **fields):
    data = get_api_log_context()
    data.update(fields)
    logger.log(level, format_log_event("api", event, **data))
```

## 7.4 Emo helper

In `emo/ws.py`:

```python
def _log_emo_event(level, event, **fields):
    logger.log(level, format_log_event("emo", event, **fields))
```

## 7.5 Daemon logging manager skeleton

In `logging_manager.py`:

```python
def configure_daemon_logging(config, logger_name="supysonic"):
    log_dir = config.get("log_dir")
    if not log_dir and config.get("log_file"):
        log_dir = os.path.dirname(config["log_file"]) or "."
    normalized = {
        "log_dir": log_dir,
        "log_rotate": config.get("log_rotate", True),
        "log_level": config.get("log_level", "WARNING"),
        "log_backup_count": config.get("log_backup_count", 7),
    }
    return configure_category_logging(
        normalized,
        logger_name=logger_name,
        categories=("summary", "daemon", "watcher", "scanner"),
        route_prefixes={
            "daemon": (f"{logger_name}.daemon",),
            "watcher": (f"{logger_name}.watcher",),
            "scanner": (f"{logger_name}.scanner", f"{logger_name}.scanner_func"),
        },
    )
```

---

# 8. Current Test Migration Matrix

## 8.1 `tests/base/test_access_logging.py`

### Current assertion

```python
self.assertIn("[ACCESS:REST]", access_content)
```

Replace with:

```python
self.assertIn("access event=request", access_content)
self.assertIn("type=REST", access_content)
```

### Current assertion

```python
self.assertIn("/rest/ping?u=root&t=abc&s=def", access_content)
```

Replace with:

```python
self.assertIn("path=/rest/ping", access_content)
self.assertIn("query_keys=s,t,u", access_content)
self.assertNotIn("?u=root", access_content)
self.assertNotIn("t=abc", access_content)
self.assertNotIn("s=def", access_content)
```

### Current assertion

```python
self.assertIn("[ACCESS:WEB]", access_content)
self.assertIn("/page?tab=albums", access_content)
```

Replace with:

```python
self.assertIn("type=WEB", access_content)
self.assertIn("path=/page", access_content)
self.assertIn("query_keys=tab", access_content)
self.assertNotIn("?tab=albums", access_content)
```

### Current socket assertion

```python
self.assertIn("[ACCESS:SOCKET]", access_content)
```

Replace with either:

Option A, if socket access uses same access event format:

```python
self.assertIn("access event=socket", access_content)
```

Option B, if keeping access event request style for socket:

```python
self.assertIn("access event=request", access_content)
self.assertIn("type=SOCKET", access_content)
```

Recommended: use Option A for socket connect/disconnect summary:

```text
access event=socket type=SOCKET event_name=connect ...
```

But avoid duplicate `event=` keys. Better:

```text
access event=socket type=SOCKET socket_event=connect sid=...
```

Then tests:

```python
self.assertIn("access event=socket", access_content)
self.assertIn("socket_event=connect", access_content)
self.assertIn("socket_event=disconnect", access_content)
```

## 8.2 `tests/base/test_logging_manager.py`

Phase 2 should keep six Web files.

No need to add daemon files to Web logging test.

Phase 3 should add separate daemon logging test rather than changing Web file expectations.

## 8.3 New test files

Create:

```text
tests/base/test_logging_utils.py
tests/api/test_api_logging.py
tests/base/test_scanner_logging.py
tests/base/test_daemon_logging.py
```

If these files already exist locally after partial work, extend them.

---

# 9. Edge Cases and Failure Injection

## 9.1 Access logging

Test:

- no query string
- query string with sensitive values
- long `X-Request-ID`
- blank `X-Request-ID`
- response direct passthrough
- streamed response
- error response still has `X-Request-ID`
- `after_request` runs even for 4xx/5xx generated by Flask handlers

## 9.2 API logging

Test:

- missing `u`
- missing `c`
- wrong password
- invalid `enc:` password
- invalid UUID
- missing entity
- missing cover file
- daemon unavailable in `/startScan`
- unsupported endpoint

Use monkeypatch/mocking where possible.

## 9.3 Emo logging

Test:

- non-dict message
- missing action
- payload not dict
- unauthenticated action
- failed auth
- cross-user control denied
- target client offline
- queue payload with IDs does not leak IDs
- queue payload invalid type logs bad_request

## 9.4 Scanner logging

Test:

- empty queue
- nonexistent folder
- stop requested before finishing
- folder scan OSError
- metadata stage exception if currently propagated
- review task count unknown fallback

## 9.5 Daemon logging

Test without starting real listener where possible.

Use direct logger routing tests for logging manager.

For daemon lifecycle:

- call small helper if extracted
- otherwise use mocked config and monkeypatched Listener/Daemon where practical

## 9.6 Watcher logging

Avoid real filesystem observer in unit tests.

Test:

- direct `SupysonicWatcher.add_folder` with mocked observer
- direct `ScannerProcessingQueue.put` if practical
- logger routing to watcher.log

---

# 10. Security Review Checklist

Before merge, grep generated logs from tests and manual run for:

```text
password
p=
token
t=abc
s=def
Authorization
Cookie
queueSongIds
```

Expected:

- sensitive field names may appear in `query_keys`
- sensitive values must not appear
- full query string must not appear
- queue song IDs must not appear in `emo.log`

Review code for:

- any `request.url`
- any `request.full_path`
- any `request.query_string`
- any direct log of `request.values`
- any direct log of WebSocket payload
- any direct log of uploaded file content
- any direct log of database URI with password

Approved use:

- `request.path`
- `request.args.keys()`
- summarized payload fields

---

# 11. Performance Review Checklist

Review added logs for potential high volume.

Do not INFO log:

- every streamed audio chunk
- every cover art success
- every normal REST success
- every track scan
- every broadcast target
- every raw filesystem event

Use DEBUG for:

- raw file created/modified/deleted/moved
- individual missing cover/artist details
- per-item watcher internals

Use INFO for:

- lifecycle summaries
- failures
- important actions
- schedule/trigger events

---

# 12. Compatibility Review Checklist

Verify:

- Web `log_dir` works
- Web old `log_file` fallback works
- Web no logging directory -> console only
- Daemon `log_dir` works
- Daemon old `log_file` fallback works
- Daemon no logging directory -> console only
- repeated configure calls do not duplicate handlers
- unmanaged handlers are preserved
- existing API responses unchanged
- existing scanner behavior unchanged
- existing daemon behavior unchanged

---

# 13. Manual Validation Script

After implementation, run the service and manually trigger:

## 13.1 REST ping

```bash
curl -i "http://localhost:5000/rest/ping.view?u=root&t=abc&s=def&c=test"
```

Verify:

- `X-Request-ID` response header exists
- `access.log` has:
  - `access event=request`
  - `type=REST`
  - `query_keys=c,s,t,u`
- `access.log` does not have:
  - `t=abc`
  - `s=def`
  - full query string

## 13.2 Bad auth

```bash
curl -i "http://localhost:5000/rest/getArtists.view?u=root&p=wrong&c=test"
```

Verify:

- `api.log` has `api event=auth_failure`
- no password value appears

## 13.3 Cover art failure

```bash
curl -i "http://localhost:5000/rest/getCoverArt.view?id=missing&u=root&p=xxx&c=test"
```

Verify:

- `api.log` has `cover_art_failed`

## 13.4 Start scan

```bash
curl -i "http://localhost:5000/rest/startScan.view?u=root&p=xxx&c=test"
```

Verify:

- success: `api event=scan_requested`
- daemon unavailable: `api event=scan_request_failed`

## 13.5 WebSocket

Use existing test client or app client.

Verify:

- connect/disconnect appears in access or emo logs
- failed login appears in `emo.log`
- queue update does not expose song IDs

## 13.6 Daemon

Start daemon.

Verify files:

```text
supysonic.log
daemon.log
watcher.log
scanner.log
```

Verify:

- daemon start event
- daemon listening event
- watcher start event if enabled

---

# 14. Open Implementation Decisions With Defaults

These do not need product approval unless engineer disagrees.

## 14.1 Socket access event format

Default:

```text
access event=socket type=SOCKET socket_event=connect sid=...
```

Reason:

- avoids confusing `access event=request` for non-HTTP message layer
- avoids duplicate `event=` keys

## 14.2 Separate daemon debug log

Default: no.

When `log_level=DEBUG`, write DEBUG to normal daemon/category logs.

## 14.3 Watcher raw file events

Default:

- DEBUG for raw filesystem events
- INFO for schedule/processing summaries

## 14.4 Scanner trigger field

Default:

- implement `trigger=unknown` first
- add real trigger if easy without API churn

## 14.5 Logging directory creation failure

Default preferred behavior:

- console warning
- continue with console-only logging

If current app conventions prefer fail-fast, document it and add tests.

---

# 15. Definition of Done: PR 1

PR 1 is done when:

- `supysonic/logging_utils.py` exists
- `format_log_event` tests pass
- access logs use key=value
- access logs no longer include raw query
- access logs include request ID
- HTTP responses include `X-Request-ID`
- `api.log` auth failures include request ID
- `api.log` bad request / not found / high-value failures are implemented
- `api.log` does not log normal successful read requests
- `emo.log` covers auth/device/session/control/queue summaries
- `emo.log` never includes full queue song IDs
- `scanner.log` covers run/folder/stage summaries
- `task.log` uses key=value
- config sample Web section updated
- docs updated
- focused tests pass
- regression tests pass
- manual validation checklist completed

---

# 16. Definition of Done: PR 2

PR 2 is done when:

- `configure_daemon_logging` exists
- `DAEMON.log_dir` exists
- `DAEMON.log_backup_count` exists
- daemon uses logging_manager
- `daemon.log` exists and receives daemon events
- `watcher.log` exists and receives watcher events
- daemon scanner logs route to `scanner.log`
- daemon/watcher/scanner events also appear in `supysonic.log`
- legacy daemon `log_file` fallback works
- repeated daemon setup does not duplicate logs
- config sample daemon section updated
- docs updated
- daemon logging tests pass
- regression tests pass
- manual daemon validation completed

---

# 17. Final Full Test Command

```bash
python -m unittest \
  tests.base.test_logging_utils \
  tests.base.test_logging_manager \
  tests.base.test_access_logging \
  tests.api.test_api_logging \
  tests.base.test_emo_logging \
  tests.base.test_scanner_helpers \
  tests.base.test_scanner_logging \
  tests.base.test_task_manager \
  tests.base.test_daemon_logging \
  tests.base.test_web_startup \
  tests.frontend.test_admin_tasks \
  tests.frontend.test_metadata_inbox \
  tests.frontend.test_metadata_review \
  tests.frontend.test_metadata_review_actions \
  tests.frontend.test_metadata_form \
  tests.frontend.test_metadata_review_workspace
```

---

# 18. Final Py Compile Command

```bash
python -m py_compile \
  supysonic/logging_utils.py \
  supysonic/logging_manager.py \
  supysonic/web.py \
  supysonic/api/__init__.py \
  supysonic/api/errors.py \
  supysonic/api/browse.py \
  supysonic/api/media.py \
  supysonic/api/scan.py \
  supysonic/emo/__init__.py \
  supysonic/emo/client.py \
  supysonic/emo/ws.py \
  supysonic/daemon/__init__.py \
  supysonic/daemon/server.py \
  supysonic/watcher.py \
  supysonic/scanner.py \
  supysonic/scanner_func/scanner_runtime.py \
  supysonic/scanner_func/scanner_folder.py \
  supysonic/TaskManger.py
```

---

# 19. Reviewer Checklist

Before approving:

- [ ] Does access log avoid raw query strings?
- [ ] Does access log include request ID?
- [ ] Does every HTTP response include `X-Request-ID`?
- [ ] Are API successes kept out of `api.log` except important actions?
- [ ] Are secrets redacted?
- [ ] Are queue song IDs absent from `emo.log`?
- [ ] Are logs key=value?
- [ ] Are high-volume success paths not logged at INFO?
- [ ] Are old config fallbacks preserved?
- [ ] Are daemon and Web logging configured independently?
- [ ] Are tests updated away from old access format?
- [ ] Are docs and config sample updated?
- [ ] Is rollback easy?

---

# 20. Rollback

No database migration is involved.

PR 1 rollback:

- restores previous access format
- restores previous Web logging behavior

PR 2 rollback:

- restores old daemon `setup_logging`
- restores daemon `log_file` behavior

If only a subset fails, prefer reverting the affected PR rather than hotfixing partial logging state.

---

# 21. Future Phase 4 Ideas

Not part of this plan:

- log viewer UI
- log search and filtering
- JSON logging
- OpenTelemetry traces
- compressed rotated logs
- configurable log levels per category
- websocket HTTP upgrade `101` logging
- client log upload correlation using `X-Request-ID`
