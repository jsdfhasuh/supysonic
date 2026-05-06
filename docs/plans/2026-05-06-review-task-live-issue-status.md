# Review Task Live Issue Status Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add live issue resolution feedback to album and artist review task pages so users can see when issues are resolved and when a task is ready to confirm.

**Architecture:** Reuse existing review task pages and save endpoints. The frontend performs immediate local evaluation from current form state, while the backend returns canonical issue status summaries after each save so the UI can reconcile optimistic state with persisted state.

**Tech Stack:** Flask, Jinja templates, vanilla JavaScript, unittest.

---

### Task 1: Define issue status contract

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Test: `tests/frontend/test_metadata_review_actions.py`

**Step 1: Write failing tests**
- Assert album, tracks, and artist save responses include an issue summary payload.
- Assert the payload marks issues resolved after relevant saves.

**Step 2: Run targeted tests to verify failure**
- Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_actions`

**Step 3: Write minimal implementation**
- Add backend helpers that compute canonical issue status from the saved task state.
- Return `issue_status` and `ready_to_confirm` from review save endpoints.

**Step 4: Run tests to verify pass**
- Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_actions`

### Task 2: Add live issue UI on review pages

**Files:**
- Modify: `supysonic/templates/metadata-review-task.html`
- Modify: `supysonic/templates/metadata-review-artist-task.html`
- Test: `tests/frontend/test_metadata_review_workspace.py`

**Step 1: Write failing tests**
- Assert both review pages render issue status containers and ready-to-confirm copy.
- Assert frontend script includes local evaluation hooks.

**Step 2: Run targeted tests to verify failure**
- Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace`

**Step 3: Write minimal implementation**
- Render issue status summary in both review sidebars.
- Add local form listeners that recompute issue state immediately.
- Reconcile local state with backend `issue_status` after save.

**Step 4: Run tests to verify pass**
- Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace`

### Task 3: Regression verification

**Files:**
- Test: `tests/frontend/test_metadata_review_workspace.py`
- Test: `tests/frontend/test_metadata_review_actions.py`
- Test: `tests/frontend/test_metadata_inbox.py`

**Step 1: Run focused regression suite**
- Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_workspace tests.frontend.test_metadata_review_actions tests.frontend.test_metadata_inbox`

**Step 2: Check diff hygiene**
- Run: `git diff --check`
