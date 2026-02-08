from __future__ import annotations

import hashlib
import json
import time
from importlib import metadata
from typing import Any, Mapping

from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
    SolverStatus,
)


def _safe_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def _capture_solver_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for pkg in ("ortools", "pulp", "scipy"):
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


def _assert_canonicalizable(payload: Any, *, label: str) -> None:
    try:
        to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
    except Exception as exc:
        raise TypeError(f"{label} is not canonical-serializable: {exc}") from exc


class SolverRunner(MethodRunner):
    @property
    def supported_backends(self) -> frozenset[ComputeBackend]:
        return frozenset({ComputeBackend.SOLVER})

    def is_available(self) -> bool:
        return _safe_version("ortools") is not None or _safe_version("pulp") is not None

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
        resolved["__seed__"] = seed

        started = time.perf_counter()
        raw = method_class.pure_step(state, resolved)
        wall_ms = (time.perf_counter() - started) * 1000

        solver_info: dict[str, Any] = {}
        if isinstance(raw, tuple) and len(raw) == 2:
            output, solver_info = raw
        else:
            output = raw

        _assert_canonicalizable(output, label="solver output")
        _assert_canonicalizable(solver_info, label="solver_info")

        status_raw = str(solver_info.get("status", SolverStatus.UNKNOWN.value)).lower()
        try:
            status = SolverStatus(status_raw)
        except ValueError:
            status = SolverStatus.UNKNOWN

        versions = _capture_solver_versions()
        fp_payload = {
            "backend": ComputeBackend.SOLVER.value,
            "seed": seed,
            "versions": versions,
            "status": status.value,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fp_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        warnings = solver_info.get("warnings", [])
        if isinstance(warnings, str):
            warnings = [warnings]

        artifacts = {
            "solver_status": status.value,
            "solver_gap": solver_info.get("gap"),
            "solver_iterations": solver_info.get("iterations"),
            "solver_objective_value": solver_info.get("objective_value"),
        }

        return MethodResult(
            output=output,
            timing=MethodTiming(wall_time_ms=wall_ms),
            reproducibility=ReproducibilityInfo(
                backend=ComputeBackend.SOLVER,
                determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
                seed=seed,
                library_versions=versions,
                solver_status=status,
                solver_gap=solver_info.get("gap"),
                solver_iterations=solver_info.get("iterations"),
                fingerprint=fingerprint,
                note="Solver reproducibility depends on solver version and tolerances.",
            ),
            artifacts=artifacts,
            warnings=tuple(str(item) for item in warnings),
        )
