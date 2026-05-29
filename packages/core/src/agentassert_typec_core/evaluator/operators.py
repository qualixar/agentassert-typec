from __future__ import annotations

from agentassert_typec_core.exceptions import ContractLoadError

try:
    from agentassert_abc.evaluator.operators import evaluate_check  # pragma: no cover

    def _has_abc() -> bool:  # pragma: no cover
        return True  # pragma: no cover
except ImportError:
    evaluate_check = None

    def _has_abc() -> bool:
        return False


def evaluate_abc_check(check: object, state: dict) -> bool:
    if evaluate_check is None:
        raise ContractLoadError(
            "install agentassert-abc for full predicate support"
        )
    return evaluate_check(check, state)
