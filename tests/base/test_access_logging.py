import logging
import os
import shutil
import tempfile
import unittest

from flask import Flask, send_file

from supysonic.db import release_database
from supysonic.emo.ws import socketio
from supysonic.managers.user import UserManager
from supysonic.web import create_application

from tests.testbase import TestConfig


class AccessLoggingTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp()
        self.logger_name = "supysonic.test.access"
        self.base_logger = logging.getLogger(self.logger_name)
        self.previous_handlers = list(self.base_logger.handlers)
        self.previous_level = self.base_logger.level
        self.previous_propagate = self.base_logger.propagate
        self.base_logger.handlers = []
        self.base_logger.setLevel(logging.NOTSET)
        self.base_logger.propagate = False

    def tearDown(self):
        for handler in list(self.base_logger.handlers):
            handler.close()
        self.base_logger.handlers = self.previous_handlers
        self.base_logger.setLevel(self.previous_level)
        self.base_logger.propagate = self.previous_propagate
        shutil.rmtree(self._tmp_dir)

    def _create_app(self):
        from supysonic.logging_manager import configure_web_logging, register_access_logging

        file_path = os.path.join(self._tmp_dir, "sample.bin")
        with open(file_path, "wb") as f:
            f.write(b"sample-bytes")

        configure_web_logging(
            {
                "log_dir": self._tmp_dir,
                "log_rotate": False,
                "log_level": "INFO",
                "log_backup_count": 7,
            },
            logger_name=self.logger_name,
        )

        app = Flask(__name__)
        app.testing = True

        @app.route("/rest/ping")
        def rest_ping():
            return "ok"

        @app.route("/page")
        def page():
            return "page"

        @app.route("/download")
        def download():
            return send_file(file_path, conditional=True)

        register_access_logging(app, logger_name=self.logger_name)
        return app

    def test_logs_rest_requests_to_access_and_summary_logs(self):
        app = self._create_app()
        client = app.test_client()

        response = client.get("/rest/ping?u=root&t=abc&s=def")
        request_id = response.headers.get("X-Request-ID")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(request_id)
        with open(os.path.join(self._tmp_dir, "access.log"), "r", encoding="utf-8") as f:
            access_content = f.read()
        with open(os.path.join(self._tmp_dir, "supysonic.log"), "r", encoding="utf-8") as f:
            summary_content = f.read()

        self.assertIn("access event=request", access_content)
        self.assertIn("type=REST", access_content)
        self.assertIn("path=/rest/ping", access_content)
        self.assertIn('query="u=root&t=***&s=***"', access_content)
        self.assertNotIn("t=abc", access_content)
        self.assertNotIn("s=def", access_content)
        self.assertIn("status=200", access_content)
        self.assertIn("bytes=2", access_content)
        self.assertIn("duration=", access_content)
        self.assertIn(f"request_id={request_id}", access_content)
        self.assertIn("access event=request", summary_content)
        self.assertIn(f"request_id={request_id}", summary_content)

    def test_redacts_plain_password_query_parameter(self):
        app = self._create_app()
        client = app.test_client()

        response = client.get("/rest/ping?u=alice&p=secret&c=test-client")

        self.assertEqual(response.status_code, 200)
        with open(os.path.join(self._tmp_dir, "access.log"), "r", encoding="utf-8") as f:
            access_content = f.read()

        self.assertIn('query="u=alice&p=***&c=test-client"', access_content)
        self.assertNotIn("p=secret", access_content)

    def test_preserves_incoming_request_id(self):
        app = self._create_app()
        client = app.test_client()

        response = client.get("/rest/ping", headers={"X-Request-ID": "client-req-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Request-ID"), "client-req-1")

        with open(os.path.join(self._tmp_dir, "access.log"), "r", encoding="utf-8") as f:
            access_content = f.read()

        self.assertIn("request_id=client-req-1", access_content)

    def test_sanitizes_invalid_incoming_request_id(self):
        app = self._create_app()
        client = app.test_client()

        response = client.get("/rest/ping", headers={"X-Request-ID": " bad req/id "})
        request_id = response.headers.get("X-Request-ID")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(request_id)
        self.assertEqual(request_id, "bad-req-id")

        with open(os.path.join(self._tmp_dir, "access.log"), "r", encoding="utf-8") as f:
            access_content = f.read()

        self.assertIn(f"request_id={request_id}", access_content)

    def test_logs_web_requests_as_access_web(self):
        app = self._create_app()
        client = app.test_client()

        response = client.get("/page?tab=albums")

        self.assertEqual(response.status_code, 200)
        with open(os.path.join(self._tmp_dir, "access.log"), "r", encoding="utf-8") as f:
            access_content = f.read()

        self.assertIn("access event=request", access_content)
        self.assertIn("type=WEB", access_content)
        self.assertIn("path=/page", access_content)
        self.assertIn('query="tab=albums"', access_content)
        self.assertIn("status=200", access_content)

    def test_logs_send_file_requests_without_breaking_direct_passthrough(self):
        app = self._create_app()
        client = app.test_client()

        response = client.get("/download")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"sample-bytes")
        finally:
            response.close()

        with open(os.path.join(self._tmp_dir, "access.log"), "r", encoding="utf-8") as f:
            access_content = f.read()

        self.assertIn("access event=request", access_content)
        self.assertIn("path=/download", access_content)
        self.assertIn("status=200", access_content)


class SocketAccessLoggingTestCase(unittest.TestCase):
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

    def tearDown(self):
        release_database()
        shutil.rmtree(self._dir)
        os.close(self._db[0])
        os.remove(self._db[1])

    def test_logs_socket_connect_and_disconnect_summary(self):
        client = socketio.test_client(self.app, namespace="/emo", flask_test_client=self.http_client)
        client.disconnect(namespace="/emo")

        with open(os.path.join(self._dir, "access.log"), "r", encoding="utf-8") as f:
            access_content = f.read()

        self.assertIn("access event=socket", access_content)
        self.assertIn("type=SOCKET", access_content)
        self.assertIn("socket_event=connect", access_content)
        self.assertIn("socket_event=disconnect", access_content)
