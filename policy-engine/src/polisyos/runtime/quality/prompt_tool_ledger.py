"""Prompt, tool, and parser authority ledger for model-assisted runtime steps."""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.runtime.quality.evidence_independence import (
    EvidenceIndependenceError,
    build_evidence_independence_map,
    validate_evidence_independence_map_record,
)

SCHEMA_VERSION = "policyos.prompt_tool_parser_authority_ledger.v1"
PROMPT_TOOL_LEDGER_KIND = "runtime.prompt_tool_parser_authority_ledger"
PROMPT_TOOL_LEDGER_SCHEMA = "polisyos.runtime.PromptToolParserAuthorityLedger"
PROMPT_TOOL_LEDGER_REPORT_KEY = "prompt_tool_ledger"
PROMPT_TOOL_LEDGER_REF_KEY = "prompt_tool_ledger_ref"
PROMPT_TOOL_LEDGER_FILENAME = "prompt_tool_ledger.json"
REPAIR_FMEA_SURFACE_SCHEMA_VERSION = "policyos.runtime.prompt_tool_repair_fmea_surface.v1"
COMPRESSION_LOSS_SCHEMA_VERSION = "policyos.runtime.compression_loss_receipt.v1"
ORCHESTRATION_CHOICE_POLICY_CATALOG_SCHEMA_VERSION = (
    "policyos.runtime.orchestration_choice_policy_catalog.v1"
)
ORCHESTRATION_AUTHORITY_DELTA_SCHEMA_VERSION = (
    "policyos.runtime.orchestration_authority_delta.v1"
)
_POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[4]
_ORCHESTRATION_CHOICE_POLICY_RELATIVE_PATH = Path(
    "architecture/production_quality/orchestration_choice_policies.toml"
)
_ORCHESTRATION_CHOICE_POLICY_PATH = (
    _POLICY_ENGINE_ROOT / _ORCHESTRATION_CHOICE_POLICY_RELATIVE_PATH
)
_ORCHESTRATION_CHOICE_POLICY_OWNER = "team-runtime-quality"
_COMPRESSION_MAY_NOT_USE_FOR = (
    "claim_authority",
    "evidence_authority",
    "policy_recommendation",
    "publication_authority",
    "scorecard_authority",
    "closeout_authority",
)

AuthorityScope = Literal["evidence", "claims", "scorecard", "approval"]
ValidationStatus = Literal["pass", "fail", "warn", "blocked", "not_applicable"]
RepairDecisionStatus = Literal["applied", "rejected", "not_applicable"]
ToolCallStatus = Literal["pass", "fail", "blocked", "skipped"]
RepairFailureMode = Literal[
    "parser_contract_repair",
    "tool_output_repair",
    "schema_healing",
    "operator_workaround",
    "authority_handoff_repair",
    "unknown",
]

AUTHORITY_SCOPES: tuple[AuthorityScope, ...] = (
    "evidence",
    "claims",
    "scorecard",
    "approval",
)
_PASS_STATUSES = {"pass", "not_applicable"}


class PromptToolLedgerError(ValueError):
    """Typed prompt/tool/parser authority invariant violation."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


class OrchestrationChoicePolicy(BaseModel):
    """Owner policy for one data-declared orchestration choice kind."""

    model_config = ConfigDict(extra="forbid")

    choice_kind: str = Field(min_length=1)
    decision_policy_ref: str = Field(min_length=1)
    authority_effect: str = Field(min_length=1)
    governance_burden_change_allowed: bool = False
    policy_owner: str = _ORCHESTRATION_CHOICE_POLICY_OWNER
    approval_owner: str = _ORCHESTRATION_CHOICE_POLICY_OWNER
    policy_fingerprint: str | None = None
    authoritative_for: tuple[str, ...] = Field(default=())

    @field_validator(
        "choice_kind",
        "decision_policy_ref",
        "authority_effect",
        "policy_owner",
        "approval_owner",
    )
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)

    @model_validator(mode="after")
    def _bind_owner_policy(self) -> OrchestrationChoicePolicy:
        if self.policy_owner != _ORCHESTRATION_CHOICE_POLICY_OWNER:
            raise ValueError("orchestration choice policy owner is not canonical")
        if self.approval_owner != _ORCHESTRATION_CHOICE_POLICY_OWNER:
            raise ValueError("orchestration choice approval owner is not canonical")
        if self.authoritative_for:
            raise ValueError("orchestration choice policies cannot grant authority")
        expected = _fingerprint(
            {
                "choice_kind": self.choice_kind,
                "decision_policy_ref": self.decision_policy_ref,
                "authority_effect": self.authority_effect,
                "governance_burden_change_allowed": (
                    self.governance_burden_change_allowed
                ),
                "policy_owner": self.policy_owner,
                "approval_owner": self.approval_owner,
                "authoritative_for": [],
            }
        )
        if self.policy_fingerprint is not None and self.policy_fingerprint != expected:
            raise ValueError("orchestration choice policy fingerprint mismatch")
        self.policy_fingerprint = expected
        return self


class OrchestrationChoiceContext(BaseModel):
    """Runtime-derived candidate partition for one orchestration choice."""

    model_config = ConfigDict(extra="forbid")

    choice_id: str = Field(min_length=1)
    choice_kind: str = Field(min_length=1)
    candidate_universe: tuple[str, ...]
    selected: tuple[str, ...] = Field(default=())
    rejected: tuple[str, ...] = Field(default=())
    governance_burden_before: tuple[str, ...] = Field(default=())
    governance_burden_after: tuple[str, ...] = Field(default=())
    source_refs: tuple[str, ...] = Field(default=())

    @field_validator("choice_id", "choice_kind")
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "candidate_universe",
        "selected",
        "rejected",
        "governance_burden_before",
        "governance_burden_after",
        "source_refs",
    )
    @classmethod
    def _validate_identity_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_identity_tuple(values)


class OrchestrationAuthorityDelta(BaseModel):
    """Typed non-authoritative effect of one owner-validated choice."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = ORCHESTRATION_AUTHORITY_DELTA_SCHEMA_VERSION
    delta_id: str = Field(min_length=1)
    choice_id: str = Field(min_length=1)
    choice_kind: str = Field(min_length=1)
    candidate_universe: tuple[str, ...]
    selected: tuple[str, ...] = Field(default=())
    rejected: tuple[str, ...] = Field(default=())
    decision_policy_ref: str = Field(min_length=1)
    decision_policy_owner: str = _ORCHESTRATION_CHOICE_POLICY_OWNER
    owner_policy_fingerprint: str = Field(min_length=1)
    decision_context_fingerprint: str = Field(min_length=1)
    authority_effect: str = Field(min_length=1)
    governance_burden_before: tuple[str, ...] = Field(default=())
    governance_burden_after: tuple[str, ...] = Field(default=())
    governance_burden_change_allowed: bool = False
    predicate_provenance: Literal["recomputed"] = "recomputed"
    authoritative_for: tuple[str, ...] = Field(default=())

    @field_validator(
        "delta_id",
        "choice_id",
        "choice_kind",
        "decision_policy_ref",
        "decision_policy_owner",
        "owner_policy_fingerprint",
        "decision_context_fingerprint",
        "authority_effect",
    )
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "candidate_universe",
        "selected",
        "rejected",
        "governance_burden_before",
        "governance_burden_after",
    )
    @classmethod
    def _validate_identity_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_identity_tuple(values)

    @model_validator(mode="after")
    def _validate_non_authoritative_partition(self) -> OrchestrationAuthorityDelta:
        if self.schema_version != ORCHESTRATION_AUTHORITY_DELTA_SCHEMA_VERSION:
            raise ValueError("unsupported orchestration authority-delta schema")
        if _choice_partition_issue(self) is not None:
            raise ValueError("orchestration choice candidate partition is invalid")
        if self.authoritative_for:
            raise ValueError("orchestration authority deltas cannot grant authority")
        return self


class OrchestrationAuthorityDeltaCompletenessReceipt(BaseModel):
    """Owner-reconciled full-denominator authority-delta completeness result."""

    model_config = ConfigDict(extra="forbid")

    receipt_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    owner_policy_count: int = Field(ge=0)
    observed_choice_count: int = Field(ge=0)
    emitted_delta_count: int = Field(ge=0)
    owner_choice_kinds: tuple[str, ...] = Field(default=())
    observed_choice_kinds: tuple[str, ...] = Field(default=())
    emitted_choice_kinds: tuple[str, ...] = Field(default=())
    owner_policy_catalog_ref: str = Field(min_length=1)
    owner_policy_catalog_fingerprint: str = Field(min_length=1)
    observed_choice_population_fingerprint: str = Field(min_length=1)
    emitted_delta_population_fingerprint: str = Field(min_length=1)
    predicate_provenance: Literal["independently_reconciled"] = (
        "independently_reconciled"
    )
    decisive_property: Literal[
        "owner_validated_full_choice_population_and_exact_candidate_partition"
    ] = "owner_validated_full_choice_population_and_exact_candidate_partition"
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=())

    @model_validator(mode="after")
    def _validate_receipt_boundary(self) -> OrchestrationAuthorityDeltaCompletenessReceipt:
        if self.authoritative_for:
            raise ValueError("authority-delta completeness cannot grant authority")
        if self.status == "pass" and self.issue_codes:
            raise ValueError("passing authority-delta completeness cannot carry issues")
        if self.status == "fail" and not self.issue_codes:
            raise ValueError("failing authority-delta completeness requires issues")
        return self


class OrchestrationAuthorityDeltaDerivation(BaseModel):
    """Owner derivation of deltas plus its full-denominator receipt."""

    model_config = ConfigDict(extra="forbid")

    deltas: tuple[OrchestrationAuthorityDelta, ...] = Field(default=())
    completeness: OrchestrationAuthorityDeltaCompletenessReceipt


class CompressionMaterialItem(BaseModel):
    """Content-bound semantic item considered by compression."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(default=())
    item_fingerprint: str | None = None

    @field_validator("item_id", "content")
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("source_refs")
    @classmethod
    def _clean_source_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_identity_tuple(values)

    @model_validator(mode="after")
    def _bind_item_content(self) -> CompressionMaterialItem:
        expected = _fingerprint(self.model_dump(exclude={"item_fingerprint"}))
        if self.item_fingerprint is not None and self.item_fingerprint != expected:
            raise ValueError("compression material fingerprint mismatch")
        self.item_fingerprint = expected
        return self


class CompressionClaimItem(CompressionMaterialItem):
    """Claim item with use-relative presentation semantics."""

    claim_kind: Literal[
        "substantive",
        "procedural_binding",
        "negative_terminal",
        "constitutive_step",
        "delta",
    ] = "substantive"
    presentation_scope: Literal["bounded", "broad_consensus"] = "bounded"
    evidence_independence_ref: str | None = None
    basis_refs: tuple[str, ...] = Field(default=())

    @field_validator("evidence_independence_ref")
    @classmethod
    def _clean_optional_ref(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("basis_refs")
    @classmethod
    def _clean_basis_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_identity_tuple(values)


class CompressionMaterialSet(BaseModel):
    """Structured source or candidate-summary semantics for compression."""

    model_config = ConfigDict(extra="forbid")

    claims: tuple[CompressionClaimItem, ...] = Field(default=())
    limitations: tuple[CompressionMaterialItem, ...] = Field(default=())
    denied_uses: tuple[CompressionMaterialItem, ...] = Field(default=())
    counterevidence: tuple[CompressionMaterialItem, ...] = Field(default=())
    governance_burden_refs: tuple[str, ...] = Field(default=())
    framing_refs: tuple[str, ...] = Field(default=())
    material_fingerprint: str | None = None

    @field_validator("governance_burden_refs", "framing_refs")
    @classmethod
    def _clean_semantic_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_identity_tuple(values)

    @model_validator(mode="after")
    def _bind_material_content(self) -> CompressionMaterialSet:
        item_ids = [
            item.item_id
            for items in (
                self.claims,
                self.limitations,
                self.denied_uses,
                self.counterevidence,
            )
            for item in items
        ]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("compression material item ids must be unique")
        expected = _fingerprint(self.model_dump(exclude={"material_fingerprint"}))
        if self.material_fingerprint is not None and self.material_fingerprint != expected:
            raise ValueError("compression material-set fingerprint mismatch")
        self.material_fingerprint = expected
        return self


class CompressionEvidenceIndependenceBasis(BaseModel):
    """Pinned inputs used to rebuild one evidence-independence map exactly."""

    model_config = ConfigDict(extra="forbid")

    independence_map: dict[str, Any]
    evidence_lines: tuple[dict[str, Any], ...]
    portfolio_designs: tuple[dict[str, Any], ...]
    method_consensus_reports: tuple[dict[str, Any], ...] = Field(default=())
    method_equivalence_reports: tuple[dict[str, Any], ...] = Field(default=())
    feature_flags: dict[str, bool] | None = None
    graded_independence_config: dict[str, Any] | None = None
    rare_domain_context: dict[str, Any] | None = None
    producer_execution_started_at: str | datetime


class CompressionDroppedItemDisposition(BaseModel):
    """Canonical authority effect for one dropped source item."""

    model_config = ConfigDict(extra="forbid")

    item_ref: str = Field(min_length=1)
    category: Literal["claims", "limitations", "denied_uses", "counterevidence"]
    reason_code: str = Field(min_length=1)
    authority_effect: Literal["authority_reduced", "material_omission_blocks_summary"]


class CompressionTerminalResult(BaseModel):
    """Completed governed refusal emitted instead of an unsafe clean summary."""

    model_config = ConfigDict(extra="forbid")

    result_kind: Literal["governed_refusal"] = "governed_refusal"
    refusal_scope: Literal["premise_relative"] = "premise_relative"
    issue_codes: tuple[str, ...]
    retained_limitations: tuple[str, ...] = Field(default=())
    retained_denied_uses: tuple[str, ...] = Field(default=())


class CompressionLossReceipt(BaseModel):
    """Typed retained-versus-dropped semantics for one compression act."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = COMPRESSION_LOSS_SCHEMA_VERSION
    receipt_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    summary_ref: str = Field(min_length=1)
    source_material: CompressionMaterialSet
    candidate_summary: CompressionMaterialSet
    source_fingerprint: str = Field(min_length=1)
    candidate_summary_fingerprint: str = Field(min_length=1)
    status: Literal["pass", "blocked"]
    disposition: Literal["exact", "lossy_but_safe", "blocked_material_omission"]
    summary_reconstruction: Literal["exact", "proved_conservative", "not_established"]
    emitted_summary: CompressionMaterialSet | None = None
    terminal_result: CompressionTerminalResult | None = None
    retained_claims: tuple[str, ...] = Field(default=())
    dropped_claims: tuple[str, ...] = Field(default=())
    retained_limitations: tuple[str, ...] = Field(default=())
    dropped_limitations: tuple[str, ...] = Field(default=())
    retained_denied_uses: tuple[str, ...] = Field(default=())
    dropped_denied_uses: tuple[str, ...] = Field(default=())
    retained_counterevidence: tuple[str, ...] = Field(default=())
    dropped_counterevidence: tuple[str, ...] = Field(default=())
    introduced_summary_items: tuple[str, ...] = Field(default=())
    dropped_item_dispositions: tuple[CompressionDroppedItemDisposition, ...] = (
        Field(default=())
    )
    evidence_independence_status_by_claim: dict[str, str] = Field(default_factory=dict)
    authority_deltas: tuple[OrchestrationAuthorityDelta, ...] = Field(default=())
    authority_delta_completeness: (
        OrchestrationAuthorityDeltaCompletenessReceipt | None
    ) = None
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = _COMPRESSION_MAY_NOT_USE_FOR

    @model_validator(mode="after")
    def _validate_receipt_semantics(self) -> CompressionLossReceipt:
        if self.schema_version != COMPRESSION_LOSS_SCHEMA_VERSION:
            raise ValueError("unsupported compression-loss receipt schema")
        if self.authoritative_for:
            raise ValueError("compression-loss receipts cannot grant authority")
        if self.source_fingerprint != self.source_material.material_fingerprint:
            raise ValueError("compression source fingerprint mismatch")
        if (
            self.candidate_summary_fingerprint
            != self.candidate_summary.material_fingerprint
        ):
            raise ValueError("compression candidate-summary fingerprint mismatch")
        if self.status == "pass":
            if self.issue_codes or self.emitted_summary is None or self.terminal_result:
                raise ValueError("passing compression receipt must emit only a clean summary")
        elif self.emitted_summary is not None or self.terminal_result is None:
            raise ValueError("blocked compression receipt must emit a governed refusal")
        return self


def load_orchestration_choice_policies() -> tuple[OrchestrationChoicePolicy, ...]:
    """Load the fixed owner policy catalog for orchestration choices."""

    try:
        document = tomllib.loads(
            _ORCHESTRATION_CHOICE_POLICY_PATH.read_text(encoding="utf-8")
        )
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PromptToolLedgerError(
            "orchestration_choice_owner_policy_unavailable",
            "The canonical orchestration-choice policy catalog is unavailable.",
        ) from exc
    if document.get("schema_version") != ORCHESTRATION_CHOICE_POLICY_CATALOG_SCHEMA_VERSION:
        raise PromptToolLedgerError(
            "orchestration_choice_owner_policy_invalid",
            "The orchestration-choice policy catalog schema is not supported.",
        )
    owner = _optional_text(document.get("owner"))
    approval_owner = _optional_text(document.get("approval_owner"))
    if (
        owner != _ORCHESTRATION_CHOICE_POLICY_OWNER
        or approval_owner != _ORCHESTRATION_CHOICE_POLICY_OWNER
    ):
        raise PromptToolLedgerError(
            "orchestration_choice_owner_policy_invalid",
            "The orchestration-choice policy catalog is not owner-bound.",
        )
    raw_rows = document.get("choice_policy")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise PromptToolLedgerError(
            "orchestration_choice_owner_policy_invalid",
            "The orchestration-choice policy catalog has no choice population.",
        )
    try:
        policies = tuple(
            OrchestrationChoicePolicy.model_validate(
                {
                    **dict(row),
                    "policy_owner": owner,
                    "approval_owner": approval_owner,
                }
            )
            for row in raw_rows
            if isinstance(row, Mapping)
        )
    except ValidationError as exc:
        raise PromptToolLedgerError(
            "orchestration_choice_owner_policy_invalid",
            "The orchestration-choice policy catalog contains an invalid row.",
        ) from exc
    kinds = [policy.choice_kind for policy in policies]
    if len(policies) != len(raw_rows) or len(kinds) != len(set(kinds)):
        raise PromptToolLedgerError(
            "orchestration_choice_owner_policy_invalid",
            "The orchestration-choice policy population must be complete and unique.",
        )
    return policies


def build_orchestration_authority_deltas(
    contexts: Iterable[OrchestrationChoiceContext | Mapping[str, Any]],
) -> OrchestrationAuthorityDeltaDerivation:
    """Derive non-authoritative deltas over the complete owner choice population."""

    context_rows, parse_issues = _coerce_choice_contexts(contexts)
    policies = load_orchestration_choice_policies()
    policy_by_kind = {policy.choice_kind: policy for policy in policies}
    duplicate_kinds = _duplicates(context.choice_kind for context in context_rows)
    duplicate_ids = _duplicates(context.choice_id for context in context_rows)
    deltas: list[OrchestrationAuthorityDelta] = []
    for context in context_rows:
        policy = policy_by_kind.get(context.choice_kind)
        if (
            policy is None
            or context.choice_kind in duplicate_kinds
            or context.choice_id in duplicate_ids
            or _choice_partition_issue(context) is not None
        ):
            continue
        deltas.append(
            OrchestrationAuthorityDelta(
                delta_id=f"orchestration-authority-delta:{context.choice_id}",
                choice_id=context.choice_id,
                choice_kind=context.choice_kind,
                candidate_universe=context.candidate_universe,
                selected=context.selected,
                rejected=context.rejected,
                decision_policy_ref=policy.decision_policy_ref,
                decision_policy_owner=policy.policy_owner,
                owner_policy_fingerprint=str(policy.policy_fingerprint),
                decision_context_fingerprint=_choice_context_fingerprint(context),
                authority_effect=policy.authority_effect,
                governance_burden_before=context.governance_burden_before,
                governance_burden_after=context.governance_burden_after,
                governance_burden_change_allowed=(
                    policy.governance_burden_change_allowed
                ),
            )
        )
    completeness = _authority_delta_completeness_receipt(
        contexts=context_rows,
        deltas=tuple(deltas),
        policies=policies,
        extra_issue_codes=parse_issues,
    )
    return OrchestrationAuthorityDeltaDerivation(
        deltas=tuple(deltas),
        completeness=completeness,
    )


def validate_orchestration_authority_delta_completeness(
    *,
    contexts: Iterable[OrchestrationChoiceContext | Mapping[str, Any]],
    deltas: Iterable[OrchestrationAuthorityDelta | Mapping[str, Any]],
) -> OrchestrationAuthorityDeltaCompletenessReceipt:
    """Recompute the owner predicate over contexts and emitted deltas."""

    context_rows, context_issues = _coerce_choice_contexts(contexts)
    delta_rows, delta_issues = _coerce_authority_deltas(deltas)
    return _authority_delta_completeness_receipt(
        contexts=context_rows,
        deltas=delta_rows,
        policies=load_orchestration_choice_policies(),
        extra_issue_codes=(*context_issues, *delta_issues),
    )


def build_compression_loss_receipt(
    *,
    receipt_id: str,
    source_ref: str,
    summary_ref: str,
    source_material: CompressionMaterialSet | Mapping[str, Any],
    candidate_summary: CompressionMaterialSet | Mapping[str, Any],
    authority_deltas: Iterable[OrchestrationAuthorityDelta | Mapping[str, Any]] = (),
    authority_delta_completeness: (
        OrchestrationAuthorityDeltaCompletenessReceipt | Mapping[str, Any] | None
    ) = None,
    evidence_independence_bases: Mapping[
        str,
        CompressionEvidenceIndependenceBasis | Mapping[str, Any],
    ]
    | None = None,
) -> CompressionLossReceipt:
    """Recompute a use-relative conservative compression-loss receipt."""

    source = (
        source_material
        if isinstance(source_material, CompressionMaterialSet)
        else CompressionMaterialSet.model_validate(source_material)
    )
    summary = (
        candidate_summary
        if isinstance(candidate_summary, CompressionMaterialSet)
        else CompressionMaterialSet.model_validate(candidate_summary)
    )
    delta_rows, delta_parse_issues = _coerce_authority_deltas(authority_deltas)
    completeness = _coerce_authority_delta_completeness(
        authority_delta_completeness
    )
    policies = load_orchestration_choice_policies()
    policy_by_kind = {policy.choice_kind: policy for policy in policies}
    issues = list(delta_parse_issues)
    if delta_rows and completeness is None:
        issues.append("compression_authority_delta_completeness_missing")
    elif completeness is not None and not _completeness_matches_deltas(
        completeness,
        deltas=delta_rows,
        policies=policies,
    ):
        issues.append("compression_authority_delta_completeness_failed")
    for delta in delta_rows:
        if _authority_delta_owner_issue(delta, policy_by_kind) is not None:
            issues.append("orchestration_authority_delta_owner_validation_failed")

    partitions = {
        category: _compression_partition(
            getattr(source, category),
            getattr(summary, category),
        )
        for category in ("claims", "limitations", "denied_uses", "counterevidence")
    }
    retained_claims, dropped_claims, introduced_claims = partitions["claims"]
    retained_limitations, dropped_limitations, introduced_limitations = partitions[
        "limitations"
    ]
    retained_denied_uses, dropped_denied_uses, introduced_denied_uses = partitions[
        "denied_uses"
    ]
    (
        retained_counterevidence,
        dropped_counterevidence,
        introduced_counterevidence,
    ) = partitions["counterevidence"]
    introduced = (
        *introduced_claims,
        *introduced_limitations,
        *introduced_denied_uses,
        *introduced_counterevidence,
    )
    if dropped_limitations:
        issues.append("compression_retained_limitation_dropped")
    if dropped_denied_uses:
        issues.append("compression_denied_use_dropped")
    if dropped_counterevidence:
        issues.append("compression_counterevidence_dropped")
    if introduced:
        issues.append("compression_summary_authority_amplified")

    dropped_claim_refs = set(dropped_claims)
    for claim in source.claims:
        item_ref = _compression_item_ref(claim)
        if item_ref not in dropped_claim_refs:
            continue
        if claim.claim_kind == "negative_terminal":
            issues.append("compression_hidden_negative_terminal")
        elif claim.claim_kind == "constitutive_step":
            issues.append("compression_missing_constitutive_step")
    for claim in summary.claims:
        if claim.claim_kind == "delta" and not claim.basis_refs:
            issues.append("compression_bare_delta")

    independence_status_by_claim: dict[str, str] = {}
    bases = evidence_independence_bases or {}
    for claim in summary.claims:
        if claim.presentation_scope != "broad_consensus":
            continue
        basis_value = bases.get(str(claim.evidence_independence_ref or ""))
        try:
            status = _recomputed_independence_status(basis_value)
        except (EvidenceIndependenceError, PromptToolLedgerError, ValidationError):
            status = "not_established"
        independence_status_by_claim[claim.item_id] = status
        if status != "sufficient":
            issues.append("compression_broad_consensus_not_supported")

    burden_narrowed = bool(
        set(source.governance_burden_refs) - set(summary.governance_burden_refs)
    )
    if burden_narrowed and not any(
        _delta_records_governance_change(
            delta,
            source=source,
            summary=summary,
            policy_by_kind=policy_by_kind,
        )
        for delta in delta_rows
    ):
        issues.append("compression_governance_burden_narrowed_without_delta")

    issue_codes = tuple(dict.fromkeys(issues))
    dropped_dispositions = _dropped_item_dispositions(
        source=source,
        dropped_by_category={
            "claims": dropped_claims,
            "limitations": dropped_limitations,
            "denied_uses": dropped_denied_uses,
            "counterevidence": dropped_counterevidence,
        },
    )
    has_any_drop = any(
        (
            dropped_claims,
            dropped_limitations,
            dropped_denied_uses,
            dropped_counterevidence,
        )
    )
    status: Literal["pass", "blocked"] = "blocked" if issue_codes else "pass"
    disposition: Literal["exact", "lossy_but_safe", "blocked_material_omission"]
    if status == "blocked":
        disposition = "blocked_material_omission"
        reconstruction: Literal["exact", "proved_conservative", "not_established"] = (
            "not_established"
        )
    elif has_any_drop:
        disposition = "lossy_but_safe"
        reconstruction = "proved_conservative"
    else:
        disposition = "exact"
        reconstruction = "exact"
    all_source_limitations = tuple(item.content for item in source.limitations)
    all_source_denied_uses = tuple(item.content for item in source.denied_uses)
    terminal = (
        CompressionTerminalResult(
            issue_codes=issue_codes,
            retained_limitations=all_source_limitations,
            retained_denied_uses=all_source_denied_uses,
        )
        if status == "blocked"
        else None
    )
    return CompressionLossReceipt(
        receipt_id=receipt_id,
        source_ref=source_ref,
        summary_ref=summary_ref,
        source_material=source,
        candidate_summary=summary,
        source_fingerprint=str(source.material_fingerprint),
        candidate_summary_fingerprint=str(summary.material_fingerprint),
        status=status,
        disposition=disposition,
        summary_reconstruction=reconstruction,
        emitted_summary=summary if status == "pass" else None,
        terminal_result=terminal,
        retained_claims=retained_claims,
        dropped_claims=dropped_claims,
        retained_limitations=retained_limitations,
        dropped_limitations=dropped_limitations,
        retained_denied_uses=retained_denied_uses,
        dropped_denied_uses=dropped_denied_uses,
        retained_counterevidence=retained_counterevidence,
        dropped_counterevidence=dropped_counterevidence,
        introduced_summary_items=introduced,
        dropped_item_dispositions=dropped_dispositions,
        evidence_independence_status_by_claim=independence_status_by_claim,
        authority_deltas=delta_rows,
        authority_delta_completeness=completeness,
        issue_codes=issue_codes,
    )


def validate_compression_loss_receipt(
    receipt: CompressionLossReceipt | Mapping[str, Any],
    *,
    evidence_independence_bases: Mapping[
        str,
        CompressionEvidenceIndependenceBasis | Mapping[str, Any],
    ]
    | None = None,
) -> CompressionLossReceipt:
    """Recompute a receipt and reject any caller-authored disposition or status."""

    try:
        parsed = (
            receipt
            if isinstance(receipt, CompressionLossReceipt)
            else CompressionLossReceipt.model_validate(receipt)
        )
    except ValidationError as exc:
        raise PromptToolLedgerError(
            "compression_loss_receipt_owner_validation_failed"
        ) from exc
    recomputed = build_compression_loss_receipt(
        receipt_id=parsed.receipt_id,
        source_ref=parsed.source_ref,
        summary_ref=parsed.summary_ref,
        source_material=parsed.source_material,
        candidate_summary=parsed.candidate_summary,
        authority_deltas=parsed.authority_deltas,
        authority_delta_completeness=parsed.authority_delta_completeness,
        evidence_independence_bases=evidence_independence_bases,
    )
    if recomputed.model_dump(mode="json") != parsed.model_dump(mode="json"):
        raise PromptToolLedgerError("compression_loss_receipt_owner_validation_failed")
    return recomputed


def _coerce_choice_contexts(
    values: Iterable[OrchestrationChoiceContext | Mapping[str, Any]],
) -> tuple[tuple[OrchestrationChoiceContext, ...], tuple[str, ...]]:
    rows: list[OrchestrationChoiceContext] = []
    issues: list[str] = []
    for value in values:
        try:
            rows.append(
                value
                if isinstance(value, OrchestrationChoiceContext)
                else OrchestrationChoiceContext.model_validate(value)
            )
        except ValidationError:
            issues.append("orchestration_choice_context_invalid")
    return tuple(rows), tuple(dict.fromkeys(issues))


def _coerce_authority_deltas(
    values: Iterable[OrchestrationAuthorityDelta | Mapping[str, Any]],
) -> tuple[tuple[OrchestrationAuthorityDelta, ...], tuple[str, ...]]:
    rows: list[OrchestrationAuthorityDelta] = []
    issues: list[str] = []
    for value in values:
        try:
            rows.append(
                value
                if isinstance(value, OrchestrationAuthorityDelta)
                else OrchestrationAuthorityDelta.model_validate(value)
            )
        except ValidationError:
            issues.append("orchestration_authority_delta_owner_validation_failed")
    return tuple(rows), tuple(dict.fromkeys(issues))


def _coerce_authority_delta_completeness(
    value: OrchestrationAuthorityDeltaCompletenessReceipt | Mapping[str, Any] | None,
) -> OrchestrationAuthorityDeltaCompletenessReceipt | None:
    if value is None:
        return None
    if isinstance(value, OrchestrationAuthorityDeltaCompletenessReceipt):
        return value
    return OrchestrationAuthorityDeltaCompletenessReceipt.model_validate(value)


def _authority_delta_completeness_receipt(
    *,
    contexts: tuple[OrchestrationChoiceContext, ...],
    deltas: tuple[OrchestrationAuthorityDelta, ...],
    policies: tuple[OrchestrationChoicePolicy, ...],
    extra_issue_codes: Iterable[str] = (),
) -> OrchestrationAuthorityDeltaCompletenessReceipt:
    issues = list(extra_issue_codes)
    policy_by_kind = {policy.choice_kind: policy for policy in policies}
    context_by_id = {context.choice_id: context for context in contexts}
    owner_kinds = tuple(policy.choice_kind for policy in policies)
    observed_kinds = tuple(context.choice_kind for context in contexts)
    emitted_kinds = tuple(delta.choice_kind for delta in deltas)
    if _duplicates(observed_kinds) or _duplicates(context.choice_id for context in contexts):
        issues.append("orchestration_choice_population_duplicate")
    if set(observed_kinds) - set(owner_kinds):
        issues.append("orchestration_choice_kind_unowned")
    if set(owner_kinds) - set(observed_kinds):
        issues.append("orchestration_choice_owner_population_incomplete")
    if any(_choice_partition_issue(context) is not None for context in contexts):
        issues.append("orchestration_choice_candidate_partition_invalid")
    if _duplicates(delta.delta_id for delta in deltas) or _duplicates(
        delta.choice_id for delta in deltas
    ):
        issues.append("orchestration_authority_delta_population_duplicate")
    for delta in deltas:
        policy_issue = _authority_delta_owner_issue(delta, policy_by_kind)
        context = context_by_id.get(delta.choice_id)
        context_mismatch = (
            context is None
            or delta.choice_kind != context.choice_kind
            or delta.candidate_universe != context.candidate_universe
            or delta.selected != context.selected
            or delta.rejected != context.rejected
            or delta.governance_burden_before != context.governance_burden_before
            or delta.governance_burden_after != context.governance_burden_after
            or delta.decision_context_fingerprint
            != _choice_context_fingerprint(context)
        )
        if policy_issue is not None or context_mismatch:
            issues.append("orchestration_authority_delta_owner_validation_failed")
    if (
        len(deltas) != len(policies)
        or len(contexts) != len(policies)
        or set(emitted_kinds) != set(owner_kinds)
        or {delta.choice_id for delta in deltas} != set(context_by_id)
    ):
        issues.append("orchestration_authority_delta_population_incomplete")
    issue_codes = tuple(dict.fromkeys(issues))
    catalog_fingerprint = _owner_policy_catalog_fingerprint(policies)
    observed_fingerprint = _choice_population_fingerprint(contexts)
    emitted_fingerprint = _delta_population_fingerprint(deltas)
    receipt_fingerprint = _fingerprint(
        {
            "owner_policy_catalog_fingerprint": catalog_fingerprint,
            "observed_choice_population_fingerprint": observed_fingerprint,
            "emitted_delta_population_fingerprint": emitted_fingerprint,
        }
    )
    return OrchestrationAuthorityDeltaCompletenessReceipt(
        receipt_id=f"orchestration-authority-delta-completeness:{receipt_fingerprint}",
        status="fail" if issue_codes else "pass",
        owner_policy_count=len(policies),
        observed_choice_count=len(contexts),
        emitted_delta_count=len(deltas),
        owner_choice_kinds=owner_kinds,
        observed_choice_kinds=observed_kinds,
        emitted_choice_kinds=emitted_kinds,
        owner_policy_catalog_ref=(
            f"repo://{_ORCHESTRATION_CHOICE_POLICY_RELATIVE_PATH.as_posix()}"
        ),
        owner_policy_catalog_fingerprint=catalog_fingerprint,
        observed_choice_population_fingerprint=observed_fingerprint,
        emitted_delta_population_fingerprint=emitted_fingerprint,
        issue_codes=issue_codes,
    )


def _completeness_matches_deltas(
    completeness: OrchestrationAuthorityDeltaCompletenessReceipt,
    *,
    deltas: tuple[OrchestrationAuthorityDelta, ...],
    policies: tuple[OrchestrationChoicePolicy, ...],
) -> bool:
    owner_kinds = tuple(policy.choice_kind for policy in policies)
    emitted_kinds = tuple(delta.choice_kind for delta in deltas)
    return (
        completeness.status == "pass"
        and completeness.owner_policy_count == len(policies)
        and completeness.emitted_delta_count == len(deltas)
        and completeness.owner_choice_kinds == owner_kinds
        and completeness.emitted_choice_kinds == emitted_kinds
        and completeness.owner_policy_catalog_ref
        == f"repo://{_ORCHESTRATION_CHOICE_POLICY_RELATIVE_PATH.as_posix()}"
        and completeness.owner_policy_catalog_fingerprint
        == _owner_policy_catalog_fingerprint(policies)
        and completeness.emitted_delta_population_fingerprint
        == _delta_population_fingerprint(deltas)
    )


def _owner_policy_catalog_fingerprint(
    policies: tuple[OrchestrationChoicePolicy, ...],
) -> str:
    return _fingerprint([policy.model_dump(mode="json") for policy in policies])


def _choice_population_fingerprint(
    contexts: tuple[OrchestrationChoiceContext, ...],
) -> str:
    return _fingerprint([context.model_dump(mode="json") for context in contexts])


def _delta_population_fingerprint(
    deltas: tuple[OrchestrationAuthorityDelta, ...],
) -> str:
    return _fingerprint([delta.model_dump(mode="json") for delta in deltas])


def _authority_delta_owner_issue(
    delta: OrchestrationAuthorityDelta,
    policy_by_kind: Mapping[str, OrchestrationChoicePolicy],
) -> str | None:
    policy = policy_by_kind.get(delta.choice_kind)
    if policy is None:
        return "orchestration_choice_kind_unowned"
    if (
        delta.schema_version != ORCHESTRATION_AUTHORITY_DELTA_SCHEMA_VERSION
        or delta.decision_policy_ref != policy.decision_policy_ref
        or delta.decision_policy_owner != policy.policy_owner
        or delta.owner_policy_fingerprint != policy.policy_fingerprint
        or delta.authority_effect != policy.authority_effect
        or delta.governance_burden_change_allowed
        != policy.governance_burden_change_allowed
        or delta.predicate_provenance != "recomputed"
        or delta.authoritative_for
        or _choice_partition_issue(delta) is not None
    ):
        return "orchestration_authority_delta_owner_validation_failed"
    return None


def _choice_context_fingerprint(context: OrchestrationChoiceContext) -> str:
    return _fingerprint(context.model_dump(mode="json"))


def _choice_partition_issue(
    value: OrchestrationChoiceContext | OrchestrationAuthorityDelta,
) -> str | None:
    universe = value.candidate_universe
    selected = value.selected
    rejected = value.rejected
    if not universe:
        return "candidate_universe_empty"
    if (
        len(universe) != len(set(universe))
        or len(selected) != len(set(selected))
        or len(rejected) != len(set(rejected))
    ):
        return "candidate_identity_duplicate"
    if set(selected) & set(rejected):
        return "selected_rejected_overlap"
    if set(universe) != set(selected) | set(rejected):
        return "candidate_partition_incomplete"
    return None


def _compression_partition(
    source_items: Sequence[CompressionMaterialItem],
    summary_items: Sequence[CompressionMaterialItem],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    source_by_fingerprint = {
        str(item.item_fingerprint): item for item in source_items
    }
    summary_by_fingerprint = {
        str(item.item_fingerprint): item for item in summary_items
    }
    retained_fingerprints = set(source_by_fingerprint) & set(summary_by_fingerprint)
    dropped_fingerprints = set(source_by_fingerprint) - set(summary_by_fingerprint)
    introduced_fingerprints = set(summary_by_fingerprint) - set(source_by_fingerprint)
    return (
        tuple(
            _compression_item_ref(item)
            for fingerprint, item in source_by_fingerprint.items()
            if fingerprint in retained_fingerprints
        ),
        tuple(
            _compression_item_ref(item)
            for fingerprint, item in source_by_fingerprint.items()
            if fingerprint in dropped_fingerprints
        ),
        tuple(
            _compression_item_ref(item)
            for fingerprint, item in summary_by_fingerprint.items()
            if fingerprint in introduced_fingerprints
        ),
    )


def _compression_item_ref(item: CompressionMaterialItem) -> str:
    return f"{item.item_id}@{item.item_fingerprint}"


def _dropped_item_dispositions(
    *,
    source: CompressionMaterialSet,
    dropped_by_category: Mapping[str, tuple[str, ...]],
) -> tuple[CompressionDroppedItemDisposition, ...]:
    dispositions: list[CompressionDroppedItemDisposition] = []
    for category in ("claims", "limitations", "denied_uses", "counterevidence"):
        dropped = set(dropped_by_category[category])
        for item in getattr(source, category):
            item_ref = _compression_item_ref(item)
            if item_ref not in dropped:
                continue
            protected_claim = isinstance(item, CompressionClaimItem) and item.claim_kind in {
                "negative_terminal",
                "constitutive_step",
            }
            blocks = category != "claims" or protected_claim
            dispositions.append(
                CompressionDroppedItemDisposition(
                    item_ref=item_ref,
                    category=category,
                    reason_code=(
                        "material_omission_blocks_public_summary"
                        if blocks
                        else "claim_omitted_authority_reduced"
                    ),
                    authority_effect=(
                        "material_omission_blocks_summary"
                        if blocks
                        else "authority_reduced"
                    ),
                )
            )
    return tuple(dispositions)


def _recomputed_independence_status(
    value: CompressionEvidenceIndependenceBasis | Mapping[str, Any] | None,
) -> str:
    if value is None:
        raise PromptToolLedgerError("compression_independence_basis_missing")
    basis = (
        value
        if isinstance(value, CompressionEvidenceIndependenceBasis)
        else CompressionEvidenceIndependenceBasis.model_validate(value)
    )
    if not basis.evidence_lines or not basis.portfolio_designs:
        raise PromptToolLedgerError("compression_independence_basis_missing")
    source_map = dict(basis.independence_map)
    map_id = _optional_text(source_map.get("map_id"))
    if map_id is None:
        raise PromptToolLedgerError("compression_independence_basis_missing")
    rebuilt = build_evidence_independence_map(
        basis.evidence_lines,
        portfolio_designs=basis.portfolio_designs,
        method_consensus_reports=basis.method_consensus_reports,
        method_equivalence_reports=basis.method_equivalence_reports,
        feature_flags=basis.feature_flags,
        graded_independence_config=basis.graded_independence_config,
        rare_domain_context=basis.rare_domain_context,
        map_id=map_id,
        producer_execution_started_at=basis.producer_execution_started_at,
        evidence_ref=_optional_text(source_map.get("evidence_ref")),
        runtime_event_ref=_optional_text(source_map.get("runtime_event_ref")),
    )
    normalized_source = validate_evidence_independence_map_record(
        source_map,
        evidence_lines=basis.evidence_lines,
        portfolio_designs=basis.portfolio_designs,
        producer_execution_started_at=basis.producer_execution_started_at,
    )
    normalized_rebuilt = validate_evidence_independence_map_record(
        rebuilt,
        evidence_lines=basis.evidence_lines,
        portfolio_designs=basis.portfolio_designs,
        producer_execution_started_at=basis.producer_execution_started_at,
    )
    if _fingerprint(normalized_source) != _fingerprint(normalized_rebuilt):
        raise PromptToolLedgerError("compression_independence_reconstruction_mismatch")
    effective_mass = normalized_rebuilt.get("effective_mass_report")
    if not isinstance(effective_mass, Mapping):
        raise PromptToolLedgerError("compression_independence_basis_missing")
    return str(effective_mass.get("independence_status") or "not_established")


def _delta_records_governance_change(
    delta: OrchestrationAuthorityDelta,
    *,
    source: CompressionMaterialSet,
    summary: CompressionMaterialSet,
    policy_by_kind: Mapping[str, OrchestrationChoicePolicy],
) -> bool:
    return (
        _authority_delta_owner_issue(delta, policy_by_kind) is None
        and delta.governance_burden_change_allowed
        and delta.governance_burden_before == source.governance_burden_refs
        and delta.governance_burden_after == summary.governance_burden_refs
    )


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _unique_identity_tuple(values: Iterable[Any]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        text = _optional_text(value)
        if text is None:
            raise ValueError("identity values must be non-empty text")
        if text in result:
            raise ValueError("identity values must be unique")
        result.append(text)
    return tuple(result)


class PromptTemplateRecord(BaseModel):
    """Prompt/template identity and rendered input authority."""

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    template_ref: str | None = None
    rendered_prompt_ref: str | None = None
    rendered_input_refs: tuple[str, ...] = Field(default=())
    template_variables_fingerprint: str | None = None
    prompt_fingerprint: str | None = None

    @field_validator(
        "template_id",
        "template_version",
        "template_ref",
        "rendered_prompt_ref",
        "template_variables_fingerprint",
        "prompt_fingerprint",
    )
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("rendered_input_refs")
    @classmethod
    def _clean_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_ref_tuple(values)

    @model_validator(mode="after")
    def _fill_prompt_fingerprint(self) -> PromptTemplateRecord:
        if self.prompt_fingerprint is None:
            self.prompt_fingerprint = _fingerprint(
                {
                    "template_id": self.template_id,
                    "template_version": self.template_version,
                    "template_ref": self.template_ref,
                    "rendered_prompt_ref": self.rendered_prompt_ref,
                    "rendered_input_refs": list(self.rendered_input_refs),
                    "template_variables_fingerprint": self.template_variables_fingerprint,
                }
            )
        return self


class ModelProviderConfig(BaseModel):
    """Provider/model execution configuration for one model-assisted step."""

    model_config = ConfigDict(extra="allow")

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_fingerprint: str | None = None
    provider_config_ref: str | None = None
    temperature: float | None = None
    max_tokens: int | None = Field(default=None, ge=0)
    response_format: dict[str, Any] | None = None

    @field_validator("provider", "model", "model_fingerprint", "provider_config_ref")
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)


class ToolSchemaRecord(BaseModel):
    """Allowlisted tool schema identity for one callable tool."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tool_name: str = Field(min_length=1)
    schema_ref: str | None = None
    json_schema: dict[str, Any] | None = Field(default=None, alias="schema")
    schema_fingerprint: str | None = None

    @field_validator("tool_name", "schema_ref", "schema_fingerprint")
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _fill_schema_fingerprint(self) -> ToolSchemaRecord:
        if self.schema_fingerprint is None:
            if self.json_schema is None and self.schema_ref is None:
                raise ValueError("tool schema requires schema_ref, schema, or schema_fingerprint")
            self.schema_fingerprint = _fingerprint(
                {
                    "tool_name": self.tool_name,
                    "schema_ref": self.schema_ref,
                    "schema": self.json_schema,
                }
            )
        return self


class ToolCallRecord(BaseModel):
    """One model-requested tool call and its persisted result refs."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1)
    call_ref: str = Field(min_length=1)
    output_ref: str | None = None
    rejection_ref: str | None = None
    status: ToolCallStatus = "pass"

    @field_validator("tool_name", "call_ref", "output_ref", "rejection_ref")
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _require_result_ref(self) -> ToolCallRecord:
        if self.status == "pass" and self.output_ref is None:
            raise ValueError("passing tool calls require output_ref")
        if self.status in {"blocked", "fail"} and self.rejection_ref is None:
            raise ValueError("blocked or failed tool calls require rejection_ref")
        return self


class ParserContract(BaseModel):
    """Parser contract used to turn model output into runtime artifacts."""

    model_config = ConfigDict(extra="forbid")

    parser_id: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    contract_ref: str = Field(min_length=1)
    input_schema_ref: str = Field(min_length=1)
    output_schema_ref: str = Field(min_length=1)

    @field_validator(
        "parser_id",
        "parser_version",
        "contract_ref",
        "input_schema_ref",
        "output_schema_ref",
    )
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)


class ValidationRef(BaseModel):
    """Validation artifact that proves parser/output contract status."""

    model_config = ConfigDict(extra="forbid")

    validator_id: str = Field(min_length=1)
    status: ValidationStatus
    validation_ref: str = Field(min_length=1)

    @field_validator("validator_id", "validation_ref")
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)


class RepairDecisionFMEAAnnotation(BaseModel):
    """FMEA-style risk annotation for one repair decision."""

    model_config = ConfigDict(extra="forbid")

    failure_mode: RepairFailureMode = "unknown"
    severity: int = Field(ge=1, le=10)
    cause: str = Field(min_length=1)
    recommended_mitigation: str = Field(min_length=1)
    residual_risk: str = Field(min_length=1)
    occurrence: int = Field(ge=1, le=10)
    detectability: int = Field(ge=1, le=10)
    risk_priority_number: int | None = Field(default=None, ge=1, le=1000)
    owner: str = Field(min_length=1)
    controls: tuple[str, ...] = Field(default=())
    evidence_ref: str | None = None
    authority_effect: Literal[
        "accepted_mitigation",
        "authority_blocked",
        "candidate_only",
        "advisory",
    ] = "accepted_mitigation"

    @field_validator(
        "cause",
        "recommended_mitigation",
        "residual_risk",
        "owner",
        "evidence_ref",
    )
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("controls")
    @classmethod
    def _clean_controls(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        controls = tuple(_clean_refs(values))
        if not controls:
            raise ValueError("repair FMEA annotations require mitigation controls")
        return controls

    @model_validator(mode="after")
    def _fill_risk_priority_number(self) -> RepairDecisionFMEAAnnotation:
        expected = self.severity * self.occurrence * self.detectability
        if self.risk_priority_number is None:
            self.risk_priority_number = expected
        return self


class RepairDecision(BaseModel):
    """Recorded repair or healing decision for prompt/parser/tool output."""

    model_config = ConfigDict(extra="forbid")

    decision: str = Field(min_length=1)
    status: RepairDecisionStatus
    reason: str = Field(min_length=1)
    repair_ref: str | None = None
    approved_by: str | None = None
    fmea_annotation: RepairDecisionFMEAAnnotation | None = None

    @field_validator("decision", "reason", "repair_ref", "approved_by")
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _require_applied_ref(self) -> RepairDecision:
        if self.status == "applied" and self.repair_ref is None:
            raise ValueError("applied repair decisions require repair_ref")
        return self


class AuthorityHandoffRef(BaseModel):
    """Consumer handoff proving where model-assisted output became authority."""

    model_config = ConfigDict(extra="forbid")

    scope: AuthorityScope
    handoff_ref: str = Field(min_length=1)
    consumer: str = Field(min_length=1)
    status: ValidationStatus = "pass"

    @field_validator("handoff_ref", "consumer")
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)


class PromptToolLedgerFinding(BaseModel):
    """Operator-facing prompt/tool symptom classification."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    severity: Literal["info", "warn", "fail"] = "warn"
    failure_reason: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    validator_ref: str = Field(min_length=1)
    upstream_spine_blocker_refs: tuple[str, ...] = Field(default=())

    @field_validator("code", "failure_reason", "step_id", "validator_ref")
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("upstream_spine_blocker_refs")
    @classmethod
    def _clean_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_ref_tuple(values)


class ModelAssistedStepLedger(BaseModel):
    """One model-assisted step that can influence runtime authority."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    step_kind: str = Field(min_length=1)
    authority_scopes: tuple[AuthorityScope, ...]
    prompt: PromptTemplateRecord
    model_provider: ModelProviderConfig
    tool_allowlist: tuple[str, ...] = Field(default=())
    tool_schemas: tuple[ToolSchemaRecord, ...] = Field(default=())
    tool_call_refs: tuple[ToolCallRecord, ...] = Field(default=())
    output_refs: tuple[str, ...]
    parser_contract: ParserContract
    validation_refs: tuple[ValidationRef, ...]
    repair_decisions: tuple[RepairDecision, ...] = Field(default=())
    authority_handoff_refs: tuple[AuthorityHandoffRef, ...]

    @field_validator("step_id", "step_kind")
    @classmethod
    def _clean_text_field(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator("tool_allowlist", "output_refs")
    @classmethod
    def _clean_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_ref_tuple(values)

    @field_validator("authority_scopes")
    @classmethod
    def _require_authority_scope(
        cls,
        values: tuple[AuthorityScope, ...],
    ) -> tuple[AuthorityScope, ...]:
        if not values:
            raise ValueError("model-assisted steps require at least one authority scope")
        return tuple(dict.fromkeys(values))

    @model_validator(mode="after")
    def _validate_authority_materials(self) -> ModelAssistedStepLedger:
        allowlist = set(self.tool_allowlist)
        schema_tools = {schema.tool_name for schema in self.tool_schemas}
        if allowlist and not allowlist <= schema_tools:
            missing = sorted(allowlist - schema_tools)
            raise ValueError("tool_allowlist missing schemas: " + ", ".join(missing))
        for call in self.tool_call_refs:
            if call.tool_name not in allowlist:
                raise ValueError(f"tool call not in allowlist: {call.tool_name}")
            if call.tool_name not in schema_tools:
                raise ValueError(f"tool call missing schema: {call.tool_name}")
        if not self.prompt.rendered_input_refs:
            raise ValueError("authority steps require rendered_input_refs")
        if not self.output_refs:
            raise ValueError("authority steps require output_refs")
        if not self.validation_refs:
            raise ValueError("authority steps require validation_refs")
        if not self.authority_handoff_refs:
            raise ValueError("authority steps require authority_handoff_refs")
        return self


class PromptToolParserAuthorityLedger(BaseModel):
    """Durable authority ledger for prompt/tool/parser mediated runtime outputs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    model_variant_id: str | None = None
    prompt_tool_ledger_ref: str | None = None
    steps: tuple[ModelAssistedStepLedger, ...]
    orchestration_authority_deltas: tuple[OrchestrationAuthorityDelta, ...] = Field(
        default=()
    )
    authority_delta_completeness_receipts: tuple[
        OrchestrationAuthorityDeltaCompletenessReceipt, ...
    ] = Field(default=())
    compression_loss_receipts: tuple[CompressionLossReceipt, ...] = Field(default=())
    findings: tuple[PromptToolLedgerFinding, ...] = Field(default=())
    summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def _require_schema_version(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported prompt/tool/parser ledger schema: {value}")
        return value

    @field_validator("run_id", "job_id", "model_variant_id", "prompt_tool_ledger_ref")
    @classmethod
    def _clean_text_field(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("steps")
    @classmethod
    def _require_steps(
        cls,
        values: tuple[ModelAssistedStepLedger, ...],
    ) -> tuple[ModelAssistedStepLedger, ...]:
        if not values:
            raise ValueError("prompt/tool/parser ledger requires at least one step")
        return values

    @model_validator(mode="after")
    def _fill_summary(self) -> PromptToolParserAuthorityLedger:
        scopes = sorted({scope for step in self.steps for scope in step.authority_scopes})
        tool_names = sorted({tool for step in self.steps for tool in step.tool_allowlist})
        repair_count = sum(len(step.repair_decisions) for step in self.steps)
        repair_annotations = [
            decision.fmea_annotation
            for step in self.steps
            for decision in step.repair_decisions
            if decision.fmea_annotation is not None
        ]
        unannotated_repairs = [
            decision
            for step in self.steps
            for decision in step.repair_decisions
            if decision.fmea_annotation is None
        ]
        repair_rpns = [
            int(annotation.risk_priority_number)
            for annotation in repair_annotations
            if annotation.risk_priority_number is not None
        ]
        status = (
            "pass"
            if self._has_required_authority_scopes(AUTHORITY_SCOPES)
            and self._steps_have_passing_validation()
            else "fail"
        )
        self.summary = {
            **dict(self.summary or {}),
            "status": status,
            "step_count": len(self.steps),
            "authority_scopes": scopes,
            "tool_count": len(tool_names),
            "tool_names": tool_names,
            "repair_decision_count": repair_count,
            "repair_fmea_annotation_count": len(repair_annotations),
            "repair_fmea_unannotated_count": len(unannotated_repairs),
            "repair_fmea_max_rpn": max(repair_rpns) if repair_rpns else None,
            "repair_fmea_machinery_failure_count": sum(
                1
                for step in self.steps
                for decision in step.repair_decisions
                if decision.status != "not_applicable"
                and decision.fmea_annotation is not None
            ),
            "orchestration_authority_delta_count": len(
                self.orchestration_authority_deltas
            ),
            "authority_delta_completeness_receipt_count": len(
                self.authority_delta_completeness_receipts
            ),
            "compression_loss_receipt_count": len(self.compression_loss_receipts),
            "blocked_compression_loss_receipt_count": sum(
                receipt.status == "blocked"
                for receipt in self.compression_loss_receipts
            ),
            "finding_count": len(self.findings),
            "upstream_spine_blocker_refs": sorted(
                {
                    ref
                    for finding in self.findings
                    for ref in finding.upstream_spine_blocker_refs
                }
            ),
        }
        if unannotated_repairs:
            self.summary["status"] = "fail"
        if self.orchestration_authority_deltas and (
            not self.authority_delta_completeness_receipts
            or any(
                receipt.status != "pass"
                for receipt in self.authority_delta_completeness_receipts
            )
        ):
            self.summary["status"] = "fail"
        if self.compression_loss_receipts and (
            not self.orchestration_authority_deltas
            or any(receipt.status != "pass" for receipt in self.compression_loss_receipts)
        ):
            self.summary["status"] = "fail"
        return self

    def _has_required_authority_scopes(self, scopes: Sequence[str]) -> bool:
        present = {scope for step in self.steps for scope in step.authority_scopes}
        return set(scopes) <= present

    def _steps_have_passing_validation(self) -> bool:
        return all(
            any(ref.status in _PASS_STATUSES for ref in step.validation_refs)
            and any(handoff.status in _PASS_STATUSES for handoff in step.authority_handoff_refs)
            for step in self.steps
        )


@dataclass(frozen=True)
class PromptToolParserAuthorityValidation:
    """Scorecard-friendly validation result for prompt/tool/parser authority."""

    satisfied: bool
    missing_codes: tuple[str, ...]
    step_count: int
    authority_scopes: tuple[str, ...]


def validate_prompt_tool_parser_authority(
    payload: PromptToolParserAuthorityLedger | Mapping[str, Any] | None,
    *,
    required_scopes: Sequence[str] = AUTHORITY_SCOPES,
) -> PromptToolParserAuthorityValidation:
    """Validate a ledger as authority for prompt/tool/parser mediated outputs."""

    if payload is None:
        return PromptToolParserAuthorityValidation(
            satisfied=False,
            missing_codes=("prompt_tool_parser_authority_ledger_missing",),
            step_count=0,
            authority_scopes=(),
        )
    try:
        ledger = (
            payload
            if isinstance(payload, PromptToolParserAuthorityLedger)
            else PromptToolParserAuthorityLedger.model_validate(payload)
        )
    except ValidationError:
        return PromptToolParserAuthorityValidation(
            satisfied=False,
            missing_codes=("prompt_tool_parser_authority_ledger_invalid",),
            step_count=0,
            authority_scopes=(),
        )

    scopes = tuple(sorted({scope for step in ledger.steps for scope in step.authority_scopes}))
    missing = tuple(
        f"prompt_tool_parser_{scope}_handoff_missing"
        for scope in required_scopes
        if scope not in scopes
    )
    status = str(ledger.summary.get("status") or "").casefold()
    unannotated_count = _int_or_zero(ledger.summary.get("repair_fmea_unannotated_count"))
    if unannotated_count > 0:
        missing = (*missing, "prompt_tool_repair_fmea_refs_missing")
    if status not in {"pass", "ok", "passed"}:
        missing = (*missing, "prompt_tool_parser_authority_ledger_not_passing")
    return PromptToolParserAuthorityValidation(
        satisfied=not missing,
        missing_codes=missing,
        step_count=len(ledger.steps),
        authority_scopes=scopes,
    )


def serialize_prompt_tool_ledger(
    ledger: PromptToolParserAuthorityLedger | Mapping[str, Any],
) -> dict[str, Any]:
    """Return JSON-compatible prompt/tool/parser ledger payload."""

    parsed = (
        ledger
        if isinstance(ledger, PromptToolParserAuthorityLedger)
        else PromptToolParserAuthorityLedger.model_validate(ledger)
    )
    return parsed.model_dump(mode="json", exclude_none=True, by_alias=True)


def persist_runtime_quality_json_artifact(
    *,
    payload: object,
    store: Any,
    kind: str,
    schema_name: str,
    schema_version: str = "1.0",
    inputs: Iterable[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a runtime-quality JSON artifact with canonical CAS metadata."""

    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def persist_prompt_tool_ledger(
    ledger: PromptToolParserAuthorityLedger | Mapping[str, Any],
    *,
    store: Any,
    inputs: Iterable[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a prompt/tool/parser authority ledger in CAS and return its ref."""

    payload = serialize_prompt_tool_ledger(ledger)
    return persist_runtime_quality_json_artifact(
        payload=payload,
        store=store,
        kind=PROMPT_TOOL_LEDGER_KIND,
        schema_name=PROMPT_TOOL_LEDGER_SCHEMA,
        inputs=inputs,
    )


def prompt_tool_repair_machinery_failures(
    ledger: PromptToolParserAuthorityLedger | Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Project repair decisions as operator-visible machinery failures.

    Args:
        ledger: Prompt/tool/parser authority ledger.

    Returns:
        Non-not-applicable repair decisions with W10.F FMEA refs, suitable for
        scorecard, dashboard, operator, and closeout reader surfaces.
    """

    parsed = _coerce_ledger(ledger)
    if parsed is None:
        return []

    failures: list[dict[str, Any]] = []
    for step in parsed.steps:
        for decision in step.repair_decisions:
            annotation = decision.fmea_annotation
            if decision.status == "not_applicable" or annotation is None:
                continue
            failures.append(
                {
                    "failure_id": f"prompt_tool_repair:{step.step_id}:{decision.decision}",
                    "step_id": step.step_id,
                    "decision": decision.decision,
                    "status": decision.status,
                    "repair_ref": decision.repair_ref,
                    "failure_mode": annotation.failure_mode,
                    "severity": annotation.severity,
                    "cause": annotation.cause,
                    "recommended_mitigation": annotation.recommended_mitigation,
                    "residual_risk": annotation.residual_risk,
                    "risk_priority_number": annotation.risk_priority_number,
                    "authority_effect": annotation.authority_effect,
                    "evidence_ref": annotation.evidence_ref,
                    "owner": annotation.owner,
                    "surface": "prompt_tool_repair_fmea",
                }
            )
    return failures


def prompt_tool_repair_fmea_closeout_record(
    ledger: PromptToolParserAuthorityLedger | Mapping[str, Any],
) -> dict[str, Any]:
    """Build the closeout-reader surface for prompt/tool repair FMEA."""

    if (
        isinstance(ledger, Mapping)
        and ledger.get("schema_version") == REPAIR_FMEA_SURFACE_SCHEMA_VERSION
    ):
        return dict(ledger)
    parsed = _coerce_ledger(ledger)
    if parsed is None:
        return {
            "schema_version": REPAIR_FMEA_SURFACE_SCHEMA_VERSION,
            "status": "fail",
            "authority_role": "module_closeout_evidence",
            "provenance_kind": "runtime_reader",
            "surface": "prompt_tool_repair_fmea",
            "summary": {
                "repair_decision_count": 0,
                "repair_fmea_annotation_count": 0,
                "repair_fmea_unannotated_count": 0,
                "repair_machinery_failure_count": 0,
            },
            "repair_machinery_failures": [],
            "issues": [
                {
                    "code": "prompt_tool_repair_fmea_ledger_invalid",
                    "severity": "fail",
                    "message": "Prompt/tool repair FMEA closeout record could not parse ledger.",
                    "next_action": "Emit a valid prompt/tool parser authority ledger.",
                }
            ],
        }

    failures = prompt_tool_repair_machinery_failures(parsed)
    unannotated = [
        {
            "step_id": step.step_id,
            "decision": decision.decision,
            "status": decision.status,
            "repair_ref": decision.repair_ref,
        }
        for step in parsed.steps
        for decision in step.repair_decisions
        if decision.fmea_annotation is None
    ]
    issues = [
        {
            "code": "prompt_tool_repair_decision_machinery_failure",
            "severity": "limitation",
            "message": (
                f"Prompt/tool repair decision {failure['decision']} surfaced as "
                f"{failure['failure_mode']} machinery failure."
            ),
            "next_action": failure["recommended_mitigation"],
            "failure_id": failure["failure_id"],
            "failure_mode": failure["failure_mode"],
            "cause": failure["cause"],
            "residual_risk": failure["residual_risk"],
            "evidence_ref": failure["evidence_ref"],
            "source_producer": "polisyos.runtime.quality.prompt_tool_ledger",
        }
        for failure in failures
    ]
    issues.extend(
        {
            "code": "prompt_tool_repair_fmea_refs_missing",
            "severity": "fail",
            "message": (
                f"Prompt/tool repair decision {row['decision']} is missing W10.F "
                "FMEA refs."
            ),
            "next_action": (
                "Annotate the repair decision with failure_mode, severity, cause, "
                "recommended_mitigation, and residual_risk before closeout."
            ),
            "step_id": row["step_id"],
            "repair_ref": row["repair_ref"],
            "source_producer": "polisyos.runtime.quality.prompt_tool_ledger",
        }
        for row in unannotated
    )
    status = "fail" if unannotated else "warn" if failures else "pass"
    return {
        "schema_version": REPAIR_FMEA_SURFACE_SCHEMA_VERSION,
        "status": status,
        "run_id": parsed.run_id,
        "job_id": parsed.job_id,
        "authority_role": "module_closeout_evidence",
        "provenance_kind": "runtime_reader",
        "surface": "prompt_tool_repair_fmea",
        "producer_ref": "polisyos.runtime.quality.prompt_tool_ledger",
        "summary": {
            "repair_decision_count": parsed.summary["repair_decision_count"],
            "repair_fmea_annotation_count": parsed.summary["repair_fmea_annotation_count"],
            "repair_fmea_unannotated_count": parsed.summary["repair_fmea_unannotated_count"],
            "repair_machinery_failure_count": len(failures),
            "max_risk_priority_number": parsed.summary["repair_fmea_max_rpn"],
        },
        "repair_machinery_failures": failures,
        "unannotated_repair_decisions": unannotated,
        "issues": issues,
    }


def build_prompt_tool_ledger_from_model_variant(
    *,
    run_id: str,
    job_id: str,
    variant: Mapping[str, Any],
    rendered_input_refs: Iterable[str],
    output_refs: Iterable[str],
    authority_handoff_refs: Iterable[str],
    generated_at: datetime | None = None,
) -> PromptToolParserAuthorityLedger:
    """Build a conservative ledger from a runtime model-variant summary."""

    variant_id = _optional_text(variant.get("model_variant_id")) or "unknown_variant"
    model = _optional_text(variant.get("model")) or "unknown_model"
    provider = _optional_text(variant.get("provider")) or "unknown_provider"
    base_inputs = tuple(_clean_refs(rendered_input_refs))
    base_outputs = tuple(_clean_refs(output_refs))
    handoff_values = tuple(_clean_refs(authority_handoff_refs))
    if not base_inputs:
        base_inputs = (f"model_variant_id:{variant_id}",)
    if not base_outputs:
        base_outputs = (f"model_variant_id:{variant_id}:output",)
    if not handoff_values:
        handoff_values = base_outputs

    raw_steps = variant.get("steps")
    step_rows = (
        [dict(item) for item in raw_steps if isinstance(item, Mapping)]
        if isinstance(raw_steps, list)
        else []
    )
    if not step_rows:
        step_rows = [
            {
                "agent": "model_variant",
                "action": "model_variant_output",
                "status": variant.get("status") or "completed",
            }
        ]

    steps = []
    for index, row in enumerate(step_rows, start=1):
        action = _optional_text(row.get("action")) or f"model_step_{index}"
        agent = _optional_text(row.get("agent")) or "llm_agent"
        status = str(row.get("status") or "ok").casefold()
        validation_status: ValidationStatus = (
            "pass" if status in {"ok", "completed", "pass", "success"} else "fail"
        )
        schema_healing_count = int(variant.get("schema_healing_count") or 0)
        repair_decision: dict[str, Any] = {
            "decision": "schema_healing_not_required"
            if schema_healing_count <= 0
            else "schema_healing_applied",
            "status": "not_applicable" if schema_healing_count <= 0 else "applied",
            "reason": (
                "Runtime variant reported no schema healing."
                if schema_healing_count <= 0
                else "Runtime variant reported schema healing."
            ),
        }
        if schema_healing_count > 0:
            repair_decision["repair_ref"] = handoff_values[0]
            repair_decision["fmea_annotation"] = {
                "failure_mode": "parser_contract_repair",
                "severity": 6,
                "cause": "model_output_failed_parser_contract",
                "recommended_mitigation": (
                    "Keep strict parser validation and preserve repaired output as "
                    "candidate-only until authority handoff validation passes."
                ),
                "residual_risk": (
                    "Parser healing may mask prompt or tool drift; audit the repair ref "
                    "before reuse in production authority runs."
                ),
                "occurrence": 2,
                "detectability": 3,
                "owner": "team-runtime-ops",
                "controls": [
                    "strict parser validation",
                    "authority handoff validation",
                ],
                "evidence_ref": handoff_values[0],
                "authority_effect": "accepted_mitigation",
            }
        else:
            repair_decision["fmea_annotation"] = {
                "failure_mode": "parser_contract_repair",
                "severity": 1,
                "cause": "strict_parser_validation_passed",
                "recommended_mitigation": (
                    "Keep strict parser validation and retain the no-repair decision "
                    "for audit replay."
                ),
                "residual_risk": "No residual repair risk observed for this step.",
                "occurrence": 1,
                "detectability": 1,
                "owner": "team-runtime-ops",
                "controls": ["strict parser validation"],
                "evidence_ref": handoff_values[0],
                "authority_effect": "advisory",
            }
        steps.append(
            {
                "step_id": f"{variant_id}:{agent}:{action}:{index}",
                "step_kind": action,
                "authority_scopes": list(AUTHORITY_SCOPES),
                "prompt": {
                    "template_id": f"{agent}.{action}",
                    "template_version": "runtime-inferred",
                    "rendered_input_refs": list(base_inputs),
                    "template_variables_fingerprint": _fingerprint(dict(row.get("details") or {})),
                },
                "model_provider": {
                    "provider": provider,
                    "model": model,
                    "model_fingerprint": _optional_text(
                        variant.get("model_fingerprint") or variant.get("fingerprint")
                    ),
                },
                "tool_allowlist": [],
                "tool_schemas": [],
                "tool_call_refs": [],
                "output_refs": list(base_outputs),
                "parser_contract": {
                    "parser_id": f"{agent}.{action}.parser",
                    "parser_version": "runtime-inferred",
                    "contract_ref": handoff_values[0],
                    "input_schema_ref": base_inputs[0],
                    "output_schema_ref": base_outputs[0],
                },
                "validation_refs": [
                    {
                        "validator_id": f"{agent}.{action}.status",
                        "status": validation_status,
                        "validation_ref": handoff_values[0],
                    }
                ],
                "repair_decisions": [repair_decision],
                "authority_handoff_refs": [
                    {
                        "scope": scope,
                        "handoff_ref": handoff_values[min(pos, len(handoff_values) - 1)],
                        "consumer": f"runtime.{scope}",
                        "status": "pass",
                    }
                    for pos, scope in enumerate(AUTHORITY_SCOPES)
                ],
            }
        )
    return PromptToolParserAuthorityLedger.model_validate(
        {
            "generated_at": generated_at or datetime.now(UTC),
            "run_id": run_id,
            "job_id": job_id,
            "model_variant_id": variant_id,
            "steps": steps,
        }
    )


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or any(char in text for char in "\r\n\t"):
        return None
    return text


def _non_empty(value: Any) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError("value must be non-empty text")
    return text


def _clean_refs(values: Iterable[Any]) -> list[str]:
    refs: list[str] = []
    for value in values:
        text = _optional_text(value)
        if text is not None and text not in refs:
            refs.append(text)
    return refs


def _clean_ref_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_clean_refs(values))


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _coerce_ledger(
    value: PromptToolParserAuthorityLedger | Mapping[str, Any] | None,
) -> PromptToolParserAuthorityLedger | None:
    if value is None:
        return None
    if isinstance(value, PromptToolParserAuthorityLedger):
        return value
    if isinstance(value, Mapping):
        try:
            return PromptToolParserAuthorityLedger.model_validate(value)
        except ValidationError:
            return None
    return None


__all__ = [
    "AUTHORITY_SCOPES",
    "COMPRESSION_LOSS_SCHEMA_VERSION",
    "ORCHESTRATION_AUTHORITY_DELTA_SCHEMA_VERSION",
    "ORCHESTRATION_CHOICE_POLICY_CATALOG_SCHEMA_VERSION",
    "PROMPT_TOOL_LEDGER_FILENAME",
    "PROMPT_TOOL_LEDGER_KIND",
    "PROMPT_TOOL_LEDGER_REF_KEY",
    "PROMPT_TOOL_LEDGER_REPORT_KEY",
    "REPAIR_FMEA_SURFACE_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "AuthorityHandoffRef",
    "CompressionClaimItem",
    "CompressionDroppedItemDisposition",
    "CompressionEvidenceIndependenceBasis",
    "CompressionLossReceipt",
    "CompressionMaterialItem",
    "CompressionMaterialSet",
    "CompressionTerminalResult",
    "ModelAssistedStepLedger",
    "ModelProviderConfig",
    "OrchestrationAuthorityDelta",
    "OrchestrationAuthorityDeltaCompletenessReceipt",
    "OrchestrationAuthorityDeltaDerivation",
    "OrchestrationChoiceContext",
    "OrchestrationChoicePolicy",
    "ParserContract",
    "PromptTemplateRecord",
    "PromptToolLedgerError",
    "PromptToolLedgerFinding",
    "PromptToolParserAuthorityLedger",
    "PromptToolParserAuthorityValidation",
    "RepairDecision",
    "RepairDecisionFMEAAnnotation",
    "ToolCallRecord",
    "ToolSchemaRecord",
    "ValidationRef",
    "build_compression_loss_receipt",
    "build_orchestration_authority_deltas",
    "build_prompt_tool_ledger_from_model_variant",
    "load_orchestration_choice_policies",
    "persist_prompt_tool_ledger",
    "persist_runtime_quality_json_artifact",
    "prompt_tool_repair_fmea_closeout_record",
    "prompt_tool_repair_machinery_failures",
    "serialize_prompt_tool_ledger",
    "validate_compression_loss_receipt",
    "validate_orchestration_authority_delta_completeness",
    "validate_prompt_tool_parser_authority",
]
