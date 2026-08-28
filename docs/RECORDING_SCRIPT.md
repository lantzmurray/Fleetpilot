# FleetPilot Demo Recording Script (one continuous take, 1× speed)

Target length **2:45–3:05**. Recording rules: one take, no cuts/trims/overlays,
`.run.app` URL visible at the start, normal speed throughout. If a take fails,
record a complete new take.

**Setup (before hitting record):**
1. Warm the service: `curl -s https://fleetpilot-118750462659.us-central1.run.app/health`
   (first diagnosis after idle can take ~30s cold; warmed runs are 5–10s).
   `/health` proves runtime liveness; the live Gemini proof appears after each
   scenario in the dashboard source label.
2. Open the URL in a clean browser window, zoom ~125% for legibility.
3. Start at the dashboard with **0 alerts, 0 approvals** (click **New Run** if needed).
4. Screen recorder at 1080p+, mic on, notifications off.

## Click path (4 clicks) + spoken lines

| Time | Action on screen | Say |
| --- | --- | --- |
| 0:00–0:15 | Show the `.run.app` address bar and clean dashboard; point at health strip (model, Cloud Run revision) | "Thirty device alerts can be one server problem. FleetPilot diagnoses and acts, but risky changes stay governed." |
| 0:15 | **Click "Queue Hang"** | "This synthetic incident produces thirty stuck-job alerts across twenty-two queues." |
| 0:15–0:50 | Wait for the live Gemini RCA (5–10s warmed); show the suspect job and **Simulator outcome verified** card | "Gemini correlates one server-level cause. Policy permits the fix; FleetPilot quarantines one suspect job, releases twenty-nine, and re-checks zero alerts remain." |
| 0:50 | Point at alert counter = 0; **click "New Run"** | "Alerts at zero. Now the failure mode that motivated this build." |
| 0:55 | **Click "Guarded Firmware Rollout"** | "Thirty devices need firmware, but this action has fleet-wide blast radius." |
| 0:55–1:30 | Wait for RCA (~7s); show the approval card: 30-device scope, blast-radius count, gate reason | "Gemini proposes the remediation. Deterministic policy stops it for human approval." |
| 1:30 | **Click "Approve Pilot"** | "Approval starts only a five-device pilot." |
| 1:30–2:05 | Show **Safe abort confirmed · simulator**: 5-device pilot, 2 compliant, 3 quarantined, 25 untouched, expansion not started | "The watchdog catches frozen pushes, quarantines those attempts, and verifies the simulator stopped before expansion." |
| 2:05–2:35 | Scroll the audit journal: run ID, proposal, policy decision, approval, action, watchdog, outcome | "The audit records the proposal, policy decision, approval, action, watchdog, and outcome." |
| 2:35–2:55 | Hold final state; optionally show health strip again (source: Gemini, no fallback) | "FleetPilot completes safe work automatically and stops exactly where human judgment belongs." |

## Do NOT show
- Supplies / alert-storm / plain firmware-drift scenarios
- Repository layout, terminal, test suite, every policy rule
- Any error, reload, or re-take (start over instead)

## End states to verify before stopping the take
- Queue run: 30 → 0 alerts, 29 jobs released, 1 quarantined, simulator outcome verified
- Firmware run: 1 approval gated → pilot of 5 → 2 completed / 3 quarantined / 25 untouched → outcome aborted, no expansion approval queued
- Health strip: `gemini-3.5-flash`, source `gemini`, fallback OFF

## Hands-on click guide (exploring the app yourself)
Same four buttons in order — **Queue Hang → New Run → Guarded Firmware Rollout → Approve Pilot**.
Each scenario button starts a fresh run (new run ID; journal shows only the current run — history
stays in the POC database until the Cloud Run instance recycles). Try **Reject** on the approval, the "Additional scenarios" section,
and the `/health` endpoint to see the fallback/degradation story.
