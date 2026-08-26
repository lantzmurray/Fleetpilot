"""Focused policy boundary tests."""

from agent.policy.risk import PolicyEngine, Risk


def test_invalid_supply_cost_is_blocked_instead_of_raising():
    decision = PolicyEngine.defaults().evaluate({
        "kind": "order_supplies",
        "cost_usd": "not-a-number",
    })

    assert decision.risk is Risk.BLOCKED
    assert "invalid" in decision.reason
