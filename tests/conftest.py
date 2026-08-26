"""Shared fixtures for deterministic, network-free FleetPilot tests."""

import pytest
from fastapi.testclient import TestClient

import web.app as web_app
from agent.journal import Journal


@pytest.fixture(autouse=True)
def disable_model_credentials(monkeypatch):
    """Tests must never inherit a developer or CI model credential."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delenv("GEMINI_BACKEND", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)


@pytest.fixture
def memory_journal():
    journal = Journal(":memory:")
    try:
        yield journal
    finally:
        journal.conn.close()


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """Give each API test an isolated append-only journal and app state."""
    monkeypatch.chdir(tmp_path)
    isolated_state = web_app.AppState()
    monkeypatch.setattr(web_app, "state", isolated_state)
    with TestClient(web_app.app, raise_server_exceptions=False) as client:
        yield client
    isolated_state.db_journal.conn.close()
