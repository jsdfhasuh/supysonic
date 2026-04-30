import unittest

from types import SimpleNamespace
from unittest.mock import Mock, patch

from supysonic.scanner_func.scanner_cover import repairAlbumCover


class ScannerCoverTraceTestCase(unittest.TestCase):
    def test_repair_album_cover_logs_folder_cover_hit(self):
        scanner = SimpleNamespace(
            stats=lambda: SimpleNamespace(
                lost_covers=SimpleNamespace(albums=1),
                lost_covers_albums={},
            )
        )
        album = SimpleNamespace(id=3, name="Album", artist=SimpleNamespace(get_artist_name=lambda: "Artist"))
        track = SimpleNamespace(path="/music/Artist/Album/track.flac")
        track_query = Mock()
        track_query.where.return_value.first.return_value = track

        with patch("supysonic.scanner_func.scanner_cover.Track.select", return_value=track_query), patch(
            "supysonic.scanner_func.scanner_cover.find_cover_in_folder",
            return_value=SimpleNamespace(name="cover.jpg"),
        ), patch(
            "supysonic.scanner_func.scanner_cover.Image.get_or_create"
        ), patch(
            "supysonic.scanner_func.scanner_cover.markAlbumCoverRestored"
        ), patch(
            "supysonic.scanner_func.scanner_cover.logTrace",
            create=True,
        ) as log_trace:
            repairAlbumCover(scanner, album)

        _, trace_type, header_fields, detail_lines = log_trace.call_args[0]
        self.assertEqual(trace_type, "ALBUM_COVER_TRACE")
        self.assertEqual(header_fields["album"], "Album")
        self.assertEqual(header_fields["track_path"], track.path)
        self.assertIn("cover source: folder file", detail_lines)
        self.assertIn("selected cover file: cover.jpg", detail_lines)

    def test_repair_album_cover_logs_when_no_source_succeeds(self):
        scanner = SimpleNamespace(
            stats=lambda: SimpleNamespace(
                lost_covers=SimpleNamespace(albums=1),
                lost_covers_albums={},
            )
        )
        album = SimpleNamespace(id=3, name="Album", artist=SimpleNamespace(get_artist_name=lambda: "Artist"))
        track = SimpleNamespace(path="/music/Artist/Album/track.flac")
        track_query = Mock()
        track_query.where.return_value.first.return_value = track

        with patch("supysonic.scanner_func.scanner_cover.Track.select", return_value=track_query), patch(
            "supysonic.scanner_func.scanner_cover.find_cover_in_folder",
            return_value=None,
        ), patch(
            "supysonic.scanner_func.scanner_cover.mediafile.MediaFile",
            return_value=SimpleNamespace(art=None),
        ), patch(
            "supysonic.scanner_func.scanner_cover.logTrace",
            create=True,
        ) as log_trace:
            repairAlbumCover(scanner, album, get_cover_interner=False)

        _, trace_type, _, detail_lines = log_trace.call_args[0]
        self.assertEqual(trace_type, "ALBUM_COVER_TRACE")
        self.assertIn("folder cover lookup: miss", detail_lines)
        self.assertIn("embedded artwork: miss", detail_lines)
        self.assertIn("cover repair result: no source succeeded", detail_lines)
