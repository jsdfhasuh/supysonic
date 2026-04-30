# Web Log Management Design

## Goal

为 Supysonic Web 侧引入统一日志管理系统，把原本集中写入 `/var/supysonic/supysonic.log` 的日志按功能域拆分到多个文件，同时保留总日志。

## Confirmed Requirements

- 保留总日志文件。
- 新增分类日志文件。
- 所有日志统一放在一个目录。
- Web 配置项从单个日志文件路径改为日志目录。
- Access 日志单独成文件。
- Access 日志原样记录请求参数，不做脱敏。
- 所有分类日志与总日志都支持按天轮转。
- 轮转后按份数保留旧日志。

## Scope

第一阶段只改 Web 侧日志系统，不同时重构 daemon 侧。

覆盖以下日志文件：

- `supysonic.log`
- `access.log`
- `task.log`
- `emo.log`
- `scanner.log`
- `api.log`

## Architecture

新增 `supysonic/logging_manager.py` 作为统一日志管理入口，负责：

- 初始化日志目录
- 创建所有 file handler / console handler
- 管理日志轮转和保留份数
- 按 logger name 前缀把日志路由到分类文件
- 为 Web 注册 access logging 钩子
- 防止重复初始化导致 handler 叠加

`supysonic/web.py` 不再自己手写 `FileHandler` / `TimedRotatingFileHandler`，改为调用统一配置入口。

## Log Routing

### Summary Log

总日志 `supysonic.log` 保留，继续接收 `supysonic.*` 相关日志，作为汇总视图。

第一版也让 access 日志同步进入总日志，因此访问日志会同时出现在：

- `access.log`
- `supysonic.log`

### Category Logs

按 logger name 前缀分流：

- `supysonic.TaskManger` -> `task.log`
- `supysonic.emo` / `supysonic.emo.*` -> `emo.log`
- `supysonic.scanner` / `supysonic.scanner_func.*` / `supysonic.watcher` -> `scanner.log`
- `supysonic.api.*` -> `api.log`

其余模块先只进入 `supysonic.log`。

### Access Log

`access.log` 不依赖普通模块 logger 路由，而是由 Web 请求生命周期统一写入。

记录三类访问：

- `ACCESS:REST`
- `ACCESS:WEB`
- `ACCESS:SOCKET`

建议格式：

```text
[2026-04-30 16:40:25] [ACCESS:REST] 192.168.100.122 GET /rest/getCoverArt?id=...&u=root&t=...&s=... status=200 bytes=506200 duration=0.008085s
```

按已确认要求，query string 原样落盘。

第一版建议把 access logger 命名为 `supysonic.access`，以便：

- 独立写入 `access.log`
- 同时传播到总日志 `supysonic.log`

## Configuration

Web 侧配置从：

- `WEBAPP.log_file`

迁移到：

- `WEBAPP.log_dir`
- `WEBAPP.log_rotate`
- `WEBAPP.log_level`
- `WEBAPP.log_backup_count`

行为：

- `log_dir` 决定所有 Web 日志的存放目录
- `log_rotate=True` 时按天轮转
- `log_backup_count=N` 表示每个日志文件保留最近 N 份

第一版不引入每类日志单独路径或单独轮转参数。

## Rotation Strategy

统一使用：

- `logging.FileHandler` when `log_rotate=False`
- `TimedRotatingFileHandler(when="midnight", backupCount=log_backup_count)` when `log_rotate=True`

适用于所有 Web 日志文件。

## Access Logging Integration

建议在 Flask 侧通过：

- `before_request` 记录开始时间
- `after_request` 记录一条 access log

记录字段：

- remote addr
- method
- full path with query string
- status
- bytes
- duration
- access type

Socket 日志第一版只覆盖 namespace connect/disconnect 摘要，不承诺复刻 Engine.IO / WSGI 握手层的 `status=101`、`bytes`、`duration`。

原因：这些指标属于 websocket upgrade 请求层，而 `emo/ws.py` 的 namespace 事件层拿不到完整 HTTP 握手响应统计。

第一版 socket access 只保证：

- `ACCESS:SOCKET`
- remote addr
- namespace/path
- connect/disconnect event
- sid

后续如果需要完整 `101` 握手日志，应在更底层的 Engine.IO / WSGI 接入点补采集。

## Risks And Trade-Offs

### Expected Duplication

一条 task / emo / api / scanner / access 日志同时出现在总日志和分类日志中，是预期行为，不视为 bug。

### Sensitive Query Parameters

Access 日志原样记录认证参数会增加敏感信息长期落盘的风险。这是当前明确接受的产品取舍。

### Third-Party Logs

`werkzeug`、Flask 自身日志和其他第三方 logger 第一版不做细分，默认继续进入总日志。

## Minimal Implementation Scope

第一版最小改动范围：

- 新增 `supysonic/logging_manager.py`
- 修改 `supysonic/web.py`
- 补日志管理和 access logging 的测试

业务模块里的 `logging.getLogger(__name__)` 暂不大面积重写。

## Current Implementation Status

当前已经落地：

- `logging_manager` 骨架与目录式日志输出
- Web 侧 `log_dir` / `log_backup_count` 配置
- 兼容旧 `log_file` 到目录推导
- `access.log` for REST / WEB / SOCKET connect-disconnect summary
- `task.log` lifecycle logs
- `emo.log` login / device register logs
- `api.log` single-item retrieval failure log in `getSongs`
- `scanner.log` scan summary log

当前仍未落地：

- daemon 侧统一接入
- websocket 握手层 `101` / `bytes` / `duration` 采集
- 更广的 Emo / API / scanner 业务摘要日志
