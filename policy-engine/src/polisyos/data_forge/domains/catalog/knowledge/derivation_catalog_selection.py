"""Own policy-bound catalog selection for data-defined derivations.

Catalog text and units are evidence inputs, never authority for a transform role.
This module admits a candidate only when the configured metric/canonical-variable
edge and all applicable rights, alignment, binding, and completeness checks hold.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .acquisition_authority import derive_license_disposition
from .variable_alignment import score_variable_pair


class CatalogSelectionError(RuntimeError):
    """Typed fail-closed error raised by catalog selection policy resolution."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(f"{code}: {self.detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CatalogSelectionRoleConfig(_StrictModel):
    """Catalog owner and admissibility policy for one transform input role."""

    role: str = Field(min_length=1)
    catalog_unit: str = Field(min_length=1)
    semantic_anchor: str = Field(min_length=1)
    owner_metric_id: str = Field(min_length=1)
    owner_canonical_variable: str = Field(min_length=1)
    minimum_alignment_confidence: float = Field(ge=0.0, le=1.0)
    allow_proxy: bool
    require_executable_binding: bool
    executable_connectors: tuple[str, ...] = ()
    required_themes: tuple[str, ...] = ()
    forbidden_theme_fragments: tuple[str, ...] = ()
    required_text_fragments: tuple[str, ...] = ()
    forbidden_text_fragments: tuple[str, ...] = ()
    reference_value_pattern: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _selection_levers_are_canonical(self) -> Self:
        for field_name in (
            "executable_connectors",
            "required_themes",
            "forbidden_theme_fragments",
            "required_text_fragments",
            "forbidden_text_fragments",
        ):
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be unique and sorted")
        if self.reference_value_pattern is not None:
            try:
                pattern = re.compile(self.reference_value_pattern, re.IGNORECASE)
            except re.error as exc:
                raise ValueError("reference-value pattern must compile") from exc
            if pattern.groups != 1:
                raise ValueError("reference-value pattern requires exactly one capture group")
        return self


class CatalogSelectionPolicyConfig(_StrictModel):
    """Purpose-addressable catalog policy bound to one transform family."""

    policy_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    purposes: tuple[str, ...] = Field(min_length=1)
    country_code: str = Field(min_length=2, max_length=3)
    output_variable_id_template: str = Field(min_length=1)
    roles: tuple[CatalogSelectionRoleConfig, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _policy_is_canonical(self) -> Self:
        if self.purposes != tuple(sorted(set(self.purposes))):
            raise ValueError("purposes must be unique and sorted")
        roles = tuple(item.role for item in self.roles)
        if roles != tuple(sorted(set(roles))):
            raise ValueError("catalog selection roles must be unique and sorted")
        return self

    def role_policy(self, role: str) -> CatalogSelectionRoleConfig:
        """Resolve one exact role or fail closed."""

        matches = tuple(item for item in self.roles if item.role == role)
        if len(matches) != 1:
            raise CatalogSelectionError("catalog_selection_role_unresolved", role)
        return matches[0]

    def role_policy_for_owner_metric(self, owner_metric_id: str) -> CatalogSelectionRoleConfig:
        """Resolve the exact transform role bound to one catalog owner metric."""

        matches = tuple(item for item in self.roles if item.owner_metric_id == owner_metric_id)
        if len(matches) != 1:
            raise CatalogSelectionError(
                "catalog_selection_metric_role_unresolved",
                f"policy={self.policy_id}/metric={owner_metric_id}/count={len(matches)}",
            )
        return matches[0]

    def identity_payload(self) -> dict[str, object]:
        """Return the complete policy projection used for content binding."""

        return self.model_dump(mode="json")


@dataclass(frozen=True)
class DerivationCatalogSelectionOwner:
    """Strict selection policies plus unchanged family rows from one owner source."""

    policies: tuple[CatalogSelectionPolicyConfig, ...]
    families_payload: tuple[Mapping[str, object], ...]
    source_sha256: str


class CatalogSelectionRejectionCode(StrEnum):
    """Typed generic reasons why a catalog candidate is not owner-admissible."""

    ACCESS_AUTH_REQUIRED = "access_auth_required"
    ACQUISITION_METHOD_MISSING = "acquisition_method_missing"
    ALIGNMENT_BELOW_OWNER_THRESHOLD = "alignment_below_owner_threshold"
    ALIGNMENT_MISSING = "alignment_missing"
    CATALOG_UNIT_MISMATCH = "catalog_unit_mismatch"
    DATASET_VERSION_MISSING = "dataset_version_missing"
    DUPLICATE_YEARS = "duplicate_years"
    EXECUTABLE_BINDING_MISSING = "executable_binding_missing"
    EXECUTOR_CONNECTOR_UNIMPLEMENTED = "executor_connector_unimplemented"
    EXECUTION_TIER_NOT_EXECUTABLE = "execution_tier_not_executable"
    FORBIDDEN_TEXT_PRESENT = "forbidden_text_present"
    FORBIDDEN_THEME_PRESENT = "forbidden_theme_present"
    LICENSE_NOT_ADMISSIBLE = "license_not_admissible"
    OWNER_CANONICAL_VARIABLE_MISMATCH = "owner_canonical_variable_mismatch"
    OWNER_METRIC_MISMATCH = "owner_metric_mismatch"
    PARSER_UNSUPPORTED = "parser_unsupported"
    PROXY_NOT_ALLOWED = "proxy_not_allowed"
    PROXY_PENALTY_PRESENT = "proxy_penalty_present"
    REFERENCE_VALUE_MISSING = "reference_value_missing"
    REQUIRED_TEXT_MISSING = "required_text_missing"
    REQUIRED_THEME_MISSING = "required_theme_missing"
    SOURCE_WATERMARK_MISSING = "source_watermark_missing"
    INSUFFICIENT_EXACT_YEARS = "insufficient_exact_years"


class CatalogSelectionCandidateEvidence(_StrictModel):
    """Vocabulary-neutral evidence used to classify one catalog candidate."""

    candidate_kind: Literal["local_series", "live_carrier"]
    catalog_unit: str | None
    metric_id: str | None
    canonical_variable: str | None
    title: str
    description: str
    access_license: str
    alignment_method: str | None
    alignment_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    alignment_is_proxy: bool | None
    alignment_proxy_penalty: float | None = Field(default=None, ge=0.0, le=1.0)
    exact_binding_count: int = Field(ge=0)
    maximum_binding_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    maximum_distribution_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    connector_id: str | None = None
    execution_tier: str | None = None
    access_auth_required: bool | None = None
    parser_supported: bool | None = None
    themes: tuple[str, ...] = ()
    point_count: int | None = Field(default=None, ge=0)
    distinct_year_count: int | None = Field(default=None, ge=0)
    duplicate_year_count: int | None = Field(default=None, ge=0)
    source_watermark_count: int | None = Field(default=None, ge=0)
    dataset_version_count: int | None = Field(default=None, ge=0)
    acquisition_method_count: int | None = Field(default=None, ge=0)
    minimum_exact_years: int = Field(default=2, ge=1)

    @model_validator(mode="after")
    def _evidence_is_canonical(self) -> Self:
        if self.themes != tuple(sorted(set(self.themes))):
            raise ValueError("candidate themes must be unique and sorted")
        if self.candidate_kind == "local_series":
            counts = (
                self.point_count,
                self.distinct_year_count,
                self.duplicate_year_count,
                self.source_watermark_count,
                self.dataset_version_count,
                self.acquisition_method_count,
            )
            if any(value is None for value in counts):
                raise ValueError("local series completeness evidence must be complete")
        return self


class CatalogSelectionCandidateEvaluation(_StrictModel):
    """Typed shared disposition and generic ranking evidence for one candidate."""

    rejection_codes: tuple[CatalogSelectionRejectionCode, ...]
    eligible: bool
    semantic_alignment_score: float = Field(ge=0.0, le=1.0)
    authority_score: float | None = Field(default=None, ge=0.0, le=1.0)
    reference_value: str | None = None

    @model_validator(mode="after")
    def _disposition_is_derived(self) -> Self:
        if self.rejection_codes != tuple(sorted(set(self.rejection_codes), key=str)):
            raise ValueError("rejection codes must be unique and sorted")
        if self.eligible != (not self.rejection_codes):
            raise ValueError("eligibility must derive from rejection codes")
        return self


def load_derivation_catalog_selection(
    source: str | Path | Mapping[str, object],
) -> DerivationCatalogSelectionOwner:
    """Load strict selection policies and family rows from TOML or an in-memory source."""

    if isinstance(source, Mapping):
        payload = dict(source)
        source_bytes = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    else:
        path = Path(source)
        try:
            source_bytes = path.read_bytes()
            payload = tomllib.loads(source_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            raise CatalogSelectionError("catalog_selection_owner_invalid", path.as_posix()) from exc
    allowed_keys = {"catalog_selection_policies", "families"}
    if set(payload) - allowed_keys:
        raise CatalogSelectionError(
            "catalog_selection_owner_invalid",
            "unknown root fields: " + ",".join(sorted(set(payload) - allowed_keys)),
        )
    policies_raw = payload.get("catalog_selection_policies")
    families_raw = payload.get("families")
    if (
        not isinstance(policies_raw, Sequence)
        or isinstance(policies_raw, (str, bytes, bytearray))
        or not isinstance(families_raw, Sequence)
        or isinstance(families_raw, (str, bytes, bytearray))
    ):
        raise CatalogSelectionError("catalog_selection_owner_invalid", "missing policy/family rows")
    policies = tuple(CatalogSelectionPolicyConfig.model_validate(item) for item in policies_raw)
    families: list[Mapping[str, object]] = []
    for item in families_raw:
        if not isinstance(item, Mapping):
            raise CatalogSelectionError(
                "catalog_selection_owner_invalid",
                "family row is not a map",
            )
        families.append(dict(item))
    policy_ids = tuple(item.policy_id for item in policies)
    if len(policy_ids) != len(set(policy_ids)):
        raise CatalogSelectionError(
            "catalog_selection_owner_invalid",
            "selection policy identities must be unique",
        )
    return DerivationCatalogSelectionOwner(
        policies=tuple(sorted(policies, key=lambda item: item.policy_id)),
        families_payload=tuple(families),
        source_sha256=f"sha256:{hashlib.sha256(source_bytes).hexdigest()}",
    )


def catalog_selection_policies_for_purpose(
    owner: DerivationCatalogSelectionOwner,
    *,
    purpose: str,
) -> tuple[CatalogSelectionPolicyConfig, ...]:
    """Return every policy explicitly declaring a purpose, sorted by family id."""

    return tuple(
        sorted(
            (item for item in owner.policies if purpose in item.purposes),
            key=lambda item: (item.family_id, item.method_version, item.policy_id),
        )
    )


def resolve_catalog_selection_policy(
    owner: DerivationCatalogSelectionOwner,
    *,
    purpose: str,
    owner_metric_id: str | None = None,
    family_id: str | None = None,
    method_version: str | None = None,
) -> CatalogSelectionPolicyConfig:
    """Resolve exactly one purpose policy, optionally bound to a paid owner metric."""

    matches = catalog_selection_policies_for_purpose(owner, purpose=purpose)
    if owner_metric_id is not None:
        matches = tuple(
            policy
            for policy in matches
            if any(role.owner_metric_id == owner_metric_id for role in policy.roles)
        )
    if family_id is not None:
        matches = tuple(policy for policy in matches if policy.family_id == family_id)
    if method_version is not None:
        matches = tuple(policy for policy in matches if policy.method_version == method_version)
    if len(matches) != 1:
        identity = (
            f"family={family_id or '*'}/version={method_version or '*'}"
            if family_id is not None or method_version is not None
            else f"metric={owner_metric_id or '*'}"
        )
        raise CatalogSelectionError(
            "catalog_selection_policy_unresolved",
            f"purpose={purpose}/{identity}/count={len(matches)}",
        )
    return matches[0]


def evaluate_catalog_selection_candidate(
    policy: CatalogSelectionRoleConfig,
    evidence: CatalogSelectionCandidateEvidence,
) -> CatalogSelectionCandidateEvaluation:
    """Evaluate one candidate through the shared owner-edge and admissibility rules."""

    codes: set[CatalogSelectionRejectionCode] = set()
    if evidence.catalog_unit != policy.catalog_unit:
        codes.add(CatalogSelectionRejectionCode.CATALOG_UNIT_MISMATCH)
    if evidence.metric_id != policy.owner_metric_id:
        codes.add(CatalogSelectionRejectionCode.OWNER_METRIC_MISMATCH)
    if evidence.canonical_variable != policy.owner_canonical_variable:
        codes.add(CatalogSelectionRejectionCode.OWNER_CANONICAL_VARIABLE_MISMATCH)
    if derive_license_disposition(evidence.access_license).value != "admissible_open":
        codes.add(CatalogSelectionRejectionCode.LICENSE_NOT_ADMISSIBLE)
    if evidence.alignment_method is None or evidence.alignment_confidence is None:
        codes.add(CatalogSelectionRejectionCode.ALIGNMENT_MISSING)
    elif evidence.alignment_confidence < policy.minimum_alignment_confidence:
        codes.add(CatalogSelectionRejectionCode.ALIGNMENT_BELOW_OWNER_THRESHOLD)
    if not policy.allow_proxy and evidence.alignment_is_proxy is not False:
        codes.add(CatalogSelectionRejectionCode.PROXY_NOT_ALLOWED)
    if not policy.allow_proxy and evidence.alignment_proxy_penalty not in (None, 0, 0.0):
        codes.add(CatalogSelectionRejectionCode.PROXY_PENALTY_PRESENT)
    if policy.require_executable_binding and (
        evidence.exact_binding_count < 1
        or evidence.maximum_binding_confidence is None
        or evidence.maximum_distribution_quality is None
    ):
        codes.add(CatalogSelectionRejectionCode.EXECUTABLE_BINDING_MISSING)

    normalized = f"{evidence.title} {evidence.description}".casefold()
    if any(fragment.casefold() not in normalized for fragment in policy.required_text_fragments):
        codes.add(CatalogSelectionRejectionCode.REQUIRED_TEXT_MISSING)
    if any(fragment.casefold() in normalized for fragment in policy.forbidden_text_fragments):
        codes.add(CatalogSelectionRejectionCode.FORBIDDEN_TEXT_PRESENT)
    reference_value: str | None = None
    if policy.reference_value_pattern is not None:
        match = re.search(policy.reference_value_pattern, normalized, re.IGNORECASE)
        if match is None:
            codes.add(CatalogSelectionRejectionCode.REFERENCE_VALUE_MISSING)
        else:
            reference_value = match.group(1)

    if evidence.candidate_kind == "local_series":
        counts = (
            evidence.point_count,
            evidence.distinct_year_count,
            evidence.duplicate_year_count,
            evidence.source_watermark_count,
            evidence.dataset_version_count,
            evidence.acquisition_method_count,
        )
        if any(value is None for value in counts):
            raise CatalogSelectionError("local_series_completeness_unresolved")
        point_count = int(evidence.point_count or 0)
        distinct_year_count = int(evidence.distinct_year_count or 0)
        duplicate_year_count = int(evidence.duplicate_year_count or 0)
        source_watermark_count = int(evidence.source_watermark_count or 0)
        dataset_version_count = int(evidence.dataset_version_count or 0)
        acquisition_method_count = int(evidence.acquisition_method_count or 0)
        if distinct_year_count < evidence.minimum_exact_years:
            codes.add(CatalogSelectionRejectionCode.INSUFFICIENT_EXACT_YEARS)
        if duplicate_year_count or point_count != distinct_year_count:
            codes.add(CatalogSelectionRejectionCode.DUPLICATE_YEARS)
        if source_watermark_count != point_count:
            codes.add(CatalogSelectionRejectionCode.SOURCE_WATERMARK_MISSING)
        if dataset_version_count != point_count:
            codes.add(CatalogSelectionRejectionCode.DATASET_VERSION_MISSING)
        if acquisition_method_count != point_count:
            codes.add(CatalogSelectionRejectionCode.ACQUISITION_METHOD_MISSING)
    else:
        if (
            policy.executable_connectors
            and evidence.connector_id not in policy.executable_connectors
        ):
            codes.add(CatalogSelectionRejectionCode.EXECUTOR_CONNECTOR_UNIMPLEMENTED)
        if evidence.execution_tier not in {"fetchable", "transport_ready"}:
            codes.add(CatalogSelectionRejectionCode.EXECUTION_TIER_NOT_EXECUTABLE)
        if evidence.access_auth_required is not False:
            codes.add(CatalogSelectionRejectionCode.ACCESS_AUTH_REQUIRED)
        if evidence.parser_supported is not True:
            codes.add(CatalogSelectionRejectionCode.PARSER_UNSUPPORTED)
        if not set(policy.required_themes).issubset(evidence.themes):
            codes.add(CatalogSelectionRejectionCode.REQUIRED_THEME_MISSING)
        if any(
            fragment.casefold() in theme.casefold()
            for fragment in policy.forbidden_theme_fragments
            for theme in evidence.themes
        ):
            codes.add(CatalogSelectionRejectionCode.FORBIDDEN_THEME_PRESENT)

    semantic_score = score_variable_pair(
        left_name=policy.semantic_anchor,
        right_name=(
            f"{evidence.metric_id or ''} {evidence.canonical_variable or ''} "
            f"{evidence.title} {evidence.description}"
        ),
        left_unit=policy.catalog_unit,
        right_unit=evidence.catalog_unit or "unresolved",
    ).overall_score
    authority_values = (
        evidence.alignment_confidence,
        evidence.maximum_binding_confidence,
        evidence.maximum_distribution_quality,
    )
    authority_score = (
        None
        if any(value is None for value in authority_values)
        else min(float(value) for value in authority_values if value is not None)
    )
    rejection_codes = tuple(sorted(codes, key=str))
    return CatalogSelectionCandidateEvaluation(
        rejection_codes=rejection_codes,
        eligible=not rejection_codes,
        semantic_alignment_score=semantic_score,
        authority_score=authority_score,
        reference_value=reference_value,
    )


def catalog_selection_candidate_rank(
    evaluation: CatalogSelectionCandidateEvaluation,
    *,
    identity: tuple[str, ...],
) -> tuple[object, ...]:
    """Return the vocabulary-neutral deterministic ranking key for a candidate."""

    return (
        -evaluation.semantic_alignment_score,
        -(evaluation.authority_score or 0.0),
        *identity,
    )


__all__ = [
    "CatalogSelectionCandidateEvaluation",
    "CatalogSelectionCandidateEvidence",
    "CatalogSelectionError",
    "CatalogSelectionPolicyConfig",
    "CatalogSelectionRejectionCode",
    "CatalogSelectionRoleConfig",
    "DerivationCatalogSelectionOwner",
    "catalog_selection_candidate_rank",
    "catalog_selection_policies_for_purpose",
    "evaluate_catalog_selection_candidate",
    "load_derivation_catalog_selection",
    "resolve_catalog_selection_policy",
]
