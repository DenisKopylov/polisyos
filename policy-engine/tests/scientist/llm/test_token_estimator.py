"""Tests for token estimator."""

from __future__ import annotations

import pytest

from polisyos.scientist.llm.token_estimator import (
    estimate_tokens,
    estimate_request_tokens,
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

    def test_empty_returns_minimum(self):
        tokens = estimate_request_tokens()
        assert tokens >= 1
