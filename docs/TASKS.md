# FleetPilot Task Tracker — All Things Agentic (submit by Sun Aug 30, hard stop Mon Aug 31 noon PT)

Lane: **Taskmaster** (declared at submission, not before) · Plan: `../CONTEST_PLAN.md`

## Tuesday — smooth & freeze the judge path

- [x] T1: Fix model-resolution bug — `GEMINI_MODEL` read at import time, before `load_dotenv()` runs (both CLI + web paths)
- [x] T2: Pin eligible Gemini 3.5+ model ID — verify against live key; do not infer compliance from name
- [x] T3: Rollout-result card in UI — pilot size, completed, hung/quarantined, untouched, outcome, watchdog checks
- [x] T4: Approval cards show blast radius (device count) + gate reason
- [x] T5: Run/session ID — journal isolation per demo run (append-only history retained)
- [x] T6: Button loading/disabled states — no double-click duplicates
- [x] T7: Health/status strip — model, diagnosis source, fallback state, deployment
- [x] T8: Validate Gemini output before policy — required fields, allowed kinds, known device IDs, bounded confidence
- [x] T9: Deterministic pilot selection for firmware demo (rehearsals always hit the frozen-device path)
- [x] T10: README fixes — drop Strands mention, 5-command quickstart, license, architecture path

**Tuesday exit gate:** browser alone tells both stories — `30 alerts → 1 RCA → safe auto-fix → 0` and `human gate → 5-device pilot → hang → quarantine → abort`.

## Wednesday — test & deploy (no new features unless fixing a failed gate)

- [x] G1: Config + clean-checkout reproducibility (fresh venv, README-only instructions, compile/lint/dependency/secret scans)
- [x] G2: Deterministic suite — 11/11 harness offline + 31/31 pytest at 85.85% coverage
- [x] G3: Web/API integration — full sequence deterministic across 5 runs (incl. stale-approval isolation, 4xx handling)
- [x] G4: Live Gemini stability — 3/3 queue + 3/3 firmware diagnoses, `source:gemini`, 3.5–6.3s, no hangs or fallback (Aug 26)
  - The 1024-token JSON truncation was fixed at 8192; the passing gate used `gemini-3.6-flash` through the API-key backend with 20-second spacing.
- [x] G5: Container + Cloud Run — PASSED Aug 26
  - Service: https://fleetpilot-118750462659.us-central1.run.app · Revision fleetpilot-00001-mz4
  - Commit 59116e2 pushed to github.com/lantzmurray/Fleetpilot · Model gemini-3.5-flash @ Vertex global · service-account auth (no API key shipped)
  - Hosted verification: full 3-scene demo passed in 15.7s (queue hang cleared; firmware gated+approved; pilot aborted, 3 hung/quarantined, 25 untouched)
  - Partial: public GitHub `main`, non-root local image, and browser path pass; blocked on user running `gcloud auth login` and enabling the Cloud Run build/deploy services. Application-default login is needed only if the local gate switches to Vertex.

## Thursday — rehearse & record

- [ ] R1: Warm service; 3 consecutive one-take rehearsals <3:15, Gemini (not fallback), correct end states
- [ ] R2: Record final continuous take at 1× speed, .run.app visible, no cuts; upload pending Saturday

## Friday — freeze

- [ ] F1: Final README (hosted URL, model/framework/cloud details, eval table, disclosures)
- [ ] F2: Architecture diagram matching shipped system

## Saturday — write & submit

- [ ] S1: Devpost write-up (Taskmaster framing), video upload, clean-browser verification, disclosures
- [ ] S2: Submit Saturday evening; save receipt
- [ ] S3 (bonus, only if core done): blog post + #AllThingsAgenticHackathon social

## Release states

- TEST-READY: G1–G3 pass · DEMO-READY: G1–G5 + Thursday rehearsals · SUBMISSION-READY: S1–S2 verified
- **Current: G1–G5 PASSED — DEMO-READY pending Thursday's 3× hosted one-take rehearsals.**
