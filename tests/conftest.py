"""Shared fixtures for deterministic, network-free FleetPilot tests."""

from collections import OrderedDict

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
    isolated_browser_states = OrderedDict()
    monkeypatch.setattr(web_app, "state", isolated_state)
    monkeypatch.setattr(web_app, "browser_states", isolated_browser_states)
    with TestClient(web_app.app, raise_server_exceptions=False) as client:
        yield client
    for browser_state in isolated_browser_states.values():
        browser_state.db_journal.conn.close()
    isolated_state.db_journal.conn.close()
