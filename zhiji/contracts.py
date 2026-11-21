"""Skill Contract: executor + evaluator + data_contract. No evaluator, no launch."""
import json
from pathlib import Path

from .evaluators import compile_expr


class ContractError(ValueError):
    pass


def validate(contract: dict, registry_entries) -> dict:
    for key in ("id", "version", "title", "executor", "evaluator", "data_contract"):
        if key not in contract:
            raise ContractError(f"missing required field: {key}")
    ex = contract["executor"]
    if ex.get("kind") not in ("connector", "replay", "vision"):
        raise ContractError("executor.kind must be connector|replay|vision")
    if ex.get("entry") not in registry_entries:
        raise ContractError(f"executor.entry '{ex.get('entry')}' not in connector registry")
    if not isinstance(ex.get("route"), list) or not ex["route"]:
        raise ContractError("executor.route must be a non-empty list")
    ex.setdefault("sensitive_actions", [])

    ev = contract["evaluator"]
    checks = ev.get("outcome_checks")
    if not checks:
        raise ContractError("IRON RULE: evaluator.outcome_checks must be non-empty (no evaluator, no launch)")
    ids = set()
    for chk in checks:
        if chk.get("type") != "assert" or not chk.get("expr") or not chk.get("id"):
            raise ContractError("each outcome_check needs id/type=assert/expr")
        if chk["id"] in ids:
            raise ContractError(f"duplicate check id: {chk['id']}")
        ids.add(chk["id"])
        compile_expr(chk["expr"])  # raises UnsafeExpression
    ev.setdefault("llm_judge", {"enabled": False, "rubric": "", "sample_rate": 0.1})
    ev.setdefault("user_signal", {"weight": "highest"})

    dc = contract["data_contract"]
    if not dc.get("trajectory"):
        raise ContractError("data_contract.trajectory required")
    dc.setdefault("retention_days", 90)
    dc.setdefault("export", "opt_in_anonymized")
    return contract


def load_skills(skills_dir):
    out = []
    for p in sorted(Path(skills_dir).glob("*.json")):
        with open(p, encoding="utf-8-sig") as f:
            out.append(json.load(f))
    return out
