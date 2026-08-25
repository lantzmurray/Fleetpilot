"""Deterministic risk engine. The LLM NEVER bypasses this layer."""
from dataclasses import dataclass, field
from enum import Enum


class Risk(Enum):
    AUTO = "auto"        # execute immediately
    HUMAN = "human"      # escalate to approval inbox
    BLOCKED = "blocked"  # never execute


@dataclass
class Decision:
    risk: Risk
    reason: str
    metadata: dict = field(default_factory=dict)


ALLOWLISTED = {"restart_queue", "clear_stuck_job", "ping_device"}
HUMAN_REQUIRED = {"reroute_jobs", "disable_queue", "update_firmware"}
NEVER = {"wipe_device", "delete_server"}  # demo: nothing destructive is automated

# Supplies: small top-ups auto-approve; anything above this USD amount is a
# purchase order a human must sign off on.
ORDER_AUTO_MAX_USD = 250

# Paper is loaded on-site, never shipped — the agent only notifies the
# device's point of contact. To avoid alert fatigue, a POC hears about a
# given device at most once per day (aggregated digest, not per-event pings).
NOTIFY_COOLDOWN_HOURS = 24

# Hard caps the agent cannot exceed per cycle
MAX_ACTIONS_PER_CYCLE = 5
MAX_AFFECTED_DEVICES = 50


class PolicyEngine:
    def __init__(self, allowlisted, human_required, never, max_actions, max_devices):
        self.allowlisted = allowlisted
        self.human_required = human_required
        self.never = never
        self.max_actions = max_actions
        self.max_devices = max_devices
        self.actions_this_cycle = 0
        # device -> last notify tick; enforces the POC notification cooldown
        self.notified: dict[str, int] = {}
        self.clock = 0

    @classmethod
    def defaults(cls) -> "PolicyEngine":
        return cls(ALLOWLISTED, HUMAN_REQUIRED, NEVER,
                   MAX_ACTIONS_PER_CYCLE, MAX_AFFECTED_DEVICES)

    def evaluate(self, action: dict) -> Decision:
        kind = action.get("kind", "")

        if kind == "notify_poc":
            device = action.get("device", "")
            last = self.notified.get(device)
            if last is not None and (self.clock - last) < NOTIFY_COOLDOWN_HOURS:
                return Decision(
                    Risk.BLOCKED,
                    "POC already notified within cooldown window "
                    f"({NOTIFY_COOLDOWN_HOURS}h) — suppressing to avoid "
                    "alert fatigue")
            self.notified[device] = self.clock
            return Decision(Risk.AUTO, "POC notified (first contact in window)")

        if kind == "order_supplies":
            cost = float(action.get("cost_usd", 0))
            if cost > ORDER_AUTO_MAX_USD:
                return Decision(
                    Risk.HUMAN,
                    f"purchase order ${cost:.2f} exceeds auto-approval cap "
                    f"${ORDER_AUTO_MAX_USD}")
            self.actions_this_cycle += 1
            return Decision(Risk.AUTO, f"small top-up ${cost:.2f} under cap")
        if kind in self.never:
            return Decision(Risk.BLOCKED, f"{kind} is on the permanent denylist")
        if self.actions_this_cycle >= self.max_actions:
            return Decision(Risk.BLOCKED, "per-cycle action cap reached")
        if len(action.get("devices", [])) > self.max_devices:
            return Decision(Risk.HUMAN, "blast radius exceeds auto cap")
        if kind in self.allowlisted:
            self.actions_this_cycle += 1
            return Decision(Risk.AUTO, "allowlisted low-risk action")
        if kind in self.human_required:
            return Decision(Risk.HUMAN, "high-impact action requires approval")
        return Decision(Risk.HUMAN, f"unknown action kind '{kind}' — default to human")
