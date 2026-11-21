import pytest

from zhiji.evaluators import compile_expr, eval_expr, run_checks, compose_verdict, UnsafeExpression


def test_basic_eval():
    code = compile_expr("result['price'] <= params['target']")
    assert eval_expr(code, {"result": {"price": 90}, "params": {"target": 100}}) is True


def test_whitelist_funcs_and_comprehension():
    code = compile_expr("len(set(i['t'] for i in result['items'])) == result['count']")
    ctx = {"result": {"items": [{"t": "a"}, {"t": "a"}], "count": 1}}
    assert eval_expr(code, ctx) is True


@pytest.mark.parametrize("expr", [
    "__import__('os').system('x')",
    "result.__class__",
    "open('x')",
    "(lambda: 1)()",
    "[x for x in ().__class__.__bases__]",
])
def test_injection_blocked(expr):
    with pytest.raises(UnsafeExpression):
        compile_expr(expr)


def test_check_error_counts_as_fail():
    checks = run_checks([{"id": "a", "expr": "result['missing'] > 1"}], {"result": {}})
    assert checks[0]["pass"] is False and "error" in checks[0]


def test_verdict_composition():
    ok = [{"id": "a", "pass": True}]
    assert compose_verdict(ok)["pass"] is True
    assert compose_verdict(ok, {"status": "fail"})["pass"] is False  # judge can downgrade
    assert compose_verdict([{"id": "a", "pass": False}], None, "up")["pass"] is True  # user overrides
    assert compose_verdict(ok, None, "down")["decided_by"] == "user"
    assert compose_verdict([])["pass"] is False  # no evidence, no pass
