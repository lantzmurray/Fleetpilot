# FleetPilot — Audited AIOps Agent for Device-Fleet Incident Triage

**All Things Agentic Hackathon · Taskmaster category.**
FleetPilot turns a device-fleet alert storm into one topology-aware diagnosis,
auto-executes the safe fix, and stops risky fleet-wide changes at the exact
line where human judgment belongs. A complete governed workflow — not a chatbot.

## The problem
Large device fleets (e.g., a 200-device print fleet across 4 servers) drown ops
teams in alerts. One failed spooler fans out into dozens of device alerts;
firmware pushes freeze mid-rollout and can strand a fleet. Legacy RPA
screen-scrapes device web pages and enumerates every page-state as a
pre-written branch — any unanticipated state fails the run. Monitoring stacks
page humans but don't diagnose. Full autonomy isn't trusted — yet.

## The approach
- **Agent proposes, policy engine disposes.** Gemini diagnoses and drafts
  actions; a deterministic policy layer (allowlist, denylist, action caps,
  blast-radius and purchase limits) decides what executes. The LLM never
  bypasses it, and LLM output is validated (allowlisted kinds, known device
  IDs, bounded confidence) before it reaches policy.
- **Topology-aware RCA.** Alerts correlate across device→server→queue
  topology; one root cause collapses many symptoms. A deterministic
  correlator grounds the LLM and serves as the offline/timeout fallback.
- **Guarded firmware rollouts.** A human-approved push still starts with a
  5-device pilot; a watchdog catches frozen pushes, quarantines stuck
  devices, and aborts before fleet-wide expansion — no automatic expansion.
- **Audited autonomy.** Every observation, diagnosis, gate decision, human
  approval, and watchdog event lands in an append-only, replayable journal.

## Stack
- **Gemini 3.5+** — `gemini-3.6-flash` is the live-verified contest primary,
  with 3.5/3.7 failover; the model that actually answers is shown in the
  dashboard health strip, via the **Google GenAI SDK**
- **FastAPI** dashboard, container-verified for **Google Cloud Run**
- SQLite journal (append-only evidence store)

## Layout
```
agent/    Agent core: Gemini diagnosis + deterministic fallback, policy
          engine, rollout watchdog, fleet simulator, audit journal
  policy/ Deterministic risk engine — the LLM never bypasses this
harness/  Eval suite — 11 scenarios / 19 assertions, fully offline
web/      FastAPI dashboard: alert board, RCA card, approval inbox,
          rollout result card, run-isolated journal, health strip
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
- **Queue hang** — 30 stuck-job alerts → one RCA → allowlisted fix executes
  automatically → board clears to zero.
- **Firmware drift (pushes freeze)** — 30 compliance alerts → firmware push
  gated for human approval → 5-device pilot → watchdog catches frozen
  pushes → devices quarantined, rollout aborted, fleet untouched.
- Additional (kept as evidence, not in the demo video): alert storm, plain
  firmware drift, supplies management with cost-gated purchase orders and a
  POC-notification anti-fatigue cooldown.

## Deploy to Google Cloud Run
Create the `fleetpilot-gemini-api-key` secret first, then deploy with the exact
contest-eligible model ID confirmed for your account:
```bash
gcloud run deploy fleetpilot \
  --source . \
  --region us-central1 \
  --set-secrets GEMINI_API_KEY=fleetpilot-gemini-api-key:latest \
  --set-env-vars GEMINI_MODEL="gemini-3.6-flash" \
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
**TEST-READY locally:** 11/11 offline eval scenarios and 31/31 pytest cases
pass at 85.85% coverage; a fresh environment, five repeated API workflows, the
real browser path, dependency audit, and non-root Docker image are verified.
Gemini 3.6 passed the strict live gate with three queue and three 30-device
firmware diagnoses at 3.5–6.3 seconds each, without fallback. Cloud Run
deployment is pending CLI authentication. See
[`CONTEST_PLAN.md`](CONTEST_PLAN.md) and [`docs/TASKS.md`](docs/TASKS.md) for
the current execution plan.

## Disclosure
Fleet data is synthetic — a sandboxed fleet modeled on real multi-server,
multi-vendor print environments. No real infrastructure or employer systems
are integrated. Built for the All Things Agentic Hackathon.

## License
MIT
