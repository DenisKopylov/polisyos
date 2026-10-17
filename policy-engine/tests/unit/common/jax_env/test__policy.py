from __future__ import annotations

import os

import pytest

from polisyos.common import jax_env

pytestmark = pytest.mark.unit


def test_jax_env_defaults_to_cpu_on_darwin_without_a_user_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical env helper supplies safe defaults only when unset."""

    monkeypatch.setattr(jax_env.sys, "platform", "darwin")
    for name in (
        "JAX_PLATFORMS",
        "JAX_PLATFORM_NAME",
        "POLICY_ENGINE_ALLOW_JAX_METAL",
    ):
        monkeypatch.delenv(name, raising=False)

    jax_env.apply_jax_env_defaults()

    assert os.environ["JAX_PLATFORMS"] == "cpu"
    assert os.environ["JAX_PLATFORM_NAME"] == "cpu"


def test_jax_env_preserves_explicit_platform_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit platform selection, including opted-in Metal, is untouched."""

    monkeypatch.setattr(jax_env.sys, "platform", "darwin")
    monkeypatch.setenv("JAX_PLATFORMS", "metal")
    monkeypatch.setenv("JAX_PLATFORM_NAME", "metal")
    monkeypatch.setenv("POLICY_ENGINE_ALLOW_JAX_METAL", "1")

    jax_env.apply_jax_env_defaults()

    assert os.environ["JAX_PLATFORMS"] == "metal"
    assert os.environ["JAX_PLATFORM_NAME"] == "metal"
