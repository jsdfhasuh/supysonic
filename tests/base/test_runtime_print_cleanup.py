import os
import unittest

from contextlib import closing
from unittest.mock import patch

from supysonic.db import Album, Artist, Folder, Track

from ..testbase import TestBase


class RuntimePrintCleanupTestCase(TestBase):
    __with_api__ = True

    def setUp(self):
        super().setUp()
        self.root = Folder.create(
            name="Root",
            path=os.path.abspath("tests/assets"),
            root=True,
            cover_art="cover.jpg",
        )
        self.artist = Artist.create(name="Artist")
        self.album = Album.create(artist=self.artist, name="Album")
        self.track = Track.create(
            title="Track",
            number=1,
            disc=1,
            artist=self.artist,
            album=self.album,
            path=os.path.abspath("tests/assets/23bytes"),
            root_folder=self.root,
            folder=self.root,
            duration=2,
            bitrate=320,
            last_modification=0,
        )

    def test_cover_art_route_does_not_print_debug_output(self):
        with patch("supysonic.api.media.__new_get_cover_path", return_value=os.path.abspath("tests/assets/cover.jpg")), patch(
            "builtins.print"
        ) as print_mock, closing(
            self.client.get(
                "/rest/getCoverArt.view",
                query_string={
                    "u": "alice",
                    "p": "Alic3",
                    "c": "tests",
                    "id": str(self.root.id),
                },
            )
        ) as rv:
            self.assertEqual(rv.status_code, 200)

        print_mock.assert_not_called()

    def test_search3_route_does_not_print_debug_output(self):
        with patch("builtins.print") as print_mock:
            rv = self.client.get(
                "/rest/search3.view",
                query_string={
                    "u": "alice",
                    "p": "Alic3",
                    "c": "tests",
                    "query": "Artist",
                },
            )

        self.assertEqual(rv.status_code, 200)
        print_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
