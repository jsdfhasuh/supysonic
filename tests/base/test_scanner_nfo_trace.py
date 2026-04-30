import logging
import unittest

from types import SimpleNamespace
from unittest.mock import patch

from supysonic.scanner_func.scanner_nfo import renowAlbumByNfo


class ScannerNfoTraceTestCase(unittest.TestCase):
    def test_renow_album_by_nfo_logs_applied_updates(self):
        scanner = SimpleNamespace()
        logger = logging.getLogger("test-nfo-trace")
        album = SimpleNamespace(name="Album")
        track = SimpleNamespace(album=album)

        with patch(
            "supysonic.scanner_func.scanner_nfo._loadAlbumNfo",
            return_value=({"album": {"year": "2024"}}, "/music/Album"),
        ), patch(
            "supysonic.scanner_func.scanner_nfo._loadAlbumFolderState",
            return_value=(SimpleNamespace(path="/music/Album"), track, [track]),
        ), patch(
            "supysonic.scanner_func.scanner_nfo._renowAlbumMetadata"
        ) as renow_album_metadata, patch(
            "supysonic.scanner_func.scanner_nfo._validateTrackNumbers",
            return_value=True,
        ), patch(
            "supysonic.scanner_func.scanner_nfo._renowTrackArtists"
        ) as renow_track_artists, patch(
            "supysonic.scanner_func.scanner_nfo.logTrace",
            create=True,
        ) as log_trace:
            renowAlbumByNfo(scanner, "/music/Album/album.nfo", logger)

        renow_album_metadata.assert_called_once()
        renow_track_artists.assert_called_once_with(scanner, album, {"album": {"year": "2024"}}, logger)
        _, trace_type, header_fields, detail_lines = log_trace.call_args[0]
        self.assertEqual(trace_type, "NFO_TRACE")
        self.assertEqual(header_fields["folder"], "/music/Album")
        self.assertIn("album.nfo found", detail_lines)
        self.assertIn("album metadata updated from nfo", detail_lines)
        self.assertIn("track artist renow applied", detail_lines)

    def test_renow_album_by_nfo_logs_invalid_track_numbers_skip(self):
        scanner = SimpleNamespace()
        logger = logging.getLogger("test-nfo-trace")
        album = SimpleNamespace(name="Album")
        track = SimpleNamespace(album=album)

        with patch(
            "supysonic.scanner_func.scanner_nfo._loadAlbumNfo",
            return_value=({"album": {}}, "/music/Album"),
        ), patch(
            "supysonic.scanner_func.scanner_nfo._loadAlbumFolderState",
            return_value=(SimpleNamespace(path="/music/Album"), track, [track]),
        ), patch(
            "supysonic.scanner_func.scanner_nfo._renowAlbumMetadata"
        ), patch(
            "supysonic.scanner_func.scanner_nfo._validateTrackNumbers",
            return_value=False,
        ), patch(
            "supysonic.scanner_func.scanner_nfo._renowTrackArtists"
        ) as renow_track_artists, patch(
            "supysonic.scanner_func.scanner_nfo.logTrace",
            create=True,
        ) as log_trace:
            renowAlbumByNfo(scanner, "/music/Album/album.nfo", logger)

        renow_track_artists.assert_not_called()
        _, trace_type, _, detail_lines = log_trace.call_args[0]
        self.assertEqual(trace_type, "NFO_TRACE")
        self.assertIn("album.nfo found", detail_lines)
        self.assertIn("track artist renow skipped: invalid track numbers", detail_lines)
