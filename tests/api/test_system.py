# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.
#
# Copyright (C) 2017 Alban 'spl0k' Féron
#               2017 Óscar García Amor
#
# Distributed under terms of the GNU AGPLv3 license.

import unittest

from .apitestbase import ApiTestBase


class SystemTestCase(ApiTestBase):
    def test_ping(self):
        self._make_request("ping")

    def test_get_license(self):
        rv, child = self._make_request("getLicense", tag="license")
        self.assertEqual(child.get("valid"), "true")

    def test_open_subsonic_extensions_excludes_unsupported_transcode_offset(self):
        rv = self.client.get(
            "/rest/getOpenSubsonicExtensions.view",
            query_string={"u": "alice", "p": "Alic3", "c": "tests", "f": "json"},
        )

        data = rv.get_json()
        extensions = data["subsonic-response"]["openSubsonicExtensions"]
        self.assertNotIn(
            "transcodeOffset",
            {extension["name"] for extension in extensions},
        )

    def test_open_subsonic_extensions_includes_music_request_board(self):
        rv = self.client.get(
            "/rest/getOpenSubsonicExtensions.view",
            query_string={"u": "alice", "p": "Alic3", "c": "tests", "f": "json"},
        )

        data = rv.get_json()
        extensions = data["subsonic-response"]["openSubsonicExtensions"]
        by_name = {extension["name"]: extension for extension in extensions}
        self.assertIn("musicRequestBoard", by_name)
        self.assertEqual(by_name["musicRequestBoard"]["versions"], [1])


if __name__ == "__main__":
    unittest.main()
