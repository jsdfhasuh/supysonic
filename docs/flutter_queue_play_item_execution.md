# Flutter `queue.playItem` 执行说明

本文档给 Flutter 播放器工程师使用，专门说明设备端收到 `queue.playItem` 后应该如何执行，以及执行完成后应该如何把真实状态回传给 Emosonic Server。

适用场景：

- Flutter 客户端本身是播放器
- Flutter 客户端已经接入 Emo Socket.IO
- 需要支持被网页控制台或其他控制器远程切歌并立即播放

## 1. 结论

`queue.playItem` 只是一个“让目标设备去执行切歌并播放”的命令。

服务端不会代替播放器修改最终播放状态。

真正的闭环应该是：

1. 控制端发送 `queue.playItem`
2. 服务端把命令转发给目标播放器
3. 目标播放器本地执行切歌并开始播放
4. 目标播放器主动回传真实状态

回传至少包括：

1. `playback.update`
2. `queue.session.sync` 或 `queue.local.set`

## 2. 命令格式

### 2.1 播放 session 共享队列中的某一项

```json
{
  "type": "command",
  "action": "queue.playItem",
  "requestId": "cmd-1",
  "targetClientId": "player-1",
  "payload": {
    "sessionId": "sess-main",
    "queueIndex": 2
  }
}
```

含义：

- 目标设备 `player-1`
- 在 `sess-main` 的共享队列里
- 切到索引 `2`
- 并立即播放

### 2.2 播放设备 local queue 中的某一项

```json
{
  "type": "command",
  "action": "queue.playItem",
  "requestId": "cmd-2",
  "targetClientId": "player-1",
  "payload": {
    "sessionId": "sess-main",
    "clientId": "player-1",
    "queueIndex": 1
  }
}
```

含义：

- 目标设备 `player-1`
- 在该设备自己的 local queue 里
- 切到索引 `1`
- 并立即播放

## 3. 字段语义

- `targetClientId`
  - 这条命令最终发给哪台设备执行
- `payload.sessionId`
  - 当前房间 / 共享会话标识
- `payload.queueIndex`
  - 要切换到队列中的第几项
- `payload.clientId`
  - 可选
  - 不传时表示使用 session shared queue
  - 传了时表示使用该设备 local queue

当前服务端第一版约束：

- 如果带了 `payload.clientId`
- 它必须等于 `targetClientId`

也就是说，第一版不支持：

- 让 A 设备去播放 B 设备的 local queue

## 4. 设备端执行规则

收到 `queue.playItem` 后，播放器必须自己决定从哪条队列取歌。

规则如下：

1. 如果 `payload.clientId` 存在
   - 使用 `(sessionId, clientId)` 对应的 local queue
2. 如果 `payload.clientId` 不存在
   - 使用 `sessionId` 对应的 shared queue

然后执行：

1. 根据 `queueIndex` 找到目标 songId
2. 加载这首歌
3. 把播放器内部 current index 切到该位置
4. 从 `positionMs = 0` 开始播放
5. 播放开始后，立即回传真实状态

## 5. 推荐本地实现流程

推荐把逻辑写成类似下面的步骤：

```text
on queue.playItem(message):
  payload = message.payload
  sessionId = payload.sessionId
  queueIndex = payload.queueIndex
  queueClientId = payload.clientId

  if queueClientId exists:
    queue = localQueue[(sessionId, queueClientId)]
  else:
    queue = sessionQueue[sessionId]

  if queue not found:
    fail locally
    return

  if queueIndex out of bounds:
    fail locally
    return

  songId = queue.songIds[queueIndex]

  set active queue context
  set current index = queueIndex
  load songId
  start playback from 0ms

  emit playback.update

  if queueClientId exists:
    emit queue.local.set
  else:
    emit queue.session.sync
```

## 6. 为什么必须回传队列状态

只回 `playback.update` 不够。

原因：

- 控制台虽然能看到“当前在播哪首歌”
- 但不一定知道队列当前索引已经切到哪里
- `/control` 和 `/devices` 都会依赖队列状态显示当前项

所以推荐规则是：

1. 切共享队列播放后
   - 回传 `queue.session.sync`
2. 切本地队列播放后
   - 回传 `queue.local.set`

当前服务端行为：

- `queue.session.sync` 会广播给同 session 成员和订阅者
- `queue.local.set` 现在也会广播给同 session 成员和订阅者
- `session.subscribe` 的初始快照会带上当前 session 的 local queue 状态

如果播放器希望额外通知“队列已在本地准备完成”，还可以发送：

- `queue.ready.complete`

它不是权威队列状态，只是一个完成信号事件。

## 7. 成功执行后的回传格式

### 7.1 必回：`playback.update`

```json
{
  "type": "event",
  "action": "playback.update",
  "requestId": "playback-after-queue-play-1",
  "payload": {
    "sessionId": "sess-main",
    "state": "playing",
    "trackId": "songId3",
    "positionMs": 0,
    "volume": 70
  }
}
```

要求：

- `state` 应该是真实状态
- 如果已经开始播，就回 `playing`
- `trackId` 应该是最终实际播放的 songId
- `positionMs` 建议从 `0` 开始

### 7.2 如果播放的是 shared session queue：回 `queue.session.sync`

```json
{
  "type": "state",
  "action": "queue.session.sync",
  "requestId": "queue-after-play-1",
  "payload": {
    "sessionId": "sess-main",
    "queueSongIds": ["songId1", "songId2", "songId3"],
    "currentIndex": 2,
    "positionMs": 0
  }
}
```

要求：

- `queueSongIds` 应该是当前共享队列的完整列表
- `currentIndex` 应该是最终真实生效的索引
- `positionMs` 建议从 `0` 开始

### 7.3 如果播放的是 local queue：回 `queue.local.set`

```json
{
  "type": "state",
  "action": "queue.local.set",
  "requestId": "local-after-play-1",
  "payload": {
    "sessionId": "sess-main",
    "clientId": "player-1",
    "queueSongIds": ["songId8", "songId9", "songId10"],
    "currentIndex": 1,
    "positionMs": 0
  }
}
```

要求：

- `clientId` 必须是当前播放器自己的 `clientId`
- `queueSongIds` 应该是当前 local queue 的完整列表
- `currentIndex` 应该是真实生效的索引

### 7.4 可选：回 `queue.ready.complete`

这个动作适合在播放器已经把目标队列准备好、并希望通知控制端 UI 时使用。

shared queue 示例：

```json
{
  "type": "state",
  "action": "queue.ready.complete",
  "requestId": "ready-session-1",
  "payload": {
    "sessionId": "sess-main",
    "queueType": "session",
    "queueSongIds": ["songId1", "songId2", "songId3"]
  }
}
```

local queue 示例：

```json
{
  "type": "state",
  "action": "queue.ready.complete",
  "requestId": "ready-local-1",
  "payload": {
    "sessionId": "sess-main",
    "queueType": "local",
    "clientId": "player-1",
    "queueSongIds": ["songId8", "songId9", "songId10"]
  }
}
```

服务端会广播给：

- 同一 `sessionId` 下的在线设备
- 当前订阅了该 `sessionId` 的控制端

广播后的 payload 会补上：

- `sourceClientId`

注意：

- `queue.ready.complete` 只是准备完成通知
- 它不能替代 `queue.session.sync` / `queue.local.set`
- 也不能替代 `playback.update`

## 8. 失败时怎么处理

如果播放器无法执行，不要伪造成功状态。

常见失败场景：

- 对应队列不存在
- `queueIndex` 越界
- 目标 songId 无法解析
- 媒体加载失败

失败时建议：

1. 本地记录日志
2. 保持当前播放状态不变
3. 不要发送错误的 `playback.update`
4. 不要发送错误的 `queue.session.sync` / `queue.local.set`

如果后续需要更完整的失败通知，可以再扩展单独的错误回执协议。

## 9. Flutter 侧建议的数据结构

建议至少维护三份状态：

1. `sessionQueueBySessionId`
   - key: `sessionId`
2. `localQueueBySessionClient`
   - key: `sessionId::clientId`
3. `playbackBySessionClient`
   - key: `sessionId::clientId`

这样收到 `queue.playItem` 时，播放器端就能直接按以下规则取队列：

- 有 `clientId` -> `localQueueBySessionClient[sessionId::clientId]`
- 无 `clientId` -> `sessionQueueBySessionId[sessionId]`

## 10. 推荐执行顺序

推荐按下面顺序发送回传消息：

1. 先更新本地播放器状态
2. 先发队列状态
   - `queue.session.sync` 或 `queue.local.set`
3. 再发 `playback.update`

或者：

1. 先发 `playback.update`
2. 再发队列状态

两种都可以，但要保证：

- 两条消息都发
- 内容一致
- 都反映同一次真实执行结果

如果你希望 UI 更快表现“正在播放哪首”，优先先发 `playback.update`。

## 11. 第一版边界

当前第一版只建议支持：

1. 按 `queueIndex` 播放
2. shared queue 播放
3. local queue 播放

当前不建议在 Flutter 端自行扩展：

- 按 `songId` 查找并播放
- 自动修正服务端队列内容
- 让一个设备去执行另一个设备的 local queue

这些都可以后续再扩展，但不应混进第一版闭环。

## 12. 最终要求

Flutter 播放器端实现 `queue.playItem` 时，必须满足下面三点：

1. 能按 `clientId` 是否存在区分 shared queue 和 local queue
2. 能按 `queueIndex` 切换到正确歌曲并开始播放
3. 成功后必须回传真实生效后的队列状态和播放状态
