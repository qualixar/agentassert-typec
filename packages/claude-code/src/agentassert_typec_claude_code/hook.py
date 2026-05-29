from __future__ import annotations

import json
import os
import sys

from agentassert_typec_core.models.events import PreAction, PostAction
from agentassert_typec_core.monitor.session import SessionMonitor

_monitor_cache: dict[str, SessionMonitor] = {}


def _get_monitor(contract_path: str) -> SessionMonitor | None:
    if not contract_path:
        return None
    if contract_path in _monitor_cache:
        return _monitor_cache[contract_path]
    try:
        monitor = SessionMonitor.from_yaml(contract_path)
        _monitor_cache[contract_path] = monitor
        return monitor
    except Exception:
        return None


def _type_c_event_from_hook(hook_type: str, data: dict, session_id: str, contract_id: str):
    tool_name = data.get("tool_name", data.get("tool_name_input", {}).get("tool_name", ""))
    if not tool_name:
        tool_name = str(data.get("tool_name_input", ""))

    if hook_type == "PreToolUse":
        return PreAction(
            session_id=session_id,
            contract_id=contract_id,
            tool=tool_name,
            args=data.get("tool_input", {}),
        )
    elif hook_type == "PostToolUse":
        return PostAction(
            session_id=session_id,
            contract_id=contract_id,
            tool=tool_name,
            result=data.get("tool_output", data.get("tool_response")),
        )
    return None


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception:
        print(json.dumps({"action": "allow"}))
        return

    contract_path = os.environ.get("AGENTASSERT_CONTRACT", "")
    monitor = _get_monitor(contract_path)

    if monitor is None:
        print(json.dumps({"action": "allow"}))
        return

    hook_type = data.get("hook_type", data.get("hook_event_name", ""))
    session_id = data.get("session_id", "default")
    contract_id = monitor._contract.name

    event = _type_c_event_from_hook(hook_type, data, session_id, contract_id)

    if event is None:
        print(json.dumps({"action": "allow"}))
        return

    try:
        result = monitor.evaluate(event)
        if result.is_deny():
            print(json.dumps({
                "action": "block",
                "reason": result.reason,
                "violation": result.violation_name,
            }))
        elif result.is_modify() and result.modified_args:
            print(json.dumps({
                "action": "modify",
                "tool_input": result.modified_args,
            }))
        else:
            print(json.dumps({"action": "allow"}))
    except Exception:
        print(json.dumps({"action": "allow"}))


if __name__ == "__main__":
    main()
