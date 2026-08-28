# FleetPilot Demo Recording Script (one continuous take, 1× speed)

Target length **2:50–3:30**. Recording rules: one take, no cuts/trims/overlays,
`.run.app` URL visible at the start, normal speed throughout. If a take fails,
record a complete new take.

**Setup (before hitting record):**
1. Warm the service: `curl -s https://fleetpilot-118750462659.us-central1.run.app/health`
   (first diagnosis after idle can take ~30s cold; warmed runs are 5–10s).
   `/health` proves runtime liveness; the live Gemini proof appears after each
   scenario in the dashboard source label.
2. Open the URL in a clean browser window, zoom ~125% for legibility.
3. Start at the Dashboard tab with **all-green donuts** (click **New Run** if
   needed): 200/200 printers, 4/4 servers, 0 alerts, 100% firmware.
4. Screen recorder at 1080p+, mic on, notifications off.

Timing note: each scenario click now runs in two phases — the incident lands
**red** for ~3.5s ("Analyzing incident…" pulse) while the live Gemini call
runs, then the dashboard returns to green. Narrate the red state while it is
on screen; do not talk over the resolution with silence.

## Click path (4 clicks) + spoken lines

| Time | Action on screen | Say |
| --- | --- | --- |
| 0:00–0:15 | Show the `.run.app` address bar; all-green donuts; point at health strip (model, Cloud Run revision) | "This fleet runs two hundred printers. The dashboard opens all green — and the failure that built this product was a firmware push that froze mid-rollout while every dashboard stayed green. FleetPilot diagnoses and acts, but risky changes stay governed." |
| 0:15–0:25 | Cursor over the sidebar tabs: Printers, Queues, Firmware | "Pull printing matters here: the east server holds jobs centrally until a user badges at a device — so one stuck job can stall every release queue behind it. Keep that in mind." |
| 0:25 | **Click "Queue hang · 22 pull queues"** | "Injecting that incident now." |
| 0:25–0:35 | Donuts flip: 30 alerts red, east server drops to 3/4 — printers STAY 200/200, firmware stays 100% | "Watch the donuts. Thirty alerts open and the release server degrades — but the printers themselves are fine. This is a queue-layer incident, not a device or firmware one." |
| 0:35–0:55 | "Analyzing incident…" pulse while Gemini runs; then donuts return green, RCA card lands, **Quarantine panel** shows the suspect job | "Gemini correlates one root cause: a single 1.8 GB non-business job blocking the release spooler. Policy permits the low-risk fix — FleetPilot quarantines that one job, releases the other twenty-nine, and re-checks: zero alerts, verified, not assumed. And the resolution left evidence — the suspect job sits in quarantine with its owner, account, and queue." |
| 0:55–1:00 | Queues tab: red "1 quarantined" badge on the suspect's queue; back to Dashboard; **click New Run** | "The queue keeps a quarantine badge. Now the failure mode that motivated this build." |
| 1:00 | **Click "Guarded firmware rollout"** | "Thirty devices need firmware. This action has fleet-wide blast radius." |
| 1:00–1:10 | Donuts flip: firmware compliance drops to 170/200, 30 alerts | "Compliance drops, alerts open — and this time the fix is irreversible, so the architecture changes." |
| 1:10–1:25 | Resolve lands on the **approval card**: 30-device scope, gate reason | "Gemini proposes the remediation. Deterministic policy stops it for human approval — FleetPilot never auto-runs firmware." |
| 1:25 | **Click "Approve 5-printer pilot"** | "Approval starts only a five-device pilot. Not the fleet." |
| 1:25–2:05 | **Safe abort confirmed** card: 5-device pilot, 2 compliant, 3 quarantined, 25 untouched, expansion not started; Quarantine panel lists the frozen devices; Firmware tab shows push-target badges | "The pilot starts — and devices freeze mid-push. The watchdog catches it, quarantines the frozen three, and proves twenty-five printers were never touched. Rollout aborted, expansion stopped. That card is the whole product." |
| 2:05–2:35 | Scroll the audit journal: run ID, injection, proposal, policy decision, approval, action, watchdog, outcome | "Every step is in the append-only audit journal — the proposal, the policy decision, the approval, the action, the watchdog, the verified outcome." |
| 2:35–2:55 | Hold final state; health strip: source `gemini`, fallback OFF | "FleetPilot completes safe work automatically — and stops exactly where human judgment belongs." |

## Do NOT show
- Additional scenarios (alert storm, plain firmware drift, supplies)
- Repository layout, terminal, test suite, every policy rule
- Reports / Administration / Settings tabs (read-only POC pages)
- Any error, reload, or re-take (start over instead)

## End states to verify before stopping the take
- Queue run: red incident (30 alerts, 22 stalled queues, 3/4 servers) → green; 29 jobs released, 1 quarantined in the Quarantine panel; queue badge visible; simulator outcome verified
- Firmware run: compliance 170/200 → approval gated → pilot of 5 → 2 completed / 3 quarantined / 25 untouched → outcome aborted, no expansion approval queued; frozen devices in Quarantine panel
- Health strip: `gemini-3.5-flash` (or cascade model), source `gemini`, fallback OFF
