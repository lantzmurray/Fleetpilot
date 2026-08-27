"""FleetPilot agent core. Agent proposes; policy engine disposes."""
import argparse
import json
import math

from dotenv import load_dotenv

from agent.diagnosis import diagnose
from agent.fleet_sim import FleetSimulator
from agent.journal import Journal
from agent.policy.risk import MAX_AFFECTED_DEVICES, PolicyEngine, Risk
from agent.tools.registry import build_tools

ALLOWED_ACTION_KINDS = {"restart_queue", "clear_stuck_job", "ping_device",
                        "reroute_jobs", "disable_queue", "update_firmware",
                        "order_supplies", "notify_poc", "escalate"}


def validated_actions(actions: list, known_devices: set, journal=None,
                      enforce_device_limit: bool = True) -> list:
    """Defense against malformed/hallucinated LLM output: required fields,
    allowlisted action kinds, known device IDs only, bounded confidence,
    bounded device lists. Rejects are journaled, never silently dropped."""
    clean = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        kind = a.get("kind")
        if not isinstance(kind, str):
            if journal:
                journal.log("llm_output_rejected",
                            {"action": a, "reason": "invalid action kind"})
            continue
        if kind not in ALLOWED_ACTION_KINDS:
            if journal:
                journal.log("llm_output_rejected",
                            {"action": a, "reason": "unknown action kind"})
            continue
        requested_devices = a.get("devices", [])
        if not isinstance(requested_devices, list):
            if journal:
                journal.log(
                    "llm_output_rejected",
                    {"action": a, "reason": "device list is not an array"},
                )
            continue
        if (enforce_device_limit and
                len(requested_devices) > MAX_AFFECTED_DEVICES):
            if journal:
                journal.log(
                    "llm_output_rejected",
                    {"action": a, "reason": "device list exceeds safe bound"},
                )
            continue
        devices = [d for d in requested_devices
                   if isinstance(d, str) and d in known_devices]
        if requested_devices and not devices:
            if journal:
                journal.log("llm_output_rejected",
                            {"action": a, "reason": "no known device ids"})
            continue
        rationale = a.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            if journal:
                journal.log("llm_output_rejected",
                            {"action": a, "reason": "invalid rationale"})
            continue
        cost = a.get("cost_usd")
        if cost is not None and (
                isinstance(cost, bool) or not isinstance(cost, (int, float))
                or not math.isfinite(cost) or cost < 0):
            if journal:
                journal.log("llm_output_rejected",
                            {"action": a, "reason": "invalid cost_usd"})
            continue
        clean_action = {"kind": kind, "devices": devices,
                        "rationale": rationale}
        if cost is not None:
            clean_action["cost_usd"] = float(cost)
        clean.append(clean_action)
    return clean


def ground_action_scopes(actions: list[dict], alerts: list[dict],
                         journal=None) -> list[dict]:
    """Expand model targets only from active incident evidence.

    This happens before policy evaluation so the gate always sees the exact
    scope the executor will receive. The executor never expands on its own.
    """
    grounded: list[dict] = []
    for action in actions:
        if action["kind"] != "clear_stuck_job":
            grounded.append(action)
            continue
        requested = sorted(set(action.get("devices", [])))
        suspect_servers = {
            alert.get("server") for alert in alerts
            if alert.get("symptom") == "job_stuck"
            and alert.get("suspected_blocker")
            and alert.get("device") in requested
        }
        if not suspect_servers:
            grounded.append(action)
            continue
        effective = sorted({
            alert["device"] for alert in alerts
            if alert.get("symptom") == "job_stuck"
            and alert.get("server") in suspect_servers
        })
        expanded = {**action, "devices": effective}
        if effective != requested and journal:
            journal.log("action_scope_grounded", {
                "kind": action["kind"],
                "requested_devices": requested,
                "effective_devices": effective,
                "basis": "active job_stuck incident on suspect job server",
            })
        grounded.append(expanded)
    return grounded


def run_tick(sim: FleetSimulator, policy: PolicyEngine, journal: Journal) -> dict:
    """One agent cycle: observe -> correlate -> propose -> gate -> act/journal."""
    alerts = sim.active_alerts()
    journal.log("observe", {"alert_count": len(alerts), "alerts": alerts})

    diagnosis = diagnose(alerts)
    known = {d.device_id for d in sim.devices}
    diagnosis.proposed_actions = validated_actions(
        diagnosis.proposed_actions, known, journal,
        enforce_device_limit=diagnosis.source != "heuristic")
    diagnosis.proposed_actions = ground_action_scopes(
        diagnosis.proposed_actions, alerts, journal)
    confidence = min(max(diagnosis.confidence or 0.0, 0.0), 1.0)
    journal.log("diagnose", {
        "root_cause": diagnosis.root_cause,
        "confidence": confidence,
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
               "confidence": confidence,
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
