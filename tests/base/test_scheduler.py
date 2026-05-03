import time
import unittest

from threading import Event

from supysonic.scheduler import IntervalScheduler


class IntervalSchedulerTestCase(unittest.TestCase):
    def test_runs_job_immediately_and_repeatedly(self):
        scheduler = IntervalScheduler()
        calls = []
        done = Event()

        def runJob():
            calls.append(time.monotonic())
            if len(calls) >= 2:
                done.set()

        scheduler.register("job", runJob, 1, initial_delay=5)
        scheduler.start()

        try:
            self.assertTrue(done.wait(2))
            self.assertEqual(len(calls), 2)
        finally:
            scheduler.stop()
            scheduler.join(timeout=1)

    def test_disabled_job_does_not_run(self):
        scheduler = IntervalScheduler()
        ran = Event()

        scheduler.register("job", lambda: ran.set(), 1, enabled=False)
        scheduler.start()

        try:
            self.assertFalse(ran.wait(0.2))
        finally:
            scheduler.stop()
            scheduler.join(timeout=1)

    def test_list_jobs_reports_running_state(self):
        scheduler = IntervalScheduler()
        started = Event()
        release = Event()

        def runJob():
            started.set()
            release.wait(1)

        scheduler.register("job", runJob, 60)
        scheduler.start()

        try:
            self.assertTrue(started.wait(1))
            jobs = scheduler.list_jobs()
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["name"], "job")
            self.assertTrue(jobs[0]["running"])
            self.assertTrue(jobs[0]["run_immediately"])
            self.assertEqual(jobs[0]["interval"], 60)
        finally:
            release.set()
            scheduler.stop()
            scheduler.join(timeout=1)
