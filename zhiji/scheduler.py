"""Minimal scheduler thread: nightly memory consolidation at 02:00 local time."""
import threading
import time
from datetime import datetime, timedelta

from . import memory


class Scheduler:
    def __init__(self, store, hour=2):
        self.store = store
        self.hour = hour
        self._stop = threading.Event()
        self._thread = None

    def _next_run(self):
        n = datetime.now()
        nxt = n.replace(hour=self.hour, minute=0, second=0, microsecond=0)
        if nxt <= n:
            nxt += timedelta(days=1)
        return nxt.timestamp()

    def _loop(self):
        while not self._stop.is_set():
            wait = max(1.0, self._next_run() - time.time())
            if self._stop.wait(min(wait, 60.0)):
                break
            if time.time() >= self._next_run() - 1:
                try:
                    memory.consolidate(self.store)
                except Exception:
                    pass

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True, name="zhiji-scheduler")
        self._thread.start()

    def stop(self):
        self._stop.set()
