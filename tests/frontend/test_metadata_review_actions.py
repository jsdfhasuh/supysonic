import os
import shutil
import tempfile
import unittest

from supysonic.db import Album, AlbumArtist, AlbumReviewTask, Artist, Folder, Track, TrackArtist, User, db
from supysonic.tool import read_dict_from_json

from .frontendtestbase import FrontendTestBase
from ..testbase import TestConfig


class MetadataReviewActionsTestCase(FrontendTestBase):
    __with_api__ = True

    def setUp(self):
        self.logDir = tempfile.mkdtemp()
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["log_dir"] = self.logDir
        TestConfig.WEBAPP["log_level"] = "INFO"
        super().setUp()
        db.execute_sql("ALTER TABLE artist ADD COLUMN artist_info_json VARCHAR(4096)")
        db.execute_sql("ALTER TABLE artist ADD COLUMN real_artist_id INTEGER")
        db.execute_sql("ALTER TABLE album ADD COLUMN year VARCHAR(255)")
        db.execute_sql(
            "CREATE TABLE album_artist ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "album_id CHAR(36) NOT NULL REFERENCES album(id), "
            "artist_id CHAR(36) NOT NULL REFERENCES artist(id), "
            "position INTEGER NOT NULL DEFAULT 0, "
            "UNIQUE(album_id, artist_id)"
            ")"
        )
        db.execute_sql(
            "CREATE TABLE track_artist ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "track_id CHAR(36) NOT NULL REFERENCES track(id), "
            "artist_id CHAR(36) NOT NULL REFERENCES artist(id), "
            "position INTEGER NOT NULL DEFAULT 0, "
            "UNIQUE(track_id, artist_id)"
            ")"
        )

        alice = User.get(User.name == "alice")
        with self.client.session_transaction() as session:
            session["userid"] = str(alice.id)

        self.root = Folder.create(root=True, name="Root", path="/tmp/root")
        self.folder = Folder.create(root=False, name="Album", path="/tmp/root/album", parent=self.root)
        self.artist = Artist.create(name="Review Artist")
        self.album = Album.create(name="Review Album", artist=self.artist, year="2024")
        self.track = Track.create(
            disc=1,
            number=1,
            title="First Track",
            duration=120,
            has_art=False,
            album=self.album,
            artist=self.artist,
            bitrate=320,
            path="/tmp/review-track.flac",
            last_modification=1,
            root_folder=self.root,
            folder=self.folder,
        )
        AlbumArtist.create(album_id=self.album, artist_id=self.artist, position=1)
        TrackArtist.create(track_id=self.track, artist_id=self.artist, position=1)
        self.task = AlbumReviewTask.create(
            album=self.album,
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json='{"album_name": "Review Album", "artist_name": "Review Artist", "track_count": 1}',
        )

        self.unrelated_artist = Artist.create(name="Unrelated Artist")

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.logDir)

    def readMetadataLog(self):
        with open(os.path.join(self.config.WEBAPP["log_dir"], "metadata.log"), "r", encoding="utf-8") as f:
            return f.read()

    def test_review_task_album_update(self):
        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/album",
            json={"name": "Updated Album", "artist_name": "Updated Artist", "year": "2025"},
        )

        self.assertEqual(rv.status_code, 200)
        saved_album = Album.get_by_id(self.album.id)
        self.assertEqual(saved_album.name, "Updated Album")
        self.assertEqual(saved_album.year, "2025")
        self.assertEqual(saved_album.artist.get_artist_name(), "Updated Artist")
        album_artist_names = sorted(relation.artist_id.get_artist_name() for relation in saved_album.album_artists)
        self.assertEqual(album_artist_names, ["Updated Artist"])
        log_content = self.readMetadataLog()
        self.assertIn("metadata event=review_album_update", log_content)
        self.assertIn("result=success", log_content)
        self.assertIn(f"task_id={self.task.id}", log_content)
        self.assertIn(f"album_id={self.album.id}", log_content)

    def test_review_task_album_update_preserves_existing_guest_album_artists(self):
        guest_artist = Artist.create(name="Guest Album Artist")
        AlbumArtist.create(album_id=self.album, artist_id=guest_artist, position=2)

        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/album",
            json={"year": "2025"},
        )

        self.assertEqual(rv.status_code, 200)
        saved_album = Album.get_by_id(self.album.id)
        album_artist_names = sorted(relation.artist_id.get_artist_name() for relation in saved_album.album_artists)
        self.assertEqual(album_artist_names, ["Guest Album Artist", "Review Artist"])

    def test_review_task_tracks_update_stays_within_album_scope(self):
        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/tracks",
            json={
                "tracks": [
                    {
                        "id": str(self.track.id),
                        "number": 2,
                        "title": "Updated Track",
                        "artist_name": "Track Artist",
                    }
                ]
            },
        )

        self.assertEqual(rv.status_code, 200)
        saved_track = Track.get_by_id(self.track.id)
        self.assertEqual(saved_track.number, 2)
        self.assertEqual(saved_track.title, "Updated Track")
        self.assertEqual(saved_track.artist.get_artist_name(), "Track Artist")
        track_artist_names = sorted(relation.artist_id.get_artist_name() for relation in saved_track.track_artists)
        self.assertEqual(track_artist_names, ["Track Artist"])

    def test_review_task_tracks_update_preserves_existing_guest_track_artists(self):
        guest_artist = Artist.create(name="Guest Track Artist")
        TrackArtist.create(track_id=self.track, artist_id=guest_artist, position=2)

        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/tracks",
            json={
                "tracks": [
                    {
                        "id": str(self.track.id),
                        "title": "Retitled Track",
                    }
                ]
            },
        )

        self.assertEqual(rv.status_code, 200)
        saved_track = Track.get_by_id(self.track.id)
        track_artist_names = sorted(relation.artist_id.get_artist_name() for relation in saved_track.track_artists)
        self.assertEqual(track_artist_names, ["Guest Track Artist", "Review Artist"])

    def test_review_task_artist_update_allows_related_guest_artist(self):
        guest_artist = Artist.create(name="Guest Review Artist")
        TrackArtist.create(track_id=self.track, artist_id=guest_artist, position=2)

        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/artists/{guest_artist.id}",
            json={"biography": "Guest bio"},
        )

        self.assertEqual(rv.status_code, 200)
        saved_artist = Artist.get_by_id(guest_artist.id)
        info = read_dict_from_json(saved_artist.artist_info_json)
        self.assertEqual(info["biography"], "Guest bio")

    def test_review_task_artist_update_rejects_unrelated_artist(self):
        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/artists/{self.unrelated_artist.id}",
            json={"biography": "Should fail"},
        )

        self.assertEqual(rv.status_code, 400)
        self.assertEqual(rv.json["status"], "error")

    def test_review_task_artist_update_persists_biography(self):
        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/artists/{self.artist.id}",
            json={"biography": "Updated biography"},
        )

        self.assertEqual(rv.status_code, 200)
        saved_artist = Artist.get_by_id(self.artist.id)
        info = read_dict_from_json(saved_artist.artist_info_json)
        self.assertEqual(info["biography"], "Updated biography")
        log_content = self.readMetadataLog()
        self.assertIn("metadata event=review_artist_update", log_content)
        self.assertIn("result=success", log_content)
        self.assertIn(f"task_id={self.task.id}", log_content)
        self.assertIn(f"requested_artist_id={self.artist.id}", log_content)

    def test_review_task_confirm_rejects_invalid_task_id(self):
        rv = self.client.post("/metadata/review-tasks/not-a-uuid/confirm")

        self.assertEqual(rv.status_code, 400)
        self.assertEqual(rv.json["status"], "error")

    def test_review_task_tracks_update_rejects_missing_track(self):
        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/tracks",
            json={"tracks": [{"id": "00000000-0000-0000-0000-000000000000", "title": "ghost"}]},
        )

        self.assertEqual(rv.status_code, 404)
        self.assertEqual(rv.json["status"], "error")
        log_content = self.readMetadataLog()
        self.assertIn("metadata event=review_tracks_update", log_content)
        self.assertIn("result=not_found", log_content)
        self.assertIn("processed_count=0", log_content)

    def test_review_task_tracks_update_rolls_back_on_late_failure(self):
        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/tracks",
            json={
                "tracks": [
                    {
                        "id": str(self.track.id),
                        "number": 9,
                        "title": "Should Roll Back",
                    },
                    {
                        "id": "00000000-0000-0000-0000-000000000000",
                        "title": "ghost",
                    },
                ]
            },
        )

        self.assertEqual(rv.status_code, 404)
        saved_track = Track.get_by_id(self.track.id)
        self.assertEqual(saved_track.number, 1)
        self.assertEqual(saved_track.title, "First Track")

    def test_review_task_artist_update_rejects_missing_artist(self):
        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/artists/00000000-0000-0000-0000-000000000000",
            json={"biography": "ghost"},
        )

        self.assertEqual(rv.status_code, 404)
        self.assertEqual(rv.json["status"], "error")

    def test_review_task_album_update_rejects_resolved_task(self):
        self.task.status = "confirmed"
        self.task.save()

        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/album",
            json={"name": "Should Not Save"},
        )

        self.assertEqual(rv.status_code, 400)
        self.assertEqual(rv.json["status"], "error")

    def test_review_task_confirm_logs_success(self):
        rv = self.client.post(f"/metadata/review-tasks/{self.task.id}/confirm")

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["task_status"], "confirmed")

        log_content = self.readMetadataLog()
        self.assertIn("metadata event=review_task_confirm", log_content)
        self.assertIn("result=success", log_content)
        self.assertIn(f"task_id={self.task.id}", log_content)
        self.assertIn(f"album_id={self.album.id}", log_content)


if __name__ == "__main__":
    unittest.main()
