import os
import unittest

from unittest.mock import patch

from supysonic.db import (
    Album,
    Artist,
    Folder,
    Playlist,
    Track,
    User,
    UserRecommendationFeedback,
    db,
)
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

    def _post_feedback(self, action="dislike", user="alice", password="Alic3"):
        return self.client.post(
            "/rest/setRecommendationFeedback.view",
            query_string={
                "u": user,
                "p": password,
                "c": "tests",
                "f": "json",
                "id": str(self.track.id),
                "action": action,
                "scope": "hot_recommended",
                "reason": "user_dislike",
                "source": "emosonic",
            },
            json={},
        )

    def _create_recommended_playlist(self, user, *tracks):
        playlist = Playlist.create(
            user=user,
            name=f"{user.name}'s 2026-05-24 recommend playlist",
            comment=RECOMMENDED_PLAYLIST_COMMENT,
        )
        for track in tracks:
            playlist.add(track)
        playlist.save()
        return playlist

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

    def test_set_recommendation_feedback_dislike_is_idempotent(self):
        first = self._post_feedback("dislike")
        second = self._post_feedback("dislike")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json["subsonic-response"]["status"], "ok")
        payload = first.json["subsonic-response"]["recommendationFeedback"]
        self.assertEqual(payload["id"], str(self.track.id))
        self.assertEqual(payload["action"], "dislike")
        self.assertEqual(payload["scope"], "hot_recommended")
        self.assertEqual(UserRecommendationFeedback.select().count(), 1)

    def test_set_recommendation_feedback_restore_removes_active_dislike(self):
        self._post_feedback("dislike")

        rv = self._post_feedback("restore")

        self.assertEqual(rv.status_code, 200)
        payload = rv.json["subsonic-response"]["recommendationFeedback"]
        self.assertEqual(payload["action"], "restore")
        feedback = UserRecommendationFeedback.get()
        self.assertIsNotNone(feedback.deleted_at)

    def test_set_recommendation_feedback_rejects_invalid_action(self):
        rv = self._post_feedback("hide_forever")

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["subsonic-response"]["status"], "failed")
        error = rv.json["subsonic-response"]["error"]
        self.assertEqual(error["code"], 0)
        self.assertEqual(error["message"], "invalid recommendation feedback action")
        self.assertEqual(UserRecommendationFeedback.select().count(), 0)

    def test_get_recommended_playlist_filters_disliked_tracks_for_current_user(self):
        playlist = Playlist.create(
            user=self.user,
            name="alice's 2026-05-01 recommend playlist",
            comment=RECOMMENDED_PLAYLIST_COMMENT,
        )
        playlist.add(self.track)
        playlist.save()
        self._post_feedback("dislike")

        rv = self._get_recommended_playlist()

        payload = rv.json["subsonic-response"]["playlist"]
        self.assertEqual(payload["songCount"], 0)
        self.assertNotIn("entry", payload)

    def test_recommendation_feedback_is_isolated_per_user(self):
        bob = User.get(User.name == "bob")
        self._create_recommended_playlist(self.user, self.track)
        self._create_recommended_playlist(bob, self.track)
        self._post_feedback("dislike", user="alice", password="Alic3")

        rv = self.client.get(
            "/rest/getRecommendedPlaylists.view",
            query_string={"u": "bob", "p": "B0b", "c": "tests", "f": "json"},
        )

        payload = rv.json["subsonic-response"]["playlist"]
        self.assertEqual(payload["songCount"], 1)
        self.assertEqual(payload["entry"][0]["id"], str(self.track.id))

    def test_restored_track_can_return_to_recommended_playlist(self):
        self._create_recommended_playlist(self.user, self.track)
        self._post_feedback("dislike")
        self._post_feedback("restore")

        rv = self._get_recommended_playlist()

        payload = rv.json["subsonic-response"]["playlist"]
        self.assertEqual(payload["songCount"], 1)
        self.assertEqual(payload["entry"][0]["id"], str(self.track.id))


if __name__ == "__main__":
    unittest.main()
