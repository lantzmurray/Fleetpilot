"""Staged firmware rollout with a hang watchdog.

The LPRTool origin story, generalized: fleet tools' firmware/clone pushes
sometimes freeze or die on unexpected device-page states. So FleetPilot never
pushes fleet-wide directly — a human-approved push runs a pilot batch first;
the watchdog verifies completion; hung devices abort the rollout and get
quarantined (continue-to-next-device, with a report). Only a clean pilot
earns a second approval to expand fleet-wide.
"""
PILOT_SIZE = 5
WATCHDOG_TICKS = 3  # pushes not completing within this many checks = hung


def run_firmware_rollout(sim, journal, action: dict) -> dict:
    """Execute a human-approved firmware action as a staged rollout.

    Returns a report; if the pilot is clean, caller escalates the fleet-wide
    expansion as a NEW approval (never auto-expand).
    """
    alerts_before = len(sim.active_alerts())
    devices = [d for d in action.get("devices", []) if d not in sim.quarantined]
    # Deterministic pilot: frozen devices first so a freeze scenario always
    # exercises the watchdog path regardless of LLM ordering (demo reliability).
    devices = sorted(devices, key=lambda d: (d not in sim.frozen, d))
    if not devices:
        verification = {
            "status": "not_run",
            "basis": "synthetic_simulator_post_state",
            "external_system_verified": False,
            "pilot_checked": 0,
            "completed_compliant": 0,
            "quarantined_noncompliant": 0,
            "remainder_untouched": 0,
            "expansion_started": False,
            "alerts_before": alerts_before,
            "alerts_after": len(sim.active_alerts()),
        }
        report = {
            "outcome": "not_started",
            "pilot_size": 0,
            "pilot_completed": 0,
            "completed_devices": [],
            "hung": [],
            "quarantined": sorted(sim.quarantined),
            "remaining_devices": [],
            "fleet_untouched": 0,
            "watchdog_checks": 0,
            "verification": verification,
        }
        journal.log("rollout_not_started", {
            "reason": "no eligible devices in approved scope",
            "report": report,
        })
        return report
    pilot, remainder = devices[:PILOT_SIZE], devices[PILOT_SIZE:]

    result = sim.execute({**action, "devices": pilot, "stage": "pilot"})
    journal.log("rollout_pilot", {"pilot": pilot, "result": result})
    completed = len(result.get("completed", []))

    hung = result.get("hung", [])
    ticks = 0
    while hung and ticks < WATCHDOG_TICKS:
        # watchdog re-checks the frozen pushes; they never complete
        ticks += 1
        journal.log("watchdog", {"check": ticks, "still_hung": hung})

    if hung:
        sim.quarantined.update(hung)
        journal.log("rollout_aborted", {
            "reason": "pilot devices hung — push frozen, rollout aborted",
            "quarantined": sorted(sim.quarantined),
            "note": "fleet untouched; stuck devices flagged for manual "
                    "intervention (the failure mode that motivated this "
                    "design)",
        })
        by_id = {record["device_id"]: record
                 for record in sim.inventory_records(devices)}
        verification = {
            "status": "safe_abort_confirmed",
            "basis": "synthetic_simulator_post_state",
            "external_system_verified": False,
            "pilot_checked": len(pilot),
            "completed_compliant": sum(
                by_id[device]["current_firmware"] ==
                by_id[device]["target_firmware"]
                for device in result.get("completed", [])
            ),
            "quarantined_noncompliant": sum(
                device in sim.quarantined and
                by_id[device]["current_firmware"] !=
                by_id[device]["target_firmware"]
                for device in hung
            ),
            "remainder_untouched": sum(
                by_id[device]["current_firmware"] !=
                by_id[device]["target_firmware"]
                for device in remainder
            ),
            "expansion_started": False,
            "alerts_before": alerts_before,
            "alerts_after": len(sim.active_alerts()),
        }
        if (verification["completed_compliant"] != completed or
                verification["quarantined_noncompliant"] != len(hung) or
                verification["remainder_untouched"] != len(remainder)):
            verification = {**verification, "status": "attention"}
        journal.log("verify", verification)
        return {"outcome": "aborted", "pilot_size": len(pilot),
                "pilot_completed": completed,
                "completed_devices": sorted(result.get("completed", [])),
                "hung": sorted(hung),
                "quarantined": sorted(sim.quarantined),
                "fleet_untouched": len(remainder),
                "watchdog_checks": ticks,
                "verification": verification}

    journal.log("rollout_pilot_verified", {
        "pilot": pilot, "outcome": "clean"})
    by_id = {record["device_id"]: record
             for record in sim.inventory_records(devices)}
    verification = {
        "status": "pilot_verified",
        "basis": "synthetic_simulator_post_state",
        "external_system_verified": False,
        "pilot_checked": len(pilot),
        "completed_compliant": sum(
            by_id[device]["current_firmware"] ==
            by_id[device]["target_firmware"]
            for device in result.get("completed", [])
        ),
        "quarantined_noncompliant": 0,
        "remainder_untouched": sum(
            by_id[device]["current_firmware"] !=
            by_id[device]["target_firmware"]
            for device in remainder
        ),
        "expansion_started": False,
        "alerts_before": alerts_before,
        "alerts_after": len(sim.active_alerts()),
    }
    if (verification["completed_compliant"] != completed or
            verification["remainder_untouched"] != len(remainder)):
        verification = {**verification, "status": "attention"}
    journal.log("verify", verification)
    return {"outcome": "pilot_clean", "pilot_size": len(pilot),
            "pilot_completed": completed,
            "completed_devices": sorted(result.get("completed", [])),
            "hung": [],
            "remaining_devices": remainder,
            "fleet_untouched": len(remainder), "watchdog_checks": ticks,
            "verification": verification}
