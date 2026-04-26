"""Tests for CausalQueryValidator (Track F)."""

import pytest

from polisyos.foundry.methods.catalog.causal.query_validator import CausalQueryValidator
from polisyos.ir.analytics.causal import ProofBundle
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.dynamic_causal_semantics import (
    ForecastAnnouncementWindow,
    ForecastContrastSpec,
    ForecastIdentificationMethod,
    ForecastIdentifiedComponent,
    ForecastInterventionQuery,
    ForecastSemanticsClass,
    ForecastUpdateOperatorKind,
)
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    OperatorApplyNode,
    OperatorTargetNode,
    SideCondition,
    SideConditionKind,
    SpaceRef,
    make_backdoor_estimand,
)
from polisyos.ir.analytics.knowledge_base import DataKnowledgeBase, DatasetEntry
from polisyos.ir.analytics.query_validation_report import ValidationSeverity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dag(*edges: tuple[str, str]) -> CausalGraphModel:
    """Build a minimal DAG from (src, dst) pairs."""
    nodes = sorted({n for pair in edges for n in pair})
    causal_edges = [
        CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW) for s, d in edges
    ]
    return CausalGraphModel(graph_type=GraphType.DAG, nodes=nodes, edges=causal_edges)


def _make_single_node_dag(node: str) -> CausalGraphModel:
    return CausalGraphModel(graph_type=GraphType.DAG, nodes=[node], edges=[])


def _simple_estimand(treatment: str = "X", outcome: str = "Y") -> EstimandAST:
    return make_backdoor_estimand(
        treatment=treatment,
        outcome=outcome,
        adjustment_set=("Z",),
        dataset_ref="ds1",
    )


def _simple_kb(treatment: str = "X", outcome: str = "Y") -> DataKnowledgeBase:
    entry = DatasetEntry(
        dataset_ref="ds1",
        variables=(treatment, outcome, "Z"),
        domain=DistributionDomain.SOURCE,
        n_obs=1000,
    )
    return DataKnowledgeBase(datasets=(entry,))


# ---------------------------------------------------------------------------
# Test: valid minimal DAG (no KB)
# ---------------------------------------------------------------------------


class TestValidMinimalDag:
    def test_valid_minimal_dag_no_kb(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()
        report = CausalQueryValidator().validate(graph, ast)
        assert report.is_valid is True
        assert report.errors == ()
        assert report.warnings == ()

    def test_valid_with_kb(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()
        kb = _simple_kb()
        report = CausalQueryValidator().validate(graph, ast, kb)
        assert report.is_valid is True
        assert report.errors == ()

    def test_report_has_query_str(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()
        report = CausalQueryValidator().validate(graph, ast)
        assert "Y" in report.query_str
        assert "X" in report.query_str

    def test_report_has_checked_at(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()
        report = CausalQueryValidator().validate(graph, ast)
        assert report.checked_at != ""


# ---------------------------------------------------------------------------
# F2: Graph acyclicity
# ---------------------------------------------------------------------------


class TestGraphAcyclicity:
    def test_cycle_in_dag_is_error(self):
        # X → Y → X (cycle)
        nodes = ["X", "Y"]
        edges = [
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="Y", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ]
        # Pydantic DAG validator would reject this, so build a PAG and swap graph_type
        # to simulate a DAG that bypassed model_validator (e.g. loaded from JSON)
        graph = CausalGraphModel(graph_type=GraphType.PAG, nodes=nodes, edges=edges)
        # Override graph_type to DAG via model_copy to simulate the scenario
        graph_as_dag = graph.model_copy(update={"graph_type": GraphType.DAG})

        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=(), dataset_ref=None
        )
        report = CausalQueryValidator().validate(graph_as_dag, ast)
        codes = [e.code for e in report.errors]
        assert "GRAPH_CYCLE" in codes

    def test_pag_with_directed_cycle_is_warning_not_error(self):
        nodes = ["X", "Y"]
        edges = [
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="Y", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ]
        graph = CausalGraphModel(graph_type=GraphType.PAG, nodes=nodes, edges=edges)
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=(), dataset_ref=None
        )
        report = CausalQueryValidator().validate(graph, ast)
        error_codes = [e.code for e in report.errors]
        warning_codes = [w.code for w in report.warnings]
        assert "GRAPH_CYCLE" not in error_codes
        assert "GRAPH_CYCLE" in warning_codes

    def test_cpdag_with_directed_cycle_is_warning(self):
        nodes = ["A", "B"]
        edges = [
            CausalEdge(src="A", dst="B", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="B", dst="A", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ]
        graph = CausalGraphModel(graph_type=GraphType.CPDAG, nodes=nodes, edges=edges)
        ast = make_backdoor_estimand(
            treatment="A", outcome="B", adjustment_set=(), dataset_ref=None
        )
        report = CausalQueryValidator().validate(graph, ast)
        warning_codes = [w.code for w in report.warnings]
        assert "GRAPH_CYCLE" in warning_codes
        error_codes = [e.code for e in report.errors]
        assert "GRAPH_CYCLE" not in error_codes


# ---------------------------------------------------------------------------
# F2: treatment / outcome membership
# ---------------------------------------------------------------------------


class TestVariablesMembership:
    def test_treatment_missing_from_graph(self):
        graph = _make_single_node_dag("Y")
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=(), dataset_ref=None
        )
        report = CausalQueryValidator().validate(graph, ast)
        codes = [e.code for e in report.errors]
        assert "TREATMENT_MISSING" in codes

    def test_outcome_missing_from_graph(self):
        graph = _make_single_node_dag("X")
        ast = make_backdoor_estimand(
            treatment="X", outcome="Y", adjustment_set=(), dataset_ref=None
        )
        report = CausalQueryValidator().validate(graph, ast)
        codes = [e.code for e in report.errors]
        assert "OUTCOME_MISSING" in codes

    def test_treatment_equals_outcome(self):
        graph = _make_single_node_dag("X")
        ast = make_backdoor_estimand(
            treatment="X", outcome="X", adjustment_set=(), dataset_ref=None
        )
        report = CausalQueryValidator().validate(graph, ast)
        codes = [e.code for e in report.errors]
        assert "TREATMENT_EQUALS_OUTCOME" in codes

    def test_unknown_variable_in_estimand_is_warning(self):
        # Graph only has X and Y; estimand also references Z (adjustment)
        graph = _make_dag(("X", "Y"))
        ast = _simple_estimand()  # uses Z in adjustment set
        report = CausalQueryValidator().validate(graph, ast)
        warning_codes = [w.code for w in report.warnings]
        assert "UNKNOWN_VARIABLE" in warning_codes

    def test_s_node_dangling_uses_specific_code(self):
        # Variable named "S" should get S_NODE_DANGLING rather than UNKNOWN_VARIABLE
        graph = _make_dag(("X", "Y"))
        # Build an estimand that references "S" variable
        ast = EstimandAST(
            query_str="P(Y|do(X))",
            root=DistributionRef(
                domain=DistributionDomain.SOURCE,
                variables=("Y",),
                conditioning=("X", "S"),
            ),
            treatment="X",
            outcome="Y",
            all_variables=("X", "Y", "S"),
            identification_method="backdoor",
        )
        report = CausalQueryValidator().validate(graph, ast)
        warning_codes = [w.code for w in report.warnings]
        assert "S_NODE_DANGLING" in warning_codes


# ---------------------------------------------------------------------------
# Forecast-as-treatment query lane
# ---------------------------------------------------------------------------


def _forecast_query(**overrides) -> ForecastInterventionQuery:
    payload = {
        "message_var": "A_tau",
        "announcement_time": "2026-04-25T10:00:00Z",
        "semantics_class": ForecastSemanticsClass.DELPHIC,
        "expectation_target": "B_tau_plus",
        "outcome_target": "Y",
        "contrast_spec": ForecastContrastSpec(
            message="published_soft_landing_forecast",
            baseline_message="baseline_projection",
        ),
        "decomposition_goal": ForecastIdentifiedComponent.EXPECTATION_ONLY,
        "update_operator_kind": ForecastUpdateOperatorKind.BAYES,
        "decomposition_method": ForecastIdentificationMethod.LOCAL_INDEPENDENCE_REWEIGHTING,
        "pre_announcement_window": ForecastAnnouncementWindow(
            start="2026-04-25T09:55:00Z",
            end="2026-04-25T10:00:00Z",
        ),
        "post_announcement_window": ForecastAnnouncementWindow(
            start="2026-04-25T10:00:00Z",
            end="2026-04-25T10:05:00Z",
        ),
        "positivity_claimed": True,
        "censoring_assessed": True,
        "required_observables": ("A_tau", "B_tau_plus", "Y"),
    }
    payload.update(overrides)
    return ForecastInterventionQuery(**payload)


class TestForecastInterventionQuery:
    def test_valid_forecast_query_has_no_errors(self):
        graph = _make_dag(("A_tau", "B_tau_plus"), ("B_tau_plus", "Y"))
        report = CausalQueryValidator().validate_forecast_intervention_query(
            graph,
            _forecast_query(),
        )

        assert report.is_valid is True
        assert report.errors == ()
        assert "FORECAST_PROOF_BUNDLE_MISSING" in [w.code for w in report.warnings]

    def test_forecast_query_requires_windows_and_update_or_decomposition(self):
        graph = _make_dag(("A_tau", "B_tau_plus"), ("B_tau_plus", "Y"))
        report = CausalQueryValidator().validate_forecast_intervention_query(
            graph,
            _forecast_query(
                update_operator_kind=ForecastUpdateOperatorKind.UNKNOWN,
                decomposition_method=None,
                pre_announcement_window=None,
                post_announcement_window=None,
                positivity_claimed=False,
            ),
        )

        error_codes = [error.code for error in report.errors]
        assert "FORECAST_WINDOW_MISSING" in error_codes
        assert "FORECAST_UPDATE_OR_DECOMPOSITION_MISSING" in error_codes
        assert "FORECAST_POSITIVITY_FAILED" in error_codes

    def test_forecast_query_blocks_hard_action_without_hybrid_semantics(self):
        graph = _make_dag(("A_tau", "B_tau_plus"), ("B_tau_plus", "Y"))
        report = CausalQueryValidator().validate_forecast_intervention_query(
            graph,
            _forecast_query(hard_actions_same_window=("rate_cut",)),
        )

        assert "FORECAST_HARD_ACTION_REQUIRES_HYBRID" in [
            error.code for error in report.errors
        ]

    def test_forecast_query_requires_message_to_expectation_edge(self):
        graph = _make_dag(("A_tau", "Y"), ("B_tau_plus", "Y"))
        report = CausalQueryValidator().validate_forecast_intervention_query(
            graph,
            _forecast_query(),
        )

        assert "FORECAST_EXPECTATION_EDGE_MISSING" in [
            error.code for error in report.errors
        ]


# ---------------------------------------------------------------------------
# F2 KB: dataset presence & domain consistency
# ---------------------------------------------------------------------------


class TestKBStructuralChecks:
    def test_dataset_missing_from_kb(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()  # requires dataset_ref="ds1"
        # KB is empty — no datasets registered
        kb = DataKnowledgeBase(datasets=())
        report = CausalQueryValidator().validate(graph, ast, kb)
        codes = [e.code for e in report.errors]
        assert "DATASET_MISSING" in codes

    def test_domain_mismatch_warning(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()  # DistributionRef uses domain=SOURCE, dataset_ref="ds1"
        # KB has "ds1" as TARGET domain — mismatch
        entry = DatasetEntry(
            dataset_ref="ds1",
            variables=("X", "Y", "Z"),
            domain=DistributionDomain.TARGET,
            n_obs=1000,
        )
        kb = DataKnowledgeBase(datasets=(entry,))
        report = CausalQueryValidator().validate(graph, ast, kb)
        warning_codes = [w.code for w in report.warnings]
        assert "DOMAIN_MISMATCH" in warning_codes

    def test_none_kb_skips_dataset_checks(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()  # requires "ds1"
        # No KB provided — dataset check is skipped
        report = CausalQueryValidator().validate(graph, ast)
        codes = [e.code for e in report.errors]
        assert "DATASET_MISSING" not in codes


# ---------------------------------------------------------------------------
# F3: Feasibility checks
# ---------------------------------------------------------------------------


class TestFeasibilityChecks:
    def test_kb_infeasible_is_error(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()
        # KB has "ds1" but none of the required variables — score will be 0
        entry = DatasetEntry(
            dataset_ref="ds1",
            variables=("A", "B"),  # irrelevant variables
            domain=DistributionDomain.SOURCE,
            n_obs=1000,
        )
        kb = DataKnowledgeBase(datasets=(entry,))
        report = CausalQueryValidator().validate(graph, ast, kb)
        codes = [e.code for e in report.errors]
        assert "KB_INFEASIBLE" in codes

    def test_kb_partial_coverage_is_warning(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        # Estimand has two DistributionRefs: one covered, one not
        # Use a transport estimand to ensure partial coverage
        from polisyos.ir.analytics.estimand import make_transport_reweight_estimand

        ast = make_transport_reweight_estimand(
            treatment="X",
            outcome="Y",
            reweighting_vars=("Z",),
            source_dataset_ref="ds_source",
            target_dataset_ref="ds_target",
        )
        # Only source dataset present → partial coverage
        entry = DatasetEntry(
            dataset_ref="ds_source",
            variables=("X", "Y", "Z"),
            domain=DistributionDomain.SOURCE,
            n_obs=1000,
        )
        kb = DataKnowledgeBase(datasets=(entry,))
        report = CausalQueryValidator().validate(graph, ast, kb)
        warning_codes = [w.code for w in report.warnings]
        assert "KB_PARTIAL" in warning_codes

    def test_small_sample_warning(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()
        entry = DatasetEntry(
            dataset_ref="ds1",
            variables=("X", "Y", "Z"),
            domain=DistributionDomain.SOURCE,
            n_obs=50,  # below threshold of 100
        )
        kb = DataKnowledgeBase(datasets=(entry,))
        report = CausalQueryValidator().validate(graph, ast, kb)
        warning_codes = [w.code for w in report.warnings]
        assert "SMALL_SAMPLE" in warning_codes

    def test_no_small_sample_warning_when_n_obs_none(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()
        entry = DatasetEntry(
            dataset_ref="ds1",
            variables=("X", "Y", "Z"),
            domain=DistributionDomain.SOURCE,
            n_obs=None,  # unknown — should not warn
        )
        kb = DataKnowledgeBase(datasets=(entry,))
        report = CausalQueryValidator().validate(graph, ast, kb)
        warning_codes = [w.code for w in report.warnings]
        assert "SMALL_SAMPLE" not in warning_codes

    def test_positivity_condition_no_data(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()  # has POSITIVITY side condition on X
        # KB has "ds1" but treatment X is NOT in the dataset's variables
        entry = DatasetEntry(
            dataset_ref="ds1",
            variables=("Y", "Z"),  # X missing
            domain=DistributionDomain.SOURCE,
            n_obs=1000,
        )
        kb = DataKnowledgeBase(datasets=(entry,))
        report = CausalQueryValidator().validate(graph, ast, kb)
        warning_codes = [w.code for w in report.warnings]
        assert "POSITIVITY_DATA_ABSENT" in warning_codes

    def test_consistency_condition_no_data(self):
        graph = _make_dag(("X", "Y"))
        # Estimand with CONSISTENCY side condition
        dist = DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=("Y",),
            conditioning=("X",),
            dataset_ref="ds1",
            side_conditions=(SideCondition(kind=SideConditionKind.CONSISTENCY, variables=("X",)),),
        )
        ast = EstimandAST(
            query_str="P(Y|do(X))",
            root=dist,
            treatment="X",
            outcome="Y",
            all_variables=("X", "Y"),
            identification_method="backdoor",
        )
        entry = DatasetEntry(
            dataset_ref="ds1",
            variables=("Y",),  # X missing
            domain=DistributionDomain.SOURCE,
            n_obs=500,
        )
        kb = DataKnowledgeBase(datasets=(entry,))
        report = CausalQueryValidator().validate(graph, ast, kb)
        warning_codes = [w.code for w in report.warnings]
        assert "CONSISTENCY_DATA_ABSENT" in warning_codes

    def test_sutva_condition_emits_no_warning(self):
        graph = _make_dag(("X", "Y"))
        dist = DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=("Y",),
            conditioning=("X",),
            dataset_ref="ds1",
            side_conditions=(SideCondition(kind=SideConditionKind.SUTVA, variables=()),),
        )
        ast = EstimandAST(
            query_str="P(Y|do(X))",
            root=dist,
            treatment="X",
            outcome="Y",
            all_variables=("X", "Y"),
            identification_method="backdoor",
        )
        entry = DatasetEntry(
            dataset_ref="ds1",
            variables=("X", "Y"),
            domain=DistributionDomain.SOURCE,
            n_obs=500,
        )
        kb = DataKnowledgeBase(datasets=(entry,))
        report = CausalQueryValidator().validate(graph, ast, kb)
        # SUTVA is a design assumption; no warning expected for it specifically
        assert report.is_valid is True
        warning_codes = [w.code for w in report.warnings]
        assert "POSITIVITY_DATA_ABSENT" not in warning_codes
        assert "CONSISTENCY_DATA_ABSENT" not in warning_codes


# ---------------------------------------------------------------------------
# QueryValidationReport contract
# ---------------------------------------------------------------------------


class TestReportContract:
    def test_report_to_summary_valid(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()
        kb = _simple_kb()
        report = CausalQueryValidator().validate(graph, ast, kb)
        summary = report.to_summary()
        assert "VALID" in summary

    def test_report_to_summary_invalid(self):
        graph = _make_single_node_dag("Y")
        ast = _simple_estimand()  # treatment X not in graph
        report = CausalQueryValidator().validate(graph, ast)
        summary = report.to_summary()
        assert "INVALID" in summary

    def test_report_has_errors_method(self):
        graph = _make_single_node_dag("Y")
        ast = _simple_estimand()
        report = CausalQueryValidator().validate(graph, ast)
        assert report.has_errors() is True

    def test_report_has_warnings_method(self):
        graph = _make_dag(("X", "Y"))  # Z not in graph
        ast = _simple_estimand()  # Z in adjustment set
        report = CausalQueryValidator().validate(graph, ast)
        assert report.has_warnings() is True

    def test_is_valid_false_when_errors(self):
        graph = _make_single_node_dag("Y")
        ast = _simple_estimand()
        report = CausalQueryValidator().validate(graph, ast)
        assert report.is_valid is False

    def test_error_severity_is_error(self):
        graph = _make_single_node_dag("Y")
        ast = _simple_estimand()
        report = CausalQueryValidator().validate(graph, ast)
        for err in report.errors:
            assert err.severity is ValidationSeverity.ERROR

    def test_warning_severity_is_warning(self):
        graph = _make_dag(("X", "Y"))
        ast = _simple_estimand()
        report = CausalQueryValidator().validate(graph, ast)
        for w in report.warnings:
            assert w.severity is ValidationSeverity.WARNING

    def test_report_is_frozen(self):
        graph = _make_dag(("X", "Y"), ("Z", "Y"), ("Z", "X"))
        ast = _simple_estimand()
        report = CausalQueryValidator().validate(graph, ast)
        with pytest.raises(Exception):
            report.is_valid = True  # type: ignore[misc]

    def test_import_from_causal_package(self):
        from polisyos.foundry.methods.catalog.causal import CausalQueryValidator as CQV

        assert CQV is CausalQueryValidator


def _operator_probe_space(*, kernel_ref: str | None = "gaussian_rbf") -> SpaceRef:
    return SpaceRef(
        space_id="outcome-rkhs",
        kind="rkhs",
        kernel_ref=kernel_ref,
        characteristic=True,
        bounded_evaluation=True,
    )


def _operator_codomain_space() -> SpaceRef:
    return SpaceRef(
        space_id="modifier-rkhs",
        kind="rkhs",
        kernel_ref="linear_kernel",
        universal=True,
        bounded_evaluation=True,
    )


def _operator_ast(*, kernel_ref: str | None = "gaussian_rbf") -> EstimandAST:
    return EstimandAST(
        query_str="operator target",
        root=OperatorTargetNode(
            treatment="X",
            outcome="Y",
            effect_modifier=("V",),
            probe_space_ref=_operator_probe_space(kernel_ref=kernel_ref),
            codomain_space_ref=_operator_codomain_space(),
            operator_semantics="conditional_mean_embedding_operator",
            identification_scope="backdoor",
            operator_regularization="ridge",
        ),
        treatment="X",
        outcome="Y",
        all_variables=("X", "Y", "V"),
    )


class TestOperatorContracts:
    def test_operator_target_requires_probe_kernel(self):
        graph = _make_dag(("X", "Y"), ("V", "Y"))
        report = CausalQueryValidator().validate(graph, _operator_ast(kernel_ref=None))
        error_codes = [e.code for e in report.errors]

        assert "OPERATOR_KERNEL_MISSING" in error_codes

    def test_full_operator_without_proof_bundle_emits_warning(self):
        graph = _make_dag(("X", "Y"), ("V", "Y"))
        report = CausalQueryValidator().validate(graph, _operator_ast())
        warning_codes = [w.code for w in report.warnings]

        assert "OPERATOR_LIFT_REQUIRES_PROOF" in warning_codes

    def test_full_operator_with_uncertified_proof_bundle_is_error(self):
        graph = _make_dag(("X", "Y"), ("V", "Y"))
        proof_bundle = ProofBundle(
            proof_status="identified",
            proof_stratum="A0_trusted",
            theorem_family="id_v1",
            completeness_regime="complete",
            implementation_coverage="declared-scope:id_v1",
        )
        report = CausalQueryValidator().validate(
            graph,
            _operator_ast(),
            proof_bundle=proof_bundle,
        )
        error_codes = [e.code for e in report.errors]

        assert "OPERATOR_LIFT_UNCERTIFIED" in error_codes

    def test_operator_apply_query_can_pass_without_full_operator_lift(self):
        graph = _make_dag(("X", "Y"), ("V", "Y"))
        ast = EstimandAST(
            query_str="operator apply",
            root=OperatorApplyNode(
                operator=_operator_ast().root,
                probe_ref="cdf_probe",
                evaluation_points_ref="audit_grid",
            ),
            treatment="X",
            outcome="Y",
            all_variables=("X", "Y", "V"),
        )

        report = CausalQueryValidator().validate(graph, ast)

        assert report.is_valid is True
        assert "OPERATOR_LIFT_UNCERTIFIED" not in [e.code for e in report.errors]
