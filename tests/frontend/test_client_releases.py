import hashlib
import io
import os
import shutil
import tempfile
import unittest

from supysonic.db import ClientRelease, User

from .frontendtestbase import FrontendTestBase
from ..testbase import TestBase, TestConfig


class ClientReleaseEndpointTestCase(TestBase):
    def setUp(self):
        self.releaseUploadDir = tempfile.mkdtemp()
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["mount_client_releases"] = True
        TestConfig.WEBAPP["release_api_token"] = "release-secret"
        TestConfig.WEBAPP["release_upload_dir"] = self.releaseUploadDir
        super().setUp()

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.releaseUploadDir)

    def publishExternalRelease(self, buildNumber, downloadUrl="https://downloads.example.com/app.apk"):
        return self.client.post(
            "/client-releases/publish",
            json={
                "platform": "android",
                "buildName": "1.0.0",
                "buildNumber": buildNumber,
                "fileType": "apk",
                "downloadUrl": downloadUrl,
                "releaseNotes": "Release notes",
            },
            headers={"X-Release-Token": "release-secret"},
        )

    def test_latest_release_is_public_and_returns_json_empty_state(self):
        rv = self.client.get("/client-releases/latest?platform=android")

        self.assertEqual(rv.status_code, 404)
        self.assertEqual(rv.json["error"], "No release available")
        self.assertNotIn(b"Please login", rv.data)

    def test_publish_external_release_and_query_latest(self):
        rv = self.publishExternalRelease(2)

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json["release"]["platform"], "android")
        self.assertEqual(rv.json["release"]["version"], "1.0.0+2")
        self.assertEqual(rv.json["release"]["publishMode"], "external_url")
        self.assertTrue(rv.json["release"]["downloadUrl"].startswith("/client-releases/download/"))
        self.assertEqual(rv.json["release"]["sourceDownloadUrl"], "https://downloads.example.com/app.apk")

        redirected = self.client.get(rv.json["release"]["downloadUrl"])
        self.assertEqual(redirected.status_code, 302)
        self.assertEqual(redirected.location, "https://downloads.example.com/app.apk")

        latest = self.client.get("/client-releases/latest?platform=android")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json["release"]["version"], "1.0.0+2")

    def test_publish_requires_release_token(self):
        rv = self.client.post(
            "/client-releases/publish",
            json={
                "platform": "android",
                "buildName": "1.0.0",
                "buildNumber": 1,
                "fileType": "apk",
                "downloadUrl": "https://downloads.example.com/app.apk",
            },
        )

        self.assertEqual(rv.status_code, 403)
        self.assertEqual(rv.json["error"], "Invalid release token")

    def test_upload_release_stores_file_and_downloads_it_publicly(self):
        payload = b"apk-data"
        rv = self.client.post(
            "/client-releases/publish",
            data={
                "platform": "android",
                "buildName": "1.0.0",
                "buildNumber": "3",
                "releaseNotes": "Uploaded release",
                "file": (io.BytesIO(payload), "client.apk"),
            },
            content_type="multipart/form-data",
            headers={"X-Release-Token": "release-secret"},
        )

        self.assertEqual(rv.status_code, 200)
        release = rv.json["release"]
        self.assertEqual(release["publishMode"], "upload")
        self.assertEqual(release["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(release["fileSize"], len(payload))

        downloaded = self.client.get(release["downloadUrl"])
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.data, payload)
        downloaded.close()

    def test_publish_rejects_invalid_platform_file_type(self):
        rv = self.client.post(
            "/client-releases/publish",
            json={
                "platform": "windows",
                "buildName": "1.0.0",
                "buildNumber": 1,
                "fileType": "apk",
                "downloadUrl": "https://downloads.example.com/app.apk",
            },
            headers={"X-Release-Token": "release-secret"},
        )

        self.assertEqual(rv.status_code, 400)
        self.assertIn("Invalid file type", rv.json["error"])

    def test_republishing_same_version_overwrites_release_record(self):
        first = self.publishExternalRelease(5, "https://downloads.example.com/old.apk")
        second = self.publishExternalRelease(5, "https://downloads.example.com/new.apk")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(ClientRelease.select().count(), 1)
        latest = self.client.get("/client-releases/latest?platform=android")
        self.assertEqual(latest.json["release"]["sourceDownloadUrl"], "https://downloads.example.com/new.apk")

    def test_republishing_uploaded_release_removes_previous_upload(self):
        first = self.client.post(
            "/client-releases/publish",
            data={
                "platform": "android",
                "buildName": "1.0.0",
                "buildNumber": "6",
                "file": (io.BytesIO(b"old-apk"), "client.apk"),
            },
            content_type="multipart/form-data",
            headers={"X-Release-Token": "release-secret"},
        )
        oldPath = ClientRelease.get().file_path

        second = self.client.post(
            "/client-releases/publish",
            data={
                "platform": "android",
                "buildName": "1.0.0",
                "buildNumber": "6",
                "file": (io.BytesIO(b"new-apk"), "client.apk"),
            },
            content_type="multipart/form-data",
            headers={"X-Release-Token": "release-secret"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(os.path.exists(oldPath))
        self.assertTrue(os.path.exists(ClientRelease.get().file_path))

    def test_latest_release_uses_flutter_build_name_and_number_order(self):
        self.publishExternalRelease(9, "https://downloads.example.com/1.0.0.apk")
        self.client.post(
            "/client-releases/publish",
            json={
                "platform": "android",
                "buildName": "1.0.1",
                "buildNumber": 1,
                "fileType": "apk",
                "downloadUrl": "https://downloads.example.com/1.0.1.apk",
            },
            headers={"X-Release-Token": "release-secret"},
        )

        latest = self.client.get("/client-releases/latest?platform=android")

        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json["release"]["version"], "1.0.1+1")


class ClientReleaseHomeTestCase(FrontendTestBase):
    def setUp(self):
        self.releaseUploadDir = tempfile.mkdtemp()
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["mount_client_releases"] = True
        TestConfig.WEBAPP["release_api_token"] = "release-secret"
        TestConfig.WEBAPP["release_upload_dir"] = self.releaseUploadDir
        super().setUp()
        alice = User.get(User.name == "alice")
        with self.client.session_transaction() as session:
            session["userid"] = str(alice.id)

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.releaseUploadDir)

    def test_home_renders_latest_client_release_downloads(self):
        ClientRelease.create(
            platform="android",
            file_type="apk",
            build_name="1.0.0",
            build_number=4,
            version="1.0.0+4",
            publish_mode="external_url",
            file_name="client.apk",
            download_url="https://downloads.example.com/client.apk",
            release_notes="Stable Android build",
        )

        rv = self.client.get("/")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("Client downloads", rv.data)
        self.assertIn("Android", rv.data)
        self.assertIn("1.0.0+4", rv.data)
        self.assertIn("Download Android", rv.data)
        self.assertIn("History", rv.data)
        self.assertIn("/client-releases/history?platform=android", rv.data)
        self.assertIn("Windows", rv.data)
        self.assertIn("Not available", rv.data)

    def test_history_page_renders_platform_release_history(self):
        ClientRelease.create(
            platform="android",
            file_type="apk",
            build_name="1.0.0",
            build_number=4,
            version="1.0.0+4",
            publish_mode="external_url",
            file_name="client-v4.apk",
            download_url="https://downloads.example.com/client-v4.apk",
            release_notes="Older Android build",
        )
        ClientRelease.create(
            platform="android",
            file_type="apk",
            build_name="1.1.0",
            build_number=2,
            version="1.1.0+2",
            publish_mode="external_url",
            file_name="client-v110.apk",
            download_url="https://downloads.example.com/client-v110.apk",
            release_notes="Newer Android build",
        )

        rv = self.client.get("/client-releases/history?platform=android")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("Release history", rv.data)
        self.assertIn("Android", rv.data)
        self.assertIn("1.1.0+2", rv.data)
        self.assertIn("1.0.0+4", rv.data)
        self.assertIn("Download", rv.data)
        self.assertLess(rv.data.index("1.1.0+2"), rv.data.index("1.0.0+4"))

    def test_history_page_accepts_case_insensitive_platform(self):
        ClientRelease.create(
            platform="android",
            file_type="apk",
            build_name="1.0.0",
            build_number=4,
            version="1.0.0+4",
            publish_mode="external_url",
            file_name="client.apk",
            download_url="https://downloads.example.com/client.apk",
        )

        rv = self.client.get("/client-releases/history?platform=Android")

        self.assertEqual(rv.status_code, 200)
        self.assertIn("Android", rv.data)
        self.assertIn("1.0.0+4", rv.data)


class ClientReleaseDisabledHomeTestCase(FrontendTestBase):
    def setUp(self):
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["mount_client_releases"] = False
        super().setUp()
        alice = User.get(User.name == "alice")
        with self.client.session_transaction() as session:
            session["userid"] = str(alice.id)

    def tearDown(self):
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["mount_client_releases"] = True
        super().tearDown()

    def test_home_hides_client_release_downloads_when_feature_is_disabled(self):
        ClientRelease.create(
            platform="android",
            file_type="apk",
            build_name="1.0.0",
            build_number=4,
            version="1.0.0+4",
            publish_mode="external_url",
            file_name="client.apk",
            download_url="https://downloads.example.com/client.apk",
        )

        rv = self.client.get("/")

        self.assertEqual(rv.status_code, 200)
        self.assertNotIn("Client downloads", rv.data)
        self.assertNotIn("/client-releases/download/", rv.data)


class ClientReleaseWithoutWebUiTestCase(TestBase):
    def test_history_page_returns_not_found_when_webui_is_disabled(self):
        rv = self.client.get("/client-releases/history?platform=android")

        self.assertEqual(rv.status_code, 404)
        self.assertEqual(rv.json["error"], "Client release history page requires the web UI")


if __name__ == "__main__":
    unittest.main()
