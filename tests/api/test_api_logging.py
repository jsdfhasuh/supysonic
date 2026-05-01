import os
import shutil
import tempfile
import unittest
import requests

from unittest.mock import Mock, patch

from supysonic import db
from supysonic.cache import CacheMiss
from supysonic.daemon.exceptions import DaemonUnavailableError
from supysonic.db import Album, Artist, Folder, Track
from supysonic.db import release_database
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
        db.db.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS image (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path VARCHAR(4096) NOT NULL,
                image_type VARCHAR(10) NOT NULL,
                related_id VARCHAR(36) NOT NULL,
                created DATETIME
            )
            """
        )
        try:
            db.db.execute_sql("ALTER TABLE album ADD COLUMN year VARCHAR(255)")
        except Exception:
            pass
        try:
            db.db.execute_sql("ALTER TABLE artist ADD COLUMN artist_info_json VARCHAR(4096)")
        except Exception:
            pass
        try:
            db.db.execute_sql("ALTER TABLE artist ADD COLUMN real_artist_id INTEGER")
        except Exception:
            pass
        UserManager.add("alice", "Alic3", admin=True)

    def tearDown(self):
        release_database()
        shutil.rmtree(self._dir)
        os.close(self._db[0])
        os.remove(self._db[1])

    def readApiLog(self):
        with open(os.path.join(self._dir, "api.log"), "r", encoding="utf-8") as f:
            return f.read()

    def createMediaTrack(self):
        folder = Folder.create(
            name="Root",
            path=os.path.abspath("tests/assets"),
            root=True,
            cover_art="cover.jpg",
        )
        artist = Artist.create(name="Artist")
        album = Album.create(artist=artist, name="Album")
        return Track.create(
            title="Silence",
            number=1,
            disc=1,
            artist=artist,
            album=album,
            path=os.path.abspath("tests/assets/formats/silence.flac"),
            root_folder=folder,
            folder=folder,
            duration=2,
            bitrate=320,
            last_modification=0,
        )

    def test_logs_missing_auth_to_api_log(self):
        rv = self.client.get("/rest/getArtists?c=test-client&f=json")
        request_id = rv.headers.get("X-Request-ID")
        content = self.readApiLog()

        self.assertEqual(rv.status_code, 200)
        self.assertTrue(request_id)
        self.assertIn("api event=auth_failure", content)
        self.assertIn("reason=missing_auth", content)
        self.assertIn(f"request_id={request_id}", content)

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
        content = self.readApiLog()

        self.assertIn("api event=get_songs_item_failed", content)
        self.assertIn("track_id=bad-id", content)
        self.assertIn("reason=ValueError", content)

    def test_logs_start_scan_daemon_unavailable_to_api_log(self):
        with patch("supysonic.api.scan.DaemonClient", side_effect=DaemonUnavailableError("unavailable")):
            rv = self.client.get("/rest/startScan?u=alice&p=Alic3&c=test-client&f=json")

        self.assertEqual(rv.status_code, 200)
        content = self.readApiLog()

        self.assertIn("api event=scan_request_failed", content)
        self.assertIn("reason=daemon_unavailable", content)

    def test_successful_ping_does_not_write_api_log(self):
        rv = self.client.get("/rest/ping?u=alice&p=Alic3&c=test-client&f=json")

        self.assertEqual(rv.status_code, 200)
        content = self.readApiLog()

        self.assertNotIn("api event=", content)

    def test_logs_media_stream_failed_when_no_transcoder_is_configured(self):
        track = self.createMediaTrack()

        rv = self.client.get(
            "/rest/stream.view?u=alice&p=Alic3&c=test-client&f=json&id={}&format=ogg".format(track.id)
        )

        self.assertEqual(rv.status_code, 200)
        content = self.readApiLog()

        self.assertIn("api event=media_stream_failed", content)
        self.assertIn(f"track_id={track.id}", content)
        self.assertIn("source_format=flac", content)
        self.assertIn("target_format=ogg", content)
        self.assertIn("reason=no_transcoder", content)

    def test_logs_transcode_started_when_transcoding_begins(self):
        track = self.createMediaTrack()
        self.app.config["TRANSCODING"]["transcoder"] = "cat %srcpath"
        fake_process = Mock(stdout=Mock())

        with patch.object(self.app.transcode_cache, "get", side_effect=CacheMiss("miss")), patch.object(
            self.app.transcode_cache,
            "set_generated",
            return_value=[b"abc"],
        ), patch("supysonic.api.media.subprocess.Popen", return_value=fake_process):
            rv = self.client.get(
                "/rest/stream.view?u=alice&p=Alic3&c=test-client&f=json&id={}&format=ogg".format(track.id)
            )

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.data, b"abc")
        content = self.readApiLog()

        self.assertIn("api event=transcode_started", content)
        self.assertIn(f"track_id={track.id}", content)
        self.assertIn("source_format=flac", content)
        self.assertIn("target_format=ogg", content)

    def test_logs_download_failed_for_invalid_id(self):
        rv = self.client.get("/rest/download.view?u=alice&p=Alic3&c=test-client&f=json&id=string")

        self.assertEqual(rv.status_code, 200)
        content = self.readApiLog()

        self.assertIn("api event=download_failed", content)
        self.assertIn("entity_id=string", content)
        self.assertIn("reason=invalid_id", content)

    def test_logs_cover_art_failed_for_missing_entity(self):
        rv = self.client.get("/rest/getCoverArt.view?u=alice&p=Alic3&c=test-client&f=json&id=al-999")

        self.assertEqual(rv.status_code, 200)
        content = self.readApiLog()

        self.assertIn("api event=cover_art_failed", content)
        self.assertIn("entity_id=al-999", content)
        self.assertIn("reason=not_found", content)

    def test_logs_external_lyrics_request_failure(self):
        self.app.config["WEBAPP"]["online_lyrics"] = True

        with patch("supysonic.api.media.requests.get", side_effect=requests.exceptions.Timeout("timeout")):
            rv = self.client.get(
                "/rest/getLyrics.view?u=alice&p=Alic3&c=test-client&f=json&artist=Nobody&title=Nowhere"
            )

        self.assertEqual(rv.status_code, 200)
        content = self.readApiLog()

        self.assertIn("api event=lyrics_external_failed", content)
        self.assertIn("artist=Nobody", content)
        self.assertIn("title=Nowhere", content)
        self.assertIn("reason=Timeout", content)
