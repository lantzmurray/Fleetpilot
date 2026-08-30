## Inspiration

A firmware push that froze mid-rollout on real fleet hardware while every dashboard stayed green. Large printer fleets scatter one incident across device telemetry, print servers, queues, jobs, accounts, and change tools — and the tools that watch each layer independently can all report "fine" while the fleet is broken. FleetPilot is the operator console that would have caught it.

## What it does

FleetPilot turns printer, print-server, queue, job, account, firmware, and reachability evidence into a governed response:

1. **Observe** synthetic fleet alerts and retain the operational evidence.
2. **Correlate** shared server and queue topology before asking Gemini to refine the diagnosis and propose an action.
3. **Validate** model output (allowlisted action kinds, known device IDs, bounded confidence) and ground the exact incident scope before policy runs.
4. **Gate** — deterministic policy auto-runs a bounded low-risk action, requires a human for higher blast radius, or blocks the action.
5. **Verify** by re-observing simulator post-state rather than trusting an execution receipt.
6. **Audit** — every observation, diagnosis, gate decision, approval, action, verification, and watchdog event lands in an append-only journal.

Two proof workflows on the live dashboard:

- **Queue hang** — 30 jobs stalled across 22 pull-release queues on the secure release server collapse to one root cause: a single 1.8 GB non-business job blocking the release spooler. FleetPilot quarantines that one job, releases the other 29, and re-observes zero matching alerts with no collateral clearing — printers stay 200/200 online throughout, because it's a queue-layer incident, not a device one.
- **Guarded firmware rollout** — 30 devices report a firmware baseline mismatch. Gemini proposes the change, policy requires human approval, and approval starts only a 5-printer pilot. Two updates complete, three freeze; the watchdog quarantines the frozen devices, proves 25 printers were untouched, and stops before fleet-wide expansion.

## How I built it

- **Gemini 3.5 Flash on Vertex AI** via the Google GenAI SDK, with service-account authentication — no API key shipped in the service
- **Google Cloud Run** for the deployed service
- **FastAPI** dashboard and API
- Deterministic Python policy engine, fleet simulator, rollout watchdog, and eval harness (11 scenarios / 19 assertions, fully offline)
- SQLite append-only POC journal

The core pattern: **the agent proposes, policy disposes.** Gemini contributes diagnosis and action selection inside a larger action loop — observe → correlate → Gemini → validate → scope → policy → act/gate → verify → audit — and cannot bypass validation, policy, approval, pilot limits, or the watchdog. A labeled deterministic fallback keeps the workflow safe and testable when the model is unavailable.

## Challenges I ran into

- Gemini JSON responses truncated at 1024 tokens, silently breaking diagnosis parsing — fixed by raising the output budget to 8192 and validating output before it reaches policy.
- Cold-start latency on Cloud Run made first diagnoses take ~30s; I added a health/warmup path so rehearsed runs land in the 4–7s range.
- Model hints and executor interpretations could describe narrower or wider incident scopes than the true one — policy had to evaluate the *effective* incident scope, not either claim.
- Making browser sessions isolated within a single unauthenticated POC instance without pretending that was real authentication.

## Accomplishments that I'm proud of

- A pilot that fails safely is a *success*: when devices froze mid-push, FleetPilot proved 25 printers were never touched and refused automatic expansion.
- Post-action verification re-observes state instead of trusting executor receipts — it catches both unresolved work and collateral effects outside the policy-reviewed scope.
- 57 passing tests, 11/11 offline eval scenarios, and repeated hosted runs with live Gemini, no fallback, correct end states.
- The demo video is one continuous unedited take on the live Cloud Run deployment.

## What I learned

- High alert count does not equal high root-cause count; topology must be correlated before action.
- Policy must evaluate the effective incident scope — not a narrower model hint or a wider executor interpretation.
- An executor receipt is not proof. The system must re-observe post-state.
- A failed pilot can be a successful safety outcome when the system proves the remainder was untouched.

## What's next for FleetPilot

Production adapters: authenticated operator sessions, a durable audit store (SQLite on Cloud Run is POC evidence, not production storage), and real vendor/SNMP/HTTPS integrations in place of the synthetic simulator — while keeping the same trust boundary where the model proposes and deterministic policy decides.

---

**Links**

- Live demo: https://fleetpilot-118750462659.us-central1.run.app
- Source: https://github.com/lantzmurray/Fleetpilot
- Demo video: https://youtu.be/tjeV5Zkmsnc
