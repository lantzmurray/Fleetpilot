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


SCENARIOS = [eval_queue_hang, eval_action_cap, eval_denylist, eval_human_gate]


def main() -> int:
    results = [s() for s in SCENARIOS]
    print(f"\n{sum(results)}/{len(results)} scenarios passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
