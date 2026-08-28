"""FastAPI integration tests for the two locked contest workflows."""

from pathlib import Path

import pytest

import web.app as web_app


def run_scenario(client, name, headers=None):
    """Two-phase scenario: inject (incident visible) then resolve."""
    injected = client.post(f"/api/scenario/{name}", headers=headers)
    assert injected.status_code == 200
    resolved = client.post("/api/resolve", headers=headers)
    assert resolved.status_code == 200
    return injected.json(), resolved.json()


def test_health_reports_runtime_readiness(api_client, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-runtime")
    monkeypatch.setenv("K_SERVICE", "fleetpilot-cloud")
    monkeypatch.setenv("K_REVISION", "fleetpilot-cloud-00001")

    response = api_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["probe"] == "liveness"
    assert body["model_live_verified"] is False
    assert body["model_status"] == "not_yet_exercised"
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
    assert 'id="outcome-verification"' in index
    assert "Outcome verification" in index
    assert "SIMULATOR OUTCOME VERIFIED" in index
    assert "SAFE ABORT CONFIRMED · SIMULATOR" in index
    assert "No external fleet polling" in index
    assert "external_system_verified" in index
    assert "X-FleetPilot-Session" in index
    assert "crypto.randomUUID" in index


def test_app_shell_contract_tabs_donuts_and_new_pages():
    index = (Path(__file__).parents[1] / "web/static/index.html").read_text()

    for tab in ("Dashboard", "Printers", "Queues", "Firmware",
                "Reports", "Administration", "Settings"):
        assert tab in index
    for donut in ("donut-printers", "donut-servers", "donut-alerts",
                  "donut-compliance"):
        assert donut in index
    assert "PrintVault Secure Release" in index
    assert "Hostname" in index
    assert "pull release" in index


def test_inventory_surfaces_200_devices_with_contact_and_status_fields(api_client):
    response = api_client.get("/api/state")

    body = response.json()
    inventory = body["inventory"]
    assert len(inventory) == 200
    record = inventory[0]
    for field in ("hostname", "ip_address", "mac_address", "serial_number",
                  "manufacturer", "model", "printer_status", "last_status_at",
                  "contact_name", "contact_phone", "server", "queue"):
        assert record[field]
    hostnames = {d["hostname"] for d in inventory}
    assert len(hostnames) == 200


def test_queue_registry_shows_pull_release_queues_running_after_resolution(
        api_client):
    before = api_client.get("/api/state").json()
    stalled_before = [q for q in before["queues"] if q["status"] == "stalled"]
    assert stalled_before == []
    pull = [q for q in before["queues"] if q["queue_type"] == "pull_release"]
    assert pull and all(q["server"] == "srv-east-1" for q in pull)
    assert all(q["status"] == "running" for q in pull)

    incident, after = run_scenario(api_client, "queue_hang")

    # Incident phase: 22 pull-release queues stall red.
    stalled = [q for q in incident["queues"] if q["status"] == "stalled"]
    assert len(stalled) == 22
    assert incident["incident_active"] is True
    # The agent resolves the incident, so the queue registry must be back
    # to running with no pending jobs.
    assert [q for q in after["queues"] if q["status"] == "stalled"] == []
    assert all(q["pending_jobs"] == 0 for q in after["queues"])


def test_firmware_registry_lists_signed_vendor_packages(api_client):
    body = api_client.get("/api/state").json()

    packages = body["firmware"]["packages"]
    assert len(packages) == 6
    vendors = {p["vendor"] for p in packages}
    assert vendors == {"Xerox", "Ricoh", "HP"}
    for package in packages:
        assert package["file_name"]
        assert len(package["sha256"]) == 16
        assert package["signed_by"]
        assert package["status"] == "Approved"
    assert body["fleet"]["firmware_compliant"] == body["fleet"]["devices"]


def test_browser_sessions_cannot_read_overwrite_or_approve_each_other(
        api_client):
    operator_a = {
        "X-FleetPilot-Session": "11111111-1111-4111-8111-111111111111"
    }
    operator_b = {
        "X-FleetPilot-Session": "22222222-2222-4222-8222-222222222222"
    }

    first = run_scenario(
        api_client, "firmware_push_freezes", headers=operator_a)[1]
    approval_id = first["pending_approvals"][0]["id"]

    second_initial = api_client.get("/api/state", headers=operator_b).json()
    assert second_initial["run_id"] is None
    assert second_initial["fleet"]["alerts_open"] == 0
    assert second_initial["pending_approvals"] == []

    cross_approval = api_client.post(
        f"/api/approve/{approval_id}", headers=operator_b
    )
    assert cross_approval.status_code == 404

    second = api_client.post(
        "/api/scenario/queue_hang", headers=operator_b
    ).json()
    first_after = api_client.get("/api/state", headers=operator_a).json()

    assert second["run_id"] != first["run_id"]
    assert first_after["run_id"] == first["run_id"]
    assert first_after["pending_approvals"][0]["id"] == approval_id


def test_invalid_browser_session_id_is_rejected(api_client):
    response = api_client.get(
        "/api/state", headers={"X-FleetPilot-Session": "not-a-uuid"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid browser session id"


def test_health_reports_the_calling_browser_run(api_client):
    operator_a = {
        "X-FleetPilot-Session": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    }
    operator_b = {
        "X-FleetPilot-Session": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    }

    run_scenario(api_client, "queue_hang", headers=operator_a)

    health_a = api_client.get("/health", headers=operator_a).json()
    health_b = api_client.get("/health", headers=operator_b).json()

    assert health_a["diagnosis_source"] == "heuristic"
    assert health_b["diagnosis_source"] is None


def test_session_capacity_preserves_active_runs_instead_of_evicting(
        api_client, monkeypatch):
    operator_a = {
        "X-FleetPilot-Session": "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
    }
    operator_b = {
        "X-FleetPilot-Session": "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
    }
    monkeypatch.setattr(web_app, "MAX_BROWSER_SESSIONS", 1)

    first = run_scenario(
        api_client, "firmware_push_freezes", headers=operator_a)[1]
    refused = api_client.get("/api/state", headers=operator_b)
    first_after = api_client.get("/api/state", headers=operator_a).json()

    assert refused.status_code == 503
    assert refused.json()["detail"] == "browser session capacity reached"
    assert first_after["run_id"] == first["run_id"]
    assert first_after["pending_approvals"]


def test_new_run_starts_clean_and_preserves_prior_audit_history(api_client):
    first = run_scenario(api_client, "firmware_push_freezes")[1]
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
    first = run_scenario(api_client, "firmware_push_freezes")[1]
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
    incident, body = run_scenario(api_client, "queue_hang")

    # Incident phase: red dashboard state before resolution.
    assert incident["fleet"]["alerts_open"] == 30
    assert incident["incident_active"] is True
    assert incident["fleet"]["reachable"] == incident["fleet"]["devices"]
    assert len(incident["quarantine"]["jobs"]) == 0

    assert body["fleet"]["alerts_open"] == 0
    assert body["incident_active"] is False
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
    assert body["last_summary"]["verification"] == {
        "status": "resolved",
        "basis": "synthetic_simulator_post_state",
        "external_system_verified": False,
        "actions_checked": 1,
        "alerts_before": 30,
        "alerts_after": 0,
        "alerts_cleared": 30,
        "executor_reported_alerts_cleared": 30,
        "matching_alerts_remaining": 0,
        "unexpected_alerts_cleared": 0,
    }
    assert [event["kind"] for event in body["journal"]] == [
        "run_started", "incident_injected", "observe", "diagnose", "gate",
        "action_result", "verify", "cycle_complete", "approval_queue",
    ]


def test_resolve_requires_an_active_incident(api_client):
    response = api_client.post("/api/resolve")

    assert response.status_code == 409
    assert response.json()["detail"] == "no incident active"


def test_resolution_leaves_quarantine_evidence(api_client):
    _, body = run_scenario(api_client, "queue_hang")

    quarantined = body["quarantine"]["jobs"]
    assert len(quarantined) == 1
    job = quarantined[0]
    assert job["job_id"] == "JOB-78421"
    assert job["document_name"] == "Vacation_Photo_Book_2400dpi.pdf"
    assert job["status"] == "quarantined"
    badge_queues = [q for q in body["queues"] if q["quarantined_jobs"]]
    assert len(badge_queues) == 1
    assert badge_queues[0]["queue"] == job["queue"]
    assert badge_queues[0]["quarantined_jobs"] == 1


def test_frozen_firmware_flow_uses_only_a_pilot_then_aborts(api_client):
    injected, before = run_scenario(api_client, "firmware_push_freezes")

    # Incident phase: firmware compliance drops, alerts open, gate pending.
    assert injected["fleet"]["alerts_open"] == 30
    assert injected["fleet"]["firmware_compliant"] == 170
    assert injected["incident_active"] is True
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
    assert after["quarantine"]["devices"] == report["hung"]
    assert report["watchdog_checks"] == 3
    assert report["fleet_untouched"] == (
        len(approval["action"]["devices"]) - report["pilot_size"]
    )
    assert report["verification"] == {
        "status": "safe_abort_confirmed",
        "basis": "synthetic_simulator_post_state",
        "external_system_verified": False,
        "pilot_checked": 5,
        "completed_compliant": 2,
        "quarantined_noncompliant": 3,
        "remainder_untouched": 25,
        "expansion_started": False,
        "alerts_before": 30,
        "alerts_after": 28,
    }
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
    verify_events = [event for event in after["journal"]
                     if event["kind"] == "verify"]
    assert verify_events[-1]["payload"] == report["verification"]
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
