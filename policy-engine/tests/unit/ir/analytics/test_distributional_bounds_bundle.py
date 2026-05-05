from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.distributional import (
    CouplingDiagnostics,
    DiscreteDistributionSummary,
    DistributionalBoundsBundle,
    DistributionalBoundsMethodSummary,
    DistributionalBoundUniformity,
    DistributionalDualBoundWitness,
    DistributionalDualCertificate,
    DistributionalEffectBundle,
    DistributionalFunctional,
    DistributionalFunctionalParameters,
    DistributionalJustification,
    DistributionBin,
    FunctionalBounds,
    GridAxis,
    attach_distributional_dual_certificate_ref,
    load_distributional_bounds_bundle,
    load_distributional_dual_certificate,
    persist_discrete_distribution_summary,
    persist_distributional_bounds_bundle,
    persist_distributional_dual_certificate,
)
from polisyos.ir.refs import ArtifactRefModel


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

    ref = persist_distributional_bounds_bundle(store, bundle)
    loaded = load_distributional_bounds_bundle(store, ref)

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
    baseline_ref = persist_discrete_distribution_summary(store, _distribution_summary("income"))
    counterfactual_ref = persist_discrete_distribution_summary(
        store, _distribution_summary("income")
    )
    bounds_ref = persist_distributional_bounds_bundle(
        store,
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
    baseline_ref = persist_discrete_distribution_summary(store, _distribution_summary("income"))
    counterfactual_ref = persist_discrete_distribution_summary(
        store, _distribution_summary("income")
    )
    bounds_ref = persist_distributional_bounds_bundle(
        store,
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
    cert_ref = persist_distributional_dual_certificate(store, certificate)
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
    persisted_ref = persist_distributional_bounds_bundle(store, attached)
    loaded_bundle = load_distributional_bounds_bundle(store, persisted_ref)
    loaded_certificate = load_distributional_dual_certificate(store, cert_ref)

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
