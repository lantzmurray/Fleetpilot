# FleetPilot Devpost Submission Copy

## Inspiration

A firmware push froze mid-rollout on real fleet hardware while every dashboard
stayed green. That was the friction that built this product. Dashboards showed
compliance and uptime, but nothing verified the outcome of an action or
proportional autonomy to the risk. FleetPilot is the operator console we wished
existed: grounded diagnosis, autonomy proportional to risk, and verified
outcomes.

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

The dashboard tells the story. It opens all green (200/200 printers up, 4/4
servers, zero alerts, 100% firmware compliance). Each scenario lands red
first: alerts open, the affected server degrades, compliance drops, queues
stall. The agent then resolves it and the dashboard returns to green while
leaving quarantine evidence behind. The suspect job or frozen devices stay
listed in the Quarantine panel and badged on the affected queue. The fleet
runs a mixed MPS architecture: pull-print secure release on one server (jobs
spool centrally and print on badge tap) and direct IP queues on the rest.
That is exactly why one blocking job can stall twenty-two release queues
while every printer stays online.

Two proof workflows demonstrate it:

**Queue hang.** Thirty synthetic jobs across twenty-two pull-release queues
on the secure release server appear as thirty alerts. FleetPilot identifies
one suspect 1.8 GB non-business print job with an owner and account code,
grounds the server incident scope, quarantines the suspect job, releases the
other twenty-nine jobs, and re-observes zero matching alerts with no
collateral alert clearing. Printers stay 200/200 online throughout, because
it is a queue-layer incident, not a device one.

**Guarded firmware rollout.** Thirty printers report a synthetic firmware
baseline mismatch. Gemini proposes the change, deterministic policy requires
human approval, and approval starts only a five-printer pilot. Two simulated
updates complete; three freeze. The watchdog quarantines the failed attempts,
confirms twenty-five printers were untouched, and stops before fleet-wide
expansion.

## How we built it

- Gemini 3.5+ on Vertex AI through the Google GenAI SDK
- Google Cloud Run, using service-account authentication to Vertex AI
- FastAPI dashboard and API
- Deterministic Python policy, fleet simulator, rollout watchdog, and evals
- SQLite POC journal

This is not a chat interface. Gemini contributes diagnosis and action
selection inside a larger action loop:

`observe → correlate → Gemini → validate → scope → policy → act/gate → verify → audit`

Gemini cannot bypass validation, policy, approval, pilot limits, or the
watchdog. A labeled deterministic fallback keeps the workflow safe and
testable when the model is unavailable.

All records are deterministic and synthetic: printers, people/account labels,
documentation-only IPs, locally administered MACs, serials, locations,
contacts, print jobs, firmware versions, and polling state. No employer,
customer, vendor, or physical-device data is connected.

## Challenges we ran into

- High alert count does not equal high root-cause count. Topology had to be
  correlated before any action, or thirty alerts would look like thirty
  incidents instead of one.
- Policy had to evaluate the effective incident scope, not a narrower model
  hint or a wider executor interpretation. Either mismatch breaks autonomy
  boundaries.
- An executor receipt is not proof. The system had to re-observe post-state
  and detect both unresolved work and collateral effects.
- Scoping the POC honestly: the public build is an unauthenticated synthetic
  sandbox. Browser-session state prevents one visitor from reading,
  overwriting, or approving another visitor's run inside a single instance,
  but it is not authentication, durable state, or cross-instance production
  tenancy. SQLite on Cloud Run is not a durable audit store, and the verifier
  reads simulator state rather than claiming physical-printer or external
  management-server confirmation.

## Accomplishments that we're proud of

- One suspect 1.8 GB job quarantined, twenty-nine legitimate jobs released,
  and zero collateral alert clearing, with printers 200/200 online the whole
  time.
- A firmware pilot that failed safely: three frozen devices quarantined,
  twenty-five printers proven untouched, and automatic fleet-wide expansion
  refused.
- Gemini genuinely inside the action loop but never able to bypass
  validation, policy, approval, pilot limits, or the watchdog.
- A deterministic fallback that keeps the whole workflow safe and testable
  when the model is unavailable.

## What we learned

- High alert count does not equal high root-cause count; topology must be
  correlated before action.
- Policy must evaluate the effective incident scope, not a narrower model
  hint or a wider executor interpretation.
- An executor receipt is not proof. The system must re-observe post-state and
  detect both unresolved work and collateral effects.
- A failed pilot can be a successful safety outcome when the system proves
  the remainder was untouched and refuses automatic expansion.

## What's next for Fleet-Pilot

Production adapters: authenticated sessions, a durable audit store, and real
vendor/SNMP/HTTPS integrations to replace the synthetic simulator. From
there, expanding the policy surface to more incident classes and running the
observe-and-verify loop against real fleet hardware, so the next firmware
push that freezes mid-rollout gets caught by evidence instead of discovered
by users.

## Track

**The Taskmaster**

FleetPilot is an enterprise printer-fleet operations product entered in the
Taskmaster track because it completes a messy, multi-step incident workflow.
It is not a task-management application and does not claim the multi-agent
institutional platform required by the Fortified Enterprise Fleet track.

Secondary prize fit: **Individual/Hobbyist** and **Best Architectural Design**.

## Links

- Hosted project: <https://fleetpilot-118750462659.us-central1.run.app>
- Repository: <https://github.com/lantzmurray/Fleetpilot>
- Demo video: <https://youtu.be/tjeV5Zkmsnc>
