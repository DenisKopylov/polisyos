from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.feedback import (
    DecisionCompareReport,
    DecisionMonitoringContract,
    DecisionMonitoringReport,
    DecisionReissuePlan,
)
from polisyos.core.contracts.runtime import RunCompareView, RunFeedbackView
from polisyos.core.run.context import new_run_id
from polisyos.scientist.feedback import DecisionFeedbackService
from polisyos.scientist.nodes.builtins.state_keys import INPUT_PARAMETER_OVERRIDE_BUNDLE_REF

from .run_index import IndexedRunRecord, RunIndexService


@dataclass(frozen=True)
class PreparedReissue:
    reissued_run_id: str
    state_payload: dict[str, Any]
    monitoring_report_ref: str | None
    compare_report_ref: str | None
    reissue_plan_ref: str | None


class FeedbackService:
    def __init__(self, *, store: FileSystemCAS, run_index: RunIndexService) -> None:
        self._store = store
        self._run_index = run_index
        self._feedback = DecisionFeedbackService(store)

    def get_run_feedback(self, run: IndexedRunRecord) -> RunFeedbackView:
        if run.decision_packet_ref is None:
            return RunFeedbackView(
                run_id=run.run_id,
                source_kind=run.source_kind,
                decision_packet_ref=None,
                notes=["decision_packet_missing"],
            )
        packet_ref = str(run.decision_packet_ref.artifact_id)
        packet_payload = self._load_json(packet_ref)
        refs = self._feedback.load_feedback_refs(packet_ref)
        monitoring_contract_ref = refs.monitoring_contract_ref or self._feedback_ref_from_packet(
            packet_payload,
            "monitoring_contract_ref",
        )
        monitoring_report_ref = refs.monitoring_report_ref or self._feedback_ref_from_packet(
            packet_payload,
            "latest_monitoring_report_ref",
        )
        compare_report_ref = refs.compare_report_ref or self._feedback_ref_from_packet(
            packet_payload,
            "latest_compare_report_ref",
        )
        reissue_plan_ref = refs.reissue_plan_ref or self._feedback_ref_from_packet(
            packet_payload,
            "latest_reissue_plan_ref",
        )
        return RunFeedbackView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            decision_packet_ref=run.decision_packet_ref,
            feedback_loop=(
                packet_payload.get("feedback_loop")
                if isinstance(packet_payload.get("feedback_loop"), Mapping)
                else None
            ),
            monitoring_contract=self._load_optional_model(
                monitoring_contract_ref,
                DecisionMonitoringContract,
            ),
            monitoring_report=self._load_optional_model(
                monitoring_report_ref,
                DecisionMonitoringReport,
            ),
            compare_report=self._load_optional_model(
                compare_report_ref,
                DecisionCompareReport,
            ),
            reissue_plan=self._load_optional_model(
                reissue_plan_ref,
                DecisionReissuePlan,
            ),
            decision_validity=self._feedback_state_summary(packet_ref, packet_payload),
            notes=[],
        )

    def evaluate_run_feedback(
        self,
        run: IndexedRunRecord,
    ) -> tuple[RunFeedbackView, str | None, str | None, str | None]:
        if run.decision_packet_ref is None:
            raise ValueError("decision_packet_missing")
        packet_ref = str(run.decision_packet_ref.artifact_id)
        packet_payload = self._load_json(packet_ref)
        _, refs = self._feedback.evaluate_packet(
            run_id=run.run_id,
            packet_ref=packet_ref,
            packet_payload=packet_payload,
        )
        view = self.get_run_feedback(run)
        return (
            view,
            refs.monitoring_report_ref,
            refs.compare_report_ref,
            refs.reissue_plan_ref,
        )

    def compare_runs(
        self,
        left_run: IndexedRunRecord,
        right_run: IndexedRunRecord,
    ) -> RunCompareView:
        if left_run.decision_packet_ref is None or right_run.decision_packet_ref is None:
            raise ValueError("decision_packet_missing")
        left_packet_ref = str(left_run.decision_packet_ref.artifact_id)
        right_packet_ref = str(right_run.decision_packet_ref.artifact_id)
        report, _ = self._feedback.compare_packets(
            left_run_id=left_run.run_id,
            left_packet_ref=left_packet_ref,
            left_packet_payload=self._load_json(left_packet_ref),
            right_run_id=right_run.run_id,
            right_packet_ref=right_packet_ref,
            right_packet_payload=self._load_json(right_packet_ref),
        )
        return RunCompareView(
            left_run_id=left_run.run_id,
            right_run_id=right_run.run_id,
            report=report,
        )

    def prepare_reissue(self, run: IndexedRunRecord) -> PreparedReissue:
        feedback_view, monitoring_report_ref, compare_report_ref, reissue_plan_ref = (
            self.evaluate_run_feedback(run)
        )
        if run.experiment_state_ref is None:
            raise ValueError("experiment_state_missing")
        if reissue_plan_ref is None:
            raise ValueError("reissue_plan_missing")
        original_state = self._load_json(str(run.experiment_state_ref.artifact_id))
        plan = self._load_optional_model(reissue_plan_ref, DecisionReissuePlan)
        if plan is None:
            raise ValueError("reissue_plan_load_failed")

        inputs = (
            dict(original_state.get("inputs"))
            if isinstance(original_state, Mapping) and isinstance(original_state.get("inputs"), Mapping)
            else {}
        )
        params = (
            dict(original_state.get("params"))
            if isinstance(original_state, Mapping) and isinstance(original_state.get("params"), Mapping)
            else {}
        )
        budgets = (
            dict(original_state.get("budgets"))
            if isinstance(original_state, Mapping) and isinstance(original_state.get("budgets"), Mapping)
            else {}
        )
        new_run = new_run_id()
        if plan.parameter_override_bundle_ref is not None:
            inputs[INPUT_PARAMETER_OVERRIDE_BUNDLE_REF] = {
                "artifact_id": plan.parameter_override_bundle_ref,
                "kind": "foundry.parameter_override_bundle",
                "media_type": "application/json",
            }
        params["reissued_from_run_id"] = run.run_id
        params["reissue_plan_ref"] = reissue_plan_ref
        if feedback_view.monitoring_report is not None:
            params["feedback_refuted_metric_ids"] = list(feedback_view.monitoring_report.refuted_metric_ids)
        return PreparedReissue(
            reissued_run_id=new_run,
            state_payload={
                "run_id": new_run,
                "inputs": inputs,
                "params": params,
                "budgets": budgets,
                "execution_profile": original_state.get("execution_profile") if isinstance(original_state, Mapping) else None,
            },
            monitoring_report_ref=monitoring_report_ref,
            compare_report_ref=compare_report_ref,
            reissue_plan_ref=reissue_plan_ref,
        )

    def _feedback_state_summary(
        self,
        packet_ref: str,
        packet_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._feedback._decision_validity.get_summary(  # noqa: SLF001
            packet_ref,
            packet_payload=dict(packet_payload),
        )

    def _load_optional_model(self, ref: str | None, model_cls):
        if ref is None:
            return None
        try:
            return model_cls.model_validate(self._load_json(ref))
        except Exception:
            return None

    def _load_json(self, ref: str) -> Any:
        return from_canonical_bytes(self._store.get_bytes(ArtifactID.model_validate(ref)))

    @staticmethod
    def _feedback_ref_from_packet(packet_payload: Mapping[str, Any], key: str) -> str | None:
        feedback_loop = packet_payload.get("feedback_loop")
        if not isinstance(feedback_loop, Mapping):
            return None
        value = feedback_loop.get(key)
        if isinstance(value, Mapping):
            artifact_id = value.get("artifact_id")
            return artifact_id if isinstance(artifact_id, str) else None
        if isinstance(value, str):
            return value
        return None


__all__ = ["FeedbackService", "PreparedReissue"]
