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
agent/    Custom orchestration, Gemini diagnosis, policy, and scoped tools
  policy/ Deterministic risk engine — the LLM never bypasses this
harness/  Eval scenarios + runner (crash day, alert storm, conflicting signals)
web/      Demo UI (dashboard + approval inbox)
journal/  Append-only audit log (SQLite)
```

## Quickstart
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # add your Gemini API key
# CLI demo (single agent cycle):
.venv/bin/python -m agent.main --demo
# Web dashboard:
.venv/bin/python -m uvicorn web.app:app --port 8080   # → http://localhost:8080
# Eval suite (offline, no API key needed):
.venv/bin/python -m harness.run_evals
```

## Deploy to Google Cloud Run
Create the `fleetpilot-gemini-api-key` secret first, then deploy with the exact
contest-eligible model ID confirmed for your account:
```bash
gcloud run deploy fleetpilot \
  --source . \
  --region us-central1 \
  --set-secrets GEMINI_API_KEY=fleetpilot-gemini-api-key:latest \
  --set-env-vars GEMINI_MODEL="<confirmed Gemini 3.5+ model ID>" \
  --allow-unauthenticated
```

## Status
Working prototype: 10/10 offline eval scenarios pass; the local dashboard and a
live Gemini diagnosis have been exercised. Cloud Run deployment, full web/API
test coverage, and the contest demo gate are still pending. See
[`CONTEST_PLAN.md`](CONTEST_PLAN.md)
for the current execution plan.

*Paper/demo only. Not affiliated with any employer. Demo data is synthetic.*
