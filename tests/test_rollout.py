"""Unit tests for staged firmware rollout safety."""

from agent.fleet_sim import FleetSimulator
from agent.rollout import PILOT_SIZE, WATCHDOG_TICKS, run_firmware_rollout


def firmware_action(sim: FleetSimulator) -> dict:
    return {
        "kind": "update_firmware",
        "devices": [a["device"] for a in sim.active_alerts()],
        "rationale": "restore firmware compliance",
    }


def test_clean_pilot_requires_a_second_approval_before_expansion(memory_journal):
    sim = FleetSimulator.seed()
    sim.inject_scenario("firmware_drift")
    action = firmware_action(sim)

    report = run_firmware_rollout(sim, memory_journal, action)

    assert report["outcome"] == "pilot_clean"
    assert report["pilot_size"] == PILOT_SIZE
    assert report["pilot_completed"] == PILOT_SIZE
    assert report["hung"] == []
    assert report["fleet_untouched"] == len(action["devices"]) - PILOT_SIZE
    assert report["watchdog_checks"] == 0
    assert len(report["remaining_devices"]) == len(action["devices"]) - PILOT_SIZE
    event_kinds = [event["kind"] for event in memory_journal.replay()]
    assert event_kinds == [
        "rollout_pilot", "rollout_pilot_verified", "verify"
    ]
    assert report["verification"]["status"] == "pilot_verified"
    assert report["verification"]["external_system_verified"] is False


def test_frozen_pilot_aborts_quarantines_and_reports_every_demo_field(
        memory_journal):
    sim = FleetSimulator.seed()
    sim.inject_scenario("firmware_push_freezes")
    action = firmware_action(sim)

    report = run_firmware_rollout(sim, memory_journal, action)

    assert set(report) >= {
        "outcome",
        "pilot_size",
        "pilot_completed",
        "hung",
        "quarantined",
        "fleet_untouched",
        "watchdog_checks",
    }
    assert report["outcome"] == "aborted"
    assert report["pilot_size"] == PILOT_SIZE
    assert report["pilot_completed"] == PILOT_SIZE - len(report["hung"])
    assert report["hung"] == sorted(sim.frozen)
    assert report["quarantined"] == sorted(sim.frozen)
    assert report["fleet_untouched"] == len(action["devices"]) - PILOT_SIZE
    assert report["watchdog_checks"] == WATCHDOG_TICKS
    assert len(sim.active_alerts()) == len(action["devices"]) - report["pilot_completed"]
    events = memory_journal.replay()
    assert sum(e["kind"] == "watchdog" for e in events) == WATCHDOG_TICKS
    assert events[-2]["kind"] == "rollout_aborted"
    assert events[-1]["kind"] == "verify"
    assert report["verification"]["status"] == "safe_abort_confirmed"
    assert report["verification"]["external_system_verified"] is False


def test_empty_firmware_scope_is_not_labeled_as_a_verified_pilot(
        memory_journal):
    sim = FleetSimulator.seed()
    sim.inject_scenario("firmware_drift")

    report = run_firmware_rollout(sim, memory_journal, {
        "kind": "update_firmware",
        "devices": [],
        "rationale": "empty scope must not run",
    })

    assert report["outcome"] == "not_started"
    assert report["pilot_size"] == 0
    assert report["verification"]["status"] == "not_run"
    assert report["verification"]["external_system_verified"] is False
    assert [event["kind"] for event in memory_journal.replay()] == [
        "rollout_not_started"
    ]
