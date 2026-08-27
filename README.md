# FleetPilot — Governed AIOps for Enterprise Printer Fleets

**All Things Agentic Hackathon · enterprise print-operations POC.**
FleetPilot turns printer, print-server, and job evidence into one grounded
diagnosis, auto-executes a bounded safe fix, and stops risky fleet changes at
the exact line where human judgment belongs.

## The problem
Large printer fleets can scatter one incident across device telemetry, print
servers, queues, jobs, accounts, and change tools. One blocked spooler can fan
out across many queues; firmware automation can stall after a rollout starts.
Vendor firmware and settings watchdog capabilities already exist. FleetPilot
does **not** claim to replace them: this POC demonstrates the governed
correlation and response layer around mixed-fleet telemetry and imperfect
automation.

## The approach
- **Agent proposes, policy engine disposes.** Gemini diagnoses and drafts
  actions; a deterministic policy layer (allowlist, denylist, action caps,
  blast-radius and purchase limits) decides what executes. The LLM never
  bypasses it, and LLM output is validated (allowlisted kinds, known device
  IDs, bounded confidence) before it reaches policy.
- **Topology-aware RCA.** Alerts correlate across device→server→queue
  topology; one root cause collapses many symptoms. A deterministic
  correlator grounds the LLM and serves as the offline/timeout fallback.
- **Evidence before action.** Synthetic job ownership, queue/server scope,
  serial, IP, MAC, current/target firmware, site, contact, last poll, and
  reachability stay attached to the incident and its outcome.
- **Guarded firmware rollouts.** A human-approved push still starts with a
  5-device pilot; a watchdog catches frozen pushes, quarantines stuck
  devices, and aborts before fleet-wide expansion — no automatic expansion.
- **Audited autonomy.** Every observation, diagnosis, gate decision, human
  approval, and watchdog event lands in an append-only, replayable journal.

## Stack
- **Gemini 3.5+** — `gemini-3.5-flash` is the deployed contest primary,
  with 3.6/3.7 failover; the model that actually answers is shown in the
  dashboard health strip, via the **Google GenAI SDK**
- **FastAPI** dashboard, container-verified for **Google Cloud Run**
- SQLite journal (append-only evidence store)

## Layout
```
agent/    Agent core: Gemini diagnosis + deterministic fallback, policy
          engine, rollout watchdog, fleet simulator, audit journal
  policy/ Deterministic risk engine — the LLM never bypasses this
harness/  Eval suite — 11 scenarios / 19 assertions, fully offline
web/      FastAPI dashboard: RCA, job/device evidence, approval gate,
          rollout result, run-isolated journal, health strip
journal/  Append-only audit log (SQLite)
docs/     Task tracker + submission assets
```

See the [architecture diagram](docs/architecture.md) for the deployment flow and
the trust boundary between Gemini proposals and deterministic execution.

## Quickstart
```bash
python3 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # add your Gemini API key
# Eval suite (offline, no API key needed) — 11/11:
.venv/bin/python -m harness.run_evals
# CLI demo (single agent cycle):
.venv/bin/python -m agent.main --demo
# Web dashboard:
.venv/bin/python -m uvicorn web.app:app --port 8080   # → http://localhost:8080
```

## Demo scenarios (dashboard buttons)
- **Queue hang** — 30 jobs stalled across 22 queues on one print server → one
  suspect job identified with synthetic owner/account evidence → that job is
  quarantined → the other 29 jobs are released and alerts clear to zero.
- **Firmware drift (pushes freeze)** — 30 compliance alerts → firmware push
  gated for human approval → 5-device pilot → watchdog catches frozen
  pushes → 3 update attempts quarantined, 2 complete, and 25 remain untouched.
  All 30 printer records remain reachable, separating a management/update
  failure from a network or device-communication outage.
- Additional (kept as evidence, not in the demo video): alert storm, plain
  firmware drift, supplies management with cost-gated purchase orders and a
  POC-notification anti-fatigue cooldown.

## Deploy to Google Cloud Run
The verified deployment uses Vertex AI and the Cloud Run service account; no
Gemini API key is shipped in the service:
```bash
gcloud run deploy fleetpilot \
  --source . \
  --region us-central1 \
  --set-env-vars GEMINI_BACKEND=vertex,GCP_PROJECT_ID=<YOUR_PROJECT_ID>,GCP_REGION=global \
  --allow-unauthenticated
```
`--allow-unauthenticated` is for this synthetic, single-user contest sandbox;
do not use this deployment shape for a real fleet or multi-user environment.

## Safety & evals
The deterministic policy engine enforces: permanent denylist (destructive
actions), per-cycle action cap, blast-radius limit, $250 purchase
auto-approval cap, notification cooldown, and no automatic fleet-wide
expansion after a pilot. `python -m harness.run_evals` proves each guard
fires; all tests run offline with model credentials disabled.

## Status
**DEPLOYED BASELINE + TEST-READY UPDATE:** Cloud Run is live at
<https://fleetpilot-118750462659.us-central1.run.app>. The current evidence
update passes 11/11 offline eval scenarios and 39/39 pytest cases at 87.26%
coverage; both locked workflows pass browser QA with zero console errors. The
update is live on Cloud Run revision `fleetpilot-00003-pmv`.
Gemini passed the strict live gate with three queue and three 30-device
firmware diagnoses at 3.5–6.3 seconds each, without fallback. See
[`CONTEST_PLAN.md`](CONTEST_PLAN.md) and [`docs/TASKS.md`](docs/TASKS.md) for
the current execution plan.

## Disclosure
Every record is synthetic — including people/account labels, documentation-only
`192.0.2.0/24` addresses, locally administered MAC addresses, serials, sites,
and `.invalid` contacts. No printer, print server, customer system, vendor API,
or employer infrastructure is connected. Built for the All Things Agentic
Hackathon.

## License
MIT
