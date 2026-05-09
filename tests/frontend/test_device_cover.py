import os
import unittest

from unittest.mock import patch

from supysonic.db import Album, Artist, Folder, Track, User

from .frontendtestbase import FrontendTestBase
from ..testbase import TestConfig


class DeviceCoverTestCase(FrontendTestBase):
    __with_api__ = True

    def setUp(self):
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["log_dir"] = ""
        super().setUp()

        alice = User.get(User.name == "alice")
        with self.client.session_transaction() as session:
            session["userid"] = str(alice.id)

        self.root = Folder.create(root=True, name="Root", path="/tmp/root")
        self.folder = Folder.create(root=False, name="Album", path="/tmp/root/album", parent=self.root)
        self.artist = Artist.create(name="Artist")
        self.album = Album.create(name="Album", artist=self.artist)
        self.track = Track.create(
            disc=1,
            number=1,
            title="Track",
            duration=120,
            has_art=False,
            album=self.album,
            artist=self.artist,
            bitrate=320,
            path="/tmp/root/album/track.flac",
            last_modification=1,
            root_folder=self.root,
            folder=self.folder,
        )

    def test_device_cover_does_not_print_debug_output(self):
        cover_path = os.path.abspath("tests/assets/cover.jpg")

        with patch("supysonic.frontend.__new_get_cover_path", return_value=cover_path), patch(
            "builtins.print"
        ) as print_mock:
            rv = self.client.open(path=f"/devices/cover/{self.track.id}", method="GET")
            try:
                self.assertEqual(rv.status_code, 200)
            finally:
                rv.close()

        print_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
