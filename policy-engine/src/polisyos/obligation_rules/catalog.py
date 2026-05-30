"""Governed obligation rule catalog for universal Policy Design Cases."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.contracts import (
    build_rule_evolution_registry,
    logic_hash_for_rule,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

ID_PATTERN = r"^[a-z][a-z0-9_.-]*$"


class ObligationRuleModel(BaseModel):
    """Strict immutable base model for obligation-rule contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

OBLIGATION_RULE_CATALOG_SCHEMA_VERSION = "policyos.obligation_rules.catalog.v1"
OBLIGATION_RULE_CATALOG_CONTRACT_ID = (
    "policy_design_case.governed_obligation_rule_catalog.v1"
)
OBLIGATION_RULE_CATALOG_KIND = "obligation_rules.governed_catalog"
OBLIGATION_RULE_CATALOG_SCHEMA = "polisyos.obligation_rules.ObligationRuleCatalog"
OBLIGATION_RULE_PRODUCER_OWNER = "team-policyos-runtime"
OBLIGATION_RULE_READER_OWNER = "team-universal-compilation"
OBLIGATION_RULE_DEFAULT_CATALOG_ID = "policyos.governed_obligation_rules"
OBLIGATION_RULE_DEFAULT_VERSION = "2026.05.0"
OBLIGATION_RULE_DEFAULT_EFFECTIVE_AT = "2026-05-23T00:00:00+00:00"
OBLIGATION_RULE_EVOLUTION_BRIDGE = (
    "polisyos.obligation_rules.build_rule_evolution_registry_for_catalog"
)

_LLM_SOURCE_CLASSES = frozenset(
    {"llm_candidate", "llm_critic", "llm_drafter"}
)


class ObligationRuleGovernanceError(ValueError):
    """Raised when a rule candidate attempts to bypass governance admission."""


class ObligationRuleFamily(str, Enum):
    """Governed obligation rule families consumed by W6.C."""

    LEGAL = "legal"
    FISCAL = "fiscal"
    EQUITY = "equity"
    DATA = "data"
    IMPLEMENTATION = "implementation"
    METHOD = "method"
    PARTICIPATION = "participation"


class ObligationRuleStatus(str, Enum):
    """Lifecycle state for catalog rules."""

    PROPOSED = "proposed"
    GOVERNED = "governed"
    DEPRECATED = "deprecated"
    WITHDRAWN = "withdrawn"


class ObligationRuleSourceClass(str, Enum):
    """Source class for governed rules and unadmitted candidates."""

    GOVERNED_RULE = "governed_rule"
    DETERMINISTIC_CRITIC = "deterministic_critic"
    HISTORICAL_FAILURE = "historical_failure"
    LLM_CANDIDATE = "llm_candidate"
    LLM_CRITIC = "llm_critic"
    LLM_DRAFTER = "llm_drafter"
    HUMAN_REVIEWER = "human_reviewer"
    PUBLIC_CONTESTATION = "public_contestation"


class PublicRevalidationEffect(str, Enum):
    """Public effect for rule changes and withdrawals."""

    NONE = "none"
    ANNOTATE_PUBLIC_SURFACE = "annotate_public_surface"
    REVIEW_OPEN_CASES = "review_open_cases"
    REVALIDATE_OPEN_CASES = "revalidate_open_cases"
    REVALIDATE_PUBLIC_CASES = "revalidate_public_cases"
    WITHDRAW_PUBLIC_CLAIM = "withdraw_public_claim"


class ObligationRuleScope(ObligationRuleModel):
    """Applicability scope for one governed obligation rule."""

    jurisdictions: tuple[str, ...] = Field(default=("global",), min_length=1)
    policy_domains: tuple[str, ...] = Field(default=("universal",), min_length=1)
    authority_profiles: tuple[str, ...] = Field(
        default=("research", "governed", "production"),
        min_length=1,
    )
    temporal_window: str = Field(default="case_lifecycle", min_length=1)
    audience: tuple[str, ...] = Field(
        default=("machine", "reviewer", "expert", "public"),
        min_length=1,
    )


class FacetPredicate(ObligationRuleModel):
    """Structured facet predicate embedded in governed rule logic."""

    facet_type: str = Field(min_length=1)
    value_eq: str | None = Field(default=None, min_length=1)
    value_in: tuple[str, ...] = Field(default=())


class FacetMatchPattern(ObligationRuleModel):
    """Structured AND/OR facet pattern for vertical obligation rules."""

    facet_match_all: tuple[FacetPredicate, ...] = Field(default=())
    facet_match_any: tuple[FacetPredicate, ...] = Field(default=())
    claim_text_contains_any: tuple[str, ...] = Field(default=())
    geography_predicate_eq: str | None = Field(default=None, min_length=1)
    population_predicate_eq: str | None = Field(default=None, min_length=1)


class RuleDeprecationPolicy(ObligationRuleModel):
    """Deprecation and replay policy for a governed rule."""

    policy: str = "supersede_with_explicit_alias_or_semantic_change_record"
    sunset_after: str | None = None
    replacement_rule_id: str | None = Field(default=None, pattern=ID_PATTERN)
    replay_behavior: str = "closed_cases_replay_under_original_logic"
    public_notice_required: bool = True


class ObligationRule(ObligationRuleModel):
    """Governed obligation rule contract consumed by downstream compilers."""

    rule_id: str = Field(pattern=ID_PATTERN)
    rule_family: ObligationRuleFamily
    rule_version: str = Field(min_length=1)
    logic: dict[str, Any]
    logic_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    owner: str = Field(min_length=1)
    scope: ObligationRuleScope
    authority_level: str = Field(min_length=1)
    evidence_basis: tuple[str, ...] = Field(min_length=1)
    status: ObligationRuleStatus = ObligationRuleStatus.GOVERNED
    public_revalidation_effect: PublicRevalidationEffect
    deprecation_policy: RuleDeprecationPolicy = Field(default_factory=RuleDeprecationPolicy)
    source_class: ObligationRuleSourceClass = ObligationRuleSourceClass.GOVERNED_RULE
    source_refs: tuple[str, ...] = Field(min_length=1)
    taxonomy_refs: tuple[str, ...] = Field(default_factory=tuple)
    provenance_refs: tuple[str, ...] = Field(default_factory=tuple)
    candidate_source_class: ObligationRuleSourceClass | None = None
    governance_decision_ref: str | None = None
    validation_refs: tuple[str, ...] = Field(default_factory=tuple)
    may_not_use_for: tuple[str, ...] = Field(
        default=(
            "claim_evidence_authority",
            "silent_rulebook_admission",
            "llm_candidate_authority",
        )
    )

    @model_validator(mode="after")
    def validate_governed_rule(self) -> ObligationRule:
        """Validate governed-rule invariants that protect P07 and P15."""

        if self.status is ObligationRuleStatus.GOVERNED:
            if self.public_revalidation_effect is PublicRevalidationEffect.NONE:
                raise ValueError("governed rules require a public revalidation effect")
            if not self.owner or not self.authority_level or not self.evidence_basis:
                raise ValueError(
                    "governed rules require owner, authority_level, and evidence_basis"
                )
            if (
                self.candidate_source_class is not None
                and self.candidate_source_class.value in _LLM_SOURCE_CLASSES
                and not self.governance_decision_ref
            ):
                raise ValueError("LLM candidates require explicit governance admission")
        return self


class ObligationRuleCandidate(ObligationRuleModel):
    """Unadmitted rule candidate proposed by an LLM, critic, reviewer, or contestation."""

    candidate_id: str = Field(pattern=ID_PATTERN)
    proposed_rule_id: str = Field(pattern=ID_PATTERN)
    rule_family: ObligationRuleFamily
    source_class: ObligationRuleSourceClass
    proposed_logic: dict[str, Any]
    rationale: str = Field(min_length=1)
    prompt_fingerprint: str | None = None
    tool_refs: tuple[str, ...] = Field(default_factory=tuple)
    repair_decision_lineage: tuple[str, ...] = Field(default_factory=tuple)
    source_refs: tuple[str, ...] = Field(default_factory=tuple)
    proposed_scope: ObligationRuleScope = Field(default_factory=ObligationRuleScope)

    @model_validator(mode="after")
    def validate_candidate_source_boundary(self) -> ObligationRuleCandidate:
        """Require LLM provenance before a candidate can enter the catalog side-channel."""

        if self.source_class.value in _LLM_SOURCE_CLASSES and (
            not self.prompt_fingerprint
            or not self.tool_refs
            or not self.repair_decision_lineage
        ):
            raise ValueError(
                "LLM rule candidates require prompt fingerprint, tool refs, "
                "and repair-decision lineage"
            )
        return self


class RuleGovernanceDecision(ObligationRuleModel):
    """Explicit governance decision required to admit a candidate as governed."""

    owner: str = Field(min_length=1)
    authority_level: str = Field(min_length=1)
    evidence_basis: tuple[str, ...] = Field(min_length=1)
    admission_authority_ref: str = Field(min_length=1)
    validation_refs: tuple[str, ...] = Field(min_length=1)
    rule_version: str = OBLIGATION_RULE_DEFAULT_VERSION
    public_revalidation_effect: PublicRevalidationEffect
    scope: ObligationRuleScope | None = None


class ObligationRuleCatalogSummary(ObligationRuleModel):
    """Summary counts for catalog readers and public surfaces."""

    total_rule_count: int
    governed_rule_count: int
    proposed_rule_count: int
    deprecated_rule_count: int
    withdrawn_rule_count: int
    candidate_rule_count: int
    rules_by_family: dict[str, int]


class ObligationRuleCatalog(ObligationRuleModel):
    """Versioned governed obligation rule catalog."""

    schema_version: str = OBLIGATION_RULE_CATALOG_SCHEMA_VERSION
    contract_id: str = OBLIGATION_RULE_CATALOG_CONTRACT_ID
    catalog_id: str = Field(pattern=ID_PATTERN)
    catalog_version: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    effective_at: str = Field(min_length=1)
    catalog_ref: str = Field(min_length=1)
    producer_owner: str = OBLIGATION_RULE_PRODUCER_OWNER
    reader_owner: str = OBLIGATION_RULE_READER_OWNER
    rules: tuple[ObligationRule, ...] = Field(min_length=1)
    candidates: tuple[ObligationRuleCandidate, ...] = Field(default_factory=tuple)
    rule_evolution_registry_ref: str | None = None
    runtime_authority_envelope: dict[str, Any]
    capability_reality: dict[str, Any]
    summary: ObligationRuleCatalogSummary

    @model_validator(mode="after")
    def validate_catalog_identity(self) -> ObligationRuleCatalog:
        """Ensure a catalog cannot hide duplicate rule identities."""

        rule_ids = [rule.rule_id for rule in self.rules]
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("obligation rule catalog contains duplicate rule_id values")
        return self


class _JsonArtifactStore(Protocol):
    """Minimal CAS writer protocol used by obligation-rule persistence."""

    def put_json(
        self,
        payload: object,
        options: object,
    ) -> object:
        """Persist JSON-like payloads and return an artifact reference."""


@dataclass(frozen=True)
class _ArtifactWriteOptions:
    """Local write options shape consumed by CAS stores."""

    kind: str
    media_type: str
    schema: Mapping[str, str]
    producer: object | None = None
    env: object | None = None
    inputs: tuple[object, ...] = ()
    canon: object | None = None


def build_seed_obligation_rule_catalog(
    *,
    catalog_id: str = OBLIGATION_RULE_DEFAULT_CATALOG_ID,
    catalog_version: str = OBLIGATION_RULE_DEFAULT_VERSION,
    effective_at: str = OBLIGATION_RULE_DEFAULT_EFFECTIVE_AT,
    rule_logic_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    candidates: Sequence[ObligationRuleCandidate] = (),
) -> ObligationRuleCatalog:
    """Build the initial governed W6.B obligation rule catalog.

    Args:
        catalog_id: Stable catalog id.
        catalog_version: Catalog and seed rule version.
        effective_at: Effective timestamp for replay and public inspection.
        rule_logic_overrides: Optional per-rule logic overrides for replay tests
            and future governed revisions.
        candidates: Unadmitted rule candidates carried beside, not inside, the
            governed rulebook.

    Returns:
        A replay-safe governed rule catalog with seed rules across all W6.B
        families.
    """

    overrides = dict(rule_logic_overrides or {})
    rules = tuple(
        _build_seed_rule(
            spec,
            catalog_version=catalog_version,
            logic_override=overrides.get(spec["rule_id"]),
        )
        for spec in _seed_rule_specs()
    )
    catalog_ref = _catalog_ref(
        catalog_id=catalog_id,
        catalog_version=catalog_version,
        rules=rules,
    )
    summary = _catalog_summary(rules=rules, candidates=candidates)
    payload = ObligationRuleCatalog(
        catalog_id=catalog_id,
        catalog_version=catalog_version,
        taxonomy_version=catalog_version,
        effective_at=effective_at,
        catalog_ref=catalog_ref,
        rules=rules,
        candidates=tuple(candidates),
        runtime_authority_envelope={
            "authoritative_for": ["governed_obligation_rule_catalog"],
            "may_not_use_for": [
                "claim_evidence_authority",
                "llm_candidate_authority",
                "silent_public_revalidation_policy",
            ],
            "authority_boundary": (
                "governed rules are compilation inputs; candidate rules are never "
                "authority until admitted by a governance decision"
            ),
        },
        capability_reality={
            "reality_state": "implemented",
            "typed_contract_ref": OBLIGATION_RULE_CATALOG_CONTRACT_ID,
            "producer_ref": "polisyos.obligation_rules.build_seed_obligation_rule_catalog",
            "artifact_ref": catalog_ref,
            "bridge_ref": OBLIGATION_RULE_EVOLUTION_BRIDGE,
            "consumer_ref": "polisyos.obligation_rules.select_governed_rules",
            "verification_ref": "tests/unit/obligation_rules/test_catalog.py",
            "surface_ref": "polisyos.obligation_rules.governed_rule_catalog_public_surface",
            "semantic_test_ref": (
                "tests/unit/obligation_rules/test_catalog.py::"
                "test_llm_candidate_cannot_silently_become_governed_rule"
            ),
            "research_refs": ["C5", "C21", "C33", "P06", "P07", "P15"],
            "decision_refs": ["ADR-0163", "ADR-0100"],
            "reuse_classification": "build_new",
            "rejected_reuse_evidence": [
                "W2.B rule_evolution stores refs and replay semantics but not the "
                "governed obligation taxonomy owner.",
                "policy_design critic/objective/adversary modules produce signals, "
                "not governed rulebook entries.",
            ],
            "rollout_refs": ["Wave 6 W6.B", "I7 universal compilation smoke"],
        },
        summary=summary,
    )
    return payload


def build_rule_evolution_registry_for_catalog(
    catalog: ObligationRuleCatalog | Mapping[str, Any],
    *,
    previous_catalog: ObligationRuleCatalog | Mapping[str, Any] | None = None,
    runtime_event_ref: str | None = None,
) -> dict[str, Any]:
    """Bridge the governed obligation catalog into W2.B rule evolution.

    Args:
        catalog: Current obligation rule catalog.
        previous_catalog: Previous catalog version, if semantic-change
            detection is required.
        runtime_event_ref: Optional event reference.

    Returns:
        A W2.B rule-evolution registry preserving W6.B rule metadata.
    """

    current = _coerce_catalog(catalog)
    previous_registry = (
        _catalog_rule_evolution_registry(_coerce_catalog(previous_catalog))
        if previous_catalog is not None
        else None
    )
    registry = _catalog_rule_evolution_registry(
        current,
        previous_registry=previous_registry,
        runtime_event_ref=runtime_event_ref,
    )
    registry["obligation_rule_catalog_ref"] = current.catalog_ref
    registry["obligation_rule_catalog_version"] = current.catalog_version
    registry["capability_reality"]["orchestration_bridge"] = OBLIGATION_RULE_EVOLUTION_BRIDGE
    registry["capability_reality"]["consumer"] = (
        "polisyos.obligation_rules.select_governed_rules"
    )
    return registry


def govern_rule_candidate(
    candidate: ObligationRuleCandidate,
    *,
    decision: RuleGovernanceDecision | None = None,
) -> ObligationRule:
    """Promote a candidate only when explicit governance admission exists.

    Args:
        candidate: Proposed rule candidate.
        decision: Governance decision with owner, authority, evidence basis,
            validation refs, and public revalidation effect.

    Returns:
        A governed obligation rule.

    Raises:
        ObligationRuleGovernanceError: If the candidate lacks the explicit
            governance decision required for admission.
    """

    if decision is None:
        if candidate.source_class.value in _LLM_SOURCE_CLASSES:
            raise ObligationRuleGovernanceError(
                "LLM rule candidates cannot become governed obligation rules "
                "without explicit governance admission."
            )
        raise ObligationRuleGovernanceError(
            "Rule candidates require explicit governance admission."
        )

    logic = dict(candidate.proposed_logic)
    rule = ObligationRule(
        rule_id=candidate.proposed_rule_id,
        rule_family=candidate.rule_family,
        rule_version=decision.rule_version,
        logic=logic,
        logic_hash=_rule_logic_hash(candidate.proposed_rule_id, logic),
        owner=decision.owner,
        scope=decision.scope or candidate.proposed_scope,
        authority_level=decision.authority_level,
        evidence_basis=tuple(decision.evidence_basis),
        status=ObligationRuleStatus.GOVERNED,
        public_revalidation_effect=decision.public_revalidation_effect,
        source_class=ObligationRuleSourceClass.GOVERNED_RULE,
        source_refs=tuple(candidate.source_refs) or (f"candidate://{candidate.candidate_id}",),
        taxonomy_refs=(f"taxonomy.obligation_rules.{candidate.rule_family.value}",),
        provenance_refs=(
            candidate.prompt_fingerprint,
            *candidate.tool_refs,
            *candidate.repair_decision_lineage,
        )
        if candidate.prompt_fingerprint is not None
        else (*candidate.tool_refs, *candidate.repair_decision_lineage),
        candidate_source_class=candidate.source_class,
        governance_decision_ref=decision.admission_authority_ref,
        validation_refs=tuple(decision.validation_refs),
    )
    return rule


def select_governed_rules(
    catalog: ObligationRuleCatalog | Mapping[str, Any],
    *,
    families: Sequence[ObligationRuleFamily | str] | None = None,
    authority_levels: Sequence[str] | None = None,
    jurisdictions: Sequence[str] | None = None,
) -> tuple[ObligationRule, ...]:
    """Select governed rules for downstream obligation compilers."""

    model = _coerce_catalog(catalog)
    family_filter = {
        value.value if isinstance(value, ObligationRuleFamily) else str(value)
        for value in families or ()
    }
    authority_filter = {str(value) for value in authority_levels or ()}
    jurisdiction_filter = {str(value) for value in jurisdictions or ()}
    selected: list[ObligationRule] = []
    for rule in model.rules:
        if rule.status is not ObligationRuleStatus.GOVERNED:
            continue
        if family_filter and rule.rule_family.value not in family_filter:
            continue
        if authority_filter and rule.authority_level not in authority_filter:
            continue
        if jurisdiction_filter and not jurisdiction_filter.intersection(rule.scope.jurisdictions):
            continue
        selected.append(rule)
    return tuple(selected)


def governed_rule_catalog_public_surface(
    catalog: ObligationRuleCatalog | Mapping[str, Any],
) -> dict[str, Any]:
    """Return an audit/public inspection surface for the governed catalog."""

    model = _coerce_catalog(catalog)
    governed_rules = [rule for rule in model.rules if rule.status is ObligationRuleStatus.GOVERNED]
    rules_by_family = Counter(rule.rule_family.value for rule in governed_rules)
    return {
        "schema_version": "policyos.obligation_rules.public_surface.v1",
        "catalog_id": model.catalog_id,
        "catalog_version": model.catalog_version,
        "catalog_ref": model.catalog_ref,
        "summary": model.summary.model_dump(mode="json"),
        "rules_by_family": dict(sorted(rules_by_family.items())),
        "rule_refs": [
            {
                "rule_id": rule.rule_id,
                "rule_family": rule.rule_family.value,
                "rule_version": rule.rule_version,
                "logic_hash": rule.logic_hash,
                "status": rule.status.value,
                "owner": rule.owner,
                "authority_level": rule.authority_level,
                "public_revalidation_effect": rule.public_revalidation_effect.value,
            }
            for rule in governed_rules
        ],
        "candidate_rule_count": len(model.candidates),
        "authoritative_for": ["obligation_rule_catalog_inspection"],
        "may_not_use_for": [
            "claim_evidence_authority",
            "llm_candidate_authority",
            "silent_rulebook_admission",
            "mandatory_public_revalidation_policy",
        ],
    }


def persist_obligation_rule_catalog(
    catalog: ObligationRuleCatalog | Mapping[str, Any],
    *,
    store: _JsonArtifactStore,
) -> object:
    """Persist the governed obligation rule catalog and return its CAS ref."""

    model = _coerce_catalog(catalog)
    return store.put_json(
        model.model_dump(mode="json"),
        _ArtifactWriteOptions(
            kind=OBLIGATION_RULE_CATALOG_KIND,
            media_type="application/json",
            schema={"name": OBLIGATION_RULE_CATALOG_SCHEMA, "version": "1.0"},
        ),
    )


def _catalog_rule_evolution_registry(
    catalog: ObligationRuleCatalog,
    *,
    previous_registry: Mapping[str, Any] | None = None,
    runtime_event_ref: str | None = None,
) -> dict[str, Any]:
    governed_rules = [
        rule for rule in catalog.rules if rule.status is ObligationRuleStatus.GOVERNED
    ]
    return build_rule_evolution_registry(
        registry_id=f"{catalog.catalog_id}.rule_evolution",
        version=catalog.catalog_version,
        effective_at=catalog.effective_at,
        previous_registry=previous_registry,
        rule_refs=[_rule_evolution_ref(rule) for rule in governed_rules],
        taxonomy_refs=_taxonomy_refs(catalog, governed_rules),
        evidence_ref=catalog.catalog_ref,
        runtime_event_ref=runtime_event_ref
        or f"event://obligation-rule-catalog/{catalog.catalog_version}",
    )


def _rule_evolution_ref(rule: ObligationRule) -> dict[str, Any]:
    return {
        "requirement_id": rule.rule_id,
        "rule_id": rule.rule_id,
        "logic_hash": rule.logic_hash,
        "taxonomy_refs": list(rule.taxonomy_refs),
        "authority_purpose": "obligation_admissibility",
        "status": rule.status.value,
        "provenance_ref": rule.provenance_refs[0] if rule.provenance_refs else rule.source_refs[0],
        "rule_family": rule.rule_family.value,
        "rule_version": rule.rule_version,
        "owner": rule.owner,
        "authority_level": rule.authority_level,
        "evidence_basis": list(rule.evidence_basis),
        "scope": rule.scope.model_dump(mode="json"),
        "public_revalidation_effect": rule.public_revalidation_effect.value,
        "deprecation_policy": rule.deprecation_policy.model_dump(mode="json"),
        "source_class": rule.source_class.value,
    }


def _taxonomy_refs(
    catalog: ObligationRuleCatalog,
    governed_rules: Sequence[ObligationRule],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for family in ObligationRuleFamily:
        family_rules = [
            rule for rule in governed_rules if rule.rule_family is family
        ]
        refs.append(
            {
                "taxonomy_id": f"taxonomy.obligation_rules.{family.value}",
                "version": catalog.taxonomy_version,
                "ref": f"rule-catalog://{catalog.catalog_id}/{family.value}/{catalog.catalog_version}",
                "logic_hash": logic_hash_for_rule(
                    [
                        {"rule_id": rule.rule_id, "logic_hash": rule.logic_hash}
                        for rule in family_rules
                    ]
                ),
            }
        )
    return refs


def _build_seed_rule(
    spec: Mapping[str, Any],
    *,
    catalog_version: str,
    logic_override: Mapping[str, Any] | None = None,
) -> ObligationRule:
    rule_id = str(spec["rule_id"])
    family = ObligationRuleFamily(str(spec["family"]))
    logic = dict(logic_override or spec["logic"])
    return ObligationRule(
        rule_id=rule_id,
        rule_family=family,
        rule_version=catalog_version,
        logic=logic,
        logic_hash=_rule_logic_hash(rule_id, logic),
        owner=str(spec["owner"]),
        scope=ObligationRuleScope(
            jurisdictions=tuple(spec.get("jurisdictions", ("global",))),
            policy_domains=tuple(spec.get("policy_domains", ("universal",))),
            authority_profiles=tuple(
                spec.get("authority_profiles", ("research", "governed", "production"))
            ),
            temporal_window=str(spec.get("temporal_window", "case_lifecycle")),
            audience=tuple(spec.get("audience", ("machine", "reviewer", "expert", "public"))),
        ),
        authority_level=str(spec["authority_level"]),
        evidence_basis=tuple(str(value) for value in spec["evidence_basis"]),
        status=ObligationRuleStatus.GOVERNED,
        public_revalidation_effect=PublicRevalidationEffect(str(spec["public_revalidation_effect"])),
        source_refs=tuple(str(value) for value in spec["source_refs"]),
        taxonomy_refs=(f"taxonomy.obligation_rules.{family.value}",),
        provenance_refs=tuple(str(value) for value in spec["source_refs"]),
    )


def _catalog_summary(
    *,
    rules: Sequence[ObligationRule],
    candidates: Sequence[ObligationRuleCandidate],
) -> ObligationRuleCatalogSummary:
    statuses = Counter(rule.status.value for rule in rules)
    governed_rules = [rule for rule in rules if rule.status is ObligationRuleStatus.GOVERNED]
    return ObligationRuleCatalogSummary(
        total_rule_count=len(rules),
        governed_rule_count=statuses[ObligationRuleStatus.GOVERNED.value],
        proposed_rule_count=statuses[ObligationRuleStatus.PROPOSED.value],
        deprecated_rule_count=statuses[ObligationRuleStatus.DEPRECATED.value],
        withdrawn_rule_count=statuses[ObligationRuleStatus.WITHDRAWN.value],
        candidate_rule_count=len(candidates),
        rules_by_family=dict(
            sorted(Counter(rule.rule_family.value for rule in governed_rules).items())
        ),
    )


def _rule_logic_hash(rule_id: str, logic: Mapping[str, Any]) -> str:
    return logic_hash_for_rule({"rule_id": rule_id, "logic": dict(logic)})


def _catalog_ref(
    *,
    catalog_id: str,
    catalog_version: str,
    rules: Sequence[ObligationRule],
) -> str:
    return _derived_ref(
        {
            "catalog_id": catalog_id,
            "catalog_version": catalog_version,
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "logic_hash": rule.logic_hash,
                    "status": rule.status.value,
                }
                for rule in rules
            ],
        }
    )


def _derived_ref(payload: object) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _coerce_catalog(
    catalog: ObligationRuleCatalog | Mapping[str, Any] | None,
) -> ObligationRuleCatalog:
    if catalog is None:
        raise TypeError("catalog is required")
    if isinstance(catalog, ObligationRuleCatalog):
        return catalog
    return ObligationRuleCatalog.model_validate(catalog)


def _seed_rule_specs() -> tuple[dict[str, Any], ...]:
    specs: list[dict[str, Any]] = []
    owners = {
        ObligationRuleFamily.LEGAL: "team-lex-governance",
        ObligationRuleFamily.FISCAL: "team-runtime-quality",
        ObligationRuleFamily.EQUITY: "team-policyos-runtime",
        ObligationRuleFamily.DATA: "team-data-forge",
        ObligationRuleFamily.IMPLEMENTATION: "team-runtime-quality",
        ObligationRuleFamily.METHOD: "team-foundry-methods",
        ObligationRuleFamily.PARTICIPATION: "team-policyos-runtime",
    }
    rule_rows: Mapping[ObligationRuleFamily, tuple[tuple[str, str, tuple[str, ...], str], ...]] = {
        ObligationRuleFamily.LEGAL: (
            (
                "authority_profile_bound",
                "authority_profile_must_match_claim_use",
                ("deterministic_critic_output", "historical_failure_corpus"),
                "revalidate_public_cases",
            ),
            (
                "competence_proof_required",
                "jurisdiction_competence_must_be_proven",
                ("deterministic_critic_output", "temporal_logic_pattern"),
                "revalidate_public_cases",
            ),
            (
                "legal_basis_normpack_binding",
                "legal_basis_requires_normpack_ref",
                ("deterministic_critic_output", "policy_design_critic"),
                "revalidate_open_cases",
            ),
            (
                "privacy_pii_minimization",
                "pii_access_requires_minimization_and_purpose",
                ("deterministic_critic_output", "policy_design_critic"),
                "revalidate_public_cases",
            ),
            (
                "recourse_path_reachable",
                "public_recourse_pointer_must_be_reachable",
                ("historical_failure_corpus", "temporal_logic_pattern"),
                "annotate_public_surface",
            ),
            (
                "public_revalidation_on_tightening",
                "semantic_tightening_requires_public_annotation",
                ("rule_evolution_registry", "temporal_logic_pattern"),
                "revalidate_public_cases",
            ),
            (
                "temporal_validity_window",
                "legal_validity_window_must_cover_policy_period",
                ("temporal_logic_pattern", "deterministic_critic_output"),
                "revalidate_open_cases",
            ),
            (
                "contested_authority_requires_review",
                "contested_legal_authority_forces_reviewer_action",
                ("historical_failure_corpus", "deterministic_critic_output"),
                "review_open_cases",
            ),
        ),
        ObligationRuleFamily.FISCAL: (
            (
                "budget_envelope_binding",
                "budget_allocation_must_bind_to_envelope",
                ("deterministic_critic_output", "policy_design_objectives"),
                "revalidate_open_cases",
            ),
            (
                "funding_channel_source_trace",
                "funding_channel_requires_source_trace",
                ("policy_design_objectives", "historical_failure_corpus"),
                "annotate_public_surface",
            ),
            (
                "cost_sla_degradation_advisory",
                "run_cost_degradation_must_surface_public_effect",
                ("deterministic_critic_output", "temporal_logic_pattern"),
                "review_open_cases",
            ),
            (
                "affordability_sensitivity",
                "fiscal_affordability_requires_sensitivity_check",
                ("policy_design_objectives", "deterministic_critic_output"),
                "annotate_public_surface",
            ),
            (
                "fiscal_sustainability_horizon",
                "fiscal_claim_requires_time_horizon",
                ("temporal_logic_pattern", "policy_design_objectives"),
                "revalidate_open_cases",
            ),
            (
                "benefit_leakage_monitoring",
                "benefit_leakage_risk_requires_monitoring_plan",
                ("historical_failure_corpus", "policy_design_adversary"),
                "review_open_cases",
            ),
            (
                "opportunity_cost_alternative_baseline",
                "fiscal_superiority_requires_alternative_baseline",
                ("historical_failure_corpus", "policy_design_objectives"),
                "revalidate_public_cases",
            ),
            (
                "budget_overrun_blocker",
                "budget_overrun_blocks_publication",
                ("deterministic_critic_output", "policy_design_critic"),
                "revalidate_public_cases",
            ),
        ),
        ObligationRuleFamily.EQUITY: (
            (
                "distributional_effect_by_group",
                "distributional_effect_requires_group_breakout",
                ("policy_design_objectives", "deterministic_critic_output"),
                "revalidate_public_cases",
            ),
            (
                "eligibility_exclusion_audit",
                "eligibility_rule_requires_exclusion_audit",
                ("historical_failure_corpus", "deterministic_critic_output"),
                "review_open_cases",
            ),
            (
                "affected_person_boundary",
                "affected_person_input_cannot_be_prevalence_evidence",
                ("historical_failure_corpus", "policy_design_critic"),
                "annotate_public_surface",
            ),
            (
                "disparate_impact_review",
                "disparate_impact_warning_requires_review_action",
                ("deterministic_critic_output", "policy_design_objectives"),
                "review_open_cases",
            ),
            (
                "geographic_coverage_equity",
                "geography_scope_requires_coverage_equity_check",
                ("temporal_logic_pattern", "historical_failure_corpus"),
                "review_open_cases",
            ),
            (
                "accessibility_burden_assessment",
                "delivery_burden_requires_accessibility_assessment",
                ("policy_design_objectives", "policy_design_adversary"),
                "annotate_public_surface",
            ),
            (
                "remedial_design_for_exclusion",
                "exclusion_risk_requires_remedy_path",
                ("historical_failure_corpus", "policy_design_adversary"),
                "review_open_cases",
            ),
            (
                "equity_claim_not_prevalence",
                "participation_prevalence_cannot_close_equity_claim",
                ("historical_failure_corpus", "deterministic_critic_output"),
                "revalidate_public_cases",
            ),
        ),
        ObligationRuleFamily.DATA: (
            (
                "source_family_admissibility",
                "data_source_family_must_match_requirement",
                ("historical_failure_corpus", "deterministic_critic_output"),
                "revalidate_public_cases",
            ),
            (
                "freshness_window",
                "data_freshness_window_must_cover_claim_time",
                ("temporal_logic_pattern", "historical_failure_corpus"),
                "revalidate_public_cases",
            ),
            (
                "official_snapshot_provenance",
                "official_snapshot_requires_provenance_manifest",
                ("deterministic_critic_output", "historical_failure_corpus"),
                "revalidate_public_cases",
            ),
            (
                "data_lineage_facets",
                "data_lineage_must_preserve_input_output_facets",
                ("deterministic_critic_output", "temporal_logic_pattern"),
                "annotate_public_surface",
            ),
            (
                "measurement_error_limit",
                "measurement_error_requires_limitation_or_method_adjustment",
                ("policy_design_objectives", "deterministic_critic_output"),
                "review_open_cases",
            ),
            (
                "missingness_bias_assessment",
                "missingness_bias_requires_bias_assessment",
                ("deterministic_critic_output", "historical_failure_corpus"),
                "review_open_cases",
            ),
            (
                "source_independence_collapse",
                "shared_lineage_sources_require_independence_collapse",
                ("historical_failure_corpus", "deterministic_critic_output"),
                "revalidate_public_cases",
            ),
            (
                "pii_access_classification",
                "pii_data_requires_access_classification",
                ("deterministic_critic_output", "policy_design_critic"),
                "revalidate_public_cases",
            ),
        ),
        ObligationRuleFamily.IMPLEMENTATION: (
            (
                "administrative_feasibility",
                "implementation_requires_administrative_feasibility",
                ("policy_design_objectives", "deterministic_critic_output"),
                "review_open_cases",
            ),
            (
                "delivery_channel_capacity",
                "delivery_channel_requires_capacity_check",
                ("policy_design_adversary", "historical_failure_corpus"),
                "review_open_cases",
            ),
            (
                "operational_liveness_deadline",
                "operational_blocker_requires_bounded_deadline",
                ("temporal_logic_pattern", "deterministic_critic_output"),
                "revalidate_open_cases",
            ),
            (
                "monitoring_plan_required",
                "material_public_risk_requires_monitoring_plan",
                ("temporal_logic_pattern", "policy_design_adversary"),
                "annotate_public_surface",
            ),
            (
                "rollback_path_required",
                "production_rollout_requires_rollback_path",
                ("historical_failure_corpus", "deterministic_critic_output"),
                "revalidate_public_cases",
            ),
            (
                "implementation_risk_register",
                "implementation_risks_require_owned_register",
                ("policy_design_adversary", "historical_failure_corpus"),
                "review_open_cases",
            ),
            (
                "human_review_escalation",
                "review_required_items_need_owner_and_escalation",
                ("deterministic_critic_output", "temporal_logic_pattern"),
                "review_open_cases",
            ),
            (
                "service_degradation_public_effect",
                "service_degradation_requires_public_effect_label",
                ("deterministic_critic_output", "historical_failure_corpus"),
                "annotate_public_surface",
            ),
        ),
        ObligationRuleFamily.METHOD: (
            (
                "identification_strategy_required",
                "causal_claim_requires_identification_strategy",
                ("deterministic_critic_output", "policy_design_objectives"),
                "revalidate_public_cases",
            ),
            (
                "transportability_required",
                "cross_context_claim_requires_transportability_assessment",
                ("deterministic_critic_output", "policy_design_critic"),
                "revalidate_public_cases",
            ),
            (
                "positivity_overlap_check",
                "effect_claim_requires_positivity_overlap_check",
                ("deterministic_critic_output", "policy_design_critic"),
                "review_open_cases",
            ),
            (
                "uncertainty_quantification",
                "serious_policy_claim_requires_uncertainty_quantification",
                ("policy_design_objectives", "deterministic_critic_output"),
                "revalidate_public_cases",
            ),
            (
                "baseline_alternative_comparison",
                "superiority_claim_requires_baseline_and_alternative",
                ("historical_failure_corpus", "policy_design_objectives"),
                "revalidate_public_cases",
            ),
            (
                "sensitivity_analysis",
                "method_sensitive_claim_requires_sensitivity_analysis",
                ("policy_design_adversary", "deterministic_critic_output"),
                "review_open_cases",
            ),
            (
                "robustness_stress_test",
                "fragile_policy_requires_adversarial_stress_test",
                ("policy_design_adversary", "policy_design_objectives"),
                "annotate_public_surface",
            ),
            (
                "method_not_generic_execute",
                "generic_execute_cannot_satisfy_method_obligation",
                ("historical_failure_corpus", "deterministic_critic_output"),
                "revalidate_public_cases",
            ),
        ),
        ObligationRuleFamily.PARTICIPATION: (
            (
                "participation_provenance",
                "participation_claim_requires_provenance_record",
                ("deterministic_critic_output", "historical_failure_corpus"),
                "revalidate_public_cases",
            ),
            (
                "representativeness_limit",
                "unrepresentative_participation_requires_limitation",
                ("historical_failure_corpus", "deterministic_critic_output"),
                "annotate_public_surface",
            ),
            (
                "affected_person_voice",
                "affected_person_claim_requires_voice_or_limitation",
                ("historical_failure_corpus", "policy_design_adversary"),
                "review_open_cases",
            ),
            (
                "public_contestation_ingestion",
                "public_contestation_requires_claim_linkage",
                ("deterministic_critic_output", "historical_failure_corpus"),
                "review_open_cases",
            ),
            (
                "consent_notice",
                "participation_data_requires_notice_and_consent_boundary",
                ("deterministic_critic_output", "policy_design_critic"),
                "revalidate_public_cases",
            ),
            (
                "recourse_mechanism",
                "affected_public_needs_recourse_pointer",
                ("historical_failure_corpus", "temporal_logic_pattern"),
                "annotate_public_surface",
            ),
            (
                "deliberation_tradeoff_record",
                "value_tradeoff_requires_deliberation_record",
                ("policy_design_objectives", "historical_failure_corpus"),
                "review_open_cases",
            ),
            (
                "participation_not_evidence_authority",
                "participation_signal_cannot_fill_evidence_slot",
                ("historical_failure_corpus", "deterministic_critic_output"),
                "revalidate_public_cases",
            ),
        ),
    }
    for family, entries in rule_rows.items():
        for key, predicate, basis, effect in entries:
            authority = (
                "production"
                if family
                in {
                    ObligationRuleFamily.LEGAL,
                    ObligationRuleFamily.DATA,
                    ObligationRuleFamily.METHOD,
                    ObligationRuleFamily.PARTICIPATION,
                }
                else "governed"
            )
            specs.append(
                {
                    "rule_id": f"obligation.{family.value}.{key}",
                    "family": family.value,
                    "owner": owners[family],
                    "authority_level": authority,
                    "evidence_basis": basis,
                    "source_refs": _source_refs_for_basis(basis),
                    "public_revalidation_effect": effect,
                    "policy_domains": (family.value, "universal"),
                    "logic": {
                        "predicate": predicate,
                        "rule_family": family.value,
                        "required_for_authority_levels": ["governed", "production"],
                        "candidate_source_ceiling": "governed_rule",
                        "llm_candidate_may_satisfy": False,
                    },
                }
            )
    specs.extend(_vertical_seed_rule_specs(owners))
    return tuple(specs)


def _vertical_seed_rule_specs(
    owners: Mapping[ObligationRuleFamily, str],
) -> tuple[dict[str, Any], ...]:
    """Return governed vertical seed rules mined from W11.B corpus annotations."""

    corpus_basis = ("w11b_corpus_annotation",)

    def vertical(
        *,
        key: str,
        family: ObligationRuleFamily,
        predicate: str,
        evidence_family: str,
        obligation_id: str,
        reviewer_notes: str,
        case_id: str,
        policy_domain: str,
        facets: Sequence[Mapping[str, str]],
        text_any: Sequence[str],
        effect: str = "review_open_cases",
        authority_level: str = "governed",
        jurisdiction: str = "global",
    ) -> dict[str, Any]:
        return {
            "rule_id": f"obligation.{family.value}.{key}",
            "family": family.value,
            "owner": owners[family],
            "authority_level": authority_level,
            "evidence_basis": corpus_basis,
            "source_refs": (f"tests/fixtures/universal-corpus/cases/{case_id}.json",),
            "public_revalidation_effect": effect,
            "jurisdictions": (jurisdiction,),
            "policy_domains": (policy_domain, family.value, "vertical_corpus_seed"),
            "authority_profiles": ("research", "governed", "production"),
            "logic": {
                "predicate": predicate,
                "rule_family": family.value,
                "facet_match_all": tuple(dict(row) for row in facets),
                "claim_text_contains_any": tuple(text_any),
                "annotation_obligation_id": obligation_id,
                "case_refs": (case_id,),
                "required_evidence_constructs": _construct_refs_for_required_evidence(
                    evidence_family
                ),
                "legacy_evidence_family_alias": evidence_family,
                "legacy_evidence_alias_deprecated": True,
                "generated_from_facets": tuple(
                    f"facet:{row['facet_type']}.{row['value_eq']}" for row in facets
                ),
                "obligation_text": reviewer_notes,
                "reviewer_notes": reviewer_notes,
                "vertical_rule": True,
                "required_for_authority_levels": ["research", "governed", "production"],
                "candidate_source_ceiling": "review_required",
                "llm_candidate_may_satisfy": False,
            },
        }

    def data_family(
        *,
        key: str,
        evidence_family: str,
        predicate: str,
        facets: Sequence[Mapping[str, str]],
        text_any: Sequence[str] = (),
    ) -> dict[str, Any]:
        return {
            "rule_id": f"obligation.data.{key}",
            "family": ObligationRuleFamily.DATA.value,
            "owner": owners[ObligationRuleFamily.DATA],
            "authority_level": "governed",
            "evidence_basis": ("w7a_data_family_heuristic_sunset",),
            "source_refs": ("src/polisyos/data_requirement/compiler.py#_family_derivation_label",),
            "public_revalidation_effect": "review_open_cases",
            "policy_domains": ("data", "vertical_data_family_seed"),
            "logic": {
                "predicate": predicate,
                "rule_family": ObligationRuleFamily.DATA.value,
                "facet_match_all": tuple(dict(row) for row in facets),
                "claim_text_contains_any": tuple(text_any),
                "required_evidence_constructs": _construct_refs_for_required_evidence(
                    evidence_family
                ),
                "legacy_evidence_family_alias": evidence_family,
                "legacy_evidence_alias_deprecated": True,
                "vertical_rule": True,
                "required_for_authority_levels": ["governed", "production"],
                "candidate_source_ceiling": "review_required",
                "llm_candidate_may_satisfy": False,
            },
        }

    return (
        vertical(
            key="claim_level_credit_additionality",
            family=ObligationRuleFamily.METHOD,
            predicate="claim_level_credit_additionality_requires_counterfactual",
            evidence_family="program_evaluation_or_counterfactual_credit_additionality",
            obligation_id="obligation:claim-level-credit-additionality",
            reviewer_notes=(
                "A universal compiler should require claim-level evidence separating "
                "additional credit access for eligible MSMEs from programme volume "
                "routed through existing bank-client channels."
            ),
            case_id="ua-msme-affordable-loans-2022",
            policy_domain="msme_credit_grant",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "credit"},
                {"facet_type": "delivery_channel", "value_eq": "credit_registry"},
                {"facet_type": "population_predicate", "value_eq": "msmes"},
                {"facet_type": "geography_predicate", "value_eq": "national"},
            ),
            text_any=("affordable loans", "wartime MSME credit"),
        ),
        vertical(
            key="contingent_liability_portfolio_risk",
            family=ObligationRuleFamily.FISCAL,
            predicate="partial_guarantee_requires_portfolio_risk_monitoring",
            evidence_family="fiscal_risk_and_portfolio_quality_monitoring",
            obligation_id="obligation:contingent-liability-and-portfolio-risk",
            reviewer_notes=(
                "The case should not close as publishable without a limitation or "
                "review path for contingent liabilities, bank portfolio concentration, "
                "and wartime credit-risk deterioration."
            ),
            case_id="ua-msme-affordable-loans-2022",
            policy_domain="msme_credit_grant",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "credit"},
                {"facet_type": "risk_facet", "value_eq": "budget_feasibility"},
                {"facet_type": "population_predicate", "value_eq": "msmes"},
            ),
            text_any=("partial guarantee", "5-7-9"),
        ),
        vertical(
            key="rent_cap_competence_check",
            family=ObligationRuleFamily.LEGAL,
            predicate="rent_cap_requires_subnational_competence_check",
            evidence_family="legal_competence_analysis",
            obligation_id="obligation:rent-cap-competence-check",
            reviewer_notes=(
                "A governed recommendation should block before outcome modeling when "
                "the implementing authority lacks competence."
            ),
            case_id="w11a_berlin_rent_cap_2020",
            policy_domain="housing_rent_control",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "subsidy"},
                {"facet_type": "delivery_channel", "value_eq": "regulatory_enforcement"},
                {"facet_type": "geography_predicate", "value_eq": "municipal"},
            ),
            text_any=("rent cap", "berlin"),
            effect="revalidate_public_cases",
        ),
        vertical(
            key="ceasefire_fidelity_legitimacy",
            family=ObligationRuleFamily.IMPLEMENTATION,
            predicate="focused_deterrence_transfer_requires_fidelity_legitimacy",
            evidence_family="implementation_fidelity_and_external_validity_review",
            obligation_id="obligation:ceasefire-fidelity-and-legitimacy",
            reviewer_notes=(
                "Research use should preserve the evaluation-design limitation and "
                "require fidelity evidence before transfer to another city."
            ),
            case_id="w11a_boston_operation_ceasefire_1996",
            policy_domain="public_safety",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "service"},
                {"facet_type": "targeting_type", "value_eq": "geographic"},
                {"facet_type": "geography_predicate", "value_eq": "municipal"},
            ),
            text_any=("operation ceasefire", "focused deterrence"),
            authority_level="research",
        ),
        vertical(
            key="temporary_protection_rights_realization",
            family=ObligationRuleFamily.IMPLEMENTATION,
            predicate="temporary_protection_requires_rights_realization_monitoring",
            evidence_family="rights_access_and_local_implementation_monitoring",
            obligation_id="obligation:temporary-protection-rights-realization",
            reviewer_notes=(
                "Production authority must test whether formal rights were realized "
                "across housing, education, healthcare, and labour access."
            ),
            case_id="w11a_eu_temporary_protection_ukraine_2022",
            policy_domain="migration_displacement",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "service"},
                {"facet_type": "targeting_type", "value_eq": "risk_based"},
                {"facet_type": "geography_predicate", "value_eq": "displacement_affected"},
            ),
            text_any=("temporary protection", "ukraine"),
            authority_level="production",
        ),
        vertical(
            key="free_shs_access_quality_split",
            family=ObligationRuleFamily.IMPLEMENTATION,
            predicate="fee_abolition_requires_access_quality_capacity_split",
            evidence_family="enrollment_quality_and_capacity_evaluation",
            obligation_id="obligation:free-shs-access-quality-split",
            reviewer_notes=(
                "Research use may cite access expansion, but useful-design scoring "
                "should require separate quality and capacity evidence."
            ),
            case_id="w11a_ghana_free_shs_2017",
            policy_domain="education_access",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "subsidy"},
                {"facet_type": "population_predicate", "value_eq": "children"},
                {"facet_type": "risk_facet", "value_eq": "equity_harm"},
            ),
            text_any=("free shs", "free senior high school", "secondary school"),
            authority_level="research",
        ),
        vertical(
            key="aadhaar_exclusion_purpose_limits",
            family=ObligationRuleFamily.EQUITY,
            predicate="digital_identity_delivery_requires_exclusion_recourse_audit",
            evidence_family="rights_exclusion_and_recourse_audit",
            obligation_id="obligation:aadhaar-exclusion-and-purpose-limits",
            reviewer_notes=(
                "Production useful design must carry purpose limitation, "
                "exclusion-risk, and recourse evidence alongside delivery-efficiency "
                "claims."
            ),
            case_id="w11a_india_aadhaar_dbt_2016",
            policy_domain="digital_public_service",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "service"},
                {"facet_type": "delivery_channel", "value_eq": "credit_registry"},
                {"facet_type": "population_predicate", "value_eq": "households"},
            ),
            text_any=("aadhaar", "direct benefit transfer"),
            authority_level="production",
        ),
        vertical(
            key="ssb_tax_health_linkage",
            family=ObligationRuleFamily.METHOD,
            predicate="ssb_tax_health_claim_requires_longer_run_causal_evidence",
            evidence_family="causal_or_quasi_experimental_public_health_evaluation",
            obligation_id="obligation:ssb-tax-health-linkage",
            reviewer_notes=(
                "Research authority may use purchase evidence, but production "
                "claims about health outcomes need longer-run health and substitution "
                "evidence."
            ),
            case_id="w11a_mexico_ssb_tax_2014",
            policy_domain="public_health_intervention",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "tax"},
                {"facet_type": "funding_channel", "value_eq": "earmarked_tax"},
                {"facet_type": "geography_predicate", "value_eq": "national"},
            ),
            text_any=("ssb tax", "sugar"),
        ),
        vertical(
            key="room_for_river_scenario_monitoring",
            family=ObligationRuleFamily.IMPLEMENTATION,
            predicate="spatial_adaptation_requires_future_scenario_monitoring",
            evidence_family="hydrological_modeling_and_lifecycle_monitoring",
            obligation_id="obligation:room-for-river-scenario-monitoring",
            reviewer_notes=(
                "Research authority should preserve future-scenario uncertainty and "
                "land-use burden rather than treating completion as permanent adequacy."
            ),
            case_id="w11a_netherlands_room_for_river_2007",
            policy_domain="climate_adaptation",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "procurement"},
                {"facet_type": "geography_predicate", "value_eq": "state_or_region"},
                {"facet_type": "targeting_type", "value_eq": "geographic"},
            ),
            text_any=("room for river", "room for the river", "flood risk", "flood-risk"),
            authority_level="research",
        ),
        vertical(
            key="ehsaas_targeting_exclusion_audit",
            family=ObligationRuleFamily.EQUITY,
            predicate="emergency_cash_requires_coverage_exclusion_payment_audit",
            evidence_family="coverage_exclusion_and_payment_access_analysis",
            obligation_id="obligation:ehsaas-targeting-exclusion-audit",
            reviewer_notes=(
                "Production closeout must expose exclusion and payment access risks, "
                "not only headline coverage."
            ),
            case_id="w11a_pakistan_ehsaas_cash_2020",
            policy_domain="social_protection_targeting",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "service"},
                {"facet_type": "targeting_type", "value_eq": "means_tested"},
                {"facet_type": "population_predicate", "value_eq": "low_income_renters"},
            ),
            text_any=("ehsaas", "emergency cash"),
            authority_level="production",
        ),
        vertical(
            key="luf_prioritisation_delivery",
            family=ObligationRuleFamily.IMPLEMENTATION,
            predicate="competitive_capital_grant_requires_prioritisation_delivery_monitoring",
            evidence_family="prioritisation_method_and_delivery_monitoring",
            obligation_id="obligation:luf-prioritisation-and-delivery",
            reviewer_notes=(
                "Governed closeout must surface bid burden, place-selection method, "
                "and delivery delay rather than only allocated funding totals."
            ),
            case_id="w11a_uk_levelling_up_fund_2021",
            policy_domain="infrastructure_prioritisation",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "procurement"},
                {"facet_type": "geography_predicate", "value_eq": "state_or_region"},
                {"facet_type": "targeting_type", "value_eq": "geographic"},
            ),
            text_any=("levelling up fund", "capital grant"),
        ),
        vertical(
            key="mtd_compliance_burden_vfm",
            family=ObligationRuleFamily.FISCAL,
            predicate="digital_tax_mandate_requires_vfm_and_compliance_cost",
            evidence_family="value_for_money_and_compliance_cost_analysis",
            obligation_id="obligation:mtd-compliance-burden-vfm",
            reviewer_notes=(
                "Governed closeout must expose business compliance costs and delay "
                "risk, not only HMRC revenue estimates."
            ),
            case_id="w11a_uk_mtd_vat_2019",
            policy_domain="tax_enforcement",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "tax"},
                {"facet_type": "population_predicate", "value_eq": "firms"},
                {"facet_type": "risk_facet", "value_eq": "budget_feasibility"},
            ),
            text_any=("making tax digital", "mtd vat"),
        ),
        vertical(
            key="work_programme_hard_to_help_effects",
            family=ObligationRuleFamily.EQUITY,
            predicate="provider_activation_requires_harder_to_help_subgroup_effects",
            evidence_family="subgroup_impact_and_incentive_analysis",
            obligation_id="obligation:work-programme-hard-to-help-effects",
            reviewer_notes=(
                "Useful design must prove outcomes for harder-to-help groups, not "
                "only aggregate job outcomes."
            ),
            case_id="w11a_uk_work_programme_2011",
            policy_domain="labour_activation",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "service"},
                {"facet_type": "population_predicate", "value_eq": "workers"},
                {"facet_type": "targeting_type", "value_eq": "risk_based"},
            ),
            text_any=("work programme", "harder-to-help"),
        ),
        vertical(
            key="ppp_cross_program_fraud_screening",
            family=ObligationRuleFamily.DATA,
            predicate="forgivable_emergency_loan_requires_fraud_screening",
            evidence_family="fraud_risk_analytics",
            obligation_id="obligation:ppp-cross-program-fraud-screening",
            reviewer_notes=(
                "Production-authority support should require external-data fraud "
                "screening and distributional access analysis before treating the "
                "intervention as publishable."
            ),
            case_id="w11a_us_ppp_2020",
            policy_domain="msme_credit_grant",
            facets=(
                {"facet_type": "instrument_type", "value_eq": "credit"},
                {"facet_type": "population_predicate", "value_eq": "msmes"},
                {"facet_type": "geography_predicate", "value_eq": "state_or_region"},
            ),
            text_any=("ppp", "paycheck protection"),
            authority_level="production",
        ),
        data_family(
            key="vertical_production_msme_panel",
            evidence_family="production_msme_panel",
            predicate="msme_population_requires_production_msme_panel",
            facets=({"facet_type": "population_predicate", "value_eq": "msmes"},),
        ),
        data_family(
            key="vertical_credit_program_registry",
            evidence_family="credit_program_registry",
            predicate="credit_instrument_requires_credit_program_registry",
            facets=({"facet_type": "instrument_type", "value_eq": "credit"},),
        ),
        data_family(
            key="vertical_regional_displacement_indicators",
            evidence_family="regional_displacement_indicators",
            predicate="displacement_scope_requires_regional_indicators",
            facets=(),
            text_any=("displaced", "displacement", "wartime"),
        ),
        data_family(
            key="vertical_tax_admin_panel",
            evidence_family="tax_admin_panel",
            predicate="tax_instrument_requires_tax_admin_panel",
            facets=({"facet_type": "instrument_type", "value_eq": "tax"},),
        ),
        data_family(
            key="vertical_fiscal_revenue_series",
            evidence_family="fiscal_revenue_series",
            predicate="tax_instrument_requires_fiscal_revenue_series",
            facets=({"facet_type": "instrument_type", "value_eq": "tax"},),
        ),
        data_family(
            key="vertical_service_delivery_registry",
            evidence_family="service_delivery_registry",
            predicate="public_service_delivery_requires_registry",
            facets=({"facet_type": "delivery_channel", "value_eq": "public_service"},),
        ),
        data_family(
            key="vertical_labor_force_panel",
            evidence_family="labor_force_panel",
            predicate="worker_population_requires_labor_force_panel",
            facets=({"facet_type": "population_predicate", "value_eq": "workers"},),
        ),
    )


def _construct_refs_for_required_evidence(evidence_family: str) -> tuple[str, ...]:
    """Map W11/W7 compatibility evidence labels into governed construct refs."""

    mappings: Mapping[str, tuple[str, ...]] = {
        "program_evaluation_or_counterfactual_credit_additionality": (
            "construct:credit_access",
            "construct:credit_program_enrollment",
            "construct:firm_survival",
            "construct:treatment_effect_heterogeneity",
        ),
        "fiscal_risk_and_portfolio_quality_monitoring": (
            "construct:fiscal_burden_per_beneficiary",
            "construct:risk_score",
            "construct:credit_program_enrollment",
        ),
        "legal_competence_analysis": (
            "construct:institutional_quality",
            "construct:regulatory_compliance_rate",
            "construct:housing_rent_burden",
        ),
        "implementation_fidelity_and_external_validity_review": (
            "construct:service_quality_indicator",
            "construct:civic_legitimacy_signal",
            "construct:treatment_effect_heterogeneity",
        ),
        "rights_access_and_local_implementation_monitoring": (
            "construct:wartime_displacement_indicator",
            "construct:housing_rent_burden",
            "construct:health_outcomes",
            "construct:education_outcomes",
            "construct:labor_force_participation",
        ),
        "enrollment_quality_and_capacity_evaluation": (
            "construct:education_outcomes",
            "construct:provider_network_capacity",
            "construct:service_quality_indicator",
        ),
        "rights_exclusion_and_recourse_audit": (
            "construct:public_service_payment",
            "construct:program_targeting_accuracy",
            "construct:participation_provenance",
            "construct:civic_legitimacy_signal",
        ),
        "causal_or_quasi_experimental_public_health_evaluation": (
            "construct:health_outcomes",
            "construct:intervention_take_up_rate",
            "construct:treatment_effect_heterogeneity",
        ),
        "hydrological_modeling_and_lifecycle_monitoring": (
            "construct:regional_emissions_intensity",
            "construct:budget_flow",
            "construct:procurement_flow",
        ),
        "coverage_exclusion_and_payment_access_analysis": (
            "construct:program_targeting_accuracy",
            "construct:public_service_payment",
            "construct:poverty_rate",
        ),
        "prioritisation_method_and_delivery_monitoring": (
            "construct:budget_flow",
            "construct:procurement_flow",
            "construct:service_quality_indicator",
        ),
        "value_for_money_and_compliance_cost_analysis": (
            "construct:tax_debt",
            "construct:regulatory_compliance_rate",
            "construct:fiscal_burden_per_beneficiary",
        ),
        "subgroup_impact_and_incentive_analysis": (
            "construct:employment_count",
            "construct:labor_force_participation",
            "construct:treatment_effect_heterogeneity",
        ),
        "fraud_risk_analytics": (
            "construct:credit_program_enrollment",
            "construct:firm_survival",
            "construct:risk_score",
            "construct:program_targeting_accuracy",
        ),
        "production_msme_panel": (
            "construct:firm_survival",
            "construct:credit_access",
            "construct:employment_count",
        ),
        "credit_program_registry": (
            "construct:credit_program_enrollment",
            "construct:credit_access",
            "construct:program_participation_rate",
        ),
        "regional_displacement_indicators": (
            "construct:regional_displacement_pressure",
            "construct:wartime_displacement_indicator",
            "construct:logistics_friction",
        ),
        "tax_admin_panel": (
            "construct:tax_debt",
            "construct:risk_score",
            "construct:regulatory_compliance_rate",
        ),
        "fiscal_revenue_series": (
            "construct:budget_flow",
            "construct:macro_state",
            "construct:inflation",
        ),
        "service_delivery_registry": (
            "construct:public_service_payment",
            "construct:service_quality_indicator",
            "construct:provider_network_capacity",
        ),
        "labor_force_panel": (
            "construct:labor_force_participation",
            "construct:employment_count",
            "construct:informal_economy_indicator",
        ),
    }
    refs = mappings.get(evidence_family)
    if refs is None:
        raise ValueError(f"unknown vertical evidence family mapping: {evidence_family}")
    return refs


def _source_refs_for_basis(basis: Sequence[str]) -> tuple[str, ...]:
    source_by_basis = {
        "deterministic_critic_output": (
            "src/polisyos/scientist/policy_design/critic.py:ConstraintCritic"
        ),
        "temporal_logic_pattern": (
            "src/polisyos/ir/governance/temporal_logic.py:TemporalPolicyConstraint"
        ),
        "historical_failure_corpus": (
            "tests/fixtures/policy_design_case/semantic_false_passes/README.md"
        ),
        "policy_design_critic": "src/polisyos/scientist/policy_design/critic.py",
        "policy_design_objectives": "src/polisyos/scientist/policy_design/objectives.py",
        "policy_design_adversary": "src/polisyos/scientist/policy_design/adversary.py",
        "rule_evolution_registry": "src/polisyos/runtime/quality/rule_evolution.py",
        "w11b_corpus_annotation": "tests/fixtures/universal-corpus/README.md",
        "w7a_data_family_heuristic_sunset": (
            "src/polisyos/data_requirement/compiler.py#_family_derivation_label"
        ),
    }
    return tuple(source_by_basis[item] for item in basis if item in source_by_basis)


__all__ = [
    "OBLIGATION_RULE_CATALOG_CONTRACT_ID",
    "OBLIGATION_RULE_CATALOG_KIND",
    "OBLIGATION_RULE_CATALOG_SCHEMA",
    "OBLIGATION_RULE_CATALOG_SCHEMA_VERSION",
    "ObligationRule",
    "ObligationRuleCandidate",
    "ObligationRuleCatalog",
    "ObligationRuleCatalogSummary",
    "ObligationRuleFamily",
    "ObligationRuleGovernanceError",
    "ObligationRuleScope",
    "ObligationRuleSourceClass",
    "ObligationRuleStatus",
    "PublicRevalidationEffect",
    "RuleDeprecationPolicy",
    "RuleGovernanceDecision",
    "build_rule_evolution_registry_for_catalog",
    "build_seed_obligation_rule_catalog",
    "govern_rule_candidate",
    "governed_rule_catalog_public_surface",
    "persist_obligation_rule_catalog",
    "select_governed_rules",
]
