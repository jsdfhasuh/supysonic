import json
import os
import tempfile
import unittest

from supysonic.db import Album, Artist, Folder, Track
from supysonic.scanner_func.scanner_album_enrich import (
    applyAlbumEnrichment,
    collectAlbumsNeedingEnrichment,
    runAlbumEnrichmentPass,
)

from ..testbase import TestBase


class AlbumEnrichmentPipelineTestCase(TestBase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.artist = Artist.create(name="Enrichment Artist")
        self.root = Folder.create(root=True, name="Root", path=self.media_root)

    def createAlbumFixture(self, name="Enrichment Album", year=None, genre=None):
        album_dir = os.path.join(self.media_root, name.replace(" ", "-"))
        folder = Folder.create(root=False, name=name, path=album_dir, parent=self.root)
        album = Album.create(name=name, artist=self.artist, year=year)
        Track.create(
            disc=1,
            number=1,
            title=f"{name} Track",
            year=None,
            genre=genre,
            duration=120,
            has_art=False,
            album=album,
            artist=self.artist,
            bitrate=320,
            path=os.path.join(album_dir, "track.flac"),
            last_modification=1,
            root_folder=self.root,
            folder=folder,
        )
        return album

    def createTwoAlbumEnrichmentFixtures(self):
        return [
            self.createAlbumFixture(name="First Album"),
            self.createAlbumFixture(name="Second Album"),
        ]

    def test_apply_enrichment_fills_empty_album_fields_only(self):
        album = self.createAlbumFixture(year="1999")

        changes = applyAlbumEnrichment(
            album,
            {
                "year": "2024",
                "release_date": "2024-03-15",
                "release_type": "album",
                "primary_genre": "Rock",
                "providers_used": ["musicbrainz", "discogs"],
            },
        )

        updated = Album[album.id]
        self.assertEqual(updated.year, "1999")
        self.assertEqual(updated.release_date, "2024-03-15")
        self.assertEqual(updated.release_type, "album")
        self.assertIn("release_date", changes["album"])

    def test_apply_enrichment_backfills_empty_track_genre_only(self):
        album = self.createAlbumFixture(genre=None)
        empty_track = album.tracks.first()

        changes = applyAlbumEnrichment(album, {"primary_genre": "Rock"})

        self.assertEqual(Track[empty_track.id].genre, "Rock")
        self.assertIn(str(empty_track.id), changes["tracks"]["genre"])

    def test_apply_enrichment_records_album_info_json(self):
        album = self.createAlbumFixture()

        applyAlbumEnrichment(
            album,
            {"musicbrainz_id": "mbid", "providers_used": ["musicbrainz"]},
        )

        info = json.loads(Album[album.id].album_info_json)
        self.assertEqual(info["musicbrainz_id"], "mbid")
        self.assertEqual(info["providers_used"], ["musicbrainz"])

    def test_collect_albums_needing_enrichment_skips_complete_album(self):
        album = self.createAlbumFixture(year="2024")
        album.release_date = "2024-03-15"
        album.release_type = "album"
        album.album_info_json = json.dumps({"primary_genre": "Rock"})
        album.save()

        candidates = list(collectAlbumsNeedingEnrichment())

        self.assertNotIn(album.id, {candidate.id for candidate in candidates})

    def test_album_enrichment_pass_continues_after_provider_failure(self):
        album = self.createAlbumFixture()

        class FailingMusicBrainzClient:
            def search_album(self, artist_name, album_name):
                raise RuntimeError("provider down")

        class DiscogsClientStub:
            def is_enabled(self):
                return True

            def search_album(self, artist_name, album_name):
                return {
                    "title": "Enrichment Artist - Enrichment Album",
                    "genres": ["Rock"],
                }

        scanner = type("ScannerStub", (), {})()

        with self.assertLogs("supysonic.scanner_func.scanner_album_enrich", level="WARNING"):
            runAlbumEnrichmentPass(
                scanner,
                albums=[album],
                musicbrainz_client=FailingMusicBrainzClient(),
                discogs_client=DiscogsClientStub(),
            )

        info = json.loads(Album[album.id].album_info_json)
        self.assertEqual(info["primary_genre"], "Rock")
        self.assertIn(album.id, scanner.review_task_enriched_album_ids)

    def test_album_enrichment_pass_continues_when_discogs_enabled_check_fails(self):
        album = self.createAlbumFixture()

        class MusicBrainzClientStub:
            def search_album(self, artist_name, album_name):
                return {
                    "title": album_name,
                    "artist-credit": [{"artist": {"name": artist_name}}],
                    "date": "2024-03-15",
                    "release-group": {"primary-type": "Album"},
                }

        class FailingDiscogsClient:
            def is_enabled(self):
                raise RuntimeError("discogs config failed")

        scanner = type("ScannerStub", (), {})()

        with self.assertLogs("supysonic.scanner_func.scanner_album_enrich", level="WARNING") as logs:
            runAlbumEnrichmentPass(
                scanner,
                albums=[album],
                musicbrainz_client=MusicBrainzClientStub(),
                discogs_client=FailingDiscogsClient(),
            )

        output = "\n".join(logs.output)
        self.assertIn("event=album_enrichment_provider_result", output)
        self.assertIn("provider=discogs", output)
        self.assertIn("result=failed", output)
        self.assertIn("reason=enabled_check_failed", output)
        self.assertEqual(Album[album.id].release_date, "2024-03-15")
        self.assertIn(album.id, scanner.review_task_enriched_album_ids)

    def test_album_enrichment_pass_logs_structured_success_and_summary(self):
        album = self.createAlbumFixture()

        class MusicBrainzClientStub:
            def search_album(self, artist_name, album_name):
                return {
                    "title": album_name,
                    "artist-credit": [{"artist": {"name": artist_name}}],
                    "date": "2024-03-15",
                    "release-group": {"primary-type": "Album"},
                }

        class DiscogsClientStub:
            def is_enabled(self):
                return True

            def search_album(self, artist_name, album_name):
                return {
                    "title": f"{artist_name} - {album_name}",
                    "genres": ["Rock"],
                    "styles": ["Indie Rock"],
                }

        scanner = type("ScannerStub", (), {})()

        with self.assertLogs("supysonic.scanner_func.scanner_album_enrich", level="INFO") as logs:
            runAlbumEnrichmentPass(
                scanner,
                albums=[album],
                musicbrainz_client=MusicBrainzClientStub(),
                discogs_client=DiscogsClientStub(),
            )

        output = "\n".join(logs.output)
        self.assertIn("scanner event=album_enrichment_pass_start", output)
        self.assertIn("total_albums=1", output)
        self.assertIn("discogs_enabled=true", output)
        self.assertIn("event=album_enrichment_provider_result", output)
        self.assertIn("provider=musicbrainz", output)
        self.assertIn("provider=discogs", output)
        self.assertIn("result=matched", output)
        self.assertIn("event=album_enrichment_applied", output)
        self.assertIn(f"album_id={album.id}", output)
        self.assertIn("changed_album_fields=year,release_date,release_type,album_info_json", output)
        self.assertIn("changed_track_year_count=1", output)
        self.assertIn("changed_track_genre_count=1", output)
        self.assertIn("event=album_enrichment_pass_end", output)
        self.assertIn("processed=1", output)
        self.assertIn("matched=1", output)
        self.assertIn("applied=1", output)
        self.assertIn("failed=0", output)

    def test_album_enrichment_pass_skips_unrelated_provider_matches(self):
        album = self.createAlbumFixture()
        track = album.tracks.first()

        class MusicBrainzClientStub:
            def search_album(self, artist_name, album_name):
                return {
                    "title": "Kind of Blue",
                    "artist-credit": [{"artist": {"name": "Miles Davis"}}],
                    "date": "1959-08-17",
                    "release-group": {"primary-type": "Album"},
                }

        class DiscogsClientStub:
            def is_enabled(self):
                return True

            def search_album(self, artist_name, album_name):
                return {
                    "title": "Miles Davis - Kind of Blue",
                    "genres": ["Jazz"],
                    "styles": ["Modal"],
                }

        scanner = type("ScannerStub", (), {})()

        with self.assertLogs("supysonic.scanner_func.scanner_album_enrich", level="INFO") as logs:
            runAlbumEnrichmentPass(
                scanner,
                albums=[album],
                musicbrainz_client=MusicBrainzClientStub(),
                discogs_client=DiscogsClientStub(),
            )

        output = "\n".join(logs.output)
        self.assertIn("event=album_enrichment_provider_result", output)
        self.assertIn("result=skipped", output)
        self.assertIn("reason=candidate_mismatch", output)
        self.assertIn('candidate_artist="Miles Davis"', output)
        self.assertIn('candidate_album="Kind of Blue"', output)
        self.assertIn("event=album_enrichment_pass_end", output)
        self.assertIn("matched=0", output)
        self.assertIn("applied=0", output)
        self.assertIn("skipped=1", output)

        updated = Album[album.id]
        self.assertIsNone(updated.year)
        self.assertIsNone(updated.release_date)
        self.assertIsNone(updated.release_type)
        self.assertIsNone(updated.album_info_json)
        self.assertIsNone(Track[track.id].genre)
        self.assertFalse(hasattr(scanner, "review_task_enriched_album_ids"))

    def test_album_enrichment_pass_logs_no_change_for_existing_metadata(self):
        album = self.createAlbumFixture(year="2024", genre="Rock")
        track = album.tracks.first()
        track.year = 2024
        track.save()
        album.release_date = "2024-03-15"
        album.release_type = "album"
        album.album_info_json = json.dumps(
            {
                "musicbrainz_id": "mb-release-id",
                "primary_genre": "Rock",
                "providers_used": ["musicbrainz"],
                "source_urls": {
                    "musicbrainz": "https://musicbrainz.org/release/mb-release-id",
                },
            }
        )
        album.save()

        class MusicBrainzClientStub:
            def search_album(self, artist_name, album_name):
                return {
                    "id": "mb-release-id",
                    "title": album_name,
                    "artist-credit": [{"artist": {"name": artist_name}}],
                    "date": "2024-03-15",
                    "release-group": {"primary-type": "Album"},
                }

        scanner = type("ScannerStub", (), {})()

        with self.assertLogs("supysonic.scanner_func.scanner_album_enrich", level="INFO") as logs:
            runAlbumEnrichmentPass(
                scanner,
                albums=[album],
                musicbrainz_client=MusicBrainzClientStub(),
                discogs_client=None,
            )

        output = "\n".join(logs.output)
        self.assertIn("event=album_enrichment_no_change", output)
        self.assertIn(f"album_id={album.id}", output)
        self.assertIn("providers=musicbrainz", output)
        self.assertIn("matched=1", output)
        self.assertIn("applied=0", output)
        self.assertIn("skipped=1", output)
        self.assertFalse(hasattr(scanner, "review_task_enriched_album_ids"))

    def test_album_enrichment_pass_continues_after_single_album_failure(self):
        albums = self.createTwoAlbumEnrichmentFixtures()

        class MusicBrainzClientStub:
            def search_album(self, artist_name, album_name):
                if album_name == albums[0].name:
                    raise RuntimeError("first album failed")
                return {
                    "title": album_name,
                    "artist-credit": [{"artist": {"name": artist_name}}],
                    "date": "2024",
                    "release-group": {"primary-type": "Album"},
                }

        scanner = type("ScannerStub", (), {})()

        with self.assertLogs("supysonic.scanner_func.scanner_album_enrich", level="WARNING"):
            runAlbumEnrichmentPass(
                scanner,
                albums=albums,
                musicbrainz_client=MusicBrainzClientStub(),
                discogs_client=None,
            )

        self.assertIsNone(Album[albums[0].id].release_date)
        self.assertEqual(Album[albums[1].id].release_date, "2024")


if __name__ == "__main__":
    unittest.main()
