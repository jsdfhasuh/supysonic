import logging
import unittest

from unittest.mock import Mock

from supysonic.scanner_func.scanner_trace import buildTraceBlock, logTrace


class ScannerTraceTestCase(unittest.TestCase):
    def test_build_trace_block_formats_header_fields_and_detail_lines(self):
        trace_block = buildTraceBlock(
            "TRACK_TRACE",
            {
                "path": "/music/artist/track.flac",
                "album": "Album",
                "artists": ["Artist A", "Artist B"],
            },
            [
                "loaded existing track: no",
                "resolved artists from album.nfo",
            ],
        )

        self.assertEqual(
            trace_block,
            "TRACK_TRACE path=/music/artist/track.flac album=Album artists=Artist A, Artist B\n"
            "  - loaded existing track: no\n"
            "  - resolved artists from album.nfo",
        )

    def test_build_trace_block_skips_empty_fields_and_uses_placeholder_for_no_steps(self):
        trace_block = buildTraceBlock(
            "REPAIR_TRACE",
            {
                "album": "Album",
                "reason": None,
                "source": "",
            },
            [],
        )

        self.assertEqual(trace_block, "REPAIR_TRACE album=Album\n  - no details")

    def test_log_trace_writes_debug_block(self):
        logger = Mock(spec=logging.Logger)

        logTrace(
            logger,
            "NFO_TRACE",
            {"folder": "/music/album"},
            ["album.nfo found", "updated album year"],
        )

        logger.debug.assert_called_once_with(
            "NFO_TRACE folder=/music/album\n  - album.nfo found\n  - updated album year"
        )
