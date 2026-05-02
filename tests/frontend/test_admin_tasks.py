import json
import time
import unittest

from supysonic import db
from supysonic.TaskManger import get_task_manager

from .frontendtestbase import FrontendTestBase
from ..testbase import TestConfig


class AdminTasksTestCase(FrontendTestBase):
    def setUp(self):
        TestConfig.WEBAPP = TestConfig.WEBAPP.copy()
        TestConfig.WEBAPP["log_dir"] = ""
        super().setUp()

    def _login_as_admin(self):
        alice = db.User.get(db.User.name == "alice")
        with self.client.session_transaction() as session:
            session["userid"] = str(alice.id)

    def _login_as_normal(self):
        bob = db.User.get(db.User.name == "bob")
        with self.client.session_transaction() as session:
            session["userid"] = str(bob.id)

    def test_admin_can_access_tasks_page(self):
        self._login_as_admin()
        rv = self.client.get("/admin/tasks")
        self.assertEqual(rv.status_code, 200)
        self.assertIn("Background Tasks", rv.data)
        self.assertIn("Auto-refresh every", rv.data)

    def test_admin_tasks_page_shows_empty_state(self):
        self._login_as_admin()
        rv = self.client.get("/admin/tasks")
        self.assertIn("No background tasks recorded", rv.data)

    def test_admin_tasks_page_shows_task_rows(self):
        tm = get_task_manager()
        tm.submit_task("sample-task", lambda: "done")
        # wait briefly for the task to complete
        time.sleep(0.1)

        self._login_as_admin()
        rv = self.client.get("/admin/tasks")
        self.assertIn("sample-task", rv.data)

    def test_admin_can_access_tasks_data_json(self):
        self._login_as_admin()
        rv = self.client.get("/admin/tasks/data")
        self.assertEqual(rv.status_code, 200)
        self.assertTrue("application/json" in rv.mimetype)

        data = rv.json
        self.assertIn("tasks", data)
        self.assertIn("summary", data)
        self.assertIn("total", data["summary"])
        self.assertIn("pending", data["summary"])
        self.assertIn("completed", data["summary"])
        self.assertIn("failed", data["summary"])
        self.assertEqual(data["summary"]["total"], len(data["tasks"]))

    def test_admin_tasks_data_returns_tasks_with_expected_keys(self):
        tm = get_task_manager()
        tm.submit_task("api-task", lambda: "ok")

        self._login_as_admin()
        rv = self.client.get("/admin/tasks/data")

        tasks = rv.json["tasks"]
        self.assertGreaterEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t["task_id"], "api-task")
        self.assertIn(t["status"], ("pending", "completed"))
        self.assertIn("timestamp", t)
        self.assertIn("result", t)
        self.assertIn("error", t)

    def test_non_admin_redirected_from_tasks_page(self):
        self._login_as_normal()
        rv = self.client.get("/admin/tasks", follow_redirects=False)
        self.assertEqual(rv.status_code, 302)
        self.assertIn("/", rv.location)

    def test_non_admin_redirected_from_tasks_data(self):
        self._login_as_normal()
        rv = self.client.get("/admin/tasks/data", follow_redirects=False)
        self.assertEqual(rv.status_code, 302)
        self.assertIn("/", rv.location)

    def test_tasks_page_summary_cards_present(self):
        self._login_as_admin()
        rv = self.client.get("/admin/tasks")
        self.assertIn("summary-pending", rv.data)
        self.assertIn("summary-completed", rv.data)
        self.assertIn("summary-failed", rv.data)
        self.assertIn("summary-total", rv.data)

    def test_tasks_page_contains_polling_script(self):
        self._login_as_admin()
        rv = self.client.get("/admin/tasks")
        self.assertIn("admin/tasks/data", rv.data)
        self.assertIn("setInterval", rv.data)
        self.assertIn("fetch(dataUrl)", rv.data)
        self.assertIn('"refresh-now"', rv.data)


if __name__ == "__main__":
    unittest.main()
