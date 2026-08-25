"""Tool registry — exposes fleet operations to the Strands agent.
Each tool wraps FleetSimulator/PolicyEngine so the agent can OBSERVE and
PROPOSE, but never execute directly."""


def build_tools(sim) -> dict:
    """Return the tool surface exposed to the Strands agent.

    Day-2: decorate these with Strands @tool so the agent can call them.
    Execution-bearing tools route through PolicyEngine.evaluate first.
    """
    return {
        "list_alerts": sim.active_alerts,
        "get_topology": lambda: [{"device": d.device_id, "server": d.server,
                                  "queue": d.queue} for d in sim.devices],
        "propose_action": lambda action: action,  # journal + gate happens upstream
    }
