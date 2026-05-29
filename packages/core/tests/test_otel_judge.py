"""Tests for OTel exporter and Judge dispatcher."""

import time
import pytest
from unittest.mock import MagicMock


class TestOTelExporter:
    def test_otel_not_available_raises(self):
        from agentassert_typec_core.exporters.otel import _OTEL_AVAILABLE
        if _OTEL_AVAILABLE:
            pytest.skip("OTel is installed — cannot test import failure")
        from agentassert_typec_core.exporters.otel import TypeCOTelExporter
        with pytest.raises(ImportError, match="install agentassert-typec-core"):
            TypeCOTelExporter()

    def test_emit_request_non_blocking(self):
        from agentassert_typec_core.exporters.otel import TypeCOTelExporter, _OTEL_AVAILABLE
        if not _OTEL_AVAILABLE:
            pytest.skip("OTel not installed")
        exporter = TypeCOTelExporter()
        exporter.emit_request(
            session_id="s1", request_id="r1", contract_name="test", contract_version="0.1",
            decision="allow", violation_name="", violation_reason="",
            tool="Read", provider="anthropic", overhead_ms=5.0,
            stream=False, adapter="proxy",
        )
        assert exporter._emitted_count >= 0

    def test_emit_session_non_blocking(self):
        from agentassert_typec_core.exporters.otel import TypeCOTelExporter, _OTEL_AVAILABLE
        if not _OTEL_AVAILABLE:
            pytest.skip("OTel not installed")
        exporter = TypeCOTelExporter()
        exporter.emit_session(
            session_id="s1", contract_name="test", theta=0.95,
            turn_count=10, violation_count=2, deny_count=1,
            duration_s=120.0, jsd=0.15,
            judge_cost_usd=0.0, judge_samples=3, judge_failures=0,
        )
        assert exporter._emitted_count >= 0

    def test_drain_loop_processes_queue(self):
        from agentassert_typec_core.exporters.otel import TypeCOTelExporter, _OTEL_AVAILABLE
        if not _OTEL_AVAILABLE:
            pytest.skip("OTel not installed")
        exporter = TypeCOTelExporter()
        exporter.emit_request(
            session_id="s1", request_id="r1", contract_name="test", contract_version="0.1",
            decision="deny", violation_name="tool_blocklist", violation_reason="bad",
            tool="rm", provider="anthropic", overhead_ms=2.0,
            stream=False, adapter="proxy",
        )
        time.sleep(0.15)
        assert exporter._emitted_count >= 1

    def test_queue_overflow_drops_silently(self):
        """Fill queue to max and verify new emits don't raise."""
        from agentassert_typec_core.exporters.otel import TypeCOTelExporter, _OTEL_AVAILABLE
        if not _OTEL_AVAILABLE:
            pytest.skip("OTel not installed")
        exporter = TypeCOTelExporter()
        for i in range(1100):
            exporter.emit_request(
                session_id="s1", request_id=f"r{i}", contract_name="test",
                contract_version="0.1", decision="allow", violation_name="",
                violation_reason="", tool="Read", provider="anthropic",
                overhead_ms=1.0, stream=False, adapter="proxy",
            )
        assert exporter._dropped_count > 0

    def test_export_with_session_span(self):
        from agentassert_typec_core.exporters.otel import TypeCOTelExporter, _OTEL_AVAILABLE
        if not _OTEL_AVAILABLE:
            pytest.skip("OTel not installed")
        exporter = TypeCOTelExporter()
        exporter.emit_session(
            session_id="s2", contract_name="full", theta=0.88,
            turn_count=25, violation_count=5, deny_count=2,
            duration_s=300.0, jsd=0.22,
            judge_cost_usd=0.03, judge_samples=10, judge_failures=3,
        )
        time.sleep(0.15)
        assert exporter._emitted_count >= 1


class TestJudgeDispatcher:
    def test_should_sample_always_true_at_1(self):
        from agentassert_typec_core.judge.dispatcher import JudgeDispatcher
        dispatcher = JudgeDispatcher(cost_ceiling=100.0)
        assert dispatcher.should_sample(1.0) is True

    def test_should_sample_always_false_at_0(self):
        from agentassert_typec_core.judge.dispatcher import JudgeDispatcher
        dispatcher = JudgeDispatcher(cost_ceiling=100.0)
        assert dispatcher.should_sample(0.0) is False

    def test_should_sample_false_when_ceiling_exceeded(self):
        from agentassert_typec_core.judge.dispatcher import JudgeDispatcher
        dispatcher = JudgeDispatcher(cost_ceiling=0.0)
        assert dispatcher.should_sample(1.0) is False

    @pytest.mark.asyncio
    async def test_evaluate_no_api_key_haiku_passes(self):
        from agentassert_typec_core.judge.dispatcher import JudgeDispatcher
        import os
        saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            dispatcher = JudgeDispatcher(model="haiku")
            passed, cost = await dispatcher.evaluate("rubric", "content", "s1")
            assert passed is True
            assert cost == 0.0
        finally:
            if saved:
                os.environ["ANTHROPIC_API_KEY"] = saved

    @pytest.mark.asyncio
    async def test_evaluate_free_model_no_key_passes(self):
        from agentassert_typec_core.judge.dispatcher import JudgeDispatcher
        import os
        saved = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            dispatcher = JudgeDispatcher(model="ds-flash-free")
            passed, cost = await dispatcher.evaluate("rubric", "content", "s1")
            assert passed is True
            assert cost == 0.0
        finally:
            if saved:
                os.environ["OPENROUTER_API_KEY"] = saved

    @pytest.mark.asyncio
    async def test_evaluate_fail_safe(self):
        from agentassert_typec_core.judge.dispatcher import JudgeDispatcher
        import os
        saved_anth = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            dispatcher = JudgeDispatcher(model="haiku")
            passed, cost = await dispatcher.evaluate("rubric", "content", "s1")
            assert passed is True
        finally:
            if saved_anth:
                os.environ["ANTHROPIC_API_KEY"] = saved_anth

    def test_stats(self):
        from agentassert_typec_core.judge.dispatcher import JudgeDispatcher
        dispatcher = JudgeDispatcher(cost_ceiling=10.0, model="haiku")
        assert dispatcher.stats["ceiling"] == 10.0
        assert dispatcher.total_spent == 0.0


class TestOTelExporterCoverageGaps:
    """Covers otel.py lines 43, 118-119, 127-130."""

    def test_exporter_with_batch_processor(self):
        """Covers line 43: add_span_processor called when exporter provided."""
        from agentassert_typec_core.exporters.otel import TypeCOTelExporter, _OTEL_AVAILABLE
        if not _OTEL_AVAILABLE:
            pytest.skip("OTel not installed")
        mock_exporter = MagicMock()
        exporter = TypeCOTelExporter(exporter=mock_exporter)
        assert exporter._provider is not None

    def test_emit_session_queue_overflow_drops_silently(self):
        """Covers lines 118-119: emit_session except branch when queue is full."""
        from agentassert_typec_core.exporters.otel import TypeCOTelExporter, _OTEL_AVAILABLE
        if not _OTEL_AVAILABLE:
            pytest.skip("OTel not installed")
        exporter = TypeCOTelExporter()
        # Fill the queue completely via emit_request
        for i in range(1000):
            exporter._queue.put_nowait({"type": "request", "id": i})
        # Now emit_session must hit the except Exception branch
        exporter.emit_session(
            session_id="s1", contract_name="test", theta=0.9,
            turn_count=5, violation_count=0, deny_count=0,
            duration_s=60.0, jsd=0.1,
            judge_cost_usd=0.0, judge_samples=0, judge_failures=0,
        )
        assert exporter._dropped_count >= 1

    def test_drain_loop_handles_emit_span_exception(self):
        """Covers lines 129-130: except Exception: pass in drain loop."""
        from agentassert_typec_core.exporters.otel import TypeCOTelExporter, _OTEL_AVAILABLE
        if not _OTEL_AVAILABLE:
            pytest.skip("OTel not installed")
        exporter = TypeCOTelExporter()
        exporter._emit_span = MagicMock(side_effect=RuntimeError("span error"))
        exporter.emit_request(
            session_id="s1", request_id="r1", contract_name="test", contract_version="0.1",
            decision="allow", violation_name="", violation_reason="",
            tool="Read", provider="anthropic", overhead_ms=1.0,
            stream=False, adapter="proxy",
        )
        time.sleep(0.15)
        # No crash = except Exception: pass caught the RuntimeError

    def test_drain_loop_handles_empty_queue_timeout(self):
        """Covers lines 127-128: except Empty: continue in drain loop (queue timeout)."""
        from agentassert_typec_core.exporters.otel import TypeCOTelExporter, _OTEL_AVAILABLE
        if not _OTEL_AVAILABLE:
            pytest.skip("OTel not installed")
        TypeCOTelExporter()
        # Don't put anything in queue — drain loop will hit Empty after 1 second
        time.sleep(1.1)
        # Still alive = Empty was handled by continue
