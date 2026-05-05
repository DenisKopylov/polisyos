"""Tests for token estimator."""

from __future__ import annotations

from unittest.mock import patch

from polisyos.scientist.llm.token_estimator import (
    estimate_request_tokens,
    estimate_tokens,
)


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_basic_estimation(self):
        result = estimate_tokens("Hello, world!")
        assert result > 0

    def test_long_text(self):
        text = "word " * 1000
        result = estimate_tokens(text)
        assert result > 100  # At least some tokens

    def test_returns_int(self):
        assert isinstance(estimate_tokens("test"), int)

    def test_fallback_is_conservative_and_provider_aware(self):
        text = "a" * 120
        with patch(
            "polisyos.scientist.llm.token_estimator._tiktoken_count",
            side_effect=RuntimeError("no tokenizer"),
        ):
            openai_tokens = estimate_tokens(text, provider_hint="openai")
            anthropic_tokens = estimate_tokens(text, provider_hint="anthropic")

        assert openai_tokens >= 40
        assert anthropic_tokens >= openai_tokens


class TestEstimateRequestTokens:
    def test_system_and_user(self):
        tokens = estimate_request_tokens(system="You are helpful.", user="Hi")
        assert tokens > 0

    def test_user_only(self):
        tokens = estimate_request_tokens(user="Hello")
        assert tokens > 0

    def test_with_tools(self):
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        tokens_no_tools = estimate_request_tokens(user="Hi")
        tokens_with_tools = estimate_request_tokens(user="Hi", tools=tools)
        assert tokens_with_tools > tokens_no_tools

    def test_with_explicit_messages_transcript(self):
        short_tokens = estimate_request_tokens(messages=[{"role": "user", "content": "Hi"}])
        transcript_tokens = estimate_request_tokens(
            system="ignored when messages are provided",
            user="ignored when messages are provided",
            messages=[
                {"role": "system", "content": "policy"},
                {"role": "user", "content": "collect evidence"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "tc-1",
                            "type": "function",
                            "function": {
                                "name": "echo_tool",
                                "arguments": '{"text": "hello"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "tc-1",
                    "content": '{"echo": "hello"}',
                },
            ],
        )
        assert transcript_tokens > short_tokens

    def test_empty_returns_minimum(self):
        tokens = estimate_request_tokens()
        assert tokens >= 1

    def test_request_estimation_includes_provider_aware_tool_overhead(self):
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        with patch(
            "polisyos.scientist.llm.token_estimator._tiktoken_count",
            side_effect=RuntimeError("no tokenizer"),
        ):
            tokens = estimate_request_tokens(
                user="hello",
                tools=tools,
                model="claude-3-7-sonnet",
            )

        assert tokens >= 40
