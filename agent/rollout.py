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
    devices = [d for d in action.get("devices", []) if d not in sim.quarantined]
    pilot, remainder = devices[:PILOT_SIZE], devices[PILOT_SIZE:]

    result = sim.execute({**action, "devices": pilot, "stage": "pilot"})
    journal.log("rollout_pilot", {"pilot": pilot, "result": result})

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
        return {"outcome": "aborted", "pilot": pilot,
                "quarantined": sorted(sim.quarantined), "watchdog_checks": ticks}

    journal.log("rollout_pilot_verified", {
        "pilot": pilot, "outcome": "clean"})
    return {"outcome": "pilot_clean", "pilot": pilot,
            "remaining_devices": remainder, "watchdog_checks": ticks}
