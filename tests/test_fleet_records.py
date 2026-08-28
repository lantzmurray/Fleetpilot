"""Realistic synthetic printer, print-job, and communication evidence."""

from ipaddress import ip_address

from agent.diagnosis import Diagnosis
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
    assert suspects[0]["datatype"] == "PDF"
    assert all({"job_id", "document_name", "owner_account", "account_code",
                "department", "submitted_at", "pages", "size_mb", "status"}
               <= set(job) for job in jobs)
    assert sum(alert["suspected_blocker"] for alert in sim.active_alerts()) == 1


def test_network_alert_evidence_matches_device_reachability_and_server():
    sim = FleetSimulator.seed()
    sim.inject_scenario("alert_storm")

    records = {record["device_id"]: record for record in
               sim.inventory_records(sim.evidence_device_ids)}

    assert len(records) == 150
    assert all(records[alert["device"]]["server"] == alert["server"]
               for alert in sim.active_alerts())
    assert all(record["communication_status"] == "unreachable"
               for record in records.values())


def test_queue_remediation_preserves_job_evidence_and_releases_backlog():
    sim = FleetSimulator.seed()
    sim.inject_scenario("queue_hang")
    journal = Journal(":memory:")

    summary = run_tick(sim, PolicyEngine.defaults(), journal)
    jobs = sim.print_job_records()

    assert summary["executed"][0][0]["kind"] == "clear_stuck_job"
    assert "22 queues" in summary["root_cause"]
    assert "JOB-78421" in summary["root_cause"]
    assert [job["status"] for job in jobs if job["suspected_blocker"]] == [
        "quarantined"
    ]
    assert sum(job["status"] == "released" for job in jobs) == 29
    assert summary["verification"] == {
        "status": "resolved",
        "actions_checked": 1,
        "alerts_before": 30,
        "alerts_after": 0,
        "alerts_cleared": 30,
        "matching_alerts_remaining": 0,
    }
    verify_events = [event for event in journal.replay()
                     if event["kind"] == "verify"]
    assert len(verify_events) == 1
    assert verify_events[0]["payload"]["status"] == "resolved"
    assert verify_events[0]["payload"]["action_kind"] == "clear_stuck_job"
    assert verify_events[0]["payload"]["matching_alerts_remaining"] == 0


def test_executor_cannot_expand_beyond_the_policy_reviewed_scope():
    sim = FleetSimulator.seed()
    sim.inject_scenario("queue_hang")
    suspect = next(job for job in sim.print_job_records()
                   if job["suspected_blocker"])

    result = sim.execute({
        "kind": "clear_stuck_job",
        "devices": [suspect["device_id"]],
        "rationale": "quarantine the suspect job",
    })

    assert result["alerts_cleared"] == 1
    assert len(sim.active_alerts()) == 29
    assert sum(job["status"] == "waiting"
               for job in sim.print_job_records()) == 29


def test_model_suspect_target_is_grounded_before_the_policy_gate(
        monkeypatch, memory_journal):
    sim = FleetSimulator.seed()
    sim.inject_scenario("queue_hang")
    suspect = next(job for job in sim.print_job_records()
                   if job["suspected_blocker"])
    model_result = Diagnosis(
        root_cause="suspect job blocked shared server spooler",
        confidence=0.95,
        affected_nodes=[],
        proposed_actions=[{
            "kind": "clear_stuck_job",
            "devices": [suspect["device_id"]],
            "rationale": "quarantine the suspect job",
        }],
        source="gemini",
    )
    monkeypatch.setattr("agent.main.diagnose", lambda _alerts: model_result)

    summary = run_tick(sim, PolicyEngine.defaults(), memory_journal)

    action, result = summary["executed"][0]
    assert len(action["devices"]) == 30
    assert result["alerts_cleared"] == 30
    assert sim.active_alerts() == []
    scope_events = [event for event in memory_journal.replay()
                    if event["kind"] == "action_scope_grounded"]
    assert len(scope_events) == 1
    assert scope_events[0]["payload"]["requested_devices"] == [
        suspect["device_id"]
    ]
    assert len(scope_events[0]["payload"]["effective_devices"]) == 30


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
