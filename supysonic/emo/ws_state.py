import threading
import time


class WebSocketState:
    def __init__(self):
        self._lock = threading.RLock()
        self._sessions = {}
        self._client_to_sid = {}
        self._clients = {}
        self._queues = {}
        self._playback_states = {}

    def register_session(self, sid):
        with self._lock:
            self._sessions[sid] = {
                "sid": sid,
                "connectedAt": time.time(),
                "authenticated": False,
                "userName": None,
                "clientId": None,
            }

    def authenticate_session(self, sid, user_name):
        with self._lock:
            session_info = self._sessions.get(sid)
            if session_info is None:
                return None
            session_info["authenticated"] = True
            session_info["userName"] = user_name
            return dict(session_info)

    def get_session(self, sid):
        with self._lock:
            session_info = self._sessions.get(sid)
            return dict(session_info) if session_info is not None else None

    def register_client(self, sid, client_id, info):
        client_info = dict(info)
        client_info["clientId"] = client_id
        client_info["connectedAt"] = time.time()
        with self._lock:
            previous_sid = self._client_to_sid.get(client_id)
            if previous_sid is not None and previous_sid != sid:
                previous_session = self._sessions.get(previous_sid)
                if previous_session is not None:
                    previous_session["clientId"] = None
            self._clients[client_id] = client_info
            self._client_to_sid[client_id] = sid
            session_info = self._sessions.get(sid)
            if session_info is not None:
                session_info["clientId"] = client_id
                if client_info.get("userName"):
                    session_info["userName"] = client_info["userName"]
                    session_info["authenticated"] = True
        return dict(client_info)

    def unregister_session(self, sid):
        with self._lock:
            session_info = self._sessions.pop(sid, None)
            if session_info is None:
                return None, None
            client_id = session_info.get("clientId")
            client_info = None
            if client_id:
                current_sid = self._client_to_sid.get(client_id)
                if current_sid == sid:
                    self._client_to_sid.pop(client_id, None)
                    client_info = self._clients.pop(client_id, None)
            return session_info, client_info

    def get_client(self, client_id):
        with self._lock:
            client = self._clients.get(client_id)
            return dict(client) if client is not None else None

    def get_sid_for_client(self, client_id):
        with self._lock:
            return self._client_to_sid.get(client_id)

    def get_client_for_sid(self, sid):
        with self._lock:
            session_info = self._sessions.get(sid)
            if session_info is None or not session_info.get("clientId"):
                return None
            client = self._clients.get(session_info["clientId"])
            return dict(client) if client is not None else None

    def list_clients(self, user_name=None, session_id=None):
        with self._lock:
            clients = []
            for client in self._clients.values():
                if user_name is not None and client.get("userName") != user_name:
                    continue
                if session_id is not None and client.get("sessionId") != session_id:
                    continue
                clients.append(dict(client))
            return clients

    def list_sids(self, user_name=None, session_id=None, exclude_sid=None):
        with self._lock:
            items = []
            for sid, session_info in self._sessions.items():
                if exclude_sid is not None and sid == exclude_sid:
                    continue
                client_id = session_info.get("clientId")
                if not client_id:
                    continue
                client = self._clients.get(client_id)
                if client is None:
                    continue
                if user_name is not None and client.get("userName") != user_name:
                    continue
                if session_id is not None and client.get("sessionId") != session_id:
                    continue
                items.append((sid, dict(client)))
            return items

    def update_queue(self, session_id, queue_song_ids, current_index=0, position_ms=0):
        if not session_id:
            return None
        queue_state = {
            "sessionId": session_id,
            "queueSongIds": list(queue_song_ids),
            "currentIndex": current_index,
            "positionMs": position_ms,
            "updatedAt": time.time(),
        }
        with self._lock:
            self._queues[session_id] = queue_state
        return dict(queue_state)

    def get_queue(self, session_id):
        with self._lock:
            queue_state = self._queues.get(session_id)
            return dict(queue_state) if queue_state is not None else None

    def update_playback_state(self, session_id, state):
        if not session_id:
            return None
        playback_state = dict(state)
        playback_state["sessionId"] = session_id
        playback_state["updatedAt"] = time.time()
        with self._lock:
            self._playback_states[session_id] = playback_state
        return dict(playback_state)

    def get_playback_state(self, session_id):
        with self._lock:
            playback_state = self._playback_states.get(session_id)
            return dict(playback_state) if playback_state is not None else None


_state = WebSocketState()


def get_state():
    return _state
