import os
import shutil
import tempfile
import unittest

from unittest.mock import patch

from supysonic.db import db, release_database
from supysonic.managers.user import UserManager
from supysonic.web import create_application

from ..testbase import TestConfig


class ApiLoggingTestCase(unittest.TestCase):
    def setUp(self):
        self._db = tempfile.mkstemp()
        self._dir = tempfile.mkdtemp()
        self.config = TestConfig(False, True)
        self.config.BASE["database_uri"] = "sqlite:///" + self._db[1]
        self.config.WEBAPP["cache_dir"] = self._dir
        self.config.WEBAPP["log_dir"] = self._dir
        self.config.WEBAPP["log_level"] = "INFO"
        self.app = create_application(self.config)
        self.client = self.app.test_client()
        UserManager.add("alice", "Alic3", admin=True)

    def tearDown(self):
        release_database()
        shutil.rmtree(self._dir)
        os.close(self._db[0])
        os.remove(self._db[1])

    def test_logs_get_songs_item_errors_to_api_log(self):
        fake_track = type(
            "FakeTrack",
            (),
            {"as_subsonic_child": lambda self, user, client: {"id": "ok-track"}},
        )()

        def fake_get_entity_by_id(_cls, track_id, param="id"):
            if track_id == "bad-id":
                raise ValueError("bad track id")
            return fake_track

        with patch("supysonic.api.browse.get_entity_by_id", side_effect=fake_get_entity_by_id):
            rv = self.client.post(
                "/rest/getSongs?u=alice&p=Alic3&c=test-client&f=json",
                json={"ids": ["bad-id", "ok-id"]},
            )

        self.assertEqual(rv.status_code, 200)
        with open(os.path.join(self._dir, "api.log"), "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Error retrieving track with ID bad-id", content)
