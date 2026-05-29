"""100% coverage for judge/dispatcher.py HTTP paths via mocked httpx."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentassert_typec_core.judge.dispatcher import JudgeDispatcher


def _make_mock_response(json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_data
    return resp


def _mock_async_client(response: MagicMock) -> MagicMock:
    """Return a context-manager mock for httpx.AsyncClient."""
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ===================================================================
# _call_anthropic_haiku — lines 72-98
# ===================================================================

class TestCallAnthropicHaiku:
    @pytest.mark.asyncio
    async def test_pass_verdict(self):
        """PASS response → returns (True, cost > 0)."""
        resp = _make_mock_response({
            "content": [{"type": "text", "text": "PASS"}],
            "usage": {"input_tokens": 100, "output_tokens": 5},
        })
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            with patch("httpx.AsyncClient", return_value=_mock_async_client(resp)):
                d = JudgeDispatcher(model="haiku")
                result, cost = await d._call_anthropic_haiku("test prompt")
            assert result is True
            assert cost > 0.0
        finally:
            del os.environ["ANTHROPIC_API_KEY"]

    @pytest.mark.asyncio
    async def test_fail_verdict(self):
        """FAIL response → returns (False, cost > 0)."""
        resp = _make_mock_response({
            "content": [{"type": "text", "text": "FAIL — did not meet rubric"}],
            "usage": {"input_tokens": 120, "output_tokens": 8},
        })
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            with patch("httpx.AsyncClient", return_value=_mock_async_client(resp)):
                d = JudgeDispatcher(model="haiku")
                result, cost = await d._call_anthropic_haiku("test prompt")
            assert result is False
            assert cost > 0.0
        finally:
            del os.environ["ANTHROPIC_API_KEY"]

    @pytest.mark.asyncio
    async def test_no_content_blocks(self):
        """Empty content list → returns (False, cost)."""
        resp = _make_mock_response({
            "content": [],
            "usage": {"input_tokens": 50, "output_tokens": 2},
        })
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            with patch("httpx.AsyncClient", return_value=_mock_async_client(resp)):
                d = JudgeDispatcher(model="haiku")
                result, cost = await d._call_anthropic_haiku("test prompt")
            assert result is False
        finally:
            del os.environ["ANTHROPIC_API_KEY"]

    @pytest.mark.asyncio
    async def test_non_text_block_skipped(self):
        """Non-text content blocks are ignored."""
        resp = _make_mock_response({
            "content": [
                {"type": "tool_use", "name": "compute"},
                {"type": "text", "text": "PASS"},
            ],
            "usage": {"input_tokens": 80, "output_tokens": 4},
        })
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            with patch("httpx.AsyncClient", return_value=_mock_async_client(resp)):
                d = JudgeDispatcher(model="haiku")
                result, cost = await d._call_anthropic_haiku("test prompt")
            assert result is True
        finally:
            del os.environ["ANTHROPIC_API_KEY"]

    @pytest.mark.asyncio
    async def test_missing_usage_falls_back_to_estimate(self):
        """Missing usage dict → estimator uses len(prompt)//4."""
        resp = _make_mock_response({
            "content": [{"type": "text", "text": "PASS"}],
        })
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            with patch("httpx.AsyncClient", return_value=_mock_async_client(resp)):
                d = JudgeDispatcher(model="haiku")
                result, cost = await d._call_anthropic_haiku("a" * 400)
            assert result is True
            assert cost > 0.0
        finally:
            del os.environ["ANTHROPIC_API_KEY"]

    @pytest.mark.asyncio
    async def test_network_error_returns_fail_safe(self):
        """Network exception → fail-safe (True, 0.0)."""
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(side_effect=ConnectionError("network"))
        cm.__aexit__ = AsyncMock(return_value=False)
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            with patch("httpx.AsyncClient", return_value=cm):
                d = JudgeDispatcher(model="haiku")
                result, cost = await d._call_anthropic_haiku("test prompt")
            assert result is True
            assert cost == 0.0
        finally:
            del os.environ["ANTHROPIC_API_KEY"]


# ===================================================================
# _call_openrouter_free — lines 107-130
# ===================================================================

class TestCallOpenRouterFree:
    @pytest.mark.asyncio
    async def test_pass_verdict(self):
        resp = _make_mock_response({
            "choices": [{"message": {"content": "PASS"}}],
        })
        os.environ["OPENROUTER_API_KEY"] = "or-test-key"
        try:
            with patch("httpx.AsyncClient", return_value=_mock_async_client(resp)):
                d = JudgeDispatcher(model="ds-flash-free")
                result, cost = await d._call_openrouter_free("test prompt")
            assert result is True
            assert cost == 0.0
        finally:
            del os.environ["OPENROUTER_API_KEY"]

    @pytest.mark.asyncio
    async def test_fail_verdict(self):
        resp = _make_mock_response({
            "choices": [{"message": {"content": "FAIL"}}],
        })
        os.environ["OPENROUTER_API_KEY"] = "or-test-key"
        try:
            with patch("httpx.AsyncClient", return_value=_mock_async_client(resp)):
                d = JudgeDispatcher(model="ds-flash-free")
                result, cost = await d._call_openrouter_free("test prompt")
            assert result is False
            assert cost == 0.0
        finally:
            del os.environ["OPENROUTER_API_KEY"]

    @pytest.mark.asyncio
    async def test_empty_choices_triggers_failsafe(self):
        """Empty choices list causes IndexError → fail-safe (True, 0.0)."""
        resp = _make_mock_response({"choices": []})
        os.environ["OPENROUTER_API_KEY"] = "or-test-key"
        try:
            with patch("httpx.AsyncClient", return_value=_mock_async_client(resp)):
                d = JudgeDispatcher(model="free")
                result, cost = await d._call_openrouter_free("test prompt")
            assert result is True  # IndexError caught by except Exception
            assert cost == 0.0
        finally:
            del os.environ["OPENROUTER_API_KEY"]

    @pytest.mark.asyncio
    async def test_network_error_returns_fail_safe(self):
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(side_effect=OSError("network"))
        cm.__aexit__ = AsyncMock(return_value=False)
        os.environ["OPENROUTER_API_KEY"] = "or-test-key"
        try:
            with patch("httpx.AsyncClient", return_value=cm):
                d = JudgeDispatcher(model="ds-flash-free")
                result, cost = await d._call_openrouter_free("test prompt")
            assert result is True
            assert cost == 0.0
        finally:
            del os.environ["OPENROUTER_API_KEY"]


# ===================================================================
# evaluate() — line 59 (failure count increment) + line 62-63 (exception path)
# ===================================================================

class TestEvaluateFullPath:
    @pytest.mark.asyncio
    async def test_evaluate_fail_increments_failure_count(self):
        """evaluate() with FAIL result → _failure_count incremented (line 59)."""
        resp = _make_mock_response({
            "content": [{"type": "text", "text": "FAIL"}],
            "usage": {"input_tokens": 50, "output_tokens": 3},
        })
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            with patch("httpx.AsyncClient", return_value=_mock_async_client(resp)):
                d = JudgeDispatcher(model="haiku", cost_ceiling=10.0)
                result, cost = await d.evaluate("rubric", "content", "s1")
            assert result is False
            assert d._failure_count == 1
            assert d._spent_usd > 0.0
        finally:
            del os.environ["ANTHROPIC_API_KEY"]

    @pytest.mark.asyncio
    async def test_evaluate_pass_no_failure_count(self):
        """evaluate() with PASS result → _failure_count not incremented."""
        resp = _make_mock_response({
            "content": [{"type": "text", "text": "PASS"}],
            "usage": {"input_tokens": 50, "output_tokens": 3},
        })
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            with patch("httpx.AsyncClient", return_value=_mock_async_client(resp)):
                d = JudgeDispatcher(model="haiku", cost_ceiling=10.0)
                result, cost = await d.evaluate("rubric", "content", "s1")
            assert result is True
            assert d._failure_count == 0
        finally:
            del os.environ["ANTHROPIC_API_KEY"]

    @pytest.mark.asyncio
    async def test_evaluate_exception_in_call_returns_fail_safe(self):
        """Unhandled exception inside evaluate() → fail-safe (True, 0.0) (lines 62-63)."""
        d = JudgeDispatcher(model="haiku", cost_ceiling=10.0)
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            with patch.object(d, "_call_anthropic_haiku", side_effect=RuntimeError("boom")):
                result, cost = await d.evaluate("rubric", "content", "s1")
            assert result is True
            assert cost == 0.0
        finally:
            del os.environ["ANTHROPIC_API_KEY"]
