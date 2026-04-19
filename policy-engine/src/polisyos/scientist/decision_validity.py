"""Public scientist decision validity module API."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.timestamps import to_iso_utc, utc_now
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import content_hash, from_canonical_bytes
from polisyos.core.contracts.decision_validity import (
    DecisionDependencyEvent,
    DecisionLifecycleJob,
    DecisionTriggerRecord,
    DecisionTriggerType,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
    DecisionValidityTransition,
)
from polisyos.core.contracts.feedback import DecisionMonitoringContract
from polisyos.scientist.engine.operational_monitoring import get_operational_monitor

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore

_StateModel = TypeVar("_StateModel", bound=BaseModel)

_DECISION_VALIDITY_JSON_LOAD_ERRORS = (OSError, ValueError, json.JSONDecodeError)
_DECISION_VALIDITY_MODEL_ERRORS = (TypeError, ValueError, ValidationError)
_DECISION_VALIDITY_ARTIFACT_LOAD_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)


def _serialize_datetime(value: datetime | None) -> str | None:
    return to_iso_utc(value) if value is not None else None


class _DecisionPacketState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packet_ref: str
    decision_lineage_key: str
    current_status: DecisionValidityStatus = DecisionValidityStatus.WARNING
    last_checked_at: datetime | None = None
    evaluation_ref: str | None = None
    reasons: list[str] = Field(default_factory=list)
    active_triggers: list[DecisionTriggerRecord] = Field(default_factory=list)
    sticky_triggers: list[DecisionTriggerRecord] = Field(default_factory=list)
    dependency_keys: list[str] = Field(default_factory=list)
    review_required: bool = False
    supersedes_decision_ref: str | None = None
    superseded_by_ref: str | None = None
    monitoring_contract_ref: str | None = None
    latest_monitoring_report_ref: str | None = None
    latest_compare_report_ref: str | None = None
    latest_reissue_plan_ref: str | None = None
    lifecycle_events: list[DecisionDependencyEvent] = Field(default_factory=list)
    transition_history: list[DecisionValidityTransition] = Field(default_factory=list)
    lifecycle_jobs: list[DecisionLifecycleJob] = Field(default_factory=list)
    last_transition_at: datetime | None = None


class _DecisionLineageState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_lineage_key: str
    head_packet_ref: str
    evaluation_ref: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class _DecisionDependencyIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dependency_key: str
    packet_refs: list[str] = Field(default_factory=list)
    lineage_keys: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class DecisionValidityStateStore:
    """Decision validity state store implementation."""
    def __init__(self, cas: ArtifactStore | Path) -> None:
        root_value = getattr(cas, "root", cas)
        if isinstance(root_value, str):
            root_path = Path(root_value)
        elif isinstance(root_value, Path):
            root_path = root_value
        else:
            raise TypeError("DecisionValidityStateStore requires a local store root or Path")
        self._base = root_path / "decision_validity"
        self._packets = self._base / "packets"
        self._lineages = self._base / "lineages"
        self._dependencies = self._base / "dependencies"
        self._dedupes = self._base / "dedupes"
        self._packets.mkdir(parents=True, exist_ok=True)
        self._lineages.mkdir(parents=True, exist_ok=True)
        self._dependencies.mkdir(parents=True, exist_ok=True)
        self._dedupes.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def make_key(value: str) -> str:
        normalized = value.strip()
        return content_hash(normalized) if normalized else "global"

    def _packet_path(self, packet_ref: str) -> Path:
        return self._packets / f"{self.make_key(packet_ref)}.json"

    def _lineage_path(self, lineage_key: str) -> Path:
        return self._lineages / f"{self.make_key(lineage_key)}.json"

    def _dependency_path(self, dependency_key: str) -> Path:
        return self._dependencies / f"{self.make_key(dependency_key)}.json"

    def _dedupe_path(self, dedupe_key: str) -> Path:
        return self._dedupes / f"{self.make_key(dedupe_key)}.json"

    def load_packet(self, packet_ref: str) -> _DecisionPacketState | None:
        return self._load_model(self._packet_path(packet_ref), _DecisionPacketState)

    def save_packet(self, state: _DecisionPacketState) -> None:
        self._save_model(self._packet_path(state.packet_ref), state)

    def load_lineage(self, lineage_key: str) -> _DecisionLineageState | None:
        return self._load_model(self._lineage_path(lineage_key), _DecisionLineageState)

    def save_lineage(self, state: _DecisionLineageState) -> None:
        self._save_model(self._lineage_path(state.decision_lineage_key), state)

    def load_dependency(self, dependency_key: str) -> _DecisionDependencyIndex | None:
        return self._load_model(self._dependency_path(dependency_key), _DecisionDependencyIndex)

    def save_dependency(self, state: _DecisionDependencyIndex) -> None:
        self._save_model(self._dependency_path(state.dependency_key), state)

    def load_dedupe_event_id(self, dedupe_key: str) -> str | None:
        path = self._dedupe_path(dedupe_key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        value = payload.get("event_id")
        return value if isinstance(value, str) and value else None

    def save_dedupe_event_id(self, dedupe_key: str, event_id: str) -> None:
        path = self._dedupe_path(dedupe_key)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps({"event_id": event_id}, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        temp.replace(path)

    @staticmethod
    def _load_model(path: Path, model_type: type[_StateModel]) -> _StateModel | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except _DECISION_VALIDITY_JSON_LOAD_ERRORS:
            return None
        try:
            return cast("_StateModel", model_type.model_validate(payload))
        except _DECISION_VALIDITY_MODEL_ERRORS:
            return None

    @staticmethod
    def _save_model(path: Path, model: BaseModel) -> None:
        temp = path.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        temp.replace(path)


class DecisionValidityService:
    """Decision validity service implementation."""
    def __init__(
        self,
        store: ArtifactStore,
        *,
        reevaluate_ttl_seconds: int = 300,
    ) -> None:
        self._store = store
        self._state = DecisionValidityStateStore(store)
        self._ttl = max(0, int(reevaluate_ttl_seconds))

    def register_decision_packet(
        self,
        *,
        packet_ref: str,
        envelope: DecisionValidityEnvelope,
        baseline: DecisionValidityEvaluation,
        monitoring_contract_ref: str | None = None,
    ) -> DecisionValidityEvaluation:
        dependency_keys = envelope.dependency_keys()
        head = self._state.load_lineage(envelope.decision_lineage_key)
        supersedes_ref = head.head_packet_ref if head is not None else None

        evaluation = baseline.model_copy(
            update={
                "decision_packet_ref": packet_ref,
                "decision_lineage_key": envelope.decision_lineage_key,
                "dependency_keys": dependency_keys,
                "evaluated_at": utc_now(),
                "supersedes_decision_ref": supersedes_ref,
                "superseded_by_ref": None,
            }
        )
        persisted = self._persist_evaluation(
            packet_ref=packet_ref,
            evaluation=evaluation,
            sticky_triggers=[],
            monitoring_contract_ref=monitoring_contract_ref,
        )
        self._register_dependencies(
            packet_ref=packet_ref,
            decision_lineage_key=envelope.decision_lineage_key,
            dependency_keys=dependency_keys,
        )
        packet_state = self._state.load_packet(packet_ref)
        self._state.save_lineage(
            _DecisionLineageState(
                decision_lineage_key=envelope.decision_lineage_key,
                head_packet_ref=packet_ref,
                evaluation_ref=packet_state.evaluation_ref if packet_state is not None else None,
                updated_at=utc_now(),
            )
        )
        if supersedes_ref and supersedes_ref != packet_ref:
            self._mark_superseded(
                packet_ref=supersedes_ref,
                superseded_by_ref=packet_ref,
                lineage_key=envelope.decision_lineage_key,
            )
        if monitoring_contract_ref:
            self._schedule_monitoring_job(
                packet_ref=packet_ref,
                decision_lineage_key=envelope.decision_lineage_key,
                monitoring_contract_ref=monitoring_contract_ref,
            )
        return persisted

    def ensure_evaluation(
        self,
        packet_ref: str,
        *,
        packet_payload: dict[str, Any] | None = None,
        force: bool = False,
    ) -> DecisionValidityEvaluation:
        current_state = self._state.load_packet(packet_ref)
        if (
            not force
            and current_state is not None
            and current_state.evaluation_ref
            and current_state.last_checked_at is not None
        ):
            age = utc_now() - current_state.last_checked_at
            if age <= timedelta(seconds=self._ttl):
                loaded = self._load_evaluation(current_state.evaluation_ref)
                if loaded is not None:
                    return loaded

        payload = (
            packet_payload
            if packet_payload is not None
            else self._load_packet_payload(packet_ref)
        )
        evaluation = self._compute_evaluation(
            packet_ref=packet_ref,
            packet_payload=payload,
            current_state=current_state,
        )
        return self._persist_evaluation(
            packet_ref=packet_ref,
            evaluation=evaluation,
            sticky_triggers=list(current_state.sticky_triggers) if current_state else [],
        )

    def get_evaluation(
        self,
        packet_ref: str,
        *,
        packet_payload: dict[str, Any] | None = None,
        force: bool = False,
    ) -> tuple[DecisionValidityEvaluation, str | None]:
        evaluation = self.ensure_evaluation(
            packet_ref,
            packet_payload=packet_payload,
            force=force,
        )
        state = self._state.load_packet(packet_ref)
        return evaluation, (state.evaluation_ref if state is not None else None)

    def get_summary(
        self,
        packet_ref: str,
        *,
        packet_payload: dict[str, Any] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        evaluation, evaluation_ref = self.get_evaluation(
            packet_ref,
            packet_payload=packet_payload,
            force=force,
        )
        return {
            "status": evaluation.status.value,
            "checked_at": evaluation.evaluated_at.isoformat(),
            "reasons": list(evaluation.reasons),
            "triggers": [item.model_dump(mode="json") for item in evaluation.triggers],
            "review_required": bool(evaluation.review_required),
            "supersedes_decision_ref": (
                {"artifact_id": evaluation.supersedes_decision_ref}
                if evaluation.supersedes_decision_ref
                else None
            ),
            "superseded_by_ref": (
                {"artifact_id": evaluation.superseded_by_ref}
                if evaluation.superseded_by_ref
                else None
            ),
            "evaluation_ref": {"artifact_id": evaluation_ref} if evaluation_ref else None,
            "decision_lineage_key": evaluation.decision_lineage_key,
            "recommended_action": evaluation.recommended_action,
            "lifecycle": self._lifecycle_summary(packet_ref),
        }

    def mark_dependency_trigger(
        self,
        *,
        dependency_key: str,
        trigger: DecisionTriggerRecord,
    ) -> list[DecisionValidityEvaluation]:
        event = DecisionDependencyEvent(
            event_id=uuid.uuid4().hex,
            dedupe_key=_build_event_dedupe_key(
                trigger=trigger,
                dependency_keys=[dependency_key],
            ),
            trigger_type=trigger.trigger_type,
            status=trigger.status,
            reason=trigger.reason,
            dependency_keys=[dependency_key],
            source_ref=trigger.source_ref,
            payload=dict(trigger.details),
        )
        return self.record_dependency_event(event=event)

    def record_dependency_event(
        self,
        *,
        event: DecisionDependencyEvent,
    ) -> list[DecisionValidityEvaluation]:
        if self._state.load_dedupe_event_id(event.dedupe_key):
            cached_evaluations: list[DecisionValidityEvaluation] = []
            for dependency_key in event.dependency_keys:
                dependency = self._state.load_dependency(dependency_key)
                if dependency is None:
                    continue
                for packet_ref in dependency.packet_refs:
                    cached_evaluations.append(self.ensure_evaluation(packet_ref))
            return cached_evaluations

        self._state.save_dedupe_event_id(event.dedupe_key, event.event_id)
        if event.trigger_type == DecisionTriggerType.CONTEXT_PROFILE_DRIFT:
            get_operational_monitor().record_alert(
                alert_type="drift",
                severity="warn",
                details={
                    "dependency_keys": list(event.dependency_keys),
                    "event_id": event.event_id,
                },
            )
        packet_refs: list[str] = []
        for dependency_key in event.dependency_keys:
            dependency = self._state.load_dependency(dependency_key)
            if dependency is None:
                continue
            for packet_ref in dependency.packet_refs:
                if packet_ref not in packet_refs:
                    packet_refs.append(packet_ref)
        evaluations: list[DecisionValidityEvaluation] = []
        for packet_ref in packet_refs:
            evaluations.append(self._apply_event_to_packet(packet_ref=packet_ref, event=event))
        return evaluations

    def mark_packet_trigger(
        self,
        *,
        packet_ref: str,
        trigger: DecisionTriggerRecord,
    ) -> DecisionValidityEvaluation:
        state = self._state.load_packet(packet_ref)
        dependency_keys = (
            [trigger.dependency_key]
            if trigger.dependency_key
            else list(state.dependency_keys)
            if state is not None
            else []
        )
        event = DecisionDependencyEvent(
            event_id=uuid.uuid4().hex,
            dedupe_key=_build_event_dedupe_key(
                trigger=trigger,
                dependency_keys=dependency_keys,
                packet_ref=packet_ref,
            ),
            trigger_type=trigger.trigger_type,
            status=trigger.status,
            reason=trigger.reason,
            dependency_keys=dependency_keys,
            source_ref=trigger.source_ref,
            payload=dict(trigger.details),
        )
        if self._state.load_dedupe_event_id(event.dedupe_key):
            return self.ensure_evaluation(packet_ref)
        self._state.save_dedupe_event_id(event.dedupe_key, event.event_id)
        return self._apply_event_to_packet(packet_ref=packet_ref, event=event)

    def backfill_packet(self, packet_ref: str) -> DecisionValidityEvaluation:
        payload = self._load_packet_payload(packet_ref)
        evaluation = self.ensure_evaluation(packet_ref, packet_payload=payload, force=True)
        if _load_envelope(payload) is None:
            trigger = DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.LEGACY_PACKET,
                status=DecisionValidityStatus.WARNING,
                reason="legacy_packet_missing_validity_envelope",
            )
            evaluation = self.mark_packet_trigger(packet_ref=packet_ref, trigger=trigger)
        return evaluation

    def _apply_event_to_packet(
        self,
        *,
        packet_ref: str,
        event: DecisionDependencyEvent,
    ) -> DecisionValidityEvaluation:
        state = self._state.load_packet(packet_ref)
        if state is None:
            self.ensure_evaluation(packet_ref)
            state = self._state.load_packet(packet_ref)
        if state is None:
            payload = self._load_packet_payload(packet_ref)
            envelope = _load_envelope(payload)
            lineage_key = envelope.decision_lineage_key if envelope is not None else packet_ref
            dependency_keys = envelope.dependency_keys() if envelope is not None else []
            state = _DecisionPacketState(
                packet_ref=packet_ref,
                decision_lineage_key=lineage_key,
                dependency_keys=dependency_keys,
            )
        previous_status = state.current_status
        previous_evaluation_ref = state.evaluation_ref
        sticky = list(state.sticky_triggers if state is not None else [])
        triggers = _trigger_records_from_event(event)
        sticky = _dedupe_trigger_records([*sticky, *triggers])
        lifecycle_events = _dedupe_events([*state.lifecycle_events, event])
        lifecycle_jobs = list(state.lifecycle_jobs)
        lifecycle_jobs.append(
            DecisionLifecycleJob(
                job_id=f"decision_eval_{uuid.uuid4().hex[:12]}",
                job_kind="evaluation",
                packet_ref=packet_ref,
                decision_lineage_key=state.decision_lineage_key,
                state="completed",
                reason=event.reason,
                scheduled_for=event.occurred_at,
                trigger_event_id=event.event_id,
                completed_at=utc_now(),
                payload={"dependency_keys": list(event.dependency_keys)},
            )
        )
        state = state.model_copy(
            update={
                "sticky_triggers": sticky,
                "lifecycle_events": lifecycle_events,
                "lifecycle_jobs": _dedupe_jobs(lifecycle_jobs),
            }
        )
        self._state.save_packet(state)
        evaluation = self.ensure_evaluation(packet_ref, force=True)
        refreshed_state = self._state.load_packet(packet_ref)
        self._record_transition(
            packet_ref=packet_ref,
            decision_lineage_key=evaluation.decision_lineage_key,
            previous_status=previous_status,
            current_status=evaluation.status,
            reason=event.reason,
            event_id=event.event_id,
            review_required=evaluation.review_required,
            evaluation_ref=(
                refreshed_state.evaluation_ref
                if refreshed_state is not None
                else previous_evaluation_ref
            ),
        )
        return evaluation

    def _mark_superseded(
        self,
        *,
        packet_ref: str,
        superseded_by_ref: str,
        lineage_key: str,
    ) -> DecisionValidityEvaluation:
        current = self.ensure_evaluation(packet_ref)
        trigger = DecisionTriggerRecord(
            trigger_type=DecisionTriggerType.SUPERSEDED,
            status=DecisionValidityStatus.SUPERSEDED,
            reason=f"superseded_by:{superseded_by_ref}",
            source_ref=superseded_by_ref,
            details={"superseded_by_ref": superseded_by_ref},
        )
        updated = current.model_copy(
            update={
                "status": DecisionValidityStatus.SUPERSEDED,
                "evaluated_at": utc_now(),
                "reasons": _dedupe_strings([*current.reasons, trigger.reason]),
                "triggers": _dedupe_trigger_records([*current.triggers, trigger]),
                "review_required": False,
                "recommended_action": _recommended_action(DecisionValidityStatus.SUPERSEDED),
                "superseded_by_ref": superseded_by_ref,
                "decision_lineage_key": lineage_key,
            }
        )
        state = self._state.load_packet(packet_ref)
        sticky = list(state.sticky_triggers) if state is not None else []
        return self._persist_evaluation(
            packet_ref=packet_ref,
            evaluation=updated,
            sticky_triggers=sticky,
        )

    def _persist_evaluation(
        self,
        *,
        packet_ref: str,
        evaluation: DecisionValidityEvaluation,
        sticky_triggers: list[DecisionTriggerRecord],
        monitoring_contract_ref: str | None = None,
    ) -> DecisionValidityEvaluation:
        packet_artifact_id = ArtifactID.model_validate(packet_ref)
        evaluation_ref = self._store.put_json(
            evaluation.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind="scientist.decision_validity_evaluation",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.DecisionValidityEvaluation",
                    version="1.0",
                ),
                inputs=[InputRef(artifact_id=packet_artifact_id, role="decision_packet")],
            ),
        )
        state = self._state.load_packet(packet_ref)
        dependency_keys = list(evaluation.dependency_keys)
        if state is not None and not dependency_keys:
            dependency_keys = list(state.dependency_keys)
        packet_state = _DecisionPacketState(
            packet_ref=packet_ref,
            decision_lineage_key=evaluation.decision_lineage_key,
            current_status=evaluation.status,
            last_checked_at=evaluation.evaluated_at,
            evaluation_ref=str(evaluation_ref.artifact_id),
            reasons=list(evaluation.reasons),
            active_triggers=list(evaluation.triggers),
            sticky_triggers=sticky_triggers,
            dependency_keys=dependency_keys,
            review_required=evaluation.review_required,
            supersedes_decision_ref=evaluation.supersedes_decision_ref,
            superseded_by_ref=evaluation.superseded_by_ref,
            monitoring_contract_ref=(
                monitoring_contract_ref
                if monitoring_contract_ref is not None
                else (state.monitoring_contract_ref if state is not None else None)
            ),
            latest_monitoring_report_ref=(
                state.latest_monitoring_report_ref if state is not None else None
            ),
            latest_compare_report_ref=(
                state.latest_compare_report_ref if state is not None else None
            ),
            latest_reissue_plan_ref=(
                state.latest_reissue_plan_ref if state is not None else None
            ),
            lifecycle_events=list(state.lifecycle_events) if state is not None else [],
            transition_history=list(state.transition_history) if state is not None else [],
            lifecycle_jobs=list(state.lifecycle_jobs) if state is not None else [],
            last_transition_at=state.last_transition_at if state is not None else None,
        )
        self._state.save_packet(packet_state)
        return evaluation

    def update_feedback_refs(
        self,
        packet_ref: str,
        *,
        monitoring_contract_ref: str | None = None,
        monitoring_report_ref: str | None = None,
        compare_report_ref: str | None = None,
        reissue_plan_ref: str | None = None,
    ) -> None:
        state = self._state.load_packet(packet_ref)
        if state is None:
            self.ensure_evaluation(packet_ref)
            state = self._state.load_packet(packet_ref)
        if state is None:
            return
        self._state.save_packet(
            state.model_copy(
                update={
                    "monitoring_contract_ref": (
                        monitoring_contract_ref
                        if monitoring_contract_ref is not None
                        else state.monitoring_contract_ref
                    ),
                    "latest_monitoring_report_ref": (
                        monitoring_report_ref
                        if monitoring_report_ref is not None
                        else state.latest_monitoring_report_ref
                    ),
                    "latest_compare_report_ref": (
                        compare_report_ref
                        if compare_report_ref is not None
                        else state.latest_compare_report_ref
                    ),
                    "latest_reissue_plan_ref": (
                        reissue_plan_ref
                        if reissue_plan_ref is not None
                        else state.latest_reissue_plan_ref
                    ),
                    "lifecycle_jobs": _complete_monitoring_jobs(
                        state.lifecycle_jobs,
                        monitoring_contract_ref=monitoring_contract_ref,
                        monitoring_report_ref=monitoring_report_ref,
                    ),
                }
            )
        )

    def get_feedback_refs(self, packet_ref: str) -> dict[str, str | None]:
        state = self._state.load_packet(packet_ref)
        if state is None:
            self.ensure_evaluation(packet_ref)
            state = self._state.load_packet(packet_ref)
        if state is None:
            return {
                "monitoring_contract_ref": None,
                "latest_monitoring_report_ref": None,
                "latest_compare_report_ref": None,
                "latest_reissue_plan_ref": None,
            }
        return {
            "monitoring_contract_ref": state.monitoring_contract_ref,
            "latest_monitoring_report_ref": state.latest_monitoring_report_ref,
            "latest_compare_report_ref": state.latest_compare_report_ref,
            "latest_reissue_plan_ref": state.latest_reissue_plan_ref,
        }

    def _lifecycle_summary(self, packet_ref: str) -> dict[str, Any]:
        state = self._state.load_packet(packet_ref)
        if state is None:
            return {
                "events": [],
                "transitions": [],
                "pending_reviews": [],
                "scheduled_jobs": [],
                "reissue_candidates": [],
                "latest_transition_at": None,
            }
        pending_reviews = [
            {
                "event_id": event.event_id,
                "trigger_type": event.trigger_type.value,
                "reason": event.reason,
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in state.lifecycle_events
            if event.status == DecisionValidityStatus.REQUIRES_HUMAN_REVIEW
        ]
        reissue_candidates = []
        if state.latest_reissue_plan_ref:
            reissue_candidates.append({"artifact_id": state.latest_reissue_plan_ref})
        return {
            "events": [item.model_dump(mode="json") for item in state.lifecycle_events[-20:]],
            "transitions": [
                item.model_dump(mode="json")
                for item in state.transition_history[-20:]
            ],
            "pending_reviews": pending_reviews,
            "scheduled_jobs": [item.model_dump(mode="json") for item in state.lifecycle_jobs[-20:]],
            "reissue_candidates": reissue_candidates,
            "latest_transition_at": _serialize_datetime(state.last_transition_at),
        }

    def _record_transition(
        self,
        *,
        packet_ref: str,
        decision_lineage_key: str,
        previous_status: DecisionValidityStatus | None,
        current_status: DecisionValidityStatus,
        reason: str,
        event_id: str | None,
        review_required: bool,
        evaluation_ref: str | None,
    ) -> None:
        state = self._state.load_packet(packet_ref)
        if state is None:
            return
        latest = state.transition_history[-1] if state.transition_history else None
        if (
            latest is not None
            and latest.current_status == current_status
            and latest.reason == reason
            and latest.triggered_by_event_id == event_id
        ):
            return
        occurred_at = utc_now()
        transition = DecisionValidityTransition(
            transition_id=f"decision_transition_{uuid.uuid4().hex[:12]}",
            packet_ref=packet_ref,
            decision_lineage_key=decision_lineage_key,
            previous_status=previous_status,
            current_status=current_status,
            reason=reason,
            occurred_at=occurred_at,
            triggered_by_event_id=event_id,
            evaluation_ref=evaluation_ref,
            review_required=review_required,
        )
        self._state.save_packet(
            state.model_copy(
                update={
                    "transition_history": [*state.transition_history, transition],
                    "last_transition_at": occurred_at,
                }
            )
        )

    def _schedule_monitoring_job(
        self,
        *,
        packet_ref: str,
        decision_lineage_key: str,
        monitoring_contract_ref: str,
    ) -> None:
        state = self._state.load_packet(packet_ref)
        if state is None:
            return
        contract = self._load_monitoring_contract(monitoring_contract_ref)
        if contract is None:
            return
        scheduled_for = _monitoring_due_at(contract)
        job = DecisionLifecycleJob(
            job_id=f"decision_monitor_{uuid.uuid4().hex[:12]}",
            job_kind="scheduled_monitoring",
            packet_ref=packet_ref,
            decision_lineage_key=decision_lineage_key,
            state="pending",
            reason="monitoring_contract_registered",
            scheduled_for=scheduled_for,
            monitoring_contract_ref=monitoring_contract_ref,
            payload={"metric_ids": [item.metric_id for item in contract.metrics]},
        )
        self._state.save_packet(
            state.model_copy(
                update={
                    "lifecycle_jobs": _dedupe_jobs([*state.lifecycle_jobs, job]),
                }
            )
        )

    def _compute_evaluation(
        self,
        *,
        packet_ref: str,
        packet_payload: dict[str, Any],
        current_state: _DecisionPacketState | None,
    ) -> DecisionValidityEvaluation:
        envelope = _load_envelope(packet_payload)
        baseline = _load_baseline(packet_payload)
        sticky_triggers = list(current_state.sticky_triggers) if current_state is not None else []
        superseded_by_ref = current_state.superseded_by_ref if current_state is not None else None

        if envelope is None:
            triggers = _dedupe_trigger_records(
                [
                    DecisionTriggerRecord(
                        trigger_type=DecisionTriggerType.LEGACY_PACKET,
                        status=DecisionValidityStatus.WARNING,
                        reason="legacy_packet_missing_validity_envelope",
                    ),
                    *sticky_triggers,
                ]
            )
            reasons = _dedupe_strings(
                [
                    "legacy_packet_missing_validity_envelope",
                    *(trigger.reason for trigger in sticky_triggers),
                ]
            )
            status = DecisionValidityStatus.WARNING
            for trigger in triggers:
                status = _max_status(status, trigger.status)
            if superseded_by_ref:
                status = DecisionValidityStatus.SUPERSEDED
                superseded_reason = f"superseded_by:{superseded_by_ref}"
                reasons = _dedupe_strings([*reasons, superseded_reason])
                triggers = _dedupe_trigger_records(
                    [
                        *triggers,
                        DecisionTriggerRecord(
                            trigger_type=DecisionTriggerType.SUPERSEDED,
                            status=DecisionValidityStatus.SUPERSEDED,
                            reason=superseded_reason,
                            source_ref=superseded_by_ref,
                            details={"superseded_by_ref": superseded_by_ref},
                        ),
                    ]
                )
            return DecisionValidityEvaluation(
                decision_packet_ref=packet_ref,
                decision_lineage_key=packet_ref,
                status=status,
                reasons=reasons,
                triggers=triggers,
                dependency_keys=[],
                recommended_action=_recommended_action(status),
                review_required=status == DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
                superseded_by_ref=superseded_by_ref,
            )

        if baseline is None:
            baseline = DecisionValidityEvaluation(
                decision_packet_ref=packet_ref,
                decision_lineage_key=envelope.decision_lineage_key,
                status=DecisionValidityStatus.ACTIVE,
                dependency_keys=envelope.dependency_keys(),
                recommended_action=_recommended_action(DecisionValidityStatus.ACTIVE),
            )

        triggers = _dedupe_trigger_records([*baseline.triggers, *sticky_triggers])
        reasons = _dedupe_strings(
            [
                *baseline.reasons,
                *(trigger.reason for trigger in sticky_triggers),
            ]
        )
        status = baseline.status
        for trigger in triggers:
            status = _max_status(status, trigger.status)

        if superseded_by_ref:
            status = DecisionValidityStatus.SUPERSEDED
            superseded_reason = f"superseded_by:{superseded_by_ref}"
            reasons = _dedupe_strings([*reasons, superseded_reason])
            triggers = _dedupe_trigger_records(
                [
                    *triggers,
                    DecisionTriggerRecord(
                        trigger_type=DecisionTriggerType.SUPERSEDED,
                        status=DecisionValidityStatus.SUPERSEDED,
                        reason=superseded_reason,
                        source_ref=superseded_by_ref,
                        details={"superseded_by_ref": superseded_by_ref},
                    ),
                ]
            )

        return baseline.model_copy(
            update={
                "decision_packet_ref": packet_ref,
                "decision_lineage_key": envelope.decision_lineage_key,
                "evaluated_at": utc_now(),
                "status": status,
                "reasons": reasons,
                "triggers": triggers,
                "dependency_keys": (
                    baseline.dependency_keys
                    if baseline.dependency_keys
                    else envelope.dependency_keys()
                ),
                "review_required": status == DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
                "recommended_action": _recommended_action(status),
                "supersedes_decision_ref": (
                    current_state.supersedes_decision_ref if current_state is not None else None
                ),
                "superseded_by_ref": superseded_by_ref,
            }
        )

    def _register_dependencies(
        self,
        *,
        packet_ref: str,
        decision_lineage_key: str,
        dependency_keys: list[str],
    ) -> None:
        for dependency_key in dependency_keys:
            dependency_state = self._state.load_dependency(dependency_key)
            if dependency_state is None:
                dependency_state = _DecisionDependencyIndex(dependency_key=dependency_key)
            packet_refs = list(dependency_state.packet_refs)
            lineage_keys = list(dependency_state.lineage_keys)
            if packet_ref not in packet_refs:
                packet_refs.append(packet_ref)
            if decision_lineage_key not in lineage_keys:
                lineage_keys.append(decision_lineage_key)
            self._state.save_dependency(
                dependency_state.model_copy(
                    update={
                        "packet_refs": sorted(packet_refs),
                        "lineage_keys": sorted(lineage_keys),
                        "updated_at": utc_now(),
                    }
                )
            )

    def _load_packet_payload(self, packet_ref: str) -> dict[str, Any]:
        artifact_id = ArtifactID.model_validate(packet_ref)
        payload = from_canonical_bytes(self._store.get_bytes(artifact_id))
        return payload if isinstance(payload, dict) else {}

    def _load_evaluation(self, evaluation_ref: str) -> DecisionValidityEvaluation | None:
        try:
            artifact_id = ArtifactID.model_validate(evaluation_ref)
            payload = from_canonical_bytes(self._store.get_bytes(artifact_id))
        except _DECISION_VALIDITY_ARTIFACT_LOAD_ERRORS:
            return None
        if not isinstance(payload, dict):
            return None
        try:
            return DecisionValidityEvaluation.model_validate(payload)
        except _DECISION_VALIDITY_MODEL_ERRORS:
            return None

    def _load_monitoring_contract(
        self,
        monitoring_contract_ref: str,
    ) -> DecisionMonitoringContract | None:
        try:
            artifact_id = ArtifactID.model_validate(monitoring_contract_ref)
            payload = from_canonical_bytes(self._store.get_bytes(artifact_id))
        except _DECISION_VALIDITY_ARTIFACT_LOAD_ERRORS:
            return None
        if not isinstance(payload, dict):
            return None
        try:
            return DecisionMonitoringContract.model_validate(payload)
        except _DECISION_VALIDITY_MODEL_ERRORS:
            return None


def _load_envelope(packet_payload: dict[str, Any]) -> DecisionValidityEnvelope | None:
    value = packet_payload.get("decision_validity_envelope")
    if not isinstance(value, dict):
        return None
    try:
        return DecisionValidityEnvelope.model_validate(value)
    except _DECISION_VALIDITY_MODEL_ERRORS:
        return None


def _load_baseline(packet_payload: dict[str, Any]) -> DecisionValidityEvaluation | None:
    value = packet_payload.get("decision_validity_baseline")
    if not isinstance(value, dict):
        return None
    try:
        return DecisionValidityEvaluation.model_validate(value)
    except _DECISION_VALIDITY_MODEL_ERRORS:
        return None


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _dedupe_trigger_records(
    values: list[DecisionTriggerRecord],
) -> list[DecisionTriggerRecord]:
    deduped: list[DecisionTriggerRecord] = []
    seen: set[tuple[str, str, str | None, str | None]] = set()
    for item in values:
        key = (
            item.trigger_type.value,
            item.reason,
            item.dependency_key,
            item.source_ref,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _dedupe_events(
    values: list[DecisionDependencyEvent],
) -> list[DecisionDependencyEvent]:
    deduped: list[DecisionDependencyEvent] = []
    seen: set[str] = set()
    for item in values:
        if item.event_id in seen:
            continue
        seen.add(item.event_id)
        deduped.append(item)
    return deduped


def _dedupe_jobs(
    values: list[DecisionLifecycleJob],
) -> list[DecisionLifecycleJob]:
    deduped: list[DecisionLifecycleJob] = []
    seen: set[str] = set()
    for item in values:
        if item.job_id in seen:
            continue
        seen.add(item.job_id)
        deduped.append(item)
    return deduped


def _build_event_dedupe_key(
    *,
    trigger: DecisionTriggerRecord,
    dependency_keys: list[str],
    packet_ref: str | None = None,
) -> str:
    return str(
        content_hash(
            json.dumps(
                {
                    "trigger_type": trigger.trigger_type.value,
                    "status": trigger.status.value,
                    "reason": trigger.reason,
                    "dependency_keys": sorted(item for item in dependency_keys if item),
                    "source_ref": trigger.source_ref,
                    "packet_ref": packet_ref,
                    "details": trigger.details,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    )


def _trigger_records_from_event(
    event: DecisionDependencyEvent,
) -> list[DecisionTriggerRecord]:
    if event.dependency_keys:
        return [
            DecisionTriggerRecord(
                trigger_type=event.trigger_type,
                status=event.status,
                reason=event.reason,
                dependency_key=dependency_key,
                source_ref=event.source_ref,
                details=dict(event.payload),
            )
            for dependency_key in event.dependency_keys
        ]
    return [
        DecisionTriggerRecord(
            trigger_type=event.trigger_type,
            status=event.status,
            reason=event.reason,
            source_ref=event.source_ref,
            details=dict(event.payload),
        )
    ]


def _monitoring_due_at(contract: DecisionMonitoringContract) -> datetime:
    max_offset_days = 0
    for metric in contract.metrics:
        max_offset_days = max(
            max_offset_days,
            int(metric.window.end_offset_days) + int(metric.window.grace_days),
        )
    return cast("datetime", contract.anchor_at + timedelta(days=max_offset_days))


def _complete_monitoring_jobs(
    jobs: list[DecisionLifecycleJob],
    *,
    monitoring_contract_ref: str | None,
    monitoring_report_ref: str | None,
) -> list[DecisionLifecycleJob]:
    if monitoring_report_ref is None:
        return jobs
    completed_at = utc_now()
    updated: list[DecisionLifecycleJob] = []
    for job in jobs:
        if job.job_kind != "scheduled_monitoring":
            updated.append(job)
            continue
        if monitoring_contract_ref and job.monitoring_contract_ref != monitoring_contract_ref:
            updated.append(job)
            continue
        updated.append(
            job.model_copy(
                update={
                    "state": "completed",
                    "completed_at": completed_at,
                    "payload": {
                        **job.payload,
                        "monitoring_report_ref": monitoring_report_ref,
                    },
                }
            )
        )
    return updated


def _recommended_action(status: DecisionValidityStatus) -> str:
    if status == DecisionValidityStatus.ACTIVE:
        return "none"
    if status == DecisionValidityStatus.WARNING:
        return "monitor"
    if status == DecisionValidityStatus.STALE:
        return "refresh_decision"
    if status == DecisionValidityStatus.SUPERSEDED:
        return "review_superseded"
    if status == DecisionValidityStatus.REVOKED:
        return "record_revocation"
    return "human_review"


def _max_status(
    left: DecisionValidityStatus,
    right: DecisionValidityStatus,
) -> DecisionValidityStatus:
    order = {
        DecisionValidityStatus.ACTIVE: 0,
        DecisionValidityStatus.WARNING: 1,
        DecisionValidityStatus.STALE: 2,
        DecisionValidityStatus.REQUIRES_HUMAN_REVIEW: 3,
        DecisionValidityStatus.SUPERSEDED: 4,
        DecisionValidityStatus.REVOKED: 5,
    }
    return right if order[right] > order[left] else left


__all__ = [
    "DecisionValidityService",
    "DecisionValidityStateStore",
]
