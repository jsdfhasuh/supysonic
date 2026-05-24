import json
import os
import unittest

from unittest.mock import patch

from supysonic.db import Album, Artist, Folder, Playlist, Track, User, User_Play_Activity, db
from supysonic.recommend import RECOMMENDED_PLAYLIST_COMMENT, create_recommend_playlist
from supysonic.recommendation_feedback import set_recommendation_feedback

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

    def _create_recommended_playlist(self, day, *tracks):
        playlist = Playlist.create(
            user=self.user,
            name=f"{self.user.name}'s {day} recommend playlist",
            comment=RECOMMENDED_PLAYLIST_COMMENT,
        )
        for track in tracks or self.candidate_tracks[:1]:
            playlist.add(track)
        playlist.save()
        return playlist

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

    def test_create_recommend_playlist_excludes_user_disliked_tracks(self):
        self._record_play(self.listened_tracks[0], 2)
        self._record_play(self.listened_tracks[1], 1)
        disliked_track = self.candidate_tracks[0]

        set_recommendation_feedback(
            self.user,
            str(disliked_track.id),
            "dislike",
        )
        create_recommend_playlist(num_songs=3, user=self.user, day="2026-05-02")

        playlist = Playlist.get(Playlist.user == self.user)
        recommended_ids = {track.id for track in playlist.get_tracks()}
        self.assertNotIn(disliked_track.id, recommended_ids)

    def test_create_recommend_playlist_is_idempotent_for_same_user_and_day(self):
        self._record_play(self.listened_tracks[0], 2)
        self._record_play(self.listened_tracks[1], 1)

        first_created = create_recommend_playlist(num_songs=3, user=self.user, day="2026-05-02")
        second_created = create_recommend_playlist(num_songs=3, user=self.user, day="2026-05-02")

        self.assertEqual(first_created, 1)
        self.assertEqual(second_created, 0)
        self.assertEqual(Playlist.select().where(Playlist.user == self.user).count(), 1)

    def test_create_recommend_playlist_archives_recommendations_older_than_retention_window(self):
        self._record_play(self.listened_tracks[0], 2)
        self._record_play(self.listened_tracks[1], 1)
        old_playlist = self._create_recommended_playlist("2026-05-01", self.candidate_tracks[0])
        retained_playlist = self._create_recommended_playlist("2026-05-03", self.candidate_tracks[1])

        created = create_recommend_playlist(
            num_songs=3,
            user=self.user,
            day="2026-05-07",
            config=self.config,
        )

        self.assertEqual(created, 1)
        self.assertIsNone(Playlist.get_or_none(Playlist.id == old_playlist.id))
        self.assertIsNotNone(Playlist.get_or_none(Playlist.id == retained_playlist.id))
        archive_path = os.path.join(
            self.config.WEBAPP["cache_dir"],
            "recommend-playlists",
            self.user.name,
            "2026-05-01.json",
        )
        self.assertTrue(os.path.isfile(archive_path))
        with open(archive_path, "r", encoding="utf-8") as archive_file:
            payload = json.load(archive_file)
        self.assertEqual(payload["playlist_id"], str(old_playlist.id))
        self.assertEqual(payload["user"], self.user.name)
        self.assertEqual(payload["recommendation_day"], "2026-05-01")
        self.assertEqual(payload["track_ids"], [str(self.candidate_tracks[0].id)])
        self.assertEqual(payload["tracks"][0]["title"], self.candidate_tracks[0].title)

    def test_create_recommend_playlist_sanitizes_archive_user_directory(self):
        self._record_play(self.listened_tracks[0], 2)
        self._record_play(self.listened_tracks[1], 1)
        self._create_recommended_playlist("2026-05-01", self.candidate_tracks[0])
        self.user.name = "../alice"
        self.user.save()

        created = create_recommend_playlist(
            num_songs=3,
            user=self.user,
            day="2026-05-07",
            config=self.config,
        )

        archive_root = os.path.join(
            self.config.WEBAPP["cache_dir"],
            "recommend-playlists",
        )
        archive_path = os.path.join(archive_root, "alice", "2026-05-01.json")
        self.assertEqual(created, 1)
        self.assertTrue(os.path.isfile(archive_path))
        self.assertEqual(os.path.commonpath([archive_root, archive_path]), archive_root)
        self.assertFalse(os.path.exists(os.path.join(self.config.WEBAPP["cache_dir"], "alice")))

    def test_create_recommend_playlist_archives_old_entries_even_when_today_already_exists(self):
        self._create_recommended_playlist("2026-05-01", self.candidate_tracks[0])
        existing_today = self._create_recommended_playlist("2026-05-07", self.candidate_tracks[1])

        created = create_recommend_playlist(
            num_songs=3,
            user=self.user,
            day="2026-05-07",
            config=self.config,
        )

        self.assertEqual(created, 0)
        self.assertEqual(
            Playlist.select()
            .where(Playlist.user == self.user, Playlist.comment == RECOMMENDED_PLAYLIST_COMMENT)
            .count(),
            1,
        )
        self.assertIsNotNone(Playlist.get_or_none(Playlist.id == existing_today.id))
        archive_path = os.path.join(
            self.config.WEBAPP["cache_dir"],
            "recommend-playlists",
            self.user.name,
            "2026-05-01.json",
        )
        self.assertTrue(os.path.isfile(archive_path))

    def test_create_recommend_playlist_keeps_database_row_when_archive_write_fails(self):
        self._record_play(self.listened_tracks[0], 2)
        self._record_play(self.listened_tracks[1], 1)
        old_playlist = self._create_recommended_playlist("2026-05-01", self.candidate_tracks[0])

        with patch("supysonic.recommend.write_dict_to_json", side_effect=OSError("disk full")):
            created = create_recommend_playlist(
                num_songs=3,
                user=self.user,
                day="2026-05-07",
                config=self.config,
            )

        self.assertEqual(created, 1)
        self.assertIsNotNone(Playlist.get_or_none(Playlist.id == old_playlist.id))
        self.assertIsNotNone(
            Playlist.get_or_none(Playlist.name == "alice's 2026-05-07 recommend playlist")
        )


if __name__ == "__main__":
    unittest.main()
