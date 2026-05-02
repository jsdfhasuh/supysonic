# Mainline Logging Gap Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the remaining mainline runtime logging gaps for Web and CLI scan flows.

**Architecture:** Reuse the existing managed logging system instead of introducing new logging infrastructure. Add a dedicated Web debug file, initialize managed logging for CLI foreground scans, and replace runtime-path `print()` calls with logger output while preserving existing user-facing CLI summaries.

**Tech Stack:** Python, Flask, Click, unittest, existing `logging_manager`

---

### Task 1: Add Web Debug File Support

**Files:**
- Modify: `supysonic/logging_manager.py`
- Test: `tests/base/test_logging_manager.py`

**Step 1: Write the failing test**
- Extend Web logging manager tests to expect `web.debug.log` when `log_level=DEBUG`.
- Verify a Web logger `DEBUG` message lands in `web.debug.log` but not in `supysonic.log`.

**Step 2: Run test to verify it fails**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager`

**Step 3: Write minimal implementation**
- Add Web debug file naming support.
- Create the extra handler only when Web log level is `DEBUG`.

**Step 4: Run test to verify it passes**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager`

### Task 2: Initialize Managed Logging for Foreground CLI Scans

**Files:**
- Modify: `supysonic/cli.py`
- Test: `tests/base/test_scanner_helpers.py`

**Step 1: Write the failing test**
- Add a focused test that runs the foreground scan path under a temp `log_dir` and expects managed log files to be created.

**Step 2: Run test to verify it fails**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_helpers`

**Step 3: Write minimal implementation**
- Add a tiny helper in `cli.py` to configure managed logging before foreground scans.
- Preserve current `click.echo()` progress and summary behavior.

**Step 4: Run test to verify it passes**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_helpers`

### Task 3: Replace Runtime-Path Print Calls

**Files:**
- Modify: `supysonic/api/media.py`
- Modify: `supysonic/frontend/__init__.py`
- Modify: `supysonic/scanner_func/scanner_enrich.py`
- Modify: `supysonic/api/search.py`
- Test: `tests/base/test_access_logging.py`
- Test: `tests/base/test_scanner_helpers.py`

**Step 1: Write the failing test**
- Add targeted assertions where practical so the runtime paths still behave the same after replacing `print()` with logger output.

**Step 2: Run test to verify it fails**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_access_logging tests.base.test_scanner_helpers`

**Step 3: Write minimal implementation**
- Replace runtime-path `print()` calls with module logger calls at appropriate levels.
- Do not change endpoint or scan behavior.

**Step 4: Run test to verify it passes**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_access_logging tests.base.test_scanner_helpers`

### Task 4: Update Docs for Web Debug File

**Files:**
- Modify: `docs/setup/configuration.rst`
- Modify: `config.sample`

**Step 1: Update docs**
- Mention `web.debug.log` alongside existing Web managed log files when `log_level=DEBUG`.

**Step 2: Verify related config tests**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_web_logging tests.base.test_logging_manager`

### Task 5: Final Verification

**Files:**
- No file changes expected

**Step 1: Run focused verification**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager tests.base.test_web_logging tests.base.test_access_logging tests.base.test_scanner_helpers`

**Step 2: Run wider verification if logging code paths changed more broadly**
Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_utils tests.base.test_logging_manager tests.base.test_web_logging tests.base.test_access_logging tests.base.test_scanner_helpers`
