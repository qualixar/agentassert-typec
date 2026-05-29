import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "contracts"


class TestWrapAnthropic:
    def test_wrap_anthropic_type(self):
        from agentassert_typec_sdk.wrapper import wrap

        client = _FakeAnthropic()
        wrapped = wrap(client, str(FIXTURES / "safety-minimal.yaml"))
        assert "WrappedAnthropic" in repr(wrapped)

    def test_messages_create_passes_with_allowed_tool(self):
        from agentassert_typec_sdk.wrapper import wrap

        client = _FakeAnthropic()
        wrapped = wrap(client, str(FIXTURES / "safety-minimal.yaml"))
        resp = wrapped.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {}}]}],
            max_tokens=1024,
        )
        assert resp["status"] == "ok"

    def test_messages_create_denies_blocked_tool(self):
        from agentassert_typec_sdk.wrapper import wrap
        from agentassert_typec_core.exceptions import ContractBreachError

        client = _FakeAnthropic()
        wrapped = wrap(client, str(FIXTURES / "safety-minimal.yaml"))
        with pytest.raises(ContractBreachError):
            wrapped.messages.create(
                model="claude-sonnet-4-20250514",
                messages=[{"role": "user", "content": [{"type": "tool_use", "id": "t1", "name": "bash", "input": {}}]}],
                max_tokens=1024,
            )

    def test_unsupported_type_raises(self):
        from agentassert_typec_sdk.wrapper import wrap

        with pytest.raises(TypeError, match="Unsupported"):
            wrap("not_a_client", str(FIXTURES / "safety-minimal.yaml"))


class _FakeAnthropic:
    class messages:
        @staticmethod
        def create(**kwargs):
            return {"status": "ok", "usage": type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()}
