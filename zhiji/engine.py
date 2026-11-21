"""Task engine: state machine + confirmation gate + verification receipt + metrics.

Every run emits a full trajectory; every verdict is a reward label for self-evolution.
"""
import time

from . import replay
from .connectors import REGISTRY, COMMIT_REGISTRY, ConnectorUnavailable
from .contracts import load_skills, validate, ContractError
from .evaluators import run_checks, compose_verdict, JudgeAdapter
from .router import resolve_route, run_route, VisionNotConfigured
from .store import now

TERMINAL = ("delivered", "failed", "rejected")
DEMOTION_THRESHOLD = 2


class Engine:
    def __init__(self, store, bus, skills_dir, data_dir, judge=None):
        self.store = store
        self.bus = bus
        self.skills_dir = skills_dir
        self.data_dir = data_dir
        self.judge = judge or JudgeAdapter()

    # ---------- skill lifecycle ----------
    def init_skills(self):
        report = []
        for contract in load_skills(self.skills_dir):
            validate(contract, REGISTRY.keys())
            existing = self.store.get_skill(contract["id"], contract["version"])
            if existing is None:
                self.store.register_skill(contract)
            reg = replay.run_regression(contract, self.skills_dir, self.data_dir)
            self.store.update_skill_stats(contract["id"], contract["version"], regression=reg)
            if reg["pass"]:
                self.store.set_skill_status(contract["id"], contract["version"], "active")
                report.append({"id": contract["id"], "status": "active", "cases": reg["total"]})
            else:
                report.append({"id": contract["id"], "status": "candidate", "reason": reg.get("reason") or reg["failed"]})
        return report

    def promote(self, skill_id):
        row = self.store.get_skill(skill_id)
        if row is None:
            raise KeyError(skill_id)
        reg = replay.run_regression(row["contract"], self.skills_dir, self.data_dir)
        self.store.update_skill_stats(skill_id, row["version"], regression=reg)
        if reg["pass"]:
            self.store.set_skill_status(skill_id, row["version"], "active")
            self.store.bump_fail_streak(skill_id, row["version"], -99)
        return {"id": skill_id, "promoted": reg["pass"], "regression": reg}

    # ---------- task lifecycle ----------
    def submit(self, skill_id, params, title=None):
        row = self.store.get_skill(skill_id)
        if row is None:
            raise KeyError(f"unknown skill: {skill_id}")
        contract = row["contract"]
        task = self.store.create_task(
            skill_id=skill_id, skill_version=row["version"],
            title=title or f"{contract['title']}", intent=json_intent(params),
            params=params, status="queued", route=None,
            cost_tokens=0, cost_ms=0,
        )
        self.bus.emit(task["id"], "intent", skill=skill_id, params=params)
        return self._advance(task["id"])

    def _advance(self, task_id):
        task = self.store.get_task(task_id)
        row = self.store.get_skill(task["skill_id"], task["skill_version"])
        contract = row["contract"]
        self.store.update_task(task_id, status="planning")
        self.bus.emit(task_id, "plan", route_preference=contract["executor"]["route"],
                      sensitive_actions=contract["executor"]["sensitive_actions"])

        route = resolve_route(row, self.data_dir)
        self.store.update_task(task_id, status="executing", route=route)
        t0 = time.time()
        try:
            out = run_route(route, row, task["params"], {"store": self.store}, self.data_dir)
        except ConnectorUnavailable as e:
            self.bus.emit(task_id, "step", name="connector-unavailable", error=str(e))
            try:
                route = "replay"
                out = run_route(route, row, task["params"], {}, self.data_dir)
            except (FileNotFoundError, VisionNotConfigured):
                return self._fail_router(task_id, str(e))
        except VisionNotConfigured as e:
            return self._fail_router(task_id, str(e))
        wall_ms = int((time.time() - t0) * 1000)

        steps = out.get("steps", [])
        tokens = sum(s.get("tokens", 0) for s in steps)
        self.store.update_task(task_id, result=out["result"], route=route,
                               cost_tokens=tokens, cost_ms=wall_ms)
        for s in steps:
            self.bus.emit(task_id, "step", **s)
        self.bus.emit(task_id, "artifact", artifacts=out.get("artifacts", []))

        pending = out.get("pending_action")
        if pending and pending["type"] in contract["executor"]["sensitive_actions"]:
            conf = self.store.create_confirmation(task_id, pending["type"], pending["preview"])
            self.store.update_task(task_id, status="awaiting_confirmation", sensitive=1, intervention=1)
            self.bus.emit(task_id, "confirmation", confirmation_id=conf["id"], action=pending["type"], preview=pending["preview"])
            return self.store.get_task(task_id)

        return self._finalize(task_id, out.get("artifacts", []))

    def _fail_router(self, task_id, reason):
        verdict = {"pass": False, "decided_by": "router", "reason": reason, "checks": [],
                   "judge": {"status": "abstain"}, "user_signal": None}
        task = self.store.get_task(task_id)
        receipt = self._receipt(task, verdict, [])
        self.store.update_task(task_id, status="failed", verdict=verdict, receipt=receipt)
        self.bus.emit(task_id, "verdict", **verdict)
        self.bus.emit(task_id, "status", status="failed", reason=reason)
        return self.store.get_task(task_id)

    def _finalize(self, task_id, artifacts):
        task = self.store.get_task(task_id)
        row = self.store.get_skill(task["skill_id"], task["skill_version"])
        contract = row["contract"]
        self.store.update_task(task_id, status="evaluating")
        ctx = {"result": task["result"] or {}, "params": task["params"] or {}, "now": now(), "artifacts": artifacts}
        checks = run_checks(contract["evaluator"]["outcome_checks"], ctx)
        jr = None
        lj = contract["evaluator"].get("llm_judge", {})
        if lj.get("enabled"):
            jr = self.judge.judge(lj.get("rubric", ""), task, lj.get("sample_rate", 0.1))
        verdict = compose_verdict(checks, jr)
        receipt = self._receipt(task, verdict, artifacts)
        status = "delivered" if verdict["pass"] else "failed"
        self.store.update_task(task_id, status=status, verdict=verdict, receipt=receipt)
        self.bus.emit(task_id, "verdict", **verdict)
        self.bus.emit(task_id, "status", status=status)

        # skill stats + S2 flywheel
        stats = row["stats"] or {}
        fast = 1 if task["route"] in ("connector", "replay") else 0
        self.store.update_skill_stats(task["skill_id"], task["skill_version"],
                                      runs=stats.get("runs", 0) + 1,
                                      **{"pass": stats.get("pass", 0) + (1 if verdict["pass"] else 0)},
                                      fail=stats.get("fail", 0) + (0 if verdict["pass"] else 1),
                                      fast=stats.get("fast", 0) + fast,
                                      tokens=stats.get("tokens", 0) + task["cost_tokens"],
                                      ms=stats.get("ms", 0) + task["cost_ms"])
        if verdict["pass"]:
            self.store.bump_fail_streak(task["skill_id"], task["skill_version"], -99)
            replay.record_case(task["skill_id"], self.data_dir, task["params"], task["result"], True)
        else:
            streak = self.store.bump_fail_streak(task["skill_id"], task["skill_version"], 1)
            replay.record_case(task["skill_id"], self.data_dir, task["params"], task["result"], False)
            if streak >= DEMOTION_THRESHOLD:
                self.store.set_skill_status(task["skill_id"], task["skill_version"], "demoted")
                self.bus.emit(task_id, "skill_demoted", skill=task["skill_id"], streak=streak)
        return self.store.get_task(task_id)

    def _receipt(self, task, verdict, artifacts):
        return {"task_id": task["id"], "skill": {"id": task["skill_id"], "version": task["skill_version"]},
                "route": task["route"], "verdict": verdict,
                "evidence": {"checks": verdict.get("checks", []), "artifacts": artifacts},
                "cost": {"tokens": task["cost_tokens"], "ms": task["cost_ms"]},
                "generated_at": now()}

    # ---------- confirmation gate ----------
    def resolve_confirmation(self, conf_id, approve, reason=""):
        conf = self.store.get_confirmation(conf_id)
        if conf is None or conf["status"] != "pending":
            raise KeyError(f"confirmation not pending: {conf_id}")
        task = self.store.get_task(conf["task_id"])
        self.store.resolve_confirmation(conf_id, "approved" if approve else "rejected", reason)
        self.bus.emit(task["id"], "confirmation_resolved", approve=approve, reason=reason)
        if not approve:
            verdict = {"pass": False, "decided_by": "user_reject", "reason": reason, "checks": [],
                       "judge": {"status": "abstain"}, "user_signal": None}
            receipt = self._receipt(task, verdict, [])
            self.store.update_task(task["id"], status="rejected", verdict=verdict, receipt=receipt)
            self.bus.emit(task["id"], "status", status="rejected")
            return self.store.get_task(task["id"])
        row = self.store.get_skill(task["skill_id"], task["skill_version"])
        entry = row["contract"]["executor"]["entry"]
        artifacts = []
        if entry in COMMIT_REGISTRY:
            out = COMMIT_REGISTRY[entry](task, {"store": self.store})
            self.store.update_task(task["id"], result=out["result"],
                                   cost_ms=task["cost_ms"] + sum(s.get("ms", 0) for s in out.get("steps", [])))
            for s in out.get("steps", []):
                self.bus.emit(task["id"], "step", **s)
            artifacts = out.get("artifacts", [])
        return self._finalize(task["id"], artifacts)

    # ---------- user feedback (highest-weight eval signal) ----------
    def feedback(self, task_id, signal, note=""):
        if signal not in ("up", "down"):
            raise ValueError("signal must be up|down")
        task = self.store.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        self.store.add_feedback(task_id, signal, note)
        verdict = compose_verdict((task.get("verdict") or {}).get("checks", []),
                                  (task.get("verdict") or {}).get("judge"), signal)
        receipt = self._receipt(task, verdict, (task.get("receipt") or {}).get("evidence", {}).get("artifacts", []))
        self.store.update_task(task_id, verdict=verdict, receipt=receipt)
        self.bus.emit(task_id, "feedback", signal=signal, note=note)
        if signal == "down":
            streak = self.store.bump_fail_streak(task["skill_id"], task["skill_version"], 1)
            if streak >= DEMOTION_THRESHOLD:
                self.store.set_skill_status(task["skill_id"], task["skill_version"], "demoted")
                self.bus.emit(task_id, "skill_demoted", skill=task["skill_id"], streak=streak)
        else:
            self.store.bump_fail_streak(task["skill_id"], task["skill_version"], -99)
        return self.store.get_task(task_id)

    # ---------- metrics (same source as eval system) ----------
    def metrics(self):
        tasks = self.store.list_tasks(limit=10000)
        terminal = [t for t in tasks if t["status"] in TERMINAL]
        evaluated = [t for t in tasks if t.get("verdict")]
        executed = [t for t in tasks if t.get("route")]
        no_touch = [t for t in terminal if t["status"] == "delivered" and (t.get("verdict") or {}).get("pass") and not t["intervention"]]
        passed = [t for t in evaluated if (t.get("verdict") or {}).get("pass")]
        fast = [t for t in executed if t["route"] in ("connector", "replay")]
        pct = lambda a, b: round(len(a) / len(b) * 100, 1) if b else 0.0
        return {
            "north_star_no_touch_rate": pct(no_touch, terminal),
            "verification_pass_rate": pct(passed, evaluated),
            "fast_path_coverage": pct(fast, executed),
            "avg_cost_tokens": round(sum(t["cost_tokens"] for t in executed) / len(executed), 1) if executed else 0,
            "avg_cost_ms": round(sum(t["cost_ms"] for t in executed) / len(executed), 1) if executed else 0,
            "tasks_total": len(tasks), "terminal": len(terminal),
            "awaiting_confirmation": len([t for t in tasks if t["status"] == "awaiting_confirmation"]),
            "incidents": 0,
        }

    def today(self):
        tasks = self.store.list_tasks(limit=200)
        return {
            "done": [t for t in tasks if t["status"] in TERMINAL],
            "awaiting": [t for t in tasks if t["status"] == "awaiting_confirmation"],
            "active": [t for t in tasks if t["status"] not in TERMINAL and t["status"] != "awaiting_confirmation"],
            "metrics": self.metrics(),
        }


def json_intent(params):
    import json
    return json.dumps(params, ensure_ascii=False)[:200]
