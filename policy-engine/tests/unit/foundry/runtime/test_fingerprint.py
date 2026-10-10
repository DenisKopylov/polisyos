from __future__ import annotations

import dataclasses
import importlib.metadata as importlib_metadata
import sys
import types

import pytest

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.runtime import fingerprint as runtime_fingerprint
from polisyos.foundry.runtime.fingerprint import EnvironmentFingerprint


class TestEnvironmentFingerprint:
    def test_fingerprint_capture_populates_all_fields(self) -> None:
        fp = EnvironmentFingerprint.capture(DeterminismTier.STRICT_CPU, seed=42)
        assert fp.python_version
        assert fp.platform_system
        assert fp.platform_machine
        assert fp.jax_version
        assert fp.jaxlib_version
        assert fp.determinism_tier == DeterminismTier.STRICT_CPU
        assert fp.random_seed == 42
        assert fp.cpu_count > 0
        assert fp.captured_at

    def test_fingerprint_capture_deterministic(self) -> None:
        fp1 = EnvironmentFingerprint.capture(DeterminismTier.STRICT_CPU, seed=42)
        fp2 = EnvironmentFingerprint.capture(DeterminismTier.STRICT_CPU, seed=42)
        assert fp1.python_version == fp2.python_version
        assert fp1.jax_version == fp2.jax_version
        assert fp1.platform_system == fp2.platform_system
        assert fp1.determinism_tier == fp2.determinism_tier
        assert fp1.random_seed == fp2.random_seed

    def test_fingerprint_frozen_dataclass(self) -> None:
        fp = EnvironmentFingerprint.capture(DeterminismTier.STRICT_CPU, seed=42)
        with pytest.raises(dataclasses.FrozenInstanceError):
            fp.random_seed = 99  # type: ignore[misc]

    def test_get_jaxlib_version_returns_unknown_when_distribution_missing(
        self, monkeypatch
    ) -> None:
        def _raise_missing(_package: str) -> str:
            raise importlib_metadata.PackageNotFoundError("jaxlib")

        monkeypatch.setattr(runtime_fingerprint, "package_version", _raise_missing)

        assert runtime_fingerprint._get_jaxlib_version() == "unknown"

    def test_get_cuda_version_fast_returns_none_when_probe_fails(self, monkeypatch) -> None:
        def _raise_devices():
            raise RuntimeError("device probe failed")

        monkeypatch.delenv("CUDA_VERSION", raising=False)
        monkeypatch.setitem(sys.modules, "jax", types.SimpleNamespace(devices=_raise_devices))

        assert runtime_fingerprint._get_cuda_version_fast() is None

    def test_get_cudnn_version_reports_bundled_for_cuda_jaxlib(self, monkeypatch) -> None:
        monkeypatch.setattr(
            runtime_fingerprint,
            "package_version",
            lambda _package: "0.4.31+cuda12.cudnn89",
        )

        assert runtime_fingerprint._get_cudnn_version() == "bundled"
