import logging
import os
import shutil
import tempfile
import time
import unittest

from supysonic.TaskManger import TaskManager
from supysonic.logging_manager import configure_web_logging


class TaskManagerListResultsTestCase(unittest.TestCase):
    def setUp(self):
        self.tm = TaskManager(max_workers=1)
        # wait for worker thread to start
        time.sleep(0.05)

    def tearDown(self):
        self.tm.shutdown()

    def test_empty_returns_empty_list(self):
        results = self.tm.list_task_results()
        self.assertEqual(results, [])

    def test_returns_all_submitted_tasks(self):
        self.tm.submit_task("t1", lambda: "ok1")
        self.tm.submit_task("t2", lambda: "ok2")

        results = self.tm.list_task_results()
        task_ids = {r["task_id"] for r in results}

        self.assertEqual(len(results), 2)
        self.assertIn("t1", task_ids)
        self.assertIn("t2", task_ids)
        for r in results:
            self.assertIn("status", r)
            self.assertIn("timestamp", r)
            self.assertIn("result", r)
            self.assertIn("error", r)

    def test_sorts_by_timestamp_desc(self):
        self.tm.submit_task("older", lambda: "a")
        time.sleep(0.02)
        self.tm.submit_task("newer", lambda: "b")

        results = self.tm.list_task_results()
        self.assertEqual(results[0]["task_id"], "newer")
        self.assertEqual(results[1]["task_id"], "older")

    def test_result_contains_snapshot_not_live_reference(self):
        self.tm.submit_task("mutable", lambda: "orig")

        results = self.tm.list_task_results()
        row = results[0]

        row["status"] = "modified"
        del row["task_id"]

        results2 = self.tm.list_task_results()
        self.assertEqual(results2[0]["status"], "pending")
        self.assertIn("task_id", results2[0])


class TaskManagerLoggingTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp()
        self.logger = logging.getLogger("supysonic")
        self._previous_handlers = list(self.logger.handlers)
        self._previous_level = self.logger.level
        self._previous_propagate = self.logger.propagate
        self.logger.handlers = []
        self.logger.setLevel(logging.NOTSET)
        self.logger.propagate = False
        configure_web_logging(
            {
                "log_dir": self._tmp_dir,
                "log_rotate": False,
                "log_level": "INFO",
                "log_backup_count": 7,
            }
        )
        self.tm = TaskManager(max_workers=1)
        time.sleep(0.05)

    def tearDown(self):
        self.tm.shutdown()
        for handler in list(self.logger.handlers):
            handler.close()
        self.logger.handlers = self._previous_handlers
        self.logger.setLevel(self._previous_level)
        self.logger.propagate = self._previous_propagate
        shutil.rmtree(self._tmp_dir)

    def _wait_for_status(self, task_id, expected_status):
        deadline = time.time() + 2
        while time.time() < deadline:
            result = self.tm.get_task_result(task_id)
            if result and result.get("status") == expected_status:
                return result
            time.sleep(0.01)
        self.fail(f"task {task_id} did not reach status {expected_status}")

    def test_logs_task_start_and_completion_duration(self):
        task_id = self.tm.submit_task("task-ok", lambda: "ok")

        self._wait_for_status(task_id, "completed")

        with open(os.path.join(self._tmp_dir, "task.log"), "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Submitted task task-ok to the queue", content)
        self.assertIn("Task task-ok started", content)
        self.assertIn("Task task-ok completed successfully", content)
        self.assertIn("duration=", content)

    def test_logs_task_failure_with_error_and_duration(self):
        def raise_error():
            raise ValueError("boom")

        task_id = self.tm.submit_task("task-fail", raise_error)

        self._wait_for_status(task_id, "failed")

        with open(os.path.join(self._tmp_dir, "task.log"), "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Task task-fail started", content)
        self.assertIn("Task task-fail failed", content)
        self.assertIn("error=boom", content)
        self.assertIn("duration=", content)
