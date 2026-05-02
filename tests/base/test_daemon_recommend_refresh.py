import unittest

from types import SimpleNamespace
from unittest.mock import patch

from supysonic.daemon.server import Daemon


class DaemonRecommendRefreshTestCase(unittest.TestCase):
    def createDaemon(self, **daemon_config):
        config = SimpleNamespace(
            DAEMON={
                "socket": "daemon.sock",
                "run_watcher": False,
                "jukebox_command": None,
                **daemon_config,
            },
            BASE={},
        )
        return Daemon(config)

    def test_refresh_recommend_playlists_runs_once_per_day(self):
        daemon = self.createDaemon(recommend_playlist_size=25)

        with patch("supysonic.daemon.server.open_connection", return_value=True), patch(
            "supysonic.daemon.server.close_connection"
        ), patch(
            "supysonic.daemon.server.refreshDailyRecommendPlaylists", return_value=2
        ) as refresh_daily:
            self.assertTrue(
                daemon._Daemon__refresh_recommend_playlists_if_needed(current_day="2026-05-02")
            )
            self.assertFalse(
                daemon._Daemon__refresh_recommend_playlists_if_needed(current_day="2026-05-02")
            )

        refresh_daily.assert_called_once_with(num_songs=25, day="2026-05-02")

    def test_refresh_recommend_playlists_retries_same_day_after_failure(self):
        daemon = self.createDaemon(recommend_playlist_size=10)

        with patch("supysonic.daemon.server.open_connection", return_value=True), patch(
            "supysonic.daemon.server.close_connection"
        ), patch(
            "supysonic.daemon.server.refreshDailyRecommendPlaylists",
            side_effect=[RuntimeError("boom"), 1],
        ) as refresh_daily:
            self.assertFalse(
                daemon._Daemon__refresh_recommend_playlists_if_needed(current_day="2026-05-02")
            )
            self.assertTrue(
                daemon._Daemon__refresh_recommend_playlists_if_needed(current_day="2026-05-02")
            )

        self.assertEqual(refresh_daily.call_count, 2)

    def test_refresh_recommend_playlists_retries_when_open_connection_fails(self):
        daemon = self.createDaemon(recommend_playlist_size=10)

        with patch(
            "supysonic.daemon.server.open_connection",
            side_effect=[RuntimeError("db down"), True],
        ), patch("supysonic.daemon.server.close_connection"), patch(
            "supysonic.daemon.server.refreshDailyRecommendPlaylists",
            return_value=1,
        ) as refresh_daily:
            self.assertFalse(
                daemon._Daemon__refresh_recommend_playlists_if_needed(current_day="2026-05-02")
            )
            self.assertTrue(
                daemon._Daemon__refresh_recommend_playlists_if_needed(current_day="2026-05-02")
            )

        refresh_daily.assert_called_once_with(num_songs=10, day="2026-05-02")


if __name__ == "__main__":
    unittest.main()
