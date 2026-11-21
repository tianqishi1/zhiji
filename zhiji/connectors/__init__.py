"""L0 connectors. Each run(params, ctx) -> {result, artifacts, steps[, pending_action]}.

Demo sources are bundled fixtures (offline-runnable); live HTTP/RSS is optional.
Raise ConnectorUnavailable to trigger router fallback (replay -> vision).
"""
import csv
import io
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures"


class ConnectorUnavailable(RuntimeError):
    pass


def _step(name, t0, tokens=0):
    return {"name": name, "ms": int((time.time() - t0) * 1000), "tokens": tokens}


def _fixture(name):
    with open(FIXTURES / name, encoding="utf-8-sig") as f:
        return json.load(f)


# ---------------- daily report ----------------
def daily_report(params, ctx):
    t0 = time.time()
    steps = []
    topics = [t.lower() for t in params.get("topics", [])]
    items = []
    sources = params.get("sources")
    if sources:  # live RSS mode
        for url in sources:
            try:
                with urllib.request.urlopen(url, timeout=10) as resp:
                    root = ET.fromstring(resp.read())
                for it in root.iter("item"):
                    items.append({"title": (it.findtext("title") or "").strip(),
                                  "url": (it.findtext("link") or "").strip(),
                                  "ts": time.time(), "source": url})
            except Exception as e:
                raise ConnectorUnavailable(f"rss fetch failed: {e}") from e
            steps.append(_step(f"fetch:{url}", t0))
    else:
        items = _fixture("feeds.json")["items"]
        steps.append(_step("load:demo-feeds", t0))
    if topics:
        items = [i for i in items if any(t in (i["title"] + i.get("summary", "")).lower() for t in topics)]
    seen, deduped = set(), []
    for i in sorted(items, key=lambda x: -x.get("ts", 0)):
        if i["title"] not in seen:
            seen.add(i["title"])
            deduped.append(i)
    steps.append(_step("filter+dedup", t0))
    result = {"items": deduped, "count": len(deduped), "generated_at": time.time()}
    return {"result": result, "artifacts": [{"type": "report_items", "count": len(deduped)}], "steps": steps}


# ---------------- price watch ----------------
def price_watch(params, ctx):
    t0 = time.time()
    item = params["item"]
    source = params.get("source", "demo")
    if source == "demo":
        data = _fixture("prices.json")
        if item not in data:
            raise ConnectorUnavailable(f"item not found in demo source: {item}")
        rec = dict(data[item])
        rec["ts"] = time.time()  # simulate a live fetch timestamp
        steps = [_step("fetch:demo-price", t0)]
    else:
        try:
            with urllib.request.urlopen(source, timeout=10) as resp:
                rec = json.loads(resp.read())
            rec["ts"] = time.time()
            steps = [_step(f"fetch:{source}", t0)]
        except Exception as e:
            raise ConnectorUnavailable(f"price source failed: {e}") from e
    result = {"item": item, "price": rec["price"], "ts": rec["ts"],
              "url": rec.get("url", ""), "title": rec.get("title", item)}
    out = {"result": result, "artifacts": [{"type": "price_evidence", "url": rec.get("url", ""), "price": rec["price"]}], "steps": steps}
    if params.get("auto_buy"):
        out["pending_action"] = {"type": "pay", "preview": {"item": item, "price": rec["price"],
                                                          "target_price": params.get("target_price"),
                                                          "note": "达到目标价，模拟下单（M0 不产生真实支付）"}}
    return out


def price_watch_commit(task, ctx):
    """Called only AFTER user approves the sensitive 'pay' action."""
    r = dict(task["result"] or {})
    r["order_id"] = "demo-order-" + task["id"][-6:]
    r["ordered_at"] = time.time()
    return {"result": r, "steps": [{"name": "commit:demo-order", "ms": 5, "tokens": 0}]}


# ---------------- invoice reconcile ----------------
def invoice_reconcile(params, ctx):
    t0 = time.time()
    if params.get("demo", True):
        expected = _fixture("invoice_expected.json")["entries"]
        actual_text = (FIXTURES / "invoice_actual.csv").read_text(encoding="utf-8-sig")
    else:
        with open(params["expected"], encoding="utf-8-sig") as f:
            expected = json.load(f)["entries"]
        actual_text = Path(params["actual"]).read_text(encoding="utf-8-sig")
    actual = {}
    for row in csv.DictReader(io.StringIO(actual_text)):
        actual[row["id"]] = {"amount": float(row["amount"]), "desc": row.get("desc", "")}
    mismatches = []
    for e in expected:
        a = actual.get(e["id"])
        if a is None:
            mismatches.append({"id": e["id"], "kind": "missing", "expected": e["amount"]})
        elif abs(a["amount"] - e["amount"]) > 0.005:
            mismatches.append({"id": e["id"], "kind": "amount", "expected": e["amount"], "actual": a["amount"]})
    extra = [k for k in actual if k not in {e["id"] for e in expected}]
    for k in extra:
        mismatches.append({"id": k, "kind": "unexpected", "actual": actual[k]["amount"]})
    total_e = round(sum(e["amount"] for e in expected), 2)
    total_a = round(sum(a["amount"] for a in actual.values()), 2)
    result = {"matched": len(expected) - len([m for m in mismatches if m["kind"] != "unexpected"]),
              "mismatches": mismatches, "total_expected": total_e, "total_actual": total_a,
              "balanced": not mismatches, "checked_at": time.time()}
    return {"result": result,
            "artifacts": [{"type": "reconcile_table", "mismatches": mismatches}],
            "steps": [_step("load+reconcile", t0)]}


REGISTRY = {"daily_report": daily_report, "price_watch": price_watch, "invoice_reconcile": invoice_reconcile}
COMMIT_REGISTRY = {"price_watch": price_watch_commit}
