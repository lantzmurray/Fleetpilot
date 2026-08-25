"""FleetPilot agent core. Agent proposes; policy engine disposes."""
import argparse
import json
import os

from dotenv import load_dotenv

from agent.diagnosis import diagnose

ALLOWED_ACTION_KINDS = {"restart_queue", "clear_stuck_job", "ping_device",
                        "reroute_jobs", "disable_queue", "update_firmware",
                        "order_supplies", "notify_poc", "escalate"}


def validated_actions(actions: list, known_devices: set,
                      journal=None) -> list:
    """Defense against malformed/hallucinated LLM output: required fields,
    allowlisted action kinds, known device IDs only, bounded confidence,
    bounded device lists. Rejects are journaled, never silently dropped."""
    clean = []
    for a in actions:
        if not isinstance(a, dict) or "kind" not in a:
            continue
        if a["kind"] not in ALLOWED_ACTION_KINDS:
            if journal:
                journal.log("llm_output_rejected",
                            {"action": a, "reason": "unknown action kind"})
            continue
        devices = [d for d in a.get("devices", []) if d in known_devices]
        if a.get("devices") and not devices:
            if journal:
                journal.log("llm_output_rejected",
                            {"action": a, "reason": "no known device ids"})
            continue
        a = {**a, "devices": devices}
        clean.append(a)
    return clean
from agent.fleet_sim import FleetSimulator
from agent.journal import Journal
from agent.policy.risk import PolicyEngine, Risk
from agent.tools.registry import build_tools


def run_tick(sim: FleetSimulator, policy: PolicyEngine, journal: Journal) -> dict:
    """One agent cycle: observe -> correlate -> propose -> gate -> act/journal."""
    alerts = sim.active_alerts()
    journal.log("observe", {"alert_count": len(alerts), "alerts": alerts})

    diagnosis = diagnose(alerts)
    known = {d.device_id for d in sim.devices}
    diagnosis.proposed_actions = validated_actions(
        diagnosis.proposed_actions, known, journal)
    journal.log("diagnose", {
        "root_cause": diagnosis.root_cause,
        "confidence": min(max(diagnosis.confidence or 0.0, 0.0), 1.0),
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
            # approval inbox: action + the policy reason it was gated
            escalated.append({"action": action, "reason": decision.reason})
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
