"""Public backends numpy runner module API."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
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
from polisyos.foundry.methods.components.representation import invoke_representation_call

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


def _detached_observed_parameter(
    value: Any, *, depth: int = 0, remaining: list[int] | None = None
) -> Any:
    """Copy a bounded exact value for observation without copying arbitrary objects."""
    remaining = [4096] if remaining is None else remaining
    remaining[0] -= 1
    if depth > 16 or remaining[0] < 0:
        raise ValueError("prepared_method_parameter_projection_not_established")
    if value is None or type(value) in {bool, int, float, str, bytes, Decimal}:
        return value
    if isinstance(value, Enum):
        if value.value is not None and type(value.value) not in {
            bool,
            int,
            float,
            str,
            bytes,
            Decimal,
        }:
            raise ValueError("prepared_method_parameter_projection_not_established")
        return value
    if type(value) is np.ndarray:
        if value.dtype.hasobject or value.nbytes > 262144:
            raise ValueError("prepared_method_parameter_projection_not_established")
        return np.frombuffer(value.tobytes(order="C"), dtype=value.dtype).reshape(value.shape)
    if isinstance(value, np.generic) and not value.dtype.hasobject:
        return value.copy()
    if type(value) in {list, tuple, dict, set, frozenset}:
        if len(value) > 256:
            raise ValueError("prepared_method_parameter_projection_not_established")
        if type(value) is dict:
            if any(type(key) is not str for key in value):
                raise ValueError("prepared_method_parameter_projection_not_established")
            return {
                key: _detached_observed_parameter(item, depth=depth + 1, remaining=remaining)
                for key, item in value.items()
            }
        children = [
            _detached_observed_parameter(item, depth=depth + 1, remaining=remaining)
            for item in value
        ]
        return type(value)(children)
    raise ValueError("prepared_method_parameter_projection_not_established")


@dataclass(frozen=True, slots=True)
class PreparedNumpyMethodCall:
    """Hold the actual callable, defaults and RNG selected before a NumPy call.

    This is an in-process preparation record, not execution evidence. The
    runner consumes these same objects; it does not re-read the class slots or
    parameter defaults after the call is observed.
    """

    method_class: type
    signature: MethodSignature
    state: Any
    original_params: Mapping[str, Any]
    resolved_params: Mapping[str, Any]
    declared_params: Mapping[str, Any]
    seed: int
    pure_step: Callable[..., Any]
    postprocessor: Any
    default_rng: Callable[..., Any]
    representation_call: Callable[..., Any]
    restricted_selector: Callable[..., Any] | None
    output_dematerializer: Callable[..., Any]
    output_projection: Any
    strict_output_contract: bool
    rng_state: Mapping[str, Any]


class NumpyRunner(MethodRunner):
    """Numpy runner public type."""

    @property
    def supported_backends(self) -> frozenset[ComputeBackend]:
        return frozenset({ComputeBackend.NUMPY})

    def is_available(self) -> bool:
        return True

    def prepare_call(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        seed: int,
        runtime_context: OwnedAttemptAnchorDispatchContext | None = None,
        _detach_observation: bool = False,
    ) -> PreparedNumpyMethodCall:
        """Resolve exactly the ordinary NumPy call without executing its kernel.

        Args:
            method_class: Selected registered method class.
            signature: Selected method ABI.
            state: Already materialized ABI input object.
            params: Explicit method parameters after execution-only splitting.
            seed: Exact seed to supply to the numerical method.
            runtime_context: Existing owner-bound execution context, if any.
            _detach_observation: Isolate the bounded observer projection from
                mutable actual parameter values; unsupported objects refuse.

        Returns:
            Held preparation consumed by :meth:`execute`.

        Raises:
            ValueError: If the selected class has no callable numerical entry.
        """
        pure_step = getattr(method_class, "pure_step", None)
        if not callable(pure_step):
            raise ValueError("prepared_numpy_method_callable_unavailable")
        postprocess = getattr(method_class, "postprocess_output", None)
        resolved = _resolve_params(signature, params)
        projection_budget = [4096]
        declared = MappingProxyType(
            {
                key: _detached_observed_parameter(value, remaining=projection_budget)
                for key, value in resolved.items()
            }
            if _detach_observation
            else dict(resolved)
        )
        default_rng = np.random.default_rng
        rng = default_rng(seed)
        resolved["__rng__"] = rng
        resolved["__seed__"] = seed
        restricted_selector = None
        if runtime_context is None:
            from polisyos.foundry.methods.catalog.policy.restricted_executable_profile import (
                run_restricted_exante_if_selected,
            )

            restricted_selector = run_restricted_exante_if_selected

        return PreparedNumpyMethodCall(
            method_class=method_class,
            signature=signature,
            state=state,
            original_params=dict(params),
            resolved_params=resolved,
            declared_params=declared,
            seed=seed,
            pure_step=pure_step,
            postprocessor=postprocess,
            default_rng=default_rng,
            representation_call=invoke_representation_call,
            restricted_selector=restricted_selector,
            output_dematerializer=dematerialize_method_output,
            output_projection=getattr(method_class, "dematerialize_output", None),
            strict_output_contract=bool(getattr(method_class, "strict_output_contract", False)),
            rng_state=MappingProxyType(deepcopy(rng.bit_generator.state)),
        )

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
        _prepared_call: PreparedNumpyMethodCall | None = None,
    ) -> MethodResult:
        prepared = _prepared_call or self.prepare_call(
            method_class=method_class,
            signature=signature,
            state=state,
            params=params,
            seed=seed,
            runtime_context=runtime_context,
        )
        if (
            prepared.method_class is not method_class
            or prepared.signature is not signature
            or prepared.state is not state
            or prepared.seed != seed
        ):
            raise ValueError("prepared_numpy_method_call_identity_mismatch")
        pure_step = prepared.pure_step
        postprocess = prepared.postprocessor
        resolved = prepared.resolved_params

        representation_compatibility = ()
        started = time.perf_counter()
        restricted_invocation = None
        if runtime_context is None:
            if prepared.restricted_selector is None:
                raise ValueError("prepared_numpy_method_context_mismatch")
            profile_selected, output, restricted_invocation = prepared.restricted_selector(
                runner=self,
                captured_runner_execute=_captured_dispatch_execute,
                method_class=method_class,
                signature=signature,
                pure_step=pure_step,
                postprocessor=postprocess,
                state=state,
                resolved_params=resolved,
                original_params=prepared.original_params,
            )
            if not profile_selected:
                output, representation_compatibility = prepared.representation_call(
                    method_class=method_class,
                    signature=signature,
                    operation=pure_step,
                    postprocessor=postprocess,
                    state=state,
                    params=resolved,
                )
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
        slot_outputs = prepared.output_dematerializer(
            method_class=method_class,
            signature=signature,
            output=output,
            _captured_projection=(prepared.output_projection, prepared.strict_output_contract),
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
            representation_compatibility=representation_compatibility,
        )
