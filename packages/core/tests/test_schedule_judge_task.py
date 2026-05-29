"""100% coverage for monitor/session.py — _schedule_judge_task and schedule_judge_evaluation."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentassert_typec_core.models.contract import (
    ContractSpecExtended,
    InvariantsExtended,
    JudgePredicate,
)
from agentassert_typec_core.monitor.session import SessionMonitor, _schedule_judge_task
from agentassert_typec_core.monitor.theta import ThetaScorer


def _make_jp(action: str = "theta_penalty") -> JudgePredicate:
    return JudgePredicate(rubric="Is the output helpful?", sample_rate=1.0, model="haiku", action_on_fail=action)


def _make_dispatcher(result: tuple[bool, float] = (True, 0.001), raises: Exception | None = None) -> MagicMock:
    dispatcher = MagicMock()
    if raises is not None:
        dispatcher.evaluate = AsyncMock(side_effect=raises)
    else:
        dispatcher.evaluate = AsyncMock(return_value=result)
    dispatcher._model = "haiku"
    return dispatcher


# ===================================================================
# _schedule_judge_task — sync context path (asyncio.run)
# ===================================================================

class TestScheduleJudgeTaskSync:
    def test_pass_result_no_penalty(self):
        """Sync: passed=True → no theta penalty."""
        theta = ThetaScorer()
        _schedule_judge_task(
            _make_dispatcher((True, 0.001)),
            _make_jp("theta_penalty"),
            "output text", "s1", theta,
        )
        assert theta.compute() == 1.0

    def test_fail_result_theta_penalty_applied(self):
        """Sync: passed=False + action=theta_penalty → penalty deducted."""
        theta = ThetaScorer()
        _schedule_judge_task(
            _make_dispatcher((False, 0.001)),
            _make_jp("theta_penalty"),
            "output text", "s1", theta,
        )
        assert theta.compute() < 1.0

    def test_fail_result_non_theta_action_no_penalty(self):
        """Sync: passed=False + action=log → no theta change."""
        theta = ThetaScorer()
        _schedule_judge_task(
            _make_dispatcher((False, 0.001)),
            _make_jp("log"),
            "output text", "s1", theta,
        )
        assert theta.compute() == 1.0

    def test_exception_in_evaluate_swallowed(self):
        """Sync: exception inside _run() is caught silently."""
        theta = ThetaScorer()
        _schedule_judge_task(
            _make_dispatcher(raises=RuntimeError("network error")),
            _make_jp("theta_penalty"),
            "output text", "s1", theta,
        )
        # No exception propagated, theta unchanged
        assert theta.compute() == 1.0


# ===================================================================
# _schedule_judge_task — async context path (create_task)
# ===================================================================

class TestScheduleJudgeTaskAsync:
    @pytest.mark.asyncio
    async def test_async_pass_result_no_penalty(self):
        """Async: create_task path → passed=True, no penalty."""
        theta = ThetaScorer()
        _schedule_judge_task(
            _make_dispatcher((True, 0.001)),
            _make_jp("theta_penalty"),
            "output text", "s1", theta,
        )
        await asyncio.sleep(0.05)
        assert theta.compute() == 1.0

    @pytest.mark.asyncio
    async def test_async_fail_result_theta_penalty(self):
        """Async: create_task path → passed=False, penalty applied."""
        theta = ThetaScorer()
        _schedule_judge_task(
            _make_dispatcher((False, 0.001)),
            _make_jp("theta_penalty"),
            "output text", "s1", theta,
        )
        await asyncio.sleep(0.05)
        assert theta.compute() < 1.0

    @pytest.mark.asyncio
    async def test_async_exception_swallowed(self):
        """Async: exception inside _run() task is silently swallowed."""
        theta = ThetaScorer()
        _schedule_judge_task(
            _make_dispatcher(raises=ValueError("bad")),
            _make_jp("theta_penalty"),
            "output text", "s1", theta,
        )
        await asyncio.sleep(0.05)
        assert theta.compute() == 1.0


# ===================================================================
# schedule_judge_evaluation — line 58 early return
# ===================================================================

class TestScheduleJudgeEvaluationEarlyReturn:
    def test_no_invariants_early_return(self):
        """Covers session.py line 58: return when no process invariants."""
        spec = ContractSpecExtended(
            contractspec="1.0", kind="agent",
            name="no-inv", description="test", version="0.1",
        )
        monitor = SessionMonitor(spec)
        monitor.schedule_judge_evaluation("output", "s1")
        # No exception = early return hit correctly

    def test_invariants_no_process_early_return(self):
        """Covers session.py line 58: return when invariants but no process block."""
        from agentassert_typec_core.models.contract import HardConstraint, ConstraintCheck
        spec = ContractSpecExtended(
            contractspec="1.0", kind="agent",
            name="hard-only", description="test", version="0.1",
            invariants=InvariantsExtended(
                hard=[HardConstraint(
                    name="pii-check",
                    check=ConstraintCheck(field="pii", equals=False),
                )]
            ),
        )
        monitor = SessionMonitor(spec)
        monitor.schedule_judge_evaluation("output", "s1")
