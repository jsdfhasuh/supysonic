# Emo 多播放器房间模型改造计划

本文档用于规划 Emosonic Server 后续支持“一个房间多个播放器”的模型重构。

目标不是立即改代码，而是给出清晰的改造方向、实施顺序、数据模型和协议约束。

## 1. 背景

当前 Emo 实时控制模型主要基于两类标识：

- `clientId`
  - 标识一个设备实例
  - 用于控制命令的定向路由
- `sessionId`
  - 标识一个播放会话
  - 当前用于共享队列和共享播放状态

当前实现适合：

- 单个房间一个主播放器
- 多个控制器观察和控制这个主播放器

当前实现不适合：

- 一个房间内多个播放器同时存在
- 每个播放器拥有自己的本地队列草稿
- 只有显式同步时才更新共享队列

## 2. 改造目标

将当前模型升级为“三层状态模型”：

1. 房间共享队列
2. 设备本地队列
3. 设备播放状态

目标效果：

- 多个播放器可属于同一个房间 `sessionId`
- 每个播放器有自己的本地队列与播放状态
- 房间共享队列作为正式队列
- 只有显式同步时，本地队列才会变成房间共享队列

## 3. 核心语义

### `sessionId`

`sessionId` 应视为“房间号 / 房间会话号”。

它表示：

- 哪些设备属于同一个房间
- 哪些设备共享同一个正式房间队列
- 哪些设备应接收房间级广播

多个 `clientId` 可以共享同一个 `sessionId`。

### `clientId`

`clientId` 应视为“设备号”。

它表示：

- 一个具体设备实例
- 命令应该发给谁
- 哪个设备上报了状态

`clientId` 必须稳定且唯一。

## 4. 最终状态模型

### 4.1 房间共享队列

唯一键：`sessionId`

含义：

- 房间正式播放队列
- 房间内播放器和控制器共同看到的队列
- 服务端负责广播和持久化

推荐字段：

- `sessionId`
- `queueSongIds`
- `currentIndex`
- `positionMs`
- `sourceClientId`
- `updatedAt`

### 4.2 设备本地队列

唯一键：`sessionId + clientId`

含义：

- 当前设备在某个房间内的本地草稿队列
- 默认不广播
- 默认不影响其他播放器

推荐字段：

- `sessionId`
- `clientId`
- `queueSongIds`
- `currentIndex`
- `positionMs`
- `updatedAt`

### 4.3 设备播放状态

唯一键：`sessionId + clientId`

含义：

- 某个设备在某个房间内的真实播放状态
- 多播放器房间中，各播放器状态不能互相覆盖

推荐字段：

- `sessionId`
- `clientId`
- `state`
- `trackId`
- `positionMs`
- `volume`
- `updatedAt`

## 5. 当前实现的不足

当前实现中：

- `EmoSessionQueue`
  - 以 `session_id` 唯一
  - 适合房间共享队列
- `EmoPlaybackState`
  - 当前按 `session_id` 唯一
  - 不适合多播放器房间

因此，真正的问题不在 `EmoSessionQueue`，而在 `EmoPlaybackState` 还没有设备级粒度。

## 6. 推荐数据库改造

### 6.1 保留 `EmoSessionQueue`

继续作为房间共享正式队列表。

唯一约束：

- `session_id` 唯一

### 6.2 新增 `EmoLocalQueue`

建议新增表：

- `session_id`
- `owner_client_id`
- `queue_json`
- `current_index`
- `position_ms`
- `updated_at`
- `created_at`

唯一约束建议：

- `(session_id, owner_client_id)`

### 6.3 改造 `EmoPlaybackState`

建议改成设备级模型。

字段建议：

- `session_id`
- `owner_client_id`
- `state`
- `track_id`
- `position_ms`
- `volume`
- `playback_json`
- `updated_at`
- `created_at`

唯一约束建议：

- `(session_id, owner_client_id)`

## 7. 内存态改造

当前 `ws_state.py` 里已经有：

- `sessionId -> queue`
- `sessionId -> playbackState`

建议改成：

- `sharedQueuesBySession`
- `localQueuesByClientSession`
- `playbackStatesByClientSession`

推荐键设计：

- 房间共享队列：`sessionId`
- 本地队列：`(sessionId, clientId)`
- 播放状态：`(sessionId, clientId)`

## 8. 协议改造建议

### 8.1 继续保留房间共享队列动作

- `queue.session.sync`

语义：

- 更新房间正式共享队列
- 广播给同房间设备和订阅者

### 8.2 新增本地队列动作

推荐新增：

- `queue.local.set`
- `queue.local.get`
- `queue.local.clear`

语义：

- 只影响当前设备自己的本地队列
- 默认不广播

### 8.3 播放状态动作

- `playback.update`

建议语义明确为：

- 这是某个 `clientId` 在某个 `sessionId` 内的真实播放状态
- 广播时必须带：
  - `sourceClientId`

## 9. 推荐交互模型

### 9.1 控制器

控制器拥有两套队列视图：

- 本地草稿队列
- 房间共享队列

推荐操作：

- 编辑本地队列
- 点击“Push to room”后同步到共享队列
- 点击“Load room queue”把共享队列拉到本地编辑器

### 9.2 播放器

播放器加入某个房间后：

- 主要消费房间共享队列
- 上报自己的设备级播放状态

### 9.3 房间多个播放器

房间中多个播放器都属于同一个 `sessionId`，但各自上报自己的播放状态：

- `player-a` -> `root:living-room`
- `player-b` -> `root:living-room`
- `player-c` -> `root:living-room`

共享的是：

- 房间正式队列

不共享的是：

- 每台设备当前播放状态
- 每台设备的本地草稿队列

## 10. `/control` 页面改造方向

后续 `/control` 应明确区分三类信息：

1. 房间共享队列
2. 选中播放器本地队列
3. 选中播放器当前播放状态

推荐页面结构：

- 左侧：房间内播放器列表
- 中间：选中播放器状态
- 右侧：
  - Local Queue Editor
  - Session Queue Viewer
  - Push / Pull 按钮

## 11. Flutter 客户端改造方向

Flutter 端建议维护：

- `selectedClientId`
- `selectedSessionId`
- `localQueue`
- `sessionQueue`
- `playbackStatesByClientId`

推荐动作：

- `queue.local.set`
- `queue.session.sync`
- `playback.update`
- `session.subscribe`
- `session.unsubscribe`

## 12. 实施计划

### Phase 1：文档先行

先更新协议和客户端文档，明确：

- 共享队列
- 本地队列
- 设备级播放状态

### Phase 2：内存态改造

文件：

- `supysonic/emo/ws_state.py`

动作：

- 新增本地队列结构
- 把播放状态改为设备级键

### Phase 3：数据库改造

文件：

- `supysonic/db.py`
- `supysonic/schema/*.sql`
- `supysonic/schema/migration/*`

动作：

- 新增 `EmoLocalQueue`
- 修改 `EmoPlaybackState` 唯一约束

### Phase 4：存储层改造

文件：

- `supysonic/emo/ws_store.py`

动作：

- 新增本地队列读写
- 播放状态改为设备级读写

### Phase 5：协议处理改造

文件：

- `supysonic/emo/ws.py`

动作：

- 新增 `queue.local.*`
- `queue.session.sync` 明确为共享队列
- `playback.update` 改为设备级更新

### Phase 6：控制台改造

文件：

- `supysonic/templates/control.html`
- `supysonic/frontend/__init__.py`

动作：

- 增加本地队列编辑能力
- 增加共享队列同步按钮
- 支持房间内多个播放器显示

### Phase 7：Flutter 接入

由 Flutter 工程师根据新协议实现：

- 本地队列
- 房间队列同步
- 设备级播放状态

## 13. 推荐实施顺序

建议严格按顺序执行：

1. 文档
2. `ws_state.py`
3. DB 模型与 migration
4. `ws_store.py`
5. `ws.py`
6. `/control`
7. `/devices`
8. Flutter

## 14. 第一阶段最小落地范围

为了控制风险，推荐第一刀只做：

1. `EmoPlaybackState` 改成设备级
2. 新增 `EmoLocalQueue`
3. 新增 `queue.local.set`
4. `/control` 能同时显示：
   - 共享队列
   - 本地队列

先不要一口气做：

- 房间级批量控制命令
- 自动同步策略
- 多版本历史表
- 复杂冲突解决

## 15. 风险点

- 当前代码很多地方默认把播放状态当成 session 级
- `/devices` 和 `/control` 都要重新定义展示语义
- Flutter 端需要理解两层队列，不再是一份队列通吃
- 多播放器房间会带来“谁是主播放器”的产品问题

## 16. 总结

如果你想支持“一个房间多个播放器”，最佳模型是：

- `sessionId` = 房间号
- `clientId` = 设备号
- 房间共享队列 = `sessionId`
- 设备本地队列 = `sessionId + clientId`
- 设备播放状态 = `sessionId + clientId`

这样既能保留房间共享能力，又不会让不同设备互相覆盖状态。
