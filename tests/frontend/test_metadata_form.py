import io
import os
import shutil
import tempfile
import unittest

from PIL import Image

from supysonic.db import Album, AlbumArtist, Artist, Folder, Track, TrackArtist, User, db
from supysonic.tool import read_dict_from_json

from .frontendtestbase import FrontendTestBase
from ..testbase import TestConfig


class MetadataFormTestCase(FrontendTestBase):
    def setUp(self):
        self.logDir = tempfile.mkdtemp()
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["log_dir"] = self.logDir
        TestConfig.WEBAPP["log_level"] = "INFO"
        super().setUp()
        db.execute_sql("ALTER TABLE artist ADD COLUMN artist_info_json VARCHAR(4096)")
        db.execute_sql("ALTER TABLE artist ADD COLUMN real_artist_id INTEGER")
        db.execute_sql("ALTER TABLE album ADD COLUMN year VARCHAR(255)")
        db.execute_sql(
            "CREATE TABLE album_artist ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "album_id CHAR(36) NOT NULL REFERENCES album(id), "
            "artist_id CHAR(36) NOT NULL REFERENCES artist(id), "
            "position INTEGER NOT NULL DEFAULT 0, "
            "UNIQUE(album_id, artist_id)"
            ")"
        )
        db.execute_sql(
            "CREATE TABLE track_artist ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "track_id CHAR(36) NOT NULL REFERENCES track(id), "
            "artist_id CHAR(36) NOT NULL REFERENCES artist(id), "
            "position INTEGER NOT NULL DEFAULT 0, "
            "UNIQUE(track_id, artist_id)"
            ")"
        )
        alice = User.get(User.name == "alice")
        with self.client.session_transaction() as session:
            session["userid"] = str(alice.id)
        self.artist = Artist.create(name="Primary Artist")
        self.root = Folder.create(root=True, name="Root", path="/tmp/root")
        self.folder = Folder.create(root=False, name="Album", path="/tmp/root/album", parent=self.root)

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.logDir)

    def readMetadataLog(self):
        with open(os.path.join(self.config.WEBAPP["log_dir"], "metadata.log"), "r", encoding="utf-8") as f:
            return f.read()

    def createImageUpload(self, color=(20, 40, 60)):
        imageBuffer = io.BytesIO()
        Image.new("RGB", (900, 900), color=color).save(imageBuffer, format="PNG")
        imageBuffer.seek(0)
        return imageBuffer

    def test_artists_form_updates_biography_and_photo(self):
        imageBuffer = self.createImageUpload()

        rv = self.client.post(
            "/artists",
            data={
                "action": "change_primary_artist",
                "id": str(self.artist.id),
                "name": self.artist.name,
                "primary_name": "",
                "biography": "Updated biography",
                "artist_photo": (imageBuffer, "artist.png"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(rv.status_code, 200)
        payload = rv.json
        self.assertEqual(payload["status"], "success")

        artist = Artist.get_by_id(self.artist.id)
        self.assertTrue(os.path.isfile(artist.artist_info_json))
        info = read_dict_from_json(artist.artist_info_json)
        self.assertEqual(info["biography"], "Updated biography")
        self.assertEqual(sorted(info["image"].keys()), ["large", "medium", "small"])
        log_content = self.readMetadataLog()
        self.assertIn("metadata event=artist_form_update", log_content)
        self.assertIn("result=success", log_content)
        self.assertIn("action=change_primary_artist", log_content)
        self.assertIn(f"artist_id={self.artist.id}", log_content)
        self.assertIn("biography_updated=true", log_content)
        self.assertIn("photo_updated=true", log_content)

    def test_artists_form_rejects_invalid_photo(self):
        rv = self.client.post(
            "/artists",
            data={
                "action": "change_primary_artist",
                "id": str(self.artist.id),
                "name": self.artist.name,
                "primary_name": "",
                "biography": "Updated biography",
                "artist_photo": (io.BytesIO(b"not-an-image"), "artist.txt"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(rv.status_code, 400)
        self.assertEqual(rv.json["status"], "error")

    def test_artists_form_logs_no_change(self):
        rv = self.client.post(
            "/artists",
            json={
                "action": "change_primary_artist",
                "id": str(self.artist.id),
                "name": self.artist.name,
                "primary_name": "",
            },
        )

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["message"], "no change needed")

        log_content = self.readMetadataLog()
        self.assertIn("metadata event=artist_form_update", log_content)
        self.assertIn("result=no_change", log_content)
        self.assertIn(f"artist_id={self.artist.id}", log_content)

    def test_artists_form_change_primary_artist_merges_existing_guest_relations(self):
        alias_artist = Artist.create(name="Alias Artist")
        album = Album.create(name="Merge Album", artist=alias_artist)
        track = Track.create(
            disc=1,
            number=1,
            title="Merge Track",
            duration=120,
            has_art=False,
            album=album,
            artist=alias_artist,
            bitrate=320,
            path="/tmp/root/album/merge-track.flac",
            last_modification=1,
            root_folder=self.root,
            folder=self.folder,
        )
        AlbumArtist.create(album_id=album, artist_id=alias_artist, position=1)
        AlbumArtist.create(album_id=album, artist_id=self.artist, position=2)
        TrackArtist.create(track_id=track, artist_id=alias_artist, position=1)
        TrackArtist.create(track_id=track, artist_id=self.artist, position=2)

        rv = self.client.post(
            "/artists",
            json={
                "action": "change_primary_artist",
                "id": str(alias_artist.id),
                "name": alias_artist.name,
                "primary_name": self.artist.name,
            },
        )

        self.assertEqual(rv.status_code, 200)
        updated_album = Album.get_by_id(album.id)
        updated_track = Track.get_by_id(track.id)
        self.assertEqual(updated_album.artist_id, self.artist.id)
        self.assertEqual(updated_track.artist_id, self.artist.id)
        self.assertEqual(
            AlbumArtist.select().where(AlbumArtist.album_id == album, AlbumArtist.artist_id == self.artist).count(),
            1,
        )
        self.assertEqual(
            TrackArtist.select().where(TrackArtist.track_id == track, TrackArtist.artist_id == self.artist).count(),
            1,
        )
