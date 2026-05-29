
from agentassert_typec_proxy.normalizer.anthropic_norm import normalize_anthropic
from agentassert_typec_proxy.normalizer.openai_norm import normalize_openai


class TestAnthropicNormalizer:
    def test_plain_completion(self):
        payload = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024,
        }
        result = normalize_anthropic(payload, "s1", "r1")
        assert result.provider == "anthropic"
        assert result.model == "claude-sonnet-4-20250514"
        assert result.tool_calls == []
        assert not result.stream

    def test_tool_use_message(self):
        payload = {
            "model": "claude-sonnet-4-20250514",
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "t1",
                            "name": "Read",
                            "input": {"path": "/tmp/test.txt"},
                        }
                    ],
                }
            ],
            "max_tokens": 1024,
        }
        result = normalize_anthropic(payload, "s1", "r1")
        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc.name == "Read"
        assert tc.arguments == {"path": "/tmp/test.txt"}

    def test_streaming_request(self):
        payload = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
            "max_tokens": 1024,
        }
        result = normalize_anthropic(payload, "s1", "r1")
        assert result.stream is True


class TestOpenAINormalizer:
    def test_plain_completion(self):
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        result = normalize_openai(payload, "s1", "r1")
        assert result.provider == "openai"
        assert result.tool_calls == []

    def test_tool_call_message(self):
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "c1",
                            "function": {
                                "name": "code_interpreter",
                                "arguments": '{"code": "print(1)"}',
                            },
                        }
                    ],
                }
            ],
        }
        result = normalize_openai(payload, "s1", "r1")
        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc.name == "code_interpreter"
        assert tc.arguments == {"code": "print(1)"}

    def test_invalid_arguments_json(self):
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "c1",
                            "function": {
                                "name": "test",
                                "arguments": "not json",
                            },
                        }
                    ],
                }
            ],
        }
        result = normalize_openai(payload, "s1", "r1")
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].arguments == {}
