"""Expert adjudication labels for the universal outcome corpus."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

EXPERT_ADJUDICATION_SCHEMA_VERSION = (
    "policyos.universal_policy_design.outcome_corpus.expert_adjudication.v1"
)
EXPERT_ADJUDICATION_CONTRACT_ID = "universal_outcome_corpus.expert_adjudication.v1"
EXPERT_ADJUDICATION_USEFUL_DESIGN_GATE_SCHEMA_VERSION = (
    "policyos.universal_policy_design.outcome_corpus.useful_design_gate.v1"
)

ExpertAdjudicationLabel = Literal[
    "semantic_pass",
    "limitation_required",
    "contested",
    "unsupported",
    "false_pass",
    "fabricated_unverifiable",
    "reviewer_disagreement",
]
ExpertAdjudicationScope = Literal["case", "claim"]
AuthorityLevel = Literal["research", "governed", "production"]
C30Dimension = Literal[
    "interpretation",
    "scope",
    "legal_competence",
    "causal_support",
    "method_fit",
    "time_role_alignment",
    "participation_attribution",
    "independence",
    "public_truthfulness",
]
ReviewerRole = Literal[
    "policy_generalist",
    "domain_aware_reviewer",
    "domain_reviewer",
    "method_evidence_reviewer",
    "legal_governance_reviewer",
    "public_surface_reviewer",
    "stakeholder_participation_reviewer",
    "tie_breaker",
]
CorpusSlice = Literal[
    "deep_pilot",
    "admissibility_pair_set",
    "facet_saturation_corpus",
    "historical_failure_corpus",
    "contested_tradeoff_participation_corpus",
    "longitudinal_calibration_corpus",
]
ReviewerTopologyMode = Literal["deep_pilot_overlap", "partial_disjoint"]
DisagreementCategory = Literal[
    "none",
    "interpretation",
    "scope",
    "legal_competence",
    "causal_support",
    "method_fit",
    "time_role_alignment",
    "participation_attribution",
    "independence",
    "public_truthfulness",
    "reviewer_expertise_boundary",
    "substantive",
]

_LABEL_ORDER: tuple[str, ...] = (
    "semantic_pass",
    "limitation_required",
    "contested",
    "unsupported",
    "false_pass",
    "fabricated_unverifiable",
    "reviewer_disagreement",
)
_USEFUL_DESIGN_LABELS = frozenset({"semantic_pass", "limitation_required"})
_REJECTED_STRUCTURAL_PASS_LABELS = frozenset(
    label for label in _LABEL_ORDER if label != "semantic_pass"
)


class _StrictCorpusModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpertAdjudicationGoldCard(_StrictCorpusModel):
    """C30 gold-card fields for a rejected structural pass."""

    claim_id: str = Field(min_length=1)
    dimension_id: C30Dimension
    evidence_ref: str = Field(min_length=1)
    context_ref: str = Field(min_length=1)
    failure_mode: str = Field(min_length=1)
    why_structural_checks_missed_it: str = Field(min_length=1)
    status_should_have_been: str = Field(min_length=1)
    required_surface_change: str = Field(min_length=1)


class ExpertReviewerProfile(_StrictCorpusModel):
    """Reviewer metadata required by the W11.C reviewer topology."""

    reviewer_id: str = Field(min_length=1)
    role: ReviewerRole
    expertise_basis: list[str] = Field(min_length=1)
    conflict_disclosures: list[str] = Field(min_length=1)


class ExpertReviewerVote(_StrictCorpusModel):
    """One reviewer-level adjudication vote preserved under C30."""

    reviewer_id: str = Field(min_length=1)
    label: ExpertAdjudicationLabel
    rationale: str = Field(min_length=1)
    disagreement_category: DisagreementCategory


class ReviewerTopology(_StrictCorpusModel):
    """Reviewer topology for deep-pilot overlap and partial-disjoint review."""

    corpus_slice: CorpusSlice
    topology_mode: ReviewerTopologyMode
    annotation_guide_ref: str = Field(min_length=1)
    calibration_round_id: str | None = None
    reviewers: list[ExpertReviewerProfile] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_topology(self) -> ReviewerTopology:
        reviewer_ids = [reviewer.reviewer_id for reviewer in self.reviewers]
        if len(reviewer_ids) != len(set(reviewer_ids)):
            raise ValueError("reviewer_topology reviewer_id values must be unique")
        if self.topology_mode == "deep_pilot_overlap":
            if self.corpus_slice != "deep_pilot":
                raise ValueError("deep_pilot_overlap topology requires corpus_slice=deep_pilot")
            if len(self.reviewers) < 2:
                raise ValueError("deep_pilot_overlap requires at least two reviewers")
            if self.calibration_round_id is None:
                raise ValueError("deep_pilot_overlap requires calibration_round_id")
        return self


class ExpertAdjudicationRecord(_StrictCorpusModel):
    """One case- or claim-scoped expert adjudication label."""

    adjudication_id: str = Field(min_length=1)
    scope: ExpertAdjudicationScope
    claim_id: str | None = None
    dimension_id: C30Dimension
    label: ExpertAdjudicationLabel
    structural_pass_claimed: Literal[True]
    structural_validator_refs: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    context_refs: list[str] = Field(min_length=1)
    reviewer_votes: list[ExpertReviewerVote] = Field(min_length=1)
    gold_card: ExpertAdjudicationGoldCard | None = None

    @model_validator(mode="after")
    def _validate_scope(self) -> ExpertAdjudicationRecord:
        if self.scope == "claim" and not self.claim_id:
            raise ValueError("claim-scoped adjudication requires claim_id")
        if self.scope == "case" and self.claim_id not in {None, "case"}:
            raise ValueError("case-scoped adjudication must not target a claim_id")
        return self


class ExpertAdjudicationManifest(_StrictCorpusModel):
    """Strict W11.C manifest for expert adjudication labels."""

    schema_version: Literal[EXPERT_ADJUDICATION_SCHEMA_VERSION]
    manifest_id: str = Field(min_length=1)
    phase_id: Literal["W11.C"]
    case_id: str = Field(min_length=1)
    case_ref: str = Field(min_length=1)
    decomposition_ref: str = Field(min_length=1)
    authority_level: AuthorityLevel
    domain_id: str = Field(min_length=1)
    research_refs: list[str] = Field(min_length=2)
    pattern_ids: list[str] = Field(min_length=1)
    expected_claim_ids: list[str] = Field(min_length=1)
    reviewer_topology: ReviewerTopology
    adjudications: list[ExpertAdjudicationRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_traceability(self) -> ExpertAdjudicationManifest:
        if "C30" not in self.research_refs:
            raise ValueError("W11.C expert adjudication manifests must cite C30")
        if "P10" not in self.pattern_ids:
            raise ValueError("W11.C expert adjudication manifests must cite P10")
        if len(self.expected_claim_ids) != len(set(self.expected_claim_ids)):
            raise ValueError("expected_claim_ids must be unique")
        return self


@dataclass(frozen=True)
class ExpertAdjudicationIssue:
    """Validation issue emitted by the W11.C evaluator."""

    code: str
    message: str
    field: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        """Return a stable JSON-serializable issue shape."""

        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
        }


def expert_adjudication_json_schema() -> dict[str, Any]:
    """Return the strict JSON schema for W11.C expert adjudication manifests."""

    return ExpertAdjudicationManifest.model_json_schema(mode="validation")


def evaluate_expert_adjudication_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one W11.C expert adjudication manifest.

    The evaluator treats C30 labels as a benchmark artifact, not runtime
    authority. It verifies reviewer topology, claim coverage, gold-card
    completeness for rejected structural passes, and explicit preservation of
    reviewer disagreement.
    """

    if not isinstance(payload, Mapping):
        return _evaluation_result(
            manifest_id=None,
            case_id=None,
            status="fail",
            topology_mode=None,
            labels=(),
            label_counts={},
            claim_coverage_status="not_evaluated",
            missing_claim_ids=(),
            rejected_structural_pass_count=0,
            gold_card_count=0,
            substantive_disagreement_preserved=False,
            issues=(
                ExpertAdjudicationIssue(
                    code="expert_adjudication_manifest_invalid",
                    message="Expert adjudication manifest must be a mapping.",
                    field=None,
                ),
            ),
        )

    try:
        manifest = ExpertAdjudicationManifest.model_validate(dict(payload))
    except ValidationError as exc:
        return _evaluation_result(
            manifest_id=_text(payload.get("manifest_id")),
            case_id=_text(payload.get("case_id")),
            status="fail",
            topology_mode=None,
            labels=(),
            label_counts={},
            claim_coverage_status="not_evaluated",
            missing_claim_ids=(),
            rejected_structural_pass_count=0,
            gold_card_count=0,
            substantive_disagreement_preserved=False,
            issues=(
                ExpertAdjudicationIssue(
                    code="expert_adjudication_schema_invalid",
                    message=str(exc),
                    field=None,
                ),
            ),
        )

    issues: list[ExpertAdjudicationIssue] = []
    reviewer_ids = {reviewer.reviewer_id for reviewer in manifest.reviewer_topology.reviewers}
    case_scope_count = 0
    claim_label_ids: set[str] = set()
    labels: list[str] = []
    label_counts: Counter[str] = Counter()
    gold_card_count = 0
    rejected_count = 0
    substantive_disagreement_preserved = False

    for index, adjudication in enumerate(manifest.adjudications):
        field = f"adjudications.{index}"
        labels.append(adjudication.label)
        label_counts[adjudication.label] += 1
        if adjudication.scope == "case":
            case_scope_count += 1
        if adjudication.scope == "claim" and adjudication.claim_id:
            claim_label_ids.add(adjudication.claim_id)
            if adjudication.claim_id not in set(manifest.expected_claim_ids):
                issues.append(
                    ExpertAdjudicationIssue(
                        code="expert_adjudication_unexpected_claim_id",
                        message=(
                            "Claim-level adjudication targets a claim outside "
                            "expected_claim_ids."
                        ),
                        field=f"{field}.claim_id",
                    )
                )

        _validate_reviewer_votes(
            adjudication,
            reviewer_ids=reviewer_ids,
            topology_mode=manifest.reviewer_topology.topology_mode,
            field=field,
            issues=issues,
        )
        if len({vote.label for vote in adjudication.reviewer_votes}) > 1:
            substantive_disagreement_preserved = True

        if adjudication.label in _REJECTED_STRUCTURAL_PASS_LABELS:
            rejected_count += 1
            if adjudication.gold_card is None:
                issues.append(
                    ExpertAdjudicationIssue(
                        code="expert_adjudication_gold_card_missing",
                        message=(
                            "Every rejected structural pass requires the C30 gold-card "
                            "fields."
                        ),
                        field=f"{field}.gold_card",
                    )
                )
            else:
                gold_card_count += 1
                _validate_gold_card(
                    adjudication,
                    field=field,
                    issues=issues,
                )
        elif adjudication.gold_card is not None:
            issues.append(
                ExpertAdjudicationIssue(
                    code="expert_adjudication_pass_gold_card_unexpected",
                    message="semantic_pass adjudications must not carry rejected-pass gold cards.",
                    field=f"{field}.gold_card",
                )
            )

        if adjudication.label == "reviewer_disagreement":
            _validate_reviewer_disagreement(adjudication, field=field, issues=issues)

    if case_scope_count == 0:
        issues.append(
            ExpertAdjudicationIssue(
                code="expert_adjudication_case_label_missing",
                message="W11.C requires at least one case-scoped adjudication label.",
                field="adjudications",
            )
        )

    missing_claim_ids = tuple(
        sorted(set(manifest.expected_claim_ids).difference(claim_label_ids))
    )
    if missing_claim_ids:
        issues.append(
            ExpertAdjudicationIssue(
                code="expert_adjudication_claim_coverage_missing",
                message="Every expected claim requires a claim-scoped adjudication label.",
                field="expected_claim_ids",
            )
        )
    claim_coverage_status = "complete" if not missing_claim_ids else "missing"

    return _evaluation_result(
        manifest_id=manifest.manifest_id,
        case_id=manifest.case_id,
        status="fail" if issues else "pass",
        topology_mode=manifest.reviewer_topology.topology_mode,
        labels=_ordered_labels(labels),
        label_counts={label: label_counts[label] for label in _LABEL_ORDER if label_counts[label]},
        claim_coverage_status=claim_coverage_status,
        missing_claim_ids=missing_claim_ids,
        rejected_structural_pass_count=rejected_count,
        gold_card_count=gold_card_count,
        substantive_disagreement_preserved=substantive_disagreement_preserved,
        issues=tuple(issues),
    )


def build_expert_adjudication_useful_design_gate(
    *,
    case_id: str,
    structural_complete: bool,
    adjudication_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the W11.C consumer gate for useful-design metrics.

    A structurally complete case without expert adjudication is an honest
    structural result, but it cannot count toward useful design.
    """

    if not structural_complete:
        return _useful_design_gate(
            case_id=case_id,
            status="blocked",
            counts_toward_useful_design=False,
            blocker_code="structural_case_incomplete",
            adjudication_labels=(),
        )
    if adjudication_result is None:
        return _useful_design_gate(
            case_id=case_id,
            status="blocked",
            counts_toward_useful_design=False,
            blocker_code="expert_adjudication_missing",
            adjudication_labels=(),
        )
    if adjudication_result.get("status") != "pass":
        return _useful_design_gate(
            case_id=case_id,
            status="blocked",
            counts_toward_useful_design=False,
            blocker_code="expert_adjudication_invalid",
            adjudication_labels=_sequence_of_text(adjudication_result.get("labels")),
        )
    labels = _ordered_labels(_sequence_of_text(adjudication_result.get("labels")))
    if not labels:
        return _useful_design_gate(
            case_id=case_id,
            status="blocked",
            counts_toward_useful_design=False,
            blocker_code="expert_adjudication_labels_missing",
            adjudication_labels=(),
        )
    if set(labels).issubset(_USEFUL_DESIGN_LABELS):
        return _useful_design_gate(
            case_id=case_id,
            status="eligible",
            counts_toward_useful_design=True,
            blocker_code=None,
            adjudication_labels=labels,
        )
    return _useful_design_gate(
        case_id=case_id,
        status="blocked",
        counts_toward_useful_design=False,
        blocker_code="expert_adjudication_not_useful_design",
        adjudication_labels=labels,
    )


def _validate_reviewer_votes(
    adjudication: ExpertAdjudicationRecord,
    *,
    reviewer_ids: set[str],
    topology_mode: str,
    field: str,
    issues: list[ExpertAdjudicationIssue],
) -> None:
    seen_vote_ids: set[str] = set()
    for vote_index, vote in enumerate(adjudication.reviewer_votes):
        vote_field = f"{field}.reviewer_votes.{vote_index}"
        if vote.reviewer_id not in reviewer_ids:
            issues.append(
                ExpertAdjudicationIssue(
                    code="expert_adjudication_unknown_reviewer",
                    message="Reviewer vote references a reviewer absent from reviewer_topology.",
                    field=f"{vote_field}.reviewer_id",
                )
            )
        if vote.reviewer_id in seen_vote_ids:
            issues.append(
                ExpertAdjudicationIssue(
                    code="expert_adjudication_duplicate_reviewer_vote",
                    message="A reviewer may vote at most once per adjudication record.",
                    field=f"{vote_field}.reviewer_id",
                )
            )
        seen_vote_ids.add(vote.reviewer_id)
    if topology_mode == "deep_pilot_overlap" and len(seen_vote_ids) < 2:
        issues.append(
            ExpertAdjudicationIssue(
                code="expert_adjudication_deep_pilot_overlap_missing",
                message="Deep-pilot overlap requires at least two reviewer votes per label.",
                field=f"{field}.reviewer_votes",
            )
        )


def _validate_reviewer_disagreement(
    adjudication: ExpertAdjudicationRecord,
    *,
    field: str,
    issues: list[ExpertAdjudicationIssue],
) -> None:
    vote_labels = {vote.label for vote in adjudication.reviewer_votes}
    categories = {vote.disagreement_category for vote in adjudication.reviewer_votes}
    if len(vote_labels) < 2:
        issues.append(
            ExpertAdjudicationIssue(
                code="expert_adjudication_disagreement_votes_missing",
                message="reviewer_disagreement requires at least two distinct reviewer labels.",
                field=f"{field}.reviewer_votes",
            )
        )
    if categories == {"none"}:
        issues.append(
            ExpertAdjudicationIssue(
                code="expert_adjudication_disagreement_category_missing",
                message="reviewer_disagreement requires a substantive disagreement category.",
                field=f"{field}.reviewer_votes",
            )
        )


def _validate_gold_card(
    adjudication: ExpertAdjudicationRecord,
    *,
    field: str,
    issues: list[ExpertAdjudicationIssue],
) -> None:
    gold_card = adjudication.gold_card
    if gold_card is None:
        return
    expected_claim_id = adjudication.claim_id if adjudication.scope == "claim" else "case"
    if gold_card.claim_id != expected_claim_id:
        issues.append(
            ExpertAdjudicationIssue(
                code="expert_adjudication_gold_card_claim_mismatch",
                message="Gold-card claim_id must match the adjudication scope.",
                field=f"{field}.gold_card.claim_id",
            )
        )
    if gold_card.dimension_id != adjudication.dimension_id:
        issues.append(
            ExpertAdjudicationIssue(
                code="expert_adjudication_gold_card_dimension_mismatch",
                message="Gold-card dimension_id must match the adjudication dimension.",
                field=f"{field}.gold_card.dimension_id",
            )
        )
    if gold_card.evidence_ref not in adjudication.evidence_refs:
        issues.append(
            ExpertAdjudicationIssue(
                code="expert_adjudication_gold_card_evidence_unbound",
                message="Gold-card evidence_ref must be present in adjudication evidence_refs.",
                field=f"{field}.gold_card.evidence_ref",
            )
        )
    if gold_card.context_ref not in adjudication.context_refs:
        issues.append(
            ExpertAdjudicationIssue(
                code="expert_adjudication_gold_card_context_unbound",
                message="Gold-card context_ref must be present in adjudication context_refs.",
                field=f"{field}.gold_card.context_ref",
            )
        )


def _evaluation_result(
    *,
    manifest_id: str | None,
    case_id: str | None,
    status: str,
    topology_mode: str | None,
    labels: Iterable[str],
    label_counts: Mapping[str, int],
    claim_coverage_status: str,
    missing_claim_ids: Iterable[str],
    rejected_structural_pass_count: int,
    gold_card_count: int,
    substantive_disagreement_preserved: bool,
    issues: Iterable[ExpertAdjudicationIssue],
) -> dict[str, Any]:
    return {
        "schema_version": (
            "policyos.universal_policy_design.outcome_corpus."
            "expert_adjudication.evaluation.v1"
        ),
        "contract_id": EXPERT_ADJUDICATION_CONTRACT_ID,
        "manifest_id": manifest_id,
        "case_id": case_id,
        "status": status,
        "topology_mode": topology_mode,
        "labels": list(labels),
        "label_counts": dict(label_counts),
        "claim_coverage_status": claim_coverage_status,
        "missing_claim_ids": list(missing_claim_ids),
        "rejected_structural_pass_count": rejected_structural_pass_count,
        "gold_card_count": gold_card_count,
        "substantive_disagreement_preserved": substantive_disagreement_preserved,
        "issues": [issue.as_dict() for issue in issues],
    }


def _useful_design_gate(
    *,
    case_id: str,
    status: str,
    counts_toward_useful_design: bool,
    blocker_code: str | None,
    adjudication_labels: Iterable[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": EXPERT_ADJUDICATION_USEFUL_DESIGN_GATE_SCHEMA_VERSION,
        "case_id": case_id,
        "status": status,
        "counts_toward_useful_design": counts_toward_useful_design,
        "blocker_code": blocker_code,
        "adjudication_labels": list(adjudication_labels),
        "authoritative_for": ["useful_design_metric_eligibility"],
        "may_not_use_for": [
            "claim_authority",
            "closeout_authority",
            "legal_authority",
            "producer_evidence",
            "public_recommendation_authority",
        ],
    }
    return payload


def _ordered_labels(labels: Iterable[str]) -> list[str]:
    values = set(labels)
    return [label for label in _LABEL_ORDER if label in values]


def _sequence_of_text(value: object) -> tuple[str, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(str(item) for item in value if str(item))
    return ()


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
