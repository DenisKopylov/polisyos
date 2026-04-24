"""Tests for fallback router."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from polisyos.scientist.llm.fallback_router import (
    EndpointConfig,
    FallbackRouter,
)
from polisyos.scientist.llm.gateway_client import GatewayLLMResponse, GatewayUsage


def _ok_response(content: str = "ok") -> GatewayLLMResponse:
    return GatewayLLMResponse(content=content, usage=GatewayUsage())


@pytest.fixture
def two_endpoints():
    return [
        EndpointConfig(url="http://primary.test", api_key="k1", model="m1", priority=0),
        EndpointConfig(url="http://secondary.test", api_key="k2", model="m2", priority=1),
    ]


class TestFallbackRouter:
    def test_empty_endpoints_raises(self):
        with pytest.raises(ValueError, match="At least one endpoint"):
            FallbackRouter([])

    @pytest.mark.asyncio
    async def test_primary_success(self, two_endpoints):
        router = FallbackRouter(two_endpoints)
        with patch(
            "polisyos.scientist.llm.fallback_router.GatewayLLMClient.generate",
            new_callable=AsyncMock,
            return_value=_ok_response("primary"),
        ):
            result = await router.generate(user="hi")
            assert result.content == "primary"

    @pytest.mark.asyncio
    async def test_failover_to_secondary(self, two_endpoints):
        call_count = 0

        async def _mock_generate(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("primary down")
            return _ok_response("secondary")

        router = FallbackRouter(two_endpoints)
        with patch(
            "polisyos.scientist.llm.fallback_router.GatewayLLMClient.generate",
            side_effect=_mock_generate,
        ):
            result = await router.generate(user="hi")
            assert result.content == "secondary"

    @pytest.mark.asyncio
    async def test_all_endpoints_down(self, two_endpoints):
        router = FallbackRouter(two_endpoints)
        with (
            patch(
                "polisyos.scientist.llm.fallback_router.GatewayLLMClient.generate",
                new_callable=AsyncMock,
                side_effect=RuntimeError("down"),
            ),
            pytest.raises(RuntimeError, match="All LLM endpoints exhausted"),
        ):
            await router.generate(user="hi")

    @pytest.mark.asyncio
    async def test_failover_emits_degraded_path(self, two_endpoints):
        call_count = 0

        async def _mock_generate(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("primary down")
            return _ok_response("secondary")

        router = FallbackRouter(two_endpoints)
        with (
            patch(
                "polisyos.scientist.llm.fallback_router.GatewayLLMClient.generate",
                side_effect=_mock_generate,
            ),
            patch(
                "polisyos.scientist.llm.fallback_router.emit_degraded_path",
            ) as degraded,
        ):
            result = await router.generate(user="hi")

        assert result.content == "secondary"
        degraded.assert_called_once()

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_is_not_swallowed(self, two_endpoints):
        router = FallbackRouter(two_endpoints)
        with (
            patch(
                "polisyos.scientist.llm.fallback_router.GatewayLLMClient.generate",
                new_callable=AsyncMock,
                side_effect=KeyboardInterrupt("stop"),
            ),
            pytest.raises(KeyboardInterrupt, match="stop"),
        ):
            await router.generate(user="hi")

    def test_endpoint_health_reporting(self, two_endpoints):
        router = FallbackRouter(two_endpoints)
        health = router.endpoint_health()
        assert len(health) == 2
        assert all(h["health"] == "healthy" for h in health)

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, two_endpoints):
        """After failure_threshold failures, endpoint becomes unhealthy
        then recovers after recovery_timeout_s."""
        router = FallbackRouter(
            two_endpoints,
            failure_threshold=2,
            recovery_timeout_s=0.05,  # very short for test
        )
        # Simulate failures on primary
        for state in router._states:
            if state.config.url == "http://primary.test":
                state.record_failure()
                state.record_failure()
                break

        health = router.endpoint_health()
        primary_health = next(h for h in health if h["url"] == "http://primary.test")
        assert primary_health["health"] == "unhealthy"

        # Wait for recovery
        await asyncio.sleep(0.1)

        # Health reporting is read-only; recovery transition happens in routing.
        health = router.endpoint_health()
        primary_health = next(h for h in health if h["url"] == "http://primary.test")
        assert primary_health["health"] == "unhealthy"

        # Should now be available (degraded)
        available = router._available_endpoints()
        urls = {s.config.url for s in available}
        assert "http://primary.test" in urls
        health = router.endpoint_health()
        primary_health = next(h for h in health if h["url"] == "http://primary.test")
        assert primary_health["health"] == "degraded"
