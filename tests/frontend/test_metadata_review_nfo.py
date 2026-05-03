import os
import shutil
import tempfile
import unittest

from unittest.mock import patch

from supysonic.db import Album, AlbumReviewTask, Artist, Folder, Track, db
from supysonic.frontend.metadata_nfo import (
    buildReviewAlbumNfoData,
    getReviewAlbumNfoPath,
    mergeReviewAlbumNfo,
    writeReviewAlbumNfo,
)
from supysonic.nfo.nfo import NfoHandler

from .frontendtestbase import FrontendTestBase


class MetadataReviewNfoTestCase(FrontendTestBase):
    def setUp(self):
        super().setUp()

        self.tempDir = tempfile.mkdtemp()
        self.albumDir = os.path.join(self.tempDir, "Album")
        os.makedirs(self.albumDir)

        self.root = Folder.create(root=True, name="Root", path=self.tempDir)
        self.folder = Folder.create(
            root=False,
            name="Album",
            path=self.albumDir,
            parent=self.root,
        )
        self.artist = Artist.create(name="Review Artist")
        self.album = Album.create(name="Review Album", artist=self.artist, year="2024")
        self.secondArtist = Artist.create(name="Second Artist")
        self.task = AlbumReviewTask.create(
            album=self.album,
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json='{"album_name": "Review Album"}',
        )

        self.trackB = Track.create(
            disc=2,
            number=3,
            title="Zulu Track",
            duration=180,
            has_art=False,
            album=self.album,
            artist=self.secondArtist,
            bitrate=320,
            path=os.path.join(self.albumDir, "02-zulu.flac"),
            last_modification=1,
            root_folder=self.root,
            folder=self.folder,
        )
        self.trackA = Track.create(
            disc=1,
            number=1,
            title="Alpha Track",
            duration=120,
            has_art=False,
            album=self.album,
            artist=self.artist,
            bitrate=320,
            path=os.path.join(self.albumDir, "01-alpha.flac"),
            last_modification=1,
            root_folder=self.root,
            folder=self.folder,
        )

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.tempDir)

    def test_get_review_album_nfo_path_from_album_track_folder(self):
        self.assertEqual(
            getReviewAlbumNfoPath(self.album),
            os.path.join(self.albumDir, "album.nfo"),
        )

    def test_get_review_album_nfo_path_raises_when_album_has_no_tracks(self):
        emptyAlbum = Album.create(name="Empty Album", artist=self.artist, year="2024")

        with self.assertRaisesRegex(ValueError, "album folder not found"):
            getReviewAlbumNfoPath(emptyAlbum)

    def test_build_review_album_nfo_data_uses_current_album_and_tracks(self):
        nfoData = buildReviewAlbumNfoData(self.album)

        self.assertEqual(nfoData["album"]["title"], "Review Album")
        self.assertEqual(nfoData["album"]["year"], "2024")
        self.assertEqual(nfoData["album"]["albumartist"], "Review Artist")
        self.assertEqual(nfoData["album"]["artist"], "Review Artist")
        self.assertEqual(
            nfoData["album"]["track"],
            [
                {
                    "title": "Alpha Track",
                    "cdnum": 1,
                    "position": 1,
                    "artist": "Review Artist",
                },
                {
                    "title": "Zulu Track",
                    "cdnum": 2,
                    "position": 3,
                    "artist": "Second Artist",
                },
            ],
        )

    def test_merge_review_album_nfo_preserves_unknown_fields(self):
        mergedData = mergeReviewAlbumNfo(
            {
                "album": {
                    "title": "Old Album",
                    "studio": "Unknown Field",
                    "track": [{"title": "Old Track", "comment": "keep me"}],
                }
            },
            buildReviewAlbumNfoData(self.album),
        )

        self.assertEqual(mergedData["album"]["studio"], "Unknown Field")
        self.assertEqual(mergedData["album"]["title"], "Review Album")
        self.assertEqual(mergedData["album"]["track"][0]["title"], "Alpha Track")
        self.assertEqual(mergedData["album"]["track"][0]["comment"], "keep me")

    def test_merge_review_album_nfo_overrides_review_owned_fields(self):
        mergedData = mergeReviewAlbumNfo(
            {
                "album": {
                    "title": "Old Album",
                    "year": "1999",
                    "albumartist": "Old Artist",
                    "artist": "Old Artist",
                    "track": [{"title": "Old Track", "cdnum": 9, "position": 9, "artist": "Old Artist"}],
                }
            },
            buildReviewAlbumNfoData(self.album),
        )

        self.assertEqual(mergedData["album"]["year"], "2024")
        self.assertEqual(mergedData["album"]["albumartist"], "Review Artist")
        self.assertEqual(mergedData["album"]["artist"], "Review Artist")
        self.assertEqual(
            mergedData["album"]["track"],
            [
                {
                    "title": "Alpha Track",
                    "cdnum": 1,
                    "position": 1,
                    "artist": "Review Artist",
                },
                {
                    "title": "Zulu Track",
                    "cdnum": 2,
                    "position": 3,
                    "artist": "Second Artist",
                },
            ],
        )

    def test_write_review_album_nfo_creates_new_file(self):
        daemonClient = FakeDaemonClient()

        nfoPath = writeReviewAlbumNfo(self.task, daemonClient, suppressTtl=7)

        self.assertEqual(nfoPath, os.path.join(self.albumDir, "album.nfo"))
        self.assertEqual(daemonClient.calls, [(nfoPath, 7)])
        writtenData = NfoHandler.read(nfoPath)
        self.assertEqual(writtenData["album"]["title"], "Review Album")
        self.assertEqual(writtenData["album"]["track"][0]["title"], "Alpha Track")

    def test_write_review_album_nfo_updates_existing_file_and_preserves_unknown_fields(self):
        nfoPath = os.path.join(self.albumDir, "album.nfo")
        NfoHandler.write(
            {
                "album": {
                    "title": "Old Album",
                    "studio": "Unknown Field",
                    "track": [{"title": "Old Track", "comment": "keep me"}],
                }
            },
            output_path=nfoPath,
            pretty=True,
        )

        writeReviewAlbumNfo(self.task, FakeDaemonClient(), suppressTtl=7)

        writtenData = NfoHandler.read(nfoPath)
        self.assertEqual(writtenData["album"]["studio"], "Unknown Field")
        self.assertEqual(writtenData["album"]["title"], "Review Album")
        self.assertEqual(writtenData["album"]["track"][0]["title"], "Alpha Track")
        self.assertEqual(writtenData["album"]["track"][0]["comment"], "keep me")

    def test_write_review_album_nfo_requires_daemon_suppress_registration(self):
        with self.assertRaisesRegex(RuntimeError, "suppress failed"):
            writeReviewAlbumNfo(self.task, FailingDaemonClient(), suppressTtl=7)

    def test_write_review_album_nfo_preserves_existing_file_when_replace_fails(self):
        nfoPath = os.path.join(self.albumDir, "album.nfo")
        NfoHandler.write(
            {
                "album": {
                    "title": "Old Album",
                    "studio": "Unknown Field",
                    "track": [{"title": "Old Track", "comment": "keep me"}],
                }
            },
            output_path=nfoPath,
            pretty=True,
        )

        with patch("supysonic.frontend.metadata_nfo.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                writeReviewAlbumNfo(self.task, FakeDaemonClient(), suppressTtl=7)

        preservedData = NfoHandler.read(nfoPath)
        self.assertEqual(preservedData["album"]["title"], "Old Album")
        self.assertEqual(preservedData["album"]["studio"], "Unknown Field")


class FakeDaemonClient:
    def __init__(self):
        self.calls = []

    def suppress_nfo_path(self, path, ttl):
        self.calls.append((path, ttl))


class FailingDaemonClient:
    def suppress_nfo_path(self, path, ttl):
        raise RuntimeError("suppress failed")


if __name__ == "__main__":
    unittest.main()
