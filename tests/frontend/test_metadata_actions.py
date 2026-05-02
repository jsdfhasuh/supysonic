import unittest
import importlib.util
import io
import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image


modulePath = Path(__file__).resolve().parents[2] / "supysonic" / "frontend" / "metadata_actions.py"
moduleSpec = importlib.util.spec_from_file_location("metadata_actions", modulePath)
metadataActions = importlib.util.module_from_spec(moduleSpec)
moduleSpec.loader.exec_module(metadataActions)
assignPrimaryArtist = metadataActions.assignPrimaryArtist
updateArtistMetadata = metadataActions.updateArtistMetadata


class DummyRecord:
    def __init__(self):
        self.saved = False

    def save(self):
        self.saved = True


class DummyAlbum(DummyRecord):
    def __init__(self, artist):
        super().__init__()
        self.artist = artist


class DummyTrack(DummyRecord):
    def __init__(self, artist):
        super().__init__()
        self.artist = artist


class DummyRelation(DummyRecord):
    def __init__(self, artist):
        super().__init__()
        self.artist_id = artist


class DummyArtist(DummyRecord):
    def __init__(self, name, realArtist=None):
        super().__init__()
        self.name = name
        self.real_artist = realArtist
        self.albums = []
        self.tracks = []
        self.artist_albums = []
        self.artist_tracks = []


class MetadataActionsTestCase(unittest.TestCase):
    def setUp(self):
        self.tempDir = tempfile.mkdtemp()
        self.config = {
            "WEBAPP": {"cache_dir": self.tempDir},
            "BASE": {},
        }

    def tearDown(self):
        shutil.rmtree(self.tempDir)

    def test_assign_primary_artist_migrates_existing_relations(self):
        oldArtist = DummyArtist("Alias")
        primaryArtist = DummyArtist("Primary")
        album = DummyAlbum(oldArtist)
        track = DummyTrack(oldArtist)
        albumRelation = DummyRelation(oldArtist)
        trackRelation = DummyRelation(oldArtist)
        oldArtist.albums = [album]
        oldArtist.tracks = [track]
        oldArtist.artist_albums = [albumRelation]
        oldArtist.artist_tracks = [trackRelation]

        assignPrimaryArtist(oldArtist, primaryArtist)

        self.assertIs(album.artist, primaryArtist)
        self.assertIs(track.artist, primaryArtist)
        self.assertIs(albumRelation.artist_id, primaryArtist)
        self.assertIs(trackRelation.artist_id, primaryArtist)
        self.assertIs(oldArtist.real_artist, primaryArtist)

    def test_assign_primary_artist_uses_root_primary_artist(self):
        rootArtist = DummyArtist("Root")
        aliasPrimaryArtist = DummyArtist("Alias Primary", realArtist=rootArtist)
        oldArtist = DummyArtist("Old")
        track = DummyTrack(oldArtist)
        oldArtist.tracks = [track]

        assignPrimaryArtist(oldArtist, aliasPrimaryArtist)

        self.assertIs(track.artist, rootArtist)
        self.assertIs(oldArtist.real_artist, rootArtist)

    def test_update_artist_metadata_creates_json_and_updates_biography(self):
        artist = DummyArtist("Primary Artist")
        artist.id = "artist-1"
        artist.artist_info_json = None

        infoPath = updateArtistMetadata(self.config, artist, biography="Updated biography")

        self.assertEqual(artist.artist_info_json, infoPath)
        with open(infoPath, "r", encoding="utf-8") as infoFile:
            payload = json.load(infoFile)
        self.assertEqual(payload["biography"], "Updated biography")
        self.assertEqual(payload["image"], {})

    def test_update_artist_metadata_overwrites_generated_images(self):
        artist = DummyArtist("Primary Artist")
        artist.id = "artist-2"
        artist.artist_info_json = None
        imageBuffer = io.BytesIO()
        Image.new("RGB", (900, 900), color=(12, 34, 56)).save(imageBuffer, format="PNG")
        imageBuffer.seek(0)

        infoPath = updateArtistMetadata(self.config, artist, biography="Bio", imageFile=imageBuffer)

        with open(infoPath, "r", encoding="utf-8") as infoFile:
            payload = json.load(infoFile)
        self.assertEqual(payload["biography"], "Bio")
        self.assertEqual(sorted(payload["image"].keys()), ["large", "medium", "small"])
        for imagePath in payload["image"].values():
            self.assertTrue(Path(imagePath).is_file())

    def test_update_artist_metadata_rejects_invalid_image(self):
        artist = DummyArtist("Primary Artist")
        artist.id = "artist-3"
        artist.artist_info_json = None
        badFile = io.BytesIO(b"not-an-image")

        with self.assertRaises(ValueError):
            updateArtistMetadata(self.config, artist, biography="Bio", imageFile=badFile)
