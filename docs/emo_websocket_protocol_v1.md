# Emo Socket.IO Protocol v2

## Goals

- Keep HTTP endpoints for login, media metadata, and bootstrapping.
- Use a dedicated Socket.IO channel with namespace `/emo` and path `/emo/ws`.
- Let the server own authoritative device presence, session queue state, and playback state.
- Route device-specific commands by `clientId`.
- Share formal playback state by `sessionId`.

## Mental Model

- REST is request/response.
- Socket.IO is a long-lived event channel.
- `clientId` identifies a device instance.
- `sessionId` identifies a shared playback session.
- Commands target a device, but state belongs to a session.

## Connection Flow

1. Client connects to Socket.IO using namespace `/emo` and path `/emo/ws`.
2. Client sends `auth.login` as the first business message.
3. Server returns `system.ack` on successful authentication.
4. Client sends `device.register`.
5. Client optionally requests `device.list`.
6. Client starts sending commands, events, and state updates.

## Envelope

All business messages are JSON objects carried inside the Socket.IO `message` event.

```json
{
  "type": "command",
  "action": "player.pause",
  "requestId": "req-001",
  "targetClientId": "player-001",
  "payload": {},
  "timestamp": 1710000000
}
```

## Common Fields

- `type`: `auth`, `system`, `device`, `command`, `event`, or `state`
- `action`: concrete operation name
- `requestId`: client-generated id for request/response correlation
- `targetClientId`: target device for command routing
- `payload`: business payload
- `timestamp`: optional sender timestamp

## Core Identity Model

### `clientId`

- Stable device instance identifier
- Used by the server to route commands to one device
- Must be unique across active devices

### `sessionId`

- Stable playback session identifier
- Used by the server to scope queue state and playback state
- Multiple devices may share one `sessionId`

## Roles

- `player`: device that actually plays audio
- `controller`: device that sends playback commands
- `observer`: device that only watches state

One device may hold multiple roles.

## Queue Model

The protocol distinguishes device routing from session state.

- Device routing uses `clientId`
- Shared playback state uses `sessionId`

The authoritative session queue is represented by:

- `queueSongIds`: ordered array of server-side media ids
- `currentIndex`: active queue index
- `positionMs`: current playback offset inside the active track

This protocol does not use the old object-array queue format. The canonical queue payload is song-id based.

## Supported Actions

### Authentication

- `auth.login`

Accepted payload:

```json
{
  "u": "alice",
  "p": "Alic3"
}
```

Session cookies may also be used if the connection originates from the web UI.

### System

- `system.ping`
- `system.pong`
- `system.ack`
- `system.error`

### Devices

- `device.register`
- `device.list`

Register payload:

```json
{
  "clientId": "desktop-001",
  "deviceName": "Desktop Player",
  "roles": ["player", "controller"],
  "sessionId": "root:living-room"
}
```

### Playback Commands

- `player.play`
- `player.pause`
- `player.next`
- `player.prev`
- `player.seek`

Pause example:

```json
{
  "type": "command",
  "action": "player.pause",
  "requestId": "req-100",
  "targetClientId": "desktop-001",
  "payload": {}
}
```

Seek example:

```json
{
  "type": "command",
  "action": "player.seek",
  "requestId": "req-101",
  "targetClientId": "desktop-001",
  "payload": {
    "positionMs": 15000
  }
}
```

### Playback Events

- `playback.update`

This event reports the actual player state after local execution.

```json
{
  "type": "event",
  "action": "playback.update",
  "requestId": "playback-1",
  "payload": {
    "sessionId": "root:living-room",
    "state": "playing",
    "trackId": "songId3",
    "positionMs": 8000,
    "volume": 70
  }
}
```

Required payload fields:

- `sessionId`
- `state`
- `positionMs`

Recommended payload fields:

- `trackId`
- `volume`

### Session Queue State

- `queue.session.sync`

This is the canonical session queue update action.

```json
{
  "type": "state",
  "action": "queue.session.sync",
  "requestId": "queue-1",
  "payload": {
    "sessionId": "root:living-room",
    "queueSongIds": ["songId1", "songId2", "songId3"],
    "currentIndex": 2,
    "positionMs": 8000
  }
}
```

Required payload fields:

- `sessionId`
- `queueSongIds`
- `currentIndex`
- `positionMs`

Validation rules:

- `queueSongIds` must be an array of strings
- `currentIndex` must be an integer
- `positionMs` must be an integer
- if `queueSongIds` is non-empty, `currentIndex` must be within bounds
- if `queueSongIds` is empty, use `currentIndex = 0` and `positionMs = 0`

### Device List State

- `device.list`

This is both a requestable state snapshot and a server broadcast when device presence changes.

## Server Rules

- Unauthenticated connections may only send `auth.login` and `system.ping`.
- Commands are always routed through the server.
- Command routing uses `targetClientId`.
- Queue state and playback state are authoritative at the `sessionId` level.
- Every request-style message should end with either `system.ack` or `system.error`.
- Playback devices should send `playback.update` after they execute commands.
- `queue.session.sync` replaces the full authoritative queue for that session.

## Example Flow: Client A Pauses Client B

1. A sends `player.pause` targeting B's `clientId`.
2. Server validates A and finds B's connection from `clientId`.
3. Server forwards the command to B.
4. B pauses playback.
5. B sends `playback.update` with the shared `sessionId`.
6. Server updates session playback state.
7. Server broadcasts the updated state to devices in the same session.

## Example Flow: Controller Publishes Session Queue

1. A controller composes a formal queue.
2. A sends `queue.session.sync` with `queueSongIds`, `currentIndex`, and `positionMs`.
3. Server stores the new queue as authoritative session state.
4. Server broadcasts the new queue to devices in the same session.

## Non-Goals For v2

- Offline message delivery
- Cross-process pub/sub
- Multi-worker synchronization
- Device-to-device direct connections
- Fine-grained ACL beyond same-user control
- Local draft queue persistence on the server

## Upgrade Path

Later versions can add:

- `queue.local.set`
- `queue.session.append`
- `queue.session.remove`
- `queue.session.move`
- `session.join`
- `session.leave`
- stronger tokens instead of raw username/password
- Redis-backed shared state for multi-process deployment
