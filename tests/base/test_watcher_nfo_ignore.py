import unittest

from unittest.mock import patch

from supysonic.watcher import FLAG_NFO, OP_SCAN, ScannerProcessingQueue


class DummyTimer:
    def __init__(self, timeout, callback):
        self.timeout = timeout
        self.callback = callback

    def start(self):
        return None

    def cancel(self):
        return None


class WatcherNfoIgnoreTestCase(unittest.TestCase):
    def setUp(self):
        self.timerPatch = patch("supysonic.watcher.Timer", DummyTimer)
        self.timerPatch.start()
        self.queue = ScannerProcessingQueue(1)

    def tearDown(self):
        self.queue.stop()
        self.timerPatch.stop()

    def test_queue_ignores_suppressed_nfo_path(self):
        self.queue.suppress_nfo_path("/music/Album/album.nfo", ttl=5)

        self.queue.put("/music/Album/album.nfo", OP_SCAN | FLAG_NFO)

        self.assertEqual(list(self.queue._ScannerProcessingQueue__queue), [])

    def test_queue_allows_suppressed_nfo_path_after_ttl(self):
        with patch("supysonic.watcher.time.time", side_effect=[10, 10, 20, 20]):
            self.queue.suppress_nfo_path("/music/Album/album.nfo", ttl=5)
            self.queue.put("/music/Album/album.nfo", OP_SCAN | FLAG_NFO)

        self.assertEqual(list(self.queue._ScannerProcessingQueue__queue), ["/music/Album/album.nfo"])

    def test_queue_does_not_ignore_other_nfo_paths(self):
        self.queue.suppress_nfo_path("/music/Album/album.nfo", ttl=5)

        self.queue.put("/music/Other/album.nfo", OP_SCAN | FLAG_NFO)

        self.assertEqual(list(self.queue._ScannerProcessingQueue__queue), ["/music/Other/album.nfo"])

    def test_suppress_nfo_path_prunes_expired_entries(self):
        with patch("supysonic.watcher.time.time", side_effect=[10, 10, 20, 20]):
            self.queue.suppress_nfo_path("/music/Album/album.nfo", ttl=5)
            self.queue.suppress_nfo_path("/music/New/album.nfo", ttl=5)

        self.assertEqual(
            self.queue._ScannerProcessingQueue__suppressed_nfo_paths,
            {"/music/New/album.nfo": 25},
        )


if __name__ == "__main__":
    unittest.main()
