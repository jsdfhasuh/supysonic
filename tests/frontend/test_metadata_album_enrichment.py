import json
import unittest
from pathlib import Path

from flask import current_app

from supysonic.db import (
    Album,
    AlbumArtist,
    AlbumReviewTask,
    Artist,
    Folder,
    Track,
    TrackArtist,
    User,
)

from .frontendtestbase import FrontendTestBase
from ..testbase import TestConfig


class MetadataAlbumEnrichmentTestCase(FrontendTestBase):
    __with_api__ = True

    def setUp(self):
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["log_dir"] = ""
        super().setUp()

        alice = User.get(User.name == "alice")
        with self.client.session_transaction() as session:
            session["userid"] = str(alice.id)

        with self.app_context():
            view_functions = current_app.view_functions
            if "emo.list_logs" not in view_functions:
                current_app.add_url_rule(
                    "/emo/test-logs",
                    endpoint="emo.list_logs",
                    view_func=lambda: "",
                )

        self.artist = Artist.create(name="Enriched Artist")
        self.album = Album.create(
            name="Enriched Album",
            artist=self.artist,
            year="2024",
            release_date="2024-03-15",
            release_type="album",
            album_info_json=json.dumps(
                {
                    "providers_used": ["musicbrainz", "discogs"],
                    "styles": ["Indie Rock"],
                    "primary_genre": "Rock",
                    "musicbrainz_id": "mbid",
                    "discogs_id": "123",
                }
            ),
        )
        self.root = Folder.create(root=True, name="Root", path="/tmp/root")
        self.folder = Folder.create(
            root=False,
            name="Album",
            path="/tmp/root/album",
            parent=self.root,
        )
        self.track = Track.create(
            disc=1,
            number=1,
            title="First Track",
            duration=120,
            has_art=False,
            album=self.album,
            artist=self.artist,
            bitrate=320,
            path="/tmp/enriched-track.flac",
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
            reason="external_enrichment",
            snapshot_json=json.dumps(
                {
                    "album_name": "Enriched Album",
                    "artist_name": "Enriched Artist",
                    "year": "2024",
                    "release_date": "2024-03-15",
                    "release_type": "album",
                    "track_count": 1,
                    "enrichment": {
                        "providers_used": ["musicbrainz", "discogs"],
                        "styles": ["Indie Rock"],
                        "primary_genre": "Rock",
                    },
                }
            ),
        )

    def test_review_task_renders_album_enrichment_summary(self):
        rv = self.client.get(f"/metadata/review-tasks/{self.task.id}")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("External enrichment", rv.data)
        self.assertIn("Release date", rv.data)
        self.assertIn("2024-03-15", rv.data)
        self.assertIn("Release type", rv.data)
        self.assertIn("album", rv.data)
        self.assertIn("Styles", rv.data)
        self.assertIn("Indie Rock", rv.data)
        self.assertIn("Providers", rv.data)
        self.assertIn("MusicBrainz, Discogs", rv.data)

    def test_metadata_inbox_renders_external_enrichment_summary(self):
        rv = self.client.get("/metadata?tab=inbox")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("External enrichment: MusicBrainz, Discogs", rv.data)
        self.assertIn("Release type: album", rv.data)
        self.assertIn("Primary genre: Rock", rv.data)

    def test_album_content_template_exposes_enrichment_fields(self):
        template_path = (
            Path(__file__).resolve().parents[2]
            / "supysonic"
            / "templates"
            / "partials"
            / "metadata-album-content.html"
        )
        template = template_path.read_text(encoding="utf-8")

        self.assertIn("External enrichment", template)
        self.assertIn("id=\"releaseDate\"", template)
        self.assertIn("id=\"releaseType\"", template)
        self.assertIn("id=\"styles\"", template)
        self.assertIn("album.releaseDate", template)
        self.assertIn("album.releaseType", template)
        self.assertIn("album.styles", template)
        self.assertIn("album.musicBrainzId", template)
        self.assertIn("album.discogsId", template)


if __name__ == "__main__":
    unittest.main()
