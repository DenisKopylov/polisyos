"""Public backends solver runner module API."""
from __future__ import annotations

import json
import time
from typing import Any, Mapping

from polisyos.core.canon import CanonSpec, to_canonical_bytes, truncated_hash
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    augment_observed_tolerance_budget,
    capture_backend_runtime_fingerprint,
    capture_versions,
    runtime_stack_for,
)
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
    SolverStatus,
)
from polisyos.foundry.methods.backends.validated import VALIDATED_EXECUTION_PARAM_NAMES
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature
from polisyos.foundry.methods.io import dematerialize_method_output


def _resolve_params(signature: MethodSignature, params: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    known = {p.name for p in signature.parameters}
    unknown = set(params.keys()) - known - VALIDATED_EXECUTION_PARAM_NAMES
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
    """Solver runner public type."""
    @property
    def supported_backends(self) -> frozenset[ComputeBackend]:
        return frozenset({ComputeBackend.SOLVER})

    def is_available(self) -> bool:
        posture = capture_backend_runtime_fingerprint(ComputeBackend.SOLVER)
        return posture.available

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

        runtime_stack = runtime_stack_for(method_class)
        versions = capture_versions(
            base_packages=("ortools", "pulp", "scipy", "cvxpy", "pymoo"),
            runtime_stack=runtime_stack,
        )
        solver_name = str(solver_info.get("backend") or "").strip().lower() or None
        solver_options_payload = {
            str(key): value
            for key, value in solver_info.items()
            if key not in {"status", "gap", "iterations", "objective_value", "warnings", "backend"}
        }
        solver_options_hash = (
            truncated_hash(json.dumps(solver_options_payload, sort_keys=True, default=str), length=12)
            if solver_options_payload
            else None
        )
        posture = capture_backend_runtime_fingerprint(
            ComputeBackend.SOLVER,
            method_class=method_class,
            seed=seed,
            extra_versions=versions,
            route_key_overrides={
                "solver_name": solver_name,
                "solver_options_hash": solver_options_hash,
            },
        )
        fp_payload = {
            "backend": ComputeBackend.SOLVER.value,
            "seed": seed,
            "versions": versions,
            "status": status.value,
            "runtime_stack": runtime_stack,
        }
        fingerprint = truncated_hash(json.dumps(fp_payload, sort_keys=True), length=16)

        warnings = solver_info.get("warnings", [])
        if isinstance(warnings, str):
            warnings = [warnings]

        solver_residual_budget = {
            "primal": solver_info.get("primal_residual"),
            "dual": solver_info.get("dual_residual"),
            "gap": solver_info.get("gap"),
            "optimality": (
                solver_info.get("optimality")
                if solver_info.get("optimality") is not None
                else solver_info.get("optimality_residual")
            ),
        }
        observed_budget = augment_observed_tolerance_budget(
            posture.observed_tolerance_budget,
            solver_residual_budget=solver_residual_budget,
        )

        artifacts = {
            "solver_status": status.value,
            "solver_gap": solver_info.get("gap"),
            "solver_iterations": solver_info.get("iterations"),
            "solver_objective_value": solver_info.get("objective_value"),
        }
        slot_outputs: dict[str, Any] = {}
        if signature.output_slots:
            output_payload: Any = output
            if "solver_info" in signature.output_slot_names:
                output_payload = {
                    "result": output,
                    "solver_info": solver_info,
                }
            slot_outputs = dematerialize_method_output(
                method_class=method_class,
                signature=signature,
                output=output_payload,
            )

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
                observed_tolerance_budget=observed_budget,
                note=posture.replay_semantics,
            ),
            slot_outputs=slot_outputs,
            artifacts={
                **artifacts,
                "backend_runtime_fingerprint": {
                    **posture.as_dict(),
                    "observed_tolerance_budget": observed_budget,
                },
            },
            warnings=tuple(str(item) for item in warnings),
        )
