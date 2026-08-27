"""FastAPI integration tests for the two locked contest workflows."""

from pathlib import Path

import pytest

import web.app as web_app


def test_health_reports_runtime_readiness(api_client, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-runtime")
    monkeypatch.setenv("K_SERVICE", "fleetpilot-cloud")
    monkeypatch.setenv("K_REVISION", "fleetpilot-cloud-00001")

    response = api_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "fleetpilot-cloud"
    assert body["model"] == "gemini-test-runtime"
    assert body["deployment"] == "Cloud Run"
    assert body["revision"] == "fleetpilot-cloud-00001"


def test_approval_cost_is_html_escaped_before_inner_html_rendering():
    index = (Path(__file__).parents[1] / "web/static/index.html").read_text()

    assert "esc(p.action.cost_usd)" in index


def test_dashboard_contract_surfaces_job_device_and_network_evidence():
    index = (Path(__file__).parents[1] / "web/static/index.html").read_text()

    assert "Print operations control" in index
    assert "Incident evidence" in index
    assert "Job title" in index
    assert "Account" in index
    assert "Serial" in index
    assert "Current → target" in index
    assert "Reachability" in index
    assert "Last poll" in index
    assert "synthetic records" in index


def test_new_run_starts_clean_and_preserves_prior_audit_history(api_client):
    first = api_client.post("/api/scenario/firmware_push_freezes").json()
    first_run = first["run_id"]
    assert first["pending_approvals"]
    assert len(first["journal"]) > 1

    response = api_client.post("/api/reset")

    assert response.status_code == 200
    current = response.json()
    assert current["run_id"] != first_run
    assert current["fleet"]["devices"] == 200
    assert current["fleet"]["alerts_open"] == 0
    assert current["pending_approvals"] == []
    assert current["last_summary"] == {}
    assert current["rollout_report"] is None
    assert current["health"]["fallback_reason"] is None
    assert [event["kind"] for event in current["journal"]] == ["run_started"]
    assert current["journal"][0]["payload"]["run"] == current["run_id"]

    history = web_app.state.db_journal.replay()
    historical_runs = [event["payload"]["run"] for event in history
                       if event["kind"] == "run_started"]
    assert historical_runs == [first_run, current["run_id"]]


def test_second_scenario_cannot_inherit_first_run_state(api_client):
    first = api_client.post("/api/scenario/firmware_push_freezes").json()
    assert first["pending_approvals"]

    second = api_client.post("/api/scenario/queue_hang").json()

    assert second["run_id"] != first["run_id"]
    assert second["pending_approvals"] == []
    assert second["rollout_report"] is None
    assert second["journal"][0]["kind"] == "run_started"
    assert second["journal"][0]["payload"]["run"] == second["run_id"]
    assert all(event["payload"].get("run") != first["run_id"]
               for event in second["journal"])


def test_queue_hang_is_a_deterministic_complete_workflow(api_client):
    response = api_client.post("/api/scenario/queue_hang")

    assert response.status_code == 200
    body = response.json()
    assert body["fleet"]["alerts_open"] == 0
    assert body["pending_approvals"] == []
    assert body["last_summary"]["diagnosis_source"] == "heuristic"
    assert "30 of 30" in body["last_summary"]["root_cause"]
    assert "22 queues" in body["last_summary"]["root_cause"]
    evidence = body["evidence"]
    assert evidence["scenario"] == "queue_hang"
    assert len(evidence["print_jobs"]) == 30
    assert len(evidence["devices"]) == 30
    assert evidence["network"]["reachable"] == 30
    suspect = next(job for job in evidence["print_jobs"]
                   if job["suspected_blocker"])
    assert suspect["job_id"] == "JOB-78421"
    assert suspect["status"] == "quarantined"
    executed = body["last_summary"]["executed"]
    assert len(executed) == 1
    assert executed[0][0]["kind"] == "clear_stuck_job"
    assert executed[0][1]["alerts_cleared"] == 30
    assert [event["kind"] for event in body["journal"]] == [
        "run_started", "observe", "diagnose", "gate", "cycle_complete",
        "approval_queue",
    ]


def test_frozen_firmware_flow_uses_only_a_pilot_then_aborts(api_client):
    proposed = api_client.post("/api/scenario/firmware_push_freezes")

    assert proposed.status_code == 200
    before = proposed.json()
    assert before["fleet"]["alerts_open"] == 30
    assert len(before["pending_approvals"]) == 1
    approval = before["pending_approvals"][0]
    assert approval["action"]["kind"] == "update_firmware"
    assert len(approval["action"]["devices"]) >= 5
    assert "approval" in approval["reason"]
    records = before["evidence"]["devices"]
    assert len(records) == 30
    assert all(record["serial_number"] and record["ip_address"]
               for record in records)
    assert all(record["current_firmware"] != record["target_firmware"]
               for record in records)
    assert before["evidence"]["network"] == {
        "scope": 30,
        "reachable": 30,
        "unreachable": 0,
    }

    approved = api_client.post(f"/api/approve/{approval['id']}")

    assert approved.status_code == 200
    after = approved.json()
    report = after["rollout_report"]
    assert report["outcome"] == "aborted"
    assert report["pilot_size"] == 5
    assert report["pilot_completed"] + len(report["hung"]) == 5
    assert report["hung"] == report["quarantined"]
    assert report["watchdog_checks"] == 3
    assert report["fleet_untouched"] == (
        len(approval["action"]["devices"]) - report["pilot_size"]
    )
    assert after["fleet"]["alerts_open"] == (
        before["fleet"]["alerts_open"] - report["pilot_completed"]
    )
    assert after["pending_approvals"] == []
    by_id = {record["device_id"]: record
             for record in after["evidence"]["devices"]}
    assert all(by_id[device]["update_status"] == "quarantined"
               for device in report["hung"])
    assert all(by_id[device]["communication_status"] == "reachable"
               for device in report["hung"])
    pilot_events = [event for event in after["journal"]
                    if event["kind"] == "rollout_pilot"]
    assert len(pilot_events) == 1
    assert len(pilot_events[0]["payload"]["pilot"]) == 5
    assert not any(event["payload"].get("stage") == "full"
                   for event in after["journal"])


def test_invalid_scenario_returns_400(api_client):
    response = api_client.post("/api/scenario/not-a-real-scenario")

    assert response.status_code == 400
    assert "unknown scenario" in response.json()["detail"].lower()


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_unknown_approval_returns_404(api_client, decision):
    response = api_client.post(f"/api/{decision}/missing-id")

    assert response.status_code == 404
    assert "unknown approval" in response.json()["detail"].lower()
