from zhiji import memory
from zhiji.replay import run_regression


def test_price_hit_delivered_with_receipt(engine, store):
    t = engine.submit("price-watch", {"item": "降噪耳机 WH-1000XM6", "target_price": 1500}, "盯价命中")
    assert t["status"] == "delivered"
    assert t["verdict"]["pass"] is True
    assert t["route"] == "connector" and t["cost_tokens"] == 0
    assert t["receipt"]["evidence"]["checks"]
    kinds = [e["kind"] for e in store.traj_for(t["id"])]
    assert {"intent", "plan", "step", "verdict"} <= set(kinds)


def test_price_miss_failed(engine):
    t = engine.submit("price-watch", {"item": "机械键盘 Keychron K3", "target_price": 300}, "未达标")
    assert t["status"] == "failed" and t["verdict"]["pass"] is False


def test_sensitive_action_gated_then_approved(engine, store):
    t = engine.submit("price-watch", {"item": "降噪耳机 WH-1000XM6", "target_price": 1500, "auto_buy": True})
    assert t["status"] == "awaiting_confirmation" and t["intervention"] == 1
    confs = store.list_confirmations("pending")
    assert len(confs) == 1 and confs[0]["action"] == "pay"
    t2 = engine.resolve_confirmation(confs[0]["id"], True)
    assert t2["status"] == "delivered" and t2["result"]["order_id"]
    m = engine.metrics()
    assert m["north_star_no_touch_rate"] == 0.0  # confirmation counts as intervention


def test_reject_flows_to_memory(engine, store):
    t = engine.submit("price-watch", {"item": "降噪耳机 WH-1000XM6", "target_price": 1500, "auto_buy": True})
    conf = store.list_confirmations("pending")[0]
    t2 = engine.resolve_confirmation(conf["id"], False, "太贵了不想买")
    assert t2["status"] == "rejected"
    out = memory.consolidate(store)
    assert any("太贵了" in m["content"] for m in out["added"])
    assert out["diary"]["kind"] == "diary"


def test_consecutive_failures_demote_skill(engine, store):
    engine.submit("price-watch", {"item": "机械键盘 Keychron K3", "target_price": 300})
    engine.submit("price-watch", {"item": "机械键盘 Keychron K3", "target_price": 300})
    assert store.get_skill("price-watch")["status"] == "demoted"


def test_user_down_feedback_and_up_reset(engine, store):
    t = engine.submit("price-watch", {"item": "降噪耳机 WH-1000XM6", "target_price": 1500})
    t2 = engine.feedback(t["id"], "down", "价格证据不对")
    assert t2["verdict"]["pass"] is False and t2["verdict"]["decided_by"] == "user"
    t3 = engine.feedback(t["id"], "up")
    assert t3["verdict"]["pass"] is True
    assert store.get_skill("price-watch")["fail_streak"] == 0


def test_invoice_and_report(engine):
    t = engine.submit("invoice-reconcile", {"demo": True})
    assert t["status"] == "delivered" and t["result"]["balanced"] is True
    r = engine.submit("daily-report", {"topics": ["agent"]})
    assert r["status"] == "delivered" and r["result"]["count"] == 2


def test_metrics_shape(engine):
    engine.submit("price-watch", {"item": "降噪耳机 WH-1000XM6", "target_price": 1500})
    engine.submit("price-watch", {"item": "机械键盘 Keychron K3", "target_price": 300})
    m = engine.metrics()
    assert m["north_star_no_touch_rate"] == 50.0
    assert m["verification_pass_rate"] == 50.0
    assert m["fast_path_coverage"] == 100.0
    assert m["incidents"] == 0


def test_promotion_requires_regression_evidence(tmp_path):
    contract = {"id": "no-cases", "version": 1, "evaluator": {"outcome_checks": [{"id": "a", "expr": "1 == 1"}]}}
    reg = run_regression(contract, tmp_path / "skills", tmp_path / "data")
    assert reg["pass"] is False and "no golden cases" in reg["reason"]
