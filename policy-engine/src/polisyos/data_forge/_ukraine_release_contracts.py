"""Neutral typed contracts for candidate Ukraine release handoffs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _ArtifactRecordContentSource(Protocol):
    """Structural metadata required to project a release record into a handoff."""

    path: str
    sha256: str
    size_bytes: int


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class D5ReleaseContentRef(BaseModel):
    """Content declaration embedded in the non-authoritative D5 handoff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)

    @classmethod
    def from_artifact_record(cls, record: _ArtifactRecordContentSource) -> D5ReleaseContentRef:
        """Project release record metadata into the narrow handoff contract."""

        return cls(path=record.path, sha256=record.sha256, size_bytes=record.size_bytes)


class D5ReleaseProducerFacts(BaseModel):
    """Candidate facts supplied by the D5 producer for downstream evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_region_id: str = Field(min_length=1, max_length=120)
    primary_sector_id: str = Field(min_length=1, max_length=120)
    graph_compression_degree_preservation_score: float = Field(ge=0.0, le=1.0)
    graph_compression_edge_weight_reconstruction_error: float = Field(ge=0.0)


class D5ReleaseHandoffRequest(BaseModel):
    """Purpose-limited candidate request from DataForge to the D5 consumer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_forge.ukraine.d5_release_handoff_request.v1"] = (
        "policyos.data_forge.ukraine.d5_release_handoff_request.v1"
    )
    handoff_rule_version: Literal["ukraine-d5-release-handoff.v1"] = "ukraine-d5-release-handoff.v1"
    authority_purpose: Literal["producer_release_handoff_request"] = (
        "producer_release_handoff_request"
    )
    provenance_ref: Literal[
        "polisyos.data_forge.domains.ukraine.builders.release.build_d5_stage"
    ] = "polisyos.data_forge.domains.ukraine.builders.release.build_d5_stage"
    declared_stage: Literal["d5"] = "d5"
    declared_release_root: str = Field(min_length=1)
    created_at: str = Field(default_factory=_utc_now_iso, min_length=1)
    time_role: Literal["producer_handoff_created_at"] = "producer_handoff_created_at"
    capability_state: Literal["bridge_missing"] = "bridge_missing"
    consumer_state: Literal["consumer_missing"] = "consumer_missing"
    authoritative_for: tuple[str, ...] = ()
    may_not_use_for: tuple[str, ...] = (
        "legal_intervention_compilation",
        "governance_admissibility",
        "release_acceptance",
        "publication",
    )
    producer_facts: D5ReleaseProducerFacts
    content_refs: dict[str, D5ReleaseContentRef]

    @model_validator(mode="after")
    def _enforce_candidate_boundary(self) -> D5ReleaseHandoffRequest:
        required_refs = {
            "cell_registry",
            "d4_governance_request",
            "graph_compression_bundle",
        }
        if set(self.content_refs) != required_refs:
            raise ValueError("D5 handoff content_refs must match the exact release evidence set")
        if self.authoritative_for:
            raise ValueError("D5 producer handoff cannot declare downstream authority")
        required_denials = {
            "legal_intervention_compilation",
            "governance_admissibility",
            "release_acceptance",
            "publication",
        }
        if set(self.may_not_use_for) != required_denials:
            raise ValueError("D5 producer handoff must retain every authority denial")
        return self
