import os
import shutil
import tempfile
import unittest

from unittest.mock import MagicMock, patch

from supysonic import db
from supysonic.config import DefaultConfig

from ..testbase import TestConfig


class WebLoggingConfigTestCase(unittest.TestCase):
    def test_default_webapp_config_includes_log_dir_and_backup_count(self):
        self.assertIn("log_dir", DefaultConfig.WEBAPP)
        self.assertIn("log_backup_count", DefaultConfig.WEBAPP)


class WebLoggingSetupTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.mkdtemp()
        self._db_fd, self._db_path = tempfile.mkstemp()

    def tearDown(self):
        try:
            db.release_database()
        except AttributeError:
            pass
        shutil.rmtree(self._dir)
        os.close(self._db_fd)
        os.remove(self._db_path)

    def _make_config(self):
        config = TestConfig(False, False)
        config.BASE["database_uri"] = "sqlite:///" + self._db_path
        config.WEBAPP["cache_dir"] = self._dir
        config.WEBAPP["log_dir"] = self._dir
        config.WEBAPP["log_file"] = ""
        config.WEBAPP["log_backup_count"] = 7
        return config

    def test_create_application_calls_configure_web_logging_with_log_dir(self):
        from supysonic.web import create_application

        config = self._make_config()
        mock_tm = MagicMock()

        with patch("supysonic.web.configure_web_logging", create=True) as configure_logging, patch(
            "supysonic.TaskManger.get_task_manager",
            return_value=mock_tm,
        ):
            create_application(config)

        configure_logging.assert_called_once()
        called_config = configure_logging.call_args[0][0]
        self.assertEqual(called_config["log_dir"], self._dir)
        self.assertEqual(called_config["log_backup_count"], 7)

    def test_create_application_derives_log_dir_from_legacy_log_file(self):
        from supysonic.web import create_application

        config = self._make_config()
        config.WEBAPP.pop("log_dir", None)
        config.WEBAPP["log_file"] = os.path.join(self._dir, "legacy.log")
        mock_tm = MagicMock()

        with patch("supysonic.web.configure_web_logging", create=True) as configure_logging, patch(
            "supysonic.TaskManger.get_task_manager",
            return_value=mock_tm,
        ):
            create_application(config)

        configure_logging.assert_called_once()
        called_config = configure_logging.call_args[0][0]
        self.assertEqual(called_config["log_dir"], self._dir)

    def test_create_application_registers_access_logging(self):
        from supysonic.web import create_application

        config = self._make_config()
        mock_tm = MagicMock()

        with patch("supysonic.web.configure_web_logging", create=True), patch(
            "supysonic.web.register_access_logging",
            create=True,
        ) as register_access_logging, patch(
            "supysonic.TaskManger.get_task_manager",
            return_value=mock_tm,
        ):
            create_application(config)

        register_access_logging.assert_called_once()
