from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.invariance import (
    RegimeShiftComputationalFeasibility,
    RegimeShiftDataSignature,
    RegimeShiftEnvironmentRecord,
    RegimeShiftIdentifiabilityWitness,
    RegimeShiftIdentificationCertificate,
    RegimeShiftMECContraction,
    RegimeShiftMECContractionEdgeUpdates,
    RegimeShiftMECContractionSummary,
    RegimeShiftSetTestResult,
    RegimeShiftTargetResult,
    RegimeShiftTrack7InteractionStats,
    RegimeShiftTrack7Revalidation,
    RegimeShiftTypeAssessment,
    ShiftTypeAlphaSplit,
    ShiftTypeAssumptions,
    ShiftTypeCertificationLevel,
    ShiftTypeContextExogeneity,
    ShiftTypeGlobalShiftTest,
    ShiftTypeObservedSelectionSufficiency,
    ShiftTypeOverallLabel,
    ShiftTypePipelineAction,
    ShiftTypeSelectionOnlyWitness,
    ShiftTypeStructuralOnlyWitness,
    ShiftTypeWitnessBundle,
    ShiftTypeWitnessStatus,
    load_regime_shift_identification_certificate,
    persist_regime_shift_identification_certificate,
)
from polisyos.ir.refs import RegimeShiftIdentificationCertificateRef


def _certificate() -> RegimeShiftIdentificationCertificate:
    return RegimeShiftIdentificationCertificate(
        data_signature=RegimeShiftDataSignature(
            dataset_ref="dataset:employment_regimes",
            variables=("training_subsidy", "employment_rate"),
            sample_sizes_by_env={"pre": 120, "post": 140},
        ),
        environments=(
            RegimeShiftEnvironmentRecord(env_id="pre", regime_id="baseline"),
            RegimeShiftEnvironmentRecord(env_id="post", regime_id="subsidy"),
        ),
        targets=(
            RegimeShiftTargetResult(
                target="employment_rate",
                envs_used=("pre", "post"),
                accepted_sets=(RegimeShiftSetTestResult(S=("training_subsidy",), p_value=0.43),),
                rejected_sets=(RegimeShiftSetTestResult(S=(), p_value=0.001),),
                estimated_parents=("training_subsidy",),
            ),
        ),
        identifiability_witness=RegimeShiftIdentifiabilityWitness(
            theorem_slice="phase1_linear_icp_fallback_v1",
            model_class="linear_ols",
            assumptions=(
                "linear conditional mean specification",
                "fallback witness only",
            ),
            min_environments_required=2,
            min_informative_environments_required=1,
            environment_diversity_requirements=("at least two environments",),
            informative_envs=("post",),
            redundant_envs=(),
            diversity_satisfied=False,
            identification_scope="linear_fallback_only_not_phase_closing",
        ),
        computational_feasibility=RegimeShiftComputationalFeasibility(
            mode="exact",
            n_variables=2,
            n_targets=1,
            n_environments=2,
            n_environment_pairs=1,
            conditioning_cap_q=1,
            local_separator_cap_eta=2,
            candidate_parent_sizes={"employment_rate": 1},
            max_candidate_parents=1,
            expected_test_count=2,
            component_sizes=(2,),
            treewidth_upper_bounds=(1,),
            hard_required_edges=(("training_subsidy", "employment_rate"),),
            hard_forbidden_edges=(("employment_rate", "training_subsidy"),),
            exact_mode_possible=True,
            exact_mode_applied=True,
            selected_parent_sets={"employment_rate": ("training_subsidy",)},
            track7=RegimeShiftTrack7InteractionStats(
                revalidation_required=False,
                revalidation=RegimeShiftTrack7Revalidation(
                    performed=True,
                    severity="info",
                    exact_certificate_valid=True,
                ),
            ),
        ),
        shift_type_assessment=RegimeShiftTypeAssessment(
            overall_label=ShiftTypeOverallLabel.STRUCTURAL_ONLY_CONSISTENT,
            certification_level=ShiftTypeCertificationLevel.PROVISIONAL,
            alpha_total=0.05,
            alpha_split=ShiftTypeAlphaSplit(
                shift=0.01,
                selection=0.02,
                structural=0.02,
            ),
            assumptions=ShiftTypeAssumptions(
                context_exogeneity=ShiftTypeContextExogeneity.DECLARED,
                observed_selection_sufficiency=ShiftTypeObservedSelectionSufficiency.UNSUPPORTED,
            ),
            witnesses=ShiftTypeWitnessBundle(
                global_shift_test=ShiftTypeGlobalShiftTest(
                    method="aggregated_ks_proxy",
                    p_value=0.001,
                    effect_size=0.42,
                ),
                selection_only_witness=ShiftTypeSelectionOnlyWitness(
                    status=ShiftTypeWitnessStatus.REJECTED,
                    balancing_set=("training_subsidy",),
                    p_value=0.01,
                    per_variable_p_values={"employment_rate": 0.01},
                    max_weight=2.0,
                    ess_min=120.0,
                ),
                structural_only_witness=ShiftTypeStructuralOnlyWitness(
                    status=ShiftTypeWitnessStatus.NOT_REJECTED,
                    targets_tested=("employment_rate",),
                    accepted_parent_sets={"employment_rate": ("training_subsidy",)},
                    p_value=0.43,
                    per_target_p_values={"employment_rate": 0.43},
                ),
            ),
            pipeline_action=ShiftTypePipelineAction(
                allow_icp_graph_contraction=True,
            ),
            narrative_summary="Structural witness passed and observed selection witness failed.",
        ),
        mec_contraction=RegimeShiftMECContraction(
            edge_updates=RegimeShiftMECContractionEdgeUpdates(
                forced_orientations=(("training_subsidy", "employment_rate"),),
                forbidden_orientations=(("employment_rate", "training_subsidy"),),
            ),
            summary=RegimeShiftMECContractionSummary(edges_oriented_total=1),
        ),
    )


def test_regime_shift_certificate_roundtrips_through_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    certificate = _certificate()

    ref = persist_regime_shift_identification_certificate(store, certificate)
    loaded = load_regime_shift_identification_certificate(store, ref)

    assert isinstance(ref, RegimeShiftIdentificationCertificateRef)
    assert ref.kind == "ir.regime_shift_identification_certificate"
    assert loaded == certificate


def test_shift_type_assessment_default_alpha_split_matches_total_budget() -> None:
    assessment = RegimeShiftTypeAssessment(
        overall_label=ShiftTypeOverallLabel.AMBIGUOUS,
    )

    assert assessment.alpha_total == pytest.approx(0.05)
    assert (
        assessment.alpha_split.shift
        + assessment.alpha_split.selection
        + assessment.alpha_split.structural
    ) == pytest.approx(assessment.alpha_total)


def test_regime_shift_certificate_rejects_unknown_target_env() -> None:
    certificate = _certificate()

    with pytest.raises(ValueError, match="unknown envs"):
        RegimeShiftIdentificationCertificate.model_validate(
            certificate.model_dump(mode="json")
            | {
                "targets": [
                    certificate.targets[0]
                    .model_copy(update={"envs_used": ("missing",)})
                    .model_dump(mode="json")
                ]
            }
        )


def test_regime_shift_certificate_rejects_unknown_identifiability_witness_env() -> None:
    certificate = _certificate()

    with pytest.raises(
        ValueError, match="identifiability_witness.informative_envs references unknown envs"
    ):
        RegimeShiftIdentificationCertificate.model_validate(
            certificate.model_dump(mode="json")
            | {
                "identifiability_witness": certificate.identifiability_witness.model_copy(
                    update={"informative_envs": ("missing",)}
                ).model_dump(mode="json")
            }
        )


def test_regime_shift_certificate_rejects_unknown_shift_assessment_variable() -> None:
    certificate = _certificate()

    with pytest.raises(ValueError, match="selection_only_witness references unknown variables"):
        RegimeShiftIdentificationCertificate.model_validate(
            certificate.model_dump(mode="json")
            | {
                "shift_type_assessment": certificate.shift_type_assessment.model_copy(
                    update={
                        "witnesses": certificate.shift_type_assessment.witnesses.model_copy(
                            update={
                                "selection_only_witness": certificate.shift_type_assessment.witnesses.selection_only_witness.model_copy(
                                    update={"balancing_set": ("missing",)}
                                )
                            }
                        )
                    }
                ).model_dump(mode="json")
            }
        )


def test_regime_shift_certificate_rejects_unknown_feasibility_target() -> None:
    certificate = _certificate()

    with pytest.raises(ValueError, match="candidate_parent_sizes references unknown targets"):
        RegimeShiftIdentificationCertificate.model_validate(
            certificate.model_dump(mode="json")
            | {
                "computational_feasibility": certificate.computational_feasibility.model_copy(
                    update={"candidate_parent_sizes": {"missing": 1}}
                ).model_dump(mode="json")
            }
        )


def test_track7_revalidation_rejects_blocker_marked_as_exact_valid() -> None:
    with pytest.raises(ValueError, match="invalidate the exact certificate"):
        RegimeShiftTrack7Revalidation(
            performed=True,
            severity="blocker",
            blocker_families=("trek_rank",),
            exact_certificate_valid=True,
        )
