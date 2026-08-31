"""Machine-check closure of Foundry Phase 0 deliverables."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

type Path = Any

from polisyos.core.contracts.execution_plan import MethodCatalogSnapshot
from polisyos.core.observability import DeterminismTier
from polisyos.foundry.agent_sim.world import (
    SyntheticWorldDGP,
    phase0_seed_benchmark_binding,
    phase0_seed_world_specs,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    BackendRuntimeFingerprint,
    compose_observed_tolerance_budgets,
    validate_observed_tolerance_budget,
    validate_observed_tolerance_budget_metrics,
)
from polisyos.foundry.methods.backends.validated import ValidatedStatus
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
)
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog.bayesian.protocols import PosteriorResult
from polisyos.foundry.methods.catalog.snapshot import build_method_catalog_snapshot
from polisyos.foundry.methods.equivalence import (
    ComparatorKind,
    CrossBackendEquivalenceCertificate,
    FieldToleranceSpec,
    InMemoryEquivalenceCertificateRegistry,
    reset_default_equivalence_resolver,
    runtime_envelope_from_results,
    set_default_equivalence_resolver,
)
from polisyos.foundry.methods.microsim import (
    SurveyMicroData,
    ensure_microsim_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.selection import (
    DataCharacteristics,
    MethodAdvisorQuery,
    MethodAdvisorResult,
    MethodSelectionCriteria,
    advise_methods,
)
from polisyos.foundry.methods.selection_history import (
    MethodExecutionRecord,
    SelectionHistoryStore,
)
from polisyos.ir.analytics.forecasting_uncertainty import ForecastingUncertaintyBundle
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _manifest_path(repo_root: Path) -> Path:
    return repo_root / "tools/quality/validation/foundry_phase0_manifest.json"


def _check_result(
    check_id: str,
    *,
    ok: bool,
    detail: str,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "complete" if ok else "incomplete",
        "detail": detail,
        "evidence": dict(evidence or {}),
    }


def _has_model_field(model: type, field_name: str) -> bool:
    model_fields = getattr(model, "model_fields", None)
    if isinstance(model_fields, Mapping):
        return field_name in model_fields
    return hasattr(model, field_name)


def _history_with_numpy_advantage(method_fqn: str) -> SelectionHistoryStore:
    history = SelectionHistoryStore()
    now = time.time()
    for idx in range(3):
        history.record(
            MethodExecutionRecord(
                method_fqn=method_fqn,
                timestamp=now + idx,
                latency_ms=120.0,
                success=True,
                data_characteristics={"n_obs": 64, "n_features": 4, "backend": "jax"},
            )
        )
        history.record(
            MethodExecutionRecord(
                method_fqn=method_fqn,
                timestamp=now + 100 + idx,
                latency_ms=25.0,
                success=True,
                data_characteristics={"n_obs": 64, "n_features": 4, "backend": "numpy"},
            )
        )
    return history


def _make_statistical_posture() -> BackendRuntimeFingerprint:
    return BackendRuntimeFingerprint(
        backend=ComputeBackend.BAYESIAN,
        available=True,
        determinism_tier=DeterminismTier.STATISTICAL,
        execution_device="cpu:phase0",
        runtime_stack=("numpy", "numpyro"),
        library_versions={"numpy": "1.0"},
        route_key={
            "backend_route": "bayesian:numpy",
            "arch_family": "x86_64",
            "device_family": "cpu",
        },
    )


class _Phase0DispatchMethod:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="runtime_selected",
        namespace="phase0.validation",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.JAX,
        supports_jit=True,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="phase0 validation dispatch probe"
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
        return state


class _ValidationRunner(MethodRunner):
    def __init__(
        self,
        backend: ComputeBackend,
        *,
        equivalence_ref: str | None = None,
    ) -> None:
        self._backend = backend
        self._equivalence_ref = equivalence_ref

    @property
    def supported_backends(self) -> frozenset[ComputeBackend]:
        return frozenset({self._backend})

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
        return MethodResult(
            output={"backend": self._backend.value},
            timing=MethodTiming(wall_time_ms=1.0),
            reproducibility=ReproducibilityInfo(
                backend=self._backend,
                determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
                seed=seed,
            ),
            cross_backend_equivalence_ref=self._equivalence_ref,
        )


def _check_hmc_nuts_truthfulness() -> dict[str, Any]:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_foundry_phase0_closure")
    target_fqns = {
        "bayesian.sampling.hmc@1.0.0",
        "bayesian.sampling.nuts@1.0.0",
    }
    entries = {entry.fqn: entry for entry in snapshot.entries if entry.fqn in target_fqns}
    subset = MethodCatalogSnapshot(
        snapshot_id="foundry-phase0-truthfulness",
        entries=tuple(entries.values()),
    )
    advisor = advise_methods(
        subset,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(runnable_only=False),
            data=DataCharacteristics(n_obs=1_000),
            limit=2,
            runnable_only=False,
        ),
    )
    ok = (
        set(entries) == target_fqns
        and len(advisor.payload) == 2
        and all(entry.declared_truthfulness_tier == "asymptotic" for entry in entries.values())
        and all(entry.truthfulness_scope == "posterior" for entry in entries.values())
        and all(entry.truthfulness_tier == "asymptotic" for entry in entries.values())
        and all(entry.truthfulness_status == "catalog_only" for entry in entries.values())
        and all(row["truthfulness_tier"] == "asymptotic" for row in advisor.payload)
        and all(row["truthfulness_status"] == "catalog_only" for row in advisor.payload)
    )
    return _check_result(
        "hmc_nuts_truthfulness_closure",
        ok=ok,
        detail="HMC/NUTS declare asymptotic posterior truthfulness in catalog and advisor pre-run surfaces.",
        evidence={
            "catalog_entries": {
                fqn: {
                    "declared_truthfulness_tier": entry.declared_truthfulness_tier,
                    "truthfulness_scope": entry.truthfulness_scope,
                    "truthfulness_tier": entry.truthfulness_tier,
                    "truthfulness_status": entry.truthfulness_status,
                }
                for fqn, entry in sorted(entries.items())
            },
            "advisor_payload": list(advisor.payload),
        },
    )


def _check_statistical_tolerance_budget() -> dict[str, Any]:
    posture = _make_statistical_posture()
    reference = np.linspace(-1.0, 1.0, 128, dtype=float).reshape(64, 2)
    same_fingerprint = validate_observed_tolerance_budget(
        reference=reference,
        candidate=reference.copy(),
        budget=posture.observed_tolerance_budget,
        current_tier=DeterminismTier.STATISTICAL,
    )
    cross_architecture = validate_observed_tolerance_budget_metrics(
        metrics={
            "ks_statistic": 0.09,
            "q50_abs_error": 0.04,
            "q90_width_abs_error": 0.06,
        },
        budget=posture.observed_tolerance_budget,
        current_tier=DeterminismTier.STATISTICAL,
    )
    composed = compose_observed_tolerance_budgets(
        [same_fingerprint, cross_architecture],
        determinism_tiers=[DeterminismTier.STATISTICAL, DeterminismTier.STATISTICAL],
        composition_kind="parallel",
    )
    revalidated = validate_observed_tolerance_budget_metrics(
        metrics=composed["distributional_metrics"],
        budget=composed,
        current_tier=DeterminismTier.STATISTICAL,
    )
    expected_budget = posture.observed_tolerance_budget.get("expected_budget", {})
    ok = (
        same_fingerprint["validation_status"] == "validated"
        and cross_architecture["validation_status"] == "compatible"
        and revalidated["validation_status"] == "compatible"
        and "distributional_runtime_validation_not_implemented"
        not in cross_architecture.get("failure_reasons", [])
        and expected_budget.get("same_fingerprint_ks_tol") is not None
        and expected_budget.get("same_architecture_q50_abs_tol") is not None
        and expected_budget.get("cross_architecture_q90_width_abs_tol") is not None
    )
    return _check_result(
        "statistical_tolerance_budget_validation",
        ok=ok,
        detail="Statistical tolerance budgets are machine-checkable for direct and composed replay budgets.",
        evidence={
            "expected_budget": expected_budget,
            "same_fingerprint": same_fingerprint,
            "cross_architecture": cross_architecture,
            "composed": composed,
            "revalidated": revalidated,
        },
    )


def _check_default_dispatch_equivalence() -> dict[str, Any]:
    source_runner = _ValidationRunner(ComputeBackend.NUMPY)
    target_runner = _ValidationRunner(ComputeBackend.JAX)
    source_result = source_runner.execute(
        method_class=_Phase0DispatchMethod,
        signature=_Phase0DispatchMethod.signature,
        state={"X": np.ones((8, 2))},
        params={},
        seed=41,
    )
    target_result = target_runner.execute(
        method_class=_Phase0DispatchMethod,
        signature=_Phase0DispatchMethod.signature,
        state={"X": np.ones((8, 2))},
        params={},
        seed=41,
    )
    registry = InMemoryEquivalenceCertificateRegistry()
    registry.register(
        certificate_ref="sha256:" + "9" * 64,
        certificate=CrossBackendEquivalenceCertificate(
            certificate_id="xbeq:foundry:phase0:default-dispatch",
            method_fqn=_Phase0DispatchMethod.signature.fqn,
            runtime_envelope=runtime_envelope_from_results(
                source_result=source_result,
                target_result=target_result,
            ),
            field_specs=(
                FieldToleranceSpec(path="output.backend", comparator=ComparatorKind.EXACT),
            ),
        ),
    )

    MethodDispatcher.reset_instance()
    reset_default_equivalence_resolver()
    try:
        set_default_equivalence_resolver(registry)
        dispatcher = MethodDispatcher.get_instance()
        dispatcher._runtime_history = _history_with_numpy_advantage(
            _Phase0DispatchMethod.signature.fqn
        )
        dispatcher.register_runner(_ValidationRunner(ComputeBackend.JAX))
        dispatcher.register_runner(_ValidationRunner(ComputeBackend.NUMPY))
        result = dispatcher.dispatch(
            method_class=_Phase0DispatchMethod,
            signature=_Phase0DispatchMethod.signature,
            state={"X": np.ones((64, 4))},
            params={},
            seed=41,
        )
        ok = result.cross_backend_equivalence_ref == "sha256:" + "9" * 64
        evidence = {
            "selected_backend": result.output["backend"],
            "cross_backend_equivalence_ref": result.cross_backend_equivalence_ref,
            "artifacts": dict(result.artifacts),
        }
    finally:
        MethodDispatcher.reset_instance()
        reset_default_equivalence_resolver()

    return _check_result(
        "cross_backend_equivalence_default_dispatch",
        ok=ok,
        detail="Default dispatcher emits cross-backend equivalence certificates from the process-global resolver.",
        evidence=evidence,
    )


def _check_validated_bound_reachability() -> dict[str, Any]:
    MethodRegistry.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    method_cls = registry.get("microsim.policy.tax_benefit_calculator@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=SurveyMicroData(
            market_income=np.asarray([10000.0, 20000.0, 80000.0], dtype=float),
            weights=np.ones(3, dtype=float),
        ),
        params={"validated_mode": "required"},
        seed=43,
    )
    ok = (
        result.validated_bound is not None
        and result.validated_bound.status is ValidatedStatus.RIGOROUS_ENCLOSURE
        and "validated_bound_certificate" in result.artifacts
    )
    return _check_result(
        "validated_bound_reachability",
        ok=ok,
        detail="ValidatedBound certificates are reachable from registered critical-path estimators.",
        evidence={
            "method_fqn": method_cls.signature.fqn,
            "validated_bound": (
                None if result.validated_bound is None else result.validated_bound.as_dict()
            ),
            "artifact_keys": sorted(result.artifacts),
        },
    )


def _check_synthetic_world_registry() -> dict[str, Any]:
    specs = phase0_seed_world_specs()
    binding = phase0_seed_benchmark_binding()
    calibrated_worlds = [
        spec.world_id for spec in specs if bool(spec.metadata.get("calibrated_world"))
    ]
    ok = (
        len(specs) >= 1
        and isinstance(specs[0], SyntheticWorldDGP)
        and bool(calibrated_worlds)
        and any(world_id in binding.world_ids for world_id in calibrated_worlds)
    )
    return _check_result(
        "synthetic_world_registry",
        ok=ok,
        detail="Phase-0 synthetic worlds include a calibrated world and benchmark binding.",
        evidence={
            "world_ids": [spec.world_id for spec in specs],
            "calibrated_world_ids": calibrated_worlds,
            "binding": binding.model_dump(mode="json"),
        },
    )


def _check_smoke_benchmark(benchmark_payload: Mapping[str, Any]) -> dict[str, Any]:
    aggregate_metrics = dict(benchmark_payload.get("aggregate_metrics") or {})
    cases = list(benchmark_payload.get("cases") or [])
    calibrated_case_ids = [
        str(case.get("case_id") or case.get("name") or "")
        for case in cases
        if bool((case.get("metadata") or {}).get("calibrated_world"))
    ]
    ok = (
        float(aggregate_metrics.get("target_coverage_rate", 0.0)) == 1.0
        and float(aggregate_metrics.get("deterministic_replay_rate", 0.0)) == 1.0
        and bool(calibrated_case_ids)
    )
    return _check_result(
        "synthetic_world_smoke_benchmark",
        ok=ok,
        detail="Synthetic-world smoke benchmark reports perfect target coverage, deterministic replay, and a calibrated world.",
        evidence={
            "aggregate_metrics": aggregate_metrics,
            "calibrated_case_ids": calibrated_case_ids,
            "case_count": len(cases),
        },
    )


def build_foundry_phase0_closure_report(
    *,
    repo_root: Path,
    benchmark_report: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest_path = _manifest_path(repo_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    benchmark_payload = json.loads(benchmark_report.read_text(encoding="utf-8"))

    checks = [
        _check_result(
            "posterior_truthfulness_contract",
            ok=_has_model_field(PosteriorResult, "truthfulness_tier"),
            detail="PosteriorResult exposes truthfulness_tier as a first-class contract field.",
            evidence={"contract_id": PosteriorResult.contract_id},
        ),
        _check_result(
            "forecasting_uncertainty_bundle_contract",
            ok=all(
                _has_model_field(ForecastingUncertaintyBundle, field_name)
                for field_name in (
                    "prediction_interval",
                    "fan_chart",
                    "posterior_predictive_ref",
                    "coverage_diagnostic",
                    "horizon_policy",
                )
            ),
            detail="ForecastingUncertaintyBundle carries the full Phase-0 uncertainty contract.",
            evidence={"contract_id": ForecastingUncertaintyBundle.contract_id},
        ),
        _check_result(
            "uncertainty_envelope_provenance",
            ok=_has_model_field(UncertaintyEnvelope, "composition_provenance"),
            detail="UncertaintyEnvelope records composition provenance for chained methods.",
            evidence={"schema_version": UncertaintyEnvelope.model_fields["schema_version"].default},
        ),
        _check_result(
            "advisor_regret_certificate",
            ok="calibrated_regret_certificate" in MethodAdvisorResult.__dataclass_fields__,
            detail="MethodAdvisorResult carries calibrated regret certificates.",
            evidence={
                "dataclass_fields": sorted(MethodAdvisorResult.__dataclass_fields__),
            },
        ),
        _check_hmc_nuts_truthfulness(),
        _check_statistical_tolerance_budget(),
        _check_default_dispatch_equivalence(),
        _check_validated_bound_reachability(),
        _check_synthetic_world_registry(),
        _check_smoke_benchmark(benchmark_payload),
    ]

    overall_status = (
        "complete" if all(check["status"] == "complete" for check in checks) else "incomplete"
    )
    return {
        "assessment_id": "foundry_phase0_closure",
        "phase_id": str(manifest.get("phase_id") or "foundry.phase0"),
        "overall_status": overall_status,
        "manifest_path": _repo_relative(manifest_path, repo_root),
        "benchmark_report": _repo_relative(benchmark_report, repo_root),
        "source_of_truth": manifest.get("source_of_truth"),
        "checks": checks,
        "summary": {
            "complete_checks": sum(1 for check in checks if check["status"] == "complete"),
            "total_checks": len(checks),
        },
    }
