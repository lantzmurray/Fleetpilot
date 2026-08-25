"""Tool registry — exposes fleet operations to the Strands agent.
Each tool wraps FleetSimulator/PolicyEngine so the agent can OBSERVE and
PROPOSE, but never execute directly."""


def build_tools(sim) -> dict:
    """Return the tool surface exposed to the Strands agent.

    Day-2: decorate these with Strands @tool so the agent can call them.
    Execution-bearing tools route through PolicyEngine.evaluate first.
    """
    def supplies_report() -> list[dict]:
        """Fleet supplies telemetry: devices below reorder thresholds.
        Day-2: the agent forecasts run-out from usage history and drafts
        vendor-grouped purchase orders from this."""
        return [
            {"device": d.device_id, "model": d.model,
             "toner_pct": d.toner_pct, "paper_pct": d.paper_pct}
            for d in sim.devices
            if d.toner_pct <= 15 or d.paper_pct <= 10
        ]

    return {
        "list_alerts": sim.active_alerts,
        "get_topology": lambda: [{"device": d.device_id, "server": d.server,
                                  "queue": d.queue} for d in sim.devices],
        "supplies_report": supplies_report,
        "propose_action": lambda action: action,  # journal + gate happens upstream
    }
