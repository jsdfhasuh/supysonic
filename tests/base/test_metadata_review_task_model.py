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

    def tearDown(self):
        db.release_database()
        shutil.rmtree(self._db_dir)

    def test_album_review_task_can_be_created(self):
        artist = db.Artist.create(name="Review Artist")
        album = db.Album.create(artist=artist, name="Review Album")

        task = db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json='{"album_name": "Review Album"}',
        )

        saved_task = db.ReviewTask.get_by_id(task.id)
        self.assertEqual(saved_task.entity_type, "album")
        self.assertEqual(saved_task.entity_id, str(album.id))
        self.assertEqual(saved_task.task_type, "metadata_review")
        self.assertEqual(saved_task.status, "pending")
        self.assertEqual(saved_task.reason, "new_album")
        self.assertEqual(saved_task.snapshot_json, '{"album_name": "Review Album"}')
        self.assertEqual(saved_task.pending_key, f"album:{album.id}:pending")
        self.assertIsNotNone(saved_task.created)
        self.assertIsNotNone(saved_task.updated)
        self.assertIsNone(saved_task.resolved_at)
        self.assertIsNone(saved_task.expires_at)

    def test_artist_review_task_can_be_created_with_reason_scoped_pending_key(self):
        artist = db.Artist.create(name="Image Less Artist")

        task = db.ReviewTask.create(
            entity_type="artist",
            entity_id=str(artist.id),
            task_type="metadata_review",
            status="pending",
            reason="missing_image",
            snapshot_json='{"artist_name": "Image Less Artist"}',
        )

        saved_task = db.ReviewTask.get_by_id(task.id)
        self.assertEqual(saved_task.pending_key, f"artist:{artist.id}:pending:missing_image")

    def test_missing_year_function_creates_tasks_for_albums_without_year(self):
        from supysonic.scanner_func.scanner_review_tasks import createMissingYearAlbumReviewTasks

        artist = db.Artist.create(name="Artist No Year")
        album = db.Album.create(artist=artist, name="No Year Album", year=None)

        createMissingYearAlbumReviewTasks()

        task = db.ReviewTask.get_or_none(
            db.ReviewTask.entity_type == "album",
            db.ReviewTask.entity_id == str(album.id),
            db.ReviewTask.status == "pending",
        )
        self.assertIsNotNone(task)
        self.assertEqual(task.reason, "missing_year")

    def test_missing_year_function_skips_album_with_existing_pending_task(self):
        from supysonic.scanner_func.scanner_review_tasks import createMissingYearAlbumReviewTasks

        artist = db.Artist.create(name="Artist Dupe")
        album = db.Album.create(artist=artist, name="Already Pending Album", year=None)
        db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="pending",
            reason="new_album",
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
        db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="confirmed",
            reason="new_album",
        )

        created_count = createMissingYearAlbumReviewTasks()
        self.assertEqual(created_count, 1)

        task = db.ReviewTask.get_or_none(
            db.ReviewTask.entity_type == "album",
            db.ReviewTask.entity_id == str(album.id),
            db.ReviewTask.status == "pending",
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

        db.ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json="{}",
        )

        with self.assertRaises(IntegrityError):
            db.ReviewTask.create(
                entity_type="album",
                entity_id=str(album.id),
                task_type="metadata_review",
                status="pending",
                reason="missing_year",
                snapshot_json="{}",
            )

    def test_artist_pending_review_task_uniqueness_is_scoped_by_reason(self):
        artist = db.Artist.create(name="Scoped Pending Artist")

        db.ReviewTask.create(
            entity_type="artist",
            entity_id=str(artist.id),
            task_type="metadata_review",
            status="pending",
            reason="new_artist",
            snapshot_json="{}",
        )

        db.ReviewTask.create(
            entity_type="artist",
            entity_id=str(artist.id),
            task_type="metadata_review",
            status="pending",
            reason="missing_image",
            snapshot_json="{}",
        )

        with self.assertRaises(IntegrityError):
            db.ReviewTask.create(
                entity_type="artist",
                entity_id=str(artist.id),
                task_type="metadata_review",
                status="pending",
                reason="missing_image",
                snapshot_json="{}",
            )

    def test_sqlite_review_task_migrations_apply_in_order(self):
        migration_dir = Path(__file__).resolve().parents[2] / "supysonic" / "schema" / "migration" / "sqlite"

        db.db.execute_sql("DROP TABLE IF EXISTS review_task")
        db.db.execute_sql("DROP TABLE IF EXISTS album_review_task")
        migration_20260428 = (migration_dir / "20260428.sql").read_text(encoding="utf-8")
        migration_20260429 = (migration_dir / "20260429.sql").read_text(encoding="utf-8")

        for statement in migration_20260428.split(";"):
            if statement.strip():
                db.db.execute_sql(statement)
        for statement in migration_20260429.split(";"):
            if statement.strip():
                db.db.execute_sql(statement)

        migration_20260503 = (migration_dir / "20260503.py").read_text(encoding="utf-8")
        namespace = {}
        exec(migration_20260503, namespace)
        namespace["apply"]({"database": os.path.join(self._db_dir, 'metadata-review.db')})

        columns = {row[1] for row in db.db.execute_sql("PRAGMA table_info(review_task)").fetchall()}
        self.assertIn("pending_key", columns)
        self.assertIn("entity_type", columns)
        self.assertIn("entity_id", columns)
        self.assertIn("expires_at", columns)

    def test_postgres_review_task_migration_is_safe_for_semicolon_split_executor(self):
        migration_path = (
            Path(__file__).resolve().parents[2]
            / "supysonic"
            / "schema"
            / "migration"
            / "postgres"
            / "20260503.sql"
        )

        statements = [statement.strip() for statement in migration_path.read_text(encoding="utf-8").split(";") if statement.strip()]

        self.assertTrue(statements)
        self.assertTrue(all("$$" not in statement for statement in statements))
