"""FleetPilot dashboard backend — FastAPI.

Endpoints drive the same agent core used by the CLI, so the web demo and the
eval suite exercise identical code paths. Approval decisions made here flow
back through the simulator and journal like any other action.

Run isolation: each injected scenario starts a new run; the UI journal shows
only the current run, while the append-only SQLite journal retains the full
history as evidence.
"""
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
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
def health():
    """Runtime liveness probe; model proof exists only after a live run."""
    diagnosis_source = state.last_summary.get("diagnosis_source")
    model_live_verified = diagnosis_source in {"gemini", "glm"}
    return {
        "status": "ok",
        "probe": "liveness",
        "model": dm.model_candidates()[0],
        "model_live_verified": model_live_verified,
        "model_status": ("verified_in_last_run" if model_live_verified
                         else "not_yet_exercised"),
        "diagnosis_source": diagnosis_source,
        "fallback_reason": state.fallback_reason,
        **deployment_details(),
    }


@app.post("/api/scenario/{name}")
def inject(name: str):
    if name not in SUPPORTED_SCENARIOS:
        raise HTTPException(status_code=400, detail=f"unknown scenario {name}")
    run_id = state.new_run()
    state.run_journal.log("run_started", {"run": run_id})
    state.sim.inject_scenario(name)
    state.last_summary = run_tick(state.sim, state.policy, state.run_journal)
    state.last_model_used = dm.last_model_used
    state.fallback_reason = dm.last_fallback_reason
    for entry in state.last_summary.get("escalated", []):
        approval_id = str(uuid.uuid4())[:8]
        state.pending[approval_id] = entry  # {action, reason}
    state.run_journal.log("approval_queue",
                          {"pending": list(state.pending.keys())})
    return snapshot()


@app.post("/api/approve/{approval_id}")
def approve(approval_id: str):
    if approval_id not in state.pending:
        raise HTTPException(status_code=404, detail="unknown approval id")
    entry = state.pending.pop(approval_id)
    state.run_journal.log("human_decision",
                          {"action": entry["action"], "decision": "APPROVED"})

    if entry["action"].get("kind") == "update_firmware":
        report = run_firmware_rollout(state.sim, state.run_journal,
                                      entry["action"])
        state.rollout_report = report
        state.run_journal.log("rollout_report", report)
        if report["outcome"] == "pilot_clean" and report["remaining_devices"]:
            new_id = str(uuid.uuid4())[:8]
            state.pending[new_id] = {
                "action": {
                    **entry["action"],
                    "devices": report["remaining_devices"],
                    "rationale": "Pilot batch verified clean — expand staged "
                                 "rollout to remaining fleet",
                },
                "reason": "fleet-wide expansion after verified pilot",
            }
    else:
        result = state.sim.execute(entry["action"])
        state.run_journal.log("human_decision_result",
                              {"action": entry["action"], "result": result})
    return snapshot()


@app.post("/api/reject/{approval_id}")
def reject(approval_id: str):
    if approval_id not in state.pending:
        raise HTTPException(status_code=404, detail="unknown approval id")
    entry = state.pending.pop(approval_id)
    state.run_journal.log("human_decision",
                          {"action": entry["action"], "decision": "REJECTED"})
    return snapshot()


def snapshot() -> dict:
    alerts = state.sim.active_alerts()
    devices = state.sim.devices
    evidence_devices = state.sim.inventory_records(
        state.sim.evidence_device_ids)
    reachable = sum(
        record["communication_status"] == "reachable"
        for record in evidence_devices)
    return {
        "run_id": state.run_id,
        "fleet": {
            "devices": len(devices),
            "servers": sorted({d.server for d in devices}),
            "alerts_open": len(alerts),
            "reachable": sum(d.communication_status == "reachable"
                             for d in devices),
        },
        "evidence": {
            "scenario": state.sim.scenario,
            "synthetic": True,
            "integration_mode": "simulator_only",
            "devices": evidence_devices,
            "print_jobs": state.sim.print_job_records(),
            "network": {
                "scope": len(evidence_devices),
                "reachable": reachable,
                "unreachable": len(evidence_devices) - reachable,
            },
        },
        "alerts": alerts[:200],
        "last_summary": state.last_summary,
        "pending_approvals": [
            {"id": k, "action": v["action"], "reason": v["reason"]}
            for k, v in state.pending.items()
        ],
        "rollout_report": state.rollout_report,
        "health": {
            "model": state.last_model_used or dm.model_candidates()[0],
            "model_candidates": dm.model_candidates(),
            **deployment_details(),
            "diagnosis_source": state.last_summary.get("diagnosis_source"),
            "fallback_active": state.last_summary.get("diagnosis_source")
                               == "heuristic",
            "fallback_reason": state.fallback_reason,
        },
        "journal": (state.run_journal.events if state.run_journal else [])[-50:],
    }


@app.get("/api/state")
def get_state():
    return snapshot()


@app.post("/api/reset")
def reset():
    state.new_run()
    state.run_journal.log("run_started", {"run": state.run_id, "note": "reset"})
    return snapshot()


app.mount("/static", StaticFiles(directory="web/static"), name="static")
