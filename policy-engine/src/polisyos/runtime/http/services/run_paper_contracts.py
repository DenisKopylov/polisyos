"""Strict replayable contracts for the run paper projection."""

from __future__ import annotations

from collections import Counter
from datetime import datetime  # noqa: TC003 - Pydantic resolves public DTO fields
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.core import artifacts  # noqa: TC001 - Pydantic resolves DTOs
from polisyos.pdc import (
    DesignRecordV0,
    RunBoundDesignRecordBinding,
)
from polisyos.runtime.http.services.export_replay import (
    build_export_replay_address,
    hash_export_projection,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

RUN_PAPER_PACKET_SCHEMA_VERSION = "policyos.runtime.run_paper_packet.v1"
RUN_PAPER_PROJECTION_RULE_VERSION = "policyos.runtime.run_paper.v1"
RUN_PAPER_MANIFEST_SCHEMA_VERSION = "0.1.0"
RUN_PAPER_CASE_GAP = "case-record-not-run-bound"

_CASE_DENIED_USES = (
    "case_identity",
    "design_record",
    "grounding_state",
    "admission_state",
    "promotion_state",
    "blockers",
    "limitations",
    "objections",
    "abstentions",
)
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_VERSION_PIN_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"

RunPaperGroundingStatus = Literal[
    "current_valid",
    "grounded_shadow",
    "grounding_gap",
    "grounding_failed",
    "grounding_unavailable",
]
RunPaperAdmissionStatus = Literal[
    "candidate_unverified",
    "rejected_speculation",
    "typed_blocker",
    "limitation",
    "admitted_to_obligation",
    "admitted_to_claim",
]
RunPaperPromotionStatus = Literal["governed_promoted", "promotion_blocked"]
RunPaperCaseIssueStatus = Literal["open", "resolved", "escalated", "accepted_as_limit"]
RunPaperCaseSourcePurpose = Literal[
    "grounding_state",
    "admission_state",
    "promotion_state",
    "blocker",
    "limitation",
    "objection",
    "abstention",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RunPaperReplayQuery(_StrictModel):
    """Optional HTTP replay tuple parsed from the complete raw query multiset."""

    manifest_artifact_id: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    manifest_schema_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=_VERSION_PIN_PATTERN,
    )
    paper_projection_rule_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=_VERSION_PIN_PATTERN,
    )
    paper_projection_hash: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @classmethod
    def from_query_items(cls, items: Iterable[tuple[str, str]]) -> RunPaperReplayQuery:
        """Parse one exact query multiset without FastAPI scalar-key collapse."""

        entries = tuple((str(key), str(value)) for key, value in items)
        if not entries:
            return cls()
        counts = Counter(key for key, _value in entries)
        known = set(cls.model_fields)
        unknown = sorted(set(counts) - known)
        duplicated = sorted(key for key, count in counts.items() if count != 1)
        if unknown or duplicated:
            details: list[str] = []
            if unknown:
                details.append("unknown keys: " + ", ".join(unknown))
            if duplicated:
                details.append("duplicate keys: " + ", ".join(duplicated))
            raise RunPaperReplaySyntaxError("; ".join(details))
        try:
            return cls.model_validate(dict(entries))
        except ValidationError as exc:
            raise RunPaperReplaySyntaxError("run paper replay pin syntax is invalid") from exc


class RunPaperReplayPins(_StrictModel):
    """Complete immutable identity for one run-paper projection."""

    manifest_artifact_id: str
    manifest_schema_version: Literal["0.1.0"] = RUN_PAPER_MANIFEST_SCHEMA_VERSION
    paper_projection_rule_version: Literal["policyos.runtime.run_paper.v1"] = (
        RUN_PAPER_PROJECTION_RULE_VERSION
    )
    paper_projection_hash: str = Field(pattern=_SHA256_PATTERN)


RunPaperDesignRecordBinding = RunBoundDesignRecordBinding


class RunPaperCaseSourceVerification(_StrictModel):
    """Verifier-written binding between authority bytes and one case/run identity."""

    status: Literal["passed"] = "passed"
    validator_id: str = Field(min_length=1)
    validator_version: str = Field(min_length=1)
    bound_artifact_content_hash: str = Field(pattern=_SHA256_PATTERN)
    bound_case_id: str = Field(min_length=1)
    bound_run_id: str = Field(min_length=1)
    bound_tenant_id: str = Field(min_length=1)
    bound_cell_id: str | None
    bound_design_record_record_id: str = Field(min_length=1)


class RunPaperVerifiedCaseSource(_StrictModel):
    """Content-bound, verifier-proven source for one case authority role."""

    authority_purpose: RunPaperCaseSourcePurpose
    source_ref: artifacts.ArtifactRef
    source_digest: str = Field(pattern=_SHA256_PATTERN)
    source_schema_name: str = Field(min_length=1)
    source_schema_version: str = Field(min_length=1)
    producer: artifacts.ProducerInfo
    verification: RunPaperCaseSourceVerification
    as_of: datetime | None = None

    @model_validator(mode="after")
    def _bind_verified_source(self) -> RunPaperVerifiedCaseSource:
        artifact_id = str(self.source_ref.artifact_id)
        if self.source_digest != artifact_id:
            raise ValueError("case source_digest must equal source_ref.artifact_id")
        if self.verification.bound_artifact_content_hash != artifact_id:
            raise ValueError("case source verifier must bind the source artifact bytes")
        return self


class _RunPaperAuthorityState(_StrictModel):
    """One verified producer authority record frozen into the paper ABI."""

    source_binding: RunPaperVerifiedCaseSource


class RunPaperGroundingState(_RunPaperAuthorityState):
    """Grounding state using the generation-cycle owner's closed vocabulary."""

    vocabulary_ref: Literal["polisyos.runtime.quality.generation_cycle.GroundingStatus"] = (
        "polisyos.runtime.quality.generation_cycle.GroundingStatus"
    )
    state: RunPaperGroundingStatus


class RunPaperAdmissionState(_RunPaperAuthorityState):
    """Admission state using the hypothesis-ledger owner's closed vocabulary."""

    vocabulary_ref: Literal[
        "polisyos.runtime.quality.hypothesis_ledger.HypothesisAdmissionState"
    ] = "polisyos.runtime.quality.hypothesis_ledger.HypothesisAdmissionState"
    state: RunPaperAdmissionStatus


class RunPaperPromotionState(_RunPaperAuthorityState):
    """Promotion state using the governed G4 promotion owner's vocabulary."""

    vocabulary_ref: Literal[
        "polisyos.runtime.quality.proving_ground.governed_promotion_gate."
        "Layer3G4PromotionRecord.promotion_state"
    ] = (
        "polisyos.runtime.quality.proving_ground.governed_promotion_gate."
        "Layer3G4PromotionRecord.promotion_state"
    )
    state: RunPaperPromotionStatus


class _RunPaperCaseIssue(_StrictModel):
    issue_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    status_vocabulary_ref: Literal["polisyos.pdc.ObligationRecord.status"] = (
        "polisyos.pdc.ObligationRecord.status"
    )
    status: RunPaperCaseIssueStatus
    statement: str = Field(min_length=1)
    owner_route: str = Field(min_length=1)
    source_bindings: tuple[RunPaperVerifiedCaseSource, ...] = Field(min_length=1)


class RunPaperBlocker(_RunPaperCaseIssue):
    kind: Literal["blocker"] = "blocker"


class RunPaperLimitation(_RunPaperCaseIssue):
    kind: Literal["limitation"] = "limitation"


class RunPaperObjection(_RunPaperCaseIssue):
    kind: Literal["objection"] = "objection"


class RunPaperAbstention(_RunPaperCaseIssue):
    kind: Literal["abstention"] = "abstention"


_AUTHORITY_NONRECEIPT_ROLES = {
    "generation_cycle_grounding_authority": (
        "polisyos.runtime.quality.generation_cycle.GroundingStatus",
        ("grounding_state", "grounded_case_projection", "available_run_paper_case"),
    ),
    "hypothesis_ledger_admission_authority": (
        "polisyos.runtime.quality.hypothesis_ledger.HypothesisAdmissionState",
        ("admission_state", "admitted_case_projection", "available_run_paper_case"),
    ),
    "layer3_g4_promotion_authority": (
        "polisyos.runtime.quality.proving_ground.governed_promotion_gate."
        "Layer3G4PromotionRecord.promotion_state",
        ("promotion_state", "governed_case_projection", "available_run_paper_case"),
    ),
}


class RunPaperAuthorityNonReceipt(_StrictModel):
    """Typed proof that one authority owner did not supply an admitted record."""

    kind: Literal["run_paper_authority_nonreceipt"] = "run_paper_authority_nonreceipt"
    status: Literal["not_established"] = "not_established"
    missing_authority: Literal[
        "generation_cycle_grounding_authority",
        "hypothesis_ledger_admission_authority",
        "layer3_g4_promotion_authority",
    ]
    authority_state: Literal["absent/unallocated"] = "absent/unallocated"
    owner_route: str = Field(min_length=1)
    denied_uses: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_role_specific_nonreceipt(self) -> RunPaperAuthorityNonReceipt:
        expected_owner, expected_denied_uses = _AUTHORITY_NONRECEIPT_ROLES[
            self.missing_authority
        ]
        if self.owner_route != expected_owner or self.denied_uses != expected_denied_uses:
            raise ValueError(
                f"{self.missing_authority} nonreceipt carries the wrong owner or denied uses"
            )
        return self


def _require_bound_case_content(
    case_id: str,
    binding: RunPaperDesignRecordBinding,
    design_record: DesignRecordV0,
) -> None:
    if case_id != binding.case_id:
        raise ValueError("case_id must equal design_record_binding.case_id")
    if design_record.record_id != binding.design_record_record_id:
        raise ValueError("design_record.record_id must equal the content-bound binding record id")
    if design_record.schema_version != binding.design_record_schema_version:
        raise ValueError("DesignRecordV0 schema version does not match its binding")


class AvailableRunPaperCase(_StrictModel):
    """Frozen DS8-B slot for a future verified run-bound DesignRecord."""

    availability: Literal["available"] = "available"
    case_id: str = Field(min_length=1)
    design_record_binding: RunPaperDesignRecordBinding
    design_record: DesignRecordV0
    grounding_state: RunPaperGroundingState
    admission_state: RunPaperAdmissionState
    promotion_state: RunPaperPromotionState
    blockers: tuple[RunPaperBlocker, ...]
    limitations: tuple[RunPaperLimitation, ...]
    objections: tuple[RunPaperObjection, ...]
    abstentions: tuple[RunPaperAbstention, ...]

    @model_validator(mode="after")
    def _bind_case_and_authority(self) -> AvailableRunPaperCase:
        _require_bound_case_content(
            self.case_id,
            self.design_record_binding,
            self.design_record,
        )
        authority_sources = {
            "grounding_state": self.grounding_state.source_binding,
            "admission_state": self.admission_state.source_binding,
            "promotion_state": self.promotion_state.source_binding,
        }
        for role, source in authority_sources.items():
            self._assert_source_binding(role, source)
        source_ids = {str(source.source_ref.artifact_id) for source in authority_sources.values()}
        validator_ids = {source.verification.validator_id for source in authority_sources.values()}
        if len(source_ids) != len(authority_sources) or len(validator_ids) != len(
            authority_sources
        ):
            raise ValueError(
                "grounding, admission and promotion require distinct owner sources and verifiers"
            )
        issue_ids: list[str] = []
        issue_groups = {
            "blocker": self.blockers,
            "limitation": self.limitations,
            "objection": self.objections,
            "abstention": self.abstentions,
        }
        for role, issues in issue_groups.items():
            for issue in issues:
                issue_ids.append(issue.issue_id)
                for source in issue.source_bindings:
                    self._assert_source_binding(role, source)
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("case issue identity must be unique across all issue kinds")
        if self.promotion_state.state == "governed_promoted":
            if self.grounding_state.state != "current_valid":
                raise ValueError("governed promotion requires current_valid grounding")
            if self.admission_state.state not in {
                "admitted_to_obligation",
                "admitted_to_claim",
            }:
                raise ValueError("governed promotion requires an admitted authority state")
            if self.design_record.projection_status != "governed":
                raise ValueError("governed promotion requires a governed DesignRecordV0")
        return self

    def _assert_source_binding(
        self,
        role: str,
        source: RunPaperVerifiedCaseSource,
    ) -> None:
        binding = self.design_record_binding
        verification = source.verification
        if source.authority_purpose != role:
            raise ValueError(f"case source authority_purpose must equal {role}")
        expected = (
            self.case_id,
            binding.run_id,
            binding.tenant_id,
            binding.cell_id,
            binding.design_record_record_id,
        )
        actual = (
            verification.bound_case_id,
            verification.bound_run_id,
            verification.bound_tenant_id,
            verification.bound_cell_id,
            verification.bound_design_record_record_id,
        )
        if actual != expected:
            raise ValueError(f"{role} source verifier does not bind the packet case identity")


class AuthorityAbstainingRunPaperCase(_StrictModel):
    """Verified S2 record rendered without fabricating absent authority owners."""

    availability: Literal["record_available_authority_abstaining"] = (
        "record_available_authority_abstaining"
    )
    authority_projection: Literal["abstained"] = "abstained"
    case_id: str = Field(min_length=1)
    design_record_binding: RunPaperDesignRecordBinding
    design_record: DesignRecordV0
    grounding_nonreceipt: RunPaperAuthorityNonReceipt
    admission_nonreceipt: RunPaperAuthorityNonReceipt
    promotion_nonreceipt: RunPaperAuthorityNonReceipt

    @model_validator(mode="after")
    def _bind_case_and_authority_roles(self) -> AuthorityAbstainingRunPaperCase:
        _require_bound_case_content(
            self.case_id,
            self.design_record_binding,
            self.design_record,
        )
        expected = {
            "grounding": "generation_cycle_grounding_authority",
            "admission": "hypothesis_ledger_admission_authority",
            "promotion": "layer3_g4_promotion_authority",
        }
        actual = {
            "grounding": self.grounding_nonreceipt.missing_authority,
            "admission": self.admission_nonreceipt.missing_authority,
            "promotion": self.promotion_nonreceipt.missing_authority,
        }
        mismatched = [role for role, authority in expected.items() if actual[role] != authority]
        if mismatched:
            raise ValueError(
                "authority nonreceipt is in the wrong role: " + ", ".join(mismatched)
            )
        return self


class UnavailableRunPaperCase(_StrictModel):
    """Typed absence for the registered run-to-DesignRecord producer gap."""

    availability: Literal["artifact_missing"] = "artifact_missing"
    capability_state: Literal["producer_missing"] = "producer_missing"
    reason_code: Literal["case-record-not-run-bound"] = RUN_PAPER_CASE_GAP
    owner_route: Literal["team-runtime"] = "team-runtime"
    closure_signal: Literal["case-record-not-run-bound"] = RUN_PAPER_CASE_GAP
    may_not_use_for: tuple[str, ...] = _CASE_DENIED_USES

    @model_validator(mode="after")
    def _require_complete_denied_uses(self) -> UnavailableRunPaperCase:
        if self.may_not_use_for != _CASE_DENIED_USES:
            raise ValueError(
                "typed unavailable case must carry the complete canonical denied-use tuple"
            )
        return self


RunPaperCaseRecord = Annotated[
    AvailableRunPaperCase | AuthorityAbstainingRunPaperCase | UnavailableRunPaperCase,
    Field(discriminator="availability"),
]


class AvailableRunPaperStageTrace(_StrictModel):
    availability: Literal["available"] = "available"
    trace_ref: artifacts.ArtifactRef
    section_id: Literal["stage-trace"] = "stage-trace"
    owner_route: Literal["core RunManifest.trace_ref"] = "core RunManifest.trace_ref"


class UnavailableRunPaperStageTrace(_StrictModel):
    availability: Literal["not_established", "invalid_source"] = "not_established"
    reason: str = "verified run manifest carries no trace reference"
    owner_route: Literal["core RunManifest.trace_ref"] = "core RunManifest.trace_ref"


RunPaperStageTrace = Annotated[
    AvailableRunPaperStageTrace | UnavailableRunPaperStageTrace,
    Field(discriminator="availability"),
]


class RunPaperArtifactLink(_StrictModel):
    """One content-addressed ordinary link admitted from manifest outputs."""

    relation: Literal["run_output"] = "run_output"
    artifact_ref: artifacts.ArtifactRef
    href: str

    @model_validator(mode="after")
    def _derive_href(self) -> RunPaperArtifactLink:
        expected = f"/api/v1/artifacts/{self.artifact_ref.artifact_id}"
        if self.href != expected:
            raise ValueError("artifact link href must derive from artifact_ref")
        return self


class RunPaperRun(_StrictModel):
    run_id: str
    source_kind: Literal["core_run"] = "core_run"
    status: str
    run_terminality: Literal["terminal", "non_terminal", "not_established"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    tenant_id: str
    cell_id: str | None = None


class RunPaperSourceBinding(_StrictModel):
    """Exact verified manifest and producer provenance used by the projection."""

    manifest_ref: artifacts.ArtifactRef
    manifest_schema_name: Literal["polisyos.core.RunManifest"] = "polisyos.core.RunManifest"
    manifest_schema_version: Literal["0.1.0"] = RUN_PAPER_MANIFEST_SCHEMA_VERSION
    producer: artifacts.ProducerInfo | None
    environment: artifacts.EnvInfo | None
    registry_bundle: artifacts.ArtifactRef


def build_run_paper_semantic_projection(
    *,
    run: RunPaperRun,
    case_record: RunPaperCaseRecord,
    stage_trace: RunPaperStageTrace,
    artifact_links: tuple[RunPaperArtifactLink, ...],
    source: RunPaperSourceBinding,
) -> dict[str, object]:
    """Return the exact non-self-referential material hashed by run paper."""

    return {
        "packet_schema_version": RUN_PAPER_PACKET_SCHEMA_VERSION,
        "projection_rule_version": RUN_PAPER_PROJECTION_RULE_VERSION,
        "run": run,
        "case_record": case_record,
        "stage_trace": stage_trace,
        "artifact_links": artifact_links,
        "source": source,
    }


class RunPaperPacket(_StrictModel):
    """One replay-addressed paper and MACHINE packet for a verified run."""

    packet_schema_version: Literal["policyos.runtime.run_paper_packet.v1"] = (
        RUN_PAPER_PACKET_SCHEMA_VERSION
    )
    projection_rule_version: Literal["policyos.runtime.run_paper.v1"] = (
        RUN_PAPER_PROJECTION_RULE_VERSION
    )
    intended_audiences: tuple[Literal["reviewer"], Literal["expert"]] = (
        "reviewer",
        "expert",
    )
    run: RunPaperRun
    case_record: RunPaperCaseRecord
    stage_trace: RunPaperStageTrace
    artifact_links: tuple[RunPaperArtifactLink, ...]
    source: RunPaperSourceBinding
    replay_pins: RunPaperReplayPins
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    stable_address: str
    replay_address: str
    report_href: str

    @model_validator(mode="after")
    def _bind_packet_identity(self) -> RunPaperPacket:
        if isinstance(
            self.case_record,
            AvailableRunPaperCase | AuthorityAbstainingRunPaperCase,
        ):
            binding = self.case_record.design_record_binding
            if binding.run_id != self.run.run_id:
                raise ValueError("case binding run_id must equal packet run_id")
            if binding.tenant_id != self.run.tenant_id:
                raise ValueError("case binding tenant_id must equal packet tenant_id")
            if binding.cell_id != self.run.cell_id:
                raise ValueError("case binding cell_id must equal packet cell_id")
        if self.replay_pins.manifest_artifact_id != str(self.source.manifest_ref.artifact_id):
            raise ValueError("replay manifest pin must equal source manifest artifact id")
        if self.replay_pins.manifest_schema_version != self.source.manifest_schema_version:
            raise ValueError("replay manifest schema pin must equal source schema version")
        if self.replay_pins.paper_projection_rule_version != self.projection_rule_version:
            raise ValueError("replay rule pin must equal packet projection rule")
        semantic_projection = build_run_paper_semantic_projection(
            run=self.run,
            case_record=self.case_record,
            stage_trace=self.stage_trace,
            artifact_links=self.artifact_links,
            source=self.source,
        )
        recomputed_hash = hash_export_projection(semantic_projection)
        if self.projection_hash != recomputed_hash:
            raise ValueError("projection_hash must bind the complete paper semantics")
        if self.replay_pins.paper_projection_hash != self.projection_hash:
            raise ValueError("replay projection hash pin must equal packet projection hash")
        pin_values = self.replay_pins.model_dump(mode="json")
        expected_stable = f"/api/v1/runs/{self.run.run_id}/paper"
        expected_replay = build_export_replay_address(expected_stable, pin_values)
        expected_report = (
            build_export_replay_address(
                f"/runs/{self.run.run_id}/report",
                pin_values,
            )
            + "#stage-trace"
        )
        if self.stable_address != expected_stable:
            raise ValueError("stable_address must be derived from packet run identity")
        if self.replay_address != expected_replay:
            raise ValueError("replay_address must serialize the complete replay tuple")
        if self.report_href != expected_report:
            raise ValueError("report_href must serialize the complete replay tuple")
        return self


class RunPaperStageTraceResolution(_StrictModel):
    """Narrow verified paper result consumed by Cycle Board composition."""

    href: str
    manifest_artifact_id: str
    manifest_schema_version: Literal["0.1.0"] = RUN_PAPER_MANIFEST_SCHEMA_VERSION
    paper_projection_rule_version: Literal["policyos.runtime.run_paper.v1"] = (
        RUN_PAPER_PROJECTION_RULE_VERSION
    )
    paper_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class RunPaperReplayConflictError(ValueError):
    """Reject an absent-partial, stale, or mixed paper replay tuple."""


class RunPaperReplaySyntaxError(ValueError):
    """Reject unknown, duplicate, or malformed HTTP replay query items."""


class RunPaperSourceError(ValueError):
    """Reject a run whose terminal manifest cannot support a paper projection."""


__all__ = [
    "RUN_PAPER_CASE_GAP",
    "RUN_PAPER_MANIFEST_SCHEMA_VERSION",
    "RUN_PAPER_PACKET_SCHEMA_VERSION",
    "RUN_PAPER_PROJECTION_RULE_VERSION",
    "AuthorityAbstainingRunPaperCase",
    "AvailableRunPaperCase",
    "RunPaperAuthorityNonReceipt",
    "RunPaperCaseRecord",
    "RunPaperDesignRecordBinding",
    "RunPaperPacket",
    "RunPaperReplayConflictError",
    "RunPaperReplayPins",
    "RunPaperReplayQuery",
    "RunPaperReplaySyntaxError",
    "RunPaperSourceError",
    "RunPaperStageTrace",
    "RunPaperStageTraceResolution",
    "UnavailableRunPaperCase",
    "build_run_paper_semantic_projection",
]
