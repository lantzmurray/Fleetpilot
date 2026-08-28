# FleetPilot — Devpost Submission Copy

## Track

**The Taskmaster**

FleetPilot is an enterprise printer-fleet operations product entered in the
Taskmaster track because it completes a messy, multi-step incident workflow.
It is not a task-management application and does not claim the multi-agent
institutional platform required by the Fortified Enterprise Fleet track.

Secondary prize fit: **Individual/Hobbyist** and **Best Architectural Design**.

## Tagline

One printer-fleet incident, one grounded diagnosis, and exactly the amount of
autonomy the evidence can support.

## What it does

FleetPilot turns scattered printer, print-server, queue, job, account,
firmware, and reachability evidence into a governed response:

1. Observe synthetic fleet alerts and retain the operational evidence.
2. Correlate shared server and queue topology before asking Gemini to refine
   the diagnosis and propose an action.
3. Validate model output and ground the exact incident scope before policy.
4. Let deterministic policy auto-run a bounded low-risk action, require a
   human for higher blast radius, or block the action.
5. Re-observe simulator post-state rather than trusting an execution receipt.
6. Record observation, diagnosis, gate, action, verification, approval, and
   watchdog events in the POC journal.

## Two proof workflows

### Queue hang

Thirty synthetic jobs across twenty-two queues on one print server appear as
thirty device alerts. FleetPilot identifies one suspect 1.8 GB non-business
print job with an owner and account code, grounds the server incident scope,
quarantines the suspect job, releases the other twenty-nine jobs, and
re-observes zero matching alerts with no collateral alert clearing.

### Guarded firmware rollout

Thirty printers report a synthetic firmware baseline mismatch. Gemini proposes
the change, deterministic policy requires human approval, and approval starts
only a five-printer pilot. Two simulated updates complete; three freeze. The
watchdog quarantines the failed attempts, confirms twenty-five printers were
untouched, and stops before fleet-wide expansion.

## Why it is agentic

This is not a chat interface. Gemini contributes diagnosis and action
selection inside a larger action loop:

`observe → correlate → Gemini → validate → scope → policy → act/gate → verify → audit`

Gemini cannot bypass validation, policy, approval, pilot limits, or the
watchdog. A labeled deterministic fallback keeps the workflow safe and
testable when the model is unavailable.

## Technology

- Gemini 3.5+ on Vertex AI through the Google GenAI SDK
- Google Cloud Run, using service-account authentication to Vertex AI
- FastAPI dashboard and API
- Deterministic Python policy, fleet simulator, rollout watchdog, and evals
- SQLite POC journal

## Data sources

All records are deterministic and synthetic: printers, people/account labels,
documentation-only IPs, locally administered MACs, serials, locations,
contacts, print jobs, firmware versions, and polling state. No employer,
customer, vendor, or physical-device data is connected.

## What we learned

- High alert count does not equal high root-cause count; topology must be
  correlated before action.
- Policy must evaluate the effective incident scope, not a narrower model
  hint or a wider executor interpretation.
- An executor receipt is not proof. The system must re-observe post-state and
  detect both unresolved work and collateral effects.
- A failed pilot can be a successful safety outcome when the system proves the
  remainder was untouched and refuses automatic expansion.

## POC boundaries

The public build is an unauthenticated, single-operator synthetic sandbox.
Its in-process state and SQLite-on-Cloud-Run journal are not production
durability or tenancy. The verifier reads simulator state; it does not claim
physical-printer or external management-server confirmation. Production
adapters would add authenticated sessions, a durable audit store, and real
vendor/SNMP/HTTPS integrations.

## Links

- Hosted project: <https://fleetpilot-118750462659.us-central1.run.app>
- Repository: <https://github.com/lantzmurray/Fleetpilot>
- Demo video: **ADD PUBLIC YOUTUBE OR VIMEO URL BEFORE SUBMISSION**
