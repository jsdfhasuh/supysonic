from supysonic.db import User

from .frontendtestbase import FrontendTestBase


class RegisterTestCase(FrontendTestBase):
    def test_register_page_is_public(self):
        rv = self.client.get("/user/register")
        self.assertIn("Create account", rv.data)

    def test_register_page_creates_user_and_logs_in(self):
        rv = self.client.post(
            "/user/register",
            data={
                "user": "carol",
                "passwd": "Car0l",
                "passwd_confirm": "Car0l",
                "mail": "carol@example.com",
            },
            follow_redirects=True,
        )
        self.assertIn("Account created and logged in", rv.data)
        self.assertIsNotNone(User.get_or_none(name="carol"))
        with self.client.session_transaction() as sess:
            self.assertEqual(str(User.get(name="carol").id), str(sess["userid"]))

    def test_register_page_requires_invite_code_when_configured(self):
        with self.app_context():
            from flask import current_app

            current_app.config["WEBAPP"]["registration_invite_code"] = "EMO-2026"

        page = self.client.get("/user/register")
        self.assertIn("Invite code", page.data)

        missing = self.client.post(
            "/user/register",
            data={
                "user": "iris",
                "passwd": "Ir1s",
                "passwd_confirm": "Ir1s",
            },
            follow_redirects=True,
        )
        self.assertIn("Please provide the registration invite code", missing.data)

        invalid = self.client.post(
            "/user/register",
            data={
                "user": "iris",
                "passwd": "Ir1s",
                "passwd_confirm": "Ir1s",
                "registration_code": "WRONG",
            },
            follow_redirects=True,
        )
        self.assertIn("Invalid registration invite code", invalid.data)

        success = self.client.post(
            "/user/register",
            data={
                "user": "iris",
                "passwd": "Ir1s",
                "passwd_confirm": "Ir1s",
                "registration_code": "EMO-2026",
            },
            follow_redirects=True,
        )
        self.assertIn("Account created and logged in", success.data)
        self.assertIsNotNone(User.get_or_none(name="iris"))

    def test_register_page_can_redirect_to_lastfm_auth(self):
        with self.app_context():
            from flask import current_app

            current_app.config["LASTFM"]["api_key"] = "lastfm-key"
            current_app.config["LASTFM"]["secret"] = "lastfm-secret"

        rv = self.client.post(
            "/user/register",
            data={
                "user": "gina",
                "passwd": "Gina1",
                "passwd_confirm": "Gina1",
                "link_lastfm": "on",
            },
        )
        self.assertEqual(rv.status_code, 302)
        self.assertIn("https://www.last.fm/api/auth/?api_key=lastfm-key", rv.location)
        self.assertIn("/user/me/lastfm/link", rv.location)
        with self.client.session_transaction() as sess:
            self.assertEqual(str(User.get(name="gina").id), str(sess["userid"]))

    def test_register_page_rejects_duplicate_user(self):
        rv = self.client.post(
            "/user/register",
            data={
                "user": "alice",
                "passwd": "Alic3",
                "passwd_confirm": "Alic3",
            },
            follow_redirects=True,
        )
        self.assertIn("User &#39;alice&#39; exists", rv.data)

    def test_register_json_creates_user_and_logs_in(self):
        rv = self.client.post(
            "/user/register.json",
            json={
                "user": "dave",
                "password": "Dav3",
                "passwordConfirm": "Dav3",
                "mail": "dave@example.com",
            },
        )
        self.assertEqual(rv.status_code, 200)
        self.assertTrue(rv.json["ok"])
        self.assertEqual(rv.json["user"]["name"], "dave")
        with self.client.session_transaction() as sess:
            self.assertEqual(str(User.get(name="dave").id), str(sess["userid"]))

    def test_register_json_rejects_invalid_payload(self):
        rv = self.client.post(
            "/user/register.json",
            json={
                "user": "erin",
                "password": "Er1n",
                "passwordConfirm": "Mismatch",
            },
        )
        self.assertEqual(rv.status_code, 400)
        self.assertFalse(rv.json["ok"])
        self.assertIn("passwords don't match", rv.json["error"])

    def test_register_json_requires_invite_code_when_configured(self):
        with self.app_context():
            from flask import current_app

            current_app.config["WEBAPP"]["registration_invite_code"] = "EMO-APP"

        missing = self.client.post(
            "/user/register.json",
            json={
                "user": "jane",
                "password": "Jane1",
                "passwordConfirm": "Jane1",
            },
        )
        self.assertEqual(missing.status_code, 400)
        self.assertFalse(missing.json["ok"])
        self.assertIn("registration invite code", missing.json["error"])

        invalid = self.client.post(
            "/user/register.json",
            json={
                "user": "jane",
                "password": "Jane1",
                "passwordConfirm": "Jane1",
                "registrationCode": "WRONG",
            },
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(invalid.json["ok"])
        self.assertIn("Invalid registration invite code", invalid.json["error"])

        success = self.client.post(
            "/user/register.json",
            json={
                "user": "jane",
                "password": "Jane1",
                "passwordConfirm": "Jane1",
                "registrationCode": "EMO-APP",
            },
        )
        self.assertEqual(success.status_code, 200)
        self.assertTrue(success.json["ok"])
        self.assertEqual(success.json["user"]["name"], "jane")

    def test_register_disabled_blocks_page_and_json(self):
        with self.app_context():
            from flask import current_app

            current_app.config["WEBAPP"]["allow_user_registration"] = False

        page = self.client.get("/user/register", follow_redirects=True)
        self.assertIn("User registration is disabled", page.data)

        api = self.client.post(
            "/user/register.json",
            json={
                "user": "frank",
                "password": "Frank1",
                "passwordConfirm": "Frank1",
            },
        )
        self.assertEqual(api.status_code, 403)
        self.assertFalse(api.json["ok"])
