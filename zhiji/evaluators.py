"""Eval engine: AST-whitelisted deterministic assertions + verdict composition.

Verdict rule: base = all(outcome_checks); judge can only downgrade; user signal has highest weight.
"""
import ast

FUNCS = {"len": len, "abs": abs, "min": min, "max": max, "round": round,
         "any": any, "all": all, "int": int, "float": float, "str": str, "set": set, "sorted": sorted}

ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.UnaryOp, ast.Not, ast.USub,
    ast.Name, ast.Load, ast.Store, ast.Constant, ast.Subscript, ast.Slice,
    ast.Call, ast.List, ast.Tuple, ast.GeneratorExp, ast.ListComp, ast.comprehension,
)


class UnsafeExpression(ValueError):
    pass


def compile_expr(expr: str):
    """Parse + whitelist-validate. Raises UnsafeExpression on anything dangerous."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise UnsafeExpression(f"syntax error: {e}") from e
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise UnsafeExpression(f"forbidden node: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCS:
                raise UnsafeExpression("only whitelisted functions may be called")
            if node.keywords:
                raise UnsafeExpression("keyword args not allowed")
    return compile(tree, "<assert>", "eval")


def eval_expr(code, ctx: dict):
    return eval(code, {"__builtins__": {}}, {**FUNCS, **ctx})  # noqa: S307 - sandboxed by whitelist


def run_checks(checks, ctx):
    results = []
    for chk in checks:
        item = {"id": chk["id"], "expr": chk["expr"]}
        try:
            code = compile_expr(chk["expr"])
            value = bool(eval_expr(code, ctx))
            item["pass"] = value
            item["value"] = value
        except Exception as e:  # evaluation error counts as failed check, never silently passes
            item["pass"] = False
            item["error"] = f"{type(e).__name__}: {e}"
        results.append(item)
    return results


class JudgeAdapter:
    """M0 stub: abstain. M1: swap in OpenAI-compatible LLM call (sample_rate <= 0.1)."""

    def __init__(self, sampler=None):
        self.sampler = sampler  # callable(task) -> bool, decides sampling

    def judge(self, rubric, task, sample_rate=0.1):
        return {"status": "abstain", "reason": "llm judge not configured (M0)"}


def compose_verdict(check_results, judge_result=None, user_signal=None):
    base = all(c["pass"] for c in check_results) if check_results else False
    verdict = {"pass": base, "decided_by": "assertions", "checks": check_results,
               "judge": judge_result or {"status": "abstain"}, "user_signal": user_signal}
    if judge_result and judge_result.get("status") == "fail":
        verdict["pass"] = False
        verdict["decided_by"] = "judge"
    if user_signal in ("up", "down"):
        verdict["pass"] = user_signal == "up"
        verdict["decided_by"] = "user"
        verdict["user_signal"] = user_signal
    return verdict
