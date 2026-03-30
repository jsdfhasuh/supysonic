import unittest
import os
import tempfile

from supysonic import db
from supysonic.emo.ws_store import (
    getPlaybackState,
    getQueueState,
    savePlaybackState,
    saveQueueState,
)


class EmoWebSocketStoreTestCase(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp()
        os.close(handle)
        db.init_database("sqlite:///" + self.db_path)

    def tearDown(self):
        db.release_database()
        os.remove(self.db_path)

    def test_save_and_load_queue_state(self):
        saveQueueState(
            "root:living-room",
            "root",
            "player-1",
            ["songId1", "songId2"],
            1,
            4200,
        )

        queue_state = getQueueState("root:living-room")
        self.assertEqual(queue_state["sessionId"], "root:living-room")
        self.assertEqual(queue_state["currentIndex"], 1)
        self.assertEqual(queue_state["positionMs"], 4200)
        self.assertEqual(queue_state["queueSongIds"][0], "songId1")

    def test_save_and_load_playback_state(self):
        savePlaybackState(
            "root:living-room",
            "root",
            "player-1",
            {
                "sessionId": "root:living-room",
                "state": "playing",
                "trackId": "track-1",
                "positionMs": 4200,
                "volume": 65,
            },
        )

        playback_state = getPlaybackState("root:living-room")
        self.assertEqual(playback_state["sessionId"], "root:living-room")
        self.assertEqual(playback_state["state"], "playing")
        self.assertEqual(playback_state["trackId"], "track-1")
        self.assertEqual(playback_state["positionMs"], 4200)
        self.assertEqual(playback_state["volume"], 65)
