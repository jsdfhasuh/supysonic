import os
import unittest

from supysonic.db import Album, Artist, Folder, Playlist, Track, User
from supysonic.recommend import RECOMMENDED_PLAYLIST_COMMENT, getRecommendationDay
from supysonic.recommendation_feedback import set_recommendation_feedback

from .frontendtestbase import FrontendTestBase


class RecommendationsTestCase(FrontendTestBase):
    def setUp(self):
        super().setUp()
        self.user = User.get(User.name == "alice")
        self.root = Folder.create(root=True, name="Root", path="/music")
        self.artist = Artist.create(name="Artist!")
        self.album = Album.create(name="Album!", artist=self.artist)
        self.track = self._create_track("Recommended One", 1, genre="rock")
        self.other_track = self._create_track("Recommended Two", 2, genre="jazz")

    def _create_track(self, title: str, number: int, genre: str) -> Track:
        return Track.create(
            disc=1,
            number=number,
            title=title,
            duration=180 + number,
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

    def _create_recommended_playlist(self, *tracks: Track) -> Playlist:
        playlist = Playlist.create(
            user=self.user,
            name=f"{self.user.name}'s {getRecommendationDay()} recommend playlist",
            comment=RECOMMENDED_PLAYLIST_COMMENT,
        )
        for track in tracks:
            playlist.add(track)
        playlist.save()
        return playlist

    def test_recommendations_nav_and_page_show_daily_playlist_tracks(self):
        self._create_recommended_playlist(self.track)

        self._login("alice", "Alic3")
        home = self.client.get("/")
        rv = self.client.get("/recommendations")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("Recommendations", home.data)
        self.assertIn("Recommendations", rv.data)
        self.assertIn("Daily", rv.data)
        self.assertIn("Recommended One", rv.data)
        self.assertIn("Artist!", rv.data)
        self.assertIn("Album!", rv.data)

    def test_recommendations_filter_disliked_tracks(self):
        self._create_recommended_playlist(self.track, self.other_track)
        set_recommendation_feedback(self.user, str(self.track.id), "dislike")

        self._login("alice", "Alic3")
        rv = self.client.get("/recommendations")

        self.assertEqual(rv.status_code, 200)
        self.assertNotIn("Recommended One", rv.data)
        self.assertIn("Recommended Two", rv.data)

    def test_recommendations_fall_back_to_library_tracks_without_playlist(self):
        self._login("alice", "Alic3")
        rv = self.client.get("/recommendations?count=1")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("Random", rv.data)
        self.assertTrue(
            "Recommended One" in rv.data or "Recommended Two" in rv.data
        )


if __name__ == "__main__":
    unittest.main()
