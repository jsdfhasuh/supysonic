import logging
import os
import shutil
import tempfile
import unittest

from logging.handlers import TimedRotatingFileHandler


class LoggingManagerTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp()
        self.logger_name = "supysonic.test.logging"
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

    def test_configure_web_logging_creates_expected_log_files(self):
        from supysonic.logging_manager import configure_web_logging

        configure_web_logging(
            {
                "log_dir": self._tmp_dir,
                "log_rotate": False,
                "log_level": "INFO",
                "log_backup_count": 7,
            },
            logger_name=self.logger_name,
        )

        file_handlers = [handler for handler in self.base_logger.handlers if isinstance(handler, logging.FileHandler)]
        file_paths = sorted(os.path.basename(handler.baseFilename) for handler in file_handlers)

        self.assertEqual(
            file_paths,
            [
                "access.log",
                "api.log",
                "emo.log",
                "metadata.log",
                "scanner.log",
                "supysonic.log",
                "task.log",
            ],
        )

    def test_configure_web_logging_uses_timed_rotation_with_backup_count(self):
        from supysonic.logging_manager import configure_web_logging

        configure_web_logging(
            {
                "log_dir": self._tmp_dir,
                "log_rotate": True,
                "log_level": "INFO",
                "log_backup_count": 9,
            },
            logger_name=self.logger_name,
        )

        rotating_handlers = [
            handler for handler in self.base_logger.handlers if isinstance(handler, TimedRotatingFileHandler)
        ]

        self.assertEqual(len(rotating_handlers), 7)
        self.assertTrue(all(handler.when == "MIDNIGHT" for handler in rotating_handlers))
        self.assertTrue(all(handler.backupCount == 9 for handler in rotating_handlers))

    def test_repeated_configuration_does_not_duplicate_file_output(self):
        from supysonic.logging_manager import configure_web_logging

        config = {
            "log_dir": self._tmp_dir,
            "log_rotate": False,
            "log_level": "INFO",
            "log_backup_count": 5,
        }

        configure_web_logging(config, logger_name=self.logger_name)
        configure_web_logging(config, logger_name=self.logger_name)

        self.base_logger.info("written once")

        with open(os.path.join(self._tmp_dir, "supysonic.log"), "r", encoding="utf-8") as f:
            log_lines = [line for line in f.readlines() if "written once" in line]

        self.assertEqual(len(log_lines), 1)

    def test_debug_level_creates_separate_web_debug_log(self):
        from supysonic.logging_manager import configure_web_logging

        configure_web_logging(
            {
                "log_dir": self._tmp_dir,
                "log_rotate": False,
                "log_level": "DEBUG",
                "log_backup_count": 7,
            },
            logger_name=self.logger_name,
        )

        self.base_logger.debug("debug only")
        self.base_logger.info("info only")

        with open(os.path.join(self._tmp_dir, "web.debug.log"), "r", encoding="utf-8") as f:
            debug_content = f.read()
        with open(os.path.join(self._tmp_dir, "supysonic.log"), "r", encoding="utf-8") as f:
            summary_content = f.read()

        self.assertIn("debug only", debug_content)
        self.assertIn("info only", debug_content)
        self.assertNotIn("debug only", summary_content)
        self.assertIn("info only", summary_content)

    def test_routes_named_loggers_to_matching_category_files(self):
        from supysonic.logging_manager import configure_web_logging

        configure_web_logging(
            {
                "log_dir": self._tmp_dir,
                "log_rotate": False,
                "log_level": "INFO",
                "log_backup_count": 7,
            },
            logger_name=self.logger_name,
        )

        logging.getLogger(f"{self.logger_name}.TaskManger").info("task event")
        logging.getLogger(f"{self.logger_name}.emo.client").info("emo event")
        logging.getLogger(f"{self.logger_name}.scanner_func.scanner_enrich").info("scanner event")
        logging.getLogger(f"{self.logger_name}.api.browse").info("api event")
        logging.getLogger(f"{self.logger_name}.frontend.metadata").info("metadata event")

        with open(os.path.join(self._tmp_dir, "task.log"), "r", encoding="utf-8") as f:
            task_content = f.read()
        with open(os.path.join(self._tmp_dir, "emo.log"), "r", encoding="utf-8") as f:
            emo_content = f.read()
        with open(os.path.join(self._tmp_dir, "scanner.log"), "r", encoding="utf-8") as f:
            scanner_content = f.read()
        with open(os.path.join(self._tmp_dir, "api.log"), "r", encoding="utf-8") as f:
            api_content = f.read()
        with open(os.path.join(self._tmp_dir, "metadata.log"), "r", encoding="utf-8") as f:
            metadata_content = f.read()
        with open(os.path.join(self._tmp_dir, "supysonic.log"), "r", encoding="utf-8") as f:
            summary_content = f.read()

        self.assertIn("task event", task_content)
        self.assertNotIn("emo event", task_content)
        self.assertIn("emo event", emo_content)
        self.assertNotIn("scanner event", emo_content)
        self.assertIn("scanner event", scanner_content)
        self.assertNotIn("api event", scanner_content)
        self.assertIn("api event", api_content)
        self.assertIn("metadata event", metadata_content)
        self.assertNotIn("metadata event", api_content)
        self.assertIn("task event", summary_content)
        self.assertIn("emo event", summary_content)
        self.assertIn("scanner event", summary_content)
        self.assertIn("api event", summary_content)
        self.assertIn("metadata event", summary_content)

    def test_routes_access_logger_to_access_and_summary_logs(self):
        from supysonic.logging_manager import configure_web_logging

        configure_web_logging(
            {
                "log_dir": self._tmp_dir,
                "log_rotate": False,
                "log_level": "INFO",
                "log_backup_count": 7,
            },
            logger_name=self.logger_name,
        )

        logging.getLogger(f"{self.logger_name}.access").info("[ACCESS:REST] example")

        with open(os.path.join(self._tmp_dir, "access.log"), "r", encoding="utf-8") as f:
            access_content = f.read()
        with open(os.path.join(self._tmp_dir, "supysonic.log"), "r", encoding="utf-8") as f:
            summary_content = f.read()
        with open(os.path.join(self._tmp_dir, "task.log"), "r", encoding="utf-8") as f:
            task_content = f.read()

        self.assertIn("[ACCESS:REST] example", access_content)
        self.assertIn("[ACCESS:REST] example", summary_content)
        self.assertNotIn("[ACCESS:REST] example", task_content)
