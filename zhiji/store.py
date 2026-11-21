"""SQLite DAO. Local-first: tasks / trajectories / confirmations / memories / skills / feedback / meta."""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks(
  id TEXT PRIMARY KEY, skill_id TEXT, skill_version INTEGER, title TEXT, intent TEXT,
  params TEXT, status TEXT, route TEXT, sensitive INTEGER DEFAULT 0, intervention INTEGER DEFAULT 0,
  result TEXT, verdict TEXT, receipt TEXT, cost_tokens INTEGER DEFAULT 0, cost_ms INTEGER DEFAULT 0,
  created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS trajectories(
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, ts REAL, kind TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS confirmations(
  id TEXT PRIMARY KEY, task_id TEXT, action TEXT, preview TEXT, status TEXT DEFAULT 'pending',
  reason TEXT, created_at REAL, resolved_at REAL);
CREATE TABLE IF NOT EXISTS memories(
  id TEXT PRIMARY KEY, kind TEXT, content TEXT, source TEXT, confidence REAL DEFAULT 0.8,
  locked INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS skills(
  id TEXT, version INTEGER, status TEXT DEFAULT 'candidate', contract TEXT, stats TEXT,
  fail_streak INTEGER DEFAULT 0, promoted_at REAL, PRIMARY KEY(id, version));
CREATE TABLE IF NOT EXISTS feedback(
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, signal TEXT, note TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS idx_traj_task ON trajectories(task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
"""

JSON_FIELDS = {
    "tasks": {"params", "result", "verdict", "receipt"},
    "confirmations": {"preview"},
    "skills": {"contract", "stats"},
}


def now() -> float:
    return time.time()


def new_id(prefix: str = "") -> str:
    return (prefix + uuid.uuid4().hex[:12]) if prefix else uuid.uuid4().hex[:12]


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        with self.conn as c:
            c.executescript(SCHEMA)
            c.execute("PRAGMA journal_mode=WAL")

    @property
    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path)
            c.row_factory = sqlite3.Row
            self._local.conn = c
        return c

    def _row(self, table, row):
        if row is None:
            return None
        d = dict(row)
        for f in JSON_FIELDS.get(table, ()):
            if d.get(f) is not None:
                d[f] = json.loads(d[f])
        return d

    def _rows(self, table, rows):
        return [self._row(table, r) for r in rows]

    # ---- tasks ----
    def create_task(self, **kw) -> dict:
        kw.setdefault("id", new_id("t_"))
        kw.setdefault("created_at", now())
        kw["updated_at"] = now()
        for f in JSON_FIELDS["tasks"]:
            if f in kw and not isinstance(kw[f], str):
                kw[f] = json.dumps(kw[f], ensure_ascii=False)
        cols = ", ".join(kw)
        ph = ", ".join("?" for _ in kw)
        self.conn.execute(f"INSERT INTO tasks({cols}) VALUES({ph})", list(kw.values()))
        self.conn.commit()
        return self.get_task(kw["id"])

    def get_task(self, task_id):
        r = self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return self._row("tasks", r)

    def list_tasks(self, status=None, limit=200):
        if status:
            rs = self.conn.execute("SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit)).fetchall()
        else:
            rs = self.conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return self._rows("tasks", rs)

    def update_task(self, task_id, **kw):
        for f in JSON_FIELDS["tasks"]:
            if f in kw and not isinstance(kw[f], str):
                kw[f] = json.dumps(kw[f], ensure_ascii=False)
        kw["updated_at"] = now()
        sets = ", ".join(f"{k}=?" for k in kw)
        self.conn.execute(f"UPDATE tasks SET {sets} WHERE id=?", [*kw.values(), task_id])
        self.conn.commit()
        return self.get_task(task_id)

    # ---- trajectories ----
    def append_traj(self, task_id, kind, payload):
        self.conn.execute("INSERT INTO trajectories(task_id, ts, kind, payload) VALUES(?,?,?,?)",
                          (task_id, now(), kind, json.dumps(payload, ensure_ascii=False)))
        self.conn.commit()

    def traj_for(self, task_id):
        rs = self.conn.execute("SELECT * FROM trajectories WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
        return [{"ts": r["ts"], "kind": r["kind"], "payload": json.loads(r["payload"])} for r in rs]

    # ---- confirmations ----
    def create_confirmation(self, task_id, action, preview):
        cid = new_id("c_")
        self.conn.execute("INSERT INTO confirmations(id, task_id, action, preview, created_at) VALUES(?,?,?,?,?)",
                          (cid, task_id, action, json.dumps(preview, ensure_ascii=False), now()))
        self.conn.commit()
        return self.get_confirmation(cid)

    def get_confirmation(self, cid):
        r = self.conn.execute("SELECT * FROM confirmations WHERE id=?", (cid,)).fetchone()
        return self._row("confirmations", r)

    def list_confirmations(self, status=None):
        if status:
            rs = self.conn.execute("SELECT * FROM confirmations WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rs = self.conn.execute("SELECT * FROM confirmations ORDER BY created_at DESC").fetchall()
        return self._rows("confirmations", rs)

    def resolve_confirmation(self, cid, status, reason=""):
        self.conn.execute("UPDATE confirmations SET status=?, reason=?, resolved_at=? WHERE id=?", (status, reason, now(), cid))
        self.conn.commit()
        return self.get_confirmation(cid)

    # ---- memories ----
    def add_memory(self, kind, content, source="", confidence=0.8, locked=0):
        mid = new_id("m_")
        self.conn.execute("INSERT INTO memories(id, kind, content, source, confidence, locked, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                          (mid, kind, content, source, confidence, locked, now(), now()))
        self.conn.commit()
        return self.get_memory(mid)

    def get_memory(self, mid):
        r = self.conn.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
        return dict(r) if r else None

    def list_memories(self, include_deleted=False):
        q = "SELECT * FROM memories" + ("" if include_deleted else " WHERE deleted=0") + " ORDER BY created_at DESC"
        return [dict(r) for r in self.conn.execute(q).fetchall()]

    def update_memory(self, mid, **kw):
        kw["updated_at"] = now()
        sets = ", ".join(f"{k}=?" for k in kw)
        self.conn.execute(f"UPDATE memories SET {sets} WHERE id=?", [*kw.values(), mid])
        self.conn.commit()
        return self.get_memory(mid)

    def delete_memory(self, mid):
        return self.update_memory(mid, deleted=1)

    # ---- skills ----
    def register_skill(self, contract, status="candidate"):
        sid, ver = contract["id"], contract["version"]
        stats = {"runs": 0, "pass": 0, "fail": 0, "fast": 0, "tokens": 0, "ms": 0, "regression": None}
        self.conn.execute("INSERT OR REPLACE INTO skills(id, version, status, contract, stats) VALUES(?,?,?,?,?)",
                          (sid, ver, status, json.dumps(contract, ensure_ascii=False), json.dumps(stats)))
        self.conn.commit()
        return self.get_skill(sid, ver)

    def get_skill(self, sid, version=None):
        if version is None:
            r = self.conn.execute("SELECT * FROM skills WHERE id=? ORDER BY version DESC LIMIT 1", (sid,)).fetchone()
        else:
            r = self.conn.execute("SELECT * FROM skills WHERE id=? AND version=?", (sid, version)).fetchone()
        return self._row("skills", r)

    def list_skills(self):
        rs = self.conn.execute("SELECT * FROM skills ORDER BY id, version DESC").fetchall()
        out, seen = [], set()
        for r in self._rows("skills", rs):
            if r["id"] not in seen:
                seen.add(r["id"])
                out.append(r)
        return out

    def set_skill_status(self, sid, version, status):
        self.conn.execute("UPDATE skills SET status=?, promoted_at=? WHERE id=? AND version=?", (status, now(), sid, version))
        self.conn.commit()

    def update_skill_stats(self, sid, version, **kw):
        row = self.get_skill(sid, version)
        stats = row["stats"] or {}
        stats.update(kw)
        self.conn.execute("UPDATE skills SET stats=?, fail_streak=? WHERE id=? AND version=?",
                          (json.dumps(stats), stats.get("fail_streak", row["fail_streak"]), sid, version))
        self.conn.commit()

    def bump_fail_streak(self, sid, version, delta):
        self.conn.execute("UPDATE skills SET fail_streak=MAX(0, fail_streak+?) WHERE id=? AND version=?", (delta, sid, version))
        self.conn.commit()
        return self.get_skill(sid, version)["fail_streak"]

    # ---- feedback ----
    def add_feedback(self, task_id, signal, note=""):
        self.conn.execute("INSERT INTO feedback(task_id, signal, note, ts) VALUES(?,?,?,?)", (task_id, signal, note, now()))
        self.conn.commit()

    def feedback_for(self, task_id):
        rs = self.conn.execute("SELECT * FROM feedback WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
        return [dict(r) for r in rs]

    # ---- meta ----
    def get_meta(self, key, default=None):
        r = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default

    def set_meta(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?,?)", (key, json.dumps(value, ensure_ascii=False)))
        self.conn.commit()
