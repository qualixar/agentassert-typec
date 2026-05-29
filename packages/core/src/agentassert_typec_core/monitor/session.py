from __future__ import annotations

import asyncio
import hashlib
import threading
from collections import defaultdict, deque
from typing import TYPE_CHECKING

from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.evaluator.engine import dispatch_event
from agentassert_typec_core.models.contract import ContractSpecExtended
from agentassert_typec_core.models.decisions import DecisionResult
from agentassert_typec_core.models.events import TypeCEvent, PreAction, SessionEnd, TurnEnd
from agentassert_typec_core.monitor.drift import DriftTracker
from agentassert_typec_core.monitor.theta import ThetaScorer
from agentassert_typec_core.monitor.violation_log import ViolationLog
from agentassert_typec_core.judge.dispatcher import JudgeDispatcher

if TYPE_CHECKING:
    from agentassert_typec_core.persistence.sqlite_store import SessionStore


class SessionMonitor:
    def __init__(self, contract: ContractSpecExtended) -> None:
        self._contract = contract
        self._compiled: CompiledContract = CompiledContract.from_spec(contract)
        drift_window = contract.drift.window if contract.drift else 50
        self._drift = DriftTracker(window=drift_window)
        self._theta = ThetaScorer(
            weights=contract.reliability.weights if contract.reliability else None
        )
        self._violations = ViolationLog()
        self._lock = threading.RLock()
        self._turn_count = 0
        self._deny_count = 0
        self._judge_dispatchers: list[JudgeDispatcher] = []
        self._seen_tools_session: set[str] = set()
        self._seen_tools_turn: set[str] = set()

        # Phase 2: persistence store (attached externally via attach_store())
        self._store: "SessionStore | None" = None

        # Phase 3: cost tracking
        self._accumulated_cost_usd: float = 0.0
        self._cost_lock = threading.Lock()

        # Phase 3: repetition guard — MUST have maxlen=1000
        self._tool_call_history: deque[str] = deque(maxlen=1000)
        self._sequence_hash_counts: defaultdict[str, int] = defaultdict(int)

        self._init_judge_dispatchers()

    def _init_judge_dispatchers(self) -> None:
        if self._contract.invariants and self._contract.invariants.process:
            proc = self._contract.invariants.process
            for jp in proc.judge_predicate:
                dispatcher = JudgeDispatcher(
                    cost_ceiling=jp.cost_ceiling_usd_per_session,
                    model=jp.model,
                )
                self._judge_dispatchers.append(dispatcher)

    # ------------------------------------------------------------------
    # Phase 2: Persistence
    # ------------------------------------------------------------------

    def attach_store(self, store: "SessionStore") -> None:
        """Attach a SessionStore and immediately restore persisted state."""
        self._store = store
        self._load_from_store()

    def _load_from_store(self) -> None:
        from agentassert_typec_core.persistence.serializers import (
            load_cost,
            load_drift,
            load_meta,
            load_repetition,
            load_theta,
            load_violations,
        )
        if self._store is None:
            return
        data_theta = self._store.get("theta")
        if data_theta:
            load_theta(self._theta, data_theta)

        data_drift = self._store.get("drift")
        if data_drift:
            load_drift(self._drift, data_drift)

        data_violations = self._store.get("violations")
        if data_violations:
            load_violations(self._violations, data_violations)

        data_meta = self._store.get("session_meta")
        if data_meta:
            load_meta(self, data_meta)

        data_cost = self._store.get("cost")
        if data_cost:
            load_cost(self, data_cost)

        data_rep = self._store.get("repetition")
        if data_rep:
            load_repetition(self, data_rep)

    def _persist_to_store(self) -> None:
        """Mark all state dirty in the store (no IO — write-behind)."""
        from agentassert_typec_core.persistence.serializers import (
            dump_cost,
            dump_drift,
            dump_meta,
            dump_repetition,
            dump_theta,
            dump_violations,
        )
        if self._store is None:
            return
        self._store.put("theta", dump_theta(self._theta))
        self._store.put("drift", dump_drift(self._drift))
        self._store.put("violations", dump_violations(self._violations))
        self._store.put("session_meta", dump_meta(self))
        self._store.put("cost", dump_cost(self))
        self._store.put("repetition", dump_repetition(self))

    # ------------------------------------------------------------------
    # Core evaluation
    # ------------------------------------------------------------------

    def evaluate(self, event: TypeCEvent) -> DecisionResult:
        with self._lock:
            if isinstance(event, TurnEnd):
                self._turn_count += 1
                self._seen_tools_turn.clear()

            # Pass Phase 3 state through to engine
            result = dispatch_event(
                event,
                self._compiled,
                self._drift,
                self._theta,
                self._violations,
                seen_session=self._seen_tools_session,
                seen_turn=self._seen_tools_turn,
                accumulated_cost=self._accumulated_cost_usd,
                tool_history=self._tool_call_history,
                seq_hash_counts=self._sequence_hash_counts,
            )

            if isinstance(event, PreAction) and not result.is_deny():
                self._seen_tools_session.add(event.tool)
                self._seen_tools_turn.add(event.tool)
                # Phase 3: commit to tool call history (skip ignored tools)
                self._commit_to_history(event.tool)

            if result.is_deny():
                self._deny_count += 1

            # Phase 2: mark store dirty (no IO)
            self._persist_to_store()

            return result

    def _commit_to_history(self, tool: str) -> None:
        """Add tool to repetition guard history and update hash counts.
        Skips tools matching repetition_guard_ignore_patterns.
        """
        if self._compiled.repetition_guard_config is None:
            return
        # Check ignore patterns
        for pattern in self._compiled.repetition_guard_ignore_patterns:
            if pattern.search(tool):
                return

        self._tool_call_history.append(tool)
        W = self._compiled.repetition_guard_config.window_size
        if len(self._tool_call_history) >= W:
            window = tuple(list(self._tool_call_history)[-W:])
            seq_key = hashlib.md5("|".join(window).encode()).hexdigest()
            self._sequence_hash_counts[seq_key] += 1

    def schedule_judge_evaluation(self, turn_output: str, session_id: str) -> None:
        if not self._contract.invariants or not self._contract.invariants.process:
            return
        proc = self._contract.invariants.process
        for jp_config in proc.judge_predicate:
            for dispatcher in self._judge_dispatchers:
                if (
                    dispatcher._model == jp_config.model
                    and dispatcher.should_sample(jp_config.sample_rate)
                ):
                    _schedule_judge_task(
                        dispatcher, jp_config, turn_output, session_id, self._theta
                    )
                    break

    def close(self) -> SessionEnd:
        with self._lock:
            # Flush persistence before closing
            self._persist_to_store()
            if self._store is not None:
                self._store.flush()
                self._store.close()
                self._store = None

            theta = self._theta.compute()
            report = self._drift.report()
            return SessionEnd(
                session_id=self._contract.name,
                contract_id=self._contract.name,
                theta=theta,
                drift_report=report,
            )

    @property
    def turn_count(self) -> int:
        return self._turn_count

    @property
    def deny_count(self) -> int:
        return self._deny_count

    @classmethod
    def from_yaml(cls, path: str) -> "SessionMonitor":
        from agentassert_typec_core.dsl.parser import parse_contract
        from agentassert_typec_core.exceptions import ContractLoadError

        result = parse_contract(path)
        if not result.is_valid:
            raise ContractLoadError(f"Invalid contract: {result.errors}")
        return cls(result.contract)


def _schedule_judge_task(
    dispatcher: JudgeDispatcher,
    jp_config,
    turn_output: str,
    session_id: str,
    theta: ThetaScorer,
) -> None:
    async def _run() -> None:
        try:
            passed, cost = await dispatcher.evaluate(
                jp_config.rubric, turn_output, session_id
            )
            if not passed and jp_config.action_on_fail == "theta_penalty":
                theta.apply_penalty(0.03)
        except Exception:
            pass

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())
