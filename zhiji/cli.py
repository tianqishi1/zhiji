"""CLI: init / seed / run / serve / consolidate / promote / metrics."""
import argparse
import json
import sys
from pathlib import Path

from .bus import Bus
from .engine import Engine
from .store import Store
from . import memory

ROOT = Path(__file__).parent.parent
SKILLS = ROOT / "skills"
DATA = ROOT / "data"


def build(db=None):
    store = Store(db or DATA / "zhiji.db")
    bus = Bus(store)
    engine = Engine(store, bus, SKILLS, DATA)
    return store, bus, engine


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(prog="zhiji")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("seed")
    p_run = sub.add_parser("run")
    p_run.add_argument("skill")
    p_run.add_argument("--params", default="{}")
    p_run.add_argument("--title", default=None)
    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--host", default="127.0.0.1")
    sub.add_parser("consolidate")
    p_prom = sub.add_parser("promote")
    p_prom.add_argument("skill")
    sub.add_parser("metrics")
    args = ap.parse_args(argv)

    store, bus, engine = build()

    if args.cmd == "init":
        report = engine.init_skills()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.cmd == "seed":
        engine.init_skills()
        demos = [
            ("daily-report", {"topics": ["agent", "personal"]}, "晨报：Personal Agent 赛道动态"),
            ("price-watch", {"item": "降噪耳机 WH-1000XM6", "target_price": 1500}, "盯价：XM6 目标 ¥1500"),
            ("price-watch", {"item": "机械键盘 Keychron K3", "target_price": 300}, "盯价：K3 目标 ¥300（未达标示例）"),
            ("price-watch", {"item": "降噪耳机 WH-1000XM6", "target_price": 1500, "auto_buy": True}, "盯价+自动下单（需确认）"),
            ("invoice-reconcile", {"demo": True}, "本月账单对账"),
        ]
        for sid, params, title in demos:
            t = engine.submit(sid, params, title)
            print(f"[{t['status']:>22}] {t['title']}  verdict={'-' if not t.get('verdict') else t['verdict']['pass']}")
        print("\n演示就绪：python -m zhiji.cli serve  →  http://127.0.0.1:8765")
    elif args.cmd == "run":
        engine.init_skills()
        t = engine.submit(args.skill, json.loads(args.params), args.title)
        print(json.dumps(t, ensure_ascii=False, indent=2))
    elif args.cmd == "serve":
        from .api import make_server
        from .scheduler import Scheduler
        engine.init_skills()
        sched = Scheduler(store)
        sched.start()
        srv = make_server(engine, store, args.host, args.port)
        print(f"知几 M0 serving at http://{args.host}:{args.port}  (Ctrl+C to stop)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            sched.stop()
    elif args.cmd == "consolidate":
        print(json.dumps(memory.consolidate(store), ensure_ascii=False, indent=2))
    elif args.cmd == "promote":
        print(json.dumps(engine.promote(args.skill), ensure_ascii=False, indent=2))
    elif args.cmd == "metrics":
        print(json.dumps(engine.metrics(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
