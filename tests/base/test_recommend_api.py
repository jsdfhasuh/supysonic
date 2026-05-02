import os
import unittest

from unittest.mock import patch

from supysonic.db import Album, Artist, Folder, Playlist, Track, User, db
from supysonic.recommend import RECOMMENDED_PLAYLIST_COMMENT

from ..testbase import TestBase


class RecommendApiTestCase(TestBase):
    __with_api__ = True

    def setUp(self):
        super().setUp()
        self.user = User.get(User.name == "alice")
        self.root = Folder.create(root=True, name="Root", path="/music")
        self.artist = Artist.create(name="Artist")
        self.album = Album.create(name="Album", artist=self.artist)
        self.track = Track.create(
            disc=1,
            number=1,
            title="Song",
            duration=180,
            has_art=False,
            album=self.album,
            artist=self.artist,
            bitrate=320,
            path=os.path.join("/music", "song.flac"),
            last_modification=1,
            root_folder=self.root,
            folder=self.root,
        )

    def _get_recommended_playlist(self):
        return self.client.get(
            "/rest/getRecommendedPlaylists.view?u=alice&p=Alic3&c=tests&f=json"
        )

    def test_recommended_playlist_api_does_not_submit_background_generation_task(self):
        with patch("supysonic.TaskManger.TaskManager.submit_task") as submit_task:
            rv = self._get_recommended_playlist()

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["subsonic-response"]["status"], "ok")
        submit_task.assert_not_called()

    def test_recommended_playlist_api_falls_back_to_latest_recommended_playlist(self):
        playlist = Playlist.create(
            user=self.user,
            name="alice's 2026-05-01 recommend playlist",
            comment=RECOMMENDED_PLAYLIST_COMMENT,
        )
        playlist.add(self.track)
        playlist.save()

        rv = self._get_recommended_playlist()

        self.assertEqual(rv.status_code, 200)
        payload = rv.json["subsonic-response"]["playlist"]
        self.assertEqual(payload["name"], "alice's 2026-05-01 recommend playlist")
        self.assertEqual(payload["songCount"], 1)


if __name__ == "__main__":
    unittest.main()
