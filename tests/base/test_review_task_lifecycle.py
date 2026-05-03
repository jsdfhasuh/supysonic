import os
import shutil
import tempfile
import unittest
from datetime import timedelta

from supysonic import db


class ReviewTaskLifecycleTestCase(unittest.TestCase):
    def setUp(self):
        self._db_dir = tempfile.mkdtemp()
        db.init_database(f"sqlite:///{os.path.join(self._db_dir, 'review-task-lifecycle.db')}")

    def tearDown(self):
        db.release_database()
        shutil.rmtree(self._db_dir)

    def test_run_review_task_maintenance_expires_stale_new_artist_tasks(self):
        from supysonic.scanner_func.scanner_review_tasks import runReviewTaskMaintenance

        artist = db.Artist.create(name="Stale Artist")
        task = db.ReviewTask.create(
            entity_type="artist",
            entity_id=str(artist.id),
            task_type="metadata_review",
            status="pending",
            reason="new_artist",
            snapshot_json="{}",
            expires_at=db.now() - timedelta(days=1),
        )

        updated_count = runReviewTaskMaintenance()

        self.assertEqual(updated_count, 1)
        self.assertEqual(db.ReviewTask.get_by_id(task.id).status, "expired")

    def test_run_review_task_maintenance_confirms_clean_new_album_tasks(self):
        from supysonic.scanner_func.scanner_review_tasks import runReviewTaskMaintenance

        artist = db.Artist.create(name="Album Artist")
        album = db.Album.create(name="Album", artist=artist, year="2024")
        task = db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json='{"issues": []}',
            expires_at=db.now() - timedelta(days=1),
        )

        updated_count = runReviewTaskMaintenance()

        self.assertEqual(updated_count, 1)
        self.assertEqual(db.ReviewTask.get_by_id(task.id).status, "confirmed")

    def test_run_review_task_maintenance_keeps_album_tasks_with_issues_pending(self):
        from supysonic.scanner_func.scanner_review_tasks import runReviewTaskMaintenance

        artist = db.Artist.create(name="Issue Artist")
        album = db.Album.create(name="Issue Album", artist=artist, year=None)
        task = db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="pending",
            reason="missing_year",
            snapshot_json='{"issues": ["missing_year"]}',
            expires_at=db.now() - timedelta(days=1),
        )

        updated_count = runReviewTaskMaintenance()

        self.assertEqual(updated_count, 0)
        self.assertEqual(db.ReviewTask.get_by_id(task.id).status, "pending")

    def test_run_review_task_maintenance_logs_pending_task_details(self):
        from supysonic.scanner_func.scanner_review_tasks import runReviewTaskMaintenance

        artist = db.Artist.create(name="Pending Artist")
        album = db.Album.create(name="Pending Album", artist=artist, year=None)
        db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="pending",
            reason="missing_year",
            snapshot_json='{"album_name": "Pending Album", "artist_name": "Pending Artist", "issues": ["missing_year"]}',
            expires_at=None,
        )

        with self.assertLogs("supysonic.scanner_func.scanner_review_tasks", level="INFO") as captured:
            updated_count = runReviewTaskMaintenance()

        self.assertEqual(updated_count, 0)
        combined_logs = "\n".join(captured.output)
        self.assertIn("Pending review tasks after maintenance: 1", combined_logs)
        self.assertIn("reason=missing_year", combined_logs)
        self.assertIn("title=Pending Album", combined_logs)
        self.assertIn("expiry_policy=awaiting_album_year", combined_logs)

    def test_run_review_task_bootstrap_logs_pending_task_expiry_details(self):
        from supysonic.scanner_func.scanner_review_tasks import runReviewTaskBootstrap

        artist = db.Artist.create(name="Bootstrap Artist")
        db.ReviewTask.create(
            entity_type="artist",
            entity_id=str(artist.id),
            task_type="metadata_review",
            status="pending",
            reason="new_artist",
            snapshot_json='{"artist_name": "Bootstrap Artist", "issues": ["missing_image"]}',
            expires_at=db.now() + timedelta(days=2),
        )

        with self.assertLogs("supysonic.scanner_func.scanner_review_tasks", level="INFO") as captured:
            created_count = runReviewTaskBootstrap()

        self.assertEqual(created_count, 1)
        combined_logs = "\n".join(captured.output)
        self.assertIn("Pending review tasks after bootstrap:", combined_logs)
        self.assertIn("title=Bootstrap Artist", combined_logs)
        self.assertIn("reason=new_artist", combined_logs)
        self.assertIn("expires_at=", combined_logs)


if __name__ == "__main__":
    unittest.main()
