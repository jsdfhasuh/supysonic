# Web Log Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 Supysonic Web 侧引入目录式统一日志管理系统，保留总日志并新增 access/task/emo/scanner/api 分类日志。

**Architecture:** 新增 `logging_manager` 统一创建和路由日志 handler，`web.py` 改为调用该入口。访问日志通过 Flask 请求钩子统一采集到 `access.log`，业务日志继续依赖现有 logger name 前缀分流到分类文件。

**Tech Stack:** Python `logging`, `TimedRotatingFileHandler`, Flask request hooks, `unittest`

---

## Status Snapshot

**Overall Status:** Partially implemented

**Completed:**

- Added `supysonic/logging_manager.py`
- Switched Web logging to directory-based configuration
- Added `WEBAPP.log_dir` and `WEBAPP.log_backup_count`
- Kept legacy `WEBAPP.log_file` directory fallback in `web.py`
- Added summary log plus category logs:
  - `supysonic.log`
  - `access.log`
  - `task.log`
  - `emo.log`
  - `scanner.log`
  - `api.log`
- Added logger prefix routing for:
  - `supysonic.access`
  - `supysonic.TaskManger`
  - `supysonic.emo.*`
  - `supysonic.scanner*` / `supysonic.scanner_func.*` / `supysonic.watcher`
  - `supysonic.api.*`
- Added access logging for:
  - `ACCESS:REST`
  - `ACCESS:WEB`
  - `ACCESS:SOCKET` connect/disconnect summary
- Added task lifecycle logs:
  - submitted
  - started
  - completed with duration
  - failed with error and duration
- Added Emo business logs:
  - auth login success/failure
  - device register success
- Added API business log:
  - `/rest/getSongs` single-track retrieval failure
- Added scanner run summary log after successful scan lifecycle
- Migrated most tests from `WEBAPP["log_file"]` to `WEBAPP["log_dir"]`

**Verified:**

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager tests.base.test_web_logging tests.base.test_access_logging tests.base.test_task_manager tests.base.test_web_startup tests.base.test_emo_logging tests.api.test_api_logging tests.api.test_artist_info2_urls tests.base.test_scanner_helpers tests.frontend.test_admin_tasks tests.frontend.test_metadata_inbox tests.frontend.test_metadata_review tests.frontend.test_metadata_review_actions tests.frontend.test_metadata_form tests.frontend.test_metadata_review_workspace
```

Result: `Ran 69 tests ... OK`

```bash
"/root/enter/envs/supysonic/bin/python" -m py_compile supysonic/logging_manager.py supysonic/web.py supysonic/emo/ws.py supysonic/api/browse.py supysonic/TaskManger.py supysonic/scanner_func/scanner_runtime.py tests/base/test_emo_logging.py tests/api/test_api_logging.py tests/base/test_scanner_helpers.py
```

Result: no output, success

**Not Completed Yet:**

- Full daemon-side unification into `logging_manager`
- Full websocket handshake-level access logging with `status=101` / `bytes` / `duration`
- Broader Emo business logs for unauthorized actions / subscriptions / playback control
- Broader API business logs beyond the currently covered failure path
- More scanner high-level start/end summaries per root folder or per queued run segment
- Optional cleanup of remaining compatibility reliance on `WEBAPP.log_file`

**Suggested Next Steps:**

1. Expand `emo.log` with unauthorized action, subscribe/unsubscribe, and control command logs.
2. Expand `api.log` with auth failure and high-value route summaries.
3. Expand `scanner.log` with root-folder start/end and stop-request summaries.
4. Decide whether daemon should migrate into the same directory-based log manager next.

### Task 1: Add Logging Manager Skeleton

**Status:** Completed

**Files:**
- Create: `supysonic/logging_manager.py`
- Test: `tests/base/test_logging_manager.py`

**Step 1: Write the failing test**

写测试覆盖：

- 传入 `log_dir` 时能创建总日志和分类日志路径
- `log_rotate=False` 使用 `FileHandler`
- `log_rotate=True` 使用 `TimedRotatingFileHandler`
- `log_backup_count` 被传入 rotating handler
- 重复初始化不会重复挂载 handler 或重复写日志

**Step 2: Run test to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager
```

Expected: FAIL，因为 `supysonic/logging_manager.py` 和相关接口尚未实现。

**Step 3: Write minimal implementation**

实现最小 `logging_manager`：

- handler builder
- 按文件名创建 target handler
- 统一 formatter
- 幂等初始化保护

**Step 4: Run test to verify it passes**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager
```

Expected: PASS

### Task 2: Add Logger Prefix Routing

**Status:** Completed

**Files:**
- Modify: `supysonic/logging_manager.py`
- Test: `tests/base/test_logging_manager.py`

**Step 1: Write the failing test**

写测试覆盖：

- `supysonic.TaskManger` -> `task.log`
- `supysonic.emo.client` -> `emo.log`
- `supysonic.scanner_func.scanner_enrich` -> `scanner.log`
- `supysonic.api.browse` -> `api.log`
- `supysonic.access` -> `access.log`
- 同时保留写入 `supysonic.log`

**Step 2: Run test to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager
```

Expected: FAIL，因为前缀路由 filter 尚未实现。

**Step 3: Write minimal implementation**

实现：

- logger 前缀匹配 filter
- 总日志 handler
- 分类日志 handler

**Step 4: Run test to verify it passes**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager
```

Expected: PASS

### Task 3: Add Directory-Based Config Defaults And Compatibility

**Status:** Completed (minimal compatibility retained)

**Files:**
- Modify: `supysonic/config.py`
- Modify: `supysonic/web.py`
- Test: `tests/base/test_web_logging.py`

**Step 1: Write the failing test**

写测试覆盖：

- 默认配置包含 `WEBAPP.log_dir`
- 默认配置包含 `WEBAPP.log_backup_count`
- 新配置 `log_dir` 生效
- 若仍传旧 `log_file`，迁移行为明确

**Step 2: Run test to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_web_logging
```

Expected: FAIL，因为 `web.py` 还在手工配置日志。

**Step 3: Write minimal implementation**

修改 `config.py` 和必要的 `web.py` 读取逻辑：

- 新增 `log_dir`
- 新增 `log_backup_count`
- 优先读取 `log_dir`
- 如必须兼容旧 `log_file`，只做最小目录推导

**Step 4: Run test to verify it passes**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_web_logging
```

Expected: PASS

### Task 4: Switch Web To Logging Manager

**Status:** Completed

**Files:**
- Modify: `supysonic/web.py`
- Test: `tests/base/test_web_logging.py`

**Step 1: Write the failing test**

写测试覆盖：

- `create_application()` 调用统一 `logging_manager`
- 使用 `WEBAPP.log_dir`
- 不再直接在 `web.py` 手工 new `FileHandler`

**Step 2: Run test to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_web_logging
```

Expected: FAIL，因为 `web.py` 还在手工配置日志。

**Step 3: Write minimal implementation**

修改 `web.py`：

- 改用 `log_dir`
- 调统一配置入口
- 保留现有 console logging 语义，但由 `logging_manager` 负责幂等处理

**Step 4: Run test to verify it passes**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_web_logging
```

Expected: PASS

### Task 5: Add Access Logging

**Status:** Completed for REST/WEB

**Files:**
- Modify: `supysonic/logging_manager.py`
- Modify: `supysonic/web.py`
- Test: `tests/base/test_access_logging.py`

**Step 1: Write the failing test**

写测试覆盖：

- REST 请求写入 `access.log`
- access 日志同时写入 `supysonic.log`
- 记录完整 path + query string
- 记录 status / bytes / duration
- 区分 `ACCESS:REST` 和 `ACCESS:WEB`

**Step 2: Run test to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_access_logging
```

Expected: FAIL，因为 access hook 尚未实现。

**Step 3: Write minimal implementation**

实现：

- `before_request` 记录开始时间
- `after_request` 写 `access.log`
- 使用独立 `access` logger / handler

**Step 4: Run test to verify it passes**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_access_logging
```

Expected: PASS

### Task 6: Add Socket Access Summary

**Status:** Completed for namespace connect/disconnect summary

**Files:**
- Modify: `supysonic/emo/ws.py`
- Test: `tests/base/test_access_logging.py`

**Step 1: Write the failing test**

写测试覆盖：

- socket connect/disconnect 摘要写入 `access.log`
- 日志前缀是 `ACCESS:SOCKET`
- 不要求 `status=101` / `bytes` / `duration`

**Step 2: Run test to verify it fails**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_access_logging
```

Expected: FAIL，因为 socket access summary 尚未接入。

**Step 3: Write minimal implementation**

在 `emo/ws.py` 接入最小连接级日志，不展开到所有 socket event，也不尝试在这一层复刻握手响应指标。

**Step 4: Run test to verify it passes**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_access_logging
```

Expected: PASS

### Task 7: Verification

**Status:** Completed for current implemented scope

**Files:**
- Test only

**Step 1: Run focused tests**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_logging_manager tests.base.test_web_logging tests.base.test_access_logging
```

**Step 2: Run related regression tests**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_task_manager tests.base.test_web_startup tests.frontend.test_admin_tasks
```

**Step 3: Run syntax checks**

Run:
```bash
"/root/enter/envs/supysonic/bin/python" -m py_compile supysonic/logging_manager.py supysonic/web.py supysonic/emo/ws.py tests/base/test_logging_manager.py tests/base/test_web_logging.py tests/base/test_access_logging.py
```

### Task 8: Documentation

**Status:** In progress

**Files:**
- Modify: `docs/plans/2026-04-30-web-log-management-design.md`
- Modify: `docs/plans/2026-04-30-web-log-management.md`

**Step 1: Update final design notes**

记录最终日志文件列表、轮转策略、保留份数配置、access 日志原样记录参数的取舍。

**Step 2: Verify docs reflect code**

逐项核对文件名、配置名、测试命令。
