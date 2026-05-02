import unittest

from flask import current_app

from supysonic.db import Album, AlbumReviewTask, Artist, User, db

from .frontendtestbase import FrontendTestBase
from ..testbase import TestConfig


class MetadataInboxTestCase(FrontendTestBase):
    __with_api__ = True

    def setUp(self):
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["log_dir"] = ""
        super().setUp()
        db.execute_sql("ALTER TABLE artist ADD COLUMN artist_info_json VARCHAR(4096)")
        db.execute_sql("ALTER TABLE artist ADD COLUMN real_artist_id INTEGER")
        db.execute_sql("ALTER TABLE album ADD COLUMN year VARCHAR(255)")

        alice = User.get(User.name == "alice")
        with self.client.session_transaction() as session:
            session["userid"] = str(alice.id)

        with self.app_context():
            view_functions = current_app.view_functions
            if "emo.list_logs" not in view_functions:
                current_app.add_url_rule("/emo/test-logs", endpoint="emo.list_logs", view_func=lambda: "")

    def test_metadata_inbox_renders_pending_review_task(self):
        artist = Artist.create(name="Review Artist")
        album = Album.create(name="Review Album", artist=artist, year="2024")
        AlbumReviewTask.create(
            album=album,
            task_type="metadata_review",
            status="pending",
            reason="new_album",
            snapshot_json='{"album_name": "Review Album", "track_count": 0}',
        )

        rv = self.client.get("/metadata?tab=inbox")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("Review Album", rv.data)
        self.assertIn("Review", rv.data)
        self.assertIn("Confirm", rv.data)
        self.assertIn("Dismiss", rv.data)
        self.assertIn(f"/rest/getCoverArt?id=al-{album.id}&amp;v=1.15.0&amp;c=web", rv.data)
        self.assertNotIn("No pending review tasks yet", rv.data)

    def test_metadata_inbox_keeps_empty_state_without_tasks(self):
        rv = self.client.get("/metadata?tab=inbox")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("No pending review tasks yet", rv.data)


if __name__ == "__main__":
    unittest.main()
