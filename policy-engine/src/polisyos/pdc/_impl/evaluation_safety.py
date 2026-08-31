"""Neutral EvalSafety vocabulary and consumer-side verification contracts.

Runtime remains the authority that constructs decisions, certificates, revisions, and
consumer admission receipts. This module owns only the vocabulary shared with consumers
and the pure proof that a receipt came from that Runtime-owned minting path.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime  # noqa: TC003 - Pydantic resolves runtime annotations.
from typing import Annotated, Literal, Protocol
from uuid import uuid4

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    StringConstraints,
    model_validator,
)
from pydantic_core import to_jsonable_python

from polisyos.core import components as core_components  # noqa: TC001

from .gy_waist import ArtifactRef  # noqa: TC001

Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
NamespacedEvalSafetyId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_.-]+@[0-9]+\.[0-9]+\.[0-9]+$"),
]
PredicateProvenance = Literal[
    "recomputed",
    "independently_reconciled",
    "consumer_asserted",
    "institutionally_supplied",
    "not_established",
]
EvaluationMode = Literal[
    "simulate_only",
    "retrospective",
    "measurement_audit",
    "sandbox_pilot",
    "field_pilot",
    "deployment",
]
NamespacedEvaluationModeBlocker = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_.-]+@[0-9]+\.[0-9]+\.[0-9]+$"),
]

_RECEIPT_PRODUCER_TOKEN = object()
_RUNTIME_RECEIPT_TYPE: type[EvalSafetyConsumerAdmissionReceipt] | None = None


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


def _content_hash(
    value: BaseModel | dict[str, object],
    *,
    exclude: set[str] | None = None,
) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude=exclude or set())
    else:
        payload = to_jsonable_python(value)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class EvaluationModeResolution(BaseModel):
    """Typed result of parsing one untrusted evaluation-mode token."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["accepted", "missing", "invalid"]
    canonical_mode: EvaluationMode | None
    blocker_code: NamespacedEvaluationModeBlocker | None
    source_token_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class EvaluationInputProvenance(_FrozenModel):
    """Owner-bound classification of one input as simulated or real-world."""

    input_ref: ArtifactRef
    input_class: Literal["simulation", "real_world", "not_established"]
    predicate_provenance: PredicateProvenance


def _artifact_identity(ref: ArtifactRef) -> tuple[str, str]:
    return (ref.artifact_id, ref.content_hash)


def recompute_attempt_class(
    input_refs: tuple[ArtifactRef, ...],
    provenances: tuple[EvaluationInputProvenance, ...],
) -> Literal["simulation", "non_simulation", "not_established"]:
    """Recompute action class from an exact, independently grounded input set."""

    by_ref = {_artifact_identity(row.input_ref): row for row in provenances}
    if len(by_ref) != len(provenances) or set(by_ref) != {
        _artifact_identity(ref) for ref in input_refs
    }:
        return "not_established"
    if not provenances:
        return "not_established"
    if any(
        row.predicate_provenance not in {"recomputed", "independently_reconciled"}
        or row.input_class == "not_established"
        for row in provenances
    ):
        return "not_established"
    if any(row.input_class == "real_world" for row in provenances):
        return "non_simulation"
    return "simulation"


class EvaluationExecutionContext(_FrozenModel):
    """Reference-only context checked immediately before evaluator work."""

    intake_ref: ArtifactRef
    evaluator_owner_id: core_components.ComponentId
    design_problem_ref: Digest
    evaluation_mode: EvaluationMode
    candidate_ref: ArtifactRef
    world_model_record_ref: ArtifactRef
    target_population_scope_ref: ArtifactRef
    rule_version: str = Field(min_length=1)
    intended_start_at: datetime
    evaluation_input_refs: tuple[ArtifactRef, ...]
    evaluation_input_provenance: tuple[EvaluationInputProvenance, ...]
    eval_safety_certificate_ref: ArtifactRef | None
    eval_safety_revision_head_ref: ArtifactRef | None

    @property
    def attempt_class(self) -> Literal["simulation", "non_simulation", "not_established"]:
        """Recompute action class from the complete bound input provenance."""

        return recompute_attempt_class(
            self.evaluation_input_refs,
            self.evaluation_input_provenance,
        )

    @property
    def mode_resolution(self) -> EvaluationModeResolution:
        """Project the already-canonical Runtime context mode as an accepted result."""

        digest = "sha256:" + hashlib.sha256(self.evaluation_mode.encode("utf-8")).hexdigest()
        return EvaluationModeResolution(
            status="accepted",
            canonical_mode=self.evaluation_mode,
            blocker_code=None,
            source_token_hash=digest,
        )


def evaluation_execution_context_hash(context: EvaluationExecutionContext) -> Digest:
    """Return the canonical hash of every serialized execution-context field."""

    return _content_hash(context)


class EvalSafetyAdmissionChallenge(_FrozenModel):
    """Unrepeatable consumer-generated subject for one admission call."""

    consumer_component_id: core_components.ComponentId
    nonce: UUID4

    @classmethod
    def fresh(
        cls,
        *,
        consumer_component_id: core_components.ComponentId,
    ) -> EvalSafetyAdmissionChallenge:
        """Create a fresh challenge immediately before consumer verification."""

        return cls(consumer_component_id=consumer_component_id, nonce=uuid4())


class EvalSafetyConsumerAdmissionReceipt(_FrozenModel):
    """Immediate consumer-side revalidation result."""

    status: Literal["verified", "blocked"]
    intake_ref: ArtifactRef
    certificate_ref: ArtifactRef | None
    current_revision_head_ref: ArtifactRef | None
    execution_context_hash: Digest
    challenge: EvalSafetyAdmissionChallenge
    blocker_codes: tuple[NamespacedEvalSafetyId, ...]
    verified_at: datetime
    _producer_token: object | None = PrivateAttr(default=None)
    _producer_fingerprint: str | None = PrivateAttr(default=None)

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Register only Runtime's exact private minting subtype."""

        super().__init_subclass__(**kwargs)
        expected = (
            "polisyos.runtime.quality.evaluation_safety",
            "_ProducedEvalSafetyConsumerAdmissionReceipt",
        )
        if (cls.__module__, cls.__name__) != expected:
            raise TypeError("eval_safety_receipt_subclass_forbidden")
        global _RUNTIME_RECEIPT_TYPE
        if _RUNTIME_RECEIPT_TYPE is not None and _RUNTIME_RECEIPT_TYPE is not cls:
            raise TypeError("eval_safety_receipt_producer_already_registered")
        _RUNTIME_RECEIPT_TYPE = cls

    def model_post_init(self, __context: object) -> None:
        """Seal only a verified receipt instantiated as Runtime's registered subtype."""

        del __context
        if type(self) is _RUNTIME_RECEIPT_TYPE and self.status == "verified":
            self._producer_token = _RECEIPT_PRODUCER_TOKEN
            self._producer_fingerprint = _content_hash(self)

    @model_validator(mode="after")
    def _verify_admission_shape(self) -> EvalSafetyConsumerAdmissionReceipt:
        verified_shape = (
            self.certificate_ref is not None
            and self.current_revision_head_ref is not None
            and self.challenge.consumer_component_id
            and self.execution_context_hash
            and not self.blocker_codes
        )
        if (self.status == "verified") is not verified_shape:
            raise ValueError("eval_safety_consumer_admission_incoherent")
        return self


class EvalSafetyVerifierPort(Protocol):
    """Verification-only port; it cannot execute or schedule evaluations."""

    def require_admission(
        self,
        context: EvaluationExecutionContext,
        challenge: EvalSafetyAdmissionChallenge,
    ) -> EvalSafetyConsumerAdmissionReceipt:
        """Re-resolve and verify admission immediately before work."""


def evaluation_safety_consumer_admission_is_verified(
    receipt: EvalSafetyConsumerAdmissionReceipt,
    context: EvaluationExecutionContext,
    challenge: EvalSafetyAdmissionChallenge,
) -> bool:
    """Return whether Runtime minted a receipt for this exact context and challenge."""

    return bool(
        _RUNTIME_RECEIPT_TYPE is not None
        and type(receipt) is _RUNTIME_RECEIPT_TYPE
        and receipt._producer_token is _RECEIPT_PRODUCER_TOKEN
        and receipt._producer_fingerprint == _content_hash(receipt)
        and receipt.status == "verified"
        and not receipt.blocker_codes
        and receipt.execution_context_hash == evaluation_execution_context_hash(context)
        and receipt.challenge == challenge
        and challenge.consumer_component_id == context.evaluator_owner_id
        and receipt.intake_ref == context.intake_ref
        and receipt.certificate_ref is not None
        and receipt.certificate_ref == context.eval_safety_certificate_ref
        and receipt.current_revision_head_ref is not None
        and receipt.current_revision_head_ref == context.eval_safety_revision_head_ref
    )


__all__ = [
    "Digest",
    "EvalSafetyAdmissionChallenge",
    "EvalSafetyConsumerAdmissionReceipt",
    "EvalSafetyVerifierPort",
    "EvaluationExecutionContext",
    "EvaluationInputProvenance",
    "EvaluationMode",
    "EvaluationModeResolution",
    "NamespacedEvalSafetyId",
    "PredicateProvenance",
    "evaluation_execution_context_hash",
    "evaluation_safety_consumer_admission_is_verified",
    "recompute_attempt_class",
]
