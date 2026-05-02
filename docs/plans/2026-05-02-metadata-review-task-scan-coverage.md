# Metadata Review Task Scan Coverage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make metadata review pending tasks appear for albums created through every scan path, including watcher-driven incremental imports.

**Architecture:** Keep album creation-time detection in `rememberNewAlbum`, then add a shared review-task finalizer that runs after scan batches finish. Reuse that finalizer from both full scanner runtime and watcher incremental batches so task creation, reason selection, and snapshot refresh all happen from the same post-scan state.

**Tech Stack:** Python, Peewee, unittest, Flask/daemon scanner helpers.

---

### Task 1: Lock the behavior with failing tests

**Files:**
- Modify: `tests/base/test_scanner_helpers.py`
- Modify: `tests/base/test_watcher.py` or add a focused watcher-base test in `tests/base/`

**Step 1: Write the failing test**

Add one test proving `runScanner()` refreshes pending-task metadata from final album state, and one test proving watcher incremental batches create pending tasks after media files are scanned.

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest <targeted tests>`
Expected: FAIL because watcher batches do not finalize review tasks yet.

**Step 3: Write minimal implementation**

Do not change production code in this task.

**Step 4: Run test to verify it still fails for the intended reason**

Run the same targeted command and confirm the failure points at missing finalization behavior.

### Task 2: Add a shared review-task finalizer

**Files:**
- Modify: `supysonic/scanner_func/scanner_review_tasks.py`
- Test: `tests/base/test_scanner_helpers.py`

**Step 1: Write the failing test**

Assert that a remembered new album gets a pending task whose `reason` and `snapshot_json` are based on the album state after scan-time enrichment.

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_helpers`
Expected: FAIL on missing reason/snapshot refresh behavior.

**Step 3: Write minimal implementation**

Add a helper in `scanner_review_tasks.py` that:
- reads `scanner.review_task_album_ids`
- creates or reuses the album's pending task
- sets `reason` from final DB state (`missing_year` if year is still absent, otherwise `new_album`)
- refreshes `snapshot_json`

**Step 4: Run test to verify it passes**

Run the targeted scanner helper tests again and confirm they pass.

### Task 3: Reuse the finalizer from every scan completion path

**Files:**
- Modify: `supysonic/scanner_func/scanner_runtime.py`
- Modify: `supysonic/watcher.py`
- Test: watcher-focused base test file

**Step 1: Write the failing test**

Add a watcher test that simulates a batch with scanned media files and verifies pending tasks are finalized before prune/close.

**Step 2: Run test to verify it fails**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest <watcher test module>`
Expected: FAIL because watcher never calls the shared finalizer.

**Step 3: Write minimal implementation**

Call the shared finalizer:
- in `runScanner()` after `find_lost_information()`
- in watcher batch completion after `find_lost_information()` and before `scanner.prune()`

**Step 4: Run test to verify it passes**

Run the watcher tests again and confirm they pass.

### Task 4: Verify end-to-end regressions

**Files:**
- Verify only

**Step 1: Run focused tests**

Run:
- `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_helpers`
- `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_watcher tests.base.test_watcher_nfo_ignore`

**Step 2: Run broader scanner/metadata regression**

Run:
- `"/root/enter/envs/supysonic/bin/python" -m unittest tests.frontend.test_metadata_inbox tests.frontend.test_metadata_review_workspace tests.frontend.test_metadata_review_actions`

**Step 3: Check diff formatting**

Run: `git diff --check -- <touched files>`
Expected: no output.
