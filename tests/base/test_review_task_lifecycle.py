import os
import shutil
import tempfile
import unittest
from datetime import timedelta

from supysonic import db
from supysonic.frontend.metadata_review import reopenMetadataReviewTask


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

    def test_run_review_task_maintenance_backfills_expiry_for_clean_new_album_tasks(self):
        from supysonic.scanner_func.scanner_review_tasks import runReviewTaskMaintenance

        artist = db.Artist.create(name="Fresh Album Artist")
        album = db.Album.create(name="Fresh Album", artist=artist, year="2024")
        task = db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json='{"issues": []}',
            expires_at=None,
        )

        updated_count = runReviewTaskMaintenance()

        refreshed_task = db.ReviewTask.get_by_id(task.id)
        self.assertEqual(updated_count, 1)
        self.assertEqual(refreshed_task.status, "pending")
        self.assertIsNotNone(refreshed_task.expires_at)

    def test_run_review_task_maintenance_confirms_clean_new_album_tasks_after_backfill(self):
        from supysonic.scanner_func.scanner_review_tasks import runReviewTaskMaintenance

        artist = db.Artist.create(name="Older Album Artist")
        album = db.Album.create(name="Older Album", artist=artist, year="2024")
        task = db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json='{"issues": []}',
            created=db.now() - timedelta(days=5),
            updated=db.now() - timedelta(days=5),
            expires_at=None,
        )

        updated_count = runReviewTaskMaintenance()

        refreshed_task = db.ReviewTask.get_by_id(task.id)
        self.assertEqual(updated_count, 2)
        self.assertEqual(refreshed_task.status, "confirmed")
        self.assertIsNotNone(refreshed_task.expires_at)

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

    def test_run_review_task_maintenance_removes_legacy_duplicate_album_pending_task(self):
        from supysonic.scanner_func.scanner_review_tasks import runReviewTaskMaintenance

        artist = db.Artist.create(name="Duplicate Artist")
        album = db.Album.create(name="Duplicate Album", artist=artist, year=None)
        legacy_task = db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="pending",
            reason="missing_year",
            snapshot_json='{"album_name": "Duplicate Album", "artist_name": "Duplicate Artist", "track_count": 1}',
        )
        db.ReviewTask.update(
            entity_id=str(album.id).replace("-", ""),
            pending_key=f"{album.id}:pending",
        ).where(db.ReviewTask.id == legacy_task.id).execute()
        canonical_task = db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="pending",
            reason="missing_year",
            pending_key=f"album:{album.id}:pending",
            snapshot_json='{"album_name": "Duplicate Album", "artist_name": "Duplicate Artist", "track_count": 1, "issues": ["missing_year"]}',
        )

        updated_count = runReviewTaskMaintenance()

        self.assertEqual(updated_count, 1)
        self.assertIsNone(db.ReviewTask.get_or_none(db.ReviewTask.id == legacy_task.id))
        self.assertIsNotNone(db.ReviewTask.get_or_none(db.ReviewTask.id == canonical_task.id))

    def test_run_review_task_maintenance_removes_superseded_new_artist_task(self):
        from supysonic.scanner_func.scanner_review_tasks import runReviewTaskMaintenance

        artist = db.Artist.create(name="Duplicate Artist")
        new_artist_task = db.ReviewTask.create(
            entity_type="artist",
            entity_id=str(artist.id),
            task_type="metadata_review",
            status="pending",
            reason="new_artist",
            snapshot_json='{"artist_name": "Duplicate Artist", "issues": ["missing_image"]}',
            expires_at=db.now() + timedelta(days=2),
        )
        missing_image_task = db.ReviewTask.create(
            entity_type="artist",
            entity_id=str(artist.id),
            task_type="metadata_review",
            status="pending",
            reason="missing_image",
            snapshot_json='{"artist_name": "Duplicate Artist", "issues": ["missing_image"]}',
            expires_at=None,
        )

        updated_count = runReviewTaskMaintenance()

        self.assertEqual(updated_count, 1)
        self.assertIsNone(db.ReviewTask.get_or_none(db.ReviewTask.id == new_artist_task.id))
        self.assertIsNotNone(db.ReviewTask.get_or_none(db.ReviewTask.id == missing_image_task.id))

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

    def test_reopen_metadata_review_task_reopens_confirmed_task(self):
        artist = db.Artist.create(name="Reopen Artist")
        album = db.Album.create(name="Reopen Album", artist=artist, year="2024")
        task = db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="confirmed",
            reason="new_album",
            snapshot_json='{"issues": []}',
            resolved_at=db.now(),
        )

        reopened_task = reopenMetadataReviewTask(task)

        self.assertEqual(reopened_task.status, "pending")
        self.assertIsNone(reopened_task.resolved_at)
        self.assertEqual(reopened_task.pending_key, f"album:{album.id}:pending")

    def test_reopen_metadata_review_task_reopens_dismissed_task(self):
        artist = db.Artist.create(name="Dismissed Artist")
        task = db.ReviewTask.create(
            entity_type="artist",
            entity_id=str(artist.id),
            task_type="metadata_review",
            status="dismissed",
            reason="missing_image",
            snapshot_json='{"issues": ["missing_image"]}',
            resolved_at=db.now(),
        )

        reopened_task = reopenMetadataReviewTask(task)

        self.assertEqual(reopened_task.status, "pending")
        self.assertIsNone(reopened_task.resolved_at)
        self.assertEqual(reopened_task.pending_key, f"artist:{artist.id}:pending:missing_image")

    def test_reopen_metadata_review_task_rejects_pending_task(self):
        artist = db.Artist.create(name="Pending Artist")
        task = db.ReviewTask.create(
            entity_type="artist",
            entity_id=str(artist.id),
            task_type="metadata_review",
            status="pending",
            reason="missing_image",
            snapshot_json='{"issues": ["missing_image"]}',
        )

        with self.assertRaisesRegex(ValueError, "Only confirmed or dismissed review tasks can be reopened"):
            reopenMetadataReviewTask(task)

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

        self.assertEqual(created_count, 2)
        combined_logs = "\n".join(captured.output)
        self.assertIn("Pending review tasks after bootstrap:", combined_logs)
        self.assertIn("title=Bootstrap Artist", combined_logs)
        self.assertIn("reason=missing_image", combined_logs)
        self.assertIn("Removed superseded new-artist review task", combined_logs)


if __name__ == "__main__":
    unittest.main()
