"""Typed data requirement contracts emitted by the W7.A compiler."""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import quote

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from polisyos.core.contracts import RequirementToCapabilityQuery

DATA_REQUIREMENT_SPEC_SCHEMA_VERSION = "policyos.data_requirement_spec.v1"
DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION = "policyos.data_requirement_compilation.v2"
DATA_REQUIREMENT_COMPILATION_V1_SCHEMA_VERSION = "policyos.data_requirement_compilation.v1"
DATA_REQUIREMENT_BASIS_SCHEMA_VERSION = "policyos.data_requirement_basis_resolution.v1"
CAPABILITY_REQUIREMENT_RESOLUTION_SCHEMA_VERSION = (
    "policyos.data_requirement.capability_requirement_resolution.v1"
)

LineageStrictness = Literal["strict", "standard", "relaxed"]
TransformationTolerance = Literal[
    "none",
    "traceable",
    "derived_feature_allowed",
    "proxy_with_limitation",
]
DataRequirementTimeRole = Literal[
    "observation_time",
    "valid_time",
    "transaction_time",
    "ingestion_time",
    "publication_time",
    "forecast_time",
]


def data_requirement_authority_boundary() -> dict[str, list[str]]:
    """Return the W7.A authority boundary for data requirement artifacts."""

    return {
        "authoritative_for": [
            "data_requirements",
            "fabric_source_selection_preconditions",
            "scenario_evidence_contract_legacy_projection",
        ],
        "may_not_use_for": [
            "source_contract_binding_without_fabric_validation",
            "scenario_family_authority_lookup",
            "claim_support",
            "legal_authority",
            "method_validity",
            "projection_authority",
            "closeout_pass",
        ],
    }


def data_requirement_compilation_event_ref(run_id: str) -> str:
    """Return a collision-resistant event ref for one compiler run ID.

    Args:
        run_id: Exact run identifier to encode as one URI path component.

    Returns:
        The stable producer event reference for the run.

    Raises:
        ValueError: If the run ID is not a non-empty string.
    """

    if not isinstance(run_id, str) or not run_id:
        raise ValueError("data_requirement_run_id_missing")
    return f"event://data-requirement/{quote(run_id, safe='-._~')}"


class DataRequirementScope(BaseModel):
    """Population, geography, and time scope for a claim-bound data requirement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    population: str = Field(min_length=1)
    geography: str = Field(min_length=1)
    time: str = Field(min_length=1)
    time_role: DataRequirementTimeRole = "observation_time"
    jurisdiction: str | None = None

    @field_validator("population", "geography", "time", "jurisdiction", mode="before")
    @classmethod
    def _clean_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class DataQualityMinimums(BaseModel):
    """Minimum quality bar a Fabric SourceContract must satisfy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_quality_score: float = Field(default=0.8, ge=0.0, le=1.0)
    min_completeness: float = Field(default=0.95, ge=0.0, le=1.0)
    required_quality_refs: tuple[str, ...] = Field(default=())

    @field_validator("required_quality_refs", mode="before")
    @classmethod
    def _clean_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class DataRequirementSpec(BaseModel):
    """Claim-bound data requirement consumed by Fabric source selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_requirement_spec.v1"] = (
        DATA_REQUIREMENT_SPEC_SCHEMA_VERSION
    )
    requirement_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    claim_family: str | None = None
    claim_type: str | None = None
    claim_use: str | None = None
    required_data_families: tuple[str, ...] = Field(min_length=1)
    scope: DataRequirementScope
    recency_horizon: str = Field(min_length=1)
    lineage_strictness: LineageStrictness = "strict"
    quality_minima: DataQualityMinimums
    missingness_tolerance: float = Field(ge=0.0, le=1.0)
    transformation_tolerance: TransformationTolerance
    admissibility_predicates: tuple[str, ...] = Field(min_length=1)
    mandatory_facets: tuple[str, ...] = Field(min_length=1)
    facet_refs: tuple[str, ...] = Field(default=())
    obligation_refs: tuple[str, ...] = Field(default=())
    concept_spine_refs: tuple[str, ...] = Field(min_length=1)
    authority_profile_refs: tuple[str, ...] = Field(min_length=1)
    rule_version_ref: str = "policyos.data_requirement.compiler.v2"
    producer: str = "polisyos.data_requirement.compiler.DataRequirementCompiler"
    source_requirement_refs: tuple[str, ...] = Field(default=())
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "requirement_id",
        "claim_id",
        "claim_family",
        "claim_type",
        "claim_use",
        "recency_horizon",
        "rule_version_ref",
        "producer",
        mode="before",
    )
    @classmethod
    def _clean_optional_or_required_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator(
        "required_data_families",
        "admissibility_predicates",
        "mandatory_facets",
        "facet_refs",
        "obligation_refs",
        "concept_spine_refs",
        "authority_profile_refs",
        "source_requirement_refs",
        mode="before",
    )
    @classmethod
    def _clean_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _validate_authority_and_facets(self) -> DataRequirementSpec:
        if not self.authority_profile_refs:
            raise ValueError("authority_profile_refs are required for data authority boundary")
        if not self.concept_spine_refs:
            raise ValueError("concept_spine_refs are required for data requirement grounding")
        if not self.mandatory_facets:
            raise ValueError("mandatory_facets are required for Fabric admissibility")
        if self.missingness_tolerance > 1.0 - self.quality_minima.min_completeness:
            raise ValueError(
                "missingness_tolerance cannot exceed the completeness gap allowed by quality_minima"
            )
        return self


class CapabilityBindingSnapshot(BaseModel):
    """Typed projection of the resolver port fields consumed by requirement compilation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(min_length=1)
    rule_version_ref: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    selected_capability_ref: str | None = None
    construct_ref: str = Field(min_length=1)
    capability_index_ref: str | None = None
    authority_level: str = Field(min_length=1)
    authority_envelope_result: str = Field(min_length=1)
    binding_reasons: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    acquisition_strategies: tuple[dict[str, Any], ...] = ()
    rejected_alternatives: tuple[dict[str, Any], ...] = ()
    conflict_markers: tuple[dict[str, Any], ...] = ()

    @field_validator("binding_reasons", "blocked_reasons", "limitations", mode="before")
    @classmethod
    def _clean_reason_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _validate_result_identity(self) -> CapabilityBindingSnapshot:
        if not self.requirement_id.strip() or not self.construct_ref.strip():
            raise ValueError("capability_binding_identity_missing")
        return self


class CapabilityRequirementResolution(BaseModel):
    """Versioned compiler result binding one required construct to a resolver outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_requirement.capability_requirement_resolution.v1"] = (
        CAPABILITY_REQUIREMENT_RESOLUTION_SCHEMA_VERSION
    )
    scope_profile_id: str | None = None
    query: RequirementToCapabilityQuery
    state: Literal["binding_returned", "not_established"]
    binding: CapabilityBindingSnapshot | None = None
    reason_codes: tuple[str, ...] = ()

    @field_validator("scope_profile_id", mode="before")
    @classmethod
    def _clean_profile_id(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("reason_codes", mode="before")
    @classmethod
    def _clean_reason_codes(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_serializer(mode="wrap")
    def _serialize_query_with_contract_alias(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        payload = handler(self)
        payload["query"] = self.query.model_dump(mode="json", by_alias=True)
        return payload

    @model_validator(mode="after")
    def _validate_query_binding(self) -> CapabilityRequirementResolution:
        if self.binding is None:
            if self.state != "not_established" or not self.reason_codes:
                raise ValueError("capability_resolution_missing_binding_reason")
            return self
        if self.state != "binding_returned":
            raise ValueError("capability_resolution_state_binding_mismatch")
        if self.binding.requirement_id != self.query.requirement_id:
            raise ValueError("capability_resolution_requirement_id_mismatch")
        bound_construct = self.binding.construct_ref.removeprefix("construct:")
        if bound_construct != self.query.construct:
            raise ValueError("capability_resolution_construct_mismatch")
        return self


class DataRequirementBasisResolution(BaseModel):
    """Producer-owned status for the admitted data-requirement basis.

    ``established`` means that the compiler can point to a present candidate
    basis. The ``basis_grade`` states how that predicate was established; in
    particular, a consumer-declared family list is never upgraded to authority.
    This model carries references and reasons, not a family or construct.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_requirement_basis_resolution.v1"] = (
        DATA_REQUIREMENT_BASIS_SCHEMA_VERSION
    )
    state: Literal["established", "not_established"]
    source: Literal[
        "governed_capability_resolution",
        "explicit_scenario_family_declaration",
        "not_established",
    ]
    basis_grade: Literal[
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    ]
    reason_codes: tuple[
        Literal[
            "governed_capability_basis_resolved",
            "governed_capability_resolution_incomplete",
            "explicit_scenario_family_declaration_candidate_only",
            "explicit_empty_family_declaration_not_proof",
            "no_explicit_or_governed_data_basis",
            "legacy_report_basis_not_carried",
            "empty_compilation_not_proof_of_no_data",
        ],
        ...,
    ] = Field(default=())
    source_refs: tuple[str, ...] = Field(default=())

    @field_validator("reason_codes", "source_refs", mode="before")
    @classmethod
    def _clean_basis_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _validate_basis_grade(self) -> DataRequirementBasisResolution:
        if not self.reason_codes:
            raise ValueError("data_requirement_basis_reason_missing")
        if self.state == "established":
            if not self.source_refs or self.source == "not_established":
                raise ValueError("data_requirement_basis_source_missing")
            if self.basis_grade == "not_established":
                raise ValueError("data_requirement_basis_grade_mismatch")
            if (
                self.source == "explicit_scenario_family_declaration"
                and self.basis_grade != "consumer_asserted"
            ):
                raise ValueError("explicit_family_basis_must_remain_consumer_asserted")
            if self.source == "governed_capability_resolution" and self.basis_grade != "recomputed":
                raise ValueError("governed_capability_basis_must_be_recomputed")
        elif self.basis_grade != "not_established":
            raise ValueError("unestablished_basis_grade_mismatch")
        return self


def _legacy_unestablished_basis() -> DataRequirementBasisResolution:
    """Fail closed when an older producer did not carry a basis assessment."""

    return DataRequirementBasisResolution(
        state="not_established",
        source="not_established",
        basis_grade="not_established",
        reason_codes=("legacy_report_basis_not_carried",),
    )


class DataRequirementCompilationReport(BaseModel):
    """Compiler report carrying specs, basis status, and legacy projections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_requirement_compilation.v2"] = (
        DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION
    )
    run_id: str = Field(min_length=1)
    scenario_id: str | None = None
    specs: tuple[DataRequirementSpec, ...] = Field(default=())
    capability_resolution_schema_version: (
        Literal["policyos.data_requirement.capability_requirement_resolution.v1"] | None
    ) = None
    capability_requirement_resolutions: tuple[CapabilityRequirementResolution, ...] | None = None
    legacy_admissible_data_source_families: tuple[str, ...] = Field(default=())
    requirement_basis: DataRequirementBasisResolution = Field(
        default_factory=_legacy_unestablished_basis
    )
    producer_report_ref: str | None = Field(default=None, min_length=1)
    subject_refs: tuple[str, ...] = Field(default=())
    rule_version_refs: tuple[str, ...] = Field(default=())
    input_content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    capability_reality_label: Literal["implemented", "bridge_missing"] = "bridge_missing"
    pattern_refs: tuple[str, ...] = ("P02", "P04", "P05", "P08", "P12", "P14", "P37", "P38")
    runtime_event_ref: str | None = Field(default=None, min_length=1)
    authority_boundary: dict[str, Any] = Field(default_factory=data_requirement_authority_boundary)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("legacy_admissible_data_source_families", mode="before")
    @classmethod
    def _clean_family_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _derive_legacy_families(self) -> DataRequirementCompilationReport:
        if not self.legacy_admissible_data_source_families:
            families = tuple(
                dict.fromkeys(
                    family for spec in self.specs for family in spec.required_data_families
                )
            )
            object.__setattr__(self, "legacy_admissible_data_source_families", families)
        expected_report_ref = data_requirement_compilation_event_ref(self.run_id)
        report_ref = self.producer_report_ref or self.runtime_event_ref or expected_report_ref
        if self.producer_report_ref not in (None, report_ref) or self.runtime_event_ref not in (
            None,
            report_ref,
        ):
            raise ValueError("data_requirement_report_ref_mismatch")
        object.__setattr__(self, "producer_report_ref", report_ref)
        object.__setattr__(self, "runtime_event_ref", report_ref)
        if self.requirement_basis.state == "established":
            if not self.subject_refs or not self.rule_version_refs or not self.input_content_hash:
                raise ValueError("established_requirement_basis_input_binding_missing")
            if report_ref not in self.requirement_basis.source_refs:
                raise ValueError("requirement_basis_report_ref_missing")
            object.__setattr__(self, "capability_reality_label", "implemented")
        else:
            object.__setattr__(self, "capability_reality_label", "bridge_missing")
        if not self.authority_boundary:
            object.__setattr__(
                self,
                "authority_boundary",
                data_requirement_authority_boundary(),
            )
        if (self.capability_resolution_schema_version is None) != (
            self.capability_requirement_resolutions is None
        ):
            raise ValueError("capability_resolution_carrier_version_mismatch")
        return self


class DataRequirementCompilationReportV1(BaseModel):
    """Strict reader for the historical v1 report wire shape.

    The original report has no basis field. The typed property therefore
    reports an unestablished basis without changing the serialized v1 payload.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    _source_bytes: bytes | None = PrivateAttr(default=None)

    schema_version: Literal["policyos.data_requirement_compilation.v1"]
    run_id: str = Field(min_length=1)
    scenario_id: str | None = None
    specs: tuple[DataRequirementSpec, ...] = Field(default=())
    capability_resolution_schema_version: (
        Literal["policyos.data_requirement.capability_requirement_resolution.v1"] | None
    ) = None
    capability_requirement_resolutions: tuple[CapabilityRequirementResolution, ...] | None = None
    legacy_admissible_data_source_families: tuple[str, ...] = Field(default=())
    capability_reality_label: Literal["implemented"] = "implemented"
    pattern_refs: tuple[str, ...] = ("P02", "P05", "P08", "P12", "P14")
    runtime_event_ref: str | None = Field(default=None, min_length=1)
    authority_boundary: dict[str, Any] = Field(default_factory=data_requirement_authority_boundary)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("legacy_admissible_data_source_families", mode="before")
    @classmethod
    def _clean_legacy_family_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _derive_legacy_families(self) -> DataRequirementCompilationReportV1:
        if not self.legacy_admissible_data_source_families:
            families = tuple(
                dict.fromkeys(
                    family for spec in self.specs for family in spec.required_data_families
                )
            )
            object.__setattr__(self, "legacy_admissible_data_source_families", families)
        if self.runtime_event_ref is None:
            object.__setattr__(
                self,
                "runtime_event_ref",
                f"event://data-requirement/{_slug(self.run_id)}",
            )
        if not self.authority_boundary:
            object.__setattr__(
                self,
                "authority_boundary",
                data_requirement_authority_boundary(),
            )
        if (self.capability_resolution_schema_version is None) != (
            self.capability_requirement_resolutions is None
        ):
            raise ValueError("capability_resolution_carrier_version_mismatch")
        return self

    @property
    def requirement_basis(self) -> DataRequirementBasisResolution:
        """Return the typed absence status without restamping the v1 report."""

        return _legacy_unestablished_basis()

    @property
    def original_bytes(self) -> bytes | None:
        """Return the original JSON bytes when this report was read from bytes."""

        return self._source_bytes


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    raw_values = value if isinstance(value, (list, tuple, set)) else (value,)
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_values:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return tuple(cleaned)


def _slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "-" for ch in value)
    return slug.strip("-") or "run"


__all__ = [
    "CAPABILITY_REQUIREMENT_RESOLUTION_SCHEMA_VERSION",
    "DATA_REQUIREMENT_BASIS_SCHEMA_VERSION",
    "DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION",
    "DATA_REQUIREMENT_COMPILATION_V1_SCHEMA_VERSION",
    "DATA_REQUIREMENT_SPEC_SCHEMA_VERSION",
    "CapabilityBindingSnapshot",
    "CapabilityRequirementResolution",
    "DataQualityMinimums",
    "DataRequirementBasisResolution",
    "DataRequirementCompilationReport",
    "DataRequirementCompilationReportV1",
    "DataRequirementScope",
    "DataRequirementSpec",
    "DataRequirementTimeRole",
    "LineageStrictness",
    "TransformationTolerance",
    "data_requirement_authority_boundary",
    "data_requirement_compilation_event_ref",
]
