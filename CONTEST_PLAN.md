# FleetPilot Contest Execution Plan

*Authoritative plan as of Friday, August 28, 2026 · Submission deadline: Monday, August 31, 5:00 PM PT / 8:00 PM ET*

## Contest position

**Product/domain: Enterprise printer-fleet operations**

**Contest track: Taskmaster.** This is a complete operational workflow, not a
task-management product. Enterprise printer fleets remain the product domain.

**Also eligible for:** Individual/Hobbyist and Best Architectural Design  
**One-sentence pitch:** FleetPilot turns a device-fleet alert storm into one topology-aware diagnosis, safely completes low-risk remediation, and stops risky firmware rollouts before they become fleet-wide outages.

The entry should make three narrow claims:

- **Enterprise fleet friction:** one infrastructure failure produces dozens of device alerts, and firmware pushes can freeze halfway through a fleet.
- **Evidence-led completion:** FleetPilot correlates 30 jobs across 22 queues to one shared print-server incident, isolates a suspect job, executes the allowlisted remediation, and verifies that alerts clear.
- **Governed change orchestration:** existing vendor firmware/settings capabilities are inputs, not competitors; FleetPilot adds approval, pilot scope, watchdog evidence, quarantine, and abort behavior when automation stalls.

## Verified contest constraints

- Every category must use Gemini 3.5 or newer through Gemini API or Vertex AI, at least one accepted Google agent framework (including GenAI SDK), and at least one Google Cloud infrastructure service.
- Submit a category, description, repository with reproducible setup, architecture diagram, and an approximately four-minute demo.
- The video must be no longer than four minutes; only the first four minutes may be evaluated.
- The video must show live, unedited execution and visible Google Cloud proof, such as a `.run.app` URL or Cloud Run console/logs.
- A Devpost manager said a uniform speed-up of one continuous recording generally reads as unedited if disclosed. The safer target remains one continuous take at normal speed with no cuts, splices, overlays, or inserted footage.
- Projects must have been created during the submission period. Disclose any pre-existing work incorporated into the project.

Official references: [contest overview](https://allthingsagentichackathon.devpost.com/) · [rules](https://allthingsagentichackathon.devpost.com/rules) · [unedited-video clarification](https://allthingsagentichackathon.devpost.com/forum_topics/44809-demo-video-is-speeding-up-the-whole-recording-allowed-under-unedited)

## Actual progress through August 28

### Verified locally

- Synthetic 200-device/four-server fleet simulator.
- Topology-aware RCA with a live Gemini path and deterministic fallback.
- FastAPI dashboard with alert board, RCA result, approval inbox, and audit journal.
- Deterministic policy: allowlist, denylist, action cap, blast-radius gate, purchase cap, and notification cooldown.
- Staged firmware rollout: five-device pilot, watchdog, abort, quarantine, and no automatic fleet-wide expansion.
- Gemini timeout guard degrades to the heuristic path instead of hanging indefinitely.
- Offline harness passes **11/11 scenarios**; pytest passes **45/45** at **91.90% coverage**.
- Post-action verification re-observes simulator state, detects unresolved
  targeted alerts and collateral clearing, and explicitly reports that no
  external system was verified.
- A fresh virtual environment completes the README eval, CLI, and web quickstart.
- The full API sequence passes five consecutive local runs with isolated run IDs.
- The real browser path proves queue remediation plus the guarded 5-device abort.
- `gemini-3.6-flash` is live-verified and pinned; warmed queue and firmware
  diagnoses completed under 15 seconds with the expected 30-device scope.
- The strict live stability gate passes **6/6**: three queue and three firmware
  diagnoses used Gemini at **3.5–6.3 seconds** each with no fallback.
- The non-root Python 3.12 image passes health, both workflows, 4xx handling,
  and all 11 offline eval scenarios.

### Hosted proof

- Cloud Run deployment passed on August 26; the public service completed the
  prior three-scene workflow in 15.7 seconds on Vertex AI.
- The realistic evidence update is deployed from commit `4221ab2` on revision
  `fleetpilot-00003-pmv`. Hosted Vertex/Gemini verification cleared all 30
  queue alerts in 4.13 seconds and produced the guarded 2-completed /
  3-quarantined / 25-untouched firmware outcome in 6.81 seconds; all 30 pilot
  evidence records remained reachable.

## Locked demo story

The judged demo uses exactly two scenarios:

1. **Queue hang:** 30 synthetic jobs across 22 queues collapse into one Gemini RCA; one suspect job retains owner/account evidence; policy permits a low-risk remediation; FleetPilot quarantines it, releases the 29-job backlog, and verifies zero alerts remain. This proves a complete operational workflow, not a chatbot.
2. **Guarded firmware rollout:** 30 compliance alerts produce a firmware proposal; policy requires approval; approval starts only a five-device pilot; the watchdog catches frozen pushes, quarantines affected devices, aborts expansion, and leaves the rest of the fleet untouched. This proves failure tolerance and governed autonomy.

Supplies and alert storm remain test/README evidence. Do not tour them in the video.

## Dependency-ordered work plan

### Tuesday night — smooth and freeze the judge path

**Goal:** make both outcomes obvious without lengthy narration.

- Keep the product story enterprise fleet; submit in Taskmaster because the
  agent completes the governed workflow end to end.
- Add a persistent rollout-result card showing pilot size, completed count, hung/quarantined devices, untouched count, outcome, and watchdog checks.
- Show the approval's device count/blast radius and the reason it was gated.
- Give each demo run a run/session ID and display only the current run's journal
  by default. Within this single-operator POC process, retain prior journal
  events until the Cloud Run instance is recycled.
- Put Queue Hang and Guarded Firmware Rollout first. Move other scenarios under “Additional scenarios.”
- Add loading/disabled button states so double-clicks cannot duplicate incidents or approvals.
- Add a health/status strip that reports deployment, diagnosis source, configured model, and fallback state truthfully.
- Validate Gemini output before policy evaluation: required fields, allowed action, known device IDs, bounded confidence, and safe device count.
- Make the firmware demo's pilot selection deterministic after Gemini proposes the action, so rehearsals always exercise the known frozen-device failure path.
- Confirm and pin an exact contest-eligible Gemini 3.5+ model ID.
- Fix the current import-time model resolution so `.env` and Cloud Run's
  `GEMINI_MODEL` value are loaded before the diagnosis module selects a model.
- Correct README setup/status drift and add the missing secret-free example/configuration, license, and architecture path if absent.

**Tuesday exit gate:** the browser alone communicates both `30 alerts → one RCA → safe auto-fix → 0 alerts` and `human gate → 5-device pilot → hang detected → quarantine → expansion aborted`.

### Wednesday — test and deploy

No new product features after testing begins unless they fix a failed gate.

#### Gate 1: configuration and clean-checkout reproducibility

- Confirm the model ID, framework, Cloud Run service, environment variables, and secret handling.
- Install from a fresh virtual environment using only repository instructions.
- Ensure every README command and referenced file exists.
- Run compilation, dependency, lint, and secret scans.

**Pass:** no Strands/AWS claims remain; no secrets are committed; clean quickstart succeeds.

#### Gate 2: deterministic unit/eval suite

- Retain the current 11-scenario harness with every live model backend and
  credential disabled.
- Add pytest coverage for correlation, empty alerts, policy controls, clean/frozen pilots, quarantine, and no automatic expansion.
- Mock Gemini paths: valid response, malformed JSON, invalid action/device, timeout, quota/error, and labeled deterministic fallback.
- Measure coverage and reach at least 80% for the submitted code.

**Pass:** all tests pass twice; harness is 10/10; coverage is at least 80%; offline tests require no network.

#### Gate 3: web/API integration

Automate the actual FastAPI sequence:

- health/state returns 200;
- new demo run begins with 200 devices, zero alerts, zero approvals, and a current-run journal;
- queue hang produces one relevant remediation and ends with zero alerts;
- firmware-freeze produces one relevant human-gated action;
- approval runs only a five-device pilot and reports the expected abort/quarantine outcome;
- invalid scenario and approval IDs return clear 4xx responses;
- a second run cannot inherit stale approvals or visible events from the first.

**Pass:** the full API sequence is deterministic across five local runs.

#### Gate 4: live Gemini stability

- Run three consecutive queue and firmware diagnoses against the pinned contest model.
- Capture model, source, elapsed time, action kind, affected devices, and fallback reason.
- Use a tested SDK timeout that keeps the whole video under four minutes. Target a warmed response under 15 seconds. Never silently label a fallback as Gemini.

**Pass:** 3/3 runs per scenario produce safe, relevant proposals with `source: gemini`; no run hangs.

#### Gate 5: container and Cloud Run

- Build and run the exact Docker image locally; test UI and both workflows.
- Configure a Git remote and push the exact demo commit.
- Deploy one Cloud Run service with the Gemini key supplied through environment/secret configuration.
- Verify the public `.run.app` URL, current revision/commit, live Gemini path,
  health/status strip, current-run journal view, and logs.
- Record the service URL, region, revision, and commit SHA.

**Pass:** three consecutive hosted rehearsals finish inside the demo budget and visibly show Google Cloud, the eligible Gemini model, queue remediation, and firmware-abort evidence.

**Wednesday hard gate:** do not call the project demo-ready unless all five gates pass. If Cloud Run is blocked, Thursday starts with deployment recovery, not recording.

### Thursday — rehearse and record

#### Rehearsal gate

- Warm the Cloud Run service.
- Open the `.run.app` URL and create a fresh demo run before timing.
- Complete three consecutive one-take rehearsals at normal speed.
- Each must finish under 3:15, use Gemini rather than fallback, and end with the expected states.
- Use one browser window and four intentional clicks: Queue Hang, Reset/New Run, Guarded Firmware Rollout, Approve Pilot.

**Pass:** 3/3 rehearsals are correct, legible, and under 3:15.

#### Recording rule

- Record one continuous take at 1× speed.
- Keep the `.run.app` address visible long enough to prove Google Cloud.
- No slides, terminal switching, cuts, stitched clips, trimmed waits, or hidden errors.
- If a take fails, stop and record a complete new take.
- Uniform speed-up with a disclosure is last-resort only.

## Tight demo run-of-show (target 2:45–3:05)

| Time | Screen/action | Spoken point |
| --- | --- | --- |
| 0:00–0:15 | Cloud Run URL and clean dashboard | “Thirty device alerts can be one server problem. FleetPilot diagnoses and acts, but risky changes remain governed.” |
| 0:15 | Click **Queue Hang** | “This synthetic incident produces 30 stuck-job alerts.” |
| 0:15–0:50 | Live Gemini RCA and completed action | “Gemini correlates one server-level cause. Policy permits the low-risk fix, FleetPilot executes it, and all 30 alerts clear.” |
| 0:50 | Click **New Run** | “Now the failure mode that motivated this build.” |
| 0:55 | Click **Guarded Firmware Rollout** | “Thirty devices need firmware, but this action has fleet-wide blast radius.” |
| 0:55–1:30 | Live RCA and approval card | “Gemini proposes the remediation. Deterministic policy stops it for human approval.” |
| 1:30 | Click **Approve Pilot** | “Approval starts only a five-device pilot.” |
| 1:30–2:05 | Rollout result | “The watchdog catches frozen pushes, quarantines those devices, and aborts before expansion.” |
| 2:05–2:35 | Audit journal/status | “The audit records the proposal, policy decision, approval, action, watchdog, and outcome.” |
| 2:35–2:55 | Hold final state | “FleetPilot completes safe work automatically and stops exactly where human judgment belongs.” |

Do not narrate the repository layout, every policy rule, every scenario, or every test. Put those in the README and submission text.

## Friday through submission

### Friday

- Freeze features.
- Finalize README: five-command quickstart, hosted URL, model/framework/cloud details, eval table, failure behavior, and synthetic/public-safe disclosure.
- Add one clean architecture diagram that matches the shipped system.
- Record exact test commands and coverage.

### Saturday

- Write the Devpost description around enterprise print operations, governed autonomy, and the two locked workflows.
- Upload the continuous-take video publicly to YouTube or Vimeo.
- Verify repository access, license, setup, diagram, video, and hosted endpoint from a clean/incognito browser.
- Disclose pre-existing work if any was incorporated.

### Sunday

- Run the final deployed-commit verification.
- Submit Sunday evening and save the confirmation receipt.

### Monday

- Emergency buffer only. Internal hard stop: noon PT.

## Scope freeze

### Must ship

- Enterprise printer-fleet queue remediation with job/account evidence.
- Gemini-backed guarded firmware workflow on Cloud Run.
- Deterministic policy, approval, pilot, watchdog, quarantine, and abort.
- Clear current-run audit trail.
- Automated offline, API, failure, container, and deployed tests.
- Short unedited video, accurate README, license, and architecture diagram.

### Keep in repo, omit from demo

- Alert-storm correlation.
- Toner/paper workflows and cooldown.
- Clean firmware-pilot expansion proposal.

### Do not build before submission

- Multi-agent orchestration merely to chase the Fortified category.
- Authentication, multi-user tenancy, Firestore, or real device integrations.
- Mobile UI, voice, fine-tuning, bonus models, or extra dashboards.
- Blog/social bonus work before the core submission is complete.

## Literal release states

- **TEST-READY:** configuration, deterministic, and web integration gates pass locally.
- **DEMO-READY:** every Wednesday gate plus three Thursday Cloud Run rehearsals pass.
- **SUBMISSION-READY:** video, README, diagram, hosted revision, repository access, disclosures, and Devpost fields are verified.

**Current state on August 28: runtime and materials are demo-ready locally;
the new revision still requires hosted verification. The entry is not
submission-ready until the continuous video is uploaded and Devpost is
submitted.**
