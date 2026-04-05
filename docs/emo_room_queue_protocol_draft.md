# Emo 多播放器房间模型协议草案

本文档定义“房间共享队列 + 设备本地队列 + 多播放器房间”的 Socket.IO 协议草案。

本草案用于后续服务端、Flutter 客户端、网页控制台统一实现。

当前实现状态：

- 已实现：
  - `queue.local.get`
  - `queue.local.set`
  - `queue.session.sync`
  - `playback.update` 带 `sourceClientId`
- 规划中：
  - `queue.local.clear`
  - `queue.session.get`
  - `queue.session.clear`
  - 房间级 group command

## 1. 设计目标

目标支持以下场景：

- 一个房间内存在多个播放器
- 每个播放器拥有自己的本地队列草稿
- 房间内有一份正式共享队列
- 只有显式同步时，本地队列才覆盖房间共享队列
- 播放状态按设备维度上报，不互相覆盖

## 2. 核心概念

### `clientId`

设备实例唯一标识。

作用：

- 定向控制命令路由
- 设备级播放状态归属
- 设备级本地队列归属

### `sessionId`

房间号 / 房间会话号。

作用：

- 标识同一个房间
- 房间共享正式队列归属
- 房间广播范围归属

### 房间共享队列

房间正式队列，所有房间成员共享。

唯一键：

- `sessionId`

### 设备本地队列

某个设备在某个房间里的本地草稿队列。

唯一键：

- `sessionId + clientId`

### 设备播放状态

某个设备在某个房间里的真实播放状态。

唯一键：

- `sessionId + clientId`

## 3. 通用消息结构

```json
{
  "type": "state",
  "action": "queue.local.set",
  "requestId": "req-123",
  "targetClientId": "player-1",
  "payload": {},
  "timestamp": 1710000000
}
```

字段说明：

- `type`
  - `auth` / `system` / `device` / `command` / `event` / `state`
- `action`
  - 具体动作名
- `requestId`
  - 请求唯一编号
- `targetClientId`
  - 仅设备级命令使用
- `payload`
  - 业务数据
- `timestamp`
  - 发送时间戳

## 4. 队列模型

### 4.1 本地队列消息

#### `queue.local.set`

作用：

- 更新当前设备在当前房间内的本地草稿队列
- 不广播
- 不影响其他设备

消息：

```json
{
  "type": "state",
  "action": "queue.local.set",
  "requestId": "local-1",
  "payload": {
    "sessionId": "root:living-room",
    "clientId": "player-1",
    "queueSongIds": ["songId1", "songId2", "songId3"],
    "currentIndex": 1,
    "positionMs": 0
  }
}
```

规则：

- `sessionId` 必填
- `clientId` 必填
- `queueSongIds` 必填，字符串数组
- `currentIndex` 必填，整数
- `positionMs` 必填，整数

返回：

```json
{
  "type": "system",
  "action": "system.ack",
  "requestId": "local-1",
  "payload": {
    "updated": true
  }
}
```

#### `queue.local.get`

作用：

- 获取某个设备在某个房间里的本地草稿队列

消息：

```json
{
  "type": "state",
  "action": "queue.local.get",
  "requestId": "local-get-1",
  "payload": {
    "sessionId": "root:living-room",
    "clientId": "player-1"
  }
}
```

返回示例：

```json
{
  "type": "state",
  "action": "queue.local.set",
  "payload": {
    "sessionId": "root:living-room",
    "clientId": "player-1",
    "queueSongIds": ["songId1", "songId2", "songId3"],
    "currentIndex": 1,
    "positionMs": 0,
    "updatedAt": 1710000000
  }
}
```

#### `queue.local.clear`

作用：

- 清空本地草稿队列

消息：

```json
{
  "type": "state",
  "action": "queue.local.clear",
  "requestId": "local-clear-1",
  "payload": {
    "sessionId": "root:living-room",
    "clientId": "player-1"
  }
}
```

### 4.2 房间共享队列消息

#### `queue.session.sync`

作用：

- 更新房间正式共享队列
- 广播给房间成员和 session 订阅者

消息：

```json
{
  "type": "state",
  "action": "queue.session.sync",
  "requestId": "session-1",
  "payload": {
    "sessionId": "root:living-room",
    "sourceClientId": "controller-1",
    "queueSongIds": ["songId1", "songId2", "songId3"],
    "currentIndex": 2,
    "positionMs": 8000
  }
}
```

规则：

- `sessionId` 必填
- `queueSongIds` 必填
- `currentIndex` 必填
- `positionMs` 必填
- `sourceClientId` 由服务端广播时补上，客户端发送时可省略

广播示例：

```json
{
  "type": "state",
  "action": "queue.session.sync",
  "payload": {
    "sessionId": "root:living-room",
    "sourceClientId": "controller-1",
    "queueSongIds": ["songId1", "songId2", "songId3"],
    "currentIndex": 2,
    "positionMs": 8000,
    "updatedAt": 1710000001
  }
}
```

#### `queue.session.get`

作用：

- 获取房间正式共享队列

消息：

```json
{
  "type": "state",
  "action": "queue.session.get",
  "requestId": "session-get-1",
  "payload": {
    "sessionId": "root:living-room"
  }
}
```

#### `queue.session.clear`

作用：

- 清空房间正式共享队列

消息：

```json
{
  "type": "state",
  "action": "queue.session.clear",
  "requestId": "session-clear-1",
  "payload": {
    "sessionId": "root:living-room"
  }
}
```

## 5. 播放状态模型

### `playback.update`

作用：

- 上报某个设备在某个房间里的真实播放状态
- 服务端按 `sessionId + clientId` 保存
- 广播给房间成员和 session 订阅者

消息：

```json
{
  "type": "event",
  "action": "playback.update",
  "requestId": "playback-1",
  "payload": {
    "sessionId": "root:living-room",
    "sourceClientId": "player-1",
    "state": "playing",
    "trackId": "songId3",
    "positionMs": 8000,
    "volume": 70
  }
}
```

广播示例：

```json
{
  "type": "state",
  "action": "playback.update",
  "payload": {
    "sessionId": "root:living-room",
    "sourceClientId": "player-1",
    "state": "playing",
    "trackId": "songId3",
    "positionMs": 8000,
    "volume": 70,
    "updatedAt": 1710000001
  }
}
```

## 6. 控制命令模型

### 6.1 设备级命令

继续使用：

- `player.play`
- `player.pause`
- `player.next`
- `player.prev`
- `player.seek`
- `player.setVolume`
- `queue.playItem`

这些命令仍然按 `targetClientId` 路由。

其中 `queue.playItem` 的 payload 规则建议为：

- `sessionId` 必填
- `queueIndex` 必填
- `clientId` 可选
- 不带 `clientId` 表示从房间共享队列中选定并播放
- 带 `clientId` 表示从该设备 local queue 中选定并播放
- 第一版限制 `clientId == targetClientId`

### 6.2 房间级命令（未来可选）

后续可新增：

- `player.group.play`
- `player.group.pause`
- `player.group.next`
- `player.group.seek`

这类命令按 `sessionId` fan-out 给房间内所有播放器。

第一版建议暂不实现。

## 7. 订阅模型

### `session.subscribe`

作用：

- 订阅某个房间 `sessionId` 的广播

消息：

```json
{
  "type": "state",
  "action": "session.subscribe",
  "requestId": "sub-1",
  "payload": {
    "sessionId": "root:living-room"
  }
}
```

### `session.unsubscribe`

作用：

- 取消订阅某个房间 `sessionId`

消息：

```json
{
  "type": "state",
  "action": "session.unsubscribe",
  "requestId": "unsub-1",
  "payload": {
    "sessionId": "root:living-room"
  }
}
```

## 8. 房间内多个播放器的推荐运行方式

例如房间：

- `sessionId = root:living-room`

设备：

- `player-livingroom-left`
- `player-livingroom-right`
- `player-livingroom-tv`

都加入同一个 `sessionId`。

这时：

- 正式共享队列：一份
- 每个播放器本地队列：各自一份
- 每个播放器播放状态：各自一份

## 9. 推荐控制台行为

网页控制台 `/control` 或 Flutter 控制器建议同时显示：

1. Session Queue
2. Local Queue
3. Playback states by client

推荐按钮：

- `Load session queue`
- `Load local queue`
- `Push local -> session`
- `Clear local queue`

## 10. 数据库存储建议

### `EmoSessionQueue`

唯一键：

- `session_id`

### `EmoLocalQueue`

唯一键：

- `(session_id, owner_client_id)`

### `EmoPlaybackState`

唯一键建议调整为：

- `(session_id, owner_client_id)`

## 11. 服务端广播原则

- `device.list`
  - 按用户全量广播
- `queue.session.sync`
  - 按房间成员 + 订阅者广播
- `playback.update`
  - 按房间成员 + 订阅者广播
- `queue.local.*`
  - 默认不广播

## 12. 第一阶段最小实施范围

建议第一轮只实现：

1. `EmoLocalQueue`
2. 设备级 `EmoPlaybackState`
3. `queue.local.set`
4. `queue.session.sync`
5. `/control` 展示本地队列 + 共享队列

暂不实现：

- 房间级群播命令
- 自动同步策略
- 冲突解决
- 历史版本表

## 13. 风险点

- 旧代码里很多地方默认把播放状态当成 session 级
- `/devices` 和 `/control` 都要重新区分：
  - 房间共享队列
  - 设备本地队列
  - 设备播放状态
- Flutter 端需要新增两层队列概念

## 14. 总结

推荐最终模型：

- `sessionId` = 房间号
- `clientId` = 设备号
- 房间共享队列 = `sessionId`
- 设备本地队列 = `sessionId + clientId`
- 设备播放状态 = `sessionId + clientId`

这样既支持一个房间多个播放器，也能让“显式同步共享队列”的产品语义保持清晰。
