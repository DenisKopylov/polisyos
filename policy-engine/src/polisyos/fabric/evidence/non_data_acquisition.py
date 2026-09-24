"""Candidate non-data intake/re-entry extending Fabric evidence and core CAS.

The eight commissioned object predicates are distinct from route selection,
which remains in ``runtime.quality.acquisition_planner``. Persisted process
closure means only that the demanding candidate predicate reran and passed;
institutional truth, approval, and authority are never emitted here. Independent
verifier and demanding-owner ports let a separately owned assurance battery
judge these outputs without reusing this implementation as its oracle.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.fabric.data_plane.evidence_journal import (
    append_fsync_jsonl,
    canonical_json_bytes,
    content_sha256,
    resolve_journal_event_ref,
)
from polisyos.fabric.evidence.ceiling_relations import (
    CeilingScope,
    CeilingVocabulary,
    evaluate_ceiling,
)
from polisyos.fabric.io.atomic import file_lock

_DIGEST = r"^sha256:[0-9a-f]{64}$"
_CANDIDATE_KIND = "fabric.non_data_acquisition.candidate"
_VOCABULARY_KIND = "fabric.non_data_acquisition.ceiling_vocabulary"
_RECEIPT_KIND = "fabric.non_data_acquisition.receipt"


class AcquisitionType(StrEnum):
    """The commissioned missing-object union; unknowns are not a ninth default."""

    GROUNDING_RELATION = "grounding_relation"
    ESTIMAND_BINDING = "estimand_binding"
    OWNER_WRITABILITY = "owner_writability"
    LEGAL_MANDATE = "legal_mandate"
    NORMATIVE_AUTHORIZATION = "normative_authorization"
    IMPLEMENTATION_CAPACITY_EVIDENCE = "implementation_capacity_evidence"
    COMPETENT_HUMAN_DECISION = "competent_human_decision"
    INDEPENDENT_AUDIT = "independent_audit"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class GapShapeAssessment(_StrictModel):
    """Structural classification of a candidate demand, without domain authority."""

    outcome: Literal["one_case", "split_required", "not_established"]
    acquisition_types: tuple[AcquisitionType, ...]
    predicate_grade: Literal["recomputed"] = "recomputed"
    predicate_scope: Literal["candidate_demand_structure_only"] = "candidate_demand_structure_only"
    authority_granted: Literal[False] = False


class NonDataRequest(_StrictModel):
    """Exact candidate request; row volume is deliberately absent from identity."""

    schema_version: Literal["fabric.non_data_acquisition.request.v1"] = (
        "fabric.non_data_acquisition.request.v1"
    )
    request_id: str = Field(min_length=1)
    claim_ref: str = Field(min_length=1)
    gap_id: str = Field(min_length=1)
    demand: dict[str, Any]
    candidate_ref: str | None = Field(default=None, pattern=_DIGEST)
    vocabulary_ref: str | None = Field(default=None, pattern=_DIGEST)
    requested_use: CeilingScope | None = None
    planner_report_ref: str | None = Field(default=None, pattern=_DIGEST)


class CandidateObject(_StrictModel):
    """Content-bound candidate body, never a producer appointment or signature."""

    object_type: AcquisitionType
    demand_hash: str = Field(pattern=_DIGEST)
    body: dict[str, Any]
    ceiling: CeilingScope


class NonDataReceipt(_StrictModel):
    """Run-emitted candidate process result with an empty institutional slot."""

    schema_version: Literal["fabric.non_data_acquisition.receipt.v1"] = (
        "fabric.non_data_acquisition.receipt.v1"
    )
    request: NonDataRequest
    evaluated_at: AwareDatetime
    shape: GapShapeAssessment
    resolution_state: Literal[
        "shape_not_established",
        "split_required",
        "admission_refused",
        "reentry_closed",
        "reentry_provisional_refusal",
    ]
    reason_codes: tuple[str, ...]
    authority_granted: Literal[False] = False
    institutional_signer: None = None
    authority_purpose: Literal["candidate_process_only"] = "candidate_process_only"
    institutional_predicate_grade: Literal["not_established"] = "not_established"
    demanding_owner_id: str | None
    verifier_owner_id: str | None
    planner_report_ref: str | None = Field(default=None, pattern=_DIGEST)
    artifact_ref: str | None = Field(default=None, pattern=_DIGEST)


class AcquisitionEvaluationContext(_StrictModel):
    """Immutable exact use and time supplied to every candidate semantic owner.

    The demand and resolved candidate remain separate payloads; their content
    identities bind them to the claim, request, vocabulary and current use here.
    A ceiling comparison is necessary but cannot replace the owners' predicates.
    """

    request_id: str = Field(min_length=1)
    claim_ref: str = Field(min_length=1)
    gap_id: str = Field(min_length=1)
    demand_hash: str = Field(pattern=_DIGEST)
    candidate_ref: str = Field(pattern=_DIGEST)
    vocabulary_ref: str = Field(pattern=_DIGEST)
    planner_report_ref: str | None = Field(default=None, pattern=_DIGEST)
    requested_use: CeilingScope
    evaluated_at: AwareDatetime


class CandidateVerifier(Protocol):
    """Separately allocated semantic verifier; a signature is not its return type."""

    owner_id: str

    def verify(
        self,
        *,
        demand: Mapping[str, Any],
        candidate: Mapping[str, Any],
        context: AcquisitionEvaluationContext,
    ) -> bool:
        """Recompute candidate adequacy for this exact claim, use and time."""
        ...


class DemandingOwner(CandidateVerifier, Protocol):
    """Owner of the blocked candidate predicate, with a pure re-entry operation."""

    def reenter(
        self,
        *,
        demand: Mapping[str, Any],
        candidate: Mapping[str, Any],
        context: AcquisitionEvaluationContext,
    ) -> bool:
        """Rerun the original predicate in current context without an external act."""
        ...


def demand_hash(demand: Mapping[str, Any]) -> str:
    """Bind the entire structured demand without any observation-count proxy."""
    return content_sha256(demand)


def _complete(value: object, names: tuple[str, ...]) -> bool:
    return isinstance(value, Mapping) and all(
        isinstance(value.get(name), str) and bool(value[name].strip()) for name in names
    )


def classify_gap(demand: Mapping[str, Any]) -> GapShapeAssessment:
    """Evaluate the eight positive predicates and their structural siblings.

    This result describes the candidate demand's object, not whether an external
    institution supplied truthful facts. That latter predicate remains unknown.
    """
    known = {
        "target",
        "relation",
        "mutation",
        "act",
        "determination",
        "commitment",
        "judgment",
        "engagement",
    }
    if not demand or set(demand) - known:
        return GapShapeAssessment(outcome="not_established", acquisition_types=())
    cases = []
    classified_fields = set()
    target = demand.get("target")
    target_fields = (
        "regime",
        "population",
        "outcome",
        "horizon",
        "intercurrent_events",
        "contrast",
    )
    target_bound = _complete(target, target_fields)
    if (
        isinstance(target, Mapping)
        and set(target) == set(target_fields)
        and all(value is None or isinstance(value, str) for value in target.values())
    ):
        classified_fields.add("target")
        if not target_bound:
            cases.append(AcquisitionType.ESTIMAND_BINDING)
    relation = demand.get("relation")
    if _complete(relation, ("source", "target", "context", "evidence_regime")):
        assumptions = relation.get("assumptions")
        if (
            isinstance(assumptions, list)
            and assumptions
            and all(isinstance(x, str) and x for x in assumptions)
        ):
            classified_fields.add("relation")
            if target_bound:
                cases.append(AcquisitionType.GROUNDING_RELATION)
    if _complete(demand.get("mutation"), ("system", "object", "field", "operation", "purpose")):
        classified_fields.add("mutation")
        cases.append(AcquisitionType.OWNER_WRITABILITY)
    act = demand.get("act")
    if _complete(act, ("jurisdiction", "office", "action")):
        chain = act.get("delegation_chain")
        if isinstance(chain, list) and chain and None in chain:
            classified_fields.add("act")
            cases.append(AcquisitionType.LEGAL_MANDATE)
    if _complete(
        demand.get("determination"), ("regime", "issuer", "procedure", "purpose", "version")
    ):
        classified_fields.add("determination")
        cases.append(AcquisitionType.NORMATIVE_AUTHORIZATION)
    commitment = demand.get("commitment")
    if _complete(commitment, ("entity", "version", "stage", "environment", "horizon")):
        prerequisites = commitment.get("prerequisites")
        load = commitment.get("load")
        if (
            isinstance(load, (int, float))
            and not isinstance(load, bool)
            and load > 0
            and isinstance(prerequisites, dict)
            and prerequisites
            and None in prerequisites.values()
        ):
            classified_fields.add("commitment")
            cases.append(AcquisitionType.IMPLEMENTATION_CAPACITY_EVIDENCE)
    judgment = demand.get("judgment")
    if _complete(judgment, ("question", "role", "competence", "subject", "version")):
        work = judgment.get("required_work")
        if (
            judgment.get("assurance_engagement") is False
            and isinstance(work, list)
            and work
            and all(isinstance(x, str) and x for x in work)
        ):
            classified_fields.add("judgment")
            cases.append(AcquisitionType.COMPETENT_HUMAN_DECISION)
    if _complete(
        demand.get("engagement"),
        ("subject", "version", "criteria", "scope", "period", "level", "relationship"),
    ):
        classified_fields.add("engagement")
        cases.append(AcquisitionType.INDEPENDENT_AUDIT)
    if set(demand) != classified_fields:
        return GapShapeAssessment(outcome="not_established", acquisition_types=())
    outcome = "one_case" if len(cases) == 1 else "split_required" if cases else "not_established"
    return GapShapeAssessment(outcome=outcome, acquisition_types=tuple(cases))


class NonDataAcquisitionRuntime:
    """Resolve, compare, persist and re-enter candidate non-data acquisitions."""

    def __init__(
        self,
        *,
        store: FileSystemCAS,
        journal_path: Path,
        demanding_owner: DemandingOwner | None = None,
        independent_verifier: CandidateVerifier | None = None,
    ) -> None:
        self.store = store
        self.journal_path = journal_path
        self.demanding_owner = demanding_owner
        self.independent_verifier = independent_verifier

    def _persist(self, payload: object, kind: str) -> str:
        ref = self.store.put_bytes(
            canonical_json_bytes(payload),
            opts=PutOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=kind, version="1"),
            ),
        )
        return str(ref.artifact_id)

    def _resolve(self, ref: str, kind: str) -> dict[str, Any]:
        try:
            blob = self.store.get_bytes(ref)
            import hashlib

            if ref != "sha256:" + hashlib.sha256(blob).hexdigest():
                raise ValueError("content_identity_mismatch")
            manifest = self.store.get_manifest(ref)
            if (
                manifest.kind != kind
                or manifest.artifact_schema is None
                or manifest.artifact_schema.version != "1"
            ):
                raise ValueError("artifact_owner_kind_mismatch")
            payload = json.loads(blob)
            if not isinstance(payload, dict) or canonical_json_bytes(payload) != blob:
                raise ValueError("content_encoding_invalid")
            return payload
        except (OSError, KeyError, TypeError) as exc:
            raise ValueError("owner_target_unresolved") from exc

    def persist_candidate(self, payload: Mapping[str, Any]) -> str:
        """Persist candidate bytes; this confers neither admission nor authority."""
        candidate = CandidateObject.model_validate(payload)
        return self._persist(candidate.model_dump(mode="json"), _CANDIDATE_KIND)

    def persist_vocabulary(self, payload: Mapping[str, Any]) -> str:
        """Register complete candidate definitions through the real schema owner."""
        vocabulary = CeilingVocabulary.model_validate(payload)
        return self._persist(vocabulary.model_dump(mode="json"), _VOCABULARY_KIND)

    def _owners_accept(
        self,
        *,
        demand: Mapping[str, Any],
        candidate: Mapping[str, Any],
        context: AcquisitionEvaluationContext,
    ) -> bool:
        owner, verifier = self.demanding_owner, self.independent_verifier
        if owner is None or verifier is None or owner is verifier:
            return False
        if not owner.owner_id or not verifier.owner_id or owner.owner_id == verifier.owner_id:
            return False
        return (
            owner.verify(demand=demand, candidate=candidate, context=context) is True
            and verifier.verify(demand=demand, candidate=candidate, context=context) is True
        )

    def _admit(
        self, request: NonDataRequest, at: datetime
    ) -> tuple[
        GapShapeAssessment,
        CandidateObject | None,
        AcquisitionEvaluationContext | None,
        tuple[str, ...],
    ]:
        shape = classify_gap(request.demand)
        if shape.outcome != "one_case":
            return shape, None, None, (shape.outcome,)
        if request.candidate_ref is None:
            return shape, None, None, ("non_data_object_missing",)
        try:
            candidate = CandidateObject.model_validate(
                self._resolve(request.candidate_ref, _CANDIDATE_KIND)
            )
            if candidate.object_type != shape.acquisition_types[
                0
            ] or candidate.demand_hash != demand_hash(request.demand):
                return shape, None, None, ("candidate_demand_binding_mismatch",)
            if request.vocabulary_ref is None or request.requested_use is None:
                return shape, None, None, ("ceiling_inputs_missing",)
            vocabulary = CeilingVocabulary.model_validate(
                self._resolve(request.vocabulary_ref, _VOCABULARY_KIND)
            )
            comparison = evaluate_ceiling(
                vocabulary=vocabulary,
                requested=request.requested_use,
                ceiling=candidate.ceiling,
                at=at,
            )
            if not comparison.permitted:
                return shape, None, None, ("ceiling_refused",)
            context = AcquisitionEvaluationContext(
                request_id=request.request_id,
                claim_ref=request.claim_ref,
                gap_id=request.gap_id,
                demand_hash=demand_hash(request.demand),
                candidate_ref=request.candidate_ref,
                vocabulary_ref=request.vocabulary_ref,
                planner_report_ref=request.planner_report_ref,
                requested_use=request.requested_use,
                evaluated_at=at,
            )
            if not self._owners_accept(
                demand=request.demand,
                candidate=candidate.model_dump(mode="json"),
                context=context,
            ):
                return shape, None, None, ("independent_owner_verification_missing_or_refused",)
        except Exception as exc:
            return shape, None, None, ("owner_validation_refused", type(exc).__name__)
        return shape, candidate, context, ()

    def _event(
        self, *, state: str, request: NonDataRequest, at: datetime, artifact_ref: str
    ) -> None:
        with file_lock(self.journal_path.with_suffix(".lock")):
            count = (
                len(self.journal_path.read_text().splitlines()) if self.journal_path.exists() else 0
            )
            ref = append_fsync_jsonl(
                self.journal_path,
                {
                    "sequence": count + 1,
                    "event_kind": "fabric.non_data_acquisition.transition.v1",
                    "request_id": request.request_id,
                    "demand_hash": demand_hash(request.demand),
                    "resolution_state": state,
                    "artifact_ref": artifact_ref,
                    "evaluated_at": at.isoformat(),
                    "authority_granted": False,
                    "institutional_signer": None,
                },
            )
            resolve_journal_event_ref(ref)

    def _result(
        self, request: NonDataRequest, at: datetime, *, emit_intermediate: bool
    ) -> NonDataReceipt:
        shape, candidate, context, reasons = self._admit(request, at)
        if shape.outcome == "not_established":
            state = "shape_not_established"
        elif shape.outcome == "split_required":
            state = "split_required"
        elif candidate is None:
            state = "admission_refused"
        else:
            if emit_intermediate:
                self._event(
                    state="admitted_reentry_required",
                    request=request,
                    at=at,
                    artifact_ref=request.candidate_ref,
                )
            try:
                passed = (
                    self.demanding_owner is not None
                    and context is not None
                    and self.demanding_owner.reenter(
                        demand=request.demand,
                        candidate=candidate.model_dump(mode="json"),
                        context=context,
                    )
                    is True
                )
            except Exception:
                passed = False
            state = "reentry_closed" if passed else "reentry_provisional_refusal"
            if not passed:
                reasons = ("demanding_predicate_still_refused",)
        return NonDataReceipt(
            request=request,
            evaluated_at=at,
            shape=shape,
            resolution_state=state,
            reason_codes=reasons,
            demanding_owner_id=getattr(self.demanding_owner, "owner_id", None),
            verifier_owner_id=getattr(self.independent_verifier, "owner_id", None),
            planner_report_ref=request.planner_report_ref,
        )

    def acquire(
        self, request: NonDataRequest, *, at: datetime, row_count: int = 0
    ) -> NonDataReceipt:
        """Run candidate admission/re-entry; same-stream volume has no resolving role."""
        del row_count
        request = NonDataRequest.model_validate(request.model_dump(mode="json"))
        receipt = self._result(request, at, emit_intermediate=True)
        ref = self._persist(
            receipt.model_dump(mode="json", exclude={"artifact_ref"}), _RECEIPT_KIND
        )
        self._event(state=receipt.resolution_state, request=request, at=at, artifact_ref=ref)
        return self.read_receipt(ref)

    def read_receipt(self, ref: str) -> NonDataReceipt:
        """Read and recompute a historical candidate receipt, never an approval."""
        return self.verify_receipt(ref)

    def verify_receipt(self, ref: str, *, at: datetime | None = None) -> NonDataReceipt:
        """Recompute a persisted decision with the current allocated verifier ports."""
        receipt = NonDataReceipt.model_validate(self._resolve(ref, _RECEIPT_KIND))
        recomputed = self._result(
            receipt.request, at or receipt.evaluated_at, emit_intermediate=False
        )
        if receipt.model_dump(exclude={"artifact_ref", "evaluated_at"}) != recomputed.model_dump(
            exclude={"artifact_ref", "evaluated_at"}
        ):
            raise ValueError("receipt_recomputation_mismatch")
        return receipt.model_copy(update={"artifact_ref": ref})
