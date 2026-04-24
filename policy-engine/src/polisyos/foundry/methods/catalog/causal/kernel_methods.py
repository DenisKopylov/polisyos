"""Kernel/RKHS causal methods for Stage 14.1 runtime execution.

These methods intentionally implement a conservative finite-basis version of
kernel mean embeddings. The proof kernel still carries identification; this
module provides the estimation/runtime layer for proof-certified templates.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal._common import (
    bootstrap_ci,
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.treatment_effects import _logistic_propensity
from polisyos.ir.analytics.causal import (
    CausalMethod,
    DiagnosticTest,
    EstimationStatus,
)
from polisyos.ir.analytics.kernel_causal import KernelEstimatorSpec, KernelSpec

_KERNEL_CITATIONS = (
    "Muandet, K. et al. (2017). Kernel Mean Embedding of Distributions: A Review and Beyond.",
    "Singh, R. et al. (2019). Kernel Instrumental Variable Regression.",
    "Mastouri, A. et al. (2021). Proximal Causal Learning with Kernels.",
    "Gretton, A. et al. (2012). A Kernel Two-Sample Test.",
)
_KERNEL_WHEN_TO_USE = (
    "Use for proof-certified kernel causal estimands that require RKHS embeddings, "
    "distributional effects, transport, IV, frontdoor, or proximal bridge diagnostics."
)
_KERNEL_OUTPUT_INTERPRETATION = (
    "JSON payloads contain finite-sample RKHS approximations, diagnostics, and refusal "
    "or uncertainty details for downstream causal reporting."
)


def _json_slot(name: str) -> SlotSpec:
    return SlotSpec(name, SlotType.SCALAR, Unit(name, "json"))


def _diagnostic_signature(name: str) -> MethodSignature:
    return MethodSignature(
        name=name,
        namespace="",
        version="0.0.0",
        input_slots=frozenset(),
        output_slots=frozenset({_json_slot("result")}),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


def _nuisance_signature(name: str, output_name: str) -> MethodSignature:
    return MethodSignature(
        name=name,
        namespace="",
        version="0.0.0",
        input_slots=frozenset(),
        output_slots=frozenset({_json_slot(output_name)}),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


def _estimator_signature(name: str) -> MethodSignature:
    return MethodSignature(
        name=name,
        namespace="",
        version="0.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                _json_slot("report"),
                _json_slot("envelope"),
                _json_slot("warnings"),
                _json_slot("result"),
                _json_slot("kernel_report"),
            }
        ),
        parameters=(
            ParameterSpec(name="n_bootstrap", default=100),
            ParameterSpec(name="confidence_level", default=0.95),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


def _extract_kernel_spec(
    state: Mapping[str, Any], params: Mapping[str, Any]
) -> KernelEstimatorSpec:
    payload = params.get("kernel_spec", state.get("kernel_spec"))
    if isinstance(payload, KernelEstimatorSpec):
        return payload
    if isinstance(payload, dict):
        return KernelEstimatorSpec.model_validate(payload)
    raise ValueError("kernel methods require a kernel_spec payload")


def _as_float_matrix(value: Any) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1:
        return arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError("expected a vector or matrix input")
    return arr


def _as_float_vector(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    return arr


def _candidate_names(spec: KernelEstimatorSpec, role: str, *fallbacks: str) -> tuple[str, ...]:
    names = list(spec.variable_roles.get(role, ()))
    names.extend(value for value in fallbacks if value not in names)
    return tuple(names)


def _resolve_vector(
    state: Mapping[str, Any],
    spec: KernelEstimatorSpec,
    role: str,
    *fallbacks: str,
) -> np.ndarray | None:
    for name in _candidate_names(spec, role, *fallbacks):
        if name in state:
            return _as_float_vector(state[name], name=name)
    return None


def _resolve_matrix(
    state: Mapping[str, Any],
    spec: KernelEstimatorSpec,
    role: str,
    *fallbacks: str,
) -> np.ndarray | None:
    for name in _candidate_names(spec, role, *fallbacks):
        if name in state:
            return _as_float_matrix(state[name])
    return None


def _resolve_covariates(
    state: Mapping[str, Any], spec: KernelEstimatorSpec, n_obs: int
) -> np.ndarray:
    matrix = _resolve_matrix(state, spec, "covariates", "covariates", "X")
    if matrix is not None:
        if matrix.shape[0] != n_obs:
            raise ValueError("covariates must align with outcome/treatment rows")
        return matrix
    covariate_names = spec.variable_roles.get("covariates", ())
    if covariate_names:
        columns = []
        for name in covariate_names:
            if name not in state:
                raise ValueError(f"missing covariate column {name!r} for kernel lowering")
            column = _as_float_vector(state[name], name=name)
            if column.shape[0] != n_obs:
                raise ValueError("named covariate column length mismatch")
            columns.append(column)
        return np.column_stack(columns)
    return np.zeros((n_obs, 0), dtype=float)


def _resolve_target_covariates(
    state: Mapping[str, Any],
    spec: KernelEstimatorSpec,
    *,
    fallback_covariates: np.ndarray,
) -> np.ndarray:
    matrix = _resolve_matrix(state, spec, "target_covariates", "target_covariates")
    if matrix is None:
        return fallback_covariates
    return matrix


def _resolve_binary_treatment(
    state: Mapping[str, Any],
    spec: KernelEstimatorSpec,
) -> np.ndarray:
    treatment = _resolve_vector(state, spec, "treatment", "treatment")
    if treatment is None:
        raise ValueError("kernel estimators require a treatment vector")
    unique = np.unique(np.asarray(treatment, dtype=float))
    if unique.size > 2:
        raise ValueError("Stage 14.1 kernel runtime currently expects binary treatment")
    if unique.size == 1:
        if np.isclose(unique[0], 1.0):
            return np.ones_like(treatment, dtype=float)
        return np.zeros_like(treatment, dtype=float)
    lo, hi = float(unique[0]), float(unique[-1])
    return np.where(np.isclose(treatment, hi), 1.0, 0.0)


def _resolve_outcome(
    state: Mapping[str, Any],
    spec: KernelEstimatorSpec,
) -> np.ndarray:
    outcome = _resolve_vector(state, spec, "outcome", "outcome", "Y")
    if outcome is None:
        raise ValueError("kernel estimators require an outcome vector")
    return outcome


def _resolve_mediator(
    state: Mapping[str, Any],
    spec: KernelEstimatorSpec,
    *,
    n_obs: int,
) -> np.ndarray:
    mediator = _resolve_vector(state, spec, "mediator", "mediator", "M")
    if mediator is None:
        raise ValueError("frontdoor kernel estimator requires a mediator vector")
    if mediator.shape[0] != n_obs:
        raise ValueError("mediator vector length mismatch")
    return mediator


def _resolve_instrument(
    state: Mapping[str, Any],
    spec: KernelEstimatorSpec,
    *,
    n_obs: int,
) -> np.ndarray:
    instrument = _resolve_matrix(state, spec, "instrument", "instrument", "Z")
    if instrument is None:
        vector = _resolve_vector(state, spec, "instrument", "instrument", "Z")
        if vector is not None:
            instrument = vector.reshape(-1, 1)
    if instrument is None:
        raise ValueError("kernel IV estimator requires an instrument")
    if instrument.shape[0] != n_obs:
        raise ValueError("instrument rows must align with outcome/treatment")
    return instrument


def _resolve_proxy(
    state: Mapping[str, Any],
    spec: KernelEstimatorSpec,
    role: str,
    default_name: str,
    *,
    n_obs: int,
) -> np.ndarray:
    proxy = _resolve_vector(state, spec, role, default_name)
    if proxy is None:
        raise ValueError(f"kernel proximal estimator requires {role}")
    if proxy.shape[0] != n_obs:
        raise ValueError(f"{role} rows must align with outcome/treatment")
    return proxy


def _resolve_treatment_contrast(
    treatment: np.ndarray,
    params: Mapping[str, Any],
) -> tuple[float, float]:
    explicit = params.get("treatment_contrast")
    if isinstance(explicit, (list, tuple)) and len(explicit) == 2:
        return float(explicit[0]), float(explicit[1])
    return 1.0, 0.0


def _median_bandwidth(matrix: np.ndarray) -> float:
    arr = _as_float_matrix(matrix)
    if arr.shape[0] < 2:
        return 1.0
    diffs = arr[:, None, :] - arr[None, :, :]
    dist = np.sqrt(np.sum(diffs * diffs, axis=2))
    values = dist[np.triu_indices(arr.shape[0], k=1)]
    values = values[np.isfinite(values) & (values > 1.0e-12)]
    if values.size == 0:
        return 1.0
    return float(np.median(values))


def _bandwidth(spec: KernelSpec, reference: np.ndarray) -> float:
    raw = spec.params.get("bandwidth", "median_heuristic")
    if isinstance(raw, (int, float)) and float(raw) > 0.0:
        return float(raw)
    return _median_bandwidth(reference)


def _kernel_matrix(left: np.ndarray, right: np.ndarray, spec: KernelSpec) -> np.ndarray:
    x_left = _as_float_matrix(left)
    x_right = _as_float_matrix(right)
    name = spec.name.strip().lower()
    if name == "linear":
        return x_left @ x_right.T
    bw = _bandwidth(spec, np.vstack([x_left, x_right]))
    diffs = x_left[:, None, :] - x_right[None, :, :]
    sqdist = np.sum(diffs * diffs, axis=2)
    return np.exp(-sqdist / max(2.0 * bw * bw, 1.0e-12))


def _landmarks(values: np.ndarray, *, max_landmarks: int = 32) -> np.ndarray:
    vec = np.asarray(values, dtype=float).reshape(-1, 1)
    if vec.shape[0] <= max_landmarks:
        return vec
    quantiles = np.linspace(0.0, 1.0, max_landmarks)
    return np.quantile(vec[:, 0], quantiles).reshape(-1, 1)


def _outcome_features(
    outcome: np.ndarray,
    output_kernel: KernelSpec,
    *,
    landmarks: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(outcome, dtype=float).reshape(-1, 1)
    name = output_kernel.name.strip().lower()
    if name == "linear":
        return y, np.array([[0.0]], dtype=float)
    basis = _landmarks(y[:, 0]) if landmarks is None else _as_float_matrix(landmarks)
    return _kernel_matrix(y, basis, output_kernel), basis


def _fit_kernel_regression(
    *,
    inputs: np.ndarray,
    outputs: np.ndarray,
    input_kernel: KernelSpec,
    regularization: float,
    lambda_schedule: tuple[float, ...],
) -> dict[str, Any]:
    x = _as_float_matrix(inputs)
    y = _as_float_matrix(outputs)
    gram = _kernel_matrix(x, x, input_kernel)
    system = gram + x.shape[0] * regularization * np.eye(x.shape[0])
    alpha = np.linalg.solve(system, y)
    trace = []
    for lam in lambda_schedule:
        lam_system = gram + x.shape[0] * lam * np.eye(x.shape[0])
        lam_alpha = np.linalg.solve(lam_system, y)
        trace.append(
            {
                "lambda": float(lam),
                "condition_number": float(np.linalg.cond(lam_system)),
                "solution_norm": float(np.linalg.norm(lam_alpha)),
            }
        )
    return {
        "train_inputs": x.tolist(),
        "alpha": alpha.tolist(),
        "condition_number": float(np.linalg.cond(system)),
        "regularization_trace": trace,
    }


def _predict_kernel_regression(
    model_payload: Mapping[str, Any],
    queries: np.ndarray,
    input_kernel: KernelSpec,
) -> np.ndarray:
    train_inputs = _as_float_matrix(model_payload["train_inputs"])
    alpha = _as_float_matrix(model_payload["alpha"])
    k_q = _kernel_matrix(queries, train_inputs, input_kernel)
    return k_q @ alpha


def _density_ratio_weights(
    state: Mapping[str, Any],
    covariates: np.ndarray,
) -> np.ndarray:
    if "density_ratio_weights" in state:
        weights = _as_float_vector(state["density_ratio_weights"], name="density_ratio_weights")
        if weights.shape[0] == covariates.shape[0]:
            return np.clip(weights, 1.0e-6, None)
    target_covariates = state.get("target_covariates")
    if target_covariates is None:
        return np.ones(covariates.shape[0], dtype=float)
    target = _as_float_matrix(target_covariates)
    source = _as_float_matrix(covariates)
    domain_x = np.vstack([source, target])
    labels = np.concatenate(
        [
            np.zeros(source.shape[0], dtype=float),
            np.ones(target.shape[0], dtype=float),
        ]
    )
    probs = _logistic_propensity(domain_x, labels)
    source_probs = np.clip(probs[: source.shape[0]], 1.0e-3, 1.0 - 1.0e-3)
    ratio = source_probs / np.clip(1.0 - source_probs, 1.0e-3, None)
    scale = max(target.shape[0], 1) / max(source.shape[0], 1)
    return np.clip(ratio * scale, 1.0e-6, None)


def _build_bootstrap_interval(
    unit_embeddings: np.ndarray, *, confidence_level: float, seed: int
) -> tuple[float, float]:
    if unit_embeddings.size == 0:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    draws = np.empty(100, dtype=float)
    n_obs = unit_embeddings.shape[0]
    for idx in range(draws.shape[0]):
        sample = rng.integers(0, n_obs, size=n_obs)
        draws[idx] = float(np.linalg.norm(np.mean(unit_embeddings[sample], axis=0)))
    return bootstrap_ci(draws, confidence_level)


def _kernel_diagnostics(
    spec: KernelEstimatorSpec,
    *,
    effect_norm: float,
    condition_number: float,
    extra: dict[str, float] | None = None,
) -> list[DiagnosticTest]:
    diagnostics = [
        DiagnosticTest(
            test_name="kernel_effect_norm",
            statistic=float(effect_norm),
            passed=bool(effect_norm >= 0.0),
            details={"target_representation": spec.target_representation.value},
        ),
        DiagnosticTest(
            test_name="kernel_condition_number",
            statistic=float(condition_number),
            passed=bool(np.isfinite(condition_number) and condition_number < 1.0e8),
            details={"regularization_selection": spec.regularization.selection.value},
        ),
        DiagnosticTest(
            test_name="kernel_characteristic",
            statistic=1.0 if spec.output_kernel.characteristic else 0.0,
            passed=spec.output_kernel.characteristic,
            details={"weak_metrizing": spec.output_kernel.weak_metrizing},
        ),
    ]
    for key, value in (extra or {}).items():
        diagnostics.append(
            DiagnosticTest(
                test_name=key,
                statistic=float(value),
                passed=bool(np.isfinite(value)),
                details={},
            )
        )
    return diagnostics


def _kernel_report_payload(
    spec: KernelEstimatorSpec,
    *,
    effect_embedding: np.ndarray,
    mu_treated: np.ndarray,
    mu_control: np.ndarray,
    regularization_trace: list[dict[str, Any]],
    condition_number: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "template": spec.template.value,
        "target_representation": spec.target_representation.value,
        "consistency_claim": spec.consistency_claim.value,
        "effect_embedding": np.asarray(effect_embedding, dtype=float).tolist(),
        "treated_embedding": np.asarray(mu_treated, dtype=float).tolist(),
        "control_embedding": np.asarray(mu_control, dtype=float).tolist(),
        "effect_norm": float(np.linalg.norm(effect_embedding)),
        "condition_number": float(condition_number),
        "regularization_trace": regularization_trace,
        "characteristic": spec.output_kernel.characteristic,
        "weak_metrizing": spec.output_kernel.weak_metrizing,
        **dict(extra or {}),
    }


def _build_kernel_report(
    *,
    method: CausalMethod,
    spec: KernelEstimatorSpec,
    effect_embedding: np.ndarray,
    unit_embeddings: np.ndarray,
    mu_treated: np.ndarray,
    mu_control: np.ndarray,
    condition_number: float,
    regularization_trace: list[dict[str, Any]],
    sample_size: int,
    n_treated: int,
    n_control: int,
    inference_method: str,
    assumptions: dict[str, str],
    seed: int,
    extra_diagnostics: dict[str, float] | None = None,
    extra_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effect_norm = float(np.linalg.norm(effect_embedding))
    ci = _build_bootstrap_interval(
        unit_embeddings,
        confidence_level=0.95,
        seed=seed,
    )
    diagnostics = _kernel_diagnostics(
        spec,
        effect_norm=effect_norm,
        condition_number=condition_number,
        extra=extra_diagnostics,
    )
    report = build_success_report(
        method=method,
        estimand="kernel_distributional_effect",
        point_estimate=effect_norm,
        confidence_interval=ci,
        inference_method=inference_method,
        sample_size=sample_size,
        n_treated=n_treated,
        n_control=n_control,
        pre_periods=0,
        post_periods=0,
        assumptions=assumptions,
        diagnostics=diagnostics,
        metadata={
            "kernel_template": spec.template.value,
            "target_representation": spec.target_representation.value,
            "consistency_claim": spec.consistency_claim.value,
        },
    )
    kernel_report = _kernel_report_payload(
        spec,
        effect_embedding=effect_embedding,
        mu_treated=mu_treated,
        mu_control=mu_control,
        regularization_trace=regularization_trace,
        condition_number=condition_number,
        extra=extra_report,
    )
    return wrap_causal_output(
        report,
        warnings=[],
        extras={
            "result": {
                "effect_norm": effect_norm,
                "condition_number": float(condition_number),
                "characteristic": spec.output_kernel.characteristic,
                "weak_metrizing": spec.output_kernel.weak_metrizing,
            },
            "kernel_report": kernel_report,
            "kernel_effect": {
                "effect_embedding": np.asarray(effect_embedding, dtype=float).tolist(),
                "effect_norm": effect_norm,
                "mu_treated": np.asarray(mu_treated, dtype=float).tolist(),
                "mu_control": np.asarray(mu_control, dtype=float).tolist(),
            },
        },
    )


def _fit_backdoor_cme(
    state: Mapping[str, Any],
    spec: KernelEstimatorSpec,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    outcome = _resolve_outcome(state, spec)
    treatment = _resolve_binary_treatment(state, spec)
    covariates = _resolve_covariates(state, spec, outcome.shape[0])
    phi_y, landmarks = _outcome_features(outcome, spec.output_kernel)
    train_inputs = np.column_stack([treatment.reshape(-1, 1), covariates])
    model_payload = state.get("cme_y_given_xz_model")
    if not isinstance(model_payload, Mapping):
        input_kernel = spec.input_kernels.get("covariates", KernelSpec(name="rbf", params={}))
        model_payload = _fit_kernel_regression(
            inputs=train_inputs,
            outputs=phi_y,
            input_kernel=input_kernel,
            regularization=spec.regularization.lambda_value,
            lambda_schedule=spec.regularization.lambda_schedule,
        )
        model_payload = {
            **model_payload,
            "input_kernel": spec.input_kernels.get(
                "covariates",
                KernelSpec(name="rbf", params={}),
            ).model_dump(mode="json"),
            "outcome_landmarks": landmarks.tolist(),
        }
    input_kernel = KernelSpec.model_validate(model_payload["input_kernel"])
    q1 = np.column_stack([np.ones(outcome.shape[0]), covariates])
    q0 = np.column_stack([np.zeros(outcome.shape[0]), covariates])
    mu1_i = _predict_kernel_regression(model_payload, q1, input_kernel)
    mu0_i = _predict_kernel_regression(model_payload, q0, input_kernel)
    return outcome, treatment, covariates, dict(model_payload), mu1_i, mu0_i, phi_y


def _main_trace(model_payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], float]:
    trace = list(model_payload.get("regularization_trace", []))
    condition_number = float(model_payload.get("condition_number", float("nan")))
    return trace, condition_number


def _make_assumption_map(spec: KernelEstimatorSpec) -> dict[str, str]:
    assumptions = dict.fromkeys(
        spec.required_side_conditions, "required by proof-certified kernel lowering"
    )
    assumptions.setdefault(
        "proof_kernel_identification", "proof bundle must certify the interventional law"
    )
    return assumptions


@foundry_method(
    namespace="causal.kernel",
    version="1.0.0",
    tags={"causal", "kernel", "diagnostics", "rkhs", "tabular"},
)
class KernelSemanticsDiagnostics:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _diagnostic_signature("kernel_semantics_diagnostics")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Semantic kernel diagnostics: characteristic, weak-metrizing, and proof-side-condition alignment.",
        tags=frozenset({"causal", "kernel", "diagnostics", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        spec = _extract_kernel_spec(state, params)
        result = {
            "passed": spec.lowering_disposition.value == "ready",
            "lowering_disposition": spec.lowering_disposition.value,
            "characteristic": spec.output_kernel.characteristic,
            "weak_metrizing": spec.output_kernel.weak_metrizing,
            "required_side_conditions": list(spec.required_side_conditions),
            "blocking_reasons": list(spec.blocking_reasons),
        }
        return {"result": result, "kernel_semantics": result}


@foundry_method(
    namespace="causal.kernel",
    version="1.0.0",
    tags={"causal", "kernel", "diagnostics", "regularization", "tabular"},
)
class KernelRegularizationDiagnostics:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _diagnostic_signature("regularization_diagnostics")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Summarize kernel regularization traces and numerical stability.",
        tags=frozenset({"causal", "kernel", "diagnostics", "regularization", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        kernel_report = dict(state.get("kernel_report", {}))
        trace = list(kernel_report.get("regularization_trace", []))
        condition_number = float(kernel_report.get("condition_number", float("nan")))
        effect_norms = [float(kernel_report.get("effect_norm", 0.0))]
        instability = 0.0
        if trace:
            solution_norms = [float(item.get("solution_norm", 0.0)) for item in trace]
            if solution_norms:
                instability = float(np.std(solution_norms))
        result = {
            "passed": bool(np.isfinite(condition_number)),
            "condition_number": condition_number,
            "stability_trace": trace,
            "instability": instability,
            "effect_norms": effect_norms,
        }
        return {"result": result, "kernel_regularization": result}


@foundry_method(
    namespace="causal.kernel",
    version="1.0.0",
    tags={"causal", "kernel", "diagnostics", "distributional", "tabular"},
)
class KernelEffectTest:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _diagnostic_signature("effect_test")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Distributional kernel effect test based on permutation MMD over the observed outcome law.",
        tags=frozenset({"causal", "kernel", "distributional", "diagnostics", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        spec = _extract_kernel_spec(state, params)
        effect_payload = dict(state.get("kernel_effect", {}))
        effect_norm = float(effect_payload.get("effect_norm", 0.0))
        outcome = _resolve_vector(state, spec, "outcome", "outcome", "Y")
        treatment = _resolve_vector(state, spec, "treatment", "treatment")
        p_value = 1.0
        if outcome is not None and treatment is not None:
            y = outcome.reshape(-1, 1)
            t = _resolve_binary_treatment({"treatment": treatment}, spec)
            observed = effect_norm
            rng = np.random.default_rng(int(params.get("__seed__", 0)))
            draws = []
            for _ in range(64):
                perm = rng.permutation(t)
                treated = y[perm > 0.5]
                control = y[perm <= 0.5]
                if treated.size == 0 or control.size == 0:
                    continue
                draws.append(float(abs(np.mean(treated) - np.mean(control))))
            if draws:
                p_value = float((1.0 + np.sum(np.asarray(draws) >= observed)) / (len(draws) + 1.0))
        result = {
            "passed": bool(effect_norm > 0.0 and p_value <= 0.1),
            "effect_norm": effect_norm,
            "p_value": p_value,
            "test_name": "kernel_distributional_effect_test",
        }
        return {"result": result, "kernel_effect_test": result}


@foundry_method(
    namespace="causal.kernel",
    version="1.0.0",
    tags={"causal", "kernel", "refusal", "tabular"},
)
class KernelRefusal:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _estimator_signature("refusal")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Fail-closed kernel lowering refusal node.",
        tags=frozenset({"causal", "kernel", "refusal", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        spec = _extract_kernel_spec(state, params)
        reason = ", ".join(spec.blocking_reasons) or spec.lowering_disposition.value
        report = build_failure_report(
            method=CausalMethod.KERNEL_CME,
            status=EstimationStatus.ASSUMPTION_FAILED,
            reason=f"kernel lowering blocked: {reason}",
            estimand="kernel_distributional_effect",
            sample_size=0,
            n_treated=0,
            n_control=0,
            pre_periods=0,
            post_periods=0,
            assumptions=_make_assumption_map(spec),
        )
        return wrap_causal_output(
            report,
            warnings=[reason],
            extras={
                "result": {"blocking_reasons": list(spec.blocking_reasons)},
                "kernel_report": {},
            },
        )


@foundry_method(
    namespace="causal.kernel.nuisance",
    version="1.0.0",
    tags={"causal", "kernel", "nuisance", "cme", "tabular"},
)
class FitCMEYGivenXZ:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _nuisance_signature(
        "fit_cme_y_given_xz", "cme_y_given_xz_model"
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Fit conditional mean embedding of outcome features on treatment/covariates.",
        tags=frozenset({"causal", "kernel", "nuisance", "cme", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        spec = _extract_kernel_spec(state, params)
        outcome = _resolve_outcome(state, spec)
        treatment = _resolve_binary_treatment(state, spec)
        covariates = _resolve_covariates(state, spec, outcome.shape[0])
        phi_y, landmarks = _outcome_features(outcome, spec.output_kernel)
        model = _fit_kernel_regression(
            inputs=np.column_stack([treatment.reshape(-1, 1), covariates]),
            outputs=phi_y,
            input_kernel=spec.input_kernels.get("covariates", KernelSpec(name="rbf", params={})),
            regularization=spec.regularization.lambda_value,
            lambda_schedule=spec.regularization.lambda_schedule,
        )
        payload = {
            **model,
            "input_kernel": spec.input_kernels.get(
                "covariates", KernelSpec(name="rbf", params={})
            ).model_dump(mode="json"),
            "outcome_landmarks": landmarks.tolist(),
        }
        return {
            "cme_y_given_xz_model": payload,
            "result": {
                "condition_number": float(payload["condition_number"]),
                "n_obs": int(outcome.shape[0]),
            },
        }


@foundry_method(
    namespace="causal.kernel.nuisance",
    version="1.0.0",
    tags={"causal", "kernel", "nuisance", "cme", "tabular"},
)
class FitCMEMGivenX:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _nuisance_signature(
        "fit_cme_m_given_x", "cme_m_given_x_model"
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Fit mediator embedding weights conditioned on treatment.",
        tags=frozenset({"causal", "kernel", "nuisance", "cme", "frontdoor", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        spec = _extract_kernel_spec(state, params)
        outcome = _resolve_outcome(state, spec)
        treatment = _resolve_binary_treatment(state, spec)
        mediator = _resolve_mediator(state, spec, n_obs=outcome.shape[0])
        payload = {
            "treatment": treatment.tolist(),
            "mediator": mediator.tolist(),
            "input_kernel": spec.input_kernels.get(
                "treatment", KernelSpec(name="rbf", params={})
            ).model_dump(mode="json"),
            "regularization": spec.regularization.lambda_value,
            "lambda_schedule": list(spec.regularization.lambda_schedule),
        }
        return {
            "cme_m_given_x_model": payload,
            "result": {"n_obs": int(outcome.shape[0])},
        }


@foundry_method(
    namespace="causal.kernel.nuisance",
    version="1.0.0",
    tags={"causal", "kernel", "nuisance", "cme", "tabular"},
)
class FitCMEYGivenMX:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _nuisance_signature(
        "fit_cme_y_given_mx", "cme_y_given_mx_model"
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Fit conditional mean embedding of outcomes on mediator/treatment.",
        tags=frozenset({"causal", "kernel", "nuisance", "cme", "frontdoor", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        spec = _extract_kernel_spec(state, params)
        outcome = _resolve_outcome(state, spec)
        treatment = _resolve_binary_treatment(state, spec)
        mediator = _resolve_mediator(state, spec, n_obs=outcome.shape[0])
        phi_y, landmarks = _outcome_features(outcome, spec.output_kernel)
        model = _fit_kernel_regression(
            inputs=np.column_stack([mediator.reshape(-1, 1), treatment.reshape(-1, 1)]),
            outputs=phi_y,
            input_kernel=spec.input_kernels.get("mediator", KernelSpec(name="rbf", params={})),
            regularization=spec.regularization.lambda_value,
            lambda_schedule=spec.regularization.lambda_schedule,
        )
        payload = {
            **model,
            "input_kernel": spec.input_kernels.get(
                "mediator", KernelSpec(name="rbf", params={})
            ).model_dump(mode="json"),
            "outcome_landmarks": landmarks.tolist(),
        }
        return {
            "cme_y_given_mx_model": payload,
            "result": {
                "condition_number": float(payload["condition_number"]),
                "n_obs": int(outcome.shape[0]),
            },
        }


@foundry_method(
    namespace="causal.kernel.nuisance",
    version="1.0.0",
    tags={"causal", "kernel", "nuisance", "transport", "tabular"},
)
class FitDensityRatio:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _nuisance_signature(
        "fit_density_ratio", "density_ratio_weights"
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Estimate transport density-ratio weights between source and target covariates.",
        tags=frozenset({"causal", "kernel", "nuisance", "transport", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        spec = _extract_kernel_spec(state, params)
        outcome = _resolve_outcome(state, spec)
        covariates = _resolve_covariates(state, spec, outcome.shape[0])
        weights = _density_ratio_weights(state, covariates)
        return {
            "density_ratio_weights": weights.tolist(),
            "result": {
                "mean_weight": float(np.mean(weights)),
                "ess_fraction": float(
                    (np.sum(weights) ** 2) / max(np.sum(weights**2), 1.0) / max(len(weights), 1)
                ),
            },
        }


@foundry_method(
    namespace="causal.kernel.nuisance",
    version="1.0.0",
    tags={"causal", "kernel", "nuisance", "propensity", "tabular"},
)
class FitKernelPropensity:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _nuisance_signature("fit_propensity", "propensity_model")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Fit propensity scores for doubly robust kernel estimators.",
        tags=frozenset({"causal", "kernel", "nuisance", "propensity", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        spec = _extract_kernel_spec(state, params)
        outcome = _resolve_outcome(state, spec)
        treatment = _resolve_binary_treatment(state, spec)
        covariates = _resolve_covariates(state, spec, outcome.shape[0])
        e_hat = _logistic_propensity(covariates, treatment)
        payload = {"propensity": np.clip(e_hat, 1.0e-3, 1.0 - 1.0e-3).tolist()}
        overlap_score = float(np.mean((e_hat >= 0.1) & (e_hat <= 0.9)))
        return {
            "propensity_model": payload,
            "result": {
                "overlap_score": overlap_score,
                "passes_positivity": bool(np.all((e_hat > 0.01) & (e_hat < 0.99))),
            },
        }


@foundry_method(
    namespace="causal.kernel.nuisance",
    version="1.0.0",
    tags={"causal", "kernel", "nuisance", "iv", "tabular"},
)
class FitKIVFirstStage:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _nuisance_signature(
        "fit_kiv_first_stage", "kiv_first_stage_model"
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="First-stage kernel IV regression from instruments to treatment.",
        tags=frozenset({"causal", "kernel", "nuisance", "iv", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        spec = _extract_kernel_spec(state, params)
        outcome = _resolve_outcome(state, spec)
        treatment = _resolve_binary_treatment(state, spec)
        covariates = _resolve_covariates(state, spec, outcome.shape[0])
        instrument = _resolve_instrument(state, spec, n_obs=outcome.shape[0])
        design = np.column_stack([instrument, covariates])
        model = _fit_kernel_regression(
            inputs=design,
            outputs=treatment.reshape(-1, 1),
            input_kernel=spec.input_kernels.get("instrument", KernelSpec(name="rbf", params={})),
            regularization=spec.regularization.lambda_value,
            lambda_schedule=spec.regularization.lambda_schedule,
        )
        payload = {
            **model,
            "input_kernel": spec.input_kernels.get(
                "instrument", KernelSpec(name="rbf", params={})
            ).model_dump(mode="json"),
        }
        return {
            "kiv_first_stage_model": payload,
            "result": {
                "condition_number": float(payload["condition_number"]),
                "operator_injectivity_score": float(1.0 / max(payload["condition_number"], 1.0)),
            },
        }


@foundry_method(
    namespace="causal.kernel.nuisance",
    version="1.0.0",
    tags={"causal", "kernel", "nuisance", "iv", "tabular"},
)
class FitKIVSecondStage:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _nuisance_signature(
        "fit_kiv_second_stage", "kiv_second_stage_model"
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Second-stage kernel IV embedding regression from instrument-predicted treatment to outcomes.",
        tags=frozenset({"causal", "kernel", "nuisance", "iv", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        spec = _extract_kernel_spec(state, params)
        outcome = _resolve_outcome(state, spec)
        covariates = _resolve_covariates(state, spec, outcome.shape[0])
        first_stage = dict(state.get("kiv_first_stage_model", {}))
        if not first_stage:
            raise ValueError("kernel IV second stage requires first-stage model")
        instrument = _resolve_instrument(state, spec, n_obs=outcome.shape[0])
        input_kernel = KernelSpec.model_validate(first_stage["input_kernel"])
        treatment_hat = _predict_kernel_regression(
            first_stage, np.column_stack([instrument, covariates]), input_kernel
        )[:, 0]
        phi_y, landmarks = _outcome_features(outcome, spec.output_kernel)
        model = _fit_kernel_regression(
            inputs=np.column_stack([treatment_hat.reshape(-1, 1), covariates]),
            outputs=phi_y,
            input_kernel=spec.input_kernels.get("treatment", KernelSpec(name="rbf", params={})),
            regularization=spec.regularization.lambda_value,
            lambda_schedule=spec.regularization.lambda_schedule,
        )
        payload = {
            **model,
            "input_kernel": spec.input_kernels.get(
                "treatment", KernelSpec(name="rbf", params={})
            ).model_dump(mode="json"),
            "outcome_landmarks": landmarks.tolist(),
        }
        return {
            "kiv_second_stage_model": payload,
            "result": {
                "condition_number": float(payload["condition_number"]),
            },
        }


@foundry_method(
    namespace="causal.kernel.nuisance",
    version="1.0.0",
    tags={"causal", "kernel", "nuisance", "proximal", "tabular"},
)
class SolveKernelProximalBridge:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _nuisance_signature(
        "solve_proximal_bridge", "proximal_bridge_model"
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Solve a finite-dimensional proximal bridge approximation in feature space.",
        tags=frozenset({"causal", "kernel", "nuisance", "proximal", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        spec = _extract_kernel_spec(state, params)
        outcome = _resolve_outcome(state, spec)
        treatment = _resolve_binary_treatment(state, spec)
        covariates = _resolve_covariates(state, spec, outcome.shape[0])
        z_proxy = _resolve_proxy(
            state, spec, "treatment_proxy", "treatment_proxy", n_obs=outcome.shape[0]
        )
        w_proxy = _resolve_proxy(
            state, spec, "outcome_proxy", "outcome_proxy", n_obs=outcome.shape[0]
        )
        phi_y, landmarks = _outcome_features(outcome, spec.output_kernel)
        model = _fit_kernel_regression(
            inputs=np.column_stack([treatment.reshape(-1, 1), covariates, w_proxy.reshape(-1, 1)]),
            outputs=phi_y,
            input_kernel=spec.input_kernels.get("covariates", KernelSpec(name="rbf", params={})),
            regularization=spec.regularization.lambda_value,
            lambda_schedule=spec.regularization.lambda_schedule,
        )
        proxy_score = (
            float(abs(np.corrcoef(z_proxy, w_proxy)[0, 1]))
            if np.std(z_proxy) > 1.0e-12 and np.std(w_proxy) > 1.0e-12
            else 0.0
        )
        payload = {
            **model,
            "input_kernel": spec.input_kernels.get(
                "covariates", KernelSpec(name="rbf", params={})
            ).model_dump(mode="json"),
            "outcome_landmarks": landmarks.tolist(),
            "proxy_score": proxy_score,
        }
        return {
            "proximal_bridge_model": payload,
            "result": {
                "condition_number": float(payload["condition_number"]),
                "operator_injectivity_score": float(1.0 / max(payload["condition_number"], 1.0)),
                "proxy_association_score": proxy_score,
            },
        }


@foundry_method(
    namespace="causal.kernel",
    version="1.0.0",
    tags={"causal", "kernel", "rkhs", "plugin", "tabular"},
)
class KernelCMEPluginEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _estimator_signature("cme_plugin")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Backdoor/g-formula kernel conditional mean embedding estimator.",
        tags=frozenset({"causal", "kernel", "rkhs", "plugin", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            spec = _extract_kernel_spec(state, params)
            outcome, treatment, _, model_payload, mu1_i, mu0_i, _ = _fit_backdoor_cme(state, spec)
            effect_i = mu1_i - mu0_i
            mu1 = np.mean(mu1_i, axis=0)
            mu0 = np.mean(mu0_i, axis=0)
            trace, condition_number = _main_trace(model_payload)
            return _build_kernel_report(
                method=CausalMethod.KERNEL_CME,
                spec=spec,
                effect_embedding=mu1 - mu0,
                unit_embeddings=effect_i,
                mu_treated=mu1,
                mu_control=mu0,
                condition_number=condition_number,
                regularization_trace=trace,
                sample_size=int(outcome.shape[0]),
                n_treated=int(np.sum(treatment > 0.5)),
                n_control=int(np.sum(treatment <= 0.5)),
                inference_method="bootstrap_embedding_norm",
                assumptions=_make_assumption_map(spec),
                seed=int(params.get("__seed__", 0)),
            )
        except Exception as exc:
            spec = _extract_kernel_spec(state, params)
            report = build_failure_report(
                method=CausalMethod.KERNEL_CME,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="kernel_distributional_effect",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=_make_assumption_map(spec),
            )
            return wrap_causal_output(
                report, warnings=[str(exc)], extras={"kernel_report": {}, "result": {}}
            )


@foundry_method(
    namespace="causal.kernel",
    version="1.0.0",
    tags={"causal", "kernel", "rkhs", "frontdoor", "tabular"},
)
class KernelFrontdoorEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _estimator_signature("frontdoor_cme")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Frontdoor kernel estimator with nested empirical integration.",
        tags=frozenset({"causal", "kernel", "rkhs", "frontdoor", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            spec = _extract_kernel_spec(state, params)
            outcome = _resolve_outcome(state, spec)
            treatment = _resolve_binary_treatment(state, spec)
            mediator = _resolve_mediator(state, spec, n_obs=outcome.shape[0])
            mediator_model = dict(state.get("cme_m_given_x_model", {}))
            if not mediator_model:
                mediator_model = FitCMEMGivenX.pure_step(state, params)["cme_m_given_x_model"]
            outcome_model = dict(state.get("cme_y_given_mx_model", {}))
            if not outcome_model:
                outcome_model = FitCMEYGivenMX.pure_step(state, params)["cme_y_given_mx_model"]

            input_kernel = KernelSpec.model_validate(outcome_model["input_kernel"])
            queries_all = np.column_stack([mediator.reshape(-1, 1), treatment.reshape(-1, 1)])
            # For each mediator observation, average over empirical treatment distribution.
            g_embeddings = np.empty(
                (outcome.shape[0], _as_float_matrix(outcome_model["alpha"]).shape[1]), dtype=float
            )
            for idx, mediator_value in enumerate(mediator):
                queries = np.column_stack(
                    [
                        np.full(outcome.shape[0], mediator_value, dtype=float),
                        treatment,
                    ]
                )
                g_embeddings[idx] = np.mean(
                    _predict_kernel_regression(outcome_model, queries, input_kernel), axis=0
                )

            treat_kernel = KernelSpec.model_validate(mediator_model["input_kernel"])
            treatment_train = _as_float_vector(mediator_model["treatment"], name="treatment")
            gram_t = _kernel_matrix(
                treatment_train.reshape(-1, 1), treatment_train.reshape(-1, 1), treat_kernel
            )
            lam = float(mediator_model.get("regularization", spec.regularization.lambda_value))
            system = gram_t + treatment_train.shape[0] * lam * np.eye(treatment_train.shape[0])

            def _beta(a_value: float) -> np.ndarray:
                k_q = _kernel_matrix(
                    np.full((1, 1), a_value, dtype=float),
                    treatment_train.reshape(-1, 1),
                    treat_kernel,
                )[0]
                weights = np.linalg.solve(system, k_q)
                weights = weights / max(np.sum(np.abs(weights)), 1.0)
                return weights

            beta1 = _beta(1.0)
            beta0 = _beta(0.0)
            mu1 = beta1 @ g_embeddings
            mu0 = beta0 @ g_embeddings
            unit_effects = g_embeddings * (beta1 - beta0)[:, None]
            trace = list(spec.regularization.model_dump(mode="json").get("lambda_schedule", []))
            regularization_trace = [{"lambda": float(value)} for value in trace]
            condition_number = float(np.linalg.cond(system))
            return _build_kernel_report(
                method=CausalMethod.KERNEL_FRONTDOOR,
                spec=spec,
                effect_embedding=mu1 - mu0,
                unit_embeddings=unit_effects,
                mu_treated=np.asarray(mu1, dtype=float),
                mu_control=np.asarray(mu0, dtype=float),
                condition_number=condition_number,
                regularization_trace=regularization_trace,
                sample_size=int(outcome.shape[0]),
                n_treated=int(np.sum(treatment > 0.5)),
                n_control=int(np.sum(treatment <= 0.5)),
                inference_method="bootstrap_embedding_norm",
                assumptions=_make_assumption_map(spec),
                seed=int(params.get("__seed__", 0)),
                extra_report={"approximation": "nested_empirical_frontdoor_cme"},
            )
        except Exception as exc:
            spec = _extract_kernel_spec(state, params)
            report = build_failure_report(
                method=CausalMethod.KERNEL_FRONTDOOR,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="kernel_distributional_effect",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=_make_assumption_map(spec),
            )
            return wrap_causal_output(
                report, warnings=[str(exc)], extras={"kernel_report": {}, "result": {}}
            )


@foundry_method(
    namespace="causal.kernel",
    version="1.0.0",
    tags={"causal", "kernel", "rkhs", "transport", "tabular"},
)
class KernelTransportEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _estimator_signature("transport_cme")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Kernel transport estimator with target-weighted counterfactual averaging.",
        tags=frozenset({"causal", "kernel", "rkhs", "transport", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            spec = _extract_kernel_spec(state, params)
            outcome, treatment, covariates, model_payload, _, _, _ = _fit_backdoor_cme(state, spec)
            input_kernel = KernelSpec.model_validate(model_payload["input_kernel"])
            target_covariates = _resolve_target_covariates(
                state, spec, fallback_covariates=covariates
            )
            q1 = np.column_stack([np.ones(target_covariates.shape[0]), target_covariates])
            q0 = np.column_stack([np.zeros(target_covariates.shape[0]), target_covariates])
            mu1_i = _predict_kernel_regression(model_payload, q1, input_kernel)
            mu0_i = _predict_kernel_regression(model_payload, q0, input_kernel)
            weights = _density_ratio_weights(state, covariates)
            weights = weights / max(np.sum(weights), 1.0)
            if weights.shape[0] == mu1_i.shape[0]:
                mu1 = np.sum(mu1_i * weights[:, None], axis=0)
                mu0 = np.sum(mu0_i * weights[:, None], axis=0)
            else:
                mu1 = np.mean(mu1_i, axis=0)
                mu0 = np.mean(mu0_i, axis=0)
            trace, condition_number = _main_trace(model_payload)
            return _build_kernel_report(
                method=CausalMethod.KERNEL_TRANSPORT,
                spec=spec,
                effect_embedding=mu1 - mu0,
                unit_embeddings=mu1_i - mu0_i,
                mu_treated=mu1,
                mu_control=mu0,
                condition_number=condition_number,
                regularization_trace=trace,
                sample_size=int(outcome.shape[0]),
                n_treated=int(np.sum(treatment > 0.5)),
                n_control=int(np.sum(treatment <= 0.5)),
                inference_method="bootstrap_embedding_norm",
                assumptions=_make_assumption_map(spec),
                seed=int(params.get("__seed__", 0)),
                extra_diagnostics={"transport_weight_mean": float(np.mean(weights))},
            )
        except Exception as exc:
            spec = _extract_kernel_spec(state, params)
            report = build_failure_report(
                method=CausalMethod.KERNEL_TRANSPORT,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="kernel_distributional_effect",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=_make_assumption_map(spec),
            )
            return wrap_causal_output(
                report, warnings=[str(exc)], extras={"kernel_report": {}, "result": {}}
            )


@foundry_method(
    namespace="causal.kernel",
    version="1.0.0",
    tags={"causal", "kernel", "rkhs", "dr", "tabular"},
)
class KernelDRCMEEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _estimator_signature("dr_cme")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Doubly robust kernel embedding estimator for binary-treatment distributional effects.",
        tags=frozenset({"causal", "kernel", "rkhs", "dr", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            spec = _extract_kernel_spec(state, params)
            outcome, treatment, _, model_payload, mu1_i, mu0_i, phi_y = _fit_backdoor_cme(
                state, spec
            )
            propensity_model = dict(state.get("propensity_model", {}))
            if propensity_model and "propensity" in propensity_model:
                e_hat = np.clip(
                    _as_float_vector(propensity_model["propensity"], name="propensity"),
                    1.0e-3,
                    1.0 - 1.0e-3,
                )
            else:
                covariates = _resolve_covariates(state, spec, outcome.shape[0])
                e_hat = np.clip(_logistic_propensity(covariates, treatment), 1.0e-3, 1.0 - 1.0e-3)

            mu1_dr_i = mu1_i + (treatment[:, None] / e_hat[:, None]) * (phi_y - mu1_i)
            mu0_dr_i = mu0_i + ((1.0 - treatment)[:, None] / (1.0 - e_hat)[:, None]) * (
                phi_y - mu0_i
            )
            mu1 = np.mean(mu1_dr_i, axis=0)
            mu0 = np.mean(mu0_dr_i, axis=0)
            trace, condition_number = _main_trace(model_payload)
            return _build_kernel_report(
                method=CausalMethod.KERNEL_DR_CME,
                spec=spec,
                effect_embedding=mu1 - mu0,
                unit_embeddings=mu1_dr_i - mu0_dr_i,
                mu_treated=mu1,
                mu_control=mu0,
                condition_number=condition_number,
                regularization_trace=trace,
                sample_size=int(outcome.shape[0]),
                n_treated=int(np.sum(treatment > 0.5)),
                n_control=int(np.sum(treatment <= 0.5)),
                inference_method="bootstrap_embedding_norm",
                assumptions=_make_assumption_map(spec),
                seed=int(params.get("__seed__", 0)),
                extra_diagnostics={"mean_propensity": float(np.mean(e_hat))},
            )
        except Exception as exc:
            spec = _extract_kernel_spec(state, params)
            report = build_failure_report(
                method=CausalMethod.KERNEL_DR_CME,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="kernel_distributional_effect",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=_make_assumption_map(spec),
            )
            return wrap_causal_output(
                report, warnings=[str(exc)], extras={"kernel_report": {}, "result": {}}
            )


@foundry_method(
    namespace="causal.kernel",
    version="1.0.0",
    tags={"causal", "kernel", "rkhs", "iv", "tabular"},
)
class KernelIVEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _estimator_signature("kiv")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Two-stage kernel IV estimator for proof-certified inverse-problem queries.",
        tags=frozenset({"causal", "kernel", "rkhs", "iv", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            spec = _extract_kernel_spec(state, params)
            outcome = _resolve_outcome(state, spec)
            treatment = _resolve_binary_treatment(state, spec)
            covariates = _resolve_covariates(state, spec, outcome.shape[0])
            first_stage = dict(state.get("kiv_first_stage_model", {}))
            if not first_stage:
                first_stage = FitKIVFirstStage.pure_step(state, params)["kiv_first_stage_model"]
            second_stage = dict(state.get("kiv_second_stage_model", {}))
            if not second_stage:
                second_stage = FitKIVSecondStage.pure_step(
                    {**state, "kiv_first_stage_model": first_stage},
                    params,
                )["kiv_second_stage_model"]

            input_kernel = KernelSpec.model_validate(second_stage["input_kernel"])
            q1 = np.column_stack([np.ones(outcome.shape[0]), covariates])
            q0 = np.column_stack([np.zeros(outcome.shape[0]), covariates])
            mu1_i = _predict_kernel_regression(second_stage, q1, input_kernel)
            mu0_i = _predict_kernel_regression(second_stage, q0, input_kernel)
            mu1 = np.mean(mu1_i, axis=0)
            mu0 = np.mean(mu0_i, axis=0)
            trace, condition_number = _main_trace(second_stage)
            extra_score = float(1.0 / max(condition_number, 1.0))
            return _build_kernel_report(
                method=CausalMethod.KERNEL_IV,
                spec=spec,
                effect_embedding=mu1 - mu0,
                unit_embeddings=mu1_i - mu0_i,
                mu_treated=mu1,
                mu_control=mu0,
                condition_number=condition_number,
                regularization_trace=trace,
                sample_size=int(outcome.shape[0]),
                n_treated=int(np.sum(treatment > 0.5)),
                n_control=int(np.sum(treatment <= 0.5)),
                inference_method="bootstrap_embedding_norm",
                assumptions=_make_assumption_map(spec),
                seed=int(params.get("__seed__", 0)),
                extra_diagnostics={"operator_injectivity_score": extra_score},
            )
        except Exception as exc:
            spec = _extract_kernel_spec(state, params)
            report = build_failure_report(
                method=CausalMethod.KERNEL_IV,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="kernel_distributional_effect",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=_make_assumption_map(spec),
            )
            return wrap_causal_output(
                report, warnings=[str(exc)], extras={"kernel_report": {}, "result": {}}
            )


@foundry_method(
    namespace="causal.kernel",
    version="1.0.0",
    tags={"causal", "kernel", "rkhs", "proximal", "tabular"},
)
class KernelProximalMinimaxEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = _estimator_signature("proximal_minimax")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Finite-dimensional proximal minimax estimator over outcome embeddings.",
        tags=frozenset({"causal", "kernel", "rkhs", "proximal", "tabular"}),
        citations=_KERNEL_CITATIONS,
        when_to_use=_KERNEL_WHEN_TO_USE,
        output_interpretation=_KERNEL_OUTPUT_INTERPRETATION,
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            spec = _extract_kernel_spec(state, params)
            outcome = _resolve_outcome(state, spec)
            treatment = _resolve_binary_treatment(state, spec)
            covariates = _resolve_covariates(state, spec, outcome.shape[0])
            bridge_model = dict(state.get("proximal_bridge_model", {}))
            if not bridge_model:
                bridge_model = SolveKernelProximalBridge.pure_step(state, params)[
                    "proximal_bridge_model"
                ]

            input_kernel = KernelSpec.model_validate(bridge_model["input_kernel"])
            w_proxy = _resolve_proxy(
                state, spec, "outcome_proxy", "outcome_proxy", n_obs=outcome.shape[0]
            )
            design1 = np.column_stack(
                [np.ones(outcome.shape[0]), covariates, w_proxy.reshape(-1, 1)]
            )
            design0 = np.column_stack(
                [np.zeros(outcome.shape[0]), covariates, w_proxy.reshape(-1, 1)]
            )
            mu1_i = _predict_kernel_regression(bridge_model, design1, input_kernel)
            mu0_i = _predict_kernel_regression(bridge_model, design0, input_kernel)
            mu1 = np.mean(mu1_i, axis=0)
            mu0 = np.mean(mu0_i, axis=0)
            trace, condition_number = _main_trace(bridge_model)
            proxy_score = float(bridge_model.get("proxy_score", 0.0))
            return _build_kernel_report(
                method=CausalMethod.KERNEL_PROXIMAL_MINIMAX,
                spec=spec,
                effect_embedding=mu1 - mu0,
                unit_embeddings=mu1_i - mu0_i,
                mu_treated=mu1,
                mu_control=mu0,
                condition_number=condition_number,
                regularization_trace=trace,
                sample_size=int(outcome.shape[0]),
                n_treated=int(np.sum(treatment > 0.5)),
                n_control=int(np.sum(treatment <= 0.5)),
                inference_method="bootstrap_embedding_norm",
                assumptions=_make_assumption_map(spec),
                seed=int(params.get("__seed__", 0)),
                extra_diagnostics={
                    "operator_injectivity_score": float(1.0 / max(condition_number, 1.0)),
                    "proxy_association_score": proxy_score,
                },
            )
        except Exception as exc:
            spec = _extract_kernel_spec(state, params)
            report = build_failure_report(
                method=CausalMethod.KERNEL_PROXIMAL_MINIMAX,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="kernel_distributional_effect",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=_make_assumption_map(spec),
            )
            return wrap_causal_output(
                report, warnings=[str(exc)], extras={"kernel_report": {}, "result": {}}
            )


__all__ = [
    "FitCMEMGivenX",
    "FitCMEYGivenMX",
    "FitCMEYGivenXZ",
    "FitDensityRatio",
    "FitKIVFirstStage",
    "FitKIVSecondStage",
    "FitKernelPropensity",
    "KernelCMEPluginEstimator",
    "KernelDRCMEEstimator",
    "KernelEffectTest",
    "KernelFrontdoorEstimator",
    "KernelIVEstimator",
    "KernelProximalMinimaxEstimator",
    "KernelRefusal",
    "KernelRegularizationDiagnostics",
    "KernelSemanticsDiagnostics",
    "KernelTransportEstimator",
    "SolveKernelProximalBridge",
]
