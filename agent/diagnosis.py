"""Diagnosis engine: turns raw alerts into a structured RCA + proposed actions.

Primary path: Gemini (via the Google GenAI SDK — satisfies the hackathon's
agent-framework requirement) with JSON-schema-constrained output.
Fallback path: deterministic topology correlation, used when no API key is
configured (offline dev/tests) — and also sent to Gemini as grounding so the
LLM verifies rather than hallucinates.
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

GEMINI_TIMEOUT_S = 14  # per candidate; below the warmed-demo gate
GLM_TIMEOUT_S = 30     # test backend; ~6s with thinking disabled, 35s+ without

# Rules require Gemini 3.5 or newer; all verified available to our key Aug 25.
# Resolved lazily per call — .env/load_dotenv may run after this module imports.
# Preview endpoints can spike with 503s under demand, so we use an eligible
# primary plus verified failovers and record
# which model actually answered (surfaced in the health strip).
MODEL_CASCADE = ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash")
last_model_used: str | None = None
last_fallback_reason: str | None = None


def model_candidates() -> list[str]:
    pinned = os.environ.get("GEMINI_MODEL")
    return [pinned] if pinned else list(MODEL_CASCADE)


def _build_prompt(alerts, heuristic: Diagnosis) -> str:
    context = json.dumps(
        _compact_context(alerts, heuristic), separators=(",", ":"))
    return (
        "Enterprise fleet AIOps. Verify the grounded diagnosis and return "
        "the smallest relevant action. Only copy device IDs from the input. "
        "Allowed actions: restart_queue, clear_stuck_job, ping_device, "
        "reroute_jobs, disable_queue, update_firmware, order_supplies, "
        f"notify_poc. Return ONLY a JSON object with keys root_cause, "
        f"confidence (0-1), affected_nodes, proposed_actions (each with "
        f"kind, devices, rationale). Input:{context}"
    )


def _glm_diagnose(alerts, heuristic: Diagnosis) -> Diagnosis:
    """OpenAI-compatible test backend (e.g., GLM). Same contract as the
    Gemini path: JSON in, validated diagnosis out; deterministic fallback
    on any failure. NOT contest-eligible — used to rehearse at full cadence
    without burning Gemini quota. Flip LLM_BACKEND back for the real demo."""
    global last_fallback_reason, last_model_used
    api_key = os.environ.get("GLM_API_KEY")
    if not api_key:
        last_fallback_reason = "no_glm_credentials"
        return heuristic
    import httpx  # lazy: offline paths never load it

    model = os.environ.get("GLM_MODEL", "glm-5.2")
    base = os.environ.get("GLM_BASE_URL", "https://api.z.ai/api/paas/v4")

    def call():
        r = httpx.post(
            f"{base.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "temperature": 0,
                  "response_format": {"type": "json_object"},
                  # thinking mode takes 35s+; disabled answers in ~6s
                  "thinking": {"type": "disabled"},
                  "messages": [{"role": "user",
                                "content": _build_prompt(alerts, heuristic)}]},
            timeout=GLM_TIMEOUT_S)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    try:
        pool = ThreadPoolExecutor(max_workers=1)
        text = pool.submit(call).result(timeout=GLM_TIMEOUT_S + 1)
    except Exception as exc:  # noqa: BLE001
        last_fallback_reason = type(exc).__name__
        return heuristic
    result = _parse(text)
    if result is None:
        last_fallback_reason = "malformed_model_response"
        return heuristic
    last_model_used = model
    return Diagnosis(source="glm", **result)


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
    source: str  # "gemini" | "glm" (test backend) | "heuristic"


def heuristic_diagnose(alerts: list[dict]) -> Diagnosis:
    """Deterministic correlation: group alerts by (server, symptom) — one
    hung spooler on a server fans out across all its devices/queues, so
    server-level grouping collapses the storm into one incident. If the
    alerts within a group share a single queue, narrow to queue level."""
    if not alerts:
        return Diagnosis("no active alerts", 1.0, [], [], "heuristic")
    groups = defaultdict(list)
    for a in alerts:
        symptom = a.get("symptom")
        scope = "fleet" if symptom == "firmware_noncompliant" else a.get(
            "server")
        groups[(scope, symptom)].append(a)
    (server, symptom), members = max(
        groups.items(), key=lambda kv: len(kv[1]))
    queues = {a.get("queue") for a in members}
    if server == "fleet":
        location = "enterprise fleet"
    elif len(queues) == 1:
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


def _compact_context(alerts: list[dict], heuristic: Diagnosis) -> dict:
    """Keep the live request small while preserving grounded fleet scope."""
    groups: dict[tuple, dict] = {}
    for alert in alerts:
        key = (alert.get("server"), alert.get("symptom"))
        current = groups.get(key, {"devices": [], "queues": set()})
        groups[key] = {
            "devices": [*current["devices"], alert.get("device")],
            "queues": {*current["queues"], alert.get("queue")},
        }
    return {
        "alert_count": len(alerts),
        "groups": [
            {
                "server": server,
                "symptom": symptom,
                "devices": values["devices"],
                "queues": sorted(values["queues"]),
            }
            for (server, symptom), values in groups.items()
        ],
        "grounded_root_cause": heuristic.root_cause,
        "grounded_confidence": heuristic.confidence,
    }


def gemini_diagnose(alerts, heuristic: Diagnosis, api_key=None) -> Diagnosis:
    """Ask Gemini to verify/refine the heuristic RCA. Returns the heuristic
    result unchanged if no credentials are configured.

    Backends (GEMINI_BACKEND env): "vertex" uses Vertex AI inside the Google
    Cloud project (real quotas, billed against credits — the demo path);
    default uses an AI Studio API key (free tier, 20 req/day/model cap)."""
    global last_fallback_reason, last_model_used
    last_fallback_reason = None
    last_model_used = None

    if os.environ.get("LLM_BACKEND", "").lower() == "glm":
        return _glm_diagnose(alerts, heuristic)

    backend = os.environ.get("GEMINI_BACKEND", "api-key").lower()
    client = None
    if backend == "vertex":
        project = os.environ.get("GCP_PROJECT_ID") or os.environ.get(
            "GOOGLE_CLOUD_PROJECT")
        if project:
            from google import genai  # lazy: offline paths never load the SDK
            client = genai.Client(
                vertexai=True, project=project,
                location=os.environ.get("GCP_REGION", "us-central1"))
        else:
            last_fallback_reason = "vertex_selected_but_no_project"
    else:
        api_key = api_key or os.environ.get("GEMINI_API_KEY") or \
            os.environ.get("LLM_API_KEY")
        if api_key:
            from google import genai
            client = genai.Client(api_key=api_key)
    if client is None:
        if not last_fallback_reason:
            last_fallback_reason = "no_model_credentials"
        return heuristic

    from google.genai import types  # lazy: offline paths never load the SDK
    context = json.dumps(
        _compact_context(alerts, heuristic), separators=(",", ":"))
    prompt = (
        "Enterprise fleet AIOps. Verify the grounded diagnosis and return "
        "the smallest relevant action. Only copy device IDs from the input. "
        "Allowed actions: restart_queue, clear_stuck_job, ping_device, "
        "reroute_jobs, disable_queue, update_firmware, order_supplies, "
        f"notify_poc. Input:{context}"
    )

    def call(model: str):
        thinking_level = (
            types.ThinkingLevel.LOW
            if model.startswith("gemini-3.7")
            else types.ThinkingLevel.MINIMAL
        )
        return client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SCHEMA,
                # thinking tokens count against this cap on 3.5-flash;
                # 1024 truncated the JSON (MAX_TOKENS) and silently degraded
                # to the heuristic — keep it generous, output stays small
                max_output_tokens=8192,
                temperature=0,
                thinking_config=types.ThinkingConfig(
                    thinking_level=thinking_level),
            ),
        )

    response = None
    deadline = time.monotonic() + GEMINI_TIMEOUT_S
    for model in model_candidates():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            last_fallback_reason = "TimeoutError"
            break
        try:
            # hard timeout: SDK retries with backoff can stall minutes on
            # rate limits; the heuristic answer is always the fallback.
            # NB: no `with` block — shutdown(wait=True) would still block
            # on a hung call; we abandon the thread instead.
            pool = ThreadPoolExecutor(max_workers=1)
            response = pool.submit(call, model).result(
                timeout=remaining)
            pool.shutdown(wait=False, cancel_futures=True)
            last_model_used = model
            last_fallback_reason = None
            break
        # The SDK exposes transport, quota, retry, timeout, and response
        # exceptions from several dependency layers. Every one has the same
        # safe outcome here: try the next eligible model, then use grounding.
        except Exception as exc:  # noqa: BLE001
            pool.shutdown(wait=False, cancel_futures=True)
            status = getattr(exc, "status", None) or getattr(exc, "code", None)
            last_fallback_reason = type(exc).__name__
            if status:
                last_fallback_reason += f":{status}"
            continue  # 503/timeouts on one model -> try the next
    if response is None:
        return heuristic
    result = _parse(response.text)
    if result is None:  # malformed despite schema — never trust blindly
        last_fallback_reason = "malformed_model_response"
        return heuristic
    result["source"] = "gemini"
    return Diagnosis(**result)


def _parse(text: str):
    try:
        if not text:
            return None
        text = text.strip()
        # strip markdown fences some modes emit: ```json ... ```
        if text.startswith("```"):
            text = text.strip("`").lstrip("json").strip()
        data = json.loads(text)
        # json_object mode sometimes double-wraps the payload:
        # {"answer": "{...}"} or {"answer": {...}}
        if isinstance(data, dict) and "root_cause" not in data:
            for v in data.values():
                if isinstance(v, str) and v.strip().startswith("{"):
                    data = json.loads(v)
                    break
                if isinstance(v, dict) and "root_cause" in v:
                    data = v
                    break
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
