# Metadata Logging Design

**Goal:** Add structured audit logs for metadata editing workflows and route them to a dedicated `metadata.log` file without changing existing access logging behavior.

**Scope**
- Add `metadata.log` to Web log file management.
- Route `supysonic.frontend.metadata` logger output to `metadata.log`.
- Emit structured business logs for metadata write endpoints only.
- Keep `access.log` as the request-level source of truth for all metadata HTTP traffic.

**Out of Scope**
- No new logging framework.
- No changes to GET-only metadata pages or artist autocomplete.
- No logging of biography text, uploaded image contents, passwords, tokens, or other large/sensitive payloads.

**Architecture**
- Reuse `format_log_event()` for structured `key=value` logging.
- Keep summary logging unchanged so metadata events still appear in `supysonic.log`.
- Add a tiny metadata-local helper in `supysonic/frontend/metadata.py` to attach shared context:
  - `request_id`
  - `user`
  - `path`

**Event Coverage**
- `metadata event=review_album_update`
- `metadata event=review_tracks_update`
- `metadata event=review_artist_update`
- `metadata event=review_task_confirm`
- `metadata event=review_task_dismiss`
- `metadata event=artist_form_update`

**Testing Strategy**
- Extend `tests/base/test_logging_manager.py` for file creation and logger routing.
- Extend existing frontend metadata tests to assert representative metadata audit events.
- Verify dedicated `metadata.log` output and summary log propagation.

**Risk Notes**
- `review_tracks_update` is not transactional, so failure logs should include progress summary instead of claiming an all-or-nothing result.
- Existing metadata behavior should remain unchanged; this work is logging-only.
