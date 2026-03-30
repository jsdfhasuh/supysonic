import unittest

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "supysonic" / "emo" / "ws_state.py"
MODULE_SPEC = spec_from_file_location("emo_ws_state", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError("Unable to load emo ws_state module")
MODULE = module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)
WebSocketState = MODULE.WebSocketState


class EmoWebSocketStateTestCase(unittest.TestCase):
    def setUp(self):
        self.state = WebSocketState()

    def test_register_and_unregister_client(self):
        self.state.register_session("sid-1")
        self.state.authenticate_session("sid-1", "alice")
        client = self.state.register_client(
            "sid-1",
            "player-1",
            {
                "userName": "alice",
                "deviceName": "Living Room",
                "roles": ["player"],
                "sessionId": "sess-1",
            },
        )

        self.assertEqual(client["clientId"], "player-1")
        self.assertEqual(self.state.get_sid_for_client("player-1"), "sid-1")
        self.assertEqual(len(self.state.list_clients(user_name="alice")), 1)

        session_info, removed = self.state.unregister_session("sid-1")
        self.assertEqual(session_info["userName"], "alice")
        self.assertEqual(removed["deviceName"], "Living Room")
        self.assertIsNone(self.state.get_sid_for_client("player-1"))

    def test_queue_and_playback_state_are_stored_per_session(self):
        queue_state = self.state.update_queue(
            "sess-1", ["songId1", "songId2"], current_index=1, position_ms=3200
        )
        playback_state = self.state.update_playback_state(
            "sess-1", {"state": "playing", "trackId": "2", "positionMs": 1234}
        )

        self.assertEqual(queue_state["currentIndex"], 1)
        self.assertEqual(queue_state["positionMs"], 3200)
        self.assertEqual(self.state.get_queue("sess-1")["queueSongIds"][0], "songId1")
        self.assertEqual(playback_state["state"], "playing")
        self.assertEqual(self.state.get_playback_state("sess-1")["trackId"], "2")

    def test_re_registering_same_client_id_keeps_latest_session_mapping(self):
        self.state.register_session("sid-1")
        self.state.authenticate_session("sid-1", "root")
        self.state.register_client(
            "sid-1",
            "controller-1",
            {
                "userName": "root",
                "deviceName": "Phone Remote",
                "roles": ["controller"],
                "sessionId": "root:living-room",
            },
        )

        self.state.register_session("sid-2")
        self.state.authenticate_session("sid-2", "root")
        self.state.register_client(
            "sid-2",
            "controller-1",
            {
                "userName": "root",
                "deviceName": "Phone Remote",
                "roles": ["controller"],
                "sessionId": "root:living-room",
            },
        )

        session_info, removed = self.state.unregister_session("sid-1")
        self.assertEqual(session_info["userName"], "root")
        self.assertIsNone(removed)
        self.assertEqual(self.state.get_sid_for_client("controller-1"), "sid-2")
        self.assertIsNotNone(self.state.get_client_for_sid("sid-2"))
