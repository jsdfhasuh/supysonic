import os
import tempfile
import unittest

from types import SimpleNamespace
from unittest.mock import Mock, patch

from supysonic.scanner_func.scanner_enrich import repairAlbumYear, repairArtistProfiles, repairMissingArtistImages


class ScannerRepairTraceTestCase(unittest.TestCase):
    def test_repair_album_year_logs_track_year_hit(self):
        scanner = SimpleNamespace(stats=lambda: SimpleNamespace(lost_year_albums={"Album": "/music/Album"}))
        album = SimpleNamespace(
            id=5,
            name="Album",
            year=None,
            artist=SimpleNamespace(get_artist_name=lambda: "Artist"),
            save=Mock(),
        )
        track_query = Mock()
        track_query.where.return_value.first.return_value = SimpleNamespace(year="2024", path="/music/Album/track.flac")

        with patch("supysonic.scanner_func.scanner_enrich.Track.select", return_value=track_query), patch(
            "supysonic.scanner_func.scanner_enrich.logTrace",
            create=True,
        ) as log_trace:
            result = repairAlbumYear(scanner, album)

        self.assertTrue(result)
        self.assertEqual(album.year, "2024")
        _, trace_type, header_fields, detail_lines = log_trace.call_args[0]
        self.assertEqual(trace_type, "REPAIR_TRACE")
        self.assertEqual(header_fields["album"], "Album")
        self.assertIn("repair type: album year", detail_lines)
        self.assertIn("year source: track metadata", detail_lines)
        self.assertIn("repair result: success", detail_lines)

    def test_repair_album_year_logs_failed_repair(self):
        scanner = SimpleNamespace(stats=lambda: SimpleNamespace(lost_year_albums={"Album": "/music/Album"}))
        album = SimpleNamespace(
            id=5,
            name="Album",
            year=None,
            artist=SimpleNamespace(get_artist_name=lambda: "Artist"),
            save=Mock(),
        )
        track_query = Mock()
        track_query.where.return_value.first.return_value = None

        with patch("supysonic.scanner_func.scanner_enrich.Track.select", return_value=track_query), patch(
            "supysonic.scanner_func.scanner_enrich.search_musicbrainz_album",
            return_value=None,
        ), patch(
            "supysonic.scanner_func.scanner_enrich.logTrace",
            create=True,
        ) as log_trace:
            result = repairAlbumYear(scanner, album)

        self.assertFalse(result)
        _, trace_type, _, detail_lines = log_trace.call_args[0]
        self.assertEqual(trace_type, "REPAIR_TRACE")
        self.assertIn("year source: track metadata miss", detail_lines)
        self.assertIn("year source: musicbrainz miss", detail_lines)
        self.assertIn("repair result: no year found", detail_lines)

    def test_repair_album_year_does_not_print_musicbrainz_year(self):
        scanner = SimpleNamespace(stats=lambda: SimpleNamespace(lost_year_albums={"Album": "/music/Album"}))
        album = SimpleNamespace(
            id=5,
            name="Album",
            year=None,
            artist=SimpleNamespace(get_artist_name=lambda: "Artist"),
            save=Mock(),
        )
        track_query = Mock()
        track_query.where.return_value.first.return_value = None

        with patch("supysonic.scanner_func.scanner_enrich.Track.select", return_value=track_query), patch(
            "supysonic.scanner_func.scanner_enrich.search_musicbrainz_album",
            return_value={"id": "mbid-1"},
        ), patch(
            "supysonic.scanner_func.scanner_enrich.get_musicbrainz_album",
            return_value={"date": "2021-04-03"},
        ), patch(
            "supysonic.scanner_func.scanner_enrich.logTrace",
            create=True,
        ), patch("builtins.print") as print_mock:
            result = repairAlbumYear(scanner, album)

        self.assertTrue(result)
        self.assertEqual(album.year, "2021")
        print_mock.assert_not_called()

    def test_repair_artist_profiles_logs_successful_profile_repair(self):
        temp_dir = tempfile.mkdtemp()
        real_exists = os.path.exists
        scanner = SimpleNamespace(
            scan_config=SimpleNamespace(
                SPOTIFY={"client_id": "client-id"},
                LASTFM={"display_lang": "en"},
                BASE={"tempdatafolder": temp_dir},
            ),
            stats=lambda: SimpleNamespace(
                lost_covers=SimpleNamespace(artists=1),
                lost_covers_artists=["Artist"],
            ),
        )
        user = SimpleNamespace(lastfm_status=True)
        artist = SimpleNamespace(
            name="Artist",
            artist_info_json=None,
            get_artist_name=lambda: "Artist",
            save=Mock(),
        )
        sp = Mock()
        lfm = Mock()
        sp.get_artist_info.return_value = {
            "artists": {
                "items": [
                    {"images": [{"height": 640, "url": "https://example.com/large.png"}]}
                ]
            }
        }
        lfm.get_artistinfo.return_value = {
            "artist": {
                "name": "Artist",
                "url": "https://last.fm/artist",
                "bio": {"links": {"link": {"href": "https://wiki.example/artist"}}},
            }
        }
        lfm.get_lastfm_wiki.return_value = "Biography"

        with patch("supysonic.scanner_func.scanner_enrich.MySpotify", return_value=sp), patch(
            "supysonic.scanner_func.scanner_enrich.LastFm",
            return_value=lfm,
        ), patch(
            "supysonic.scanner_func.scanner_enrich.download_image",
            return_value=os.path.join(temp_dir, "artist", "Artist", "large.png"),
        ), patch(
            "supysonic.scanner_func.scanner_enrich.write_dict_to_json"
        ), patch(
            "supysonic.scanner_func.scanner_enrich.os.path.exists",
            side_effect=lambda path: path.endswith("info.json") or real_exists(path),
        ), patch(
            "supysonic.scanner_func.scanner_enrich.logTrace",
            create=True,
        ) as log_trace:
            repairArtistProfiles(scanner, [artist], get_cover_interner=True, user=user)

        _, trace_type, header_fields, detail_lines = log_trace.call_args[0]
        self.assertEqual(trace_type, "REPAIR_TRACE")
        self.assertEqual(header_fields["artist"], "Artist")
        self.assertIn("repair type: artist profile", detail_lines)
        self.assertIn("spotify images: hit", detail_lines)
        self.assertIn("lastfm biography: hit", detail_lines)
        self.assertIn("repair result: success", detail_lines)

    def test_repair_missing_artist_images_logs_missing_spotify_repair(self):
        scanner = SimpleNamespace(
            scan_config=SimpleNamespace(SPOTIFY={"client_id": "client-id"}),
        )
        user = SimpleNamespace(lastfm_status=True)
        artist = SimpleNamespace(name="Artist", artist_info_json="/tmp/info.json")
        sp = Mock()
        sp.get_artist_info.return_value = {"artists": {"items": []}}

        class FakeArtistInfoField:
            @staticmethod
            def is_null(_value):
                return None

        class FakeArtistModel:
            artist_info_json = FakeArtistInfoField()

            @staticmethod
            def select():
                select_result = Mock()
                select_result.where.return_value = [artist]
                return select_result

        with patch("supysonic.scanner_func.scanner_enrich.MySpotify", return_value=sp), patch(
            "supysonic.scanner_func.scanner_enrich.Artist",
            FakeArtistModel,
        ), patch(
            "supysonic.scanner_func.scanner_enrich.read_dict_from_json",
            return_value={"image": {"large": "/tmp/large.png"}},
        ), patch(
            "supysonic.scanner_func.scanner_enrich.os.path.exists",
            side_effect=lambda path: path == "/tmp/info.json",
        ), patch(
            "supysonic.scanner_func.scanner_enrich.logTrace",
            create=True,
        ) as log_trace:
            repairMissingArtistImages(scanner, get_cover_interner=True, user=user)

        _, trace_type, header_fields, detail_lines = log_trace.call_args[0]
        self.assertEqual(trace_type, "REPAIR_TRACE")
        self.assertEqual(header_fields["artist"], "Artist")
        self.assertIn("repair type: artist images", detail_lines)
        self.assertIn("missing image size: large", detail_lines)
        self.assertIn("spotify images: miss (empty result)", detail_lines)
        self.assertIn("repair result: no missing image restored", detail_lines)

    def test_repair_artist_profiles_distinguishes_empty_spotify_result(self):
        temp_dir = tempfile.mkdtemp()
        scanner = SimpleNamespace(
            scan_config=SimpleNamespace(
                SPOTIFY={"client_id": "client-id"},
                LASTFM={"display_lang": "en"},
                BASE={"tempdatafolder": temp_dir},
            ),
            stats=lambda: SimpleNamespace(
                lost_covers=SimpleNamespace(artists=1),
                lost_covers_artists=["Artist"],
            ),
        )
        user = SimpleNamespace(lastfm_status=True)
        artist = SimpleNamespace(name="Artist", get_artist_name=lambda: "Artist")
        sp = Mock()
        lfm = Mock()
        sp.get_artist_info.return_value = {"artists": {"items": []}}
        lfm.get_artistinfo.return_value = {
            "artist": {
                "name": "Artist",
                "url": "https://last.fm/artist",
                "bio": {"links": {"link": {"href": "https://wiki.example/artist"}}},
            }
        }

        with patch("supysonic.scanner_func.scanner_enrich.MySpotify", return_value=sp), patch(
            "supysonic.scanner_func.scanner_enrich.LastFm",
            return_value=lfm,
        ), patch(
            "supysonic.scanner_func.scanner_enrich.logTrace",
            create=True,
        ) as log_trace:
            repairArtistProfiles(scanner, [artist], get_cover_interner=True, user=user)

        _, _, _, detail_lines = log_trace.call_args[0]
        self.assertIn("spotify images: miss (empty result)", detail_lines)
        self.assertIn("repair result: no profile data found", detail_lines)

    def test_repair_missing_artist_images_logs_download_failure(self):
        scanner = SimpleNamespace(
            scan_config=SimpleNamespace(SPOTIFY={"client_id": "client-id"}),
        )
        user = SimpleNamespace(lastfm_status=True)
        artist = SimpleNamespace(name="Artist", artist_info_json="/tmp/info.json")
        sp = Mock()
        sp.get_artist_info.return_value = {
            "artists": {
                "items": [
                    {"images": [{"height": 640, "url": "https://example.com/large.png"}]}
                ]
            }
        }

        class FakeArtistInfoField:
            @staticmethod
            def is_null(_value):
                return None

        class FakeArtistModel:
            artist_info_json = FakeArtistInfoField()

            @staticmethod
            def select():
                select_result = Mock()
                select_result.where.return_value = [artist]
                return select_result

        with patch("supysonic.scanner_func.scanner_enrich.MySpotify", return_value=sp), patch(
            "supysonic.scanner_func.scanner_enrich.Artist",
            FakeArtistModel,
        ), patch(
            "supysonic.scanner_func.scanner_enrich.read_dict_from_json",
            return_value={"image": {"large": "/tmp/large.png"}},
        ), patch(
            "supysonic.scanner_func.scanner_enrich.os.path.exists",
            side_effect=lambda path: path == "/tmp/info.json",
        ), patch(
            "supysonic.scanner_func.scanner_enrich.download_image",
            return_value=None,
        ), patch(
            "supysonic.scanner_func.scanner_enrich.logTrace",
            create=True,
        ) as log_trace:
            repairMissingArtistImages(scanner, get_cover_interner=True, user=user)

        _, _, _, detail_lines = log_trace.call_args[0]
        self.assertIn("spotify images: hit", detail_lines)
        self.assertIn("spotify image download failed: large", detail_lines)
        self.assertIn("repair result: no missing image restored", detail_lines)
