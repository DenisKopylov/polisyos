from __future__ import annotations

import hashlib
import json
import time
from importlib import metadata
from typing import Any, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
)


def _safe_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def _capture_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for pkg in ("numpy", "scipy", "statsmodels", "pandas", "linearmodels", "sklearn"):
        version = _safe_version(pkg)
        if version:
            versions[pkg] = version
    return versions


def _resolve_params(signature: MethodSignature, params: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    known = {p.name for p in signature.parameters}
    unknown = set(params.keys()) - known
    if unknown:
        raise ValueError(f"Unknown parameters for {signature.fqn}: {sorted(unknown)}")
    for param in signature.parameters:
        result[param.name] = params.get(param.name, param.default)
    return result


class NumpyRunner(MethodRunner):
    @property
    def supported_backends(self) -> frozenset[ComputeBackend]:
        return frozenset({ComputeBackend.NUMPY})

    def is_available(self) -> bool:
        return True

    def execute(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        seed: int,
    ) -> MethodResult:
        resolved = _resolve_params(signature, params)
        rng = np.random.default_rng(seed)
        resolved["__rng__"] = rng
        resolved["__seed__"] = seed

        started = time.perf_counter()
        output = method_class.pure_step(state, resolved)
        wall_ms = (time.perf_counter() - started) * 1000

        versions = _capture_versions()
        fp_payload = {
            "backend": ComputeBackend.NUMPY.value,
            "seed": seed,
            "versions": versions,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fp_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        return MethodResult(
            output=output,
            timing=MethodTiming(wall_time_ms=wall_ms),
            reproducibility=ReproducibilityInfo(
                backend=ComputeBackend.NUMPY,
                determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
                seed=seed,
                library_versions=versions,
                fingerprint=fingerprint,
                note="Deterministic within fixed dependency versions and seed.",
            ),
        )

