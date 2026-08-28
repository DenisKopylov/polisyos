"""Public scientist feedback module API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.decision_validity import (
    DecisionTriggerRecord,
    DecisionTriggerType,
    DecisionValidityStatus,
)
from polisyos.core.contracts.feedback import (
    CompareDeltaSection,
    DecisionCompareReport,
    DecisionMonitoringContract,
    DecisionMonitoringReport,
    DecisionReissuePlan,
    MonitoredMetric,
    MonitoringMetricResult,
    MonitoringRange,
    MonitoringVerdict,
)
from polisyos.core.contracts.foundry import ParameterOverrideBundle
from polisyos.fabric.connectors.contracts.schema import DataSchema
from polisyos.fabric.data_plane import (
    compare_historical_rows,
    persist_historical_semantic_diff_report,
)
from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.ir.analytics.calibration import CalibrationConfig, CalibrationTarget
from polisyos.lex.simulator.cli import load_norm_pack
from polisyos.lex.simulator.diff import diff_norm_packs
from polisyos.scientist.feedback.utils import (
    _aggregate_monitoring_verdict,
    _as_bool_or_none,
    _as_float,
    _as_str,
    _extract_artifact_id,
    _extract_feedback_ref,
    _extract_metric_observation,
    _extract_revised_metric_ids,
    _extract_rows,
    _outside_range,
    _path_get,
    _within_range,
)
from polisyos.scientist.methods.autotune.calibration import apply_calibration_meta_overrides
from polisyos.scientist.orchestration.engine.operational_monitoring import get_operational_monitor
from polisyos.scientist.validation.decision_validity import DecisionValidityService


@dataclass(frozen=True)
class FeedbackArtifacts:
    """Feedback artifacts public type."""

    monitoring_contract_ref: str | None = None
    monitoring_report_ref: str | None = None
    compare_report_ref: str | None = None
    reissue_plan_ref: str | None = None


def build_monitoring_contract_from_packet(
    *,
    run_id: str,
    decision_lineage_key: str | None,
    anchor_at: datetime,
    packet_payload: Mapping[str, Any],
    override: Mapping[str, Any] | None = None,
) -> DecisionMonitoringContract | None:
    """Build monitoring contract from packet."""
    simulation_results = (
        packet_payload.get("simulation_results")
        if isinstance(packet_payload.get("simulation_results"), Mapping)
        else {}
    )
    backtest = (
        packet_payload.get("backtest")
        if isinstance(packet_payload.get("backtest"), Mapping)
        else {}
    )
    metrics: list[MonitoredMetric] = []
    overall_mae = _as_float(backtest.get("overall_mae")) or 0.0
    overall_rmse = _as_float(backtest.get("overall_rmse")) or overall_mae
    window_override = override.get("default_window") if isinstance(override, Mapping) else None

    for metric_id, raw_value in simulation_results.items():
        baseline_value = _as_float(raw_value)
        if baseline_value is None:
            continue
        confirm_margin = max(abs(baseline_value) * 0.1, overall_mae, 0.01)
        refute_margin = max(abs(baseline_value) * 0.2, overall_rmse, confirm_margin * 2.0)
        metric_override = (
            override.get("metrics", {}).get(metric_id, {})
            if isinstance(override, Mapping) and isinstance(override.get("metrics"), Mapping)
            else {}
        )
        metrics.append(
            MonitoredMetric(
                metric_id=str(metric_id),
                source_metric_id=str(metric_override.get("source_metric_id") or metric_id),
                baseline_value=baseline_value,
                confirm_range=MonitoringRange(
                    lower=baseline_value - confirm_margin,
                    upper=baseline_value + confirm_margin,
                ),
                refute_range=MonitoringRange(
                    lower=baseline_value - refute_margin,
                    upper=baseline_value + refute_margin,
                ),
                min_observations=max(int(metric_override.get("min_observations", 1) or 1), 1),
                weight=float(metric_override.get("weight", 1.0) or 1.0),
                recalibration_target=bool(metric_override.get("recalibration_target", True)),
                metadata={"window_override": window_override} if window_override else {},
            )
        )

    if not metrics:
        return None

    return DecisionMonitoringContract(
        run_id=run_id,
        decision_lineage_key=decision_lineage_key,
        anchor_at=anchor_at,
        backtest_mode_effective=_as_str(backtest.get("prediction_mode_effective")),
        backtest_trust_eligible=_as_bool_or_none(backtest.get("trust_eligible")),
        metrics=metrics,
        notes=[],
    )


def build_parameter_override_bundle(
    calibration_report: CalibrationReport,
) -> ParameterOverrideBundle | None:
    """Build parameter override bundle."""
    overrides: dict[str, dict[str, Any]] = {}
    sources: dict[str, list[str]] = {}
    for key, value in calibration_report.calibrated_params.items():
        if "." not in key:
            continue
        node_id, param_name = key.split(".", 1)
        overrides.setdefault(node_id, {})[param_name] = value
        sources.setdefault(node_id, []).append(key)
    if not overrides:
        return None
    return ParameterOverrideBundle(
        overrides=overrides,
        sources=sources,
        notes=["materialized_from_calibration_report"],
    )


class DecisionFeedbackService:
    """Decision feedback service implementation."""

    def __init__(self, store: ArtifactStore) -> None:
        self._store = store
        self._decision_validity = DecisionValidityService(store)

    def persist_monitoring_contract(
        self,
        contract: DecisionMonitoringContract,
        *,
        inputs: list[InputRef] | None = None,
    ) -> str:
        ref = self._put_model(
            contract,
            kind="scientist.decision_monitoring_contract",
            schema_name="polisyos.scientist.DecisionMonitoringContract",
            schema_version=contract.schema_version,
            inputs=inputs,
        )
        return str(ref.artifact_id)

    def load_feedback_refs(self, packet_ref: str) -> FeedbackArtifacts:
        refs = self._decision_validity.get_feedback_refs(packet_ref)
        return FeedbackArtifacts(
            monitoring_contract_ref=refs["monitoring_contract_ref"],
            monitoring_report_ref=refs["latest_monitoring_report_ref"],
            compare_report_ref=refs["latest_compare_report_ref"],
            reissue_plan_ref=refs["latest_reissue_plan_ref"],
        )

    def get_decision_validity_summary(
        self,
        packet_ref: str,
        *,
        packet_payload: Mapping[str, Any] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Return the decision-validity summary through the public feedback API."""
        return self._decision_validity.get_summary(
            packet_ref,
            packet_payload=dict(packet_payload) if packet_payload is not None else None,
            force=force,
        )

    def evaluate_packet(
        self,
        *,
        run_id: str,
        packet_ref: str,
        packet_payload: Mapping[str, Any],
    ) -> tuple[DecisionMonitoringReport, FeedbackArtifacts]:
        refs = self.load_feedback_refs(packet_ref)
        contract_ref = refs.monitoring_contract_ref or _extract_feedback_ref(
            packet_payload, "monitoring_contract_ref"
        )
        if contract_ref is None:
            raise ValueError("feedback monitoring contract is missing")
        contract = self._load_model(contract_ref, DecisionMonitoringContract)

        actuals_payload = self._load_actuals_payload(packet_payload)
        degraded_reasons: list[str] = []
        metric_results: list[MonitoringMetricResult] = []
        refuted_metric_ids: list[str] = []

        for metric in contract.metrics:
            actual_value, observed_count = _extract_metric_observation(
                actuals_payload,
                metric.source_metric_id,
            )
            verdict = MonitoringVerdict.PENDING
            reason = None
            delta = None
            if actual_value is None or observed_count < metric.min_observations:
                verdict = MonitoringVerdict.INSUFFICIENT_DATA
                reason = "insufficient_actual_observations"
            else:
                delta = round(actual_value - metric.baseline_value, 6)
                if _within_range(actual_value, metric.confirm_range):
                    verdict = MonitoringVerdict.CONFIRMED
                    reason = "actual_value_within_confirm_range"
                elif _outside_range(actual_value, metric.refute_range):
                    verdict = MonitoringVerdict.REFUTED
                    reason = "actual_value_outside_refute_range"
                    refuted_metric_ids.append(metric.metric_id)
                else:
                    verdict = MonitoringVerdict.INCONCLUSIVE
                    reason = "actual_value_between_confirm_and_refute"

            metric_results.append(
                MonitoringMetricResult(
                    metric_id=metric.metric_id,
                    source_metric_id=metric.source_metric_id,
                    baseline_value=metric.baseline_value,
                    actual_value=actual_value,
                    observed_count=observed_count,
                    verdict=verdict,
                    reason=reason,
                    delta=delta,
                    recalibration_target=(
                        metric.recalibration_target and verdict == MonitoringVerdict.REFUTED
                    ),
                )
            )

        overall_verdict = _aggregate_monitoring_verdict(
            metric_results,
            degraded=contract.backtest_trust_eligible is False,
        )
        if contract.backtest_trust_eligible is False:
            degraded_reasons.append("backtest_trust_not_eligible")

        report = DecisionMonitoringReport(
            run_id=run_id,
            decision_packet_ref=packet_ref,
            monitoring_contract_ref=contract_ref,
            anchor_at=contract.anchor_at,
            overall_verdict=overall_verdict,
            metrics=metric_results,
            refuted_metric_ids=refuted_metric_ids,
            degraded_reasons=degraded_reasons,
            notes=[],
        )
        report_ref = self._put_model(
            report,
            kind="scientist.decision_monitoring_report",
            schema_name="polisyos.scientist.DecisionMonitoringReport",
            schema_version=report.schema_version,
            inputs=[
                InputRef(
                    artifact_id=ArtifactID.model_validate(packet_ref),
                    role="decision_packet",
                ),
                InputRef(
                    artifact_id=ArtifactID.model_validate(contract_ref),
                    role="monitoring_contract",
                ),
            ],
        )

        compare_report_ref: str | None = None
        reissue_plan_ref: str | None = None
        if refuted_metric_ids:
            workflow_id = (
                str(packet_payload.get("workflow_id"))
                if isinstance(packet_payload.get("workflow_id"), str)
                else None
            )
            get_operational_monitor().ingest_metric_regressions(
                refuted_metric_ids,
                workflow_id=workflow_id,
                run_id=run_id,
            )
            trigger = DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.POST_DEPLOYMENT_REFUTATION,
                status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
                reason="post_deployment_refutation_detected",
                source_ref=str(report_ref.artifact_id),
                details={"refuted_metric_ids": refuted_metric_ids},
            )
            self._decision_validity.mark_packet_trigger(packet_ref=packet_ref, trigger=trigger)

            compare_report, compare_report_ref = self.compare_packets(
                left_run_id=run_id,
                left_packet_ref=packet_ref,
                left_packet_payload=packet_payload,
                right_run_id=run_id,
                right_packet_ref=packet_ref,
                right_packet_payload=packet_payload,
                monitoring_report=report,
                monitoring_report_ref=str(report_ref.artifact_id),
            )
            reissue_plan, reissue_plan_ref = self.build_reissue_plan(
                source_run_id=run_id,
                source_packet_ref=packet_ref,
                source_packet_payload=packet_payload,
                monitoring_report=report,
                monitoring_report_ref=str(report_ref.artifact_id),
                compare_report=compare_report,
                compare_report_ref=compare_report_ref,
            )
        self._decision_validity.update_feedback_refs(
            packet_ref,
            monitoring_contract_ref=contract_ref,
            monitoring_report_ref=str(report_ref.artifact_id),
            compare_report_ref=compare_report_ref,
            reissue_plan_ref=reissue_plan_ref,
        )
        return (
            report,
            FeedbackArtifacts(
                monitoring_contract_ref=contract_ref,
                monitoring_report_ref=str(report_ref.artifact_id),
                compare_report_ref=compare_report_ref,
                reissue_plan_ref=reissue_plan_ref,
            ),
        )

    def compare_packets(
        self,
        *,
        left_run_id: str,
        left_packet_ref: str,
        left_packet_payload: Mapping[str, Any],
        right_run_id: str,
        right_packet_ref: str,
        right_packet_payload: Mapping[str, Any],
        monitoring_report: DecisionMonitoringReport | None = None,
        monitoring_report_ref: str | None = None,
    ) -> tuple[DecisionCompareReport, str]:
        deltas = {
            "law": self._law_delta(left_packet_payload, right_packet_payload),
            "data": self._data_delta(left_packet_payload, right_packet_payload),
            "evidence": self._evidence_delta(left_packet_payload, right_packet_payload),
            "model": self._model_delta(left_packet_payload, right_packet_payload),
            "governance": self._governance_delta(
                left_packet_ref,
                right_packet_ref,
                left_packet_payload,
                right_packet_payload,
            ),
            "outcome": self._outcome_delta(
                left_packet_payload,
                right_packet_payload,
                monitoring_report,
            ),
        }
        root_cause = [name for name, delta in deltas.items() if delta.changed]
        if (
            not root_cause
            and monitoring_report is not None
            and monitoring_report.refuted_metric_ids
        ):
            root_cause = ["outcome"]
        report = DecisionCompareReport(
            left_run_id=left_run_id,
            right_run_id=right_run_id,
            left_decision_packet_ref=left_packet_ref,
            right_decision_packet_ref=right_packet_ref,
            deltas=deltas,
            root_cause=root_cause,
            notes=(
                [f"monitoring_report_ref:{monitoring_report_ref}"]
                if monitoring_report_ref is not None
                else []
            ),
        )
        report_ref = self._put_model(
            report,
            kind="scientist.decision_compare_report",
            schema_name="polisyos.scientist.DecisionCompareReport",
            schema_version=report.schema_version,
            inputs=[
                InputRef(
                    artifact_id=ArtifactID.model_validate(left_packet_ref),
                    role="left_decision_packet",
                ),
                InputRef(
                    artifact_id=ArtifactID.model_validate(right_packet_ref),
                    role="right_decision_packet",
                ),
            ],
        )
        return report, str(report_ref.artifact_id)

    def build_reissue_plan(
        self,
        *,
        source_run_id: str,
        source_packet_ref: str,
        source_packet_payload: Mapping[str, Any],
        monitoring_report: DecisionMonitoringReport,
        monitoring_report_ref: str,
        compare_report: DecisionCompareReport,
        compare_report_ref: str,
    ) -> tuple[DecisionReissuePlan, str | None]:
        calibration_config_ref: str | None = None
        parameter_override_bundle_ref: str | None = None

        refuted_metrics = [
            item for item in monitoring_report.metrics if item.verdict == MonitoringVerdict.REFUTED
        ]
        if refuted_metrics:
            base_config = CalibrationConfig(
                targets=[
                    CalibrationTarget(
                        target_id=item.metric_id,
                        model_metric_path=item.metric_id,
                        fabric_metric=item.source_metric_id,
                    )
                    for item in refuted_metrics
                ],
                max_steps=100,
            )
            config = apply_calibration_meta_overrides(
                base_config,
                context={
                    "source_run_id": source_run_id,
                    "source_packet_ref": source_packet_ref,
                    "source_packet_payload": dict(source_packet_payload),
                    "monitoring_report": monitoring_report,
                    "monitoring_report_ref": monitoring_report_ref,
                    "compare_report": compare_report,
                    "compare_report_ref": compare_report_ref,
                },
            )
            config_ref = self._put_model(
                config,
                kind="foundry.calibration_config",
                schema_name="polisyos.ir.CalibrationConfig",
                schema_version=config.schema_version,
                inputs=[
                    InputRef(
                        artifact_id=ArtifactID.model_validate(source_packet_ref),
                        role="decision_packet",
                    ),
                ],
            )
            calibration_config_ref = str(config_ref.artifact_id)

        calibration_report_ref = _path_get(
            source_packet_payload,
            ("inputs", "calibration_report_ref"),
        )
        if isinstance(calibration_report_ref, str):
            try:
                calibration_report = self._load_model(calibration_report_ref, CalibrationReport)
                override_bundle = build_parameter_override_bundle(calibration_report)
                if override_bundle is not None:
                    override_ref = self._put_model(
                        override_bundle,
                        kind="foundry.parameter_override_bundle",
                        schema_name="polisyos.foundry.ParameterOverrideBundle",
                        schema_version=override_bundle.schema_version,
                        inputs=[
                            InputRef(
                                artifact_id=ArtifactID.model_validate(calibration_report_ref),
                                role="calibration_report",
                            )
                        ],
                    )
                    parameter_override_bundle_ref = str(override_ref.artifact_id)
            except Exception:
                parameter_override_bundle_ref = None

        plan = DecisionReissuePlan(
            source_run_id=source_run_id,
            source_decision_packet_ref=source_packet_ref,
            monitoring_report_ref=monitoring_report_ref,
            compare_report_ref=compare_report_ref,
            calibration_config_ref=calibration_config_ref,
            parameter_override_bundle_ref=parameter_override_bundle_ref,
            refuted_metric_ids=list(monitoring_report.refuted_metric_ids),
            revised_metric_ids=_extract_revised_metric_ids(compare_report),
            notes=[],
        )
        plan_ref = self._put_model(
            plan,
            kind="scientist.decision_reissue_plan",
            schema_name="polisyos.scientist.DecisionReissuePlan",
            schema_version=plan.schema_version,
            inputs=[
                InputRef(
                    artifact_id=ArtifactID.model_validate(source_packet_ref),
                    role="decision_packet",
                ),
                InputRef(
                    artifact_id=ArtifactID.model_validate(monitoring_report_ref),
                    role="monitoring_report",
                ),
                InputRef(
                    artifact_id=ArtifactID.model_validate(compare_report_ref),
                    role="compare_report",
                ),
            ],
        )
        return plan, str(plan_ref.artifact_id)

    def _load_actuals_payload(self, packet_payload: Mapping[str, Any]) -> Any:
        data_snapshot_ref = _path_get(packet_payload, ("inputs", "data_snapshot_ref"))
        if not isinstance(data_snapshot_ref, str):
            return {}
        snapshot_payload = self._load_json(data_snapshot_ref)
        data_ref = _extract_artifact_id(snapshot_payload.get("data_ref"))
        if data_ref is None:
            return {}
        return self._load_json(data_ref)

    def _law_delta(
        self,
        left_packet_payload: Mapping[str, Any],
        right_packet_payload: Mapping[str, Any],
    ) -> CompareDeltaSection:
        left_ref = _path_get(left_packet_payload, ("inputs", "norm_pack_ref"))
        right_ref = _path_get(right_packet_payload, ("inputs", "norm_pack_ref"))
        changed = left_ref != right_ref
        summary: dict[str, Any] = {"left_ref": left_ref, "right_ref": right_ref}
        details: dict[str, Any] = {}
        if isinstance(left_ref, str) and isinstance(right_ref, str) and left_ref != right_ref:
            try:
                norm_diff = diff_norm_packs(
                    load_norm_pack(self._store, left_ref),
                    load_norm_pack(self._store, right_ref),
                )
                summary.update(
                    {
                        "added_count": norm_diff.added_count,
                        "removed_count": norm_diff.removed_count,
                        "modified_count": norm_diff.modified_count,
                    }
                )
                details["norm_diff"] = norm_diff.model_dump(mode="json")
            except Exception as exc:
                details["load_error"] = str(exc)
        return CompareDeltaSection(
            changed=changed,
            refs={
                "left_norm_pack_ref": _as_str(left_ref),
                "right_norm_pack_ref": _as_str(right_ref),
            },
            summary=summary,
            details=details,
        )

    def _data_delta(
        self,
        left_packet_payload: Mapping[str, Any],
        right_packet_payload: Mapping[str, Any],
    ) -> CompareDeltaSection:
        left_snapshot_ref = _path_get(left_packet_payload, ("inputs", "data_snapshot_ref"))
        right_snapshot_ref = _path_get(right_packet_payload, ("inputs", "data_snapshot_ref"))
        details: dict[str, Any] = {}
        changed = left_snapshot_ref != right_snapshot_ref
        if isinstance(left_snapshot_ref, str) and isinstance(right_snapshot_ref, str):
            left_snapshot = self._load_json(left_snapshot_ref)
            right_snapshot = self._load_json(right_snapshot_ref)
            left_data_ref = _extract_artifact_id(left_snapshot.get("data_ref"))
            right_data_ref = _extract_artifact_id(right_snapshot.get("data_ref"))
            left_schema_ref = _extract_artifact_id(left_snapshot.get("data_schema_ref"))
            right_schema_ref = _extract_artifact_id(right_snapshot.get("data_schema_ref"))
            if all(
                isinstance(item, str)
                for item in (
                    left_data_ref,
                    right_data_ref,
                    left_schema_ref,
                    right_schema_ref,
                )
            ):
                try:
                    left_schema = self._load_model(left_schema_ref, DataSchema)
                    right_schema = self._load_model(right_schema_ref, DataSchema)
                    left_rows = _extract_rows(self._load_json(left_data_ref))
                    right_rows = _extract_rows(self._load_json(right_data_ref))
                    semantic_diff = compare_historical_rows(
                        left_schema,
                        left_rows,
                        right_schema,
                        right_rows,
                        left_data_ref=left_data_ref,
                        right_data_ref=right_data_ref,
                    )
                    diff_ref = persist_historical_semantic_diff_report(
                        self._store,
                        semantic_diff,
                        inputs=[
                            InputRef(
                                artifact_id=ArtifactID.model_validate(left_data_ref),
                                role="left_data",
                            ),
                            InputRef(
                                artifact_id=ArtifactID.model_validate(right_data_ref),
                                role="right_data",
                            ),
                        ],
                    )
                    details["semantic_diff"] = semantic_diff.model_dump(mode="json")
                    details["semantic_diff_ref"] = str(diff_ref.artifact_id)
                    changed = (
                        changed
                        or semantic_diff.summary.material_revision
                        or semantic_diff.summary.schema_only
                    )
                except Exception as exc:
                    details["semantic_diff_error"] = str(exc)
        return CompareDeltaSection(
            changed=changed,
            refs={
                "left_data_snapshot_ref": _as_str(left_snapshot_ref),
                "right_data_snapshot_ref": _as_str(right_snapshot_ref),
            },
            summary={
                "left_data_snapshot_ref": left_snapshot_ref,
                "right_data_snapshot_ref": right_snapshot_ref,
            },
            details=details,
        )

    def _evidence_delta(
        self,
        left_packet_payload: Mapping[str, Any],
        right_packet_payload: Mapping[str, Any],
    ) -> CompareDeltaSection:
        keys = [
            ("knowledge_bundle_ref", "inputs"),
            ("research_intent_ref", "inputs"),
            ("causal_report_ref", "artifacts"),
            ("econometric_evidence_ref", "artifacts"),
        ]
        summary: dict[str, Any] = {}
        changed_refs = 0
        for key, section in keys:
            left_value = _path_get(left_packet_payload, (section, key))
            right_value = _path_get(right_packet_payload, (section, key))
            summary[key] = {"left": left_value, "right": right_value}
            if left_value != right_value:
                changed_refs += 1
        return CompareDeltaSection(
            changed=changed_refs > 0,
            summary={"changed_ref_count": changed_refs},
            details=summary,
        )

    def _model_delta(
        self,
        left_packet_payload: Mapping[str, Any],
        right_packet_payload: Mapping[str, Any],
    ) -> CompareDeltaSection:
        fields = [
            ("exec_plan_ref", "artifacts"),
            ("program_graph_ref", "artifacts"),
            ("lowered_ir_ref", "artifacts"),
            ("calibration_report_ref", "inputs"),
        ]
        details: dict[str, Any] = {}
        changed = False
        for field_name, section in fields:
            left_value = _path_get(left_packet_payload, (section, field_name))
            right_value = _path_get(right_packet_payload, (section, field_name))
            details[field_name] = {"left": left_value, "right": right_value}
            changed = changed or left_value != right_value
        left_feedback = (
            left_packet_payload.get("feedback_loop")
            if isinstance(left_packet_payload.get("feedback_loop"), Mapping)
            else {}
        )
        right_feedback = (
            right_packet_payload.get("feedback_loop")
            if isinstance(right_packet_payload.get("feedback_loop"), Mapping)
            else {}
        )
        model_posture = {
            "left_backtest_mode_effective": left_feedback.get("backtest_mode_effective"),
            "right_backtest_mode_effective": right_feedback.get("backtest_mode_effective"),
            "left_backtest_trust_eligible": left_feedback.get("backtest_trust_eligible"),
            "right_backtest_trust_eligible": right_feedback.get("backtest_trust_eligible"),
        }
        changed = changed or (
            model_posture["left_backtest_mode_effective"]
            != model_posture["right_backtest_mode_effective"]
            or model_posture["left_backtest_trust_eligible"]
            != model_posture["right_backtest_trust_eligible"]
        )
        return CompareDeltaSection(
            changed=changed,
            summary=model_posture,
            details=details,
        )

    def _governance_delta(
        self,
        left_packet_ref: str,
        right_packet_ref: str,
        left_packet_payload: Mapping[str, Any],
        right_packet_payload: Mapping[str, Any],
    ) -> CompareDeltaSection:
        left_governance = (
            left_packet_payload.get("governance")
            if isinstance(left_packet_payload.get("governance"), Mapping)
            else {}
        )
        right_governance = (
            right_packet_payload.get("governance")
            if isinstance(right_packet_payload.get("governance"), Mapping)
            else {}
        )
        left_validity = self._decision_validity.get_summary(
            left_packet_ref,
            packet_payload=dict(left_packet_payload),
        )
        right_validity = self._decision_validity.get_summary(
            right_packet_ref,
            packet_payload=dict(right_packet_payload),
        )
        changed = left_governance.get("verdict") != right_governance.get(
            "verdict"
        ) or left_validity.get("status") != right_validity.get("status")
        return CompareDeltaSection(
            changed=changed,
            summary={
                "left_verdict": left_governance.get("verdict"),
                "right_verdict": right_governance.get("verdict"),
                "left_validity_status": left_validity.get("status"),
                "right_validity_status": right_validity.get("status"),
            },
            details={},
        )

    def _outcome_delta(
        self,
        left_packet_payload: Mapping[str, Any],
        right_packet_payload: Mapping[str, Any],
        monitoring_report: DecisionMonitoringReport | None,
    ) -> CompareDeltaSection:
        left_results = (
            left_packet_payload.get("simulation_results")
            if isinstance(left_packet_payload.get("simulation_results"), Mapping)
            else {}
        )
        right_results = (
            right_packet_payload.get("simulation_results")
            if isinstance(right_packet_payload.get("simulation_results"), Mapping)
            else {}
        )
        keys = sorted(set(left_results) | set(right_results))
        deltas: dict[str, dict[str, Any]] = {}
        changed = False
        for key in keys:
            left_value = _as_float(left_results.get(key))
            right_value = _as_float(right_results.get(key))
            if left_value != right_value:
                changed = True
            deltas[str(key)] = {
                "left": left_value,
                "right": right_value,
                "delta": (
                    round((right_value or 0.0) - (left_value or 0.0), 6)
                    if left_value is not None and right_value is not None
                    else None
                ),
            }
        if monitoring_report is not None:
            changed = changed or bool(monitoring_report.refuted_metric_ids)
            deltas["observed_actuals"] = {
                item.metric_id: {
                    "baseline": item.baseline_value,
                    "actual": item.actual_value,
                    "verdict": item.verdict.value,
                    "delta": item.delta,
                }
                for item in monitoring_report.metrics
            }
        return CompareDeltaSection(
            changed=changed,
            summary={"metric_count": len(keys)},
            details=deltas,
        )

    def _put_model(
        self,
        model: object,
        *,
        kind: str,
        schema_name: str,
        schema_version: str,
        inputs: list[InputRef] | None = None,
    ):
        return self._store.put_json(
            model,
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version=schema_version),
                inputs=inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

    def _load_json(self, ref: str) -> object:
        return from_canonical_bytes(self._store.get_bytes(ArtifactID.model_validate(ref)))

    def _load_model(self, ref: str, model_cls):
        return model_cls.model_validate(self._load_json(ref))


__all__ = [
    "DecisionFeedbackService",
    "FeedbackArtifacts",
    "build_monitoring_contract_from_packet",
    "build_parameter_override_bundle",
]
