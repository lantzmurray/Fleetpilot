"""Synthetic fleet + alert simulator — demo data only, modeled on a
multi-server print fleet (devices -> servers -> queues topology)."""
import random
from dataclasses import dataclass, field


@dataclass
class Device:
    device_id: str
    server: str
    queue: str
    model: str


SERVERS = ["srv-east-1", "srv-east-2", "srv-west-1", "srv-west-2"]


@dataclass
class FleetSimulator:
    devices: list[Device] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)

    @classmethod
    def seed(cls, n_devices: int = 200, seed: int = 42) -> "FleetSimulator":
        rng = random.Random(seed)
        devices = [
            Device(f"DEV-{i:04d}", rng.choice(SERVERS), f"Q-{i % 40:02d}",
                   rng.choice(["Xerox", "Ricoh", "HP"]))
            for i in range(n_devices)
        ]
        return cls(devices=devices)

    def inject_scenario(self, name: str) -> None:
        """Scripted scenarios for demo + evals."""
        if name == "queue_hang":
            # One server's queue hangs -> 30 devices all report 'job stuck'
            affected = [d for d in self.devices if d.server == "srv-east-1"][:30]
            self.alerts = [
                {"device": d.device_id, "server": d.server, "queue": d.queue,
                 "symptom": "job_stuck", "severity": "high"}
                for d in affected
            ]
        elif name == "alert_storm":
            self.alerts = [
                {"device": f"DEV-{i:04d}", "server": "srv-west-2",
                 "queue": f"Q-{i % 40:02d}", "symptom": "offline",
                 "severity": "critical"}
                for i in range(150)
            ]
        elif name == "firmware_drift":
            # Fleet firmware audit: a vendor patch is missing across a mixed
            # fleet — cross-vendor compliance (Xerox/Ricoh/HP) use case.
            by_vendor: dict[str, list[Device]] = {}
            for d in self.devices:
                by_vendor.setdefault(d.model, []).append(d)
            for vendor, devs in by_vendor.items():
                for d in devs[:10]:  # 10 devices per vendor non-compliant
                    self.alerts.append({
                        "device": d.device_id, "server": d.server,
                        "queue": d.queue, "symptom": "firmware_noncompliant",
                        "severity": "medium", "model": vendor,
                    })
        else:
            raise ValueError(f"unknown scenario {name}")

    def active_alerts(self) -> list[dict]:
        return self.alerts

    def execute(self, action: dict) -> dict:
        # TODO(day-2): apply allowlisted actions, clear resolved alerts
        return {"applied": action, "alerts_cleared": 0}
