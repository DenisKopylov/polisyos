"""Source-bound candidate posterior consumption through the existing owners."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_manifest_profile_sha256,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.manifest import InputRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.calibration import uncertainty_adapter
from polisyos.foundry.calibration.uncertainty_adapter import (
    load_persisted_posterior_summary,
    persist_posterior_summary_from_method_evidence,
    propagate_selected_posterior_summary,
)
from polisyos.foundry.methods import MethodRegistry
from polisyos.foundry.uncertainty import MonteCarloPropagator
from polisyos.ir.analytics.posterior_summary import PosteriorPointRole, PosteriorSummaryRef
from tests.unit.scientist.compute.test_runner_posterior_summary import _run_native_fixture


@pytest.fixture(autouse=True)
def _reset_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _job(tmp_path: Path, *, offset: float = 0.0):
    values = np.asarray([[offset, offset + 1.0, offset + 2.0, offset + 3.0]], dtype="<f8")
    result = _run_native_fixture(tmp_path, samples={"theta": values}, credible_mass=0.9)
    assert result.issues == []
    assert result.method_evidence_ref is not None
    assert result.method_evidence_ref.manifest_profile_sha256 is not None
    summary_ref = result.posterior_summary_refs[PosteriorPointRole.POSTERIOR_MEAN]
    assert summary_ref.manifest_profile_sha256 is not None
    return summary_ref, result.method_evidence_ref


def _different_evidence_view(store: FileSystemCAS, evidence: ArtifactRef) -> ArtifactRef:
    manifest = store.get_manifest(evidence)
    payload = from_canonical_bytes(store.get_bytes(evidence))
    sibling = store.put_json(
        payload,
        PutOptions(
            kind="scientist.method_evidence",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.MethodExecutionEvidence", version="0.1.0"),
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, max_depth=139),
        return_selected_profile=True,
    )
    assert sibling.artifact_id == evidence.artifact_id
    assert sibling.manifest_profile_sha256 is not None
    assert sibling.manifest_profile_sha256 != evidence.manifest_profile_sha256
    return sibling


def _consume(store, summary_ref, evidence_ref, calls, *, role=PosteriorPointRole.POSTERIOR_MEAN):
    def evaluate(*, theta: float) -> dict[str, float]:
        calls.append(theta)
        return {"value": theta}

    return propagate_selected_posterior_summary(
        store,
        summary_ref,
        expected_method_evidence_ref=evidence_ref,
        simulation_fn=evaluate,
        nominal_params={},
        parameter_names=("theta",),
        output_metric_ids=("value",),
        point_role=role,
    )


def test_selected_reader_recomputes_source_mass_and_evidence_after_caller_mutation(
    tmp_path: Path,
) -> None:
    summary_ref, evidence_ref = _job(tmp_path)
    store = FileSystemCAS(tmp_path)
    summary = load_persisted_posterior_summary(store, summary_ref)
    sibling = _different_evidence_view(store, evidence_ref)
    assert summary.source_method_evidence_ref is not None
    summary.source_method_evidence_ref.manifest_profile_sha256 = sibling.manifest_profile_sha256
    forged = summary.model_copy(update={"credible_mass": 0.8})
    assert forged.parameters["theta"].equal_tail_interval == (0.0, 3.0)

    # This documents the bounded DTO-only behavior; the altered declarations
    # pass its self-recomputation because these two masses share endpoints.
    direct = MonteCarloPropagator().propagate_posterior_summary(
        forged,
        simulation_fn=lambda theta: {"value": theta},
        nominal_params={},
        parameter_names=("theta",),
        output_metric_ids=("value",),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    assert direct.output_summaries["value"].credible_mass == 0.8
    assert direct.source_method_evidence_ref is not None
    assert (
        direct.source_method_evidence_ref.manifest_profile_sha256 == sibling.manifest_profile_sha256
    )

    calls: list[float] = []
    checked = _consume(store, summary_ref, evidence_ref, calls)
    output = checked.output_summaries["value"]
    assert output.credible_mass == 0.9
    assert output.equal_tail_interval == (0.0, 3.0)
    assert output.selected_point_value == 1.5
    assert output.draw_values == (0.0, 1.0, 2.0, 3.0)
    assert calls == [1.5, 0.0, 1.0, 2.0, 3.0]
    assert checked.source_method_evidence_ref is not None
    assert artifact_ref_identity_key(
        ArtifactRef.model_validate(checked.source_method_evidence_ref.model_dump(mode="python"))
    ) == artifact_ref_identity_key(evidence_ref)
    assert checked.gate_eligible is False
    assert checked.unit_binding_status == "not_established"


def test_selected_candidate_preserves_asymmetric_two_coordinate_joint_law(tmp_path: Path) -> None:
    theta = np.asarray([[0.0] * 99 + [100.0]], dtype="<f8")
    index = np.asarray([list(range(100))], dtype="<f8")
    job = _run_native_fixture(tmp_path, samples={"theta": theta, "index": index}, credible_mass=0.9)
    assert job.issues == [] and job.method_evidence_ref is not None
    summary_ref = job.posterior_summary_refs[PosteriorPointRole.POSTERIOR_MEAN]
    calls: list[tuple[float, float]] = []

    def evaluate(*, theta: float, index: float) -> dict[str, float]:
        calls.append((theta, index))
        return {"theta": theta, "joint": theta + index}

    result = propagate_selected_posterior_summary(
        FileSystemCAS(tmp_path),
        summary_ref,
        expected_method_evidence_ref=job.method_evidence_ref,
        simulation_fn=evaluate,
        nominal_params={},
        parameter_names=("theta", "index"),
        output_metric_ids=("theta", "joint"),
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    # Independent empirical values for 99 zeros and one 100: mean 1 lies
    # outside the 90% inverse-CDF interval [0,0]. Pairing must survive.
    expected_rows = (*((0.0, float(i)) for i in range(99)), (100.0, 99.0))
    assert result.selected_input_point == (1.0, 49.5)
    assert result.joint_input_matrix.rows == expected_rows
    assert calls == [(1.0, 49.5), *expected_rows]
    assert result.output_summaries["theta"].posterior_mean == 1.0
    assert result.output_summaries["theta"].equal_tail_interval == (0.0, 0.0)
    assert result.output_summaries["joint"].draw_values == (*(float(i) for i in range(99)), 199.0)
    assert result.output_summaries["joint"].posterior_mean == 50.5
    assert result.output_summaries["joint"].equal_tail_interval == (4.0, 94.0)
    assert result.gate_eligible is False


def test_selected_route_supports_real_cas_with_mapping_manifests(tmp_path: Path) -> None:
    summary_ref, evidence_ref = _job(tmp_path)
    underlying = FileSystemCAS(tmp_path)
    mapping_reads: list[tuple[str, str, str, str | None]] = []

    class MappingView:
        def __getattr__(self, name: str) -> Any:
            return getattr(underlying, name)

        def get_manifest(self, selector):
            if isinstance(selector, ArtifactRef):
                mapping_reads.append(artifact_ref_identity_key(selector))
            else:
                mapping_reads.append(("artifact_id_only", str(selector), "", None))
            return underlying.get_manifest(selector).model_dump(
                mode="json", by_alias=True, exclude_none=True
            )

    calls: list[float] = []
    output = _consume(MappingView(), summary_ref, evidence_ref, calls)
    assert artifact_ref_identity_key(summary_ref) in mapping_reads
    assert artifact_ref_identity_key(evidence_ref) in mapping_reads
    assert output.output_summaries["value"].credible_mass == 0.9
    assert calls == [1.5, 0.0, 1.0, 2.0, 3.0]


def test_selected_summary_and_evidence_full_refs_work_without_optional_profile_only_lookup(
    tmp_path: Path,
) -> None:
    _summary_ref, evidence_ref = _job(tmp_path)
    actual = FileSystemCAS(tmp_path)
    selected_evidence = _different_evidence_view(actual, evidence_ref)
    assert selected_evidence.manifest_profile_sha256 != artifact_manifest_profile_sha256(
        actual.get_manifest(selected_evidence.artifact_id)
    )

    class FullRefOnlyView:
        def __getattr__(self, name: str) -> Any:
            if name == "get_manifest_by_profile":
                raise AttributeError(name)
            return getattr(actual, name)

    facade = FullRefOnlyView()
    assert not hasattr(facade, "get_manifest_by_profile")
    summary_ref = persist_posterior_summary_from_method_evidence(
        facade, selected_evidence, point_role=PosteriorPointRole.POSTERIOR_MEAN
    )
    selected_summary_manifest = actual.get_manifest(
        ArtifactRef.model_validate(summary_ref.model_dump(mode="python"))
    )
    assert summary_ref.manifest_profile_sha256 is not None
    assert len(selected_summary_manifest.inputs) == 1
    assert selected_summary_manifest.inputs[0].manifest_profile_sha256 == (
        selected_evidence.manifest_profile_sha256
    )

    # Producer metadata is a test-only manifest-profile dimension. Keep the
    # producer-owned CAN.2 profile, summary bytes, and selected evidence edge.
    payload = from_canonical_bytes(actual.get_bytes(summary_ref.artifact_id))
    synthetic_producer = ProducerInfo(
        component="tests.synthetic_posterior_summary_view", version="1.0"
    )
    alternate = actual.put_json(
        payload,
        PutOptions(
            kind="ir.posterior_summary",
            media_type="application/json",
            schema=SchemaInfo(name="ir.PosteriorSummaryV11", version="1.1"),
            producer=synthetic_producer,
            inputs=selected_summary_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    alternate_ref = PosteriorSummaryRef.model_validate(alternate.model_dump(mode="python"))
    assert alternate_ref.artifact_id == summary_ref.artifact_id
    assert alternate_ref.manifest_profile_sha256 is not None
    assert alternate_ref.manifest_profile_sha256 != summary_ref.manifest_profile_sha256
    assert alternate_ref.manifest_profile_sha256 != artifact_manifest_profile_sha256(
        actual.get_manifest(summary_ref.artifact_id)
    )
    alternate_manifest = actual.get_manifest(
        ArtifactRef.model_validate(alternate_ref.model_dump(mode="python"))
    )
    assert alternate_manifest.producer == synthetic_producer
    assert alternate_manifest.canon == selected_summary_manifest.canon
    assert alternate_manifest.inputs == selected_summary_manifest.inputs
    calls: list[float] = []
    result = _consume(facade, alternate_ref, selected_evidence, calls)
    assert result.output_summaries["value"].credible_mass == 0.9
    assert calls == [1.5, 0.0, 1.0, 2.0, 3.0]


def test_profileless_nested_result_is_legacy_readable_but_selected_route_refuses(
    tmp_path: Path,
) -> None:
    _summary_ref, evidence_ref = _job(tmp_path)
    store = FileSystemCAS(tmp_path)
    evidence = from_canonical_bytes(store.get_bytes(evidence_ref))
    result_ref = dict(evidence["method_result_ref"])
    assert result_ref.pop("manifest_profile_sha256")
    evidence["method_result_ref"] = result_ref
    legacy_evidence = store.put_json(
        evidence,
        PutOptions(
            kind="scientist.method_evidence",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.MethodExecutionEvidence", version="0.1.0"),
            inputs=[InputRef(artifact_id=result_ref["artifact_id"], role="method_result")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    summary_ref = persist_posterior_summary_from_method_evidence(
        store, legacy_evidence, point_role=PosteriorPointRole.POSTERIOR_MEAN
    )
    # Existing legacy reader keeps its old default-result behavior. The new
    # selected route requires the actual nested result profile instead.
    assert load_persisted_posterior_summary(store, summary_ref).credible_mass == 0.9
    calls: list[float] = []
    with pytest.raises(ValueError, match="requires an exact method-result view"):
        _consume(store, summary_ref, legacy_evidence, calls)
    assert calls == []


def test_valid_same_bytes_sibling_profile_is_not_the_held_job_view(tmp_path: Path) -> None:
    _summary_ref, evidence_ref = _job(tmp_path)
    store = FileSystemCAS(tmp_path)
    sibling = _different_evidence_view(store, evidence_ref)
    sibling_summary_ref = persist_posterior_summary_from_method_evidence(
        store,
        sibling,
        point_role=PosteriorPointRole.POSTERIOR_MEAN,
    )
    # The other selected route is internally valid; its disagreement is with
    # the independently held method-job evidence view, not bad CAS bytes.
    assert load_persisted_posterior_summary(store, sibling_summary_ref).credible_mass == 0.9
    calls: list[float] = []
    with pytest.raises(ValueError, match="held method-evidence view"):
        _consume(store, sibling_summary_ref, evidence_ref, calls)
    assert calls == []


def test_same_summary_bytes_with_foreign_selected_edge_are_refused(tmp_path: Path) -> None:
    summary_ref, evidence_ref = _job(tmp_path)
    store = FileSystemCAS(tmp_path)
    sibling = _different_evidence_view(store, evidence_ref)
    payload = from_canonical_bytes(store.get_bytes(summary_ref.artifact_id))
    foreign_view = store.put_json(
        payload,
        PutOptions(
            kind="ir.posterior_summary",
            media_type="application/json",
            schema=SchemaInfo(name="ir.PosteriorSummaryV11", version="1.1"),
            inputs=[
                InputRef(
                    artifact_id=sibling.artifact_id,
                    role="method_evidence",
                    manifest_profile_sha256=sibling.manifest_profile_sha256,
                )
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    foreign_ref = PosteriorSummaryRef.model_validate(foreign_view.model_dump(mode="python"))
    assert foreign_ref.artifact_id == summary_ref.artifact_id
    assert foreign_ref.manifest_profile_sha256 != summary_ref.manifest_profile_sha256
    assert load_persisted_posterior_summary(store, summary_ref).credible_mass == 0.9
    calls: list[float] = []
    with pytest.raises(ValueError, match="does not bind the selected method-evidence view"):
        _consume(store, foreign_ref, evidence_ref, calls)
    assert calls == []


def test_valid_other_job_is_not_the_held_job_view(tmp_path: Path) -> None:
    _first_summary, first_evidence = _job(tmp_path)
    second_summary, second_evidence = _job(tmp_path, offset=10.0)
    store = FileSystemCAS(tmp_path)
    assert artifact_ref_identity_key(first_evidence) != artifact_ref_identity_key(second_evidence)
    assert load_persisted_posterior_summary(store, second_summary).credible_mass == 0.9
    calls: list[float] = []
    with pytest.raises(ValueError, match="held method-evidence view"):
        _consume(store, second_summary, first_evidence, calls)
    assert calls == []


@pytest.mark.parametrize("case", ["summary_profile", "evidence_profile", "evidence_kind", "role"])
def test_invalid_selected_context_refuses_before_evaluation(tmp_path: Path, case: str) -> None:
    summary_ref, evidence_ref = _job(tmp_path)
    role = PosteriorPointRole.POSTERIOR_MEAN
    if case == "summary_profile":
        summary_ref = summary_ref.model_copy(update={"manifest_profile_sha256": None})
    elif case == "evidence_profile":
        evidence_ref = evidence_ref.model_copy(update={"manifest_profile_sha256": None})
    elif case == "evidence_kind":
        evidence_ref = evidence_ref.model_copy(update={"kind": "scientist.method_result"})
    else:
        role = PosteriorPointRole.POSTERIOR_MEDIAN
    calls: list[float] = []
    with pytest.raises(ValueError):
        _consume(FileSystemCAS(tmp_path), summary_ref, evidence_ref, calls, role=role)
    assert calls == []


def test_mutable_input_ref_changes_do_not_change_captured_selected_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    summary_ref, evidence_ref = _job(tmp_path)
    original_profile = evidence_ref.manifest_profile_sha256
    original_summary_profile = summary_ref.manifest_profile_sha256
    real_reader = uncertainty_adapter.load_persisted_posterior_summary
    observations: list[str | None] = []

    def reader_then_mutate(store, ref, **kwargs):
        observations.append(ref.manifest_profile_sha256)
        summary_ref.manifest_profile_sha256 = "sha256:" + "0" * 64
        evidence_ref.manifest_profile_sha256 = "sha256:" + "1" * 64
        # This semantic assertion fires before an invalid-profile CAS lookup if
        # the implementation accidentally aliases the caller's mutable ref.
        assert ref.manifest_profile_sha256 == original_summary_profile
        assert kwargs["require_selected_result"] is True
        return real_reader(store, ref, **kwargs)

    monkeypatch.setattr(uncertainty_adapter, "load_persisted_posterior_summary", reader_then_mutate)
    calls: list[float] = []
    output = _consume(FileSystemCAS(tmp_path), summary_ref, evidence_ref, calls)
    assert observations and observations[0] not in {None, "sha256:" + "0" * 64}
    assert output.source_method_evidence_ref is not None
    assert output.source_method_evidence_ref.manifest_profile_sha256 == original_profile
    assert calls == [1.5, 0.0, 1.0, 2.0, 3.0]


def test_unavailable_evidence_cannot_be_bypassed_by_intact_summary(tmp_path: Path) -> None:
    summary_ref, evidence_ref = _job(tmp_path)
    blocked_id = str(evidence_ref.artifact_id)

    class EvidenceMissingStore(FileSystemCAS):
        def get_bytes(self, artifact_id: Any) -> bytes:
            requested = getattr(artifact_id, "artifact_id", artifact_id)
            if str(requested) == blocked_id:
                raise FileNotFoundError("selected method-evidence bytes are unavailable")
            return super().get_bytes(artifact_id)

    # All other artifact bytes and manifests remain available in the real CAS.
    store = EvidenceMissingStore(tmp_path)
    assert store.get_bytes(summary_ref.artifact_id)
    calls: list[float] = []
    with pytest.raises(FileNotFoundError, match="selected method-evidence bytes are unavailable"):
        _consume(store, summary_ref, evidence_ref, calls)
    assert calls == []
