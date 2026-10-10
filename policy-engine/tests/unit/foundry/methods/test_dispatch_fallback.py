"""
Tests for pluggable fallback strategy in MethodDispatcher (Phase 7).
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from polisyos.foundry.methods.backends.dispatch import (
    FallbackStrategy,
    MethodDispatcher,
    SignatureAwareFallback,
)
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
)

# =============================================================================
# Fixtures
# =============================================================================


def _make_signature(
    *,
    backend: ComputeBackend = ComputeBackend.JAX,
    supports_grad: bool = True,
    supports_vmap: bool = True,
    supports_jit: bool = True,
) -> MethodSignature:
    return MethodSignature(
        name="test_method",
        namespace="tests.fallback",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=backend,
        supports_grad=supports_grad,
        supports_vmap=supports_vmap,
        supports_jit=supports_jit,
    )


class _DummyMethodClass:
    signature: ClassVar[MethodSignature] = _make_signature()
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="dummy")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> Any:
        return state


# =============================================================================
# SignatureAwareFallback unit tests
# =============================================================================


class TestSignatureAwareFallback:
    def test_fallback_skips_incompatible_backend(self):
        """Method with supports_grad=True should NOT fall back to NumPy."""
        strategy = SignatureAwareFallback()
        sig = _make_signature(
            backend=ComputeBackend.JAX,
            supports_grad=True,
            supports_vmap=False,
        )
        result = strategy.select_fallback(_DummyMethodClass, sig, ComputeBackend.JAX)
        assert result is None

    def test_fallback_skips_vmap_incompatible(self):
        """Method with supports_vmap=True should NOT fall back to NumPy."""
        strategy = SignatureAwareFallback()
        sig = _make_signature(
            backend=ComputeBackend.JAX,
            supports_grad=False,
            supports_vmap=True,
        )
        result = strategy.select_fallback(_DummyMethodClass, sig, ComputeBackend.JAX)
        assert result is None

    def test_fallback_selects_compatible_backend(self):
        """Method without grad/vmap should fall back to NumPy."""
        strategy = SignatureAwareFallback()
        sig = _make_signature(
            backend=ComputeBackend.JAX,
            supports_grad=False,
            supports_vmap=False,
            supports_jit=False,
        )
        result = strategy.select_fallback(_DummyMethodClass, sig, ComputeBackend.JAX)
        assert result is ComputeBackend.NUMPY

    def test_fallback_returns_none_when_no_option(self):
        """When failed backend is NUMPY and no other compatible option exists."""
        strategy = SignatureAwareFallback()
        sig = _make_signature(
            backend=ComputeBackend.NUMPY,
            supports_grad=False,
            supports_vmap=False,
            supports_jit=False,
        )
        result = strategy.select_fallback(_DummyMethodClass, sig, ComputeBackend.NUMPY)
        assert result is None

    def test_fallback_skips_failed_backend(self):
        """The failed backend should never be selected as fallback."""
        strategy = SignatureAwareFallback()
        sig = _make_signature(
            backend=ComputeBackend.NUMPY,
            supports_grad=False,
            supports_vmap=False,
            supports_jit=False,
        )
        # Fail NUMPY — only NUMPY in FALLBACK_ORDER → None
        result = strategy.select_fallback(_DummyMethodClass, sig, ComputeBackend.NUMPY)
        assert result is None


# =============================================================================
# Custom strategy injection
# =============================================================================


class _AlwaysSolverFallback:
    """Test strategy that always falls back to SOLVER."""

    def select_fallback(
        self,
        method_class: type,
        signature: MethodSignature,
        failed_backend: ComputeBackend,
    ) -> ComputeBackend | None:
        return ComputeBackend.SOLVER


class TestCustomFallbackStrategy:
    @pytest.fixture(autouse=True)
    def _reset(self):
        MethodDispatcher.reset_instance()
        yield
        MethodDispatcher.reset_instance()

    def test_custom_fallback_strategy_injected(self):
        """Custom FallbackStrategy should be used by dispatcher."""
        custom = _AlwaysSolverFallback()
        dispatcher = MethodDispatcher(fallback_strategy=custom)
        assert dispatcher._fallback_strategy is custom

    def test_default_fallback_is_signature_aware(self):
        """Without explicit strategy, SignatureAwareFallback is default."""
        dispatcher = MethodDispatcher()
        assert isinstance(dispatcher._fallback_strategy, SignatureAwareFallback)

    def test_custom_strategy_is_fallback_strategy_protocol(self):
        """Custom strategy satisfies FallbackStrategy protocol."""
        custom = _AlwaysSolverFallback()
        assert isinstance(custom, FallbackStrategy)
