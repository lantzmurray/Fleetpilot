"""Diagnosis engine: turns raw alerts into a structured RCA + proposed actions.

Primary path: Gemini (via the Google GenAI SDK — satisfies the hackathon's
agent-framework requirement) with JSON-schema-constrained output.
Fallback path: deterministic topology correlation, used when no API key is
configured (offline dev/tests) — and also sent to Gemini as grounding so the
LLM verifies rather than hallucinates.
"""
import os
from collections import defaultdict
from dataclasses import dataclass

# Rules require Gemini 3.x; override with GEMINI_MODEL if the exact ID differs
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string"},
        "confidence": {"type": "number"},
        "affected_nodes": {
            "type": "array",
            "items": {"type": "object", "properties": {
                "server": {"type": "string"},
                "queue": {"type": "string"},
            }},
        },
        "proposed_actions": {
            "type": "array",
            "items": {"type": "object", "properties": {
                "kind": {"type": "string"},
                "devices": {"type": "array", "items": {"type": "string"}},
                "cost_usd": {"type": "number"},
                "rationale": {"type": "string"},
            }, "required": ["kind", "rationale"]},
        },
    },
    "required": ["root_cause", "confidence", "proposed_actions"],
}

# symptom -> remediation mapping the LLM may propose (it cannot invent kinds;
# unknown kinds default to HUMAN in the policy engine anyway)
REMEDIATION_HINTS = {
    "job_stuck": {"kind": "restart_queue", "rationale": "clear hung queue spooler"},
    "toner_low": {"kind": "order_supplies", "rationale": "reorder toner below threshold"},
    "paper_low": {"kind": "notify_poc", "rationale": "ask site contact to load paper"},
    "firmware_noncompliant": {"kind": "update_firmware",
                              "rationale": "staged firmware compliance push"},
    "offline": {"kind": "ping_device", "rationale": "verify reachability before escalation"},
}


@dataclass
class Diagnosis:
    root_cause: str
    confidence: float
    affected_nodes: list
    proposed_actions: list
    source: str  # "gemini" | "heuristic"


def heuristic_diagnose(alerts: list[dict]) -> Diagnosis:
    """Deterministic correlation: group alerts by (server, symptom) — one
    hung spooler on a server fans out across all its devices/queues, so
    server-level grouping collapses the storm into one incident. If the
    alerts within a group share a single queue, narrow to queue level."""
    if not alerts:
        return Diagnosis("no active alerts", 1.0, [], [], "heuristic")
    groups = defaultdict(list)
    for a in alerts:
        groups[(a.get("server"), a.get("symptom"))].append(a)
    (server, symptom), members = max(
        groups.items(), key=lambda kv: len(kv[1]))
    queues = {a.get("queue") for a in members}
    if len(queues) == 1:
        location = f"queue {next(iter(queues))} on server {server}"
    else:
        location = f"server {server} ({len(queues)} queues affected)"
    share = len(members) / len(alerts)
    hint = REMEDIATION_HINTS.get(symptom, {})
    action = {
        "kind": hint.get("kind", "escalate"),
        "devices": sorted({a["device"] for a in members}),
        "rationale": hint.get("rationale", "unknown symptom — escalate"),
    }
    if hint.get("kind") == "order_supplies":
        action["cost_usd"] = round(len(action["devices"]) * 79.99, 2)
    return Diagnosis(
        root_cause=f"{symptom} at {location} affecting "
                   f"{len(members)} of {len(alerts)} alerts",
        confidence=round(0.5 + 0.5 * share, 2),
        affected_nodes=[{"server": server,
                         "queue": next(iter(queues)) if len(queues) == 1 else "*"}],
        proposed_actions=[action],
        source="heuristic")


def gemini_diagnose(alerts, heuristic: Diagnosis, api_key=None) -> Diagnosis:
    """Ask Gemini to verify/refine the heuristic RCA. Returns the heuristic
    result unchanged if no API key is configured."""
    from google.genai import types  # imported lazily; SDK is optional at test time
    api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get(
        "LLM_API_KEY")
    if not api_key:
        return heuristic

    from google import genai
    client = genai.Client(api_key=api_key)
    prompt = (
        "You are an AIOps diagnosis agent for an enterprise printer fleet "
        "(devices -> servers -> queues topology). Active alerts:\n"
        f"{alerts[:200]}\n\n"
        "A deterministic correlator proposes this root cause:\n"
        f"{heuristic.root_cause} (confidence {heuristic.confidence})\n"
        "Verify against the alerts. Confirm, refine, or split into multiple "
        "root causes if the alerts clearly have more than one. Only propose "
        "action kinds from this allowlist: restart_queue, clear_stuck_job, "
        "ping_device, reroute_jobs, disable_queue, update_firmware, "
        "order_supplies, notify_poc. Spend-averse: prefer the smallest "
        "action that resolves the most alerts."
    )
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SCHEMA,
        ),
    )
    result = _parse(response.text)
    if result is None:  # malformed despite schema — never trust blindly
        return heuristic
    result["source"] = "gemini"
    return Diagnosis(**result)


def _parse(text: str):
    import json
    try:
        data = json.loads(text)
        return {
            "root_cause": data["root_cause"],
            "confidence": float(data.get("confidence", 0)),
            "affected_nodes": data.get("affected_nodes", []),
            "proposed_actions": data.get("proposed_actions", []),
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def diagnose(alerts: list[dict]) -> Diagnosis:
    heuristic = heuristic_diagnose(alerts)
    return gemini_diagnose(alerts, heuristic)
