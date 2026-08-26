"""Public scientist publisher module API and decision-grade compiler."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.evidence.claims.export import (
    ClaimExportAudience,
    ClaimLedgerExport,
)
from polisyos.scientist.evidence.claims.head_index import (
    ClaimLedgerCurrentHeadProjection,
    ClaimLedgerExportService,
    ClaimLedgerHeadResolutionNonReceipt,
    ClaimLedgerOwnerKey,
    ClaimLedgerOwnerPort,
    project_claim_ledger_current_head,
)
from polisyos.scientist.governance.continuous.reports import (
    DecisionValidityReport,
    export_public_validity_report,
)
from polisyos.scientist.governance.human_review.models import HumanReviewPacket
from polisyos.scientist.governance.human_review.packets import review_packet_summary
from polisyos.scientist.methods.research_dag.models import ResearchDAGArtifact
from polisyos.scientist.methods.research_dag.replay import (
    legacy_replay_status,
    public_replay_export,
)

DECISION_GRADE_COMPILER_FLAG = "scientist.best_in_class.wave2.phase2_7.decision_grade_compiler"
COMPILER_BACKED_DECISION_CARD_FLAG = (
    "scientist.best_in_class.wave2.phase2_7.compiler_backed_decision_card"
)
DECISION_GRADE_EXPORT_KIND = "scientist.decision_grade_export"
DECISION_GRADE_EXPORT_SCHEMA_NAME = "polisyos.scientist.DecisionGradeExport"
DECISION_GRADE_EXPORT_SCHEMA_VERSION = "1.0"

FORBIDDEN_PUBLIC_EXPORT_TOKENS: tuple[str, ...] = (
    "hidden_benchmark",
    "hidden_eval",
    "hidden_holdout",
    "private_eval",
    "internal_monitor",
    "benchmark_answer",
    "raw_transcript",
    "system_prompt",
    "developer_prompt",
)


class OutputAudience(str, Enum):
    """Audience-specific compiler tiers."""

    PUBLIC = "public"
    REVIEWER = "reviewer"
    EXPERT = "expert"
    MACHINE = "machine"


class OutputOmissionRecord(BaseModel):
    """Intentional omission from an audience export."""

    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(min_length=1)
    audience: OutputAudience
    reason: str = Field(min_length=1)
    hidden_ref: ArtifactRef | None = None

    @field_validator("field_path", "reason")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("output omission fields cannot be blank")
        return value


class DecisionGradeExport(BaseModel):
    """Compiled output tier derived from the same claim ledger and research DAG."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    audience: OutputAudience
    claims_ref: ArtifactRef
    research_dag_ref: ArtifactRef
    payload: dict[str, Any]
    omissions: list[OutputOmissionRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_export_contract(self) -> DecisionGradeExport:
        trust = self.payload.get("trust_provenance")
        if not isinstance(trust, Mapping):
            raise ValueError("decision-grade exports require trust_provenance")
        _validate_trust_refs(
            trust, claims_ref=self.claims_ref, research_dag_ref=self.research_dag_ref
        )
        current_head = ClaimLedgerCurrentHeadProjection.model_validate(
            self.payload.get("claim_current_head")
        )
        if current_head.ledger_artifact_ref != self.claims_ref:
            raise ValueError("decision-grade claim current-head trust mismatch")
        _validate_current_head_trust(trust, current_head=current_head)

        blocked_count = _blocked_count(self.payload)
        visible_blocked = _has_visible_blocked_claims(self.payload)
        if blocked_count > 0:
            if self.audience in {
                OutputAudience.REVIEWER,
                OutputAudience.EXPERT,
                OutputAudience.MACHINE,
            }:
                if not visible_blocked:
                    raise ValueError("reviewer/expert/machine exports must include blocked claims")
            elif not any(_omission_covers_blockers(item) for item in self.omissions):
                raise ValueError("blocked claims cannot be silently omitted")

        if self.audience is OutputAudience.PUBLIC:
            if any(item.hidden_ref is not None for item in self.omissions):
                raise ValueError("public omissions must not expose hidden refs")
            _raise_if_forbidden_public_export(self.payload)
        return self


def compile_decision_grade_export(
    *,
    run_id: str,
    audience: OutputAudience | str,
    research_dag_ref: ArtifactRef,
    claim_owner: ClaimLedgerOwnerPort,
    claim_owner_key: ClaimLedgerOwnerKey,
    research_dag: ResearchDAGArtifact,
    decision_payload: Mapping[str, Any] | None = None,
    evidence_bundle_ref: ArtifactRef | None = None,
    benchmark_authority_verdict: Any | None = None,
    human_review_packet: HumanReviewPacket | None = None,
    human_review_packet_ref: ArtifactRef | None = None,
    continuous_governance_report: DecisionValidityReport | Mapping[str, Any] | None = None,
    continuous_governance_report_ref: ArtifactRef | None = None,
    reissue_packet_ref: ArtifactRef | None = None,
    withdrawal_record_ref: ArtifactRef | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> DecisionGradeExport:
    """Compile one audience-specific output from governed research artifacts."""

    resolved_audience = OutputAudience(audience)
    decision = dict(decision_payload or {})
    claim_audience = _claim_export_audience(resolved_audience)
    before = claim_owner.resolve_current(owner_key=claim_owner_key)
    if isinstance(before, ClaimLedgerHeadResolutionNonReceipt):
        raise ValueError(before.code)
    claim_export = ClaimLedgerExportService(claim_owner=claim_owner).export(
        owner_key=claim_owner_key,
        audience=claim_audience,
    )
    if isinstance(claim_export, ClaimLedgerHeadResolutionNonReceipt):
        raise ValueError(claim_export.code)
    confirmed_export = ClaimLedgerExportService(claim_owner=claim_owner).export(
        owner_key=claim_owner_key,
        audience=claim_audience,
    )
    if isinstance(confirmed_export, ClaimLedgerHeadResolutionNonReceipt):
        raise ValueError(confirmed_export.code)
    after = claim_owner.resolve_current(owner_key=claim_owner_key)
    if isinstance(after, ClaimLedgerHeadResolutionNonReceipt):
        raise ValueError(after.code)
    if after != before or confirmed_export != claim_export:
        raise ValueError("claim_head_changed_during_export")
    if claim_export.audience != claim_audience:
        raise ValueError("claim_owner_export_audience_mismatch")
    claim_current_head = project_claim_ledger_current_head(
        head=before,
        claim_export=claim_export,
    )
    claims_ref = before.statement.ledger_artifact_ref
    _validate_compile_sources(
        run_id=run_id,
        claims_ref=claims_ref,
        claim_export=claim_export,
        research_dag=research_dag,
    )
    ledger_summary = _claim_summary_from_export(claim_export)
    blocked_summary = _blocked_summary_from_export(claim_export)
    replay_export = public_replay_export(research_dag)
    governance = _continuous_governance_payload(
        continuous_governance_report,
        audience=resolved_audience,
    )
    trust = _trust_provenance(
        claims_ref=claims_ref,
        claim_current_head=claim_current_head,
        research_dag_ref=research_dag_ref,
        claim_export=claim_export,
        research_dag=research_dag,
        research_replay=replay_export,
        continuous_governance=governance,
        evidence_bundle_ref=evidence_bundle_ref,
        human_review_packet_ref=human_review_packet_ref,
        continuous_governance_report_ref=continuous_governance_report_ref,
        reissue_packet_ref=reissue_packet_ref,
        withdrawal_record_ref=withdrawal_record_ref,
    )

    omissions = _omissions_for_claim_export(claim_export, audience=resolved_audience)
    common = {
        "schema_version": "1.0",
        "run_id": run_id,
        "audience": resolved_audience.value,
        "claim_ledger_summary": ledger_summary,
        "research_dag_summary": _research_dag_summary(research_dag, replay_export),
        "continuous_governance": governance,
        "trust_provenance": trust,
        "claim_current_head": claim_current_head.model_dump(mode="json"),
        "metadata": dict(metadata or {}),
    }

    if resolved_audience is OutputAudience.PUBLIC:
        payload = {
            **common,
            "tier": "public_summary",
            "summary": _public_summary(decision, claim_export.model_dump(mode="json")),
            "approved_claims": _visible_claims(claim_export.model_dump(mode="json")),
            "limits": _public_limits(
                ledger_summary=ledger_summary,
                blocked_summary=blocked_summary,
                replay_export=replay_export,
            ),
            "blocked_claim_summary": {
                "schema_version": "1.0",
                "run_id": run_id,
                "blocked_count": blocked_summary.get("blocked_count", 0),
                "blocked_claims_omitted": bool(blocked_summary.get("blocked_count", 0)),
            },
            "research_path": _public_research_path(replay_export),
        }
    elif resolved_audience is OutputAudience.REVIEWER:
        payload = {
            **common,
            "tier": "reviewer_packet",
            "claim_ledger_export": claim_export.model_dump(mode="json"),
            "blocked_claim_summary": blocked_summary,
            "reviewer_controls": _reviewer_controls(human_review_packet),
            "evidence": _evidence_payload(
                claim_export,
                evidence_bundle_ref=evidence_bundle_ref,
            ),
            "research_replay": replay_export,
        }
    elif resolved_audience is OutputAudience.EXPERT:
        payload = {
            **common,
            "tier": "expert_appendix",
            "claim_ledger_export": claim_export.model_dump(mode="json"),
            "blocked_claim_summary": blocked_summary,
            "methods": _methods_payload(research_dag, replay_export),
            "uncertainty": _dict_section(decision, "uncertainty"),
            "assumptions": _assumptions_payload(decision),
            "benchmark_authority": _benchmark_payload(benchmark_authority_verdict),
            "research_replay": replay_export,
        }
    else:
        payload = {
            **common,
            "tier": "machine_export",
            "claim_ledger_export": claim_export.model_dump(mode="json"),
            "blocked_claim_summary": blocked_summary,
            "research_replay": replay_export,
            "refs": {
                "claims_ref": _artifact_ref_payload(claims_ref),
                "research_dag_ref": _artifact_ref_payload(research_dag_ref),
                "evidence_bundle_ref": _optional_artifact_ref_payload(evidence_bundle_ref),
                "human_review_packet_ref": _optional_artifact_ref_payload(human_review_packet_ref),
                "continuous_governance_report_ref": _optional_artifact_ref_payload(
                    continuous_governance_report_ref
                ),
                "reissue_packet_ref": _optional_artifact_ref_payload(reissue_packet_ref),
                "withdrawal_record_ref": _optional_artifact_ref_payload(withdrawal_record_ref),
            },
            "frontend_trust_view": _frontend_trust_view(
                trust=trust,
                claim_export=claim_export.model_dump(mode="json"),
                blocked_summary=blocked_summary,
                replay_export=replay_export,
            ),
        }

    return DecisionGradeExport(
        run_id=run_id,
        audience=resolved_audience,
        claims_ref=claims_ref,
        research_dag_ref=research_dag_ref,
        payload=payload,
        omissions=omissions,
    )


def compile_decision_grade_exports(
    *,
    run_id: str,
    research_dag_ref: ArtifactRef,
    claim_owner: ClaimLedgerOwnerPort,
    claim_owner_key: ClaimLedgerOwnerKey,
    research_dag: ResearchDAGArtifact,
    audiences: tuple[OutputAudience | str, ...] = tuple(OutputAudience),
    **kwargs: Any,
) -> dict[OutputAudience, DecisionGradeExport]:
    """Compile multiple audience tiers and validate shared provenance refs."""

    exports = {
        OutputAudience(audience): compile_decision_grade_export(
            run_id=run_id,
            audience=OutputAudience(audience),
            research_dag_ref=research_dag_ref,
            claim_owner=claim_owner,
            claim_owner_key=claim_owner_key,
            research_dag=research_dag,
            **kwargs,
        )
        for audience in audiences
    }
    assert_decision_grade_exports_consistent(exports.values())
    return exports


def assert_decision_grade_exports_consistent(
    exports: Any,
) -> None:
    """Ensure output tiers derive from one claim ledger and one Research DAG."""

    export_list = list(exports)
    if not export_list:
        raise ValueError("at least one decision-grade export is required")
    claims_refs = {_artifact_ref_key(item.claims_ref) for item in export_list}
    dag_refs = {_artifact_ref_key(item.research_dag_ref) for item in export_list}
    if len(claims_refs) != 1 or len(dag_refs) != 1:
        raise ValueError("decision-grade exports must share claims_ref and research_dag_ref")
    owner_views = {
        (
            _artifact_ref_mapping_key(item.payload["trust_provenance"].get("claim_head_ref")),
            item.payload["trust_provenance"].get("claim_head_content_hash"),
            item.payload["trust_provenance"].get("claim_head_generation"),
            item.payload["trust_provenance"].get("claim_currentness"),
            tuple(item.payload["trust_provenance"].get("pending_receipt_refs", ())),
            tuple(item.payload["trust_provenance"].get("pending_batch_receipt_refs", ())),
            tuple(item.payload["trust_provenance"].get("pending_affected_claim_ids", ())),
            item.payload["trust_provenance"].get("pending_mapping_unresolved"),
        )
        for item in export_list
    }
    if len(owner_views) != 1:
        raise ValueError("decision-grade exports must share one current Claim owner projection")


def decision_grade_export_inputs(export: DecisionGradeExport) -> list[InputRef]:
    """Return manifest lineage inputs for a persisted decision-grade export."""

    return [
        InputRef(artifact_id=export.claims_ref.artifact_id, role="claims"),
        InputRef(artifact_id=export.research_dag_ref.artifact_id, role="research_dag"),
    ]


def persist_decision_grade_export(
    store: Any,
    export: DecisionGradeExport,
    *,
    claim_owner: ClaimLedgerOwnerPort,
    claim_owner_key: ClaimLedgerOwnerKey,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist only after re-resolving its exact owner-held Claim projection."""

    claim_audience = _claim_export_audience(export.audience)
    before = claim_owner.resolve_current(owner_key=claim_owner_key)
    if isinstance(before, ClaimLedgerHeadResolutionNonReceipt):
        raise ValueError(before.code)
    claim_export = ClaimLedgerExportService(claim_owner=claim_owner).export(
        owner_key=claim_owner_key,
        audience=claim_audience,
    )
    if isinstance(claim_export, ClaimLedgerHeadResolutionNonReceipt):
        raise ValueError(claim_export.code)
    after = claim_owner.resolve_current(owner_key=claim_owner_key)
    if isinstance(after, ClaimLedgerHeadResolutionNonReceipt):
        raise ValueError(after.code)
    current_projection = project_claim_ledger_current_head(
        head=before,
        claim_export=claim_export,
    )
    if (
        before != after
        or export.claims_ref != before.statement.ledger_artifact_ref
        or ClaimLedgerCurrentHeadProjection.model_validate(export.payload.get("claim_current_head"))
        != current_projection
        or export.payload.get("claim_ledger_summary") != _claim_summary_from_export(claim_export)
    ):
        raise ValueError("decision_grade_claim_owner_projection_mismatch")
    blocked_summary = _blocked_summary_from_export(claim_export)
    if export.audience is OutputAudience.PUBLIC:
        expected_blocked = {
            "schema_version": "1.0",
            "run_id": export.run_id,
            "blocked_count": blocked_summary.get("blocked_count", 0),
            "blocked_claims_omitted": bool(blocked_summary.get("blocked_count", 0)),
        }
        if (
            export.payload.get("approved_claims")
            != _visible_claims(claim_export.model_dump(mode="json"))
            or export.payload.get("blocked_claim_summary") != expected_blocked
            or export.omissions
            != _omissions_for_claim_export(
                claim_export,
                audience=OutputAudience.PUBLIC,
            )
        ):
            raise ValueError("decision_grade_claim_owner_projection_mismatch")
    elif (
        export.payload.get("claim_ledger_export") != claim_export.model_dump(mode="json")
        or export.payload.get("blocked_claim_summary") != blocked_summary
    ):
        raise ValueError("decision_grade_claim_owner_projection_mismatch")

    return store.put_json(
        export,
        PutOptions(
            kind=DECISION_GRADE_EXPORT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=DECISION_GRADE_EXPORT_SCHEMA_NAME,
                version=DECISION_GRADE_EXPORT_SCHEMA_VERSION,
            ),
            inputs=list(inputs) if inputs is not None else decision_grade_export_inputs(export),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_decision_grade_export(store: Any, ref: ArtifactRef) -> DecisionGradeExport:
    """Load a persisted decision-grade export from CAS."""

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return DecisionGradeExport.model_validate(payload)


def _validate_compile_sources(
    *,
    run_id: str,
    claims_ref: ArtifactRef,
    claim_export: ClaimLedgerExport,
    research_dag: ResearchDAGArtifact,
) -> None:
    if claim_export.run_id != run_id:
        raise ValueError("claim ledger run_id must match decision-grade export run_id")
    if research_dag.run_id != run_id:
        raise ValueError("research DAG run_id must match decision-grade export run_id")
    if research_dag.claim_ledger_ref is not None and research_dag.claim_ledger_ref != claims_ref:
        raise ValueError("research DAG claim_ledger_ref must match claims_ref")


def publish_decision(state: Mapping[str, Any]) -> dict[str, Any]:
    """Build a canonical decision packet payload from engine state."""
    run_id = str(state.get("run_id") or "unknown")
    return {
        "schema_version": "2.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "run_record": {
            "schema_version": "2.0",
            "run_id": run_id,
            "seed": int(state.get("params", {}).get("random_seed", 0) or 0),
            "engine": "scientist.engine",
        },
        "simulation_results": state.get("simulation_results"),
        "governance": state.get("feedback"),
        "notes": [],
    }


def _claim_export_audience(audience: OutputAudience) -> ClaimExportAudience:
    if audience is OutputAudience.PUBLIC:
        return ClaimExportAudience.PUBLIC
    if audience is OutputAudience.REVIEWER:
        return ClaimExportAudience.REVIEWER
    if audience is OutputAudience.EXPERT:
        return ClaimExportAudience.EXPERT
    return ClaimExportAudience.MACHINE


def _claim_summary_from_export(export: ClaimLedgerExport) -> dict[str, Any]:
    publishability_counts: dict[str, int] = {}
    for claim in export.claims:
        publishability_counts[claim.publishability] = (
            publishability_counts.get(claim.publishability, 0) + 1
        )
    review_required = [
        claim.claim_id for claim in export.claims if claim.publishability == "review_required"
    ]
    lifecycle_limitations = export.metadata.get("lifecycle_limitation_by_claim", {})
    if isinstance(lifecycle_limitations, Mapping):
        review_required = sorted(
            {
                *review_required,
                *(
                    str(claim_id)
                    for claim_id, action in lifecycle_limitations.items()
                    if action == "review_required"
                ),
            }
        )
    return {
        "schema_version": export.schema_version,
        "run_id": export.run_id,
        "claim_count": len(export.claims),
        "family_assignment_count": export.metadata.get("family_assignment_count", 0),
        "baseline_record_count": export.metadata.get("baseline_record_count", 0),
        "alternative_record_count": export.metadata.get("alternative_record_count", 0),
        "comparison_record_count": export.metadata.get("comparison_record_count", 0),
        "lifecycle_status": export.lifecycle_status,
        "publishability_counts": publishability_counts,
        "blocked_claim_ids": list(export.blocked_claim_ids),
        "review_required_claim_ids": review_required,
        "publication_ready": (
            not export.blocked_claim_ids
            and not review_required
            and not export.metadata.get("lifecycle_limited_claim_ids")
            and export.metadata.get("claim_currentness") == "current"
        ),
        "claim_currentness": export.metadata.get("claim_currentness"),
        "claim_bridge_pending": bool(export.metadata.get("claim_bridge_pending")),
    }


def _blocked_summary_from_export(export: ClaimLedgerExport) -> dict[str, Any]:
    blocked = [
        {
            "claim_id": claim.claim_id,
            "text": claim.text,
            "blocked_reasons": list(claim.blocked_reasons),
            "counterevidence_ref_count": claim.counterevidence_ref_count,
            "reviewer_ref_count": claim.reviewer_ref_count,
        }
        for claim in export.claims
        if claim.claim_id in export.blocked_claim_ids and claim.visible
    ]
    return {
        "schema_version": export.schema_version,
        "run_id": export.run_id,
        "lifecycle_status": export.lifecycle_status,
        "blocked_count": len(export.blocked_claim_ids),
        "blocked_claims": blocked,
        "superseded_claim_ids": list(export.superseded_claim_ids),
    }


def _trust_provenance(
    *,
    claims_ref: ArtifactRef,
    claim_current_head: ClaimLedgerCurrentHeadProjection,
    research_dag_ref: ArtifactRef,
    claim_export: ClaimLedgerExport,
    research_dag: ResearchDAGArtifact,
    research_replay: Mapping[str, Any],
    continuous_governance: Mapping[str, Any],
    evidence_bundle_ref: ArtifactRef | None,
    human_review_packet_ref: ArtifactRef | None,
    continuous_governance_report_ref: ArtifactRef | None,
    reissue_packet_ref: ArtifactRef | None,
    withdrawal_record_ref: ArtifactRef | None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "claims_ref": _artifact_ref_payload(claims_ref),
        "claim_head_ref": _artifact_ref_payload(claim_current_head.head_ref),
        "claim_head_content_hash": claim_current_head.head_content_hash,
        "claim_head_generation": claim_current_head.head_generation,
        "claim_currentness": claim_current_head.claim_currentness,
        "claim_bridge_pending": claim_current_head.claim_bridge_pending,
        "pending_receipt_refs": list(claim_current_head.pending_receipt_refs),
        "pending_batch_receipt_refs": list(claim_current_head.pending_batch_receipt_refs),
        "pending_affected_claim_ids": list(claim_current_head.pending_affected_claim_ids),
        "pending_mapping_unresolved": claim_current_head.pending_mapping_unresolved,
        "completed_batch_denominator_established": (
            claim_current_head.completed_batch_denominator_established
        ),
        "research_dag_ref": _artifact_ref_payload(research_dag_ref),
        "claim_count": len(claim_export.claims),
        "blocked_claim_count": len(claim_export.blocked_claim_ids),
        "research_step_count": len(research_replay.get("steps", []) or []),
        "research_dag_status": research_replay.get("replay_status")
        or legacy_replay_status(research_dag),
        "workflow_id": research_dag.workflow_id,
        "continuous_governance_status": continuous_governance.get("status"),
        "sidecar_refs": {
            "evidence_bundle_ref": _optional_artifact_ref_payload(evidence_bundle_ref),
            "human_review_packet_ref": _optional_artifact_ref_payload(human_review_packet_ref),
            "continuous_governance_report_ref": _optional_artifact_ref_payload(
                continuous_governance_report_ref
            ),
            "reissue_packet_ref": _optional_artifact_ref_payload(reissue_packet_ref),
            "withdrawal_record_ref": _optional_artifact_ref_payload(withdrawal_record_ref),
        },
    }


def _validate_current_head_trust(
    trust: Mapping[str, Any],
    *,
    current_head: ClaimLedgerCurrentHeadProjection,
) -> None:
    """Reject any serialized trust view that diverges from its typed owner read."""

    expected = {
        "claim_head_ref": _artifact_ref_payload(current_head.head_ref),
        "claim_head_content_hash": current_head.head_content_hash,
        "claim_head_generation": current_head.head_generation,
        "claim_currentness": current_head.claim_currentness,
        "claim_bridge_pending": current_head.claim_bridge_pending,
        "pending_receipt_refs": list(current_head.pending_receipt_refs),
        "pending_batch_receipt_refs": list(current_head.pending_batch_receipt_refs),
        "pending_affected_claim_ids": list(current_head.pending_affected_claim_ids),
        "pending_mapping_unresolved": current_head.pending_mapping_unresolved,
        "completed_batch_denominator_established": (
            current_head.completed_batch_denominator_established
        ),
    }
    if any(trust.get(key) != value for key, value in expected.items()):
        raise ValueError("decision-grade claim current-head trust mismatch")


def _research_dag_summary(
    dag: ResearchDAGArtifact,
    replay_export: Mapping[str, Any],
) -> dict[str, Any]:
    node_type_counts: dict[str, int] = {}
    for node in dag.nodes:
        node_type_counts[node.node_type.value] = node_type_counts.get(node.node_type.value, 0) + 1
    return {
        "schema_version": dag.schema_version,
        "run_id": dag.run_id,
        "workflow_id": dag.workflow_id,
        "node_count": len(dag.nodes),
        "edge_count": len(dag.edges),
        "node_type_counts": node_type_counts,
        "replay_status": replay_export.get("replay_status"),
        "hidden_content_redacted": dag.hidden_content_redacted,
    }


def _public_summary(
    decision_payload: Mapping[str, Any],
    claim_export_payload: Mapping[str, Any],
) -> str:
    metadata = claim_export_payload.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("claim_currentness") != "current":
        return "Public claim summary withheld while Claim Ledger currentness is not established."
    omitted = claim_export_payload.get("omitted_claim_ids")
    if isinstance(omitted, list) and omitted:
        for claim in claim_export_payload.get("claims", []) or []:
            if isinstance(claim, Mapping) and claim.get("visible") is True:
                text = claim.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        return "Public claim summary withheld because owner-qualified claims are limited."
    for key in ("policy_summary", "policy_answer", "summary"):
        value = decision_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for claim in claim_export_payload.get("claims", []) or []:
        if isinstance(claim, Mapping) and claim.get("visible") is True:
            text = claim.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return "Decision-grade public summary compiled from approved claims."


def _visible_claims(claim_export_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for claim in claim_export_payload.get("claims", []) or []:
        if isinstance(claim, Mapping) and claim.get("visible") is True:
            claims.append(
                {
                    "claim_id": claim.get("claim_id"),
                    "text": claim.get("text"),
                    "claim_type": claim.get("claim_type"),
                    "support_status": claim.get("support_status"),
                    "readiness_level": claim.get("readiness_level"),
                    "source_attribution": list(claim.get("source_attribution", []) or []),
                }
            )
    return claims


def _public_limits(
    *,
    ledger_summary: Mapping[str, Any],
    blocked_summary: Mapping[str, Any],
    replay_export: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "claim_count": ledger_summary.get("claim_count", 0),
        "blocked_claim_count": blocked_summary.get("blocked_count", 0),
        "claim_currentness": ledger_summary.get("claim_currentness"),
        "claim_bridge_pending": bool(ledger_summary.get("claim_bridge_pending")),
        "publication_ready": bool(ledger_summary.get("publication_ready")),
        "review_required_claim_ids": list(
            ledger_summary.get("review_required_claim_ids", []) or []
        ),
        "omits_blocked_claim_details": bool(blocked_summary.get("blocked_count", 0)),
        "research_replay_status": replay_export.get("replay_status"),
    }


def _public_research_path(replay_export: Mapping[str, Any]) -> dict[str, Any]:
    steps = replay_export.get("steps", []) or []
    return {
        "run_id": replay_export.get("run_id"),
        "workflow_id": replay_export.get("workflow_id"),
        "replay_status": replay_export.get("replay_status"),
        "step_count": len(steps) if isinstance(steps, list) else 0,
        "hidden_content_redacted": replay_export.get("hidden_content_redacted", True),
    }


def _reviewer_controls(packet: HumanReviewPacket | None) -> dict[str, Any]:
    if packet is None:
        return {
            "packet_status": "not_attached",
            "controls": [
                "request_explanation",
                "request_rerun",
                "approve_or_reject_release",
            ],
            "recommended_reviewer_actions": ["verify_claims", "approve_or_reject_release"],
        }
    return {
        "packet_status": "attached",
        **review_packet_summary(packet),
    }


def _evidence_payload(
    claim_export: ClaimLedgerExport,
    *,
    evidence_bundle_ref: ArtifactRef | None,
) -> dict[str, Any]:
    claims = claim_export.claims
    return {
        "evidence_bundle_ref": _optional_artifact_ref_payload(evidence_bundle_ref),
        "evidence_ref_count": sum(claim.evidence_ref_count for claim in claims),
        "counterevidence_ref_count": sum(claim.counterevidence_ref_count for claim in claims),
        "claims_without_evidence": [
            claim.claim_id for claim in claims if claim.evidence_ref_count == 0
        ],
    }


def _methods_payload(
    dag: ResearchDAGArtifact,
    replay_export: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "workflow_id": dag.workflow_id,
        "research_dag": _research_dag_summary(dag, replay_export),
        "research_path": replay_export,
        "artifact_ref_count": sum(len(node.artifact_refs) for node in dag.nodes),
        "claim_link_count": sum(len(node.claim_ids) for node in dag.nodes),
    }


def _assumptions_payload(decision_payload: Mapping[str, Any]) -> dict[str, Any]:
    assumptions: list[str] = []
    for key in ("causal", "causal_validity", "uncertainty", "welfare", "analysis_limits"):
        section = _dict_section(decision_payload, key)
        for nested_key in ("assumptions", "unresolved_assumptions", "limits", "gaps"):
            value = section.get(nested_key)
            if isinstance(value, list):
                assumptions.extend(str(item) for item in value)
    return {"items": sorted(set(assumptions)), "count": len(set(assumptions))}


def _benchmark_payload(verdict: Any | None) -> dict[str, Any]:
    if verdict is None:
        return {"status": "not_attached"}
    public_export = getattr(verdict, "public_export", None)
    if callable(public_export):
        exported = public_export()
        return dict(exported) if isinstance(exported, Mapping) else {"status": "unavailable"}
    if isinstance(verdict, Mapping):
        return dict(verdict)
    model_dump = getattr(verdict, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump(mode="json"))
    return {"status": "unavailable"}


def _continuous_governance_payload(
    report: DecisionValidityReport | Mapping[str, Any] | None,
    *,
    audience: OutputAudience,
) -> dict[str, Any]:
    if report is None:
        return {"status": "not_attached"}
    if isinstance(report, DecisionValidityReport):
        if audience is OutputAudience.PUBLIC:
            return export_public_validity_report(report)
        return report.model_dump(mode="json")
    return dict(report)


def _frontend_trust_view(
    *,
    trust: Mapping[str, Any],
    claim_export: Mapping[str, Any],
    blocked_summary: Mapping[str, Any],
    replay_export: Mapping[str, Any],
) -> dict[str, Any]:
    blocked_claim_ids = [
        str(item.get("claim_id"))
        for item in blocked_summary.get("blocked_claims", []) or []
        if isinstance(item, Mapping) and item.get("claim_id")
    ]
    return {
        "claims_ref": trust.get("claims_ref"),
        "research_dag_ref": trust.get("research_dag_ref"),
        "claim_count": trust.get("claim_count", 0),
        "blocked_claim_count": blocked_summary.get("blocked_count", 0),
        "approved_claim_ids": [
            claim.get("claim_id")
            for claim in claim_export.get("claims", []) or []
            if isinstance(claim, Mapping) and claim.get("publishability") == "publishable"
        ],
        "blocked_claim_ids": blocked_claim_ids,
        "research_step_count": trust.get("research_step_count", 0),
        "research_replay_status": replay_export.get("replay_status"),
        "continuous_governance_status": trust.get("continuous_governance_status"),
    }


def _omissions_for_claim_export(
    claim_export: Any,
    *,
    audience: OutputAudience,
) -> list[OutputOmissionRecord]:
    if audience is not OutputAudience.PUBLIC:
        return []
    omissions: list[OutputOmissionRecord] = []
    for exported_claim in claim_export.claims:
        if exported_claim.visible:
            continue
        field_path = f"claim_ledger_export.claims[{exported_claim.claim_id}]"
        reason = exported_claim.omission_reason or "claim hidden from public audience"
        omissions.append(
            OutputOmissionRecord(
                field_path=field_path,
                audience=audience,
                reason=reason,
            )
        )
    if claim_export.blocked_claim_ids:
        omissions.append(
            OutputOmissionRecord(
                field_path="blocked_claim_summary.blocked_claims",
                audience=audience,
                reason="blocked claim details are visible only to reviewer, expert or machine tiers",
            )
        )
    return omissions


def _dict_section(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _artifact_ref_payload(ref: ArtifactRef) -> dict[str, str]:
    return {
        "artifact_id": str(ref.artifact_id),
        "kind": ref.kind,
        "media_type": ref.media_type,
    }


def _artifact_ref_key(ref: ArtifactRef) -> tuple[str, str, str]:
    return (str(ref.artifact_id), ref.kind, ref.media_type)


def _artifact_ref_mapping_key(value: object) -> tuple[str, str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("trust_provenance artifact ref is not a mapping")
    try:
        return _artifact_ref_key(ArtifactRef.model_validate(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("trust_provenance artifact ref is invalid") from exc


def _optional_artifact_ref_payload(ref: ArtifactRef | None) -> dict[str, str] | None:
    return _artifact_ref_payload(ref) if ref is not None else None


def _validate_trust_refs(
    trust: Mapping[str, Any],
    *,
    claims_ref: ArtifactRef,
    research_dag_ref: ArtifactRef,
) -> None:
    claims = trust.get("claims_ref")
    dag = trust.get("research_dag_ref")
    if not isinstance(claims, Mapping) or not isinstance(dag, Mapping):
        raise ValueError("trust_provenance requires claims_ref and research_dag_ref")
    if _artifact_ref_mapping_key(claims) != _artifact_ref_key(claims_ref):
        raise ValueError("trust_provenance claims_ref does not match export claims_ref")
    if _artifact_ref_mapping_key(dag) != _artifact_ref_key(research_dag_ref):
        raise ValueError("trust_provenance research_dag_ref does not match export research_dag_ref")


def _blocked_count(payload: Mapping[str, Any]) -> int:
    summary = payload.get("blocked_claim_summary")
    if isinstance(summary, Mapping) and isinstance(summary.get("blocked_count"), int):
        return int(summary["blocked_count"])
    claim_export = payload.get("claim_ledger_export")
    if isinstance(claim_export, Mapping):
        return sum(
            1
            for claim in claim_export.get("claims", []) or []
            if isinstance(claim, Mapping) and claim.get("publishability") == "blocked"
        )
    return 0


def _has_visible_blocked_claims(payload: Mapping[str, Any]) -> bool:
    summary = payload.get("blocked_claim_summary")
    if isinstance(summary, Mapping):
        blocked_claims = summary.get("blocked_claims")
        if isinstance(blocked_claims, list) and blocked_claims:
            return True
    claim_export = payload.get("claim_ledger_export")
    if isinstance(claim_export, Mapping):
        return any(
            isinstance(claim, Mapping)
            and claim.get("publishability") == "blocked"
            and claim.get("visible") is True
            for claim in claim_export.get("claims", []) or []
        )
    return False


def _omission_covers_blockers(omission: OutputOmissionRecord) -> bool:
    return "blocked" in omission.field_path.lower() or "blocked" in omission.reason.lower()


def _raise_if_forbidden_public_export(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered_key = str(key).lower()
            if any(token in lowered_key for token in FORBIDDEN_PUBLIC_EXPORT_TOKENS):
                raise ValueError(f"public export contains forbidden key: {path}.{key}")
            _raise_if_forbidden_public_export(item, path=f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _raise_if_forbidden_public_export(item, path=f"{path}[{index}]")
    elif isinstance(value, str):
        lowered_value = value.lower()
        if any(token in lowered_value for token in FORBIDDEN_PUBLIC_EXPORT_TOKENS):
            raise ValueError(f"public export contains forbidden value at {path}")


__all__ = [
    "COMPILER_BACKED_DECISION_CARD_FLAG",
    "DECISION_GRADE_COMPILER_FLAG",
    "DECISION_GRADE_EXPORT_KIND",
    "DECISION_GRADE_EXPORT_SCHEMA_NAME",
    "DECISION_GRADE_EXPORT_SCHEMA_VERSION",
    "FORBIDDEN_PUBLIC_EXPORT_TOKENS",
    "DecisionGradeExport",
    "OutputAudience",
    "OutputOmissionRecord",
    "assert_decision_grade_exports_consistent",
    "compile_decision_grade_export",
    "compile_decision_grade_exports",
    "decision_grade_export_inputs",
    "load_decision_grade_export",
    "persist_decision_grade_export",
    "publish_decision",
]
