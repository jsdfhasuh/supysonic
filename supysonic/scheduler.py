import logging

from dataclasses import dataclass
from threading import Event, Lock, Thread
from typing import Callable

from .logging_utils import format_log_event

logger = logging.getLogger(__name__)


@dataclass
class _ScheduledJob:
    name: str
    func: Callable[[], object]
    interval: int
    run_immediately: bool = True
    enabled: bool = True
    initial_delay: int | None = None
    thread: Thread | None = None


class IntervalScheduler:
    def __init__(self):
        self._jobs: dict[str, _ScheduledJob] = {}
        self._lock = Lock()
        self._stop_event = Event()
        self._started = False

    def register(
        self,
        name: str,
        func: Callable[[], object],
        interval: int,
        *,
        run_immediately: bool = True,
        enabled: bool = True,
        initial_delay: int | None = None,
    ) -> None:
        job = _ScheduledJob(
            name=name,
            func=func,
            interval=max(1, int(interval)),
            run_immediately=run_immediately,
            enabled=enabled,
            initial_delay=None if initial_delay is None else max(0, int(initial_delay)),
        )
        with self._lock:
            self._jobs[name] = job
            should_start = self._started and enabled

        if should_start:
            self._start_job(job)

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            jobs = [job for job in self._jobs.values() if job.enabled]

        for job in jobs:
            self._start_job(job)

    def stop(self) -> None:
        self._stop_event.set()

    def join(self, timeout: float | None = None) -> None:
        with self._lock:
            threads = [job.thread for job in self._jobs.values() if job.thread is not None]

        for thread in threads:
            thread.join(timeout=timeout)

    def list_jobs(self) -> list[dict[str, object]]:
        with self._lock:
            jobs = list(self._jobs.values())

        return [
            {
                "name": job.name,
                "interval": job.interval,
                "enabled": job.enabled,
                "run_immediately": job.run_immediately,
                "initial_delay": job.initial_delay,
                "running": bool(job.thread and job.thread.is_alive()),
            }
            for job in jobs
        ]

    def _start_job(self, job: _ScheduledJob) -> None:
        with self._lock:
            if job.thread is not None and job.thread.is_alive():
                return
            job.thread = Thread(target=self._run_job, args=(job,), daemon=True)
            job.thread.start()

    def _run_job(self, job: _ScheduledJob) -> None:
        delay = 0 if job.run_immediately else job.initial_delay
        if delay is None:
            delay = job.interval

        while not self._stop_event.wait(delay):
            try:
                job.func()
            except Exception as exc:
                logger.exception(
                    format_log_event(
                        "scheduler",
                        "job_failed",
                        job=job.name,
                        error_type=exc.__class__.__name__,
                    )
                )
            delay = job.interval
