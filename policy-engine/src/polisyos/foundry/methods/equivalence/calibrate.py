"""Calibration harness for backend-equivalence certificates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np

from polisyos.core.canon import fingerprint
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.foundry.methods.backends.adapters import adapt_state
from polisyos.foundry.methods.backends.bayesian_runner import BayesianRunner
from polisyos.foundry.methods.backends.jax_runner import JaxRunner
from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner
from polisyos.foundry.methods.backends.protocol import MethodResult, MethodRunner
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    compose_observed_tolerance_budgets,
)
from polisyos.foundry.methods.backends.solver_runner import SolverRunner
from polisyos.foundry.methods.base import ComputeBackend
from polisyos.foundry.methods.equivalence.bounds import (
    EquivalencePolicy,
    FieldCalibrationStats,
    derive_field_tolerance_spec,
    derive_pairwise_budget,
)
from polisyos.foundry.methods.equivalence.canonicalize import (
    canonicalize_method_result,
)
from polisyos.foundry.methods.equivalence.protocol import (
    CrossBackendEquivalenceCertificate,
    EquivalenceRuntimeEnvelope,
    EquivalenceVerdict,
    EquivalenceVerificationReport,
    FieldToleranceSpec,
)
from polisyos.foundry.methods.equivalence.verify import (
    runtime_envelope_from_results,
    verify_backend_equivalence,
)
from polisyos.foundry.methods.registry import MethodRegistry, get_registry


@dataclass(frozen=True, slots=True)
class CalibrationCase:
    """One deterministic/stochastic calibration run configuration."""

    state: Any
    params: Mapping[str, Any] = field(default_factory=dict)
    seed: int = 0
    label: str = ""
    state_backend: ComputeBackend = ComputeBackend.NUMPY


@dataclass(frozen=True, slots=True)
class CalibrationBattery:
    """Battery of input regimes used to calibrate one backend pair."""

    cases: tuple[CalibrationCase, ...]
    battery_id: str = "xbeq.manual.v1"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.cases:
            raise ValueError("CalibrationBattery.cases must be non-empty")

    @property
    def digest(self) -> str:
        payload = {
            "battery_id": self.battery_id,
            "cases": [
                {
                    "label": case.label,
                    "seed": case.seed,
                    "state_backend": case.state_backend.value,
                    "state": _normalize_for_hash(case.state),
                    "params": _normalize_for_hash(dict(case.params)),
                }
                for case in self.cases
            ],
            "metadata": _normalize_for_hash(dict(self.metadata)),
        }
        return fingerprint(
            payload,
            prefix=True,
            canon_spec=CanonSpec(forbid_floats=False),
        )


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    """Detailed calibration output beyond the certificate itself."""

    certificate: CrossBackendEquivalenceCertificate
    field_stats: tuple[FieldCalibrationStats, ...]
    case_reports: tuple[EquivalenceVerificationReport, ...]


def calibrate_backend_pair(
    *,
    method_fqn: str,
    source_backend: ComputeBackend,
    target_backend: ComputeBackend,
    battery: CalibrationBattery,
    policy: EquivalencePolicy,
    registry: MethodRegistry | None = None,
) -> CrossBackendEquivalenceCertificate:
    """Calibrate one backend pair and return a certificate artifact payload."""

    return calibrate_backend_pair_detailed(
        method_fqn=method_fqn,
        source_backend=source_backend,
        target_backend=target_backend,
        battery=battery,
        policy=policy,
        registry=registry,
    ).certificate


def calibrate_backend_pair_detailed(
    *,
    method_fqn: str,
    source_backend: ComputeBackend,
    target_backend: ComputeBackend,
    battery: CalibrationBattery,
    policy: EquivalencePolicy,
    registry: MethodRegistry | None = None,
) -> CalibrationResult:
    """Run one battery through two backends and synthesize a certificate."""

    reg = registry or get_registry()
    method_class = reg.get(method_fqn)
    signature = method_class.signature
    source_runner = _runner_for_backend(source_backend, registry=reg)
    target_runner = _runner_for_backend(target_backend, registry=reg)
    if not source_runner.is_available():
        raise RuntimeError(f"Source backend '{source_backend.value}' is not available")
    if not target_runner.is_available():
        raise RuntimeError(f"Target backend '{target_backend.value}' is not available")

    observations: list[tuple[MethodResult, MethodResult]] = []
    common_paths: set[str] | None = None
    for case in battery.cases:
        source_result = _execute_case(
            runner=source_runner,
            backend=source_backend,
            method_class=method_class,
            signature=signature,
            case=case,
        )
        target_result = _execute_case(
            runner=target_runner,
            backend=target_backend,
            method_class=method_class,
            signature=signature,
            case=case,
        )
        observations.append((source_result, target_result))
        source_tree = canonicalize_method_result(source_result)
        target_tree = canonicalize_method_result(target_result)
        case_paths = {
            path
            for path in source_tree.keys() & target_tree.keys()
            if _path_selected(path=path, policy=policy)
        }
        common_paths = case_paths if common_paths is None else common_paths & case_paths

    if not common_paths:
        raise RuntimeError("Calibration battery produced no common comparable field paths")

    field_specs: list[FieldToleranceSpec] = []
    field_stats: list[FieldCalibrationStats] = []
    source_runtime_envelopes: list[EquivalenceRuntimeEnvelope] = []
    for source_result, target_result in observations:
        source_runtime_envelopes.append(
            runtime_envelope_from_results(
                source_result=source_result,
                target_result=target_result,
            )
        )

    for path in sorted(common_paths):
        samples: list[tuple[Any, Any]] = []
        base_abs_tol = 0.0
        base_rel_tol = 0.0
        for source_result, target_result in observations:
            source_tree = canonicalize_method_result(source_result)
            target_tree = canonicalize_method_result(target_result)
            samples.append((source_tree[path], target_tree[path]))
            obs_abs_tol, obs_rel_tol = derive_pairwise_budget(
                source_result=source_result,
                target_result=target_result,
            )
            base_abs_tol = max(base_abs_tol, obs_abs_tol)
            base_rel_tol = max(base_rel_tol, obs_rel_tol)
        spec, stats = derive_field_tolerance_spec(
            path=path,
            samples=samples,
            base_abs_tol=base_abs_tol,
            base_rel_tol=base_rel_tol,
            policy=policy,
        )
        field_specs.append(spec)
        field_stats.append(stats)

    certificate = CrossBackendEquivalenceCertificate(
        certificate_id=_certificate_id(
            method_fqn=method_fqn,
            source_backend=source_backend,
            target_backend=target_backend,
        ),
        method_fqn=method_fqn,
        runtime_envelope=_merge_runtime_envelopes(
            source_backend=source_backend,
            target_backend=target_backend,
            envelopes=tuple(source_runtime_envelopes),
            pin_runtime_fingerprints=policy.pin_runtime_fingerprints,
        ),
        field_specs=tuple(field_specs),
        confidence=policy.confidence,
        provenance={
            "calibration_policy": {
                "strict_quantile": policy.strict_quantile,
                "relaxed_multiplier": policy.relaxed_multiplier,
                "relaxed_headroom": policy.relaxed_headroom,
                "scale_floor": policy.scale_floor,
                "equal_nan": policy.equal_nan,
            },
            "field_statistics": [stats.as_dict() for stats in field_stats],
        },
        test_vectors={
            "battery_id": battery.battery_id,
            "dataset_digest": battery.digest,
            "n_cases": len(battery.cases),
            "labels": [case.label for case in battery.cases if case.label],
            "metadata": dict(battery.metadata),
        },
        created_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        expires_at=_expires_at(policy),
    )

    case_reports = tuple(
        verify_backend_equivalence(
            result=source_result,
            counterpart=target_result,
            certificate=certificate,
            method_fqn=method_fqn,
        )
        for source_result, target_result in observations
    )
    final_verdict = _aggregate_case_verdicts(case_reports)
    certificate = replace(
        certificate,
        global_verdict=final_verdict,
        provenance={
            **dict(certificate.provenance),
            "ci_measured_tolerance_budget": _calibration_ci_measured_budget(
                case_reports=case_reports,
                battery_id=battery.battery_id,
            ),
        },
    )
    return CalibrationResult(
        certificate=certificate,
        field_stats=tuple(field_stats),
        case_reports=case_reports,
    )


def _execute_case(
    *,
    runner: MethodRunner,
    backend: ComputeBackend,
    method_class: type,
    signature,
    case: CalibrationCase,
) -> MethodResult:
    state = adapt_state(
        case.state,
        source_backend=case.state_backend,
        target_backend=backend,
    )
    params = adapt_state(
        dict(case.params),
        source_backend=case.state_backend,
        target_backend=backend,
    )
    return runner.execute(
        method_class=method_class,
        signature=signature,
        state=state,
        params=params,
        seed=case.seed,
    )


def _runner_for_backend(
    backend: ComputeBackend,
    *,
    registry: MethodRegistry | None = None,
) -> MethodRunner:
    if backend is ComputeBackend.NUMPY:
        return NumpyRunner()
    if backend is ComputeBackend.JAX:
        if registry is None:
            return JaxRunner()
        from polisyos.foundry.methods.compiler import MethodCompiler

        return JaxRunner(MethodCompiler(registry=registry))
    if backend is ComputeBackend.SOLVER:
        return SolverRunner()
    if backend is ComputeBackend.BAYESIAN:
        return BayesianRunner()
    raise ValueError(f"Unsupported backend: {backend.value}")


def _path_selected(*, path: str, policy: EquivalencePolicy) -> bool:
    if policy.include_prefixes and not any(
        path == prefix or path.startswith(f"{prefix}.") for prefix in policy.include_prefixes
    ):
        return False
    if any(path == prefix or path.startswith(f"{prefix}.") for prefix in policy.exclude_prefixes):
        return False
    return True


def _merge_runtime_envelopes(
    *,
    source_backend: ComputeBackend,
    target_backend: ComputeBackend,
    envelopes: tuple[EquivalenceRuntimeEnvelope, ...],
    pin_runtime_fingerprints: bool,
) -> EquivalenceRuntimeEnvelope:
    source_versions = _common_string_mapping(
        tuple(env.source_library_versions for env in envelopes)
    )
    target_versions = _common_string_mapping(
        tuple(env.target_library_versions for env in envelopes)
    )
    source_execution_device = _common_or_none(
        tuple(env.source_execution_device for env in envelopes)
    )
    target_execution_device = _common_or_none(
        tuple(env.target_execution_device for env in envelopes)
    )
    source_tier = _common_or_none(tuple(env.source_determinism_tier for env in envelopes))
    target_tier = _common_or_none(tuple(env.target_determinism_tier for env in envelopes))
    source_route_key = _common_mapping(tuple(env.source_route_key for env in envelopes))
    target_route_key = _common_mapping(tuple(env.target_route_key for env in envelopes))
    source_runtime_fingerprint = (
        _common_or_none(tuple(env.source_runtime_fingerprint for env in envelopes))
        if pin_runtime_fingerprints
        else None
    )
    target_runtime_fingerprint = (
        _common_or_none(tuple(env.target_runtime_fingerprint for env in envelopes))
        if pin_runtime_fingerprints
        else None
    )
    return EquivalenceRuntimeEnvelope(
        source_backend=source_backend,
        target_backend=target_backend,
        source_runtime_fingerprint=source_runtime_fingerprint,
        target_runtime_fingerprint=target_runtime_fingerprint,
        source_execution_device=source_execution_device,
        target_execution_device=target_execution_device,
        source_determinism_tier=source_tier,
        target_determinism_tier=target_tier,
        source_library_versions=source_versions,
        target_library_versions=target_versions,
        source_route_key=source_route_key,
        target_route_key=target_route_key,
    )


def _aggregate_case_verdicts(
    reports: tuple[EquivalenceVerificationReport, ...],
) -> EquivalenceVerdict:
    if any(report.verdict is EquivalenceVerdict.UNKNOWN for report in reports):
        return EquivalenceVerdict.UNKNOWN
    if any(report.verdict is EquivalenceVerdict.FAIL for report in reports):
        return EquivalenceVerdict.FAIL
    if any(report.verdict is EquivalenceVerdict.PASS_RELAXED for report in reports):
        return EquivalenceVerdict.PASS_RELAXED
    return EquivalenceVerdict.PASS_STRICT


def _calibration_ci_measured_budget(
    *,
    case_reports: tuple[EquivalenceVerificationReport, ...],
    battery_id: str,
) -> dict[str, Any]:
    measured = [
        dict(report.runtime_budget_validation)
        for report in case_reports
        if report.runtime_budget_validation
    ]
    if not measured:
        return {
            "budget_source": "none",
            "canary_suite_id": battery_id,
            "sample_count": 0,
        }

    composed = compose_observed_tolerance_budgets(
        measured,
        composition_kind="parallel",
    )
    abs_samples = [
        float(budget["abs_tol_p99"]) for budget in measured if budget.get("abs_tol_p99") is not None
    ]
    rel_samples = [
        float(budget["rel_tol_p99"]) for budget in measured if budget.get("rel_tol_p99") is not None
    ]
    composed["budget_source"] = "ci_measured"
    composed["canary_suite_id"] = battery_id
    composed["sample_count"] = len(measured)
    if abs_samples:
        abs_values = np.asarray(abs_samples, dtype=np.float64)
        composed["abs_tol_p50"] = float(np.quantile(abs_values, 0.50))
        composed["abs_tol_p95"] = float(np.quantile(abs_values, 0.95))
        composed["abs_tol_p99"] = float(np.quantile(abs_values, 0.99))
    if rel_samples:
        rel_values = np.asarray(rel_samples, dtype=np.float64)
        composed["rel_tol_p50"] = float(np.quantile(rel_values, 0.50))
        composed["rel_tol_p95"] = float(np.quantile(rel_values, 0.95))
        composed["rel_tol_p99"] = float(np.quantile(rel_values, 0.99))
    return composed


def _certificate_id(
    *,
    method_fqn: str,
    source_backend: ComputeBackend,
    target_backend: ComputeBackend,
) -> str:
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"xbeq:{method_fqn}:{source_backend.value}__{target_backend.value}:{timestamp}"


def _expires_at(policy: EquivalencePolicy) -> str | None:
    if policy.certificate_ttl_days is None:
        return None
    expires_at = datetime.now(UTC).replace(microsecond=0) + timedelta(
        days=policy.certificate_ttl_days
    )
    return expires_at.isoformat().replace("+00:00", "Z")


def _common_string_mapping(mappings: tuple[Mapping[str, str], ...]) -> dict[str, str]:
    if not mappings:
        return {}
    keys = set(mappings[0])
    for mapping in mappings[1:]:
        keys &= set(mapping)
    common: dict[str, str] = {}
    for key in sorted(keys):
        values = {mapping.get(key) for mapping in mappings}
        if len(values) == 1:
            value = next(iter(values))
            if value is not None:
                common[str(key)] = str(value)
    return common


def _common_mapping(mappings: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    if not mappings:
        return {}
    keys = set(mappings[0])
    for mapping in mappings[1:]:
        keys &= set(mapping)
    common: dict[str, Any] = {}
    for key in sorted(keys):
        values = [mapping.get(key) for mapping in mappings]
        first = values[0]
        if all(value == first for value in values):
            common[str(key)] = first
    return common


def _common_or_none(values: tuple[Any, ...]) -> Any | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    first = filtered[0]
    if all(value == first for value in filtered):
        return first
    return None


def _normalize_for_hash(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_for_hash(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_for_hash(item) for item in value]
    if hasattr(value, "shape") and hasattr(value, "dtype"):
        return np.asarray(value).tolist()
    return value


__all__ = [
    "CalibrationBattery",
    "CalibrationCase",
    "CalibrationResult",
    "calibrate_backend_pair",
    "calibrate_backend_pair_detailed",
]
