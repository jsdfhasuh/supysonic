# Supysonic / Emosonic Logging System Deep Implementation Blueprint v4

> Version: 4.0  
> Relationship to v3: This is an execution-depth supplement to `supysonic-logging-system-completion-plan-v3.md`.  
> Purpose: Provide function-level implementation notes, exact test migration guidance, assertion patterns, failure-injection ideas, and PR review gates.

---

# 0. How to Use This Document

Use this document together with v3.

- v3 = product/architecture/specification
- v4 = execution blueprint for the engineer writing code and tests

Recommended workflow:

1. Read v3 once.
2. Use v4 section by section while implementing.
3. Do not skip tests.
4. Do not combine Phase 2 and Phase 3 into one PR.
5. Keep behavior changes limited to approved logging behavior changes.

---

# 1. Implementation Ground Rules

## 1.1 Do not change runtime behavior

Logging work must not alter:

- Subsonic REST API response format
- HTTP status codes
- authentication behavior
- scanner behavior
- daemon lifecycle behavior
- watcher scheduling behavior
- WebSocket protocol messages

Approved behavior changes only:

- `access.log` no longer stores raw query string
- HTTP responses include `X-Request-ID`
- log text format changes to key=value

## 1.2 Logging must be additive and safe

Logging should not:

- swallow exceptions
- change return values
- change database writes
- add expensive DB queries
- iterate large collections purely for logging
- include secrets
- include full queue song IDs
- log high-volume success events at INFO

## 1.3 Tests are part of the implementation

Do not treat tests as afterthoughts.

Each logging event must have at least one test proving:

- it appears in the correct log file
- it has the correct key=value shape
- sensitive values are not present
- it does not appear in unrelated category files where applicable

---

# 2. Phase 2 Implementation Ticket Breakdown

## Ticket P2-001: Add `logging_utils`

### Files

```text
CREATE supysonic/logging_utils.py
CREATE tests/base/test_logging_utils.py
```

### Implementation tasks

- Add `format_log_event(domain, event, **fields)`
- Add field sanitizer
- Add sensitive-field redaction
- Add stable quoting rules
- Add list/tuple/set support
- Avoid multi-line log injection

### Suggested tests

```python
def test_formats_basic_event(self):
    self.assertEqual(
        format_log_event("api", "auth_failure", user="alice", reason="wrong_password"),
        "api event=auth_failure user=alice reason=wrong_password",
    )
```

```python
def test_redacts_sensitive_fields(self):
    line = format_log_event("api", "auth_failure", p="secret", t="token", s="salt")
    self.assertIn("p=***", line)
    self.assertIn("t=***", line)
    self.assertIn("s=***", line)
    self.assertNotIn("secret", line)
    self.assertNotIn("token", line)
    self.assertNotIn("salt", line)
```

```python
def test_escapes_newline(self):
    line = format_log_event("api", "bad_request", reason="bad\nthing")
    self.assertNotIn("\nbad", line)
```

```python
def test_formats_list_as_comma_joined(self):
    line = format_log_event("emo", "device_register", roles=["player", "controller"])
    self.assertIn("roles=player,controller", line)
```

### Definition of done

- Tests pass
- No dependency on Flask
- No logging configuration side effects

---

## Ticket P2-002: Add request_id and safe access logs

### Files

```text
MODIFY supysonic/logging_manager.py
MODIFY tests/base/test_access_logging.py
```

### Implementation tasks

- Add `uuid` import
- Add `_sanitize_request_id`
- Add `_get_or_create_request_id`
- In `before_request`, store:
  - `g.supysonic_access_started_at`
  - `g.supysonic_request_id`
- In `after_request`, set:
  - `response.headers["X-Request-ID"]`
- Replace raw target logging with:
  - `path=request.path`
  - `query_keys=...`
- Use `format_log_event("access", "request", ...)`
- Keep summary routing unchanged

### Existing tests that must change

Current tests assert:

```text
[ACCESS:REST]
/rest/ping?u=root&t=abc&s=def
[ACCESS:WEB]
/page?tab=albums
```

Replace those with new assertions.

### New assertion pattern

```python
self.assertIn("access event=request", access_content)
self.assertIn("type=REST", access_content)
self.assertIn("path=/rest/ping", access_content)
self.assertIn("query_keys=s,t,u", access_content)
self.assertIn("status=200", access_content)
self.assertIn("bytes=2", access_content)
self.assertIn("duration=", access_content)
self.assertIn("request_id=", access_content)

self.assertNotIn("?u=root", access_content)
self.assertNotIn("t=abc", access_content)
self.assertNotIn("s=def", access_content)
```

### New request ID tests

```python
def test_response_includes_generated_request_id(self):
    response = client.get("/rest/ping")
    self.assertIn("X-Request-ID", response.headers)
    self.assertTrue(response.headers["X-Request-ID"])
```

```python
def test_preserves_incoming_request_id(self):
    response = client.get("/rest/ping", headers={"X-Request-ID": "client-req-1"})
    self.assertEqual(response.headers["X-Request-ID"], "client-req-1")
```

```python
def test_access_log_contains_same_request_id_as_response(self):
    response = client.get("/rest/ping")
    request_id = response.headers["X-Request-ID"]
    access_content = read_access_log()
    self.assertIn(f"request_id={request_id}", access_content)
```

### Edge cases

- blank incoming request ID
- very long incoming request ID
- incoming request ID with newline
- error response still gets header

### Definition of done

- access logs no raw query
- response always has request ID
- existing send_file test still passes
- socket connect/disconnect access logs still pass with new format

---

## Ticket P2-003: API logging helper and global error logging

### Files

```text
MODIFY supysonic/api/__init__.py
MODIFY supysonic/api/errors.py
MODIFY tests/api/test_api_logging.py
```

### Why this matters

Current API failure behavior is partly centralized in `api/errors.py`.

If only endpoint functions are instrumented, important failures will be missed:

- `ValueError`
- missing request key
- Peewee `DoesNotExist`
- unknown method
- generic server error

### Implementation tasks in `api/__init__.py`

Add:

```python
def get_request_id()
def get_api_log_context()
def log_api_event(level, event, **fields)
```

### Implementation tasks in `api/errors.py`

Add logging before returning existing error response.

Examples:

```python
@api.errorhandler(ValueError)
def value_error(e):
    log_api_event(logging.WARNING, "bad_request", reason=str(e.__class__.__name__))
    return GenericError("{0.__class__.__name__}: {0}".format(e))
```

For `BadRequestKeyError`:

```text
api event=bad_request param=<missing key if available> reason=missing_parameter
```

For `DoesNotExist`:

```text
api event=entity_not_found entity=<model name>
```

For unknown method:

```text
api event=unknown_method route=/rest/...
```

For 500:

```text
api event=server_error error_type=...
```

Use `logger.exception` only where stack trace is valuable and not too noisy.

### Test cases

```python
def test_logs_missing_auth_to_api_log(self):
    rv = self.client.get("/rest/getArtists?c=test-client&f=json")
    content = read_api_log()
    self.assertIn("api event=auth_failure", content)
    self.assertIn("reason=missing_auth", content)
```

```python
def test_logs_invalid_uuid_to_api_log(self):
    rv = self.client.get("/rest/getSong?u=alice&p=Alic3&c=test-client&id=bad-id&f=json")
    content = read_api_log()
    self.assertIn("api event=bad_request", content)
```

```python
def test_successful_get_artists_does_not_write_api_log(self):
    rv = self.client.get("/rest/getArtists?u=alice&p=Alic3&c=test-client&f=json")
    content = read_api_log()
    self.assertNotIn("api event=", content)
```

### Important

`api.log` may contain previous startup lines depending test setup.  
Tests should either:

- read log after truncating it, or
- assert absence of specific success event, not absolute emptiness.

### Definition of done

- global API failures are logged
- existing API responses unchanged
- no sensitive values in `api.log`

---

## Ticket P2-004: Endpoint-specific API logs

### Files

```text
MODIFY supysonic/api/browse.py
MODIFY supysonic/api/media.py
MODIFY supysonic/api/scan.py
MODIFY tests/api/test_api_logging.py
```

### `browse.py`

#### `/getSongs`

Current test expects natural text:

```text
Error retrieving track with ID bad-id
```

Replace with:

```text
api event=get_songs_item_failed track_id=bad-id
```

Suggested implementation:

```python
except Exception as e:
    log_api_event(
        logging.WARNING,
        "get_songs_item_failed",
        track_id=track_id,
        reason=e.__class__.__name__,
    )
```

Do not log full exception if it may contain sensitive info.

### `media.py`

#### Remove print

Current code has:

```python
print(f"eid: {eid}")
```

Remove it.

#### `/stream`

Instrument only failure and optional transcode start.

Failure examples:

- no transcoder
- OSError launching process
- missing file if detectable

Do not log every stream success.

#### `/download`

Log:

- invalid ID
- not found
- nothing to download

#### `/getCoverArt`

Log:

- cover not found
- cover file missing
- invalid size

#### `/getLyrics`

Log external ChartLyrics failure only if online lyrics is enabled.

Do not log lyrics content.

### `scan.py`

#### `/startScan`

On success:

```text
api event=scan_requested result=queued scanning=true count=0
```

On daemon unavailable:

```text
api event=scan_request_failed result=failed reason=daemon_unavailable
```

#### `/getScanStatus`

Only log daemon unavailable.

### Tests

Use mocking:

- patch `DaemonClient` to raise `DaemonUnavailableError`
- patch cover path function to return missing path
- patch transcoder config to force no transcoder path

### Definition of done

- high-value API failures have structured logs
- success spam avoided

---

## Ticket P2-005: Emo WebSocket logs

### Files

```text
MODIFY supysonic/emo/ws.py
MODIFY tests/base/test_emo_logging.py
```

### Current tests assert old text

Current test expects:

```text
emo auth login succeeded user=alice
emo device registered user=alice client_id=player-1 session_id=sess-1
```

Replace with:

```text
emo event=auth_login result=success user=alice
emo event=device_register result=success user=alice client_id=player-1 session_id=sess-1
```

### Add helper

```python
def _log_emo_event(level, event, **fields):
    logger.log(level, format_log_event("emo", event, **fields))
```

### Message validation logs

Instrument these branches:

- message not dict
- missing action
- payload not dict
- unauthenticated action
- unsupported action

### Auth logs

Success:

```text
emo event=auth_login result=success user=alice client_request_id=auth-1
```

Failure:

```text
emo event=auth_login result=failure user=alice client_request_id=auth-1 reason=invalid_credentials
```

No password value.

### Device logs

Success:

```text
emo event=device_register result=success user=alice client_id=player-1 session_id=sess-1 roles=player client_request_id=register-1
```

### Queue logs

For `queue.local.set`, assert:

```python
self.assertIn("emo event=queue_local_set", content)
self.assertIn("queue_size=2", content)
self.assertNotIn("song-id-1", content)
self.assertNotIn("song-id-2", content)
```

### Control logs

Use two socket clients:

- client A registers as controller
- client B registers as player
- A sends `player.pause` to B

Assert:

```text
emo event=control_forward result=success action=player.pause source_client_id=controller target_client_id=player
```

Target offline test:

- send command to nonexistent target
- expect `result=not_found`

Cross-user test may be more complex; optional if existing state helper makes it difficult.

### Definition of done

- key=value logs
- no queue ID leakage
- client requestId captured

---

## Ticket P2-006: HTTP Emo logs

### Files

```text
MODIFY supysonic/emo/__init__.py
MODIFY supysonic/emo/client.py
```

### Required events

Auth failures in `emo/__init__.py` should mirror API auth failures:

```text
emo event=auth_failure result=failure user=alice reason=wrong_credentials
```

`client.py` upload/view/download failures:

```text
emo event=upload_log_failed result=bad_request reason=no_file_part
emo event=upload_log_failed result=bad_request reason=empty_filename
emo event=upload_log_failed result=server_error reason=save_failed
emo event=view_log_failed result=not_found filename=...
emo event=download_log_failed result=not_found filename=...
```

Do not log uploaded file content.

---

## Ticket P2-007: Scanner lifecycle logs

### Files

```text
MODIFY supysonic/scanner_func/scanner_runtime.py
MODIFY supysonic/scanner_func/scanner_folder.py
CREATE tests/base/test_scanner_logging.py
MODIFY tests/base/test_scanner_helpers.py
```

### `scanner_runtime.py`

Current tests assert:

```python
fake_logger.info.assert_any_call("begin to find all covers")
fake_logger.info.assert_any_call("scan summary scanned=%s ...", ...)
```

Replace with key=value assertions.

Possible implementation:

```python
logger.info(format_log_event(
    "scanner",
    "run_start",
    trigger=getattr(scanner, "trigger", "unknown"),
    queued_folders="unknown",
    force=getattr(scanner, "force_scan", "-"),
    follow_symlinks=getattr(scanner, "follow_symlinks", "-"),
))
```

At summary:

```python
logger.info(format_log_event(
    "scanner",
    "run_end",
    scanned=stats.scanned,
    existing_tracks=stats.existing_tracks,
    added_artists=stats.added.artists,
    added_albums=stats.added.albums,
    added_tracks=stats.added.tracks,
    deleted_artists=stats.deleted.artists,
    deleted_albums=stats.deleted.albums,
    deleted_tracks=stats.deleted.tracks,
    errors=len(stats.errors),
))
```

### `scanner_folder.py`

Current code logs:

```text
Scanning folder %s
```

Replace/add:

```text
scanner event=folder_start folder=root path=/music
scanner event=folder_end folder=root path=/music duration=...
```

Folder skip is in runtime when `Folder.DoesNotExist`.

Add there:

```text
scanner event=folder_skip folder=... reason=not_found
```

### Tests

Create direct unit tests using fake logger.

Example:

```python
messages = []
fake_logger = SimpleNamespace(info=lambda message, *args: messages.append(message % args if args else message))
...
self.assertTrue(any("scanner event=run_end" in m for m in messages))
```

Better: if using `Mock`, assert substrings from call args:

```python
logged = "\n".join(str(call.args[0]) for call in fake_logger.info.call_args_list)
self.assertIn("scanner event=run_end", logged)
self.assertIn("scanned=7", logged)
```

### Definition of done

- scanner lifecycle logs are structured
- tests no longer expect old natural text
- stop_requested path logs `run_stopped`

---

## Ticket P2-008: Task manager key=value

### Files

```text
MODIFY supysonic/TaskManger.py
MODIFY tests/base/test_task_manager.py
```

### Required logs

```text
task event=submitted task_id=...
task event=started task_id=...
task event=completed task_id=... duration=...
task event=failed task_id=... duration=... error_type=...
```

### Tests

Assert key=value lines in `task.log`.

---

# 3. Phase 3 Deep Implementation Notes

## Ticket P3-001: Shared category logging refactor

### Files

```text
MODIFY supysonic/logging_manager.py
MODIFY tests/base/test_logging_manager.py
CREATE tests/base/test_daemon_logging.py
```

### Key rule

Do not break `configure_web_logging`.

Current Web tests expect six files. Keep that.

### Add generic function

```python
def configure_category_logging(
    config,
    logger_name="supysonic",
    categories=None,
    route_prefixes=None,
):
    ...
```

### Web should call generic

```python
def configure_web_logging(config, logger_name="supysonic"):
    return configure_category_logging(
        config,
        logger_name=logger_name,
        categories=("summary", "access", "task", "emo", "scanner", "api"),
        route_prefixes=_build_web_route_prefixes(logger_name),
    )
```

### Daemon should call generic

```python
def configure_daemon_logging(config, logger_name="supysonic"):
    ...
```

### Test web compatibility

Existing file list test should still pass:

```text
access.log
api.log
emo.log
scanner.log
supysonic.log
task.log
```

Daemon test separately expects:

```text
daemon.log
watcher.log
scanner.log
supysonic.log
```

---

## Ticket P3-002: Config migration

### Files

```text
MODIFY supysonic/config.py
MODIFY config.sample
```

Add to `DefaultConfig.DAEMON`:

```python
"log_dir": None,
"log_backup_count": 7,
```

Keep:

```python
"log_file": None,
```

### Tests

In daemon logging tests:

```python
config = {
    "log_file": os.path.join(tmpdir, "old-daemon.log"),
    "log_rotate": False,
    "log_level": "INFO",
}
configure_daemon_logging(config, logger_name=...)
```

Assert logs appear in `tmpdir`.

---

## Ticket P3-003: Replace daemon setup_logging

### Files

```text
MODIFY supysonic/daemon/__init__.py
```

### Current helpers to remove if unused

- `_MinLevelFilter`
- `_has_console_handler`
- `_has_file_handler`
- `_get_debug_log_file`

### Keep wrapper

```python
def setup_logging(config):
    configure_daemon_logging(config, logger_name="supysonic")
```

### Test

Patch `supysonic.daemon.configure_daemon_logging` if imported directly, or inspect handlers after `setup_logging`.

---

## Ticket P3-004: Daemon lifecycle logs

### Files

```text
MODIFY supysonic/daemon/__init__.py
MODIFY supysonic/daemon/server.py
```

### Exact locations

#### `daemon/__init__.py main()`

After `setup_logging(config.DAEMON)`:

```text
daemon event=start socket=... watcher=... log_level=...
```

Around `daemon.run()`:

```text
daemon event=crash
```

#### `__terminate`

Log:

```text
daemon event=stop signal=...
```

#### `Daemon.run()`

After Listener:

```text
daemon event=listening socket=...
```

After watcher start:

```text
daemon event=watcher_started
```

Optional if using watcher domain only; prefer watcher domain in watcher file.

#### `Daemon.__handle_connection`

Unknown command:

```text
daemon event=unknown_command command_type=...
```

#### `Daemon.start_scan`

At function entry:

```text
daemon event=scan_requested folders=... force=...
```

If scanner alive:

```text
daemon event=scan_queued reason=scanner_already_running
```

If starting scanner:

```text
daemon event=scan_started folders=... force=...
```

#### `Daemon.terminate`

Log begin/end and components stopped.

---

## Ticket P3-005: Watcher logs

### Files

```text
MODIFY supysonic/watcher.py
```

### Where to log

#### `SupysonicWatcher.start`

```text
watcher event=start delay=...
```

After each folder add, `add_folder` logs separately.

#### `SupysonicWatcher.stop`

```text
watcher event=stop
```

#### `add_folder`

```text
watcher event=folder_watch_added path=...
```

#### `remove_folder`

```text
watcher event=folder_watch_removed path=...
```

#### Event handler methods

`on_created`, `on_deleted`, `on_modified`, `on_moved`

Use DEBUG:

```text
watcher event=file_event_queued action=created path=... op=scan,create
```

#### `ScannerProcessingQueue.put`

Use DEBUG or INFO depending noise decision:

```text
watcher event=scan_scheduled path=... delay=... op=...
```

#### `ScannerProcessingQueue.__run`

Before processing:

```text
watcher event=queue_processing_start pending=...
```

#### item processors

Existing logs:

- Moving
- Scanning
- Removing
- Looking for covers
- Potentially adding cover
- Removing cover
- Moving cover
- Looking for nfo
- Potentially adding nfo
- Removing nfo
- Moving nfo

Convert to key=value.

---

# 4. Failure-Injection Test Recipes

## 4.1 API daemon unavailable

Patch:

```python
with patch("supysonic.api.scan.DaemonClient") as daemon_client:
    daemon_client.side_effect = DaemonUnavailableError("unavailable")
```

Assert:

```text
api event=scan_request_failed
reason=daemon_unavailable
```

## 4.2 Cover art missing

Patch `__new_get_cover_path` or create DB state causing missing cover.

Assert:

```text
api event=cover_art_failed
reason=not_found
```

## 4.3 Invalid query value

Call:

```text
/rest/getSong?id=not-a-uuid
```

Assert:

```text
api event=bad_request
```

## 4.4 Queue ID leak test

Send:

```python
"queueSongIds": ["secret-song-id-1", "secret-song-id-2"]
```

Assert:

```python
self.assertNotIn("secret-song-id-1", content)
self.assertNotIn("secret-song-id-2", content)
self.assertIn("queue_size=2", content)
```

## 4.5 Access raw query leak test

Request:

```text
/rest/ping?u=alice&t=secret-token&s=secret-salt&c=test-client
```

Assert:

```python
self.assertNotIn("secret-token", access_content)
self.assertNotIn("secret-salt", access_content)
self.assertNotIn("?u=alice", access_content)
self.assertIn("query_keys=c,s,t,u", access_content)
```

---

# 5. Final Engineering Notes

## 5.1 Do not chase 100% endpoint coverage in first PR

The target is high-value logging coverage, not logging every possible exception branch.

Prioritize:

1. auth failures
2. bad request
3. not found
4. media failures
5. scan failures
6. websocket control/session/queue failures

## 5.2 Avoid broad exception wrapping

Do not add:

```python
try:
    entire_endpoint()
except Exception as e:
    log
    raise
```

unless there is already such broad handling.

Prefer logging in existing branch points.

## 5.3 Do not add new dependencies

Use Python stdlib only.

## 5.4 Use existing test style

The project uses `unittest`, temp dirs, sqlite temp DBs, and `unittest.mock.patch`.

Follow that style.

## 5.5 Be careful with logger names in tests

Existing tests often use custom logger names like:

```text
supysonic.test.access
supysonic.test.logging
```

When adding routing tests, use custom logger names to avoid contaminating global `supysonic` handlers.

## 5.6 Clean up handlers

Tests should restore logger handlers and close file handlers.

Follow existing patterns in:

```text
tests/base/test_access_logging.py
tests/base/test_logging_manager.py
```

---

# 6. Final Sign-off Checklist for Local Engineer

Before saying the logging system is complete:

## Web / access

- [ ] every HTTP response has `X-Request-ID`
- [ ] incoming request ID is preserved safely
- [ ] access log has key=value
- [ ] access log has no raw query
- [ ] access log has query_keys
- [ ] send_file/direct_passthrough still works

## API

- [ ] auth failures logged
- [ ] bad requests logged
- [ ] not found logged
- [ ] media failures logged
- [ ] scan failures logged
- [ ] normal successful reads not logged to api.log
- [ ] no secrets logged

## Emo

- [ ] auth success/failure logged
- [ ] device register logged
- [ ] unauthorized actions logged
- [ ] subscribe/unsubscribe logged
- [ ] control forward success/failure logged
- [ ] queue summary logged
- [ ] queue song IDs not logged

## Scanner/task

- [ ] scanner run start/end logged
- [ ] folder start/end logged
- [ ] stop requested logged
- [ ] task lifecycle key=value

## Daemon/watcher

- [ ] daemon logging uses logging_manager
- [ ] daemon.log routes correctly
- [ ] watcher.log routes correctly
- [ ] scanner.log receives daemon scanner logs
- [ ] old daemon log_file fallback works
- [ ] no duplicate handlers

## Docs/config

- [ ] config.sample updated
- [ ] docs updated
- [ ] old log_file documented as compatibility-only

## Tests

- [ ] focused tests pass
- [ ] regression tests pass
- [ ] py_compile passes
- [ ] manual validation completed
