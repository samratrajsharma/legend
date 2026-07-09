"""Tests for knowit.providers — model-string resolution and key/connection checks."""
from __future__ import annotations

from knowit.providers import ORDER, PROVIDERS, key_present, resolve
# Aliased: importing the production `test_connection` under its own name would
# make pytest try to collect it as a test case.
from knowit.providers import test_connection as check_connection


def test_resolve_prefixes_model():
    assert resolve("anthropic", "claude-3-5-haiku-latest") == (
        "anthropic/claude-3-5-haiku-latest", {})
    assert resolve("groq", "llama-3.1-8b-instant") == (
        "groq/llama-3.1-8b-instant", {})


def test_resolve_adds_base_url_for_local_providers():
    model, extra = resolve("ollama", "llama3.1")
    assert model == "ollama/llama3.1"
    assert extra["api_base"] == "http://localhost:11434"
    # explicit override wins over the default
    _, extra2 = resolve("ollama", "llama3.1", base_url="http://host:9999/")
    assert extra2["api_base"] == "http://host:9999/"


def test_resolve_raw_passthrough_and_empties():
    assert resolve("", "gpt-4o") == ("gpt-4o", {})       # no provider => raw string
    assert resolve("openai", "") == ("", {})             # no model => empty
    assert resolve("unknown-provider", "m") == ("m", {})  # unknown => raw


def test_key_present(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert key_present("openai") is False
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert key_present("openai") is True
    assert key_present("ollama") is True          # no key required
    assert key_present("unknown") is True          # unknown => assume present


def test_connection_no_model_short_circuits():
    # must not touch the network when no model is configured
    assert check_connection("") == (False, "no model configured")


def test_provider_registry_shape():
    assert ORDER[0] == ""                          # "" = no LLM option
    for name in ("openai", "anthropic", "groq", "ollama", "openrouter", "custom"):
        assert name in PROVIDERS
        p = PROVIDERS[name]
        assert {"label", "key_env", "prefix", "models"} <= set(p)
