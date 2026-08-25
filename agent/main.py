"""FleetPilot agent core. Agent proposes; policy engine disposes."""
import argparse
import json
import os

from dotenv import load_dotenv

from agent.diagnosis import diagnose
from agent.fleet_sim import FleetSimulator
from agent.journal import Journal
from agent.policy.risk import PolicyEngine, Risk
from agent.tools.registry import build_tools


def run_tick(sim: FleetSimulator, policy: PolicyEngine, journal: Journal) -> dict:
    """One agent cycle: observe -> correlate -> propose -> gate -> act/journal."""
    alerts = sim.active_alerts()
    journal.log("observe", {"alert_count": len(alerts), "alerts": alerts})

    diagnosis = diagnose(alerts)
    journal.log("diagnose", {
        "root_cause": diagnosis.root_cause,
        "confidence": diagnosis.confidence,
        "affected_nodes": diagnosis.affected_nodes,
        "source": diagnosis.source,
        "proposed_actions": diagnosis.proposed_actions,
    })

    executed, blocked, escalated = [], [], []
    for action in diagnosis.proposed_actions:
        decision = policy.evaluate(action)
        journal.log("gate", {"action": action,
                             "decision": decision.risk.value,
                             "reason": decision.reason})
        if decision.risk is Risk.AUTO:
            result = sim.execute(action)
            executed.append((action, result))
        elif decision.risk is Risk.HUMAN:
            escalated.append(action)      # approval inbox (day-3: web UI)
        else:
            blocked.append((action, decision.reason))

    summary = {"root_cause": diagnosis.root_cause,
               "confidence": diagnosis.confidence,
               "diagnosis_source": diagnosis.source,
               "executed": executed, "escalated": escalated, "blocked": blocked}
    journal.log("cycle_complete", summary)
    return summary


def main(demo: bool = False) -> None:
    load_dotenv()
    sim = FleetSimulator.seed()
    policy = PolicyEngine.defaults()
    journal = Journal()
    build_tools(sim)
    if demo:
        sim.inject_scenario("queue_hang")
    summary = run_tick(sim, policy, journal)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="run scripted demo scenario")
    args = ap.parse_args()
    main(demo=args.demo)
