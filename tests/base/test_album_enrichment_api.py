import json
import os
import shutil
import tempfile
import unittest

from supysonic.db import Album, AlbumArtist, Artist, Folder, Track, User

from ..testbase import TestBase


class AlbumEnrichmentApiTestCase(TestBase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.artist = Artist.create(name="API Enrichment Artist")
        self.root = Folder.create(root=True, name="Root", path=self.media_root)
        self.folder = Folder.create(
            root=False,
            name="API Enrichment Album",
            path=os.path.join(self.media_root, "album"),
            parent=self.root,
        )
        self.album = Album.create(
            name="API Enrichment Album",
            artist=self.artist,
            year="2024",
            release_date="2024-03-15",
            release_type="album",
            album_info_json=json.dumps(
                {
                    "styles": ["Indie Rock"],
                    "musicbrainz_id": "mbid",
                    "discogs_id": "123",
                }
            ),
        )
        AlbumArtist.create(album_id=self.album, artist_id=self.artist, position=1)
        Track.create(
            disc=1,
            number=1,
            title="API Track",
            duration=120,
            has_art=False,
            album=self.album,
            artist=self.artist,
            bitrate=320,
            path=os.path.join(self.folder.path, "track.flac"),
            last_modification=1,
            root_folder=self.root,
            folder=self.folder,
        )

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.media_root)

    def test_as_subsonic_album_returns_enrichment_extensions(self):
        user = User.get(User.name == "alice")

        payload = self.album.as_subsonic_album(user, "music-client")

        self.assertIn("releaseDate", payload)
        self.assertIn("releaseType", payload)
        self.assertIn("styles", payload)
        self.assertIn("musicBrainzId", payload)
        self.assertIn("discogsId", payload)
        self.assertEqual(payload["releaseDate"], "2024-03-15")
        self.assertEqual(payload["releaseType"], "album")
        self.assertEqual(payload["styles"], ["Indie Rock"])
        self.assertEqual(payload["musicBrainzId"], "mbid")
        self.assertEqual(payload["discogsId"], "123")


if __name__ == "__main__":
    unittest.main()
