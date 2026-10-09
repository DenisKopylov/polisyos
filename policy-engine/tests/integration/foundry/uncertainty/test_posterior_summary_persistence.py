from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.calibration.uncertainty_adapter import (
    load_persisted_posterior_summary,
    persist_posterior_summary_from_method_evidence,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.bayesian import ensure_bayesian_methods_registered
from polisyos.foundry.methods.ml import TabularData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.posterior_summary import PosteriorPointRole, PosteriorSummaryRef
from polisyos.ir.registry.refs import UncertaintyEnvelopeRef
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import MethodRuntimeProviders, run_job


def _pin_numeric_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "BLIS_NUM_THREADS",
    ):
        monkeypatch.setenv(name, "1")


def test_native_bayesian_method_evidence_persists_candidate_summary(tmp_path, monkeypatch) -> None:
    _pin_numeric_threads(monkeypatch)
    registry = MethodRegistry()
    ensure_bayesian_methods_registered(registry)
    dispatcher = MethodDispatcher()
    providers = MethodRuntimeProviders(
        registry_provider=lambda: registry,
        dispatcher_provider=lambda: dispatcher,
    )
    method = registry.get("bayesian.sampling.hmc@1.0.0")
    state = TabularData(
        features=np.asarray([[-1.0], [0.0], [1.0], [2.0]], dtype=np.float64),
        target=np.asarray([-1.1, 0.2, 1.0, 1.8], dtype=np.float64),
        feature_names=["x"],
    )
    result = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=method.signature.fqn,
            method_params={
                "runtime_backend": "numpy",
                "num_warmup": 32,
                "num_samples": 32,
                "num_chains": 1,
                "step_size": 0.02,
                "n_leapfrog": 4,
            },
            seed=11,
        ),
        cas_root=tmp_path,
        method_state=state,
        store_factory=lambda path: FileSystemCAS(path),
        method_runtime_providers=providers,
    )

    assert result.issues == []
    assert result.method_result_ref is not None
    assert result.method_evidence_ref is not None
    assert result.method_evidence_ref.kind == "scientist.method_evidence"
    assert set(result.posterior_summary_refs) == {
        PosteriorPointRole.POSTERIOR_MEAN,
        PosteriorPointRole.POSTERIOR_MEDIAN,
    }

    producer_store = FileSystemCAS(tmp_path)
    evidence_payload = from_canonical_bytes(
        producer_store.get_bytes(result.method_evidence_ref.artifact_id)
    )
    producer_evidence_manifest = producer_store.get_manifest(result.method_evidence_ref)
    assert [edge.role for edge in producer_evidence_manifest.inputs] == ["method_result"]
    selected_evidence_ref = producer_store.put_json(
        evidence_payload,
        PutOptions(
            kind="scientist.method_evidence",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.MethodExecutionEvidence", version="0.1.0"),
            inputs=producer_evidence_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, max_depth=129),
    )
    assert str(selected_evidence_ref.artifact_id) == str(result.method_evidence_ref.artifact_id)
    assert selected_evidence_ref.manifest_profile_sha256 is not None
    assert (
        producer_store.get_manifest(selected_evidence_ref).inputs
        == producer_evidence_manifest.inputs
    )

    summary_ref = persist_posterior_summary_from_method_evidence(
        producer_store,
        selected_evidence_ref,
        credible_mass=0.9,
        point_role=PosteriorPointRole.POSTERIOR_MEDIAN,
    )
    fresh_store = FileSystemCAS(tmp_path)
    summary = load_persisted_posterior_summary(fresh_store, summary_ref)
    job_summary_refs = result.posterior_summary_refs
    job_summary = load_persisted_posterior_summary(
        fresh_store,
        job_summary_refs[PosteriorPointRole.POSTERIOR_MEDIAN],
    )
    assert job_summary.point_role is PosteriorPointRole.POSTERIOR_MEDIAN
    assert job_summary.gate_eligible is False
    assert job_summary.unit_binding_status == "not_established"
    assert job_summary.source_method_evidence_ref is not None
    assert str(job_summary.source_method_evidence_ref.artifact_id) == str(
        result.method_evidence_ref.artifact_id
    )
    assert (
        job_summary.source_method_evidence_ref.manifest_profile_sha256
        == result.method_evidence_ref.manifest_profile_sha256
    )

    assert summary.point_role is PosteriorPointRole.POSTERIOR_MEDIAN
    assert summary.chain_count == 1
    assert summary.draws_per_chain == 32
    assert summary.gate_eligible is False
    assert summary.unit_binding_status == "not_established"
    assert summary.source_method_evidence_ref is not None
    assert str(summary.source_method_evidence_ref.artifact_id) == str(
        selected_evidence_ref.artifact_id
    )
    assert (
        summary.source_method_evidence_ref.manifest_profile_sha256
        == selected_evidence_ref.manifest_profile_sha256
    )
    assert summary.source_draws_payload["schema"] == "foundry.bayesian.draws.v1"
    assert summary.source_draws_hash.startswith("sha256:")
    assert "intercept" in summary.parameters
    assert (
        summary.parameters["intercept"].selected_point
        == summary.parameters["intercept"].posterior_median
    )

    summary_manifest = fresh_store.get_manifest(summary_ref.artifact_id)
    assert len(summary_manifest.inputs) == 1
    assert summary_manifest.inputs[0].role == "method_evidence"
    assert str(summary_manifest.inputs[0].artifact_id) == str(selected_evidence_ref.artifact_id)
    assert (
        summary_manifest.inputs[0].manifest_profile_sha256
        == selected_evidence_ref.manifest_profile_sha256
    )

    # Keep a valid default summary sidecar, then write a sibling selected view
    # whose evidence edge names another profile for the same evidence blob.
    alternate_evidence_ref = producer_store.put_json(
        evidence_payload,
        PutOptions(
            kind="scientist.method_evidence",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.MethodExecutionEvidence",
                version="0.1.0",
            ),
            inputs=producer_evidence_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, max_depth=130),
    )
    assert alternate_evidence_ref.artifact_id == selected_evidence_ref.artifact_id
    assert alternate_evidence_ref.manifest_profile_sha256 is not None
    assert (
        alternate_evidence_ref.manifest_profile_sha256
        != selected_evidence_ref.manifest_profile_sha256
    )
    selected_summary_view = fresh_store.put_json(
        from_canonical_bytes(fresh_store.get_bytes(summary_ref.artifact_id)),
        PutOptions(
            kind="ir.posterior_summary",
            media_type="application/json",
            schema=SchemaInfo(name="ir.PosteriorSummaryV11", version="1.1"),
            inputs=[
                InputRef(
                    artifact_id=alternate_evidence_ref.artifact_id,
                    role="method_evidence",
                    manifest_profile_sha256=alternate_evidence_ref.manifest_profile_sha256,
                )
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selected_summary_ref = PosteriorSummaryRef.model_validate(
        selected_summary_view.model_dump(mode="python")
    )
    assert selected_summary_ref.artifact_id == summary_ref.artifact_id
    assert selected_summary_ref.manifest_profile_sha256 is not None
    assert (
        fresh_store.get_manifest_by_profile(
            selected_summary_ref.artifact_id,
            selected_summary_ref.manifest_profile_sha256,
        )
        .inputs[0]
        .manifest_profile_sha256
        == alternate_evidence_ref.manifest_profile_sha256
    )
    assert load_persisted_posterior_summary(fresh_store, summary_ref) == summary
    with pytest.raises(ValueError, match="does not bind the selected method-evidence view"):
        load_persisted_posterior_summary(fresh_store, selected_summary_ref)

    evaluator_calls: list[tuple[float, float]] = []

    def actual_predictive_evaluator(*, intercept: float, sigma: float) -> dict[str, float]:
        evaluator_calls.append((intercept, sigma))
        return {"linear_predictive_location": intercept + sigma}

    selected_parameters = ("intercept", "sigma")
    expected_joint_rows = job_summary.joint_row_values(selected_parameters)
    pushforward = MonteCarloPropagator().propagate_posterior_summary(
        job_summary,
        simulation_fn=actual_predictive_evaluator,
        nominal_params={},
        parameter_names=selected_parameters,
        output_metric_ids=("linear_predictive_location",),
        point_role=PosteriorPointRole.POSTERIOR_MEDIAN,
    )
    metric = pushforward.output_summaries["linear_predictive_location"]

    assert pushforward.source_draws_ref == job_summary.source_draws_ref
    assert pushforward.source_draws_hash == job_summary.source_draws_hash
    assert pushforward.source_method_evidence_ref == job_summary.source_method_evidence_ref
    assert pushforward.point_role is PosteriorPointRole.POSTERIOR_MEDIAN
    assert pushforward.joint_input_matrix.rows == expected_joint_rows
    assert pushforward.joint_input_matrix.content_sha256.startswith("sha256:")
    assert len(evaluator_calls) == len(expected_joint_rows) + 1
    assert evaluator_calls[0] == tuple(
        job_summary.parameters[name].selected_point for name in selected_parameters
    )
    assert tuple(evaluator_calls[1:]) == expected_joint_rows
    assert metric.draw_values == tuple(row[0] + row[1] for row in expected_joint_rows)
    assert metric.selected_point_value == (
        job_summary.parameters["intercept"].selected_point
        + job_summary.parameters["sigma"].selected_point
    )
    assert metric.successful_draw_count == len(expected_joint_rows)
    assert pushforward.gate_eligible is False
    assert pushforward.unit_binding_status == "not_established"

    with pytest.raises(ValidationError):
        UncertaintyEnvelopeRef.model_validate(summary_ref.model_dump(mode="python"))
