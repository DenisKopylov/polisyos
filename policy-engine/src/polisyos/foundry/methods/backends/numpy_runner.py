"""Public backends numpy runner module API."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import numpy as np

from polisyos.core.canon import truncated_hash
from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
    RuntimeContextDispatchError,
)
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    capture_backend_runtime_fingerprint,
    capture_versions,
    runtime_stack_for,
)
from polisyos.foundry.methods.backends.validated import VALIDATED_EXECUTION_PARAM_NAMES
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature
from polisyos.foundry.methods.components.io import dematerialize_method_output

if TYPE_CHECKING:
    from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorDispatchContext


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
        runtime_context: OwnedAttemptAnchorDispatchContext | None = None,
        _captured_dispatch_execute: Any | None = None,
    ) -> MethodResult:
        pure_step = getattr(method_class, "pure_step", None)
        postprocess = getattr(method_class, "postprocess_output", None)
        resolved = _resolve_params(signature, params)
        rng = np.random.default_rng(seed)
        resolved["__rng__"] = rng
        resolved["__seed__"] = seed

        started = time.perf_counter()
        restricted_invocation = None
        if runtime_context is None:
            from polisyos.foundry.methods.catalog.policy.restricted_executable_profile import (
                run_restricted_exante_if_selected,
            )

            profile_selected, output, restricted_invocation = run_restricted_exante_if_selected(
                runner=self,
                captured_runner_execute=_captured_dispatch_execute,
                method_class=method_class,
                signature=signature,
                pure_step=pure_step,
                postprocessor=postprocess,
                state=state,
                resolved_params=resolved,
                original_params=params,
            )
            if not profile_selected:
                output = pure_step(state, resolved)
        else:
            from polisyos.core.contracts.owned_attempt_anchor import (
                OwnedAttemptAnchorDispatchContext,
            )

            if not isinstance(runtime_context, OwnedAttemptAnchorDispatchContext):
                raise RuntimeContextDispatchError("invalid_context")
            capture = runtime_context.input_capture
            if (
                signature.fqn
                not in {
                    "causal.hte.causal_forest@2.0.0",
                    "causal.hte.double_ml@2.0.0",
                    "causal.hte.meta_learner@2.0.0",
                    "causal.hte.forest_dr@2.0.0",
                }
                or getattr(method_class, "owned_hte_method_fqn", None) != signature.fqn
                or getattr(method_class, "owned_hte_method_abi", None) != "2.0.0"
                or getattr(capture, "method_fqn", None) != signature.fqn
                or getattr(capture, "method_abi", None) != "2.0.0"
            ):
                raise RuntimeContextDispatchError("method_identity_mismatch")
            context_entry = getattr(method_class, "pure_step_with_runtime_context", None)
            if not callable(context_entry):
                raise RuntimeContextDispatchError("method_not_supported")
            output = context_entry(state, resolved, runtime_context=runtime_context)
        if callable(postprocess):
            output = postprocess(output=output, state=state, params=resolved)
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
        if restricted_invocation is not None:
            restricted_invocation = replace(
                restricted_invocation, backend_runtime_fingerprint=posture.compute_hash()
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
            restricted_invocation=restricted_invocation,
        )
