from zhiji import memory
from zhiji.connectors import daily_report, price_watch, invoice_reconcile, ConnectorUnavailable
import pytest


def test_report_dedup():
    out = daily_report({}, {})
    titles = [i["title"] for i in out["result"]["items"]]
    assert len(titles) == len(set(titles)) == 4


def test_price_missing_item_unavailable():
    with pytest.raises(ConnectorUnavailable):
        price_watch({"item": "不存在的商品"}, {})


def test_invoice_balanced():
    out = invoice_reconcile({"demo": True}, {})
    assert out["result"]["balanced"] is True and out["result"]["matched"] == 4


def test_memory_crud_and_diary(store):
    m = store.add_memory("preference", "喜欢深色界面", source="user")
    assert store.get_memory(m["id"])["content"] == "喜欢深色界面"
    store.update_memory(m["id"], content="喜欢浅色界面")
    assert store.get_memory(m["id"])["content"] == "喜欢浅色界面"
    store.delete_memory(m["id"])
    assert all(x["id"] != m["id"] for x in store.list_memories())
    out = memory.consolidate(store)
    assert out["diary"]["kind"] == "diary"
    assert store.get_meta("last_consolidation") > 0
