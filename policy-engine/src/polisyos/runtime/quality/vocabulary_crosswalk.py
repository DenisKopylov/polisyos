"""Conserve candidate semantics across owner vocabularies without minting authority.

INT-R4 owns movement-source diagnosis; OPS-R5 owns the four constrained response
coordinates. This module registers their shared candidate identities, consumed
by ``constrained_response``. Existing adaptation custody owns lifecycle status.
The reference/checker is documented in ``canonical-vocabulary-crosswalk.md``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from polisyos.runtime.quality.adaptation_transition import KPIControlStateSnapshot

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

MOVEMENT_VOCABULARY_ID = "SMDV-1@1"
TARGET_OWNER = "polisyos.runtime.quality.adaptation_transition.KPIControlStateSnapshot.status"
BLOCKING_DIMENSIONS = (
    "source_identity",
    "namespace_version",
    "source_owner",
    "authority_purpose",
    "provenance",
    "time_scope",
    "blocking_contributor",
    "negative_remedy",
    "permission_or_prohibition",
    "claim_version_scope",
    "partial_order_relation",
    "lifecycle_owner",
    "source_qualifier",
)


class MovementClass(StrEnum):
    """Bounded INT-R4 movement locations, not a universal physical-cause ontology."""

    EXPECTED_VARIATION = "expected_variation"
    OBSERVATION_PROCESS_CHANGE = "observation_process_change"
    INTERVENTION_DELIVERY_OR_VERSION = "intervention_delivery_or_version"
    BEHAVIORAL_RESPONSE = "behavioral_response"
    CONTEXT_OR_INTERFERENCE = "context_or_interference"
    PREDICTION_ERROR = "prediction_error"
    DIAGNOSIS_UNRESOLVED = "diagnosis_unresolved"


class EpistemicFactor(StrEnum):
    """Evidence coordinate; no member is a lifecycle status or an authority grant."""

    E0 = "E0"
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"
    E4 = "E4"


class ExposureFactor(StrEnum):
    """Exposure coordinate, subject to independent execution and restart evidence."""

    X0 = "X0"
    X1 = "X1"
    X2 = "X2"
    X3 = "X3"
    X4 = "X4"


class InterventionFactor(StrEnum):
    """Intervention-version coordinate, separate from intact claim status."""

    V0 = "V0"
    V1 = "V1"
    V2 = "V2"
    V3 = "V3"
    V4 = "V4"


class ClaimFactor(StrEnum):
    """Claim coordinate, preserving independent externally grounded continuation."""

    C0 = "C0"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"


def movement_registry() -> list[dict[str, object]]:
    """Return the complete movement-channel registration, never caller authority."""
    return [
        {
            "vocabulary_id": MOVEMENT_VOCABULARY_ID,
            "semantic_role": "movement_source",
            "owner": f"{__name__}.MovementClass",
            "terms": [item.value for item in MovementClass],
        }
    ]


def validate_movement_registry(registry: Sequence[Mapping[str, object]]) -> None:
    """Refuse any second registration regardless of its name or term overlap.

    Args:
        registry: Complete registration set for the admitted movement channel.

    Raises:
        ValueError: The channel forks or its canonical definition changes.
    """
    if len(registry) != 1:
        raise ValueError("movement_vocabulary_fork")
    item = registry[0]
    if (
        item.get("vocabulary_id") != MOVEMENT_VOCABULARY_ID
        or item.get("semantic_role") != "movement_source"
        or item.get("owner") != f"{__name__}.MovementClass"
    ):
        raise ValueError("movement_vocabulary_identity_drift")
    terms = item.get("terms")
    if not isinstance(terms, (tuple, list)) or sorted(terms) != sorted(
        member.value for member in MovementClass
    ):
        raise ValueError("movement_vocabulary_terms_drift")


def require_canonical_movement(vocabulary_id: str, value: str) -> MovementClass:
    """Admit a source class through the only registered production namespace.

    Args:
        vocabulary_id: Exact versioned source namespace.
        value: Exact member identity, never a translated label or inferred synonym.

    Returns:
        The canonical candidate class, without diagnosis or learning authority.

    Raises:
        ValueError: Registry, namespace or member is not the canonical definition.
    """
    validate_movement_registry(movement_registry())
    if vocabulary_id != MOVEMENT_VOCABULARY_ID:
        raise ValueError("movement_namespace_refused")
    try:
        return MovementClass(value)
    except ValueError as exc:
        raise ValueError("movement_member_refused") from exc


def target_statuses() -> tuple[str, ...]:
    """Derive the whole existing custody status field, rather than copying a list."""
    return get_args(KPIControlStateSnapshot.model_fields["status"].annotation)


class CrosswalkEntry(BaseModel):
    """One scoped source identity carried to an existing owner's status adjunct."""

    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")
    vocabulary_id: str = Field(min_length=1)
    source_term: str = Field(min_length=1)
    source_owner: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    semantic_purpose: Literal["candidate_identity_transport"] = "candidate_identity_transport"
    target_owner: str = Field(min_length=1)


class CrosswalkProjection(CrosswalkEntry):
    """Candidate identity adjunct; the existing producer retains its exact status."""

    target_status: str
    authority_granted: Literal[False] = False
    dropped_display_label: bool


def project_term(
    entry: CrosswalkEntry,
    *,
    current_status: str,
    losses: Sequence[str] = (),
) -> CrosswalkProjection:
    """Preserve a candidate identity or refuse an authority-relevant loss.

    A table row cannot downgrade a blocking dimension: the invariant is enforced
    here independently of the reference's human-readable loss classifications.

    Args:
        entry: Versioned owner-scoped candidate identity, not an authority assertion.
        current_status: Already produced lifecycle value of the declared target owner.
        losses: Every dimension the proposed presentation would discard.

    Returns:
        A source-identity-preserving adjunct with no new status or authority.

    Raises:
        ValueError: A blocking/unknown loss, identity mismatch or unregistered status.
    """
    entry = CrosswalkEntry.model_validate(entry.model_dump())
    if entry.target_owner != TARGET_OWNER:
        raise ValueError("target_owner_refused")
    if current_status not in target_statuses():
        raise ValueError("target_status_unregistered")
    for loss in losses:
        if loss in BLOCKING_DIMENSIONS:
            raise ValueError(f"blocking_loss:{loss}")
        if loss != "display_label":
            raise ValueError(f"unclassified_loss:{loss}")
    if entry.vocabulary_id == MOVEMENT_VOCABULARY_ID:
        require_canonical_movement(entry.vocabulary_id, entry.source_term)
    if entry.vocabulary_id == "int-r5.reason@0.1.0-candidate" and (
        not entry.source_term.startswith("polisyos.int_r5.reason.")
        or not entry.source_term.endswith("@0.1.0-candidate")
    ):
        raise ValueError("reason_namespace_or_version_lost")
    return CrosswalkProjection(
        **entry.model_dump(),
        target_status=current_status,
        dropped_display_label="display_label" in losses,
    )
