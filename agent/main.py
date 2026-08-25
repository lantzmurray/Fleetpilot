"""FleetPilot agent core. Agent proposes; policy engine disposes."""
import argparse

from agent.fleet_sim import FleetSimulator
from agent.journal import Journal
from agent.policy.risk import PolicyEngine, Risk
from agent.tools.registry import build_tools


def run_tick(sim: FleetSimulator, policy: PolicyEngine, journal: Journal) -> dict:
    """One agent cycle: observe -> correlate -> propose -> gate -> act/journal."""
    alerts = sim.active_alerts()
    journal.log("observe", {"alert_count": len(alerts), "alerts": alerts})

    # TODO(day-2): LLM diagnosis via Strands — structured output:
    # {root_cause, confidence, affected_topology_nodes, proposed_actions[]}
    diagnosis = {"root_cause": "UNIMPLEMENTED", "confidence": 0.0,
                 "proposed_actions": []}
    journal.log("diagnose", diagnosis)

    executed, blocked, escalated = [], [], []
    for action in diagnosis["proposed_actions"]:
        decision = policy.evaluate(action)
        journal.log("gate", {"action": action, "decision": decision})
        if decision.risk is Risk.AUTO:
            result = sim.execute(action)  # TODO(day-2)
            executed.append((action, result))
        elif decision.risk is Risk.HUMAN:
            escalated.append(action)      # TODO(day-3): approval inbox
        else:
            blocked.append((action, decision.reason))

    summary = {"executed": executed, "escalated": escalated, "blocked": blocked}
    journal.log("cycle_complete", summary)
    return summary


def main(demo: bool = False) -> None:
    sim = FleetSimulator.seed()
    policy = PolicyEngine.defaults()
    journal = Journal()
    build_tools(sim)  # registered for Strands integration (day-2)
    run_tick(sim, policy, journal)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="run scripted demo scenario")
    args = ap.parse_args()
    main(demo=args.demo)
