# I Built an AI Agent That Manages a Printer Fleet — And It's Not Allowed to Touch It Without Permission

*How FleetPilot turned the most boring infrastructure on earth into a case study in governed autonomy — and why the agent's most important feature is its ability to say no.*

> **Disclosure:** I created this article for the purposes of entering the All Things Agentic Hackathon. FleetPilot is my entry — you can find the code and demo video on the [project page](https://github.com/lantzmurray/Fleetpilot).

---

## The incident that built this product

Every operations engineer has a story like this. Mine is a firmware push that froze mid-rollout on a real fleet. The management console said everything was fine. The dashboards stayed green. Meanwhile, devices were stuck halfway through an update, jobs were piling up, and the only way to know was a human noticing that something *should have finished by now.*

That failure mode is why FleetPilot exists. It's an AIOps agent for enterprise printer fleets — 200 devices, 4 print servers, mixed pull-print and direct-IP queues — that diagnoses incidents, remediates them, and knows exactly where autonomy has to stop.

## The uncomfortable truth about "AI agents" in ops

Most agent demos you see are chat loops with tools bolted on. They're impressive right up until you ask the question that matters in operations: **what happens when it's wrong?**

In fleet ops, wrong looks like:

- A firmware push that bricks 200 devices
- a purchase order nobody approved
- an "all clear" that nobody verified

So FleetPilot is built around a principle I stole from safety engineering: **the model proposes; deterministic code disposes.**

## The architecture in one diagram (drawn in words)

```
Fleet telemetry (synthetic 200-device fleet, 4 servers)
        │
        ▼
Deterministic correlator  ──►  grounds the incident
        │                      (server/queue topology, blast radius)
        ▼
Gemini 3.5 Flash (Vertex AI) ──► refines diagnosis, proposes action
        │                         (JSON-schema constrained, validated)
        ▼
Policy engine (pure Python) ──► AUTO / HUMAN / BLOCKED
        │   allowlists, blast-radius caps, $ purchase limits,
        │   notification cooldowns, permanent denylist
        ├── AUTO ──► execute ──► re-observe (verify, don't trust receipts)
        └── HUMAN ─► approval inbox ──► staged rollout + hang watchdog
        │
        ▼
Append-only audit journal — every step replayable
```

The LLM never executes anything. It sees a *grounded* summary of the incident (a deterministic correlator's hypothesis plus topology), returns a schema-constrained diagnosis and proposed action, and then a policy engine — the same code on every run, no creativity allowed — decides what actually happens.

## Four things I learned building it

### 1. Grounding beats prompt engineering

The deterministic correlator runs first and hands Gemini its hypothesis. The model's job is to *verify and refine*, not invent. This one design choice eliminated hallucinated root causes almost entirely — and when the model is unreachable (rate limits happen), the correlator's answer is the fallback, so the agent degrades instead of dying.

### 2. LLM output needs a bouncer

Everything Gemini returns is validated before it touches policy: allowed action kinds only, device IDs that actually exist in the fleet, bounded confidence, bounded scope. A malformed or hallucinated response is journaled and rejected — it can't reach the execution path. My eval suite literally tests hallucinated actions (someone has to try `deploy_rootkit` and get bounced).

### 3. Verification is re-observation, not receipts

When the agent executes a fix, it doesn't log "success" because the action returned. It **re-observes the fleet** and confirms the alerts actually cleared. The difference sounds academic until you've spent a career watching automation report victory over a still-broken system.

### 4. The demo moment that writes itself: the frozen pilot

The signature scenario is a guarded firmware rollout. Thirty devices drift out of compliance. Gemini proposes the push. Policy refuses to auto-run it — fleet-wide blast radius means a human approves. And here's the part that comes from that real frozen-push incident: approval starts a **five-device pilot**, not the fleet. A watchdog verifies each push. In the demo, three devices freeze mid-push — the watchdog catches them, quarantines them, aborts the expansion, and proves twenty-five devices were never touched.

That "aborted, 3 quarantined, 25 untouched" card is the whole product in one sentence: **the agent did the safe part, caught the unsafe part, and left evidence a compliance officer could audit.**

## The anti-fatigue detail nobody thinks about

Supplies management has a rule I'm weirdly proud of: paper is loaded on-site, so the agent never orders it — it notifies the device's point of contact, **at most once per 24 hours per device**. Because an agent that generates a notification per event isn't removing noise from ops; it *is* the noise. The suppression is logged, so you can prove the agent protected the humans from itself.

## The boring stack that makes it credible

- **Gemini 3.5 Flash via Vertex AI** — schema-constrained JSON output, model cascade with timeout guard
- **Google Cloud Run** — the whole service, service-account auth, no API keys in the container
- **FastAPI + SQLite** — the journal is append-only because audit trails don't get UPDATE statements
- **57 automated tests + an 11-scenario eval harness that runs fully offline** — every policy rule (denylist, action caps, purchase limits, cooldowns, no-auto-expansion) has a test proving it fires

That last bullet matters more than it looks. The eval harness runs with all model credentials stripped — meaning the safety architecture is *testable without the LLM*. You don't have to trust the model to trust the guardrails.

## What I'd tell the next person building an ops agent

Start from the failure modes, not the capabilities. The question isn't "what can the agent do?" — it's "what does it do when the model is wrong, the API is down, the push freezes, or the purchase order is too big?" If you can answer those four questions with code instead of hope, you have an agent an enterprise might actually run.

FleetPilot's answer: propose with the model, decide with policy, verify with re-observation, and prove everything in an append-only journal.

Autonomy proportional to evidence. That's the whole philosophy — and it turns out a printer fleet is a perfectly good place to demonstrate it.

---

*FleetPilot runs on a synthetic fleet modeled on real multi-server, multi-vendor print environments — no employer systems or real infrastructure are integrated. Code, tests, and the demo: [github.com/lantzmurray/Fleetpilot](https://github.com/lantzmurray/Fleetpilot). Live demo deployed on Cloud Run. Built for the All Things Agentic Hackathon (#AllThingsAgenticHackathon).*
