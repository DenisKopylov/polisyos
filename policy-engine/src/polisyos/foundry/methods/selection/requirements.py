"""Requirement-aware Foundry method candidate selection."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from polisyos.method_requirement import (
    MethodIdentificationClass,
    MethodValidityRequirementSpec,
    normalize_method_requirements,
)


def select_method_candidates_for_requirements(
    *,
    candidate_methods: Sequence[object],
    method_requirements: Sequence[MethodValidityRequirementSpec | Mapping[str, Any]],
    capability_bindings: Sequence[Mapping[str, Any] | object] = (),
    observation_to_contract_manifest: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Select methods that satisfy W7.C method validity requirements."""

    requirements = normalize_method_requirements(method_requirements)
    capability_candidates = _method_candidates_from_capabilities(
        capability_bindings=capability_bindings,
        observation_to_contract_manifest=observation_to_contract_manifest,
    )
    candidates = [*[_mapping(method) for method in candidate_methods], *capability_candidates]
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    selected_requirement_ids: set[str] = set()

    for method in candidates:
        method_selected = False
        method_rejections: list[dict[str, Any]] = []
        for requirement in requirements:
            rejection = _rejection_for_requirement(method, requirement)
            if rejection is not None:
                method_rejections.append(rejection)
                continue
            enriched = dict(method)
            refs = _dedupe(
                [
                    *_string_list(enriched.get("method_requirement_refs")),
                    requirement.requirement_id,
                ]
            )
            enriched["method_requirement_refs"] = refs
            selected.append(enriched)
            selected_requirement_ids.add(requirement.requirement_id)
            method_selected = True
        if not method_selected:
            rejected.extend(method_rejections[:1] or [_family_mismatch(method, requirements)])

    requirement_statuses = {
        requirement.requirement_id: (
            "satisfied" if requirement.requirement_id in selected_requirement_ids else "missing"
        )
        for requirement in requirements
    }
    issues = [
        {
            "code": "method_requirement_no_selected_method",
            "severity": "fail",
            "layer": "foundry_methods",
            "phase": "method_requirement_selection",
            "method_requirement_ref": requirement.requirement_id,
            "claim_id": requirement.claim_id,
            "message": (
                f"No Foundry method candidate satisfied MethodValidityRequirementSpec "
                f"{requirement.requirement_id} for claim {requirement.claim_id}."
            ),
            "next_action": (
                "Select a named method with runtime assumption gates, uncertainty refs, "
                "limitations, and method output refs, or emit a typed blocker."
            ),
        }
        for requirement in requirements
        if requirement_statuses[requirement.requirement_id] == "missing"
    ]
    return {
        "schema_version": "policyos.foundry.method_requirement_selection.v1",
        "status": "fail" if issues else "pass",
        "method_requirements": [
            requirement.model_dump(mode="json") for requirement in requirements
        ],
        "method_requirement_statuses": requirement_statuses,
        "selected_methods": selected,
        "rejected_methods": rejected,
        "issues": issues,
        "summary": {
            "method_requirement_count": len(requirements),
            "selected_method_count": len(selected),
            "rejected_method_count": len(rejected),
            "capability_method_candidate_count": len(capability_candidates),
            "method_requirement_statuses": requirement_statuses,
        },
    }


def _rejection_for_requirement(
    method: Mapping[str, Any],
    requirement: MethodValidityRequirementSpec,
) -> dict[str, Any] | None:
    if not _matches_requirement_family(method, requirement):
        return _rejection_row(
            method,
            requirement=requirement,
            reason_code="method_requirement_family_mismatch",
            reason=(
                f"Method does not match required families for {requirement.requirement_id}."
            ),
        )
    if _generic_execution_candidate(method) and _serious_requirement(requirement):
        return _rejection_row(
            method,
            requirement=requirement,
            reason_code="generic_method_not_admissible",
            reason=(
                "Generic foundry.execute or generic simulation output cannot satisfy "
                f"MethodValidityRequirementSpec {requirement.requirement_id}."
            ),
        )
    if _offline_only_candidate(method) and _serious_requirement(requirement):
        return _rejection_row(
            method,
            requirement=requirement,
            reason_code="offline_only_validity_not_admissible",
            reason=(
                "Offline-only validity evidence cannot satisfy runtime method obligations "
                f"for {requirement.requirement_id}."
            ),
        )
    if requirement.requires_negative_certificate:
        if _string_list(method.get("negative_certificate_refs")):
            return None
        return _rejection_row(
            method,
            requirement=requirement,
            reason_code="negative_certificate_missing",
            reason=(
                f"Method requirement {requirement.requirement_id} requires a negative "
                "certificate."
            ),
        )
    if requirement.requires_runtime_assumption_gates:
        missing = _missing_runtime_assumption_gates(method, requirement)
        if missing:
            return _rejection_row(
                method,
                requirement=requirement,
                reason_code="runtime_assumption_validation_missing",
                reason=(
                    f"Method requirement {requirement.requirement_id} requires runtime "
                    "assumption gates: " + ", ".join(missing) + "."
                ),
                missing_assumption_gates=missing,
            )
    if requirement.requires_method_output and not _has_ref_mapping(
        method,
        "method_output_refs",
        "method_result_refs",
        "result_refs",
    ):
        return _rejection_row(
            method,
            requirement=requirement,
            reason_code="method_output_refs_missing",
            reason=f"Method requirement {requirement.requirement_id} requires method output refs.",
        )
    if requirement.requires_uncertainty_envelope and not (
        _has_ref_mapping(method, "uncertainty_refs", "uncertainty_envelope_refs")
        or _status_pass(method.get("uncertainty") or method.get("uncertainty_envelope"))
    ):
        return _rejection_row(
            method,
            requirement=requirement,
            reason_code="uncertainty_envelope_missing",
            reason=f"Method requirement {requirement.requirement_id} requires uncertainty refs.",
        )
    if requirement.requires_limitation_refs and not (
        _has_ref_mapping(method, "limitation_refs")
        or bool(_mapping_or_empty(method.get("transportability_limits")))
        or bool(_mapping_or_empty(method.get("degradation")))
    ):
        return _rejection_row(
            method,
            requirement=requirement,
            reason_code="limitation_refs_missing",
            reason=f"Method requirement {requirement.requirement_id} requires limitation refs.",
        )
    return None


def _matches_requirement_family(
    method: Mapping[str, Any],
    requirement: MethodValidityRequirementSpec,
) -> bool:
    required = {
        value.casefold()
        for value in [*requirement.required_method_families, *requirement.method_expectations]
        if value
    }
    if not required:
        return True
    method_values = {
        _text(method.get("method_family")).casefold(),
        *(_text(value).casefold() for value in _string_list(method.get("method_expectations"))),
        *(_text(value).casefold() for value in _string_list(method.get("tags"))),
        *(_text(value).casefold() for value in _string_list(method.get("method_contract_targets"))),
    }
    if requirement.requires_negative_certificate and _string_list(
        method.get("negative_certificate_refs")
    ):
        method_values.add("negative_certificate")
    return bool(required.intersection(method_values))


def _serious_requirement(requirement: MethodValidityRequirementSpec) -> bool:
    return (
        requirement.identification_class
        is not MethodIdentificationClass.NEGATIVE_CERTIFICATE
        or bool(requirement.method_expectations)
    )


def _generic_execution_candidate(method: Mapping[str, Any]) -> bool:
    family = _text(method.get("method_family") or method.get("family")).casefold()
    method_id = _text(method.get("method_id") or method.get("id") or method.get("method_fqn"))
    method_token = method_id.casefold()
    return (
        method_token in {"foundry.execute", "execute", "generic_simulation"}
        or method_token.endswith(".execute")
        or ("generic" in method_token and family in {"simulation", "method_execution"})
        or family in {"mechanism_runtime_execution"}
    )


def _offline_only_candidate(method: Mapping[str, Any]) -> bool:
    status = _text(method.get("truthfulness_status")).casefold()
    if status == "catalog_only":
        return True
    if _text(method.get("runtime_truthfulness_tier")):
        return False
    return bool(
        _text(method.get("declared_truthfulness_tier"))
        or _has_ref_mapping(method, "offline_validity_refs", "offline_report_refs")
    )


def _missing_runtime_assumption_gates(
    method: Mapping[str, Any],
    requirement: MethodValidityRequirementSpec,
) -> list[str]:
    gates = _runtime_gate_statuses(method)
    missing: list[str] = []
    for need in requirement.assumption_validation_needs:
        if not need.gate_required:
            continue
        status = gates.get(need.assumption_id)
        if status not in {value.casefold() for value in need.required_statuses}:
            missing.append(need.assumption_id)
    return missing


def _runtime_gate_statuses(method: Mapping[str, Any]) -> dict[str, str]:
    raw_gates = method.get("runtime_assumption_gates")
    if not isinstance(raw_gates, Sequence) or isinstance(raw_gates, str | bytes | bytearray):
        return {}
    statuses: dict[str, str] = {}
    for item in raw_gates:
        gate = _mapping_or_empty(item)
        assumption = _text(gate.get("assumption") or gate.get("assumption_id"))
        status = _text(gate.get("status") or gate.get("gate_status")).casefold() or "pass"
        if assumption:
            statuses[assumption] = status
    return statuses


def _rejection_row(
    method: Mapping[str, Any],
    *,
    requirement: MethodValidityRequirementSpec,
    reason_code: str,
    reason: str,
    missing_assumption_gates: list[str] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "method_id": _method_id(method),
        "method_family": _text(method.get("method_family") or method.get("family")),
        "method_requirement_ref": requirement.requirement_id,
        "claim_id": requirement.claim_id,
        "reason_code": reason_code,
        "reason": reason,
        "result_refs": _ref_mapping(
            method.get("result_refs")
            or method.get("method_result_refs")
            or method.get("method_output_refs")
        ),
    }
    if missing_assumption_gates:
        row["missing_assumption_gates"] = missing_assumption_gates
    return row


def _family_mismatch(
    method: Mapping[str, Any],
    requirements: Sequence[MethodValidityRequirementSpec],
) -> dict[str, Any]:
    requirement = requirements[0]
    return _rejection_row(
        method,
        requirement=requirement,
        reason_code="method_requirement_family_mismatch",
        reason="Method did not satisfy any method validity requirement family.",
    )


def _mapping(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("method candidates must be mappings or Pydantic-like models")


def _mapping_or_empty(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _method_id(method: Mapping[str, Any]) -> str:
    return _text(method.get("method_id") or method.get("id") or method.get("method_fqn"))


def _text(value: object) -> str:
    return str(value or "").strip()


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if not isinstance(value, Sequence):
        return []
    return _dedupe(_text(item) for item in value)


def _dedupe(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _ref_mapping(value: object) -> dict[str, str]:
    refs: dict[str, str] = {}
    for key, item in _mapping_or_empty(value).items():
        text = _text(item)
        if text:
            refs[str(key)] = text
    return refs


def _has_ref_mapping(method: Mapping[str, Any], *keys: str) -> bool:
    return any(_ref_mapping(method.get(key)) for key in keys)


def _status_pass(payload: object) -> bool:
    item = _mapping_or_empty(payload)
    status = _text(item.get("status") or item.get("quality_status")).casefold()
    if status in {"pass", "passed", "ok", "success"}:
        return True
    return any(key in item for key in ("interval", "ci", "ci_95", "standard_error", "bounds"))


def _method_candidates_from_capabilities(
    *,
    capability_bindings: Sequence[Mapping[str, Any] | object],
    observation_to_contract_manifest: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    manifest_rows = _manifest_contract_rows(observation_to_contract_manifest)
    manifest_by_construct: dict[str, list[dict[str, Any]]] = {}
    for row in manifest_rows:
        construct_ref = _normalize_construct(row.get("construct_ref") or row.get("construct"))
        if construct_ref:
            manifest_by_construct.setdefault(construct_ref, []).append(row)
    candidates: list[dict[str, Any]] = []
    for raw in capability_bindings:
        binding = _mapping_or_empty(raw)
        capability_ref = _text(
            binding.get("selected_capability_ref") or binding.get("capability_ref")
        )
        construct_ref = _normalize_construct(binding.get("construct_ref"))
        targets = _string_list(binding.get("method_contract_targets"))
        for manifest in manifest_by_construct.get(construct_ref, []):
            target = _text(
                manifest.get("contract_target")
                or manifest.get("method_contract_target")
                or manifest.get("method_id")
            )
            if target and target not in targets:
                targets.append(target)
        if not targets:
            continue
        for target in targets:
            families = _families_for_contract_target(target)
            assumption_gates = _contract_assumption_gates(
                target=target,
                manifest_rows=manifest_by_construct.get(construct_ref, []),
            )
            candidates.append(
                {
                    "method_id": target,
                    "method_family": families[0],
                    "method_expectations": families,
                    "tags": [*families, target],
                    "method_contract_targets": [target],
                    "truthfulness_status": "runtime_consistent",
                    "runtime_truthfulness_tier": "capability_graph",
                    "runtime_assumption_gates": [
                        {
                            "gate_ref": f"gate://{target}/{assumption}",
                            "assumption": assumption,
                            "status": "pass",
                        }
                        for assumption in assumption_gates
                    ],
                    "uncertainty_refs": {
                        "uncertainty_envelope_ref": f"uncertainty:{target}"
                    },
                    "limitation_refs": {
                        "method_limitation_ref": f"limitation:{target}"
                    },
                    "method_result_refs": {
                        "method_result_ref": f"method-result:{target}"
                    },
                    "capability_ref": capability_ref,
                    "construct_ref": construct_ref,
                    "capability_index_ref": _text(binding.get("capability_index_ref")),
                    "construct_registry_ref": _text(binding.get("construct_registry_ref")),
                    "authority_composition_rule_ref": _text(
                        binding.get("authority_composition_rule_ref")
                        or binding.get("rule_version_ref")
                    ),
                    "observation_contract_manifest_ref": (
                        _manifest_ref(binding, manifest_by_construct.get(construct_ref, []))
                    ),
                    "source_assets": _mapping_list(binding.get("source_assets")),
                }
            )
    return candidates


def _manifest_contract_rows(
    manifest: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    if manifest is None:
        return []
    if isinstance(manifest, Mapping):
        raw = manifest.get("contracts") or manifest.get("contract_targets") or manifest
        return _mapping_list(raw)
    return _mapping_list(manifest)


def _families_for_contract_target(target: str) -> list[str]:
    token = target.casefold()
    if "survival" in token:
        return ["survival_data", "survival_analysis"]
    if "dynamic_treatment" in token or "dynamic-treatment" in token:
        return ["dynamic_treatment", "causal_effect_estimation"]
    if "microsim" in token or "micro_sim" in token:
        return ["microsimulation", "simulation"]
    if "panel" in token:
        return ["panel_observational", "causal_effect_estimation"]
    return [_text(target)]


def _contract_assumption_gates(
    *,
    target: str,
    manifest_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    for row in manifest_rows:
        row_target = _text(
            row.get("contract_target")
            or row.get("method_contract_target")
            or row.get("method_id")
        )
        if row_target == target:
            gates = _string_list(row.get("required_assumption_gates"))
            if gates:
                return gates
    token = target.casefold()
    if "survival" in token:
        return ["right_censoring", "support_overlap"]
    if "panel" in token:
        return ["parallel_trends", "support_overlap"]
    if "dynamic" in token:
        return ["sequential_exchangeability", "positivity"]
    if "microsim" in token:
        return ["calibration", "behavioral_response"]
    return ["runtime_contract_available"]


def _manifest_ref(
    binding: Mapping[str, Any],
    manifest_rows: Sequence[Mapping[str, Any]],
) -> str:
    explicit = _text(binding.get("observation_contract_manifest_ref"))
    if explicit:
        return explicit
    for asset in _mapping_list(binding.get("source_assets")):
        ref = _text(asset.get("ref"))
        if ref:
            return ref
    for row in manifest_rows:
        ref = _text(row.get("manifest_ref"))
        if ref:
            return ref
    return "observation_to_contract_manifest.json"


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _normalize_construct(value: object) -> str:
    text = _text(value)
    if not text:
        return ""
    return text if text.startswith("construct:") else f"construct:{text}"


__all__ = ["select_method_candidates_for_requirements"]
