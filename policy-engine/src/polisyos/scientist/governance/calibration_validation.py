"""Execute C5b replay validation and persist promotion bundles for calibration candidates.

The runner composes historical backtest replay, stress-scenario evaluation, and
leaderboard scoring into one `CalibrationValidationBundle`. If C5a governance
already short-circuited, the bundle is persisted as `blocked_by_governance`
without running replay so downstream promotion logic can audit the stop reason.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.backtest import BacktestReportRef
from polisyos.core.contracts.scientist import (
    CalibrationValidationBundleRef,
    GovernanceAccountabilityArtifactRef,
    StressTestReportRef,
)
from polisyos.data_forge.read_api.ukraine import (
    UkraineJSONSnapshotProvenance,
    read_ukraine_json_snapshot,
)
from polisyos.ir.analytics.backtest import BacktestReport, load_backtest_report
from polisyos.ir.analytics.interference import InterferenceCertificate, NetworkInterferenceReport
from polisyos.ir.analytics.transportability import TransportabilityResult
from polisyos.ir.observation.bundles import BacktestPlanBundle
from polisyos.ir.observation.contract_compilers import SpecificationCurveInput
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
from polisyos.scientist.methods.discovery.utility_judge import DownstreamUtilityReport

_S1_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT = {
    "scientist.d3.household_candidate_basis": "household_source_basis",
    "scientist.d4.calibration_splits": "selected_split_manifest",
}


def _s1_source_json_snapshot_model_type(consumer_contract: str) -> Any | None:
    """Resolve only the source models declared by the existing D3 and D4 readers."""
    if consumer_contract == "scientist.d3.household_candidate_basis":
        from polisyos.data_forge.domains.ukraine.manifests import (
            HouseholdDiagnosticPanelBasis,
        )

        return HouseholdDiagnosticPanelBasis
    if consumer_contract == "scientist.d4.calibration_splits":
        return dict[str, dict[str, str]]
    return None


_CALIBRATION_VALIDATION_BUNDLE_SCHEMA_NAME = (
    "polisyos.scientist.governance.CalibrationValidationBundle"
)
_CALIBRATION_VALIDATION_BUNDLE_SCHEMA_VERSIONS = ("1.0", "1.1")
_CANDIDATE_DIAGNOSTIC_SOURCE_ROLES = (
    "household_candidate_panel",
    *_S1_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT.values(),
)


def _input_edge_identity(
    value: InputRef | ArtifactRef | BacktestReportRef,
    *,
    role: str | None = None,
) -> tuple[str, str, str | None]:
    """Return the complete role, artifact, and selected-view identity of one edge."""
    edge_role = value.role if isinstance(value, InputRef) else role
    if edge_role is None:
        raise ValueError("artifact input edge identity requires its declared role")
    return (
        edge_role,
        str(value.artifact_id),
        getattr(value, "manifest_profile_sha256", None),
    )


def _input_edges_for_role(inputs: list[InputRef], role: str) -> list[InputRef]:
    """Return every actual manifest edge assigned to one role."""
    return [item for item in inputs if item.role == role]


def _candidate_input_edge(candidate_ref: ArtifactRef) -> InputRef:
    """Preserve the typed candidate's selected manifest view on producer edges."""
    return InputRef(
        artifact_id=candidate_ref.artifact_id,
        role="candidate",
        manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
    )


def _candidate_source_input_edge_status(
    store: FileSystemCAS,
    bundle_candidate_ref: ArtifactRef,
    bundle_inputs: list[InputRef],
    report_inputs: list[InputRef],
) -> tuple[str, str | None]:
    """Reconcile every persisted source edge and typed candidate lineage."""
    required_roles = set(_CANDIDATE_DIAGNOSTIC_SOURCE_ROLES)
    bundle_roles = {item.role for item in bundle_inputs}
    report_roles = {item.role for item in report_inputs}
    source_roles = bundle_roles | report_roles | required_roles | {"candidate"}
    unselected_profiles: set[str] = set()
    resolved_views: set[tuple[str, str]] = set()
    for role in sorted(source_roles):
        bundle_edges = _input_edges_for_role(bundle_inputs, role)
        report_edges = _input_edges_for_role(report_inputs, role)
        if role == "candidate" and not bundle_edges and not report_edges:
            return "not_established", "candidate_source_candidate_edge_not_selected"
        if role in required_roles | {"candidate"} and (
            len(bundle_edges) != 1 or len(report_edges) != 1
        ):
            return "unavailable", f"candidate_source_input_edge_mismatch:{role}"
        bundle_ids = Counter(_input_edge_identity(edge) for edge in bundle_edges)
        report_ids = Counter(_input_edge_identity(edge) for edge in report_edges)
        if bundle_ids != report_ids:
            return "unavailable", f"candidate_source_input_edge_mismatch:{role}"
        if (
            role == "candidate"
            and bundle_edges
            and _input_edge_identity(bundle_edges[0])
            != _input_edge_identity(bundle_candidate_ref, role="candidate")
        ):
            return "unavailable", "candidate_source_candidate_reference_mismatch"
        for edge in bundle_edges:
            profile = edge.manifest_profile_sha256
            if profile is None:
                unselected_profiles.add(role)
                continue
            selected = (str(edge.artifact_id), profile)
            if selected in resolved_views:
                continue
            try:
                store.get_manifest_by_profile(*selected)
            except Exception:
                return "unavailable", f"candidate_source_manifest_profile_unavailable:{role}"
            resolved_views.add(selected)
    if unselected_profiles:
        return "not_established", "candidate_source_manifest_profile_not_selected:" + ",".join(
            sorted(unselected_profiles)
        )
    return "available", None


def _calibration_validation_schema_version(
    source_json_snapshot_reads: dict[str, UkraineJSONSnapshotProvenance],
) -> Literal["1.0", "1.1"]:
    """Version persisted selected-source provenance without rewriting legacy bundles."""
    return "1.1" if source_json_snapshot_reads else "1.0"


def _validate_source_json_snapshot_reads(
    reads: dict[str, UkraineJSONSnapshotProvenance],
) -> None:
    """Keep reader-selected profile status bound to its named consumer contract."""
    for contract, provenance in reads.items():
        if contract != provenance.consumer_contract:
            raise ValueError("source JSON profile key differs from its consumer contract")
        if provenance.profile_status == "declared_unknown_candidate":
            raise ValueError("unknown-profile JSON remains raw-only and cannot feed C5b")
    selected_s1_contracts = set(reads) & set(_S1_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT)
    if selected_s1_contracts and selected_s1_contracts != set(
        _S1_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT
    ):
        raise ValueError("S1 candidate diagnostics require both selected JSON source profiles")


def _source_json_snapshot_input_status(
    store: FileSystemCAS,
    reads: dict[str, UkraineJSONSnapshotProvenance],
    inputs: list[InputRef],
) -> tuple[str, str | None]:
    """Reconcile selected source profiles against exact persisted C5b lineage edges."""
    if not reads:
        return "not_established", "source_json_snapshot_reads_absent"
    expected_contracts = set(_S1_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT)
    supplied_contracts = set(reads)
    if not supplied_contracts <= expected_contracts:
        return "not_established", "source_json_snapshot_contract_set_unrecognized"
    if supplied_contracts != expected_contracts:
        return "unavailable", "source_json_snapshot_contract_set_incomplete"
    selected_ids: set[str] = set()
    for contract, role in _S1_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT.items():
        provenance = reads[contract]
        if provenance.consumer_contract != contract:
            return "unavailable", f"source_json_snapshot_consumer_contract_mismatch:{contract}"
        if (
            provenance.profile_status == "declared_unknown_candidate"
            or provenance.schema_validation_provenance != "recomputed"
            or provenance.source_materialization == "raw_only_candidate"
            or (
                provenance.profile_status == "declared_bytes_conformant"
                and provenance.source_materialization != "reader_materialized"
            )
            or (
                provenance.profile_status == "profile_absent_raw_snapshot_candidate"
                and provenance.source_materialization != "raw_snapshot_candidate"
            )
        ):
            return "unavailable", f"source_json_snapshot_profile_not_admitted:{contract}"
        if (
            provenance.artifact_kind != "data_forge.ukraine.stage_output_snapshot"
            or provenance.artifact_ref.kind != provenance.artifact_kind
            or provenance.artifact_ref.media_type != "application/json"
            or provenance.media_type != "application/json"
        ):
            return "unavailable", f"source_json_snapshot_artifact_profile_mismatch:{contract}"
        if (
            provenance.artifact_ref.manifest_profile_sha256
            != provenance.selected_manifest_profile_sha256
            or provenance.artifact_ref.manifest_profile_sha256 is None
        ):
            return "unavailable", f"source_json_snapshot_selected_profile_mismatch:{contract}"
        selected_ids.add(str(provenance.artifact_ref.artifact_id))
        matches = _input_edges_for_role(inputs, role)
        if len(matches) != 1:
            return "unavailable", f"source_json_snapshot_input_edge_mismatch:{contract}"
        input_ref = matches[0]
        expected_edge = _input_edge_identity(provenance.artifact_ref, role=role)
        if _input_edge_identity(input_ref) != expected_edge:
            return "unavailable", f"source_json_snapshot_input_edge_mismatch:{contract}"
        try:
            source_manifest = store.get_manifest(provenance.artifact_ref)
            source_bytes = store.get_bytes(provenance.artifact_ref)
        except Exception:
            return "unavailable", f"source_json_snapshot_source_artifact_unavailable:{contract}"
        source_schema = source_manifest.artifact_schema
        if (
            source_manifest.kind != provenance.artifact_kind
            or source_manifest.media_type != provenance.media_type
            or str(source_manifest.artifact_id) != str(provenance.artifact_ref.artifact_id)
            or len(source_bytes) != provenance.content_size_bytes
            or hashlib.sha256(source_bytes).hexdigest() != provenance.content_sha256
            or (None if source_schema is None else source_schema.name) != provenance.schema_name
            or (None if source_schema is None else source_schema.version)
            != provenance.schema_version
        ):
            return "unavailable", f"source_json_snapshot_source_manifest_mismatch:{contract}"
        model_type = _s1_source_json_snapshot_model_type(contract)
        if model_type is None:
            return "not_established", f"source_json_snapshot_reader_not_registered:{contract}"
        try:
            recomputed_read = read_ukraine_json_snapshot(
                store,
                provenance.artifact_ref,
                raw_payload_bytes=source_bytes,
                expected_sha256=hashlib.sha256(source_bytes).hexdigest(),
                expected_size_bytes=len(source_bytes),
                expected_kind="data_forge.ukraine.stage_output_snapshot",
                consumer_contract=contract,
                model_type=model_type,
            )
        except Exception:
            return "unavailable", f"source_json_snapshot_contract_validation_failed:{contract}"
        if recomputed_read.provenance != provenance:
            return "unavailable", f"source_json_snapshot_recomputed_provenance_mismatch:{contract}"
    if len(selected_ids) != len(_S1_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT):
        return "unavailable", "source_json_snapshot_artifacts_not_distinct"
    return "available", None


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
    purpose: str = Field(default="promotion", pattern="^(promotion|candidate_diagnostic)$")
    input_refs: list[InputRef] = Field(default_factory=list)
    source_json_snapshot_reads: dict[str, UkraineJSONSnapshotProvenance] = Field(
        default_factory=dict
    )
    selected_training_role: str | None = Field(default=None, min_length=1)
    selected_validation_role: str | None = Field(default=None, min_length=1)
    selected_holdout_role: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_selected_split_request(self) -> CalibrationValidationRunnerInput:
        if _input_edges_for_role(self.input_refs, "candidate"):
            raise ValueError("candidate role is reserved for the typed C5b producer binding")
        requested = (
            self.selected_training_role,
            self.selected_validation_role,
            self.selected_holdout_role,
        )
        supplied = [role for role in requested if role is not None]
        if len(supplied) != len(set(supplied)):
            raise ValueError("selected training, validation and holdout roles must be distinct")
        if (requested[0] is None) != (requested[2] is None):
            raise ValueError("selected training and holdout roles must be supplied together")
        if requested[1] is not None and any(role is None for role in requested):
            raise ValueError("validation role requires the complete three-role request")
        bundle_requests = []
        for item in self.backtest_plan_bundles.values():
            roles = (
                item.selected_training_role,
                item.selected_validation_role,
                item.selected_holdout_role,
            )
            if any(role is not None for role in roles):
                bundle_requests.append(roles)
        if any(role is not None for role in requested):
            if len(bundle_requests) != len(self.backtest_plan_bundles) or any(
                roles != requested for roles in bundle_requests
            ):
                raise ValueError("backtest bundles do not match the C5b selected role request")
        elif len(set(bundle_requests)) > 1:
            raise ValueError("backtest bundles disagree on the selected split role request")
        _validate_source_json_snapshot_reads(self.source_json_snapshot_reads)
        if self.purpose == "candidate_diagnostic":
            if any(role is None for role in requested):
                raise ValueError("candidate diagnostic requires three selected named split roles")
            if not self.backtest_plan_bundles or len(bundle_requests) != len(
                self.backtest_plan_bundles
            ):
                raise ValueError("candidate diagnostic requires role-bound backtest bundles")
            required_roles = _CANDIDATE_DIAGNOSTIC_SOURCE_ROLES
            for role in required_roles:
                matches = _input_edges_for_role(self.input_refs, role)
                if len(matches) != 1:
                    raise ValueError(f"candidate diagnostic requires exactly one {role} input")
            bound_ids = [
                str(item.artifact_id) for item in self.input_refs if item.role in required_roles
            ]
            if len(set(bound_ids)) != len(required_roles):
                raise ValueError("candidate diagnostic source input refs must be distinct")
            for contract, role in _S1_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT.items():
                provenance = self.source_json_snapshot_reads.get(contract)
                if provenance is None:
                    continue
                matches = _input_edges_for_role(self.input_refs, role)
                expected_edge = _input_edge_identity(provenance.artifact_ref, role=role)
                if len(matches) != 1 or _input_edge_identity(matches[0]) != expected_edge:
                    raise ValueError(f"candidate source profile read is not bound to {role}")
        return self


def _selected_split_roles(
    bundle: CalibrationValidationRunnerInput,
) -> tuple[str | None, str | None, str | None]:
    """Resolve one consistent typed split request across C5b and its bundles."""
    requested = (
        bundle.selected_training_role,
        bundle.selected_validation_role,
        bundle.selected_holdout_role,
    )
    if any(role is not None for role in requested):
        return requested
    role_requests = {
        (
            item.selected_training_role,
            item.selected_validation_role,
            item.selected_holdout_role,
        )
        for item in bundle.backtest_plan_bundles.values()
        if any(
            (
                item.selected_training_role,
                item.selected_validation_role,
                item.selected_holdout_role,
            )
        )
    }
    if len(role_requests) > 1:
        raise ValueError("backtest bundles disagree on the selected split role request")
    return next(iter(role_requests), (None, None, None))


def _selected_split_role_payload(
    roles: tuple[str | None, str | None, str | None],
) -> dict[str, str]:
    """Return the serializable, named role request without invented defaults."""
    return {
        key: role
        for key, role in zip(("training", "validation", "holdout"), roles, strict=True)
        if role is not None
    }


class CalibrationValidationBundle(BaseModel):
    """Persisted bundle combining backtest, stress, and leaderboard validation.

    This is the durable decision artifact consumed by promotion dashboards and
    downstream orchestration. `status` records whether replay ran or governance
    blocked first, while the nested report refs preserve the audit trail.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1"] = "1.0"
    run_id: str = Field(min_length=1)
    candidate_ref: ArtifactRef
    governance_verdict: str = Field(min_length=1)
    status: str = Field(pattern="^(completed|blocked_by_governance|candidate_diagnostic)$")
    purpose: str = Field(default="promotion", pattern="^(promotion|candidate_diagnostic)$")
    backtest_matrix: BacktestMatrixResult | None = None
    stress_scenarios: StressScenarioResult | None = None
    leaderboard_entry: CalibrationLeaderboardEntry | None = None
    lesson_card_ref: ArtifactRef | None = None
    governance_accountability_ref: GovernanceAccountabilityArtifactRef | None = None
    governance_accountability_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    selected_training_role: str | None = Field(default=None, min_length=1)
    selected_validation_role: str | None = Field(default=None, min_length=1)
    selected_holdout_role: str | None = Field(default=None, min_length=1)
    source_json_snapshot_reads: dict[str, UkraineJSONSnapshotProvenance] = Field(
        default_factory=dict,
        exclude_if=lambda value: not value,
    )

    _fresh_backtest_report: BacktestReport | None = PrivateAttr(default=None)
    _fresh_backtest_report_status: str = PrivateAttr(default="not_loaded")
    _fresh_backtest_report_reason: str | None = PrivateAttr(default=None)
    _fresh_source_json_snapshot_binding_status: str = PrivateAttr(default="not_established")
    _fresh_source_json_snapshot_binding_reason: str | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _validate_selected_split_roles(self) -> CalibrationValidationBundle:
        requested = (
            self.selected_training_role,
            self.selected_validation_role,
            self.selected_holdout_role,
        )
        supplied = [role for role in requested if role is not None]
        if len(supplied) != len(set(supplied)):
            raise ValueError("selected training, validation and holdout roles must be distinct")
        if (requested[0] is None) != (requested[2] is None):
            raise ValueError("selected training and holdout roles must be supplied together")
        if requested[1] is not None and any(role is None for role in requested):
            raise ValueError("validation role requires the complete three-role request")
        if self.purpose == "candidate_diagnostic" and any(role is None for role in requested):
            raise ValueError("candidate diagnostic must retain its three selected split roles")
        if self.source_json_snapshot_reads and self.schema_version != "1.1":
            raise ValueError("source JSON snapshot provenance requires bundle schema 1.1")
        return self

    @model_validator(mode="after")
    def _candidate_diagnostic_is_nonpromotable(self) -> CalibrationValidationBundle:
        if self.purpose == "candidate_diagnostic":
            if self.status != "candidate_diagnostic":
                raise ValueError("candidate diagnostic purpose requires its distinct status")
            if self.governance_verdict != "human_gate":
                raise ValueError("candidate diagnostic cannot claim a governance approval")
            if (
                self.leaderboard_entry is not None
                or self.stress_scenarios is not None
                or self.lesson_card_ref is not None
                or self.governance_accountability_ref is not None
            ):
                raise ValueError("candidate diagnostic cannot carry promotion outputs")
        return self

    def readout_summary(self) -> dict[str, Any]:
        """Return a compact promotion-oriented summary for UIs and lessons."""

        entry = self.leaderboard_entry
        metrics = None if entry is None else entry.metrics
        report = self._fresh_backtest_report
        report_status = self._fresh_backtest_report_status
        diagnostics = None
        diagnostics_status = "unavailable"
        from polisyos.scientist.governance.backtest_matrix import (
            verify_backtest_diagnostic_projection,
            verify_backtest_trust_projection,
        )

        diagnostic_projection = (
            verify_backtest_diagnostic_projection(report) if report is not None else None
        )
        if diagnostic_projection is not None:
            diagnostics = diagnostic_projection.metric_diagnostics
            if diagnostics is not None:
                diagnostics_status = diagnostic_projection.status if diagnostics else "empty"
        source_binding_status = self._fresh_source_json_snapshot_binding_status
        source_binding_reason = self._fresh_source_json_snapshot_binding_reason
        if self.purpose == "candidate_diagnostic" and source_binding_status != "available":
            diagnostics = None
            diagnostics_status = "unavailable"
        trust_projection = verify_backtest_trust_projection(report) if report is not None else None
        trust_status = "unavailable" if trust_projection is None else trust_projection.status
        trust_reason = (
            "backtest_report_unavailable" if trust_projection is None else trust_projection.reason
        )
        trust_score = None if trust_projection is None else trust_projection.score
        trust_grade = None if trust_projection is None else trust_projection.grade
        if self.purpose == "candidate_diagnostic" and source_binding_status != "available":
            trust_status = "unavailable"
            trust_reason = source_binding_reason
            trust_score = None
            trust_grade = None
        report_qualifies = bool(
            report is not None
            and report_status == "available"
            and trust_projection is not None
            and trust_projection.eligible
            and diagnostics_status == "computed"
        )
        return {
            "status": self.status,
            "purpose": self.purpose,
            "backtest_report_ref": (
                None
                if self.backtest_report_ref is None
                else str(self.backtest_report_ref.artifact_id)
            ),
            "backtest_report_status": report_status,
            "backtest_report_reason": self._fresh_backtest_report_reason,
            "backtest_metric_diagnostics_status": diagnostics_status,
            "backtest_metric_diagnostics": diagnostics,
            "backtest_metric_diagnostics_reason": (
                source_binding_reason
                if self.purpose == "candidate_diagnostic" and source_binding_status != "available"
                else None
                if diagnostic_projection is None
                else diagnostic_projection.reason
            ),
            "backtest_trust_status": trust_status,
            "backtest_trust_reason": trust_reason,
            "backtest_trust_score": trust_score,
            "backtest_trust_grade": trust_grade,
            "selected_training_role": self.selected_training_role,
            "selected_validation_role": self.selected_validation_role,
            "selected_holdout_role": self.selected_holdout_role,
            "source_json_snapshot_binding_status": self._fresh_source_json_snapshot_binding_status,
            "source_json_snapshot_binding_reason": self._fresh_source_json_snapshot_binding_reason,
            "source_json_snapshot_reads": {
                contract: provenance.model_dump(mode="json")
                for contract, provenance in self.source_json_snapshot_reads.items()
            },
            "composite_score": None if metrics is None else metrics.composite_score,
            "eligible_for_promotion": (
                False
                if self.purpose == "candidate_diagnostic" or metrics is None or not report_qualifies
                else metrics.eligible_for_promotion
            ),
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

        selected_roles = _selected_split_roles(bundle)
        selected_role_payload = _selected_split_role_payload(selected_roles)
        if bool(bundle.governance_report.metadata.get("short_circuited")):
            blocked = CalibrationValidationBundle(
                schema_version=_calibration_validation_schema_version(
                    bundle.source_json_snapshot_reads
                ),
                run_id=bundle.run_id,
                candidate_ref=bundle.candidate_ref,
                governance_verdict=bundle.governance_report.resolved_verdict(),
                status="blocked_by_governance",
                selected_training_role=selected_roles[0],
                selected_validation_role=selected_roles[1],
                selected_holdout_role=selected_roles[2],
                source_json_snapshot_reads=dict(bundle.source_json_snapshot_reads),
                metadata={"blocked_reason": "c5a_short_circuited", **dict(bundle.metadata)},
            )
            blocked = self._attach_accountability_artifact(
                bundle_input=bundle,
                validation_bundle=blocked,
            )
            blocked_ref = persist_calibration_validation_bundle(self._store, blocked)
            fresh = load_calibration_validation_bundle(self._store, blocked_ref)
            return CalibrationValidationRunnerResult(bundle_ref=blocked_ref, bundle=fresh)

        if bundle.purpose == "candidate_diagnostic":
            if any(selected_role is None for selected_role in selected_roles):
                raise ValueError("candidate diagnostic requires three selected named split roles")
            artifact_inputs = [
                _candidate_input_edge(bundle.candidate_ref),
                *bundle.input_refs,
            ]
            backtest_matrix = self._backtest_runner.run(
                bundle.backtest_plan_bundles,
                inputs=artifact_inputs,
                metadata={
                    "run_id": bundle.run_id,
                    "purpose": "candidate_diagnostic",
                    "selected_split_roles": selected_role_payload,
                },
            )
            diagnostic_bundle = CalibrationValidationBundle(
                schema_version=_calibration_validation_schema_version(
                    bundle.source_json_snapshot_reads
                ),
                run_id=bundle.run_id,
                candidate_ref=bundle.candidate_ref,
                governance_verdict="human_gate",
                status="candidate_diagnostic",
                purpose="candidate_diagnostic",
                backtest_matrix=backtest_matrix,
                selected_training_role=selected_roles[0],
                selected_validation_role=selected_roles[1],
                selected_holdout_role=selected_roles[2],
                source_json_snapshot_reads=dict(bundle.source_json_snapshot_reads),
                metadata={
                    **dict(bundle.metadata),
                    "eligible_for_promotion": False,
                    "authority_purpose": "candidate_diagnostic",
                },
            )
            ref = persist_calibration_validation_bundle(
                self._store, diagnostic_bundle, inputs=artifact_inputs
            )
            fresh = load_calibration_validation_bundle(self._store, ref)
            return CalibrationValidationRunnerResult(bundle_ref=ref, bundle=fresh)

        artifact_inputs = [
            _candidate_input_edge(bundle.candidate_ref),
            *bundle.input_refs,
        ]
        backtest_matrix = self._backtest_runner.run(
            bundle.backtest_plan_bundles,
            inputs=artifact_inputs,
            metadata={"run_id": bundle.run_id, "selected_split_roles": selected_role_payload},
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
            schema_version=_calibration_validation_schema_version(
                bundle.source_json_snapshot_reads
            ),
            run_id=bundle.run_id,
            candidate_ref=bundle.candidate_ref,
            governance_verdict=bundle.governance_report.resolved_verdict(),
            status="completed",
            purpose="promotion",
            backtest_matrix=backtest_matrix,
            selected_training_role=selected_roles[0],
            selected_validation_role=selected_roles[1],
            selected_holdout_role=selected_roles[2],
            source_json_snapshot_reads=dict(bundle.source_json_snapshot_reads),
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
        fresh = load_calibration_validation_bundle(self._store, bundle_ref)
        return CalibrationValidationRunnerResult(bundle_ref=bundle_ref, bundle=fresh)

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
                _candidate_input_edge(bundle_input.candidate_ref),
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
        from polisyos.scientist.methods.search.lessons import (
            LessonCard,
            LessonKind,
            LessonTrustLevel,
        )
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
        lesson_context = resolve_transfer_context(
            run_id=bundle_input.run_id, task_family="policy", domain="general"
        )
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

    resolved_inputs = list(inputs or [])
    report_ref = bundle.backtest_report_ref
    if report_ref is not None:
        # This one edge is structural; other caller edges may use the same role.
        resolved_inputs.append(
            InputRef(
                artifact_id=report_ref.artifact_id,
                role="backtest_report",
                manifest_profile_sha256=report_ref.manifest_profile_sha256,
            )
        )
    ref = store.put_json(
        bundle,
        PutOptions(
            kind="scientist.calibration_validation_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name=_CALIBRATION_VALIDATION_BUNDLE_SCHEMA_NAME,
                version=bundle.schema_version,
            ),
            inputs=resolved_inputs,
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
    from polisyos.core.artifacts import load_core_json_artifact

    payload = load_core_json_artifact(store, ref)
    bundle = CalibrationValidationBundle.model_validate(payload)
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    if (
        manifest.kind != "scientist.calibration_validation_bundle"
        or manifest.media_type != "application/json"
        or schema is None
        or schema.name != _CALIBRATION_VALIDATION_BUNDLE_SCHEMA_NAME
        or schema.version not in _CALIBRATION_VALIDATION_BUNDLE_SCHEMA_VERSIONS
        or schema.version != bundle.schema_version
    ):
        raise ValueError("calibration validation bundle manifest schema does not match its payload")
    report_ref = bundle.backtest_report_ref
    if report_ref is None:
        bundle._fresh_backtest_report_status = "not_linked"
        return bundle
    try:
        (
            bundle._fresh_source_json_snapshot_binding_status,
            bundle._fresh_source_json_snapshot_binding_reason,
        ) = _source_json_snapshot_input_status(
            store, bundle.source_json_snapshot_reads, manifest.inputs
        )
        report_edges = _input_edges_for_role(manifest.inputs, "backtest_report")
    except Exception:
        bundle._fresh_backtest_report_status = "unavailable"
        bundle._fresh_backtest_report_reason = "c5b_manifest_unavailable"
        if bundle.source_json_snapshot_reads:
            bundle._fresh_source_json_snapshot_binding_status = "unavailable"
            bundle._fresh_source_json_snapshot_binding_reason = "c5b_manifest_unavailable"
        return bundle
    expected_report_edge = _input_edge_identity(report_ref, role="backtest_report")
    structural_report_indices = [
        i
        for i, edge in enumerate(manifest.inputs)
        if _input_edge_identity(edge) == expected_report_edge
    ]
    if not structural_report_indices:
        bundle._fresh_backtest_report_status = "unavailable"
        bundle._fresh_backtest_report_reason = (
            "nested_backtest_report_input_edge_missing_or_conflicting"
        )
        bundle._fresh_source_json_snapshot_binding_status = "unavailable"
        bundle._fresh_source_json_snapshot_binding_reason = bundle._fresh_backtest_report_reason
        return bundle
    # Remove one exact typed C5b→report edge only; all remaining inputs are source edges.
    bundle_source_inputs = list(manifest.inputs)
    del bundle_source_inputs[structural_report_indices[0]]
    try:
        report_manifest = store.get_manifest(
            ArtifactRef.model_validate(report_ref.model_dump(mode="python"))
        )
        report = load_backtest_report(_ensure_ir_artifact_store(store), report_ref)
    except Exception:
        bundle._fresh_backtest_report_status = "unavailable"
        bundle._fresh_backtest_report_reason = "nested_backtest_report_invalid"
        return bundle
    if bundle.purpose == "candidate_diagnostic":
        source_edge_status, source_edge_reason = _candidate_source_input_edge_status(
            store,
            bundle.candidate_ref,
            bundle_source_inputs,
            report_manifest.inputs,
        )
        if source_edge_status == "unavailable":
            bundle._fresh_source_json_snapshot_binding_status = "unavailable"
            bundle._fresh_source_json_snapshot_binding_reason = source_edge_reason
        if source_edge_status == "not_established":
            if bundle._fresh_source_json_snapshot_binding_status == "available":
                bundle._fresh_source_json_snapshot_binding_status = "not_established"
                bundle._fresh_source_json_snapshot_binding_reason = source_edge_reason
            elif bundle._fresh_source_json_snapshot_binding_status == "not_established":
                bundle._fresh_source_json_snapshot_binding_reason = source_edge_reason
    expected_roles = _selected_split_role_payload(
        (
            bundle.selected_training_role,
            bundle.selected_validation_role,
            bundle.selected_holdout_role,
        )
    )
    if expected_roles and report.metadata.get("selected_split_roles") != expected_roles:
        bundle._fresh_backtest_report_status = "unavailable"
        bundle._fresh_backtest_report_reason = "nested_backtest_report_role_request_mismatch"
        return bundle
    bundle._fresh_backtest_report = report
    bundle._fresh_backtest_report_status = "available"
    return bundle


__all__ = [
    "CalibrationValidationBundle",
    "CalibrationValidationLessonPublisher",
    "CalibrationValidationRunner",
    "CalibrationValidationRunnerInput",
    "CalibrationValidationRunnerResult",
    "load_calibration_validation_bundle",
    "persist_calibration_validation_bundle",
]
