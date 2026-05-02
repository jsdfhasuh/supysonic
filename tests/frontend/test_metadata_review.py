import unittest
import os
import shutil
import tempfile

from supysonic.db import Album, AlbumReviewTask, Artist, Folder, Track, User, db

from .frontendtestbase import FrontendTestBase
from ..testbase import TestConfig


class MetadataReviewTestCase(FrontendTestBase):
    def setUp(self):
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["log_dir"] = ""
        self.mediaRootDir = tempfile.mkdtemp()
        self.albumDir = os.path.join(self.mediaRootDir, "album")
        os.makedirs(self.albumDir)
        super().setUp()
        db.execute_sql("ALTER TABLE artist ADD COLUMN artist_info_json VARCHAR(4096)")
        db.execute_sql("ALTER TABLE artist ADD COLUMN real_artist_id INTEGER")
        db.execute_sql("ALTER TABLE album ADD COLUMN year VARCHAR(255)")

        alice = User.get(User.name == "alice")
        with self.client.session_transaction() as session:
            session["userid"] = str(alice.id)

        self.artist = Artist.create(name="Review Artist")
        self.album = Album.create(name="Review Album", artist=self.artist, year="2024")
        self.root = Folder.create(root=True, name="Root", path=self.mediaRootDir)
        self.folder = Folder.create(root=False, name="Album", path=self.albumDir, parent=self.root)
        Track.create(
            disc=1,
            number=1,
            title="First Track",
            duration=120,
            has_art=False,
            album=self.album,
            artist=self.artist,
            bitrate=320,
            path=os.path.join(self.albumDir, "review-track.flac"),
            last_modification=1,
            root_folder=self.root,
            folder=self.folder,
        )
        self.task = AlbumReviewTask.create(
            album=self.album,
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json='{"album_name": "Review Album"}',
        )

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.mediaRootDir)

    def test_confirm_review_task(self):
        rv = self.client.post(f"/metadata/review-tasks/{self.task.id}/confirm")

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["status"], "success")

        saved_task = AlbumReviewTask.get_by_id(self.task.id)
        self.assertEqual(saved_task.status, "confirmed")
        self.assertIsNotNone(saved_task.resolved_at)

    def test_confirm_review_task_redirects_to_workspace_when_requested(self):
        rv = self.client.post(
            f"/metadata/review-tasks/{self.task.id}/confirm?redirect=1&section=artists"
        )

        self.assertEqual(rv.status_code, 302)
        self.assertIn(f"/metadata/review-tasks/{self.task.id}?section=artists", rv.location)

    def test_dismiss_review_task(self):
        rv = self.client.post(f"/metadata/review-tasks/{self.task.id}/dismiss")

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["status"], "success")

        saved_task = AlbumReviewTask.get_by_id(self.task.id)
        self.assertEqual(saved_task.status, "dismissed")
        self.assertIsNotNone(saved_task.resolved_at)

    def test_confirm_review_task_rejects_resolved_task(self):
        self.task.status = "dismissed"
        self.task.save()

        rv = self.client.post(f"/metadata/review-tasks/{self.task.id}/confirm")

        self.assertEqual(rv.status_code, 400)
        self.assertEqual(rv.json["status"], "error")

    def test_metadata_artist_suggestions_returns_matching_library_artists(self):
        Artist.create(name="Radiohead")
        Artist.create(name="Rage Against the Machine")
        Artist.create(name="The Cranberries")
        Artist.create(name="Daft Punk")

        rv = self.client.get("/metadata/artist-suggestions?q=ra")

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["status"], "success")
        self.assertEqual(rv.json["artists"][:2], ["Radiohead", "Rage Against the Machine"])
        self.assertEqual(rv.json["artists"][2], "The Cranberries")
        self.assertNotIn("Daft Punk", rv.json["artists"])


if __name__ == "__main__":
    unittest.main()
