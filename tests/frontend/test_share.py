import uuid

from supysonic.db import Album, Artist, Folder, SharedTrackLink, Track, User

from .frontendtestbase import FrontendTestBase


class ShareTrackTestCase(FrontendTestBase):
    def setUp(self):
        super().setUp()

        folder = Folder.create(name="Root", path="tests/assets", root=True)
        artist = Artist.create(name="Artist!")
        album = Album.create(name="Album!", artist=artist)

        self.track = Track.create(
            path="tests/assets/23bytes",
            title="23bytes",
            artist=artist,
            album=album,
            folder=folder,
            root_folder=folder,
            duration=2,
            disc=1,
            number=1,
            bitrate=320,
            last_modification=0,
        )

    def test_create_share_requires_login(self):
        rv = self.client.get(f"/track/{self.track.id}/share", follow_redirects=True)
        self.assertIn("Please login", rv.data)

    def test_create_and_open_share_link(self):
        self._login("alice", "Alic3")
        rv = self.client.get(f"/track/{self.track.id}/share", follow_redirects=True)
        self.assertIn("Share link created", rv.data)
        self.assertEqual(SharedTrackLink.select().count(), 1)

        link = SharedTrackLink.select().first()
        self._logout()

        share_page = self.client.get(f"/share/track/{link.token}")
        self.assertIn("23bytes", share_page.data)
        self.assertIn("Artist!", share_page.data)

        stream = self.client.get(f"/share/track/{link.token}/stream")
        self.assertEqual(stream.status_code, 200)

    def test_share_index_and_disable(self):
        self._login("alice", "Alic3")
        self.client.get(f"/track/{self.track.id}/share", follow_redirects=True)
        link = SharedTrackLink.select().first()

        rv = self.client.get("/share")
        self.assertIn("Shared tracks", rv.data)
        self.assertIn(link.token, rv.data)

        rv = self.client.get(f"/share/track/{link.token}/disable", follow_redirects=True)
        self.assertIn("disabled", rv.data)
        self.assertFalse(SharedTrackLink.get_by_id(link.id).enabled)

    def test_invalid_share_returns_404(self):
        rv = self.client.get(f"/share/track/{uuid.uuid4()}")
        self.assertEqual(rv.status_code, 404)
