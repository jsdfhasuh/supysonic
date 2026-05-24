import json
import unittest
from datetime import timedelta

from supysonic.db import Album, Artist, ReviewTask, now
from supysonic.scanner_func.scanner_review_tasks import (
    EXTERNAL_ENRICHMENT_REVIEW_REASON,
    METADATA_REVIEW_TASK_TYPE,
    buildAlbumReviewSnapshot,
    createReviewTasks,
)

from ..testbase import TestBase


class AlbumEnrichmentReviewTaskTestCase(TestBase):
    def createAlbum(self):
        artist = Artist.create(name="Enrichment Review Artist")
        return Album.create(name="Enrichment Review Album", artist=artist, year="2024")

    def test_album_review_snapshot_includes_enrichment_summary(self):
        album = self.createAlbum()
        album.album_info_json = json.dumps({"providers_used": ["musicbrainz"]})
        album.release_date = "2024-03-15"
        album.release_type = "album"
        album.save()

        snapshot = json.loads(buildAlbumReviewSnapshot(album))

        self.assertEqual(snapshot["release_date"], "2024-03-15")
        self.assertEqual(snapshot["release_type"], "album")
        self.assertEqual(snapshot["enrichment"]["providers_used"], ["musicbrainz"])

    def test_external_enrichment_creates_album_review_task(self):
        album = self.createAlbum()
        scanner = type("ScannerStub", (), {"review_task_enriched_album_ids": {album.id}})()

        with self.assertLogs("supysonic.scanner_func.scanner_review_tasks", level="INFO") as logs:
            createReviewTasks(scanner)

        task = ReviewTask.get(ReviewTask.entity_id == str(album.id))
        self.assertEqual(task.reason, EXTERNAL_ENRICHMENT_REVIEW_REASON)
        self.assertEqual(task.pending_key, f"album:{album.id}:pending:external_enrichment")
        self.assertIsNotNone(task.expires_at)
        self.assertGreaterEqual(task.expires_at, now() + timedelta(days=2))
        self.assertLessEqual(task.expires_at, now() + timedelta(days=3, seconds=1))
        output = "\n".join(logs.output)
        self.assertIn("scanner event=external_enrichment_review_task_created", output)
        self.assertIn(f"album_id={album.id}", output)
        self.assertIn(f"task_id={task.id}", output)
        self.assertIn("reason=external_enrichment", output)

    def test_external_enrichment_updates_existing_pending_album_task(self):
        album = self.createAlbum()
        ReviewTask.create(
            entity_type="album",
            entity_id=str(album.id),
            task_type=METADATA_REVIEW_TASK_TYPE,
            status="pending",
            reason="new_album",
            snapshot_json="{}",
        )
        scanner = type("ScannerStub", (), {"review_task_enriched_album_ids": {album.id}})()

        with self.assertLogs("supysonic.scanner_func.scanner_review_tasks", level="INFO") as logs:
            createReviewTasks(scanner)

        tasks = ReviewTask.select().where(ReviewTask.entity_id == str(album.id))
        task = tasks.get()
        self.assertEqual(tasks.count(), 1)
        self.assertEqual(task.reason, "new_album")
        self.assertIn("Enrichment Review Album", task.snapshot_json)
        output = "\n".join(logs.output)
        self.assertIn("scanner event=external_enrichment_review_task_updated", output)
        self.assertIn(f"album_id={album.id}", output)
        self.assertIn(f"task_id={task.id}", output)
        self.assertIn("reason=new_album", output)


if __name__ == "__main__":
    unittest.main()
