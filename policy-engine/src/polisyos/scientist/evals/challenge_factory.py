"""Adversarial challenge factory contracts and registry admission helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evals.leakage import detect_benchmark_contamination
from polisyos.scientist.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.search.failure_cards import TypedFailureCard

__all__ = [
    "ChallengeClass",
    "ChallengeFactoryReport",
    "ChallengeSeed",
    "ChallengeSeedKind",
    "ChallengeStatus",
    "GeneratedChallenge",
    "REQUIRED_CHALLENGE_CLASSES",
    "assert_challenge_public_export_clean",
    "challenge_class_for_failure_card",
    "export_public_challenge_factory_report",
    "generate_challenge_from_failure_card",
    "generate_challenge_from_seed",
    "generate_challenge_report_from_failure_cards",
    "generate_challenge_report_from_seeds",
    "mutate_generated_challenge",
    "promote_generated_challenge",
    "register_challenge_pack_with_benchmark_registry",
]


class ChallengeStatus(StrEnum):
    """Review and admission lifecycle for generated challenges."""

    GENERATED = "generated"
    REVIEW_REQUIRED = "review_required"
    APPROVED_FOR_PUBLIC = "approved_for_public"
    APPROVED_FOR_PRIVATE = "approved_for_private"
    APPROVED_FOR_HIDDEN = "approved_for_hidden"
    REJECTED = "rejected"
    RETIRED = "retired"


class ChallengeClass(StrEnum):
    """Required Phase 2.5 adversarial challenge classes."""

    SOURCE_CONTRADICTION = "source_contradiction"
    STALE_SOURCE = "stale_source"
    FORGED_CITATION = "forged_citation"
    MISSING_TRANSPORTABILITY_ASSUMPTION = "missing_transportability_assumption"
    HIDDEN_CONFOUNDING_PROXY_ASSUMPTION_TRAP = "hidden_confounding_proxy_assumption_trap"
    FAIRNESS_THRESHOLD_REVERSAL = "fairness_threshold_reversal"
    LEGAL_EXCEPTION = "legal_exception"
    POLICY_GAMING_STRATEGIC_RESPONSE = "policy_gaming_strategic_response"
    BUDGET_INFEASIBILITY = "budget_infeasibility"
    AMBIGUOUS_HUMAN_REVIEW_INSTRUCTION = "ambiguous_human_review_instruction"


class ChallengeSeedKind(StrEnum):
    """Input source for challenge generation."""

    FAILURE_CARD = "failure_card"
    NEAR_MISS = "near_miss"
    POLICY_DOMAIN_RISK = "policy_domain_risk"


REQUIRED_CHALLENGE_CLASSES: tuple[str, ...] = tuple(item.value for item in ChallengeClass)
_HIDDEN_ADMISSION_STATUSES = {ChallengeStatus.APPROVED_FOR_HIDDEN}
_PUBLIC_PRIVATE_ADMISSION_STATUSES = {
    ChallengeStatus.APPROVED_FOR_PUBLIC,
    ChallengeStatus.APPROVED_FOR_PRIVATE,
    ChallengeStatus.APPROVED_FOR_HIDDEN,
}
_PRIVATE_DATA_KEYS = {
    "private_data",
    "contains_private_data",
    "private_source",
    "pii",
    "sensitive_data",
    "tenant_private",
}


class GeneratedChallenge(BaseModel):
    """Candidate challenge generated from a failure, near-miss, or risk pattern."""

    model_config = ConfigDict(extra="forbid")

    challenge_id: str = Field(min_length=1)
    challenge_class: str = Field(min_length=1)
    source_failure_refs: list[ArtifactRef] = Field(default_factory=list)
    prompt_or_case_ref: ArtifactRef
    expected_failure_mode: str = Field(min_length=1)
    status: ChallengeStatus = ChallengeStatus.GENERATED
    leakage_risk: Literal["low", "medium", "high"] = "medium"
    reviewer_refs: list[ArtifactRef] = Field(default_factory=list)
    source_failure_types: list[str] = Field(default_factory=list)
    source_seed_ids: list[str] = Field(default_factory=list)
    source_seed_kind: ChallengeSeedKind | None = None
    lineage_key: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_hidden_admission(self) -> GeneratedChallenge:
        if self.status in _HIDDEN_ADMISSION_STATUSES and not self.reviewer_refs:
            raise ValueError("hidden challenge admission requires reviewer_refs")
        if self.status in _HIDDEN_ADMISSION_STATUSES and self.leakage_risk == "high":
            raise ValueError("high-leakage generated challenge cannot be admitted as hidden")
        if self.lineage_key is None:
            self.lineage_key = _stable_lineage_key(
                self.challenge_class,
                self.expected_failure_mode,
                self.source_failure_types,
                self.source_failure_refs,
            )
        return self


class ChallengeSeed(BaseModel):
    """Near-miss or policy-domain risk seed for candidate challenge generation."""

    model_config = ConfigDict(extra="forbid")

    seed_id: str = Field(min_length=1)
    seed_kind: ChallengeSeedKind
    challenge_class: ChallengeClass
    prompt_or_case_ref: ArtifactRef
    expected_failure_mode: str = Field(min_length=1)
    source_refs: list[ArtifactRef] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    leakage_risk: Literal["low", "medium", "high"] = "medium"
    private_data: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChallengeFactoryReport(BaseModel):
    """One shadow-mode challenge-factory run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    generated: list[GeneratedChallenge] = Field(default_factory=list)
    promoted_pack_refs: list[ArtifactRef] = Field(default_factory=list)
    rejected_reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_generated_hidden_items(self) -> ChallengeFactoryReport:
        for challenge in self.generated:
            if challenge.status in _HIDDEN_ADMISSION_STATUSES and not challenge.reviewer_refs:
                raise ValueError("hidden challenge in report requires reviewer_refs")
        return self


def challenge_class_for_failure_card(failure_card: TypedFailureCard) -> ChallengeClass:
    """Map existing failure-card signals to a Phase 2.5 challenge class."""

    explicit = str(failure_card.metadata.get("challenge_class") or "").strip().lower()
    if explicit:
        try:
            return ChallengeClass(explicit)
        except ValueError:
            pass
    text = " ".join(
        [
            failure_card.failure_type,
            failure_card.judge_name,
            failure_card.description,
            failure_card.remediation_hint or "",
            " ".join(str(tag) for tag in failure_card.metadata.get("tags", []) or []),
        ]
    ).lower()
    mapping: tuple[tuple[tuple[str, ...], ChallengeClass], ...] = (
        (("contradict", "conflict", "inconsistent source"), ChallengeClass.SOURCE_CONTRADICTION),
        (("stale", "fresh", "recency", "withdrawn"), ChallengeClass.STALE_SOURCE),
        (("citation", "quote", "forged", "hallucinated_source"), ChallengeClass.FORGED_CITATION),
        (
            ("transport", "external_validity", "portability"),
            ChallengeClass.MISSING_TRANSPORTABILITY_ASSUMPTION,
        ),
        (
            ("confound", "proxy", "omitted", "unobserved"),
            ChallengeClass.HIDDEN_CONFOUNDING_PROXY_ASSUMPTION_TRAP,
        ),
        (("fairness", "equity", "threshold"), ChallengeClass.FAIRNESS_THRESHOLD_REVERSAL),
        (("legal", "statute", "exception", "jurisdiction"), ChallengeClass.LEGAL_EXCEPTION),
        (("gaming", "strategic", "incentive", "ic_"), ChallengeClass.POLICY_GAMING_STRATEGIC_RESPONSE),
        (("budget", "cost", "infeasible", "feasibility"), ChallengeClass.BUDGET_INFEASIBILITY),
        (
            ("human_review", "reviewer", "escalation", "explanation", "ambiguous"),
            ChallengeClass.AMBIGUOUS_HUMAN_REVIEW_INSTRUCTION,
        ),
    )
    for needles, challenge_class in mapping:
        if any(needle in text for needle in needles):
            return challenge_class
    return ChallengeClass.SOURCE_CONTRADICTION


def generate_challenge_from_failure_card(
    failure_card: TypedFailureCard,
    *,
    run_id: str,
    prompt_or_case_ref: ArtifactRef,
    target_visibility: Literal["public", "private", "hidden"] = "private",
    challenge_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> GeneratedChallenge:
    """Create a review-required candidate challenge from a failure card."""

    if target_visibility == "public" and _failure_card_has_private_data(failure_card):
        raise ValueError("failure card with private data cannot generate public challenge content")
    challenge_class = challenge_class_for_failure_card(failure_card)
    source_failure_refs = [failure_card.evidence_ref] if failure_card.evidence_ref else []
    expected_failure_mode = _expected_failure_mode(failure_card, challenge_class)
    generated_id = challenge_id or _stable_id(
        "challenge",
        run_id,
        failure_card.judge_name,
        failure_card.failure_type,
        expected_failure_mode,
        str(prompt_or_case_ref.artifact_id),
    )
    status = ChallengeStatus.REVIEW_REQUIRED
    if target_visibility == "public":
        status = ChallengeStatus.REVIEW_REQUIRED
    return GeneratedChallenge(
        challenge_id=generated_id,
        challenge_class=challenge_class.value,
        source_failure_refs=source_failure_refs,
        prompt_or_case_ref=prompt_or_case_ref,
        expected_failure_mode=expected_failure_mode,
        status=status,
        leakage_risk=_leakage_risk_for_failure_card(failure_card, target_visibility),
        source_failure_types=[failure_card.failure_type],
        source_seed_ids=[failure_card.failure_type],
        source_seed_kind=ChallengeSeedKind.FAILURE_CARD,
        metadata={
            "run_id": run_id,
            "judge_name": failure_card.judge_name,
            "severity": getattr(failure_card.severity, "value", str(failure_card.severity)),
            "target_visibility": target_visibility,
            **(metadata or {}),
        },
    )


def generate_challenge_from_seed(
    seed: ChallengeSeed,
    *,
    run_id: str,
    target_visibility: Literal["public", "private", "hidden"] = "private",
    challenge_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> GeneratedChallenge:
    """Create a review-required challenge from a near-miss or policy-domain risk seed."""

    if target_visibility == "public" and seed.private_data:
        raise ValueError("seed with private data cannot generate public challenge content")
    generated_id = challenge_id or _stable_id(
        "challenge",
        run_id,
        seed.seed_kind.value,
        seed.seed_id,
        seed.challenge_class.value,
        str(seed.prompt_or_case_ref.artifact_id),
    )
    leakage_risk = "high" if target_visibility == "public" and seed.private_data else seed.leakage_risk
    return GeneratedChallenge(
        challenge_id=generated_id,
        challenge_class=seed.challenge_class.value,
        source_failure_refs=list(seed.source_refs),
        prompt_or_case_ref=seed.prompt_or_case_ref,
        expected_failure_mode=seed.expected_failure_mode,
        status=ChallengeStatus.REVIEW_REQUIRED,
        leakage_risk=leakage_risk,
        source_seed_ids=[seed.seed_id],
        source_seed_kind=seed.seed_kind,
        metadata={
            "run_id": run_id,
            "seed_summary": seed.summary,
            "seed_kind": seed.seed_kind.value,
            "target_visibility": target_visibility,
            **seed.metadata,
            **(metadata or {}),
        },
    )


def generate_challenge_report_from_seeds(
    *,
    run_id: str,
    seeds: Iterable[ChallengeSeed],
    target_visibility: Literal["public", "private", "hidden"] = "private",
    metadata: dict[str, Any] | None = None,
) -> ChallengeFactoryReport:
    """Generate candidate challenges from near-miss and policy-domain risk seeds."""

    generated: list[GeneratedChallenge] = []
    rejected_reasons: list[str] = []
    for seed in seeds:
        try:
            generated.append(
                generate_challenge_from_seed(
                    seed,
                    run_id=run_id,
                    target_visibility=target_visibility,
                )
            )
        except ValueError as exc:
            rejected_reasons.append(f"{seed.seed_id}:{exc}")
    return ChallengeFactoryReport(
        run_id=run_id,
        generated=generated,
        rejected_reasons=rejected_reasons,
        metadata=metadata or {},
    )


def generate_challenge_report_from_failure_cards(
    *,
    run_id: str,
    failure_cards: Iterable[TypedFailureCard],
    prompt_or_case_refs: Iterable[ArtifactRef],
    target_visibility: Literal["public", "private", "hidden"] = "private",
    metadata: dict[str, Any] | None = None,
) -> ChallengeFactoryReport:
    """Generate a shadow-mode challenge report from failure cards."""

    refs = list(prompt_or_case_refs)
    if not refs:
        raise ValueError("prompt_or_case_refs must include at least one ArtifactRef")
    generated: list[GeneratedChallenge] = []
    rejected_reasons: list[str] = []
    for index, failure_card in enumerate(failure_cards):
        prompt_ref = refs[index % len(refs)]
        try:
            generated.append(
                generate_challenge_from_failure_card(
                    failure_card,
                    run_id=run_id,
                    prompt_or_case_ref=prompt_ref,
                    target_visibility=target_visibility,
                )
            )
        except ValueError as exc:
            rejected_reasons.append(f"{failure_card.failure_type}:{exc}")
    return ChallengeFactoryReport(
        run_id=run_id,
        generated=generated,
        rejected_reasons=rejected_reasons,
        metadata=metadata or {},
    )


def mutate_generated_challenge(
    challenge: GeneratedChallenge,
    *,
    mutation_strategy: str,
    prompt_or_case_ref: ArtifactRef | None = None,
    expected_failure_mode: str | None = None,
    challenge_class: ChallengeClass | str | None = None,
    metadata: dict[str, Any] | None = None,
) -> GeneratedChallenge:
    """Create a review-required mutation of a generated challenge.

    Mutations inherit lineage but reset review state; a mutated case must be
    reviewed before it can enter public, private, rotating or hidden packs.
    """

    strategy = str(mutation_strategy or "").strip()
    if not strategy:
        raise ValueError("mutation_strategy must be non-empty")
    resolved_class = _coerce_challenge_class(challenge_class) if challenge_class else challenge.challenge_class
    resolved_failure_mode = (
        expected_failure_mode
        or f"{challenge.expected_failure_mode}; mutation={strategy}"
    )[:1000]
    mutation_id = _stable_id(
        "challenge",
        "mutation",
        challenge.challenge_id,
        strategy,
        resolved_class,
        resolved_failure_mode,
        str((prompt_or_case_ref or challenge.prompt_or_case_ref).artifact_id),
    )
    return GeneratedChallenge(
        challenge_id=mutation_id,
        challenge_class=resolved_class,
        source_failure_refs=list(challenge.source_failure_refs),
        prompt_or_case_ref=prompt_or_case_ref or challenge.prompt_or_case_ref,
        expected_failure_mode=resolved_failure_mode,
        status=ChallengeStatus.REVIEW_REQUIRED,
        leakage_risk=challenge.leakage_risk,
        source_failure_types=list(challenge.source_failure_types),
        source_seed_ids=list({*challenge.source_seed_ids, challenge.challenge_id}),
        source_seed_kind=challenge.source_seed_kind,
        metadata={
            **challenge.metadata,
            "parent_challenge_id": challenge.challenge_id,
            "parent_lineage_key": challenge.lineage_key,
            "mutation_strategy": strategy,
            **(metadata or {}),
        },
    )


def promote_generated_challenge(
    challenge: GeneratedChallenge,
    *,
    status: ChallengeStatus,
    reviewer_refs: Iterable[ArtifactRef] = (),
    leakage_risk: Literal["low", "medium", "high"] | None = None,
) -> GeneratedChallenge:
    """Return a reviewed challenge copy promoted to a public/private/hidden status."""

    reviewers = list(reviewer_refs) or list(challenge.reviewer_refs)
    if status in _PUBLIC_PRIVATE_ADMISSION_STATUSES and not reviewers:
        raise ValueError("challenge promotion requires reviewer_refs")
    final_leakage_risk = leakage_risk or challenge.leakage_risk
    if status is ChallengeStatus.APPROVED_FOR_HIDDEN and final_leakage_risk == "high":
        raise ValueError("high-leakage generated challenge cannot be admitted as hidden")
    return challenge.model_copy(
        update={
            "status": status,
            "reviewer_refs": reviewers,
            **({"leakage_risk": leakage_risk} if leakage_risk is not None else {}),
        }
    )


def register_challenge_pack_with_benchmark_registry(
    registry: BenchmarkRegistry,
    *,
    split_type: Literal["public", "private", "hidden_holdout", "rotating_challenge", "sentinel", "adversarial"],
    pack_ref: ArtifactRef,
    challenges: Iterable[GeneratedChallenge],
    family: str,
    loop_id: str | None = None,
    run_id: str | None = None,
    suite_id: str | None = None,
    rotation_group: str | None = None,
    benchmark_revision: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Register a reviewed challenge pack with `BenchmarkRegistry`.

    Generated challenges are never admitted as hidden benchmark evidence here.
    Hidden and private splits require reviewed hidden approval.
    """

    challenge_list = list(challenges)
    if not challenge_list:
        raise ValueError("challenge pack registration requires at least one challenge")
    if split_type == "hidden_holdout":
        _assert_all_hidden_approved(challenge_list)
    elif split_type in {"public", "private", "rotating_challenge", "sentinel", "adversarial"}:
        _assert_all_reviewed(challenge_list)
    lineage = _lineage_metadata(challenge_list)
    lineage["kind"] = split_type
    lineage["status"] = "active"
    registry.record(
        split_type,
        pack_ref,
        run_id=run_id,
        loop_id=loop_id,
        suite_id=suite_id,
        family=family,
        artifact_kind=pack_ref.kind,
        rotation_group=rotation_group,
        visibility=_visibility_for_split(split_type),
        benchmark_revision=benchmark_revision,
        metadata={
            "challenge_pack_lineage": lineage,
            "review_before_hidden": True,
            **(metadata or {}),
        },
    )


def assert_challenge_public_export_clean(
    payload: Any,
    *,
    hidden_ref_ids: set[str] | None = None,
    hidden_suite_ids: set[str] | None = None,
    canary_tokens: set[str] | None = None,
) -> None:
    """Raise when a challenge payload contains hidden refs, suite ids or canaries."""

    findings = detect_benchmark_contamination(
        payload,
        hidden_ref_ids=hidden_ref_ids or set(),
        hidden_suite_ids=hidden_suite_ids or set(),
    )
    rendered = json.dumps(payload, sort_keys=True, default=str)
    for token in sorted(canary_tokens or set()):
        if token and token in rendered:
            findings.append(
                type(findings[0])(
                    token_kind="canary",
                    token=token,
                    message="hidden challenge canary leaked into public challenge export",
                )
                if findings
                else _canary_finding(token)
            )
    if findings:
        tokens = ", ".join(f"{finding.token_kind}:{finding.token}" for finding in findings)
        raise ValueError(f"challenge public export contamination detected: {tokens}")


def export_public_challenge_factory_report(
    report: ChallengeFactoryReport,
    *,
    hidden_ref_ids: set[str] | None = None,
    hidden_suite_ids: set[str] | None = None,
    canary_tokens: set[str] | None = None,
) -> dict[str, Any]:
    """Return a public-safe challenge-factory summary after contamination scan."""

    assert_challenge_public_export_clean(
        report.model_dump(mode="json"),
        hidden_ref_ids=hidden_ref_ids,
        hidden_suite_ids=hidden_suite_ids,
        canary_tokens=canary_tokens,
    )
    return {
        "schema_version": report.schema_version,
        "run_id": report.run_id,
        "generated_count": len(report.generated),
        "promoted_pack_count": len(report.promoted_pack_refs),
        "rejected_count": len(report.rejected_reasons),
        "challenge_classes": sorted({item.challenge_class for item in report.generated}),
        "statuses": sorted({item.status.value for item in report.generated}),
        "lineage_keys": sorted({item.lineage_key for item in report.generated if item.lineage_key}),
    }


def _canary_finding(token: str):
    from polisyos.scientist.evals.leakage import BenchmarkContaminationFinding

    return BenchmarkContaminationFinding(
        token_kind="canary",
        token=token,
        message="hidden challenge canary leaked into public challenge export",
    )


def _assert_all_hidden_approved(challenges: list[GeneratedChallenge]) -> None:
    for challenge in challenges:
        if challenge.status is not ChallengeStatus.APPROVED_FOR_HIDDEN or not challenge.reviewer_refs:
            raise ValueError("generated challenge cannot be registered as hidden without review refs")


def _assert_all_reviewed(challenges: list[GeneratedChallenge]) -> None:
    for challenge in challenges:
        if challenge.status not in _PUBLIC_PRIVATE_ADMISSION_STATUSES or not challenge.reviewer_refs:
            raise ValueError("generated challenge cannot be registered before review promotion")


def _lineage_metadata(challenges: list[GeneratedChallenge]) -> dict[str, Any]:
    source_failure_ref_ids = sorted(
        {
            str(ref.artifact_id)
            for challenge in challenges
            for ref in challenge.source_failure_refs
        }
    )
    source_challenge_ids = sorted({challenge.challenge_id for challenge in challenges})
    lineage_key = _stable_id(
        "challenge-lineage",
        ",".join(sorted(challenge.lineage_key or challenge.challenge_id for challenge in challenges)),
    )
    return {
        "lineage_key": lineage_key,
        "source_challenge_ids": source_challenge_ids,
        "source_failure_ref_ids": source_failure_ref_ids,
        "challenge_classes": sorted({challenge.challenge_class for challenge in challenges}),
        "reviewer_ref_ids": sorted(
            {
                str(ref.artifact_id)
                for challenge in challenges
                for ref in challenge.reviewer_refs
            }
        ),
        "statuses": sorted({challenge.status.value for challenge in challenges}),
    }


def _visibility_for_split(split_type: str) -> str:
    if split_type == "public":
        return "public"
    if split_type in {"hidden_holdout", "sentinel"}:
        return "hidden"
    return "private"


def _expected_failure_mode(
    failure_card: TypedFailureCard,
    challenge_class: ChallengeClass,
) -> str:
    hint = failure_card.remediation_hint or "Add a reviewable challenge for this failure mode."
    return f"{challenge_class.value}:{failure_card.failure_type}:{hint}"[:1000]


def _leakage_risk_for_failure_card(
    failure_card: TypedFailureCard,
    target_visibility: str,
) -> Literal["low", "medium", "high"]:
    explicit = str(failure_card.metadata.get("leakage_risk") or "").strip().lower()
    if explicit in {"low", "medium", "high"}:
        return explicit  # type: ignore[return-value]
    if _failure_card_has_private_data(failure_card):
        return "high" if target_visibility == "public" else "medium"
    if target_visibility == "hidden":
        return "medium"
    return "low"


def _failure_card_has_private_data(failure_card: TypedFailureCard) -> bool:
    metadata = failure_card.metadata or {}
    for key, value in metadata.items():
        if str(key).lower() in _PRIVATE_DATA_KEYS and bool(value):
            return True
    tags = metadata.get("tags") or []
    if isinstance(tags, list | tuple | set):
        return any(str(tag).strip().lower() in _PRIVATE_DATA_KEYS for tag in tags)
    return False


def _stable_id(prefix: str, *parts: object) -> str:
    material = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _coerce_challenge_class(value: ChallengeClass | str) -> str:
    if isinstance(value, ChallengeClass):
        return value.value
    return ChallengeClass(str(value)).value


def _stable_lineage_key(
    challenge_class: str,
    expected_failure_mode: str,
    source_failure_types: list[str],
    source_failure_refs: list[ArtifactRef],
) -> str:
    return _stable_id(
        "lineage",
        challenge_class,
        expected_failure_mode,
        ",".join(sorted(source_failure_types)),
        ",".join(sorted(str(ref.artifact_id) for ref in source_failure_refs)),
    )
