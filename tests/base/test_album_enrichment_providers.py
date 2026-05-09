import unittest

import requests

from supysonic.discogs import DiscogsClient
from supysonic.scanner_func.scanner_album_enrich import (
    isAlbumMatchCandidate,
    mergeAlbumEnrichment,
    normalizeDiscogsAlbum,
    normalizeMusicBrainzAlbum,
)


class AlbumEnrichmentProviderTestCase(unittest.TestCase):
    def test_musicbrainz_normalizer_extracts_release_date_year_and_type(self):
        payload = {
            "id": "mb-release-id",
            "date": "2024-03-15",
            "release-group": {"primary-type": "Album"},
        }

        result = normalizeMusicBrainzAlbum(payload)

        self.assertEqual(result["musicbrainz_id"], "mb-release-id")
        self.assertEqual(result["release_date"], "2024-03-15")
        self.assertEqual(result["year"], "2024")
        self.assertEqual(result["release_type"], "album")

    def test_discogs_primary_genre_prefers_first_genre(self):
        payload = {"id": 123, "genres": ["Rock"], "styles": ["Indie Rock"]}

        result = normalizeDiscogsAlbum(payload)

        self.assertEqual(result["discogs_id"], "123")
        self.assertEqual(result["genres"], ["Rock"])
        self.assertEqual(result["styles"], ["Indie Rock"])
        self.assertEqual(result["primary_genre"], "Rock")

    def test_merge_keeps_musicbrainz_structured_fields_and_discogs_taxonomy(self):
        result = mergeAlbumEnrichment(
            {"release_date": "2024", "year": "2024", "release_type": "album"},
            {"genres": ["Rock"], "styles": ["Indie Rock"], "primary_genre": "Rock"},
        )

        self.assertEqual(result["release_date"], "2024")
        self.assertEqual(result["primary_genre"], "Rock")

    def test_matching_guard_rejects_obviously_unrelated_album(self):
        self.assertFalse(
            isAlbumMatchCandidate(
                artist_name="Radiohead",
                album_name="OK Computer",
                candidate_artist="Miles Davis",
                candidate_album="Kind of Blue",
            )
        )

    def test_discogs_client_is_disabled_without_token_even_when_enabled(self):
        client = DiscogsClient(
            {
                "enabled": True,
                "token": "",
                "api_url": "https://api.discogs.com",
                "user_agent": "Supysonic/1.0",
            }
        )

        self.assertFalse(client.is_enabled())
        self.assertEqual(client.search_album("Artist", "Album"), {})

    def test_discogs_client_is_disabled_with_missing_config(self):
        client = DiscogsClient({})

        self.assertFalse(client.is_enabled())
        self.assertEqual(client.search_album("Artist", "Album"), {})

    def test_discogs_client_returns_empty_on_rate_limit(self):
        class ResponseStub:
            status_code = 429

            def json(self):
                return {}

        client = DiscogsClient(
            {
                "enabled": True,
                "token": "secret-token",
                "api_url": "https://api.discogs.com",
                "user_agent": "Supysonic/1.0",
            },
            request_get=lambda *args, **kwargs: ResponseStub(),
        )

        with self.assertLogs("supysonic.discogs", level="WARNING"):
            result = client.search_album("Artist", "Album")

        self.assertEqual(result, {})

    def test_discogs_client_returns_empty_on_http_error(self):
        class ResponseStub:
            status_code = 500

            def json(self):
                return {"message": "server error"}

        client = DiscogsClient(
            {
                "enabled": True,
                "token": "secret-token",
                "api_url": "https://api.discogs.com",
                "user_agent": "Supysonic/1.0",
            },
            request_get=lambda *args, **kwargs: ResponseStub(),
        )

        with self.assertLogs("supysonic.discogs", level="WARNING"):
            result = client.search_album("Artist", "Album")

        self.assertEqual(result, {})

    def test_discogs_client_returns_empty_on_network_error(self):
        def raise_timeout(*args, **kwargs):
            raise requests.exceptions.Timeout("timeout")

        client = DiscogsClient(
            {
                "enabled": True,
                "token": "secret-token",
                "api_url": "https://api.discogs.com",
                "user_agent": "Supysonic/1.0",
            },
            request_get=raise_timeout,
        )

        with self.assertLogs("supysonic.discogs", level="WARNING"):
            result = client.search_album("Artist", "Album")

        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
