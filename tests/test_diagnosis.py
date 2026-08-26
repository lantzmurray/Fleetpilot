"""Unit tests for deterministic and Gemini-backed diagnosis behavior."""

import json
from types import SimpleNamespace

from google import genai
from google.genai import types

import agent.diagnosis as diagnosis_module
from agent.diagnosis import Diagnosis, diagnose, gemini_diagnose, heuristic_diagnose
from agent.fleet_sim import FleetSimulator
from agent.main import run_tick
from agent.policy.risk import PolicyEngine


def queue_alerts() -> list[dict]:
    sim = FleetSimulator.seed()
    sim.inject_scenario("queue_hang")
    return sim.active_alerts()


class FakeModels:
    def __init__(self, response_text=None, error=None):
        self.response_text = response_text
        self.error = error
        self.models_seen: list[str] = []
        self.requests_seen: list[tuple[str, object]] = []

    def generate_content(self, *, model, contents, config):
        self.models_seen.append(model)
        self.requests_seen.append((contents, config))
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.response_text)


def install_fake_client(monkeypatch, models: FakeModels):
    clients = []

    def factory(*, api_key):
        clients.append(api_key)
        return SimpleNamespace(models=models)

    monkeypatch.setattr(genai, "Client", factory)
    return clients


def test_empty_alerts_have_a_noop_diagnosis():
    result = heuristic_diagnose([])

    assert result == Diagnosis(
        root_cause="no active alerts",
        confidence=1.0,
        affected_nodes=[],
        proposed_actions=[],
        source="heuristic",
    )


def test_default_model_uses_the_live_verified_contest_primary(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    assert diagnosis_module.model_candidates()[0] == "gemini-3.6-flash"


def test_queue_alerts_collapse_to_one_server_level_remediation():
    result = heuristic_diagnose(queue_alerts())

    assert "job_stuck" in result.root_cause
    assert "30 of 30" in result.root_cause
    assert result.confidence == 1.0
    assert len(result.proposed_actions) == 1
    assert result.proposed_actions[0]["kind"] == "restart_queue"
    assert len(result.proposed_actions[0]["devices"]) == 30


def test_firmware_drift_collapses_to_one_fleet_wide_compliance_action():
    sim = FleetSimulator.seed()
    sim.inject_scenario("firmware_drift")

    result = heuristic_diagnose(sim.active_alerts())

    assert "30 of 30" in result.root_cause
    assert result.proposed_actions[0]["kind"] == "update_firmware"
    assert len(result.proposed_actions[0]["devices"]) == 30


def test_model_pin_is_resolved_at_call_time(monkeypatch):
    """A value loaded after module import must control the next SDK call."""
    payload = json.dumps({
        "root_cause": "verified queue hang",
        "confidence": 0.93,
        "affected_nodes": [{"server": "srv-east-1", "queue": "*"}],
        "proposed_actions": [{
            "kind": "restart_queue",
            "devices": ["DEV-0000"],
            "rationale": "restart the affected spooler",
        }],
    })
    models = FakeModels(response_text=payload)
    install_fake_client(monkeypatch, models)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-runtime-pin")

    heuristic = heuristic_diagnose(queue_alerts())
    result = gemini_diagnose(queue_alerts(), heuristic, api_key="test-key")

    assert result.source == "gemini"
    assert models.models_seen == ["gemini-runtime-pin"]
    assert diagnosis_module.last_model_used == "gemini-runtime-pin"


def test_gemini_request_is_compact_and_uses_demo_latency_controls(monkeypatch):
    payload = json.dumps({
        "root_cause": "verified queue hang",
        "confidence": 0.93,
        "affected_nodes": [{"server": "srv-east-1", "queue": "*"}],
        "proposed_actions": [{
            "kind": "restart_queue",
            "devices": ["DEV-0000"],
            "rationale": "restart the affected spooler",
        }],
    })
    models = FakeModels(response_text=payload)
    install_fake_client(monkeypatch, models)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")

    gemini_diagnose(
        queue_alerts(), heuristic_diagnose(queue_alerts()), api_key="test-key")

    contents, config = models.requests_seen[0]
    assert len(contents) < 3500
    assert '"alert_count":30' in contents
    assert "'severity':" not in contents
    # generous cap: thinking tokens count against it; 1024 truncated JSON
    assert config.max_output_tokens >= 4096
    assert config.thinking_config.thinking_level is types.ThinkingLevel.MINIMAL


def test_gemini_37_uses_a_supported_low_thinking_level(monkeypatch):
    payload = json.dumps({
        "root_cause": "verified queue hang",
        "confidence": 0.9,
        "proposed_actions": [],
    })
    models = FakeModels(response_text=payload)
    install_fake_client(monkeypatch, models)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.7-flash")

    gemini_diagnose(
        queue_alerts(), heuristic_diagnose(queue_alerts()), api_key="test-key")

    _, config = models.requests_seen[0]
    assert config.thinking_config.thinking_level is types.ThinkingLevel.LOW


def test_successful_failover_clears_the_prior_model_error(monkeypatch):
    payload = json.dumps({
        "root_cause": "verified queue hang",
        "confidence": 0.9,
        "proposed_actions": [],
    })

    class FailOnceModels(FakeModels):
        def generate_content(self, *, model, contents, config):
            self.models_seen.append(model)
            self.requests_seen.append((contents, config))
            if len(self.models_seen) == 1:
                raise RuntimeError("first candidate unavailable")
            return SimpleNamespace(text=payload)

    models = FailOnceModels()
    install_fake_client(monkeypatch, models)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    result = gemini_diagnose(
        queue_alerts(), heuristic_diagnose(queue_alerts()), api_key="test-key")

    assert result.source == "gemini"
    assert models.models_seen[:2] == ["gemini-3.6-flash", "gemini-3.5-flash"]
    assert diagnosis_module.last_model_used == "gemini-3.5-flash"
    assert diagnosis_module.last_fallback_reason is None


def test_model_cascade_shares_one_overall_timeout_budget(monkeypatch):
    submitted_models = []
    timeouts = []

    class FailedFuture:
        def result(self, timeout):
            timeouts.append(timeout)
            raise RuntimeError("candidate unavailable")

    class FakePool:
        def __init__(self, max_workers):
            assert max_workers == 1

        def submit(self, _call, model):
            submitted_models.append(model)
            return FailedFuture()

        def shutdown(self, **_kwargs):
            return None

    clock = iter([0.0, 1.0, 10.0, 15.0])
    monkeypatch.setattr(
        diagnosis_module, "time",
        SimpleNamespace(monotonic=lambda: next(clock)), raising=False)
    monkeypatch.setattr(diagnosis_module, "ThreadPoolExecutor", FakePool)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    models = FakeModels(response_text=None)
    install_fake_client(monkeypatch, models)

    result = gemini_diagnose(
        queue_alerts(), heuristic_diagnose(queue_alerts()), api_key="test-key")

    assert result.source == "heuristic"
    assert submitted_models == ["gemini-3.6-flash", "gemini-3.5-flash"]
    assert timeouts == [13.0, 4.0]
    assert diagnosis_module.last_fallback_reason == "TimeoutError"


def test_no_credentials_never_constructs_a_client(monkeypatch):
    """The normal offline path must be deterministic and make no SDK call."""
    def fail_if_called(**_kwargs):
        raise AssertionError("offline diagnosis attempted to construct a client")

    monkeypatch.setattr(genai, "Client", fail_if_called)

    result = diagnose(queue_alerts())

    assert result.source == "heuristic"
    assert result.proposed_actions[0]["kind"] == "restart_queue"


def test_malformed_gemini_json_falls_back_to_grounded_heuristic(monkeypatch):
    models = FakeModels(response_text="not-json")
    install_fake_client(monkeypatch, models)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    heuristic = heuristic_diagnose(queue_alerts())

    result = gemini_diagnose(queue_alerts(), heuristic, api_key="test-key")

    assert result is heuristic
    assert result.source == "heuristic"
    assert diagnosis_module.last_fallback_reason == "malformed_model_response"


def test_gemini_error_falls_back_without_leaking_the_error(monkeypatch):
    models = FakeModels(error=RuntimeError("simulated quota failure"))
    install_fake_client(monkeypatch, models)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    heuristic = heuristic_diagnose(queue_alerts())

    result = gemini_diagnose(queue_alerts(), heuristic, api_key="test-key")

    assert result is heuristic
    assert models.models_seen == ["gemini-test"]
    assert diagnosis_module.last_model_used is None
    assert diagnosis_module.last_fallback_reason == "RuntimeError"


def test_run_tick_rejects_unknown_actions_and_devices(monkeypatch, memory_journal):
    sim = FleetSimulator.seed()
    sim.inject_scenario("queue_hang")
    proposed = Diagnosis(
        root_cause="untrusted model response",
        confidence=0.8,
        affected_nodes=[],
        proposed_actions=[
            {"kind": "deploy_rootkit", "devices": ["DEV-0000"]},
            {"kind": "restart_queue", "devices": ["GHOST-0001"]},
        ],
        source="gemini",
    )
    monkeypatch.setattr("agent.main.diagnose", lambda _alerts: proposed)
    summary = run_tick(sim, PolicyEngine.defaults(), memory_journal)

    assert summary["executed"] == []
    assert summary["escalated"] == []
    assert summary["blocked"] == []
    rejected = [e for e in memory_journal.replay()
                if e["kind"] == "llm_output_rejected"]
    assert {e["payload"]["reason"] for e in rejected} == {
        "unknown action kind",
        "no known device ids",
    }


def test_run_tick_bounds_confidence_exposed_to_callers(monkeypatch, memory_journal):
    sim = FleetSimulator.seed()
    proposed = Diagnosis(
        root_cause="overconfident model response",
        confidence=9.2,
        affected_nodes=[],
        proposed_actions=[],
        source="gemini",
    )
    monkeypatch.setattr("agent.main.diagnose", lambda _alerts: proposed)

    summary = run_tick(sim, PolicyEngine.defaults(), memory_journal)

    assert summary["confidence"] == 1.0


def test_run_tick_rejects_an_oversized_model_device_list(
        monkeypatch, memory_journal):
    sim = FleetSimulator.seed()
    proposed = Diagnosis(
        root_cause="unsafe broad model response",
        confidence=0.8,
        affected_nodes=[],
        proposed_actions=[{
            "kind": "restart_queue",
            "devices": [d.device_id for d in sim.devices[:51]],
            "rationale": "too broad for a model-selected action",
        }],
        source="gemini",
    )
    monkeypatch.setattr("agent.main.diagnose", lambda _alerts: proposed)
    summary = run_tick(sim, PolicyEngine.defaults(), memory_journal)

    assert summary["executed"] == []
    rejected = [e for e in memory_journal.replay()
                if e["kind"] == "llm_output_rejected"]
    assert rejected[-1]["payload"]["reason"] == "device list exceeds safe bound"


def test_trusted_alert_storm_is_human_gated_not_silently_dropped(
        memory_journal):
    sim = FleetSimulator.seed()
    sim.inject_scenario("alert_storm")

    summary = run_tick(sim, PolicyEngine.defaults(), memory_journal)

    assert summary["executed"] == []
    assert len(summary["escalated"]) == 1
    assert len(summary["escalated"][0]["action"]["devices"]) == 150
    assert "blast radius" in summary["escalated"][0]["reason"]


def test_malformed_model_action_fields_are_rejected_without_exceptions(
        memory_journal):
    from agent.main import validated_actions

    clean = validated_actions([
        {"kind": ["order_supplies"], "devices": [], "rationale": "bad kind"},
        {"kind": "order_supplies", "devices": [], "cost_usd": "<img src=x>",
         "rationale": "unsafe cost"},
        {"kind": "order_supplies", "devices": [], "cost_usd": 25,
         "rationale": {"html": "<script>"}},
    ], {"DEV-0001"}, memory_journal)

    assert clean == []
    reasons = [event["payload"]["reason"] for event in memory_journal.replay()]
    assert reasons == [
        "invalid action kind",
        "invalid cost_usd",
        "invalid rationale",
    ]
