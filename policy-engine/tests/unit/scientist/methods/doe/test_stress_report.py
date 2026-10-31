"""Source-bound stress accounting stays separate from score admission."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    InputRef,
    PutOptions,
    load_core_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.ir import UncertaintyType
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.backtesting.phase_d4_source import build_phase_d4_suite_roster
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
)
from polisyos.scientist.methods.doe.stress_report import (
    StressOutcomeBasis,
    StressScoreResolution,
    StressTestReport,
    resolve_stress_report_artifact,
    resolve_stress_score_components,
)
from polisyos.scientist.methods.search.actionable_side_information import (
    load_actionable_side_information,
)
from polisyos.scientist.methods.search.adversarial import run_stress_test
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.methods.search.objective import CompositeObjective, GDPGrowthObjective
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_reporting import (
    _merge_stress_test_reports,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)

_UNIT = "test-only-growth-unit"


def _candidate(store: FileSystemCAS) -> ArtifactRef:
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(problem_id="sample_problem", domain=ProblemDomain.FISCAL),
            policy_spec=PolicySpec(policy_id="sample_policy"),
            model_spec=ModelSpec(model_id="sample_model", data_snapshot_ref="sha256:" + "3" * 64),
        ),
        candidate_id="sample_candidate",
    )
    return persist_policy_candidate_schema(store, candidate, return_selected_profile=True)


def _produce(
    store: FileSystemCAS,
    candidate_ref: ArtifactRef,
    *,
    top_k: int = 1,
    stop_early: bool = False,
    threshold: float | None = 0.0,
) -> StressTestReport:
    values = iter((-1.0, 1.0, -1.0, 1.0))
    return run_stress_test(
        adversarial_plan=AdversarialPlan(
            parameter_specs=[
                ParameterSpec(name="x", lower_bound=-1.0, upper_bound=1.0),
                ParameterSpec(name="y", lower_bound=-1.0, upper_bound=1.0),
            ],
            strategy=AdversarialStrategy.GRID_EXTREME,
            max_iterations=4,
            vulnerability_threshold=threshold,
            stop_on_first_vulnerability=stop_early,
            collect_top_k=top_k,
        ),
        base_objective=CompositeObjective([GDPGrowthObjective(expected_unit=_UNIT)]),
        stage_b_evaluator=lambda _candidate, _context: {
            "simulation_results": {
                "gdp_change": next(values),
                "metric_units": {"gdp_change": _UNIT},
            }
        },
        context={"policy_candidate_ref": candidate_ref},
        cas=store,
    )


def _basis(store: FileSystemCAS, report: StressTestReport) -> StressOutcomeBasis:
    return StressOutcomeBasis.model_validate(
        load_core_json_artifact(store, report.score_components[0].outcome_basis_ref)
    )


def _persist_control_basis(
    store: FileSystemCAS, report: StressTestReport, basis: StressOutcomeBasis
):
    component = report.score_components[0]
    manifest = store.get_manifest(component.outcome_basis_ref)
    ref = store.put_json(
        basis,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return component.model_copy(update={"outcome_basis_ref": ref})


def test_producer_to_fresh_level5_keeps_sample_fraction_top_k_independent(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _candidate(store)
    observed = []
    for top_k in (1, 10):
        produced = _produce(store, candidate_ref, top_k=top_k)
        assert produced.cas_artifact_ref is not None
        _, resolution = resolve_stress_report_artifact(
            FileSystemCAS(store.root),
            produced.cas_artifact_ref,
            expected_candidate_ref=candidate_ref,
        )
        # Objective selection remains unbound even though its declared source rows replay.
        assert resolution.status == "unbound"
        assert resolution.robustness_score is None
        assessment = resolution.observed_sample_assessment
        assert assessment is not None
        assert assessment["status"] == "complete"
        assert assessment["observed_fraction"] == 0.5
        assert assessment["attempted"] == assessment["finite_evaluated"] == 4
        assert assessment["violated_scenarios"] == 2
        assert assessment["unknown_or_nonfinite"] == 0
        assert assessment["planned_scenarios"] == 4
        assert assessment["admission_status"] == "unbound"
        assert assessment["limitation"] == "selected_objective_intent_not_independently_established"
        result = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
            {},
            {
                "store": FileSystemCAS(store.root),
                "policy_candidate_ref": candidate_ref,
                "stress_test_report_ref": produced.cas_artifact_ref,
            },
        )
        assert result.feedback["stress_observed_sample_assessment"] == assessment
        assert result.feedback["stress_score_value"] is None
        assert result.feedback["stress_robust"] is None
        assert result.terminal_action == "defer_to_human"
        assert result.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == 1.0
        assert result.actionable_side_information_ref is not None
        persisted = load_actionable_side_information(
            FileSystemCAS(store.root), result.actionable_side_information_ref
        )
        assert persisted.metadata["stress_observed_sample_assessment"] == assessment
        manifest = store.get_manifest(result.actionable_side_information_ref)
        assert any(
            item.role == "stress_test_report"
            and item.artifact_id == produced.cas_artifact_ref.artifact_id
            and item.manifest_profile_sha256 == produced.cas_artifact_ref.manifest_profile_sha256
            for item in manifest.inputs
        )
        observed.append(assessment)
    assert observed[0] == observed[1]


def test_real_early_stop_produces_partial_fraction_without_protected_score(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _candidate(store)
    produced = _produce(store, candidate_ref, stop_early=True)
    assert produced.cas_artifact_ref is not None
    result = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {},
        {
            "store": FileSystemCAS(store.root),
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": produced.cas_artifact_ref,
        },
    )
    assessment = result.feedback["stress_observed_sample_assessment"]
    assert assessment["status"] == "partial"
    assert assessment["completeness"] is False
    assert assessment["observed_fraction"] == 0.0
    assert assessment["attempted"] == assessment["finite_evaluated"] == 1
    assert assessment["violated_scenarios"] == 1
    assert assessment["planned_scenarios"] == 4
    assert result.feedback["stress_score_status"] == "partial"
    assert result.feedback["stress_score_value"] is None
    assert result.terminal_action == "defer_to_human"


def test_missing_violation_threshold_does_not_establish_observed_fraction(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _candidate(store)
    produced = _produce(store, candidate_ref, threshold=None)
    assert produced.cas_artifact_ref is not None
    _, resolution = resolve_stress_report_artifact(
        store, produced.cas_artifact_ref, expected_candidate_ref=candidate_ref
    )
    assert resolution.robustness_score is None
    assert resolution.observed_sample_assessment is None
    result = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {},
        {
            "store": store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": produced.cas_artifact_ref,
        },
    )
    assert result.feedback["stress_observed_sample_assessment"]["status"] == "unassessed"
    assert result.feedback["stress_score_value"] is None


@pytest.mark.parametrize("unknown_status", ["unknown", "invalid"])
def test_unknown_and_skipped_rows_are_separate_from_finite_denominator(
    tmp_path, unknown_status: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _candidate(store)
    produced = _produce(store, candidate_ref)
    basis = _basis(store, produced)
    rows = basis.outcomes[:3]
    rows[1] = rows[1].model_copy(
        update={"status": unknown_status, "vulnerabilities": [], "objective_evidence": None}
    )
    rows[2] = rows[2].model_copy(
        update={"status": "skipped", "vulnerabilities": [], "objective_evidence": None}
    )
    component = _persist_control_basis(
        store, produced, basis.model_copy(update={"outcomes": rows, "complete": False})
    )
    resolution = resolve_stress_score_components(
        store, [component], expected_candidate_ref=candidate_ref
    )
    assessment = resolution.observed_sample_assessment
    assert assessment is not None
    assert assessment["status"] == "partial"
    assert assessment["observed_fraction"] == 0.0
    assert assessment["attempted"] == 2
    assert assessment["finite_evaluated"] == assessment["violated_scenarios"] == 1
    assert assessment["unknown_or_nonfinite"] == 1
    assert assessment["planned_scenarios"] == 4
    assert resolution.status == "partial"
    assert resolution.robustness_score is None


@pytest.mark.parametrize("keep", [0, 1])
def test_partial_prefix_has_exact_source_roster_and_zero_fraction_is_unavailable(
    tmp_path, keep: int
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _candidate(store)
    produced = _produce(store, candidate_ref)
    basis = _basis(store, produced)
    component = _persist_control_basis(
        store,
        produced,
        basis.model_copy(update={"outcomes": basis.outcomes[:keep], "complete": False}),
    )
    resolution = resolve_stress_score_components(
        store, [component], expected_candidate_ref=candidate_ref
    )
    assessment = resolution.observed_sample_assessment
    assert assessment is not None
    assert assessment["finite_evaluated"] == keep
    assert assessment["observed_fraction"] == (None if keep == 0 else 0.0)
    assert assessment["planned_scenarios"] == 4
    assert assessment["status"] == "partial"
    assert resolution.robustness_score is None


@pytest.mark.parametrize(
    "corruption", ["duplicate", "omitted", "reordered", "value", "skipped_value"]
)
def test_same_shape_partial_source_cannot_replace_selected_ids_order_or_values(
    tmp_path, corruption: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _candidate(store)
    produced = _produce(store, candidate_ref)
    basis = _basis(store, produced)
    rows = basis.outcomes[:2]
    if corruption == "duplicate":
        rows[1] = rows[0].model_copy(update={"occurrence_index": 1})
    elif corruption == "omitted":
        rows = [rows[1].model_copy(update={"occurrence_index": 0})]
    elif corruption == "reordered":
        rows = [rows[1], rows[0]]
    else:
        rows[0] = rows[0].model_copy(
            update={
                "parameter_values": {**rows[0].parameter_values, "x": 123.0},
                **(
                    {"status": "skipped", "vulnerabilities": [], "objective_evidence": None}
                    if corruption == "skipped_value"
                    else {}
                ),
            }
        )
    component = _persist_control_basis(
        store, produced, basis.model_copy(update={"outcomes": rows, "complete": False})
    )
    resolution = resolve_stress_score_components(
        store, [component], expected_candidate_ref=candidate_ref
    )
    assert resolution.status in {"invalid", "partial"}
    assert resolution.observed_sample_assessment is None
    assert resolution.robustness_score is None


def test_mixed_components_retain_full_planned_denominator_and_unresolved_limit(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _candidate(store)
    full = _produce(store, candidate_ref, top_k=10)
    partial = _produce(store, candidate_ref, stop_early=True)
    components = [partial.score_components[0], full.score_components[0]]
    resolution = resolve_stress_score_components(
        store, components, expected_candidate_ref=candidate_ref
    )
    assessment = resolution.observed_sample_assessment
    assert assessment is not None
    assert assessment["status"] == "partial"
    assert assessment["planned_scenarios"] == 8
    assert assessment["finite_evaluated"] == 5
    assert assessment["violated_scenarios"] == 3
    assert assessment["observed_fraction"] == 0.4
    assert resolution.status == "partial"
    assert resolution.robustness_score is None
    unbound_ref = components[1].outcome_basis_ref.model_copy(
        update={"manifest_profile_sha256": None}
    )
    unresolved = resolve_stress_score_components(
        store,
        [components[0], components[1].model_copy(update={"outcome_basis_ref": unbound_ref})],
        expected_candidate_ref=candidate_ref,
    )
    assert unresolved.status == "unbound"
    assert unresolved.observed_sample_assessment is None
    assert unresolved.robustness_score is None


def test_recomputed_shaped_summary_does_not_construct_private_source_accounting() -> None:
    resolution = StressScoreResolution(
        status="available",
        score_profile="finite_binary_scenario_v1",
        robustness_score=1.0,
        total_scenarios_evaluated=4,
        passed_count=4,
        predicate_status="recomputed",
        reason_code="source_bound_occurrences_recomputed",
    )
    assert resolution.observed_sample_assessment is None
    assert "observed_sample_assessment" not in resolution.model_dump(mode="json")


def test_typed_merge_counts_selected_views_and_distinct_producer_occurrences(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref = _candidate(store)
    produced = _produce(store, candidate_ref)
    component = produced.score_components[0]
    original_manifest = store.get_manifest(component.outcome_basis_ref)
    alternate_profile_ref = store.put_json(
        load_core_json_artifact(store, component.outcome_basis_ref),
        PutOptions(
            kind=original_manifest.kind,
            media_type=original_manifest.media_type,
            schema=original_manifest.artifact_schema,
            inputs=[
                *original_manifest.inputs,
                InputRef(
                    artifact_id=candidate_ref.artifact_id,
                    role="test_only_alternate_profile",
                    manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert alternate_profile_ref.artifact_id == component.outcome_basis_ref.artifact_id
    assert alternate_profile_ref.manifest_profile_sha256 != (
        component.outcome_basis_ref.manifest_profile_sha256
    )
    separate_invocation = _produce(store, candidate_ref)
    separate_component = separate_invocation.score_components[0]
    assert (
        separate_component.outcome_basis_ref.artifact_id != component.outcome_basis_ref.artifact_id
    )
    components = [
        component,
        component,
        component.model_copy(update={"outcome_basis_ref": alternate_profile_ref}),
        separate_component,
    ]
    selection_ref = persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="merge-loop",
            suite_id="policy_selection",
            candidate_ref=candidate_ref,
            selection_metrics={"score": 1.0},
            holdout_metrics={"score": 1.0},
            sample_counts={"selection": 1},
            runtime_split_type=BenchmarkSplit.SELECTION,
            promotable=False,
        ),
        return_selected_profile=True,
    )
    roster = build_phase_d4_suite_roster(
        store,
        rotating_evaluation_refs=[],
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=selection_ref,
        expected_run_id="merge-run",
        expected_loop_id="merge-loop",
    )
    base = produced.model_copy(
        update={
            "score_components": components,
            "total_scenarios_evaluated": 999,
            "metadata": {"base_total_scenarios_evaluated": 888},
        }
    )
    merged = _merge_stress_test_reports(base, [], store=store, expected_phase_d4_roster=roster)
    assert merged.score_components == components
    assert merged.total_scenarios_evaluated == 12
    assert merged.metadata["base_total_scenarios_evaluated"] == 12
    assert merged.metadata["scenario_count_status"] == "recomputed"
    # Counting selected rows does not admit duplicated component identities.
    resolution = resolve_stress_score_components(
        store, components, expected_candidate_ref=candidate_ref
    )
    assert resolution.status == "invalid"
    assert resolution.reason_code == "duplicate_component_id"
    assert resolution.robustness_score is None

    for claimed_count in (0, 999):
        unknown = _merge_stress_test_reports(
            StressTestReport(
                report_id="unbound-legacy-count", total_scenarios_evaluated=claimed_count
            ),
            [],
            store=store,
            expected_phase_d4_roster=roster,
        )
        assert unknown.total_scenarios_evaluated == 0
        assert unknown.metadata["scenario_count_status"] == (
            "partial" if claimed_count else "recomputed"
        )
        assert unknown.metadata["unassessed_scenario_count_sources"] == (
            ["unbound-legacy-count"] if claimed_count else []
        )
        # A loaded legacy source is not the producer's newly constructed empty placeholder.
        assert unknown.score_profile == "mixed_unscored"
        assert unknown.robustness_score is None
