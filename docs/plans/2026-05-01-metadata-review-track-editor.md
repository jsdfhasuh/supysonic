# Metadata Review Track Editor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the metadata review `Tracks` tab into a context-rich inline editing workbench while keeping the same editable fields and save behavior.

**Architecture:** Keep all track save behavior in the existing review-task endpoint and only redesign the presentation layer for the `Tracks` panel. Use a test-first approach: lock the new panel structure with frontend render tests, then make the smallest template and CSS changes needed to satisfy the new layout.

**Tech Stack:** Jinja2 templates, project CSS, Flask frontend tests with `unittest`

---

### Task 1: Lock the new tracks panel contract

**Files:**
- Modify: `tests/frontend/test_metadata_review_workspace.py`

**Step 1: Write the failing test**

- Add assertions against `GET /metadata/review-tasks/<task_id>?section=tracks` for the new tracks-panel structure.
- Assert the response contains layout markers for:
  - the compact track context header
  - the stacked editor list
  - inline editable title and artist fields

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace.MetadataReviewWorkspaceTestCase.test_review_workspace_honors_requested_section`

Expected: FAIL because the old table layout does not render the new markers.

**Step 3: Keep the test focused**

- Do not assert on unrelated page chrome.
- Do not assert on exact CSS values.
- Prefer stable class names/structure markers over fragile formatting text.

**Step 4: Re-run after implementation**

Run the same command again after the template/CSS work.

Expected: PASS.

### Task 2: Replace the table with a track editor workbench

**Files:**
- Modify: `supysonic/templates/partials/metadata-review-tracks-panel.html`

**Step 1: Add the compact track context header**

- Render album cover using `reviewSummary.cover_art_url`.
- Render album name, artist, year, track count, and total duration.
- Keep copy scoped to metadata review, not transcoding.

**Step 2: Replace the bordered table**

- Remove the table-based layout.
- Render a stacked editor list where each row contains:
  - editable `number`
  - editable `title`
  - editable `artist`
  - read-only `duration`

**Step 3: Preserve current field semantics**

- Keep existing `data-track-number`
- Keep existing `data-track-title`
- Keep existing `data-track-artist`
- Keep existing `data-review-track-row`
- Keep the autocomplete suggestion container

**Step 4: Preserve save action**

- Keep the form action pointing at `frontend.update_metadata_review_task_tracks`.
- Keep the `Save track changes` button semantics.

### Task 3: Style the new panel with minimal CSS changes

**Files:**
- Modify: `supysonic/static/css/metadata.css`

**Step 1: Add track-workbench container styles**

- Add styles for the compact header block.
- Add styles for track metadata chips.
- Add styles for the stacked editor surface.

**Step 2: Add row editor styles**

- Create rounded row cards.
- Use subtle hover/background states instead of table borders.
- Make the number field compact.
- Make the title field visually dominant.
- Keep artist input visually secondary.
- Keep duration right-aligned.

**Step 3: Add responsive behavior**

- Ensure the row layout collapses cleanly on narrow screens.
- Avoid horizontal overflow for normal track titles.

### Task 4: Verify the refreshed review workspace

**Files:**
- Verify: `tests/frontend/test_metadata_review_workspace.py`
- Verify: `tests/frontend/test_metadata_review_actions.py`

**Step 1: Run the focused render test**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace.MetadataReviewWorkspaceTestCase.test_review_workspace_honors_requested_section`

Expected: PASS.

**Step 2: Run the workspace and action regressions**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace tests.frontend.test_metadata_review_actions`

Expected: PASS.

**Step 3: Check patch formatting**

Run: `git diff --check -- docs/plans/2026-05-01-metadata-review-track-editor-design.md docs/plans/2026-05-01-metadata-review-track-editor.md supysonic/templates/partials/metadata-review-tracks-panel.html supysonic/static/css/metadata.css tests/frontend/test_metadata_review_workspace.py`

Expected: no output.

### Task 5: Optional follow-up after visual pass

**Files:**
- Review only: `supysonic/templates/metadata-review-task.html`

**Step 1: Decide if page-level summary spacing needs adjustment**

- Only touch the outer page template if the new tracks panel creates obvious imbalance.
- Do not expand scope into album/artists panel redesign unless separately requested.
