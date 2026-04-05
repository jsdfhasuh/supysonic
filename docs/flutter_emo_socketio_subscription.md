# Flutter Emo Session Subscription 对接文档

本文档专门说明 Flutter 客户端如何实现 `session.subscribe` / `session.unsubscribe`，用于实时订阅某个播放会话的状态与队列广播。

适用场景：

- Flutter 客户端是控制器，不是真正的播放器
- 客户端需要实时观察某个目标播放器所在的 `sessionId`
- 客户端希望收到该会话的：
  - `playback.update`
  - `queue.session.sync`

## 1. 为什么需要订阅

服务端里有两种不同的标识：

- `clientId`
  - 用于把命令路由给具体设备
- `sessionId`
  - 用于标识共享播放会话

控制命令通过 `targetClientId` 定向发送。  
播放状态和正式会话队列通过 `sessionId` 广播。

如果 Flutter 客户端本身不是该 `sessionId` 的正式成员，但又想实时看到这组状态，就必须显式订阅这个会话。

## 2. 订阅后的效果

当客户端成功订阅某个 `sessionId` 后，服务端会做两件事：

1. 立即推送这个会话的当前快照
  - `playback.update`
  - `queue.session.sync`
2. 后续只要该 `sessionId` 有新的状态广播，订阅者也会收到

这意味着：

- 你不需要每次都主动拉状态
- 选中目标播放器后就能持续实时观察它的会话变化

## 3. 前置条件

客户端必须先完成以下步骤：

1. `connect`
2. `auth.login`
3. `device.register`

只有已注册设备的连接才允许发送：

- `session.subscribe`
- `session.unsubscribe`

## 4. 订阅消息

消息名：`session.subscribe`

```json
{
  "type": "state",
  "action": "session.subscribe",
  "requestId": "sub-1",
  "payload": {
    "sessionId": "root:living-room"
  },
  "timestamp": 1710000000
}
```

字段要求：

- `type`：固定为 `state`
- `action`：固定为 `session.subscribe`
- `requestId`：必填，建议唯一
- `payload.sessionId`：必填，目标会话 ID

## 5. 取消订阅消息

消息名：`session.unsubscribe`

服务端当前**已经支持**该接口。

作用：

- 取消当前 Socket.IO 连接对某个 `sessionId` 的订阅
- 取消后，该连接将不再接收这个 `sessionId` 的：
  - `playback.update`
  - `queue.session.sync`

推荐使用场景：

- 控制器切换当前控制目标时，先退订旧 session
- 页面关闭、播放器切换、用户离开房间时主动清理订阅

```json
{
  "type": "state",
  "action": "session.unsubscribe",
  "requestId": "unsub-1",
  "payload": {
    "sessionId": "root:living-room"
  },
  "timestamp": 1710000001
}
```

取消订阅成功后，服务端会返回当前连接剩余的订阅列表：

```json
{
  "type": "system",
  "action": "system.ack",
  "requestId": "unsub-1",
  "payload": {
    "subscriptions": []
  }
}
```

如果当前连接还订阅了其他 session，则会返回剩余列表，例如：

```json
{
  "type": "system",
  "action": "system.ack",
  "requestId": "unsub-1",
  "payload": {
    "subscriptions": ["root:bedroom"]
  }
}
```

## 6. 服务端成功响应

成功时返回 `system.ack`：

```json
{
  "type": "system",
  "action": "system.ack",
  "requestId": "sub-1",
  "payload": {
    "subscriptions": ["root:living-room"]
  }
}
```

说明：

- `subscriptions` 表示当前这个连接已订阅的全部 `sessionId`
- Flutter 端应在本地记录这个集合
- 这条规则同时适用于：
  - `session.subscribe`
  - `session.unsubscribe`

## 7. 服务端错误响应

失败时返回 `system.error`：

```json
{
  "type": "system",
  "action": "system.error",
  "requestId": "sub-1",
  "payload": {
    "code": "forbidden",
    "message": "Cannot subscribe to a session outside your scope"
  }
}
```

常见错误：

- `unauthorized`
  - 还没认证
- `forbidden`
  - 还没注册设备
  - 订阅了不属于当前用户作用域的 `sessionId`
- `bad_request`
  - 缺少 `sessionId`

## 8. 订阅成功后的服务端快照推送

当 `session.subscribe` 成功后，服务端会立即推送当前会话快照。

### 播放状态快照

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
    "updatedAt": 1710000002
  }
}
```

### 队列快照

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
    "updatedAt": 1710000002
  }
}
```

## 9. 后续实时更新

订阅建立后，服务端以后会把该 `sessionId` 的实时广播也推送给订阅者：

- `playback.update`
- `queue.session.sync`

并且这两类广播都会带：

- `sourceClientId`

用于标识最后一次上报该状态或提交该队列的设备。

也就是说，Flutter 控制器客户端不需要再自己轮询状态。

注意：

- `queue.local.get`

不属于 session 广播模型，仍然只面向当前请求连接。

- `queue.local.set`

属于设备本地队列更新事件，但现在会推送给：

- 同一 `sessionId` 下的在线设备
- 当前订阅了该 `sessionId` 的控制端

并且在 `session.subscribe` 成功后的初始快照里，也会带上该 session 现有的 local queue 状态。

## 10. 推荐使用方式

### 场景：切换当前控制目标

推荐顺序：

1. 如果之前已订阅旧 `sessionId`，先发 `session.unsubscribe`
2. 再发新的 `session.subscribe`
3. 等待服务端推送当前快照
4. 之后持续接收实时状态

不要让同一个控制页面长期同时订阅很多 session，除非你的产品真的需要多会话监控。

## 11. Flutter 本地状态建议

建议维护：

- `selectedClientId`
- `selectedSessionId`
- `subscribedSessionIds`
- `playbackBySession`
- `queueBySession`

推荐最小结构：

```dart
class EmoRealtimeState {
  String? selectedClientId;
  String? selectedSessionId;
  final Set<String> subscribedSessionIds = {};
  final Map<String, Map<String, dynamic>> playbackBySession = {};
  final Map<String, Map<String, dynamic>> queueBySession = {};
}
```

## 12. Flutter 伪代码

```dart
Future<void> subscribeSession(String sessionId) async {
  socket.emit('message', {
    'type': 'state',
    'action': 'session.subscribe',
    'requestId': 'sub-${DateTime.now().millisecondsSinceEpoch}',
    'payload': {
      'sessionId': sessionId,
    },
    'timestamp': DateTime.now().millisecondsSinceEpoch / 1000,
  });
}

Future<void> unsubscribeSession(String sessionId) async {
  socket.emit('message', {
    'type': 'state',
    'action': 'session.unsubscribe',
    'requestId': 'unsub-${DateTime.now().millisecondsSinceEpoch}',
    'payload': {
      'sessionId': sessionId,
    },
    'timestamp': DateTime.now().millisecondsSinceEpoch / 1000,
  });
}

socket.on('message', (data) {
  final action = data['action'];
  final requestId = data['requestId'];
  final payload = data['payload'] ?? {};

  if (action == 'system.ack' && requestId.toString().startsWith('sub-')) {
    final subscriptions = List<String>.from(payload['subscriptions'] ?? []);
    state.subscribedSessionIds
      ..clear()
      ..addAll(subscriptions);
    return;
  }

  if (action == 'system.ack' && requestId.toString().startsWith('unsub-')) {
    final subscriptions = List<String>.from(payload['subscriptions'] ?? []);
    state.subscribedSessionIds
      ..clear()
      ..addAll(subscriptions);
    return;
  }

  if (action == 'playback.update') {
    final sessionId = payload['sessionId'];
    if (sessionId != null) {
      state.playbackBySession[sessionId] = Map<String, dynamic>.from(payload);
    }
    return;
  }

  if (action == 'queue.session.sync') {
    final sessionId = payload['sessionId'];
    if (sessionId != null) {
      state.queueBySession[sessionId] = Map<String, dynamic>.from(payload);
    }
    return;
  }
});
```

## 13. 切换目标播放器的推荐流程

```dart
Future<void> switchTarget({
  required String clientId,
  required String sessionId,
}) async {
  final oldSessionId = state.selectedSessionId;

  state.selectedClientId = clientId;
  state.selectedSessionId = sessionId;

  if (oldSessionId != null && oldSessionId != sessionId) {
    await unsubscribeSession(oldSessionId);
  }

  if (!state.subscribedSessionIds.contains(sessionId)) {
    await subscribeSession(sessionId);
  }
}
```

## 14. 关键注意事项

- `session.subscribe` 只负责订阅会话状态，不负责控制命令
- `session.unsubscribe` 当前服务端已实现，Flutter 客户端可以直接使用
- 控制命令仍然必须通过 `targetClientId` 发送
- 订阅成功后，服务端会立即推送当前快照
- 之后的新 `playback.update` / `queue.session.sync` 会继续实时推送
- 订阅失败时不要假设当前状态可用
- 切换目标时记得取消旧订阅，避免多个 session 混在一起

## 15. 最短交付摘要

给 Flutter 工程师的最短版本：

- 新增支持：
  - `session.subscribe`
  - `session.unsubscribe`
- 作用：
  - 实时订阅某个 `sessionId` 的播放状态和队列广播
- 订阅成功后：
  - 会立即收到 `playback.update`
  - 会立即收到 `queue.session.sync`
- 控制命令仍然按 `targetClientId` 发送
- 切换控制目标时：
  - 先退订旧 session
  - 再订阅新 session
