"""FleetPilot dashboard backend — FastAPI.

Endpoints drive the same agent core used by the CLI, so the web demo and the
eval suite exercise identical code paths. Approval decisions made here flow
back through the simulator and journal like any other action.

Browser isolation: each browser gets bounded in-process state, and each
injected scenario starts a new run inside that state. The current-run journal
is a demo view; SQLite on Cloud Run remains ephemeral POC evidence.
"""
import os
import uuid
from collections import OrderedDict
from threading import Lock

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import agent.diagnosis as dm
from agent.fleet_sim import SUPPORTED_SCENARIOS, FleetSimulator
from agent.journal import Journal
from agent.main import run_tick
from agent.policy.risk import PolicyEngine
from agent.rollout import run_firmware_rollout

load_dotenv()

app = FastAPI(title="FleetPilot")


class RunJournal:
    """Writes to the append-only DB (evidence) AND a per-run in-memory list
    (what the dashboard shows)."""

    def __init__(self, db: Journal):
        self.db = db
        self.events: list[dict] = []

    def log(self, kind: str, payload: dict) -> int:
        entry_id = self.db.log(kind, payload)
        self.events.append({"id": entry_id, "kind": kind, "payload": payload})
        return entry_id


class AppState:
    def __init__(self):
        self.sim = FleetSimulator.seed()
        self.policy = PolicyEngine.defaults()
        self.db_journal = Journal("journal/audit.db")
        self.run_journal: RunJournal | None = None
        self.run_id: str | None = None
        self.pending: dict[str, dict] = {}   # approval_id -> {action, reason}
        self.last_summary: dict = {}
        self.rollout_report: dict | None = None
        self.last_model_used: str | None = None
        self.fallback_reason: str | None = None

    def new_run(self) -> str:
        self.sim = FleetSimulator.seed()
        self.policy = PolicyEngine.defaults()
        self.run_id = str(uuid.uuid4())[:8]
        self.run_journal = RunJournal(self.db_journal)
        self.pending = {}
        self.last_summary = {}
        self.rollout_report = None
        self.last_model_used = None
        self.fallback_reason = None
        return self.run_id


state = AppState()
SESSION_HEADER = "X-FleetPilot-Session"
MAX_BROWSER_SESSIONS = 64
browser_states: OrderedDict[str, AppState] = OrderedDict()
browser_states_lock = Lock()


def state_for_request(request: Request) -> AppState:
    """Return bounded state for one browser; headerless scripts use default."""
    raw_session_id = request.headers.get(SESSION_HEADER)
    if raw_session_id is None:
        return state
    try:
        session_id = str(uuid.UUID(raw_session_id))
    except (AttributeError, ValueError):
        raise HTTPException(
            status_code=400, detail="invalid browser session id"
        ) from None

    with browser_states_lock:
        current = browser_states.get(session_id)
        if current is not None:
            browser_states.move_to_end(session_id)
            return current
        if len(browser_states) >= MAX_BROWSER_SESSIONS:
            raise HTTPException(
                status_code=503,
                detail="browser session capacity reached",
            )
        current = AppState()
        browser_states[session_id] = current
        return current


def deployment_details() -> dict:
    return {
        "deployment": "Cloud Run" if os.environ.get("K_SERVICE") else "local",
        "service": os.environ.get("K_SERVICE", "fleetpilot"),
        "revision": os.environ.get("K_REVISION"),
    }


@app.get("/")
def index():
    return FileResponse("web/static/index.html")


@app.get("/health")
def health(request: Request):
    """Runtime liveness probe; model proof exists only after a live run."""
    current = state_for_request(request)
    diagnosis_source = current.last_summary.get("diagnosis_source")
    model_live_verified = diagnosis_source in {"gemini", "glm"}
    return {
        "status": "ok",
        "probe": "liveness",
        "model": dm.model_candidates()[0],
        "model_live_verified": model_live_verified,
        "model_status": ("verified_in_last_run" if model_live_verified
                         else "not_yet_exercised"),
        "diagnosis_source": diagnosis_source,
        "fallback_reason": current.fallback_reason,
        **deployment_details(),
    }


@app.post("/api/scenario/{name}")
def inject(name: str, request: Request):
    if name not in SUPPORTED_SCENARIOS:
        raise HTTPException(status_code=400, detail=f"unknown scenario {name}")
    current = state_for_request(request)
    run_id = current.new_run()
    current.run_journal.log("run_started", {"run": run_id})
    current.sim.inject_scenario(name)
    current.last_summary = run_tick(
        current.sim, current.policy, current.run_journal)
    current.last_model_used = dm.last_model_used
    current.fallback_reason = dm.last_fallback_reason
    for entry in current.last_summary.get("escalated", []):
        approval_id = str(uuid.uuid4())[:8]
        current.pending[approval_id] = entry  # {action, reason}
    current.run_journal.log(
        "approval_queue", {"pending": list(current.pending.keys())})
    return snapshot(current)


@app.post("/api/approve/{approval_id}")
def approve(approval_id: str, request: Request):
    current = state_for_request(request)
    if approval_id not in current.pending:
        raise HTTPException(status_code=404, detail="unknown approval id")
    entry = current.pending.pop(approval_id)
    current.run_journal.log(
        "human_decision",
        {"action": entry["action"], "decision": "APPROVED"},
    )

    if entry["action"].get("kind") == "update_firmware":
        report = run_firmware_rollout(current.sim, current.run_journal,
                                      entry["action"])
        current.rollout_report = report
        current.run_journal.log("rollout_report", report)
        if report["outcome"] == "pilot_clean" and report["remaining_devices"]:
            new_id = str(uuid.uuid4())[:8]
            current.pending[new_id] = {
                "action": {
                    **entry["action"],
                    "devices": report["remaining_devices"],
                    "rationale": "Pilot batch verified clean — expand staged "
                                 "rollout to remaining fleet",
                },
                "reason": "fleet-wide expansion after verified pilot",
            }
    else:
        result = current.sim.execute(entry["action"])
        current.run_journal.log(
            "human_decision_result",
            {"action": entry["action"], "result": result},
        )
    return snapshot(current)


@app.post("/api/reject/{approval_id}")
def reject(approval_id: str, request: Request):
    current = state_for_request(request)
    if approval_id not in current.pending:
        raise HTTPException(status_code=404, detail="unknown approval id")
    entry = current.pending.pop(approval_id)
    current.run_journal.log(
        "human_decision",
        {"action": entry["action"], "decision": "REJECTED"},
    )
    return snapshot(current)


def snapshot(current: AppState) -> dict:
    alerts = current.sim.active_alerts()
    devices = current.sim.devices
    evidence_devices = current.sim.inventory_records(
        current.sim.evidence_device_ids)
    reachable = sum(
        record["communication_status"] == "reachable"
        for record in evidence_devices)
    return {
        "run_id": current.run_id,
        "fleet": {
            "devices": len(devices),
            "servers": sorted({d.server for d in devices}),
            "alerts_open": len(alerts),
            "reachable": sum(d.communication_status == "reachable"
                             for d in devices),
        },
        "evidence": {
            "scenario": current.sim.scenario,
            "synthetic": True,
            "integration_mode": "simulator_only",
            "devices": evidence_devices,
            "print_jobs": current.sim.print_job_records(),
            "network": {
                "scope": len(evidence_devices),
                "reachable": reachable,
                "unreachable": len(evidence_devices) - reachable,
            },
        },
        "alerts": alerts[:200],
        "last_summary": current.last_summary,
        "pending_approvals": [
            {"id": k, "action": v["action"], "reason": v["reason"]}
            for k, v in current.pending.items()
        ],
        "rollout_report": current.rollout_report,
        "health": {
            "model": current.last_model_used or dm.model_candidates()[0],
            "model_candidates": dm.model_candidates(),
            **deployment_details(),
            "diagnosis_source": current.last_summary.get("diagnosis_source"),
            "fallback_active": current.last_summary.get("diagnosis_source")
                               == "heuristic",
            "fallback_reason": current.fallback_reason,
        },
        "journal": (current.run_journal.events
                    if current.run_journal else [])[-50:],
    }


@app.get("/api/state")
def get_state(request: Request):
    return snapshot(state_for_request(request))


@app.post("/api/reset")
def reset(request: Request):
    current = state_for_request(request)
    current.new_run()
    current.run_journal.log(
        "run_started", {"run": current.run_id, "note": "reset"})
    return snapshot(current)


app.mount("/static", StaticFiles(directory="web/static"), name="static")
