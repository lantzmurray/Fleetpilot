"""FleetPilot dashboard backend — FastAPI.

Endpoints drive the same agent core used by the CLI, so the web demo and the
eval suite exercise identical code paths. Approval decisions made here flow
back through the simulator and journal like any other action.
"""
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent.diagnosis import Diagnosis
from agent.fleet_sim import FleetSimulator
from agent.journal import Journal
from agent.main import run_tick
from agent.policy.risk import PolicyEngine, Risk

load_dotenv()

app = FastAPI(title="FleetPilot")


class AppState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.sim = FleetSimulator.seed()
        self.policy = PolicyEngine.defaults()
        self.journal = Journal("journal/audit.db")
        self.pending: dict[str, dict] = {}   # approval_id -> action
        self.last_summary: dict = {}
        self.last_diagnosis: Diagnosis | None = None


state = AppState()


@app.get("/")
def index():
    return FileResponse("web/static/index.html")


@app.post("/api/scenario/{name}")
def inject(name: str):
    """Inject a scripted scenario, run one agent cycle, return the result."""
    state.policy = PolicyEngine.defaults()  # reset per-cycle counters
    state.sim.inject_scenario(name)
    state.last_summary = run_tick(state.sim, state.policy, state.journal)
    # stash escalated actions for the approval inbox
    for action in state.last_summary.get("escalated", []):
        approval_id = str(uuid.uuid4())[:8]
        state.pending[approval_id] = action
    state.journal.log("approval_queue", {"pending": list(state.pending.keys())})
    return snapshot()


@app.post("/api/approve/{approval_id}")
def approve(approval_id: str):
    if approval_id not in state.pending:
        return {"error": "unknown approval id"}
    action = state.pending.pop(approval_id)
    result = state.sim.execute(action)
    state.journal.log("human_decision",
                      {"action": action, "decision": "APPROVED", "result": result})
    return snapshot()


@app.post("/api/reject/{approval_id}")
def reject(approval_id: str):
    if approval_id not in state.pending:
        return {"error": "unknown approval id"}
    action = state.pending.pop(approval_id)
    state.journal.log("human_decision", {"action": action, "decision": "REJECTED"})
    return snapshot()


def snapshot() -> dict:
    alerts = state.sim.active_alerts()
    devices = state.sim.devices
    return {
        "fleet": {
            "devices": len(devices),
            "servers": sorted({d.server for d in devices}),
            "alerts_open": len(alerts),
        },
        "alerts": alerts[:200],
        "last_summary": state.last_summary,
        "pending_approvals": [
            {"id": k, "action": v} for k, v in state.pending.items()
        ],
        "journal": state.journal.replay()[-50:],
    }


@app.get("/api/state")
def get_state():
    return snapshot()


@app.post("/api/reset")
def reset():
    state.reset()
    return snapshot()


app.mount("/static", StaticFiles(directory="web/static"), name="static")
