from __future__ import annotations

import time
import threading
from queue import Queue, Empty
from typing import Any

try:
    from opentelemetry import trace  # noqa: F401
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
    from opentelemetry.trace import SpanKind, Status, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OTEL_AVAILABLE = False  # pragma: no cover


class TypeCOTelExporter:
    """Fire-and-forget OTel exporter for AgentAssert Type-C.

    Architecture (verified against OTel Python SDK BatchSpanProcessor):
    - Main thread: emit_*() → put event on queue (non-blocking, drops on overflow)
    - Background daemon thread: drain queue → create spans → auto-export via BatchSpanProcessor
    - Queue max: 1000 (LIFO semantic — newest data matters more for diagnostics)

    This ensures OTel telemetry NEVER adds to p99 latency.
    """

    def __init__(
        self,
        exporter: SpanExporter | None = None,
        service_name: str = "agentassert-typec",
    ) -> None:
        if not _OTEL_AVAILABLE:  # pragma: no cover
            raise ImportError(  # pragma: no cover
                "opentelemetry-api and opentelemetry-sdk required. "
                "Install: pip install agentassert-typec-core[otel]"
            )
        self._queue: Queue[dict[str, Any]] = Queue(maxsize=1000)
        self._provider = TracerProvider()
        if exporter:
            self._provider.add_span_processor(BatchSpanProcessor(exporter))
        self._tracer = self._provider.get_tracer("agentassert.typec", "0.4.0")
        self._service_name = service_name
        self._worker = threading.Thread(target=self._drain_loop, daemon=True)
        self._worker.start()
        self._dropped_count = 0
        self._emitted_count = 0

    def emit_request(
        self,
        session_id: str,
        request_id: str,
        contract_name: str,
        contract_version: str,
        decision: str,
        violation_name: str,
        violation_reason: str,
        tool: str,
        provider: str,
        overhead_ms: float,
        stream: bool,
        adapter: str,
    ) -> None:
        event = {
            "type": "request",
            "session_id": session_id,
            "request_id": request_id,
            "contract_name": contract_name,
            "contract_version": contract_version,
            "decision": decision,
            "violation_name": violation_name,
            "violation_reason": violation_reason,
            "tool": tool,
            "provider": provider,
            "overhead_ms": overhead_ms,
            "stream": stream,
            "adapter": adapter,
            "timestamp": time.time(),
        }
        try:
            self._queue.put_nowait(event)
        except Exception:
            self._dropped_count += 1

    def emit_session(
        self,
        session_id: str,
        contract_name: str,
        theta: float,
        turn_count: int,
        violation_count: int,
        deny_count: int,
        duration_s: float,
        jsd: float,
        judge_cost_usd: float,
        judge_samples: int,
        judge_failures: int,
    ) -> None:
        event = {
            "type": "session",
            "session_id": session_id,
            "contract_name": contract_name,
            "theta": theta,
            "turn_count": turn_count,
            "violation_count": violation_count,
            "deny_count": deny_count,
            "duration_s": duration_s,
            "jsd": jsd,
            "judge_cost_usd": judge_cost_usd,
            "judge_samples": judge_samples,
            "judge_failures": judge_failures,
            "timestamp": time.time(),
        }
        try:
            self._queue.put_nowait(event)
        except Exception:
            self._dropped_count += 1

    def _drain_loop(self) -> None:
        while True:
            try:
                event = self._queue.get(timeout=1.0)
                self._emit_span(event)
                self._emitted_count += 1
            except Empty:
                continue
            except Exception:
                pass

    def _emit_span(self, event: dict[str, Any]) -> None:
        event_type = event["type"]
        span_name = f"agentassert.typec.{event_type}"

        with self._tracer.start_as_current_span(span_name, kind=SpanKind.INTERNAL) as span:
            if event_type == "request":
                span.set_attributes({
                    "agentassert.typec.request.id": event["request_id"],
                    "agentassert.typec.session.id": event["session_id"],
                    "agentassert.typec.contract.name": event["contract_name"],
                    "agentassert.typec.contract.version": event["contract_version"],
                    "agentassert.typec.decision": event["decision"],
                    "agentassert.typec.violation.name": event["violation_name"],
                    "agentassert.typec.violation.reason": event["violation_reason"],
                    "agentassert.typec.tool": event["tool"],
                    "agentassert.typec.provider": event["provider"],
                    "agentassert.typec.proxy.overhead_ms": event["overhead_ms"],
                    "agentassert.typec.stream": event["stream"],
                    "agentassert.typec.adapter": event["adapter"],
                    "service.name": self._service_name,
                })
                if event["decision"] == "deny":
                    span.set_status(Status(StatusCode.ERROR, event["violation_reason"]))

            elif event_type == "session":
                span.set_attributes({
                    "agentassert.typec.session.id": event["session_id"],
                    "agentassert.typec.session.contract": event["contract_name"],
                    "agentassert.typec.session.theta": event["theta"],
                    "agentassert.typec.session.turn_count": event["turn_count"],
                    "agentassert.typec.session.violation_count": event["violation_count"],
                    "agentassert.typec.session.deny_count": event["deny_count"],
                    "agentassert.typec.session.duration_s": event["duration_s"],
                    "agentassert.typec.drift.jsd": event["jsd"],
                    "agentassert.typec.judge.cost_usd": event["judge_cost_usd"],
                    "agentassert.typec.judge.samples": event["judge_samples"],
                    "agentassert.typec.judge.failures": event["judge_failures"],
                    "service.name": self._service_name,
                })
