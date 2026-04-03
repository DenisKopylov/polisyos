from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
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
from polisyos.scientist.compute.advanced_methods import (
    BilevelOptimizationAdapter,
    CellPrototypeBuilder,
    FactorModelEmbeddingBuilder,
    HeckmanCorrectionAdapter,
    SobolDiagnosticsAdapter,
    SpecificationCurveAdapter,
    run_c7_advanced_suite,
)
from fixtures.c7_synthetic_data import (
    N_AGENTS,
    N_CELLS,
    build_c7_synthetic_fixture,
)


def _write_cas_artifact(store: FileSystemCAS, ref, path: Path) -> Path:
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
        _write_cas_artifact(store, pca_result.bundle_ref, tmp_path / "agent_factor_embeddings_v1.npz")
    )
    dynamic_payload = load_npz_payload(
        _write_cas_artifact(store, dynamic_result.bundle_ref, tmp_path / "agent_factor_embeddings_dynamic_v1.npz")
    )

    assert store.has(pca_result.bundle_ref.artifact_id)
    assert store.has(dynamic_result.bundle_ref.artifact_id)
    assert pca_result.method_result_refs and dynamic_result.method_result_refs
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
        _write_cas_artifact(store, cell_result.bundle_ref, tmp_path / "cell_prototype_embeddings_v1.npz")
    )
    bilevel_bundle = load_json_bundle(
        _write_cas_artifact(store, bilevel_result.bundle_ref, tmp_path / "bilevel_problem_bundle_v1.json"),
        BilevelProblemBundle,
    )
    heckman_rows = load_parquet_rows(
        _write_cas_artifact(store, heckman_result.bundle_ref, tmp_path / "heckman_correction_bundle_v1.parquet")
    )
    sobol_bundle = load_json_bundle(
        _write_cas_artifact(store, sobol_result.bundle_ref, tmp_path / "sobol_diagnostics_bundle_v1.json"),
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


@pytest.mark.skipif(importlib.util.find_spec("lifelines") is None, reason="lifelines is required for survival C7 tests")
def test_run_c7_advanced_suite_persists_all_sidecar_artifacts(tmp_path) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_suite")

    result = run_c7_advanced_suite(store, inputs=fixture.advanced_inputs)

    survival_rows = load_parquet_rows(
        _write_cas_artifact(store, result.survival_hazards.bundle_ref, tmp_path / "survival_hazard_bundle_v1.parquet")
    )

    assert len(result.bundle_refs()) == 7
    for ref in result.bundle_refs().values():
        assert store.has(ref.artifact_id)
    assert survival_rows
    assert all(np.isfinite(float(row["risk_score"])) for row in survival_rows)
    assert {row["firm_id"] for row in survival_rows}
    assert result.survival_hazards.method_result_refs
    assert result.survival_hazards.method_evidence_refs
