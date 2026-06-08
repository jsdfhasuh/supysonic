from supysonic.db import MusicRequest, User

from .frontendtestbase import FrontendTestBase


class MusicRequestTestCase(FrontendTestBase):
    def test_index_requires_login(self):
        rv = self.client.get("/music-requests", follow_redirects=True)

        self.assertIn("Please login", rv.data)

    def test_create_album_request(self):
        self._login("alice", "Alic3")

        rv = self.client.post(
            "/music-requests",
            data={
                "artist_name": "Missing Artist",
                "album_name": "Missing Album",
                "tracks": "First song\nSecond song\n",
                "note": "Japanese edition",
            },
            follow_redirects=True,
        )

        self.assertIn("Music request saved", rv.data)
        self.assertEqual(MusicRequest.select().count(), 1)
        record = MusicRequest.get()
        self.assertEqual(record.user.name, "alice")
        self.assertEqual(record.artist_name, "Missing Artist")
        self.assertEqual(record.album_name, "Missing Album")
        self.assertEqual(record.get_track_titles(), ["First song", "Second song"])
        self.assertEqual(record.note, "Japanese edition")
        self.assertEqual(record.status, MusicRequest.STATUS_PENDING)
        self.assertIn("Missing Album", rv.data)
        self.assertIn("First song", rv.data)

    def test_all_logged_in_users_can_view_requests(self):
        MusicRequest.create(
            user=User.get(name="alice"),
            artist_name="Visible Artist",
            album_name="Visible Album",
        )

        self._login("bob", "B0b")
        rv = self.client.get("/music-requests")

        self.assertIn("Visible Artist", rv.data)
        self.assertIn("Visible Album", rv.data)

    def test_create_request_validation(self):
        self._login("alice", "Alic3")

        rv = self.client.post(
            "/music-requests",
            data={"album_name": "No artist"},
            follow_redirects=True,
        )

        self.assertIn("Missing artist name", rv.data)
        self.assertEqual(MusicRequest.select().count(), 0)

        rv = self.client.post(
            "/music-requests",
            data={"artist_name": "No target"},
            follow_redirects=True,
        )

        self.assertIn("Provide an album name or at least one track title", rv.data)
        self.assertEqual(MusicRequest.select().count(), 0)

    def test_duplicate_pending_request_warns_but_allows_create(self):
        self._login("alice", "Alic3")
        payload = {"artist_name": "Same Artist", "album_name": "Same Album"}

        self.client.post("/music-requests", data=payload, follow_redirects=True)
        rv = self.client.post("/music-requests", data=payload, follow_redirects=True)

        self.assertIn("similar pending request already exists", rv.data)
        self.assertEqual(MusicRequest.select().count(), 2)

    def test_submitter_can_delete_own_request_but_not_others(self):
        record = MusicRequest.create(
            user=User.get(name="alice"),
            artist_name="Delete Artist",
            album_name="Delete Album",
        )

        self._login("bob", "B0b")
        rv = self.client.post(
            f"/music-requests/{record.id}/delete",
            follow_redirects=True,
        )
        self.assertIn("not allowed", rv.data)
        self.assertEqual(MusicRequest.select().count(), 1)
        self._logout()

        self._login("alice", "Alic3")
        rv = self.client.post(
            f"/music-requests/{record.id}/delete",
            follow_redirects=True,
        )
        self.assertIn("deleted", rv.data)
        self.assertEqual(MusicRequest.select().count(), 0)

    def test_admin_updates_status_and_regular_user_cannot(self):
        record = MusicRequest.create(
            user=User.get(name="bob"),
            artist_name="Status Artist",
            album_name="Status Album",
        )

        self._login("bob", "B0b")
        rv = self.client.post(
            f"/music-requests/{record.id}/status",
            data={"status": MusicRequest.STATUS_RESOLVED, "status_note": "Added"},
            follow_redirects=True,
        )
        self.assertIn("not allowed", rv.data)
        self.assertEqual(MusicRequest.get_by_id(record.id).status, MusicRequest.STATUS_PENDING)
        self._logout()

        self._login("alice", "Alic3")
        rv = self.client.post(
            f"/music-requests/{record.id}/status",
            data={"status": MusicRequest.STATUS_RESOLVED, "status_note": "Added"},
            follow_redirects=True,
        )

        self.assertIn("status updated", rv.data)
        updated = MusicRequest.get_by_id(record.id)
        self.assertEqual(updated.status, MusicRequest.STATUS_RESOLVED)
        self.assertEqual(updated.status_note, "Added")
        self.assertIsNotNone(updated.resolved_at)
