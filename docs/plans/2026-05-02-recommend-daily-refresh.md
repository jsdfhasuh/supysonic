# Recommend Daily Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move recommended playlist creation off the request path and refresh one playlist per user per local day from the daemon.

**Architecture:** `supysonic.recommend` owns daily naming, lookup, and per-user playlist generation. `supysonic.api.playlists` becomes read-only for recommended playlists. `supysonic.daemon.server` runs a single background loop that refreshes once per day and retries later on failure.

**Tech Stack:** Python, Flask, Peewee, unittest.

---

### Task 1: Align Tests And Current Code

**Files:**
- Modify: `tests/base/test_recommend.py`
- Modify: `tests/base/test_recommend_api.py`
- Modify: `tests/base/test_daemon_recommend_refresh.py`

**Step 1: Run the targeted tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_recommend tests.base.test_recommend_api tests.base.test_daemon_recommend_refresh`

**Step 2: Capture the exact failures**

Confirm whether failures are from imports, request-path behavior, or daemon refresh wiring.

### Task 2: Make API Read-Only

**Files:**
- Modify: `supysonic/api/playlists.py`
- Test: `tests/base/test_recommend_api.py`

**Step 1: Keep `getRecommendedPlaylists` read-only**

Return today's playlist, then latest historical recommended playlist, then random fallback.

**Step 2: Keep recommended playlists out of the normal playlist list**

Filter both legacy `recommend` and current `recommended` comments.

**Step 3: Run the API tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_recommend_api`

### Task 3: Add Daemon Daily Refresh

**Files:**
- Modify: `supysonic/daemon/server.py`
- Test: `tests/base/test_daemon_recommend_refresh.py`

**Step 1: Add a single refresh loop in daemon**

Refresh once per local day, skip repeated success for the same day, and retry after failures.

**Step 2: Run daemon refresh tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_daemon_recommend_refresh`

### Task 4: Finish Recommendation Generation

**Files:**
- Modify: `supysonic/recommend.py`
- Test: `tests/base/test_recommend.py`

**Step 1: Keep same-day generation idempotent**

Create at most one playlist per user and day.

**Step 2: Exclude listened tracks and fill remaining slots**

Prefer genre and artist signals, then global popularity fallback.

**Step 3: Run recommendation tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_recommend`

### Task 5: Full Verification

**Files:**
- Modify: none unless failures require it
- Test: `tests/base/test_recommend.py`
- Test: `tests/base/test_recommend_api.py`
- Test: `tests/base/test_daemon_recommend_refresh.py`

**Step 1: Run the targeted suite**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_recommend tests.base.test_recommend_api tests.base.test_daemon_recommend_refresh`

**Step 2: If green, run nearby regression tests**

Run: `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_task_manager tests.base.test_daemon_logging`
