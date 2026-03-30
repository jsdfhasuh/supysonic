import logging
import time

from flask import current_app, request, session
from flask_socketio import Namespace, SocketIO, emit

from ..db import close_connection, open_connection
from ..managers.user import UserManager
from .ws_store import (
    getPlaybackState,
    getQueueState,
    savePlaybackState,
    saveQueueState,
)
from .ws_state import get_state


logger = logging.getLogger(__name__)
state = get_state()
socketio = SocketIO(async_mode="threading", cors_allowed_origins="*", path="/emo/ws")

ALLOWED_PRE_AUTH = {"auth.login", "system.ping"}
CONTROL_ACTIONS = {
    "player.play",
    "player.pause",
    "player.next",
    "player.prev",
    "player.seek",
    "player.setVolume",
}


def init_socketio(app):
    socketio.init_app(app, path="/emo/ws")
    return socketio


def _build_message(msg_type, action, payload=None, **extra):
    message = {
        "type": msg_type,
        "action": action,
        "payload": payload or {},
        "timestamp": time.time(),
    }
    message.update(extra)
    return message


def _send_ack(request_id=None, payload=None):
    emit("message", _build_message("system", "system.ack", payload, requestId=request_id))


def _send_error(code, message, request_id=None):
    payload = {"code": code, "message": message}
    emit("message", _build_message("system", "system.error", payload, requestId=request_id))


def _get_session_user():
    user_id = session.get("userid")
    if not user_id:
        return None
    open_connection(reuse=True)
    try:
        return UserManager.get(user_id)
    except Exception:  # pragma: nocover
        return None
    finally:
        close_connection()


def _authenticate(payload):
    session_user = _get_session_user()
    if session_user is not None:
        return session_user

    user_name = payload.get("u")
    password = payload.get("p")
    if not user_name or not password:
        return None

    open_connection(reuse=True)
    try:
        return UserManager.try_auth(user_name, password)
    finally:
        close_connection()


def _broadcast_clients(user_name):
    message = _build_message(
        "state", "device.list", {"devices": state.list_clients(user_name=user_name)}
    )
    for target_sid, _ in state.list_sids(user_name=user_name):
        socketio.emit("message", message, to=target_sid, namespace="/emo")


def _broadcast_queue(user_name, session_id):
    queue_state = state.get_queue(session_id)
    if queue_state is None:
        return
    message = _build_message("state", "queue.session.sync", queue_state)
    for target_sid, _ in state.list_sids(user_name=user_name, session_id=session_id):
        socketio.emit("message", message, to=target_sid, namespace="/emo")


def _broadcast_playback_state(user_name, session_id):
    playback_state = state.get_playback_state(session_id)
    if playback_state is None:
        return
    message = _build_message("state", "playback.update", playback_state)
    for target_sid, _ in state.list_sids(user_name=user_name, session_id=session_id):
        socketio.emit("message", message, to=target_sid, namespace="/emo")


def _restorePersistedState(sid, session_id):
    queue_state = state.get_queue(session_id)
    if queue_state is None:
        queue_state = getQueueState(session_id)
        if queue_state is not None:
            state.update_queue(
                session_id,
                queue_state.get("queueSongIds") or [],
                queue_state.get("currentIndex", 0),
                queue_state.get("positionMs", 0),
            )

    if queue_state is not None:
        socketio.emit(
            "message",
            _build_message("state", "queue.session.sync", queue_state),
            to=sid,
            namespace="/emo",
        )

    playback_state = state.get_playback_state(session_id)
    if playback_state is None:
        playback_state = getPlaybackState(session_id)
        if playback_state is not None:
            state.update_playback_state(session_id, playback_state)

    if playback_state is not None:
        socketio.emit(
            "message",
            _build_message("state", "playback.update", playback_state),
            to=sid,
            namespace="/emo",
        )


def _register_device(sid, user_name, payload):
    client_id = payload.get("clientId")
    if not client_id:
        raise ValueError("Missing clientId")

    roles = payload.get("roles") or []
    if not isinstance(roles, list):
        raise ValueError("roles must be a list")

    return state.register_client(
        sid,
        client_id,
        {
            "userName": user_name,
            "deviceName": payload.get("deviceName") or client_id,
            "roles": roles,
            "sessionId": payload.get("sessionId") or client_id,
            "capabilities": payload.get("capabilities") or {},
        },
    )


def _route_command(sender, message):
    target_client_id = message.get("targetClientId")
    if not target_client_id:
        raise ValueError("Missing targetClientId")

    target_sid = state.get_sid_for_client(target_client_id)
    target_client = state.get_client(target_client_id)
    if target_sid is None or target_client is None:
        raise LookupError("Target client is offline")

    if target_client.get("userName") != sender.get("userName"):
        raise PermissionError("Cross-user control is not allowed")

    outgoing = _build_message(
        "command",
        message["action"],
        message["payload"],
        requestId=message.get("requestId"),
        sourceClientId=sender["clientId"],
        targetClientId=target_client_id,
    )
    socketio.emit("message", outgoing, to=target_sid, namespace="/emo")


class EmoNamespace(Namespace):
    def on_connect(self):
        if not current_app.config["WEBAPP"].get("emo_ws_enabled", True):
            return False
        state.register_session(request.sid)
        logger.info("emo socket connected: %s", request.sid)

    def on_disconnect(self):
        session_info, client_info = state.unregister_session(request.sid)
        logger.info("emo socket disconnected: %s", request.sid)
        if client_info is not None:
            _broadcast_clients(client_info["userName"])
        elif session_info is not None and session_info.get("userName"):
            _broadcast_clients(session_info["userName"])

    def on_message(self, message):
        if not isinstance(message, dict):
            _send_error("bad_request", "Message must be a JSON object")
            return

        action = message.get("action")
        request_id = message.get("requestId")
        if not isinstance(action, str) or not action:
            _send_error("bad_request", "Missing message action", request_id)
            return

        payload = message.get("payload")
        if payload is None:
            payload = {}
            message["payload"] = payload
        elif not isinstance(payload, dict):
            _send_error("bad_request", "Payload must be a JSON object", request_id)
            return

        session_info = state.get_session(request.sid)
        current_user_name = None if session_info is None else session_info.get("userName")
        current_client = state.get_client_for_sid(request.sid)

        if action == "system.ping":
            emit("message", _build_message("system", "system.pong", {}, requestId=request_id))
            return

        if (session_info is None or not session_info.get("authenticated")) and action not in ALLOWED_PRE_AUTH:
            _send_error("unauthorized", "Authenticate first", request_id)
            return

        try:
            if action == "auth.login":
                user = _authenticate(payload)
                if user is None:
                    _send_error("unauthorized", "Invalid credentials", request_id)
                    return
                state.authenticate_session(request.sid, user.name)
                current_user_name = user.name
                _send_ack(request_id, {"authenticated": True, "userName": user.name})
            elif action == "device.register":
                if not current_user_name:
                    raise PermissionError("Authenticate first")
                current_client = _register_device(request.sid, current_user_name, payload)
                _send_ack(request_id, {"client": current_client})
                _broadcast_clients(current_user_name)
                _restorePersistedState(request.sid, current_client.get("sessionId"))
            elif action == "device.list":
                emit(
                    "message",
                    _build_message(
                        "state",
                        "device.list",
                        {"devices": state.list_clients(user_name=current_user_name)},
                    ),
                )
            elif action in CONTROL_ACTIONS:
                if current_client is None:
                    raise PermissionError("Register the device before sending commands")
                _route_command(current_client, message)
                _send_ack(request_id, {"forwarded": True})
            elif action == "playback.update":
                if current_client is None:
                    raise PermissionError("Register the device before publishing state")
                session_id = payload.get("sessionId") or current_client.get("sessionId")
                state.update_playback_state(session_id, payload)
                savePlaybackState(
                    session_id,
                    current_user_name,
                    current_client.get("clientId"),
                    payload,
                )
                _send_ack(request_id, {"updated": True})
                _broadcast_playback_state(current_user_name, session_id)
            elif action == "queue.session.sync":
                if current_client is None:
                    raise PermissionError("Register the device before syncing queue")
                session_id = payload.get("sessionId") or current_client.get("sessionId")
                queue_song_ids = payload.get("queueSongIds")
                if not isinstance(queue_song_ids, list):
                    raise ValueError("queueSongIds must be a list")
                if not all(isinstance(song_id, str) and song_id for song_id in queue_song_ids):
                    raise ValueError("queueSongIds must contain non-empty strings")
                current_index = payload.get("currentIndex", 0)
                position_ms = payload.get("positionMs", 0)
                if not isinstance(current_index, int):
                    raise ValueError("currentIndex must be an integer")
                if not isinstance(position_ms, int):
                    raise ValueError("positionMs must be an integer")
                if queue_song_ids:
                    if current_index < 0 or current_index >= len(queue_song_ids):
                        raise ValueError("currentIndex is out of bounds")
                elif current_index != 0 or position_ms != 0:
                    raise ValueError("empty queue must use currentIndex=0 and positionMs=0")

                state.update_queue(session_id, queue_song_ids, current_index, position_ms)
                saveQueueState(
                    session_id,
                    current_user_name,
                    current_client.get("clientId"),
                    queue_song_ids,
                    current_index,
                    position_ms,
                )
                _send_ack(request_id, {"updated": True})
                _broadcast_queue(current_user_name, session_id)
            else:
                _send_error("not_supported", f"Unsupported action: {action}", request_id)
        except PermissionError as exc:
            _send_error("forbidden", str(exc), request_id)
        except LookupError as exc:
            _send_error("not_found", str(exc), request_id)
        except ValueError as exc:
            _send_error("bad_request", str(exc), request_id)


socketio.on_namespace(EmoNamespace("/emo"))
