# LinkedIn Post

I built an AI agent for printer-fleet operations—and gave it a hard limit: it is not allowed to touch risky infrastructure without permission.

FleetPilot turns a synthetic 200-device alert storm into one topology-aware diagnosis, proposes a remediation with Gemini, and lets deterministic policy decide what can actually happen.

The important part is what happens when things go wrong:

• Low-risk queue incidents can be remediated automatically, then verified by re-observing the fleet.
• High-impact firmware changes require human approval.
• Approval starts a five-device pilot—not a fleet-wide rollout.
• When three devices freeze, the watchdog quarantines them, aborts expansion, and leaves 25 devices untouched.

The design principle is simple: the model proposes; deterministic code disposes; verification proves the result.

That is the kind of agent I would trust in operations: autonomy proportional to evidence, with every decision recorded in an append-only audit journal.

I built FleetPilot for the All Things Agentic Hackathon. The code, tests, and demo are here: https://github.com/lantzmurray/Fleetpilot

The fleet and incidents are synthetic and do not connect to employer systems or real infrastructure.

#AllThingsAgenticHackathon #AI #AIOps #CloudRun #Gemini #Automation #SRE #Infrastructure
