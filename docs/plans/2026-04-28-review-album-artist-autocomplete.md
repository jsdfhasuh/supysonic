# Review Album Artist Autocomplete Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add live library-backed artist suggestions while editing the album artist in the metadata review task.

**Architecture:** Add a small frontend route that returns matching artist names from the library, then wire the album artist input in the review task page to fetch and render a lightweight suggestion list. Keep the implementation scoped to the album review form so it stays minimal and reusable later.

**Tech Stack:** Flask, Peewee, Jinja2, vanilla JavaScript, unittest

---

### Task 1: Add failing tests for suggestions endpoint and UI hooks

**Files:**
- Modify: `tests/frontend/test_metadata_review.py`
- Modify: `tests/frontend/test_metadata_review_workspace.py`

**Step 1: Write the failing test**
- Add a route-level test for a new metadata artist suggestions endpoint.
- Add a template test asserting the review page exposes autocomplete hooks for the album artist field.

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review tests.frontend.test_metadata_review_workspace`

Expected: FAIL because the endpoint and hooks do not exist yet.

### Task 2: Implement the suggestions endpoint

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Test: `tests/frontend/test_metadata_review.py`

**Step 1: Write minimal implementation**
- Add a GET endpoint that accepts `q` and returns matching artist names.
- Prefer prefix matches first, then fuzzy contains matches, and cap the result count.

**Step 2: Run targeted tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review`

Expected: PASS.

### Task 3: Implement album artist autocomplete UI

**Files:**
- Modify: `supysonic/templates/partials/metadata-review-album-panel.html`
- Modify: `supysonic/templates/metadata-review-task.html`
- Test: `tests/frontend/test_metadata_review_workspace.py`

**Step 1: Write minimal implementation**
- Add suggestion container markup under the album artist input.
- Add vanilla JS to fetch suggestions while typing, render the list, and fill the input when an item is chosen.
- Do not enable interactions when the review task is read-only.

**Step 2: Run targeted tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace`

Expected: PASS.

### Task 4: Run regression coverage

**Files:**
- Test: `tests/frontend/test_metadata_review.py`
- Test: `tests/frontend/test_metadata_review_workspace.py`
- Test: `tests/frontend/test_metadata_review_actions.py`
- Test: `tests/frontend/test_metadata_inbox.py`
- Test: `tests/frontend/test_metadata_workspace.py`

**Step 1: Run regression tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review tests.frontend.test_metadata_review_workspace tests.frontend.test_metadata_review_actions tests.frontend.test_metadata_inbox tests.frontend.test_metadata_workspace`

Expected: PASS.
