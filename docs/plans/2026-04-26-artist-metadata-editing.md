# Artist Metadata Editing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add biography editing and single-photo upload to `/artists`, storing data in the existing artist metadata JSON structure.

**Architecture:** Extend the existing `/artists` admin endpoint to accept multipart form submissions, then move JSON update and image generation logic into reusable helpers under `supysonic/frontend/`. Reuse existing `Artist.artist_info_json`, `Artist.get_info()`, and cover-art serving code so no schema or API format changes are needed.

**Tech Stack:** Python, Flask, Peewee, Pillow, unittest, existing Supysonic templates.

---

### Task 1: Cover the new UI contract

**Files:**
- Modify: `tests/frontend/test_metadata.py`
- Modify: `supysonic/templates/metadata.html`

**Step 1: Write the failing test**

Assert that the artist modal template includes:
- `Primary artist name:`
- a biography field
- a file input for artist photo
- multipart form submission markers in the script

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.frontend.test_metadata`
Expected: FAIL because the new fields do not exist yet.

**Step 3: Write minimal implementation**

Update the modal markup and submit logic in `supysonic/templates/metadata.html`.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.frontend.test_metadata`
Expected: PASS.

### Task 2: Add metadata file helpers

**Files:**
- Modify: `supysonic/frontend/metadata_actions.py`
- Create/Modify: `tests/frontend/test_metadata_actions.py`

**Step 1: Write the failing test**

Add tests for helper behavior:
- create metadata JSON when missing
- update biography text
- overwrite image paths after generating `small`, `medium`, `large`
- reject invalid images

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.frontend.test_metadata_actions`
Expected: FAIL because helper functions are missing.

**Step 3: Write minimal implementation**

Implement helper functions to:
- resolve the effective primary artist
- locate/create artist metadata directory and JSON
- load/update/write metadata JSON
- open uploaded images and save three derived sizes

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.frontend.test_metadata_actions`
Expected: PASS.

### Task 3: Wire multipart handling into `/artists`

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Create: `tests/frontend/test_metadata_form.py`

**Step 1: Write the failing test**

Add integration tests covering:
- logged-in admin can POST multipart form data to `/artists`
- biography is persisted
- uploaded photo creates metadata image paths
- invalid photo returns 400

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests.frontend.test_metadata_form`
Expected: FAIL because the route only supports the previous JSON flow.

**Step 3: Write minimal implementation**

Update `/artists` POST to:
- accept `request.form` + `request.files`
- preserve legacy JSON behavior
- apply primary-artist reassignment when requested
- update biography/image metadata on the effective primary artist

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests.frontend.test_metadata_form`
Expected: PASS.

### Task 4: Run focused verification

**Files:**
- Modify as needed based on failures

**Step 1: Run the focused test suite**

Run: `python -m unittest tests.frontend.test_metadata tests.frontend.test_metadata_actions tests.frontend.test_metadata_form`
Expected: PASS.

**Step 2: Run syntax verification**

Run: `python -m py_compile "/workspace/supysonic/supysonic/frontend/metadata.py" "/workspace/supysonic/supysonic/frontend/metadata_actions.py" "/workspace/supysonic/tests/frontend/test_metadata.py" "/workspace/supysonic/tests/frontend/test_metadata_actions.py" "/workspace/supysonic/tests/frontend/test_metadata_form.py"`
Expected: no output.

**Step 3: Document verification results**

Record exactly which commands passed and any remaining gaps.
