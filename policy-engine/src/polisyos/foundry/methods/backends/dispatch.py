"""Route protocol-compliant methods to backend runners with fallback and telemetry.

`MethodDispatcher` chooses the concrete runner declared by
`MethodSignature.backend`, applies circuit-breaker/fallback policy, records
selection-history telemetry, and returns the `MethodResult` produced by the
backend runtime.
"""

from __future__ import annotations

import threading
import time as _time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Protocol, runtime_checkable

from polisyos.core.backends import BackendDispatcher
from polisyos.core.backends import BackendNotAvailableError as CoreBackendNotAvailableError
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.foundry.methods._internal.logging import _infer_n_obs, get_foundry_logger
from polisyos.foundry.methods.backends.circuit_breaker import (
    BackendCircuitOpenError,
    get_circuit_breaker_registry,
)
from polisyos.foundry.methods.backends.protocol import MethodResult, MethodRunner, MethodTiming
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    augment_observed_tolerance_budget,
    capture_backend_runtime_fingerprint,
)
from polisyos.foundry.methods.backends.validated import (
    ValidatedMode,
    maybe_certify,
    split_validated_execution_params,
    validated_bound_to_envelopes,
)
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature
from polisyos.foundry.methods.equivalence import (
    EquivalenceCertificateResolver,
    assess_certificate_applicability,
    attach_equivalence_ref,
    get_default_equivalence_resolver,
)
from polisyos.foundry.methods.exceptions import FoundryMethodError
from polisyos.foundry.methods.lifecycle.output_monitor import (
    _emit_anomaly_metric,
    get_output_monitor,
)
from polisyos.foundry.methods.selection.history import (
    AdvisorExecutionContext,
    MethodExecutionRecord,
    RuntimePredictor,
    SelectionHistoryStore,
    fit_runtime_predictor_from_history,
    get_global_selection_history,
    split_advisor_execution_params,
)
from polisyos.ir.analytics import extract_truthfulness_receipt

_log = get_foundry_logger("foundry.backends.dispatch")
_USD_PER_MS = {
    ComputeBackend.NUMPY: 5.0e-7,
    ComputeBackend.JAX: 8.0e-7,
    ComputeBackend.SOLVER: 1.2e-6,
    ComputeBackend.BAYESIAN: 1.5e-6,
}


def _infer_data_characteristics(state: Any, n_obs: int | None) -> dict[str, Any]:
    characteristics: dict[str, Any] = {}
    if n_obs is not None:
        characteristics["n_obs"] = int(n_obs)
    if isinstance(state, Mapping):
        for key in ("features", "covariates", "X"):
            value = state.get(key)
            shape = getattr(value, "shape", None)
            if shape and len(shape) >= 2:
                characteristics["n_features"] = int(shape[-1])
                break
    return characteristics


def _record_execution(
    *,
    signature: MethodSignature,
    elapsed_ms: float,
    success: bool,
    n_obs: int | None,
    state: Any,
    failure_type: str | None = None,
    backend_used: ComputeBackend | None = None,
    result: MethodResult | None = None,
    advisor_context: AdvisorExecutionContext | None = None,
    history_store: SelectionHistoryStore | None = None,
) -> None:
    try:
        receipt = extract_truthfulness_receipt(result.artifacts if result is not None else None)
        if receipt is None and result is not None:
            receipt = extract_truthfulness_receipt(result.output)
        record = MethodExecutionRecord(
            method_fqn=signature.fqn,
            timestamp=_time.time(),
            latency_ms=max(elapsed_ms, 0.0),
            success=success,
            failure_type=failure_type,
            data_characteristics={
                **_infer_data_characteristics(state, n_obs),
                "backend": (backend_used or signature.backend).value,
            },
            runtime_truthfulness_tier=(
                None
                if receipt is None or receipt.runtime_truthfulness_tier is None
                else receipt.runtime_truthfulness_tier.value
            ),
            effective_truthfulness_tier=(
                None
                if receipt is None or receipt.effective_truthfulness_tier is None
                else receipt.effective_truthfulness_tier.value
            ),
            truthfulness_scope=(
                None
                if receipt is None or receipt.truthfulness_scope is None
                else receipt.truthfulness_scope.value
            ),
            truthfulness_status=(
                None if receipt is None or receipt.status is None else receipt.status.value
            ),
            truthfulness_evidence_ref=None if receipt is None else receipt.evidence_ref,
            query_fingerprint=(
                None if advisor_context is None else advisor_context.query_fingerprint
            ),
            loss_profile_id=(None if advisor_context is None else advisor_context.loss_profile_id),
            candidate_fqns=(
                () if advisor_context is None else tuple(advisor_context.candidate_fqns)
            ),
            selected_rank=(None if advisor_context is None else advisor_context.selected_rank),
            selection_propensity=(
                None if advisor_context is None else advisor_context.selection_propensity
            ),
            advisor_score_vector=(
                {} if advisor_context is None else dict(advisor_context.advisor_score_vector)
            ),
            realized_loss_components={
                "failure_penalty": 0.0 if success else 1.0,
            },
            shadow_loss_estimates=(
                {} if advisor_context is None else dict(advisor_context.shadow_loss_estimates)
            ),
        )
        target_history = get_global_selection_history() if history_store is None else history_store
        target_history.record(record)
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        _log.warning(
            "method_dispatch_record_failed",
            fqn=signature.fqn,
            backend=(backend_used or signature.backend).value,
            exc=type(exc).__name__,
        )


def _estimate_cost_usd(*, backend: ComputeBackend, timing: MethodTiming) -> float:
    unit_cost = _USD_PER_MS.get(backend, 5.0e-7)
    compile_ms = max(float(timing.compile_time_ms or 0.0), 0.0)
    wall_ms = max(float(timing.wall_time_ms), 0.0)
    return round((wall_ms * unit_cost) + (compile_ms * unit_cost * 0.25), 10)


def _build_dispatch_artifacts(
    *,
    signature: MethodSignature,
    decision: DispatchDecision,
    attempts: list[tuple[ComputeBackend, str]],
    result: MethodResult,
    n_obs: int | None,
    declared_route_budget: Mapping[str, Any] | None = None,
    observed_route_budget: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cost_usd = _estimate_cost_usd(
        backend=result.reproducibility.backend,
        timing=result.timing,
    )
    return {
        "dispatch_trace": {
            "method_fqn": signature.fqn,
            "requested_backend": decision.requested_backend.value,
            "selected_backend": result.reproducibility.backend.value,
            "selection_reason": decision.reason,
            "attempts": [
                {"backend": backend.value, "outcome": outcome} for backend, outcome in attempts
            ],
            "predicted_requested_ms": decision.predicted_requested_ms,
            "predicted_selected_ms": decision.predicted_selected_ms,
            "n_obs": n_obs,
            "degraded": any(outcome != "success" for _, outcome in attempts[:-1]),
            "declared_route_budget": (
                None if declared_route_budget is None else dict(declared_route_budget)
            ),
            "observed_route_budget": (
                None if observed_route_budget is None else dict(observed_route_budget)
            ),
        },
        "cost_attribution": {
            "method_fqn": signature.fqn,
            "backend": result.reproducibility.backend.value,
            "wall_time_ms": float(result.timing.wall_time_ms),
            "compile_time_ms": (
                None
                if result.timing.compile_time_ms is None
                else float(result.timing.compile_time_ms)
            ),
            "cpu_time_ms": (
                None if result.timing.cpu_time_ms is None else float(result.timing.cpu_time_ms)
            ),
            "estimated_cost_usd": cost_usd,
            "usd_per_ms": _USD_PER_MS.get(result.reproducibility.backend, 5.0e-7),
            "determinism_tier": result.reproducibility.determinism_tier.value,
            "seed": result.reproducibility.seed,
        },
    }


def _apply_dispatch_contract_overlay(
    *,
    result: MethodResult,
    signature: MethodSignature,
    backend_used: ComputeBackend,
    declared_tier: str | None,
    fallback_observed_budget: Mapping[str, Any] | None = None,
) -> MethodResult:
    observed_budget = dict(result.reproducibility.observed_tolerance_budget or {})
    fingerprint_artifact = result.artifacts.get("backend_runtime_fingerprint")
    if isinstance(fingerprint_artifact, Mapping):
        observed_budget = dict(
            fingerprint_artifact.get("observed_tolerance_budget") or observed_budget
        )
    if not observed_budget and fallback_observed_budget is not None:
        observed_budget = dict(fallback_observed_budget)

    if backend_used != signature.backend:
        observed_budget = augment_observed_tolerance_budget(
            observed_budget,
            route_key_updates={
                "backend_route": f"{signature.backend.value}->{backend_used.value}_fallback",
            },
            validation_status="degraded",
            downgraded_from=declared_tier,
            downgraded_to=result.reproducibility.determinism_tier.value,
            failure_reasons=(f"fallback_route:{signature.backend.value}->{backend_used.value}",),
            expected_budget_updates={
                "semantic_mode": (
                    f"{(observed_budget.get('expected_budget') or {}).get('semantic_mode', 'best_effort')}_fallback"
                ),
            },
        )

    updated_artifacts = dict(result.artifacts)
    if isinstance(fingerprint_artifact, Mapping):
        updated_fingerprint = dict(fingerprint_artifact)
        updated_fingerprint["route_key"] = dict(
            observed_budget.get("route_key") or updated_fingerprint.get("route_key") or {}
        )
        updated_fingerprint["observed_tolerance_budget"] = observed_budget
        updated_artifacts["backend_runtime_fingerprint"] = updated_fingerprint

    return MethodResult(
        output=result.output,
        timing=result.timing,
        reproducibility=replace(
            result.reproducibility,
            observed_tolerance_budget=observed_budget,
        ),
        cross_backend_equivalence_ref=result.cross_backend_equivalence_ref,
        slot_outputs=result.slot_outputs,
        artifacts=updated_artifacts,
        warnings=result.warnings,
        validated_bound=result.validated_bound,
    )


def _merge_dispatch_result(
    *,
    result: MethodResult,
    artifacts: Mapping[str, Any],
    warnings: tuple[str, ...] = (),
) -> MethodResult:
    truthfulness_receipt = extract_truthfulness_receipt(result.artifacts)
    if truthfulness_receipt is None:
        truthfulness_receipt = extract_truthfulness_receipt(result.output)
    merged_artifacts = {**dict(result.artifacts), **dict(artifacts)}
    if truthfulness_receipt is not None:
        merged_artifacts.setdefault(
            "truthfulness_receipt",
            truthfulness_receipt.model_dump(mode="json"),
        )
    return MethodResult(
        output=result.output,
        timing=result.timing,
        reproducibility=result.reproducibility,
        cross_backend_equivalence_ref=result.cross_backend_equivalence_ref,
        slot_outputs=result.slot_outputs,
        artifacts=merged_artifacts,
        warnings=tuple(dict.fromkeys((*result.warnings, *warnings))),
        validated_bound=result.validated_bound,
    )


@dataclass(frozen=True)
class BackendNotAvailableError(RuntimeError):
    """Signal that the requested backend runtime is not installed or healthy."""

    backend: ComputeBackend

    def __str__(self) -> str:
        return (
            f"Compute backend '{self.backend.value}' is not available. "
            f"Install optional dependencies for this backend."
        )


_KNOWN_DISPATCH_FAILURES = (
    BackendCircuitOpenError,
    BackendNotAvailableError,
    FloatingPointError,
    FoundryMethodError,
    ImportError,
    ModuleNotFoundError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)


@dataclass(frozen=True)
class DispatchDecision:
    """Resolved backend choice for one dispatch attempt."""

    requested_backend: ComputeBackend
    selected_backend: ComputeBackend
    reason: str
    predicted_requested_ms: float | None = None
    predicted_selected_ms: float | None = None


@runtime_checkable
class FallbackStrategy(Protocol):
    """Choose a compatible fallback backend when the primary runner is unavailable."""

    def select_fallback(
        self,
        method_class: type,
        signature: MethodSignature,
        failed_backend: ComputeBackend,
    ) -> ComputeBackend | None: ...


class SignatureAwareFallback:
    """Fallback policy that only downgrades to backends compatible with the signature."""

    FALLBACK_ORDER = [ComputeBackend.NUMPY]

    def select_fallback(
        self,
        method_class: type,
        signature: MethodSignature,
        failed_backend: ComputeBackend,
    ) -> ComputeBackend | None:
        for backend in self.FALLBACK_ORDER:
            if backend == failed_backend:
                continue
            if self._is_compatible(signature, backend):
                return backend
        return None

    def _is_compatible(self, signature: MethodSignature, backend: ComputeBackend) -> bool:
        # JAX-specific features (vmap, grad) incompatible with NumPy
        if backend == ComputeBackend.NUMPY and (signature.supports_grad or signature.supports_vmap):
            return False
        return True


class MethodDispatcher:
    """Thread-safe singleton dispatcher that resolves and invokes backend runners."""

    _instance: MethodDispatcher | None = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        *,
        fallback_strategy: FallbackStrategy | None = None,
        runtime_history: SelectionHistoryStore | None = None,
        runtime_predictor: RuntimePredictor | None = None,
        enable_runtime_selection: bool = True,
        runtime_selection_ratio: float = 0.85,
        runtime_selection_min_delta_ms: float = 2.0,
        equivalence_resolver: EquivalenceCertificateResolver | None = None,
    ) -> None:
        self._dispatcher = BackendDispatcher[ComputeBackend, MethodRunner](
            factory=self._create_runner,
            availability_check=lambda runner: runner.is_available(),
        )
        self._runner_lock = threading.RLock()
        self._fallback_strategy: FallbackStrategy = fallback_strategy or SignatureAwareFallback()
        self._runtime_history = runtime_history
        self._runtime_predictor = runtime_predictor
        self._enable_runtime_selection = bool(enable_runtime_selection)
        self._runtime_selection_ratio = float(runtime_selection_ratio)
        self._runtime_selection_min_delta_ms = float(runtime_selection_min_delta_ms)
        self._equivalence_resolver = equivalence_resolver

    @classmethod
    def get_instance(cls) -> MethodDispatcher:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(
                        equivalence_resolver=get_default_equivalence_resolver(),
                    )
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._instance_lock:
            cls._instance = None

    def register_runner(self, runner: MethodRunner) -> None:
        """Register one runner implementation under all backends it supports."""
        with self._runner_lock:
            for backend in runner.supported_backends:
                self._dispatcher.register(backend, runner)

    def available_backends(self) -> frozenset[ComputeBackend]:
        """Return the set of currently available backend runtimes."""
        with self._runner_lock:
            return self._dispatcher.available_backends()

    def dispatch(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        seed: int,
    ) -> MethodResult:
        """Dispatch one method invocation to the declared backend with fallback.

        Args:
            method_class: Protocol-compliant method class to execute.
            signature: Method ABI and backend declaration.
            state: Materialized input payload/state for the method.
            params: Runtime parameters merged by the caller.
            seed: Backend seed used for reproducible stochastic execution.

        Returns:
            `MethodResult` from the selected runner.

        Raises:
            BackendCircuitOpenError: If the primary backend circuit is open and
                no compatible fallback succeeds.
            BackendNotAvailableError: If the requested backend has no available
                runner implementation.
            Exception: Propagates backend execution failures after telemetry is
                recorded.
        """
        method_params, advisor_context = split_advisor_execution_params(params)
        method_params, validated_policy = split_validated_execution_params(method_params)
        n_obs = _infer_n_obs(state)
        decision = self._select_backend(
            method_class=method_class,
            signature=signature,
            state=state,
            n_obs=n_obs,
        )
        backend_used = decision.selected_backend
        tracer = get_tracer()
        metrics = get_metrics()

        with tracer.start_as_current_span(
            "foundry.method.dispatch",
            attributes={
                "foundry.method_fqn": signature.fqn,
                "foundry.requested_backend": signature.backend.value,
                "foundry.selected_backend": backend_used.value,
                "foundry.selection_reason": decision.reason,
                "foundry.n_obs": -1 if n_obs is None else int(n_obs),
            },
        ) as span:
            _log.debug(
                "method_dispatch_start",
                fqn=signature.fqn,
                backend=backend_used.value,
                requested_backend=signature.backend.value,
                selection_reason=decision.reason,
                n_obs=n_obs,
            )
            t0 = _time.perf_counter()
            last_exc: Exception | None = None
            attempts: list[tuple[ComputeBackend, str]] = []
            try:
                result = self._dispatch_with_candidates(
                    method_class=method_class,
                    signature=signature,
                    state=state,
                    params=method_params,
                    seed=seed,
                    preferred_backend=decision.selected_backend,
                    attempts=attempts,
                )
                if attempts:
                    backend_used = attempts[-1][0]
            except _KNOWN_DISPATCH_FAILURES as exc:
                last_exc = exc

            if last_exc is not None:
                elapsed_ms = (_time.perf_counter() - t0) * 1000
                _log.error(
                    "method_dispatch_error",
                    fqn=signature.fqn,
                    backend=backend_used.value,
                    requested_backend=signature.backend.value,
                    elapsed_ms=round(elapsed_ms, 2),
                    exc=type(last_exc).__name__,
                    attempts=[(backend.value, reason) for backend, reason in attempts],
                )
                _record_execution(
                    signature=signature,
                    elapsed_ms=elapsed_ms,
                    success=False,
                    n_obs=n_obs,
                    state=state,
                    failure_type=type(last_exc).__name__,
                    backend_used=backend_used,
                    result=result if "result" in locals() else None,
                    advisor_context=advisor_context,
                    history_store=self._runtime_history,
                )
                span.set_attribute("foundry.dispatch_status", "error")
                span.set_attribute("foundry.elapsed_ms", elapsed_ms)
                span.set_attribute("foundry.error_type", type(last_exc).__name__)
                if hasattr(span, "record_exception"):
                    span.record_exception(last_exc)
                metrics.record_degraded_path(
                    component="foundry.method.dispatch",
                    operation=signature.fqn,
                    reason=decision.reason,
                    error_type=type(last_exc).__name__,
                )
                raise last_exc

            elapsed_ms = (_time.perf_counter() - t0) * 1000
            declared_posture = capture_backend_runtime_fingerprint(
                signature.backend,
                method_class=method_class,
                seed=seed,
            )
            declared_route_budget = declared_posture.observed_tolerance_budget
            result = _apply_dispatch_contract_overlay(
                result=result,
                signature=signature,
                backend_used=backend_used,
                declared_tier=(
                    None
                    if declared_posture.determinism_tier is None
                    else declared_posture.determinism_tier.value
                ),
                fallback_observed_budget=capture_backend_runtime_fingerprint(
                    backend_used,
                    method_class=method_class,
                    seed=seed,
                ).observed_tolerance_budget,
            )
            dispatch_artifacts = _build_dispatch_artifacts(
                signature=signature,
                decision=decision,
                attempts=attempts,
                result=result,
                n_obs=n_obs,
                declared_route_budget=declared_route_budget,
                observed_route_budget=result.reproducibility.observed_tolerance_budget,
            )
            extra_warnings: list[str] = []
            if backend_used != signature.backend:
                extra_warnings.append(
                    f"dispatch_backend_mismatch:{signature.backend.value}->{backend_used.value}"
                )
                extra_warnings.append(
                    f"dispatch_contract_degraded:{signature.backend.value}->{backend_used.value}"
                )
            if any(outcome != "success" for _, outcome in attempts[:-1]):
                metrics.record_degraded_path(
                    component="foundry.method.dispatch",
                    operation=signature.fqn,
                    reason="fallback_recovery",
                    error_type=None,
                )
            validated_bound = maybe_certify(
                signature=signature,
                state=state,
                params=method_params,
                output=result.output,
                execution_policy=validated_policy,
            )
            validated_artifacts: dict[str, Any] = {}
            if validated_bound is not None:
                validated_artifacts["validated_bound_certificate"] = validated_bound.as_dict()
                validated_envelopes = validated_bound_to_envelopes(validated_bound)
                if validated_envelopes:
                    serialized_envelopes = [
                        envelope.model_dump(mode="json") for envelope in validated_envelopes
                    ]
                    validated_artifacts["validated_uncertainty_envelopes"] = serialized_envelopes
                    if len(serialized_envelopes) == 1:
                        validated_artifacts["validated_uncertainty_envelope"] = (
                            serialized_envelopes[0]
                        )
            if (
                validated_policy.mode is ValidatedMode.REQUIRED
                and validated_bound is not None
                and validated_bound.status.value in {"indeterminate", "not_applicable"}
            ):
                extra_warnings.append(
                    f"validated_bound_{validated_bound.status.value}:{validated_bound.quantity}"
                )
            result = _merge_dispatch_result(
                result=result,
                artifacts={**dispatch_artifacts, **validated_artifacts},
                warnings=tuple(extra_warnings),
            )
            result = self._maybe_attach_equivalence_certificate(
                result=result,
                signature=signature,
                backend_used=backend_used,
            )
            if validated_bound is not None:
                result = MethodResult(
                    output=result.output,
                    timing=result.timing,
                    reproducibility=result.reproducibility,
                    cross_backend_equivalence_ref=result.cross_backend_equivalence_ref,
                    slot_outputs=result.slot_outputs,
                    artifacts=result.artifacts,
                    warnings=result.warnings,
                    validated_bound=validated_bound,
                )
            _log.info(
                "method_dispatch_complete",
                fqn=signature.fqn,
                backend=backend_used.value,
                requested_backend=signature.backend.value,
                elapsed_ms=round(elapsed_ms, 2),
                n_obs=n_obs,
                selection_reason=decision.reason,
                attempts=[(backend.value, reason) for backend, reason in attempts],
            )
            _record_execution(
                signature=signature,
                elapsed_ms=elapsed_ms,
                success=True,
                n_obs=n_obs,
                state=state,
                backend_used=backend_used,
                result=result,
                advisor_context=advisor_context,
                history_store=self._runtime_history,
            )
            span.set_attribute("foundry.dispatch_status", "success")
            span.set_attribute("foundry.elapsed_ms", elapsed_ms)
            span.set_attribute(
                "foundry.estimated_cost_usd",
                dispatch_artifacts["cost_attribution"]["estimated_cost_usd"],
            )
            span.set_attribute(
                "foundry.determinism_tier",
                result.reproducibility.determinism_tier.value,
            )
            if metrics.slo_run_cost_usd:
                metrics.slo_run_cost_usd.record(
                    dispatch_artifacts["cost_attribution"]["estimated_cost_usd"],
                    {
                        "component": "foundry_method",
                        "method_fqn": signature.fqn,
                        "backend": backend_used.value,
                    },
                )

        # Basic anomaly detection: NaN/Inf + key sanity (vectorised, near-zero cost)
        expected_keys: set[str] | None = None
        if signature.output_slots:
            expected_keys = {s.name for s in signature.output_slots}
        monitor = get_output_monitor()
        flags = monitor.check_basic(result.output, expected_keys=expected_keys)
        if flags:
            import warnings

            for flag in flags:
                warnings.warn(str(flag), stacklevel=3)
            _emit_anomaly_metric(signature.fqn, flags)

        return result

    def _maybe_attach_equivalence_certificate(
        self,
        *,
        result: MethodResult,
        signature: MethodSignature,
        backend_used: ComputeBackend,
    ) -> MethodResult:
        resolver = self._equivalence_resolver or get_default_equivalence_resolver()
        if resolver is None:
            return result
        if result.cross_backend_equivalence_ref is not None:
            return result
        if backend_used == signature.backend:
            return result
        resolved = resolver.resolve(
            method_fqn=signature.fqn,
            source_backend=backend_used,
            target_backend=signature.backend,
        )
        if resolved is None:
            return result
        applicability = assess_certificate_applicability(
            result=result,
            certificate=resolved.certificate,
            target_backend=signature.backend,
            method_fqn=signature.fqn,
        )
        if not applicability.applicable:
            return result
        return attach_equivalence_ref(
            result,
            resolved.certificate_ref,
            applicability.verdict,
            report=applicability,
            attestation_ref=resolved.attestation_ref,
        )

    def _dispatch_with_candidates(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        seed: int,
        preferred_backend: ComputeBackend,
        attempts: list[tuple[ComputeBackend, str]],
    ) -> MethodResult:
        last_exc: Exception | None = None
        for backend in self._candidate_backends(
            method_class=method_class,
            signature=signature,
            preferred_backend=preferred_backend,
        ):
            try:
                result = self._execute_on_backend(
                    backend=backend,
                    method_class=method_class,
                    signature=signature,
                    state=state,
                    params=params,
                    seed=seed,
                )
                attempts.append((backend, "success"))
                return result
            except BackendCircuitOpenError as exc:
                attempts.append((backend, "circuit_open"))
                last_exc = exc
            except BackendNotAvailableError as exc:
                attempts.append((backend, "runner_unavailable"))
                last_exc = exc
            except _KNOWN_DISPATCH_FAILURES as exc:
                attempts.append((backend, type(exc).__name__))
                last_exc = exc
                if backend == signature.backend:
                    raise
                _log.warning(
                    "method_dispatch_profile_backend_failed",
                    fqn=signature.fqn,
                    backend=backend.value,
                    requested_backend=signature.backend.value,
                    exc=type(exc).__name__,
                )
        if last_exc is not None:
            raise last_exc
        raise BackendNotAvailableError(preferred_backend)

    def _candidate_backends(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        preferred_backend: ComputeBackend,
    ) -> tuple[ComputeBackend, ...]:
        ordered: list[ComputeBackend] = [preferred_backend]
        if preferred_backend != signature.backend:
            ordered.append(signature.backend)
        fallback_backend = self._fallback_strategy.select_fallback(
            method_class,
            signature,
            signature.backend,
        )
        if fallback_backend is not None and fallback_backend not in ordered:
            ordered.append(fallback_backend)
        return tuple(ordered)

    def _execute_on_backend(
        self,
        *,
        backend: ComputeBackend,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        seed: int,
    ) -> MethodResult:
        runner = self._resolve_runner(backend)
        breaker = get_circuit_breaker_registry().get(backend.value)

        def _execute() -> MethodResult:
            return runner.execute(
                method_class=method_class,
                signature=signature,
                state=state,
                params=params,
                seed=seed,
            )

        return breaker.call(_execute)

    def _select_backend(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        n_obs: int | None,
    ) -> DispatchDecision:
        requested_backend = signature.backend
        if not self._enable_runtime_selection:
            return DispatchDecision(
                requested_backend=requested_backend,
                selected_backend=requested_backend,
                reason="declared_backend",
            )

        fallback_backend = self._fallback_strategy.select_fallback(
            method_class,
            signature,
            requested_backend,
        )
        if fallback_backend is None or requested_backend == fallback_backend:
            return DispatchDecision(
                requested_backend=requested_backend,
                selected_backend=requested_backend,
                reason="declared_backend",
            )

        predictor = self._get_runtime_predictor()
        if predictor is None or n_obs is None:
            return DispatchDecision(
                requested_backend=requested_backend,
                selected_backend=requested_backend,
                reason="declared_backend",
            )

        n_features = _infer_data_characteristics(state, n_obs).get("n_features", 1)
        predicted_requested = predictor.predict_ms(
            signature.fqn,
            int(n_obs),
            int(n_features),
            backend=requested_backend.value,
        )
        predicted_fallback = predictor.predict_ms(
            signature.fqn,
            int(n_obs),
            int(n_features),
            backend=fallback_backend.value,
        )

        if not self._backend_is_viable(fallback_backend):
            return DispatchDecision(
                requested_backend=requested_backend,
                selected_backend=requested_backend,
                reason="declared_backend",
                predicted_requested_ms=predicted_requested,
                predicted_selected_ms=predicted_requested,
            )

        if (
            predicted_fallback + self._runtime_selection_min_delta_ms
            <= predicted_requested * self._runtime_selection_ratio
        ):
            return DispatchDecision(
                requested_backend=requested_backend,
                selected_backend=fallback_backend,
                reason="runtime_profile_fallback_preferred",
                predicted_requested_ms=predicted_requested,
                predicted_selected_ms=predicted_fallback,
            )

        return DispatchDecision(
            requested_backend=requested_backend,
            selected_backend=requested_backend,
            reason="declared_backend",
            predicted_requested_ms=predicted_requested,
            predicted_selected_ms=predicted_requested,
        )

    def _get_runtime_predictor(self) -> RuntimePredictor | None:
        if self._runtime_predictor is not None:
            return self._runtime_predictor
        history = (
            get_global_selection_history()
            if self._runtime_history is None
            else self._runtime_history
        )
        if len(history) == 0:
            return None
        return fit_runtime_predictor_from_history(history)

    def _backend_is_viable(self, backend: ComputeBackend) -> bool:
        breaker = get_circuit_breaker_registry().get(backend.value)
        if breaker.state is not None and breaker.state.value == "open":
            return False
        try:
            self._resolve_runner(backend)
        except BackendNotAvailableError:
            return False
        return True

    def _resolve_runner(self, backend: ComputeBackend) -> MethodRunner:
        try:
            return self._dispatcher.resolve(backend)
        except CoreBackendNotAvailableError as exc:
            raise BackendNotAvailableError(backend) from exc

    @staticmethod
    def _create_runner(backend: ComputeBackend) -> MethodRunner:
        if backend is ComputeBackend.JAX:
            from polisyos.foundry.methods.backends.jax_runner import JaxRunner

            return JaxRunner()
        if backend is ComputeBackend.NUMPY:
            from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner

            return NumpyRunner()
        if backend is ComputeBackend.SOLVER:
            from polisyos.foundry.methods.backends.solver_runner import SolverRunner

            return SolverRunner()
        if backend is ComputeBackend.BAYESIAN:
            from polisyos.foundry.methods.backends.bayesian_runner import BayesianRunner

            return BayesianRunner()
        raise ValueError(f"Unsupported backend: {backend}")
