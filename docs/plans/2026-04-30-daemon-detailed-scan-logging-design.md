# Daemon Detailed Scan Logging Design

## Goal

为 daemon 增加更易翻阅的详细扫描日志，同时保留现有主日志的可读性。

## Requirements

- 保留 daemon 主日志文件，继续承载 `INFO` 及以上级别信息。
- 新增独立 debug 日志文件，承载 `DEBUG` 及以上级别信息。
- debug 文件仅在 `DAEMON.log_level=DEBUG` 时启用。
- 不新增第三个 trace 文件。
- scanner 详细日志按统一 block 格式输出，覆盖以下链路：
  - `TRACK_TRACE`
  - `ALBUM_COVER_TRACE`
  - `NFO_TRACE`
  - `REPAIR_TRACE`

## Chosen Approach

采用单 logger 加双文件 handler 的方案。

- `supysonic-daemon.log` 只写 `INFO+`
- `supysonic-daemon.debug.log` 在 `DEBUG` 模式下写 `DEBUG+`
- scanner 各模块继续使用现有日志体系，不引入第二套业务 logger
- 新增轻量 trace helper，统一多行 block 输出格式

这个方案比拆双 logger 更小，也比第三个 trace 文件更符合当前需求。

## Trace Block Format

每个 trace block 使用纯文本多行格式：

```text
TRACK_TRACE path=/music/A/Album/track.flac track_id=12 disc=1 number=3
  - track artists source: fallback album artists
  - resolved track artists: Artist A, Artist B
  - resolved main artist: Artist A
```

规则：

- 第一行是 trace 类型和关键头字段
- 后续每行用 `  - ` 前缀表示决策步骤
- 空头字段跳过
- 没有步骤时输出 `no details`

## Scope

### TRACK_TRACE

记录单文件扫描后的 artist 决策结果，优先回答：

- 该文件最终使用了哪些 track artists
- 主 artist 最终是谁
- 是否回退到了 album artists

### ALBUM_COVER_TRACE

记录封面修复尝试顺序，优先回答：

- folder cover 是否命中
- embedded artwork 是否命中
- remote download 是否命中
- 最终为什么失败

### NFO_TRACE

记录 `album.nfo` 应用过程，优先回答：

- 是否找到 `album.nfo`
- 是否应用了 album metadata 更新
- track artist renow 是否执行或为何跳过

### REPAIR_TRACE

记录扫描后补救链路，当前已覆盖：

- album year repair
- artist profile repair
- missing artist image repair

优先回答：

- 是否从 track metadata / MusicBrainz / Last.fm 命中年份
- artist profile 是否从 Spotify / Last.fm 命中图片和简介
- 缺失 artist image 是否被重新下载
- 最终是否修复成功

## Non-Goals

- 不引入 JSON logging
- 不重写现有 scanner 调用图
- 不修改现有 `INFO` 文案语义
- 第一阶段不追求覆盖所有 scanner helper，只先覆盖最关键的四条链路
