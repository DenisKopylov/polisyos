"""DOD-137/138/139: Alignment certification policy, outer objective, and bounded search."""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.datasets.knowledge.proxy_resolver import compose_confidence_chain
from polisyos.datasets.knowledge.variable_alignment import (
    VariableAlignment,
    default_seed_alignments_path,
    load_seed_alignments,
    score_variable_pair,
)
from polisyos.ir.analytics.cross_graph import (
    InterfaceMapping,
    InterfaceMappingEntry,
    InterfaceRole,
    InterfaceVariableBinding,
    InterfaceVariableSchema,
    SCMFragment,
)
from polisyos.ir.analytics.latent_bridge_synthesis import (
    LatentBridgeEvidence,
    LatentBridgeHypothesis,
    LatentBridgeHypothesisRef,
    LatentBridgeStatus,
    LatentBridgeSynthesisPolicy,
    load_latent_bridge_hypothesis,
    persist_latent_bridge_hypothesis,
    synthesize_latent_bridge,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import AlignmentReportRef, VariableAlignmentCertificateRef
from polisyos.scientist.cross_graph.compiler import (
    build_fragment_alignment_ontology_warnings,
)
from polisyos.scientist.search.latent_governance import (
    assess_latent_bridge_governance,
    materialize_latent_bridge_governance,
)

_VARIABLE_ALIGNMENT_CERTIFICATE_SCHEMA_NAME = "ir.variable_alignment_certificate"
_VARIABLE_ALIGNMENT_CERTIFICATE_SCHEMA_VERSION = "1.2"
_ALIGNMENT_REPORT_SCHEMA_NAME = "ir.alignment_report"
_ALIGNMENT_REPORT_SCHEMA_VERSION = "1.2"
_EXPECTED_ONTOLOGY_WARNING_ERRORS = (AttributeError, KeyError, TypeError, ValueError)
logger = logging.getLogger(__name__)


class AlignmentCertificateType(str, Enum):
    """Alignment certificate type public type."""
    EXACT = "exact"
    SCALE_LINK = "scale_link"
    LATENT_LINK_IRT = "latent_link_irt"
    PROXY_BUNDLE = "proxy_bundle"
    TEXT_CONCEPT_MAP = "text_concept_map"


class AlignmentType(str, Enum):
    """Alignment type public type."""
    EXACT = "exact"
    SCALE_LINKED = "scale_linked"
    PROXY = "proxy"
    LATENT_BRIDGE = "latent_bridge"
    INCOMPATIBLE = "incompatible"


class AlignmentReviewerState(str, Enum):
    """Alignment reviewer state data model."""
    AUTOMATED = "automated"
    PENDING_REVIEW = "pending_review"
    HUMAN_VERIFIED = "human_verified"


class MeasurementComparabilityGrade(str, Enum):
    """Measurement comparability grade public type."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


class AlignmentOverallStatus(str, Enum):
    """Alignment overall status public type."""
    ALIGNED = "aligned"
    PARTIALLY_ALIGNED = "partially_aligned"
    INCOMPATIBLE = "incompatible"


class AlignmentReviewStatus(str, Enum):
    """Alignment review status public type."""
    CLEAR = "clear"
    PENDING_REVIEW = "pending_review"


class MetadataCheckStatus(str, Enum):
    """Metadata check status public type."""
    MATCH = "match"
    COMPATIBLE = "compatible"
    WARNING = "warning"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class AlignmentDegradedOutcomeCode(str, Enum):
    """Typed degraded outcomes for optional alignment diagnostics."""

    ONTOLOGY_WARNING_BUILD_FAILED = "ontology_warning_build_failed"


class AlignmentDegradedOutcome(BaseModel):
    """Structured degraded outcome captured inside alignment-report metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: AlignmentDegradedOutcomeCode
    fragment_pair: tuple[str, str]
    detail: str = Field(..., min_length=1, max_length=512)


@dataclass(frozen=True)
class _OntologyWarningResult:
    warnings: tuple[str, ...] = ()
    degraded_outcomes: tuple[AlignmentDegradedOutcome, ...] = ()


class AlignmentVerificationConfig(BaseModel):
    """Deterministic verification rules for SCM fragment interface alignment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_candidate_score: float = Field(default=0.45, ge=0.0, le=1.0)
    min_proxy_score: float = Field(default=0.55, ge=0.0, le=1.0)
    min_definition_overlap: float = Field(default=0.25, ge=0.0, le=1.0)
    min_exact_semantic_score: float = Field(default=0.85, ge=0.0, le=1.0)
    known_unit_transforms: dict[str, str | None] = Field(
        default_factory=lambda: {
            "percent->ratio": "artifact:transform:percent_to_ratio",
            "ratio->percent": "artifact:transform:ratio_to_percent",
        }
    )
    explicit_latent_bridges: dict[str, Any] = Field(default_factory=dict)
    human_verified_pairs: list[str] = Field(default_factory=list)
    metadata_comparator_overrides: dict[str, str] = Field(default_factory=dict)
    seed_alignments_path: str | None = None
    latent_bridge_policy: LatentBridgeSynthesisPolicy = Field(
        default_factory=LatentBridgeSynthesisPolicy
    )
    latent_bridge_evidence: dict[str, LatentBridgeEvidence] = Field(default_factory=dict)


class AlignmentCertificate(BaseModel):
    """Single alignment certificate between a source and target variable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cert_type: AlignmentCertificateType
    source_variable: str
    target_variable: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)


class CertificationResult(BaseModel):
    """Result of validating a chain of alignment certificates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    effective_confidence: float = Field(ge=0.0, le=1.0)
    violations: list[str] = Field(default_factory=list)
    long_chain_warning: str | None = None


class VariableAlignmentCertificate(BaseModel):
    """B.1 IR contract for semantic alignment between fragment interface variables."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.2", pattern=r"^\d+\.\d+$")
    variable_a: str = Field(min_length=1)
    fragment_a_id: str = Field(min_length=1)
    variable_b: str = Field(min_length=1)
    fragment_b_id: str = Field(min_length=1)
    alignment_type: AlignmentType
    measurement_model_a_ref: str | None = None
    measurement_model_b_ref: str | None = None
    transform_ref: str | None = None
    proxy_evidence_ref: str | None = None
    latent_bridge_hypothesis_ref: LatentBridgeHypothesisRef | None = None
    latent_bridge_ref: str | None = None
    assumptions_introduced: list[str] = Field(default_factory=list)
    reviewer: AlignmentReviewerState = AlignmentReviewerState.AUTOMATED
    metadata_checks: list["VariableMetadataCheck"] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_latent_bridge_invariants(self) -> "VariableAlignmentCertificate":
        if self.alignment_type is AlignmentType.LATENT_BRIDGE:
            if self.latent_bridge_hypothesis_ref is None and not (
                self.latent_bridge_ref and str(self.latent_bridge_ref).strip()
            ):
                raise ValueError(
                    "latent_bridge_hypothesis_ref or latent_bridge_ref must be non-empty "
                    "when alignment_type is LATENT_BRIDGE"
                )
        return self


class VariableMetadataCheck(BaseModel):
    """Variable metadata check public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1)
    left_value: Any = None
    right_value: Any = None
    status: MetadataCheckStatus
    comparator: str = Field(min_length=1)
    note: str | None = None


class AlignmentReport(BaseModel):
    """Aggregate semantic alignment status across stitched SCM fragments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.2", pattern=r"^\d+\.\d+$")
    fragment_ids: list[str] = Field(default_factory=list)
    per_variable_certificates: list[VariableAlignmentCertificate] = Field(default_factory=list)
    overall_status: AlignmentOverallStatus
    review_status: AlignmentReviewStatus = AlignmentReviewStatus.CLEAR
    incompatible_pairs: list[tuple[str, str]] = Field(default_factory=list)
    alignment_assumptions: list[str] = Field(default_factory=list)
    ontology_mismatch_warnings: list[str] = Field(default_factory=list)
    measurement_comparability_grade: MeasurementComparabilityGrade
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _backfill_review_status(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        normalized = dict(payload)
        if "review_status" not in normalized:
            overall_status = str(normalized.get("overall_status", "")).strip().lower()
            normalized["review_status"] = (
                AlignmentReviewStatus.PENDING_REVIEW.value
                if overall_status == AlignmentOverallStatus.PARTIALLY_ALIGNED.value
                else AlignmentReviewStatus.CLEAR.value
            )
        return normalized


def build_alignment_report(
    *,
    fragment_ids: Sequence[str],
    certificates: Sequence[VariableAlignmentCertificate],
    ontology_mismatch_warnings: Sequence[str] | None = None,
    disconnected_fragment_ids: Sequence[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AlignmentReport:
    """Build alignment report."""
    normalized_fragment_ids = _dedupe_strings(fragment_ids)
    normalized_disconnected_ids = _dedupe_strings(disconnected_fragment_ids or [])
    alignment_assumptions: list[str] = []
    incompatible_pairs: list[tuple[str, str]] = []
    metadata_warnings: list[str] = []
    review_status = AlignmentReviewStatus.CLEAR
    grade = MeasurementComparabilityGrade.INSUFFICIENT
    metadata_payload = dict(metadata or {})

    if certificates:
        certificate_grades = [_grade_for_certificate(certificate) for certificate in certificates]
        grade = min(certificate_grades, key=_measurement_grade_rank)

    for certificate in certificates:
        alignment_assumptions.extend(certificate.assumptions_introduced)
        metadata_warnings.extend(
            str(item)
            for item in certificate.metadata.get("metadata_warnings", [])
            if str(item).strip()
        )
        if certificate.alignment_type is AlignmentType.INCOMPATIBLE:
            incompatible_pairs.append(
                (
                    f"{certificate.fragment_a_id}:{certificate.variable_a}",
                    f"{certificate.fragment_b_id}:{certificate.variable_b}",
                )
            )

        if certificate.reviewer is AlignmentReviewerState.PENDING_REVIEW:
            review_status = AlignmentReviewStatus.PENDING_REVIEW

    if incompatible_pairs or normalized_disconnected_ids:
        overall_status = AlignmentOverallStatus.INCOMPATIBLE
    elif not certificates:
        overall_status = (
            AlignmentOverallStatus.ALIGNED
            if len(normalized_fragment_ids) <= 1
            else AlignmentOverallStatus.INCOMPATIBLE
        )
    elif review_status is AlignmentReviewStatus.PENDING_REVIEW:
        overall_status = AlignmentOverallStatus.PARTIALLY_ALIGNED
    else:
        overall_status = AlignmentOverallStatus.ALIGNED

    return AlignmentReport(
        fragment_ids=normalized_fragment_ids,
        per_variable_certificates=list(certificates),
        overall_status=overall_status,
        review_status=review_status,
        incompatible_pairs=_dedupe_pairs(incompatible_pairs),
        alignment_assumptions=_dedupe_strings(alignment_assumptions),
        ontology_mismatch_warnings=_dedupe_strings(ontology_mismatch_warnings or []),
        measurement_comparability_grade=grade,
        metadata={
            **metadata_payload,
            "disconnected_fragment_ids": normalized_disconnected_ids,
            "metadata_warnings": _dedupe_strings(metadata_warnings),
        },
    )


def verify_fragment_alignment(
    fragment_a: SCMFragment,
    fragment_b: SCMFragment,
    *,
    config: AlignmentVerificationConfig | None = None,
    ontology: Sequence[Any] | None = None,
    artifact_store: ArtifactStore | None = None,
) -> tuple[AlignmentReport, InterfaceMapping]:
    """Verify fragment alignment helper."""
    return _verify_fragment_bundle_alignment_impl(
        [fragment_a, fragment_b],
        config=config,
        ontology=ontology,
        artifact_store=artifact_store,
        stitch_pairs=[(fragment_a.fragment_id, fragment_b.fragment_id)],
        topology_mode="direct",
        preserve_fragment_order=True,
    )


def verify_fragment_bundle_alignment(
    fragments: Sequence[SCMFragment],
    *,
    config: AlignmentVerificationConfig | None = None,
    ontology: Sequence[Any] | None = None,
    stitch_pairs: Sequence[tuple[str, str]] | None = None,
    artifact_store: ArtifactStore | None = None,
) -> tuple[AlignmentReport, InterfaceMapping]:
    """Verify fragment bundle alignment helper."""
    return _verify_fragment_bundle_alignment_impl(
        fragments,
        config=config,
        ontology=ontology,
        artifact_store=artifact_store,
        stitch_pairs=stitch_pairs,
        topology_mode="auto",
    )


@dataclass(frozen=True)
class _FragmentPairSummary:
    fragment_pair: tuple[str, str]
    candidates: tuple["_PairCandidate", ...]
    positive_candidates: tuple["_PairCandidate", ...]
    eligible_variables_a: tuple[str, ...]
    eligible_variables_b: tuple[str, ...]
    weight: tuple[int, int, float]


def _verify_fragment_bundle_alignment_impl(
    fragments: Sequence[SCMFragment],
    *,
    config: AlignmentVerificationConfig | None,
    ontology: Sequence[Any] | None,
    artifact_store: ArtifactStore | None,
    stitch_pairs: Sequence[tuple[str, str]] | None,
    topology_mode: Literal["auto", "direct"],
    preserve_fragment_order: bool = False,
) -> tuple[AlignmentReport, InterfaceMapping]:
    verification_config = config or AlignmentVerificationConfig()
    ordered_fragments = (
        list(fragments)
        if preserve_fragment_order
        else sorted(fragments, key=lambda item: item.fragment_id)
    )
    if len({fragment.fragment_id for fragment in ordered_fragments}) != len(ordered_fragments):
        raise ValueError("fragments must have unique fragment_id values")

    fragment_ids = [fragment.fragment_id for fragment in ordered_fragments]
    if len(ordered_fragments) < 2:
        return (
            build_alignment_report(fragment_ids=fragment_ids, certificates=[]),
            InterfaceMapping(fragment_ids=fragment_ids),
        )

    seed_alignments = _load_seed_alignments(verification_config)
    schemas = {
        fragment.fragment_id: fragment.to_interface_schema().variables for fragment in ordered_fragments
    }
    fragments_by_id = {fragment.fragment_id: fragment for fragment in ordered_fragments}
    pair_summaries: dict[tuple[str, str], _FragmentPairSummary] = {}
    for idx, fragment_a in enumerate(ordered_fragments):
        for fragment_b in ordered_fragments[idx + 1 :]:
            pair_key = _fragment_pair_key(fragment_a.fragment_id, fragment_b.fragment_id)
            pair_summaries[pair_key] = _build_fragment_pair_summary(
                fragment_a=fragment_a,
                fragment_b=fragment_b,
                schema_a=schemas[fragment_a.fragment_id],
                schema_b=schemas[fragment_b.fragment_id],
                config=verification_config,
                artifact_store=artifact_store,
                seed_alignments=seed_alignments,
            )

    selected_pairs, disconnected_fragment_ids, disconnected_components, resolved_topology_mode = (
        _resolve_bundle_stitch_topology(
            fragment_ids=fragment_ids,
            pair_summaries=pair_summaries,
            stitch_pairs=stitch_pairs,
            topology_mode=topology_mode,
        )
    )

    certificates: list[VariableAlignmentCertificate] = []
    ontology_warnings: list[str] = []
    degraded_outcomes: list[AlignmentDegradedOutcome] = []
    stitched_surface: dict[str, set[str]] = {fragment_id: set() for fragment_id in fragment_ids}
    for fragment_a_id, fragment_b_id in selected_pairs:
        pair_key = _fragment_pair_key(fragment_a_id, fragment_b_id)
        summary = pair_summaries.get(pair_key)
        if summary is None:
            continue
        pair_certificates = _select_pair_certificates(
            summary.candidates,
            schema_a=schemas[fragment_a_id],
            schema_b=schemas[fragment_b_id],
            coverage_variables_a=summary.eligible_variables_a,
            coverage_variables_b=summary.eligible_variables_b,
            include_negative_coverage=True,
        )
        certificates.extend(pair_certificates)
        ontology_result = _build_ontology_warnings(
            fragment_a=fragments_by_id[fragment_a_id],
            fragment_b=fragments_by_id[fragment_b_id],
            certificates=pair_certificates,
            ontology=ontology or [],
        )
        ontology_warnings.extend(ontology_result.warnings)
        degraded_outcomes.extend(ontology_result.degraded_outcomes)
        stitched_surface[fragment_a_id].update(summary.eligible_variables_a)
        stitched_surface[fragment_b_id].update(summary.eligible_variables_b)

    boundary_interface_variables = _boundary_interface_variables(
        ordered_fragments,
        stitched_surface=stitched_surface,
    )
    report = build_alignment_report(
        fragment_ids=fragment_ids,
        certificates=_dedupe_certificates(certificates),
        ontology_mismatch_warnings=ontology_warnings,
        disconnected_fragment_ids=disconnected_fragment_ids,
        metadata={
            "selected_stitch_pairs": [list(pair) for pair in selected_pairs],
            "boundary_interface_variables": boundary_interface_variables,
            "disconnected_components": [list(component) for component in disconnected_components],
            "stitch_topology_mode": resolved_topology_mode,
            **(
                {
                    "degraded_outcomes": [
                        outcome.model_dump(mode="json")
                        for outcome in _dedupe_degraded_outcomes(degraded_outcomes)
                    ]
                }
                if degraded_outcomes
                else {}
            ),
        },
    )
    mapping = _build_interface_mapping(
        fragment_ids=fragment_ids,
        schemas=schemas,
        certificates=report.per_variable_certificates,
    )
    return report, mapping


TAU_MIN_LOWER = 0.55
TAU_MIN_UPPER = 0.95


class _PairCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    variable_a: InterfaceVariableSchema
    variable_b: InterfaceVariableSchema
    certificate: VariableAlignmentCertificate
    plausible: bool = False
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    priority: int = 0


def _load_seed_alignments(config: AlignmentVerificationConfig) -> list[VariableAlignment]:
    path = Path(config.seed_alignments_path) if config.seed_alignments_path else default_seed_alignments_path()
    return load_seed_alignments(path)


def _build_pair_candidates(
    *,
    fragment_a: SCMFragment,
    fragment_b: SCMFragment,
    schema_a: Sequence[InterfaceVariableSchema],
    schema_b: Sequence[InterfaceVariableSchema],
    config: AlignmentVerificationConfig,
    artifact_store: ArtifactStore | None,
    seed_alignments: Sequence[VariableAlignment],
) -> list[_PairCandidate]:
    candidates: list[_PairCandidate] = []
    for variable_a in schema_a:
        for variable_b in schema_b:
            if not _roles_are_stitch_compatible(variable_a.role, variable_b.role):
                continue
            certificate, plausible, score, priority = _classify_pair(
                fragment_a=fragment_a,
                fragment_b=fragment_b,
                variable_a=variable_a,
                variable_b=variable_b,
                config=config,
                artifact_store=artifact_store,
                seed_alignments=seed_alignments,
            )
            candidates.append(
                _PairCandidate(
                    variable_a=variable_a,
                    variable_b=variable_b,
                    certificate=certificate,
                    plausible=plausible,
                    score=score,
                    priority=priority,
                )
            )
    candidates.sort(
        key=lambda item: (
            -item.priority,
            -item.score,
            item.variable_a.variable_name,
            item.variable_b.variable_name,
        )
    )
    return candidates


_DEFAULT_METADATA_KEYS: tuple[str, ...] = (
    "population",
    "subgroup",
    "geography",
    "time_window",
    "aggregation",
    "measurement_basis",
)
_HARD_METADATA_COMPARATORS = frozenset({"normalized_equality", "time_window"})


def _compare_variable_metadata(
    *,
    variable_a: InterfaceVariableSchema,
    variable_b: InterfaceVariableSchema,
    config: AlignmentVerificationConfig,
) -> tuple[list[VariableMetadataCheck], list[str], list[str]]:
    left_metadata = {
        str(key).strip(): value
        for key, value in dict(variable_a.metadata).items()
        if str(key).strip()
    }
    right_metadata = {
        str(key).strip(): value
        for key, value in dict(variable_b.metadata).items()
        if str(key).strip()
    }
    ordered_keys = [
        key
        for key in _DEFAULT_METADATA_KEYS
        if key in left_metadata or key in right_metadata
    ]
    ordered_keys.extend(
        sorted((set(left_metadata) | set(right_metadata)) - set(_DEFAULT_METADATA_KEYS))
    )

    checks: list[VariableMetadataCheck] = []
    warning_keys: list[str] = []
    hard_mismatch_keys: list[str] = []
    for key in ordered_keys:
        comparator = config.metadata_comparator_overrides.get(key) or _default_metadata_comparator(key)
        check = _run_metadata_comparator(
            key=key,
            left_value=left_metadata.get(key),
            right_value=right_metadata.get(key),
            comparator=comparator,
        )
        checks.append(check)
        if check.status is MetadataCheckStatus.WARNING:
            warning_keys.append(key)
        if (
            check.status is MetadataCheckStatus.MISMATCH
            and check.comparator in _HARD_METADATA_COMPARATORS
        ):
            hard_mismatch_keys.append(key)
    return checks, warning_keys, hard_mismatch_keys


def _default_metadata_comparator(key: str) -> str:
    if key in {"population", "subgroup", "aggregation", "measurement_basis"}:
        return "normalized_equality"
    if key == "geography":
        return "geography_warning"
    if key == "time_window":
        return "time_window"
    return "unknown_key"


def _run_metadata_comparator(
    *,
    key: str,
    left_value: Any,
    right_value: Any,
    comparator: str,
) -> VariableMetadataCheck:
    if comparator == "normalized_equality":
        return _normalized_equality_check(key=key, left_value=left_value, right_value=right_value)
    if comparator == "geography_warning":
        return _geography_warning_check(key=key, left_value=left_value, right_value=right_value)
    if comparator == "time_window":
        return _time_window_check(key=key, left_value=left_value, right_value=right_value)
    return VariableMetadataCheck(
        key=key,
        left_value=left_value,
        right_value=right_value,
        status=MetadataCheckStatus.UNKNOWN,
        comparator=comparator,
        note="no registered comparator",
    )


def _normalized_equality_check(
    *,
    key: str,
    left_value: Any,
    right_value: Any,
) -> VariableMetadataCheck:
    if left_value is None and right_value is None:
        return VariableMetadataCheck(
            key=key,
            left_value=left_value,
            right_value=right_value,
            status=MetadataCheckStatus.UNKNOWN,
            comparator="normalized_equality",
            note="metadata missing on both sides",
        )
    if left_value is None or right_value is None:
        return VariableMetadataCheck(
            key=key,
            left_value=left_value,
            right_value=right_value,
            status=MetadataCheckStatus.UNKNOWN,
            comparator="normalized_equality",
            note="metadata missing on one side",
        )
    status = (
        MetadataCheckStatus.MATCH
        if _normalize_metadata_value(left_value) == _normalize_metadata_value(right_value)
        else MetadataCheckStatus.MISMATCH
    )
    return VariableMetadataCheck(
        key=key,
        left_value=left_value,
        right_value=right_value,
        status=status,
        comparator="normalized_equality",
        note=None if status is MetadataCheckStatus.MATCH else "normalized values differ",
    )


def _geography_warning_check(
    *,
    key: str,
    left_value: Any,
    right_value: Any,
) -> VariableMetadataCheck:
    if left_value is None and right_value is None:
        return VariableMetadataCheck(
            key=key,
            left_value=left_value,
            right_value=right_value,
            status=MetadataCheckStatus.UNKNOWN,
            comparator="geography_warning",
            note="metadata missing on both sides",
        )
    if left_value is None or right_value is None:
        return VariableMetadataCheck(
            key=key,
            left_value=left_value,
            right_value=right_value,
            status=MetadataCheckStatus.UNKNOWN,
            comparator="geography_warning",
            note="metadata missing on one side",
        )
    normalized_left = _normalize_metadata_value(left_value)
    normalized_right = _normalize_metadata_value(right_value)
    status = (
        MetadataCheckStatus.MATCH
        if normalized_left == normalized_right
        else MetadataCheckStatus.WARNING
    )
    return VariableMetadataCheck(
        key=key,
        left_value=left_value,
        right_value=right_value,
        status=status,
        comparator="geography_warning",
        note=None if status is MetadataCheckStatus.MATCH else "geography differs",
    )


def _time_window_check(
    *,
    key: str,
    left_value: Any,
    right_value: Any,
) -> VariableMetadataCheck:
    if left_value is None and right_value is None:
        return VariableMetadataCheck(
            key=key,
            left_value=left_value,
            right_value=right_value,
            status=MetadataCheckStatus.UNKNOWN,
            comparator="time_window",
            note="metadata missing on both sides",
        )
    if left_value is None or right_value is None:
        return VariableMetadataCheck(
            key=key,
            left_value=left_value,
            right_value=right_value,
            status=MetadataCheckStatus.UNKNOWN,
            comparator="time_window",
            note="metadata missing on one side",
        )
    if _normalize_metadata_value(left_value) == _normalize_metadata_value(right_value):
        return VariableMetadataCheck(
            key=key,
            left_value=left_value,
            right_value=right_value,
            status=MetadataCheckStatus.MATCH,
            comparator="time_window",
        )
    left_bounds = _parse_time_window_bounds(left_value)
    right_bounds = _parse_time_window_bounds(right_value)
    if left_bounds is None or right_bounds is None:
        return VariableMetadataCheck(
            key=key,
            left_value=left_value,
            right_value=right_value,
            status=MetadataCheckStatus.UNKNOWN,
            comparator="time_window",
            note="time window format is not parseable",
        )
    left_start, left_end = left_bounds
    right_start, right_end = right_bounds
    overlaps = left_start <= right_end and right_start <= left_end
    status = MetadataCheckStatus.WARNING if overlaps else MetadataCheckStatus.MISMATCH
    note = "time windows overlap or contain each other" if overlaps else "time windows are disjoint"
    return VariableMetadataCheck(
        key=key,
        left_value=left_value,
        right_value=right_value,
        status=status,
        comparator="time_window",
        note=note,
    )


def _normalize_metadata_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.strip().lower().split())
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        normalized = {
            str(key).strip().lower(): _normalize_metadata_value(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
        return json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    if isinstance(value, (list, tuple, set)):
        normalized = [_normalize_metadata_value(item) for item in value]
        return json.dumps(normalized, separators=(",", ":"))
    return str(value).strip().lower()


def _parse_time_window_bounds(value: Any) -> tuple[datetime, datetime] | None:
    if isinstance(value, dict):
        start = value.get("start", value.get("from"))
        end = value.get("end", value.get("to"))
        start_dt = _parse_datetime_like(start)
        end_dt = _parse_datetime_like(end)
        if start_dt is not None and end_dt is not None and start_dt <= end_dt:
            return start_dt, end_dt
        return None
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return None
        if "/" in token:
            left, right = token.split("/", 1)
            left_dt = _parse_datetime_like(left)
            right_dt = _parse_datetime_like(right)
            if left_dt is not None and right_dt is not None and left_dt <= right_dt:
                return left_dt, right_dt
            return None
        parsed = _parse_datetime_like(token)
        if parsed is None:
            return None
        return parsed, parsed
    return None


def _parse_datetime_like(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    token = str(value or "").strip()
    if not token:
        return None
    if len(token) == 4 and token.isdigit():
        return datetime(int(token), 1, 1)
    for parser in (datetime.fromisoformat, _parse_iso_date):
        try:
            parsed = parser(token.replace("Z", "+00:00"))
        except ValueError:
            continue
        if isinstance(parsed, datetime):
            return parsed
        if isinstance(parsed, date):
            return datetime.combine(parsed, datetime.min.time())
    return None


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def _coerce_latent_bridge_hypothesis_ref(
    payload: Any,
) -> LatentBridgeHypothesisRef | None:
    if payload in (None, ""):
        return None
    candidate = payload
    if isinstance(candidate, LatentBridgeHypothesisRef):
        return candidate
    if hasattr(candidate, "model_dump") and not isinstance(candidate, dict):
        candidate = candidate.model_dump(mode="json")
    try:
        return LatentBridgeHypothesisRef.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def _load_governed_latent_bridge_hypothesis(
    *,
    artifact_store: ArtifactStore | None,
    hypothesis_ref: LatentBridgeHypothesisRef | None,
) -> LatentBridgeHypothesis | None:
    if artifact_store is None or hypothesis_ref is None:
        return None
    try:
        hypothesis = load_latent_bridge_hypothesis(artifact_store, hypothesis_ref)
    except Exception:
        return None
    return materialize_latent_bridge_governance(hypothesis)


def _legacy_latent_bridge_governance_metadata(
    *,
    latent_bridge_ref: str | None,
    extra_blockers: Sequence[str] = (),
) -> dict[str, Any]:
    blockers = _dedupe_strings(
        [
            "latent_promotion_evidence_missing",
            "latent_artifact_proof_only",
            *(
                ["latent_bridge_legacy_ref_only"]
                if latent_bridge_ref
                else []
            ),
            *list(extra_blockers),
        ]
    )
    return {
        "active": True,
        "valid": False,
        "claim_mode": "proof_only",
        "degradation_mode": "research_only",
        "readiness_cap": "proof_only",
        "promotion_allowed": False,
        "human_gate_required": True,
        "not_for_decision_support": True,
        "missing_requirements": list(blockers),
        "surfaced_assumptions": [],
        "surfaced_falsification_tests": [],
        "no_promotion_reasons": list(blockers),
        "promotion_verdict": None,
        "metadata": {
            "latent_artifact_kind": "latent_bridge",
            "latent_artifact_blockers": list(blockers),
            "legacy_latent_bridge_ref": latent_bridge_ref,
        },
    }


def _latent_bridge_governance_metadata(
    hypothesis: LatentBridgeHypothesis | None,
    *,
    fallback_legacy_ref: str | None = None,
    extra_blockers: Sequence[str] = (),
) -> dict[str, Any]:
    if hypothesis is None:
        return _legacy_latent_bridge_governance_metadata(
            latent_bridge_ref=fallback_legacy_ref,
            extra_blockers=extra_blockers,
        )
    assessment = assess_latent_bridge_governance(hypothesis)
    if assessment is None:
        return _legacy_latent_bridge_governance_metadata(
            latent_bridge_ref=fallback_legacy_ref,
            extra_blockers=extra_blockers,
        )
    metadata = dict(assessment.model_dump(mode="json"))
    metadata["metadata"] = dict(metadata.get("metadata", {}))
    metadata["metadata"]["latent_artifact_blockers"] = _dedupe_strings(
        [
            *(
                metadata["metadata"].get("latent_artifact_blockers", [])
                if isinstance(metadata.get("metadata"), dict)
                else []
            ),
            *list(extra_blockers),
        ]
    )
    if fallback_legacy_ref:
        metadata["metadata"]["legacy_latent_bridge_ref"] = fallback_legacy_ref
    return metadata


def _classify_pair(
    *,
    fragment_a: SCMFragment,
    fragment_b: SCMFragment,
    variable_a: InterfaceVariableSchema,
    variable_b: InterfaceVariableSchema,
    config: AlignmentVerificationConfig,
    artifact_store: ArtifactStore | None,
    seed_alignments: Sequence[VariableAlignment],
) -> tuple[VariableAlignmentCertificate, bool, float, int]:
    pair_score = score_variable_pair(
        left_name=variable_a.variable_name,
        right_name=variable_b.variable_name,
        left_definition=variable_a.definition,
        right_definition=variable_b.definition,
        left_unit=variable_a.unit,
        right_unit=variable_b.unit,
        seed_alignments=seed_alignments,
    )
    pair_key = _pair_key(
        fragment_a.fragment_id,
        variable_a.variable_name,
        fragment_b.fragment_id,
        variable_b.variable_name,
    )
    explicit_latent_bridge_payload = config.explicit_latent_bridges.get(pair_key)
    latent_bridge_ref: str | None = None
    latent_bridge_hypothesis_ref = _coerce_latent_bridge_hypothesis_ref(
        explicit_latent_bridge_payload
    )
    explicit_latent_bridge_blockers: list[str] = []
    if latent_bridge_hypothesis_ref is None and explicit_latent_bridge_payload not in (None, ""):
        token = str(explicit_latent_bridge_payload).strip()
        if token:
            latent_bridge_ref = token
        else:
            explicit_latent_bridge_blockers.append("latent_bridge_ref_unresolvable")
    explicit_latent_bridge_hypothesis = _load_governed_latent_bridge_hypothesis(
        artifact_store=artifact_store,
        hypothesis_ref=latent_bridge_hypothesis_ref,
    )
    if latent_bridge_hypothesis_ref is not None and explicit_latent_bridge_hypothesis is None:
        explicit_latent_bridge_blockers.append("latent_bridge_hypothesis_unresolved")
    measurement_models_compatible = _measurement_models_compatible(
        variable_a.measurement_model_ref,
        variable_b.measurement_model_ref,
    )
    metadata_checks, metadata_warning_keys, metadata_hard_mismatch_keys = _compare_variable_metadata(
        variable_a=variable_a,
        variable_b=variable_b,
        config=config,
    )
    auto_latent_bridge_hypothesis: LatentBridgeHypothesis | None = None
    if (
        latent_bridge_ref is None
        and latent_bridge_hypothesis_ref is None
        and pair_key in config.latent_bridge_evidence
        and config.latent_bridge_policy.enable_auto_latent_bridge
    ):
        evidence = config.latent_bridge_evidence[pair_key]
        if metadata_hard_mismatch_keys:
            evidence = evidence.model_copy(update={"hard_metadata_mismatch": True})
        auto_latent_bridge_hypothesis = synthesize_latent_bridge(
            pair_key=pair_key,
            evidence=evidence,
            policy=config.latent_bridge_policy,
        )
    transform_ref = _known_transform_ref(variable_a.unit, variable_b.unit, config)
    definitions_present = bool(str(variable_a.definition).strip() and str(variable_b.definition).strip())
    definition_overlap_sufficient = pair_score.definition_score >= config.min_definition_overlap
    compatible_definition_evidence = bool(definition_overlap_sufficient or not definitions_present)
    units_present = bool(str(variable_a.unit or "").strip() and str(variable_b.unit or "").strip())
    units_conflict = bool(
        units_present
        and transform_ref is None
        and pair_score.unit_compatibility_score < 0.5
    )
    measurement_conflict = not measurement_models_compatible
    canonical_evidence = bool(pair_score.shared_canonical_vars) or pair_score.seed_support_score > 0.0
    semantic_construct_evidence = bool(
        not pair_score.exact_name_match
        and pair_score.semantic_score >= config.min_exact_semantic_score
    )
    construct_evidence = bool(
        canonical_evidence
        or definition_overlap_sufficient
        or semantic_construct_evidence
    )
    hard_conflict_reasons: list[str] = []
    if pair_score.exact_name_match and definitions_present and not definition_overlap_sufficient:
        hard_conflict_reasons.append("name_match_with_definition_conflict")
    if units_conflict:
        hard_conflict_reasons.append("unit_conflict")
    if measurement_conflict:
        hard_conflict_reasons.append("measurement_model_conflict")
    if metadata_hard_mismatch_keys:
        hard_conflict_reasons.extend(
            f"metadata_mismatch:{key}" for key in metadata_hard_mismatch_keys
        )
    if pair_score.exact_name_match and not construct_evidence and not transform_ref:
        hard_conflict_reasons.append("name_only_match_without_supporting_evidence")
    hard_conflict = bool(
        metadata_hard_mismatch_keys
        or (
            pair_score.exact_name_match
            and hard_conflict_reasons
            and not canonical_evidence
            and not latent_bridge_ref
            and latent_bridge_hypothesis_ref is None
        )
    )
    exact_match = bool(
        pair_score.exact_name_match
        and _definitions_compatible(pair_score.definition_score, variable_a, variable_b)
        and pair_score.unit_compatibility_score >= 0.5
        and measurement_models_compatible
    )
    same_construct = bool(
        canonical_evidence
        or semantic_construct_evidence
        or (
            pair_score.exact_name_match
            and compatible_definition_evidence
        )
    )
    scale_link_supported = bool(
        transform_ref
        and same_construct
        and _definitions_compatible(pair_score.definition_score, variable_a, variable_b)
        and measurement_models_compatible
    )
    proxy_supported = bool(
        not hard_conflict
        and construct_evidence
        and measurement_models_compatible
        and (
            pair_score.overall_score >= config.min_proxy_score
            or canonical_evidence
            or semantic_construct_evidence
            or (
                definition_overlap_sufficient
                and pair_score.semantic_score >= 0.35
            )
        )
    )
    plausible = bool(
        not hard_conflict
        and (
            latent_bridge_ref
            or latent_bridge_hypothesis_ref is not None
            or exact_match
            or scale_link_supported
            or proxy_supported
        )
    )
    reviewer = _reviewer_state_for_pair(
        alignment_type=AlignmentType.EXACT,
        pair_key=pair_key,
        config=config,
    )
    alignment_type = AlignmentType.INCOMPATIBLE
    proxy_ref: str | None = None
    assumptions: list[str] = []
    metadata = {
        "score": pair_score.model_dump(mode="json"),
        "measurement_models_compatible": measurement_models_compatible,
        "pair_key": pair_key,
        "construct_evidence": construct_evidence,
        "hard_conflict": hard_conflict,
        "hard_conflict_reasons": hard_conflict_reasons,
        "metadata_warning_keys": metadata_warning_keys,
        "metadata_hard_mismatch_keys": metadata_hard_mismatch_keys,
        "metadata_warnings": [
            f"{key}: {check.note or 'warning'}"
            for key, check in (
                (check.key, check)
                for check in metadata_checks
                if check.status is MetadataCheckStatus.WARNING
            )
        ],
    }
    if auto_latent_bridge_hypothesis is not None:
        metadata["latent_bridge_status_snapshot"] = auto_latent_bridge_hypothesis.model_dump(
            mode="json"
        )
    auto_latent_bridge_hypothesis_ref: LatentBridgeHypothesisRef | None = None
    if (
        auto_latent_bridge_hypothesis is not None
        and auto_latent_bridge_hypothesis.status is LatentBridgeStatus.PROPOSED
        and not hard_conflict
    ):
        if artifact_store is None:
            raise ValueError(
                "artifact_store is required to persist automatic latent bridge hypotheses"
            )
        auto_latent_bridge_hypothesis = materialize_latent_bridge_governance(
            auto_latent_bridge_hypothesis
        )
        auto_latent_bridge_hypothesis_ref = persist_latent_bridge_hypothesis(
            artifact_store,
            auto_latent_bridge_hypothesis,
        )
        metadata["latent_bridge_status_snapshot"] = auto_latent_bridge_hypothesis.model_dump(
            mode="json"
        )
        metadata["latent_bridge_hypothesis_ref"] = auto_latent_bridge_hypothesis_ref.model_dump(
            mode="json"
        )

    resolved_latent_bridge_hypothesis = (
        auto_latent_bridge_hypothesis
        if auto_latent_bridge_hypothesis_ref is not None
        else explicit_latent_bridge_hypothesis
    )
    if latent_bridge_hypothesis_ref is not None:
        metadata["latent_bridge_hypothesis_ref"] = latent_bridge_hypothesis_ref.model_dump(
            mode="json"
        )
    if explicit_latent_bridge_hypothesis is not None:
        metadata["latent_bridge_status_snapshot"] = explicit_latent_bridge_hypothesis.model_dump(
            mode="json"
        )
    if latent_bridge_ref:
        metadata["legacy_latent_bridge_ref"] = latent_bridge_ref
    if explicit_latent_bridge_blockers:
        metadata["latent_bridge_resolution_blockers"] = list(explicit_latent_bridge_blockers)
    metadata["latent_bridge_governance"] = _latent_bridge_governance_metadata(
        resolved_latent_bridge_hypothesis,
        fallback_legacy_ref=latent_bridge_ref,
        extra_blockers=explicit_latent_bridge_blockers,
    )

    if hard_conflict:
        reviewer = _reviewer_state_for_pair(
            alignment_type=AlignmentType.INCOMPATIBLE,
            pair_key=pair_key,
            config=config,
        )
        priority = 0
    elif latent_bridge_ref:
        alignment_type = AlignmentType.LATENT_BRIDGE
        reviewer = _reviewer_state_for_pair(
            alignment_type=alignment_type,
            pair_key=pair_key,
            config=config,
        )
        assumptions.append("latent_bridge_evidence_required")
        priority = 1
    elif latent_bridge_hypothesis_ref is not None and not hard_conflict:
        alignment_type = AlignmentType.LATENT_BRIDGE
        reviewer = _reviewer_state_for_pair(
            alignment_type=alignment_type,
            pair_key=pair_key,
            config=config,
        )
        assumptions.append("latent_bridge_evidence_required")
        priority = 1
    elif (
        auto_latent_bridge_hypothesis_ref is not None
        and auto_latent_bridge_hypothesis is not None
    ):
        alignment_type = AlignmentType.LATENT_BRIDGE
        latent_bridge_hypothesis_ref = auto_latent_bridge_hypothesis_ref
        reviewer = _reviewer_state_for_pair(
            alignment_type=alignment_type,
            pair_key=pair_key,
            config=config,
        )
        assumptions.append(
            f"latent_bridge:auto:{auto_latent_bridge_hypothesis.synthesis_mode.value}"
        )
        priority = 1
    elif exact_match:
        alignment_type = AlignmentType.EXACT
        reviewer = _reviewer_state_for_pair(
            alignment_type=alignment_type,
            pair_key=pair_key,
            config=config,
        )
        priority = 4
    elif scale_link_supported:
        alignment_type = AlignmentType.SCALE_LINKED
        reviewer = _reviewer_state_for_pair(
            alignment_type=alignment_type,
            pair_key=pair_key,
            config=config,
        )
        assumptions.append(f"known_unit_transform:{_unit_pair_key(variable_a.unit, variable_b.unit)}")
        priority = 3
    elif proxy_supported:
        alignment_type = AlignmentType.PROXY
        reviewer = _reviewer_state_for_pair(
            alignment_type=alignment_type,
            pair_key=pair_key,
            config=config,
        )
        assumptions.append("proxy_semantic_alignment")
        if pair_score.shared_canonical_vars:
            proxy_ref = f"seed_alignment:{pair_score.shared_canonical_vars[0]}"
        else:
            proxy_ref = "heuristic:semantic_alignment"
        priority = 2
    else:
        reviewer = _reviewer_state_for_pair(
            alignment_type=AlignmentType.INCOMPATIBLE,
            pair_key=pair_key,
            config=config,
        )
        priority = 0

    certificate = VariableAlignmentCertificate(
        variable_a=variable_a.variable_name,
        fragment_a_id=fragment_a.fragment_id,
        variable_b=variable_b.variable_name,
        fragment_b_id=fragment_b.fragment_id,
        alignment_type=alignment_type,
        measurement_model_a_ref=variable_a.measurement_model_ref,
        measurement_model_b_ref=variable_b.measurement_model_ref,
        transform_ref=transform_ref if alignment_type is AlignmentType.SCALE_LINKED else None,
        proxy_evidence_ref=proxy_ref if alignment_type is AlignmentType.PROXY else None,
        latent_bridge_hypothesis_ref=(
            latent_bridge_hypothesis_ref
            if alignment_type is AlignmentType.LATENT_BRIDGE
            else None
        ),
        latent_bridge_ref=latent_bridge_ref if alignment_type is AlignmentType.LATENT_BRIDGE else None,
        assumptions_introduced=_dedupe_strings(assumptions),
        reviewer=reviewer,
        metadata_checks=metadata_checks,
        metadata=metadata,
    )
    return certificate, plausible, pair_score.overall_score, priority


def _select_pair_certificates(
    candidates: Sequence[_PairCandidate],
    *,
    schema_a: Sequence[InterfaceVariableSchema],
    schema_b: Sequence[InterfaceVariableSchema],
    coverage_variables_a: Sequence[str] | None = None,
    coverage_variables_b: Sequence[str] | None = None,
    include_negative_coverage: bool = True,
) -> list[VariableAlignmentCertificate]:
    selected = _select_positive_pair_candidates(candidates)
    if not include_negative_coverage:
        return [
            candidate.certificate
            for candidate in sorted(
                selected,
                key=lambda item: (
                    item.variable_a.variable_name,
                    item.variable_b.variable_name,
                ),
            )
        ]

    used_a = {candidate.variable_a.variable_name for candidate in selected}
    used_b = {candidate.variable_b.variable_name for candidate in selected}

    by_a: dict[str, list[_PairCandidate]] = {}
    by_b: dict[str, list[_PairCandidate]] = {}
    for candidate in candidates:
        by_a.setdefault(candidate.variable_a.variable_name, []).append(candidate)
        by_b.setdefault(candidate.variable_b.variable_name, []).append(candidate)

    selected_pairs = {
        (
            candidate.variable_a.variable_name,
            candidate.variable_b.variable_name,
        )
        for candidate in selected
    }
    all_a = set(coverage_variables_a or _candidate_variable_names(candidates, side="a"))
    all_b = set(coverage_variables_b or _candidate_variable_names(candidates, side="b"))
    uncovered_a = sorted(all_a - used_a)
    uncovered_b = sorted(all_b - used_b)

    for variable_a in uncovered_a:
        candidate = _best_coverage_candidate(
            by_a.get(variable_a, ()),
            selected_pairs=selected_pairs,
            preferred_uncovered={key for key in uncovered_b if key not in used_b},
            opposite_attr="variable_b",
        )
        if candidate is None:
            continue
        selected.append(candidate)
        selected_pairs.add((candidate.variable_a.variable_name, candidate.variable_b.variable_name))
        used_a.add(candidate.variable_a.variable_name)
        used_b.add(candidate.variable_b.variable_name)

    for variable_b in sorted(all_b - used_b):
        candidate = _best_coverage_candidate(
            by_b.get(variable_b, ()),
            selected_pairs=selected_pairs,
            preferred_uncovered={key for key in sorted(all_a - used_a)},
            opposite_attr="variable_a",
        )
        if candidate is None:
            continue
        selected.append(candidate)
        selected_pairs.add((candidate.variable_a.variable_name, candidate.variable_b.variable_name))
        used_a.add(candidate.variable_a.variable_name)
        used_b.add(candidate.variable_b.variable_name)

    certificates = [
        candidate.certificate
        if candidate.certificate.alignment_type is not AlignmentType.INCOMPATIBLE
        else _coverage_incompatible_certificate(
            candidate,
            coverage_reason="unmatched_exposed_interface",
        )
        for candidate in selected
    ]
    certificates.sort(
        key=lambda item: (
            item.fragment_a_id,
            item.variable_a,
            item.fragment_b_id,
            item.variable_b,
        )
    )
    return certificates


def _best_coverage_candidate(
    candidates: Sequence[_PairCandidate],
    *,
    selected_pairs: set[tuple[str, str]],
    preferred_uncovered: set[str],
    opposite_attr: Literal["variable_a", "variable_b"],
) -> _PairCandidate | None:
    ranked = sorted(
        candidates,
        key=lambda item: (
            getattr(item, opposite_attr).variable_name not in preferred_uncovered,
            -item.score,
            -item.priority,
            item.certificate.alignment_type.value,
            item.variable_a.variable_name,
            item.variable_b.variable_name,
        ),
    )
    for candidate in ranked:
        pair_key = (
            candidate.variable_a.variable_name,
            candidate.variable_b.variable_name,
        )
        if pair_key not in selected_pairs:
            return candidate
    return None


def _select_positive_pair_candidates(
    candidates: Sequence[_PairCandidate],
) -> list[_PairCandidate]:
    selected: list[_PairCandidate] = []
    used_a: set[str] = set()
    used_b: set[str] = set()
    for candidate in candidates:
        key_a = candidate.variable_a.variable_name
        key_b = candidate.variable_b.variable_name
        if key_a in used_a or key_b in used_b:
            continue
        if candidate.certificate.alignment_type is AlignmentType.INCOMPATIBLE:
            continue
        selected.append(candidate)
        used_a.add(key_a)
        used_b.add(key_b)
    return selected


def _candidate_variable_names(
    candidates: Sequence[_PairCandidate],
    *,
    side: Literal["a", "b"],
) -> list[str]:
    attr = "variable_a" if side == "a" else "variable_b"
    return sorted(
        {
            getattr(candidate, attr).variable_name
            for candidate in candidates
        }
    )


def _build_fragment_pair_summary(
    *,
    fragment_a: SCMFragment,
    fragment_b: SCMFragment,
    schema_a: Sequence[InterfaceVariableSchema],
    schema_b: Sequence[InterfaceVariableSchema],
    config: AlignmentVerificationConfig,
    artifact_store: ArtifactStore | None,
    seed_alignments: Sequence[VariableAlignment],
) -> _FragmentPairSummary:
    candidates = tuple(
        _build_pair_candidates(
            fragment_a=fragment_a,
            fragment_b=fragment_b,
            schema_a=schema_a,
            schema_b=schema_b,
            config=config,
            artifact_store=artifact_store,
            seed_alignments=seed_alignments,
        )
    )
    positive_candidates = tuple(_select_positive_pair_candidates(candidates))
    return _FragmentPairSummary(
        fragment_pair=_fragment_pair_key(fragment_a.fragment_id, fragment_b.fragment_id),
        candidates=candidates,
        positive_candidates=positive_candidates,
        eligible_variables_a=tuple(_candidate_variable_names(candidates, side="a")),
        eligible_variables_b=tuple(_candidate_variable_names(candidates, side="b")),
        weight=(
            len(positive_candidates),
            sum(candidate.priority for candidate in positive_candidates),
            round(sum(candidate.score for candidate in positive_candidates), 6),
        ),
    )


def _resolve_bundle_stitch_topology(
    *,
    fragment_ids: Sequence[str],
    pair_summaries: dict[tuple[str, str], _FragmentPairSummary],
    stitch_pairs: Sequence[tuple[str, str]] | None,
    topology_mode: Literal["auto", "direct"],
) -> tuple[list[tuple[str, str]], list[str], list[list[str]], str]:
    if topology_mode == "direct":
        selected_pairs = _normalize_stitch_pairs(stitch_pairs or [], fragment_ids)
        disconnected_fragment_ids, disconnected_components = _disconnected_fragment_metadata(
            fragment_ids=fragment_ids,
            selected_pairs=selected_pairs,
            pair_summaries=pair_summaries,
        )
        return selected_pairs, disconnected_fragment_ids, disconnected_components, topology_mode

    explicit_pairs = _normalize_stitch_pairs(stitch_pairs or [], fragment_ids)
    if explicit_pairs:
        disconnected_fragment_ids, disconnected_components = _disconnected_fragment_metadata(
            fragment_ids=fragment_ids,
            selected_pairs=explicit_pairs,
            pair_summaries=pair_summaries,
        )
        return explicit_pairs, disconnected_fragment_ids, disconnected_components, "explicit"

    selected_pairs: list[tuple[str, str]] = []
    parent = {fragment_id: fragment_id for fragment_id in fragment_ids}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> bool:
        root_left = find(left)
        root_right = find(right)
        if root_left == root_right:
            return False
        if root_left <= root_right:
            parent[root_right] = root_left
        else:
            parent[root_left] = root_right
        return True

    ranked_summaries = sorted(
        (
            summary
            for summary in pair_summaries.values()
            if summary.positive_candidates
        ),
        key=lambda summary: (
            -summary.weight[0],
            -summary.weight[1],
            -summary.weight[2],
            summary.fragment_pair[0],
            summary.fragment_pair[1],
        ),
    )
    for summary in ranked_summaries:
        fragment_a_id, fragment_b_id = summary.fragment_pair
        if union(fragment_a_id, fragment_b_id):
            selected_pairs.append(summary.fragment_pair)

    if len(fragment_ids) == 2 and not selected_pairs:
        selected_pairs = [_fragment_pair_key(fragment_ids[0], fragment_ids[1])]

    disconnected_fragment_ids, disconnected_components = _disconnected_fragment_metadata(
        fragment_ids=fragment_ids,
        selected_pairs=selected_pairs,
        pair_summaries=pair_summaries,
    )
    return selected_pairs, disconnected_fragment_ids, disconnected_components, "auto"


def _disconnected_fragment_metadata(
    *,
    fragment_ids: Sequence[str],
    selected_pairs: Sequence[tuple[str, str]],
    pair_summaries: dict[tuple[str, str], _FragmentPairSummary],
) -> tuple[list[str], list[list[str]]]:
    parent = {fragment_id: fragment_id for fragment_id in fragment_ids}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left == root_right:
            return
        if root_left <= root_right:
            parent[root_right] = root_left
        else:
            parent[root_left] = root_right

    positive_selected_pairs = [
        pair
        for pair in selected_pairs
        if pair_summaries.get(pair) is not None and pair_summaries[pair].positive_candidates
    ]
    for fragment_a_id, fragment_b_id in positive_selected_pairs:
        union(fragment_a_id, fragment_b_id)

    components: dict[str, list[str]] = {}
    for fragment_id in fragment_ids:
        components.setdefault(find(fragment_id), []).append(fragment_id)
    disconnected_components = [
        sorted(component)
        for component in sorted(components.values(), key=lambda item: (len(item), item))
        if len(component) >= 1
    ]
    if len(disconnected_components) <= 1:
        return [], disconnected_components
    if not positive_selected_pairs:
        return sorted(fragment_ids), disconnected_components
    anchor_fragment_id = sorted(fragment_ids)[0]
    anchor_component = next(
        (component for component in disconnected_components if anchor_fragment_id in component),
        [],
    )
    disconnected_fragment_ids = sorted(
        {
            fragment_id
            for component in disconnected_components
            if component != anchor_component
            for fragment_id in component
        }
    )
    return disconnected_fragment_ids, disconnected_components


def _normalize_stitch_pairs(
    stitch_pairs: Sequence[tuple[str, str]],
    fragment_ids: Sequence[str],
) -> list[tuple[str, str]]:
    known_fragment_ids = set(fragment_ids)
    normalized: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_left, raw_right in stitch_pairs:
        left = str(raw_left).strip()
        right = str(raw_right).strip()
        if not left or not right or left == right:
            raise ValueError("stitch_pairs must contain distinct non-empty fragment ids")
        if left not in known_fragment_ids or right not in known_fragment_ids:
            raise ValueError("stitch_pairs reference unknown fragment ids")
        pair = _fragment_pair_key(left, right)
        if pair in seen:
            continue
        seen.add(pair)
        normalized.append(pair)
    normalized.sort()
    return normalized


def _fragment_pair_key(left_fragment_id: str, right_fragment_id: str) -> tuple[str, str]:
    left = str(left_fragment_id).strip()
    right = str(right_fragment_id).strip()
    return (left, right) if left <= right else (right, left)


def _roles_are_stitch_compatible(
    left_role: InterfaceRole,
    right_role: InterfaceRole,
) -> bool:
    if left_role is InterfaceRole.SHARED or right_role is InterfaceRole.SHARED:
        return True
    return {left_role, right_role} == {InterfaceRole.INPUT, InterfaceRole.OUTPUT}


def _boundary_interface_variables(
    fragments: Sequence[SCMFragment],
    *,
    stitched_surface: dict[str, set[str]],
) -> dict[str, list[str]]:
    boundary: dict[str, list[str]] = {}
    for fragment in fragments:
        exposed_variables = sorted(set(fragment.exposed_inputs) | set(fragment.exposed_outputs))
        boundary[fragment.fragment_id] = [
            variable_name
            for variable_name in exposed_variables
            if variable_name not in stitched_surface.get(fragment.fragment_id, set())
        ]
    return boundary


def _coverage_incompatible_certificate(
    candidate: _PairCandidate,
    *,
    coverage_reason: str,
) -> VariableAlignmentCertificate:
    metadata = dict(candidate.certificate.metadata)
    metadata.update(
        {
            "coverage_reason": coverage_reason,
            "selected_from_alignment_type": candidate.certificate.alignment_type.value,
            "selected_from_score": candidate.score,
            "selected_from_priority": candidate.priority,
        }
    )
    return candidate.certificate.model_copy(
        update={
            "alignment_type": AlignmentType.INCOMPATIBLE,
            "transform_ref": None,
            "proxy_evidence_ref": None,
            "latent_bridge_hypothesis_ref": None,
            "latent_bridge_ref": None,
            "assumptions_introduced": [],
            "reviewer": AlignmentReviewerState.AUTOMATED,
            "metadata": metadata,
        }
    )


def _build_interface_mapping(
    *,
    fragment_ids: Sequence[str],
    schemas: dict[str, Sequence[InterfaceVariableSchema]],
    certificates: Sequence[VariableAlignmentCertificate],
) -> InterfaceMapping:
    certs = [
        certificate
        for certificate in certificates
        if certificate.alignment_type is not AlignmentType.INCOMPATIBLE
    ]
    if not certs:
        return InterfaceMapping(fragment_ids=_dedupe_strings(fragment_ids))

    binding_details: dict[tuple[str, str], InterfaceVariableSchema] = {}
    for fragment_id, variables in schemas.items():
        for variable in variables:
            binding_details[(fragment_id, variable.variable_name)] = variable

    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def find(item: tuple[str, str]) -> tuple[str, str]:
        parent.setdefault(item, item)
        if parent[item] != item:
            parent[item] = find(parent[item])
        return parent[item]

    def union(left: tuple[str, str], right: tuple[str, str]) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left == root_right:
            return
        if root_left <= root_right:
            parent[root_right] = root_left
        else:
            parent[root_left] = root_right

    for certificate in certs:
        union(
            (certificate.fragment_a_id, certificate.variable_a),
            (certificate.fragment_b_id, certificate.variable_b),
        )

    components: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for certificate in certs:
        for binding in (
            (certificate.fragment_a_id, certificate.variable_a),
            (certificate.fragment_b_id, certificate.variable_b),
        ):
            components.setdefault(find(binding), [])
            if binding not in components[find(binding)]:
                components[find(binding)].append(binding)

    entries: list[InterfaceMappingEntry] = []
    for bindings in sorted(
        (sorted(component) for component in components.values() if len(component) >= 2),
        key=lambda item: item,
    ):
        component_certs = [
            certificate
            for certificate in certs
            if {
                (certificate.fragment_a_id, certificate.variable_a),
                (certificate.fragment_b_id, certificate.variable_b),
            }.issubset(set(bindings))
        ]
        canonical_name = _preferred_component_name(bindings)
        digest = hashlib.sha256(
            "|".join(f"{fragment_id}:{variable_name}" for fragment_id, variable_name in bindings).encode(
                "utf-8"
            )
        ).hexdigest()[:12]
        alignment_type = _component_alignment_type(component_certs)
        reviewer = _component_reviewer(component_certs)
        assumptions = _dedupe_strings(
            [
                assumption
                for certificate in component_certs
                for assumption in certificate.assumptions_introduced
            ]
        )
        entry_metadata: dict[str, Any] = {
            "fragment_ids": sorted({fragment_id for fragment_id, _ in bindings}),
            "pair_count": len(component_certs),
        }
        if alignment_type is AlignmentType.LATENT_BRIDGE:
            entry_metadata.update(_component_latent_bridge_metadata(component_certs))
        entries.append(
            InterfaceMappingEntry(
                interface_id=f"interface::{digest}",
                canonical_node_id=f"stitched::{canonical_name}::{digest}",
                bindings=[
                    InterfaceVariableBinding(
                        fragment_id=fragment_id,
                        variable_name=variable_name,
                        observed=binding_details[(fragment_id, variable_name)].observed,
                        measurement_model_ref=binding_details[(fragment_id, variable_name)].measurement_model_ref,
                        definition=binding_details[(fragment_id, variable_name)].definition,
                        unit=binding_details[(fragment_id, variable_name)].unit,
                        metadata=dict(binding_details[(fragment_id, variable_name)].metadata),
                    )
                    for fragment_id, variable_name in bindings
                ],
                observed=all(binding_details[(fragment_id, variable_name)].observed for fragment_id, variable_name in bindings),
                alignment_type=alignment_type.value,
                reviewer=reviewer.value,
                assumptions_introduced=assumptions,
                metadata=entry_metadata,
            )
        )

    entries.sort(key=lambda item: item.interface_id)
    return InterfaceMapping(fragment_ids=_dedupe_strings(fragment_ids), entries=entries)


def _component_alignment_type(
    certificates: Sequence[VariableAlignmentCertificate],
) -> AlignmentType:
    if any(item.alignment_type is AlignmentType.LATENT_BRIDGE for item in certificates):
        return AlignmentType.LATENT_BRIDGE
    if any(item.alignment_type is AlignmentType.PROXY for item in certificates):
        return AlignmentType.PROXY
    if any(item.alignment_type is AlignmentType.SCALE_LINKED for item in certificates):
        return AlignmentType.SCALE_LINKED
    return AlignmentType.EXACT


def _component_reviewer(
    certificates: Sequence[VariableAlignmentCertificate],
) -> AlignmentReviewerState:
    if any(item.reviewer is AlignmentReviewerState.PENDING_REVIEW for item in certificates):
        return AlignmentReviewerState.PENDING_REVIEW
    if certificates and all(item.reviewer is AlignmentReviewerState.HUMAN_VERIFIED for item in certificates):
        return AlignmentReviewerState.HUMAN_VERIFIED
    return AlignmentReviewerState.AUTOMATED


def _component_latent_bridge_metadata(
    certificates: Sequence[VariableAlignmentCertificate],
) -> dict[str, Any]:
    readiness_caps: list[str] = []
    blockers: list[str] = []
    promotion_allowed = False
    for certificate in certificates:
        governance = certificate.metadata.get("latent_bridge_governance")
        if not isinstance(governance, dict):
            continue
        cap = str(governance.get("readiness_cap", "")).strip().lower()
        if cap:
            readiness_caps.append(cap)
        promotion_allowed = promotion_allowed or bool(governance.get("promotion_allowed", False))
        payload = governance.get("metadata", {})
        if isinstance(payload, dict):
            blockers.extend(
                str(item)
                for item in payload.get("latent_artifact_blockers", [])
                if str(item).strip()
            )
        blockers.extend(
            str(item)
            for item in governance.get("no_promotion_reasons", [])
            if str(item).strip()
        )
    return {
        "latent_bridge_readiness_cap": _minimum_readiness_cap(readiness_caps),
        "latent_bridge_promotion_allowed": promotion_allowed,
        "latent_artifact_blockers": _dedupe_strings(blockers),
    }


def _minimum_readiness_cap(readiness_caps: Sequence[str]) -> str:
    if not readiness_caps:
        return "proof_only"
    rank = {"proof_only": 0, "bounds_ready": 1, "estimation_ready": 2}
    normalized = [str(cap).strip().lower() for cap in readiness_caps if str(cap).strip()]
    if not normalized:
        return "proof_only"
    return min(normalized, key=lambda cap: rank.get(cap, 0))


def _preferred_component_name(bindings: Sequence[tuple[str, str]]) -> str:
    normalized = sorted({_normalize_variable_name(variable_name) for _, variable_name in bindings})
    return normalized[0] if normalized else "interface"


def _known_transform_ref(
    left_unit: str | None,
    right_unit: str | None,
    config: AlignmentVerificationConfig,
) -> str | None:
    key = _unit_pair_key(left_unit, right_unit)
    return config.known_unit_transforms.get(key)


def _unit_pair_key(left_unit: str | None, right_unit: str | None) -> str:
    return f"{_normalize_unit(left_unit)}->{_normalize_unit(right_unit)}"


def _normalize_unit(value: str | None) -> str:
    aliases = {
        "%": "percent",
        "pct": "percent",
        "percentage": "percent",
        "proportion": "ratio",
    }
    token = str(value or "").strip().lower()
    return aliases.get(token, token)


def _definitions_compatible(
    definition_score: float,
    variable_a: InterfaceVariableSchema,
    variable_b: InterfaceVariableSchema,
) -> bool:
    if not str(variable_a.definition).strip() or not str(variable_b.definition).strip():
        return True
    return definition_score >= 0.25


def _measurement_models_compatible(left_ref: str | None, right_ref: str | None) -> bool:
    left = str(left_ref or "").strip()
    right = str(right_ref or "").strip()
    if not left or not right:
        return True
    return left == right


def _reviewer_state_for_pair(
    *,
    alignment_type: AlignmentType,
    pair_key: str,
    config: AlignmentVerificationConfig,
) -> AlignmentReviewerState:
    if pair_key in set(config.human_verified_pairs):
        return AlignmentReviewerState.HUMAN_VERIFIED
    if alignment_type in {AlignmentType.PROXY, AlignmentType.LATENT_BRIDGE}:
        return AlignmentReviewerState.PENDING_REVIEW
    return AlignmentReviewerState.AUTOMATED


def _pair_key(
    fragment_a_id: str,
    variable_a: str,
    fragment_b_id: str,
    variable_b: str,
) -> str:
    ordered = sorted(
        (
            f"{fragment_a_id}:{variable_a}",
            f"{fragment_b_id}:{variable_b}",
        )
    )
    return "|".join(ordered)


def _normalize_variable_name(value: str) -> str:
    token = "".join(ch if ch.isalnum() else "_" for ch in str(value).strip().lower())
    while "__" in token:
        token = token.replace("__", "_")
    return token.strip("_") or "var"


def _dedupe_certificates(
    certificates: Sequence[VariableAlignmentCertificate],
) -> list[VariableAlignmentCertificate]:
    unique: dict[tuple[str, str, str, str], VariableAlignmentCertificate] = {}
    for certificate in certificates:
        key = (
            certificate.fragment_a_id,
            certificate.variable_a,
            certificate.fragment_b_id,
            certificate.variable_b,
        )
        unique[key] = certificate
    return [unique[key] for key in sorted(unique)]


def _build_ontology_warnings(
    *,
    fragment_a: SCMFragment,
    fragment_b: SCMFragment,
    certificates: Sequence[VariableAlignmentCertificate],
    ontology: Sequence[Any],
) -> _OntologyWarningResult:
    if not ontology or not certificates:
        return _OntologyWarningResult()
    try:
        return _OntologyWarningResult(
            warnings=tuple(
                build_fragment_alignment_ontology_warnings(
                    fragment_a=fragment_a,
                    fragment_b=fragment_b,
                    certificates=certificates,
                    ontology=list(ontology),
                )
            )
        )
    except _EXPECTED_ONTOLOGY_WARNING_ERRORS as exc:
        logger.warning(
            "Alignment ontology warning build failed for fragments %s/%s: %s",
            fragment_a.fragment_id,
            fragment_b.fragment_id,
            exc,
        )
        warning = (
            "alignment degraded: ontology_warning_build_failed for pair "
            f"{fragment_a.fragment_id}<->{fragment_b.fragment_id}"
        )
        return _OntologyWarningResult(
            warnings=(warning,),
            degraded_outcomes=(
                AlignmentDegradedOutcome(
                    code=AlignmentDegradedOutcomeCode.ONTOLOGY_WARNING_BUILD_FAILED,
                    fragment_pair=(fragment_a.fragment_id, fragment_b.fragment_id),
                    detail=str(exc),
                ),
            ),
        )


class AlignmentCertificationPolicy(BaseModel):
    """Policy governing how alignment certificates are validated."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed_types: tuple[AlignmentCertificateType, ...] = Field(
        default=tuple(sorted(AlignmentCertificateType, key=lambda x: x.value))
    )
    tau_min: float = 0.65
    composition_rule: Literal["harmonic", "multiplicative"] = "harmonic"
    max_chain_length: int = Field(default=5, ge=1)

    @field_validator("tau_min")
    @classmethod
    def _validate_tau_min(cls, v: float) -> float:
        if v < TAU_MIN_LOWER or v > TAU_MIN_UPPER:
            raise ValueError(
                f"tau_min must be in [{TAU_MIN_LOWER}, {TAU_MIN_UPPER}], got {v}"
            )
        return v

    def validate_chain(self, chain: list[AlignmentCertificate]) -> CertificationResult:
        """Check types, compose confidence, enforce tau_min."""
        violations: list[str] = []
        warning: str | None = None

        if not chain:
            return CertificationResult(
                passed=False,
                effective_confidence=0.0,
                violations=["empty chain"],
            )

        if len(chain) > self.max_chain_length:
            violations.append(
                f"chain length {len(chain)} exceeds max {self.max_chain_length}"
            )

        allowed = set(self.allowed_types)
        for cert in chain:
            if cert.cert_type not in allowed:
                violations.append(
                    f"certificate type {cert.cert_type.value} not allowed by policy"
                )

        scores = [cert.confidence for cert in chain]
        if self.composition_rule == "harmonic":
            effective = compose_confidence_chain(scores)
        else:
            effective = 1.0
            for s in scores:
                effective *= s

        if len(chain) > self.max_chain_length:
            warning = (
                f"Chain length {len(chain)} exceeds recommended "
                f"maximum {self.max_chain_length}; confidence degradation likely."
            )

        passed = effective >= self.tau_min and not violations
        return CertificationResult(
            passed=passed,
            effective_confidence=effective,
            violations=violations,
            long_chain_warning=warning,
        )


# --- DOD-138: Outer objective formula ---


class OuterObjectiveResult(BaseModel):
    """Result of evaluating the outer objective for one policy configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score: float
    coverage: float = Field(ge=0.0, le=1.0)
    conflict_norm: float = Field(ge=0.0, le=1.0)
    lambda_conflict: float
    config: AlignmentCertificationPolicy
    is_feasible: bool


def compute_outer_objective(
    coverage_queries: float,
    irreducible_conflict_norm: float,
    lambda_conflict: float = 1.0,
) -> float:
    """score(N) = coverage - lambda_conflict * irreducible_conflict_norm"""
    return coverage_queries - lambda_conflict * irreducible_conflict_norm


# --- DOD-139: Bounded knobs + grid search ---

TAU_GRID: tuple[float, ...] = (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)
LAMBDA_GRID: tuple[float, ...] = (0.5, 1.0, 2.0)

def _sorted_types(*items: AlignmentCertificateType) -> tuple[AlignmentCertificateType, ...]:
    return tuple(sorted(items, key=lambda x: x.value))


_ALL_TYPES = _sorted_types(*AlignmentCertificateType)
_NO_TEXT = _sorted_types(
    *(t for t in AlignmentCertificateType if t != AlignmentCertificateType.TEXT_CONCEPT_MAP)
)
_EXACT_SCALE = _sorted_types(AlignmentCertificateType.EXACT, AlignmentCertificateType.SCALE_LINK)
_EXACT_ONLY = _sorted_types(AlignmentCertificateType.EXACT)
_PROXY_IRT = _sorted_types(
    AlignmentCertificateType.PROXY_BUNDLE,
    AlignmentCertificateType.LATENT_LINK_IRT,
)
_EXACT_PROXY = _sorted_types(AlignmentCertificateType.EXACT, AlignmentCertificateType.PROXY_BUNDLE)

TYPE_CONFIGS: tuple[tuple[AlignmentCertificateType, ...], ...] = (
    _ALL_TYPES,
    _NO_TEXT,
    _EXACT_SCALE,
    _EXACT_ONLY,
    _PROXY_IRT,
    _EXACT_PROXY,
)

MAX_OUTER_SOLVES = 48
MAX_OUTER_WALLTIME_SEC = 3.0


class OuterSearchResult(BaseModel):
    """Result of bounded grid search over alignment policy knobs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    best_config: AlignmentCertificationPolicy
    best_score: float
    configs_evaluated: int
    truncated: bool
    all_scores: list[OuterObjectiveResult] = Field(default_factory=list)


def run_outer_search(
    evaluator: Callable[..., OuterObjectiveResult],
    type_configs: Sequence[tuple[AlignmentCertificateType, ...]] | None = None,
) -> OuterSearchResult:
    """Bounded grid search over (tau, lambda, type_config) space."""
    configs = type_configs if type_configs is not None else TYPE_CONFIGS
    best_score = float("-inf")
    best_config: AlignmentCertificationPolicy | None = None
    all_scores: list[OuterObjectiveResult] = []
    evaluated = 0
    start = time.monotonic()

    for type_set in configs:
        for tau in TAU_GRID:
            for _lambda in LAMBDA_GRID:
                if evaluated >= MAX_OUTER_SOLVES:
                    return OuterSearchResult(
                        best_config=best_config or _default_policy(),
                        best_score=best_score if best_config else 0.0,
                        configs_evaluated=evaluated,
                        truncated=True,
                        all_scores=all_scores,
                    )
                elapsed = time.monotonic() - start
                if elapsed > MAX_OUTER_WALLTIME_SEC:
                    return OuterSearchResult(
                        best_config=best_config or _default_policy(),
                        best_score=best_score if best_config else 0.0,
                        configs_evaluated=evaluated,
                        truncated=True,
                        all_scores=all_scores,
                    )

                policy = AlignmentCertificationPolicy(
                    allowed_types=type_set,
                    tau_min=tau,
                )
                result = _call_outer_evaluator(
                    evaluator=evaluator,
                    policy=policy,
                    lambda_conflict=float(_lambda),
                )
                all_scores.append(result)
                evaluated += 1
                if result.score > best_score:
                    best_score = result.score
                    best_config = policy

    return OuterSearchResult(
        best_config=best_config or _default_policy(),
        best_score=best_score if best_config else 0.0,
        configs_evaluated=evaluated,
        truncated=False,
        all_scores=all_scores,
    )


def _default_policy() -> AlignmentCertificationPolicy:
    return AlignmentCertificationPolicy()


def persist_variable_alignment_certificate(
    store: ArtifactStore,
    certificate: VariableAlignmentCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _VARIABLE_ALIGNMENT_CERTIFICATE_SCHEMA_NAME,
    schema_version: str = _VARIABLE_ALIGNMENT_CERTIFICATE_SCHEMA_VERSION,
) -> VariableAlignmentCertificateRef:
    """Persist variable alignment certificate helper."""
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind=_VARIABLE_ALIGNMENT_CERTIFICATE_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return VariableAlignmentCertificateRef.model_validate(ref)


def load_variable_alignment_certificate(
    store: ArtifactStore,
    ref: VariableAlignmentCertificateRef,
) -> VariableAlignmentCertificate:
    """Load variable alignment certificate."""
    payload = get_json_artifact(store, ref.artifact_id)
    return VariableAlignmentCertificate.model_validate(payload)


def persist_alignment_report(
    store: ArtifactStore,
    report: AlignmentReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _ALIGNMENT_REPORT_SCHEMA_NAME,
    schema_version: str = _ALIGNMENT_REPORT_SCHEMA_VERSION,
) -> AlignmentReportRef:
    """Persist alignment report helper."""
    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind=_ALIGNMENT_REPORT_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return AlignmentReportRef.model_validate(ref)


def load_alignment_report(
    store: ArtifactStore,
    ref: AlignmentReportRef,
) -> AlignmentReport:
    """Load alignment report."""
    payload = get_json_artifact(store, ref.artifact_id)
    return AlignmentReport.model_validate(payload)


def _measurement_grade_rank(grade: MeasurementComparabilityGrade) -> int:
    ranks = {
        MeasurementComparabilityGrade.INSUFFICIENT: 0,
        MeasurementComparabilityGrade.LOW: 1,
        MeasurementComparabilityGrade.MEDIUM: 2,
        MeasurementComparabilityGrade.HIGH: 3,
    }
    return ranks[grade]


def _grade_for_certificate(
    certificate: VariableAlignmentCertificate,
) -> MeasurementComparabilityGrade:
    base_grade = {
        AlignmentType.EXACT: MeasurementComparabilityGrade.HIGH,
        AlignmentType.SCALE_LINKED: MeasurementComparabilityGrade.MEDIUM,
        AlignmentType.PROXY: MeasurementComparabilityGrade.LOW,
        AlignmentType.LATENT_BRIDGE: MeasurementComparabilityGrade.LOW,
        AlignmentType.INCOMPATIBLE: MeasurementComparabilityGrade.INSUFFICIENT,
    }[certificate.alignment_type]
    if certificate.reviewer is not AlignmentReviewerState.PENDING_REVIEW:
        return base_grade
    if base_grade is MeasurementComparabilityGrade.HIGH:
        return MeasurementComparabilityGrade.MEDIUM
    if base_grade is MeasurementComparabilityGrade.MEDIUM:
        return MeasurementComparabilityGrade.LOW
    return base_grade


def _dedupe_strings(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _dedupe_pairs(values: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    output: list[tuple[str, str]] = []
    for left, right in values:
        pair = (str(left).strip(), str(right).strip())
        if not pair[0] or not pair[1] or pair in seen:
            continue
        seen.add(pair)
        output.append(pair)
    return output


def _dedupe_degraded_outcomes(
    values: Sequence[AlignmentDegradedOutcome],
) -> list[AlignmentDegradedOutcome]:
    seen: set[tuple[str, tuple[str, str], str]] = set()
    output: list[AlignmentDegradedOutcome] = []
    for value in values:
        key = (value.code.value, tuple(value.fragment_pair), value.detail.strip())
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def _call_outer_evaluator(
    *,
    evaluator: Callable[..., OuterObjectiveResult],
    policy: AlignmentCertificationPolicy,
    lambda_conflict: float,
) -> OuterObjectiveResult:
    try:
        signature = inspect.signature(evaluator)
        if len(signature.parameters) >= 2:
            return evaluator(policy, lambda_conflict)
    except (TypeError, ValueError):
        # Some callables may not expose signatures (C-ext / functools partial).
        pass
    result = evaluator(policy)
    if result.lambda_conflict != float(lambda_conflict):
        return result.model_copy(update={"lambda_conflict": float(lambda_conflict)})
    return result


VariableAlignmentCertificate.model_rebuild()


__all__ = [
    "AlignmentDegradedOutcome",
    "AlignmentDegradedOutcomeCode",
    "AlignmentOverallStatus",
    "AlignmentReviewStatus",
    "AlignmentCertificateType",
    "AlignmentCertificate",
    "AlignmentCertificationPolicy",
    "AlignmentReport",
    "AlignmentVerificationConfig",
    "AlignmentReviewerState",
    "AlignmentType",
    "CertificationResult",
    "MetadataCheckStatus",
    "MeasurementComparabilityGrade",
    "OuterObjectiveResult",
    "OuterSearchResult",
    "TAU_GRID",
    "TAU_MIN_LOWER",
    "TAU_MIN_UPPER",
    "LAMBDA_GRID",
    "MAX_OUTER_SOLVES",
    "MAX_OUTER_WALLTIME_SEC",
    "TYPE_CONFIGS",
    "VariableMetadataCheck",
    "VariableAlignmentCertificate",
    "build_alignment_report",
    "compute_outer_objective",
    "load_alignment_report",
    "load_variable_alignment_certificate",
    "persist_alignment_report",
    "persist_variable_alignment_certificate",
    "run_outer_search",
    "verify_fragment_alignment",
    "verify_fragment_bundle_alignment",
]
