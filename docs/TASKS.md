# FleetPilot Task Tracker — All Things Agentic (submit by Sun Aug 30, hard stop Mon Aug 31 noon PT)

Product story: **enterprise printer-fleet AIOps**. Contest track:
**Taskmaster**. The track describes the complete workflow; it does not turn the
product into a task-management app. Plan: `../CONTEST_PLAN.md`

## Tuesday — smooth & freeze the judge path

- [x] T1: Fix model-resolution bug — `GEMINI_MODEL` read at import time, before `load_dotenv()` runs (both CLI + web paths)
- [x] T2: Pin eligible Gemini 3.5+ model ID — verify against live key; do not infer compliance from name
- [x] T3: Rollout-result card in UI — pilot size, completed, hung/quarantined, untouched, outcome, watchdog checks
- [x] T4: Approval cards show blast radius (device count) + gate reason
- [x] T5: Run/session ID — current-run journal view inside the single-operator process (prior events retained until instance recycle)
- [x] T6: Button loading/disabled states — no double-click duplicates
- [x] T7: Health/status strip — model, diagnosis source, fallback state, deployment
- [x] T8: Validate Gemini output before policy — required fields, allowed kinds, known device IDs, bounded confidence
- [x] T9: Deterministic pilot selection for firmware demo (rehearsals always hit the frozen-device path)
- [x] T10: README fixes — drop Strands mention, 5-command quickstart, license, architecture path

**Tuesday exit gate:** browser alone tells both stories — `30 alerts → 1 RCA → safe auto-fix → 0` and `human gate → 5-device pilot → hang → quarantine → abort`.

## Wednesday — test & deploy (no new features unless fixing a failed gate)

- [x] G1: Config + clean-checkout reproducibility (fresh venv, README-only instructions, compile/lint/dependency/secret scans)
- [x] G2: Deterministic suite — 11/11 harness offline + 45/45 pytest at 91.90% coverage
- [x] G3: Web/API integration — full sequence deterministic across 5 runs (incl. stale-approval isolation, 4xx handling)
- [x] G4: Live Gemini stability — 3/3 queue + 3/3 firmware diagnoses, `source:gemini`, 3.5–6.3s, no hangs or fallback (Aug 26)
  - The 1024-token JSON truncation was fixed at 8192; the passing gate used `gemini-3.6-flash` through the API-key backend with 20-second spacing.
- [x] G5: Container + Cloud Run — PASSED Aug 26
  - Service: https://fleetpilot-118750462659.us-central1.run.app · Revision fleetpilot-00001-mz4
  - Commit 59116e2 pushed to github.com/lantzmurray/Fleetpilot · Model gemini-3.5-flash @ Vertex global · service-account auth (no API key shipped)
  - Hosted verification: full 3-scene demo passed in 15.7s (queue hang cleared; firmware gated+approved; pilot aborted, 3 hung/quarantined, 25 untouched)
- [x] G6: Realistic synthetic evidence — 30 jobs / 22 queues with owner and account; 200 printer records with serial/IP/MAC/site/contact; current→target firmware; reachability and last-poll state (Aug 27)
  - Local: 39/39 pytest at 87.26%, 11/11 eval scenarios, code/security review clear, both browser paths at zero console errors.
  - Hosted: commit `4221ab2`, revision `fleetpilot-00003-pmv`, Vertex/Gemini queue path 4.13s (30 alerts cleared, 29 jobs released), firmware diagnosis 6.81s (2 completed, 3 quarantined, 25 untouched, all 30 reachable).
- [x] G7: Judge-challenge hardening — re-observed synthetic outcomes, collateral-scope detection, empty-pilot rejection, distinct action/verification audit events, all-backend offline isolation, and honest liveness/model-proof labels (Aug 28)

## Thursday — rehearse & record

- [x] R1: Warm service; 3 consecutive one-take rehearsals <3:15, Gemini (not fallback), correct end states (Aug 27)
  - `scripts/rehearse_hosted.py` vs revision `fleetpilot-00003-pmv`: 3/3 full sequences passed.
    Queue diagnoses 33.8s cold / 4.7–9.7s warmed; firmware 6.9–8.7s; all `source:gemini`,
    `gemini-3.5-flash` @ Vertex, no fallback. End states each run: 30→0 alerts, 29 released /
    1 quarantined job; pilot 5 (2 completed, 3 quarantined, 25 untouched), outcome `aborted`,
    no auto-expansion, run IDs isolated.
- [ ] R2: Record final continuous take at 1× speed, .run.app visible, no cuts; upload pending Saturday

## Friday — freeze

- [x] F1: Final README (hosted URL, model/framework/cloud details, proof table, disclosures)
- [x] F2: Architecture diagram matching shipped system and POC limits

## Saturday — write & submit

- [ ] S1: Paste prepared Devpost write-up, add video URL, clean-browser verification, disclosures
- [ ] S2: Submit Saturday evening; save receipt
- [ ] S3 (bonus, only if core done): blog post + #AllThingsAgenticHackathon social

## Release states

- TEST-READY: G1–G3 pass · DEMO-READY: G1–G5 + Thursday rehearsals · SUBMISSION-READY: S1–S2 verified
- **Current: G1–G7 + R1 + F1–F2 PASSED. Deploy/hosted recheck, R2 recording, and S1–S2 remain.**
