import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from supysonic import db
from peewee import IntegrityError


class MetadataReviewTaskModelTestCase(unittest.TestCase):
    def setUp(self):
        self._db_dir = tempfile.mkdtemp()
        db.init_database(f"sqlite:///{os.path.join(self._db_dir, 'metadata-review.db')}")
        db.db.execute_sql("ALTER TABLE album ADD COLUMN year VARCHAR(255)")
        db.db.execute_sql("ALTER TABLE artist ADD COLUMN artist_info_json VARCHAR(4096)")
        db.db.execute_sql("ALTER TABLE artist ADD COLUMN real_artist_id INTEGER")

    def tearDown(self):
        db.release_database()
        shutil.rmtree(self._db_dir)

    def test_album_review_task_can_be_created(self):
        artist = db.Artist.create(name="Review Artist")
        album = db.Album.create(artist=artist, name="Review Album")

        task = db.AlbumReviewTask.create(
            album=album,
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json='{"album_name": "Review Album"}',
        )

        saved_task = db.AlbumReviewTask.get_by_id(task.id)
        self.assertEqual(saved_task.album_id, album.id)
        self.assertEqual(saved_task.task_type, "metadata_review")
        self.assertEqual(saved_task.status, "pending")
        self.assertEqual(saved_task.reason, "new_album")
        self.assertEqual(saved_task.snapshot_json, '{"album_name": "Review Album"}')
        self.assertIsNotNone(saved_task.created)
        self.assertIsNotNone(saved_task.updated)
        self.assertIsNone(saved_task.resolved_at)

    def test_missing_year_function_creates_tasks_for_albums_without_year(self):
        from supysonic.scanner_func.scanner_review_tasks import createMissingYearAlbumReviewTasks

        artist = db.Artist.create(name="Artist No Year")
        album = db.Album.create(artist=artist, name="No Year Album", year=None)

        createMissingYearAlbumReviewTasks()

        task = db.AlbumReviewTask.get_or_none(
            db.AlbumReviewTask.album == album,
            db.AlbumReviewTask.status == "pending",
        )
        self.assertIsNotNone(task)
        self.assertEqual(task.reason, "missing_year")

    def test_missing_year_function_skips_album_with_existing_pending_task(self):
        from supysonic.scanner_func.scanner_review_tasks import createMissingYearAlbumReviewTasks

        artist = db.Artist.create(name="Artist Dupe")
        album = db.Album.create(artist=artist, name="Already Pending Album", year=None)
        db.AlbumReviewTask.create(
            album=album, task_type="metadata_review", status="pending", reason="new_album",
        )

        created_count = createMissingYearAlbumReviewTasks()
        self.assertEqual(created_count, 0)

    def test_missing_year_function_skips_album_with_year(self):
        from supysonic.scanner_func.scanner_review_tasks import createMissingYearAlbumReviewTasks

        artist = db.Artist.create(name="Artist With Year")
        db.Album.create(artist=artist, name="Has Year Album", year="2020")

        created_count = createMissingYearAlbumReviewTasks()
        self.assertEqual(created_count, 0)

    def test_missing_year_function_allows_new_task_when_old_is_closed(self):
        from supysonic.scanner_func.scanner_review_tasks import createMissingYearAlbumReviewTasks

        artist = db.Artist.create(name="Artist Closed")
        album = db.Album.create(artist=artist, name="Closed But Still No Year", year=None)
        db.AlbumReviewTask.create(
            album=album, task_type="metadata_review", status="confirmed", reason="new_album",
        )

        created_count = createMissingYearAlbumReviewTasks()
        self.assertEqual(created_count, 1)

        task = db.AlbumReviewTask.get_or_none(
            db.AlbumReviewTask.album == album,
            db.AlbumReviewTask.status == "pending",
        )
        self.assertIsNotNone(task)
        self.assertEqual(task.reason, "missing_year")

    def test_missing_year_bootstrap_opens_and_closes_database_connection(self):
        from supysonic.scanner_func.scanner_review_tasks import runMissingYearAlbumReviewBootstrap

        with patch("supysonic.scanner_func.scanner_review_tasks.open_connection") as open_connection, patch(
            "supysonic.scanner_func.scanner_review_tasks.close_connection"
        ) as close_connection, patch(
            "supysonic.scanner_func.scanner_review_tasks.createMissingYearAlbumReviewTasks",
            return_value=3,
        ) as create_missing_year:
            created_count = runMissingYearAlbumReviewBootstrap()

        self.assertEqual(created_count, 3)
        open_connection.assert_called_once_with(reuse=True)
        create_missing_year.assert_called_once_with()
        close_connection.assert_called_once_with()

    def test_pending_review_task_uniqueness_is_enforced_by_database(self):
        artist = db.Artist.create(name="Unique Pending Artist")
        album = db.Album.create(artist=artist, name="Unique Pending Album", year=None)

        db.AlbumReviewTask.create(
            album=album,
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json="{}",
            pending_key=f"{album.id}:pending",
        )

        with self.assertRaises(IntegrityError):
            db.AlbumReviewTask.create(
                album=album,
                task_type="metadata_review",
                status="pending",
                reason="missing_year",
                snapshot_json="{}",
                pending_key=f"{album.id}:pending",
            )

    def test_sqlite_review_task_migrations_apply_in_order(self):
        migration_dir = Path(__file__).resolve().parents[2] / "supysonic" / "schema" / "migration" / "sqlite"

        db.db.execute_sql("DROP TABLE album_review_task")
        migration_20260428 = (migration_dir / "20260428.sql").read_text(encoding="utf-8")
        migration_20260429 = (migration_dir / "20260429.sql").read_text(encoding="utf-8")

        for statement in migration_20260428.split(";"):
            if statement.strip():
                db.db.execute_sql(statement)
        for statement in migration_20260429.split(";"):
            if statement.strip():
                db.db.execute_sql(statement)

        columns = {row[1] for row in db.db.execute_sql("PRAGMA table_info(album_review_task)").fetchall()}
        self.assertIn("pending_key", columns)
