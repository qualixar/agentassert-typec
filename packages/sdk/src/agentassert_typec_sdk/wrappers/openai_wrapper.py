from __future__ import annotations


from agentassert_typec_core.models.events import PostAction
from agentassert_typec_core.monitor.session import SessionMonitor
from agentassert_typec_sdk.enforcement import build_pre_action, check_and_raise


class WrappedOpenAI:
    def __init__(self, client, monitor: SessionMonitor):
        self._client = client
        self._monitor = monitor
        self._chat = _WrappedChat(client, monitor)

    @property
    def chat(self):
        return self._chat

    def __getattr__(self, name):
        return getattr(self._client, name)

    def __repr__(self):
        return f"WrappedOpenAI(contract={self._monitor._contract.name})"


class _WrappedChat:
    def __init__(self, client, monitor: SessionMonitor):
        self._inner = client.chat
        self._monitor = monitor
        self.completions = _WrappedCompletions(client.chat.completions, monitor)


class _WrappedCompletions:
    def __init__(self, completions, monitor: SessionMonitor):
        self._inner = completions
        self._monitor = monitor

    def create(self, **kwargs):
        messages = kwargs.get("messages", [])
        tool_name = _extract_openai_tool(messages)
        event = build_pre_action(tool_name, kwargs, "sdk-session", self._monitor._contract.name)
        modified = check_and_raise(self._monitor, event)
        if modified:
            kwargs = {**kwargs, **modified}

        response = self._inner.create(**kwargs)

        post = PostAction(
            session_id="sdk-session",
            contract_id=self._monitor._contract.name,
            tool=tool_name,
            state={
                "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                "output_tokens": getattr(response.usage, "completion_tokens", 0),
            },
        )
        self._monitor.evaluate(post)
        return response


def _extract_openai_tool(messages):
    for msg in messages:
        tool_calls = msg.get("tool_calls", [])
        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            if name:
                return name
    return "openai.chat.completion"
