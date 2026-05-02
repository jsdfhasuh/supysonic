# Metadata Review Tracks Editor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the metadata review `Tracks` tab so it keeps the approved album header and right rail while replacing the middle track editor with a `fbc2687e4c1d4a8091bedf504e6d96cb`-style sequence-and-focused-editor workspace.

**Architecture:** Keep the backend contract unchanged and move the redesign into the template and CSS layer. Preserve the approved album header and right rail structure, then replace only the middle track editor area with a continuous scroll layout that keeps the current save selectors and artist autocomplete hooks intact.

**Tech Stack:** Jinja2 templates, project CSS, Flask frontend tests with `unittest`

---

### Task 1: Lock the continuous editor render contract

**Files:**
- Modify: `tests/frontend/test_metadata_review_workspace.py`

**Step 1: Write the failing test**

- Add assertions against `GET /metadata/review-tasks/<task_id>?section=tracks` for the new continuous editor layout.
- Assert the response contains stable structure markers for:
  - the stronger album context header
  - the continuous track editor list container
  - at least one visible track editor row
  - the core metadata group

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace.MetadataReviewWorkspaceTestCase.test_review_workspace_honors_requested_section`

Expected: FAIL because the current stacked row editor does not render the new continuous-editor markers.

**Step 3: Keep the test honest**

- Do not assert on exact CSS values.
- Do not assert on unrelated page chrome.
- Prefer stable `data-*` markers and section headings over brittle whitespace or text formatting.

**Step 4: Re-run after implementation**

Run the same command again after the template and CSS changes.

Expected: PASS.

### Task 2: Replace the stacked row editor with a continuous scroll editor

**Files:**
- Modify: `supysonic/templates/partials/metadata-review-tracks-panel.html`

**Step 1: Keep the album context block but strengthen it**

- Continue rendering `reviewSummary.cover_art_url`, album title, artist, year, track count, and total duration.
- Rework the structure so the cover and album title read more like the `fbc...` reference.
- Keep the helper copy scoped to metadata review.

**Step 2: Replace the current editor list wrapper**

- Remove the stacked `data-review-track-editor-row` card treatment as the primary layout.
- Render a left sequence list plus a right focused editor panel for the selected track.
- Use explicit structure markers such as:

```html
<div class="metadata-review-track-studio" data-review-track-studio>
  <div class="metadata-review-track-sequence" data-review-track-sequence>
    <button type="button" data-review-track-sequence-item>...</button>
  </div>
  <section data-review-track-editor-panel data-review-track-row>
    ...
  </div>
```

**Step 3: Keep field scope minimal**

- Render only the real editable fields:
  - `number`
  - `title`
  - `artist_name`
- Render `duration` as read-only display content.
- `album` may appear as a read-only context note inside the focused editor.
- Do not add fake editable inputs for genre, year, ISRC, language, composer, lyricist, or comments.

**Step 4: Preserve the existing save hooks**

- Keep `data-review-track-row` on each logical track item.
- Keep `data-track-number` on the number input.
- Keep `data-track-title` on the title input.
- Keep `data-track-artist` on the artist input.
- Keep the autocomplete suggestion container inside the focused editor.
- Ensure the selected-track switcher does not interfere with form submission.

### Task 3: Style the revised split-reference layout

**Files:**
- Modify: `supysonic/static/css/metadata.css`

**Step 1: Strengthen the album header surface**

- Increase visual emphasis on the cover, title, and metadata chips.
- Keep the header block visually closer to `fbc...` than to the current compact editor header.

**Step 2: Add continuous editor row styling**

- Style each row as a dense, scannable editor surface.
- Keep number compact, title dominant, artist secondary, and duration easy to scan.
- Remove any reliance on collapse state styling.

**Step 3: Add responsive behavior**

- Ensure visible track editor rows wrap cleanly on narrow screens.
- Ensure inputs stack without horizontal scrolling under normal content lengths.
- Avoid making the right rail a prerequisite for editing tracks on mobile.

### Task 4: Verify client-side track editing still works with the new markup

**Files:**
- Verify: `supysonic/templates/metadata-review-task.html`
- Modify only if needed: `supysonic/templates/metadata-review-task.html`

**Step 1: Check the current submit and autocomplete hooks against the new DOM**

- Confirm the track-save collection still discovers all visible `data-review-track-row` containers.
- Confirm each row still exposes `data-track-number`, `data-track-title`, and `data-track-artist`.
- Confirm the artist suggestion container remains reachable from the artist input.

**Step 2: Make the smallest JS adjustment only if the new continuous DOM breaks traversal**

- Do not rewrite the submission flow unless the new DOM proves it necessary.
- If a change is required, keep it scoped to DOM selection only.

**Step 3: Re-run the focused frontend review tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace tests.frontend.test_metadata_review_actions`

Expected: PASS.

### Task 5: Run verification and patch hygiene checks

**Files:**
- Verify: `tests/frontend/test_metadata_review_workspace.py`
- Verify: `tests/frontend/test_metadata_review_actions.py`

**Step 1: Run the focused render test**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace.MetadataReviewWorkspaceTestCase.test_review_workspace_honors_requested_section`

Expected: PASS.

**Step 2: Run the workspace regression set**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace tests.frontend.test_metadata_review_actions tests.frontend.test_metadata_inbox tests.frontend.test_metadata_form tests.frontend.test_device_cover`

Expected: PASS.

**Step 3: Check patch formatting**

Run: `git diff --check -- docs/plans/2026-05-02-metadata-review-accordion-track-editor-design.md docs/plans/2026-05-02-metadata-review-accordion-track-editor.md supysonic/templates/partials/metadata-review-tracks-panel.html supysonic/static/css/metadata.css tests/frontend/test_metadata_review_workspace.py`

Expected: no output.
