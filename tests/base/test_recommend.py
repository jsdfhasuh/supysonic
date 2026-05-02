import os
import unittest

from supysonic.db import Album, Artist, Folder, Playlist, Track, User, User_Play_Activity, db
from supysonic.recommend import RECOMMENDED_PLAYLIST_COMMENT, create_recommend_playlist

from ..testbase import TestBase


class RecommendTestCase(TestBase):
    def setUp(self):
        super().setUp()
        db.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS user_play_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id CHAR(36) NOT NULL REFERENCES track(id) ON DELETE CASCADE,
                user_id CHAR(36) NOT NULL REFERENCES user(id) ON DELETE CASCADE,
                time DATETIME NOT NULL
            )
            """
        )
        self.user = User.get(User.name == "alice")
        self.root = Folder.create(root=True, name="Root", path="/music")
        self.artist = Artist.create(name="Artist")
        self.album = Album.create(name="Album", artist=self.artist)
        self.listened_tracks = [
            self._create_track("Listened One", 1, genre="rock"),
            self._create_track("Listened Two", 2, genre="rock"),
        ]
        self.candidate_tracks = [
            self._create_track("Candidate Rock", 3, genre="rock"),
            self._create_track("Candidate Artist", 4, genre="pop"),
            self._create_track("Candidate Other", 5, genre="jazz"),
        ]

    def _create_track(self, title, number, genre=None):
        return Track.create(
            disc=1,
            number=number,
            title=title,
            duration=180,
            has_art=False,
            album=self.album,
            artist=self.artist,
            genre=genre,
            bitrate=320,
            path=os.path.join("/music", f"{number}.flac"),
            last_modification=1,
            root_folder=self.root,
            folder=self.root,
        )

    def _record_play(self, track, count):
        for _ in range(count):
            User_Play_Activity.create(track=track, user=self.user)

    def test_create_recommend_playlist_creates_local_day_playlist_with_recommended_comment(self):
        self._record_play(self.listened_tracks[0], 3)
        self._record_play(self.listened_tracks[1], 1)

        created = create_recommend_playlist(num_songs=3, user=self.user, day="2026-05-02")

        self.assertEqual(created, 1)
        playlist = Playlist.get(Playlist.user == self.user)
        self.assertEqual(playlist.name, "alice's 2026-05-02 recommend playlist")
        self.assertEqual(playlist.comment, RECOMMENDED_PLAYLIST_COMMENT)

    def test_create_recommend_playlist_excludes_already_listened_tracks(self):
        self._record_play(self.listened_tracks[0], 2)
        self._record_play(self.listened_tracks[1], 1)

        create_recommend_playlist(num_songs=3, user=self.user, day="2026-05-02")

        playlist = Playlist.get(Playlist.user == self.user)
        recommended_ids = {track.id for track in playlist.get_tracks()}
        listened_ids = {track.id for track in self.listened_tracks}
        self.assertTrue(recommended_ids)
        self.assertTrue(recommended_ids.isdisjoint(listened_ids))

    def test_create_recommend_playlist_is_idempotent_for_same_user_and_day(self):
        self._record_play(self.listened_tracks[0], 2)
        self._record_play(self.listened_tracks[1], 1)

        first_created = create_recommend_playlist(num_songs=3, user=self.user, day="2026-05-02")
        second_created = create_recommend_playlist(num_songs=3, user=self.user, day="2026-05-02")

        self.assertEqual(first_created, 1)
        self.assertEqual(second_created, 0)
        self.assertEqual(Playlist.select().where(Playlist.user == self.user).count(), 1)


if __name__ == "__main__":
    unittest.main()
