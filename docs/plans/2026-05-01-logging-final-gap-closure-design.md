# Logging Final Gap Closure Design

**Goal:** Close the remaining structured logging gaps so the implementation aligns with the current logging blueprint without changing the existing logging infrastructure.

**Scope:**
- Keep the current logging manager, file layout, request ID behavior, and rotation strategy.
- Add missing high-value structured log events in `emo`, `api`, and `scanner`.
- Add or extend targeted unit tests for each newly logged path.

**Out of Scope:**
- No new log files, handlers, or routing rules.
- No broad refactor of unrelated business logic.
- No forced implementation of blueprint events that do not map cleanly to the current runtime flow.

## Approach

### 1. Emo gap closure

Add structured logging for currently unlogged but meaningful websocket paths:
- `bad_message`
- `unauthorized_action`
- `unsupported_action`
- `playback_update`
- `queue_local_get`
- `queue_session_sync`
- `queue_ready_complete`
- failed action outcomes that currently only send websocket errors: `forbidden`, `not_found`, `bad_request`

Rules:
- Keep payload summaries compact.
- Never log passwords.
- Never log full queue song ID lists when a size/count summary is enough.

### 2. API media gap closure

Add structured logging only to existing high-value media error and action paths that are already represented in the blueprint and have obvious runtime meaning:
- `media_stream_failed`
- `download_failed`
- `cover_art_failed`
- `lyrics_external_failed`
- `transcode_started` when an actual transcode path is entered and the signal is reliable

Rules:
- Prefer failure logs first.
- Include request context and the smallest useful identifiers.
- Avoid speculative event names on ambiguous code paths.

### 3. Scanner lifecycle closure

Add `run_stopped` when a stop request aborts the scanner before post-processing completes.

Evaluate blueprint events:
- `folder_skip`
- `metadata_stage_start`
- `metadata_stage_end`
- `review_tasks_created`

Implement only if there is a real, stable hook in current code. If not, document why they remain intentionally absent after this pass.

## Testing Strategy

- Extend existing focused test modules instead of creating broad new suites.
- Verify log content by reading the category log files.
- Keep regression tests narrow and tied to the newly added event paths.
- Re-run the existing broad logging regression suite after targeted tests pass.

## Success Criteria

- Remaining high-value logging gaps in `emo`, `api`, and `scanner` are either implemented or explicitly ruled out with code-based justification.
- No changes to current file routing or rotation behavior.
- Relevant logging tests pass.
