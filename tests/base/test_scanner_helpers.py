# This file is part of Supysonic.
# Supysonic is a Python implementation of the Subsonic server API.

import os
import shutil
import tempfile
import unittest

from types import SimpleNamespace
from unittest.mock import Mock, patch

from supysonic import db
from supysonic.scanner_func import scanner_folder
from supysonic.scanner_func import scanner_runtime
from supysonic.scanner_func import Stats
from supysonic.scanner_func.scanner_lookup import findRootFolder
from supysonic.scanner_func.scanner_persist import resolveTrackArtists


class ScannerHelpersTestCase(unittest.TestCase):
    def setUp(self):
        self._db_dir = tempfile.mkdtemp()
        db.init_database(f"sqlite:///{os.path.join(self._db_dir, 'scanner-tests.db')}")
        db.db.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS track_artist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                artist_id INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        db.db.execute_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS track_artist_track_id_artist_id ON track_artist(track_id, artist_id)"
        )
        db.db.execute_sql("ALTER TABLE artist ADD COLUMN artist_info_json VARCHAR(4096)")
        db.db.execute_sql("ALTER TABLE artist ADD COLUMN real_artist_id INTEGER")
        db.db.execute_sql("ALTER TABLE album ADD COLUMN year VARCHAR(255)")
        self.stats = Stats()
        self.scanner = SimpleNamespace(stats=lambda: self.stats)

    def tearDown(self):
        db.release_database()
        shutil.rmtree(self._db_dir)

    def test_resolve_track_artists_matches_nfo_disc_and_position(self):
        with patch(
            "supysonic.scanner_func.scanner_persist.findArtist",
            return_value=SimpleNamespace(name="Nfo Artist"),
        ):
            track_artists, track_artist = resolveTrackArtists(
                self.scanner,
                {
                    "album": {
                        "track": [
                            {"cdnum": "2", "position": "7", "artist": ["Nfo Artist"]}
                        ]
                    }
                },
                {"disc": 2, "number": 7},
                ["Fallback Artist"],
            )

        self.assertEqual(track_artists, ["Nfo Artist"])
        self.assertEqual(track_artist.name, "Nfo Artist")

    def test_find_root_folder_does_not_match_by_partial_prefix(self):
        base_dir = tempfile.mkdtemp()
        try:
            music_dir = os.path.join(base_dir, "music")
            music2_dir = os.path.join(base_dir, "music2")
            os.makedirs(music_dir)
            os.makedirs(music2_dir)

            folder_a = db.Folder.create(root=True, name="music", path=music_dir)
            folder_b = db.Folder.create(root=True, name="music2", path=music2_dir)

            resolved = findRootFolder(os.path.join(music2_dir, "album", "track.flac"))

            self.assertEqual(resolved.id, folder_b.id)
            self.assertNotEqual(resolved.id, folder_a.id)
        finally:
            shutil.rmtree(base_dir)

    def test_replace_track_artists_removes_stale_relations(self):
        root_dir = tempfile.mkdtemp()
        try:
            album_dir = os.path.join(root_dir, "album")
            os.makedirs(album_dir)

            root_folder = db.Folder.create(root=True, name="root", path=root_dir)
            folder = db.Folder.create(root=False, name="album", path=album_dir, parent=root_folder)
            old_artist = db.Artist.create(name="Old Artist")
            new_artist = db.Artist.create(name="New Artist")
            album = db.Album.create(name="Album", artist=old_artist)
            track = db.Track.create(
                disc=1,
                number=1,
                title="Track",
                duration=1,
                has_art=False,
                album=album,
                artist=old_artist,
                bitrate=128,
                path=os.path.join(album_dir, "track.flac"),
                last_modification=1,
                root_folder=root_folder,
                folder=folder,
            )

            db.TrackArtist.create(track_id=track, artist_id=old_artist)

            from supysonic.scanner_func.scanner_relations import replaceTrackArtists

            with patch(
                "supysonic.scanner_func.scanner_relations.findArtist",
                return_value=new_artist,
            ):
                replaceTrackArtists(self.scanner, ["New Artist"], track)

            track_artist_ids = sorted(relation.artist_id_id for relation in track.track_artists)
            self.assertEqual(track_artist_ids, [new_artist.id])
        finally:
            shutil.rmtree(root_dir)

    def test_create_album_review_tasks_creates_one_pending_task_per_new_album(self):
        artist = db.Artist.create(name="Review Artist")
        album = db.Album.create(name="Review Album", artist=artist)

        from supysonic.scanner_func.scanner_review_tasks import createAlbumReviewTasks, rememberNewAlbum

        rememberNewAlbum(self.scanner, album)
        createAlbumReviewTasks(self.scanner)

        tasks = list(db.AlbumReviewTask.select().where(db.AlbumReviewTask.album == album))
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].status, "pending")
        self.assertEqual(tasks[0].reason, "new_album")

    def test_create_album_review_tasks_skips_when_pending_task_exists(self):
        artist = db.Artist.create(name="Review Artist")
        album = db.Album.create(name="Review Album", artist=artist)

        db.AlbumReviewTask.create(
            album=album,
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json="{}",
        )

        from supysonic.scanner_func.scanner_review_tasks import createAlbumReviewTasks, rememberNewAlbum

        rememberNewAlbum(self.scanner, album)
        createAlbumReviewTasks(self.scanner)

        task_count = db.AlbumReviewTask.select().where(db.AlbumReviewTask.album == album).count()
        self.assertEqual(task_count, 1)

    def test_create_album_review_tasks_allows_new_task_after_closed_task(self):
        artist = db.Artist.create(name="Review Artist")
        album = db.Album.create(name="Review Album", artist=artist)

        db.AlbumReviewTask.create(
            album=album,
            task_type="metadata_review",
            status="dismissed",
            reason="new_album",
            snapshot_json="{}",
            resolved_at=db.now(),
        )

        from supysonic.scanner_func.scanner_review_tasks import createAlbumReviewTasks, rememberNewAlbum

        rememberNewAlbum(self.scanner, album)
        createAlbumReviewTasks(self.scanner)

        tasks = list(
            db.AlbumReviewTask.select()
            .where(db.AlbumReviewTask.album == album)
            .order_by(db.AlbumReviewTask.created)
        )
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[-1].status, "pending")

    def test_run_scanner_skips_post_processing_after_stop_requested(self):
        calls = []

        class FakeScanner:
            def __init__(self):
                self.stop_requested = False

            def next_queued_folder(self):
                if calls:
                    return None
                return "folder"

            def scan_folder(self, folder):
                calls.append(("scan_folder", folder))
                self.stop_requested = True

            def decideAllPositions(self):
                calls.append(("decideAllPositions", None))

            def find_lost_information(self):
                calls.append(("find_lost_information", None))

            def handle_done(self):
                calls.append(("handle_done", None))

        fake_scanner = FakeScanner()
        fake_logger = SimpleNamespace(info=lambda *args, **kwargs: None)

        with patch.object(scanner_runtime, "open_connection", return_value=False), patch.object(
            scanner_runtime, "close_connection"
        ), patch.object(scanner_runtime, "Folder") as folder_model, patch.object(
            scanner_runtime, "pruneLibrary"
        ) as prune_library:
            folder_model.get.return_value = "folder-row"

            scanner_runtime.runScanner(fake_scanner, fake_logger)

        self.assertEqual(calls, [("scan_folder", "folder-row")])
        prune_library.assert_not_called()

    def test_run_scanner_logs_summary_after_successful_run(self):
        calls = []

        class FakeScanner:
            stop_requested = False

            def __init__(self):
                self._stats = SimpleNamespace(
                    added=SimpleNamespace(artists=1, albums=2, tracks=3),
                    deleted=SimpleNamespace(artists=4, albums=5, tracks=6),
                    errors=["bad-file.mp3", "bad-folder"],
                    scanned=7,
                    existing_tracks=8,
                )

            def next_queued_folder(self):
                if calls:
                    return None
                return "folder"

            def scan_folder(self, folder):
                calls.append(("scan_folder", folder))

            def decideAllPositions(self):
                calls.append(("decideAllPositions", None))

            def find_lost_information(self):
                calls.append(("find_lost_information", None))

            def handle_done(self):
                calls.append(("handle_done", None))

            def stats(self):
                return self._stats

        fake_scanner = FakeScanner()
        fake_logger = Mock()

        with patch.object(scanner_runtime, "open_connection", return_value=False), patch.object(
            scanner_runtime, "close_connection"
        ), patch.object(scanner_runtime, "Folder") as folder_model, patch.object(
            scanner_runtime, "pruneLibrary"
        ) as prune_library, patch.object(
            scanner_runtime, "createAlbumReviewTasks"
        ) as create_review_tasks:
            folder_model.get.return_value = "folder-row"

            scanner_runtime.runScanner(fake_scanner, fake_logger)

        prune_library.assert_called_once_with(fake_scanner)
        create_review_tasks.assert_called_once_with(fake_scanner)
        fake_logger.info.assert_any_call("begin to find all covers")
        fake_logger.info.assert_any_call(
            "scan summary scanned=%s existing_tracks=%s added=%s/%s/%s deleted=%s/%s/%s errors=%s",
            7,
            8,
            1,
            2,
            3,
            4,
            5,
            6,
            2,
        )

    def test_scan_folder_entries_continues_after_scandir_error(self):
        root_dir = tempfile.mkdtemp()
        try:
            bad_dir = os.path.join(root_dir, "blocked")
            good_file = os.path.join(root_dir, "song.mp3")
            os.makedirs(bad_dir)
            with open(good_file, "wb") as f:
                f.write(b"")

            root_folder = db.Folder.create(root=True, name="root", path=root_dir)
            scanned_paths = []
            scanner = SimpleNamespace(
                stop_requested=False,
                follow_symlinks=False,
                should_scan_extension=lambda path: path.endswith(".mp3"),
                scan_file=lambda entry: scanned_paths.append(entry.path),
                report_progress=lambda folder_name, scanned: None,
                stats=lambda: self.stats,
            )

            real_scandir = os.scandir

            def fake_scandir(path):
                if path == bad_dir:
                    raise PermissionError("blocked")
                return real_scandir(path)

            with patch("supysonic.scanner_func.scanner_folder.os.scandir", side_effect=fake_scandir):
                scanner_folder._scanFolderEntries(scanner, root_folder)

            self.assertEqual(scanned_paths, [good_file])
            self.assertEqual(self.stats.errors, [bad_dir])
        finally:
            shutil.rmtree(root_dir)


if __name__ == "__main__":
    unittest.main()
