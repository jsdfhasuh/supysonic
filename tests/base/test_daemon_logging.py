import logging
import os
import shutil
import tempfile
import unittest

from supysonic.daemon import setup_logging
from supysonic.daemon import logger as daemon_logger


class DaemonLoggingTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp()
        self._previous_handlers = list(daemon_logger.handlers)
        self._previous_level = daemon_logger.level
        self._previous_propagate = daemon_logger.propagate

        daemon_logger.handlers = []
        daemon_logger.setLevel(logging.NOTSET)
        daemon_logger.propagate = False

    def tearDown(self):
        for handler in list(daemon_logger.handlers):
            handler.close()
        daemon_logger.handlers = self._previous_handlers
        daemon_logger.setLevel(self._previous_level)
        daemon_logger.propagate = self._previous_propagate
        shutil.rmtree(self._tmp_dir)

    def test_info_level_does_not_create_debug_log_file(self):
        log_file = os.path.join(self._tmp_dir, "supysonic-daemon.log")

        setup_logging(
            {
                "log_file": log_file,
                "log_rotate": False,
                "log_level": "INFO",
            }
        )

        daemon_logger.debug("debug hidden")
        daemon_logger.info("info visible")

        with open(log_file, "r", encoding="utf-8") as f:
            log_content = f.read()

        self.assertIn("info visible", log_content)
        self.assertNotIn("debug hidden", log_content)
        self.assertFalse(os.path.exists(os.path.join(self._tmp_dir, "supysonic-daemon.debug.log")))

    def test_debug_level_writes_to_separate_debug_log_file(self):
        log_file = os.path.join(self._tmp_dir, "supysonic-daemon.log")
        debug_log_file = os.path.join(self._tmp_dir, "supysonic-daemon.debug.log")

        setup_logging(
            {
                "log_file": log_file,
                "log_rotate": False,
                "log_level": "DEBUG",
            }
        )

        daemon_logger.debug("debug visible")
        daemon_logger.info("info visible")

        with open(log_file, "r", encoding="utf-8") as f:
            main_log_content = f.read()

        with open(debug_log_file, "r", encoding="utf-8") as f:
            debug_log_content = f.read()

        self.assertIn("info visible", main_log_content)
        self.assertNotIn("debug visible", main_log_content)
        self.assertIn("debug visible", debug_log_content)
        self.assertIn("info visible", debug_log_content)

    def test_repeated_setup_logging_does_not_duplicate_file_output(self):
        log_file = os.path.join(self._tmp_dir, "supysonic-daemon.log")

        config = {
            "log_file": log_file,
            "log_rotate": False,
            "log_level": "INFO",
        }

        setup_logging(config)
        setup_logging(config)

        daemon_logger.info("written once")

        with open(log_file, "r", encoding="utf-8") as f:
            log_lines = [line for line in f.readlines() if "written once" in line]

        self.assertEqual(len(log_lines), 1)
