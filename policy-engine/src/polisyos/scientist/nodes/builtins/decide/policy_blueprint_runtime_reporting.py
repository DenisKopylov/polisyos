from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeGuard

from pydantic import BaseModel

from polisyos.core.artifacts import (
    ArtifactRef,
    InputRef,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.canon import CanonSpec, CanonViolation, to_canonical_bytes
from polisyos.scientist.methods.backtesting.adversarial import (
    ABSTRACTION_LEAKAGE_SUITE_ID,
    MULTIPLICITY_DISCLOSURE_SUITE_ID,
    STRATEGIC_GAMING_SUITE_ID,
)
from polisyos.scientist.methods.doe.stress_report import (
    _STRESS_TEST_REPORT_ARTIFACT_KIND,
    _STRESS_TEST_REPORT_SCHEMA_NAME,
    StressOutcomeBasis,
    StressScoreComponent,
    StressScoreResolution,
    StressTestReport,
    Vulnerability,
    _load_stress_report_source,
    load_selected_stress_outcome_basis,
    resolve_stress_score_components,
)
from polisyos.scientist.methods.search.funnel.level0_static import Level0StaticValidator
from polisyos.scientist.methods.search.funnel.level1_heuristic import Level1CheapHeuristic
from polisyos.scientist.methods.search.funnel.level2_causal import Level2CausalPlausibility
from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.methods.search.funnel.level6_promotion import Level6PromotionStage
from polisyos.scientist.methods.search.funnel.types import FunnelOutcome
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreAdmission,
    ObjectiveScoreStatus,
    reconcile_objective_score_assessment,
)
from polisyos.scientist.methods.search.transfer_context import TransferContext
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
    _RuntimeSession,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    _CURRENT_POLICY_OUTPUT_ARTIFACT_KEYS,
    _CURRENT_POLICY_PROMOTION_PARAM_KEYS,
    build_vulnerabilities,
    clear_current_policy_promotion_projection,
    load_causal_report,
    load_distributional_report_for_state,
    load_governance_report,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_STRESS_TEST_REPORT_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeEvent, NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.scientist.methods.backtesting.phase_d4_source import PhaseD4SuiteRoster


def _is_builtin_number(value: object) -> TypeGuard[int | float]:
    """Narrow only the exact JSON numeric primitives used by finite-score gates."""
    return type(value) is int or type(value) is float


def _metadata_int(value: object, *, field_name: str) -> int:
    """Parse an explicitly supplied JSON count without turning malformed values into absence."""
    try:
        if isinstance(value, str):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field_name}_invalid") from exc
    raise ValueError(f"{field_name}_invalid")


def _ensure_stress_test_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    evaluation_vector: PolicyEvaluationVector,
    supplemental_reports: list[StressTestReport] | None = None,
    supplemental_report_refs: list[ArtifactRef] | None = None,
    phase_d4_suite_ids: list[str] | None = None,
    expected_candidate_ref: ArtifactRef,
    expected_selection_evaluation_ref: ArtifactRef | None = None,
    expected_phase_d4_roster: PhaseD4SuiteRoster | None = None,
) -> ArtifactRef | None:
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    paired_reports = list(supplemental_reports or [])
    paired_refs = list(supplemental_report_refs or [])
    if len(paired_reports) != len(paired_refs):
        raise ValueError("stress_report_source_pair_count_mismatch")
    if (
        expected_candidate_ref.kind != PolicyCandidateSchema.ARTIFACT_KIND
        or expected_candidate_ref.media_type != PolicyCandidateSchema.ARTIFACT_MEDIA_TYPE
    ):
        raise ValueError("stress_report_expected_candidate_identity_mismatch")
    existing_ref = state.artifacts_index.get(ARTIFACT_STRESS_TEST_REPORT_REF)
    replacement_suite_ids = (
        [item.suite_id for item in expected_phase_d4_roster.suites]
        if expected_phase_d4_roster is not None
        else [str(item) for item in (phase_d4_suite_ids or []) if str(item).strip()]
    )
    if existing_ref is not None and not paired_reports and not replacement_suite_ids:
        return existing_ref

    report = _load_stress_test_report(ctx, existing_ref)
    if report is None:
        report = StressTestReport(
            schema_version="1.1",
            report_id=f"stress_{state.run_id}",
            total_scenarios_evaluated=0,
            vulnerabilities=build_vulnerabilities(
                evaluation=evaluation_vector,
                distributional=load_distributional_report_for_state(ctx, state),
                causal_report=load_causal_report(ctx, state),
                governance_report=load_governance_report(ctx, state),
            ),
            robustness_score=None,
            score_status="not_evaluated",
            score_reason="no_finite_occurrence_basis",
            metadata={
                "generated_by": "run_policy_blueprint_runtime",
                "phase_d4_suite_ids": [],
                "phase_d4_suite_scenario_counts": {},
                "base_total_scenarios_evaluated": 0,
            },
        )
    for source_ref, supplied_report in zip(paired_refs, paired_reports, strict=True):
        resolved_report = _load_stress_test_report(ctx, source_ref)
        if resolved_report is None or resolved_report.model_dump(
            mode="json"
        ) != supplied_report.model_dump(mode="json"):
            raise ValueError("stress_report_source_body_mismatch")

    report = _merge_stress_test_reports(
        report,
        paired_reports,
        replacement_suite_ids=replacement_suite_ids,
        store=ctx.store,
        expected_phase_d4_roster=expected_phase_d4_roster,
    )
    report = _recompute_stress_test_report(report)
    if report.score_profile in {"continuous_severity_v1", "mixed_unscored"}:
        resolution = StressScoreResolution(
            status="profile_mismatch",
            component_ids=[item.component_id for item in report.score_components],
            reason_code="mixed_or_nonbinary_score_profiles",
        )
    elif expected_phase_d4_roster is None:
        resolution = StressScoreResolution(
            status="unbound",
            component_ids=[item.component_id for item in report.score_components],
            reason_code="phase_d4_selected_roster_not_established",
            case_truth_required=bool(report.score_components),
            case_truth_status="not_established",
            case_truth_reason="phase_d4_selected_roster_not_established",
        )
    else:
        resolution = resolve_stress_score_components(
            ctx.store,
            report.score_components,
            expected_candidate_ref=expected_candidate_ref,
            expected_run_id=state.run_id,
            expected_selection_evaluation_ref=expected_selection_evaluation_ref,
            expected_phase_d4_roster=expected_phase_d4_roster,
        )
    d4_case_truth_required = resolution.case_truth_required is True
    report = report.model_copy(
        update={
            "schema_version": "1.2" if d4_case_truth_required else "1.1",
            "case_truth_status": resolution.case_truth_status,
            "case_truth_reason": resolution.case_truth_reason if d4_case_truth_required else None,
            "score_status": resolution.status,
            "score_reason": resolution.reason_code,
            "score_predicate_status": resolution.predicate_status,
            "score_profile": resolution.score_profile or report.score_profile,
            "robustness_score": resolution.robustness_score,
            "total_scenarios_evaluated": (
                resolution.total_scenarios_evaluated
                if resolution.status == "available"
                else report.total_scenarios_evaluated
            ),
            "critical_count": resolution.critical_count
            if resolution.status == "available"
            else report.critical_count,
            "high_count": resolution.high_count
            if resolution.status == "available"
            else report.high_count,
            "medium_count": resolution.medium_count
            if resolution.status == "available"
            else report.medium_count,
        }
    )
    report._case_truth_required = resolution.case_truth_required
    input_refs = [
        InputRef(
            artifact_id=expected_candidate_ref.artifact_id,
            role="candidate",
            manifest_profile_sha256=expected_candidate_ref.manifest_profile_sha256,
        )
    ]
    if existing_ref is not None:
        input_refs.append(
            InputRef(
                artifact_id=existing_ref.artifact_id,
                role="base_stress_report",
                manifest_profile_sha256=existing_ref.manifest_profile_sha256,
            )
        )
    input_refs.extend(
        input_ref_from_artifact_ref(source_ref, role="supplemental_stress_report")
        for source_ref in paired_refs
    )
    input_refs.extend(
        input_ref_from_artifact_ref(component.outcome_basis_ref, role="stress_outcome_basis")
        for component in report.score_components
    )
    if expected_phase_d4_roster is not None:
        from polisyos.scientist.methods.backtesting.phase_d4_source import (
            PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE,
        )

        input_refs.extend(
            input_ref_from_artifact_ref(
                evaluation_ref,
                role=PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE,
            )
            for evaluation_ref in expected_phase_d4_roster.suite_evaluation_refs
        )
    return ctx.store.put_json(
        report,
        PutOptions(
            kind=_STRESS_TEST_REPORT_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_STRESS_TEST_REPORT_SCHEMA_NAME, version="1.1"),
            inputs=input_refs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _merge_stress_test_reports(
    base_report: StressTestReport,
    supplemental_reports: list[StressTestReport],
    *,
    replacement_suite_ids: list[str] | None = None,
    store: ArtifactStore | None = None,
    expected_phase_d4_roster: PhaseD4SuiteRoster | None = None,
) -> StressTestReport:
    """Merge source reports using typed selected suite refs when CAS is available.

    The no-store path is a legacy diagnostics-only view used by display-level
    tests; it never classifies score components by their string identifiers.
    Runtime report production supplies both CAS and the current typed roster.
    """
    if store is not None and expected_phase_d4_roster is not None:
        return _merge_typed_stress_test_reports(
            base_report,
            supplemental_reports,
            store=store,
            roster=expected_phase_d4_roster,
        )
    if store is not None:
        components = [
            *base_report.score_components,
            *(item for report in supplemental_reports for item in report.score_components),
        ]
        vulnerabilities = [
            *base_report.vulnerabilities,
            *(item for report in supplemental_reports for item in report.vulnerabilities),
        ]
        return base_report.model_copy(
            update={
                "schema_version": "1.2",
                "score_components": components,
                "vulnerabilities": vulnerabilities,
                "score_status": "unbound",
                "score_reason": "phase_d4_selected_roster_not_established",
                "score_predicate_status": "not_established",
                "case_truth_status": "not_established",
                "case_truth_reason": "phase_d4_selected_roster_not_established",
                "robustness_score": None,
            }
        )
    return _merge_legacy_stress_test_diagnostics(
        base_report,
        supplemental_reports,
        replacement_suite_ids=replacement_suite_ids,
    )


def _merge_typed_stress_test_reports(
    base_report: StressTestReport,
    supplemental_reports: list[StressTestReport],
    *,
    store: ArtifactStore,
    roster: PhaseD4SuiteRoster,
) -> StressTestReport:
    """Replace only stale D.4 rows identified by their selected typed source refs."""
    selected = {item.suite_id: item for item in roster.suites}
    selected_keys = {
        suite_id: item.benchmark_evaluation_ref.model_dump_json()
        for suite_id, item in selected.items()
    }
    supplemental_by_suite: dict[str, list[StressScoreComponent]] = {}
    supplemental_components: list[StressScoreComponent] = []
    for report in supplemental_reports:
        if not report.score_components:
            continue
        for component in report.score_components:
            basis, _ = load_selected_stress_outcome_basis(
                store,
                component.outcome_basis_ref,
            )
            if (
                basis.source_kind != "phase_d4_suite"
                or basis.suite_id is None
                or basis.benchmark_evaluation_ref is None
                or basis.suite_id not in selected
                or basis.benchmark_evaluation_ref.model_dump_json() != selected_keys[basis.suite_id]
            ):
                raise ValueError("phase_d4_supplemental_component_outside_selected_roster")
            supplemental_by_suite.setdefault(basis.suite_id, []).append(component)
            supplemental_components.append(component)

    base_non_d4: list[StressScoreComponent] = []
    base_current_d4: list[StressScoreComponent] = []
    removed_base_d4_vulnerabilities: list[Vulnerability] = []
    d4_scenario_counts: dict[str, int] = {}
    for component in base_report.score_components:
        basis, _ = load_selected_stress_outcome_basis(
            store,
            component.outcome_basis_ref,
        )
        if basis.source_kind != "phase_d4_suite":
            base_non_d4.append(component)
            continue
        current = selected.get(basis.suite_id or "")
        is_current = (
            current is not None
            and basis.suite_version == current.suite_version
            and basis.benchmark_evaluation_ref is not None
            and basis.benchmark_evaluation_ref.model_dump_json()
            == selected_keys[basis.suite_id or ""]
        )
        if is_current and not supplemental_by_suite.get(basis.suite_id or ""):
            base_current_d4.append(component)
            d4_scenario_counts[basis.suite_id or ""] = d4_scenario_counts.get(
                basis.suite_id or "", 0
            ) + len(basis.outcomes)
            continue
        removed_base_d4_vulnerabilities.extend(
            vulnerability for outcome in basis.outcomes for vulnerability in outcome.vulnerabilities
        )

    score_components = [*base_non_d4, *base_current_d4, *supplemental_components]
    for suite_id, components in supplemental_by_suite.items():
        count = 0
        for component in components:
            basis, _ = load_selected_stress_outcome_basis(store, component.outcome_basis_ref)
            count += len(basis.outcomes)
        d4_scenario_counts[suite_id] = count

    removed = Counter(item.model_dump_json() for item in removed_base_d4_vulnerabilities)
    retained_vulnerabilities: list[Vulnerability] = []
    for vulnerability in base_report.vulnerabilities:
        key = vulnerability.model_dump_json()
        if removed[key] > 0:
            removed[key] -= 1
        else:
            retained_vulnerabilities.append(vulnerability)
    vulnerabilities = [
        *retained_vulnerabilities,
        *[item for report in supplemental_reports for item in report.vulnerabilities],
    ]

    reports = [base_report, *supplemental_reports]
    score_source_reports: list[dict[str, Any]] = []
    for source_report in reports:
        recorded_sources = source_report.metadata.get("score_source_reports")
        if isinstance(recorded_sources, list) and recorded_sources:
            score_source_reports.extend(
                dict(item) for item in recorded_sources if isinstance(item, dict)
            )
            continue
        source_score = source_report.robustness_score
        if not _is_builtin_number(source_score) or not math.isfinite(source_score):
            source_score = None
        score_source_reports.append(
            {
                "report_id": source_report.report_id,
                "schema_version": source_report.schema_version,
                "score_status": source_report.score_status,
                "score_profile": source_report.score_profile,
                "reported_score": source_score,
                "reported_score_present": source_report.robustness_score is not None,
            }
        )
    has_unscored_scope = any(
        report.score_profile != "finite_binary_scenario_v1"
        or (report.total_scenarios_evaluated > 0 and not report.score_components)
        or (bool(report.vulnerabilities) and not report.score_components)
        or (report.robustness_score is not None and not report.score_components)
        or (report.schema_version not in {"1.1", "1.2"} and report.total_scenarios_evaluated > 0)
        for report in reports
    )
    score_profile = (
        "mixed_unscored"
        if has_unscored_scope
        else "finite_binary_scenario_v1"
        if score_components
        else base_report.score_profile
    )
    score_status = (
        "profile_mismatch" if score_profile == "mixed_unscored" else base_report.score_status
    )
    base_total_scenarios = _metadata_int(
        base_report.metadata.get(
            "base_total_scenarios_evaluated", base_report.total_scenarios_evaluated
        ),
        field_name="base_total_scenarios_evaluated",
    )
    return base_report.model_copy(
        update={
            "schema_version": "1.2" if roster.suites else "1.1",
            "total_scenarios_evaluated": base_total_scenarios + sum(d4_scenario_counts.values()),
            "score_components": score_components,
            "score_profile": score_profile,
            "score_status": score_status,
            "score_reason": (
                "mixed_finite_and_unscored_sources"
                if score_profile == "mixed_unscored"
                else base_report.score_reason
            ),
            "robustness_score": None
            if score_profile == "mixed_unscored"
            else base_report.robustness_score,
            "vulnerabilities": vulnerabilities,
            "metadata": {
                **dict(base_report.metadata),
                "phase_d4_suite_ids": sorted(selected),
                "phase_d4_suite_scenario_counts": d4_scenario_counts,
                "base_total_scenarios_evaluated": base_total_scenarios,
                "score_source_reports": score_source_reports,
            },
        }
    )


def _merge_legacy_stress_test_diagnostics(
    base_report: StressTestReport,
    supplemental_reports: list[StressTestReport],
    *,
    replacement_suite_ids: list[str] | None,
) -> StressTestReport:
    """Merge unscored display summaries without granting score authority."""
    replacement_suite_ids_set = {
        str(item).strip() for item in (replacement_suite_ids or []) if str(item).strip()
    }
    if not supplemental_reports and not replacement_suite_ids_set:
        return base_report
    replacement_suite_ids_set.update(
        str(report.metadata.get("challenge_suite_id")).strip()
        for report in supplemental_reports
        if str(report.metadata.get("challenge_suite_id") or "").strip()
    )
    vulnerabilities = [
        item
        for item in base_report.vulnerabilities
        if _phase_d4_suite_id_from_vulnerability(item) not in replacement_suite_ids_set
    ]
    score_components = [
        *base_report.score_components,
        *(component for report in supplemental_reports for component in report.score_components),
    ]
    reports = [base_report, *supplemental_reports]
    score_source_reports: list[dict[str, Any]] = []
    for source_report in reports:
        source_score = source_report.robustness_score
        if not _is_builtin_number(source_score) or not math.isfinite(source_score):
            source_score = None
        score_source_reports.append(
            {
                "report_id": source_report.report_id,
                "schema_version": source_report.schema_version,
                "score_status": source_report.score_status,
                "score_profile": source_report.score_profile,
                "reported_score": source_score,
                "reported_score_present": source_report.robustness_score is not None,
            }
        )
    counts = dict(base_report.metadata.get("phase_d4_suite_scenario_counts", {}))
    for suite_id in replacement_suite_ids_set:
        counts.pop(suite_id, None)
    for report in supplemental_reports:
        suite_id = report.metadata.get("challenge_suite_id")
        if isinstance(suite_id, str) and suite_id.strip():
            counts[suite_id] = int(report.total_scenarios_evaluated)
        vulnerabilities.extend(report.vulnerabilities)
    base_total_scenarios = _metadata_int(
        base_report.metadata.get(
            "base_total_scenarios_evaluated",
            max(base_report.total_scenarios_evaluated - sum(counts.values()), 0),
        ),
        field_name="base_total_scenarios_evaluated",
    )
    return base_report.model_copy(
        update={
            "total_scenarios_evaluated": base_total_scenarios + sum(counts.values()),
            "score_components": score_components,
            "vulnerabilities": vulnerabilities,
            "robustness_score": None,
            "score_status": "unbound",
            "score_reason": "legacy_diagnostic_merge_not_cas_resolved",
            "score_predicate_status": "not_established",
            "metadata": {
                **dict(base_report.metadata),
                "phase_d4_suite_ids": sorted(counts),
                "phase_d4_suite_scenario_counts": counts,
                "base_total_scenarios_evaluated": base_total_scenarios,
                "score_source_reports": score_source_reports,
            },
        }
    )


def _phase_d4_suite_id_from_vulnerability(vulnerability: Vulnerability) -> str | None:
    candidate = str(getattr(vulnerability, "vulnerability_id", "")).strip()
    if ":" not in candidate:
        return None
    suite_id, _, _ = candidate.partition(":")
    if suite_id in {
        STRATEGIC_GAMING_SUITE_ID,
        MULTIPLICITY_DISCLOSURE_SUITE_ID,
        ABSTRACTION_LEAKAGE_SUITE_ID,
    }:
        return suite_id
    return None


def _recompute_stress_test_report(report: StressTestReport) -> StressTestReport:
    return report.model_copy(
        update={
            "critical_count": sum(
                1 for item in report.vulnerabilities if item.severity == "critical"
            ),
            "high_count": sum(1 for item in report.vulnerabilities if item.severity == "high"),
            "medium_count": sum(1 for item in report.vulnerabilities if item.severity == "medium"),
        }
    )


def _serialize_funnel_outcome(outcome: FunnelOutcome) -> dict[str, Any]:
    payload = {
        "ticket_id": outcome.ticket_id,
        "candidate_hash": outcome.candidate_hash,
        "compute_cost_usd": outcome.compute_cost_usd,
        "compute_cost_origin": outcome.compute_cost_origin,
        "trace": [
            {
                "fidelity_level": step.fidelity_level,
                "stage_name": step.stage_name,
                "objective_value": step.objective_value,
                "is_promising": step.is_promising,
                "score_status": step.score_status.value,
                "score_admission": (
                    None
                    if step.score_admission is None
                    else step.score_admission.to_surface_payload()
                ),
                "duration_seconds": step.duration_seconds,
                "compute_cost_usd": step.compute_cost_usd,
                "compute_cost_origin": step.compute_cost_origin,
                "executed_work_packet_status": step.executed_work_packet_status,
                "executed_work_packet_ref": (
                    None
                    if step.executed_work_packet_ref is None
                    else step.executed_work_packet_ref.model_dump(mode="json")
                ),
                "routing_decision": step.routing_decision,
                "voi_action": step.voi_action,
                "voi_priority": step.voi_priority,
                "failure_count": step.failure_count,
                "blocker_count": step.blocker_count,
            }
            for step in outcome.trace
        ],
        "prior_attempt_ticket_id": getattr(outcome, "prior_attempt_ticket_id", None),
        "prior_attempt_trace": [
            {
                "fidelity_level": step.fidelity_level,
                "stage_name": step.stage_name,
                "objective_value": step.objective_value,
                "is_promising": step.is_promising,
                "score_status": step.score_status.value,
                "score_admission": (
                    None
                    if step.score_admission is None
                    else step.score_admission.to_surface_payload()
                ),
                "duration_seconds": step.duration_seconds,
                "compute_cost_usd": step.compute_cost_usd,
                "compute_cost_origin": step.compute_cost_origin,
                "executed_work_packet_status": step.executed_work_packet_status,
                "executed_work_packet_ref": (
                    None
                    if step.executed_work_packet_ref is None
                    else step.executed_work_packet_ref.model_dump(mode="json")
                ),
                "routing_decision": step.routing_decision,
                "voi_action": step.voi_action,
                "voi_priority": step.voi_priority,
                "failure_count": step.failure_count,
                "blocker_count": step.blocker_count,
            }
            for step in getattr(outcome, "prior_attempt_trace", ())
        ],
        "prior_attempt_history_status": outcome.prior_attempt_history_status,
        "prior_attempt_history": [
            {
                "ticket_id": attempt.ticket_id,
                "trace": [
                    {
                        "fidelity_level": step.fidelity_level,
                        "stage_name": step.stage_name,
                        "objective_value": step.objective_value,
                        "is_promising": step.is_promising,
                        "score_status": step.score_status.value,
                        "score_admission": (
                            None
                            if step.score_admission is None
                            else step.score_admission.to_surface_payload()
                        ),
                        "duration_seconds": step.duration_seconds,
                        "compute_cost_usd": step.compute_cost_usd,
                        "compute_cost_origin": step.compute_cost_origin,
                        "executed_work_packet_status": step.executed_work_packet_status,
                        "executed_work_packet_ref": (
                            None
                            if step.executed_work_packet_ref is None
                            else step.executed_work_packet_ref.model_dump(mode="json")
                        ),
                        "routing_decision": step.routing_decision,
                        "voi_action": step.voi_action,
                        "voi_priority": step.voi_priority,
                        "failure_count": step.failure_count,
                        "blocker_count": step.blocker_count,
                    }
                    for step in attempt.trace
                ],
            }
            for attempt in outcome.prior_attempt_history
        ],
        "stage_results": {
            str(level): {
                "stage_name": result.stage_name,
                "objective_value": result.objective_value,
                "is_promising": result.is_promising,
                "score_status": result.score_status.value,
                "score_admission": (
                    None
                    if result.score_admission is None
                    else result.score_admission.to_surface_payload()
                ),
                "feedback": result.feedback,
                "failure_cards": [card.model_dump(mode="json") for card in result.failure_cards],
                "fidelity_level": result.fidelity_level,
                "compute_cost_usd": result.compute_cost_usd,
                "compute_cost_origin": result.compute_cost_origin,
                "executed_work_packet_status": result.executed_work_packet_status,
                "executed_work_packet_ref": (
                    None
                    if result.executed_work_packet_ref is None
                    else result.executed_work_packet_ref.model_dump(mode="json")
                ),
                "terminal_action": result.terminal_action,
            }
            for level, result in outcome.stage_results.items()
        },
        "final_action": outcome.final_action,
        "completed": outcome.completed,
        "degradation_mode": outcome.degradation_mode,
        "uncertainty_historical_max": outcome.uncertainty_envelope.model_dump(mode="json"),
        "uncertainty_current": (
            None
            if outcome.current_uncertainty_envelope is None
            else outcome.current_uncertainty_envelope.model_dump(mode="json")
        ),
        "uncertainty_observation_refs": [
            ref.model_dump(mode="json") for ref in outcome.uncertainty_observation_refs
        ],
        "uncertainty_intake_failures": list(outcome.uncertainty_intake_failures),
        "search_uncertainty_current_read": (
            None
            if outcome.search_uncertainty_current_read is None
            else outcome.search_uncertainty_current_read.model_dump(mode="json", exclude_none=False)
        ),
        "audit_refs": [ref.model_dump(mode="json") for ref in outcome.audit_refs],
        "actionable_side_information_refs": [
            ref.model_dump(mode="json") for ref in outcome.actionable_side_information_refs
        ],
    }

    if outcome.result_reuse_source_ticket_id is not None:
        payload.update(
            parent_ticket_id=outcome.parent_ticket_id,
            lineage=list(outcome.lineage),
            continuation_reason=outcome.continuation_reason,
            result_reuse_source_ticket_id=outcome.result_reuse_source_ticket_id,
        )
    return payload


def _extract_level5_gate(outcome: FunnelOutcome) -> dict[str, Any]:
    level5 = outcome.stage_results.get(5)
    if level5 is None:
        return {"passed": False, "reason": "level5_not_executed"}
    feedback = level5.feedback or {}
    score_value = feedback.get("stress_score_value")
    score_is_finite_binary = (
        feedback.get("stress_score_status") == "available"
        and feedback.get("stress_score_profile") == "finite_binary_scenario_v1"
        and feedback.get("stress_score_predicate_status")
        in {"recomputed", "independently_reconciled"}
        and _is_builtin_number(score_value)
        and math.isfinite(score_value)
        and (
            not feedback.get("stress_score_case_truth_required", False)
            or feedback.get("stress_score_case_truth_status") == "recomputed"
        )
    )
    return {
        "passed": (
            level5.is_promising
            and level5.terminal_action not in {"reject", "defer_to_human"}
            and score_is_finite_binary
        ),
        "reason": None if score_is_finite_binary else "finite_stress_score_unavailable",
        "score_status": feedback.get("stress_score_status"),
        "score_profile": feedback.get("stress_score_profile"),
        "score_reason": feedback.get("stress_score_reason"),
        "case_truth_status": feedback.get("stress_score_case_truth_status"),
        "case_truth_required": feedback.get("stress_score_case_truth_required", False),
        "terminal_action": level5.terminal_action,
        "failure_count": len(level5.failure_cards),
        "critical_failures": [
            card.failure_type for card in level5.failure_cards if card.is_blocker
        ],
    }


def _load_stress_test_report(
    ctx: ExecutionContext,
    ref: ArtifactRef | None,
) -> StressTestReport | None:
    if ref is None:
        return None
    return _load_stress_report_source(ctx.store, ref, allow_unselected_profile=True)[0]


def _find_non_finite_projection_values(value: Any) -> list[dict[str, str]]:
    """Locate non-finite leaves without changing the source projection."""
    findings: list[dict[str, str]] = []

    def visit(child: Any, location: str, ancestors: frozenset[int]) -> None:
        if type(child) is float:
            if not math.isfinite(child):
                kind = (
                    "nan"
                    if math.isnan(child)
                    else "positive_infinity"
                    if child > 0
                    else "negative_infinity"
                )
                findings.append({"location": location, "kind": kind})
            return

        child_id = id(child)
        if child_id in ancestors:
            return
        next_ancestors = ancestors | {child_id}
        if isinstance(child, BaseModel):
            members = child.model_dump(mode="python", by_alias=True, exclude_none=False)
            visit(members, location, ancestors)
        elif is_dataclass(child) and not isinstance(child, type):
            for field in fields(child):
                visit(getattr(child, field.name), f"{location}.{field.name}", next_ancestors)
        elif isinstance(child, Mapping):
            for key, member in child.items():
                key_location = (
                    f"{location}.{key}"
                    if isinstance(key, str) and key.isidentifier()
                    else f"{location}[{key!r}]"
                )
                visit(member, key_location, next_ancestors)
        elif isinstance(child, (list, tuple)):
            for index, member in enumerate(child):
                visit(member, f"{location}[{index}]", next_ancestors)

    visit(value, "$", frozenset())
    return findings


def _funnel_projection_failure_basis(outcome: FunnelOutcome) -> dict[str, Any]:
    """Project typed stage failure evidence into a finite diagnostic payload."""
    stage_evidence: list[dict[str, Any]] = []
    for level, result in sorted(outcome.stage_results.items()):
        feedback = result.feedback if isinstance(result.feedback, Mapping) else {}
        issues = feedback.get("issues")
        issue_messages = [
            issue["message"]
            for issue in (issues if isinstance(issues, (list, tuple)) else ())
            if isinstance(issue, Mapping) and isinstance(issue.get("message"), str)
        ]
        verdict = feedback.get("verdict")
        stage_evidence.append(
            {
                "fidelity_level": level,
                "stage_name": result.stage_name,
                "verdict": verdict if isinstance(verdict, str) else None,
                "failure_types": [card.failure_type for card in result.failure_cards],
                "issue_messages": issue_messages,
            }
        )
    return {
        "evaluation_status": outcome.evaluation_status,
        "final_action": outcome.final_action,
        "failure_types": [card.failure_type for card in outcome.failure_cards],
        "stage_evidence": stage_evidence,
    }


def _runtime_session_artifact_refs(session: _RuntimeSession) -> list[ArtifactRef]:
    """Retain references produced before final outcome projection was attempted."""
    refs: list[ArtifactRef] = []
    candidates: list[Any] = [
        session.candidate_ref,
        session.selection_vector_ref,
        session.selection_ref,
        session.evidence_ref,
        session.ambiguity_certificate_ref,
        session.platform_meta_ref,
        session.stress_report_ref,
        session.replay_bundle_ref,
        session.replay_verification_ref,
        session.governance_ref,
        session.hidden_holdout_ref,
        session.calibration_ref,
        *session.runtime_artifacts_index.values(),
    ]
    strategic_output = session.strategic_output
    if strategic_output is not None:
        candidates.extend(
            (
                strategic_output.strategic_scm_ref,
                strategic_output.strategic_response_bundle_ref,
            )
        )

    outcome = session.outcome
    if outcome is not None:
        candidates.extend((*outcome.audit_refs, *outcome.actionable_side_information_refs))
        for result in outcome.stage_results.values():
            candidates.extend(
                (
                    result.executed_work_packet_ref,
                    result.uncertainty_observation_ref,
                    result.actionable_side_information_ref,
                    *result.audit_refs,
                )
            )
        for step in outcome.trace:
            candidates.append(step.executed_work_packet_ref)

    seen: set[tuple[str, str | None, str, str]] = set()
    for candidate in candidates:
        if not isinstance(candidate, ArtifactRef):
            continue
        identity = (
            str(candidate.artifact_id),
            candidate.manifest_profile_sha256,
            candidate.kind,
            candidate.media_type,
        )
        if identity not in seen:
            seen.add(identity)
            refs.append(candidate)
    return refs


def _funnel_projection_refusal(
    session: _RuntimeSession,
    projection: Any,
    exc: Exception,
) -> NodeOutcome:
    """Return a typed lossless-refusal result without branching or attaching state."""
    findings = _find_non_finite_projection_values(projection)
    if findings:
        first_finding = findings[0]
        failure_basis = "canonical_json_rejected_non_finite_funnel_leaf"
        location = first_finding["location"]
        value_kind = first_finding["kind"]
        message = (
            "Funnel outcome could not be represented as finite state JSON at "
            f"{location} ({value_kind}); the original state was retained."
        )
    else:
        failure_basis = "canonical_json_rejected_funnel_projection"
        location = "$"
        value_kind = "serializer_or_json_value_not_supported"
        message = (
            "Funnel outcome could not be represented as finite state JSON; "
            "the original state was retained."
        )
    error = NodeError(
        code=node_errors.ERROR_INVALID_STATE,
        message=message,
        details={
            "projection": "funnel_outcome",
            "failure_basis": failure_basis,
            "location": location,
            "value_kind": value_kind,
            "non_finite_values": findings,
            "canonical_validation_error": str(exc),
            "funnel_failure_basis": _funnel_projection_failure_basis(session.outcome),
        },
    )
    return NodeOutcome(
        status="fail",
        state=session.state,
        artifacts=_runtime_session_artifact_refs(session),
        error=error,
    )


def _project_voi_scope(transfer_context: Mapping[str, Any]) -> dict[str, str]:
    """Project the producer-resolved typed scope into promotion evidence metadata."""
    scope = TransferContext.model_validate(transfer_context)
    return {
        "task_family": scope.task_family,
        "domain": scope.domain,
        "tenant_scope": scope.tenant_hash or "",
        "tenant_scope_status": scope.tenant_scope_status.value,
    }


def finalize_runtime_session(session: _RuntimeSession) -> NodeOutcome:
    """Persist final evidence, branch state, and emit the node's existing events."""
    owner = session.owner
    ctx = session.ctx
    state = session.state
    outcome = session.outcome
    evidence_bundle = session.evidence_bundle
    predictive_voi = session.predictive_voi
    transfer_context = session.transfer_context
    assert evidence_bundle is not None
    assert session.selection_vector is not None
    assert session.selection_ref is not None
    assert session.evidence_ref is not None

    serialized_funnel_outcome: dict[str, Any] | None = None
    try:
        serialized_funnel_outcome = owner._serialize_funnel_outcome(outcome)
        if not isinstance(serialized_funnel_outcome, dict):
            raise CanonViolation("funnel outcome projection must be a JSON object")
        to_canonical_bytes(
            serialized_funnel_outcome,
            CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
        )
    except (CanonViolation, TypeError, ValueError) as exc:
        return _funnel_projection_refusal(session, serialized_funnel_outcome, exc)

    final_evaluation_vector, final_evaluation_ref = owner._resolve_runtime_policy_evaluation(
        ctx,
        candidate_ref=session.candidate_ref,
        outcome=outcome,
        fallback=session.selection_vector,
        runtime_backend=session.runtime_backend,
    )
    final_replay_bundle_ref = session.replay_bundle_ref
    final_replay_verification_ref = None
    if final_evaluation_ref is not None:
        final_replay_bundle_ref, final_replay_verification_ref = (
            owner._reissue_replay_verification_for_subject(
                ctx,
                run_id=state.run_id,
                candidate_ref=session.candidate_ref,
                evaluation_ref=final_evaluation_ref,
                replay_bundle_ref=session.replay_bundle_ref,
                replay_verification_ref=session.replay_verification_ref,
            )
        )
    stage4_feedback = dict(
        (outcome.stage_results.get(4).feedback or {})
        if outcome.stage_results.get(4) is not None
        else {}
    )
    evidence_bundle = evidence_bundle.model_copy(
        update={
            "evaluation_ref": final_evaluation_ref,
            "replay_bundle_ref": final_replay_bundle_ref,
            "replay_verification_ref": final_replay_verification_ref,
            "metadata": {
                **evidence_bundle.metadata,
                "voi_model_status": [
                    status.model_dump(mode="json") for status in predictive_voi.model_status()
                ],
                "voi_scope": _project_voi_scope(transfer_context),
                "promotion_grade_fidelity": (
                    "full" if outcome.stage_results.get(4) is not None else "selection_only"
                ),
                "promotion_grade_backend_kind": str(
                    stage4_feedback.get("policy_runtime_backend_kind")
                    or session.selection_artifact.provenance.backend_kind
                ),
                "promotion_grade_promotable_source": bool(
                    stage4_feedback.get(
                        "policy_runtime_promotable_source",
                        session.selection_artifact.provenance.promotable_source,
                    )
                ),
                "promotion_grade_degradation_mode": (
                    str(stage4_feedback.get("policy_runtime_degradation_mode"))
                    if stage4_feedback.get("policy_runtime_degradation_mode") is not None
                    else session.selection_artifact.provenance.degradation_mode
                ),
            },
        }
    )
    evidence_ref = owner.persist_promotion_evidence_bundle(
        ctx.store,
        evidence_bundle,
        inputs=[
            input_ref_from_artifact_ref(session.candidate_ref, role="candidate"),
            input_ref_from_artifact_ref(session.selection_ref, role="selection_evaluation"),
            input_ref_from_artifact_ref(
                session.evidence_ref,
                role="source_promotion_evidence_bundle",
            ),
            *(
                [input_ref_from_artifact_ref(final_evaluation_ref, role="policy_evaluation")]
                if final_evaluation_ref is not None
                else []
            ),
            *(
                [input_ref_from_artifact_ref(final_replay_bundle_ref, role="replay_bundle")]
                if final_replay_bundle_ref is not None
                else []
            ),
            *(
                [
                    input_ref_from_artifact_ref(
                        final_replay_verification_ref,
                        role="replay_verification",
                    )
                ]
                if final_replay_verification_ref is not None
                else []
            ),
        ],
    )
    voi_input_refs = [
        ref
        for ref in (session.candidate_ref, final_evaluation_ref, evidence_ref)
        if ref is not None
    ]
    voi_report = predictive_voi.report_for_decisions(
        run_id=state.run_id,
        decisions=(
            [outcome.last_scheduling_decision]
            if outcome.last_scheduling_decision is not None
            else []
        ),
        calibration_status=str(state.params.get("voi_calibration_status") or "shadow"),
        input_refs_by_candidate_id=(
            {outcome.candidate_hash: voi_input_refs}
            if outcome.last_scheduling_decision is not None
            else {}
        ),
        metadata={
            "source": "run_policy_blueprint_runtime",
            "final_action": outcome.final_action,
            "completed": outcome.completed,
            "trace_step_count": len(outcome.trace),
        },
    )
    voi_report_ref = owner.persist_voi_run_report(ctx.store, voi_report)

    new_state = owner.branch_state(
        state,
        write_paths=(
            "artifacts_index",
            "policy_output_bundle_ref",
            "policy_brief_ref",
            "champion_policy_dossier_ref",
            "params.policy_promotion_result",
            "params.judge_verdict",
            "params.decision_readiness_contract",
            "params.promotion_decision",
            "params.policy_promotion_projection_status",
            "params.reported_policy_promotion_history",
            "params.policy_brief",
            "params.translator_compliance",
            "params.policy_candidate_ref",
            "params.policy_evaluation",
            "params.policy_evaluation_ref",
            "params.promotion_evidence_bundle_ref",
            "params.replay_bundle_ref",
            "params.replay_verification_ref",
            "params.funnel_outcome",
            "params._funnel_outcome",
            "params.policy_level5_gate",
            "params.policy_runtime_source_statuses",
            "params.audit_refs",
            "params.actionable_side_information_refs",
            "params.voi_run_report_ref",
            "params.strategic_response",
            "params.strategic_response_source",
        ),
    ).state
    new_state.artifacts_index.update(session.runtime_artifacts_index)
    new_state.params["policy_candidate_ref"] = session.candidate_ref.model_dump(mode="json")
    new_state.params["policy_evaluation"] = final_evaluation_vector.model_dump(mode="json")
    if final_evaluation_ref is not None:
        new_state.params["policy_evaluation_ref"] = final_evaluation_ref.model_dump(mode="json")
    new_state.params["replay_bundle_ref"] = (
        final_replay_bundle_ref.model_dump(mode="json")
        if final_replay_bundle_ref is not None
        else None
    )
    new_state.params["replay_verification_ref"] = (
        final_replay_verification_ref.model_dump(mode="json")
        if final_replay_verification_ref is not None
        else None
    )
    new_state.params["promotion_evidence_bundle_ref"] = evidence_ref.model_dump(mode="json")
    new_state.params["funnel_outcome"] = serialized_funnel_outcome
    new_state.params["_funnel_outcome"] = serialized_funnel_outcome
    new_state.params["policy_level5_gate"] = owner._extract_level5_gate(outcome)
    new_state.params["policy_runtime_source_statuses"] = dict(session.runtime_source_statuses)
    new_state.params["audit_refs"] = [ref.model_dump(mode="json") for ref in outcome.audit_refs]
    new_state.params["actionable_side_information_refs"] = [
        ref.model_dump(mode="json") for ref in outcome.actionable_side_information_refs
    ]
    new_state.params["voi_run_report_ref"] = voi_report_ref.model_dump(mode="json")
    if session.strategic_output.strategic_response_summary is not None:
        new_state.params["strategic_response"] = dict(
            session.strategic_output.strategic_response_summary
        )
        new_state.params.setdefault("strategic_response_source", "policy_runtime")
    new_state.artifacts_index[owner.ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF] = evidence_ref
    new_state.artifacts_index[owner.ARTIFACT_VOI_RUN_REPORT_REF] = voi_report_ref
    if final_replay_bundle_ref is not None:
        new_state.artifacts_index[owner.ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF] = (
            final_replay_bundle_ref
        )
    else:
        new_state.artifacts_index.pop(owner.ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF, None)
    if session.platform_meta_ref is not None:
        new_state.artifacts_index[owner.ARTIFACT_PLATFORM_META_EVALUATION_REPORT_REF] = (
            session.platform_meta_ref
        )
    if session.stress_report_ref is not None:
        new_state.artifacts_index[owner.ARTIFACT_STRESS_TEST_REPORT_REF] = session.stress_report_ref
    if session.ambiguity_certificate_ref is not None:
        new_state.artifacts_index[owner.ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = (
            session.ambiguity_certificate_ref
        )

    promotion_feedback = dict(outcome.final_result.feedback or {}) if outcome.final_result else {}
    _project_promotion_feedback(
        new_state,
        promotion_feedback,
        outcome=outcome,
        candidate_ref=session.candidate_ref,
        evidence_ref=evidence_ref,
    )
    session.evidence_bundle = evidence_bundle
    session.evidence_ref = evidence_ref
    session.final_evaluation_vector = final_evaluation_vector
    session.final_evaluation_ref = final_evaluation_ref
    if final_evaluation_ref is not None:
        session.replay_bundle_ref = final_replay_bundle_ref
        session.replay_verification_ref = final_replay_verification_ref
    session.voi_report_ref = voi_report_ref
    session.new_state = new_state
    return _build_runtime_outcome(session)


def _project_promotion_feedback(
    new_state: Any,
    promotion_feedback: dict[str, Any],
    *,
    outcome: FunnelOutcome,
    candidate_ref: ArtifactRef,
    evidence_ref: ArtifactRef,
) -> None:
    """Keep current promotion projection report-only until an owner receipt exists."""
    admission = _runtime_outcome_score_admission(outcome)
    reason = _promotion_projection_reason(outcome, admission)
    previous_params = {
        key: _report_json_value(new_state.params[key])
        for key in _CURRENT_POLICY_PROMOTION_PARAM_KEYS
        if key in new_state.params
    }
    previous_refs: dict[str, Any] = {}
    state_refs = {
        key: _report_json_value(value)
        for key, value in (
            ("policy_output_bundle_ref", new_state.policy_output_bundle_ref),
            ("policy_brief_ref", new_state.policy_brief_ref),
            ("champion_policy_dossier_ref", new_state.champion_policy_dossier_ref),
        )
        if value is not None
    }
    artifact_refs = {
        key: _report_json_value(new_state.artifacts_index[key])
        for key in _CURRENT_POLICY_OUTPUT_ARTIFACT_KEYS
        if key in new_state.artifacts_index
    }
    if state_refs:
        previous_refs["state"] = state_refs
    if artifact_refs:
        previous_refs["artifacts_index"] = artifact_refs
    incoming_feedback = {
        key: _report_json_value(promotion_feedback[key])
        for key in (
            "promotion_result",
            "judge_verdict",
            "decision_readiness_contract",
            "promotion_decision",
            "promotion_reason",
        )
        if key in promotion_feedback
    }
    history = new_state.params.get("reported_policy_promotion_history")
    if isinstance(history, list):
        history_items = list(history)
    elif "reported_policy_promotion_history" in new_state.params:
        history_items = [
            {
                "record_type": "unparsed_prior_history",
                "value": _report_json_value(history),
            }
        ]
    else:
        history_items = []
    if previous_params or previous_refs:
        history_items.append(
            {
                "record_type": "prior_current_projection",
                "run_id": new_state.run_id,
                "params": previous_params,
                "refs": previous_refs,
            }
        )

    status = {
        "schema_version": "1.0",
        "status": "reported_only",
        "authority_status": "not_established",
        "reason": reason,
        "run_id": new_state.run_id,
        "candidate_ref": candidate_ref.model_dump(mode="json"),
        "promotion_evidence_bundle_ref": evidence_ref.model_dump(mode="json"),
        "score_admission": admission.to_surface_payload(),
        "funnel_final_action": outcome.final_action,
        "funnel_completed": outcome.completed,
        "reported_stage_terminal_action": (
            None if outcome.final_result is None else outcome.final_result.terminal_action
        ),
    }
    history_items.append(
        {
            "record_type": "current_run_reported_feedback",
            "run_id": new_state.run_id,
            "candidate_ref": candidate_ref.model_dump(mode="json"),
            "promotion_evidence_bundle_ref": evidence_ref.model_dump(mode="json"),
            "promotion_projection_status": status,
            "incoming_feedback": incoming_feedback,
        }
    )

    clear_current_policy_promotion_projection(new_state)
    new_state.params["policy_promotion_projection_status"] = status
    new_state.params["reported_policy_promotion_history"] = history_items


def _runtime_outcome_score_admission(outcome: FunnelOutcome) -> ObjectiveScoreAdmission:
    result = outcome.final_result
    if result is None:
        return reconcile_objective_score_assessment(None, None)
    return reconcile_objective_score_assessment(
        result.score_assessment,
        result.simulation_results,
        prior_admission=result.score_admission,
        reported_status=result.score_status,
        reported_value=result.objective_value,
    )


def _promotion_projection_reason(outcome: FunnelOutcome, admission: ObjectiveScoreAdmission) -> str:
    """Name the recomputed blocker without turning score into promotion authority."""
    if admission.status is ObjectiveScoreStatus.INVALID:
        return "selected_score_invalid"
    if admission.status is ObjectiveScoreStatus.UNAVAILABLE:
        return "selected_score_unavailable"
    if admission.status is ObjectiveScoreStatus.NOT_ESTABLISHED:
        return "selected_score_not_established"
    if outcome.final_action != "complete" or not outcome.completed:
        return "funnel_outcome_not_complete"
    return "protected_owner_receipt_not_established"


def _report_json_value(value: Any) -> Any:
    """Retain reported evidence as finite JSON without interpreting it as authority."""
    if value is None or type(value) in {str, bool, int}:
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, float):
        return value if math.isfinite(value) else {"non_finite_float": repr(value)}
    if isinstance(value, BaseModel):
        return _report_json_value(value.model_dump(mode="json"))
    if is_dataclass(value):
        return _report_json_value(
            {field.name: getattr(value, field.name) for field in fields(value)}
        )
    if isinstance(value, Mapping):
        return {str(key): _report_json_value(member) for key, member in value.items()}
    if isinstance(value, (list, tuple)):
        return [_report_json_value(member) for member in value]
    return {
        "unprojected_type": f"{type(value).__module__}.{type(value).__qualname__}",
        "repr": repr(value),
    }


def _build_runtime_outcome(session: _RuntimeSession) -> NodeOutcome:
    owner = session.owner
    outcome = session.outcome
    artifacts = [session.selection_ref, session.evidence_ref]
    artifacts.extend(
        ref
        for ref in (
            session.ambiguity_certificate_ref,
            session.strategic_output.strategic_scm_ref,
            session.strategic_output.strategic_response_bundle_ref,
            session.platform_meta_ref,
            session.stress_report_ref,
        )
        if ref is not None
    )
    artifacts.append(session.voi_report_ref)
    events = [
        NodeEvent(
            level="info",
            message="Blueprint-native policy runtime executed through L0-L6.",
            attrs={
                "final_action": outcome.final_action,
                "completed": outcome.completed,
                "has_hidden_holdout": session.hidden_holdout_ref is not None,
            },
        )
    ]
    if session.cross_graph_profile is None and session.runtime_source_statuses:
        events.append(
            NodeEvent(
                level="info",
                message=(
                    "Policy runtime inferred evidence source availability from config "
                    "because no cross-graph profile artifact was available."
                ),
                attrs={"evidence_source_statuses": dict(session.runtime_source_statuses)},
            )
        )
    if session.phase_d4_warnings:
        events.append(
            NodeEvent(
                level="warn",
                message="Phase D.4 challenge suites emitted warnings.",
                attrs={"warnings": list(session.phase_d4_warnings)},
            )
        )
    if session.strategic_output.warnings:
        events.append(
            NodeEvent(
                level="warn",
                message="Strategic runtime artifact flow emitted warnings.",
                attrs={"warnings": list(session.strategic_output.warnings)},
            )
        )
    return NodeOutcome(status="ok", state=session.new_state, artifacts=artifacts, events=events)
