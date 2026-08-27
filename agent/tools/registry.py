"""Tool registry — exposes scoped fleet operations to the agent workflow.
Each tool wraps FleetSimulator/PolicyEngine so the agent can OBSERVE and
PROPOSE, but never execute directly."""


def build_tools(sim) -> dict:
    """Return the tool surface exposed to the diagnosis/action workflow.

    The registry keeps simulator access narrow and explicit so model-generated
    proposals cannot call arbitrary application functions.
    Execution-bearing tools route through PolicyEngine.evaluate first.
    """
    def supplies_report() -> list[dict]:
        """Fleet supplies telemetry: devices below reorder thresholds.
        Day-2: the agent forecasts run-out from usage history and drafts
        vendor-grouped purchase orders from this."""
        return [
            {"device": d.device_id, "manufacturer": d.manufacturer,
             "model": d.model, "serial_number": d.serial_number,
             "toner_pct": d.toner_pct, "paper_pct": d.paper_pct}
            for d in sim.devices
            if d.toner_pct <= 15 or d.paper_pct <= 10
        ]

    return {
        "list_alerts": sim.active_alerts,
        "get_topology": lambda: [{"device": d.device_id,
                                  "server": d.server, "queue": d.queue,
                                  "ip_address": d.ip_address}
                                 for d in sim.devices],
        "supplies_report": supplies_report,
        "propose_action": lambda action: action,  # journal + gate happens upstream
    }
