"""Memory v0 + nightly consolidation (S1). Every memory carries its source; user has full control."""
import time

from .store import now


def consolidate(store, bus=None):
    """Scan today's rejected confirmations / down feedback / verdicts -> memory candidates + diary."""
    last = store.get_meta("last_consolidation", 0)
    t = now()
    added = []

    for c in store.list_confirmations("rejected"):
        if (c["resolved_at"] or 0) > last:
            m = store.add_memory("preference",
                                 f"用户拒绝了敏感动作「{c['action']}」" + (f"，原因：{c['reason']}" if c["reason"] else ""),
                                 source=f"confirmation:{c['id']}", confidence=0.9)
            added.append(m)

    tasks = store.list_tasks(limit=500)
    down_tasks, up_count, pass_count, evaluated = [], 0, 0, 0
    for task in tasks:
        if task["created_at"] <= last:
            continue
        fb = store.feedback_for(task["id"])
        for f in fb:
            if f["signal"] == "down":
                down_tasks.append((task, f))
            elif f["signal"] == "up":
                up_count += 1
        v = task.get("verdict")
        if v:
            evaluated += 1
            if v.get("pass"):
                pass_count += 1

    for task, f in down_tasks:
        m = store.add_memory("correction",
                             f"「{task['title']}」的结果被用户标记为不满意" + (f"：{f['note']}" if f["note"] else "") + "，需重探索/修正策略",
                             source=f"task:{task['id']}", confidence=0.85)
        added.append(m)

    rate = round(pass_count / evaluated * 100) if evaluated else 0
    diary = store.add_memory("diary",
                             f"今晚我整理了 {len(added)} 条新记忆；今日处理 {evaluated} 个已评测任务，核验通过率 {rate}%，收到 {up_count} 个👍。",
                             source="consolidation", confidence=1.0)
    store.set_meta("last_consolidation", t)
    return {"diary": diary, "added": added, "stats": {"evaluated": evaluated, "pass_rate": rate}}
