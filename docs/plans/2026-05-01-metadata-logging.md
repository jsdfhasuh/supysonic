# Metadata Logging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated `metadata.log` file and structured audit logs for metadata editing flows.

**Architecture:** Extend the existing Web logging manager with a new metadata category, then add minimal structured logging in `supysonic/frontend/metadata.py`. Cover the change with focused logging-manager and frontend tests, then update the configuration docs to mention the new file.

**Tech Stack:** Python, Flask, unittest, existing `format_log_event()` logging helpers

---

### Task 1: Add Metadata Log Routing

**Files:**
- Modify: `supysonic/logging_manager.py`
- Test: `tests/base/test_logging_manager.py`

**Step 1: Write the failing test**
- Extend the Web logging manager tests to expect `metadata.log` in created files.
- Add a routing assertion proving `supysonic.frontend.metadata` writes to `metadata.log` and `supysonic.log`.

**Step 2: Run test to verify it fails**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager`

**Step 3: Write minimal implementation**
- Add `metadata.log` to the Web log file name map.
- Route `supysonic.frontend.metadata` to the metadata category.

**Step 4: Run test to verify it passes**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager`

### Task 2: Add Metadata Review Audit Logs

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Test: `tests/frontend/test_metadata_review_actions.py`

**Step 1: Write the failing test**
- Add assertions for representative review-task audit events in `metadata.log`.
- Cover at least one success and one failure path.

**Step 2: Run test to verify it fails**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_actions`

**Step 3: Write minimal implementation**
- Add a metadata-local logging helper.
- Emit structured audit logs from the review-task POST routes only.

**Step 4: Run test to verify it passes**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_review_actions`

### Task 3: Add Artist Form Audit Logs

**Files:**
- Modify: `supysonic/frontend/metadata.py`
- Test: `tests/frontend/test_metadata_form.py`

**Step 1: Write the failing test**
- Add assertions for `artist_form_update` success and `no_change` cases.

**Step 2: Run test to verify it fails**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_form`

**Step 3: Write minimal implementation**
- Replace the current free-form artist form log lines with one structured event per request outcome.

**Step 4: Run test to verify it passes**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_form`

### Task 4: Update User-Facing Logging Docs

**Files:**
- Modify: `docs/setup/configuration.rst`
- Modify: `config.sample`

**Step 1: Update the docs**
- Add `metadata.log` to the documented Web log file list.

**Step 2: Verify references**
Run: `python -m unittest tests.base.test_web_logging`

### Task 5: Final Verification

**Files:**
- No file changes expected

**Step 1: Run focused verification**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager tests.frontend.test_metadata_review_actions tests.frontend.test_metadata_form`

**Step 2: Run wider logging verification if needed**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager tests.base.test_access_logging tests.base.test_web_logging tests.frontend.test_metadata_review_actions tests.frontend.test_metadata_form`
