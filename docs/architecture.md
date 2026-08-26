# FleetPilot Architecture

```mermaid
flowchart LR
    Operator["Fleet operator"] --> UI["FastAPI dashboard<br/>Cloud Run target"]
    UI --> Simulator["Synthetic fleet telemetry<br/>devices, queues, servers"]
    Simulator --> Correlator["Deterministic topology correlator"]
    Correlator --> Gemini["Gemini 3.5+<br/>Google GenAI SDK"]
    Gemini --> Validator["Output validator<br/>known actions and devices"]
    Validator --> Policy["Deterministic policy<br/>allow, approve, block"]
    Policy -->|"low risk"| Tools["Scoped fleet tools"]
    Policy -->|"high impact"| Approval["Human approval inbox"]
    Approval --> Pilot["Five-device pilot"]
    Pilot --> Watchdog["Watchdog and quarantine"]
    Tools --> Verify["Outcome verification"]
    Watchdog --> Verify
    Correlator -. "labeled fallback" .-> Validator
    UI --> Journal["Append-only SQLite journal"]
    Validator --> Journal
    Policy --> Journal
    Approval --> Journal
    Watchdog --> Journal
```

## Trust boundary

Gemini may diagnose and propose an action, but it cannot call fleet operations
directly. Proposals must pass schema and device validation, then the
deterministic policy decides whether a scoped tool may run, a human must
approve, or the action is blocked. Every transition is written to the audit
journal. All fleet data and actions in the contest build are synthetic.
