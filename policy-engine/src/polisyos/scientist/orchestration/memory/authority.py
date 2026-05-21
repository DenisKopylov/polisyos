"""Runtime authority records for memory influence in serious runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

MemoryAuthorityKind = Literal["no_memory_abstention", "memory_use_authority"]


class MemoryAuthorityContaminationCheck(BaseModel):
    """One contamination check that gates memory influence."""

    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1)
    status: Literal["pass", "blocked"]
    contamination_detected: bool
    evidence_ref: str = Field(min_length=1)
    observed_scope: dict[str, Any] | str | None = None

    @model_validator(mode="after")
    def _status_matches_detection(self) -> MemoryAuthorityContaminationCheck:
        if self.status == "pass" and self.contamination_detected:
            raise ValueError("passing contamination check cannot report contamination")
        if self.status == "blocked" and not self.contamination_detected:
            raise ValueError("blocked contamination check must report contamination")
        return self


class MemoryAuthorityRecord(BaseModel):
    """Runtime-owned decision emitted before memory can influence serious output."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.scientist.memory_authority_record.v1"] = (
        "policyos.scientist.memory_authority_record.v1"
    )
    record_id: str = Field(default_factory=lambda: f"memory-authority-{uuid4().hex}")
    run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    authority_kind: MemoryAuthorityKind
    runtime_owned: bool = True
    memory_used: bool
    replay_surface_empty: bool
    selected_memory_refs: list[str] = Field(default_factory=list)
    retrieval_event_refs: list[str] = Field(default_factory=list)
    applicability_refs: list[str] = Field(default_factory=list)
    prompt_authority_refs: dict[str, str] = Field(min_length=1)
    tool_authority_refs: dict[str, str] = Field(min_length=1)
    contamination_checks: list[MemoryAuthorityContaminationCheck] = Field(min_length=1)
    emission_order: int = Field(ge=0)
    serious_output_influence_order: int = Field(ge=0)
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    no_memory_reason: str | None = None
    empty_replay_surface_accepted_without_runtime_record: bool = False
    reviewer_note: str | None = None

    @model_validator(mode="after")
    def _validate_authority_kind(self) -> MemoryAuthorityRecord:
        if self.authority_kind == "no_memory_abstention":
            if self.memory_used:
                raise ValueError("no_memory_abstention cannot mark memory_used")
            if self.selected_memory_refs or self.retrieval_event_refs or self.applicability_refs:
                raise ValueError("no_memory_abstention cannot carry memory refs")
            if not self.no_memory_reason:
                raise ValueError("no_memory_abstention requires no_memory_reason")
            if self.empty_replay_surface_accepted_without_runtime_record:
                raise ValueError(
                    "empty replay surface cannot be accepted without runtime record"
                )
        if self.authority_kind == "memory_use_authority":
            if not self.memory_used:
                raise ValueError("memory_use_authority requires memory_used")
            if not self.selected_memory_refs:
                raise ValueError("memory_use_authority requires selected memory refs")
            if not self.retrieval_event_refs:
                raise ValueError("memory_use_authority requires retrieval event refs")
            if not self.applicability_refs:
                raise ValueError("memory_use_authority requires applicability refs")
            if self.replay_surface_empty:
                raise ValueError("memory_use_authority cannot have empty replay surface")
        return self

    def tenant_scope(self) -> dict[str, str]:
        """Return the tenant/cell scope in the artifact shape used by Wave 35G."""

        return {"tenant_id": self.tenant_id, "cell_id": self.cell_id}

    def to_trace_dict(self) -> dict[str, Any]:
        """Serialize the record with derived trace fields for closeout artifacts."""

        payload = self.model_dump(mode="json")
        payload["tenant_scope"] = self.tenant_scope()
        payload["emitted_before_serious_output_influence"] = (
            self.emission_order < self.serious_output_influence_order
        )
        return payload


def build_no_memory_abstention_record(
    *,
    run_id: str,
    tenant_id: str,
    cell_id: str,
    replay_surface_empty: bool,
    prompt_authority_refs: Mapping[str, str],
    tool_authority_refs: Mapping[str, str],
    contamination_checks: Sequence[Mapping[str, Any]],
    emission_order: int,
    serious_output_influence_order: int,
    no_memory_reason: str | None = None,
) -> MemoryAuthorityRecord:
    """Build the explicit runtime abstention required before serious output."""

    return MemoryAuthorityRecord(
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        authority_kind="no_memory_abstention",
        memory_used=False,
        replay_surface_empty=replay_surface_empty,
        prompt_authority_refs=dict(prompt_authority_refs),
        tool_authority_refs=dict(tool_authority_refs),
        contamination_checks=[
            MemoryAuthorityContaminationCheck.model_validate(row)
            for row in contamination_checks
        ],
        emission_order=emission_order,
        serious_output_influence_order=serious_output_influence_order,
        no_memory_reason=no_memory_reason
        or (
            "No runtime memory candidate was selected for the serious run; "
            "empty replay surfaces do not count without this runtime abstention record."
        ),
    )


def build_memory_use_authority_record(
    *,
    run_id: str,
    tenant_id: str,
    cell_id: str,
    selected_memory_refs: Sequence[str],
    retrieval_event_refs: Sequence[str],
    applicability_refs: Sequence[str],
    prompt_authority_refs: Mapping[str, str],
    tool_authority_refs: Mapping[str, str],
    contamination_checks: Sequence[Mapping[str, Any]],
    emission_order: int,
    serious_output_influence_order: int,
) -> MemoryAuthorityRecord:
    """Build a memory-use authority handoff emitted before output influence."""

    return MemoryAuthorityRecord(
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        authority_kind="memory_use_authority",
        memory_used=True,
        replay_surface_empty=False,
        selected_memory_refs=list(selected_memory_refs),
        retrieval_event_refs=list(retrieval_event_refs),
        applicability_refs=list(applicability_refs),
        prompt_authority_refs=dict(prompt_authority_refs),
        tool_authority_refs=dict(tool_authority_refs),
        contamination_checks=[
            MemoryAuthorityContaminationCheck.model_validate(row)
            for row in contamination_checks
        ],
        emission_order=emission_order,
        serious_output_influence_order=serious_output_influence_order,
    )


def assert_memory_authority_for_serious_output(
    record: MemoryAuthorityRecord | None,
    *,
    replay_surface_empty: bool,
) -> MemoryAuthorityRecord:
    """Require explicit runtime memory authority before serious output influence."""

    if record is None:
        if replay_surface_empty:
            raise ValueError("empty replay surface is not memory abstention")
        raise ValueError("missing runtime memory authority record")
    if not record.runtime_owned:
        raise ValueError("memory authority record must be runtime owned")
    if record.emission_order >= record.serious_output_influence_order:
        raise ValueError("memory authority record must be emitted before serious output influence")
    blocked = [
        check.check_id
        for check in record.contamination_checks
        if check.status != "pass" or check.contamination_detected
    ]
    if blocked:
        raise ValueError(f"memory contamination checks block authority: {', '.join(blocked)}")
    if record.authority_kind == "no_memory_abstention" and not record.replay_surface_empty:
        raise ValueError("no_memory_abstention requires an empty replay memory surface")
    if record.authority_kind == "memory_use_authority" and replay_surface_empty:
        raise ValueError("memory_use_authority requires a non-empty replay memory surface")
    return record


__all__ = [
    "MemoryAuthorityContaminationCheck",
    "MemoryAuthorityKind",
    "MemoryAuthorityRecord",
    "assert_memory_authority_for_serious_output",
    "build_memory_use_authority_record",
    "build_no_memory_abstention_record",
]
