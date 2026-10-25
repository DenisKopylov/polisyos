"""Public export redaction and authority-boundary helpers."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from types import UnionType
from typing import TYPE_CHECKING, Any, SupportsInt, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError

from polisyos.core import PromptSanitizer, scan_secret_and_pii
from polisyos.core.contracts.policy_design_case_projection import PolicyDesignCaseProjection
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.authority import (
    AuthorityEnvelopeInput,
    AuthoritySurfaceDecision,
    EvidenceAuthorityEnvelope,
    authority_surface_decision,
    deserialize_authority_envelope,
)
from polisyos.runtime.quality.candidate_firewall import (
    candidate_firewall_issues_for_payload,
)
from polisyos.runtime.quality.case_lifecycle import (
    LIFECYCLE_REISSUE_REPORT_SCHEMA_VERSION,
    PUBLIC_REVISION_STATE_SCHEMA_VERSION,
    PolicyDesignLifecycleError,
    validate_lifecycle_reissue_report,
)
from polisyos.runtime.quality.contestability import (
    PolicyDesignContestabilityError,
    verified_recourse_pointer_for_publication,
)
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleError,
    GenerationCycleRun,
    N9EligibleRunSource,
    eligible_n9_source_for_run,
    validate_generation_cycle_run,
)
from polisyos.runtime.quality.open_world_risk import (
    OpenWorldRiskArtifactResolver,
    OpenWorldRiskGenerationProjectionResolver,
    OpenWorldRiskPromotionGate,
    OpenWorldRiskPublicLimitation,
    OpenWorldRiskResolutionNonReceipt,
)
from polisyos.runtime.quality.projection_semantics import (
    build_policy_design_case_projection_from_runtime_graph,
    build_policy_design_case_projection_semantics,
    verify_policy_design_case_projection_consumer_contract,
    verify_s9_projection_faithfulness_for_pdc_consumer_contract,
    verify_s10_forecast_projection_consumer_contract,
    verify_s11_predictive_projection_consumer_contract,
    verify_s12_resource_projection_consumer_contract,
    verify_s13_post_deploy_accountability_projection_consumer_contract,
    verify_s14_universality_projection_consumer_contract,
)
from polisyos.runtime.quality.promotion_sequence import (
    CanonicalPromotionReceipt,
    validate_canonical_promotion_receipt,
)
from polisyos.runtime.quality.rule_evolution import (
    RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.runtime.quality.design_problem import DesignProblem

PUBLIC_EXPORT_SCHEMA_VERSION = "policyos.runtime.public_export_bundle.v1"
PUBLIC_EXPORT_REDACTION_POLICY_REF = "redaction-policy/public-export-v1"


def _iter_mapping_items[K, V](
    value: Mapping[K, V],
) -> Iterator[tuple[K, V]]:
    """Iterate a mapping through its canonical key and item lookup protocol."""

    for key in value:
        yield key, value[key]


def _copy_mapping[K, V](value: Mapping[K, V]) -> dict[K, V]:
    """Copy every mapping entry without trusting overridable view methods."""

    return {key: value[key] for key in value}


_TENANT_PRIVATE_REF_PATTERNS = (
    re.compile(r"^sha256:[0-9a-f]{64}$", re.IGNORECASE),
    re.compile(r"^cas://sha256/[0-9a-f]{64}$", re.IGNORECASE),
)

_SCALAR_WELFARE_KEYS = frozenset(
    {
        "aggregate_welfare",
        "bcr",
        "net_benefit",
        "npv",
        "scalar_aggregate",
        "scalar_welfare",
        "welfare_aggregate",
        "welfare_delta",
        "welfare_score",
    }
)
_PUBLIC_EXPORT_EVIDENCE_CLASSES = {
    "diagnostic_supporting",
    "public_exported",
    "redacted_derived",
}
_PUBLIC_EXPORT_AUTHORITY_ROLES = {
    "diagnostic_only",
    "not_authoritative",
    "packaging_only",
    "projection_only",
}
_AUTHORITY_ROLES = {
    "approval_input",
    "producer_authority",
    "readiness_input",
    "runtime_blocker",
    "scorecard_input",
}
_AUTHORITY_PROVENANCE_KINDS = {
    "runtime_blocker",
    "runtime_emitted",
    "runtime_fallback",
}
_OFFICIAL_USE_LIMITS = {
    "official_use": "public_audit_only",
    "may_be_used_for": [
        "public_audit",
        "operator_triage",
        "external_explanation",
    ],
    "may_not_be_used_for": [
        "scorecard_authority",
        "approval_authority",
        "runtime_closeout_authority",
        "provider_credential_validation",
        "tenant_identity_resolution",
    ],
    "authority_limitation": (
        "This bundle is a redacted projection. Use the referenced runtime "
        "authority graph for scorecard, readiness, approval, or closeout."
    ),
}


def _normalize_public_export_mapping(
    value: Mapping[str, object],
    *,
    field: str,
) -> dict[str, object]:
    """Snapshot nested public JSON input before validators or scanners inspect it."""

    normalized = _normalize_public_export_value(value, field=field, ancestors=set())
    if not isinstance(normalized, dict):
        raise PublicExportRedactionError(
            "public_export_mapping_invalid",
            f"{field} must be a mapping.",
        )
    return normalized


def _snapshot_public_export_sequence(value: object, *, field: str) -> list[object]:
    """Read a declared sequence through indexed access without retaining its implementation."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PublicExportRedactionError(
            "public_export_sequence_invalid",
            f"{field} must be a sequence.",
        )
    try:
        if isinstance(value, list):
            items = [list.__getitem__(value, index) for index in range(list.__len__(value))]
        elif isinstance(value, tuple):
            items = [tuple.__getitem__(value, index) for index in range(tuple.__len__(value))]
        else:
            items = [value[index] for index in range(len(value))]
    except Exception as exc:
        raise PublicExportRedactionError(
            "public_export_sequence_invalid",
            f"{field} could not be read as a sequence.",
        ) from exc
    if any(item is value for item in items):
        raise PublicExportRedactionError(
            "public_export_payload_cycle",
            "Public export inputs must be acyclic.",
        )
    return items


def _normalize_public_export_value(
    value: object,
    *,
    field: str,
    ancestors: set[int],
) -> object:
    """Copy JSON values and reject unsupported leaves before any serializer sees them."""

    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if math.isfinite(value):
            return value
        raise PublicExportRedactionError(
            "public_export_value_invalid",
            f"{field} contains a non-finite number.",
        )
    if isinstance(value, (str, bytes, bytearray)):
        raise PublicExportRedactionError(
            "public_export_value_invalid",
            f"{field} contains a value outside the JSON domain.",
        )
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in ancestors:
            raise PublicExportRedactionError(
                "public_export_payload_cycle",
                "Public export inputs must be acyclic.",
            )
        ancestors.add(identity)
        try:
            normalized: dict[str, object] = {}
            if isinstance(value, dict):
                entries = ((key, dict.__getitem__(value, key)) for key in dict.__iter__(value))
            else:
                entries = _iter_mapping_items(value)
            for key, item in entries:
                if type(key) is not str:
                    raise PublicExportRedactionError(
                        "public_export_mapping_key_invalid",
                        f"{field} keys must be plain strings.",
                    )
                if key in normalized:
                    raise PublicExportRedactionError(
                        "public_export_mapping_key_invalid",
                        f"{field} contains duplicate mapping keys.",
                    )
                normalized[key] = _normalize_public_export_value(
                    item,
                    field=field,
                    ancestors=ancestors,
                )
            return normalized
        except PublicExportRedactionError:
            raise
        except Exception as exc:
            raise PublicExportRedactionError(
                "public_export_mapping_invalid",
                f"{field} could not be read as a mapping.",
            ) from exc
        finally:
            ancestors.remove(identity)
    if isinstance(value, Sequence):
        identity = id(value)
        if identity in ancestors:
            raise PublicExportRedactionError(
                "public_export_payload_cycle",
                "Public export inputs must be acyclic.",
            )
        ancestors.add(identity)
        try:
            items = _snapshot_public_export_sequence(value, field=field)
            return [
                _normalize_public_export_value(
                    item,
                    field=field,
                    ancestors=ancestors,
                )
                for item in items
            ]
        finally:
            ancestors.remove(identity)
    raise PublicExportRedactionError(
        "public_export_value_invalid",
        f"{field} contains a value outside the JSON domain.",
    )


def _normalize_public_export_authority_envelopes(
    values: Sequence[AuthorityEnvelopeInput],
) -> list[AuthorityEnvelopeInput]:
    """Snapshot envelopes while preserving their declared typed owner boundary."""

    raw_envelopes = _snapshot_public_export_sequence(values, field="authority_envelopes")
    envelopes: list[AuthorityEnvelopeInput] = []
    for envelope in raw_envelopes:
        if isinstance(envelope, Mapping):
            envelopes.append(
                _normalize_public_export_mapping(envelope, field="authority_envelopes")
            )
        elif isinstance(envelope, (EvidenceAuthorityEnvelope, str, bytes)):
            envelopes.append(envelope)
        else:
            raise PublicExportRedactionError(
                "public_export_authority_envelope_invalid",
                "Authority envelope entries must be typed models, mappings, or encoded values.",
            )
    return envelopes


def _normalize_authority_envelope_input(
    value: AuthorityEnvelopeInput,
) -> AuthorityEnvelopeInput:
    """Normalize mapping envelopes before model validation consumes them."""

    if isinstance(value, Mapping):
        return _normalize_public_export_mapping(value, field="authority_envelopes")
    return value


class PublicExportRedactionError(ValueError):
    """Typed public-export redaction or authority-boundary violation."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        authority_surface_decisions: Sequence[Mapping[str, object]] = (),
    ) -> None:
        self.code = code
        self.authority_surface_decisions = [
            _copy_mapping(item) for item in authority_surface_decisions
        ]
        super().__init__(f"{code}: {message or code}")


def project_promotion_open_world_limitation(
    *,
    run: GenerationCycleRun,
    design_problem: DesignProblem,
    receipt: CanonicalPromotionReceipt | Mapping[str, object],
    resolver: OpenWorldRiskArtifactResolver,
    repo_root: Path | None = None,
    n9_source: N9EligibleRunSource | None = None,
) -> OpenWorldRiskPublicLimitation | None:
    """Project OWR only from one current receipt bound to its exact N6 run."""

    try:
        source = eligible_n9_source_for_run(run)
    except GenerationCycleError as exc:
        raise PublicExportRedactionError(
            exc.code,
            str(exc),
        ) from exc
    if source is None:
        raise PublicExportRedactionError("generation_cycle_blocked_before_n9_cannot_supply_receipt")
    if n9_source is not None and (
        type(n9_source) is not N9EligibleRunSource or n9_source.run is not run
    ):
        raise PublicExportRedactionError("promotion_receipt_run_binding_mismatch")
    run_issues = validate_generation_cycle_run(run, repo_root=repo_root)
    if run_issues:
        raise PublicExportRedactionError(
            str(run_issues[0].get("code") or "generation_cycle_run_invalid")
        )
    if run.design_problem_ref != gy_content_hash(design_problem.model_dump(mode="json")):
        raise PublicExportRedactionError("promotion_receipt_run_binding_mismatch")
    try:
        parsed = (
            receipt
            if type(receipt) is CanonicalPromotionReceipt
            else CanonicalPromotionReceipt.model_validate(receipt)
        )
    except ValueError as exc:
        raise PublicExportRedactionError("promotion_receipt_invalid", str(exc)) from exc
    if type(parsed) is not CanonicalPromotionReceipt:
        raise PublicExportRedactionError("legacy_open_world_gate_authority_not_admitted")
    payload = parsed.model_dump(mode="json")
    if sum(item == payload for item in source.promotion_port.receipts) != 1:
        raise PublicExportRedactionError("promotion_receipt_run_binding_mismatch")
    summaries = tuple(
        summary
        for summary in run.candidate_summaries
        if summary.candidate_id == parsed.candidate_id
    )
    if len(summaries) != 1:
        raise PublicExportRedactionError("promotion_candidate_owner_binding_invalid")
    summary = summaries[0]
    if (
        parsed.owner_projection.design_problem_binding.problem_content_hash
        != run.design_problem_ref
        or parsed.owner_projection.candidate_summary != summary
    ):
        raise PublicExportRedactionError("promotion_receipt_run_binding_mismatch")
    issues = validate_canonical_promotion_receipt(
        parsed,
        repo_root=repo_root,
        candidate_summary=summary,
        design_problem=design_problem,
        value_receipt=summary.value_receipt,
        open_world_resolver=resolver,
    )
    if issues:
        code = str(issues[0].get("code") or "promotion_receipt_invalid")
        raise PublicExportRedactionError(code)
    gate = parsed.owner_projection.open_world_gate
    if gate is None:
        raise PublicExportRedactionError("open_world_projection_not_established")
    if gate.status == "established":
        return None
    return OpenWorldRiskPublicLimitation(
        status=gate.status,
        code=gate.limitation_code,
        vector_artifact_ref=gate.vector_artifact_ref,
    )


def project_pre_n9_open_world_limitations(
    *,
    run: GenerationCycleRun,
    design_problem: DesignProblem,
    resolver: OpenWorldRiskGenerationProjectionResolver,
    repo_root: Path | None = None,
) -> tuple[OpenWorldRiskPublicLimitation, ...]:
    """Replay pre-N9 OWR evidence only with a live source-bound N6 receipt."""

    run_issues = validate_generation_cycle_run(run, repo_root=repo_root)
    if run_issues:
        raise PublicExportRedactionError(
            str(run_issues[0].get("code") or "generation_cycle_run_invalid")
        )
    if run.design_problem_ref != gy_content_hash(design_problem.model_dump(mode="json")):
        raise PublicExportRedactionError("open_world_vector_query_mismatch")
    port = run.promotion_port
    if (
        port.status != "not_promoted"
        or port.reason != "epoch_validity_refused:policy_admission_missing"
        or port.receipts
        or port.certified_candidate_ids
    ):
        raise PublicExportRedactionError("open_world_projection_not_established")
    observations = port.pre_n9_open_world_gates
    if not observations:
        raise PublicExportRedactionError("open_world_projection_not_established")
    if len(observations) != len(run.candidate_summaries) or tuple(
        row.ordinal for row in observations
    ) != tuple(range(len(run.candidate_summaries))):
        raise PublicExportRedactionError("open_world_vector_query_mismatch")
    limitations: list[OpenWorldRiskPublicLimitation] = []
    for observation in observations:
        try:
            gate = OpenWorldRiskPromotionGate.model_validate(observation.gate_payload)
        except ValueError as exc:
            raise PublicExportRedactionError(
                "open_world_projection_not_established",
                str(exc),
            ) from exc
        verified = resolver.resolve_verified_for_generation(
            gate=gate,
            expected_problem=design_problem,
            expected_summaries=run.candidate_summaries,
            expected_ordinal=observation.ordinal,
        )
        if isinstance(verified, OpenWorldRiskResolutionNonReceipt):
            raise PublicExportRedactionError(verified.code)
        vector = verified.vector
        if vector.status == "established":
            continue
        limitations.append(
            OpenWorldRiskPublicLimitation(
                status=vector.status,
                code=vector.limitation_code,
                vector_artifact_ref=verified.vector_artifact_ref,
            )
        )
    return tuple(limitations)


class _ProjectionReferenceNotRepresentableError(ValueError):
    """Raised when a private reference occupies a required typed PDC field."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(path)


def _is_projection_reference_field(field_name: str) -> bool:
    """Return whether the typed schema names a field as a reference."""

    return field_name.endswith(("_ref", "_refs", "_ref_fingerprint"))


def _projection_annotation_for_value(value: object, annotation: object) -> tuple[object, bool]:
    """Select a union member from the actual runtime value and retain optionality."""

    args = get_args(annotation)
    origin = get_origin(annotation)
    optional = type(None) in args
    if origin not in (UnionType, Union):
        return annotation, optional
    choices = tuple(choice for choice in args if choice is not type(None))
    for choice in choices:
        if choice is Any:
            return choice, optional
        if choice is str and type(value) is str:
            return choice, optional
        if (
            isinstance(choice, type)
            and issubclass(choice, BaseModel)
            and isinstance(value, Mapping)
        ):
            return choice, optional
        choice_origin = get_origin(choice)
        if isinstance(value, Mapping) and choice_origin in (dict, Mapping):
            return choice, optional
        if (
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes, bytearray))
            and choice_origin in (list, tuple, Sequence)
        ):
            return choice, optional
        if isinstance(choice, type) and type(value) is choice:
            return choice, optional
    return choices[0], optional


def _redact_projection_value_by_schema(
    value: object,
    annotation: object,
    *,
    field_name: str,
    path: str,
    path_tokens: tuple[str | int, ...],
    redactions: list[dict[str, str]],
    scanner_redaction_paths: frozenset[tuple[str | int, ...]],
    optional_field: bool = False,
) -> object:
    """Erase private refs according to typed reference fields, never replace their types."""

    annotation, annotation_optional = _projection_annotation_for_value(value, annotation)
    optional = optional_field or annotation_optional
    origin = get_origin(annotation)
    args = get_args(annotation)
    changed_by_scanner = path_tokens in scanner_redaction_paths
    reference_field = _is_projection_reference_field(field_name)

    if value is None:
        return None

    if annotation is Any or annotation is object:
        return _redact_tenant_private_refs(
            value,
            path=path,
            redactions=redactions,
        )

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="python")
        if not isinstance(value, Mapping):
            return value
        return _redact_projection_model_by_schema(
            value,
            annotation,
            path=path,
            path_tokens=path_tokens,
            redactions=redactions,
            scanner_redaction_paths=scanner_redaction_paths,
        )

    if annotation is str:
        if type(value) is not str:
            return value
        if _is_tenant_private_ref(value):
            if reference_field and optional:
                redactions.append({"path": path, "reason": "tenant_private_ref"})
                return None
            if reference_field:
                raise _ProjectionReferenceNotRepresentableError(path)
            raise _ProjectionReferenceNotRepresentableError(path)
        if changed_by_scanner and reference_field:
            if optional:
                redactions.append({"path": path, "reason": "canonical_secret_redaction"})
                return None
            raise _ProjectionReferenceNotRepresentableError(path)
        return value

    if origin in (list, tuple, Sequence):
        item_annotation = args[0] if args else Any
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return value
        sanitized: list[object] = []
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            item_tokens = (*path_tokens, index)
            if type(item) is str and (
                _is_tenant_private_ref(item) or item_tokens in scanner_redaction_paths
            ):
                if reference_field:
                    redactions.append(
                        {
                            "path": item_path,
                            "reason": (
                                "tenant_private_ref"
                                if _is_tenant_private_ref(item)
                                else "canonical_secret_redaction"
                            ),
                        }
                    )
                    continue
                if _is_tenant_private_ref(item):
                    raise _ProjectionReferenceNotRepresentableError(item_path)
            sanitized.append(
                _redact_projection_value_by_schema(
                    item,
                    item_annotation,
                    field_name=field_name,
                    path=item_path,
                    path_tokens=item_tokens,
                    redactions=redactions,
                    scanner_redaction_paths=scanner_redaction_paths,
                )
            )
        return tuple(sanitized) if isinstance(value, tuple) else sanitized

    if origin in (dict, Mapping):
        key_annotation, value_annotation = args if len(args) == 2 else (str, Any)
        if not isinstance(value, Mapping):
            return value
        sanitized_mapping: dict[object, object] = {}
        for key, item in _iter_mapping_items(value):
            item_path = f"{path}.{key}"
            item_tokens = (*path_tokens, str(key))
            key_is_private = type(key) is str and _is_tenant_private_ref(key)
            item_is_private = type(item) is str and _is_tenant_private_ref(item)
            scanner_changed = item_tokens in scanner_redaction_paths
            if reference_field and (key_is_private or item_is_private or scanner_changed):
                redactions.append(
                    {
                        "path": item_path,
                        "reason": (
                            "tenant_private_ref"
                            if key_is_private or item_is_private
                            else "canonical_secret_redaction"
                        ),
                    }
                )
                continue
            if key_is_private:
                raise _ProjectionReferenceNotRepresentableError(item_path)
            sanitized_key = _redact_projection_value_by_schema(
                key,
                key_annotation,
                field_name=field_name,
                path=f"{path}.<key>",
                path_tokens=path_tokens,
                redactions=redactions,
                scanner_redaction_paths=scanner_redaction_paths,
            )
            sanitized_mapping[sanitized_key] = _redact_projection_value_by_schema(
                item,
                value_annotation,
                field_name=field_name,
                path=item_path,
                path_tokens=item_tokens,
                redactions=redactions,
                scanner_redaction_paths=scanner_redaction_paths,
            )
        return sanitized_mapping

    return value


def _redact_projection_model_by_schema(
    value: Mapping[str, object],
    model_type: type[BaseModel],
    *,
    path: str,
    path_tokens: tuple[str | int, ...],
    redactions: list[dict[str, str]],
    scanner_redaction_paths: frozenset[tuple[str | int, ...]] = frozenset(),
) -> dict[str, object]:
    """Recursively redact only schema-typed reference fields from a public projection."""

    fields = model_type.model_fields
    sanitized: dict[str, object] = {}
    for key, item in _iter_mapping_items(value):
        field = fields.get(key)
        if field is None:
            raise _ProjectionReferenceNotRepresentableError(f"{path}.{key}")
        sanitized[key] = _redact_projection_value_by_schema(
            item,
            field.annotation,
            field_name=key,
            path=f"{path}.{key}",
            path_tokens=(*path_tokens, key),
            redactions=redactions,
            scanner_redaction_paths=scanner_redaction_paths,
        )
    return sanitized


def _split_projection_extensions(
    value: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Separate the strict PDC DTO from already-produced S/G3 sibling projections."""

    fields = PolicyDesignCaseProjection.model_fields
    typed_projection: dict[str, object] = {}
    extensions: dict[str, object] = {}
    for key, item in _iter_mapping_items(value):
        if key in fields:
            typed_projection[key] = item
        else:
            extensions[key] = item
    return typed_projection, extensions


def _mapping_contains_exact_pair(
    value: object,
    *,
    key: str,
    expected: object,
) -> bool:
    if isinstance(value, Mapping):
        for nested_key, nested_value in _iter_mapping_items(value):
            if nested_key == key and nested_value == expected:
                return True
            if _mapping_contains_exact_pair(nested_value, key=key, expected=expected):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_mapping_contains_exact_pair(item, key=key, expected=expected) for item in value)
    return False


def _named_verification_matches(
    value: object,
    *,
    verification_key: str,
    field_name: str,
    expected: object,
) -> bool:
    if isinstance(value, Mapping):
        for key, nested_value in _iter_mapping_items(value):
            if (
                key == verification_key
                and isinstance(nested_value, Mapping)
                and nested_value.get(field_name) == expected
            ):
                return True
            if _named_verification_matches(
                nested_value,
                verification_key=verification_key,
                field_name=field_name,
                expected=expected,
            ):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(
            _named_verification_matches(
                item,
                verification_key=verification_key,
                field_name=field_name,
                expected=expected,
            )
            for item in value
        )
    return False


def _unrepresented_projection_extensions(
    extensions: Mapping[str, object],
    semantic_audit: Mapping[str, object],
) -> dict[str, object]:
    """Retain only projection additions not already represented by their audit owner."""

    retained: dict[str, object] = {}
    for key, value in _iter_mapping_items(extensions):
        if key == "s9_projection_faithfulness":
            retained[key] = value
            continue
        if _mapping_contains_exact_pair(semantic_audit, key=key, expected=value):
            continue
        if key.endswith("_contract_verification_status"):
            verification_key = key.removesuffix("_status")
            if key.startswith("s9_"):
                verification_key = "s9_projection_faithfulness"
            if _named_verification_matches(
                semantic_audit,
                verification_key=verification_key,
                field_name="status",
                expected=value,
            ):
                continue
        if key.endswith("_contract_verification_ref"):
            verification_key = key.removesuffix("_ref")
            if key.startswith("s9_"):
                verification_key = "s9_projection_faithfulness"
            if _named_verification_matches(
                semantic_audit,
                verification_key=verification_key,
                field_name="consumer_contract_ref",
                expected=value,
            ):
                continue
        retained[key] = value
    return retained


def _redact_and_verify_public_projection(
    projection: Mapping[str, object],
    *,
    previous_verification: Mapping[str, object] | None,
    runtime_pdc_graph: Mapping[str, object] | None,
    scanner_redaction_paths: frozenset[tuple[str | int, ...]] = frozenset(),
) -> tuple[dict[str, object] | None, dict[str, object], list[dict[str, str]]]:
    """Rebuild and verify the strict PDC after each reference-redaction pass."""

    redactions: list[dict[str, str]] = []
    try:
        typed_projection = _redact_projection_model_by_schema(
            projection,
            PolicyDesignCaseProjection,
            path="projection_semantics",
            path_tokens=(),
            redactions=redactions,
            scanner_redaction_paths=scanner_redaction_paths,
        )
    except _ProjectionReferenceNotRepresentableError as exc:
        previous = previous_verification or {
            "schema_version": (
                "policyos.runtime.policy_design_case.projection_contract_verification.v1"
            ),
            "status": "fail",
        }
        refusal = _projection_verification_with_siblings(
            previous,
            previous,
            refusal_path=exc.path,
        )
        return None, refusal, redactions

    if redactions:
        typed_projection = _mark_projection_redacted(
            typed_projection,
            reference_paths=[item["path"] for item in redactions],
        )
    typed_projection_model = PolicyDesignCaseProjection.model_validate(typed_projection)
    typed_projection, verification = _verify_final_public_projection(
        typed_projection_model.model_dump(mode="json"),
        expected_closeout_truth=typed_projection_model.closeout_truth.model_dump(mode="json"),
        expected_contested_record_ids=[
            record.contested_record_id for record in typed_projection_model.contested_records
        ],
        runtime_pdc_graph=runtime_pdc_graph,
        previous_verification=previous_verification,
    )
    return typed_projection, verification, redactions


def _mark_projection_redacted(
    projection: dict[str, object],
    *,
    reference_paths: Sequence[str],
) -> dict[str, object]:
    """Record truthful redaction state without inventing a replacement reference."""

    if not reference_paths:
        return projection
    summary_value = projection.get("redaction_summary")
    summary = _copy_mapping(summary_value) if isinstance(summary_value, Mapping) else {}
    existing_paths = summary.get("tenant_private_reference_paths")
    paths = (
        [item for item in existing_paths if type(item) is str]
        if isinstance(existing_paths, list)
        else []
    )
    for path in reference_paths:
        if path not in paths:
            paths.append(path)
    summary["redacted_for_public"] = True
    summary["tenant_private_reference_count"] = len(paths)
    summary["tenant_private_reference_paths"] = sorted(paths)
    projection["redaction_summary"] = summary
    projection["redacted"] = True
    projection["evidence_class"] = "redacted_derived"
    return projection


def _projection_verification_with_siblings(
    pdc_verification: Mapping[str, object],
    previous: Mapping[str, object] | None,
    *,
    refusal_path: str | None = None,
) -> dict[str, object]:
    """Bind aggregate status to the final PDC verdict and preserved S/G3 verdicts."""

    result = _copy_mapping(pdc_verification)
    sibling_keys = (
        "s9_projection_faithfulness",
        "s10_forecast_projection",
        "s11_predictive_projection",
        "s12_resource_projection",
        "s13_post_deploy_accountability_projection",
        "s14_universality_projection",
        "layer3_g3_analytics_search_projection",
    )
    statuses = [str(result.get("status") or "fail")]
    if previous is not None:
        for key in sibling_keys:
            sibling = previous.get(key)
            if isinstance(sibling, Mapping):
                sibling_copy = _copy_mapping(sibling)
                result[key] = sibling_copy
                statuses.append(str(sibling_copy.get("status") or "fail"))
    if refusal_path is not None:
        issues_value = result.get("issues")
        issues = (
            [_copy_mapping(item) for item in issues_value if isinstance(item, Mapping)]
            if isinstance(issues_value, list)
            else []
        )
        issues.append(
            {
                "code": "public_export_projection_reference_not_representable",
                "audience": "public",
                "path": refusal_path,
            }
        )
        result["issues"] = issues
        contracts_value = result.get("consumer_contracts")
        contracts = (
            [_copy_mapping(item) for item in contracts_value if isinstance(item, Mapping)]
            if isinstance(contracts_value, list)
            else []
        )
        result["consumer_contracts"] = [
            {
                "consumer": "public",
                "audience": "public",
                "status": "fail",
                "issue_codes": ["public_export_projection_reference_not_representable"],
                "verified_fields": [],
            },
            *[row for row in contracts if row.get("audience") != "public"],
        ]
        statuses.append("fail")
    result["status"] = "fail" if any(status != "pass" for status in statuses) else "pass"
    return result


def _verify_final_public_projection(
    projection: dict[str, object],
    *,
    expected_closeout_truth: Mapping[str, object],
    expected_contested_record_ids: Sequence[str],
    runtime_pdc_graph: Mapping[str, object] | None,
    previous_verification: Mapping[str, object] | None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Recompute the typed PDC verdict after redaction, then compose sibling statuses."""

    pdc = verify_policy_design_case_projection_consumer_contract(
        projections={"public": projection},
        expected_closeout_truth=expected_closeout_truth,
        expected_contested_record_ids=expected_contested_record_ids,
        runtime_pdc_graph=runtime_pdc_graph,
    )
    pdc_status = str(pdc.get("status") or "fail")
    projection["contract_verification_status"] = pdc_status
    projection["contract_verification_refs"] = [
        "policyos.runtime.policy_design_case.projection_contract_verification.v1"
    ]
    return projection, _projection_verification_with_siblings(
        pdc,
        previous_verification,
    )


_FINAL_STAGE_AUDIT_SPECS = (
    (
        "s10",
        "s10_forecast_projection",
        "s10_forecast_projection_contract_verification",
        "s10_forecast_projection",
    ),
    (
        "s11",
        "s11_predictive_projection",
        "s11_predictive_projection_contract_verification",
        "s11_predictive_projection",
    ),
    (
        "s12",
        "s12_resource_projection",
        "s12_resource_projection_contract_verification",
        "s12_resource_projection",
    ),
    (
        "s13",
        "s13_post_deploy_accountability_projection",
        "s13_post_deploy_accountability_projection_contract_verification",
        "s13_post_deploy_accountability_projection",
    ),
    (
        "s14",
        "s14_universality_projection",
        "s14_universality_projection_contract_verification",
        "s14_universality_projection",
    ),
)


_FINAL_AUDIT_REDACTED = object()
_REDACTED_PRIVATE_KEY = re.compile(r"^\[REDACTED_TENANT_PRIVATE_REF_KEY_[0-9a-f]{16}\]$")
_FINAL_STAGE_AUDIT_RECORD_PATHS = frozenset(
    ("semantic_audit", projection_key) for _, projection_key, _, _ in _FINAL_STAGE_AUDIT_SPECS
) | frozenset(
    {
        ("semantic_audit", "layer3_g3_analytics_search_projection"),
        (
            "semantic_audit",
            "projection_extensions",
            "s9_projection_faithfulness",
        ),
    }
)


def _is_final_stage_audit_payload_path(path: tuple[str | int, ...]) -> bool:
    return any(
        path[: len(record_path)] == record_path for record_path in _FINAL_STAGE_AUDIT_RECORD_PATHS
    )


def _final_audit_path(path: tuple[str | int, ...]) -> str:
    if not path:
        return ""
    rendered = str(path[0])
    for component in path[1:]:
        rendered += f"[{component}]" if isinstance(component, int) else f".{component}"
    return rendered


def _remove_final_audit_redactions(
    value: object,
    *,
    path: tuple[str | int, ...],
    tenant_private_paths: frozenset[str],
    scanner_redaction_paths: frozenset[tuple[str | int, ...]],
) -> object:
    """Normalize exact redaction receipts only within registered stage payloads.

    The shared redactors still sanitize every emitted field. This second pass removes their
    replacement values only from records whose typed consumer contracts must be recomputed;
    explanatory markers in unrelated audit records remain visible.
    """

    is_stage_payload = _is_final_stage_audit_payload_path(path)
    if is_stage_payload and (
        path in scanner_redaction_paths or _final_audit_path(path) in tenant_private_paths
    ):
        return _FINAL_AUDIT_REDACTED
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, nested in _iter_mapping_items(value):
            public_key = key if type(key) is str else str(key)
            child_path = (*path, public_key)
            child_path_text = _final_audit_path(child_path)
            if (
                is_stage_payload
                and child_path_text in tenant_private_paths
                and _REDACTED_PRIVATE_KEY.fullmatch(public_key)
            ):
                continue
            sanitized = _remove_final_audit_redactions(
                nested,
                path=child_path,
                tenant_private_paths=tenant_private_paths,
                scanner_redaction_paths=scanner_redaction_paths,
            )
            result[public_key] = None if sanitized is _FINAL_AUDIT_REDACTED else sanitized
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        sanitized_items: list[object] = []
        for index, nested in enumerate(value):
            sanitized = _remove_final_audit_redactions(
                nested,
                path=(*path, index),
                tenant_private_paths=tenant_private_paths,
                scanner_redaction_paths=scanner_redaction_paths,
            )
            if sanitized is not _FINAL_AUDIT_REDACTED:
                sanitized_items.append(sanitized)
        return sanitized_items
    return value


def _run_final_stage_consumer_verifier(
    stage: str,
    record: Mapping[str, object],
) -> dict[str, Any]:
    """Run the registered consumer contract on its exact final emitted record."""

    projections = {"public": record}
    if stage == "s10":
        return verify_s10_forecast_projection_consumer_contract(projections=projections)
    if stage == "s11":
        return verify_s11_predictive_projection_consumer_contract(projections=projections)
    if stage == "s12":
        return verify_s12_resource_projection_consumer_contract(projections=projections)
    if stage == "s13":
        return verify_s13_post_deploy_accountability_projection_consumer_contract(
            projections=projections
        )
    if stage == "s14":
        return verify_s14_universality_projection_consumer_contract(projections=projections)
    raise ValueError(f"Unregistered public-export stage {stage!r}.")


def _final_s9_verification(
    *,
    audit: dict[str, object],
    projection: Mapping[str, object] | None,
    aggregate_before: Mapping[str, object] | None,
) -> dict[str, Any] | None:
    extensions_value = audit.get("projection_extensions")
    extensions = _copy_mapping(extensions_value) if isinstance(extensions_value, Mapping) else {}
    faithfulness = extensions.get("s9_projection_faithfulness")
    previous = aggregate_before.get("s9_projection_faithfulness") if aggregate_before else None
    active = (isinstance(faithfulness, Mapping) and bool(faithfulness)) or isinstance(
        previous, Mapping
    )
    if not active:
        return None

    projection_value = _copy_mapping(projection) if isinstance(projection, Mapping) else {}
    source_state_value = projection_value.get("source_state")
    source_state = (
        _copy_mapping(source_state_value) if isinstance(source_state_value, Mapping) else {}
    )
    verifier_projection = {
        **projection_value,
        "projection_policy": _text(source_state.get("s9_projection_policy")),
        "source_revision_ref": _text(source_state.get("s9_source_revision_ref")),
        "s9_projection_faithfulness": (
            _copy_mapping(faithfulness) if isinstance(faithfulness, Mapping) else {}
        ),
    }
    closeout_value = projection_value.get("closeout_truth")
    closeout_truth = _copy_mapping(closeout_value) if isinstance(closeout_value, Mapping) else {}
    contested_ids = [
        _text(record.get("contested_record_id"))
        for record in _as_sequence(projection_value.get("contested_records"))
        if isinstance(record, Mapping) and _text(record.get("contested_record_id"))
    ]
    verification = verify_s9_projection_faithfulness_for_pdc_consumer_contract(
        projections={"public": verifier_projection},
        expected_closeout_truth=closeout_truth,
        expected_contested_record_ids=contested_ids,
    )
    if "s9_projection_contract_verification_status" in extensions:
        extensions["s9_projection_contract_verification_status"] = verification.get("status")
    if "s9_projection_contract_verification_ref" in extensions:
        extensions["s9_projection_contract_verification_ref"] = verification.get(
            "consumer_contract_ref"
        )
    if isinstance(extensions_value, Mapping):
        audit["projection_extensions"] = extensions
    return verification


def _final_g3_verification(
    audit: dict[str, object],
    aggregate_before: Mapping[str, object] | None,
) -> dict[str, object] | None:
    projection_key = "layer3_g3_analytics_search_projection"
    verification_key = "layer3_g3_analytics_search_projection_contract_verification"
    aggregate_key = "layer3_g3_analytics_search_projection"
    record_value = audit.get(projection_key)
    previous = audit.get(verification_key)
    previous_aggregate = aggregate_before.get(aggregate_key) if aggregate_before else None
    active = isinstance(record_value, Mapping) and bool(record_value)
    active = active or isinstance(previous, Mapping) or isinstance(previous_aggregate, Mapping)
    if not active:
        return None

    from polisyos.runtime.quality.proving_ground.proof_carrying_analytics_search import (
        Layer3G3PublicExportProjectionRefSurface,
        build_g3_public_export_projection_ref_surface,
    )

    clean_record = _copy_mapping(record_value) if isinstance(record_value, Mapping) else {}
    model_fields = Layer3G3PublicExportProjectionRefSurface.model_fields
    typed_input = {key: value for key, value in clean_record.items() if key in model_fields}

    def build_from_projection(surface: Mapping[str, object]) -> dict[str, object]:
        certificate_report = {
            "resolved_certificate_count": _int(surface.get("resolved_certificate_count")),
            "blocking_certificate_count": _int(surface.get("blocked_certificate_count")),
        }
        proof_records = [
            {"proof_ref": reference}
            for reference in _text_list(surface.get("proof_carrying_analytics_refs"))
        ]
        bridge_refs = _text_list(surface.get("ir_analytics_bridge_refs"))
        bridge = {"bridge_ref": bridge_refs[0]} if bridge_refs else None
        derived = build_g3_public_export_projection_ref_surface(
            certificate_resolution_report=certificate_report,
            proof_carrying_analytics_records=proof_records,
            ir_analytics_bridge=bridge,
        )
        return derived.model_dump(mode="json")

    try:
        surface = Layer3G3PublicExportProjectionRefSurface.model_validate(typed_input)
    except ValidationError:
        derived_refusal = build_g3_public_export_projection_ref_surface(
            certificate_resolution_report={"resolved_certificate_count": 0},
            proof_carrying_analytics_records=(),
            ir_analytics_bridge=None,
        )
        surface = Layer3G3PublicExportProjectionRefSurface(
            status="fail",
            public_payload_redaction_status="fail",
            issue_codes=derived_refusal.issue_codes,
        )
        clean_record = {
            "audience": "PUBLIC",
            "authority_role": "projection_only",
            "projection_policy": "reads_layer3_g3_resolution_status_as_audit_refs",
        }

    surface_payload = surface.model_dump(mode="python")
    derived = build_from_projection(surface_payload)
    original_status = surface.status
    final_status = (
        "fail"
        if original_status == "pass" and _text(derived.get("status")) != "pass"
        else original_status
    )
    issue_codes = tuple(
        dict.fromkeys((*surface.issue_codes, *_text_list(derived.get("issue_codes"))))
    )
    model_payload = surface.model_dump(mode="python")
    model_payload.update(status=final_status, issue_codes=issue_codes)
    final_surface = Layer3G3PublicExportProjectionRefSurface.model_validate(model_payload)
    final_record = _copy_mapping(clean_record)
    final_record.update(final_surface.model_dump(mode="json"))
    verifier_status = (
        "pass"
        if final_surface.status == "pass"
        and final_surface.public_payload_redaction_status == "pass"
        else "fail"
    )
    verification: dict[str, object] = {
        "consumer_contract_ref": (
            "policyos.runtime.policy_design_case.layer3_g3_public_projection_verification.v1"
        ),
        "status": verifier_status,
        "public_projection": final_record,
        "issue_codes": list(final_surface.issue_codes),
    }
    audit[projection_key] = final_record
    audit[verification_key] = verification
    return verification


def _reverify_final_public_audit(
    semantic_audit: Mapping[str, object],
    *,
    projection: Mapping[str, object] | None,
    runtime_pdc_graph: Mapping[str, object] | None,
    tenant_private_paths: frozenset[str],
    scanner_redaction_paths: frozenset[tuple[str | int, ...]],
) -> tuple[dict[str, object], dict[str, object] | None]:
    """Recompute every emitted PDC and S9-G3 verdict after recursive redaction."""

    sanitized_value = _remove_final_audit_redactions(
        semantic_audit,
        path=("semantic_audit",),
        tenant_private_paths=tenant_private_paths,
        scanner_redaction_paths=scanner_redaction_paths,
    )
    if not isinstance(sanitized_value, Mapping):
        raise PublicExportRedactionError(
            "public_export_final_audit_invalid",
            "Final public audit must remain a JSON mapping after path-bound redaction.",
        )
    audit = _copy_mapping(sanitized_value)
    aggregate_before_value = audit.get("projection_contract_verification")
    aggregate_before = (
        _copy_mapping(aggregate_before_value)
        if isinstance(aggregate_before_value, Mapping)
        else None
    )

    pdc_verification: dict[str, Any] | None
    if isinstance(projection, Mapping):
        typed_projection = PolicyDesignCaseProjection.model_validate(_copy_mapping(projection))
        final_projection, pdc_verification = _verify_final_public_projection(
            typed_projection.model_dump(mode="json"),
            expected_closeout_truth=typed_projection.closeout_truth.model_dump(mode="json"),
            expected_contested_record_ids=[
                record.contested_record_id for record in typed_projection.contested_records
            ],
            runtime_pdc_graph=runtime_pdc_graph,
            previous_verification=None,
        )
    elif aggregate_before is not None:
        pdc_verification = _copy_mapping(aggregate_before)
        for key in (
            "s9_projection_faithfulness",
            "s10_forecast_projection",
            "s11_predictive_projection",
            "s12_resource_projection",
            "s13_post_deploy_accountability_projection",
            "s14_universality_projection",
            "layer3_g3_analytics_search_projection",
        ):
            pdc_verification.pop(key, None)
        pdc_verification["status"] = "fail"
        final_projection = None
    else:
        pdc_verification = None
        final_projection = None

    fresh_siblings: dict[str, object] = {}
    s9_verification = _final_s9_verification(
        audit=audit,
        projection=final_projection,
        aggregate_before=aggregate_before,
    )
    if s9_verification is not None:
        fresh_siblings["s9_projection_faithfulness"] = s9_verification

    for stage, projection_key, verification_key, aggregate_key in _FINAL_STAGE_AUDIT_SPECS:
        record_value = audit.get(projection_key)
        verification_value = audit.get(verification_key)
        aggregate_value = (
            aggregate_before.get(aggregate_key) if aggregate_before is not None else None
        )
        active = isinstance(record_value, Mapping) and bool(record_value)
        active = active or isinstance(verification_value, Mapping)
        active = active or isinstance(aggregate_value, Mapping)
        if not active:
            continue
        record = _copy_mapping(record_value) if isinstance(record_value, Mapping) else {}
        verification = _run_final_stage_consumer_verifier(stage, record)
        audit[verification_key] = verification
        fresh_siblings[aggregate_key] = verification

    g3_verification = _final_g3_verification(audit, aggregate_before)
    if g3_verification is not None:
        fresh_siblings["layer3_g3_analytics_search_projection"] = g3_verification

    if pdc_verification is None and fresh_siblings:
        pdc_verification = verify_policy_design_case_projection_consumer_contract(
            projections={"public": {}},
            expected_closeout_truth={},
            expected_contested_record_ids=(),
            runtime_pdc_graph=runtime_pdc_graph,
        )
    if pdc_verification is None:
        audit["projection_contract_verification"] = None
    else:
        audit["projection_contract_verification"] = _projection_verification_with_siblings(
            pdc_verification,
            fresh_siblings,
        )
    return audit, final_projection


def build_public_export_bundle(
    *,
    run_id: str,
    artifacts: Mapping[str, object],
    authority_envelopes: Sequence[AuthorityEnvelopeInput] = (),
    policy_design_case: Mapping[str, object] | None = None,
    runtime_pdc_graph: Mapping[str, object] | None = None,
    projection_payload: Mapping[str, object] | None = None,
    runtime_truth_preservation: Mapping[str, object] | None = None,
    title: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Build a redacted public projection that cannot satisfy authority gates."""

    if type(run_id) is not str or (title is not None and type(title) is not str):
        raise PublicExportRedactionError(
            "public_export_text_input_invalid",
            "Run identifiers and titles must be plain strings.",
        )
    authority_envelopes = _normalize_public_export_authority_envelopes(authority_envelopes)
    artifacts = _normalize_public_export_mapping(artifacts, field="artifacts")
    if policy_design_case is not None:
        policy_design_case = _normalize_public_export_mapping(
            policy_design_case,
            field="policy_design_case",
        )
    if runtime_pdc_graph is not None:
        runtime_pdc_graph = _normalize_public_export_mapping(
            runtime_pdc_graph,
            field="runtime_pdc_graph",
        )
    if projection_payload is not None:
        projection_payload = _normalize_public_export_mapping(
            projection_payload,
            field="projection_payload",
        )
    if runtime_truth_preservation is not None:
        runtime_truth_preservation = _normalize_public_export_mapping(
            runtime_truth_preservation,
            field="runtime_truth_preservation",
        )
    recourse_pointer = None
    if policy_design_case is not None:
        try:
            recourse_pointer = verified_recourse_pointer_for_publication(
                policy_design_case=policy_design_case,
                projection_payload=projection_payload or {},
            )
        except PolicyDesignContestabilityError as exc:
            raise PublicExportRedactionError(exc.code, exc.message) from exc
    _assert_no_unexplained_replay_drift(artifacts)
    _assert_public_export_candidate_firewall(artifacts)
    _assert_public_welfare_frontier_surface(artifacts)
    if projection_payload is not None:
        _assert_public_welfare_frontier_surface(projection_payload)
    (
        sanitized_artifacts,
        secret_pii_scan_reports,
        redactions,
        sanitizer_strangle_receipt,
    ) = _scan_public_export_artifacts(run_id=run_id, artifacts=artifacts)
    authority_surface_decisions = _authority_surface_decisions_for_public_export(artifacts)
    public_authority_surface_decisions = _public_authority_surface_decisions(
        authority_surface_decisions,
        redactions=redactions,
    )
    blocking_decisions = [
        (artifact_key, decision)
        for artifact_key, decision in authority_surface_decisions
        if decision.blocking
    ]
    if blocking_decisions:
        artifact_key, decision = blocking_decisions[0]
        raise PublicExportRedactionError(
            "authority_surface_blocked",
            (f"{artifact_key} cannot be exported for {decision.purpose}: {decision.reason}"),
            authority_surface_decisions=public_authority_surface_decisions,
        )
    rule_evolution_annotations = _iter_rule_evolution_annotations(sanitized_artifacts)
    public_revision_states = _iter_public_revision_states(sanitized_artifacts)
    orchestration_continuity = _public_orchestration_continuity_projection(sanitized_artifacts)
    validated_authority_envelopes = [
        deserialize_authority_envelope(_normalize_authority_envelope_input(envelope))
        for envelope in authority_envelopes
    ]
    authority_projections = [
        _authority_projection(envelope) for envelope in validated_authority_envelopes
    ]
    tenant_private_refs = _tenant_private_refs_in_payload(
        {
            "run_id": run_id,
            "title": title,
            "artifacts": artifacts,
            "authority_envelopes": [
                envelope.model_dump(mode="json") for envelope in validated_authority_envelopes
            ],
            "policy_design_case": policy_design_case,
            "runtime_pdc_graph": runtime_pdc_graph,
            "projection_payload": projection_payload,
            "runtime_truth_preservation": runtime_truth_preservation,
        }
    )
    for authority_projection in authority_projections:
        _assert_no_tenant_private_ref_leak(authority_projection, tenant_private_refs)
    projection_semantics = None
    projection_extensions: dict[str, object] = {}
    projection_contract_verification = None
    s10_verification = None
    s10_projection = None
    s11_verification = None
    s11_projection = None
    s12_verification = None
    s12_projection = None
    s13_verification = None
    s13_projection = None
    s13_public_revision_state = None
    s14_verification = None
    s14_projection = None
    g3_verification = None
    g3_projection = None
    if runtime_pdc_graph is not None:
        projection_semantics = build_policy_design_case_projection_from_runtime_graph(
            runtime_pdc_graph=runtime_pdc_graph,
            surface="public_export",
            generated_at=generated_at,
        )
        projection_contract_verification = verify_policy_design_case_projection_consumer_contract(
            projections={"public": projection_semantics},
            expected_closeout_truth=projection_semantics["closeout_truth"],
            expected_contested_record_ids=[
                str(record.get("contested_record_id"))
                for record in projection_semantics.get("contested_records", [])
                if isinstance(record, Mapping)
            ],
            runtime_pdc_graph=runtime_pdc_graph,
        )
        projection_semantics = {
            **projection_semantics,
            "contract_verification_status": str(
                projection_contract_verification.get("status") or "fail"
            ),
            "contract_verification_refs": [
                "policyos.runtime.policy_design_case.projection_contract_verification.v1"
            ],
        }
    elif policy_design_case is not None:
        projection_source: dict[str, object] = {
            "public_export_classification": "public_redacted_projection",
            "evidence_class": "redacted_derived",
        }
        if projection_payload is not None:
            projection_source.update(_copy_mapping(projection_payload))
        projection_semantics = build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case,
            surface="public_export",
            source_payload=projection_source,
            source_ref=(
                source_ref
                if isinstance(
                    (source_ref := projection_source.get("source_ref")),
                    str,
                )
                else None
            ),
            generated_at=generated_at,
        )
        projection_contract_verification = verify_policy_design_case_projection_consumer_contract(
            projections={"public": projection_semantics},
            expected_closeout_truth=projection_semantics["closeout_truth"],
            expected_contested_record_ids=[
                str(record.get("contested_record_id"))
                for record in projection_semantics.get("contested_records", [])
                if isinstance(record, Mapping)
            ],
        )
        projection_semantics = {
            **projection_semantics,
            "contract_verification_status": str(
                projection_contract_verification.get("status") or "fail"
            ),
            "contract_verification_refs": [
                "policyos.runtime.policy_design_case.projection_contract_verification.v1"
            ],
        }
    if projection_semantics is not None and projection_payload is not None:
        projection_semantics, s9_verification = _apply_s9_projection_faithfulness(
            projection_semantics=projection_semantics,
            projection_payload=projection_payload,
        )
        if s9_verification is not None and projection_contract_verification is not None:
            projection_contract_verification = {
                **projection_contract_verification,
                "s9_projection_faithfulness": s9_verification,
                "status": "fail"
                if (
                    projection_contract_verification.get("status") == "fail"
                    or s9_verification.get("status") == "fail"
                )
                else "pass",
            }
        projection_semantics, s10_verification, s10_projection = _apply_s10_forecast_projection(
            projection_semantics=projection_semantics,
            projection_payload=projection_payload,
        )
        if s10_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        s10_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "s10_forecast_projection_verification.v1"
                        )
                    ),
                    "status": str(s10_verification.get("status") or "fail"),
                    "s10_forecast_projection": s10_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "s10_forecast_projection": s10_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or s10_verification.get("status") == "fail"
                    )
                    else "pass",
                }
        projection_semantics, s11_verification, s11_projection = _apply_s11_predictive_projection(
            projection_semantics=projection_semantics,
            projection_payload=projection_payload,
        )
        if s11_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        s11_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "s11_predictive_projection_verification.v1"
                        )
                    ),
                    "status": str(s11_verification.get("status") or "fail"),
                    "s11_predictive_projection": s11_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "s11_predictive_projection": s11_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or s11_verification.get("status") == "fail"
                    )
                    else "pass",
                }
        projection_semantics, s12_verification, s12_projection = _apply_s12_resource_projection(
            projection_semantics=projection_semantics,
            projection_payload=projection_payload,
        )
        if s12_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        s12_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "s12_resource_projection_verification.v1"
                        )
                    ),
                    "status": str(s12_verification.get("status") or "fail"),
                    "s12_resource_projection": s12_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "s12_resource_projection": s12_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or s12_verification.get("status") == "fail"
                    )
                    else "pass",
                }
        projection_semantics, s13_verification, s13_projection, s13_public_revision_state = (
            _apply_s13_post_deploy_accountability_projection(
                projection_semantics=projection_semantics,
                projection_payload=projection_payload,
            )
        )
        if s13_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        s13_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "s13_accountability_projection_verification.v1"
                        )
                    ),
                    "status": str(s13_verification.get("status") or "fail"),
                    "s13_post_deploy_accountability_projection": s13_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "s13_post_deploy_accountability_projection": s13_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or s13_verification.get("status") == "fail"
                    )
                    else "pass",
                }
        projection_semantics, s14_verification, s14_projection = _apply_s14_universality_projection(
            projection_semantics=projection_semantics,
            projection_payload=projection_payload,
        )
        if s14_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        s14_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "s14_universality_projection_verification.v1"
                        )
                    ),
                    "status": str(s14_verification.get("status") or "fail"),
                    "s14_universality_projection": s14_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "s14_universality_projection": s14_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or s14_verification.get("status") == "fail"
                    )
                    else "pass",
                }
        projection_semantics, g3_verification, g3_projection = (
            _apply_layer3_g3_analytics_search_projection(
                projection_semantics=projection_semantics,
                projection_payload=projection_payload,
            )
        )
        if g3_verification is not None:
            if projection_contract_verification is None:
                projection_contract_verification = {
                    "schema_version": str(
                        g3_verification.get("consumer_contract_ref")
                        or (
                            "policyos.runtime.policy_design_case."
                            "layer3_g3_projection_verification.v1"
                        )
                    ),
                    "status": str(g3_verification.get("status") or "fail"),
                    "layer3_g3_analytics_search_projection": g3_verification,
                }
            else:
                projection_contract_verification = {
                    **projection_contract_verification,
                    "layer3_g3_analytics_search_projection": g3_verification,
                    "status": "fail"
                    if (
                        projection_contract_verification.get("status") == "fail"
                        or g3_verification.get("status") == "fail"
                    )
                    else "pass",
                }
    _assert_public_claim_omissions_manifested(sanitized_artifacts, projection_semantics)
    if projection_semantics is not None:
        projection_semantics, projection_extensions = _split_projection_extensions(
            projection_semantics
        )
        (
            projection_semantics,
            projection_contract_verification,
            projection_redactions,
        ) = _redact_and_verify_public_projection(
            projection_semantics,
            previous_verification=projection_contract_verification,
            runtime_pdc_graph=runtime_pdc_graph,
        )
        redactions.extend(projection_redactions)
    exported_public_revision_states = list(public_revision_states)
    if s13_public_revision_state is not None:
        exported_public_revision_states.append(s13_public_revision_state)
    bundle = {
        "schema_version": PUBLIC_EXPORT_SCHEMA_VERSION,
        "generated_at": (generated_at or datetime.now(UTC)).replace(microsecond=0).isoformat(),
        "run_id": run_id,
        "title": title or "Public export bundle",
        "public_export_classification": "public_redacted_projection",
        "evidence_class": "redacted_derived",
        "authority_role": "projection_only",
        "provenance_kind": "runtime_projection",
        "redaction_policy_ref": PUBLIC_EXPORT_REDACTION_POLICY_REF,
        "allowed_scorecard_authority_role": "not_authoritative",
        "allowed_approval_authority_role": "not_authoritative",
        "official_use_limits": dict(_OFFICIAL_USE_LIMITS),
        "artifacts": sanitized_artifacts,
        **(
            {"runtime_truth_preservation": _copy_mapping(runtime_truth_preservation)}
            if runtime_truth_preservation is not None
            else {}
        ),
        "semantic_audit": {
            "artifact_keys": sorted(str(key) for key in sanitized_artifacts),
            "authority_projection_count": len(authority_projections),
            "authority_projections": authority_projections,
            "runtime_orchestration_continuity": orchestration_continuity,
            "recourse_pointer": recourse_pointer,
            "rule_evolution_annotations": rule_evolution_annotations,
            "public_revision_states": exported_public_revision_states,
            "s10_forecast_projection": s10_projection,
            "s10_forecast_projection_contract_verification": s10_verification,
            "s11_predictive_projection": s11_projection,
            "s11_predictive_projection_contract_verification": s11_verification,
            "s12_resource_projection": s12_projection,
            "s12_resource_projection_contract_verification": s12_verification,
            "s14_universality_projection": s14_projection,
            "s14_universality_projection_contract_verification": s14_verification,
            "layer3_g3_analytics_search_projection": g3_projection,
            "layer3_g3_analytics_search_projection_contract_verification": (g3_verification),
            "authority_surface_decisions": public_authority_surface_decisions,
            "omission_manifest": (
                _copy_public_sequence(
                    projection_semantics.get("omission_manifest", []),
                    field="omission_manifest",
                )
                if projection_semantics is not None
                else []
            ),
            "audit_refs": (
                _copy_public_sequence(
                    projection_semantics.get("audit_refs", []),
                    field="audit_refs",
                )
                if projection_semantics is not None
                else []
            ),
            "projection_contract_verification": projection_contract_verification,
            "secret_pii_scan_reports": secret_pii_scan_reports,
            "strangle_receipts": [sanitizer_strangle_receipt],
        },
        "redaction_summary": {
            "redaction_policy_ref": PUBLIC_EXPORT_REDACTION_POLICY_REF,
            "redacted_path_count": len(redactions),
            "erased_paths": sorted({item["path"] for item in redactions}),
            "upserted_redactions": redactions,
            "strangle_receipt": sanitizer_strangle_receipt,
        },
    }
    if s13_projection is not None or s13_verification is not None:
        semantic_audit = dict(bundle["semantic_audit"])
        semantic_audit["s13_post_deploy_accountability_projection"] = s13_projection
        semantic_audit["s13_post_deploy_accountability_projection_contract_verification"] = (
            s13_verification
        )
        bundle["semantic_audit"] = semantic_audit
    if projection_extensions:
        semantic_audit = dict(bundle["semantic_audit"])
        missing_projection_extensions = _unrepresented_projection_extensions(
            projection_extensions,
            semantic_audit,
        )
        if missing_projection_extensions:
            semantic_audit["projection_extensions"] = missing_projection_extensions
        bundle["semantic_audit"] = semantic_audit
    semantic_audit_value = bundle.get("semantic_audit")
    if isinstance(semantic_audit_value, Mapping):
        audit_redactions: list[dict[str, str]] = []
        redacted_audit = _redact_tenant_private_refs(
            semantic_audit_value,
            path="semantic_audit",
            redactions=audit_redactions,
        )
        if not isinstance(redacted_audit, Mapping):
            raise PublicExportRedactionError(
                "public_export_semantic_audit_invalid",
                "Redacted semantic audit must preserve its mapping shape.",
            )
        bundle["semantic_audit"] = _copy_mapping(redacted_audit)
        if audit_redactions:
            redaction_summary_value = bundle.get("redaction_summary")
            if not isinstance(redaction_summary_value, Mapping):
                raise PublicExportRedactionError(
                    "public_export_redaction_summary_invalid",
                    "Semantic-audit redaction requires a valid bundle redaction summary.",
                )
            redaction_summary = _copy_mapping(redaction_summary_value)
            existing_redactions_value = redaction_summary.get("upserted_redactions")
            existing_redactions = (
                [
                    _copy_mapping(item)
                    for item in existing_redactions_value
                    if isinstance(item, Mapping)
                ]
                if isinstance(existing_redactions_value, list)
                else []
            )
            existing_redactions.extend(audit_redactions)
            redaction_summary["upserted_redactions"] = existing_redactions
            redaction_summary["redacted_path_count"] = len(existing_redactions)
            redaction_summary["erased_paths"] = sorted(
                {str(item.get("path")) for item in existing_redactions if isinstance(item, Mapping)}
            )
            bundle["redaction_summary"] = redaction_summary
    if projection_semantics is not None:
        bundle["projection_semantics"] = projection_semantics
    bundle = _normalize_public_export_mapping(bundle, field="public_export_bundle")
    complete_sanitizer = PromptSanitizer()
    complete_scan = scan_secret_and_pii(
        bundle,
        scope="dashboard/public/export packets",
        artifact_ref_or_route="public-export://complete-bundle",
        sanitizer=complete_sanitizer,
        redact=True,
        block_on_findings=False,
    )
    if not isinstance(complete_scan.redacted_payload, Mapping):
        raise PublicExportRedactionError(
            "public_export_complete_scan_invalid_payload",
            "Canonical complete-bundle scan did not preserve public export mapping shape.",
        )
    complete_bundle = _copy_mapping(complete_scan.redacted_payload)
    complete_scan_redaction_values = _verified_redaction_values(
        bundle,
        complete_bundle,
        sanitizer=complete_sanitizer,
    )
    complete_audit = complete_bundle.get("semantic_audit")
    complete_summary = complete_bundle.get("redaction_summary")
    if not isinstance(complete_audit, Mapping) or not isinstance(complete_summary, Mapping):
        raise PublicExportRedactionError(
            "public_export_complete_scan_receipt_missing",
            "Complete-bundle redaction receipts are missing or malformed.",
        )
    audit = _copy_mapping(complete_audit)
    existing_reports = audit.get("secret_pii_scan_reports")
    scan_reports = (
        [_copy_mapping(item) for item in existing_reports if isinstance(item, Mapping)]
        if isinstance(existing_reports, list)
        else []
    )
    scan_reports.extend(report.model_dump(mode="json") for report in complete_scan.reports)
    audit["secret_pii_scan_reports"] = scan_reports
    complete_bundle["semantic_audit"] = audit
    summary = _copy_mapping(complete_summary)
    redactions_value = summary.get("upserted_redactions")
    redactions = (
        [_copy_mapping(item) for item in redactions_value if isinstance(item, Mapping)]
        if isinstance(redactions_value, list)
        else []
    )
    redactions.extend(
        {
            "path": f"complete_bundle_redaction:{index}",
            "reason": _canonical_redaction_reason(placeholder),
        }
        for index, placeholder in enumerate(sorted(complete_sanitizer.placeholder_map()), start=1)
    )
    summary["redacted_path_count"] = len(redactions)
    summary["erased_paths"] = sorted({item["path"] for item in redactions})
    summary["upserted_redactions"] = redactions
    complete_bundle["redaction_summary"] = summary
    scanned_projection = complete_bundle.get("projection_semantics")
    if isinstance(scanned_projection, Mapping):
        scanned_audit = complete_bundle.get("semantic_audit")
        previous_projection_verification = (
            scanned_audit.get("projection_contract_verification")
            if isinstance(scanned_audit, Mapping)
            else None
        )
        scanner_projection_paths = frozenset(
            path[1:]
            for path in complete_scan_redaction_values
            if path and path[0] == "projection_semantics"
        )
        (
            final_projection,
            final_projection_verification,
            projection_redactions,
        ) = _redact_and_verify_public_projection(
            scanned_projection,
            previous_verification=(
                previous_projection_verification
                if isinstance(previous_projection_verification, Mapping)
                else None
            ),
            runtime_pdc_graph=runtime_pdc_graph,
            scanner_redaction_paths=scanner_projection_paths,
        )
        summary_redactions = summary.get("upserted_redactions")
        if not isinstance(summary_redactions, list):
            summary_redactions = []
        summary_redactions.extend(projection_redactions)
        summary["upserted_redactions"] = summary_redactions
        summary["redacted_path_count"] = len(summary_redactions)
        summary["erased_paths"] = sorted(
            {str(item.get("path")) for item in summary_redactions if isinstance(item, Mapping)}
        )
        complete_bundle["redaction_summary"] = summary
        if final_projection is None:
            complete_bundle.pop("projection_semantics", None)
        else:
            complete_bundle["projection_semantics"] = final_projection
        final_audit = _copy_mapping(scanned_audit) if isinstance(scanned_audit, Mapping) else {}
        final_audit["projection_contract_verification"] = final_projection_verification
        tenant_private_paths = frozenset(
            _text(item.get("path"))
            for item in summary_redactions
            if isinstance(item, Mapping)
            and item.get("reason") == "tenant_private_ref"
            and _text(item.get("path")).startswith("semantic_audit.")
        )
        scanner_audit_paths = frozenset(
            path for path in complete_scan_redaction_values if path and path[0] == "semantic_audit"
        )
        final_audit, final_projection = _reverify_final_public_audit(
            final_audit,
            projection=final_projection,
            runtime_pdc_graph=runtime_pdc_graph,
            tenant_private_paths=tenant_private_paths,
            scanner_redaction_paths=scanner_audit_paths,
        )
        if final_projection is None:
            complete_bundle.pop("projection_semantics", None)
        else:
            complete_bundle["projection_semantics"] = final_projection
        complete_bundle["semantic_audit"] = final_audit
    else:
        scanned_audit = complete_bundle.get("semantic_audit")
        if not isinstance(scanned_audit, Mapping):
            raise PublicExportRedactionError(
                "public_export_final_audit_invalid",
                "Final public audit must remain a mapping after complete-bundle scanning.",
            )
        final_audit = _copy_mapping(scanned_audit)
        existing_projection_verification = final_audit.get("projection_contract_verification")
        if isinstance(existing_projection_verification, Mapping):
            final_audit["projection_contract_verification"] = _copy_mapping(
                existing_projection_verification
            )
        tenant_private_paths = frozenset(
            _text(item.get("path"))
            for item in redactions
            if isinstance(item, Mapping)
            and item.get("reason") == "tenant_private_ref"
            and _text(item.get("path")).startswith("semantic_audit.")
        )
        scanner_audit_paths = frozenset(
            path for path in complete_scan_redaction_values if path and path[0] == "semantic_audit"
        )
        final_audit, _ = _reverify_final_public_audit(
            final_audit,
            projection=None,
            runtime_pdc_graph=runtime_pdc_graph,
            tenant_private_paths=tenant_private_paths,
            scanner_redaction_paths=scanner_audit_paths,
        )
        complete_bundle.pop("projection_semantics", None)
        complete_bundle["semantic_audit"] = final_audit
    final_scan = scan_secret_and_pii(
        _complete_scan_verification_view(
            complete_bundle,
            verified_redaction_values=complete_scan_redaction_values,
        ),
        scope="dashboard/public/export packets",
        artifact_ref_or_route=f"public-export://{run_id}/complete-bundle-final",
        sanitizer=PromptSanitizer(),
        redact=False,
        block_on_findings=True,
    )
    if final_scan.has_findings:
        raise PublicExportRedactionError(
            "public_export_complete_scan_residual",
            "Sensitive material remained after complete-bundle redaction.",
        )
    complete_bundle = _normalize_public_export_mapping(
        complete_bundle,
        field="public_export_bundle",
    )
    assert_public_export_official_use_limits(complete_bundle)
    final_projection_value = complete_bundle.get("projection_semantics")
    if isinstance(final_projection_value, Mapping):
        PolicyDesignCaseProjection.model_validate(final_projection_value)
    _assert_no_tenant_private_ref_leak(complete_bundle, tenant_private_refs)
    return complete_bundle


def _verified_redaction_values(
    original: object,
    redacted: object,
    *,
    sanitizer: PromptSanitizer,
) -> dict[tuple[str | int, ...], tuple[object, str, tuple[str, ...]]]:
    """Bind generated redaction markers to their changed source paths and values."""

    generated_placeholders = tuple(sorted(sanitizer.placeholder_map()))
    replacements: dict[tuple[str | int, ...], tuple[object, str, tuple[str, ...]]] = {}

    def visit(
        before: object,
        after: object,
        path: tuple[str | int, ...],
    ) -> None:
        if isinstance(after, str):
            markers = tuple(marker for marker in generated_placeholders if marker in after)
            if before != after and markers:
                replacements[path] = (before, after, markers)
            return
        if isinstance(before, dict) and isinstance(after, dict):
            for key, after_value in after.items():
                visit(before.get(key), after_value, (*path, str(key)))
            return
        if isinstance(before, list) and isinstance(after, list):
            for index, after_value in enumerate(after):
                before_value = before[index] if index < len(before) else None
                visit(before_value, after_value, (*path, index))
            return
        if isinstance(before, tuple) and isinstance(after, tuple):
            for index, after_value in enumerate(after):
                before_value = before[index] if index < len(before) else None
                visit(before_value, after_value, (*path, index))

    visit(original, redacted, ())
    return replacements


def _complete_scan_verification_view(
    value: object,
    *,
    verified_redaction_values: Mapping[
        tuple[str | int, ...],
        tuple[object, str, tuple[str, ...]],
    ],
) -> object:
    """Remove only same-pass markers from the exact values that received them."""

    def project(current: object, path: tuple[str | int, ...]) -> object:
        if isinstance(current, str):
            replacement = verified_redaction_values.get(path)
            if replacement is None or current != replacement[1]:
                return current
            verification_value = current
            for marker in replacement[2]:
                verification_value = verification_value.replace(marker, "")
            return verification_value
        if isinstance(current, dict):
            return {key: project(item, (*path, str(key))) for key, item in current.items()}
        if isinstance(current, list):
            return [project(item, (*path, index)) for index, item in enumerate(current)]
        if isinstance(current, tuple):
            return tuple(project(item, (*path, index)) for index, item in enumerate(current))
        return current

    return project(value, ())


def _scan_public_export_artifacts(
    *,
    run_id: str,
    artifacts: Mapping[str, object],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, str]], dict[str, object]]:
    sanitizer = PromptSanitizer()
    scan = scan_secret_and_pii(
        _copy_mapping(artifacts),
        scope="dashboard/public/export packets",
        artifact_ref_or_route=f"public-export://{run_id}",
        sanitizer=sanitizer,
        redact=True,
        block_on_findings=False,
    )
    if not isinstance(scan.redacted_payload, Mapping):
        raise PublicExportRedactionError(
            "public_export_secret_scan_invalid_payload",
            "Canonical secret/PII scan did not preserve public export mapping shape.",
        )
    private_ref_redactions: list[dict[str, str]] = []
    sanitized_artifacts = _redact_tenant_private_refs(
        scan.redacted_payload,
        path="artifacts",
        redactions=private_ref_redactions,
    )
    if not isinstance(sanitized_artifacts, Mapping):
        raise PublicExportRedactionError(
            "public_export_private_ref_scan_invalid_payload",
            "Private-ref scan did not preserve public export mapping shape.",
        )
    placeholder_map = sanitizer.placeholder_map()
    redactions = [
        {
            "path": f"canonical_redaction:{index}",
            "reason": _canonical_redaction_reason(placeholder),
        }
        for index, placeholder in enumerate(sorted(placeholder_map), start=1)
    ]
    redactions.extend(private_ref_redactions)
    return (
        _copy_mapping(sanitized_artifacts),
        [report.model_dump(mode="json") for report in scan.reports],
        redactions,
        _public_export_sanitizer_strangle_receipt(),
    )


def _redact_tenant_private_refs(
    value: object,
    *,
    path: str,
    redactions: list[dict[str, str]],
) -> object:
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for key, item in _iter_mapping_items(value):
            raw_key = str(key)
            public_key = _public_mapping_key(raw_key)
            if public_key != raw_key:
                redactions.append(
                    {
                        "path": f"{path}.{public_key}",
                        "reason": "tenant_private_ref",
                    }
                )
            sanitized[public_key] = _redact_tenant_private_refs(
                item,
                path=f"{path}.{public_key}",
                redactions=redactions,
            )
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _redact_tenant_private_refs(
                item,
                path=f"{path}[{index}]",
                redactions=redactions,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, str) and _is_tenant_private_ref(value):
        redactions.append({"path": path, "reason": "tenant_private_ref"})
        return {
            "redacted": True,
            "reason": "tenant_private_ref",
            "fingerprint": _fingerprint(value),
        }
    return value


def _is_tenant_private_ref(value: str) -> bool:
    text = value.strip()
    return any(pattern.fullmatch(text) for pattern in _TENANT_PRIVATE_REF_PATTERNS)


def _public_mapping_key(value: str) -> str:
    if not _is_tenant_private_ref(value):
        return value
    digest = hashlib.sha256(value.strip().encode("utf-8")).hexdigest()[:16]
    return f"[REDACTED_TENANT_PRIVATE_REF_KEY_{digest}]"


def _tenant_private_refs_in_payload(value: object) -> frozenset[str]:
    refs: set[str] = set()

    def collect(item: object) -> None:
        if isinstance(item, Mapping):
            for key, nested in _iter_mapping_items(item):
                collect(str(key))
                collect(nested)
            return
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for nested in item:
                collect(nested)
            return
        if isinstance(item, str) and _is_tenant_private_ref(item):
            refs.add(item.strip())

    collect(value)
    return frozenset(refs)


def _assert_no_tenant_private_ref_leak(
    value: object,
    tenant_private_refs: frozenset[str],
) -> None:
    if not tenant_private_refs:
        return

    def first_leak_path(item: object, *, path: str) -> str | None:
        if isinstance(item, Mapping):
            for key, nested in _iter_mapping_items(item):
                key_text = str(key)
                if any(ref in key_text for ref in tenant_private_refs):
                    return f"{path}.<key>"
                leak_path = first_leak_path(nested, path=f"{path}.{key_text}")
                if leak_path is not None:
                    return leak_path
            return None
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for index, nested in enumerate(item):
                leak_path = first_leak_path(nested, path=f"{path}[{index}]")
                if leak_path is not None:
                    return leak_path
            return None
        if isinstance(item, str) and any(ref in item for ref in tenant_private_refs):
            return path
        return None

    leak_path = first_leak_path(value, path="public_export")
    if leak_path is not None:
        raise PublicExportRedactionError(
            "public_export_tenant_private_ref_leak",
            f"Caller private-ref material survived at {leak_path}.",
        )


def _public_authority_surface_decisions(
    decisions: Sequence[tuple[str, AuthoritySurfaceDecision]],
    *,
    redactions: list[dict[str, str]],
) -> list[dict[str, object]]:
    projection = _redact_tenant_private_refs(
        [
            {
                "artifact_key": artifact_key,
                "decision": decision.model_dump(mode="json"),
            }
            for artifact_key, decision in decisions
        ],
        path="semantic_audit.authority_surface_decisions",
        redactions=redactions,
    )
    if not isinstance(projection, list) or not all(
        isinstance(item, Mapping) for item in projection
    ):
        raise PublicExportRedactionError(
            "public_export_authority_decision_scan_invalid_payload",
            "Private-ref scan did not preserve authority decision projection shape.",
        )
    return [_copy_mapping(item) for item in projection]


def _canonical_redaction_reason(placeholder: str) -> str:
    if "_EMAIL_" in placeholder:
        return "email:redacted_by_canonical_scanner"
    if "_KEYED_SECRET_" in placeholder:
        return "keyed_secret:redacted_by_canonical_scanner"
    return "secret_pii:redacted_by_canonical_scanner"


def _public_export_sanitizer_strangle_receipt() -> dict[str, object]:
    return {
        "predecessor_ref": (
            "runtime.quality.public_export._FORBIDDEN_*_TOKENS._sanitize_public_payload"
        ),
        "replacement_ref": "polisyos.core.llm.sanitization.scan_secret_and_pii",
        "disposition": "deleted_live_path_default_flipped_to_composed_gate",
        "default_before": "public export used a parallel deny-list sanitizer",
        "default_after": (
            "public export scans artifact inputs before semantic derivation and scans the "
            "complete returned bundle after authority projections and runtime truth are added; "
            "every artifact is also admitted through authority_surface_decision"
        ),
        "remaining_callers": [],
    }


def _authority_surface_decisions_for_public_export(
    artifacts: Mapping[str, object],
) -> list[tuple[str, AuthoritySurfaceDecision]]:
    decisions: list[tuple[str, AuthoritySurfaceDecision]] = []
    for key, artifact in _iter_mapping_items(artifacts):
        if not isinstance(artifact, Mapping):
            continue
        export_decision = authority_surface_decision(
            artifact,
            surface="export",
            artifact_ref_or_route=f"public-export://{key}",
            secret_pii_scope="dashboard/public/export packets",  # noqa: S106
            block_on_secret_findings=False,
            missing_authority_disposition="downgrade",
            missing_boundary_disposition="downgrade",
        )
        public_packet_decision = authority_surface_decision(
            artifact,
            surface="public_packet",
            artifact_ref_or_route=f"public-packet://{key}",
            secret_pii_scope="dashboard/public/export packets",  # noqa: S106
            block_on_secret_findings=False,
            missing_authority_disposition="downgrade",
            missing_boundary_disposition="downgrade",
        )
        for decision in (export_decision, public_packet_decision):
            decisions.append((str(key), decision))
    return decisions


def _apply_s14_universality_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object] | None]:
    if not _has_s14_universality_projection(projection_payload):
        return _copy_mapping(projection_semantics), None, None
    verification = verify_s14_universality_projection_consumer_contract(
        projections={"public": projection_payload},
    )
    if verification.get("status") != "pass":
        raise PublicExportRedactionError(
            _first_s14_issue_code(verification),
            "S14 universality projection consumer contract must pass before public release.",
        )
    public_projection = _copy_optional_public_mapping(
        verification.get("public_projection"), field="public_projection"
    )
    s14_projection = _copy_optional_public_mapping(
        verification.get("s14_universality_projection"), field="s14_universality_projection"
    )
    enriched = _copy_mapping(projection_semantics)
    may_not = _unique_texts(
        [
            *_text_list(enriched.get("may_not_be_used_for")),
            *_text_list(public_projection.get("may_not_be_used_for")),
            "production_rollout_authority",
            "production_recommendation",
            "recommendation_authority",
            "approval_authority",
            "claim_authority",
            "runtime_closeout_authority",
            "scorecard_authority",
            "aggregate_universal_score",
        ]
    )
    limitations = _unique_texts(
        [
            *_text_list(enriched.get("limitations")),
            public_projection.get("public_universality_limitation"),
            "S14 universality is projection-only and limited to the declared envelope.",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            s14_projection.get("s14_universality_assurance_ref"),
            s14_projection.get("universality_claim_gate_ref"),
            s14_projection.get("declared_operation_envelope_ref"),
            s14_projection.get("d4_corpus_track_coverage_ref"),
            s14_projection.get("expert_oracle_bootstrap_ref"),
            s14_projection.get("breadth_floor_config_ref"),
            s14_projection.get("universality_baseline_comparison_ref"),
            s14_projection.get("grounded_authority_coverage_ref"),
            s14_projection.get("evaluation_status_composition_ref"),
            s14_projection.get("axis_scorecard_ref"),
            s14_projection.get("sealed_battery_run_ref"),
            s14_projection.get("mechanism_generality_report_ref"),
            s14_projection.get("rule_version_ref"),
            *_text_list(s14_projection.get("skeptic_defeater_refs")),
            *_text_list(s14_projection.get("s9_projection_faithfulness_refs")),
        ]
    )
    source_state = _copy_optional_public_mapping(enriched.get("source_state"), field="source_state")
    source_state.update(
        {
            "s14_universality_assurance_ref": s14_projection.get("s14_universality_assurance_ref"),
            "s14_projection_policy": "reads_s14_universality_assurance_as_projection",
            "universality_claim_gate_ref": s14_projection.get("universality_claim_gate_ref"),
        }
    )
    enriched.update(
        {
            "authority_role": "projection_only",
            "universality_claim_disposition": public_projection.get(
                "universality_claim_disposition"
            ),
            "declared_operation_envelope_ref": public_projection.get(
                "declared_operation_envelope_ref"
            ),
            "s14_universality_assurance_ref": public_projection.get(
                "s14_universality_assurance_ref"
            ),
            "universality_claim_gate_ref": public_projection.get("universality_claim_gate_ref"),
            "d4_corpus_track_coverage_ref": public_projection.get("d4_corpus_track_coverage_ref"),
            "d4_corpus_track_coverage_status": public_projection.get(
                "d4_corpus_track_coverage_status"
            ),
            "d4_breadth_limitation_summary": public_projection.get("d4_breadth_limitation_summary"),
            "expert_oracle_bootstrap_ref": public_projection.get("expert_oracle_bootstrap_ref"),
            "expert_oracle_seed_only_layer_refs": public_projection.get(
                "expert_oracle_seed_only_layer_refs"
            ),
            "breadth_floor_config_ref": public_projection.get("breadth_floor_config_ref"),
            "breadth_floor_status": public_projection.get("breadth_floor_status"),
            "excluded_domain_refs": public_projection.get("excluded_domain_refs"),
            "universality_baseline_comparison_ref": public_projection.get(
                "universality_baseline_comparison_ref"
            ),
            "baseline_comparison_status": public_projection.get("baseline_comparison_status"),
            "grounded_authority_coverage_ref": public_projection.get(
                "grounded_authority_coverage_ref"
            ),
            "grounded_authority_status": public_projection.get("grounded_authority_status"),
            "evaluation_status_composition_ref": public_projection.get(
                "evaluation_status_composition_ref"
            ),
            "status_composition_limit_refs": public_projection.get("status_composition_limit_refs"),
            "axis_scorecard_ref": public_projection.get("axis_scorecard_ref"),
            "out_of_envelope_axis_refs": public_projection.get("out_of_envelope_axis_refs"),
            "not_tested_axis_refs": public_projection.get("not_tested_axis_refs"),
            "mechanism_generality_status": public_projection.get("mechanism_generality_status"),
            "sublinear_marginal_bespoke_cost_status": public_projection.get(
                "sublinear_marginal_bespoke_cost_status"
            ),
            "skeptic_defeater_statuses": public_projection.get("skeptic_defeater_statuses"),
            "s9_projection_faithfulness_refs": public_projection.get(
                "s9_projection_faithfulness_refs"
            ),
            "public_universality_limitation": public_projection.get(
                "public_universality_limitation"
            ),
            "may_not_be_used_for": may_not,
            "limitations": limitations,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "s14_universality_projection_contract_verification_status": (
                verification.get("status")
            ),
            "s14_universality_projection_contract_verification_ref": (
                verification.get("consumer_contract_ref")
            ),
        }
    )
    return enriched, verification, s14_projection


def _apply_s13_post_deploy_accountability_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[
    dict[str, object],
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
]:
    s13_projection = _s13_accountability_projection_record(projection_payload)
    if not s13_projection:
        return _copy_mapping(projection_semantics), None, None, None
    verification = verify_s13_post_deploy_accountability_projection_consumer_contract(
        projections={"public": s13_projection},
    )
    if verification.get("status") != "pass":
        raise PublicExportRedactionError(
            _first_s13_issue_code(verification),
            "S13 accountability projection consumer contract must pass before public release.",
        )
    revision_state = _s13_public_revision_state(projection_payload)
    public_projection = _copy_optional_public_mapping(
        verification.get("public_projection"), field="public_projection"
    )
    enriched = _copy_mapping(projection_semantics)
    accountability_note = _text(
        public_projection.get("public_accountability_note")
        or s13_projection.get("public_accountability_note")
    )
    may_not = _unique_texts(
        [
            *_text_list(enriched.get("may_not_be_used_for")),
            *_text_list(public_projection.get("may_not_be_used_for")),
            "current_evidence_slot",
            "pre_policy_evidence",
            "production_rollout_authority",
            "recommendation_authority",
            "approval_authority",
            "scorecard_authority",
            "s14_universality",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            s13_projection.get("accountability_posture_ref"),
            s13_projection.get("deployment_dossier_ref"),
            s13_projection.get("public_revision_state_ref"),
            s13_projection.get("public_accountability_note_ref"),
            s13_projection.get("rule_version_ref"),
            *_text_list(s13_projection.get("divergence_record_refs")),
            *_text_list(s13_projection.get("learning_update_proposal_refs")),
        ]
    )
    source_state = _copy_optional_public_mapping(enriched.get("source_state"), field="source_state")
    source_state.update(
        {
            "s13_accountability_posture_ref": s13_projection.get("accountability_posture_ref"),
            "s13_projection_policy": ("reads_post_deploy_accountability_posture_as_revision_note"),
            "s13_public_revision_state_ref": s13_projection.get("public_revision_state_ref"),
        }
    )
    enriched.update(
        {
            "public_accountability_note": accountability_note,
            "public_accountability_note_ref": s13_projection.get("public_accountability_note_ref"),
            "public_revision_state_ref": s13_projection.get("public_revision_state_ref"),
            "envelope_revision_direction": s13_projection.get("envelope_revision_direction"),
            "closed_case_historical_meaning": (
                s13_projection.get("closed_case_historical_meaning") or "preserved"
            ),
            "authority_role": "projection_only",
            "may_not_be_used_for": may_not,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "s13_post_deploy_accountability_projection_contract_verification_status": (
                verification.get("status")
            ),
            "s13_post_deploy_accountability_projection_contract_verification_ref": (
                verification.get("consumer_contract_ref")
            ),
        }
    )
    return enriched, verification, s13_projection, revision_state


def _apply_s12_resource_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object] | None]:
    s12_projection = _s12_resource_projection_record(projection_payload)
    if not s12_projection:
        return _copy_mapping(projection_semantics), None, None
    verification = verify_s12_resource_projection_consumer_contract(
        projections={"public": s12_projection},
    )
    if verification.get("status") != "pass":
        raise PublicExportRedactionError(
            _first_s12_issue_code(verification),
            "S12 resource projection consumer contract must pass before public release.",
        )
    public_projection = _copy_optional_public_mapping(
        verification.get("public_projection"), field="public_projection"
    )
    enriched = _copy_mapping(projection_semantics)
    growth_limitation = _text(
        public_projection.get("s12_public_growth_limitation")
        or s12_projection.get("s12_public_growth_limitation")
    )
    limitations = _unique_texts(
        [
            *_text_list(enriched.get("limitations")),
            growth_limitation,
            "S12 resource allocation remains allocation-only, not recommendation authority.",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            s12_projection.get("resource_allocation_policy_ref"),
            s12_projection.get("envelope_growth_ledger_ref"),
            s12_projection.get("growth_thermometer_ref"),
            s12_projection.get("rule_version_ref"),
            *_text_list(s12_projection.get("voi_allocation_refs")),
            *_text_list(s12_projection.get("residual_limitation_refs")),
        ]
    )
    may_not = _unique_texts(
        [
            *_text_list(enriched.get("may_not_be_used_for")),
            *_text_list(public_projection.get("may_not_be_used_for")),
            "production_authority",
            "production_recommendation",
            "publication_authority",
            "claim_authority",
            "closeout_authority",
            "recommendation_authority",
        ]
    )
    source_state = _copy_optional_public_mapping(enriched.get("source_state"), field="source_state")
    source_state.update(
        {
            "s12_resource_posture_ref": s12_projection.get("resource_allocation_policy_ref"),
            "s12_projection_policy": "reads_resource_economics_posture_as_constraint",
            "s12_explore_exploit_posture": s12_projection.get("explore_exploit_posture"),
        }
    )
    enriched.update(
        {
            "explore_exploit_posture": s12_projection.get("explore_exploit_posture"),
            "override_rate_trend": s12_projection.get("override_rate_trend"),
            "reuse_rate_trend": s12_projection.get("reuse_rate_trend"),
            "s12_public_growth_limitation": growth_limitation,
            "authority_role": "projection_only",
            "may_not_be_used_for": may_not,
            "limitations": limitations,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "s12_resource_projection_contract_verification_status": verification.get("status"),
            "s12_resource_projection_contract_verification_ref": verification.get(
                "consumer_contract_ref"
            ),
        }
    )
    return enriched, verification, s12_projection


def _apply_s11_predictive_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object] | None]:
    s11_projection = _s11_predictive_projection_record(projection_payload)
    if not s11_projection:
        return _copy_mapping(projection_semantics), None, None
    verification = verify_s11_predictive_projection_consumer_contract(
        projections={"public": s11_projection},
    )
    if verification.get("status") != "pass":
        raise PublicExportRedactionError(
            _first_s11_issue_code(verification),
            "S11 predictive projection consumer contract must pass before public release.",
        )
    public_projection = _copy_optional_public_mapping(
        verification.get("public_projection"), field="public_projection"
    )
    enriched = _copy_mapping(projection_semantics)
    s11_limitation = _text(
        public_projection.get("s11_public_limitation")
        or s11_projection.get("s11_public_limitation")
    )
    limitations = _unique_texts(
        [
            *_text_list(enriched.get("limitations")),
            s11_limitation,
            "S11 predictive relaxation remains calibration-limited and not authority.",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            s11_projection.get("s11_predictive_posture_ref"),
            s11_projection.get("proof_carrying_analytics_ref"),
            s11_projection.get("ir_analytics_bridge_ref"),
            s11_projection.get("rule_version_ref"),
            *_text_list(s11_projection.get("predictive_axis_upgrade_refs")),
            *_text_list(s11_projection.get("residual_limitation_refs")),
        ]
    )
    may_not = _unique_texts(
        [
            *_text_list(enriched.get("may_not_be_used_for")),
            *_text_list(public_projection.get("may_not_be_used_for")),
            "production_recommendation",
            "production_claim_authority",
            "publication_authority",
            "claim_authority",
            "runtime_closeout_authority",
        ]
    )
    source_state = _copy_optional_public_mapping(enriched.get("source_state"), field="source_state")
    source_state.update(
        {
            "s11_predictive_posture_ref": s11_projection.get("s11_predictive_posture_ref"),
            "s11_projection_policy": "reads_predictive_posture_as_constraint",
            "s11_effective_predictive_posture": s11_projection.get("effective_predictive_posture"),
        }
    )
    enriched.update(
        {
            "effective_predictive_posture": s11_projection.get("effective_predictive_posture"),
            "s11_public_limitation": s11_limitation,
            "authority_role": "projection_only",
            "may_not_be_used_for": may_not,
            "limitations": limitations,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "s11_predictive_projection_contract_verification_status": (verification.get("status")),
            "s11_predictive_projection_contract_verification_ref": verification.get(
                "consumer_contract_ref"
            ),
        }
    )
    return enriched, verification, s11_projection


def _apply_layer3_g3_analytics_search_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object] | None]:
    g3_projection = _layer3_g3_analytics_search_projection_record(projection_payload)
    if not g3_projection:
        return _copy_mapping(projection_semantics), None, None
    verification = {
        "consumer_contract_ref": (
            "policyos.runtime.policy_design_case.layer3_g3_public_projection_verification.v1"
        ),
        "status": "pass",
        "public_projection": g3_projection,
    }
    enriched = _copy_mapping(projection_semantics)
    may_not = _unique_texts(
        [
            *_text_list(enriched.get("may_not_be_used_for")),
            *_text_list(g3_projection.get("may_not_use_for")),
            "claim_authority",
            "policy_recommendation",
            "closeout_authority",
            "publication_authority",
            "search_hit_as_certificate",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            g3_projection.get("certificate_resolution_report_ref"),
            *_text_list(g3_projection.get("search_ledger_refs")),
            *_text_list(g3_projection.get("redacted_search_frontier_refs")),
            *_text_list(g3_projection.get("proof_carrying_analytics_refs")),
            *_text_list(g3_projection.get("ir_analytics_bridge_refs")),
            *_text_list(g3_projection.get("method_requirement_refs")),
            *_text_list(g3_projection.get("s11_predictive_posture_refs")),
        ]
    )
    source_state = _copy_optional_public_mapping(enriched.get("source_state"), field="source_state")
    source_state.update(
        {
            "layer3_g3_projection_policy": "reads_projection_only_search_resolution_refs",
            "layer3_g3_certificate_resolution_report_ref": g3_projection.get(
                "certificate_resolution_report_ref"
            ),
            "layer3_g3_public_export_projection_ref": g3_projection.get("projection_ref"),
        }
    )
    enriched.update(
        {
            "layer3_g3_public_export_projection_status": g3_projection.get("status"),
            "layer3_g3_certificate_resolution_report_ref": g3_projection.get(
                "certificate_resolution_report_ref"
            ),
            "layer3_g3_resolved_certificate_count": g3_projection.get("resolved_certificate_count"),
            "layer3_g3_blocked_certificate_count": g3_projection.get("blocked_certificate_count"),
            "authority_role": "projection_only",
            "may_not_be_used_for": may_not,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "layer3_g3_analytics_search_projection_contract_verification_status": (
                verification["status"]
            ),
            "layer3_g3_analytics_search_projection_contract_verification_ref": (
                verification["consumer_contract_ref"]
            ),
        }
    )
    return enriched, verification, g3_projection


def _apply_s10_forecast_projection(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object] | None]:
    s10_projection = _s10_forecast_projection_record(projection_payload)
    if not s10_projection:
        return _copy_mapping(projection_semantics), None, None
    missing_refs = _s10_missing_machine_export_refs(s10_projection)
    if missing_refs:
        raise PublicExportRedactionError(
            "s10_machine_export_requires_calibration_and_source_refs",
            "S10 public export requires reconstructable calibration, source, and method refs.",
        )
    verification = verify_s10_forecast_projection_consumer_contract(
        projections={"public": s10_projection},
    )
    if verification.get("status") != "pass":
        raise PublicExportRedactionError(
            _first_s10_issue_code(verification),
            "S10 forecast projection consumer contract must pass before public release.",
        )
    enriched = _copy_mapping(projection_semantics)
    limitations = _unique_texts(
        [
            *_text_list(enriched.get("limitations")),
            *_text_list(s10_projection.get("limitations")),
            s10_projection.get("forecast_authority_disposition_reason"),
            "forecast support only; not production recommendation authority",
        ]
    )
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            s10_projection.get("forecast_support_ref"),
            s10_projection.get("forecast_calibration_record_ref"),
            s10_projection.get("design_graph_ref"),
            s10_projection.get("prediction_context_ref"),
            s10_projection.get("source_contract_ref"),
            s10_projection.get("method_validity_ref"),
            s10_projection.get("credible_evaluation_evidence_ref"),
            s10_projection.get("rule_version_ref"),
        ]
    )
    source_state = _copy_optional_public_mapping(enriched.get("source_state"), field="source_state")
    source_state.update(
        {
            "s10_forecast_support_ref": s10_projection.get("forecast_support_ref"),
            "s10_design_graph_ref": s10_projection.get("design_graph_ref"),
            "s10_prediction_context_ref": s10_projection.get("prediction_context_ref"),
            "s10_projection_policy": "reads_forecast_support_posture",
        }
    )
    enriched.update(
        {
            "forecast_tier": s10_projection.get("forecast_tier"),
            "observable_subset_calibration_status": s10_projection.get(
                "observable_subset_calibration_status"
            ),
            "uncertainty_interval_refs": list(
                _as_sequence(s10_projection.get("uncertainty_interval_refs"))
            ),
            "limitations": limitations,
            "audit_refs": audit_refs,
            "source_state": source_state,
            "s10_forecast_projection_contract_verification_status": verification.get("status"),
            "s10_forecast_projection_contract_verification_ref": verification.get(
                "consumer_contract_ref"
            ),
        }
    )
    return enriched, verification, s10_projection


def _s10_forecast_projection_record(
    projection_payload: Mapping[str, object],
) -> dict[str, object]:
    if not (
        _text(projection_payload.get("forecast_support_ref"))
        or _text(projection_payload.get("forecast_tier"))
    ):
        return {}
    authority_boundary = _copy_public_mapping_if_present(
        projection_payload.get("authority_boundary"),
        field="authority_boundary",
    )
    welfare_comparison = _copy_public_mapping_if_present(
        projection_payload.get("welfare_comparison"),
        field="welfare_comparison",
    )
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_forecast_support_posture",
        "forecast_support_ref": _text(projection_payload.get("forecast_support_ref")),
        "forecast_tier": _text(projection_payload.get("forecast_tier")),
        "forecast_authority_disposition_reason": _text(
            projection_payload.get("forecast_authority_disposition_reason")
        ),
        "forecast_support_label": _text(projection_payload.get("forecast_support_label")),
        "forecast_calibration_record_ref": _text(
            projection_payload.get("forecast_calibration_record_ref")
        ),
        "observable_subset_calibration_status": _text(
            projection_payload.get("observable_subset_calibration_status")
            or projection_payload.get("calibration_status")
            or projection_payload.get("forecast_calibration_status")
        ),
        "design_graph_ref": _text(projection_payload.get("design_graph_ref")),
        "prediction_context_ref": _text(projection_payload.get("prediction_context_ref")),
        "policy_context_ref": _text(projection_payload.get("policy_context_ref")),
        "source_contract_ref": _text(projection_payload.get("source_contract_ref")),
        "method_validity_ref": _text(projection_payload.get("method_validity_ref")),
        "credible_evaluation_evidence_ref": _text(
            projection_payload.get("credible_evaluation_evidence_ref")
        ),
        "uncertainty_interval_refs": _text_list(
            projection_payload.get("uncertainty_interval_refs")
        ),
        "welfare_comparison": welfare_comparison,
        "authority_boundary": authority_boundary,
        "limitations": _text_list(projection_payload.get("limitations")),
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection_payload.get("may_not_be_used_for")),
                *_text_list(projection_payload.get("may_not_use_for")),
            ]
        ),
        "rule_version_ref": _text(projection_payload.get("rule_version_ref")),
    }


def _s11_predictive_projection_record(
    projection_payload: Mapping[str, object],
) -> dict[str, object]:
    if not (
        _text(projection_payload.get("s11_predictive_posture_ref"))
        or _text(projection_payload.get("predictive_knowledge_ref"))
        or _as_sequence(projection_payload.get("predictive_axis_rows"))
    ):
        return {}
    authority_boundary = _copy_public_mapping_if_present(
        projection_payload.get("authority_boundary"),
        field="authority_boundary",
    )
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_predictive_posture_as_constraint",
        "s11_predictive_posture_ref": _text(
            projection_payload.get("s11_predictive_posture_ref")
            or projection_payload.get("predictive_knowledge_ref")
        ),
        "effective_predictive_posture": _text(
            projection_payload.get("effective_predictive_posture")
            or projection_payload.get("predictive_authority_status")
        ),
        "predictive_axis_upgrade_refs": _text_list(
            projection_payload.get("predictive_axis_upgrade_refs")
            or projection_payload.get("axis_upgrade_refs")
        ),
        "predictive_axis_rows": [
            _copy_mapping(row)
            for row in _as_sequence(projection_payload.get("predictive_axis_rows"))
            if isinstance(row, Mapping)
        ],
        "per_axis_predictive_calibration_status": _text(
            projection_payload.get("per_axis_predictive_calibration_status")
        ),
        "per_axis_predictive_calibration_threshold_ref": _text(
            projection_payload.get("per_axis_predictive_calibration_threshold_ref")
        ),
        "proof_carrying_analytics_ref": _text(
            projection_payload.get("proof_carrying_analytics_ref")
        ),
        "ir_analytics_bridge_ref": _text(projection_payload.get("ir_analytics_bridge_ref")),
        "residual_limitation_refs": _text_list(projection_payload.get("residual_limitation_refs")),
        "weakest_boundary_reason": _text(projection_payload.get("weakest_boundary_reason")),
        "s11_public_limitation": _text(projection_payload.get("s11_public_limitation")),
        "authority_boundary": authority_boundary,
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection_payload.get("may_not_be_used_for")),
                *_text_list(projection_payload.get("may_not_use_for")),
            ]
        ),
        "rule_version_ref": _text(projection_payload.get("rule_version_ref")),
    }


def _layer3_g3_analytics_search_projection_record(
    projection_payload: Mapping[str, object],
) -> dict[str, object]:
    raw = projection_payload.get("layer3_g3_public_export_projection")
    if not isinstance(raw, Mapping):
        return {}
    authority_boundary = _copy_public_mapping_if_present(
        raw.get("authority_boundary"),
        field="authority_boundary",
    )
    may_not = _unique_texts(
        [
            *_text_list(raw.get("may_not_use_for")),
            *_text_list(raw.get("may_not_be_used_for")),
            *_text_list(authority_boundary.get("may_not_use_for")),
        ]
    )
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_layer3_g3_resolution_status_as_audit_refs",
        "projection_ref": _text(raw.get("projection_ref")),
        "status": _text(raw.get("status")) or "unknown",
        "certificate_resolution_report_ref": _text(raw.get("certificate_resolution_report_ref")),
        "search_ledger_refs": _text_list(raw.get("search_ledger_refs")),
        "redacted_search_frontier_refs": _text_list(raw.get("redacted_search_frontier_refs")),
        "proof_carrying_analytics_refs": _text_list(raw.get("proof_carrying_analytics_refs")),
        "ir_analytics_bridge_refs": _text_list(raw.get("ir_analytics_bridge_refs")),
        "method_requirement_refs": _text_list(raw.get("method_requirement_refs")),
        "s11_predictive_posture_refs": _text_list(raw.get("s11_predictive_posture_refs")),
        "resolved_certificate_count": _int(raw.get("resolved_certificate_count")),
        "blocked_certificate_count": _int(raw.get("blocked_certificate_count")),
        "authority_boundary": authority_boundary,
        "may_not_use_for": may_not,
        "raw_proof_payload_exported": False,
        "raw_cas_manifest_exported": False,
        "raw_query_ledger_exported": False,
    }


def _s12_resource_projection_record(
    projection_payload: Mapping[str, object],
) -> dict[str, object]:
    if not (
        _text(projection_payload.get("resource_allocation_policy_ref"))
        or _text(projection_payload.get("s12_resource_posture_ref"))
        or _text(projection_payload.get("explore_exploit_posture"))
    ):
        return {}
    authority_boundary = _copy_public_mapping_if_present(
        projection_payload.get("authority_boundary"),
        field="authority_boundary",
    )
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_resource_economics_posture_as_constraint",
        "s12_resource_posture_ref": _text(projection_payload.get("s12_resource_posture_ref")),
        "resource_allocation_policy_ref": _text(
            projection_payload.get("resource_allocation_policy_ref")
            or projection_payload.get("s12_resource_posture_ref")
        ),
        "explore_exploit_posture": _text(projection_payload.get("explore_exploit_posture")),
        "explore_exploit_dial_ref": _text(projection_payload.get("explore_exploit_dial_ref")),
        "voi_allocation_refs": _text_list(projection_payload.get("voi_allocation_refs")),
        "voi_site_count": _int(projection_payload.get("voi_site_count")),
        "typed_budget_refs": _text_list(projection_payload.get("typed_budget_refs")),
        "pareto_archive_ref": _text(projection_payload.get("pareto_archive_ref")),
        "envelope_growth_ledger_ref": _text(projection_payload.get("envelope_growth_ledger_ref")),
        "growth_thermometer_ref": _text(projection_payload.get("growth_thermometer_ref")),
        "override_rate_trend": _text(projection_payload.get("override_rate_trend")),
        "reuse_rate_trend": _text(projection_payload.get("reuse_rate_trend")),
        "held_out_status": _text(projection_payload.get("held_out_status")),
        "resource_allocation_disposition": _text(
            projection_payload.get("resource_allocation_disposition")
        ),
        "residual_limitation_refs": _text_list(projection_payload.get("residual_limitation_refs")),
        "s12_public_growth_limitation": _text(
            projection_payload.get("s12_public_growth_limitation")
        ),
        "authority_boundary": authority_boundary,
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection_payload.get("may_not_be_used_for")),
                *_text_list(projection_payload.get("may_not_use_for")),
            ]
        ),
        "rule_version_ref": _text(projection_payload.get("rule_version_ref")),
    }


def _s13_accountability_projection_record(
    projection_payload: Mapping[str, object],
) -> dict[str, object]:
    if not (
        _text(projection_payload.get("accountability_posture_ref"))
        or _text(projection_payload.get("public_accountability_note_ref"))
    ):
        return {}
    authority_boundary = _copy_public_mapping_if_present(
        projection_payload.get("authority_boundary"),
        field="authority_boundary",
    )
    return {
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_s13_post_deploy_accountability_posture",
        "accountability_posture_ref": _text(projection_payload.get("accountability_posture_ref")),
        "deployment_dossier_ref": _text(projection_payload.get("deployment_dossier_ref")),
        "divergence_record_refs": _text_list(projection_payload.get("divergence_record_refs")),
        "learning_update_proposal_refs": _text_list(
            projection_payload.get("learning_update_proposal_refs")
        ),
        "envelope_revision_ref": _text(projection_payload.get("envelope_revision_ref")),
        "certified_envelope_delta_ref": _text(
            projection_payload.get("certified_envelope_delta_ref")
        ),
        "assurance_case_delta_ref": _text(projection_payload.get("assurance_case_delta_ref")),
        "attribution_status": _text(projection_payload.get("attribution_status")),
        "attribution_classes": _text_list(projection_payload.get("attribution_classes")),
        "learning_change_control_classes": _text_list(
            projection_payload.get("learning_change_control_classes")
        ),
        "lifecycle_reissue_disposition": _text(
            projection_payload.get("lifecycle_reissue_disposition")
        ),
        "envelope_revision_direction": _text(projection_payload.get("envelope_revision_direction")),
        "assurance_case_change": _text(projection_payload.get("assurance_case_change")),
        "mape_k_trace_ref": _text(projection_payload.get("mape_k_trace_ref")),
        "public_revision_state_ref": _text(projection_payload.get("public_revision_state_ref")),
        "public_accountability_note_ref": _text(
            projection_payload.get("public_accountability_note_ref")
        ),
        "public_accountability_note": _text(projection_payload.get("public_accountability_note")),
        "closed_case_historical_meaning": _text(
            projection_payload.get("closed_case_historical_meaning")
        ),
        "authority_boundary": authority_boundary,
        "may_not_be_used_for": _unique_texts(
            [
                *_text_list(projection_payload.get("may_not_be_used_for")),
                *_text_list(projection_payload.get("may_not_use_for")),
            ]
        ),
        "rule_version_ref": _text(projection_payload.get("rule_version_ref")),
    }


def _s13_public_revision_state(
    projection_payload: Mapping[str, object],
) -> dict[str, object] | None:
    revision_state = projection_payload.get("public_revision_state")
    if not isinstance(revision_state, Mapping):
        return None
    state = _copy_mapping(revision_state)
    claim_ids = _unique_texts(
        [
            *_text_list(state.get("affected_claim_ids")),
            *_text_list(state.get("unaffected_claim_ids")),
        ]
    )
    if not claim_ids:
        claim_ids = ["unknown_claim"]
    validation_state = dict(state)
    if validation_state.get("silent_upgrade_allowed") is not False:
        validation_state["authority_role"] = "projection_only"
    report = {
        "schema_version": LIFECYCLE_REISSUE_REPORT_SCHEMA_VERSION,
        "report_id": "s13-public-revision-state-validation",
        "case_id": "s13-post-deploy-accountability",
        "claim_ids": claim_ids,
        "event_impacts": [],
        "claim_revision_states": [],
        "public_revision_state": validation_state,
        "issues": [],
        "status": "review_required",
        "evidence_ref": _text(projection_payload.get("public_revision_state_ref"))
        or "projection_payload",
        "runtime_event_ref": _text(projection_payload.get("accountability_posture_ref"))
        or "projection_payload",
    }
    try:
        validate_lifecycle_reissue_report(report)
    except PolicyDesignLifecycleError as exc:
        raise PublicExportRedactionError(exc.code, str(exc)) from exc
    return state


def _s10_missing_machine_export_refs(
    s10_projection: Mapping[str, object],
) -> list[str]:
    required = (
        "forecast_calibration_record_ref",
        "design_graph_ref",
        "prediction_context_ref",
        "source_contract_ref",
        "method_validity_ref",
        "credible_evaluation_evidence_ref",
        "rule_version_ref",
    )
    missing = [key for key in required if not _text(s10_projection.get(key))]
    if not isinstance(s10_projection.get("authority_boundary"), Mapping):
        missing.append("authority_boundary")
    return missing


def _first_s10_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s10_forecast_projection_failed"


def _first_s11_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s11_predictive_projection_failed"


def _first_s12_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s12_resource_projection_failed"


def _first_s13_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s13_accountability_projection_failed"


def _first_s14_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s14_universality_projection_failed"


def _has_s14_universality_projection(payload: Mapping[str, object]) -> bool:
    return any(
        _text(payload.get(field_name))
        for field_name in (
            "s14_universality_assurance_ref",
            "universality_claim_gate_ref",
            "declared_operation_envelope_ref",
            "axis_scorecard_ref",
            "sealed_battery_run_ref",
        )
    )


def _apply_s9_projection_faithfulness(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None]:
    faithfulness = _s9_faithfulness_record(projection_payload)
    if not faithfulness:
        return _copy_mapping(projection_semantics), None
    verifier_payload = {
        **_copy_mapping(projection_semantics),
        "projection_policy": "reads_canonical_design_record",
        "source_revision_ref": _text(
            projection_payload.get("source_revision_ref") or faithfulness.get("source_revision_ref")
        ),
        "s9_projection_faithfulness": faithfulness,
    }
    if "omission_manifest" in projection_payload:
        verifier_payload["omission_manifest"] = projection_payload["omission_manifest"]
    verification = verify_s9_projection_faithfulness_for_pdc_consumer_contract(
        projections={"public": verifier_payload},
        expected_closeout_truth=_copy_optional_public_mapping(
            projection_semantics.get("closeout_truth"),
            field="closeout_truth",
        ),
        expected_contested_record_ids=[
            _text(record.get("contested_record_id"))
            for record in _as_sequence(projection_semantics.get("contested_records"))
            if isinstance(record, Mapping)
        ],
    )
    if verification.get("status") != "pass":
        code = _first_s9_issue_code(verification)
        raise PublicExportRedactionError(
            code,
            "S9 projection faithfulness must pass before public release.",
        )
    enriched = _copy_mapping(projection_semantics)
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            *_s9_audit_refs(faithfulness),
            *_text_list(projection_payload.get("s9_lowering_append_refs")),
            *_text_list(projection_payload.get("lowering_append_refs")),
        ]
    )
    source_state = _copy_optional_public_mapping(enriched.get("source_state"), field="source_state")
    source_state.update(
        {
            "s9_source_revision_ref": _text(faithfulness.get("source_revision_ref")),
            "s9_canonical_design_record_ref": _text(
                faithfulness.get("canonical_design_record_ref")
            ),
            "s9_canonical_design_record_digest": _text(
                faithfulness.get("canonical_design_record_digest")
            ),
            "s9_projection_policy": "reads_canonical_design_record",
        }
    )
    enriched.update(
        {
            "s9_projection_faithfulness": faithfulness,
            "s9_projection_contract_verification_status": verification.get("status"),
            "s9_projection_contract_verification_ref": verification.get("consumer_contract_ref"),
            "audit_refs": audit_refs,
            "source_state": source_state,
        }
    )
    return enriched, verification


def _s9_faithfulness_record(payload: Mapping[str, object]) -> dict[str, object]:
    record = payload.get("s9_projection_faithfulness")
    s9_projection = payload.get("s9_projection")
    if record is None and isinstance(s9_projection, Mapping):
        record = s9_projection.get("s9_projection_faithfulness")
    if isinstance(record, Mapping):
        return _copy_public_mapping(record, field="s9_projection_faithfulness")
    model_dump = getattr(record, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, Mapping):
            return _copy_public_mapping(dumped, field="s9_projection_faithfulness")
    return {}


def _s9_audit_refs(faithfulness: Mapping[str, object]) -> list[str]:
    return _unique_texts(
        [
            faithfulness.get("faithfulness_ref"),
            faithfulness.get("render_ref"),
            faithfulness.get("request_ref"),
            faithfulness.get("canonical_design_record_ref"),
            faithfulness.get("source_revision_ref"),
        ]
    )


def _first_s9_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s9_projection_faithfulness_failed"


def _assert_public_claim_omissions_manifested(
    artifacts: Mapping[str, object],
    projection_semantics: Mapping[str, object] | None,
) -> None:
    omitted_claim_ids = set(_iter_omitted_claim_ids(artifacts))
    if not omitted_claim_ids:
        return
    manifested_claim_ids: set[str] = set()
    if projection_semantics is not None:
        for row in _as_sequence(projection_semantics.get("omission_manifest")):
            if isinstance(row, Mapping):
                manifested_claim_ids.update(
                    str(value) for value in _as_sequence(row.get("claim_ids"))
                )
    if not omitted_claim_ids <= manifested_claim_ids:
        raise PublicExportRedactionError(
            "public_export_omission_manifest_missing",
            "public exports must manifest omitted blocked claims instead of silently dropping them",
        )


def _assert_public_export_candidate_firewall(artifacts: Mapping[str, object]) -> None:
    hypothesis_ledger = _find_hypothesis_ledger(artifacts)
    issues = candidate_firewall_issues_for_payload(
        artifacts,
        hypothesis_ledger=hypothesis_ledger,
        authority_slots=("projection_authority",),
        surface="public_export",
    )
    if issues:
        issue = issues[0]
        raise PublicExportRedactionError(
            str(issue.get("code") or "candidate_firewall_blocked"),
            str(issue.get("message") or "Candidate content cannot be publicly exported."),
        )


def _assert_public_welfare_frontier_surface(payload: Mapping[str, object]) -> None:
    scalar_keys = {
        key for key in payload if key in _SCALAR_WELFARE_KEYS and payload[key] is not None
    }
    if not scalar_keys:
        return
    has_frontier = bool(payload.get("frontier") or payload.get("pareto_frontier"))
    has_value_choice = bool(payload.get("value_choice") or payload.get("value_choice_decision"))
    has_provenance = bool(
        payload.get("social_weight_provenance") or payload.get("social_weight_provenance_refs")
    )
    if has_frontier and has_value_choice and has_provenance:
        return
    raise PublicExportRedactionError(
        "scalar_welfare_aggregate_without_frontier",
        "Scalar welfare aggregates cannot be published without Pareto frontier, "
        "value-choice, and social-weight provenance records.",
    )


def _find_hypothesis_ledger(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        ledger = value.get("hypothesis_ledger")
        if isinstance(ledger, Mapping):
            return ledger
        for _, item in _iter_mapping_items(value):
            found = _find_hypothesis_ledger(item)
            if found is not None:
                return found
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found = _find_hypothesis_ledger(item)
            if found is not None:
                return found
    return None


def _iter_omitted_claim_ids(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in _iter_mapping_items(value):
            lowered = str(key).casefold()
            if lowered in {"omitted_claim_ids", "omitted_blocked_claim_ids"}:
                found.extend(str(claim_id) for claim_id in _as_sequence(item) if str(claim_id))
                continue
            if lowered in {"omitted_claims", "omitted_blocked_claims"}:
                for claim in _as_sequence(item):
                    if isinstance(claim, Mapping):
                        claim_id = str(claim.get("claim_id") or claim.get("id") or "")
                        if claim_id:
                            found.append(claim_id)
                    elif str(claim):
                        found.append(str(claim))
                continue
            found.extend(_iter_omitted_claim_ids(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_omitted_claim_ids(item))
    return sorted(set(found))


def _assert_no_unexplained_replay_drift(artifacts: Mapping[str, object]) -> None:
    for explanation in _iter_drift_explanations(artifacts):
        if _is_unexplained_replay_drift(explanation):
            raise PublicExportRedactionError(
                "public_export_replay_drift_unexplained",
                "public exports require typed accepted replay drift or reproduction",
            )
        if _is_unbounded_replay_drift(explanation):
            raise PublicExportRedactionError(
                "public_export_replay_drift_unbounded",
                "public exports require replay drift to stay within production impact bounds",
            )


def _iter_drift_explanations(value: object) -> Sequence[Mapping[str, object]]:
    found: list[Mapping[str, object]] = []
    if isinstance(value, Mapping):
        if _looks_like_drift_explanation(value):
            found.append(value)
        for key, item in _iter_mapping_items(value):
            if key == "drift_explanation" and isinstance(item, Mapping):
                found.append(item)
            else:
                found.extend(_iter_drift_explanations(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_drift_explanations(item))
    return found


def _looks_like_drift_explanation(value: Mapping[str, object]) -> bool:
    return (
        value.get("schema_version") == "policyos.drift_explanation.v1"
        or "drift_sources" in value
        or "unexplained_difference_count" in value
    )


def _iter_rule_evolution_annotations(value: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(value, Mapping):
        if _looks_like_rule_evolution_annotation(value):
            found.append(_copy_mapping(value))
        for _, item in _iter_mapping_items(value):
            found.extend(_iter_rule_evolution_annotations(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_rule_evolution_annotations(item))
    return found


def _iter_public_revision_states(value: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(value, Mapping):
        if _looks_like_public_revision_state(value):
            found.append(_copy_mapping(value))
        for _, item in _iter_mapping_items(value):
            found.extend(_iter_public_revision_states(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_public_revision_states(item))
    return found


def _public_orchestration_continuity_projection(
    artifacts: Mapping[str, object],
) -> dict[str, object] | None:
    value = artifacts.get("runtime_orchestration_continuity")
    if not isinstance(value, Mapping):
        return None
    return {
        "schema_version": value.get("schema_version"),
        "status": value.get("status"),
        "carrier_ref": value.get("carrier_ref"),
        "concept_spine_ref": value.get("concept_spine_ref"),
        "jurisdiction_spine_ref": value.get("jurisdiction_spine_ref"),
        "runtime_claim_registry_ref": value.get("runtime_claim_registry_ref"),
        "producer_handshake_ledger_ref": value.get("producer_handshake_ledger_ref"),
        "handoff_ref_count": _summary_count(value, "handoff_ref_count"),
        "producer_binding_ref_count": _summary_count(value, "producer_binding_ref_count"),
        "authority_role": "projection_only",
        "may_not_use_for": [
            "producer_domain_truth",
            "runtime_closeout_authority",
            "scorecard_authority",
            "approval_authority",
        ],
    }


def _summary_count(value: Mapping[str, object], key: str) -> int:
    summary = value.get("summary")
    if not isinstance(summary, Mapping):
        return 0
    try:
        return int(summary.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _looks_like_rule_evolution_annotation(value: Mapping[str, object]) -> bool:
    return value.get("schema_version") == RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION or (
        "public_annotation_state" in value
        and "revalidation_state" in value
        and "silent_upgrade_allowed" in value
    )


def _looks_like_public_revision_state(value: Mapping[str, object]) -> bool:
    return value.get("schema_version") == PUBLIC_REVISION_STATE_SCHEMA_VERSION or (
        "affected_claim_ids" in value
        and "unaffected_claim_ids" in value
        and "silent_upgrade_allowed" in value
        and value.get("authority_role") == "projection_only"
    )


def _is_unexplained_replay_drift(explanation: Mapping[str, object]) -> bool:
    status = str(explanation.get("status") or "").strip().casefold()
    readiness = str(explanation.get("production_readiness") or "").strip().casefold()
    summary = explanation.get("summary")
    unexplained_count = 0
    if isinstance(summary, Mapping):
        try:
            unexplained_count = int(summary.get("unexplained_difference_count") or 0)
        except (TypeError, ValueError):
            unexplained_count = 0
    return status == "unexplained_drift" or (
        readiness in {"blocked", "fail", "failed"} and unexplained_count > 0
    )


def _is_unbounded_replay_drift(explanation: Mapping[str, object]) -> bool:
    status = str(explanation.get("status") or "").strip().casefold()
    readiness = str(explanation.get("production_readiness") or "").strip().casefold()
    summary = explanation.get("summary")
    max_impact = ""
    if isinstance(summary, Mapping):
        max_impact = str(summary.get("max_impact") or "").strip().casefold()
    blocker = explanation.get("blocking_failure")
    blocker_code = str(blocker.get("code") or "").strip() if isinstance(blocker, Mapping) else ""
    return (
        status == "accepted_drift_non_ready"
        or blocker_code == "authority_replay_drift_unbounded"
        or (readiness in {"blocked", "fail", "failed"} and max_impact in {"medium", "high"})
    )


def assert_public_export_official_use_limits(bundle: Mapping[str, object]) -> None:
    """Fail closed if a public export is shaped like authority evidence."""

    evidence_class = str(bundle.get("evidence_class") or "").strip().casefold()
    authority_role = str(bundle.get("authority_role") or "").strip().casefold()
    provenance_kind = str(bundle.get("provenance_kind") or "").strip().casefold()
    if (
        evidence_class not in _PUBLIC_EXPORT_EVIDENCE_CLASSES
        or authority_role in _AUTHORITY_ROLES
        or authority_role not in _PUBLIC_EXPORT_AUTHORITY_ROLES
        or provenance_kind in _AUTHORITY_PROVENANCE_KINDS
    ):
        raise PublicExportRedactionError(
            "public_export_not_authority",
            "public exports must remain redacted projection-only artifacts",
        )

    limits = bundle.get("official_use_limits")
    if not isinstance(limits, Mapping):
        raise PublicExportRedactionError(
            "public_export_official_use_limits_missing",
            "official-use limits are required",
        )
    disallowed = {
        str(item) for item in _as_sequence(limits.get("may_not_be_used_for")) if str(item).strip()
    }
    required = {
        "approval_authority",
        "runtime_closeout_authority",
        "scorecard_authority",
    }
    if limits.get("official_use") != "public_audit_only" or not required <= disallowed:
        raise PublicExportRedactionError(
            "public_export_official_use_limits_missing",
            "public export must forbid scorecard, approval, and closeout authority use",
        )


def _authority_projection(envelope: AuthorityEnvelopeInput) -> dict[str, object]:
    validated = deserialize_authority_envelope(envelope)
    closure = validated.same_input_closure
    source_ref = validated.cas_ref or validated.artifact_ref
    return {
        "evidence_id": validated.evidence_id,
        "artifact_kind": validated.artifact_kind,
        "schema_name": validated.schema_name,
        "schema_version": validated.schema_version,
        "producer_component": validated.producer_component,
        "owner": validated.owner,
        "phase": validated.phase,
        "validation_status": validated.validation_status,
        "source_blocking_status": validated.blocking_status,
        "source_authority_role": validated.authority_role,
        "source_evidence_class": validated.evidence_class,
        "source_provenance_kind": validated.provenance_kind,
        "authority_role": "projection_only",
        "evidence_class": "redacted_derived",
        "provenance_kind": "runtime_projection",
        "allowed_scorecard_authority_role": "not_authoritative",
        "allowed_approval_authority_role": "not_authoritative",
        "runtime_event_ref_fingerprint": _fingerprint(validated.runtime_event_ref),
        "source_authority_ref_fingerprint": _fingerprint(source_ref),
        "same_input_closure_status": closure.status,
        "same_input_closure_fingerprint": _fingerprint(
            closure.closure_sha256 or closure.closure_id
        ),
        "tenant_redacted": True,
    }


def _fingerprint(value: object) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _text_list(value: object) -> list[str]:
    return _unique_texts(_as_sequence(value))


def _int(value: object) -> int:
    if not value or not isinstance(value, (str, bytes, bytearray, SupportsInt)):
        return 0
    try:
        return max(0, int(value))
    except (OverflowError, TypeError, ValueError):
        return 0


def _copy_public_mapping(value: object, *, field: str) -> dict[str, object]:
    """Copy a JSON-shaped mapping without losing its string-key contract."""

    if not isinstance(value, Mapping):
        raise PublicExportRedactionError(
            "public_export_mapping_invalid",
            f"{field} must be a mapping.",
        )
    copied: dict[str, object] = {}
    for key, item in _iter_mapping_items(value):
        if not isinstance(key, str):
            raise PublicExportRedactionError(
                "public_export_mapping_key_invalid",
                f"{field} keys must be strings.",
            )
        copied[key] = item
    return copied


def _copy_optional_public_mapping(value: object, *, field: str) -> dict[str, object]:
    """Copy an optional mapping, preserving absence as an empty projection."""

    if value is None:
        return {}
    return _copy_public_mapping(value, field=field)


def _copy_public_mapping_if_present(value: object, *, field: str) -> dict[str, object]:
    """Copy a supplied mapping, retaining the existing absent/non-mapping fallback."""

    if not isinstance(value, Mapping):
        return {}
    return _copy_public_mapping(value, field=field)


def _copy_public_sequence(value: object, *, field: str) -> list[object]:
    """Copy an optional JSON sequence while rejecting text and non-sequences."""

    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    raise PublicExportRedactionError(
        "public_export_sequence_invalid",
        f"{field} must be a sequence.",
    )


def _unique_texts(values: Sequence[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in result:
            result.append(text)
    return result


def _as_sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


__all__ = [
    "PUBLIC_EXPORT_REDACTION_POLICY_REF",
    "PUBLIC_EXPORT_SCHEMA_VERSION",
    "PublicExportRedactionError",
    "assert_public_export_official_use_limits",
    "build_public_export_bundle",
    "project_pre_n9_open_world_limitations",
    "project_promotion_open_world_limitation",
]
