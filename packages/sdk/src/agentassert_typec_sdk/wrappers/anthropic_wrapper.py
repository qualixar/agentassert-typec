from __future__ import annotations

from agentassert_typec_core.models.events import PostAction
from agentassert_typec_core.monitor.session import SessionMonitor
from agentassert_typec_sdk.enforcement import build_pre_action, check_and_raise


class WrappedAnthropic:
    def __init__(self, client, monitor: SessionMonitor):
        self._client = client
        self._monitor = monitor
        self._messages = _WrappedMessages(client, monitor)

    @property
    def messages(self):
        return self._messages

    def __getattr__(self, name):
        return getattr(self._client, name)

    def __repr__(self):
        return f"WrappedAnthropic(contract={self._monitor._contract.name})"


class _WrappedMessages:
    def __init__(self, client, monitor: SessionMonitor):
        self._client = client.messages
        self._monitor = monitor

    def create(self, **kwargs):
        messages = kwargs.get("messages", [])
        tool_name = _extract_anthropic_tool(messages)
        event = build_pre_action(tool_name, kwargs, "sdk-session", self._monitor._contract.name)
        modified = check_and_raise(self._monitor, event)
        if modified:
            kwargs = {**kwargs, **modified}

        response = self._client.create(**kwargs)

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "output_tokens", 0) if usage else 0

        post = PostAction(
            session_id="sdk-session",
            contract_id=self._monitor._contract.name,
            tool=tool_name,
            state={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )
        self._monitor.evaluate(post)
        return response

    def stream(self, **kwargs):
        messages = kwargs.get("messages", [])
        tool_name = _extract_anthropic_tool(messages)
        event = build_pre_action(tool_name, kwargs, "sdk-session", self._monitor._contract.name)
        check_and_raise(self._monitor, event)

        stream = self._client.stream(**kwargs)

        def monitored_stream():
            yield from stream
            self._monitor.evaluate(PostAction(
                session_id="sdk-session",
                contract_id=self._monitor._contract.name,
                tool=tool_name,
            ))

        return monitored_stream()


def _extract_anthropic_tool(messages):
    for msg in messages:
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    return block.get("name", "unknown")
    return "anthropic.messages"
