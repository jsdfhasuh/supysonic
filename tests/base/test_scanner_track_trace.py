import unittest

from types import SimpleNamespace
from unittest.mock import Mock, patch

from supysonic.scanner_func.scanner_pipeline import processScanFile


class ScannerTrackTraceTestCase(unittest.TestCase):
    def test_process_scan_file_logs_track_trace_with_fallback_album_artists(self):
        scanner = SimpleNamespace(stats=lambda: SimpleNamespace(existing_tracks=0, errors=[]))
        target = SimpleNamespace(
            path="/music/Artist/Album/track.flac",
            basename="track.flac",
            stat=SimpleNamespace(st_mtime=123),
        )
        tag = SimpleNamespace()
        track_artist = SimpleNamespace(name="Album Artist")
        track = SimpleNamespace(id=9)

        with patch(
            "supysonic.scanner_func.scanner_pipeline.getScanTargetInfo",
            return_value=target,
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.loadTrackForScan",
            return_value=(None, tag, {}),
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.resolveAlbumContext",
            return_value=(
                {"album": {"track": []}},
                ["Album Artist"],
                "album-row",
                {
                    "album_artists": ["Album Artist"],
                    "album_artist_source": "fallback unknown",
                    "raw_album_artists": [],
                    "raw_artists": [],
                    "artist_source": "fallback unknown",
                },
            ),
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.buildTrackData",
            return_value={"disc": 1, "number": 1, "title": "Track"},
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.resolveTrackArtists",
            return_value=(["Album Artist"], track_artist),
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.createOrUpdateTrack",
            return_value=track,
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.replaceTrackArtists"
        ) as replace_track_artists, patch(
            "supysonic.scanner_func.scanner_pipeline.logTrace",
            create=True,
        ) as log_trace:
            processScanFile(scanner, target.path)

        replace_track_artists.assert_called_once_with(scanner, ["Album Artist"], track)
        log_trace.assert_called_once()

        _, trace_type, header_fields, detail_lines = log_trace.call_args[0]
        self.assertEqual(trace_type, "TRACK_TRACE")
        self.assertEqual(header_fields["path"], target.path)
        self.assertEqual(header_fields["track_id"], track.id)
        self.assertIn("track artists source: fallback album artists", detail_lines)
        self.assertIn("resolved track artists: Album Artist", detail_lines)
        self.assertIn("resolved main artist: Album Artist", detail_lines)

    def test_process_scan_file_logs_tag_and_nfo_source_chain(self):
        scanner = SimpleNamespace(stats=lambda: SimpleNamespace(existing_tracks=0, errors=[]))
        target = SimpleNamespace(
            path="/music/Artist/Album/track.flac",
            basename="track.flac",
            stat=SimpleNamespace(st_mtime=123),
        )
        tag = SimpleNamespace(mgfile={"artist": ["Tag Artist"], "albumartist": ["Tag Album Artist"]})
        track_artist = SimpleNamespace(name="Nfo Track Artist")
        track = SimpleNamespace(id=10)
        nfo_data = {
            "album": {
                "artist": ["Nfo Album Artist"],
                "albumartist": ["Nfo Album Main Artist"],
                "track": [
                    {"cdnum": "1", "position": "1", "artist": ["Nfo Track Artist"]}
                ],
            }
        }

        with patch(
            "supysonic.scanner_func.scanner_pipeline.getScanTargetInfo",
            return_value=target,
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.loadTrackForScan",
            return_value=(None, tag, {}),
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.resolveAlbumContext",
            return_value=(
                nfo_data,
                ["Nfo Album Artist"],
                "album-row",
                {
                    "album_artists": ["Nfo Album Main Artist"],
                    "album_artist_source": "album.nfo albumartist",
                    "raw_album_artists": ["Tag Album Artist"],
                    "raw_artists": ["Tag Artist"],
                    "artist_source": "album.nfo artist",
                },
            ),
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.buildTrackData",
            return_value={"disc": 1, "number": 1, "title": "Track"},
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.resolveTrackArtists",
            return_value=(["Nfo Track Artist"], track_artist),
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.createOrUpdateTrack",
            return_value=track,
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.replaceTrackArtists"
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.logTrace",
            create=True,
        ) as log_trace:
            processScanFile(scanner, target.path)

        _, _, _, detail_lines = log_trace.call_args[0]
        self.assertIn("album artists source: album.nfo albumartist", detail_lines)
        self.assertIn("album artists from tag: Tag Album Artist", detail_lines)
        self.assertIn("album artists from nfo: Nfo Album Main Artist", detail_lines)
        self.assertIn("album track artists source: album.nfo artist", detail_lines)
        self.assertIn("track artists source: album.nfo track artists", detail_lines)
        self.assertIn("track artists from tag: Tag Artist", detail_lines)
        self.assertIn("track artists from nfo: Nfo Track Artist", detail_lines)

    def test_resolve_album_context_returns_trace_context_for_tag_and_unknown_fallback(self):
        from supysonic.scanner_func.scanner_file import resolveAlbumContext

        scanner = SimpleNamespace()
        tag = SimpleNamespace(album="Album", mgfile={"artist": ["Tag Artist"], "albumartist": []})

        with patch("supysonic.scanner_func.scanner_file.readNfo", return_value={}), patch(
            "supysonic.scanner_func.scanner_file.recordAlbumArtists",
            return_value=(None, "album-row", None),
        ), patch(
            "supysonic.scanner_func.scanner_file.sanitizeString",
            side_effect=lambda value: "Album" if value == tag.album else value,
        ):
            _, artists, album_id, trace_context = resolveAlbumContext(
                scanner,
                "/music/Artist/Album/track.flac",
                tag,
            )

        self.assertEqual(artists, ["Tag Artist"])
        self.assertEqual(album_id, "album-row")
        self.assertEqual(trace_context["album_artists"], ["Tag Artist"])
        self.assertEqual(trace_context["album_artist_source"], "tag artist fallback")
        self.assertEqual(trace_context["artist_source"], "tag artist")
        self.assertEqual(trace_context["resolved_album_artists"], ["Tag Artist"])
        self.assertEqual(trace_context["resolved_album_artist_count"], 1)
        self.assertEqual(trace_context["raw_artists"], ["Tag Artist"])
        self.assertEqual(trace_context["raw_album_artists"], [])

    def test_process_scan_file_logs_resolved_album_artists_summary(self):
        scanner = SimpleNamespace(stats=lambda: SimpleNamespace(existing_tracks=0, errors=[]))
        target = SimpleNamespace(
            path="/music/Artist/Album/track.flac",
            basename="track.flac",
            stat=SimpleNamespace(st_mtime=123),
        )
        tag = SimpleNamespace(mgfile={"artist": ["Tag Artist"], "albumartist": ["Tag Album Artist"]})
        track_artist = SimpleNamespace(name="Track Artist")
        track = SimpleNamespace(id=11)

        with patch(
            "supysonic.scanner_func.scanner_pipeline.getScanTargetInfo",
            return_value=target,
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.loadTrackForScan",
            return_value=(None, tag, {}),
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.resolveAlbumContext",
            return_value=(
                {"album": {"track": []}},
                ["Track Artist"],
                "album-row",
                {
                    "album_artists": ["Artist A", "Artist B"],
                    "album_artist_source": "album.nfo albumartist",
                    "raw_album_artists": ["Tag Album Artist"],
                    "raw_artists": ["Tag Artist"],
                    "artist_source": "album.nfo artist",
                    "resolved_album_artists": ["Artist A", "Artist B"],
                    "resolved_album_artist_count": 2,
                },
            ),
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.buildTrackData",
            return_value={"disc": 1, "number": 1, "title": "Track"},
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.resolveTrackArtists",
            return_value=(["Track Artist"], track_artist),
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.createOrUpdateTrack",
            return_value=track,
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.replaceTrackArtists"
        ), patch(
            "supysonic.scanner_func.scanner_pipeline.logTrace",
            create=True,
        ) as log_trace:
            processScanFile(scanner, target.path)

        _, _, _, detail_lines = log_trace.call_args[0]
        self.assertIn("resolved album artists: Artist A, Artist B", detail_lines)
        self.assertIn("resolved album artist count: 2", detail_lines)
