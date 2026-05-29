"""Tests for upstream URL override (v0.5 feature)."""
from __future__ import annotations

import os

import pytest

from agentassert_typec_proxy.forwarder import provider_url


def test_default_anthropic():
    assert provider_url("anthropic") == "https://api.anthropic.com"


def test_default_openai():
    assert provider_url("openai") == "https://api.openai.com"


def test_contract_override_anthropic():
    overrides = {"anthropic": "https://api.deepseek.com/anthropic"}
    assert provider_url("anthropic", overrides) == "https://api.deepseek.com/anthropic"


def test_contract_override_openai():
    overrides = {"openai": "https://api.deepseek.com/v1"}
    assert provider_url("openai", overrides) == "https://api.deepseek.com/v1"


def test_contract_override_strips_trailing_slash():
    overrides = {"anthropic": "https://api.deepseek.com/anthropic/"}
    assert provider_url("anthropic", overrides) == "https://api.deepseek.com/anthropic"


def test_env_var_typec_upstream_anthropic(monkeypatch):
    monkeypatch.setenv("TYPEC_UPSTREAM_ANTHROPIC", "https://my-custom.llm/anthropic")
    assert provider_url("anthropic") == "https://my-custom.llm/anthropic"


def test_env_var_anthropic_base_url(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
    assert provider_url("anthropic") == "https://api.deepseek.com/anthropic"


def test_env_var_openai_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    assert provider_url("openai") == "https://api.deepseek.com/v1"


def test_contract_overrides_env_var(monkeypatch):
    """Contract upstream takes priority over env vars."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://env-value.example.com")
    overrides = {"anthropic": "https://contract-value.example.com"}
    assert provider_url("anthropic", overrides) == "https://contract-value.example.com"


def test_empty_contract_override_falls_through_to_env(monkeypatch):
    """Empty string in overrides dict falls through to env var."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://env-fallback.example.com")
    overrides = {"anthropic": ""}
    assert provider_url("anthropic", overrides) == "https://env-fallback.example.com"


def test_unknown_provider_returns_empty():
    assert provider_url("unknown_provider") == ""
