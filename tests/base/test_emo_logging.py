import os
import shutil
import tempfile
import unittest

from supysonic.db import release_database
from supysonic.emo.ws import socketio
from supysonic.managers.user import UserManager
from supysonic.web import create_application

from tests.testbase import TestConfig


class EmoLoggingTestCase(unittest.TestCase):
    def setUp(self):
        self._db = tempfile.mkstemp()
        self._dir = tempfile.mkdtemp()
        self.config = TestConfig(False, False)
        self.config.BASE["database_uri"] = "sqlite:///" + self._db[1]
        self.config.WEBAPP["cache_dir"] = self._dir
        self.config.WEBAPP["log_dir"] = self._dir
        self.config.WEBAPP["log_level"] = "INFO"
        self.config.WEBAPP["mount_emosonic"] = True
        self.app = create_application(self.config)
        self.http_client = self.app.test_client()
        UserManager.add("alice", "Alic3", admin=True)
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.disconnect(namespace="/emo")
        release_database()
        shutil.rmtree(self._dir)
        os.close(self._db[0])
        os.remove(self._db[1])

    def test_logs_auth_login_and_device_register_to_emo_log(self):
        client = socketio.test_client(self.app, namespace="/emo", flask_test_client=self.http_client)
        self.clients.append(client)

        client.emit(
            "message",
            {
                "type": "auth",
                "action": "auth.login",
                "requestId": "auth-1",
                "payload": {"u": "alice", "p": "Alic3"},
            },
            namespace="/emo",
        )
        client.get_received("/emo")

        client.emit(
            "message",
            {
                "type": "device",
                "action": "device.register",
                "requestId": "register-1",
                "payload": {
                    "clientId": "player-1",
                    "deviceName": "player-1",
                    "roles": ["player"],
                    "sessionId": "sess-1",
                },
            },
            namespace="/emo",
        )
        client.get_received("/emo")

        with open(os.path.join(self._dir, "emo.log"), "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("emo auth login succeeded user=alice", content)
        self.assertIn("emo device registered user=alice client_id=player-1 session_id=sess-1", content)
