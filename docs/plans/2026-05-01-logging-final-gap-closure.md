# Logging Final Gap Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the remaining high-value structured logging gaps in `emo`, `api`, and `scanner` while preserving the current logging manager and rotation behavior.

**Architecture:** The implementation extends existing `format_log_event()` usage at already-established runtime branch points. Each gap is closed with the smallest possible code change plus a narrow regression test that reads the relevant category log file. Existing file routing, request IDs, and rotation configuration remain unchanged.

**Tech Stack:** Python, Flask, Flask-SocketIO, unittest, logging, TimedRotatingFileHandler

---

### Task 1: Emo Missing Event Coverage

**Files:**
- Modify: `supysonic/emo/ws.py`
- Modify: `tests/base/test_emo_logging.py`
- Verify context: `tests/base/test_emo_ws.py`

**Step 1: Write the failing tests**

Add targeted tests in `tests/base/test_emo_logging.py` for:
- unauthorized action before auth -> `emo event=unauthorized_action`
- unsupported action -> `emo event=unsupported_action`
- bad request / not found / forbidden websocket failures -> structured emo failure logs
- `playback.update` -> `emo event=playback_update`
- `queue.local.get` -> `emo event=queue_local_get`
- `queue.session.sync` -> `emo event=queue_session_sync`
- `queue.ready.complete` -> `emo event=queue_ready_complete`

**Step 2: Run tests to verify they fail**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_emo_logging`
Expected: FAIL because the new event assertions are not yet logged.

**Step 3: Write minimal implementation**

In `supysonic/emo/ws.py`, add `_log_emo_event(...)` calls at the exact branches that currently only emit responses or mutate state:
- pre-auth rejection branch
- unsupported action branch
- `PermissionError` / `LookupError` / `ValueError` exception handlers
- success paths for playback and queue synchronization events

Keep summaries compact:
- no passwords
- no full queue song ID lists
- include request id, client id, session id, action/result where useful

**Step 4: Run tests to verify they pass**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_emo_logging tests.base.test_emo_ws`
Expected: PASS

**Step 5: Commit**

Only if explicitly requested by the user:

```bash
git add supysonic/emo/ws.py tests/base/test_emo_logging.py tests/base/test_emo_ws.py
git commit -m "add missing emo structured logging events"
```

### Task 2: API Media Logging Coverage

**Files:**
- Modify: `supysonic/api/media.py`
- Modify: `tests/api/test_api_logging.py`
- Reuse context: `supysonic/api/__init__.py`, `supysonic/api/errors.py`

**Step 1: Write the failing tests**

Add targeted tests for the highest-value media paths that have an existing, reliable branch:
- stream failure -> `api event=media_stream_failed`
- download failure -> `api event=download_failed`
- cover art failure -> `api event=cover_art_failed`
- external lyrics fetch failure -> `api event=lyrics_external_failed`
- transcode start -> `api event=transcode_started` only if a deterministic hook exists in current code

**Step 2: Run tests to verify they fail**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.api.test_api_logging`
Expected: FAIL for the new log expectations.

**Step 3: Write minimal implementation**

In `supysonic/api/media.py`, add `log_api_event(...)` only where the runtime branch is unambiguous and already has the data needed for logging.

Prefer:
- failure logs before broad success logs
- smallest useful identifiers
- reason/error type fields over raw trace text

If `transcode_started` has no clean hook, leave it out and document that decision in the final report instead of forcing artificial logging.

**Step 4: Run tests to verify they pass**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.api.test_api_logging`
Expected: PASS

**Step 5: Commit**

Only if explicitly requested by the user:

```bash
git add supysonic/api/media.py tests/api/test_api_logging.py
git commit -m "add media structured logging coverage"
```

### Task 3: Scanner Lifecycle Completion

**Files:**
- Modify: `supysonic/scanner_func/scanner_runtime.py`
- Modify: `supysonic/scanner_func/scanner_review_tasks.py` if a natural hook exists
- Modify: `tests/base/test_scanner_helpers.py`

**Step 1: Write the failing tests**

Add tests for:
- stop-requested scanner run -> `scanner event=run_stopped`
- review task creation summary -> `scanner event=review_tasks_created` only if the review-task creation function exposes a stable summary point

Do not add tests for blueprint events that still lack a real runtime hook.

**Step 2: Run tests to verify they fail**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_helpers`
Expected: FAIL for the new assertions.

**Step 3: Write minimal implementation**

In `supysonic/scanner_func/scanner_runtime.py`, log `run_stopped` immediately before early return when `scanner.stop_requested` aborts post-processing.

If `createAlbumReviewTasks(...)` can report a reliable created count without invasive refactoring, log `review_tasks_created` at that point. Otherwise, skip that event and document the limitation.

**Step 4: Run tests to verify they pass**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_helpers`
Expected: PASS

**Step 5: Commit**

Only if explicitly requested by the user:

```bash
git add supysonic/scanner_func/scanner_runtime.py supysonic/scanner_func/scanner_review_tasks.py tests/base/test_scanner_helpers.py
git commit -m "complete scanner lifecycle logging"
```

### Task 4: Broad Verification

**Files:**
- Verify only: `supysonic/logging_manager.py`, `supysonic/emo/ws.py`, `supysonic/api/media.py`, `supysonic/scanner_func/scanner_runtime.py`
- Verify only: `tests/base/test_logging_utils.py`, `tests/base/test_logging_manager.py`, `tests/base/test_web_logging.py`, `tests/base/test_access_logging.py`, `tests/base/test_emo_logging.py`, `tests/api/test_api_logging.py`, `tests/base/test_task_manager.py`, `tests/base/test_scanner_helpers.py`, `tests/base/test_daemon_logging.py`, `tests/base/test_emo_ws.py`

**Step 1: Run the focused regression suite**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_utils tests.base.test_logging_manager tests.base.test_web_logging tests.base.test_access_logging tests.base.test_emo_logging tests.api.test_api_logging tests.base.test_task_manager tests.base.test_scanner_helpers tests.base.test_daemon_logging tests.base.test_emo_ws`
Expected: PASS

**Step 2: Re-verify rotation behavior if logging manager changed**

Run a direct check that `configure_web_logging(...)` and `configure_daemon_logging(...)` still attach `TimedRotatingFileHandler` with the configured `backupCount`.

**Step 3: Summarize any intentional omissions**

Document any blueprint events not implemented because no stable runtime hook exists in the current architecture.

**Step 4: Commit**

Only if explicitly requested by the user:

```bash
git add supysonic/emo/ws.py supysonic/api/media.py supysonic/scanner_func/scanner_runtime.py tests/base/test_emo_logging.py tests/api/test_api_logging.py tests/base/test_scanner_helpers.py docs/plans/2026-05-01-logging-final-gap-closure-design.md docs/plans/2026-05-01-logging-final-gap-closure.md
git commit -m "close remaining structured logging gaps"
```
