from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from dataclasses import replace

import numpy as np
import pytest
from _helpers.c7_synthetic_data import (
    N_AGENTS,
    N_CELLS,
    build_c7_synthetic_fixture,
)

import polisyos.scientist.methods.advanced as advanced_module
from polisyos.common.serialization import to_python_data
from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
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
from polisyos.scientist.compute.job_spec import JobKey, JobResult, JobSpec
from polisyos.scientist.compute.runner import (
    MethodBackend,
    MethodRuntimeProviders,
)
from polisyos.scientist.compute.runner import (
    run_job as execute_job,
)
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
    assert pca_result.bundle_ref.manifest_profile_sha256 is None
    assert dynamic_result.bundle_ref.manifest_profile_sha256 is None
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
    method_spec = JobSpec(
        job_kind="method",
        method_fqn="ml.survival.survival_analysis@1.0.0",
        method_version="1.0.0",
    )
    job_result_ref = store.put_json(
        JobResult(
            job_key=JobKey.from_spec(method_spec),
            method_result_ref=method_result_ref,
            method_evidence_ref=method_evidence_ref,
        ),
        PutOptions(
            kind="scientist.compute.job_result",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.compute.JobResult",
                version="0.1.0",
            ),
        ),
        return_selected_profile=True,
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
            job_result_ref,
        )

    monkeypatch.setattr(adapter, "_run_method", _run_method)

    result = adapter.run(fixture.advanced_inputs)

    assert isinstance(fixture.advanced_inputs.survival_contract, dict)
    assert len(observed_input) == 1
    expected = fixture.advanced_inputs.survival_contract
    materialized = observed_input[0]
    np.testing.assert_array_equal(materialized.features, expected["features"])
    np.testing.assert_array_equal(materialized.durations, expected["durations"])
    np.testing.assert_array_equal(materialized.events, expected["events"])
    assert materialized.feature_names == expected.get("feature_names")
    assert materialized.metadata == expected.get("metadata", {})
    assert result.job_result_refs == (job_result_ref,)
    bundle_manifest = store.get_manifest(result.bundle_ref)
    assert any(
        edge.artifact_id == job_result_ref.artifact_id
        and edge.manifest_profile_sha256 == job_result_ref.manifest_profile_sha256
        for edge in bundle_manifest.inputs
    )
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


def test_method_input_snapshot_refuses_transplant_and_missing_profile(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / ".cas_method_input_controls")
    adapter = FactorModelEmbeddingBuilder(store)
    caller_state = {"exog": np.asarray([[1.0, 2.0], [3.0, 4.0]])}
    unrelated_ref = store.put_json(
        [[90, 91], [92, 93]],
        PutOptions(
            kind="scientist.method_input_slot",
            media_type="application/json",
            schema=SchemaInfo(name="candidate.transplanted.input", version="0.1.0"),
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="derived from the executed state"):
        adapter._run_method(
            method_fqn="econometrics.factor.principal_components@1.0.0",
            input_state=caller_state,
            method_params={"n_factors": 1},
            seed=17,
            input_refs={"exog": unrelated_ref},
        )

    json_native_state = {
        "explicit_null": None,
        "metadata": {"source_ids": ["source-a"], "context": {"epoch": 3}},
    }
    assert advanced_module._method_input_values(json_native_state) == json_native_state
    refs = advanced_module._persist_method_input_refs(
        store,
        method_fqn="econometrics.factor.principal_components@1.0.0",
        input_state=json_native_state,
    )
    assert set(refs) == set(json_native_state)
    assert all(ref.manifest_profile_sha256 is not None for ref in refs.values())
    assert {
        slot: load_core_json_artifact(store, ref) for slot, ref in refs.items()
    } == json_native_state
    with pytest.raises(TypeError, match="keys must be non-empty strings"):
        advanced_module._method_input_values({"metadata": {1: "not JSON object-key data"}})
    with pytest.raises(TypeError, match="keys must be non-empty strings"):
        advanced_module._method_input_values({"metadata": {1: "not JSON object-key data"}})
    with pytest.raises(ValueError):
        advanced_module._method_input_values({"unsupported": object()})

    original_put_json = store.put_json

    def _remove_selected_profile(*args, **kwargs):
        ref = original_put_json(*args, **kwargs)
        return ref.model_copy(update={"manifest_profile_sha256": None})

    monkeypatch.setattr(store, "put_json", _remove_selected_profile)
    with pytest.raises(ValueError, match="no selected manifest profile"):
        advanced_module._persist_method_input_refs(
            store,
            method_fqn="econometrics.factor.principal_components@1.0.0",
            input_state=caller_state,
        )


@pytest.mark.skipif(
    importlib.util.find_spec("lifelines") is None,
    reason="lifelines is required for survival C7 tests",
)
def test_run_c7_advanced_suite_persists_all_sidecar_artifacts(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_c7_synthetic_fixture(tmp_path)
    store = FileSystemCAS(tmp_path / ".cas_suite")
    jobs: list[tuple[JobSpec, MethodBackend, JobResult]] = []
    source_states: list[tuple[MethodBackend, str, object, dict, int]] = []
    backend_inputs: list[tuple[str, dict]] = []
    persisted_job_specs: list[JobSpec] = []
    inside_job = False
    original_run_job = execute_job
    original_method_call = advanced_module._AdvancedMethodBase._run_method
    original_backend_run = MethodBackend.run
    original_core_json_load = advanced_module.load_core_json_artifact

    def _capture_core_json_load(store_arg, selector, **kwargs):
        payload = original_core_json_load(store_arg, selector, **kwargs)
        if getattr(selector, "kind", None) == "scientist.compute.job_spec":
            persisted_job_specs.append(JobSpec.model_validate(payload))
        return payload

    def _capture_backend_run(self, *args, **kwargs):
        if inside_job:
            backend_inputs.append((kwargs["method_fqn"], dict(kwargs["input_state"])))
        return original_backend_run(self, *args, **kwargs)

    def _capture_run_job(spec: JobSpec, **kwargs):
        nonlocal inside_job
        assert persisted_job_specs, "run_job received a request without a selected CAS readback"
        assert spec == persisted_job_specs.pop(0)
        assert kwargs.get("method_state") is None
        assert kwargs.get("capture_dispatch_binding") is False
        backend = kwargs.get("backend")
        assert isinstance(backend, MethodBackend)
        inside_job = True
        try:
            result = original_run_job(spec, **kwargs)
        finally:
            inside_job = False
        jobs.append((spec, backend, result))
        return result

    def _capture_source_state(self, **kwargs):
        source_states.append(
            (
                self.backend,
                kwargs["method_fqn"],
                kwargs["input_state"],
                dict(kwargs["method_params"]),
                kwargs["seed"],
            )
        )
        return original_method_call(self, **kwargs)

    monkeypatch.setattr(advanced_module, "load_core_json_artifact", _capture_core_json_load)
    monkeypatch.setattr(advanced_module, "run_job", _capture_run_job)
    monkeypatch.setattr(MethodBackend, "run", _capture_backend_run)
    monkeypatch.setattr(advanced_module._AdvancedMethodBase, "_run_method", _capture_source_state)
    result = run_c7_advanced_suite(
        store, inputs=fixture.advanced_inputs, return_selected_profile=True
    )

    survival_rows = load_parquet_rows(
        _write_cas_artifact(
            store,
            result.survival_hazards.bundle_ref,
            tmp_path / "survival_hazard_bundle_v1.parquet",
        )
    )

    assert len(result.bundle_refs()) == 7
    persisted = [
        result.factor_embeddings,
        result.cell_prototypes,
        result.bilevel_problem,
        result.heckman_correction,
        result.survival_hazards,
        result.sobol_diagnostics,
        result.specification_curve,
    ]
    assert all(artifact.job_result_refs for artifact in persisted)
    assert len(jobs) == len(source_states) == len(backend_inputs) == 8
    assert not persisted_job_specs
    for ref in result.bundle_refs().values():
        assert store.has(ref.artifact_id)
        assert ref.manifest_profile_sha256 is not None
        assert (
            store.get_manifest_by_profile(
                str(ref.artifact_id), ref.manifest_profile_sha256
            ).artifact_id
            == ref.artifact_id
        )
    for artifact in persisted:
        assert artifact.bundle_ref.manifest_profile_sha256 is not None
        bundle_manifest = store.get_manifest_by_profile(
            str(artifact.bundle_ref.artifact_id),
            artifact.bundle_ref.manifest_profile_sha256,
        )
        reader_job_result_refs = []
        for edge in bundle_manifest.inputs:
            child_manifest = store.get_manifest_by_profile(
                str(edge.artifact_id), edge.manifest_profile_sha256
            )
            if child_manifest.kind == advanced_module._METHOD_JOB_RESULT_KIND:
                reader_job_result_refs.append(
                    ArtifactRef(
                        artifact_id=edge.artifact_id,
                        kind=child_manifest.kind,
                        media_type=child_manifest.media_type,
                        manifest_profile_sha256=edge.manifest_profile_sha256,
                    )
                )
        assert tuple(reader_job_result_refs) == artifact.job_result_refs
        expected_edges = [
            (ref.artifact_id, ref.manifest_profile_sha256)
            for ref in (
                *artifact.method_result_refs,
                *artifact.method_evidence_refs,
                *artifact.job_result_refs,
            )
        ]
        assert [
            (edge.artifact_id, edge.manifest_profile_sha256) for edge in bundle_manifest.inputs
        ] == expected_edges
        assert all(profile is not None for _, profile in expected_edges)

    flattened_refs = [
        triple
        for artifact in persisted
        for triple in zip(
            artifact.method_result_refs,
            artifact.method_evidence_refs,
            artifact.job_result_refs,
            strict=True,
        )
    ]
    for (method_result_ref, evidence_ref, job_result_ref), (
        spec,
        backend,
        job_result,
    ), source, observed in zip(flattened_refs, jobs, source_states, backend_inputs, strict=True):
        assert job_result.issues == []
        assert job_result.method_result_ref == method_result_ref
        assert job_result.method_evidence_ref == evidence_ref
        assert job_result_ref.manifest_profile_sha256 is not None
        assert job_result.job_key == JobKey.from_spec(spec)
        stored_job_result = JobResult.model_validate(load_core_json_artifact(store, job_result_ref))
        assert to_python_data(
            stored_job_result.model_dump(mode="python"), sort_keys=True, unsupported="error"
        ) == to_python_data(
            job_result.model_dump(mode="python"), sort_keys=True, unsupported="error"
        )
        assert to_python_data(
            load_core_json_artifact(store, method_result_ref),
            sort_keys=True,
            unsupported="error",
        ) == to_python_data(
            stored_job_result.final_state,
            sort_keys=True,
            unsupported="error",
        )
        assert stored_job_result.job_key == JobKey.from_spec(spec)
        job_result_manifest = store.get_manifest_by_profile(
            str(job_result_ref.artifact_id), job_result_ref.manifest_profile_sha256
        )
        job_spec_edges = [edge for edge in job_result_manifest.inputs if edge.role == "job_spec"]
        assert len(job_spec_edges) == 1
        job_spec_edge = job_spec_edges[0]
        job_spec_manifest = store.get_manifest_by_profile(
            str(job_spec_edge.artifact_id), job_spec_edge.manifest_profile_sha256
        )
        stored_spec_ref = ArtifactRef(
            artifact_id=job_spec_edge.artifact_id,
            kind=job_spec_manifest.kind,
            media_type=job_spec_manifest.media_type,
            manifest_profile_sha256=job_spec_edge.manifest_profile_sha256,
        )
        stored_spec = JobSpec.model_validate(load_core_json_artifact(store, stored_spec_ref))
        assert stored_spec == spec
        assert stored_job_result.job_key == JobKey.from_spec(stored_spec)
        assert {
            (edge.role, str(edge.artifact_id), edge.manifest_profile_sha256)
            for edge in job_result_manifest.inputs
        } == {
            ("job_spec", str(stored_spec_ref.artifact_id), stored_spec_ref.manifest_profile_sha256),
            (
                "method_result",
                str(method_result_ref.artifact_id),
                method_result_ref.manifest_profile_sha256,
            ),
            (
                "method_evidence",
                str(evidence_ref.artifact_id),
                evidence_ref.manifest_profile_sha256,
            ),
        }
        mutated_request = stored_spec.model_copy(update={"seed": stored_spec.seed + 1})
        assert JobKey.from_spec(mutated_request) != stored_job_result.job_key
        assert job_result_ref.manifest_profile_sha256 is not None
        assert method_result_ref.manifest_profile_sha256 is not None
        assert evidence_ref.manifest_profile_sha256 is not None
        method_manifest = store.get_manifest_by_profile(
            str(method_result_ref.artifact_id), method_result_ref.manifest_profile_sha256
        )
        assert {
            (edge.role, str(edge.artifact_id), edge.manifest_profile_sha256)
            for edge in method_manifest.inputs
        } == {
            (f"input:{slot}", str(ref.artifact_id), ref.manifest_profile_sha256)
            for slot, ref in spec.input_refs.items()
        }
        evidence_manifest = store.get_manifest_by_profile(
            str(evidence_ref.artifact_id), evidence_ref.manifest_profile_sha256
        )
        assert [
            (edge.artifact_id, edge.manifest_profile_sha256) for edge in evidence_manifest.inputs
        ] == [(method_result_ref.artifact_id, method_result_ref.manifest_profile_sha256)]
        assert JobKey.from_spec(spec) == job_result.job_key
        assert spec.method_version == spec.method_fqn.rsplit("@", 1)[1]
        assert observed[0] == spec.method_fqn
        source_state = source[2]
        if isinstance(source_state, Mapping):
            raw_source_state = source_state
        else:
            model_dump = getattr(source_state, "model_dump", None)
            raw_source_state = (
                model_dump(
                    mode="python",
                    by_alias=True,
                    exclude_none=False,
                    exclude_unset=False,
                )
                if callable(model_dump)
                else vars(source_state)
            )
        expected_source_values = to_python_data(
            raw_source_state, sort_keys=True, unsupported="error"
        )
        selected_values = {
            slot: load_core_json_artifact(store, ref) for slot, ref in spec.input_refs.items()
        }
        assert selected_values == expected_source_values
        assert observed[1] == selected_values
        assert set(spec.input_refs) == set(expected_source_values)
        assert all(ref.manifest_profile_sha256 is not None for ref in spec.input_refs.values())
        assert spec.seed == source[4]
        assert spec.method_params == to_python_data(source[3], sort_keys=True, unsupported="error")
        backend, method_fqn, source_state, method_params, seed = source
        if method_fqn == "ml.survival.survival_analysis@1.0.0":
            assert source_state.metadata == {
                "event_set_id": "c7_synthetic_firm_events",
                "panel_id": "c7_synthetic_firm_panels",
            }
            assert selected_values["metadata"] == source_state.metadata
            assert load_core_json_artifact(store, spec.input_refs["feature_names"]) == list(
                source_state.feature_names
            )
        direct = backend.run(
            cas_root=store.root,
            method_fqn=method_fqn,
            method_version=None,
            input_state=source_state,
            method_params=method_params,
            seed=seed,
        )
        assert to_python_data(
            direct.final_state, sort_keys=True, unsupported="error"
        ) == to_python_data(job_result.final_state, sort_keys=True, unsupported="error")

    assert survival_rows
    survival_contract = fixture.advanced_inputs.survival_contract
    feature_names = (
        survival_contract.feature_names
        if isinstance(survival_contract, SurvivalData)
        else survival_contract["feature_names"]
    )
    assert set(result.survival_hazards.manifest.contract_payload["coefficients"]) == set(
        feature_names
    )
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
        assert ref.manifest_profile_sha256 is None
