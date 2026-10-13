"""Bind Fabric SourceContract candidates against compiled data requirements."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, get_args

from polisyos.core.contracts.control import DataNeed
from polisyos.data_requirement import (
    CapabilityRequirementResolution,
    DataRequirementScope,
    DataRequirementSpec,
)

FABRIC_DATA_REQUIREMENT_BINDINGS_SCHEMA_VERSION = (
    "policyos.fabric.data_requirement_bindings.v1"
)
CATALOG_DATA_NEED_PROJECTION_SCHEMA_VERSION = (
    "policyos.fabric.catalog_data_need_projection.v1"
)

_CATALOG_REQUEST_ENVELOPE_FIELDS = frozenset(
    {
        "runtime_grounding_context",
        "capability_requirement_resolutions",
        "catalog_request_context",
    }
)
_DEFAULT_SCOPE_GEOGRAPHIES = frozenset(
    {"geography", "scenario_geography", "state_or_region"}
)


def _project_data_requirement_to_catalog_needs(
    *,
    compiled_requirement_spec: object,
) -> tuple[tuple[DataNeed, ...], dict[str, Any]]:
    """Project known requirement scope into Catalog queries without granting admission.

    The return value is either a typed, candidate-only set of ``DataNeed`` rows
    plus a complete limitation report, or a typed refusal with no query rows.
    A Catalog candidate or fetch plan is never an acquired or admitted artifact.
    """

    payload = _payload(compiled_requirement_spec)
    if not payload:
        return (), _catalog_projection_refusal("compiled_requirement_missing")
    allowed = set(DataRequirementSpec.model_fields) | _CATALOG_REQUEST_ENVELOPE_FIELDS
    extra_fields = sorted(set(payload) - allowed)
    if extra_fields:
        return (), _catalog_projection_refusal(
            "compiled_requirement_fields_unrecognized",
            fields=extra_fields,
        )
    typed_payload = {
        field: payload[field]
        for field in DataRequirementSpec.model_fields
        if field in payload
    }
    try:
        requirement = DataRequirementSpec.model_validate(typed_payload)
    except (TypeError, ValueError) as exc:
        return (), _catalog_projection_refusal(
            "compiled_requirement_invalid",
            validation_error=type(exc).__name__,
        )

    profile = requirement.metadata.get("scope_profile")
    if not isinstance(profile, Mapping):
        return (), _catalog_projection_refusal(
            "scope_profile_not_established",
            requirement_id=requirement.requirement_id,
            source_scope={
                **requirement.scope.model_dump(mode="json"),
                "quality_minima": requirement.quality_minima.model_dump(mode="json"),
                "required_data_families": list(requirement.required_data_families),
                "recency_horizon": requirement.recency_horizon,
            },
        )
    profile_fields = {
        "profile_id",
        "jurisdiction",
        "time_window",
        "required_constructs",
        "candidate_construct_proposals",
        "time_role",
        "granularity",
        "unrepresented_fields",
    }
    unknown_profile_fields = sorted(set(profile) - profile_fields)
    raw_unrepresented_fields = profile.get("unrepresented_fields", ())
    if not isinstance(raw_unrepresented_fields, Sequence) or isinstance(
        raw_unrepresented_fields,
        str | bytes | bytearray,
    ) or any(not isinstance(item, str) or not item.strip() for item in raw_unrepresented_fields):
        return (), _catalog_projection_refusal(
            "scope_profile_unrepresented_fields_invalid",
            requirement_id=requirement.requirement_id,
        )
    unrepresented_profile_fields = list(raw_unrepresented_fields)
    if unknown_profile_fields or unrepresented_profile_fields:
        return (), _catalog_projection_refusal(
            "scope_profile_fields_unrepresented",
            fields=sorted(set(unknown_profile_fields) | set(unrepresented_profile_fields)),
            requirement_id=requirement.requirement_id,
        )
    profile_id = _catalog_text(profile.get("profile_id"))
    if not profile_id:
        return (), _catalog_projection_refusal(
            "scope_profile_identity_missing",
            requirement_id=requirement.requirement_id,
        )

    raw_window = profile.get("time_window")
    if not isinstance(raw_window, Mapping):
        return (), _catalog_projection_refusal(
            "scope_profile_time_window_invalid",
            profile_id=profile_id,
        )
    unknown_window_fields = sorted(set(raw_window) - {"start", "end"})
    if unknown_window_fields:
        return (), _catalog_projection_refusal(
            "scope_profile_time_window_fields_unrepresented",
            fields=unknown_window_fields,
            profile_id=profile_id,
        )
    for field in ("start", "end"):
        value = raw_window.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            return (), _catalog_projection_refusal(
                "scope_profile_time_window_value_invalid",
                field=field,
                profile_id=profile_id,
            )
    for field in ("time_role", "granularity"):
        value = profile.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            return (), _catalog_projection_refusal(
                "scope_profile_value_invalid",
                field=field,
                profile_id=profile_id,
            )
    for field in ("required_constructs", "candidate_construct_proposals"):
        value = profile.get(field, ())
        if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
            return (), _catalog_projection_refusal(
                "scope_profile_constructs_invalid",
                field=field,
                profile_id=profile_id,
            )
        if any(not isinstance(item, str) or not item.strip() for item in value):
            return (), _catalog_projection_refusal(
                "scope_profile_constructs_invalid",
                field=field,
                profile_id=profile_id,
            )
    time_start = _catalog_text(raw_window.get("start")) or None
    time_end = _catalog_text(raw_window.get("end")) or None
    time_role = _catalog_text(profile.get("time_role")) or None
    granularity = _catalog_text(profile.get("granularity")) or None
    supported_time_roles = get_args(DataRequirementScope.model_fields["time_role"].annotation)
    if time_role is not None and time_role not in supported_time_roles:
        return (), _catalog_projection_refusal(
            "scope_profile_time_role_invalid",
            profile_id=profile_id,
        )
    if time_role is not None and time_role != requirement.scope.time_role:
        return (), _catalog_projection_refusal(
            "catalog_time_role_conflict",
            profile_id=profile_id,
            time_role=time_role,
            requirement_time_role=requirement.scope.time_role,
        )
    if (time_start or time_end) and time_role is None:
        return (), _catalog_projection_refusal(
            "catalog_time_role_not_established",
            profile_id=profile_id,
            time_window={"start": time_start, "end": time_end},
        )
    effective_time_role = time_role or requirement.scope.time_role
    if effective_time_role != "observation_time" or (
        (time_start or time_end) and time_role != "observation_time"
    ):
        return (), _catalog_projection_refusal(
            "catalog_time_role_unrepresentable",
            profile_id=profile_id,
            time_role=effective_time_role,
        )
    if not granularity:
        return (), _catalog_projection_refusal(
            "catalog_granularity_not_established",
            profile_id=profile_id,
        )

    raw_profile_geography = profile.get("jurisdiction")
    if raw_profile_geography is not None and (
        not isinstance(raw_profile_geography, str) or not raw_profile_geography.strip()
    ):
        return (), _catalog_projection_refusal(
            "scope_profile_geography_invalid",
            profile_id=profile_id,
        )
    profile_geography = _catalog_text(raw_profile_geography)
    spec_geography = requirement.scope.jurisdiction or requirement.scope.geography
    profile_geography_is_generic = (
        profile_geography.casefold() in _DEFAULT_SCOPE_GEOGRAPHIES
    )
    if (
        profile_geography
        and not profile_geography_is_generic
        and requirement.scope.jurisdiction
        and profile_geography != requirement.scope.jurisdiction
    ):
        return (), _catalog_projection_refusal(
            "scope_profile_geography_conflict",
            profile_id=profile_id,
        )
    declared_geography = (
        profile_geography
        if profile_geography and not profile_geography_is_generic
        else spec_geography
    )
    geography = (
        declared_geography
        if declared_geography.casefold() not in _DEFAULT_SCOPE_GEOGRAPHIES
        else None
    )

    resolution_rows, resolution_error = _catalog_projection_resolutions(payload)
    if resolution_error is not None:
        return (), _catalog_projection_refusal(
            "capability_resolution_invalid",
            detail=resolution_error,
            profile_id=profile_id,
        )
    matching_resolutions = tuple(
        resolution
        for resolution in resolution_rows
        if resolution.query.source_family_alias
        and resolution.query.source_family_alias.casefold()
        in {family.casefold() for family in requirement.required_data_families}
    )
    required_constructs = set(profile.get("required_constructs", ()))
    unbound_resolution_scope = False
    for resolution in matching_resolutions:
        if resolution.query.construct not in required_constructs:
            return (), _catalog_projection_refusal(
                "capability_resolution_construct_mismatch",
                profile_id=profile_id,
                resolution_requirement_id=resolution.query.requirement_id,
                resolution_construct=resolution.query.construct,
            )
        if resolution.scope_profile_id and resolution.scope_profile_id != profile_id:
            return (), _catalog_projection_refusal(
                "capability_resolution_profile_mismatch",
                profile_id=profile_id,
                resolution_profile_id=resolution.scope_profile_id,
            )
        if not resolution.scope_profile_id:
            unbound_resolution_scope = True
        resolution_geography = resolution.query.geography
        resolution_geography_is_generic = (
            resolution_geography.casefold() in _DEFAULT_SCOPE_GEOGRAPHIES
        )
        if geography is None and not resolution_geography_is_generic:
            return (), _catalog_projection_refusal(
                "capability_resolution_geography_not_bound_to_requirement",
                profile_id=profile_id,
                resolution_requirement_id=resolution.query.requirement_id,
            )
        if geography is not None and resolution_geography != geography:
            return (), _catalog_projection_refusal(
                "capability_resolution_geography_mismatch",
                profile_id=profile_id,
            )
        if (
            resolution.query.time_window.start != time_start
            or resolution.query.time_window.end != time_end
        ):
            return (), _catalog_projection_refusal(
                "capability_resolution_time_window_mismatch",
                profile_id=profile_id,
            )

    request_context = payload.get("catalog_request_context")
    if request_context is not None and not isinstance(request_context, Mapping):
        return (), _catalog_projection_refusal(
            "catalog_request_context_invalid",
            profile_id=profile_id,
        )
    context = request_context if isinstance(request_context, Mapping) else {}
    if set(context) - {"budget_fields", "availability_fields"}:
        return (), _catalog_projection_refusal(
            "catalog_request_context_fields_unrecognized",
            profile_id=profile_id,
        )
    budget_fields = context.get("budget_fields", {})
    availability_fields = context.get("availability_fields", {})
    if not isinstance(budget_fields, Mapping) or not isinstance(availability_fields, Mapping):
        return (), _catalog_projection_refusal(
            "catalog_request_context_fields_invalid",
            profile_id=profile_id,
        )
    if budget_fields:
        zero_budget = any(
            type(value) in {int, float} and float(value) == 0.0
            for value in budget_fields.values()
        )
        return (), _catalog_projection_refusal(
            "catalog_zero_budget_unrepresentable"
            if zero_budget
            else "catalog_budget_unrepresentable",
            budget_fields=sorted(str(key) for key in budget_fields),
            profile_id=profile_id,
        )
    if availability_fields:
        return (), _catalog_projection_refusal(
            "catalog_availability_filter_unrepresentable",
            availability_fields=sorted(str(key) for key in availability_fields),
            profile_id=profile_id,
        )

    needs = tuple(
        DataNeed(
            metric=family,
            geography=geography,
            time_start=time_start,
            time_end=time_end,
            granularity=granularity,
            quality_min=requirement.quality_minima.min_quality_score,
            purpose="n7_catalog_candidate_resolution",
        )
        for family in requirement.required_data_families
    )
    mapped_paths = {
        "required_data_families",
        "scope.geography",
        "scope.jurisdiction",
        "scope.time_role",
        "quality_minima.min_quality_score",
        "metadata.scope_profile.profile_id",
        "metadata.scope_profile.jurisdiction",
        "metadata.scope_profile.time_window.start",
        "metadata.scope_profile.time_window.end",
        "metadata.scope_profile.time_role",
        "metadata.scope_profile.granularity",
        "metadata.scope_profile.required_constructs",
        "metadata.scope_profile.candidate_construct_proposals",
    }
    unrepresented = sorted(
        path
        for path, value in _catalog_requirement_leaf_paths(
            requirement.model_dump(mode="json")
        )
        if path not in mapped_paths and value not in (None, "", [], {})
    )
    limitations = ["catalog_resolution_is_candidate_only"]
    if not matching_resolutions:
        limitations.append("capability_resolution_not_established_for_source_family")
    elif unbound_resolution_scope or any(
        resolution.state == "not_established" for resolution in matching_resolutions
    ):
        limitations.append("capability_resolution_not_established")
    if not time_role:
        limitations.append("time_role_not_established")
    if not geography:
        limitations.append("geography_not_established")
    if unrepresented:
        limitations.append("compiled_requirement_fields_not_enforced_by_catalog_query")
    report = {
        "schema_version": CATALOG_DATA_NEED_PROJECTION_SCHEMA_VERSION,
        "disposition": "candidate_only",
        "authority_status": "not_established",
        "requirement_id": requirement.requirement_id,
        "scope_profile_id": profile_id,
        "source_scope": {
            "geography": declared_geography,
            "catalog_geography": geography,
            "population": requirement.scope.population,
            "time": requirement.scope.time,
            "time_role": time_role,
            "time_window": {"start": time_start, "end": time_end},
            "granularity": granularity,
            "recency_horizon": requirement.recency_horizon,
            "quality_minima": requirement.quality_minima.model_dump(mode="json"),
        },
        "mapped_data_needs": [need.model_dump(mode="json") for need in needs],
        "capability_resolution_status": (
            "not_established"
            if not matching_resolutions
            or unbound_resolution_scope
            or any(resolution.state == "not_established" for resolution in matching_resolutions)
            else "binding_returned_candidate_only"
        ),
        "resolution_requirement_ids": [
            resolution.query.requirement_id for resolution in matching_resolutions
        ],
        "unrepresented_requirement_fields": unrepresented,
        "budget_status": "not_established_at_catalog_boundary",
        "availability_status": "not_established_at_catalog_boundary",
        "limitations": limitations,
    }
    return needs, report


def _catalog_projection_resolutions(
    payload: Mapping[str, Any],
) -> tuple[tuple[CapabilityRequirementResolution, ...], str | None]:
    raw_rows = payload.get("capability_requirement_resolutions", ())
    if raw_rows is None:
        return (), None
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, str | bytes | bytearray):
        return (), "resolution_rows_not_a_sequence"
    rows: list[CapabilityRequirementResolution] = []
    for index, raw in enumerate(raw_rows):
        row_payload = _payload(raw)
        if not row_payload:
            return (), f"resolution_row_{index}_not_a_mapping"
        try:
            rows.append(CapabilityRequirementResolution.model_validate(row_payload))
        except (TypeError, ValueError) as exc:
            return (), f"resolution_row_{index}_{type(exc).__name__}"
    return tuple(rows), None


def _catalog_requirement_leaf_paths(
    value: object,
    *,
    prefix: str = "",
) -> tuple[tuple[str, object], ...]:
    """Enumerate actual nested requirement data so new typed fields fail visible."""

    if isinstance(value, Mapping):
        return tuple(
            row
            for key, child in value.items()
            for row in _catalog_requirement_leaf_paths(child, prefix=f"{prefix}.{key}".strip("."))
        )
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        if not value:
            return ((prefix, value),)
        return tuple(
            row
            for index, child in enumerate(value)
            for row in _catalog_requirement_leaf_paths(child, prefix=f"{prefix}[{index}]")
        )
    return ((prefix, value),)


def _catalog_projection_refusal(
    reason_code: str,
    **details: Any,
) -> dict[str, Any]:
    return {
        "schema_version": CATALOG_DATA_NEED_PROJECTION_SCHEMA_VERSION,
        "disposition": "refused",
        "authority_status": "not_established",
        "reason_codes": [reason_code],
        "limitations": ["no_catalog_request_emitted"],
        **details,
    }


def _catalog_text(value: object) -> str:
    """Read only actual text values from the open metadata carrier."""

    return value.strip() if isinstance(value, str) else ""


def build_source_contract_requirement_bindings(
    *,
    data_requirement_specs: Sequence[DataRequirementSpec | Mapping[str, Any]],
    source_contract_candidates: Sequence[Mapping[str, Any]],
    selected_candidate_refs: Sequence[str] = (),
    capability_bindings: Sequence[Mapping[str, Any] | object] = (),
) -> dict[str, Any]:
    """Classify SourceContract candidates against compiled DataRequirementSpec rows.

    Args:
        data_requirement_specs: Claim-bound compiled requirements.
        source_contract_candidates: Fabric source candidates with source family,
            present facets, and optional source contract validation status.
        selected_candidate_refs: Candidate refs that an upstream selector already
            attempted to use. Nonmatching selected refs are rejected; other
            nonmatching refs remain context-only inventory.
        capability_bindings: Shared capability-graph binding results from the
            requirement-to-capability resolver. When present, these are consumed
            as producer-backed source-contract bindings instead of falling back
            to source-family guesses.

    Returns:
        A JSON-serializable selected/rejected/blocked/context_only binding report.
    """

    specs = tuple(_coerce_spec(item) for item in data_requirement_specs)
    candidates = tuple(_candidate(item) for item in source_contract_candidates)
    selected_refs = {_text(item) for item in selected_candidate_refs if _text(item)}
    capability_rows = _capability_requirement_bindings(
        specs=specs,
        capability_bindings=capability_bindings,
    )
    capability_answered_requirements = {
        _text(row.get("requirement_id"))
        for row in capability_rows
        if row.get("binding_status") in {"selected", "blocked"}
        and _text(row.get("requirement_id"))
    }
    required_families = {
        family.casefold()
        for spec in specs
        for family in spec.required_data_families
        if family
    }
    matched_candidate_refs: set[str] = set()
    bindings: list[dict[str, Any]] = []

    for spec in specs:
        if spec.requirement_id in capability_answered_requirements:
            continue
        for source_family in spec.required_data_families:
            matching = [
                candidate
                for candidate in candidates
                if candidate["source_family"].casefold() == source_family.casefold()
            ]
            if not matching:
                bindings.append(_blocked_requirement_binding(spec, source_family, candidates))
                continue
            candidate = _best_candidate(matching, spec.mandatory_facets)
            matched_candidate_refs.add(candidate["candidate_ref"])
            bindings.append(_candidate_requirement_binding(spec, source_family, candidate))

    for candidate in candidates:
        candidate_ref = candidate["candidate_ref"]
        if candidate_ref in matched_candidate_refs:
            continue
        if candidate["source_family"].casefold() in required_families:
            continue
        binding_status = "rejected" if candidate_ref in selected_refs else "context_only"
        bindings.append(
            {
                "data_requirement_id": None,
                "requirement_id": None,
                "claim_id": None,
                "source_family": candidate["source_family"],
                "candidate_ref": candidate_ref,
                "binding_status": binding_status,
                "reason_code": "no_matching_data_requirement_spec"
                if binding_status == "rejected"
                else "outside_compiled_data_requirement",
                "authority_surface": "context_inventory",
                "present_facets": sorted(candidate["present_facets"]),
                "missing_facets": [],
                "source_contract_validation": dict(candidate["source_contract_validation"]),
            }
        )

    summary = {
        "requirements": sum(len(spec.required_data_families) for spec in specs),
        "selected": _count((*capability_rows, *bindings), "selected"),
        "rejected": _count((*capability_rows, *bindings), "rejected"),
        "blocked": _count((*capability_rows, *bindings), "blocked"),
        "context_only": _count((*capability_rows, *bindings), "context_only"),
    }
    if capability_rows:
        summary["capability_binding_count"] = len(capability_rows)
    return {
        "schema_version": FABRIC_DATA_REQUIREMENT_BINDINGS_SCHEMA_VERSION,
        "requirement_source": "compiled_data_requirement_spec",
        "summary": summary,
        "source_contract_bindings": [*capability_rows, *bindings],
    }


def _candidate_requirement_binding(
    spec: DataRequirementSpec,
    source_family: str,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    present_facets = set(candidate["present_facets"])
    missing_facets = sorted(
        facet for facet in spec.mandatory_facets if facet not in present_facets
    )
    validation = dict(candidate["source_contract_validation"])
    validation_status = _text(validation.get("status")).casefold()
    if not missing_facets and validation_status == "pass":
        binding_status = "selected"
        reason_code = None
        authority_surface = "compiled_data_requirement"
    else:
        binding_status = "rejected"
        reason_code = _candidate_rejection_reason(missing_facets, validation_status)
        authority_surface = "fabric_source_contract_validation"
    return {
        "data_requirement_id": spec.requirement_id,
        "requirement_id": spec.requirement_id,
        "claim_id": spec.claim_id,
        "source_family": source_family,
        "required_data_families": list(spec.required_data_families),
        "candidate_ref": candidate["candidate_ref"],
        "binding_status": binding_status,
        "reason_code": reason_code,
        "authority_surface": authority_surface,
        "present_facets": sorted(present_facets),
        "missing_facets": missing_facets,
        "mandatory_facets": list(spec.mandatory_facets),
        "admissibility_predicates": list(spec.admissibility_predicates),
        "source_contract_validation": validation,
    }


def _blocked_requirement_binding(
    spec: DataRequirementSpec,
    source_family: str,
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "data_requirement_id": spec.requirement_id,
        "requirement_id": spec.requirement_id,
        "claim_id": spec.claim_id,
        "source_family": source_family,
        "required_data_families": list(spec.required_data_families),
        "candidate_ref": None,
        "binding_status": "blocked",
        "reason_code": "required_source_family_absent",
        "authority_surface": "compiled_data_requirement",
        "present_facets": [],
        "missing_facets": list(spec.mandatory_facets),
        "mandatory_facets": list(spec.mandatory_facets),
        "admissibility_predicates": list(spec.admissibility_predicates),
        "source_contract_validation": {
            "status": "missing",
            "reason_code": "source_family_absent",
        },
        "rejected_candidate_source_families": sorted(
            {
                candidate["source_family"]
                for candidate in candidates
                if candidate["source_family"]
            }
        ),
    }


def _capability_requirement_bindings(
    *,
    specs: Sequence[DataRequirementSpec],
    capability_bindings: Sequence[Mapping[str, Any] | object],
) -> list[dict[str, Any]]:
    specs_by_id = {spec.requirement_id: spec for spec in specs}
    rows: list[dict[str, Any]] = []
    for raw in capability_bindings:
        binding = _payload(raw)
        requirement_id = _text(binding.get("requirement_id"))
        spec = specs_by_id.get(requirement_id)
        if spec is None:
            continue
        status = _text(binding.get("status"))
        capability_ref = _text(
            binding.get("selected_capability_ref") or binding.get("capability_ref")
        )
        if not capability_ref and status.startswith("selected_"):
            continue
        selected = status.startswith("selected_")
        blocked = status.startswith("blocked_")
        if not (selected or blocked):
            continue
        source_assets = _mapping_list(binding.get("source_assets"))
        base = {
            "data_requirement_id": spec.requirement_id,
            "requirement_id": spec.requirement_id,
            "claim_id": spec.claim_id,
            "source_family": _source_family_for_binding(spec, binding),
            "required_data_families": list(spec.required_data_families),
            "candidate_ref": capability_ref or None,
            "capability_ref": capability_ref or None,
            "construct_ref": _text(binding.get("construct_ref")) or None,
            "capability_index_ref": _text(binding.get("capability_index_ref")) or None,
            "construct_registry_ref": _text(binding.get("construct_registry_ref")) or None,
            "authority_composition_rule_ref": _text(
                binding.get("authority_composition_rule_ref")
                or binding.get("rule_version_ref")
            )
            or None,
            "authority_envelope_result": _text(binding.get("authority_envelope_result"))
            or None,
            "authority_surface": "capability_graph",
            "source_assets": source_assets,
            "source_asset_refs": [
                _text(asset.get("ref"))
                for asset in source_assets
                if _text(asset.get("ref"))
            ],
            "field_refs": sorted(
                {
                    field
                    for asset in source_assets
                    for field in _text_list(asset.get("fields"))
                }
            ),
            "rights_envelope": _payload(binding.get("rights_envelope")),
            "quality_score": _payload(binding.get("quality_score")),
            "limitations": _text_list(binding.get("limitations")),
            "conflict_markers": _mapping_list(binding.get("conflict_markers")),
            "present_facets": list(spec.mandatory_facets) if selected else [],
            "missing_facets": [] if selected else list(spec.mandatory_facets),
            "mandatory_facets": list(spec.mandatory_facets),
            "admissibility_predicates": list(spec.admissibility_predicates),
            "source_contract_validation": {
                "status": "pass" if selected else "blocked",
                "reason_code": status or "capability_binding_unavailable",
            },
        }
        if selected:
            rows.append(
                {
                    **base,
                    "binding_status": "selected",
                    "reason_code": _text(binding.get("binding_reasons"))
                    or "capability_binding_selected",
                }
            )
        else:
            rows.append(
                {
                    **base,
                    "binding_status": "blocked",
                    "reason_code": _text(binding.get("blocked_reasons"))
                    or status
                    or "capability_binding_blocked",
                }
            )
        for rejected in _mapping_list(binding.get("rejected_alternatives")):
            rejected_ref = _text(
                rejected.get("capability_ref")
                or rejected.get("selected_capability_ref")
                or rejected.get("candidate_ref")
            )
            rows.append(
                {
                    "data_requirement_id": spec.requirement_id,
                    "requirement_id": spec.requirement_id,
                    "claim_id": spec.claim_id,
                    "source_family": _text(rejected.get("source_family"))
                    or _source_family_for_binding(spec, binding),
                    "candidate_ref": rejected_ref or None,
                    "capability_ref": rejected_ref or None,
                    "construct_ref": rejected.get("construct_ref")
                    or binding.get("construct_ref"),
                    "capability_index_ref": binding.get("capability_index_ref"),
                    "construct_registry_ref": binding.get("construct_registry_ref"),
                    "authority_composition_rule_ref": binding.get(
                        "authority_composition_rule_ref"
                    )
                    or binding.get("rule_version_ref"),
                    "binding_status": "rejected",
                    "reason_code": _text(rejected.get("rejection_reason"))
                    or "capability_rejected_alternative",
                    "rejection_severity": _text(rejected.get("rejection_severity"))
                    or "soft",
                    "authority_surface": "capability_graph",
                    "present_facets": [],
                    "missing_facets": [],
                    "source_contract_validation": {
                        "status": "rejected",
                        "reason_code": _text(rejected.get("rejection_reason"))
                        or "capability_rejected_alternative",
                    },
                }
            )
    return rows


def _candidate_rejection_reason(
    missing_facets: Sequence[str],
    validation_status: str,
) -> str:
    if validation_status == "missing":
        return "source_contract_missing"
    if validation_status in {"blocked", "inactive", "sunset"}:
        return "source_contract_not_active"
    if validation_status and validation_status != "pass":
        return "source_contract_validation_failed"
    if missing_facets:
        return "source_contract_facets_missing"
    return "source_contract_validation_failed"


def _best_candidate(
    candidates: Sequence[Mapping[str, Any]],
    mandatory_facets: Sequence[str],
) -> Mapping[str, Any]:
    expected = set(mandatory_facets)
    return max(
        candidates,
        key=lambda candidate: len(expected & set(candidate["present_facets"])),
    )


def _candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    validation = candidate.get("source_contract_validation")
    return {
        "candidate_ref": _text(candidate.get("candidate_ref"))
        or f"source-contract-candidate:{_text(candidate.get('source_family')) or 'unknown'}",
        "source_family": _text(candidate.get("source_family")) or "unknown",
        "present_facets": _text_set(candidate.get("present_facets")),
        "source_contract_validation": (
            dict(validation)
            if isinstance(validation, Mapping)
            else {"status": "pass"}
        ),
    }


def _payload(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json", exclude_none=True)
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _text_list(value: object) -> list[str]:
    if value is None:
        return []
    values = (
        value
        if isinstance(value, Sequence)
        and not isinstance(value, str | bytes | bytearray)
        else (value,)
    )
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _source_family_for_binding(
    spec: DataRequirementSpec,
    binding: Mapping[str, Any],
) -> str:
    explicit = _text(binding.get("source_family"))
    if explicit:
        return explicit
    if spec.required_data_families:
        return spec.required_data_families[0]
    construct_ref = _text(binding.get("construct_ref")).removeprefix("construct:")
    return construct_ref or "capability_graph"


def _coerce_spec(spec: DataRequirementSpec | Mapping[str, Any]) -> DataRequirementSpec:
    if isinstance(spec, DataRequirementSpec):
        return spec
    return DataRequirementSpec.model_validate(spec)


def _count(bindings: Sequence[Mapping[str, Any]], status: str) -> int:
    return sum(1 for item in bindings if item.get("binding_status") == status)


def _text_set(value: object) -> set[str]:
    if value is None:
        return set()
    raw_values = value if isinstance(value, (list, tuple, set)) else (value,)
    return {text for item in raw_values if (text := _text(item))}


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


__all__ = [
    "FABRIC_DATA_REQUIREMENT_BINDINGS_SCHEMA_VERSION",
    "build_source_contract_requirement_bindings",
]
