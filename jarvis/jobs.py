"""Background jobs: long renders, simulations and exports.

A job runs on its own thread so the conversation can carry on. When it
finishes, Jarvis announces it, and the result shows up in Jarvis's system
prompt so it can answer questions about it.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
import traceback
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)


@dataclass
class Job:
    name: str
    status: str = "running"  # running, done, failed
    result: str = ""
    started: dt.datetime = field(default_factory=dt.datetime.now)
    finished: dt.datetime | None = None


class JobManager:
    def __init__(self, announce: Callable[[str], None]) -> None:
        self.announce = announce
        self.jobs: list[Job] = []
        self._lock = threading.Lock()

    def start(self, name: str, fn: Callable[[], tuple[bool, str]],
              done_message: Callable[[Job], str] | None = None) -> Job:
        """Run ``fn`` in the background. It returns (success, result text)."""
        job = Job(name)
        with self._lock:
            self.jobs.append(job)

        def work() -> None:
            try:
                ok, result = fn()
            except Exception as exc:  # noqa: BLE001 - report instead of dying silently
                log.debug(traceback.format_exc())
                ok, result = False, f"{type(exc).__name__}: {exc}"
            job.status = "done" if ok else "failed"
            job.result = result
            job.finished = dt.datetime.now()
            if done_message:
                message = done_message(job)
            elif ok:
                message = f"The {name} job is finished."
            else:
                message = f"The {name} job failed. {result.splitlines()[0] if result else ''}"
            self.announce(message)

        threading.Thread(target=work, name=f"job:{name}", daemon=True).start()
        return job

    def watch_process(self, name: str, pid: int, output: str) -> Job:
        """Announce when an outside process (e.g. a Blender render) exits."""
        def wait() -> tuple[bool, str]:
            import psutil

            try:
                psutil.Process(pid).wait()
            except psutil.NoSuchProcess:
                pass
            return True, f"Output: {output}"

        return self.start(name, wait, lambda job: f"The {name} is finished. It's saved at {output}.")

    def summary(self, limit: int = 5) -> str:
        with self._lock:
            recent = self.jobs[-limit:]
        lines = []
        for job in recent:
            when = job.started.strftime("%H:%M")
            detail = job.result.splitlines()[0][:200] if job.result else ""
            lines.append(f"- {job.name} (started {when}): {job.status}" + (f" - {detail}" if detail else ""))
        return "\n".join(lines)
