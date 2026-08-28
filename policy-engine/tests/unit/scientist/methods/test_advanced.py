from __future__ import annotations

import importlib.util
from dataclasses import replace

import numpy as np
import pytest
from _helpers.c7_synthetic_data import (
    N_AGENTS,
    N_CELLS,
    build_c7_synthetic_fixture,
)

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.ml.protocols import SurvivalData
from polisyos.foundry.methods.registry import MethodRegistry, registry_scope
from polisyos.ir.observation.bundles import (
    BilevelProblemBundle,
    SobolDiagnosticsBundle,
    SpecificationCurveDiagnosticsBundle,
)
from polisyos.ir.observation.contract_compilers import (
    load_json_bundle,
    load_npz_payload,
    load_parquet_rows,
)
from polisyos.scientist.compute.runner import MethodBackend, MethodRuntimeProviders
from polisyos.scientist.methods.advanced import (
    BilevelOptimizationAdapter,
    CellPrototypeBuilder,
    FactorModelEmbeddingBuilder,
    HeckmanCorrectionAdapter,
    SobolDiagnosticsAdapter,
    SpecificationCurveAdapter,
    SurvivalModelAdapter,
    run_c7_advanced_suite,
)


def _write_cas_artifact(store: FileSystemCAS, ref, path):
    path.write_bytes(store.get_bytes(ref.artifact_id))
    return path


def test_factor_builder_supports_pca_and_dynamic_modes(tmp_path) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_factor")
    pca_result = FactorModelEmbeddingBuilder(store).run(fixture.advanced_inputs)
    dynamic_result = FactorModelEmbeddingBuilder(store).run(
        replace(fixture.advanced_inputs, temporal_embedding_mode="dynamic")
    )

    pca_payload = load_npz_payload(
        _write_cas_artifact(
            store,
            pca_result.bundle_ref,
            tmp_path / "agent_factor_embeddings_v1.npz",
        )
    )
    dynamic_payload = load_npz_payload(
        _write_cas_artifact(
            store,
            dynamic_result.bundle_ref,
            tmp_path / "agent_factor_embeddings_dynamic_v1.npz",
        )
    )

    assert store.has(pca_result.bundle_ref.artifact_id)
    assert store.has(dynamic_result.bundle_ref.artifact_id)
    assert pca_result.method_result_refs
    assert dynamic_result.method_result_refs
    assert pca_payload["embeddings"].shape[0] == N_AGENTS
    assert dynamic_payload["embeddings"].shape[0] == N_AGENTS
    assert np.isfinite(np.asarray(pca_payload["embeddings"], dtype=float)).all()
    assert np.isfinite(np.asarray(dynamic_payload["embeddings"], dtype=float)).all()
    assert pca_payload["factor_loadings"].shape[1] == pca_payload["embeddings"].shape[1]
    assert dynamic_payload["factor_loadings"].shape[1] == dynamic_payload["embeddings"].shape[1]


def test_non_survival_c7_adapters_persist_valid_artifacts(tmp_path) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_non_survival")

    cell_result = CellPrototypeBuilder(store).run(fixture.advanced_inputs)
    bilevel_result = BilevelOptimizationAdapter(store).run(fixture.advanced_inputs)
    heckman_result = HeckmanCorrectionAdapter(store).run(fixture.advanced_inputs)
    sobol_result = SobolDiagnosticsAdapter(store).run(fixture.advanced_inputs)
    spec_result = SpecificationCurveAdapter(store).run(fixture.advanced_inputs)

    cell_payload = load_npz_payload(
        _write_cas_artifact(
            store,
            cell_result.bundle_ref,
            tmp_path / "cell_prototype_embeddings_v1.npz",
        )
    )
    bilevel_bundle = load_json_bundle(
        _write_cas_artifact(
            store,
            bilevel_result.bundle_ref,
            tmp_path / "bilevel_problem_bundle_v1.json",
        ),
        BilevelProblemBundle,
    )
    heckman_rows = load_parquet_rows(
        _write_cas_artifact(
            store,
            heckman_result.bundle_ref,
            tmp_path / "heckman_correction_bundle_v1.parquet",
        )
    )
    sobol_bundle = load_json_bundle(
        _write_cas_artifact(
            store,
            sobol_result.bundle_ref,
            tmp_path / "sobol_diagnostics_bundle_v1.json",
        ),
        SobolDiagnosticsBundle,
    )
    spec_bundle = load_json_bundle(
        _write_cas_artifact(
            store,
            spec_result.bundle_ref,
            tmp_path / "specification_curve_diagnostics_v1.json",
        ),
        SpecificationCurveDiagnosticsBundle,
    )

    assert cell_payload["labels"].shape[0] == N_CELLS
    assert cell_payload["prototype_centers"].ndim == 2
    assert np.isfinite(np.asarray(cell_payload["prototype_centers"], dtype=float)).all()
    assert bilevel_bundle.optimization_target == "optimization.bilevel.bilevel@1.1.0"
    assert bilevel_bundle.ambiguity_mode == "auto"
    assert bilevel_bundle.certificate_mode == "residual_or_bounds"
    assert bilevel_bundle.result_summary["upper_feasible"] is True
    assert bilevel_bundle.result_summary["lower_feasible"] is True
    assert heckman_rows
    assert all(np.isfinite(float(row["corrected_log_output"])) for row in heckman_rows)
    assert len(sobol_bundle.target_names) == len(sobol_bundle.first_order_indices)
    assert all(np.isfinite(value) for row in sobol_bundle.first_order_indices for value in row)
    assert spec_bundle.specification_ids
    assert np.isfinite(np.asarray(spec_bundle.sorted_estimates, dtype=float)).all()
    for artifact in (cell_result, bilevel_result, heckman_result, sobol_result, spec_result):
        assert artifact.method_result_refs
        assert artifact.method_evidence_refs
        assert store.has(artifact.bundle_ref.artifact_id)


def test_c7_adapter_uses_injected_method_registry(tmp_path, monkeypatch) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_registry")
    registry = MethodRegistry()

    def _boom() -> MethodRegistry:
        raise AssertionError("global method registry should not be used")

    monkeypatch.setattr(
        "polisyos.scientist.methods.advanced.MethodRegistry.get_instance",
        _boom,
    )
    monkeypatch.setattr(
        "polisyos.scientist.compute.runner.MethodRegistry.get_instance",
        _boom,
    )

    result = BilevelOptimizationAdapter(
        store,
        MethodBackend(registry_provider=lambda: registry),
        method_registry=registry,
    ).run(fixture.advanced_inputs)

    assert store.has(result.bundle_ref.artifact_id)
    assert result.method_result_refs
    assert result.method_evidence_refs


def test_c7_adapter_loader_skips_private_placeholder_methods(tmp_path) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_registry_private")

    with registry_scope() as registry:
        result = BilevelOptimizationAdapter(
            store,
            MethodBackend(registry_provider=lambda: registry),
            method_registry=registry,
        ).run(fixture.advanced_inputs)

        registered_fqns = {signature.fqn for signature in registry.list_all()}

    assert store.has(result.bundle_ref.artifact_id)
    assert "optimization.bilevel.bilevel@1.1.0" in registered_fqns
    assert ".bilevel@0.0.0" not in registered_fqns


def test_bilevel_c7_bundle_roundtrip_with_new_params(tmp_path) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_bilevel_params")

    result = BilevelOptimizationAdapter(store).run(
        replace(
            fixture.advanced_inputs,
            bilevel_ambiguity_mode="required",
            bilevel_tie_break="optimistic",
            bilevel_delta_near_opt=0.25,
            bilevel_certificate_mode="leader_objective_bounds",
        )
    )

    bundle = load_json_bundle(
        _write_cas_artifact(
            store,
            result.bundle_ref,
            tmp_path / "bilevel_problem_bundle_v1.json",
        ),
        BilevelProblemBundle,
    )

    assert bundle.optimization_target == "optimization.bilevel.bilevel@1.1.0"
    assert bundle.ambiguity_mode == "required"
    assert bundle.tie_break == "optimistic"
    assert bundle.delta_near_opt == pytest.approx(0.25)
    assert bundle.certificate_mode == "leader_objective_bounds"


def test_survival_adapter_materializes_compiled_ir_payload(tmp_path, monkeypatch) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_survival_materialization")
    adapter = SurvivalModelAdapter(store)
    method_result_ref = store.put_bytes(
        b"{}",
        PutOptions(kind="scientist.method_result", media_type="application/json"),
    )
    method_evidence_ref = store.put_bytes(
        b'{"evidence":true}',
        PutOptions(kind="scientist.method_evidence", media_type="application/json"),
    )
    observed_input: list[SurvivalData] = []

    def _run_method(**kwargs):
        input_state = kwargs["input_state"]
        assert isinstance(input_state, SurvivalData)
        observed_input.append(input_state)
        return (
            {
                "result": {
                    "method_name": "survival_analysis",
                    "risk_scores": np.linspace(0.1, 0.9, input_state.features.shape[0]),
                    "concordance_index": 0.75,
                    "coefficients": {},
                    "metadata": {"backend": "test"},
                }
            },
            method_result_ref,
            method_evidence_ref,
        )

    monkeypatch.setattr(adapter, "_run_method", _run_method)

    result = adapter.run(fixture.advanced_inputs)

    assert isinstance(fixture.advanced_inputs.survival_contract, dict)
    assert observed_input
    assert store.has(result.bundle_ref.artifact_id)


def test_survival_adapter_rejects_malformed_compiled_ir_payload(tmp_path) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_survival_materialization_invalid")
    malformed_inputs = replace(
        fixture.advanced_inputs,
        survival_contract={
            "features": [[1.0], [2.0]],
            "durations": [1.0],
            "events": [1, 0],
        },
    )

    with pytest.raises(ValueError, match="invalid payload for method contract"):
        SurvivalModelAdapter(store).run(malformed_inputs)


@pytest.mark.skipif(
    importlib.util.find_spec("lifelines") is None,
    reason="lifelines is required for survival C7 tests",
)
def test_run_c7_advanced_suite_persists_all_sidecar_artifacts(tmp_path) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_suite")

    result = run_c7_advanced_suite(store, inputs=fixture.advanced_inputs)

    survival_rows = load_parquet_rows(
        _write_cas_artifact(
            store,
            result.survival_hazards.bundle_ref,
            tmp_path / "survival_hazard_bundle_v1.parquet",
        )
    )

    assert len(result.bundle_refs()) == 7
    for ref in result.bundle_refs().values():
        assert store.has(ref.artifact_id)
    assert survival_rows
    assert all(np.isfinite(float(row["risk_score"])) for row in survival_rows)
    assert {row["firm_id"] for row in survival_rows}
    assert result.survival_hazards.method_result_refs
    assert result.survival_hazards.method_evidence_refs


@pytest.mark.skipif(
    importlib.util.find_spec("lifelines") is None,
    reason="lifelines is required for survival C7 tests",
)
def test_run_c7_advanced_suite_uses_injected_method_runtime_providers(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_suite_injected")
    registry = MethodRegistry()
    dispatcher = MethodDispatcher()

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("global method singleton lookup should not be used")

    monkeypatch.setattr(
        "polisyos.scientist.methods.advanced.MethodRegistry.get_instance",
        _boom,
    )
    monkeypatch.setattr(
        "polisyos.scientist.compute.runner.MethodRegistry.get_instance",
        _boom,
    )
    monkeypatch.setattr(
        "polisyos.scientist.compute.runner.MethodDispatcher.get_instance",
        _boom,
    )

    providers = MethodRuntimeProviders(
        registry_provider=lambda: registry,
        dispatcher_provider=lambda: dispatcher,
    )
    result = run_c7_advanced_suite(
        store,
        inputs=fixture.advanced_inputs,
        method_runtime_providers=providers,
    )

    assert len(result.bundle_refs()) == 7
    for ref in result.bundle_refs().values():
        assert store.has(ref.artifact_id)
