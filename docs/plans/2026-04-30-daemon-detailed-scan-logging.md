# Daemon Detailed Scan Logging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 daemon 增加双文件日志和 scanner 关键决策 trace。

**Architecture:** daemon 启动时配置 `INFO` 主日志和按 `DEBUG` 开关启用的 debug 日志；scanner 使用统一 trace helper 输出多行 block。第一阶段覆盖单文件扫描、封面修复、NFO 修正、album year repair 四条链路。

**Tech Stack:** Python `logging`, `TimedRotatingFileHandler`, `unittest`

---

### Task 1: Daemon Dual Log Files

**Files:**
- Modify: `supysonic/daemon/__init__.py`
- Test: `tests/base/test_daemon_logging.py`

1. 写 `INFO` 模式不生成 debug 文件的测试。
2. 运行 `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_daemon_logging` 并确认失败。
3. 为主日志添加 `INFO` 过滤，为 `DEBUG` 模式增加 `.debug.log` handler。
4. 重新运行测试并确认通过。

### Task 2: Shared Trace Helper

**Files:**
- Create: `supysonic/scanner_func/scanner_trace.py`
- Test: `tests/base/test_scanner_trace.py`

1. 写 trace block 格式测试。
2. 运行 `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_trace` 并确认失败。
3. 实现 `buildTraceBlock()` 和 `logTrace()`。
4. 重新运行测试并确认通过。

### Task 3: TRACK_TRACE

**Files:**
- Modify: `supysonic/scanner_func/scanner_pipeline.py`
- Test: `tests/base/test_scanner_track_trace.py`

1. 写 album artist fallback 场景测试。
2. 运行 `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_track_trace` 并确认失败。
3. 在 `processScanFile()` 聚合 track trace。
4. 重新运行测试并确认通过。

### Task 4: ALBUM_COVER_TRACE

**Files:**
- Modify: `supysonic/scanner_func/scanner_cover.py`
- Test: `tests/base/test_scanner_cover_trace.py`

1. 写 folder cover hit 和全部 miss 场景测试。
2. 运行 `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_cover_trace` 并确认失败。
3. 在 `repairAlbumCover()` 聚合 cover trace。
4. 重新运行测试并确认通过。

### Task 5: NFO_TRACE

**Files:**
- Modify: `supysonic/scanner_func/scanner_nfo.py`
- Test: `tests/base/test_scanner_nfo_trace.py`

1. 写 NFO 应用成功和编号异常跳过测试。
2. 运行 `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_nfo_trace` 并确认失败。
3. 在 `renowAlbumByNfo()` 聚合 NFO trace。
4. 重新运行测试并确认通过。

### Task 6: REPAIR_TRACE

**Files:**
- Modify: `supysonic/scanner_func/scanner_enrich.py`
- Test: `tests/base/test_scanner_repair_trace.py`

1. 写 album year repair 成功和失败测试。
2. 运行 `"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_scanner_repair_trace` 并确认失败。
3. 在 `repairAlbumYear()` 聚合 repair trace。
4. 重新运行测试并确认通过。

### Task 7: Verification

**Files:**
- Test only

1. 运行：

```bash
"/root/enter/envs/supysonic/bin/python" -m unittest tests.base.test_daemon_logging tests.base.test_scanner_trace tests.base.test_scanner_track_trace tests.base.test_scanner_cover_trace tests.base.test_scanner_nfo_trace tests.base.test_scanner_repair_trace tests.base.test_scanner_helpers
```

2. 运行：

```bash
"/root/enter/envs/supysonic/bin/python" -m py_compile supysonic/daemon/__init__.py supysonic/scanner_func/scanner_trace.py supysonic/scanner_func/scanner_pipeline.py supysonic/scanner_func/scanner_cover.py supysonic/scanner_func/scanner_nfo.py supysonic/scanner_func/scanner_enrich.py tests/base/test_daemon_logging.py tests/base/test_scanner_trace.py tests/base/test_scanner_track_trace.py tests/base/test_scanner_cover_trace.py tests/base/test_scanner_nfo_trace.py tests/base/test_scanner_repair_trace.py
```

### Task 8: Follow-ups

**Files:**
- Optional later: `supysonic/scanner_func/scanner_file.py`
- Optional later: `supysonic/scanner_func/scanner_enrich.py`

1. 第二阶段可继续细化 `TRACK_TRACE` 的 tag / nfo / fallback 来源。
2. 第二阶段可继续细化 `REPAIR_TRACE` 的下载失败原因和远端来源差异。
3. 若后续日志量过大，再评估 block 截断或更细粒度开关。
