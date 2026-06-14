import unittest

from lxml import etree

from supysonic.db import MusicRequest, User

from .apitestbase import ApiTestBase


class MusicRequestApiTestCase(ApiTestBase):
    def _api_get(self, endpoint, args=None):
        query = {"u": "alice", "p": "Alic3", "c": "tests", "f": "json"}
        if args:
            query.update(args)
        return self.client.get(f"/rest/{endpoint}.view", query_string=query)

    def _api_post(self, endpoint, data=None):
        payload = {"u": "alice", "p": "Alic3", "c": "tests", "f": "json"}
        if data:
            payload.update(data)
        return self.client.post(f"/rest/{endpoint}.view", data=payload)

    def _json_response(self, rv):
        self.assertEqual(rv.status_code, 200)
        return rv.get_json()["subsonic-response"]

    def _assert_error(self, rv, code):
        data = self._json_response(rv)
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["error"]["code"], code)
        return data

    def _create_record(self, user_name, **kwargs):
        defaults = {
            "artist_name": "Request Artist",
            "album_name": "Request Album",
        }
        defaults.update(kwargs)
        return MusicRequest.create(user=User.get(name=user_name), **defaults)

    def test_list_music_requests_for_all_users_with_filter_and_pagination(self):
        alice_pending = self._create_record("alice", artist_name="Alice Artist")
        self._create_record("bob", artist_name="Bob Artist")
        resolved = self._create_record(
            "bob",
            artist_name="Resolved Artist",
            status=MusicRequest.STATUS_RESOLVED,
        )

        data = self._json_response(self._api_get("getMusicRequests"))

        requests = data["musicRequests"]["musicRequest"]
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["musicRequests"]["total"], 3)
        self.assertEqual(data["musicRequests"]["pendingCount"], 2)
        self.assertEqual(data["musicRequests"]["resolvedCount"], 1)
        self.assertEqual(data["musicRequests"]["rejectedCount"], 0)
        self.assertIn(str(alice_pending.id), {record["id"] for record in requests})
        self.assertEqual(requests[0]["status"], MusicRequest.STATUS_PENDING)
        self.assertTrue(requests[0]["canUpdateStatus"])

        data = self._json_response(
            self._api_get(
                "getMusicRequests",
                {"status": MusicRequest.STATUS_RESOLVED, "count": "1", "offset": "0"},
            )
        )
        requests = data["musicRequests"]["musicRequest"]
        self.assertEqual(data["musicRequests"]["count"], 1)
        self.assertEqual(data["musicRequests"]["total"], 1)
        self.assertEqual(requests[0]["id"], str(resolved.id))
        self.assertEqual(requests[0]["username"], "bob")

    def test_list_music_requests_rejects_invalid_filters(self):
        self._assert_error(
            self._api_get("getMusicRequests", {"status": "done"}),
            0,
        )
        self._assert_error(
            self._api_get("getMusicRequests", {"count": "many"}),
            0,
        )
        self._assert_error(
            self._api_get("getMusicRequests", {"offset": "-1"}),
            0,
        )

    def test_create_music_request_validates_and_stores_tracks(self):
        self._assert_error(self._api_post("createMusicRequest"), 10)
        self._assert_error(
            self._api_post("createMusicRequest", {"artistName": "No target"}),
            0,
        )

        rv = self.client.post(
            "/rest/createMusicRequest.view",
            data={
                "u": "alice",
                "p": "Alic3",
                "c": "tests",
                "f": "json",
                "artistName": "Missing Artist",
                "albumName": "Missing Album",
                "track": ["First song", "  Second song  "],
                "tracks": "Third song\n\nFourth song",
                "note": "Japanese edition",
            },
        )
        data = self._json_response(rv)

        record_data = data["musicRequest"]
        record = MusicRequest.get_by_id(record_data["id"])
        self.assertEqual(record.user.name, "alice")
        self.assertEqual(record.album_name, "Missing Album")
        self.assertEqual(
            record.get_track_titles(),
            ["First song", "Second song", "Third song", "Fourth song"],
        )
        self.assertEqual(record.note, "Japanese edition")
        self.assertEqual(record_data["track"], record.get_track_titles())
        self.assertFalse(record_data["similarPending"])

    def test_create_music_request_reports_similar_pending_request(self):
        self._create_record(
            "bob",
            artist_name="Same Artist",
            album_name="Same Album",
        )

        data = self._json_response(
            self._api_post(
                "createMusicRequest",
                {"artistName": " same   artist ", "albumName": "SAME ALBUM"},
            )
        )

        self.assertTrue(data["musicRequest"]["similarPending"])
        self.assertEqual(MusicRequest.select().count(), 2)

    def test_delete_music_request_permissions(self):
        record = self._create_record("alice")
        bob_record = self._create_record("bob", artist_name="Bob Artist")

        self._assert_error(
            self._api_post(
                "deleteMusicRequest",
                {"u": "bob", "p": "B0b", "id": str(record.id)},
            ),
            50,
        )
        self.assertEqual(MusicRequest.select().count(), 2)

        self._json_response(
            self._api_post(
                "deleteMusicRequest",
                {"u": "bob", "p": "B0b", "id": str(bob_record.id)},
            )
        )
        self.assertIsNone(MusicRequest.get_or_none(MusicRequest.id == bob_record.id))

        self._json_response(
            self._api_post("deleteMusicRequest", {"id": str(record.id)})
        )
        self.assertEqual(MusicRequest.select().count(), 0)

    def test_update_music_request_status_requires_admin(self):
        record = self._create_record("bob")

        self._assert_error(
            self._api_post(
                "updateMusicRequestStatus",
                {
                    "u": "bob",
                    "p": "B0b",
                    "id": str(record.id),
                    "status": MusicRequest.STATUS_RESOLVED,
                },
            ),
            50,
        )
        self.assertEqual(MusicRequest.get_by_id(record.id).status, MusicRequest.STATUS_PENDING)

        self._assert_error(
            self._api_post(
                "updateMusicRequestStatus",
                {"id": str(record.id), "status": "done"},
            ),
            0,
        )

        data = self._json_response(
            self._api_post(
                "updateMusicRequestStatus",
                {
                    "id": str(record.id),
                    "status": MusicRequest.STATUS_RESOLVED,
                    "statusNote": "Added",
                },
            )
        )

        updated = MusicRequest.get_by_id(record.id)
        self.assertEqual(updated.status, MusicRequest.STATUS_RESOLVED)
        self.assertEqual(updated.status_note, "Added")
        self.assertIsNotNone(updated.resolved_at)
        self.assertEqual(data["musicRequest"]["status"], MusicRequest.STATUS_RESOLVED)
        self.assertEqual(data["musicRequest"]["statusNote"], "Added")
        self.assertIn("resolvedAt", data["musicRequest"])

    def test_music_request_id_errors_and_auth_requirement(self):
        self._assert_error(self._api_post("deleteMusicRequest"), 10)
        self._assert_error(
            self._api_post("deleteMusicRequest", {"id": "not-a-uuid"}),
            0,
        )
        self._assert_error(
            self._api_post(
                "deleteMusicRequest",
                {"id": "00000000-0000-0000-0000-000000000000"},
            ),
            70,
        )

        rv = self.client.get(
            "/rest/getMusicRequests.view",
            query_string={"p": "Alic3", "c": "tests", "f": "json"},
        )
        self._assert_error(rv, 10)

    def test_get_music_requests_xml_smoke(self):
        record = self._create_record("alice", artist_name="XML Artist")

        rv = self.client.get(
            "/rest/getMusicRequests.view",
            query_string={"u": "alice", "p": "Alic3", "c": "tests"},
        )

        xml = etree.fromstring(rv.data)
        self.assertEqual(xml.get("status"), "ok")
        music_requests = self._find(xml, "./musicRequests")
        self.assertIsNotNone(music_requests)
        item = self._find(music_requests, f"./musicRequest[@id='{record.id}']")
        self.assertIsNotNone(item)
        self.assertEqual(item.get("artistName"), "XML Artist")


if __name__ == "__main__":
    unittest.main()
