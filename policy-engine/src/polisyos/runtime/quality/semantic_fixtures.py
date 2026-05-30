"""Semantic gold-card fixtures for Policy Design Case false-pass evaluation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SEMANTIC_GOLD_CARD_SCHEMA_VERSION = "policyos.runtime.policy_design_case.semantic_gold_card.v1"
SEMANTIC_GOLD_CARD_CONTRACT_ID = "policy_design_case.semantic_gold_card.v1"
SEMANTIC_EVALUATION_PACK_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.semantic_evaluation_pack.v1"
)
SEMANTIC_EVALUATION_PACK_CONTRACT_ID = "policy_design_case.semantic_evaluation_pack.v1"

SemanticFailureMode = Literal[
    "projection_laundering",
    "participation_laundering",
    "participation_prevalence_negative",
    "raw_count_inflation",
    "method_mismatch",
    "stale_evidence",
    "llm_speculation",
    "unsupported_claim",
    "unreachable_recourse_pointer",
    "tuned_threshold_hardcoding",
]
SemanticAxis = Literal[
    "authority",
    "participation",
    "evidence_strength",
    "claim_support",
    "method",
    "freshness",
    "source_classification",
    "recourse",
    "tuned_config",
]
SemanticPackSplit = Literal["public", "hidden", "rotating"]
SemanticPublicExportVisibility = Literal["public_detail", "aggregate_only"]
SemanticAdjudicationLabel = Literal[
    "semantic_pass",
    "limitation_required",
    "contested",
    "unsupported",
    "false_pass",
    "fabricated_unverifiable",
    "reviewer_disagreement",
]

_P15_FAILURE_MODES = frozenset(
    {
        "projection_laundering",
        "participation_laundering",
        "participation_prevalence_negative",
        "llm_speculation",
    }
)
_PUBLISHABLE_STATUSES = frozenset({"admissible", "publishable", "published"})
_CURRENT_FRESHNESS_STATUSES = frozenset({"pass", "current", "claimed_current", "fresh"})
_LLM_SOURCE_KINDS = frozenset({"llm_candidate", "llm_critic", "llm_drafter"})


class _StrictGoldCardModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SemanticStructuralVerdict(_StrictGoldCardModel):
    """Structural validator result preserved by a semantic gold card."""

    status: Literal["pass"]
    validator_refs: list[str] = Field(min_length=1)
    completeness_claims: list[str] = Field(min_length=1)


class SemanticAdjudication(_StrictGoldCardModel):
    """Human-readable adjudication attached to one semantic false-pass case."""

    status: Literal["fail"]
    adjudicator: str = Field(min_length=1)
    failure_mode: SemanticFailureMode
    failure_code: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    authority_effect: Literal["block_closeout", "publish_with_limitation", "review_required"]
    required_remediation: str = Field(min_length=1)


class SemanticProbe(_StrictGoldCardModel):
    """One content-level probe that explains why a structural pass is false."""

    probe_id: str = Field(min_length=1)
    semantic_axis: SemanticAxis
    pattern_ids: list[str] = Field(min_length=1)
    observed_signal: str = Field(min_length=1)
    expected_signal: str = Field(min_length=1)
    verdict: Literal["fail"]
    failure_code: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)


class SemanticEvaluationFixtureEntry(_StrictGoldCardModel):
    """One fixture reference in a split-aware semantic evaluation pack."""

    fixture_id: str = Field(min_length=1)
    fixture_ref: str = Field(min_length=1)
    failure_mode: SemanticFailureMode
    challenge_family: str | None = None


class SemanticEvaluationRotationPolicy(_StrictGoldCardModel):
    """Rotation policy for challenge fixtures that must not become static targets."""

    rotation_interval_days: int = Field(gt=0)
    next_rotation_due: date
    owner: str = Field(min_length=1)


class SemanticEvaluationPackSplit(_StrictGoldCardModel):
    """Public, hidden, or rotating split inside a W5.B evaluation pack."""

    split: SemanticPackSplit
    purpose: str = Field(min_length=1)
    public_export_visibility: SemanticPublicExportVisibility
    fixtures: list[SemanticEvaluationFixtureEntry] = Field(min_length=1)
    rotation_policy: SemanticEvaluationRotationPolicy | None = None

    @model_validator(mode="after")
    def _validate_rotation_policy(self) -> SemanticEvaluationPackSplit:
        if self.split == "rotating" and self.rotation_policy is None:
            raise ValueError("rotating semantic evaluation split requires rotation_policy")
        return self


class PolicyDesignCaseSemanticEvaluationPack(_StrictGoldCardModel):
    """Strict manifest for W5.B public, hidden, and rotating semantic packs."""

    schema_version: Literal[SEMANTIC_EVALUATION_PACK_SCHEMA_VERSION]
    pack_id: str = Field(min_length=1)
    phase_id: Literal["W5.B"]
    title: str = Field(min_length=1)
    research_refs: list[str] = Field(min_length=2)
    pattern_ids: list[str] = Field(min_length=1)
    adjudication_labels: list[SemanticAdjudicationLabel] = Field(min_length=1)
    required_failure_modes: list[SemanticFailureMode] = Field(min_length=1)
    reviewer_protocol_ref: str = Field(min_length=1)
    splits: list[SemanticEvaluationPackSplit] = Field(min_length=3)
    benchmark_metadata: dict[str, Any] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_pack_consistency(self) -> PolicyDesignCaseSemanticEvaluationPack:
        if "E22" not in self.research_refs or "C30" not in self.research_refs:
            raise ValueError("W5.B semantic evaluation packs must cite E22 and C30")
        for pattern_id in ("P10", "P14", "P15"):
            if pattern_id not in self.pattern_ids:
                raise ValueError(f"W5.B semantic evaluation packs must cite {pattern_id}")
        split_names = {split.split for split in self.splits}
        if split_names != {"public", "hidden", "rotating"}:
            raise ValueError("semantic evaluation pack must define public, hidden, and rotating")
        entry_modes = {fixture.failure_mode for split in self.splits for fixture in split.fixtures}
        missing_modes = set(self.required_failure_modes) - entry_modes
        if missing_modes:
            raise ValueError(
                "semantic evaluation pack missing required failure modes: "
                + ", ".join(sorted(missing_modes))
            )
        fixture_refs = [fixture.fixture_ref for split in self.splits for fixture in split.fixtures]
        if len(fixture_refs) != len(set(fixture_refs)):
            raise ValueError("semantic evaluation pack fixture_refs must be unique")
        return self


class PolicyDesignCaseSemanticGoldCardFixture(_StrictGoldCardModel):
    """Strict schema for a Policy Design Case semantic false-pass fixture."""

    schema_version: Literal[SEMANTIC_GOLD_CARD_SCHEMA_VERSION]
    fixture_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    expected_status: Literal["semantic_fail"]
    failure_mode: SemanticFailureMode
    research_refs: list[str] = Field(min_length=2)
    pattern_ids: list[str] = Field(min_length=1)
    structural_pass_claimed: Literal[True]
    structural_verdict: SemanticStructuralVerdict
    semantic_adjudication: SemanticAdjudication
    semantic_probes: list[SemanticProbe] = Field(min_length=1)
    payload: dict[str, Any] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_gold_card_consistency(self) -> PolicyDesignCaseSemanticGoldCardFixture:
        if self.semantic_adjudication.failure_mode != self.failure_mode:
            raise ValueError("semantic adjudication failure_mode must match fixture failure_mode")
        if "C30" not in self.research_refs or not {"E1", "E22"} & set(self.research_refs):
            raise ValueError("semantic gold cards must cite C30 and either E1 or E22")
        if "P10" not in self.pattern_ids:
            raise ValueError("semantic gold cards must cite P10")
        if self.failure_mode in _P15_FAILURE_MODES and "P15" not in self.pattern_ids:
            raise ValueError("P15 laundering fixtures must cite P15")
        if self.failure_mode == "raw_count_inflation" and "P14" not in self.pattern_ids:
            raise ValueError("raw-count inflation fixtures must cite P14")
        failure_code = self.semantic_adjudication.failure_code
        for probe in self.semantic_probes:
            if probe.failure_code != failure_code:
                raise ValueError("semantic probe failure_code must match adjudication failure_code")
            if "P10" not in probe.pattern_ids:
                raise ValueError("semantic probes must cite P10")
        return self


@dataclass(frozen=True)
class SemanticGoldCardValidationIssue:
    """Validation issue for a semantic gold-card fixture."""

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


def semantic_gold_card_json_schema() -> dict[str, Any]:
    """Return the strict JSON schema for Policy Design Case semantic gold cards."""

    return PolicyDesignCaseSemanticGoldCardFixture.model_json_schema(mode="validation")


def semantic_evaluation_pack_json_schema() -> dict[str, Any]:
    """Return the strict JSON schema for W5.B semantic evaluation packs."""

    return PolicyDesignCaseSemanticEvaluationPack.model_json_schema(mode="validation")


def evaluate_semantic_gold_card_fixture(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one W1.B semantic gold-card fixture.

    The result deliberately separates fixture validity from semantic status. A
    valid false-pass fixture has a passing structural verdict and a failing
    semantic verdict derived from the payload, not merely copied from metadata.
    """

    preflight_issues = _preflight_issues(payload)
    if preflight_issues:
        return _evaluation_result(
            fixture_status="invalid",
            structural_status=_structural_status(payload),
            semantic_status="not_evaluated",
            expected_failure_code=_expected_failure_code(payload),
            detected_failure_codes=(),
            issues=preflight_issues,
        )

    try:
        card = PolicyDesignCaseSemanticGoldCardFixture.model_validate(dict(payload))
    except ValidationError as exc:
        return _evaluation_result(
            fixture_status="invalid",
            structural_status=_structural_status(payload),
            semantic_status="not_evaluated",
            expected_failure_code=_expected_failure_code(payload),
            detected_failure_codes=(),
            issues=(
                SemanticGoldCardValidationIssue(
                    code="semantic_gold_card_schema_invalid",
                    message=str(exc),
                    field=None,
                ),
            ),
        )

    detected_failure_codes = tuple(sorted(_detected_failure_codes(card)))
    expected_failure_code = card.semantic_adjudication.failure_code
    issues: list[SemanticGoldCardValidationIssue] = []
    if expected_failure_code not in detected_failure_codes:
        issues.append(
            SemanticGoldCardValidationIssue(
                code="semantic_gold_card_expected_failure_not_detected",
                message=(
                    "Gold-card metadata declares a semantic failure, but the payload "
                    "does not deterministically exhibit that failure."
                ),
                field="payload",
            )
        )

    return _evaluation_result(
        fixture_status="invalid" if issues else "valid",
        structural_status=card.structural_verdict.status,
        semantic_status="fail" if detected_failure_codes else "pass",
        expected_failure_code=expected_failure_code,
        detected_failure_codes=detected_failure_codes,
        issues=tuple(issues),
        fixture_id=card.fixture_id,
        failure_mode=card.failure_mode,
    )


def evaluate_semantic_evaluation_pack(
    manifest: Mapping[str, Any],
    fixtures_by_ref: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Evaluate a split-aware W5.B semantic false-pass benchmark pack.

    The pack evaluator deliberately consumes fixture payloads by reference so
    public, hidden, and rotating splits can be governed separately. Hidden and
    rotating fixtures may be evaluated internally, but their public export
    visibility must remain aggregate-only.
    """

    if not isinstance(manifest, Mapping):
        return _pack_result(
            pack_id=None,
            status="fail",
            split_summary={},
            detected_failure_modes=(),
            detected_failure_codes=(),
            detected_pattern_ids=(),
            issues=(
                SemanticGoldCardValidationIssue(
                    code="semantic_pack_manifest_invalid",
                    message="Semantic evaluation pack manifest must be a mapping.",
                    field=None,
                ),
            ),
        )

    try:
        pack = PolicyDesignCaseSemanticEvaluationPack.model_validate(dict(manifest))
    except ValidationError as exc:
        return _pack_result(
            pack_id=_text(manifest.get("pack_id")),
            status="fail",
            split_summary={},
            detected_failure_modes=(),
            detected_failure_codes=(),
            detected_pattern_ids=(),
            issues=(
                SemanticGoldCardValidationIssue(
                    code="semantic_pack_schema_invalid",
                    message=str(exc),
                    field=None,
                ),
            ),
        )

    issues: list[SemanticGoldCardValidationIssue] = []
    split_summary = {split.split: len(split.fixtures) for split in pack.splits}
    detected_failure_modes: set[str] = set()
    detected_failure_codes: set[str] = set()
    detected_pattern_ids: set[str] = set()

    for split in pack.splits:
        if (
            split.split in {"hidden", "rotating"}
            and split.public_export_visibility != "aggregate_only"
        ):
            issues.append(
                SemanticGoldCardValidationIssue(
                    code="semantic_pack_hidden_detail_leakage",
                    message=(
                        "Hidden and rotating semantic fixtures must expose only "
                        "aggregate public status."
                    ),
                    field=f"splits.{split.split}.public_export_visibility",
                )
            )
        for fixture in split.fixtures:
            payload = fixtures_by_ref.get(fixture.fixture_ref)
            if payload is None:
                issues.append(
                    SemanticGoldCardValidationIssue(
                        code="semantic_pack_fixture_missing",
                        message="Semantic evaluation pack references a missing fixture.",
                        field=fixture.fixture_ref,
                    )
                )
                continue
            evaluation = evaluate_semantic_gold_card_fixture(payload)
            if evaluation["fixture_status"] != "valid":
                issues.append(
                    SemanticGoldCardValidationIssue(
                        code="semantic_pack_fixture_invalid",
                        message="Semantic evaluation pack fixture did not validate.",
                        field=fixture.fixture_ref,
                    )
                )
                continue
            if evaluation["fixture_id"] != fixture.fixture_id:
                issues.append(
                    SemanticGoldCardValidationIssue(
                        code="semantic_pack_fixture_id_mismatch",
                        message="Semantic evaluation fixture id does not match manifest entry.",
                        field=fixture.fixture_ref,
                    )
                )
            if evaluation["failure_mode"] != fixture.failure_mode:
                issues.append(
                    SemanticGoldCardValidationIssue(
                        code="semantic_pack_failure_mode_mismatch",
                        message=(
                            "Semantic evaluation fixture failure mode does not match "
                            "manifest entry."
                        ),
                        field=fixture.fixture_ref,
                    )
                )
            detected_failure_modes.add(str(evaluation["failure_mode"]))
            detected_failure_codes.update(
                str(code) for code in evaluation["detected_failure_codes"]
            )
            detected_pattern_ids.update(str(pattern_id) for pattern_id in payload["pattern_ids"])

    missing_required_modes = set(pack.required_failure_modes) - detected_failure_modes
    if missing_required_modes:
        issues.append(
            SemanticGoldCardValidationIssue(
                code="semantic_pack_required_failure_mode_missing",
                message=(
                    "Semantic evaluation pack did not validate required failure modes: "
                    + ", ".join(sorted(missing_required_modes))
                ),
                field="required_failure_modes",
            )
        )

    return _pack_result(
        pack_id=pack.pack_id,
        status="fail" if issues else "pass",
        split_summary=split_summary,
        detected_failure_modes=tuple(sorted(detected_failure_modes)),
        detected_failure_codes=tuple(sorted(detected_failure_codes)),
        detected_pattern_ids=tuple(sorted(detected_pattern_ids)),
        issues=tuple(issues),
    )


def _preflight_issues(payload: Mapping[str, Any]) -> tuple[SemanticGoldCardValidationIssue, ...]:
    issues: list[SemanticGoldCardValidationIssue] = []
    if not isinstance(payload, Mapping):
        return (
            SemanticGoldCardValidationIssue(
                code="semantic_gold_card_payload_invalid",
                message="Semantic gold-card payload must be a mapping.",
                field=None,
            ),
        )
    if payload.get("structural_pass_claimed") is not True:
        issues.append(
            SemanticGoldCardValidationIssue(
                code="semantic_gold_card_structural_pass_missing",
                message="False-pass fixtures must declare structural_pass_claimed=true.",
                field="structural_pass_claimed",
            )
        )
    structural_verdict = payload.get("structural_verdict")
    if not isinstance(structural_verdict, Mapping) or structural_verdict.get("status") != "pass":
        issues.append(
            SemanticGoldCardValidationIssue(
                code="semantic_gold_card_structural_pass_missing",
                message="False-pass fixtures must preserve a passing structural verdict.",
                field="structural_verdict.status",
            )
        )
    semantic_probes = payload.get("semantic_probes")
    if not isinstance(semantic_probes, list) or not semantic_probes:
        issues.append(
            SemanticGoldCardValidationIssue(
                code="semantic_gold_card_probe_missing",
                message="False-pass fixtures must include at least one content-level probe.",
                field="semantic_probes",
            )
        )
    return tuple(issues)


def _evaluation_result(
    *,
    fixture_status: str,
    structural_status: str,
    semantic_status: str,
    expected_failure_code: str | None,
    detected_failure_codes: Iterable[str],
    issues: Iterable[SemanticGoldCardValidationIssue],
    fixture_id: str | None = None,
    failure_mode: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.semantic_gold_card.evaluation.v1",
        "fixture_id": fixture_id,
        "failure_mode": failure_mode,
        "fixture_status": fixture_status,
        "structural_status": structural_status,
        "semantic_status": semantic_status,
        "expected_failure_code": expected_failure_code,
        "detected_failure_codes": list(detected_failure_codes),
        "issues": [issue.as_dict() for issue in issues],
    }


def _pack_result(
    *,
    pack_id: str | None,
    status: str,
    split_summary: Mapping[str, int],
    detected_failure_modes: Iterable[str],
    detected_failure_codes: Iterable[str],
    detected_pattern_ids: Iterable[str],
    issues: Iterable[SemanticGoldCardValidationIssue],
) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.semantic_evaluation_pack.result.v1",
        "pack_id": pack_id,
        "status": status,
        "split_summary": dict(split_summary),
        "detected_failure_modes": list(detected_failure_modes),
        "detected_failure_codes": list(detected_failure_codes),
        "detected_pattern_ids": list(detected_pattern_ids),
        "issues": [issue.as_dict() for issue in issues],
    }


def _detected_failure_codes(card: PolicyDesignCaseSemanticGoldCardFixture) -> set[str]:
    detectors = {
        "projection_laundering": _detect_projection_laundering,
        "participation_laundering": _detect_participation_laundering,
        "participation_prevalence_negative": _detect_participation_prevalence_negative,
        "raw_count_inflation": _detect_raw_count_inflation,
        "method_mismatch": _detect_method_mismatch,
        "stale_evidence": _detect_stale_evidence,
        "llm_speculation": _detect_llm_speculation,
        "unsupported_claim": _detect_unsupported_claim,
        "unreachable_recourse_pointer": _detect_unreachable_recourse_pointer,
        "tuned_threshold_hardcoding": _detect_tuned_threshold_hardcoding,
    }
    detector = detectors[card.failure_mode]
    return detector(card.payload)


def _detect_projection_laundering(payload: Mapping[str, Any]) -> set[str]:
    projection = _mapping(payload.get("projection"))
    authority_chain = _mapping(payload.get("authority_chain"))
    publishable = projection.get("claims_publishable") is True or (
        _normalized(projection.get("public_status")) in _PUBLISHABLE_STATUSES
    )
    closeout_ref = _text(authority_chain.get("closeout_evidence_ref"))
    forbidden_uses = set(_text_values(authority_chain.get("may_not_use_for")))
    if publishable and closeout_ref is None and "closeout" in forbidden_uses:
        return {"semantic_projection_laundering"}
    return set()


def _detect_participation_laundering(payload: Mapping[str, Any]) -> set[str]:
    participation = _mapping(payload.get("participation"))
    final_claim = _mapping(payload.get("final_claim"))
    unrepresented = _text_values(participation.get("unrepresented_classes"))
    claimed_status = _normalized(participation.get("claimed_status"))
    downgrade_ref = _text(participation.get("downgrade_ref"))
    uses_legitimacy = final_claim.get("uses_participation_for_legitimacy") is True
    if (
        claimed_status in {"adequate", "representative", "legitimate"}
        and unrepresented
        and uses_legitimacy
        and downgrade_ref is None
    ):
        return {"semantic_participation_laundering"}
    return set()


def _detect_participation_prevalence_negative(payload: Mapping[str, Any]) -> set[str]:
    participation = _mapping(payload.get("participation"))
    projection = _mapping(payload.get("projection") or payload.get("final_claim"))
    requested_use = _normalized(
        participation.get("claim_use_requested") or projection.get("participation_claim_use")
    )
    allowed_use = _normalized(participation.get("claim_use_allowed"))
    authority_level = _normalized(participation.get("authority_level"))
    population_scope = _normalized(
        participation.get("population_scope") or projection.get("population_scope")
    )
    representativeness = _normalized(participation.get("representativeness_class"))
    provenance_class = _normalized(participation.get("provenance_class"))
    source_kind = _normalized(participation.get("source_kind"))
    projected_use = _normalized(
        projection.get("participation_claim_use") or projection.get("claim_use")
    )
    prevalence_claimed = requested_use == "prevalence" and (
        projected_use == "prevalence"
        or projection.get("prevalence_supported") is True
        or _normalized(projection.get("participation_prevalence_status")) in _PUBLISHABLE_STATUSES
    )
    downgrade_or_blocker = _text(
        participation.get("downgrade_ref")
        or participation.get("blocker_ref")
        or participation.get("limitation_ref")
    )
    insufficient_basis = (
        allowed_use not in {"prevalence", "population_prevalence"}
        or representativeness in {"nonrepresentative", "unknown", "self_selected"}
        or provenance_class.startswith(("c_", "d_"))
        or source_kind in {"consultation", "hearing", "testimony", "expert_interview"}
    )
    if (
        prevalence_claimed
        and authority_level in {"governed", "production"}
        and population_scope in {"affected_population", "general_population", "affected_subgroup"}
        and insufficient_basis
        and downgrade_or_blocker is None
    ):
        return {"semantic_participation_prevalence_negative"}
    return set()


def _detect_raw_count_inflation(payload: Mapping[str, Any]) -> set[str]:
    strength = _mapping(payload.get("evidence_strength"))
    raw_count = _int_or_none(strength.get("raw_evidence_line_count"))
    effective_count = _int_or_none(strength.get("effective_independent_evidence_count"))
    projected_strength = _normalized(strength.get("projected_strength"))
    collapse_clusters = strength.get("collapse_clusters")
    if raw_count is None or effective_count is None:
        return set()
    has_collapse = isinstance(collapse_clusters, list) and bool(collapse_clusters)
    if raw_count > effective_count and projected_strength == "strong" and has_collapse:
        return {"semantic_raw_count_inflation"}
    return set()


def _detect_method_mismatch(payload: Mapping[str, Any]) -> set[str]:
    binding = _mapping(payload.get("method_binding"))
    required = _normalized(binding.get("required_method_family"))
    selected = _normalized(binding.get("selected_method_family"))
    status = _normalized(binding.get("compatibility_status"))
    claim_verb = _normalized(binding.get("claim_verb"))
    causal_claim = claim_verb in {"cause", "causes", "causal", "reduces", "increases"}
    if (
        causal_claim
        and required
        and selected
        and required != selected
        and status == "claimed_compatible"
    ):
        return {"semantic_method_mismatch"}
    return set()


def _detect_stale_evidence(payload: Mapping[str, Any]) -> set[str]:
    freshness = _mapping(payload.get("freshness"))
    policy_time = _date_or_none(freshness.get("policy_time"))
    if policy_time is None:
        return set()
    for evidence in _mapping_items(freshness.get("evidence")):
        evidence_as_of = _date_or_none(evidence.get("evidence_as_of"))
        window_days = _int_or_none(evidence.get("acceptable_recency_window_days"))
        freshness_status = _normalized(evidence.get("freshness_status"))
        if evidence_as_of is None or window_days is None:
            continue
        if (
            policy_time - evidence_as_of
        ).days > window_days and freshness_status in _CURRENT_FRESHNESS_STATUSES:
            return {"semantic_stale_evidence"}
    return set()


def _detect_llm_speculation(payload: Mapping[str, Any]) -> set[str]:
    source_classification = _mapping(payload.get("source_classification"))
    for slot in _mapping_items(source_classification.get("authority_slots")):
        source_kind = _normalized(slot.get("source_kind"))
        used_as_authority = slot.get("used_as_authority") is True
        producer_validation_ref = _text(slot.get("producer_validation_ref"))
        if (
            source_kind in _LLM_SOURCE_KINDS
            and used_as_authority
            and producer_validation_ref is None
        ):
            return {"semantic_llm_speculation_laundering"}
    return set()


def _detect_unsupported_claim(payload: Mapping[str, Any]) -> set[str]:
    support = _mapping(payload.get("claim_support"))
    claimed_status = _normalized(
        support.get("claimed_support_status")
        or support.get("support_status")
        or support.get("projected_support")
    )
    publication_status = _normalized(
        support.get("publication_status") or support.get("public_status")
    )
    publishable = (
        support.get("projected_publishable") is True or publication_status in _PUBLISHABLE_STATUSES
    )
    supporting_refs = _text_values(
        support.get("supporting_evidence_refs") or support.get("evidence_refs")
    )
    blocker_ref = _text(
        support.get("blocker_ref") or support.get("deficit_ref") or support.get("limitation_ref")
    )
    if (
        (claimed_status in {"supported", "strong", "admissible", "publishable"} or publishable)
        and not supporting_refs
        and blocker_ref is None
    ):
        return {"semantic_unsupported_claim"}
    return set()


def _detect_unreachable_recourse_pointer(payload: Mapping[str, Any]) -> set[str]:
    from polisyos.runtime.quality.contestability import (
        PolicyDesignContestabilityError,
        verified_recourse_pointer_for_publication,
    )

    policy_design_case = _mapping(payload.get("policy_design_case")) or payload
    projection_payload = _mapping(payload.get("projection")) or _mapping(
        payload.get("contestability")
    )
    if not projection_payload:
        projection_payload = payload
    try:
        verified_recourse_pointer_for_publication(
            policy_design_case=policy_design_case,
            projection_payload=projection_payload,
        )
    except PolicyDesignContestabilityError as exc:
        if exc.code == "public_export_recourse_pointer_unreachable":
            return {"semantic_recourse_pointer_unreachable"}
    return set()


def _detect_tuned_threshold_hardcoding(payload: Mapping[str, Any]) -> set[str]:
    tuned_parameters = _mapping(
        payload.get("tuned_parameters")
        or payload.get("governed_config")
        or payload.get("thresholds")
    )
    parameters = _mapping_items(
        tuned_parameters.get("parameters")
        or tuned_parameters.get("thresholds")
        or tuned_parameters.get("values")
    )
    if not parameters and tuned_parameters:
        parameters = (tuned_parameters,)
    public_output = _mapping(
        tuned_parameters.get("public_output")
        or payload.get("projection")
        or payload.get("public_output")
    )
    threshold_claimed_final = (
        _normalized(public_output.get("threshold_status")) in {"final", "hardcoded_final"}
        or public_output.get("claims_structural_truth") is True
    )
    if not threshold_claimed_final:
        return set()
    for parameter in parameters:
        status = _normalized(
            parameter.get("status") or parameter.get("config_status") or parameter.get("posture")
        )
        missing_governance = not any(
            _text(parameter.get(key))
            for key in ("owner", "config_ref", "governed_config_ref", "adr_ref", "version")
        )
        if (
            status in {"hardcoded", "hardcoded_final", "final", "fixed_final"}
            and missing_governance
        ):
            return {"semantic_tuned_threshold_hardcoding"}
    return set()


def _structural_status(payload: Mapping[str, Any]) -> str:
    structural_verdict = payload.get("structural_verdict") if isinstance(payload, Mapping) else None
    if isinstance(structural_verdict, Mapping):
        status = _text(structural_verdict.get("status"))
        if status is not None:
            return status
    return "unknown"


def _expected_failure_code(payload: Mapping[str, Any]) -> str | None:
    adjudication = payload.get("semantic_adjudication") if isinstance(payload, Mapping) else None
    if isinstance(adjudication, Mapping):
        return _text(adjudication.get("failure_code"))
    return None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_items(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = _text(value)
        return (text,) if text is not None else ()
    if not isinstance(value, list):
        return ()
    values: list[str] = []
    for item in value:
        text = _text(item)
        if text is not None:
            values.append(text)
    return tuple(values)


def _normalized(value: object) -> str:
    text = _text(value)
    return text.lower() if text is not None else ""


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def _date_or_none(value: object) -> date | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


__all__ = [
    "SEMANTIC_EVALUATION_PACK_CONTRACT_ID",
    "SEMANTIC_EVALUATION_PACK_SCHEMA_VERSION",
    "SEMANTIC_GOLD_CARD_CONTRACT_ID",
    "SEMANTIC_GOLD_CARD_SCHEMA_VERSION",
    "PolicyDesignCaseSemanticEvaluationPack",
    "PolicyDesignCaseSemanticGoldCardFixture",
    "SemanticAdjudication",
    "SemanticEvaluationFixtureEntry",
    "SemanticEvaluationPackSplit",
    "SemanticEvaluationRotationPolicy",
    "SemanticGoldCardValidationIssue",
    "SemanticProbe",
    "SemanticStructuralVerdict",
    "evaluate_semantic_evaluation_pack",
    "evaluate_semantic_gold_card_fixture",
    "semantic_evaluation_pack_json_schema",
    "semantic_gold_card_json_schema",
]
