from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    IdentifiabilityDiagnosticRef,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.foundry.calibration.hessian import HessianResult
from polisyos.foundry.calibration.identifiability import (
    IdentifiabilityDiagnosticConfig,
    IdentifiabilityDiagnosticStatus,
    IdentifiabilityStatus,
    aggregate_moment_summary,
    attach_identifiability_diagnostic_ref,
    diagnose_identifiability,
    identifiability_diagnostic,
    load_identifiability_diagnostic_result,
)


def _make_hessian_result(
    diag: list[float],
    param_names: list[str] | None = None,
) -> HessianResult:
    """Helper: build a HessianResult from diagonal Hessian values."""
    n = len(diag)
    H = np.diag(diag)
    cov = np.diag([1.0 / d for d in diag])
    std = np.array([1.0 / d**0.5 for d in diag])
    eigvals = np.array(sorted(diag))
    if param_names is None:
        param_names = [f"p{i}" for i in range(n)]
    cond = max(diag) / min(diag) if min(diag) > 0 else float("inf")
    return HessianResult(
        hessian=H,
        covariance=cov,
        std=std,
        eigenvalues=eigvals,
        condition_number=cond,
        n_repaired=0,
        param_names=param_names,
        strategy="exact",
    )


def test_identified_parameter() -> None:
    """Parameters with large Hessian diagonal should be IDENTIFIED."""
    hr = _make_hessian_result([1.0, 5.0], ["alpha", "beta"])
    report = diagnose_identifiability(hr)

    assert report.n_identified == 2
    assert report.n_sloppy == 0
    assert report.n_non_identified == 0
    for p in report.params:
        assert p.status == IdentifiabilityStatus.IDENTIFIED


def test_sloppy_parameter_flagged() -> None:
    """A parameter with eigenvalue in (1e-8, 1e-3) should be SLOPPY."""
    hr = _make_hessian_result([1.0, 1e-5], ["good", "sloppy"])
    report = diagnose_identifiability(hr)

    assert report.n_identified == 1
    assert report.n_sloppy == 1
    statuses = {p.name: p.status for p in report.params}
    assert statuses["good"] == IdentifiabilityStatus.IDENTIFIED
    assert statuses["sloppy"] == IdentifiabilityStatus.SLOPPY


def test_non_identified_parameter_flagged() -> None:
    """A parameter with eigenvalue <= 1e-8 should be NON_IDENTIFIED."""
    hr = _make_hessian_result([2.0, 1e-10], ["strong", "flat"])
    report = diagnose_identifiability(hr)

    assert report.n_identified == 1
    assert report.n_non_identified == 1
    statuses = {p.name: p.status for p in report.params}
    assert statuses["strong"] == IdentifiabilityStatus.IDENTIFIED
    assert statuses["flat"] == IdentifiabilityStatus.NON_IDENTIFIED
    assert report.effective_dimension == 1


def _put_minimal_simulation_result(store: FileSystemCAS) -> SimulationResultRef:
    exec_ref = store.put_json(
        {"schema_version": "1.0", "kind": "test_exec_plan"},
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        {"values": {"mean_y": 0.0}},
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    simulation_result = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=exec_ref.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
    )
    ref = store.put_json(
        simulation_result,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return SimulationResultRef(artifact_id=ref.artifact_id)


def test_aggregate_identifiability_config_validates_quantiles() -> None:
    config = IdentifiabilityDiagnosticConfig(
        quantiles=(0.10, 0.50, 0.90),
        simulation_reps=2,
        bootstrap_reps=0,
    )

    assert config.quantiles == (0.10, 0.50, 0.90)
    with pytest.raises(ValueError, match="unique and sorted"):
        IdentifiabilityDiagnosticConfig(quantiles=(0.50, 0.10))


def test_aggregate_moment_summary_uses_mean_variance_and_configured_quantiles() -> None:
    summary = aggregate_moment_summary(
        [1.0, 2.0, 3.0, 4.0],
        quantiles=(0.25, 0.50, 0.75),
        prefix="income",
    )

    assert summary["income_mean"] == pytest.approx(2.5)
    assert summary["income_variance"] == pytest.approx(1.25)
    assert summary["income_q25"] == pytest.approx(1.75)
    assert summary["income_q50"] == pytest.approx(2.5)
    assert summary["income_q75"] == pytest.approx(3.25)


def test_aggregate_identifiability_gaussian_affine_sidecar_persists(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    simulation_ref = _put_minimal_simulation_result(store)
    z25 = -0.6744897501960817
    z75 = 0.6744897501960817

    def evaluator(theta: dict[str, float], seed: int | None) -> dict[str, float]:
        del seed
        mu = float(theta["mu"])
        sigma = float(theta["sigma"])
        return {
            "mean_y": 1.0 + 2.0 * mu,
            "var_y": 4.0 * sigma * sigma,
            "q25_y": 1.0 + 2.0 * (mu + sigma * z25),
            "q75_y": 1.0 + 2.0 * (mu + sigma * z75),
        }

    center = {"mu": 0.5, "sigma": 1.2}
    observed = evaluator(center, None)
    result = identifiability_diagnostic(
        store,
        simulation_result_ref=simulation_ref,
        observed_moment_bundle=observed,
        parameter_center=center,
        summary_evaluator=evaluator,
        config=IdentifiabilityDiagnosticConfig(
            simulation_reps=2,
            bootstrap_reps=8,
            profile_grid_size=5,
            seed=123,
        ),
    )

    assert result.status is IdentifiabilityDiagnosticStatus.IDENTIFIED
    assert result.jacobian_rank == 2
    assert result.effective_dimension == 2
    assert result.sensitivity_matrix_ref is not None
    assert result.profile_trace_ref is not None
    assert result.diagnostic_ref is not None

    loaded = load_identifiability_diagnostic_result(store, result.diagnostic_ref)
    assert loaded.status is IdentifiabilityDiagnosticStatus.IDENTIFIED
    assert loaded.sensitivity_matrix_ref is not None

    manifest = store.get_manifest(result.diagnostic_ref.artifact_id)
    assert manifest.kind == "foundry.identifiability_diagnostic"
    assert {item.role for item in manifest.inputs} >= {
        "simulation_result",
        "artifact.sensitivity_matrix_ref",
        "artifact.profile_trace_ref",
    }

    attached_ref = attach_identifiability_diagnostic_ref(
        store,
        simulation_result_ref=simulation_ref,
        diagnostic_ref=IdentifiabilityDiagnosticRef(
            artifact_id=result.diagnostic_ref.artifact_id
        ),
    )
    attached = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(attached_ref.artifact_id))
    )
    assert attached.identifiability_diagnostic_ref is not None
    assert attached.identifiability_diagnostic_ref.artifact_id == result.diagnostic_ref.artifact_id


def test_aggregate_identifiability_profiles_minimize_over_nuisance_parameters(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    simulation_ref = _put_minimal_simulation_result(store)

    def evaluator(theta: dict[str, float], seed: int | None) -> dict[str, float]:
        del seed
        return {"sum": float(theta["a"] + theta["b"])}

    result = identifiability_diagnostic(
        store,
        simulation_result_ref=simulation_ref,
        observed_moment_bundle={"sum": 2.0},
        parameter_center={"a": 1.0, "b": 1.0},
        summary_evaluator=evaluator,
        config=IdentifiabilityDiagnosticConfig(
            simulation_reps=1,
            bootstrap_reps=0,
            profile_grid_size=3,
            allow_underidentified=True,
            profile_nuisance_grid_size=3,
            profile_nuisance_refinements=0,
        ),
    )

    assert result.status is IdentifiabilityDiagnosticStatus.NON_IDENTIFIED
    assert result.jacobian_rank == 1
    assert result.profile_trace_ref is not None
    trace = from_canonical_bytes(store.get_bytes(result.profile_trace_ref.artifact_id))
    assert trace["profile_method"] == "grid_coordinate_minimized_nuisance"
    a_profile = trace["traces"]["a"]
    assert [point["theta_star"]["b"] for point in a_profile] == pytest.approx(
        [1.25, 1.0, 0.75]
    )
    assert [point["distance"] for point in a_profile] == pytest.approx([0.0, 0.0, 0.0])


def test_aggregate_identifiability_condition_warn_threshold_marks_sloppy(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    simulation_ref = _put_minimal_simulation_result(store)

    def evaluator(theta: dict[str, float], seed: int | None) -> dict[str, float]:
        del seed
        return {"mean_y": float(theta["strong"]), "q50_y": 1e-4 * float(theta["weak"])}

    result = identifiability_diagnostic(
        store,
        simulation_result_ref=simulation_ref,
        observed_moment_bundle={"mean_y": 1.0, "q50_y": 1e-4},
        parameter_center={"strong": 1.0, "weak": 1.0},
        summary_evaluator=evaluator,
        config=IdentifiabilityDiagnosticConfig(
            simulation_reps=1,
            bootstrap_reps=0,
            profile_grid_size=0,
            condition_warn_threshold=1e6,
            condition_block_threshold=1e10,
        ),
    )

    assert result.status is IdentifiabilityDiagnosticStatus.SLOPPY
    assert result.condition_number is not None
    assert result.condition_number >= 1e6


def test_aggregate_identifiability_common_random_numbers_are_deterministic(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    simulation_ref = _put_minimal_simulation_result(store)

    def evaluator(theta: dict[str, float], seed: int | None) -> dict[str, float]:
        noise = 0.0 if seed is None else (seed % 3) * 0.01
        return {
            "mean_y": float(theta["mu"]) + noise,
            "q50_y": float(theta["sigma"]) - noise,
        }

    config = IdentifiabilityDiagnosticConfig(
        simulation_reps=4,
        bootstrap_reps=4,
        profile_grid_size=0,
        seed=777,
    )
    kwargs = {
        "simulation_result_ref": simulation_ref,
        "observed_moment_bundle": {"mean_y": 1.0, "q50_y": 2.0},
        "parameter_center": {"mu": 1.0, "sigma": 2.0},
        "summary_evaluator": evaluator,
        "config": config,
    }

    first = identifiability_diagnostic(store, **kwargs)
    second = identifiability_diagnostic(store, **kwargs)

    assert first.fisher_eigenvalues == second.fisher_eigenvalues
    assert first.bootstrap_min_eigen_ci == second.bootstrap_min_eigen_ci
    assert first.bootstrap_rank_stability == second.bootstrap_rank_stability


def test_aggregate_identifiability_blocks_underidentified_summary(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    simulation_ref = _put_minimal_simulation_result(store)

    result = identifiability_diagnostic(
        store,
        simulation_result_ref=simulation_ref,
        observed_moment_bundle={"mean_y": 10.0, "var_y": 2.0},
        parameter_center={"pi": 0.5, "mu_1": 1.0, "mu_2": 2.0},
        config=IdentifiabilityDiagnosticConfig(bootstrap_reps=0, profile_grid_size=0),
    )

    assert result.status is IdentifiabilityDiagnosticStatus.NON_IDENTIFIED
    assert result.effective_dimension == 2
    assert result.blocking_reasons == ("underidentified_summary_vector:2<parameters:3",)
    assert result.diagnostic_ref is not None


def test_aggregate_identifiability_requires_parameter_center(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    simulation_ref = _put_minimal_simulation_result(store)

    with pytest.raises(ValueError, match="parameter_center is required"):
        identifiability_diagnostic(
            store,
            simulation_result_ref=simulation_ref,
            observed_moment_bundle={"mean_y": 1.0, "var_y": 2.0},
            config=IdentifiabilityDiagnosticConfig(bootstrap_reps=0, profile_grid_size=0),
        )
