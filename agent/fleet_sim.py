"""Deterministic synthetic printer-fleet and incident simulator.

The records are deliberately realistic enough for an operator demo while
remaining unmistakably fictional: documentation-only IP addresses, locally
administered MAC addresses, and ``.invalid`` contacts. No device is polled.
"""
import random
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, replace
from typing import ClassVar


@dataclass(frozen=True)
class Device:
    device_id: str
    manufacturer: str
    model: str
    serial_number: str
    ip_address: str
    mac_address: str
    server: str
    queue: str
    current_firmware: str
    target_firmware: str
    site: str
    address: str
    point_of_contact: str
    last_poll_age_seconds: int
    communication_status: str = "reachable"
    management_channel: str = "SNMPv3 + HTTPS"
    toner_pct: int = 100
    paper_pct: int = 100


@dataclass(frozen=True)
class PrintJob:
    job_id: str
    document_name: str
    owner_account: str
    account_code: str
    department: str
    server: str
    queue: str
    device_id: str
    submitted_at: str
    pages: int
    size_mb: float
    datatype: str
    status: str
    suspected_blocker: bool = False
    policy_signal: str = "business"


SERVERS = ["srv-east-1", "srv-east-2", "srv-west-1", "srv-west-2"]
SUPPORTED_SCENARIOS = {
    "queue_hang",
    "alert_storm",
    "firmware_drift",
    "firmware_push_freezes",
    "low_supplies",
}

DEVICE_PROFILES = {
    "Xerox": (
        ("AltaLink C8155", "120.005.003", "120.005.013"),
        ("VersaLink B625", "112.014.021", "112.014.031"),
    ),
    "Ricoh": (
        ("IM C6010", "1.18.0", "1.24.0"),
        ("M 320F", "1.11.2", "1.16.0"),
    ),
    "HP": (
        ("LaserJet Enterprise MFP 6800dn", "5.7.0", "5.7.1"),
        ("Color LaserJet Enterprise 5700dn", "5.6.3", "5.7.1"),
    ),
}
SERIAL_PREFIX = {"Xerox": "XRX", "Ricoh": "RCH", "HP": "HPI"}
SITE_DETAILS = {
    "srv-east-1": (
        "Raleigh Operations Center",
        "100 Example Plaza, Raleigh, NC 27600",
        "avery.morgan@east-1.example.invalid",
    ),
    "srv-east-2": (
        "Richmond Service Center",
        "200 Sample Avenue, Richmond, VA 23200",
        "casey.nguyen@east-2.example.invalid",
    ),
    "srv-west-1": (
        "Denver Regional Office",
        "300 Demonstration Drive, Denver, CO 80200",
        "morgan.patel@west-1.example.invalid",
    ),
    "srv-west-2": (
        "Phoenix Distribution Center",
        "400 Prototype Parkway, Phoenix, AZ 85000",
        "riley.chen@west-2.example.invalid",
    ),
}


@dataclass
class FleetSimulator:
    devices: list[Device] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)
    print_jobs: list[PrintJob] = field(default_factory=list)
    evidence_device_ids: list[str] = field(default_factory=list)
    scenario: str | None = None
    frozen: set[str] = field(default_factory=set)
    quarantined: set[str] = field(default_factory=set)

    @classmethod
    def seed(cls, n_devices: int = 200, seed: int = 42) -> "FleetSimulator":
        rng = random.Random(seed)
        devices: list[Device] = []
        for i in range(n_devices):
            server = rng.choice(SERVERS)
            manufacturer = rng.choice(list(DEVICE_PROFILES))
            model, _old_firmware, target_firmware = DEVICE_PROFILES[
                manufacturer][i % 2]
            site, address, point_of_contact = SITE_DETAILS[server]
            devices.append(Device(
                device_id=f"DEV-{i:04d}",
                manufacturer=manufacturer,
                model=model,
                serial_number=f"SYN-{SERIAL_PREFIX[manufacturer]}-{i + 1:06d}",
                # RFC 5737 TEST-NET-1 is safe for documentation and demos.
                ip_address=f"192.0.2.{i + 1}",
                mac_address=f"02:42:00:00:{i // 256:02x}:{i % 256:02x}",
                server=server,
                queue=f"Q-{i % 40:02d}",
                current_firmware=target_firmware,
                target_firmware=target_firmware,
                site=site,
                address=address,
                point_of_contact=point_of_contact,
                last_poll_age_seconds=18 + (i * 7) % 103,
                toner_pct=rng.randint(5, 100),
                paper_pct=rng.randint(10, 100),
            ))
        return cls(devices=devices)

    def inject_scenario(self, name: str) -> None:
        """Reset transient state and inject one scripted demo scenario."""
        if name not in SUPPORTED_SCENARIOS:
            raise ValueError(f"unknown scenario {name}")
        self.alerts = []
        self.print_jobs = []
        self.evidence_device_ids = []
        self.frozen = set()
        self.quarantined = set()
        self.scenario = name

        if name == "queue_hang":
            self._inject_queue_hang()
        elif name == "alert_storm":
            self._inject_alert_storm()
        elif name in {"firmware_drift", "firmware_push_freezes"}:
            self._inject_firmware_drift()
            if name == "firmware_push_freezes":
                self.frozen = set(self.evidence_device_ids[:3])
        elif name == "low_supplies":
            self._inject_low_supplies()

    def _inject_queue_hang(self) -> None:
        affected = [d for d in self.devices if d.server == "srv-east-1"][:30]
        self.evidence_device_ids = [d.device_id for d in affected]
        ordinary_names = (
            "Q3_Budget_Workbook.xlsx", "Customer_Onboarding_Packet.pdf",
            "Warehouse_Pick_List.pdf", "Weekly_Service_Report.pdf",
            "Benefits_Enrollment_Guide.pdf", "Product_Specification.pdf",
        )
        departments = (
            ("finance.ops", "FIN-110", "Finance"),
            ("support.desk", "OPS-315", "Customer Support"),
            ("warehouse.team", "SCM-402", "Supply Chain"),
            ("people.ops", "HR-108", "People Operations"),
        )
        jobs: list[PrintJob] = []
        alerts: list[dict] = []
        for index, device in enumerate(affected):
            suspected = index == 0
            account, account_code, department = departments[index % len(departments)]
            job = PrintJob(
                job_id="JOB-78421" if suspected else f"JOB-{78422 + index:05d}",
                document_name=("Vacation_Photo_Book_2400dpi.pdf" if suspected
                               else ordinary_names[index % len(ordinary_names)]),
                owner_account="jordan.lee" if suspected else account,
                account_code="MKT-204" if suspected else account_code,
                department="Marketing" if suspected else department,
                server=device.server,
                queue=device.queue,
                device_id=device.device_id,
                submitted_at=f"2026-08-27T09:{12 + index:02d}:00-04:00",
                pages=486 if suspected else 4 + (index * 7) % 96,
                size_mb=1842.6 if suspected else round(0.8 + index * 2.7, 1),
                datatype="PDF" if suspected or index % 3 else "PCL6",
                status="blocking" if suspected else "waiting",
                suspected_blocker=suspected,
                policy_signal="review_non_business_content" if suspected else "business",
            )
            jobs.append(job)
            alerts.append({
                "device": device.device_id,
                "server": device.server,
                "queue": device.queue,
                "symptom": "job_stuck",
                "severity": "high",
                "job_id": job.job_id,
                "document_name": job.document_name,
                "owner_account": job.owner_account,
                "account_code": job.account_code,
                "pages": job.pages,
                "size_mb": job.size_mb,
                "datatype": job.datatype,
                "suspected_blocker": job.suspected_blocker,
            })
        self.print_jobs = jobs
        self.alerts = alerts

    def _inject_alert_storm(self) -> None:
        affected_ids = {device.device_id for device in self.devices[:150]}
        site, address, point_of_contact = SITE_DETAILS["srv-west-2"]
        self.devices = [
            replace(
                device,
                server="srv-west-2",
                site=site,
                address=address,
                point_of_contact=point_of_contact,
                communication_status="unreachable",
                last_poll_age_seconds=900 + int(device.device_id[-4:]),
            )
            if device.device_id in affected_ids else device
            for device in self.devices
        ]
        affected = self.devices[:150]
        self.evidence_device_ids = [device.device_id for device in affected]
        self.alerts = [
            {"device": device.device_id, "server": device.server,
             "queue": device.queue, "symptom": "offline",
             "severity": "critical"}
            for device in affected
        ]

    def _inject_firmware_drift(self) -> None:
        by_vendor: dict[str, list[Device]] = {}
        for device in self.devices:
            by_vendor.setdefault(device.manufacturer, []).append(device)
        affected = [device for vendor in DEVICE_PROFILES
                    for device in by_vendor.get(vendor, [])[:10]]
        old_versions = {
            model: old
            for profiles in DEVICE_PROFILES.values()
            for model, old, _target in profiles
        }
        affected_ids = {device.device_id for device in affected}
        self.devices = [
            replace(device, current_firmware=old_versions[device.model])
            if device.device_id in affected_ids else device
            for device in self.devices
        ]
        self.evidence_device_ids = [device.device_id for device in affected]
        by_id = {device.device_id: device for device in self.devices}
        self.alerts = [
            {
                "device": device_id,
                "server": by_id[device_id].server,
                "queue": by_id[device_id].queue,
                "symptom": "firmware_noncompliant",
                "severity": "medium",
                "manufacturer": by_id[device_id].manufacturer,
                "model": by_id[device_id].model,
                "serial_number": by_id[device_id].serial_number,
                "current_firmware": by_id[device_id].current_firmware,
                "target_firmware": by_id[device_id].target_firmware,
            }
            for device_id in self.evidence_device_ids
        ]

    def _inject_low_supplies(self) -> None:
        for device in self.devices:
            if device.toner_pct <= 15:
                self.alerts.append({
                    "device": device.device_id, "server": device.server,
                    "queue": device.queue, "symptom": "toner_low",
                    "severity": "medium", "model": device.model,
                    "toner_pct": device.toner_pct,
                })
            if device.paper_pct <= 10:
                self.alerts.append({
                    "device": device.device_id, "server": device.server,
                    "queue": device.queue, "symptom": "paper_low",
                    "severity": "low", "paper_pct": device.paper_pct,
                    "disposition": "notify_poc",
                })
        self.evidence_device_ids = list(dict.fromkeys(
            alert["device"] for alert in self.alerts))

    def active_alerts(self) -> list[dict]:
        return self.alerts

    def inventory_records(self, device_ids: Iterable[str] | None = None) -> list[dict]:
        selected = set(device_ids) if device_ids is not None else None
        records = []
        for device in self.devices:
            if selected is not None and device.device_id not in selected:
                continue
            record = asdict(device)
            if device.device_id in self.quarantined:
                update_status = "quarantined"
            elif device.current_firmware != device.target_firmware:
                update_status = "update_required"
            else:
                update_status = "compliant"
            records.append({**record, "update_status": update_status,
                            "synthetic": True})
        return records

    def print_job_records(self) -> list[dict]:
        return [{**asdict(job), "synthetic": True} for job in self.print_jobs]

    RESOLVES: ClassVar[dict[str, set[str]]] = {
        "restart_queue": {"job_stuck"},
        "clear_stuck_job": {"job_stuck"},
        "ping_device": {"offline"},
        "update_firmware": {"firmware_noncompliant"},
    }

    def execute(self, action: dict) -> dict:
        """Apply an allowlisted action and retain before/after evidence."""
        kind = action.get("kind", "")
        device_ids = set(action.get("devices", []))

        if kind == "update_firmware":
            hung = sorted(device_ids & self.frozen)
            completed = sorted(device_ids - self.frozen - self.quarantined)
            completed_ids = set(completed)
            self.devices = [
                replace(device, current_firmware=device.target_firmware)
                if device.device_id in completed_ids else device
                for device in self.devices
            ]
            before = len(self.alerts)
            self.alerts = [alert for alert in self.alerts
                           if alert["device"] not in completed_ids]
            return {"applied": action, "stage": action.get("stage", "full"),
                    "completed": completed, "hung": hung,
                    "alerts_cleared": before - len(self.alerts)}

        symptoms = self.RESOLVES.get(kind, set())
        before = len(self.alerts)
        self.alerts = [
            alert for alert in self.alerts
            if not (alert["device"] in device_ids and
                    alert["symptom"] in symptoms)
        ]
        if kind in {"clear_stuck_job", "restart_queue"}:
            self.print_jobs = [
                replace(job, status=("quarantined" if job.suspected_blocker
                                     else "released"))
                if job.device_id in device_ids else job
                for job in self.print_jobs
            ]
        return {"applied": action, "alerts_cleared": before - len(self.alerts)}
