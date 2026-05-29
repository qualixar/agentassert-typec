from __future__ import annotations

from agentassert_typec_core.models.events import PreAction
from agentassert_typec_core.monitor.session import SessionMonitor
from agentassert_typec_core.exceptions import ContractBreachError


def build_pre_action(tool_name: str, args: dict, session_id: str, contract_id: str) -> PreAction:
    return PreAction(
        session_id=session_id,
        contract_id=contract_id,
        tool=tool_name,
        args=args,
    )


def check_and_raise(monitor: SessionMonitor, event: PreAction) -> dict | None:
    result = monitor.evaluate(event)
    if result.is_deny():
        raise ContractBreachError(
            violation_name=result.violation_name,
            reason=result.reason,
            tool=event.tool,
            session_id=event.session_id,
            contract_id=event.contract_id,
        )
    if result.is_modify() and result.modified_args:
        return result.modified_args
    return None
