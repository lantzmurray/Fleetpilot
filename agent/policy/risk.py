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

    @classmethod
    def defaults(cls) -> "PolicyEngine":
        return cls(ALLOWLISTED, HUMAN_REQUIRED, NEVER,
                   MAX_ACTIONS_PER_CYCLE, MAX_AFFECTED_DEVICES)

    def evaluate(self, action: dict) -> Decision:
        kind = action.get("kind", "")
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
