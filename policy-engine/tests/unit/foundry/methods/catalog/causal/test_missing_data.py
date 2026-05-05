"""Tests for Phase 2: Missing Data Theory (M-graphs).

Covers:
  - GraphType.MGRAPH validation and build_mgraph factory
  - RecoverabilityResult: test_recoverability algorithm
  - OrderedRecovery: ordered_recovery algorithm
  - full_law_identify: two-stage pipeline
  - Foundry methods: pure_step interfaces
"""

import numpy as np
import pytest
from polisyos.foundry.methods.catalog.causal.missing_data import (
    AdministrativeMissingnessAssessment,
    assess_administrative_missingness,
)
from polisyos.ir.analytics.administrative_missingness import (
    AdministrativeMissingnessClass,
    AdministrativeMissingnessDirection,
    AdministrativeMissingnessMetadata,
    AdministrativeMissingnessScenarioFamily,
    AdministrativeMissingnessUnitScope,
    MissingnessAssessmentStatus,
    attach_administrative_missingness_metadata,
    build_compliance_based_mgraph,
    build_registration_based_mgraph,
    build_system_change_based_mgraph,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.mgraph import (
    MissingnessKind,
    build_mgraph,
    extract_mgraph_metadata,
)

# ---------------------------------------------------------------------------
# Shared DGP helpers
# ---------------------------------------------------------------------------


def make_mcar_mgraph() -> CausalGraphModel:
    """X → Y, R_X is MCAR (no parents)."""
    return build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        missingness_map={"X": MissingnessKind.MCAR},
    )


def make_mar_mgraph() -> CausalGraphModel:
    """R_X depends on Y (MAR: missingness determined by observed variable, X not ancestor of Y)."""
    return build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("Y", "R_X")],
        missingness_map={"X": MissingnessKind.MAR},
    )


def make_mnar_mgraph() -> CausalGraphModel:
    """X → Y, X → R_X (MNAR: missingness depends on X itself)."""
    return build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        missingness_map={"X": MissingnessKind.MNAR},
    )


def make_fully_observed_graph() -> CausalGraphModel:
    """X → Y, no missing data at all."""
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )


def make_multivar_mcar_mgraph() -> CausalGraphModel:
    """X → Y, both MCAR."""
    return build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        missingness_map={
            "X": MissingnessKind.MCAR,
            "Y": MissingnessKind.MCAR,
        },
    )


def make_partial_mnar_mgraph() -> CausalGraphModel:
    """X → Y, X is MCAR, Y is MNAR (Y → R_Y)."""
    return build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        missingness_map={
            "X": MissingnessKind.MCAR,
            "Y": MissingnessKind.MNAR,
        },
    )


def make_confounded_mcar_mgraph() -> CausalGraphModel:
    """X → Y with bidirected X ↔ Y (latent confounder), X MCAR.
    Stage 1 should pass (MCAR), Stage 2 should HEDGE_FOUND (non-identifiable).
    """
    return build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        bidirected_edges=[("X", "Y")],
        missingness_map={"X": MissingnessKind.MCAR},
    )


def make_irrelevant_mnar_mgraph() -> CausalGraphModel:
    """X -> Y is cleanly identified, but unrelated Z has MNAR missingness."""
    return build_mgraph(
        substantive_vars=["X", "Y", "Z"],
        directed_edges=[("X", "Y")],
        missingness_map={"Z": MissingnessKind.MNAR},
    )


# ---------------------------------------------------------------------------
# T1: MCAR is recoverable
# ---------------------------------------------------------------------------


def test_mcar_is_recoverable():
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        RecoverabilityStatus,
        test_recoverability,
    )

    graph = make_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = test_recoverability(
        query_vars=frozenset(meta.substantive_vars),
        graph=graph,
        mgraph_meta=meta,
    )
    assert result.status == RecoverabilityStatus.RECOVERABLE
    assert result.blocking_r_nodes == frozenset()
    assert result.recovery_estimand is not None


# ---------------------------------------------------------------------------
# T2: MAR is recoverable
# ---------------------------------------------------------------------------


def test_mar_is_recoverable():
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        RecoverabilityStatus,
        test_recoverability,
    )

    graph = make_mar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = test_recoverability(
        query_vars=frozenset(meta.substantive_vars),
        graph=graph,
        mgraph_meta=meta,
    )
    assert result.status == RecoverabilityStatus.RECOVERABLE
    assert result.blocking_r_nodes == frozenset()


# ---------------------------------------------------------------------------
# T3: MNAR is NOT recoverable
# ---------------------------------------------------------------------------


def test_mnar_not_recoverable():
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        RecoverabilityStatus,
        test_recoverability,
    )

    graph = make_mnar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = test_recoverability(
        query_vars=frozenset(meta.substantive_vars),
        graph=graph,
        mgraph_meta=meta,
    )
    assert result.status == RecoverabilityStatus.NOT_RECOVERABLE
    assert "R_X" in result.blocking_r_nodes
    assert result.recovery_estimand is None


# ---------------------------------------------------------------------------
# T4: Fully observed graph (no R-nodes) is trivially recoverable
# ---------------------------------------------------------------------------


def test_fully_observed_trivial():
    """For a fully-observed graph, build an explicit MGRAPH with no missingness."""
    # A graph where all vars are fully observed still needs to be MGRAPH type
    # to use test_recoverability. Build one with empty missingness_map.
    graph = build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        missingness_map={},  # no missingness at all
    )
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        RecoverabilityStatus,
        test_recoverability,
    )

    meta = extract_mgraph_metadata(graph)
    result = test_recoverability(
        query_vars=frozenset(meta.substantive_vars),
        graph=graph,
        mgraph_meta=meta,
    )
    assert result.status == RecoverabilityStatus.RECOVERABLE
    assert result.blocking_r_nodes == frozenset()


# ---------------------------------------------------------------------------
# T5: Both MCAR — both recoverable
# ---------------------------------------------------------------------------


def test_multivar_both_mcar():
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        RecoverabilityStatus,
        test_recoverability,
    )

    graph = make_multivar_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = test_recoverability(
        query_vars=frozenset(meta.substantive_vars),
        graph=graph,
        mgraph_meta=meta,
    )
    assert result.status == RecoverabilityStatus.RECOVERABLE


# ---------------------------------------------------------------------------
# T6: Partial non-recoverability — only MNAR R-node is blocked
# ---------------------------------------------------------------------------


def test_partial_nonrecoverability():
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        RecoverabilityStatus,
        test_recoverability,
    )

    graph = make_partial_mnar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = test_recoverability(
        query_vars=frozenset(meta.substantive_vars),
        graph=graph,
        mgraph_meta=meta,
    )
    assert result.status == RecoverabilityStatus.NOT_RECOVERABLE
    assert "R_Y" in result.blocking_r_nodes
    # R_X (MCAR) must NOT be blocking
    assert "R_X" not in result.blocking_r_nodes


# ---------------------------------------------------------------------------
# T6b: build_mgraph legacy/base_graph compatibility
# ---------------------------------------------------------------------------


def test_build_mgraph_legacy_base_graph_api_preserves_mnar_blocking():
    """Legacy base_graph + missing_variables input should still build a valid M-graph."""
    base_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    graph = build_mgraph(
        base_graph=base_graph,
        missing_variables={"X": MissingnessKind.MNAR},
    )

    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        RecoverabilityStatus,
        test_recoverability,
    )

    meta = extract_mgraph_metadata(graph)
    result = test_recoverability(
        query_vars=frozenset({"X"}),
        graph=graph,
        mgraph_meta=meta,
    )
    assert result.status == RecoverabilityStatus.NOT_RECOVERABLE
    assert result.blocking_r_nodes == frozenset({"R_X"})


def test_build_mgraph_accepts_explicit_missingness_edges():
    """Explicit missingness edges should be routed into the M-graph metadata correctly."""
    graph = build_mgraph(
        substantive_vars=["X", "Y", "Z"],
        directed_edges=[("X", "Y")],
        missingness_map={"X": MissingnessKind.MAR},
        missingness_edges=[("Z", "R_X")],
    )

    meta = extract_mgraph_metadata(graph)
    assert frozenset(meta.substantive_vars) == frozenset({"X", "Y", "Z"})
    assert {f"R_{node.target_variable}" for node in meta.r_nodes} == {"R_X"}

    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        RecoverabilityStatus,
        test_recoverability,
    )

    result = test_recoverability(
        query_vars=frozenset({"X"}),
        graph=graph,
        mgraph_meta=meta,
    )
    assert result.status == RecoverabilityStatus.RECOVERABLE


# ---------------------------------------------------------------------------
# T6c: Administrative missingness taxonomy and assessment
# ---------------------------------------------------------------------------


def test_registration_based_assessment_is_recoverable_when_frame_observed():
    graph = build_registration_based_mgraph(
        substantive_vars=["income", "outcome"],
        directed_edges=[("income", "outcome")],
        target_variables=["income"],
        registration_indicator="registration_flag",
        eligibility_covariates=["eligibility_score"],
        population_frame_observed=True,
    )

    assessment = assess_administrative_missingness(graph=graph)

    assert assessment.scenario_family is AdministrativeMissingnessScenarioFamily.REGISTRATION_BASED
    assert assessment.scenario_class is AdministrativeMissingnessClass.REGISTRATION_NOT_REGISTERED
    assert assessment.missingness_direction is AdministrativeMissingnessDirection.NOT_GENERATED
    assert assessment.missingness_unit_scope is AdministrativeMissingnessUnitScope.RECORD
    assert assessment.status is MissingnessAssessmentStatus.RECOVERABLE
    assert set(assessment.administrative_covariates_present) == {
        "registration_flag",
        "eligibility_score",
    }
    assert assessment.recoverability is not None
    assert assessment.recoverability.blocking_r_nodes == ()
    assert assessment.recommended_method_stack[:2] == ("ipw", "aipw")


def test_registration_based_assessment_marks_selection_only_frame_as_partial():
    graph = build_registration_based_mgraph(
        substantive_vars=["income", "outcome"],
        directed_edges=[("income", "outcome")],
        target_variables=["income"],
        registration_indicator="registration_flag",
        eligibility_covariates=["eligibility_score"],
        population_frame_observed=False,
    )

    assessment = assess_administrative_missingness(graph=graph)

    assert assessment.status is MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE
    assert any("non-registered" in recommendation for recommendation in assessment.recommendations)


def test_registration_builder_defaults_application_channel_to_not_applied():
    graph = build_registration_based_mgraph(
        substantive_vars=["benefit_need", "benefit_award"],
        directed_edges=[("benefit_need", "benefit_award")],
        target_variables=["benefit_award"],
        registration_indicator="application_submitted",
        eligibility_covariates=["eligibility_score"],
        population_frame_observed=True,
    )

    assessment = assess_administrative_missingness(graph=graph)

    assert assessment.scenario_class is AdministrativeMissingnessClass.REGISTRATION_NOT_APPLIED
    assert assessment.missingness_direction is AdministrativeMissingnessDirection.NOT_GENERATED


def test_compliance_based_assessment_detects_self_censoring():
    graph = build_compliance_based_mgraph(
        substantive_vars=["income", "outcome"],
        directed_edges=[("income", "outcome")],
        target_variables=["income"],
        compliance_indicator="filing_complete",
        compliance_driver_covariates=["deadline_pressure"],
        self_censoring_variables=["income"],
    )

    assessment = assess_administrative_missingness(graph=graph)

    assert assessment.scenario_family is AdministrativeMissingnessScenarioFamily.COMPLIANCE_BASED
    assert assessment.status is MissingnessAssessmentStatus.NOT_RECOVERABLE
    assert assessment.recoverability is not None
    assert "R_income" in assessment.recoverability.blocking_r_nodes


def test_system_change_assessment_populates_testability_audit():
    graph = build_system_change_based_mgraph(
        substantive_vars=["income", "outcome"],
        directed_edges=[("income", "outcome")],
        target_variables=["income"],
        system_version_variable="system_version",
        rollout_covariates=["region"],
        affected_outcomes=["outcome"],
    )
    income_star = np.array([10.0, np.nan, 12.0, np.nan, 15.0, 18.0, np.nan, 20.0])
    data = {
        "region": np.array([0, 0, 1, 1, 0, 1, 0, 1]),
        "system_version": np.array([1, 0, 1, 0, 1, 1, 0, 1]),
        "outcome": np.array([1.2, 0.8, 1.5, 0.7, 1.8, 2.0, 0.9, 2.1]),
        "R_income": np.array([1, 0, 1, 0, 1, 1, 0, 1]),
        "income_star": income_star,
    }

    assessment = assess_administrative_missingness(graph=graph, data=data)

    assert assessment.scenario_family is AdministrativeMissingnessScenarioFamily.SYSTEM_CHANGE_BASED
    assert assessment.scenario_class is AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK
    assert assessment.status is MissingnessAssessmentStatus.RECOVERABLE
    assert assessment.testability_audit is not None
    assert assessment.testability_audit.implications_tested >= 0


def test_system_change_builder_defaults_office_outage_to_service_unavailable():
    graph = build_system_change_based_mgraph(
        substantive_vars=["income", "outcome"],
        directed_edges=[("income", "outcome")],
        target_variables=["income"],
        time_variable="event_month",
        office_availability_covariates=["office_open_flag"],
    )

    assessment = assess_administrative_missingness(graph=graph)

    assert (
        assessment.scenario_class
        is AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED
    )
    assert assessment.status is MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE
    assert assessment.missingness_unit_scope is AdministrativeMissingnessUnitScope.TIME_WINDOW


def test_linkage_failure_assessment_is_partially_recoverable_with_validation_subset():
    graph = build_mgraph(
        substantive_vars=["survey_income", "admin_earnings", "identifier_quality", "link_success"],
        directed_edges=[
            ("survey_income", "admin_earnings"),
            ("identifier_quality", "link_success"),
        ],
        missingness_map={"admin_earnings": MissingnessKind.MAR},
        missingness_edges=[("link_success", "R_admin_earnings")],
    )
    graph = attach_administrative_missingness_metadata(
        graph,
        AdministrativeMissingnessMetadata(
            scenario_family=AdministrativeMissingnessScenarioFamily.HYBRID,
            scenario_class=AdministrativeMissingnessClass.LINKAGE_FAILURE,
            missingness_direction=AdministrativeMissingnessDirection.NOT_LINKED,
            missingness_unit_scope=AdministrativeMissingnessUnitScope.LINK,
            target_variables=("admin_earnings",),
            identifier_quality_covariates=("identifier_quality",),
            validation_subset_available=True,
            evidence_refs=("artifact://linkage/validation",),
        ),
    )

    assessment = assess_administrative_missingness(graph=graph)

    assert assessment.scenario_class is AdministrativeMissingnessClass.LINKAGE_FAILURE
    assert assessment.status is MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE
    assert assessment.estimands_at_risk[0].scope == "linked_population"
    assert assessment.recommended_method_stack[:2] == (
        "probabilistic_linkage_with_uncertainty",
        "ipw_on_link_success",
    )
    assert assessment.evidence[0].ref == "artifact://linkage/validation"


def test_retention_expired_assessment_blocks_point_recovery_without_window_metadata():
    graph = build_mgraph(
        substantive_vars=["benefit_amount", "event_time", "retention_rule"],
        directed_edges=[("event_time", "benefit_amount"), ("event_time", "retention_rule")],
        missingness_map={"benefit_amount": MissingnessKind.MAR},
        missingness_edges=[("retention_rule", "R_benefit_amount")],
    )
    graph = attach_administrative_missingness_metadata(
        graph,
        AdministrativeMissingnessMetadata(
            scenario_family=AdministrativeMissingnessScenarioFamily.HYBRID,
            scenario_class=AdministrativeMissingnessClass.RETENTION_EXPIRED,
            missingness_direction=AdministrativeMissingnessDirection.DELETED,
            missingness_unit_scope=AdministrativeMissingnessUnitScope.TIME_WINDOW,
            target_variables=("benefit_amount",),
            time_variable="event_time",
            retention_window_observed=False,
            retention_schedule_id="retention_v1",
        ),
    )

    assessment = assess_administrative_missingness(graph=graph)

    assert assessment.status is MissingnessAssessmentStatus.NOT_RECOVERABLE
    assert assessment.target_population_after_restriction is not None
    assert assessment.recommended_method_stack == (
        "restricted_estimand",
        "monotone_bounds",
    )


def test_processing_backlog_assessment_requires_nowcast_style_repair():
    graph = build_mgraph(
        substantive_vars=["award_amount", "event_month", "backlog_batch"],
        directed_edges=[("event_month", "backlog_batch")],
        missingness_map={"award_amount": MissingnessKind.MAR},
        missingness_edges=[("backlog_batch", "R_award_amount")],
    )
    graph = attach_administrative_missingness_metadata(
        graph,
        AdministrativeMissingnessMetadata(
            scenario_family=AdministrativeMissingnessScenarioFamily.HYBRID,
            scenario_class=AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG,
            missingness_direction=AdministrativeMissingnessDirection.DELAYED,
            missingness_unit_scope=AdministrativeMissingnessUnitScope.EXTRACT,
            target_variables=("award_amount",),
            time_variable="event_month",
            processing_lag_covariates=("backlog_batch",),
            matured_cohorts_observed=True,
        ),
    )

    assessment = assess_administrative_missingness(graph=graph)

    assert assessment.status is MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE
    assert assessment.recommended_method_stack[:2] == (
        "lag_adjusted_ipw",
        "nowcasting",
    )
    assert assessment.sensitivity_plan


def test_assessment_populates_full_law_identification_metadata_for_query():
    graph = build_registration_based_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        target_variables=["X"],
        registration_indicator="registration_flag",
        eligibility_covariates=["eligibility_score"],
        population_frame_observed=True,
    )

    assessment = assess_administrative_missingness(
        graph=graph,
        treatment="X",
        outcome="Y",
    )

    full_law = assessment.metadata.get("full_law_identification")
    assert isinstance(full_law, dict)
    assert full_law["status"] == "identified"
    assert full_law["treatment"] == ["X"]
    assert full_law["outcome"] == ["Y"]


def test_administrative_missingness_assessment_foundry_method_returns_report():
    graph = build_registration_based_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        target_variables=["X"],
        registration_indicator="registration_flag",
        eligibility_covariates=["eligibility_score"],
        population_frame_observed=True,
    )

    result = AdministrativeMissingnessAssessment.pure_step(
        {"mgraph_data": graph.model_dump(mode="json")},
        {"treatment": ["X"], "outcome": ["Y"]},
    )

    report = result["assessment_report"]
    assert report["scenario_family"] == "registration_based"
    assert report["status"] == "recoverable"
    assert report["metadata"]["full_law_identification"]["status"] == "identified"


# ---------------------------------------------------------------------------
# T7: ordered_recovery returns EstimandAST with ProductNode root
# ---------------------------------------------------------------------------


def test_ordered_recovery_mcar_returns_estimand_ast():
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import ordered_recovery
    from polisyos.ir.analytics.estimand import EstimandAST, ProductNode

    graph = make_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    estimand = ordered_recovery(graph=graph, mgraph_meta=meta)

    assert isinstance(estimand, EstimandAST)
    assert isinstance(estimand.root, ProductNode)
    assert estimand.identification_method == "ordered_recovery"


# ---------------------------------------------------------------------------
# T8: ordered_recovery respects topological order
# ---------------------------------------------------------------------------


def test_ordered_recovery_topological_order():
    """X → Y: X must appear before Y in the recovery factor sequence."""
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import ordered_recovery
    from polisyos.ir.analytics.estimand import ProductNode, RecoveredDistNode

    graph = make_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    estimand = ordered_recovery(graph=graph, mgraph_meta=meta)

    assert isinstance(estimand.root, ProductNode)
    variables_in_order = [
        f.variable for f in estimand.root.factors if isinstance(f, RecoveredDistNode)
    ]
    # X has no parent in the DAG, Y has X as parent → X must come first
    assert variables_in_order.index("X") < variables_in_order.index("Y")


# ---------------------------------------------------------------------------
# T9: ordered_recovery generates one proof step per substantive variable
# ---------------------------------------------------------------------------


def test_ordered_recovery_proof_steps_count():
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        test_recoverability,
    )

    graph = make_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = test_recoverability(
        query_vars=frozenset(meta.substantive_vars),
        graph=graph,
        mgraph_meta=meta,
    )
    # One proof step per query variable (MGRAPH_RECOVERABLE_VAR or MGRAPH_TRIVIALLY_OBSERVED)
    recov_steps = [
        s
        for s in result.proof_steps
        if s.rule_name in ("MGRAPH_RECOVERABLE_VAR", "MGRAPH_TRIVIALLY_OBSERVED")
    ]
    assert len(recov_steps) == len(meta.substantive_vars)


# ---------------------------------------------------------------------------
# T10: MCAR factor has correct missingness_kind
# ---------------------------------------------------------------------------


def test_ordered_recovery_missingness_kind_in_factors():
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import ordered_recovery
    from polisyos.ir.analytics.estimand import ProductNode, RecoveredDistNode

    graph = make_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    estimand = ordered_recovery(graph=graph, mgraph_meta=meta)

    assert isinstance(estimand.root, ProductNode)
    x_factor = next(
        (
            f
            for f in estimand.root.factors
            if isinstance(f, RecoveredDistNode) and f.variable == "X"
        ),
        None,
    )
    assert x_factor is not None
    assert x_factor.missingness_kind == "mcar"
    assert x_factor.missingness_indicator == "R_X"
    assert x_factor.proxy_variable == "X_star"


# ---------------------------------------------------------------------------
# T11: full_law_identify with MCAR simple graph → IDENTIFIED
# ---------------------------------------------------------------------------


def test_full_law_identify_mcar_simple():
    from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import full_law_identify

    graph = make_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = full_law_identify(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        mgraph_meta=meta,
    )
    assert result.status == IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert result.algorithm_version == "full_law_v1"


# ---------------------------------------------------------------------------
# T12: full_law_identify with MNAR X → NOT_RECOVERABLE
# ---------------------------------------------------------------------------


def test_full_law_identify_mnar_blocked():
    from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import full_law_identify

    graph = make_mnar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = full_law_identify(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        mgraph_meta=meta,
    )
    assert result.status == IdentificationStatus.NOT_RECOVERABLE
    assert result.estimand_ast is None


# ---------------------------------------------------------------------------
# T13: full_law_identify with confounded MCAR → HEDGE_FOUND (Stage 2 fails)
# ---------------------------------------------------------------------------


def test_full_law_identify_hedge_stage2():
    from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import full_law_identify

    graph = make_confounded_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = full_law_identify(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        mgraph_meta=meta,
    )
    # Stage 1 passes (MCAR → recoverable), Stage 2 fails (latent confounder)
    assert result.status in (
        IdentificationStatus.HEDGE_FOUND,
        IdentificationStatus.ORACLE_NEEDED,
    )


# ---------------------------------------------------------------------------
# T14: full_law_identify proof_steps contain both STAGE1 and STAGE2 entries
# ---------------------------------------------------------------------------


def test_full_law_identify_proof_steps_include_both_stages():
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import full_law_identify

    graph = make_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = full_law_identify(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        mgraph_meta=meta,
    )
    rule_names = {s.rule_name for s in result.proof_steps}
    assert "FULL_LAW_STAGE1_PASS" in rule_names
    assert "FULL_LAW_STAGE2" in rule_names


def test_full_law_identify_soft_policy_routes_through_policy_id():
    from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import full_law_identify
    from polisyos.ir.analytics.estimand import StochasticInterventionNode, StochasticPolicy

    graph = make_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = full_law_identify(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        mgraph_meta=meta,
        policy=StochasticPolicy(policy_type="soft", policy_expr="pi(X)"),
    )

    assert result.status == IdentificationStatus.IDENTIFIED
    assert result.estimand_ast is not None
    assert isinstance(result.estimand_ast.root, StochasticInterventionNode)
    assert "FULL_LAW_STAGE2" in {step.rule_name for step in result.proof_steps}


def test_joint_recoverability_full_law_identified_and_recoverable():
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        identify_joint_recoverability,
    )
    from polisyos.ir.analytics.recoverability import JointDecisionStatus

    graph = make_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    decision = identify_joint_recoverability(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        mgraph_meta=meta,
    )

    assert decision.verdict is JointDecisionStatus.IDENTIFIED_AND_RECOVERABLE
    assert decision.recoverability.status.value == "recoverable"
    assert decision.recoverability.recovery_scope.value == "full_law"
    assert decision.recoverability.recovery_expression_ast is not None


def test_joint_recoverability_direct_query_survives_irrelevant_mnar():
    """Full law is blocked by Z, but P(Y|do(X)) only needs recoverable X/Y."""
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        identify_joint_recoverability,
    )
    from polisyos.ir.analytics.recoverability import JointDecisionStatus

    graph = make_irrelevant_mnar_mgraph()
    meta = extract_mgraph_metadata(graph)
    decision = identify_joint_recoverability(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        mgraph_meta=meta,
    )

    assert decision.verdict is JointDecisionStatus.IDENTIFIED_AND_RECOVERABLE
    assert decision.recoverability.recovery_scope.value == "causal_query"
    assert decision.metadata["full_law_recoverability"]["status"] == (
        "recoverable_under_assumptions"
    )
    assert decision.recoverability.metadata["required_recoverable_variables"] == ["X", "Y"]


def test_joint_recoverability_identified_but_not_recoverable_has_repairs():
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        identify_joint_recoverability,
    )
    from polisyos.ir.analytics.negative_certificate import BlockingType
    from polisyos.ir.analytics.recoverability import JointDecisionStatus

    graph = make_mnar_mgraph()
    meta = extract_mgraph_metadata(graph)
    decision = identify_joint_recoverability(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
        mgraph_meta=meta,
    )

    assert decision.verdict is JointDecisionStatus.IDENTIFIED_BUT_NOT_RECOVERABLE
    assert "R_X" in decision.recoverability.blocking_r_nodes
    assert decision.recoverability.minimal_repair_sets
    assert decision.negative_certificate is not None
    assert decision.negative_certificate.blocking_type is BlockingType.MISSINGNESS_NOT_RECOVERABLE


def test_causal_engine_identify_joint_exposes_joint_certificate():
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
    from polisyos.ir.analytics.recoverability import JointDecisionStatus

    graph = make_mcar_mgraph()
    decision = CausalEngine().identify_joint("X", "Y", graph)

    assert decision.verdict is JointDecisionStatus.IDENTIFIED_AND_RECOVERABLE
    assert decision.target_query == "P(Y|do(X))"


def test_causal_engine_identify_legacy_path_uses_joint_direct_recovery():
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
    from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
    from polisyos.ir.analytics.negative_certificate import NegativeCertificate

    graph = make_irrelevant_mnar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = CausalEngine().identify("X", "Y", graph, mgraph_meta=meta)

    assert not isinstance(result, NegativeCertificate)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.metadata["recoverability_certificate"]["recovery_scope"] == "causal_query"
    assert result.metadata["joint_decision"]["verdict"] == "IdentifiedAndRecoverable"


def test_causal_engine_identify_auto_extracts_mgraph_metadata_for_joint_direct_recovery():
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
    from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
    from polisyos.ir.analytics.negative_certificate import NegativeCertificate

    graph = make_irrelevant_mnar_mgraph()
    result = CausalEngine().identify("X", "Y", graph)

    assert not isinstance(result, NegativeCertificate)
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.metadata["recoverability_certificate"]["recovery_scope"] == "causal_query"
    assert result.metadata["joint_decision"]["verdict"] == "IdentifiedAndRecoverable"


def test_causal_engine_identify_legacy_path_returns_missingness_certificate():
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
    from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate

    graph = make_mnar_mgraph()
    meta = extract_mgraph_metadata(graph)
    result = CausalEngine().identify("X", "Y", graph, mgraph_meta=meta)

    assert isinstance(result, NegativeCertificate)
    assert result.blocking_type is BlockingType.MISSINGNESS_NOT_RECOVERABLE
    assert result.quantitative_diagnostics["recoverability"]["status"] == (
        "recoverable_under_assumptions"
    )


def test_causal_engine_identify_auto_extracts_mgraph_metadata_for_missingness_blocker():
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
    from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate

    graph = make_mnar_mgraph()
    result = CausalEngine().identify("X", "Y", graph)

    assert isinstance(result, NegativeCertificate)
    assert result.blocking_type is BlockingType.MISSINGNESS_NOT_RECOVERABLE
    assert result.quantitative_diagnostics["recoverability"]["status"] == (
        "recoverable_under_assumptions"
    )


# ---------------------------------------------------------------------------
# T15: build_mgraph factory with MCAR produces valid CausalGraphModel
# ---------------------------------------------------------------------------


def test_build_mgraph_factory_mcar_valid():
    graph = build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        missingness_map={"X": MissingnessKind.MCAR},
    )
    assert graph.graph_type == GraphType.MGRAPH
    assert "R_X" in graph.nodes
    assert "X_star" in graph.nodes
    assert "X" in graph.nodes
    assert "Y" in graph.nodes
    # Edge R_X → X_star must exist
    directed = {
        (e.src, e.dst)
        for e in graph.edges
        if e.mark_src == EdgeMark.TAIL and e.mark_dst == EdgeMark.ARROW
    }
    assert ("R_X", "X_star") in directed


# ---------------------------------------------------------------------------
# T16: build_mgraph factory with MNAR adds X → R_X edge
# ---------------------------------------------------------------------------


def test_build_mgraph_factory_mnar_has_edge():
    graph = build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[("X", "Y")],
        missingness_map={"X": MissingnessKind.MNAR},
    )
    directed = {
        (e.src, e.dst)
        for e in graph.edges
        if e.mark_src == EdgeMark.TAIL and e.mark_dst == EdgeMark.ARROW
    }
    assert ("X", "R_X") in directed


# ---------------------------------------------------------------------------
# T17: MGRAPH validator rejects graph with missing proxy node
# ---------------------------------------------------------------------------


def test_mgraph_validator_missing_proxy_raises():
    """Constructing a CausalGraphModel(MGRAPH) with R_X but no X_star → ValueError."""
    with pytest.raises(ValueError, match="X_star"):
        CausalGraphModel(
            graph_type=GraphType.MGRAPH,
            nodes=["X", "Y", "R_X"],  # X_star is missing
            edges=[CausalEdge(src="X", dst="Y")],
        )


# ---------------------------------------------------------------------------
# T18: All three Foundry methods' pure_step return expected top-level keys
# ---------------------------------------------------------------------------


def test_foundry_methods_pure_step_all_three():
    from polisyos.foundry.methods.catalog.causal.missing_data import (
        FullLawIdentify,
        OrderedRecovery,
        RecoverabilityTest,
    )

    graph = make_mcar_mgraph()
    graph_dict = graph.model_dump(mode="json")

    # RecoverabilityTest
    out_rt = RecoverabilityTest.pure_step(
        {"mgraph_data": graph_dict},
        {"query_variables": [], "dataset_ref": None},
    )
    assert "recoverability_result" in out_rt
    assert "status" in out_rt["recoverability_result"]
    assert out_rt["recoverability_result"]["status"] == "recoverable"

    # OrderedRecovery
    out_or = OrderedRecovery.pure_step(
        {"mgraph_data": graph_dict},
        {"dataset_ref": None},
    )
    assert "recovery_estimand" in out_or
    assert "ordered_recovery_steps" in out_or
    assert out_or["recovery_estimand"] is not None

    # FullLawIdentify
    out_fl = FullLawIdentify.pure_step(
        {"mgraph_data": graph_dict, "treatment": "X", "outcome": "Y"},
        {"oracle": "none", "dataset_ref": None},
    )
    assert "identification_result" in out_fl
    assert "status" in out_fl["identification_result"]
    assert out_fl["identification_result"]["status"] == "identified"


# ---------------------------------------------------------------------------
# T19: testable_implications derives observable CI claims only
# ---------------------------------------------------------------------------


def test_testable_implications_are_observed_only():
    from polisyos.foundry.methods.catalog.causal.missing_data import (
        testable_implications,
    )

    graph = make_mcar_mgraph()
    meta = extract_mgraph_metadata(graph)
    implications = testable_implications(graph, meta, max_conditioning_set_size=1)

    observed = set(meta.fully_observed_vars)
    observed.update(p.proxy_name for p in meta.proxy_nodes)
    observed.update(f"R_{r.target_variable}" for r in meta.r_nodes)

    assert implications
    assert all({imp.x, imp.y}.issubset(observed) for imp in implications)
    assert all(set(imp.z).issubset(observed) for imp in implications)
    assert any({imp.x, imp.y} == {"R_X", "Y"} and imp.z == () for imp in implications)


# ---------------------------------------------------------------------------
# T20: continuous route uses partial correlation and BH correction
# ---------------------------------------------------------------------------


def test_mgraph_implications_continuous_route():
    from polisyos.foundry.methods.catalog.causal.missing_data import (
        ConditionalIndependence,
        test_mgraph_implications,
    )

    graph = build_mgraph(
        substantive_vars=["X", "Y", "Y_dep", "Z"],
        directed_edges=[],
        missingness_map={},
    )
    meta = extract_mgraph_metadata(graph)
    rng = np.random.default_rng(7)
    n = 500
    z = rng.normal(size=n)
    x = z + 0.15 * rng.normal(size=n)
    y = z + 0.15 * rng.normal(size=n)
    y_dep = x + 0.3 * rng.normal(size=n)
    data = {"X": x, "Y": y, "Y_dep": y_dep, "Z": z}

    implications = [
        ConditionalIndependence(x="X", y="Y", z=("Z",)),
        ConditionalIndependence(x="X", y="Y_dep", z=("Z",)),
    ]
    report = test_mgraph_implications(
        graph=graph,
        mgraph_meta=meta,
        data=data,
        implications=implications,
        alpha=0.05,
    )

    assert report.test_method == "adaptive_mgraph_ci"
    assert report.results[0].test_name == "partial_correlation"
    assert report.results[0].metadata["route"] == "partial_correlation"
    assert report.results[0].passed is True
    assert report.results[1].passed is False
    assert report.implications_tested == 2
    assert report.implications_passed == 1
    assert report.overall_valid is False


# ---------------------------------------------------------------------------
# T21: categorical route uses G-test / conditional G-test
# ---------------------------------------------------------------------------


def test_mgraph_implications_categorical_route():
    from polisyos.foundry.methods.catalog.causal.missing_data import (
        ConditionalIndependence,
        test_mgraph_implications,
    )

    graph = build_mgraph(
        substantive_vars=["X", "Y", "Y_dep", "Z"],
        directed_edges=[],
        missingness_map={},
    )
    meta = extract_mgraph_metadata(graph)
    rng = np.random.default_rng(17)
    n = 600
    z = rng.integers(0, 2, size=n).astype(str)
    x = np.where(z == "0", rng.integers(0, 3, size=n), rng.integers(0, 3, size=n)).astype(str)
    y = np.where(z == "0", rng.integers(0, 3, size=n), rng.integers(0, 3, size=n)).astype(str)
    y_dep = x.copy()
    data = {"X": x, "Y": y, "Y_dep": y_dep, "Z": z}

    implications = [
        ConditionalIndependence(x="X", y="Y", z=("Z",)),
        ConditionalIndependence(x="X", y="Y_dep", z=("Z",)),
    ]
    report = test_mgraph_implications(
        graph=graph,
        mgraph_meta=meta,
        data=data,
        implications=implications,
        alpha=0.05,
    )

    assert report.results[0].test_name == "conditional_g_test"
    assert report.results[0].metadata["route"] == "conditional_g_test"
    assert report.results[0].passed is True
    assert report.results[1].passed is False
    assert report.results[1].adjusted_p_value <= 0.05
    assert report.warnings == []


def test_mgraph_implications_categorical_route_preserves_dp_calibration(tmp_path):
    from polisyos.foundry.methods.catalog.causal.missing_data import (
        ConditionalIndependence,
        MGraphImplicationTester,
        test_mgraph_implications,
    )

    graph = build_mgraph(
        substantive_vars=["X", "Y_dep", "Z"],
        directed_edges=[],
        missingness_map={},
    )
    meta = extract_mgraph_metadata(graph)
    rng = np.random.default_rng(23)
    n = 600
    z = rng.integers(0, 2, size=n).astype(str)
    x = np.where(z == "0", rng.integers(0, 3, size=n), rng.integers(0, 3, size=n)).astype(str)
    y_dep = x.copy()
    data = {"X": x, "Y_dep": y_dep, "Z": z}

    implications = [ConditionalIndependence(x="X", y="Y_dep", z=("Z",))]
    report = test_mgraph_implications(
        graph=graph,
        mgraph_meta=meta,
        data=data,
        implications=implications,
        alpha=0.05,
        dp_context={
            "mechanism": "gaussian_counts",
            "epsilon": 0.7,
            "delta": 1e-6,
        },
        judge_threshold_registry_root=str(tmp_path),
    )

    result = report.results[0]
    assert result.test_name == "conditional_g_test"
    assert result.metadata["route"] == "conditional_g_test"
    assert result.metadata["ci_test_impl"] == "categorical_ci"
    assert result.metadata["calibration_mode"] == "analytic_weighted_chi2"
    assert result.metadata["dp_context_summary"]["mechanism"] == "gaussian_counts"
    assert result.metadata["threshold_registry_scope"]["family"] == "categorical_ci"

    out = MGraphImplicationTester.pure_step(
        {"mgraph_data": graph.model_dump(mode="json"), "data": data},
        {
            "implications": implications,
            "alpha": 0.05,
            "dp_context": {
                "mechanism": "gaussian_counts",
                "epsilon": 0.7,
                "delta": 1e-6,
            },
            "judge_threshold_registry_root": str(tmp_path),
        },
    )
    result_payload = out["test_report"]["results"][0]["metadata"]
    assert result_payload["dp_context_summary"]["mechanism"] == "gaussian_counts"
    assert result_payload["threshold_registry_scope"]["family"] == "categorical_ci"


# ---------------------------------------------------------------------------
# T22: mixed route uses kernel-based CMI-style approximation
# ---------------------------------------------------------------------------


def test_mgraph_implications_mixed_route_and_serialization():
    from polisyos.foundry.methods.catalog.causal.missing_data import (
        ConditionalIndependence,
        MGraphImplicationTester,
        test_mgraph_implications,
    )

    graph = build_mgraph(
        substantive_vars=["X", "Y", "Y_dep", "Z"],
        directed_edges=[],
        missingness_map={},
    )
    meta = extract_mgraph_metadata(graph)
    rng = np.random.default_rng(29)
    n = 450
    z = rng.integers(0, 2, size=n).astype(str)
    x = rng.normal(size=n) + (z == "1").astype(float) * 1.5
    y = rng.normal(size=n) + (z == "1").astype(float) * 1.5
    y_dep = x + 0.05 * rng.normal(size=n)
    data = {"X": x, "Y": y, "Y_dep": y_dep, "Z": z}

    implications = [
        ConditionalIndependence(x="X", y="Y", z=("Z",)),
        ConditionalIndependence(x="X", y="Y_dep", z=("Z",)),
    ]
    report = test_mgraph_implications(
        graph=graph,
        mgraph_meta=meta,
        data=data,
        implications=implications,
        alpha=0.05,
    )

    assert report.results[0].test_name == "kci_mixed"
    assert report.results[0].metadata["route"] == "kci_mixed"
    assert report.results[0].passed is True
    assert report.results[1].passed is False
    assert report.warnings
    assert any("kci_mixed" in warning for warning in report.warnings)

    graph_dict = graph.model_dump(mode="json")
    out = MGraphImplicationTester.pure_step(
        {"mgraph_data": graph_dict, "data": data},
        {"implications": implications, "alpha": 0.05, "max_conditioning_set_size": 1},
    )
    assert out["test_report"]["test_method"] == "adaptive_mgraph_ci"
    assert out["test_report"]["results"][0]["test_name"] == "kci_mixed"


# ---------------------------------------------------------------------------
# T23: missing columns fail loudly
# ---------------------------------------------------------------------------


def test_mgraph_implications_missing_column_raises():
    from polisyos.foundry.methods.catalog.causal.missing_data import (
        ConditionalIndependence,
        test_mgraph_implications,
    )

    graph = build_mgraph(
        substantive_vars=["X", "Y"],
        directed_edges=[],
        missingness_map={},
    )
    meta = extract_mgraph_metadata(graph)
    data = {"X": np.array([0.0, 1.0, 0.5]), "Y": np.array([1.0, 0.0, 0.25])}

    with pytest.raises(KeyError, match="Missing data column"):
        test_mgraph_implications(
            graph=graph,
            mgraph_meta=meta,
            data=data,
            implications=[ConditionalIndependence(x="X", y="Z", z=())],
            alpha=0.05,
        )
