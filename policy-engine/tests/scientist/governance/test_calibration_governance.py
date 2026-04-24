from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.observation.contracts import ObservationFamily
from polisyos.scientist.discovery.active import ActiveDisambiguationPlannerInput
from polisyos.scientist.discovery.aggregator import EdgeConfidenceEntry, EdgeConfidenceMatrix
from polisyos.scientist.discovery.priors import (
    DisputedEdge,
    GraphPriorBundle,
    PriorEdge,
    PriorKnowledgeBundle,
)
from polisyos.scientist.discovery.schema import (
    ComputeFootprint,
    DiscoveryAlgorithmFamily,
    DiscoveryMethod,
    GraphHypothesis,
)
from polisyos.scientist.discovery.stability import (
    BootstrapMode,
    BootstrapStabilityConfig,
    BootstrapStabilityReport,
    HypothesisStabilitySummary,
)
from polisyos.scientist.discovery.utility_judge import (
    DownstreamUtilityReport,
    HypothesisUtilityScore,
)
from polisyos.scientist.governance.calibration import (
    CalibrationGovernanceInput,
    CalibrationGovernanceReport,
    CalibrationGovernanceRunner,
)
from polisyos.scientist.search.lessons import (
    LessonKind,
    LessonQuery,
    LessonRegistry,
    load_lesson_card,
)


def _ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind="scientist.test",
        media_type="application/json",
    )


def _passing_summary() -> dict[str, Any]:
    return {
        "fallback_mode": "exact_equilibrium",
        "closure_summary": {"mode": "exact_equilibrium", "equilibrium_count": 1},
    }


def _failing_strategic_summary() -> dict[str, Any]:
    return {
        "fallback_mode": "static_ate",
        "multiplicity_note": "explicit_tie_breaking_disclosed",
        "closure_summary": {"mode": "static_ate", "equilibrium_count": 1},
    }


class _FakePass(ValidatorPass):
    def __init__(
        self,
        pass_id: str,
        estimated_cost_ms: int,
        recorder: list[str],
        *,
        issues: list[ComplianceIssue] | None = None,
    ) -> None:
        self._pass_id = pass_id
        self._estimated_cost_ms = estimated_cost_ms
        self._recorder = recorder
        self._issues = list(issues or [])

    @property
    def pass_id(self) -> str:
        return self._pass_id

    @property
    def estimated_cost_ms(self) -> int:
        return self._estimated_cost_ms

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        del ctx
        self._recorder.append(self._pass_id)
        return list(self._issues)


def _macro_fake_passes(recorder: list[str], *, checkpoint_issue: ComplianceIssue | None = None):
    checkpoint_issues = [] if checkpoint_issue is None else [checkpoint_issue]
    return [
        _FakePass("budget", 50, recorder),
        _FakePass("checkpoint", 20, recorder, issues=checkpoint_issues),
        _FakePass("confidence", 40, recorder),
        _FakePass("freshness", 10, recorder),
    ]


def _procurement_fake_passes(recorder: list[str]):
    return [
        _FakePass("budget", 50, recorder),
        _FakePass("checkpoint", 20, recorder),
        _FakePass("confidence", 40, recorder),
        _FakePass("freshness", 10, recorder),
        _FakePass("sutva_check", 30, recorder),
        _FakePass("transportability_required", 35, recorder),
    ]


def _active_query() -> CausalQuery:
    return CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )


def _active_hypothesis() -> GraphHypothesis:
    return GraphHypothesis(
        hypothesis_id="h1",
        algorithm_family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
        method=DiscoveryMethod.PC,
        graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y", "Z"],
            edges=[
                CausalEdge(src="Z", dst="X", combined_confidence=0.8),
                CausalEdge(src="X", dst="Y", combined_confidence=0.8),
            ],
            discovery_method="pc",
        ),
        edge_confidence={"Z->X": 0.8, "X->Y": 0.8},
        compute_footprint=ComputeFootprint(),
    )


def _active_input() -> ActiveDisambiguationPlannerInput:
    return ActiveDisambiguationPlannerInput(
        edge_confidence_matrix=EdgeConfidenceMatrix(
            entries=[
                EdgeConfidenceEntry(
                    skeleton_key="X--Y",
                    edge_key="X->Y",
                    src="X",
                    dst="Y",
                    presence_confidence=0.8,
                    orientation_confidence=0.4,
                    directional_support={"X->Y": 0.5, "Y->X": 0.45},
                    orientation_support={"X|tail>arrow|Y": 0.5, "Y|tail>arrow|X": 0.45},
                    supporting_hypothesis_ids=["h1"],
                    disputed=True,
                    dispute_reasons=["orientation_conflict"],
                )
            ]
        ),
        bootstrap_stability_report=BootstrapStabilityReport(
            bootstrap_mode=BootstrapMode.ROW,
            config=BootstrapStabilityConfig(n_resamples=5),
            summaries=[
                HypothesisStabilitySummary(
                    hypothesis_id="h1",
                    edge_selection_frequency={"X->Y": 0.6},
                    mean_edge_stability=0.6,
                    adjustment_set_stability=0.6,
                    completed_resamples=5,
                )
            ],
        ),
        downstream_utility_report=DownstreamUtilityReport(
            scores=[
                HypothesisUtilityScore(
                    hypothesis_id="h1",
                    identification_status="identified",
                    identifiability_score=1.0,
                    stability_score=0.7,
                    composite_score=0.9,
                    rank=1,
                )
            ],
            recommended_shortlist=["h1"],
        ),
        hypotheses=[_active_hypothesis()],
        graph_prior_bundle=GraphPriorBundle(
            disputed_edges=[
                DisputedEdge(
                    dispute_id="d1",
                    skeleton_key="X--Y",
                    candidate_edges=[
                        PriorEdge(
                            edge_key="X->Y",
                            src="X",
                            dst="Y",
                            presence_confidence=0.8,
                            orientation_confidence=0.4,
                            supporting_hypothesis_ids=["h1"],
                        )
                    ],
                    dispute_reasons=["orientation_conflict"],
                )
            ]
        ),
        prior_knowledge_bundle=PriorKnowledgeBundle(),
        causal_query=_active_query(),
    )


def test_runner_orders_global_before_family_passes(cas_store, mvp_profile) -> None:
    recorder: list[str] = []
    runner = CalibrationGovernanceRunner(passes=_macro_fake_passes(recorder))
    report = runner.run(
        CalibrationGovernanceInput(
            run_id="R_macro_ok",
            observation_families=[ObservationFamily.MACRO_STATE],
            profile=mvp_profile,
            pass_state={"_store": cas_store},
            candidate_ref=_ref("a"),
            params={"strategic_response_summary": _passing_summary()},
        )
    )

    assert report.verdict == "approve"
    assert recorder == [
        "freshness",
        "checkpoint",
        "confidence",
        "budget",
        "freshness",
        "confidence",
    ]
    assert report.metadata["execution_sequence"][:6] == [
        "global:freshness",
        "global:checkpoint",
        "global:confidence",
        "global:budget",
        "macro_state:freshness",
        "macro_state:confidence",
    ]
    abstraction = next(
        result
        for result in report.adversarial_results
        if result.alias == "abstraction_leakage_adversarial"
    )
    assert abstraction.status == "not_applicable"


def test_runner_short_circuits_on_global_blocker(cas_store, mvp_profile) -> None:
    recorder: list[str] = []
    checkpoint_issue = ComplianceIssue(
        pass_id="checkpoint",
        path=["state", "last_checkpoint_ref"],
        message="missing checkpoint",
        severity=IssueSeverity.BLOCKER,
        code="CHECKPOINT_MISSING",
    )
    runner = CalibrationGovernanceRunner(
        passes=_macro_fake_passes(recorder, checkpoint_issue=checkpoint_issue)
    )
    report = runner.run(
        CalibrationGovernanceInput(
            run_id="R_macro_block",
            observation_families=[ObservationFamily.MACRO_STATE],
            profile=mvp_profile,
            pass_state={"_store": cas_store},
            candidate_ref=_ref("b"),
            params={"strategic_response_summary": _passing_summary()},
        )
    )

    assert report.verdict == "reject"
    assert recorder == ["freshness", "checkpoint"]
    assert report.family_results == []
    assert report.adversarial_results == []
    assert report.metadata["short_circuited"] is True


def test_procurement_strategic_gaming_failure_rejects_run(cas_store, mvp_profile) -> None:
    recorder: list[str] = []
    runner = CalibrationGovernanceRunner(passes=_procurement_fake_passes(recorder))
    report = runner.run(
        CalibrationGovernanceInput(
            run_id="R_procurement_fail",
            observation_families=[ObservationFamily.PROCUREMENT_FLOWS],
            profile=mvp_profile,
            pass_state={"_store": cas_store},
            candidate_ref=_ref("c"),
            params={"strategic_response_summary": _failing_strategic_summary()},
        )
    )

    strategic = next(
        result
        for result in report.adversarial_results
        if result.alias == "strategic_gaming_adversarial"
    )
    multiplicity = next(
        result
        for result in report.adversarial_results
        if result.alias == "multiplicity_disclosure_adversarial"
    )
    assert report.verdict == "reject"
    assert strategic.status == "failed"
    assert multiplicity.status == "passed"
    assert any(issue.code == "ADVERSARIAL_SUITE_FAILED" for issue in report.issues)


def test_missing_required_adversarial_inputs_block_and_keep_abstraction_optional(
    cas_store,
    mvp_profile,
) -> None:
    recorder: list[str] = []
    runner = CalibrationGovernanceRunner(passes=_procurement_fake_passes(recorder))
    report = runner.run(
        CalibrationGovernanceInput(
            run_id="R_procurement_missing",
            observation_families=[ObservationFamily.PROCUREMENT_FLOWS],
            profile=mvp_profile,
            pass_state={"_store": cas_store},
            candidate_ref=_ref("d"),
            params={},
        )
    )

    strategic = next(
        result
        for result in report.adversarial_results
        if result.alias == "strategic_gaming_adversarial"
    )
    multiplicity = next(
        result
        for result in report.adversarial_results
        if result.alias == "multiplicity_disclosure_adversarial"
    )
    abstraction = next(
        result
        for result in report.adversarial_results
        if result.alias == "abstraction_leakage_adversarial"
    )
    assert report.verdict == "reject"
    assert strategic.status == "missing_inputs"
    assert multiplicity.status == "missing_inputs"
    assert abstraction.status == "not_applicable"
    assert (
        sum(1 for issue in report.issues if issue.code == "ADVERSARIAL_SUITE_MISSING_INPUTS") == 2
    )


def test_lesson_card_publisher_writes_registry_entry(tmp_path, cas_store, mvp_profile) -> None:
    recorder: list[str] = []
    registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=cas_store)
    runner = CalibrationGovernanceRunner(passes=_macro_fake_passes(recorder))
    report = runner.run(
        CalibrationGovernanceInput(
            run_id="R_lesson",
            observation_families=[ObservationFamily.MACRO_STATE],
            profile=mvp_profile,
            pass_state={"_store": cas_store},
            candidate_ref=_ref("e"),
            params={"strategic_response_summary": _passing_summary()},
            lesson_registry=registry,
        )
    )

    assert report.lesson_card_ref is not None
    card = load_lesson_card(cas_store, report.lesson_card_ref)
    assert card.kind == LessonKind.SUCCESS
    hits = registry.query(LessonQuery(source_run_id="R_lesson", limit=5))
    assert any(hit.lesson_id == card.lesson_id for hit in hits)


def test_active_disambiguation_integration_embeds_ranked_targets(cas_store, mvp_profile) -> None:
    recorder: list[str] = []
    runner = CalibrationGovernanceRunner(passes=_macro_fake_passes(recorder))
    report = runner.run(
        CalibrationGovernanceInput(
            run_id="R_active",
            observation_families=[ObservationFamily.MACRO_STATE],
            profile=mvp_profile,
            pass_state={"_store": cas_store},
            candidate_ref=_ref("f"),
            params={"strategic_response_summary": _passing_summary()},
            active_disambiguation_input=_active_input(),
        )
    )

    assert report.verdict == "approve"
    assert report.active_disambiguation_targets
    assert any(
        action.action_type == "run_intervention" for action in report.active_disambiguation_actions
    )


@pytest.mark.parametrize(
    ("issues", "expected_verdict"),
    [
        ([], "approve"),
        (
            [
                ComplianceIssue(
                    pass_id="freshness",
                    path=["state", "data_sources"],
                    message="stale",
                    severity=IssueSeverity.WARNING,
                    code="FRESHNESS_STALE",
                )
            ],
            "needs_revision",
        ),
        (
            [
                ComplianceIssue(
                    pass_id="checkpoint",
                    path=["state", "last_checkpoint_ref"],
                    message="missing",
                    severity=IssueSeverity.BLOCKER,
                    code="CHECKPOINT_MISSING",
                )
            ],
            "reject",
        ),
        (
            [
                ComplianceIssue(
                    pass_id="human_review_required",
                    path=["state", "review"],
                    message="manual review",
                    severity=IssueSeverity.WARNING,
                    code="HUMAN_REVIEW_REQUESTED",
                )
            ],
            "human_gate",
        ),
    ],
)
def test_to_governance_report_maps_verdict_from_issue_set(
    issues: list[ComplianceIssue],
    expected_verdict: str,
) -> None:
    report = CalibrationGovernanceReport(verdict="approve", issues=issues)
    assert report.to_governance_report().verdict == expected_verdict
