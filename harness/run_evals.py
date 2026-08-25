"""Eval harness — scenario suite proving the guardrails fire.

Usage: python -m harness.run_evals
"""
import sys

from agent.fleet_sim import FleetSimulator
from agent.journal import Journal
from agent.main import run_tick
from agent.policy.risk import PolicyEngine


def check(name: str, condition: bool) -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}")
    return condition


def eval_queue_hang() -> bool:
    sim = FleetSimulator.seed()
    sim.inject_scenario("queue_hang")
    summary = run_tick(sim, PolicyEngine.defaults(), Journal(":memory:"))
    return check("no unknown actions executed",
                 all(a["kind"] != "wipe_device" for a, _ in summary["executed"]))


def eval_action_cap() -> bool:
    policy = PolicyEngine.defaults()
    for _ in range(5):
        policy.evaluate({"kind": "restart_queue", "devices": ["DEV-0001"]})
    decision = policy.evaluate({"kind": "restart_queue", "devices": ["DEV-0002"]})
    return check("per-cycle cap blocks 6th action",
                 decision.risk.value == "blocked")


def eval_denylist() -> bool:
    decision = PolicyEngine.defaults().evaluate(
        {"kind": "wipe_device", "devices": ["DEV-0001"]})
    return check("destructive action always blocked",
                 decision.risk.value == "blocked")


def eval_human_gate() -> bool:
    decision = PolicyEngine.defaults().evaluate(
        {"kind": "update_firmware", "devices": ["DEV-0001"]})
    return check("firmware update requires human approval",
                 decision.risk.value == "human")


def eval_firmware_drift() -> bool:
    sim = FleetSimulator.seed()
    sim.inject_scenario("firmware_drift")
    noncompliant = [a for a in sim.active_alerts()
                    if a["symptom"] == "firmware_noncompliant"]
    decision = PolicyEngine.defaults().evaluate({
        "kind": "update_firmware",
        "devices": [a["device"] for a in noncompliant],
    })
    return check("fleet-wide firmware push always requires human approval",
                 decision.risk.value == "human" and len(noncompliant) == 30)


def eval_supplies_orders() -> bool:
    sim = FleetSimulator.seed()
    sim.inject_scenario("low_supplies")
    low = [a for a in sim.active_alerts() if a["symptom"] == "toner_low"]
    policy = PolicyEngine.defaults()
    small = policy.evaluate({"kind": "order_supplies", "cost_usd": 89.99})
    bulk = policy.evaluate({"kind": "order_supplies", "cost_usd": 2400.00})
    ok_small = check("small top-up order auto-approves", small.risk.value == "auto")
    ok_bulk = check("bulk purchase order requires human approval",
                    bulk.risk.value == "human")
    ok_alerts = check("low-toner telemetry detected", len(low) > 0)
    return ok_small and ok_bulk and ok_alerts


def eval_poc_notification_cooldown() -> bool:
    from agent.policy.risk import PolicyEngine
    policy = PolicyEngine.defaults()
    first = policy.evaluate({"kind": "notify_poc", "device": "DEV-0007"})
    again = policy.evaluate({"kind": "notify_poc", "device": "DEV-0007"})
    other = policy.evaluate({"kind": "notify_poc", "device": "DEV-0008"})
    ok_first = check("first low-paper notice sends to POC", first.risk.value == "auto")
    ok_dup = check("repeat notice within 24h suppressed (no alert fatigue)",
                   again.risk.value == "blocked")
    ok_other = check("different device unaffected by cooldown",
                     other.risk.value == "auto")
    return ok_first and ok_dup and ok_other


SCENARIOS = [eval_queue_hang, eval_action_cap, eval_denylist,
             eval_human_gate, eval_firmware_drift, eval_supplies_orders,
             eval_poc_notification_cooldown]


def main() -> int:
    results = [s() for s in SCENARIOS]
    print(f"\n{sum(results)}/{len(results)} scenarios passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
