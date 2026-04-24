"""Public backends numpy runner module API."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any

import numpy as np

from polisyos.core.canon import truncated_hash
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    capture_backend_runtime_fingerprint,
    capture_versions,
    runtime_stack_for,
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


class NumpyRunner(MethodRunner):
    """Numpy runner public type."""

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

        determinism_tier = DeterminismTier.LIBRARY_DETERMINISTIC
        artifacts: dict[str, Any] = {}
        warnings: list[str] = []
        class_tier = getattr(method_class, "determinism_tier", None)
        if isinstance(class_tier, DeterminismTier):
            determinism_tier = class_tier
        if isinstance(output, dict):
            maybe_tier = output.get("__determinism_tier__")
            if isinstance(maybe_tier, DeterminismTier):
                determinism_tier = maybe_tier
                output = dict(output)
                output.pop("__determinism_tier__", None)
            maybe_artifacts = output.get("__numpy_artifacts__")
            if isinstance(maybe_artifacts, Mapping):
                output = dict(output)
                output.pop("__numpy_artifacts__", None)
                artifacts.update({str(key): value for key, value in maybe_artifacts.items()})
            maybe_warnings = output.get("__numpy_warnings__")
            if isinstance(maybe_warnings, (list, tuple, set, frozenset)):
                output = dict(output)
                output.pop("__numpy_warnings__", None)
                warnings.extend(str(item) for item in maybe_warnings)

        runtime_stack = runtime_stack_for(method_class)
        versions = capture_versions(
            base_packages=("numpy", "scipy", "statsmodels", "pandas"),
            runtime_stack=runtime_stack,
        )
        posture = capture_backend_runtime_fingerprint(
            ComputeBackend.NUMPY,
            method_class=method_class,
            seed=seed,
            extra_versions=versions,
        )
        fp_payload = {
            "backend": ComputeBackend.NUMPY.value,
            "seed": seed,
            "versions": versions,
            "runtime_stack": runtime_stack,
        }
        fingerprint = truncated_hash(json.dumps(fp_payload, sort_keys=True), length=16)
        slot_outputs = dematerialize_method_output(
            method_class=method_class,
            signature=signature,
            output=output,
        )

        return MethodResult(
            output=output,
            timing=MethodTiming(wall_time_ms=wall_ms),
            reproducibility=ReproducibilityInfo(
                backend=ComputeBackend.NUMPY,
                determinism_tier=determinism_tier,
                seed=seed,
                library_versions=versions,
                fingerprint=fingerprint,
                observed_tolerance_budget=posture.observed_tolerance_budget,
                note=(
                    "Statistical reproducibility within fixed dependency versions and seed."
                    if determinism_tier is DeterminismTier.STATISTICAL
                    else posture.replay_semantics
                ),
            ),
            slot_outputs=slot_outputs,
            artifacts={**artifacts, "backend_runtime_fingerprint": posture.as_dict()},
            warnings=tuple(dict.fromkeys(warnings)),
        )
