import unittest
import tempfile
import os

from flask import current_app
from uuid import uuid4

from supysonic.tool import write_dict_to_json
from supysonic.db import Album, AlbumArtist, AlbumReviewTask, Artist, Folder, Track, TrackArtist, User, db

from .frontendtestbase import FrontendTestBase
from ..testbase import TestConfig


class MetadataReviewWorkspaceTestCase(FrontendTestBase):
    __with_api__ = True

    def setUp(self):
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["log_dir"] = ""
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

        with self.app_context():
            view_functions = current_app.view_functions
            if "emo.list_logs" not in view_functions:
                current_app.add_url_rule("/emo/test-logs", endpoint="emo.list_logs", view_func=lambda: "")

        self.artist = Artist.create(name="Review Artist")
        imagePath = os.path.join(tempfile.gettempdir(), "review-artist-image.png")
        write_dict_to_json({"biography": "", "image": {"large": imagePath}}, imagePath + ".json")
        self.artist.artist_info_json = imagePath + ".json"
        self.artist.save()
        self.album = Album.create(name="Review Album", artist=self.artist, year="2024")
        self.root = Folder.create(root=True, name="Root", path="/tmp/root")
        self.folder = Folder.create(root=False, name="Album", path="/tmp/root/album", parent=self.root)
        Track.create(
            disc=1,
            number=1,
            title="First Track",
            duration=120,
            has_art=False,
            album=self.album,
            artist=self.artist,
            bitrate=320,
            path="/tmp/review-track.flac",
            last_modification=1,
            root_folder=self.root,
            folder=self.folder,
        )
        AlbumArtist.create(album_id=self.album, artist_id=self.artist, position=1)
        TrackArtist.create(track_id=self.album.tracks.get(), artist_id=self.artist, position=1)
        self.task = AlbumReviewTask.create(
            album=self.album,
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json='{"album_name": "Review Album", "artist_name": "Review Artist", "track_count": 1}',
        )

    def test_review_workspace_renders_scoped_album_task(self):
        rv = self.client.get(f"/metadata/review-tasks/{self.task.id}")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("Metadata / Inbox / Review Task", rv.data)
        self.assertIn("Review Album", rv.data)
        self.assertIn("Review Artist", rv.data)
        self.assertIn("Album", rv.data)
        self.assertIn("Tracks", rv.data)
        self.assertIn("Artists", rv.data)
        self.assertIn("Confirm Task", rv.data)
        self.assertIn("Dismiss Task", rv.data)
        self.assertIn("edits are scoped to this album review task", rv.data.lower())
        self.assertIn("metadata-review-feedback", rv.data)
        self.assertIn("data-review-task-action", rv.data)
        self.assertIn("applyResolvedReviewTaskState", rv.data)
        self.assertIn("updateReviewSummaryStatus", rv.data)
        self.assertIn("applyAlbumFormChanges", rv.data)
        self.assertIn("applyTrackFormChanges", rv.data)
        self.assertIn("applyArtistFormChanges", rv.data)
        self.assertIn("review-album-artist-suggestions", rv.data)
        self.assertIn("data-track-artist-suggestions", rv.data)
        self.assertIn("artist-autocomplete.js", rv.data)
        self.assertIn("/metadata/artist-suggestions", rv.data)
        self.assertNotIn("reloadReviewPage('album')", rv.data)
        self.assertNotIn("reloadReviewPage('tracks')", rv.data)
        self.assertNotIn("reloadReviewPage('artists')", rv.data)
        self.assertIn(f"/rest/getCoverArt?id=al-{self.album.id}&amp;v=1.15.0&amp;c=web", rv.data)
        self.assertIn(f"/rest/getCoverArt?id=ar-{self.artist.id}&amp;v=1.15.0&amp;c=web", rv.data)
        self.assertNotIn("Loading album data...", rv.data)
        self.assertNotIn("Loading artist data...", rv.data)

    def test_review_workspace_includes_back_to_metadata_button(self):
        rv = self.client.get(f"/metadata/review-tasks/{self.task.id}?section=tracks")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("Back to Metadata Inbox", rv.data)
        self.assertIn('href="/metadata?tab=inbox"', rv.data)
        self.assertIn("metadata-review-return-bar", rv.data)
        self.assertIn("metadata-review-back-link", rv.data)

    def test_review_workspace_confirm_button_includes_nfo_write_warning(self):
        rv = self.client.get(f"/metadata/review-tasks/{self.task.id}")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("Confirm Task", rv.data)
        self.assertIn("album.nfo", rv.data)
        self.assertIn("window.confirm", rv.data)
        self.assertIn("button.dataset.reviewTaskLabel === 'confirm'", rv.data)
        self.assertIn("window.location.assign(metadataInboxUrl)", rv.data)
        self.assertIn('/metadata?tab=inbox', rv.data)

    def test_review_workspace_includes_guest_relation_artists(self):
        guest_artist = Artist.create(name="Guest Relation Artist")
        AlbumArtist.create(album_id=self.album, artist_id=guest_artist, position=2)
        TrackArtist.create(track_id=self.album.tracks.get(), artist_id=guest_artist, position=2)

        rv = self.client.get(f"/metadata/review-tasks/{self.task.id}")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("Guest Relation Artist", rv.data)

    def test_review_workspace_handles_artist_metadata_without_image_key(self):
        image_less_artist = Artist.create(name="Image Less Artist")
        image_less_artist.artist_info_json = os.path.join(tempfile.gettempdir(), "image-less-artist.json")
        write_dict_to_json({"biography": "No image key"}, image_less_artist.artist_info_json)
        image_less_artist.save()
        AlbumArtist.create(album_id=self.album, artist_id=image_less_artist, position=2)

        rv = self.client.get(f"/metadata/review-tasks/{self.task.id}")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("Image Less Artist", rv.data)

    def test_review_workspace_rejects_invalid_task_id(self):
        rv = self.client.get("/metadata/review-tasks/not-a-uuid")

        self.assertEqual(rv.status_code, 400)
        self.assertEqual(rv.json["status"], "error")

    def test_review_workspace_returns_404_for_missing_task(self):
        rv = self.client.get(f"/metadata/review-tasks/{uuid4()}")

        self.assertEqual(rv.status_code, 404)
        self.assertEqual(rv.json["status"], "error")

    def test_review_workspace_honors_requested_section(self):
        rv = self.client.get(f"/metadata/review-tasks/{self.task.id}?section=tracks")

        self.assertEqual(rv.status_code, 200)
        self.assertIn('data-review-panel="tracks"', rv.data)
        self.assertIn("tab-btn active", rv.data)
        self.assertIn("data-review-track-workbench", rv.data)
        self.assertIn("data-review-track-context", rv.data)
        self.assertIn("data-review-track-studio", rv.data)
        self.assertIn("data-review-track-sequence", rv.data)
        self.assertIn("data-review-track-sequence-item", rv.data)
        self.assertIn("data-review-track-editor-panel", rv.data)
        self.assertIn("data-review-track-album-note", rv.data)

    def test_review_workspace_renders_resolved_task_as_read_only(self):
        self.task.status = "confirmed"
        self.task.save()

        rv = self.client.get(f"/metadata/review-tasks/{self.task.id}")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("This review task is resolved and now read-only", rv.data)
        self.assertIn("disabled", rv.data)
        self.assertNotIn("Save album changes</button>", rv.data)


if __name__ == "__main__":
    unittest.main()
