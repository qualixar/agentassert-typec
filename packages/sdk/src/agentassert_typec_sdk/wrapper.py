from __future__ import annotations

from typing import Any

from agentassert_typec_core.monitor.session import SessionMonitor


def wrap(client: Any, contract_path: str) -> Any:
    """Wrap an Anthropic or OpenAI client with behavioral contract enforcement.

    Usage:
        from anthropic import Anthropic
        from agentassert_typec_sdk import wrap

        client = wrap(Anthropic(), "contract.yaml")
        # client.messages.create(...) is now enforced

    Supported client types:
        - anthropic.Anthropic
        - anthropic.AsyncAnthropic
        - openai.OpenAI
        - openai.AsyncOpenAI
    """

    monitor = SessionMonitor.from_yaml(contract_path)
    client_type_name = type(client).__module__ + "." + type(client).__name__

    if "anthropic" in client_type_name.lower():
        from agentassert_typec_sdk.wrappers.anthropic_wrapper import WrappedAnthropic
        return WrappedAnthropic(client, monitor)
    elif "openai" in client_type_name.lower():
        from agentassert_typec_sdk.wrappers.openai_wrapper import WrappedOpenAI
        return WrappedOpenAI(client, monitor)
    else:
        raise TypeError(
            f"Unsupported client type: {type(client).__name__}. "
            f"Supported: anthropic.Anthropic, anthropic.AsyncAnthropic, "
            f"openai.OpenAI, openai.AsyncOpenAI. "
            f"For other clients, use the HTTP proxy instead."
        )
