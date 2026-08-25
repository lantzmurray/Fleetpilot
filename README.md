# FleetPilot — Audited AIOps Agent for Device-Fleet Incident Triage

An autonomous agent that triages device-fleet incidents (printers, queues, endpoints),
performs topology-aware root-cause analysis, drafts remediations, and executes only
**risk-approved** actions — every decision logged in a replayable audit trail.

Built for the All Things Agentic Hackathon (deadline Aug 31, 5:00 PM PT).

## The problem
Large device fleets (e.g., an 8,000-device print fleet across 4 servers) drown ops
teams in alerts. Most are noise; a few share one root cause. Humans burn hours
correlating manually. Full autonomy isn't trusted — yet.

## The approach
- **Agent proposes, policy engine disposes.** The LLM diagnoses and drafts actions;
  a deterministic policy layer (risk scores, allowlists, rate limits) decides what
  actually executes.
- **Topology-aware RCA.** Alerts are correlated against a device→server→queue
  topology graph so one root cause collapses many symptoms.
- **Audited autonomy.** Every observation, diagnosis, action, and approval is
  written to an append-only journal you can replay and inspect.
- **Human-in-the-loop.** High-risk actions wait for one-click approve/reject.

## Layout
```
agent/    Strands agent core (loop, tools, memory)
  policy/ Deterministic risk engine — the LLM never bypasses this
harness/  Eval scenarios + runner (crash day, alert storm, conflicting signals)
web/      Demo UI (dashboard + approval inbox)
docs/     Architecture diagram, submission assets
journal/  Append-only audit log (SQLite)
```

## Quickstart
```bash
pip install -r requirements.txt
cp .env.example .env   # add keys
python -m agent.main --demo
```

## Status
Scaffold — see `docs/PLAN.md` for the day-by-day build plan.

*Paper/demo only. Not affiliated with any employer. Demo data is synthetic.*
