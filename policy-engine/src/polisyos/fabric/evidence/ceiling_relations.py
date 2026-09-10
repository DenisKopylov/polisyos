"""Candidate non-data ceiling algebra on the existing Fabric evidence plane.

This module owns comparison of registered, versioned definitions. It does not
establish their institutional standing: even a passing comparison cannot sign,
approve, or publish anything. Domain owners supply content; the independent
admission verifier in ``non_data_acquisition`` remains a separate port.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class CeilingDimension(StrEnum):
    """The commissioned INT-R2 AUD-F007 field denominator, not a universal set."""

    POPULATION = "population"
    JURISDICTION = "jurisdiction"
    PURPOSE_AUDIENCE = "purpose_audience"
    SOURCE_TARGET_CONTEXT = "source_target_context"
    EVIDENCE_CLASS = "evidence_class"
    MAINTAINED_ASSUMPTIONS = "maintained_assumptions"
    MAXIMUM_CLAIM_STRENGTH = "maximum_claim_strength"
    MAXIMUM_COMMITMENT_STAGE = "maximum_commitment_stage"


class PartialOrder(_StrictModel):
    """Finite registered order whose edges run from narrower to broader."""

    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        """Reject unknown edges, duplicate definitions and cycles."""
        if len(set(self.nodes)) != len(self.nodes) or any(not node for node in self.nodes):
            raise ValueError("order_nodes_invalid")
        if len(set(self.edges)) != len(self.edges):
            raise ValueError("order_edges_duplicate")
        for left, right in self.edges:
            if left not in self.nodes or right not in self.nodes:
                raise ValueError("order_edge_unknown_node")
            if left == right or self._reachable(right, left):
                raise ValueError("order_cycle")
        return self

    def _reachable(self, left: str, right: str) -> bool:
        pending = [left]
        seen = set()
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            if node == right:
                return True
            pending.extend(target for source, target in self.edges if source == node)
        return False

    def contains(self, requested: str, ceiling: str) -> bool:
        """Return known-node reflexive/transitive containment only."""
        return (
            requested in self.nodes
            and ceiling in self.nodes
            and self._reachable(requested, ceiling)
        )


class CurrentInterval(_StrictModel):
    """Explicit currentness window; missing or reversed bounds cannot default."""

    valid_from: AwareDatetime
    valid_until: AwareDatetime

    @model_validator(mode="after")
    def ordered(self) -> Self:
        """Reject empty or reversed currentness windows."""
        if self.valid_from >= self.valid_until:
            raise ValueError("interval_invalid")
        return self

    def current(self, at: datetime) -> bool:
        """Use a half-open interval, so expiry is never current."""
        return self.valid_from <= at < self.valid_until


class JurisdictionOrder(PartialOrder):
    """Subordination defined only for explicitly registered competence acts."""

    action_refs: tuple[str, ...] = Field(min_length=1)


class TransportWitness(CurrentInterval):
    """One exact source-to-target compatibility definition with currentness."""

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)


class CeilingVocabulary(_StrictModel):
    """Resolved candidate definitions consumed by all eight field relations."""

    version: str = Field(min_length=1)
    exact_identities: dict[str, tuple[str, ...]]
    population_members: dict[str, tuple[str, ...]]
    jurisdiction_order: JurisdictionOrder
    purpose_order: PartialOrder
    audience_order: PartialOrder
    transport: tuple[TransportWitness, ...]
    evidence_claims: dict[str, tuple[str, ...]]
    assumptions: dict[str, CurrentInterval]
    strength_order: PartialOrder
    stage_order: PartialOrder

    @model_validator(mode="after")
    def validate_definitions(self) -> Self:
        """Reject empty identities and conflicting compatibility definitions."""
        if set(self.exact_identities) != exact_identity_fields():
            raise ValueError("exact_identity_denominator_incomplete")
        if any(
            any(not value for value in values) or len(set(values)) != len(values)
            for values in self.exact_identities.values()
        ):
            raise ValueError("exact_identity_definition_invalid")
        for mapping in (self.population_members, self.evidence_claims):
            if any(
                not key
                or not value
                or any(not item for item in value)
                or len(value) != len(set(value))
                for key, value in mapping.items()
            ):
                raise ValueError("vocabulary_definition_invalid")
        if any(not key for key in self.assumptions):
            raise ValueError("assumption_identity_missing")
        pairs = [(row.source, row.target) for row in self.transport]
        if len(pairs) != len(set(pairs)):
            raise ValueError("transport_definition_ambiguous")
        return self


class CeilingScope(CurrentInterval):
    """Fully explicit use or ceiling, with no permissive unknown defaults."""

    claim_kind: str = Field(min_length=1)
    action_ref: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    object_ref: str = Field(min_length=1)
    review_at: AwareDatetime
    operation: str = Field(min_length=1)
    permitted_operations: tuple[str, ...]
    prohibited_uses: tuple[str, ...]
    use: str = Field(min_length=1)
    population_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    purpose_ref: str = Field(min_length=1)
    audience_ref: str = Field(min_length=1)
    source_context_ref: str = Field(min_length=1)
    target_context_ref: str = Field(min_length=1)
    evidence_class_ref: str = Field(min_length=1)
    assumption_refs: tuple[str, ...]
    claim_strength_ref: str = Field(min_length=1)
    commitment_stage_ref: str = Field(min_length=1)
    load: float = Field(ge=0, allow_inf_nan=False)
    rule_version_ref: str = Field(min_length=1)
    reference_epoch_ref: str = Field(min_length=1)
    downstream_gate_refs: tuple[str, ...] = Field(min_length=1)


class CeilingResult(_StrictModel):
    """Recomputed comparison result, explicitly without institutional authority."""

    permitted: bool
    relations: dict[str, bool]
    exact_controls: bool
    authority_granted: Literal[False] = False
    institutional_signer: None = None


def exact_identity_fields() -> set[str]:
    """Derive every remaining token field from the actual scope schema.

    An added field cannot silently escape checking: absent registered identities
    make vocabulary admission fail before any candidate comparison can pass.
    """
    relational = {
        "population_ref",
        "jurisdiction_ref",
        "purpose_ref",
        "audience_ref",
        "source_context_ref",
        "target_context_ref",
        "evidence_class_ref",
        "assumption_refs",
        "claim_strength_ref",
        "commitment_stage_ref",
    }
    temporal_or_numeric = {"valid_from", "valid_until", "review_at", "load"}
    return set(CeilingScope.model_fields) - relational - temporal_or_numeric


def registered_ceiling_relations() -> dict[str, dict[str, str]]:
    """Read the complete commissioned registry and reconcile it to live algebras."""
    payload = json.loads(Path(__file__).with_name("ceiling_vocabulary.json").read_text())
    relations = payload["relations"]
    if set(relations) != {member.value for member in CeilingDimension}:
        raise ValueError("ceiling_relation_registry_incomplete")
    if any(value.get("owner") != __name__ for value in relations.values()):
        raise ValueError("ceiling_relation_owner_mismatch")
    return relations


def evaluate_ceiling(
    *,
    vocabulary: CeilingVocabulary,
    requested: CeilingScope,
    ceiling: CeilingScope,
    at: datetime,
) -> CeilingResult:
    """Recompute every relation; unknowns and conflicting exact controls refuse."""
    vocabulary = CeilingVocabulary.model_validate(vocabulary.model_dump(mode="json"))
    requested = CeilingScope.model_validate(requested.model_dump(mode="json"))
    ceiling = CeilingScope.model_validate(ceiling.model_dump(mode="json"))
    registered_ceiling_relations()
    populations = vocabulary.population_members
    assumptions = vocabulary.assumptions
    relations = {
        "population": requested.population_ref in populations
        and ceiling.population_ref in populations
        and set(populations[requested.population_ref]) <= set(populations[ceiling.population_ref]),
        "jurisdiction": requested.action_ref in vocabulary.jurisdiction_order.action_refs
        and vocabulary.jurisdiction_order.contains(
            requested.jurisdiction_ref, ceiling.jurisdiction_ref
        ),
        "purpose_audience": vocabulary.purpose_order.contains(
            requested.purpose_ref, ceiling.purpose_ref
        )
        and vocabulary.audience_order.contains(requested.audience_ref, ceiling.audience_ref),
        "source_target_context": requested.source_context_ref == ceiling.source_context_ref
        and requested.target_context_ref == ceiling.target_context_ref
        and any(
            row.source == requested.source_context_ref
            and row.target == requested.target_context_ref
            and row.current(at)
            for row in vocabulary.transport
        ),
        "evidence_class": requested.evidence_class_ref == ceiling.evidence_class_ref
        and requested.claim_kind in vocabulary.evidence_claims.get(ceiling.evidence_class_ref, ()),
        "maintained_assumptions": bool(ceiling.assumption_refs)
        and set(requested.assumption_refs) == set(ceiling.assumption_refs)
        and all(
            ref in assumptions and assumptions[ref].current(at) for ref in ceiling.assumption_refs
        ),
        "maximum_claim_strength": vocabulary.strength_order.contains(
            requested.claim_strength_ref, ceiling.claim_strength_ref
        ),
        "maximum_commitment_stage": vocabulary.stage_order.contains(
            requested.commitment_stage_ref, ceiling.commitment_stage_ref
        )
        and requested.load <= ceiling.load,
    }
    exact = True
    for field in exact_identity_fields():
        allowed = vocabulary.exact_identities[field]
        for scope in (requested, ceiling):
            values = getattr(scope, field)
            values = (values,) if isinstance(values, str) else values
            exact = exact and all(value in allowed for value in values)
        if isinstance(getattr(requested, field), str) and field not in {"operation", "use"}:
            exact = exact and getattr(requested, field) == getattr(ceiling, field)
    exact = exact and requested.current(at) and ceiling.current(at)
    exact = exact and ceiling.valid_from <= requested.valid_from
    exact = exact and requested.valid_until <= ceiling.valid_until
    exact = exact and at < min(requested.review_at, ceiling.review_at)
    exact = exact and requested.operation in ceiling.permitted_operations
    exact = exact and set(requested.permitted_operations) <= set(ceiling.permitted_operations)
    exact = exact and requested.use not in set(ceiling.prohibited_uses) | set(
        requested.prohibited_uses
    )
    exact = exact and set(ceiling.downstream_gate_refs) <= set(requested.downstream_gate_refs)
    return CeilingResult(
        permitted=exact and all(relations.values()), relations=relations, exact_controls=exact
    )
