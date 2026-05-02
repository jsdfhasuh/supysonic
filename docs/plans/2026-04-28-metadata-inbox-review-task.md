# Metadata Inbox Review Task Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an album-based metadata inbox with a scoped review workspace so each task is tied to one album while allowing edits to that album, its tracks, and its related artists.

**Architecture:** Add a persistent `AlbumReviewTask` model plus schema migrations, collect newly created albums during scanning, and create review tasks after scan post-processing completes. Replace the current empty Inbox with a real task list, then add a dedicated task detail workspace that is scoped to exactly one album and reuses existing album and artist edit behaviors without exposing global album or artist walls.

**Tech Stack:** Python, Flask, Peewee, unittest, Jinja templates, existing Supysonic metadata frontend.

---

### Task 1: Add the review task schema

**Files:**
- Modify: `supysonic/db.py`
- Modify: `supysonic/schema/migration/sqlite/20260327.sql` or create next dated migration if needed
- Modify: `supysonic/schema/migration/mysql/20260327.sql` or create next dated migration if needed
- Modify: `supysonic/schema/migration/postgres/20260327.sql` or create next dated migration if needed
- Test: `tests/frontend/test_metadata_workspace.py`

**Step 1: Write the failing test**

Add a template regression test that asserts the Inbox no longer only shows the empty placeholder and that task-oriented strings such as `Review`, `Confirm`, and `Dismiss` appear in the metadata workspace template path once wired.

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.frontend.test_metadata_workspace`
Expected: FAIL because Inbox is still static.

**Step 3: Write minimal implementation**

Add `AlbumReviewTask` in `supysonic/db.py` with fields:
- `id`
- `album` foreign key to `Album`
- `task_type`
- `status`
- `reason`
- `snapshot_json`
- `created`
- `updated`
- `resolved_at`

Keep the first version intentionally narrow:
- `task_type = metadata_review`
- `reason = new_album`
- `status in pending, confirmed, dismissed, expired`

Add indexes for:
- `album + status`
- `status + created`

Add schema migration SQL for sqlite/mysql/postgres and bump `SCHEMA_VERSION` in `supysonic/db.py`.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.frontend.test_metadata_workspace`
Expected: still failing for Inbox strings until later tasks, but schema code must import and compile cleanly.

### Task 2: Add task creation helpers and scanner integration points

**Files:**
- Create: `supysonic/scanner_func/scanner_review_tasks.py`
- Modify: `supysonic/scanner_func/scanner_pipeline.py`
- Modify: `supysonic/scanner_func/scanner_runtime.py`
- Test: `tests/base/test_scanner_helpers.py`

**Step 1: Write the failing test**

Add scanner helper tests covering:
- a newly created album is recorded as a candidate during scan
- only one open task is created for an album
- a closed task allows a new task on later scan

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.base.test_scanner_helpers`
Expected: FAIL because task collection and creation helpers do not exist.

**Step 3: Write minimal implementation**

Create helpers in `supysonic/scanner_func/scanner_review_tasks.py`:
- `rememberNewAlbum(scanner, album)`
- `buildAlbumReviewSnapshot(album)`
- `createAlbumReviewTasks(scanner)`

Rules:
- collect album ids on the scanner instance for the current run
- never create tasks during single-file persistence
- create tasks only after scan traversal and metadata repair have stabilized album state
- skip creation if an existing `pending` task exists for the album
- create a new task if previous tasks are only `confirmed`, `dismissed`, or `expired`

Wire collection from `supysonic/scanner_func/scanner_pipeline.py` at the point where an album is first created or discovered as new.

Call task generation from `supysonic/scanner_func/scanner_runtime.py` after `scanner.find_lost_information()` and before `scanner.handle_done()`.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.base.test_scanner_helpers`
Expected: PASS.

### Task 3: Add metadata review query and status actions

**Files:**
- Create: `supysonic/frontend/metadata_review.py`
- Modify: `supysonic/frontend/metadata.py`
- Test: `tests/frontend/test_metadata_review.py`

**Step 1: Write the failing test**

Add tests for:
- listing Inbox tasks by status
- confirming a pending task
- dismissing a pending task
- rejecting invalid task ids or already resolved state transitions as appropriate

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.frontend.test_metadata_review`
Expected: FAIL because the helper module and routes do not exist.

**Step 3: Write minimal implementation**

Create `supysonic/frontend/metadata_review.py` with focused helpers:
- `listMetadataReviewTasks(status=None)`
- `getMetadataReviewTask(taskId)`
- `confirmMetadataReviewTask(task)`
- `dismissMetadataReviewTask(task)`

Update `supysonic/frontend/metadata.py` to add POST routes for:
- `/metadata/review-tasks/<task_id>/confirm`
- `/metadata/review-tasks/<task_id>/dismiss`

Keep responses simple JSON for task actions.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.frontend.test_metadata_review`
Expected: PASS.

### Task 4: Replace static Inbox with a real task list

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Modify: `supysonic/templates/metadata-workspace.html`
- Create: `supysonic/templates/partials/metadata-inbox-content.html`
- Test: `tests/frontend/test_metadata_workspace.py`

**Step 1: Write the failing test**

Expand template tests to assert:
- Inbox renders task list markup
- filter chips exist
- task actions `Review`, `Confirm`, `Dismiss` exist
- empty state still exists when there are no tasks

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.frontend.test_metadata_workspace`
Expected: FAIL because Inbox is still static.

**Step 3: Write minimal implementation**

Refactor `metadata-workspace.html` so Inbox includes `partials/metadata-inbox-content.html`.

Render the chosen Stitch-inspired structure:
- vertical task list
- album cover, album name, artist, year, track count, created time, pending badge
- issue hints
- actions `Review`, `Confirm`, `Dismiss`
- compact filter chips
- small summary panel

Do not add full SPA behavior. Use server-rendered HTML with minimal form posts or button actions.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.frontend.test_metadata_workspace`
Expected: PASS.

### Task 5: Build the scoped album review workspace

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Create: `supysonic/templates/metadata-review-task.html`
- Create: `supysonic/templates/partials/metadata-review-album-panel.html`
- Create: `supysonic/templates/partials/metadata-review-tracks-panel.html`
- Create: `supysonic/templates/partials/metadata-review-artists-panel.html`
- Modify: `supysonic/static/css/metadata.css`
- Test: `tests/frontend/test_metadata_review_workspace.py`

**Step 1: Write the failing test**

Add tests asserting the review workspace contains:
- breadcrumb metadata / inbox / review task
- scoped warning text
- tabs `Album`, `Tracks`, `Artists`
- task-level actions `Confirm Task` and `Dismiss Task`
- no full-library wall markers such as `Loading album data...` or `Loading artist data...`

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.frontend.test_metadata_review_workspace`
Expected: FAIL because the page does not exist.

**Step 3: Write minimal implementation**

Add a GET route such as `/metadata/review-tasks/<task_id>`.

Render a page based on the chosen Stitch screen:
- task header with album summary
- three tabs scoped only to this album
- right-side sticky review summary card
- task scope warning strip

For the first implementation, scope data as follows:
- Album tab: only the task album
- Tracks tab: only tracks for the task album
- Artists tab: only the album artist plus any related track artists

Reuse existing save behavior where possible, but do not route the user back into the global album wall or artist wall.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.frontend.test_metadata_review_workspace`
Expected: PASS.

### Task 6: Connect review workspace editing actions to existing metadata flows

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Modify: `supysonic/frontend/metadata_actions.py`
- Modify: `supysonic/templates/partials/metadata-review-album-panel.html`
- Modify: `supysonic/templates/partials/metadata-review-tracks-panel.html`
- Modify: `supysonic/templates/partials/metadata-review-artists-panel.html`
- Test: `tests/frontend/test_metadata_review_actions.py`

**Step 1: Write the failing test**

Add tests covering task-scoped edits:
- album fields update from the review page
- track rows update only for the current album
- artist metadata updates from the review page target only related artists

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.frontend.test_metadata_review_actions`
Expected: FAIL because the review workspace is read-only or missing submit handlers.

**Step 3: Write minimal implementation**

Add narrow POST handlers or helper calls for:
- album updates
- track updates
- artist metadata / primary artist updates

Keep the scope bounded to the current task album and its related entities. Reject unrelated ids.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.frontend.test_metadata_review_actions`
Expected: PASS.

### Task 7: Focused verification

**Files:**
- Modify as needed based on failures

**Step 1: Run focused review-task tests**

Run: `python -m unittest tests.base.test_scanner_helpers tests.frontend.test_metadata_workspace tests.frontend.test_metadata_review tests.frontend.test_metadata_review_workspace tests.frontend.test_metadata_review_actions`
Expected: PASS.

**Step 2: Run existing metadata regressions**

Run: `python -m unittest tests.frontend.test_metadata tests.frontend.test_metadata_actions tests.frontend.test_metadata_form`
Expected: PASS.

**Step 3: Run syntax verification**

Run: `python -m py_compile "/workspace/supysonic/supysonic/db.py" "/workspace/supysonic/supysonic/frontend/metadata.py" "/workspace/supysonic/supysonic/frontend/metadata_review.py" "/workspace/supysonic/supysonic/scanner_func/scanner_review_tasks.py"`
Expected: no output.

**Step 4: Document verification results**

Record exactly which commands passed, what remains unverified, and any schema-migration caveats.
