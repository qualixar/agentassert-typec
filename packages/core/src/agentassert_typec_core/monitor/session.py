from __future__ import annotations

import asyncio
import threading

from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.evaluator.engine import dispatch_event
from agentassert_typec_core.models.contract import ContractSpecExtended
from agentassert_typec_core.models.decisions import DecisionResult
from agentassert_typec_core.models.events import TypeCEvent, SessionEnd, TurnEnd
from agentassert_typec_core.monitor.drift import DriftTracker
from agentassert_typec_core.monitor.theta import ThetaScorer
from agentassert_typec_core.monitor.violation_log import ViolationLog
from agentassert_typec_core.judge.dispatcher import JudgeDispatcher


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

    def evaluate(self, event: TypeCEvent) -> DecisionResult:
        with self._lock:
            if isinstance(event, TurnEnd):
                self._turn_count += 1
            result = dispatch_event(
                event, self._compiled, self._drift, self._theta, self._violations
            )
            if result.is_deny():
                self._deny_count += 1
            return result

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
