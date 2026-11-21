"""Trajectory bus: every state change becomes an event; the raw material of self-evolution."""
class Bus:
    def __init__(self, store):
        self.store = store
        self.subscribers = []

    def subscribe(self, fn):
        self.subscribers.append(fn)

    def emit(self, task_id, kind, **payload):
        self.store.append_traj(task_id, kind, payload)
        for fn in self.subscribers:
            try:
                fn(task_id, kind, payload)
            except Exception:
                pass  # subscribers must never break the task pipeline
