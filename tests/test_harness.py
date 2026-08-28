"""Contracts that keep the safety harness deterministic and offline."""

import os

import harness.run_evals as run_evals


def test_harness_clears_every_supported_model_backend(monkeypatch):
    observed = {}
    for name in (
        "GEMINI_API_KEY",
        "LLM_API_KEY",
        "GLM_API_KEY",
        "LLM_BACKEND",
        "GEMINI_BACKEND",
        "GCP_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
    ):
        monkeypatch.setenv(name, f"should-not-be-visible-{name}")

    def observe_environment():
        observed.update({name: os.environ.get(name) for name in (
            "GEMINI_API_KEY",
            "LLM_API_KEY",
            "GLM_API_KEY",
            "LLM_BACKEND",
            "GEMINI_BACKEND",
            "GCP_PROJECT_ID",
            "GOOGLE_CLOUD_PROJECT",
        )})
        return True

    monkeypatch.setattr(run_evals, "SCENARIOS", [observe_environment])

    assert run_evals.main() == 0
    assert observed == {
        "GEMINI_API_KEY": None,
        "LLM_API_KEY": None,
        "GLM_API_KEY": None,
        "LLM_BACKEND": None,
        "GEMINI_BACKEND": None,
        "GCP_PROJECT_ID": None,
        "GOOGLE_CLOUD_PROJECT": None,
    }
