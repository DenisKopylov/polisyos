"""Public governance calibration module API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.observation.contracts import ObservationFamily
from polisyos.ir.observation.governance import (
    DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY,
    GovernancePassMappingRegistry,
    ObservationFamilyPolicyRegistry,
)
from polisyos.scientist.backtesting import (
    ABSTRACTION_LEAKAGE_SUITE_ID,
    MULTIPLICITY_DISCLOSURE_SUITE_ID,
    STRATEGIC_GAMING_SUITE_ID,
)
from polisyos.scientist.backtesting.adversarial import ChallengeSuiteResult, run_phase_d4_challenge_suites
from polisyos.scientist.discovery.active import (
    ActiveDisambiguationPlan,
    ActiveDisambiguationPlanner,
    ActiveDisambiguationPlannerInput,
    DisambiguationAction,
    DisambiguationTarget,
)
from polisyos.scientist.governance.pass_registry import load_governance_passes
from polisyos.scientist.governance.pipeline import ValidationPipeline
from polisyos.scientist.governance.report import GovernanceReport


class CalibrationPassResult(BaseModel):
    """Execution summary for one governance pass within calibration review."""

    model_config = ConfigDict(extra="forbid")

    pass_id: str = Field(min_length=1)
    executed: bool = True
    estimated_cost_ms: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    issue_count: int = Field(default=0, ge=0)
    blocker_count: int = Field(default=0, ge=0)
    issues: list[ComplianceIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CalibrationFamilyGovernanceResult(BaseModel):
    """Per-observation-family governance outcome for calibration review."""

    model_config = ConfigDict(extra="forbid")

    family: ObservationFamily
    configured_pass_ids: list[str] = Field(default_factory=list)
    adversarial_aliases: list[str] = Field(default_factory=list)
    pass_results: list[CalibrationPassResult] = Field(default_factory=list)
    issues: list[ComplianceIssue] = Field(default_factory=list)
    blocker_count: int = Field(default=0, ge=0)
    trace: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CalibrationAdversarialResult(BaseModel):
    """Outcome of one required adversarial or challenge suite."""

    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=1)
    suite_id: str = Field(min_length=1)
    required: bool = False
    status: Literal["passed", "failed", "missing_inputs", "not_applicable"]
    issues: list[ComplianceIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suite_result: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CalibrationGovernanceInput(BaseModel):
    """Inputs required to run calibration governance over a candidate policy."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    run_id: str = Field(min_length=1)
    observation_families: list[ObservationFamily] = Field(default_factory=list, min_length=1)
    profile: ValidationProfile
    pass_state: dict[str, Any] = Field(default_factory=dict)
    candidate_ref: ArtifactRef
    artifacts_index: dict[str, ArtifactRef] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    selection_metadata: dict[str, Any] | None = None
    lesson_registry: Any | None = None
    active_disambiguation_input: ActiveDisambiguationPlannerInput | None = None


class CalibrationGovernanceReport(BaseModel):
    """Top-level report returned by the calibration governance runner."""

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["approve", "needs_revision", "reject", "human_gate"]
    global_results: list[CalibrationPassResult] = Field(default_factory=list)
    family_results: list[CalibrationFamilyGovernanceResult] = Field(default_factory=list)
    adversarial_results: list[CalibrationAdversarialResult] = Field(default_factory=list)
    issues: list[ComplianceIssue] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    lesson_card_ref: ArtifactRef | None = None
    active_disambiguation_targets: list[DisambiguationTarget] = Field(default_factory=list)
    active_disambiguation_actions: list[DisambiguationAction] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def resolved_verdict(self) -> Literal["approve", "needs_revision", "reject", "human_gate"]:
        """Compute the effective verdict from the collected issues."""

        if any(issue.code == "HUMAN_REVIEW_REQUESTED" for issue in self.issues):
            return "human_gate"
        if any(issue.severity == IssueSeverity.BLOCKER for issue in self.issues):
            return "reject"
        if self.issues:
            return "needs_revision"
        return "approve"

    def to_governance_report(self) -> GovernanceReport:
        """Project the calibration-specific report into the generic governance format."""

        return GovernanceReport(
            verdict=self.resolved_verdict(),
            issues=[issue.model_dump(mode="json") for issue in self.issues],
            notes=list(self.notes),
        )


class CalibrationAdversarialSuiteRegistry(BaseModel):
    """Registry mapping governance aliases to challenge-suite ids."""

    model_config = ConfigDict(extra="forbid")

    suite_aliases: dict[str, str] = Field(default_factory=dict)

    def suite_id_for(self, alias: str) -> str | None:
        return self.suite_aliases.get(alias)

    def is_alias(self, alias: str) -> bool:
        return alias in self.suite_aliases

    @classmethod
    def default(cls) -> "CalibrationAdversarialSuiteRegistry":
        return cls(
            suite_aliases={
                "strategic_gaming_adversarial": STRATEGIC_GAMING_SUITE_ID,
                "multiplicity_disclosure_adversarial": MULTIPLICITY_DISCLOSURE_SUITE_ID,
                "abstraction_leakage_adversarial": ABSTRACTION_LEAKAGE_SUITE_ID,
            }
        )


class LessonCardPublisher:
    """Publisher that records calibration-governance lessons into local search memory."""

    def publish(
        self,
        bundle: CalibrationGovernanceInput,
        report: CalibrationGovernanceReport,
    ) -> ArtifactRef | None:
        from polisyos.scientist.search.lessons import LessonCard, LessonKind, LessonTrustLevel
        from polisyos.scientist.search.transfer_context import resolve_transfer_context

        registry = bundle.lesson_registry
        if registry is None or not hasattr(registry, "record_local"):
            return None

        verdict = report.resolved_verdict()
        kind = LessonKind.SUCCESS if verdict == "approve" else LessonKind.FAILURE
        failed_pass_ids = sorted({issue.pass_id for issue in report.issues if issue.pass_id})
        suite_ids = [
            result.suite_id
            for result in report.adversarial_results
            if result.status != "not_applicable"
        ]
        metadata = {
            "run_id": bundle.run_id,
            "observation_families": [family.value for family in bundle.observation_families],
            "failed_pass_ids": failed_pass_ids,
            "suite_ids": suite_ids,
            "verdict": verdict,
            "candidate_ref": bundle.candidate_ref.model_dump(mode="json"),
            "artifacts_index": {
                key: ref.model_dump(mode="json") for key, ref in bundle.artifacts_index.items()
            },
            **dict(report.metadata),
        }
        remediation = next(
            (issue.suggestion for issue in report.issues if issue.suggestion),
            None,
        )
        lesson_context = resolve_transfer_context(
            run_id=bundle.run_id,
            task_family="policy",
        )
        card = LessonCard(
            kind=kind,
            summary=(
                f"Calibration governance completed with verdict '{verdict}' "
                f"for {len(bundle.observation_families)} observation families."
            ),
            failure_type=(
                "calibration_governance_success"
                if verdict == "approve"
                else f"calibration_governance_{verdict}"
            ),
            stage_name="calibration_governance",
            fidelity_level=0,
            candidate_hash=str(bundle.candidate_ref.artifact_id),
            source_run_id=bundle.run_id,
            confidence=1.0 if verdict == "approve" else 0.75,
            trust_level=LessonTrustLevel.LOCAL,
            task_family=lesson_context.task_family,
            domain=lesson_context.domain,
            tags=[family.value for family in bundle.observation_families],
            remediation_hint=remediation,
            trace_refs=list(report.metadata.get("execution_sequence", [])),
            metadata=metadata,
        )
        return registry.record_local(card, context=lesson_context)


class ActiveDisambiguationIntegration:
    """Thin wrapper around the active-disambiguation planner."""

    def __init__(self, planner: ActiveDisambiguationPlanner | None = None) -> None:
        self._planner = planner or ActiveDisambiguationPlanner()

    def plan(
        self,
        planner_input: ActiveDisambiguationPlannerInput | None,
    ) -> ActiveDisambiguationPlan | None:
        if planner_input is None:
            return None
        return self._planner.plan(planner_input)


@dataclass(frozen=True)
class _ScopeRunResult:
    pass_results: list[CalibrationPassResult]
    issues: list[ComplianceIssue]
    blocker_count: int
    trace: dict[str, Any]
    executed_pass_ids: list[str]


class CalibrationGovernanceRunner:
    """Runner that executes the calibration-governance stack.

    The runner evaluates global passes, family-scoped passes, required
    adversarial suites, and optional active disambiguation, then assembles a
    promotion-oriented governance report and lesson card.
    """

    def __init__(
        self,
        *,
        passes: Sequence[ValidatorPass] | None = None,
        policy_registry: ObservationFamilyPolicyRegistry | None = None,
        mapping_registry: GovernancePassMappingRegistry | None = None,
        adversarial_suite_registry: CalibrationAdversarialSuiteRegistry | None = None,
        lesson_publisher: LessonCardPublisher | None = None,
        active_disambiguation_integration: ActiveDisambiguationIntegration | None = None,
    ) -> None:
        self._passes = list(passes or load_governance_passes())
        self._pass_lookup = {validator.pass_id: validator for validator in self._passes}
        self._pipeline = ValidationPipeline(self._passes)
        self._policy_registry = policy_registry or DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY
        self._mapping_registry = mapping_registry or GovernancePassMappingRegistry.from_policy_registry(
            self._policy_registry
        )
        self._adversarial_suite_registry = (
            adversarial_suite_registry or CalibrationAdversarialSuiteRegistry.default()
        )
        self._lesson_publisher = lesson_publisher or LessonCardPublisher()
        self._active_disambiguation_integration = (
            active_disambiguation_integration or ActiveDisambiguationIntegration()
        )

    def run(self, bundle: CalibrationGovernanceInput) -> CalibrationGovernanceReport:
        """Run calibration governance for the supplied candidate bundle."""

        families = _ordered_families(bundle.observation_families)
        execution_sequence: list[str] = []
        global_results, family_results, adversarial_results = [], [], []
        issues: list[ComplianceIssue] = []
        notes: list[str] = []
        short_circuited = False

        global_scope = self._run_scope(
            run_id=bundle.run_id,
            profile=bundle.profile,
            pass_ids=list(self._mapping_registry.global_mandatory_passes),
            pass_state=dict(bundle.pass_state),
        )
        global_results.extend(global_scope.pass_results)
        issues.extend(global_scope.issues)
        execution_sequence.extend(f"global:{pass_id}" for pass_id in global_scope.executed_pass_ids)
        if global_scope.blocker_count > 0 and bundle.profile.short_circuit_on_blocker:
            short_circuited = True

        configured_family_aliases: dict[ObservationFamily, list[str]] = {}
        if not short_circuited:
            for family in families:
                configured_pass_ids = self._mapping_registry.for_family(family)
                adversarial_aliases = [
                    pass_id
                    for pass_id in configured_pass_ids
                    if self._adversarial_suite_registry.is_alias(pass_id)
                ]
                configured_family_aliases[family] = adversarial_aliases
                scope = self._run_scope(
                    run_id=bundle.run_id,
                    profile=bundle.profile,
                    pass_ids=configured_pass_ids,
                    pass_state={**bundle.pass_state, "observation_family": family.value},
                )
                family_results.append(
                    CalibrationFamilyGovernanceResult(
                        family=family,
                        configured_pass_ids=configured_pass_ids,
                        adversarial_aliases=adversarial_aliases,
                        pass_results=scope.pass_results,
                        issues=scope.issues,
                        blocker_count=scope.blocker_count,
                        trace=scope.trace,
                    )
                )
                issues.extend(scope.issues)
                execution_sequence.extend(
                    f"{family.value}:{pass_id}" for pass_id in scope.executed_pass_ids
                )
                if scope.blocker_count > 0 and bundle.profile.short_circuit_on_blocker:
                    short_circuited = True
                    break

        if not short_circuited:
            adversarial_outcome = self._run_adversarial(bundle, configured_family_aliases)
            adversarial_results.extend(adversarial_outcome.results)
            issues.extend(adversarial_outcome.issues)
            notes.extend(adversarial_outcome.notes)
            execution_sequence.extend(adversarial_outcome.execution_sequence)

        active_disambiguation_plan = self._active_disambiguation_integration.plan(
            bundle.active_disambiguation_input
        )
        if active_disambiguation_plan is None:
            notes.append("active_disambiguation:not_requested")
            active_targets: list[DisambiguationTarget] = []
            active_actions: list[DisambiguationAction] = []
        else:
            notes.append(f"active_disambiguation:{active_disambiguation_plan.status}")
            active_targets = list(active_disambiguation_plan.targets)
            active_actions = list(active_disambiguation_plan.actions)

        report = CalibrationGovernanceReport(
            verdict="approve",
            global_results=global_results,
            family_results=family_results,
            adversarial_results=adversarial_results,
            issues=issues,
            notes=notes,
            active_disambiguation_targets=active_targets,
            active_disambiguation_actions=active_actions,
            metadata={
                "execution_sequence": execution_sequence,
                "short_circuited": short_circuited,
                "observation_families": [family.value for family in families],
                "global_mandatory_passes": list(self._mapping_registry.global_mandatory_passes),
            },
        )
        report = report.model_copy(update={"verdict": report.resolved_verdict()})
        lesson_card_ref = self._lesson_publisher.publish(bundle, report)
        if lesson_card_ref is not None:
            report = report.model_copy(update={"lesson_card_ref": lesson_card_ref})
        return report

    def _run_scope(
        self,
        *,
        run_id: str,
        profile: ValidationProfile,
        pass_ids: list[str],
        pass_state: dict[str, Any],
    ) -> _ScopeRunResult:
        real_pass_ids = [
            pass_id for pass_id in pass_ids if not self._adversarial_suite_registry.is_alias(pass_id)
        ]
        missing_pass_ids = [pass_id for pass_id in real_pass_ids if pass_id not in self._pass_lookup]
        issues = [
            ComplianceIssue(
                pass_id=pass_id,
                path=["governance", "pass_registry", pass_id],
                message=f"Configured governance pass '{pass_id}' is unavailable.",
                severity=IssueSeverity.BLOCKER,
                code="GOVERNANCE_PASS_UNAVAILABLE",
                suggestion="Register the pass in scientist.governance.pass_entrypoints.",
            )
            for pass_id in missing_pass_ids
        ]
        selected_pass_ids = [pass_id for pass_id in real_pass_ids if pass_id in self._pass_lookup]
        trace_dict: dict[str, Any] = {}
        if selected_pass_ids:
            effective_profile = ValidationProfile(
                level=profile.level,
                pass_ids=frozenset(selected_pass_ids),
                thresholds=dict(profile.thresholds),
                short_circuit_on_blocker=profile.short_circuit_on_blocker,
            )
            pass_ctx = PassContext(
                ir=None,
                state=pass_state,
                registry_bundle=None,
                profile=effective_profile,
                run_id=run_id,
            )
            pipeline_issues, trace = self._pipeline.validate(pass_ctx, effective_profile)
            issues.extend(pipeline_issues)
            trace_dict = trace.to_dict()
        else:
            trace_dict = {
                "run_id": run_id,
                "profile": profile.level.value,
                "short_circuited": False,
                "spans": [],
            }

        span_by_id = {
            str(span["pass_id"]): span
            for span in trace_dict.get("spans", [])
            if isinstance(span, dict) and span.get("pass_id")
        }
        pass_results: list[CalibrationPassResult] = []
        for pass_id in selected_pass_ids:
            span = span_by_id.get(pass_id)
            pass_issues = [issue for issue in issues if issue.pass_id == pass_id]
            pass_results.append(
                CalibrationPassResult(
                    pass_id=pass_id,
                    executed=span is not None,
                    estimated_cost_ms=self._pass_lookup[pass_id].estimated_cost_ms,
                    duration_ms=None if span is None else span.get("duration_ms"),
                    issue_count=len(pass_issues),
                    blocker_count=sum(
                        1 for issue in pass_issues if issue.severity == IssueSeverity.BLOCKER
                    ),
                    issues=pass_issues,
                    metadata={
                        "skipped_due_to_short_circuit": (
                            span is None and bool(trace_dict.get("short_circuited"))
                        )
                    },
                )
            )
        for pass_id in missing_pass_ids:
            pass_results.append(
                CalibrationPassResult(
                    pass_id=pass_id,
                    executed=False,
                    issue_count=1,
                    blocker_count=1,
                    issues=[issue for issue in issues if issue.pass_id == pass_id],
                    metadata={"missing_validator": True},
                )
            )

        blocker_count = sum(1 for issue in issues if issue.severity == IssueSeverity.BLOCKER)
        executed_pass_ids = [
            str(span["pass_id"])
            for span in trace_dict.get("spans", [])
            if isinstance(span, dict) and span.get("pass_id")
        ]
        return _ScopeRunResult(
            pass_results=pass_results,
            issues=issues,
            blocker_count=blocker_count,
            trace=trace_dict,
            executed_pass_ids=executed_pass_ids,
        )

    def _run_adversarial(
        self,
        bundle: CalibrationGovernanceInput,
        configured_family_aliases: dict[ObservationFamily, list[str]],
    ) -> "_AdversarialOutcome":
        required = {
            "multiplicity_disclosure_adversarial": True,
            "strategic_gaming_adversarial": (
                any(
                    "strategic_gaming_adversarial" in aliases
                    for aliases in configured_family_aliases.values()
                )
                or any(
                    self._policy_registry.for_family(family).requires_strategic_response_check
                    for family in configured_family_aliases
                )
            ),
            "abstraction_leakage_adversarial": _uses_abstraction(bundle),
        }
        store = bundle.pass_state.get("_store")
        if store is None:
            suite_results: list[ChallengeSuiteResult] = []
            warnings = ["adversarial_suite_store_missing"]
        else:
            suite_results, warnings = run_phase_d4_challenge_suites(
                store=store,
                run_id=bundle.run_id,
                loop_id=str(bundle.params.get("loop_id") or "calibration_governance"),
                candidate_ref=bundle.candidate_ref,
                params=bundle.params,
                artifacts_index=bundle.artifacts_index,
                selection_metadata=bundle.selection_metadata,
            )
        results_by_suite = {result.suite_id: result for result in suite_results}

        adversarial_results: list[CalibrationAdversarialResult] = []
        issues: list[ComplianceIssue] = []
        execution_sequence: list[str] = []
        for alias, suite_id in self._adversarial_suite_registry.suite_aliases.items():
            suite_result = results_by_suite.get(suite_id)
            is_required = bool(required.get(alias, False))
            if suite_result is None:
                status: Literal["passed", "failed", "missing_inputs", "not_applicable"]
                status = "missing_inputs" if is_required else "not_applicable"
                result_issues = []
                if is_required:
                    result_issues.append(_adversarial_missing_issue(alias, suite_id))
                    issues.extend(result_issues)
                adversarial_results.append(
                    CalibrationAdversarialResult(
                        alias=alias,
                        suite_id=suite_id,
                        required=is_required,
                        status=status,
                        issues=result_issues,
                        warnings=list(warnings),
                    )
                )
                continue

            execution_sequence.append(f"adversarial:{alias}")
            failed = not suite_result.benchmark_evaluation.promotable
            result_issues = []
            if failed and is_required:
                result_issues.append(_adversarial_failure_issue(alias, suite_result))
                issues.extend(result_issues)
            adversarial_results.append(
                CalibrationAdversarialResult(
                    alias=alias,
                    suite_id=suite_id,
                    required=is_required,
                    status="failed" if failed else "passed",
                    issues=result_issues,
                    warnings=list(warnings),
                    suite_result=_challenge_suite_payload(suite_result),
                )
            )

        return _AdversarialOutcome(
            results=adversarial_results,
            issues=issues,
            notes=list(warnings),
            execution_sequence=execution_sequence,
        )


@dataclass(frozen=True)
class _AdversarialOutcome:
    results: list[CalibrationAdversarialResult]
    issues: list[ComplianceIssue]
    notes: list[str]
    execution_sequence: list[str]


def _ordered_families(families: Sequence[ObservationFamily]) -> list[ObservationFamily]:
    seen = {family for family in families}
    return [family for family in ObservationFamily if family in seen]


def _uses_abstraction(bundle: CalibrationGovernanceInput) -> bool:
    if bool(bundle.params.get("uses_abstraction")):
        return True
    if bundle.params.get("abstraction_preservation_type") is not None:
        return True
    if bundle.params.get("abm_alignment_warnings") is not None:
        return True
    return any(
        key in bundle.artifacts_index
        for key in {"abstraction_certificate_ref", "finite_state_abstraction_map_ref"}
    )


def _challenge_suite_payload(result: ChallengeSuiteResult) -> dict[str, Any]:
    return {
        "suite_id": result.suite_id,
        "suite_version": result.suite_version,
        "runtime_split_type": result.runtime_split_type.value,
        "benchmark_evaluation": result.benchmark_evaluation.model_dump(mode="json"),
        "stress_test_report": (
            None
            if result.stress_test_report is None
            else result.stress_test_report.model_dump(mode="json")
        ),
        "warnings": list(result.warnings),
    }


def _adversarial_missing_issue(alias: str, suite_id: str) -> ComplianceIssue:
    return ComplianceIssue(
        pass_id=alias,
        path=["adversarial", alias],
        message=f"Required adversarial suite '{suite_id}' is missing required inputs.",
        severity=IssueSeverity.BLOCKER,
        code="ADVERSARIAL_SUITE_MISSING_INPUTS",
        suggestion="Provide the artifacts or summary payload needed by the calibration challenge suite.",
    )


def _adversarial_failure_issue(
    alias: str,
    suite_result: ChallengeSuiteResult,
) -> ComplianceIssue:
    return ComplianceIssue(
        pass_id=alias,
        path=["adversarial", alias],
        message=f"Required adversarial suite '{suite_result.suite_id}' failed promotion guardrails.",
        severity=IssueSeverity.BLOCKER,
        code="ADVERSARIAL_SUITE_FAILED",
        suggestion="Review the suite diagnostics and repair the calibration before promotion.",
        input_value=suite_result.suite_id,
    )


__all__ = [
    "ActiveDisambiguationIntegration",
    "CalibrationAdversarialResult",
    "CalibrationAdversarialSuiteRegistry",
    "CalibrationFamilyGovernanceResult",
    "CalibrationGovernanceInput",
    "CalibrationGovernanceReport",
    "CalibrationGovernanceRunner",
    "CalibrationPassResult",
    "LessonCardPublisher",
]
