"""Three-level execution router: connector -> replay -> vision (M0 stub, honest failure)."""
from pathlib import Path

from .connectors import REGISTRY, ConnectorUnavailable


class VisionNotConfigured(RuntimeError):
    pass


def resolve_route(skill_row, data_dir):
    """Pick the fast path when the skill is active; otherwise fall back."""
    contract = skill_row["contract"]
    if skill_row["status"] == "active" and contract["executor"]["kind"] == "connector":
        return "connector"
    for r in contract["executor"]["route"]:
        if r == "connector" and contract["executor"]["entry"] in REGISTRY:
            return "connector"
        if r == "replay" and (Path(data_dir) / "replay" / f"{skill_row['id']}.json").exists():
            return "replay"
    return "vision"


def run_route(route, skill_row, params, ctx, data_dir):
    contract = skill_row["contract"]
    entry = contract["executor"]["entry"]
    if route == "connector":
        return REGISTRY[entry](params, ctx)  # may raise ConnectorUnavailable
    if route == "replay":
        import json
        script = json.loads((Path(data_dir) / "replay" / f"{skill_row['id']}.json").read_text(encoding="utf-8-sig"))
        return {"result": script["result"], "artifacts": script.get("artifacts", []),
                "steps": [{"name": "replay:recorded-script", "ms": 1, "tokens": 0}]}
    raise VisionNotConfigured("vision GUI fallback not configured in M0 (planned: cloud phone + map replay)")
