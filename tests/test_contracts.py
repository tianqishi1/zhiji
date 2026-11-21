import pytest

from zhiji.contracts import validate, ContractError
from zhiji.evaluators import UnsafeExpression
from zhiji.connectors import REGISTRY


def base_contract():
    return {
        "id": "x", "version": 1, "title": "测试",
        "executor": {"kind": "connector", "entry": "price_watch", "route": ["connector"], "sensitive_actions": []},
        "evaluator": {"outcome_checks": [{"id": "a", "type": "assert", "expr": "result['price'] <= 100"}]},
        "data_contract": {"trajectory": ["intent", "verdict"]},
    }


def test_valid_contract_passes():
    assert validate(base_contract(), REGISTRY.keys())["id"] == "x"


def test_no_evaluator_no_launch():
    c = base_contract()
    c["evaluator"] = {"outcome_checks": []}
    with pytest.raises(ContractError):
        validate(c, REGISTRY.keys())


def test_missing_evaluator_field():
    c = base_contract()
    del c["evaluator"]
    with pytest.raises(ContractError):
        validate(c, REGISTRY.keys())


def test_unsafe_expr_rejected():
    c = base_contract()
    c["evaluator"]["outcome_checks"][0]["expr"] = "__import__('os').system('calc')"
    with pytest.raises(UnsafeExpression):
        validate(c, REGISTRY.keys())


def test_unknown_entry_rejected():
    c = base_contract()
    c["executor"]["entry"] = "not_registered"
    with pytest.raises(ContractError):
        validate(c, REGISTRY.keys())
