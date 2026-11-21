"""HTTP API + static web. Stdlib-only; the API contract stays frozen when M1 swaps in FastAPI."""
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

WEB_ROOT = Path(__file__).parent.parent / "web"
WEB_DIR = WEB_ROOT / "dist"          # Vue 3 build output (cd web && npm install && npm run build)
LEGACY_PAGE = WEB_ROOT / "legacy.html"  # pre-Vue fallback, kept for reference
MIME = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".woff2": "font/woff2", ".map": "application/json",
}


def make_server(engine, store, host="127.0.0.1", port=8765):
    routes = []

    def route(method, pattern):
        def deco(fn):
            routes.append((method, re.compile(f"^{pattern}$"), fn))
            return fn
        return deco

    @route("GET", r"/api/today")
    def today(m, q, b):
        return 200, engine.today()

    @route("GET", r"/api/tasks")
    def tasks(m, q, b):
        return 200, store.list_tasks(status=q.get("status", [None])[0])

    @route("POST", r"/api/tasks")
    def submit(m, q, b):
        try:
            return 200, engine.submit(b["skill_id"], b.get("params", {}), b.get("title"))
        except KeyError as e:
            return 404, {"error": str(e)}

    @route("GET", r"/api/tasks/([\w-]+)")
    def task_detail(m, q, b):
        t = store.get_task(m.group(1))
        if t is None:
            return 404, {"error": "task not found"}
        return 200, {"task": t, "trajectory": store.traj_for(t["id"]), "feedback": store.feedback_for(t["id"])}

    @route("POST", r"/api/tasks/([\w-]+)/feedback")
    def feedback(m, q, b):
        try:
            return 200, engine.feedback(m.group(1), b.get("signal"), b.get("note", ""))
        except (KeyError, ValueError) as e:
            return 400, {"error": str(e)}

    @route("GET", r"/api/confirmations")
    def confirmations(m, q, b):
        return 200, store.list_confirmations(status=q.get("status", [None])[0])

    @route("POST", r"/api/confirmations/([\w-]+)/resolve")
    def resolve(m, q, b):
        try:
            return 200, engine.resolve_confirmation(m.group(1), bool(b.get("approve")), b.get("reason", ""))
        except KeyError as e:
            return 404, {"error": str(e)}

    @route("GET", r"/api/memories")
    def memories(m, q, b):
        return 200, store.list_memories()

    @route("POST", r"/api/memories")
    def add_memory(m, q, b):
        return 200, store.add_memory(b.get("kind", "profile"), b["content"], b.get("source", "user"), b.get("confidence", 1.0), b.get("locked", 0))

    @route("PATCH", r"/api/memories/([\w-]+)")
    def edit_memory(m, q, b):
        if store.get_memory(m.group(1)) is None:
            return 404, {"error": "memory not found"}
        return 200, store.update_memory(m.group(1), **{k: v for k, v in b.items() if k in ("content", "kind", "confidence", "locked")})

    @route("DELETE", r"/api/memories/([\w-]+)")
    def del_memory(m, q, b):
        return 200, store.delete_memory(m.group(1))

    @route("GET", r"/api/skills")
    def skills(m, q, b):
        return 200, store.list_skills()

    @route("POST", r"/api/skills/([\w-]+)/promote")
    def promote(m, q, b):
        try:
            return 200, engine.promote(m.group(1))
        except KeyError as e:
            return 404, {"error": str(e)}

    @route("GET", r"/api/metrics")
    def metrics(m, q, b):
        return 200, engine.metrics()

    @route("POST", r"/api/consolidate")
    def consolidate(m, q, b):
        from . import memory
        return 200, memory.consolidate(store)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, obj):
            data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _dispatch(self, method):
            parsed = urlparse(self.path)
            path, query = parsed.path, parse_qs(parsed.query)
            body = {}
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                try:
                    body = json.loads(self.rfile.read(length).decode("utf-8-sig"))
                except Exception:
                    return self._send(400, {"error": "invalid json body"})
            if method == "GET" and not path.startswith("/api/"):
                rel = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
                fp = (WEB_DIR / rel).resolve()
                if not str(fp).startswith(str(WEB_DIR.resolve())) or not fp.is_file():
                    fp = LEGACY_PAGE if path in ("/", "/index.html") and LEGACY_PAGE.is_file() else None
                if fp is None:
                    return self._send(404, {"error": "web/dist missing: cd web && npm install && npm run build"})
                data = fp.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", MIME.get(fp.suffix, "application/octet-stream"))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return self.wfile.write(data)
            for m, pat, fn in routes:
                if m != method:
                    continue
                mt = pat.match(path)
                if mt:
                    try:
                        code, obj = fn(mt, query, body)
                    except Exception as e:
                        code, obj = 500, {"error": f"{type(e).__name__}: {e}"}
                    return self._send(code, obj)
            self._send(404, {"error": f"no route: {method} {path}"})

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def do_PATCH(self):
            self._dispatch("PATCH")

        def do_DELETE(self):
            self._dispatch("DELETE")

    return ThreadingHTTPServer((host, port), Handler)
