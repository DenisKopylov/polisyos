"""Execute C5b replay validation and persist promotion bundles for calibration candidates.

The runner composes historical backtest replay, stress-scenario evaluation, and
leaderboard scoring into one `CalibrationValidationBundle`. If C5a governance
already short-circuited, the bundle is persisted as `blocked_by_governance`
without running replay so downstream promotion logic can audit the stop reason.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.backtest import BacktestReportRef
from polisyos.core.contracts.scientist import (
    CalibrationValidationBundleRef,
    GovernanceAccountabilityArtifactRef,
    StressTestReportRef,
)
from polisyos.ir.analytics.interference import InterferenceCertificate, NetworkInterferenceReport
from polisyos.ir.analytics.transportability import TransportabilityResult
from polisyos.ir.observation.bundles import BacktestPlanBundle
from polisyos.ir.observation.contract_compilers import SpecificationCurveInput
from polisyos.scientist.methods.discovery.utility_judge import DownstreamUtilityReport
from polisyos.scientist.governance.accountability import (
    GovernanceAccountabilityInput,
    build_governance_accountability_artifact,
    persist_governance_accountability_artifact,
)
from polisyos.scientist.governance.backtest_matrix import (
    BacktestKind,
    BacktestMatrixResult,
    BacktestMatrixRunner,
)
from polisyos.scientist.governance.calibration import CalibrationGovernanceReport
from polisyos.scientist.governance.calibration_leaderboard import (
    CalibrationLeaderboard,
    CalibrationLeaderboardEntry,
)
from polisyos.scientist.governance.stress_scenarios import (
    StressScenarioKind,
    StressScenarioResult,
    StressScenarioRunner,
)


class CalibrationValidationRunnerInput(BaseModel):
    """Input payload for C5b calibration validation and promotion scoring.

    The bundle links the candidate artifact, C5a governance report, replay
    inputs, baseline metrics, and optional strategic/interference summaries that
    feed leaderboard metrics and lesson publication.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    run_id: str = Field(min_length=1)
    candidate_ref: ArtifactRef
    governance_report: CalibrationGovernanceReport
    calibration_fit_score: float | None = Field(default=None, ge=0.0, le=1.0)
    backtest_plan_bundles: dict[BacktestKind, BacktestPlanBundle] = Field(default_factory=dict)
    specification_curve_input: SpecificationCurveInput | None = None
    downstream_utility_report: DownstreamUtilityReport | None = None
    transportability_result: TransportabilityResult | None = None
    network_interference_report: NetworkInterferenceReport | None = None
    interference_certificate: InterferenceCertificate | None = None
    strategic_summary: dict[str, Any] | None = None
    baseline_metrics: dict[str, float] = Field(default_factory=dict)
    baseline_objective: float | None = None
    scenario_objective_overrides: dict[StressScenarioKind, float] = Field(default_factory=dict)
    scenario_metric_overrides: dict[StressScenarioKind, dict[str, float]] = Field(
        default_factory=dict
    )
    lesson_registry: Any | None = None
    accountability_input: GovernanceAccountabilityInput | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CalibrationValidationBundle(BaseModel):
    """Persisted bundle combining backtest, stress, and leaderboard validation.

    This is the durable decision artifact consumed by promotion dashboards and
    downstream orchestration. `status` records whether replay ran or governance
    blocked first, while the nested report refs preserve the audit trail.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    run_id: str = Field(min_length=1)
    candidate_ref: ArtifactRef
    governance_verdict: str = Field(min_length=1)
    status: str = Field(pattern="^(completed|blocked_by_governance)$")
    backtest_matrix: BacktestMatrixResult | None = None
    stress_scenarios: StressScenarioResult | None = None
    leaderboard_entry: CalibrationLeaderboardEntry | None = None
    lesson_card_ref: ArtifactRef | None = None
    governance_accountability_ref: GovernanceAccountabilityArtifactRef | None = None
    governance_accountability_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def readout_summary(self) -> dict[str, Any]:
        """Return a compact promotion-oriented summary for UIs and lessons."""

        entry = self.leaderboard_entry
        metrics = None if entry is None else entry.metrics
        return {
            "status": self.status,
            "composite_score": None if metrics is None else metrics.composite_score,
            "eligible_for_promotion": False if metrics is None else metrics.eligible_for_promotion,
            "worst_backtest_kind": (
                None
                if self.backtest_matrix is None or self.backtest_matrix.worst_kind is None
                else self.backtest_matrix.worst_kind.value
            ),
            "worst_stress_scenario": (
                None
                if self.stress_scenarios is None or self.stress_scenarios.worst_scenario is None
                else self.stress_scenarios.worst_scenario.value
            ),
            "specification_curve_robustness": (
                None if metrics is None else metrics.specification_curve_robustness
            ),
            "transportability_score": None if metrics is None else metrics.transportability_score,
            "interference_fit": None if metrics is None else metrics.interference_fit,
            "strategic_response_plausibility": (
                None if metrics is None else metrics.strategic_response_plausibility
            ),
            "gap_flags": [] if metrics is None else list(metrics.gap_flags),
            "risk_weighted_verdict": self.governance_accountability_summary.get(
                "risk_weighted_verdict"
            ),
            "requires_human_review": self.governance_accountability_summary.get(
                "requires_human_review"
            ),
            "failed_accountability_thresholds": list(
                self.governance_accountability_summary.get("failed_thresholds", [])
            ),
            "escalation_triggers": list(
                self.governance_accountability_summary.get("escalation_triggers", [])
            ),
            "accountability_ref": (
                None
                if self.governance_accountability_ref is None
                else str(self.governance_accountability_ref.artifact_id)
            ),
            "accountability_summary": dict(self.governance_accountability_summary),
        }

    @property
    def backtest_report_ref(self) -> BacktestReportRef | None:
        return None if self.backtest_matrix is None else self.backtest_matrix.backtest_report_ref

    @property
    def stress_test_report_ref(self) -> StressTestReportRef | None:
        return (
            None if self.stress_scenarios is None else self.stress_scenarios.stress_test_report_ref
        )


class CalibrationValidationRunnerResult(BaseModel):
    """Pair the persisted bundle ref with the in-memory validation payload."""

    model_config = ConfigDict(extra="forbid")

    bundle_ref: CalibrationValidationBundleRef
    bundle: CalibrationValidationBundle


class CalibrationValidationRunner:
    """Runner for the C5b calibration validation stage.

    Orchestrates the backtest matrix, stress scenarios, and leaderboard scoring,
    then persists a single `CalibrationValidationBundle` that downstream
    promotion logic can consume.
    """

    def __init__(
        self,
        store: FileSystemCAS,
        *,
        backtest_runner: BacktestMatrixRunner | None = None,
        stress_runner: StressScenarioRunner | None = None,
        leaderboard: CalibrationLeaderboard | None = None,
        lesson_publisher: CalibrationValidationLessonPublisher | None = None,
    ) -> None:
        self._store = store
        self._backtest_runner = backtest_runner or BacktestMatrixRunner(store)
        self._stress_runner = stress_runner or StressScenarioRunner(store)
        self._leaderboard = leaderboard or CalibrationLeaderboard()
        self._lesson_publisher = lesson_publisher or CalibrationValidationLessonPublisher()

    def run(self, bundle: CalibrationValidationRunnerInput) -> CalibrationValidationRunnerResult:
        """Execute the full calibration validation stage for one candidate."""

        if bool(bundle.governance_report.metadata.get("short_circuited")):
            blocked = CalibrationValidationBundle(
                run_id=bundle.run_id,
                candidate_ref=bundle.candidate_ref,
                governance_verdict=bundle.governance_report.resolved_verdict(),
                status="blocked_by_governance",
                metadata={"blocked_reason": "c5a_short_circuited", **dict(bundle.metadata)},
            )
            blocked = self._attach_accountability_artifact(
                bundle_input=bundle,
                validation_bundle=blocked,
            )
            blocked_ref = persist_calibration_validation_bundle(self._store, blocked)
            return CalibrationValidationRunnerResult(bundle_ref=blocked_ref, bundle=blocked)

        artifact_inputs = [InputRef(artifact_id=bundle.candidate_ref.artifact_id, role="candidate")]
        backtest_matrix = self._backtest_runner.run(
            bundle.backtest_plan_bundles,
            inputs=artifact_inputs,
            metadata={"run_id": bundle.run_id},
        )
        baseline_metrics = (
            dict(bundle.baseline_metrics)
            if bundle.baseline_metrics
            else {"policy_value": float(bundle.calibration_fit_score or 1.0)}
        )
        stress_scenarios = self._stress_runner.run(
            baseline_metrics=baseline_metrics,
            baseline_objective=bundle.baseline_objective,
            scenario_objective_overrides=bundle.scenario_objective_overrides,
            scenario_metric_overrides=bundle.scenario_metric_overrides,
            inputs=artifact_inputs,
            metadata={"run_id": bundle.run_id},
        )
        leaderboard_entry = self._leaderboard.build_entry(
            run_id=bundle.run_id,
            candidate_ref=bundle.candidate_ref,
            governance_report=bundle.governance_report,
            calibration_fit_score=bundle.calibration_fit_score,
            backtest_matrix=backtest_matrix,
            stress_scenarios=stress_scenarios,
            specification_curve_input=bundle.specification_curve_input,
            downstream_utility_report=bundle.downstream_utility_report,
            transportability_result=bundle.transportability_result,
            network_interference_report=bundle.network_interference_report,
            interference_certificate=bundle.interference_certificate,
            strategic_summary=bundle.strategic_summary,
            metadata={"run_id": bundle.run_id},
        )
        leaderboard_entry = self._leaderboard.rank([leaderboard_entry])[0]
        validation_bundle = CalibrationValidationBundle(
            run_id=bundle.run_id,
            candidate_ref=bundle.candidate_ref,
            governance_verdict=bundle.governance_report.resolved_verdict(),
            status="completed",
            backtest_matrix=backtest_matrix,
            stress_scenarios=stress_scenarios,
            leaderboard_entry=leaderboard_entry,
            metadata=dict(bundle.metadata),
        )
        lesson_card_ref = self._lesson_publisher.publish(bundle, validation_bundle)
        if lesson_card_ref is not None:
            validation_bundle = validation_bundle.model_copy(
                update={"lesson_card_ref": lesson_card_ref}
            )
        validation_bundle = self._attach_accountability_artifact(
            bundle_input=bundle,
            validation_bundle=validation_bundle,
        )
        bundle_ref = persist_calibration_validation_bundle(
            self._store,
            validation_bundle,
            inputs=artifact_inputs,
        )
        return CalibrationValidationRunnerResult(bundle_ref=bundle_ref, bundle=validation_bundle)

    def _attach_accountability_artifact(
        self,
        *,
        bundle_input: CalibrationValidationRunnerInput,
        validation_bundle: CalibrationValidationBundle,
    ) -> CalibrationValidationBundle:
        leaderboard_metrics = (
            None
            if validation_bundle.leaderboard_entry is None
            else validation_bundle.leaderboard_entry.metrics
        )
        stress_summary = (
            None
            if validation_bundle.stress_scenarios is None
            else {
                "worst_scenario": (
                    None
                    if validation_bundle.stress_scenarios.worst_scenario is None
                    else validation_bundle.stress_scenarios.worst_scenario.value
                ),
                "critical_count": validation_bundle.stress_scenarios.critical_count,
                "high_count": validation_bundle.stress_scenarios.high_count,
            }
        )
        accountability_artifact = build_governance_accountability_artifact(
            run_id=bundle_input.run_id,
            candidate_ref=bundle_input.candidate_ref,
            governance_verdict=bundle_input.governance_report.resolved_verdict(),
            governance_issues=bundle_input.governance_report.issues,
            adversarial_results=bundle_input.governance_report.adversarial_results,
            composite_score=(
                None if leaderboard_metrics is None else leaderboard_metrics.composite_score
            ),
            eligible_for_promotion=(
                None if leaderboard_metrics is None else leaderboard_metrics.eligible_for_promotion
            ),
            stress_summary=stress_summary,
            accountability_input=bundle_input.accountability_input,
        )
        accountability_ref = persist_governance_accountability_artifact(
            self._store,
            accountability_artifact,
            inputs=[
                InputRef(artifact_id=bundle_input.candidate_ref.artifact_id, role="candidate"),
            ],
        )
        return validation_bundle.model_copy(
            update={
                "governance_accountability_ref": accountability_ref,
                "governance_accountability_summary": accountability_artifact.compact_summary(),
            }
        )


class CalibrationValidationLessonPublisher:
    """Publish C5b replay outcomes as lessons for future policy search.

    Missing validation channels become remediation hints so later candidate
    generation can prioritize evidence gaps uncovered during replay.
    """

    def publish(
        self,
        bundle_input: CalibrationValidationRunnerInput,
        bundle: CalibrationValidationBundle,
    ) -> ArtifactRef | None:
        from polisyos.scientist.methods.search.lessons import LessonCard, LessonKind, LessonTrustLevel
        from polisyos.scientist.methods.search.transfer_context import resolve_transfer_context

        registry = bundle_input.lesson_registry
        if registry is None or not hasattr(registry, "record_local"):
            return None

        summary = bundle.readout_summary()
        card = LessonCard(
            kind=(
                LessonKind.SUCCESS
                if bundle.leaderboard_entry is not None
                and bundle.leaderboard_entry.metrics.eligible_for_promotion
                else LessonKind.FAILURE
            ),
            summary=(
                f"Calibration validation finished with status '{bundle.status}' "
                f"and composite score {summary['composite_score']}."
            ),
            failure_type=(
                "calibration_validation_success"
                if bundle.leaderboard_entry is not None
                and bundle.leaderboard_entry.metrics.eligible_for_promotion
                else "calibration_validation_review"
            ),
            stage_name="calibration_validation",
            fidelity_level=0,
            candidate_hash=str(bundle_input.candidate_ref.artifact_id),
            source_run_id=bundle_input.run_id,
            confidence=0.8,
            trust_level=LessonTrustLevel.LOCAL,
            task_family="policy",
            domain="general",
            tags=[
                item.kind.value
                for item in (bundle.backtest_matrix.kind_results if bundle.backtest_matrix else [])
            ],
            remediation_hint=(
                None
                if not summary["gap_flags"]
                else "Resolve missing C5b evidence channels before promotion."
            ),
            metadata={
                "calibration_validation_summary": summary,
                "governance_verdict": bundle.governance_verdict,
            },
        )
        lesson_context = resolve_transfer_context(run_id=bundle_input.run_id, task_family="policy")
        return registry.record_local(card, context=lesson_context)


def persist_calibration_validation_bundle(
    store: FileSystemCAS,
    bundle: CalibrationValidationBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> CalibrationValidationBundleRef:
    """Persist a calibration validation bundle to the artifact store.

    Args:
        store: CAS backend used for durable bundle storage.
        bundle: Validation payload to serialize.
        inputs: Optional provenance links to upstream candidate artifacts.

    Returns:
        Typed artifact ref for the stored bundle.
    """

    ref = store.put_json(
        bundle,
        PutOptions(
            kind="scientist.calibration_validation_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.governance.CalibrationValidationBundle",
                version=bundle.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CalibrationValidationBundleRef.model_validate(ref.model_dump())


def load_calibration_validation_bundle(
    store: FileSystemCAS,
    ref: ArtifactRef | CalibrationValidationBundleRef,
) -> CalibrationValidationBundle:
    """Load a persisted calibration validation bundle from the artifact store.

    Args:
        store: CAS backend that stores the serialized bundle.
        ref: Generic or typed artifact ref pointing at the bundle payload.

    Returns:
        Parsed `CalibrationValidationBundle`.
    """

    artifact_id = ref.artifact_id if isinstance(ref, ArtifactRef) else ref.artifact_id
    payload = from_canonical_bytes(store.get_bytes(artifact_id))
    return CalibrationValidationBundle.model_validate(payload)


__all__ = [
    "CalibrationValidationBundle",
    "CalibrationValidationLessonPublisher",
    "CalibrationValidationRunner",
    "CalibrationValidationRunnerInput",
    "CalibrationValidationRunnerResult",
    "load_calibration_validation_bundle",
    "persist_calibration_validation_bundle",
]
