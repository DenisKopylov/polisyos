"""Bind Fabric SourceContract candidates against compiled data requirements."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from polisyos.data_requirement import DataRequirementSpec

FABRIC_DATA_REQUIREMENT_BINDINGS_SCHEMA_VERSION = (
    "policyos.fabric.data_requirement_bindings.v1"
)


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
