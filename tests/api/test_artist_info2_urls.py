import flask
import os
import shutil
import tempfile
import unittest

from supysonic.db import Artist
from supysonic.db import db, release_database
from supysonic.managers.user import UserManager
from supysonic.web import create_application

from ..testbase import TestConfig


class ArtistInfo2UrlTestCase(unittest.TestCase):
    def setUp(self):
        self._db = tempfile.mkstemp()
        self._dir = tempfile.mkdtemp()
        self.config = TestConfig(False, True)
        self.config.BASE["database_uri"] = "sqlite:///" + self._db[1]
        self.config.WEBAPP["cache_dir"] = self._dir
        self.config.WEBAPP["log_dir"] = self._dir

        self._app = create_application(self.config)
        self.client = self._app.test_client()

        db.execute_sql("ALTER TABLE artist ADD COLUMN artist_info_json VARCHAR(4096)")
        db.execute_sql("ALTER TABLE artist ADD COLUMN real_artist_id INTEGER")

        UserManager.add("alice", "Alic3", admin=True)
        self.artist = Artist.create(name="Test Artist")

    def tearDown(self):
        release_database()
        shutil.rmtree(self._dir)
        os.close(self._db[0])
        os.remove(self._db[1])

    def test_get_artist_info2_uses_clean_cover_art_urls(self):
        rv = self.client.get(
            "/rest/getArtistInfo2.view",
            query_string={
                "u": "alice",
                "p": "Alic3",
                "c": "tests",
                "v": "1.16.1",
                "f": "json",
                "id": str(self.artist.id),
            },
        )

        self.assertEqual(rv.status_code, 200)
        payload = flask.json.loads(rv.data)
        info = payload["subsonic-response"]["artistInfo2"]
        expected_base = f"http://localhost/rest/getCoverArt.view?id=ar-{self.artist.id}"

        self.assertEqual(info["artist_image_url"], f"{expected_base}&c=tests")
        self.assertEqual(info["smallImageUrl"], f"{expected_base}&input_size=small&c=tests")
        self.assertEqual(info["mediumImageUrl"], f"{expected_base}&input_size=medium&c=tests")
        self.assertEqual(info["largeImageUrl"], f"{expected_base}&input_size=large&c=tests")
        self.assertEqual(info["largeImageUrl"].count("?"), 1)
