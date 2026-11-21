"""S2 promotion gate: sandbox regression over golden cases before a skill goes active.

Golden cases = bundled regression suite (skills/cases/<id>.json) + recorded live successes
(data/golden/<id>.jsonl). Failure cases are auto-appended to prevent recurrence.
"""
import json
import time
from pathlib import Path

from .evaluators import run_checks


def load_cases(skill_id, skills_dir, data_dir):
    cases = []
    p = Path(skills_dir) / "cases" / f"{skill_id}.json"
    if p.exists():
        cases += json.loads(p.read_text(encoding="utf-8-sig"))
    g = Path(data_dir) / "golden" / f"{skill_id}.jsonl"
    if g.exists():
        for line in g.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                cases.append(json.loads(line))
    return cases


def record_case(skill_id, data_dir, params, result, expect_pass):
    gdir = Path(data_dir) / "golden"
    gdir.mkdir(parents=True, exist_ok=True)
    case = {"params": params, "result": result, "expect_pass": bool(expect_pass), "recorded_at": time.time()}
    with open(gdir / f"{skill_id}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(case, ensure_ascii=False) + "\n")


def run_regression(contract, skills_dir, data_dir):
    cases = load_cases(contract["id"], skills_dir, data_dir)
    if not cases:
        return {"pass": False, "reason": "no golden cases: a skill cannot be promoted without regression evidence",
                "total": 0, "failed": []}
    failed = []
    for i, case in enumerate(cases):
        ctx = {"params": case["params"], "result": case["result"],
               "now": case.get("now") or case["result"].get("ts") or case["result"].get("checked_at") or case["result"].get("generated_at") or time.time(),
               "artifacts": []}
        checks = run_checks(contract["evaluator"]["outcome_checks"], ctx)
        ok = all(c["pass"] for c in checks)
        if ok != bool(case["expect_pass"]):
            failed.append({"case": i, "expected": case["expect_pass"], "got": ok, "checks": checks})
    return {"pass": not failed, "total": len(cases), "failed": failed, "ran_at": time.time()}
