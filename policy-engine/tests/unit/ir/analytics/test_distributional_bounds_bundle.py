from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import BaseModel

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.distributional import (
    CausalAssumptionCard,
    CohortDimension,
    CouplingDiagnostics,
    DiscreteDistributionSummary,
    DistributionalBoundsBundle,
    DistributionalBoundsMethodSummary,
    DistributionalBoundUniformity,
    DistributionalCouplingStatus,
    DistributionalDualBoundWitness,
    DistributionalDualCertificate,
    DistributionalEffectBundle,
    DistributionalFunctional,
    DistributionalFunctionalParameters,
    DistributionalJustification,
    DistributionalProofArtifact,
    DistributionalProofTarget,
    DistributionBin,
    FunctionalBounds,
    GridAxis,
    OTCouplingSummary,
    QuantileShiftEntry,
    QuantileShiftSummary,
    SubgroupDistributionComparison,
    TailRiskDeltaEntry,
    TailRiskDeltaSummary,
    attach_distributional_dual_certificate_ref,
    load_causal_assumption_card,
    load_discrete_distribution_summary,
    load_distributional_bounds_bundle,
    load_distributional_dual_certificate,
    load_distributional_proof_artifact,
    load_ot_coupling_summary,
    load_quantile_shift_summary,
    load_subgroup_distribution_comparison,
    load_tail_risk_delta_summary,
    persist_causal_assumption_card,
    persist_discrete_distribution_summary,
    persist_distributional_bounds_bundle,
    persist_distributional_dual_certificate,
    persist_distributional_proof_artifact,
    persist_ot_coupling_summary,
    persist_quantile_shift_summary,
    persist_subgroup_distribution_comparison,
    persist_tail_risk_delta_summary,
)
from polisyos.ir.artifacts import ArtifactStore, get_json_artifact, put_json_artifact
from polisyos.ir.artifacts.contracts import ArtifactSelector
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    CausalAssumptionCardRef,
    DistributionalProofArtifactRef,
)


class _ManifestRecordingStore:
    def __init__(self, store: ArtifactStore) -> None:
        self._store = store
        self.selectors: list[ArtifactSelector] = []
        self._get_manifest: Callable[[ArtifactSelector], object] = store.get_manifest

    def __getattr__(self, name: str) -> object:
        return getattr(self._store, name)

    def get_manifest(self, selector: ArtifactSelector) -> object:
        self.selectors.append(selector)
        return self._get_manifest(selector)


def _distributional_proof_ref() -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id="sha256:" + "d" * 64,
        kind="ir.distributional_proof_artifact",
        media_type="application/json",
    )


def _distribution_summary(outcome_name: str) -> DiscreteDistributionSummary:
    return DiscreteDistributionSummary(
        outcome_name=outcome_name,
        sample_size=10,
        total_weight=10.0,
        weighting_mode="uniform",
        mean_value=2.0,
        min_value=1.0,
        max_value=3.0,
        bins=[
            DistributionBin(
                index=0,
                lower_edge=0.0,
                upper_edge=2.0,
                midpoint=1.0,
                probability=0.4,
                sample_count=4,
            ),
            DistributionBin(
                index=1,
                lower_edge=2.0,
                upper_edge=4.0,
                midpoint=3.0,
                probability=0.6,
                sample_count=6,
            ),
        ],
    )


def _axis() -> GridAxis:
    return GridAxis(
        axis_name="quantile",
        values=(0.1, 0.5, 0.9),
        unit="percentile",
    )


def _summary(
    *,
    method: str,
    lower: tuple[float, ...],
    upper: tuple[float, ...],
    sharpness: str = "outer_approx",
) -> DistributionalBoundsMethodSummary:
    return DistributionalBoundsMethodSummary(
        method=method,
        functional=DistributionalFunctional.QUANTILE_SHIFT,
        axis=_axis(),
        bounds=FunctionalBounds(lower=lower, upper=upper),
        sharpness=sharpness,
        assumptions_used=["test_assumption"],
        display_label=method,
    )


def _distributional_leaf_routes() -> list[
    tuple[Callable[..., object], Callable[..., object], BaseModel]
]:
    return [
        (
            persist_discrete_distribution_summary,
            load_discrete_distribution_summary,
            _distribution_summary("owner-route"),
        ),
        (
            persist_ot_coupling_summary,
            load_ot_coupling_summary,
            OTCouplingSummary(
                source_support=(0.0,),
                target_support=(0.0,),
                transport_matrix=((1.0,),),
                regularization_strength=0.1,
                sinkhorn_iterations=1,
                convergence_delta=0.0,
                weighting_mode="uniform",
            ),
        ),
        (
            persist_quantile_shift_summary,
            load_quantile_shift_summary,
            QuantileShiftSummary(
                outcome_name="owner-route",
                entries=[
                    QuantileShiftEntry(
                        quantile=0.5,
                        baseline_value=1.0,
                        counterfactual_value=2.0,
                        shift=1.0,
                    )
                ],
            ),
        ),
        (
            persist_tail_risk_delta_summary,
            load_tail_risk_delta_summary,
            TailRiskDeltaSummary(
                outcome_name="owner-route",
                entries=[
                    TailRiskDeltaEntry(
                        baseline_quantile=0.9,
                        threshold_value=1.0,
                        baseline_exceedance_probability=0.1,
                        counterfactual_exceedance_probability=0.2,
                        exceedance_probability_delta=0.1,
                    )
                ],
            ),
        ),
        (
            persist_subgroup_distribution_comparison,
            load_subgroup_distribution_comparison,
            SubgroupDistributionComparison(
                subgroup_dimension=next(iter(CohortDimension)),
                subgroup_id="owner-route",
                subgroup_label="Owner route",
                baseline_distribution_ref=ArtifactRefModel(
                    artifact_id="sha256:" + "1" * 64,
                    kind="ir.discrete_distribution_summary",
                    media_type="application/json",
                ),
                counterfactual_distribution_ref=ArtifactRefModel(
                    artifact_id="sha256:" + "2" * 64,
                    kind="ir.discrete_distribution_summary",
                    media_type="application/json",
                ),
                coupling_diagnostics=CouplingDiagnostics(mass_conservation_error=0.0),
                baseline_sample_size=1,
                counterfactual_sample_size=1,
            ),
        ),
        (
            persist_causal_assumption_card,
            load_causal_assumption_card,
            CausalAssumptionCard(
                scope="marginal",
                status="scenario_only",
                theorem_family="owner-route",
                assumption_type="test",
                description="test payload for selected-view ownership",
                testable=False,
            ),
        ),
        (
            persist_distributional_proof_artifact,
            load_distributional_proof_artifact,
            DistributionalProofArtifact(
                target=DistributionalProofTarget.COUPLING,
                coupling_status=DistributionalCouplingStatus.SCENARIO_ONLY,
                theorem_family="owner-route",
            ),
        ),
    ]


def test_distributional_leaf_routes_bind_owner_schema_and_profile(tmp_path) -> None:
    store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "owner-routes"))

    for index, (persist, load, payload) in enumerate(_distributional_leaf_routes()):
        ref = persist(store, payload)
        assert isinstance(ref, ArtifactRefModel)
        expected_ref_type = {
            5: CausalAssumptionCardRef,
            6: DistributionalProofArtifactRef,
        }.get(index, ArtifactRefModel)
        assert type(ref) is expected_ref_type

        manifest = store.get_manifest(ref)
        schema = manifest.artifact_schema
        assert schema is not None
        assert manifest.kind == ref.kind
        assert schema.name == ref.kind
        assert schema.version
        loaded = load(store, ref)
        assert isinstance(loaded, BaseModel)
        assert loaded.model_dump(mode="json") == payload.model_dump(mode="json")

        foreign_schema_data = put_json_artifact(
            store,
            payload.model_dump(mode="json"),
            kind=ref.kind,
            schema_name=f"ir.foreign_distributional_owner_{index}",
            schema_version="9.9",
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert foreign_schema_data["artifact_id"] == str(ref.artifact_id)
        assert foreign_schema_data["manifest_profile_sha256"] != ref.manifest_profile_sha256
        foreign_schema_ref = ref.model_copy(
            update={"manifest_profile_sha256": foreign_schema_data["manifest_profile_sha256"]}
        )
        assert get_json_artifact(store, foreign_schema_ref) == payload.model_dump(mode="json")
        with pytest.raises(ValueError, match="ir_distributional_leaf_owner_mismatch"):
            load(store, foreign_schema_ref)

        assert ref.manifest_profile_sha256 is not None


def test_distributional_generic_leaf_rejects_foreign_kind_with_valid_payload(tmp_path) -> None:
    store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "owner-kind"))
    persist, load, payload = _distributional_leaf_routes()[0]
    ref = persist(store, payload)
    assert isinstance(ref, ArtifactRefModel)
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    assert schema is not None

    foreign_kind_data = put_json_artifact(
        store,
        payload.model_dump(mode="json"),
        kind="ir.foreign_distributional_kind",
        schema_name=schema.name,
        schema_version=schema.version,
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert foreign_kind_data["artifact_id"] == str(ref.artifact_id)
    foreign_kind_ref = ArtifactRefModel.model_validate(foreign_kind_data)
    assert get_json_artifact(store, foreign_kind_ref) == payload.model_dump(mode="json")

    with pytest.raises(ValueError, match="ir_distributional_leaf_owner_mismatch"):
        load(store, foreign_kind_ref)


def test_distributional_generic_leaf_preserves_selected_profile_on_read(
    tmp_path,
) -> None:
    store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path / "owner-profile"))
    persist, load, payload = _distributional_leaf_routes()[0]
    ref = persist(store, payload)
    assert isinstance(ref, ArtifactRefModel)
    assert ref.manifest_profile_sha256 is not None
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    assert schema is not None

    alternate_profile_data = put_json_artifact(
        store,
        payload.model_dump(mode="json"),
        kind=ref.kind,
        schema_name=schema.name,
        schema_version=schema.version,
        canon_spec=CanonSpec(forbid_floats=False, ensure_ascii=True),
        return_selected_profile=True,
    )
    assert alternate_profile_data["artifact_id"] == str(ref.artifact_id)
    assert alternate_profile_data["manifest_profile_sha256"] != ref.manifest_profile_sha256
    alternate_profile_ref = ArtifactRefModel.model_validate(alternate_profile_data)

    recording_store = _ManifestRecordingStore(store)
    loaded = load(recording_store, alternate_profile_ref)
    assert isinstance(loaded, BaseModel)
    assert loaded.model_dump(mode="json") == payload.model_dump(mode="json")
    assert recording_store.selectors
    selected_profiles = [
        selector.get("manifest_profile_sha256")
        if isinstance(selector, dict)
        else getattr(selector, "manifest_profile_sha256", None)
        for selector in recording_store.selectors
    ]
    assert all(
        profile == alternate_profile_ref.manifest_profile_sha256 for profile in selected_profiles
    ), selected_profiles


def test_distributional_bounds_bundle_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = DistributionalBoundsBundle(
        estimand_type="quantile_shift",
        functional=DistributionalFunctional.QUANTILE_SHIFT,
        axis=_axis(),
        method_summaries=[
            _summary(
                method="lee_trimming_distributional",
                lower=(-2.0, -1.0, -0.5),
                upper=(1.0, 2.0, 3.0),
            )
        ],
        metadata={"theorem_family": "lee_trimming"},
    )

    ref = persist_distributional_bounds_bundle(_ensure_ir_artifact_store(store), bundle)
    loaded = load_distributional_bounds_bundle(_ensure_ir_artifact_store(store), ref)

    assert loaded == bundle
    assert loaded.consensus_bounds is not None
    assert loaded.consensus_bounds.lower == (-2.0, -1.0, -0.5)
    assert loaded.sharpness_status == "outer_approx"


def test_distributional_bounds_bundle_computes_pointwise_consensus() -> None:
    bundle = DistributionalBoundsBundle(
        estimand_type="quantile_shift",
        functional=DistributionalFunctional.QUANTILE_SHIFT,
        axis=_axis(),
        method_summaries=[
            _summary(
                method="lee_trimming_distributional",
                lower=(-2.0, -1.0, -0.5),
                upper=(1.0, 2.0, 3.0),
            ),
            _summary(
                method="intersection_bounds_band",
                lower=(-1.5, -0.5, 0.0),
                upper=(0.8, 1.5, 2.5),
                sharpness="unknown",
            ),
        ],
    )

    assert bundle.consensus_bounds is not None
    assert bundle.consensus_bounds.lower == (-1.5, -0.5, 0.0)
    assert bundle.consensus_bounds.upper == (0.8, 1.5, 2.5)
    assert bundle.point_identified is False
    assert bundle.sharpness_status == "unknown"


def test_distributional_bounds_bundle_rejects_axis_length_mismatches() -> None:
    with pytest.raises(ValueError, match="axis and envelopes must have equal length"):
        DistributionalBoundsMethodSummary(
            method="makarov_pointwise",
            functional=DistributionalFunctional.ITE_TAIL_RISK,
            axis=GridAxis(axis_name="effect_threshold", values=(0.1, 0.2), unit="std"),
            bounds=FunctionalBounds(lower=(0.0,), upper=(0.2,)),
            sharpness="sharp",
            assumptions_used=["known_marginals_only_no_rank_invariance"],
        )


def test_distributional_effect_bundle_accepts_distributional_bounds_refs(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = persist_discrete_distribution_summary(
        _ensure_ir_artifact_store(store), _distribution_summary("income")
    )
    counterfactual_ref = persist_discrete_distribution_summary(
        _ensure_ir_artifact_store(store), _distribution_summary("income")
    )
    bounds_ref = persist_distributional_bounds_bundle(
        _ensure_ir_artifact_store(store),
        DistributionalBoundsBundle(
            estimand_type="quantile_shift",
            functional=DistributionalFunctional.QUANTILE_SHIFT,
            axis=_axis(),
            method_summaries=[
                _summary(
                    method="lee_trimming_distributional",
                    lower=(-2.0, -1.0, -0.5),
                    upper=(1.0, 2.0, 3.0),
                )
            ],
            metadata={"theorem_family": "lee_trimming"},
        ),
    )

    bundle = DistributionalEffectBundle(
        outcome_name="income",
        justification=DistributionalJustification.BOUNDED,
        marginal_justification=DistributionalJustification.BOUNDED,
        marginal_law_justification=DistributionalJustification.BOUNDED,
        coupling_justification=None,
        baseline_distribution_ref=baseline_ref,
        counterfactual_distribution_ref=counterfactual_ref,
        coupling_ref=None,
        coupling_diagnostics=CouplingDiagnostics(
            mass_conservation_error=0.0,
            weighting_mode="uniform",
            identifiability_assumptions=["marginal_law_bounded_only"],
        ),
        distributional_bounds_refs=[bounds_ref],
        distributional_proof_ref=_distributional_proof_ref(),
        causal_assumptions=["lee_monotone_selection_S1_ge_S0"],
    )

    assert bundle.justification is DistributionalJustification.BOUNDED
    assert bundle.distributional_bounds_refs == [bounds_ref]


def test_distributional_effect_bundle_rejects_duplicate_bounds_refs(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = persist_discrete_distribution_summary(
        _ensure_ir_artifact_store(store), _distribution_summary("income")
    )
    counterfactual_ref = persist_discrete_distribution_summary(
        _ensure_ir_artifact_store(store), _distribution_summary("income")
    )
    bounds_ref = persist_distributional_bounds_bundle(
        _ensure_ir_artifact_store(store),
        DistributionalBoundsBundle(
            estimand_type="ite_tail_risk",
            functional=DistributionalFunctional.ITE_TAIL_RISK,
            axis=GridAxis(axis_name="effect_threshold", values=(1.0,), unit="uah"),
            method_summaries=[
                DistributionalBoundsMethodSummary(
                    method="makarov_pointwise",
                    functional=DistributionalFunctional.ITE_TAIL_RISK,
                    axis=GridAxis(axis_name="effect_threshold", values=(1.0,), unit="uah"),
                    bounds=FunctionalBounds(lower=(0.1,), upper=(0.4,)),
                    sharpness="sharp",
                    assumptions_used=["known_marginals_only_no_rank_invariance"],
                    display_label="makarov_pointwise",
                )
            ],
        ),
    )

    with pytest.raises(
        ValueError, match="distributional_bounds_refs contains duplicate artifact_id"
    ):
        DistributionalEffectBundle(
            outcome_name="income",
            justification=DistributionalJustification.BOUNDED,
            marginal_justification=DistributionalJustification.BOUNDED,
            marginal_law_justification=DistributionalJustification.BOUNDED,
            baseline_distribution_ref=baseline_ref,
            counterfactual_distribution_ref=counterfactual_ref,
            coupling_ref=None,
            coupling_diagnostics=CouplingDiagnostics(
                mass_conservation_error=0.0,
                weighting_mode="uniform",
                identifiability_assumptions=["marginal_law_bounded_only"],
            ),
            distributional_bounds_refs=[bounds_ref, bounds_ref],
            distributional_proof_ref=_distributional_proof_ref(),
            causal_assumptions=["known_marginals_only_no_rank_invariance"],
        )


def test_distributional_bounds_bundle_accepts_functional_parameters_and_dual_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    certificate = DistributionalDualCertificate(
        theorem_family="mtr_headcount",
        functional=DistributionalFunctional.POVERTY_HEADCOUNT,
        axis=GridAxis(axis_name="poverty_line", values=(2.5,), unit="income"),
        assumption_class="mtr",
        primal_problem_class="binary_potential_outcome_box",
        dual_problem_class="indicator_threshold_dual",
        sharpness_status="sharp",
        bound_uniformity=DistributionalBoundUniformity.NOT_APPLICABLE,
        attainment_status="attained",
        lower_bound_witness=DistributionalDualBoundWitness(
            bound_direction="lower",
            primal_objective_values=(0.25,),
            dual_objective_values=(0.25,),
            dual_gaps=(0.0,),
        ),
        upper_bound_witness=DistributionalDualBoundWitness(
            bound_direction="upper",
            primal_objective_values=(0.5,),
            dual_objective_values=(0.5,),
            dual_gaps=(0.0,),
        ),
    )
    cert_ref = persist_distributional_dual_certificate(
        _ensure_ir_artifact_store(store), certificate
    )
    bundle = DistributionalBoundsBundle(
        estimand_type="poverty_headcount_y1",
        functional=DistributionalFunctional.POVERTY_HEADCOUNT,
        axis=GridAxis(axis_name="poverty_line", values=(2.5,), unit="income"),
        functional_parameters=DistributionalFunctionalParameters(
            poverty_line=2.5,
            poverty_lines=(2.5,),
            normalization_mode="population_share",
            target_potential_outcome="y1",
        ),
        method_summaries=[
            DistributionalBoundsMethodSummary(
                method="mtr_headcount",
                functional=DistributionalFunctional.POVERTY_HEADCOUNT,
                axis=GridAxis(axis_name="poverty_line", values=(2.5,), unit="income"),
                bounds=FunctionalBounds(lower=(0.25,), upper=(0.5,)),
                sharpness="sharp",
                assumptions_used=["monotone_treatment_response_y1_ge_y0"],
            )
        ],
    )

    attached = attach_distributional_dual_certificate_ref(bundle, cert_ref)
    persisted_ref = persist_distributional_bounds_bundle(_ensure_ir_artifact_store(store), attached)
    loaded_bundle = load_distributional_bounds_bundle(
        _ensure_ir_artifact_store(store), persisted_ref
    )
    loaded_certificate = load_distributional_dual_certificate(
        _ensure_ir_artifact_store(store), cert_ref
    )

    assert loaded_bundle.dual_certificate_ref == cert_ref
    assert loaded_bundle.functional_parameters is not None
    assert loaded_bundle.functional_parameters.poverty_line == pytest.approx(2.5)
    assert loaded_certificate.theorem_family == "mtr_headcount"


def test_distributional_bounds_bundle_requires_atkinson_epsilon() -> None:
    with pytest.raises(ValueError, match="Atkinson bounds require"):
        DistributionalBoundsBundle(
            estimand_type="atkinson_y1",
            functional=DistributionalFunctional.ATKINSON,
            axis=GridAxis(axis_name="support", values=(0.0,), unit="income"),
            method_summaries=[
                DistributionalBoundsMethodSummary(
                    method="mtr_atkinson",
                    functional=DistributionalFunctional.ATKINSON,
                    axis=GridAxis(axis_name="support", values=(0.0,), unit="income"),
                    bounds=FunctionalBounds(lower=(0.1,), upper=(0.3,)),
                    sharpness="outer_approx",
                    assumptions_used=["monotone_treatment_response_y1_ge_y0"],
                )
            ],
        )
