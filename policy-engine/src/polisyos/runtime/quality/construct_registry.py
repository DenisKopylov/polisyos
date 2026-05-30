"""Governed construct registry for Policy Evidence Capability Graph Phase 2."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONSTRUCT_REGISTRY_SCHEMA_VERSION = "policyos.construct_registry.v1"
CONSTRUCT_REGISTRY_ID = "policyos.policy_evidence.construct_registry"
CONSTRUCT_REGISTRY_VERSION = "2026.05.phase2"
CONSTRUCT_REGISTRY_RULE_VERSION = "construct-registry-v1.0"
CONSTRUCT_REGISTRY_DEFAULT_PATH = (
    Path(__file__).resolve().parents[4]
    / "architecture/policy_design_case/construct_registry_v1.yaml"
)

AuthorityPosture = Literal["research", "governed_pilot", "production"]
ConstructStatus = Literal["active", "deprecated", "withdrawn"]
CorpusBindingStatus = Literal["bound", "research_only"]
CompatibilityAliasType = Literal[
    "legacy_scenario_family",
    "metric",
    "measurement_family",
    "common_term",
    "corpus_evidence_family",
]

_REQUIRED_POSTURES = frozenset({"research", "governed_pilot", "production"})
_GOVERNED_TIME_ROLES = frozenset(
    {
        "legal_effective_time",
        "policy_time",
        "data_time",
        "observation_time",
        "valid_time",
        "transaction_time",
        "ingestion_time",
        "publication_time",
        "detection_time",
        "forecast_time",
        "freshness_time",
        "retention_time",
        "replay_time",
    }
)
_GOVERNED_EVIDENCE_MODES = frozenset(
    {
        "observed",
        "derived",
        "proxy_observational",
        "bounds_only",
        "context_only",
        "simulation_only",
        "normative_authority",
        "legal_threshold",
        "scholarly_causal_support",
        "participation_attestation",
        "historical_prior",
        "candidate_unverified",
        "reviewer_admitted",
    }
)


class ConstructRegistryError(ValueError):
    """Raised when construct registry semantics are invalid or incomplete."""


class ConstructRegistryModel(BaseModel):
    """Strict base model for construct-registry contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ConstructAuthorityRequirement(ConstructRegistryModel):
    """Authority requirements for one construct under one rollout posture."""

    identification_modes: tuple[str, ...] = Field(min_length=1)
    trust_tier_min: str = Field(min_length=1)
    requires_proxy_validation_when_proxy: bool = False
    requires_construct_validity_evidence: bool = False
    construct_validity_floor: str = Field(default="face_validated", min_length=1)
    admissible_authority_results: tuple[str, ...] = Field(
        default=("admissible",),
        min_length=1,
    )

    @field_validator(
        "identification_modes",
        "admissible_authority_results",
        mode="before",
    )
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @field_validator("trust_tier_min", "construct_validity_floor", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> str:
        return _required_text(value)


class ConstructValidityRequirements(ConstructRegistryModel):
    """Construct-validity floors and negative controls for proxy use."""

    minimum_status_by_posture: Mapping[str, str] = Field(min_length=1)
    required_validation_refs: tuple[str, ...] = Field(default=())
    negative_controls: tuple[str, ...] = Field(default=())

    @field_validator("required_validation_refs", "negative_controls", mode="before")
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @field_validator("minimum_status_by_posture", mode="before")
    @classmethod
    def _clean_status_map(cls, value: object) -> Mapping[str, str]:
        if not isinstance(value, Mapping):
            raise TypeError("minimum_status_by_posture must be a mapping")
        return {
            _required_text(key): _required_text(item)
            for key, item in value.items()
        }


class ConstructAliasDeprecation(ConstructRegistryModel):
    """Sunset metadata for compatibility aliases."""

    status: Literal["active", "deprecated"] = "deprecated"
    owner: str = Field(min_length=1)
    created: str = Field(min_length=1)
    sunset_date: str = Field(min_length=1)
    sunset_trigger: str = Field(min_length=1)
    replacement: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    may_not_use_for: tuple[str, ...] = Field(
        default=("evidence_authority_selector", "production_closeout_authority"),
        min_length=1,
    )

    @field_validator(
        "owner",
        "created",
        "sunset_date",
        "sunset_trigger",
        "replacement",
        "reason",
        mode="before",
    )
    @classmethod
    def _strip_required_text(cls, value: object) -> str:
        return _required_text(value)

    @field_validator("may_not_use_for", mode="before")
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ConstructCompatibilityAlias(ConstructRegistryModel):
    """Compatibility alias that may resolve to constructs but never carries authority."""

    alias: str = Field(min_length=1)
    alias_type: CompatibilityAliasType
    deprecation: ConstructAliasDeprecation | None = None

    @field_validator("alias", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> str:
        return _required_text(value)

    @model_validator(mode="after")
    def _validate_legacy_alias_deprecation(self) -> ConstructCompatibilityAlias:
        if self.alias_type == "legacy_scenario_family" and self.deprecation is None:
            raise ValueError(
                "legacy scenario-family aliases require deprecation metadata"
            )
        return self


class ConstructCorpusBinding(ConstructRegistryModel):
    """Universal-corpus case binding for one construct."""

    case_id: str = Field(min_length=1)
    obligation_refs: tuple[str, ...] = Field(default=())
    evidence_family_refs: tuple[str, ...] = Field(default=())
    coverage_role: str = Field(default="required_evidence_construct", min_length=1)
    authority_postures: tuple[AuthorityPosture, ...] = Field(
        default=("research", "governed_pilot", "production"),
        min_length=1,
    )

    @field_validator("case_id", "coverage_role", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> str:
        return _required_text(value)

    @field_validator("obligation_refs", "evidence_family_refs", mode="before")
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ConstructEntry(ConstructRegistryModel):
    """One governed policy-decision-bearing construct."""

    construct_id: str = Field(pattern=r"^construct:[a-z][a-z0-9_]*$")
    aliases: tuple[str, ...] = Field(default=())
    compatibility_aliases: tuple[ConstructCompatibilityAlias, ...] = Field(default=())
    domain: tuple[str, ...] = Field(min_length=1)
    entity_scope: tuple[str, ...] = Field(min_length=1)
    description: str = Field(min_length=1)
    concept_spine_ref: str = Field(pattern=r"^concept:[a-z][a-z0-9_]*$")
    required_time_roles: tuple[str, ...] = Field(min_length=1)
    allowed_evidence_modes: tuple[str, ...] = Field(min_length=1)
    authority_requirements: Mapping[
        AuthorityPosture,
        ConstructAuthorityRequirement,
    ] = Field(min_length=3)
    construct_validity_requirements: ConstructValidityRequirements
    proxy_validation_rules: tuple[str, ...] = Field(min_length=1)
    allowed_method_contracts: tuple[str, ...] = Field(default=())
    legal_authority_patterns: tuple[dict[str, Any], ...] = Field(default=())
    related_scholar_claim_patterns: tuple[dict[str, Any], ...] = Field(default=())
    corpus_bindings: tuple[ConstructCorpusBinding, ...] = Field(default=())
    corpus_binding_status: CorpusBindingStatus = "bound"
    source_refs: tuple[str, ...] = Field(min_length=1)
    owner: str = Field(default="team-runtime-quality", min_length=1)
    rule_version_ref: str = Field(default=CONSTRUCT_REGISTRY_RULE_VERSION, min_length=1)
    status: ConstructStatus = "active"

    @field_validator(
        "aliases",
        "domain",
        "entity_scope",
        "required_time_roles",
        "allowed_evidence_modes",
        "proxy_validation_rules",
        "allowed_method_contracts",
        "source_refs",
        mode="before",
    )
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @field_validator("description", "owner", "rule_version_ref", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> str:
        return _required_text(value)

    @field_validator("required_time_roles")
    @classmethod
    def _validate_governed_time_roles(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_governed_values(
            values,
            allowed=_GOVERNED_TIME_ROLES,
            field_name="required_time_roles",
        )

    @field_validator("allowed_evidence_modes")
    @classmethod
    def _validate_governed_evidence_modes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_governed_values(
            values,
            allowed=_GOVERNED_EVIDENCE_MODES,
            field_name="allowed_evidence_modes",
        )

    @field_validator("authority_requirements", mode="before")
    @classmethod
    def _validate_authority_keys(cls, value: object) -> Mapping[str, object]:
        if not isinstance(value, Mapping):
            raise TypeError("authority_requirements must be a mapping")
        keys = {str(key) for key in value}
        if keys != _REQUIRED_POSTURES:
            raise ValueError(
                "authority_requirements must contain research, governed_pilot, and production"
            )
        return value

    @model_validator(mode="after")
    def _validate_construct_semantics(self) -> ConstructEntry:
        if self.status == "active" and not self.concept_spine_ref:
            raise ValueError("active constructs require concept_spine_ref")
        if self.corpus_binding_status == "bound" and not self.corpus_bindings:
            raise ValueError(
                "bound constructs require at least one corpus binding; use "
                "corpus_binding_status=research_only when intentionally unbound"
            )
        return self


class ConstructRegistry(ConstructRegistryModel):
    """Governed construct registry loaded by runtime-quality consumers."""

    schema_version: str = CONSTRUCT_REGISTRY_SCHEMA_VERSION
    registry_id: str = CONSTRUCT_REGISTRY_ID
    registry_version: str = CONSTRUCT_REGISTRY_VERSION
    rule_version_ref: str = CONSTRUCT_REGISTRY_RULE_VERSION
    owner: str = "team-runtime-quality"
    source_refs: tuple[str, ...] = Field(min_length=1)
    constructs: tuple[ConstructEntry, ...] = Field(min_length=1)
    compatibility_policy: Mapping[str, Any]
    authority_boundary: Mapping[str, Any]
    summary: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("source_refs", mode="before")
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        if value != CONSTRUCT_REGISTRY_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {CONSTRUCT_REGISTRY_SCHEMA_VERSION}"
            )
        return value

    @field_validator("registry_id")
    @classmethod
    def _validate_registry_id(cls, value: str) -> str:
        if value != CONSTRUCT_REGISTRY_ID:
            raise ValueError(f"registry_id must be {CONSTRUCT_REGISTRY_ID}")
        return value

    @field_validator("registry_version")
    @classmethod
    def _validate_registry_version(cls, value: str) -> str:
        if value != CONSTRUCT_REGISTRY_VERSION:
            raise ValueError(f"registry_version must be {CONSTRUCT_REGISTRY_VERSION}")
        return value

    @field_validator("rule_version_ref")
    @classmethod
    def _validate_rule_version_ref(cls, value: str) -> str:
        if value != CONSTRUCT_REGISTRY_RULE_VERSION:
            raise ValueError(
                f"rule_version_ref must be {CONSTRUCT_REGISTRY_RULE_VERSION}"
            )
        return value

    @model_validator(mode="after")
    def _validate_registry(self) -> ConstructRegistry:
        construct_ids = [entry.construct_id for entry in self.constructs]
        if len(set(construct_ids)) != len(construct_ids):
            raise ValueError("construct registry contains duplicate construct_id values")
        concept_refs = [entry.concept_spine_ref for entry in self.constructs]
        if len(set(concept_refs)) != len(concept_refs):
            raise ValueError("construct registry contains duplicate concept_spine_ref values")

        summary = dict(self.summary)
        summary.setdefault("construct_count", len(self.constructs))
        summary.setdefault(
            "domains",
            sorted({domain for entry in self.constructs for domain in entry.domain}),
        )
        summary.setdefault(
            "active_construct_count",
            sum(1 for entry in self.constructs if entry.status == "active"),
        )
        object.__setattr__(self, "summary", summary)
        return self


def load_construct_registry(path: str | Path | None = None) -> ConstructRegistry:
    """Load and validate the governed construct registry YAML artifact."""

    registry_path = Path(path) if path is not None else CONSTRUCT_REGISTRY_DEFAULT_PATH
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ConstructRegistryError(f"Construct registry is not a mapping: {registry_path}")
    return ConstructRegistry.model_validate(payload)


def construct_refs_for_alias(
    registry: ConstructRegistry | Mapping[str, Any],
    alias: str,
) -> tuple[str, ...]:
    """Resolve a construct id, common alias, metric alias, or legacy family alias."""

    model = _coerce_registry(registry)
    normalized_alias = _normalize_alias(alias)
    matches: list[str] = []
    for construct in model.constructs:
        aliases = {
            _normalize_alias(construct.construct_id.removeprefix("construct:")),
            _normalize_alias(construct.construct_id),
            *(_normalize_alias(item) for item in construct.aliases),
            *(_normalize_alias(item.alias) for item in construct.compatibility_aliases),
        }
        if normalized_alias in aliases:
            matches.append(construct.construct_id)
    return tuple(dict.fromkeys(matches))


def assert_scenario_family_name_alone_does_not_grant_authority(
    registry: ConstructRegistry | Mapping[str, Any],
    legacy_family: str,
    *,
    posture: AuthorityPosture,
) -> None:
    """Fail closed when callers try to use a scenario-family label as authority."""

    model = _coerce_registry(registry)
    normalized_alias = _normalize_alias(legacy_family)
    matches: list[str] = []
    legacy_alias = False
    for construct in model.constructs:
        for alias in construct.compatibility_aliases:
            if _normalize_alias(alias.alias) == normalized_alias:
                matches.append(construct.construct_id)
                legacy_alias = alias.alias_type == "legacy_scenario_family"
    if not matches:
        raise ConstructRegistryError(f"construct_alias_unknown: {legacy_family}")
    if legacy_alias:
        refs = ", ".join(dict.fromkeys(matches))
        raise ValueError(
            "scenario_family_name_not_authority: "
            f"{legacy_family} maps to {refs} for {posture}, but callers must bind "
            "a construct and satisfy posture-specific authority_requirements."
        )


def construct_registry_concept_spine_entries(
    registry: ConstructRegistry | Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Project construct links into W2.A concept-spine compatible entries."""

    model = _coerce_registry(registry)
    entries: list[dict[str, Any]] = []
    for construct in model.constructs:
        entries.append(
            {
                "concept_id": construct.concept_spine_ref,
                "concept_type": "metric",
                "label": construct.construct_id.removeprefix("construct:").replace("_", " "),
                "namespace_refs": ("policyos.construct_registry.v1",),
                "source_refs": (f"construct-registry://{model.registry_id}",),
                "producer_refs": ("runtime.construct_registry",),
                "status": "resolved",
                "time_roles": dict.fromkeys(
                    construct.required_time_roles,
                    "required_by_construct_registry",
                ),
                "geography_refs": (),
                "population_refs": (),
                "unit_refs": (),
                "bearing_policy_construct": construct.construct_id,
            }
        )
    return tuple(entries)


def validate_construct_registry_coverage(
    registry: ConstructRegistry | Mapping[str, Any],
    *,
    corpus_manifest_path: str | Path,
    minimum_constructs_per_case: int = 3,
) -> dict[str, Any]:
    """Check universal-corpus construct coverage and emit typed blockers."""

    model = _coerce_registry(registry)
    case_ids = _corpus_case_ids(Path(corpus_manifest_path))
    constructs_by_case: dict[str, set[str]] = {case_id: set() for case_id in case_ids}
    for construct in model.constructs:
        for binding in construct.corpus_bindings:
            constructs_by_case.setdefault(binding.case_id, set()).add(construct.construct_id)

    blockers: list[dict[str, Any]] = []
    case_coverage: list[dict[str, Any]] = []
    for case_id in case_ids:
        refs = sorted(constructs_by_case.get(case_id, set()))
        case_coverage.append(
            {
                "case_id": case_id,
                "construct_count": len(refs),
                "construct_refs": refs,
            }
        )
        if len(refs) < minimum_constructs_per_case:
            blockers.append(
                {
                    "code": "construct_registry_coverage_gap",
                    "case_id": case_id,
                    "construct_count": len(refs),
                    "required_construct_count": minimum_constructs_per_case,
                    "owner": "team-runtime-quality",
                    "next_command": (
                        "Add construct corpus_bindings or mark the case as out of "
                        "scope through a governed registry revision."
                    ),
                }
            )

    return {
        "schema_version": "policyos.construct_registry.coverage_report.v1",
        "status": "pass" if not blockers else "blocked",
        "registry_id": model.registry_id,
        "summary": {
            "case_count": len(case_ids),
            "minimum_constructs_per_case": minimum_constructs_per_case,
            "coverage_gap_count": len(blockers),
        },
        "case_coverage": case_coverage,
        "blockers": blockers,
    }


def validate_obligation_rule_construct_refs(
    registry: ConstructRegistry | Mapping[str, Any],
    catalog: Any,
) -> dict[str, Any]:
    """Validate that W6.B vertical required-evidence refs point to constructs."""

    model = _coerce_registry(registry)
    known_constructs = {entry.construct_id for entry in model.constructs}
    blockers: list[dict[str, Any]] = []
    checked = 0
    rules = tuple(getattr(catalog, "rules", ()))
    for rule in rules:
        logic = dict(getattr(rule, "logic", {}) or {})
        if not logic.get("vertical_rule"):
            continue
        refs = tuple(str(ref) for ref in logic.get("required_evidence_constructs") or ())
        legacy_keys = [
            key
            for key in ("required_evidence_family", "evidence_family", "data_family")
            if key in logic
        ]
        if refs or legacy_keys:
            checked += 1
        if legacy_keys:
            blockers.append(
                {
                    "code": "obligation_rule_legacy_required_evidence_family",
                    "rule_id": getattr(rule, "rule_id", "unknown"),
                    "legacy_keys": legacy_keys,
                    "owner": "team-runtime-quality",
                }
            )
        if logic.get("vertical_rule") and not refs:
            blockers.append(
                {
                    "code": "obligation_rule_required_evidence_construct_missing",
                    "rule_id": getattr(rule, "rule_id", "unknown"),
                    "owner": "team-runtime-quality",
                }
            )
        for ref in refs:
            if ref not in known_constructs:
                blockers.append(
                    {
                        "code": "obligation_rule_required_evidence_construct_unknown",
                        "rule_id": getattr(rule, "rule_id", "unknown"),
                        "construct_ref": ref,
                        "owner": "team-runtime-quality",
                    }
                )

    return {
        "schema_version": "policyos.construct_registry.obligation_rule_ref_report.v1",
        "status": "pass" if not blockers else "blocked",
        "summary": {
            "checked_rule_count": checked,
            "blocker_count": len(blockers),
        },
        "blockers": blockers,
    }


def non_ukraine_bound_constructs(
    registry: ConstructRegistry | Mapping[str, Any],
) -> tuple[str, ...]:
    """Return constructs bound to at least one non-Ukraine corpus fixture."""

    model = _coerce_registry(registry)
    refs = [
        construct.construct_id
        for construct in model.constructs
        if any(
            binding.case_id != "ua-msme-affordable-loans-2022"
            for binding in construct.corpus_bindings
        )
    ]
    return tuple(sorted(dict.fromkeys(refs)))


def construct_registry_public_surface(
    registry: ConstructRegistry | Mapping[str, Any],
) -> dict[str, Any]:
    """Return an inspection surface that cannot be used as evidence authority."""

    model = _coerce_registry(registry)
    domains = Counter(domain for construct in model.constructs for domain in construct.domain)
    return {
        "schema_version": "policyos.construct_registry.public_surface.v1",
        "registry_id": model.registry_id,
        "registry_version": model.registry_version,
        "construct_count": len(model.constructs),
        "domains": dict(sorted(domains.items())),
        "authoritative_for": ["construct_registry_inspection"],
        "may_not_use_for": ["producer_evidence_authority", "scenario_family_authority"],
    }


def _coerce_registry(registry: ConstructRegistry | Mapping[str, Any]) -> ConstructRegistry:
    if isinstance(registry, ConstructRegistry):
        return registry
    return ConstructRegistry.model_validate(registry)


def _corpus_case_ids(path: Path) -> tuple[str, ...]:
    payload = json_load(path)
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, Sequence):
        raise ConstructRegistryError(f"Universal corpus manifest missing fixtures: {path}")
    case_ids = [
        _required_text(row.get("case_id")) for row in fixtures if isinstance(row, Mapping)
    ]
    return tuple(sorted(case_ids))


def json_load(path: Path) -> Mapping[str, Any]:
    """Load a JSON mapping from disk."""

    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ConstructRegistryError(f"JSON payload is not a mapping: {path}")
    return payload


def _normalize_alias(value: object) -> str:
    return _required_text(value).strip().casefold().replace("-", "_").replace(" ", "_")


def _required_text(value: object) -> str:
    if value is None:
        raise ValueError("required text is missing")
    text = str(value).strip()
    if not text:
        raise ValueError("required text is empty")
    return text


def _validate_governed_values(
    values: tuple[str, ...],
    *,
    allowed: frozenset[str],
    field_name: str,
) -> tuple[str, ...]:
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ValueError(
            f"{field_name} contains values outside the governed taxonomy: "
            + ", ".join(unknown)
        )
    return values


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values: Sequence[object] = (value,)
    elif isinstance(value, Sequence):
        values = value
    else:
        raise TypeError("expected a string or sequence of strings")
    return tuple(_required_text(item) for item in values)


__all__ = [
    "CONSTRUCT_REGISTRY_DEFAULT_PATH",
    "CONSTRUCT_REGISTRY_ID",
    "CONSTRUCT_REGISTRY_RULE_VERSION",
    "CONSTRUCT_REGISTRY_SCHEMA_VERSION",
    "CONSTRUCT_REGISTRY_VERSION",
    "ConstructAliasDeprecation",
    "ConstructAuthorityRequirement",
    "ConstructCompatibilityAlias",
    "ConstructCorpusBinding",
    "ConstructEntry",
    "ConstructRegistry",
    "ConstructRegistryError",
    "ConstructValidityRequirements",
    "assert_scenario_family_name_alone_does_not_grant_authority",
    "construct_refs_for_alias",
    "construct_registry_concept_spine_entries",
    "construct_registry_public_surface",
    "load_construct_registry",
    "non_ukraine_bound_constructs",
    "validate_construct_registry_coverage",
    "validate_obligation_rule_construct_refs",
]
