"""Realistic synthetic printer, print-job, and communication evidence."""

from ipaddress import ip_address

from agent.fleet_sim import FleetSimulator
from agent.journal import Journal
from agent.main import run_tick
from agent.policy.risk import PolicyEngine
from agent.rollout import run_firmware_rollout


def test_seed_builds_deterministic_realistic_printer_inventory():
    first = FleetSimulator.seed().inventory_records()
    second = FleetSimulator.seed().inventory_records()

    assert first == second
    assert len(first) == 200
    assert len({record["serial_number"] for record in first}) == 200
    assert len({record["ip_address"] for record in first}) == 200
    assert len({record["mac_address"] for record in first}) == 200
    assert all(ip_address(record["ip_address"]) for record in first)
    assert all(record["manufacturer"] in {"Xerox", "Ricoh", "HP"}
               for record in first)
    assert all(record["model"] != record["manufacturer"] for record in first)
    assert all(record["communication_status"] == "reachable"
               for record in first)
    assert all(record["management_channel"] == "SNMPv3 + HTTPS"
               for record in first)
    assert all(record["point_of_contact"].endswith(".invalid")
               for record in first)


def test_queue_incident_is_thirty_jobs_across_twenty_two_queues():
    sim = FleetSimulator.seed()
    sim.inject_scenario("queue_hang")

    jobs = sim.print_job_records()
    suspects = [job for job in jobs if job["suspected_blocker"]]

    assert len(jobs) == 30
    assert len({job["queue"] for job in jobs}) == 22
    assert {job["server"] for job in jobs} == {"srv-east-1"}
    assert len(suspects) == 1
    assert suspects[0]["document_name"] == "Vacation_Photo_Book_2400dpi.pdf"
    assert suspects[0]["owner_account"] == "jordan.lee"
    assert suspects[0]["account_code"] == "MKT-204"
    assert suspects[0]["size_mb"] > 1000
    assert all({"job_id", "document_name", "owner_account", "account_code",
                "department", "submitted_at", "pages", "size_mb", "status"}
               <= set(job) for job in jobs)
    assert sum(alert["suspected_blocker"] for alert in sim.active_alerts()) == 1


def test_queue_remediation_preserves_job_evidence_and_releases_backlog():
    sim = FleetSimulator.seed()
    sim.inject_scenario("queue_hang")

    summary = run_tick(
        sim, PolicyEngine.defaults(), Journal(":memory:"))
    jobs = sim.print_job_records()

    assert summary["executed"][0][0]["kind"] == "clear_stuck_job"
    assert "22 queues" in summary["root_cause"]
    assert "JOB-78421" in summary["root_cause"]
    assert [job["status"] for job in jobs if job["suspected_blocker"]] == [
        "quarantined"
    ]
    assert sum(job["status"] == "released" for job in jobs) == 29


def test_firmware_records_separate_reachability_from_update_state(
        memory_journal):
    sim = FleetSimulator.seed()
    sim.inject_scenario("firmware_push_freezes")
    evidence_ids = sim.evidence_device_ids
    before = sim.inventory_records(evidence_ids)
    action = {
        "kind": "update_firmware",
        "devices": [alert["device"] for alert in sim.active_alerts()],
        "rationale": "restore approved firmware baseline",
    }

    report = run_firmware_rollout(sim, memory_journal, action)
    after = {record["device_id"]: record
             for record in sim.inventory_records(evidence_ids)}

    assert len(before) == 30
    assert all(record["current_firmware"] != record["target_firmware"]
               for record in before)
    assert all(record["communication_status"] == "reachable"
               for record in before)
    assert all({"serial_number", "ip_address", "mac_address", "manufacturer",
                "model", "server", "site", "address", "point_of_contact",
                "last_poll_age_seconds", "management_channel"} <= set(record)
               for record in before)
    assert all(after[device]["current_firmware"] ==
               after[device]["target_firmware"]
               for device in report["completed_devices"])
    assert all(after[device]["communication_status"] == "reachable"
               for device in report["hung"])
    assert all(after[device]["update_status"] == "quarantined"
               for device in report["hung"])
