import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from supysonic import db

from ..testbase import TestConfig


class WebStartupTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.mkdtemp()
        self._db_fd, self._db_path = tempfile.mkstemp()

    def tearDown(self):
        db.release_database()
        shutil.rmtree(self._dir)
        os.close(self._db_fd)
        os.remove(self._db_path)

    def _make_config(self, testing):
        config = TestConfig(False, False)
        config.BASE["database_uri"] = "sqlite:///" + self._db_path
        config.WEBAPP["cache_dir"] = self._dir
        config.WEBAPP["log_dir"] = ""
        if not testing:
            config.TESTING = False
        return config

    def test_submits_review_task_bootstrap_and_maintenance_when_not_testing(self):
        from supysonic.web import create_application
        from supysonic.scanner_func.scanner_review_tasks import runReviewTaskBootstrap

        config = self._make_config(testing=False)
        mock_tm = MagicMock()

        with patch("supysonic.TaskManger.get_task_manager", return_value=mock_tm):
            app = create_application(config)

        self.assertEqual(mock_tm.submit_task.call_count, 1)
        first_args, _ = mock_tm.submit_task.call_args_list[0]

        self.assertEqual(first_args[0], "bootstrap-review-tasks")
        self.assertIs(first_args[1], runReviewTaskBootstrap)

    def test_skips_bootstrap_when_testing(self):
        from supysonic.web import create_application

        config = self._make_config(testing=True)
        mock_tm = MagicMock()

        with patch("supysonic.TaskManger.get_task_manager", return_value=mock_tm):
            app = create_application(config)

        mock_tm.submit_task.assert_not_called()
