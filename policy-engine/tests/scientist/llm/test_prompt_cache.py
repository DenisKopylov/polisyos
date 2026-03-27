"""Tests for prompt cache."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from polisyos.scientist.llm.gateway_client import GatewayLLMResponse, GatewayUsage
from polisyos.scientist.llm.prompt_cache import (
    InMemoryPromptCache,
    compute_cache_key,
)


def _make_response(content: str = "cached") -> GatewayLLMResponse:
    return GatewayLLMResponse(content=content, usage=GatewayUsage())


class TestComputeCacheKey:
    def test_deterministic(self):
        k1 = compute_cache_key(system="sys", user="usr", model="m")
        k2 = compute_cache_key(system="sys", user="usr", model="m")
        assert k1 == k2

    def test_different_params_different_keys(self):
        k1 = compute_cache_key(system="sys", user="a", model="m")
        k2 = compute_cache_key(system="sys", user="b", model="m")
        assert k1 != k2

    def test_temperature_affects_key(self):
        k1 = compute_cache_key(user="hi", model="m", temperature=0.0)
        k2 = compute_cache_key(user="hi", model="m", temperature=1.0)
        assert k1 != k2


class TestInMemoryPromptCache:
    def test_hit(self):
        cache = InMemoryPromptCache(maxsize=10)
        resp = _make_response()
        cache.put("key1", resp)
        assert cache.get("key1") is resp

    def test_miss(self):
        cache = InMemoryPromptCache(maxsize=10)
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        cache = InMemoryPromptCache(maxsize=10, default_ttl_s=0.05)
        cache.put("key1", _make_response())
        time.sleep(0.1)
        assert cache.get("key1") is None

    def test_maxsize_eviction(self):
        cache = InMemoryPromptCache(maxsize=2, default_ttl_s=3600)
        cache.put("a", _make_response("a"))
        cache.put("b", _make_response("b"))
        cache.put("c", _make_response("c"))
        # "a" should be evicted (oldest)
        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.get("c") is not None

    def test_size_property(self):
        cache = InMemoryPromptCache(maxsize=10)
        assert cache.size == 0
        cache.put("a", _make_response())
        assert cache.size == 1
        cache.clear()
        assert cache.size == 0
