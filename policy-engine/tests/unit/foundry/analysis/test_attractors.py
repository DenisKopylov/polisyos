from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.canonical_profile import artifact_ref_for_manifest
from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.foundry import (
    AttractorAnalysisResult,
    AttractorAnalysisResultRef,
    AttractorStateProjection,
    BasinMap,
    BasinMapRef,
    ContinuationBranch,
    ContinuationBranchRef,
    FeedbackFixedPointCandidate,
    FeedbackSolveResult,
    FeedbackStateSnapshot,
)
from polisyos.foundry.analysis.attractors import (
    build_attractor_analysis_result,
    build_attractor_ensemble_analysis_result,
    build_feedback_attractor_analysis_result,
    classify_terminal_regime,
    largest_lyapunov_exponent,
    load_attractor_analysis_result,
    load_basin_map,
    load_continuation_branch,
    persist_attractor_analysis_result,
    persist_basin_map,
    persist_continuation_branch,
)


def test_classify_terminal_regime_detects_fixed_point() -> None:
    trajectory = np.ones((16, 2), dtype=float)

    regime = classify_terminal_regime(trajectory, tolerance=1.0e-8, rtol=0.0)

    assert regime.kind == "fixed_point"
    assert regime.existence_status == "numerically_confirmed"
    assert regime.equilibrium == (1.0, 1.0)


def test_classify_terminal_regime_detects_limit_cycle() -> None:
    trajectory = np.asarray([[0.0], [1.0]] * 24, dtype=float)

    regime = classify_terminal_regime(
        trajectory,
        tolerance=1.0e-8,
        rtol=0.0,
        window=24,
        max_period=6,
    )

    assert regime.kind == "limit_cycle"
    assert regime.period == 2


def test_largest_lyapunov_exponent_detects_logistic_chaos() -> None:
    def step(x: np.ndarray) -> np.ndarray:
        return np.asarray([4.0 * x[0] * (1.0 - x[0])], dtype=float)

    def jacobian(x: np.ndarray) -> np.ndarray:
        return np.asarray([[4.0 - 8.0 * x[0]]], dtype=float)

    exponent = largest_lyapunov_exponent(
        step,
        np.asarray([0.12345], dtype=float),
        n_steps=500,
        renorm_every=1,
        jacobian_map=jacobian,
    )

    assert exponent > 0.3


def test_attractor_analysis_result_roundtrips_through_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    trajectory = np.ones((8, 2), dtype=float)
    result = build_attractor_analysis_result(
        trajectory,
        ["income", "wealth"],
        analysis_id="analysis_fixed",
        tolerance=1.0e-8,
        rtol=0.0,
    )

    ref = persist_attractor_analysis_result(store, result)
    loaded = load_attractor_analysis_result(store, ref)

    assert loaded.analysis_id == "analysis_fixed"
    assert loaded.kind == "foundry.attractor_analysis_result"
    assert loaded.state_projection.variables == ["income", "wealth"]
    assert loaded.attractors[0].kind == "fixed_point"
    assert loaded.attractors[0].state_representation.equilibrium == {
        "income": 1.0,
        "wealth": 1.0,
    }


def test_multi_start_ensemble_builds_basin_map() -> None:
    fixed_a = np.zeros((12, 1), dtype=float)
    fixed_b = np.ones((12, 1), dtype=float)

    result, basin_map = build_attractor_ensemble_analysis_result(
        [fixed_a, fixed_b, fixed_b],
        ["stock"],
        initial_states=[{"stock": 0.0}, {"stock": 0.5}, {"stock": 0.8}],
        seeds=[1, 2, 3],
        tolerance=1.0e-8,
        rtol=0.0,
    )

    assert len(result.attractors) == 2
    assert basin_map.analysis_id == result.analysis_id
    assert basin_map.basin_measure_estimates == {"A1": 1 / 3, "A2": 2 / 3}
    assert [sample.attractor_id for sample in basin_map.samples] == ["A1", "A2", "A2"]


def test_feedback_solve_lifts_to_multiple_fixed_point_attractors() -> None:
    state = FeedbackStateSnapshot(
        variable_ids=["tax_rate"],
        values=[0.5],
        scales=[1.0],
        lower_bounds=[0.0],
        upper_bounds=[1.0],
        weights=[1.0],
    )
    alternative = FeedbackFixedPointCandidate(
        state=state.model_copy(update={"values": [0.8]}),
        residual_norm=1.0e-9,
    )
    feedback_result = FeedbackSolveResult(
        converged=True,
        initial_state=state.model_copy(update={"values": [0.1]}),
        final_state=state,
        alternative_fixed_points=[alternative],
    )

    result = build_feedback_attractor_analysis_result(feedback_result)

    assert [attractor.kind for attractor in result.attractors] == ["fixed_point", "fixed_point"]
    assert result.attractors[1].state_representation.equilibrium == {"tax_rate": 0.8}


class _ProfileRecordingCAS(FileSystemCAS):
    def __init__(self, root):
        self.read_refs: list[object] = []
        super().__init__(root)

    def get_bytes(self, artifact_id):
        self.read_refs.append(artifact_id)
        return super().get_bytes(artifact_id)


def test_analysis_loaders_read_the_exact_selected_profile_for_all_ref_types(tmp_path) -> None:
    store = _ProfileRecordingCAS(tmp_path)
    result = build_attractor_analysis_result(
        np.ones((8, 2), dtype=float),
        ["income", "wealth"],
        analysis_id="analysis_selected_profile",
        tolerance=1.0e-8,
        rtol=0.0,
    )
    attractor_ref = persist_attractor_analysis_result(store, result)
    basin = BasinMap(
        basin_id="basin_selected_profile",
        analysis_id=result.analysis_id,
        state_projection=AttractorStateProjection(variables=["income"], reduced_dimension=1),
        sampling_method="deterministic_fixture",
    )
    basin_ref = persist_basin_map(store, basin)
    branch = ContinuationBranch(
        branch_id="branch_selected_profile",
        analysis_id=result.analysis_id,
        branch_kind="equilibrium",
        parameters=["tax_rate"],
    )
    branch_ref = persist_continuation_branch(store, branch)

    for ref, loader in (
        (attractor_ref, load_attractor_analysis_result),
        (basin_ref, load_basin_map),
        (branch_ref, load_continuation_branch),
    ):
        selected = artifact_ref_for_manifest(store.get_manifest(ref))
        assert selected.manifest_profile_sha256 is not None
        store.read_refs.clear()

        loader(store, ref)

        assert any(
            isinstance(read_ref, ArtifactRef)
            and read_ref.artifact_id == selected.artifact_id
            and read_ref.kind == selected.kind
            and read_ref.media_type == selected.media_type
            and read_ref.manifest_profile_sha256 == selected.manifest_profile_sha256
            for read_ref in store.read_refs
        )


def _attractor_contract_payload() -> AttractorAnalysisResult:
    return build_attractor_analysis_result(
        np.ones((8, 2), dtype=float),
        ["income", "wealth"],
        analysis_id="analysis_contract_controls",
        tolerance=1.0e-8,
        rtol=0.0,
    )


def _basin_contract_payload() -> BasinMap:
    return BasinMap(
        basin_id="basin_contract_controls",
        analysis_id="analysis_contract_controls",
        state_projection=AttractorStateProjection(variables=["income"], reduced_dimension=1),
        sampling_method="deterministic_fixture",
    )


def _continuation_contract_payload() -> ContinuationBranch:
    return ContinuationBranch(
        branch_id="branch_contract_controls",
        analysis_id="analysis_contract_controls",
        branch_kind="equilibrium",
        parameters=["tax_rate"],
    )


@pytest.mark.parametrize(
    ("ref_type", "payload_type", "payload_factory", "loader"),
    [
        (
            AttractorAnalysisResultRef,
            AttractorAnalysisResult,
            _attractor_contract_payload,
            load_attractor_analysis_result,
        ),
        (BasinMapRef, BasinMap, _basin_contract_payload, load_basin_map),
        (
            ContinuationBranchRef,
            ContinuationBranch,
            _continuation_contract_payload,
            load_continuation_branch,
        ),
    ],
    ids=["attractor-result", "basin-map", "continuation-branch"],
)
def test_typed_analysis_loader_refuses_wrong_kind_media_schema_and_payload_version(
    tmp_path, ref_type, payload_type, payload_factory, loader
) -> None:
    store = FileSystemCAS(tmp_path)
    payload = payload_factory()
    canon_spec = CanonSpec(forbid_floats=False)
    schema = SchemaInfo(
        name=payload_type.ARTIFACT_SCHEMA_NAME,
        version=payload_type.ARTIFACT_SCHEMA_VERSION,
    )
    assert ref_type.model_fields["kind"].default == payload_type.ARTIFACT_KIND
    assert ref_type.model_fields["media_type"].default == payload_type.ARTIFACT_MEDIA_TYPE

    wrong_kind_ref = store.put_json(
        payload,
        PutOptions(
            kind=f"{payload_type.ARTIFACT_KIND}.wrong",
            media_type=payload_type.ARTIFACT_MEDIA_TYPE,
            schema=schema,
        ),
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="artifact kind"):
        loader(store, wrong_kind_ref)

    wrong_media_ref = store.put_bytes(
        to_canonical_bytes(payload, canon_spec),
        PutOptions(
            kind=payload_type.ARTIFACT_KIND,
            media_type="text/plain",
            schema=schema,
            canon=CanonInfo.from_spec(canon_spec),
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="artifact media type"):
        loader(store, wrong_media_ref)

    wrong_schema_ref = store.put_json(
        payload,
        PutOptions(
            kind=payload_type.ARTIFACT_KIND,
            media_type=payload_type.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=f"{payload_type.ARTIFACT_SCHEMA_NAME}.wrong",
                version=payload_type.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="artifact schema"):
        loader(store, wrong_schema_ref)

    wrong_payload = payload.model_dump(mode="python")
    wrong_payload["schema_version"] = "99.0"
    mismatched_payload_ref = store.put_json(
        wrong_payload,
        PutOptions(
            kind=payload_type.ARTIFACT_KIND,
            media_type=payload_type.ARTIFACT_MEDIA_TYPE,
            schema=schema,
        ),
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="payload schema_version"):
        loader(store, mismatched_payload_ref)


@pytest.mark.parametrize(
    ("ref_type", "payload_type"),
    [
        (AttractorAnalysisResultRef, AttractorAnalysisResult),
        (BasinMapRef, BasinMap),
        (ContinuationBranchRef, ContinuationBranch),
    ],
    ids=["attractor-result", "basin-map", "continuation-branch"],
)
def test_analysis_ref_dtos_constrain_kind_and_media_to_the_producer_contract(
    ref_type, payload_type
) -> None:
    valid_shape = {
        "artifact_id": "sha256:" + "a" * 64,
        "kind": payload_type.ARTIFACT_KIND,
        "media_type": payload_type.ARTIFACT_MEDIA_TYPE,
    }
    ref_type.model_validate(valid_shape)

    with pytest.raises(ValueError):
        ref_type.model_validate({**valid_shape, "kind": f"{payload_type.ARTIFACT_KIND}.wrong"})
    with pytest.raises(ValueError):
        ref_type.model_validate({**valid_shape, "media_type": "text/plain"})
