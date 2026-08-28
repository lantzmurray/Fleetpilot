# FleetPilot — Live Demo Speaking Script (~3:00)

Target: **sub-3-minute, four-click demo**. Judges see the dashboard at
<http://localhost:8080> (or the Cloud Run URL). Timing marks assume Gemini
responds within its normal 12–20s window — the fallback lines cover the rest.

**Click map:** ① `Queue hang · 22 pull queues` ② `Guarded firmware rollout`
③ `Approve 5-printer pilot` ④ (optional) `New run` for the close.

Before you start: fresh browser tab → click **New run** once → wait for
`run <id>` to appear in the Audit journal header. Never demo with a used tab.

---

## 1. Hook — the friction story (0:00–0:20)

> "Every fleet operator has a story like this. A firmware push goes out to
> hundreds of printers, a batch freezes mid-update, and nobody notices until
> the help desk lights up. By then it's a fleet-wide outage.
>
> That's the exact failure FleetPilot is built around. I'm going to show you
> two live scenarios: one where it fixes a problem on its own, and one where
> it stops a bad rollout before it becomes that outage."

*On screen: the dashboard header — "FleetPilot — evidence-led response for
enterprise printer fleets."*

## 2. Setup — what you're looking at (0:20–0:40)

> "This is a live synthetic fleet — 200 printers across four print servers,
> simulated so the demo is deterministic and public-safe. The KPIs up top
> tell the story at a glance: two hundred of two hundred printers up, all
> four servers healthy, zero alerts — all green.
>
> One architectural detail matters: this fleet runs **pull printing**. The
> east server hosts a secure-release service — jobs spool centrally and only
> print when a user badges at a device, like an Equitrac setup. Keep that in
> mind for the first scenario. Every diagnosis is Gemini 3.5-or-newer — the
> model's in the health line — and every decision lands in this audit
> journal. **Click one** — Queue hang."

**CLICK ① — "Queue hang · 22 pull queues"**

## 3. Scenario 1 — Queue hang, autonomous fix (0:40–1:30)

*(The instant you click, the dashboard flips red — point at it:)*

> "Watch the donuts. Thirty alerts just opened, and the east server dropped
> out of the healthy set — because twenty-two **pull-release** queues just
> went quiet. Jobs held, badge releases failing, no errors anywhere. Because
> every job routes through the release server's spooler, **one stuck job
> there stalls every queue behind it**. That's the pull-print failure mode.
> The printers themselves are fine — all two hundred still green — this is a
> queue-layer incident."

*(The "Analyzing incident…" panel pulses for a few seconds while Gemini
runs — keep talking:)*

> "FleetPilot is correlating the alerts against the topology: which server,
> which queues, and — critically — which single job is blocking all of them."

*(When the summary card lands and the donuts return to green:)*

> "And there it is — back to green. One diagnosis, one root cause: a single
> oversized job blocking the release spooler. The policy engine classified
> the fix as **low risk and reversible**, so it executed autonomously — no
> human needed — then re-checked the fleet. Alerts thirty to **zero**,
> verified, not assumed.
>
> And the resolution left evidence: the suspect job sits in **quarantine**
> now — this panel shows the document, owner, and queue, and the Queues tab
> keeps a red badge on the queue it came from. The whole chain — correlate,
> diagnose, decide, act, verify — is in the audit journal."

## 4. Scenario 2 — Guarded firmware rollout (1:30–2:35)

> "Now the risky one. Firmware. Same fleet, but this time the fix is
> irreversible — so the architecture changes. **Click two.**"

**CLICK ② — "Guarded firmware rollout"**

> "Nine devices need firmware. Because this action is high-risk, FleetPilot
> does **not** auto-execute. It proposes a governed plan and stops for human
> approval — right here."

*(Point at the pending approval card.)*

> "**Click three** — I approve a five-printer pilot. Not the fleet. A pilot."

**CLICK ③ — "Approve 5-printer pilot"**

*(As the rollout runs, narrate:)*

> "The pilot starts — and this is where most tools fail silently. Devices
> freeze mid-push. FleetPilot's **watchdog** is checking every device as it
> completes… and it catches the freeze.

*(Point at the outcome card when it lands:)*

> "Read this card with me: pilot of five — some completed, **some hung —
> rollout aborted — frozen devices quarantined — fleet untouched.** The
> remaining four hundred devices never received the bad firmware. That's the
> whole product in one card."

## 5. Close (2:35–3:00)

> "FleetPilot turns a fleet alert storm into one topology-aware diagnosis,
> safely executes the low-risk fixes, and stops risky rollouts before they
> become outages. That's why it's a **Taskmaster** entry: a complete
> autonomous operations workflow with a governed high-risk branch — not a
> cosmetic multi-agent demo.
>
> Forty-nine tests, eleven offline eval scenarios, and a live Cloud Run
> deployment back everything you just saw. **Click four** — one button,
> clean run, any time you want to re-verify."

**CLICK ④ — "New run" (optional, if time allows)**

---

## Fallback lines (memorize these)

- **Gemini slow (>20s):** "Live model, real latency — this is exactly why
  every action has a deadline and a deterministic fallback path."
- **Diagnosis source shows fallback instead of Gemini:** "This run fell back
  to the deterministic reasoner — the design guarantee is the demo never
  dies, it degrades honestly. Let me reset and run it again live." *(Click
  New run, re-run the scenario.)*
- **Frozen screen / panic:** Skip to the outcome card — the journal has the
  full evidence chain regardless of rendering.

## Judge Q&A prep

- **"Why not multiple agents?"** — The rubric rewards the *right* number of
  agents. One governed diagnosis loop with deterministic policy, watchdog,
  and audit components is the honest architecture; a cosmetic agent mesh
  would weaken the claim. That's why we entered Taskmaster, not Fortified.
- **"Is the browser UUID authentication?"** — No. It's per-tab session
  isolation for the public demo so one visitor can't touch another's run.
  The README states explicitly it is not auth or production tenancy.
- **"Why would 22 queues stall from one job?"** — Only pull-release queues
  stall: they all spool through the release server's shared spooler, so one
  oversized blocking job holds every badge-release behind it. Direct IP
  queues on the other servers stay green — check the Queues tab.
- **"What if Gemini hallucinates an action?"** — Output is validated:
  allowed action kinds, known device IDs, bounded confidence. Unknown or
  malformed actions are filtered — there's an eval scenario that proves it.
- **"Evidence of coverage/testing?"** — 55 pytest tests, 11-scenario offline
  eval harness that clears all model credentials to prove determinism, plus
  the append-only SQLite journal you saw in the UI.
