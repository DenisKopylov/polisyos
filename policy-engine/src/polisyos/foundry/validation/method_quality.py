"""Foundry method-validity quality reports for production canaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods.selection.requirements import (
    select_method_candidates_for_requirements,
)
from polisyos.method_requirement import normalize_method_requirements

SCHEMA_VERSION = "policyos.foundry.method_quality_report.v1"
REPORT_KIND = "foundry.method_quality_report"
REPORT_REF_KEY = "foundry_method_report_ref"
OBLIGATION_REPORT_REF_KEY = "foundry_method_obligation_report_ref"
_FOUNDRY_INPUT_REF_KEYS = (
    "data_snapshot_ref",
    "input_bindings_ref",
    "registry_bundle_ref",
)
_METHOD_RESULT_KEYS = (
    "causal_method_result_ref",
    "causal_query_method_result_ref",
    "econometric_result_ref",
    "simulation_result_ref",
)
_METHOD_EVIDENCE_KEYS = (
    "causal_method_evidence_ref",
    "causal_query_method_evidence_ref",
    "econometric_evidence_ref",
)
_METHOD_REPORT_KEYS = (
    "causal_report_ref",
    "causal_query_result_ref",
    "econometric_envelope_ref",
    "sensitivity_result_ref",
)
_SERIOUS_METHOD_EXPECTATIONS = frozenset(
    {
        "access_gap_estimation",
        "analytical_proof_surfaces",
        "assumptions",
        "budget_impact_estimation",
        "causal_effect_estimation",
        "conflict_sensitivity_analysis",
        "coverage_gap_diagnostic",
        "disparate_impact_diagnostic",
        "distributional_evidence",
        "distributional_incidence_analysis",
        "eligibility_coverage_estimation",
        "heterogeneity_by_region_or_firm_size",
        "implementation_feasibility",
        "interrupted_time_series",
        "limitations",
        "missingness_diagnostics",
        "negative_spillover_check",
        "objective_tradeoff_evidence",
        "program_effect_estimation",
        "recovery_effect_estimation",
        "regional_heterogeneity_estimation",
        "reliability_effect_estimation",
        "selection_bias_diagnostic",
        "subgroup_effect_estimation",
        "survival_effect_estimation",
        "uncertainty_interval",
        "sensitivity_to_take_up",
        "sensitivity_or_transportability_diagnostic",
        "take_up_model",
        "take_up_sensitivity",
        "targeting_error_estimation",
    }
)
_POLICY_METHOD_OBLIGATION_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "analytical_proof_surfaces": {
        "requirement_id": "foundry.method.analytical_proof_surfaces",
        "facets": ("method_refs", "analytical_proof_surfaces"),
    },
    "assumptions": {
        "requirement_id": "foundry.method.assumptions",
        "facets": ("method_refs", "assumptions"),
    },
    "causal_effect_estimation": {
        "requirement_id": "foundry.method.causal_effect_estimation",
        "facets": (
            "method_refs",
            "method_result_refs",
            "assumptions",
            "uncertainty_interval",
            "sensitivity_or_transportability",
            "missingness_diagnostics",
            "analytical_proof_surfaces",
        ),
    },
    "distributional_evidence": {
        "requirement_id": "foundry.method.distributional_evidence",
        "facets": (
            "method_refs",
            "objective_tradeoff_refs",
            "heterogeneity_evidence",
            "uncertainty_refs",
            "sensitivity_refs",
            "limitation_refs",
        ),
    },
    "heterogeneity_by_region_or_firm_size": {
        "requirement_id": "foundry.method.heterogeneity_by_region_or_firm_size",
        "facets": (
            "method_refs",
            "method_result_refs",
            "heterogeneity_evidence",
            "uncertainty_interval",
            "sensitivity_or_transportability",
            "limitation_refs",
        ),
    },
    "implementation_feasibility": {
        "requirement_id": "foundry.method.implementation_feasibility",
        "facets": (
            "method_refs",
            "objective_tradeoff_refs",
            "implementation_feasibility",
            "uncertainty_refs",
            "sensitivity_refs",
            "limitation_refs",
        ),
    },
    "limitations": {
        "requirement_id": "foundry.method.limitations",
        "facets": ("method_refs", "limitation_refs"),
    },
    "missingness_diagnostics": {
        "requirement_id": "foundry.method.missingness_diagnostics",
        "facets": ("method_refs", "missingness_diagnostics"),
    },
    "objective_tradeoff_evidence": {
        "requirement_id": "foundry.method.objective_tradeoff_evidence",
        "facets": ("method_refs", "objective_tradeoff_refs"),
    },
    "sensitivity_or_transportability_diagnostic": {
        "requirement_id": "foundry.method.sensitivity_or_transportability_diagnostic",
        "facets": ("method_refs", "sensitivity_or_transportability"),
    },
    "uncertainty_interval": {
        "requirement_id": "foundry.method.uncertainty_interval",
        "facets": ("method_refs", "uncertainty_interval"),
    },
}
_CROSS_CUTTING_METHOD_OBLIGATIONS = frozenset(
    {
        "analytical_proof_surfaces",
        "assumptions",
        "limitations",
        "missingness_diagnostics",
        "objective_tradeoff_evidence",
        "uncertainty_interval",
        "sensitivity_or_transportability_diagnostic",
    }
)
_HETEROGENEITY_EXPECTATION_MARKERS = (
    "heterogeneity",
    "subgroup",
    "distributional",
    "disparate",
)
_SENSITIVITY_EXPECTATION_MARKERS = (
    "sensitivity",
    "spillover",
    "selection_bias",
    "transportability",
)
_CORE_ESTIMATION_EXPECTATION_MARKERS = (
    "effect_estimation",
    "impact_estimation",
    "gap_estimation",
    "error_estimation",
    "coverage_estimation",
    "interrupted_time_series",
    "take_up_model",
)
_CAUSAL_ANALYTICAL_SURFACES = (
    "identification",
    "transportability",
    "partial_identification",
    "recoverability",
    "causal_ensemble",
    "falsification",
    "certificate_proof",
)
_SURFACE_REF_KEYS: dict[str, tuple[str, ...]] = {
    "identification": (
        "identification_ref",
        "identification_result_ref",
        "ir_identification_ref",
    ),
    "transportability": (
        "transportability_ref",
        "transportability_result_ref",
        "ir_transportability_ref",
    ),
    "partial_identification": (
        "partial_identification_ref",
        "partial_identification_result_ref",
        "bounds_ref",
    ),
    "recoverability": (
        "recoverability_ref",
        "recoverability_result_ref",
        "mgraph_recoverability_ref",
    ),
    "causal_ensemble": (
        "causal_ensemble_ref",
        "causal_ensemble_result_ref",
        "ensemble_ref",
    ),
    "falsification": (
        "falsification_ref",
        "falsification_result_ref",
        "negative_control_ref",
        "placebo_ref",
    ),
    "certificate_proof": (
        "certificate_ref",
        "proof_ref",
        "proof_bundle_ref",
        "certificate_proof_ref",
        "negative_certificate_ref",
    ),
}
_SURFACE_PAYLOAD_KEYS: dict[str, tuple[str, ...]] = {
    "identification": (
        "identification",
        "identification_result",
        "ir_identification",
    ),
    "transportability": (
        "transportability",
        "transportability_result",
        "ir_transportability",
    ),
    "partial_identification": (
        "partial_identification",
        "partial_identification_result",
        "bounds",
    ),
    "recoverability": (
        "recoverability",
        "recoverability_result",
        "mgraph_recoverability",
    ),
    "causal_ensemble": (
        "causal_ensemble",
        "causal_ensemble_result",
        "ensemble",
    ),
    "falsification": (
        "falsification",
        "falsification_result",
        "negative_controls",
        "placebo_tests",
    ),
    "certificate_proof": (
        "certificate",
        "proof",
        "proof_bundle",
        "negative_certificate",
    ),
}
_METHOD_VALIDITY_REGISTRY: dict[str, dict[str, Any]] = {
    "causal_effect_estimation": {
        "registry_id": "foundry.method_validity.causal_effect_estimation.v1",
        "candidate_method_families": (
            "causal_effect_estimation",
            "partial_identification",
            "causal_ensemble",
            "simulation",
        ),
        "analytical_surfaces": _CAUSAL_ANALYTICAL_SURFACES,
        "identification_requirements": {
            "requires_ir_identification": True,
            "requires_assumption_checks": True,
            "requires_overlap_or_support": True,
        },
        "transportability_limits": {
            "requires_target_population": True,
            "default_limit": (
                "Do not transport outside declared policy population, time, "
                "geography, and observed support."
            ),
        },
        "specification_space": {
            "requires_primary_specification": True,
            "requires_robustness_alternatives": True,
        },
    },
    "econometric_estimation": {
        "registry_id": "foundry.method_validity.econometric_estimation.v1",
        "candidate_method_families": ("econometric_estimation",),
        "analytical_surfaces": ("falsification", "certificate_proof"),
    },
    "simulation": {
        "registry_id": "foundry.method_validity.simulation.v1",
        "candidate_method_families": ("simulation",),
        "analytical_surfaces": ("certificate_proof",),
        "transportability_limits": {
            "default_limit": (
                "Simulation is scenario validity evidence unless paired with an "
                "analytical identification surface."
            ),
        },
    },
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _slug(value: object) -> str:
    text = "".join(
        ch if ch.isalnum() or ch in {".", "_", "-", ":"} else "-"
        for ch in _text(value)
    ).strip("-")
    return text or "method"


def _jsonable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return value


def _mapping(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _ref_id(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, Mapping):
        artifact_id = value.get("artifact_id")
        if artifact_id is not None:
            text = str(artifact_id).strip()
            return text or None
    artifact_id = getattr(value, "artifact_id", None)
    if artifact_id is None:
        return None
    text = str(artifact_id).strip()
    return text or None


def _normalize_ref_mapping(value: object) -> dict[str, str]:
    refs: dict[str, str] = {}
    for key, item in _mapping(value).items():
        ref = _ref_id(item)
        if ref is None and isinstance(item, str):
            ref = item.strip() or None
        if ref:
            refs[str(key)] = ref
    return refs


def _merge_ref_mappings(*values: object) -> dict[str, str]:
    refs: dict[str, str] = {}
    for value in values:
        refs.update(_normalize_ref_mapping(value))
    return refs


def _load_json_artifact(store: object, ref_value: object) -> dict[str, Any] | None:
    artifact_id = _ref_id(ref_value)
    if artifact_id is None or store is None:
        return None
    try:
        payload = from_canonical_bytes(store.get_bytes(ArtifactID(artifact_id)))
    except (AttributeError, FileNotFoundError, OSError, TypeError, ValueError):
        return None
    return _mapping(payload)


def _state_section(state: object, key: str) -> dict[str, Any]:
    if isinstance(state, Mapping):
        return _mapping(state.get(key))
    return _mapping(getattr(state, key, None))


def _state_value(state: object, key: str) -> object:
    if isinstance(state, Mapping):
        return state.get(key)
    return getattr(state, key, None)


def _method_id(method: dict[str, Any]) -> str:
    return _text(method.get("method_id") or method.get("id") or method.get("method_fqn"))


def _method_family(method: dict[str, Any]) -> str:
    return _text(
        method.get("method_family")
        or method.get("family")
        or method.get("method_expectation")
    )


def _method_expectations(method: dict[str, Any]) -> set[str]:
    values = method.get("method_expectations")
    if not isinstance(values, list):
        values = []
    family = _method_family(method)
    result = {_text(value).casefold() for value in values if _text(value)}
    if family:
        result.add(family.casefold())
    return result


def _registry_entry_for_method(method: dict[str, Any]) -> dict[str, Any]:
    family = _method_family(method).casefold()
    return dict(_METHOD_VALIDITY_REGISTRY.get(family) or {})


def _generic_simulation_candidate(method: dict[str, Any]) -> bool:
    family = _method_family(method).casefold()
    method_id = _method_id(method).casefold()
    return family == "simulation" and (
        method_id in {"foundry.execute", "simulation", "generic_simulation"}
        or "generic" in method_id
        or method_id.endswith(".execute")
    )


def _generic_execution_candidate(method: dict[str, Any]) -> bool:
    family = _method_family(method).casefold()
    method_id = _method_id(method).casefold()
    return _generic_simulation_candidate(method) or (
        method_id in {"foundry.execute", "execute", "method.execute"}
        or method_id.endswith(".execute")
        or (
            family in {"method_execution", "mechanism_runtime_execution"}
            and ("generic" in method_id or method_id in {"execute", "foundry.execute"})
        )
    )


def _has_serious_method_expectations(expected_method_expectations: set[str]) -> bool:
    return bool(expected_method_expectations.intersection(_SERIOUS_METHOD_EXPECTATIONS))


def _result_refs(method: dict[str, Any]) -> dict[str, str]:
    return _normalize_ref_mapping(method.get("result_refs") or method.get("method_result_refs"))


def _method_output_refs(method: dict[str, Any]) -> dict[str, str]:
    refs = _merge_ref_mappings(
        method.get("method_output_refs"),
        method.get("method_result_refs"),
        method.get("result_refs"),
    )
    return refs


def _generated_ref(prefix: str, method_id: str, label: str) -> str:
    return f"{prefix}:{_slug(method_id)}:{_slug(label)}"


def _assumption_status(value: object) -> str:
    if isinstance(value, Mapping):
        status = _text(value.get("status") or value.get("gate_status")).casefold()
    else:
        status = _text(value).casefold()
    if status in {"fail", "failed", "block", "blocked", "missing"}:
        return "fail"
    if status in {"warn", "warning", "limited", "degraded"}:
        return "warn"
    return "pass"


def _runtime_assumption_gates(method: dict[str, Any]) -> list[dict[str, str]]:
    raw_gates = method.get("runtime_assumption_gates")
    if isinstance(raw_gates, list) and raw_gates:
        gates: list[dict[str, str]] = []
        for item in raw_gates:
            gate = _mapping(item)
            gate_ref = _text(
                gate.get("gate_ref")
                or gate.get("assumption_gate_ref")
                or gate.get("ref")
                or gate.get("id")
            )
            assumption = _text(gate.get("assumption") or gate.get("assumption_id"))
            status = _assumption_status(gate.get("status") or gate.get("gate_status"))
            if gate_ref and assumption:
                gates.append(
                    {
                        "gate_ref": gate_ref,
                        "assumption": assumption,
                        "status": status,
                    }
                )
        return gates

    method_id = _method_id(method) or "method"
    explicit_refs = _normalize_ref_mapping(method.get("assumption_gate_refs"))
    assumptions = method.get("assumptions") or method.get("assumption_card")
    gates = []
    if isinstance(assumptions, Mapping):
        for assumption, value in assumptions.items():
            assumption_id = _text(assumption)
            if not assumption_id:
                continue
            gates.append(
                {
                    "gate_ref": explicit_refs.get(assumption_id)
                    or _generated_ref("foundry-assumption-gate", method_id, assumption_id),
                    "assumption": assumption_id,
                    "status": _assumption_status(value),
                }
            )
    else:
        for item in _as_list(assumptions):
            assumption_id = _text(item)
            if not assumption_id:
                continue
            gates.append(
                {
                    "gate_ref": explicit_refs.get(assumption_id)
                    or _generated_ref("foundry-assumption-gate", method_id, assumption_id),
                    "assumption": assumption_id,
                    "status": "pass",
                }
            )
    return gates


def _assumption_gate_refs(method: dict[str, Any]) -> dict[str, str]:
    raw_refs = method.get("assumption_gate_refs")
    if raw_refs is not None:
        refs = _normalize_ref_mapping(raw_refs)
        if refs:
            return refs
    return {
        gate["assumption"]: gate["gate_ref"]
        for gate in _runtime_assumption_gates(method)
        if gate.get("assumption") and gate.get("gate_ref")
    }


def _uncertainty_envelope_refs(method: dict[str, Any]) -> dict[str, str]:
    refs = _merge_ref_mappings(
        method.get("uncertainty_envelope_refs"),
        method.get("uncertainty_refs"),
    )
    if refs:
        return refs
    uncertainty = method.get("uncertainty") or method.get("uncertainty_envelope")
    if _status_pass(uncertainty):
        method_id = _method_id(method) or "method"
        return {
            "uncertainty_envelope_ref": _generated_ref(
                "foundry-uncertainty-envelope",
                method_id,
                "runtime",
            )
        }
    return {}


def _limitation_refs(method: dict[str, Any]) -> dict[str, str]:
    refs = _normalize_ref_mapping(method.get("limitation_refs"))
    if refs:
        return refs
    for key in ("limitations", "transportability_limits", "degradation"):
        if _mapping(method.get(key)):
            method_id = _method_id(method) or "method"
            return {
                "method_limitation_ref": _generated_ref(
                    "foundry-method-limitation",
                    method_id,
                    key,
                )
            }
    return {}


def _simulation_assumption_lineage_refs(method: dict[str, Any]) -> dict[str, str]:
    return _merge_ref_mappings(
        method.get("simulation_assumption_lineage_refs"),
        method.get("simulation_assumption_refs"),
        method.get("assumption_lineage_refs"),
        method.get("dgp_refs"),
    )


def _enrich_method_surfaces(method: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(method)
    enriched["method_output_refs"] = _method_output_refs(enriched)
    enriched["runtime_assumption_gates"] = _runtime_assumption_gates(enriched)
    enriched["assumption_gate_refs"] = _assumption_gate_refs(enriched)
    enriched["uncertainty_envelope_refs"] = _uncertainty_envelope_refs(enriched)
    enriched["limitation_refs"] = _limitation_refs(enriched)
    lineage_refs = _simulation_assumption_lineage_refs(enriched)
    if lineage_refs:
        enriched["simulation_assumption_lineage_refs"] = lineage_refs
    return enriched


def _surface_ref(surface: Mapping[str, Any]) -> str | None:
    for key in (
        "ref",
        "artifact_ref",
        "artifact_id",
        "result_ref",
        "certificate_ref",
        "proof_ref",
    ):
        ref = _ref_id(surface.get(key))
        if ref:
            return ref
    return None


def _registry_surface_issues(
    method: dict[str, Any],
    *,
    method_id: str,
) -> list[dict[str, Any]]:
    registry = _registry_entry_for_method(method)
    required_surfaces = tuple(str(surface) for surface in registry.get("analytical_surfaces") or ())
    if not required_surfaces:
        return []

    issues: list[dict[str, Any]] = []
    validity_surfaces = _mapping(method.get("validity_surfaces"))
    missing_surfaces: list[str] = []
    for surface_name in required_surfaces:
        surface = _mapping(validity_surfaces.get(surface_name))
        status = _text(surface.get("status")).casefold()
        if _surface_ref(surface) and status not in {"fail", "failed", "missing"}:
            continue
        missing_surfaces.append(surface_name)
    if missing_surfaces:
        issues.append(
            _issue(
                code="method_validity_surface_missing",
                method_id=method_id,
                message=(
                    f"Method {method_id or '<missing>'} is missing registry-required "
                    "validity surfaces: " + ", ".join(missing_surfaces) + "."
                ),
                next_action=(
                    "Persist IR identification, transportability, partial "
                    "identification, recoverability, causal ensemble, falsification, "
                    "and certificate/proof refs selected by the method-validity registry."
                ),
            )
        )
    return issues


def _status_pass(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    status = _text(payload.get("status") or payload.get("quality_status")).casefold()
    if status in {"pass", "passed", "ok", "success"}:
        return True
    if status in {"not_applicable", "not-applicable", "n/a", "na"}:
        return bool(_text(payload.get("rationale") or payload.get("reason")))
    return bool(payload.get("present")) or any(
        key in payload
        for key in (
            "interval",
            "ci",
            "ci_95",
            "standard_error",
            "posterior",
            "robustness",
            "missing_rate",
        )
    )


def _first_ref_for_keys(
    keys: tuple[str, ...],
    *payloads: dict[str, Any],
) -> str | None:
    for payload in payloads:
        for key in keys:
            ref = _ref_id(payload.get(key))
            if ref:
                return ref
    return None


def _first_mapping_for_keys(
    keys: tuple[str, ...],
    *payloads: dict[str, Any],
) -> dict[str, Any]:
    for payload in payloads:
        for key in keys:
            candidate = _mapping(payload.get(key))
            if candidate:
                return candidate
    return {}


def _surface_status(ref: str | None, payload: dict[str, Any]) -> str:
    if _status_pass(payload):
        return "pass"
    if ref:
        return "present"
    if payload:
        return _text(payload.get("status") or payload.get("quality_status")) or "present"
    return "missing"


def _validity_surfaces_from_payloads(
    *,
    method_family: str,
    output: dict[str, Any],
    report: dict[str, Any],
    evidence: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    registry = _METHOD_VALIDITY_REGISTRY.get(method_family.casefold()) or {}
    surfaces: dict[str, dict[str, Any]] = {}
    for surface in registry.get("analytical_surfaces") or ():
        surface_name = str(surface)
        ref = _first_ref_for_keys(
            _SURFACE_REF_KEYS.get(surface_name, ()),
            output,
            report,
            evidence,
            result,
        )
        payload = _first_mapping_for_keys(
            _SURFACE_PAYLOAD_KEYS.get(surface_name, ()),
            output,
            report,
            evidence,
            result,
        )
        surfaces[surface_name] = {
            "surface": surface_name,
            "required_by_registry": True,
            "status": _surface_status(ref, payload),
            "ref": ref,
        }
        if payload:
            surfaces[surface_name]["payload"] = payload
    return surfaces


def _identification_requirements_from_payloads(
    *,
    method_family: str,
    output: dict[str, Any],
    report: dict[str, Any],
    evidence: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    explicit = _first_mapping(
        output.get("identification_requirements"),
        report.get("identification_requirements"),
        evidence.get("identification_requirements"),
        result.get("identification_requirements"),
    )
    if explicit:
        return explicit
    identification = _first_mapping_for_keys(
        _SURFACE_PAYLOAD_KEYS["identification"],
        output,
        report,
        evidence,
        result,
    )
    if identification:
        return {
            key: value
            for key, value in identification.items()
            if key in {"estimand", "requirements", "assumptions", "strategy", "status"}
        }
    registry = _METHOD_VALIDITY_REGISTRY.get(method_family.casefold()) or {}
    return dict(_mapping(registry.get("identification_requirements")))


def _transportability_limits_from_payloads(
    *,
    method_family: str,
    output: dict[str, Any],
    report: dict[str, Any],
    evidence: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    explicit = _first_mapping(
        output.get("transportability_limits"),
        report.get("transportability_limits"),
        evidence.get("transportability_limits"),
        result.get("transportability_limits"),
    )
    if explicit:
        return explicit
    transport = _first_mapping_for_keys(
        _SURFACE_PAYLOAD_KEYS["transportability"],
        output,
        report,
        evidence,
        result,
    )
    if transport:
        return {
            key: value
            for key, value in transport.items()
            if key in {"limits", "target_population", "domain", "status", "warnings"}
        }
    registry = _METHOD_VALIDITY_REGISTRY.get(method_family.casefold()) or {}
    return dict(_mapping(registry.get("transportability_limits")))


def _missingness_handling_from_payloads(
    *,
    report: dict[str, Any],
    evidence: dict[str, Any],
    result: dict[str, Any],
    missingness: dict[str, Any],
) -> dict[str, Any]:
    metadata = _mapping(report.get("metadata"))
    artifacts = _mapping(evidence.get("artifacts"))
    explicit = _first_mapping(
        report.get("missingness_handling"),
        result.get("missingness_handling"),
        metadata.get("missingness_handling"),
        artifacts.get("missingness_handling"),
    )
    if explicit:
        return explicit
    if missingness:
        return {
            "status": missingness.get("status") or missingness.get("quality_status"),
            "missing_rate": missingness.get("missing_rate"),
            "diagnostic": missingness.get("diagnostic"),
        }
    return {}


def _specification_space_from_payloads(
    *,
    method_family: str,
    output: dict[str, Any],
    report: dict[str, Any],
    evidence: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    metadata = _mapping(report.get("metadata"))
    artifacts = _mapping(evidence.get("artifacts"))
    explicit = _first_mapping(
        output.get("specification_space"),
        report.get("specification_space"),
        result.get("specification_space"),
        metadata.get("specification_space"),
        artifacts.get("specification_space"),
    )
    if explicit:
        return explicit
    registry = _METHOD_VALIDITY_REGISTRY.get(method_family.casefold()) or {}
    return dict(_mapping(registry.get("specification_space")))


def _issue(
    *,
    code: str,
    message: str,
    method_id: str | None = None,
    severity: str = "fail",
    next_action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "layer": "foundry_methods",
        "phase": "method_quality",
        "method_id": method_id,
        "message": message,
        "next_action": next_action,
    }


def _status_from_issues(issues: list[dict[str, Any]]) -> str:
    if any(issue.get("severity") == "fail" for issue in issues):
        return "fail"
    if any(issue.get("severity") == "warn" for issue in issues):
        return "warn"
    return "pass"


def _has_ref_or_mapping(method: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = method.get(key)
        if _normalize_ref_mapping(value):
            return True
        if _mapping(value):
            return True
    return False


def _has_assumptions(method: dict[str, Any]) -> bool:
    assumptions = method.get("assumptions") or method.get("assumption_card")
    return bool(
        (isinstance(assumptions, list) and assumptions)
        or (isinstance(assumptions, dict) and assumptions)
    )


def _has_validity_surface(method: dict[str, Any], *surface_names: str) -> bool:
    validity_surfaces = _mapping(method.get("validity_surfaces"))
    if not validity_surfaces:
        return False
    names = surface_names or tuple(str(key) for key in validity_surfaces)
    for surface_name in names:
        surface = _mapping(validity_surfaces.get(surface_name))
        if _surface_ref(surface):
            return True
        status = _text(surface.get("status")).casefold()
        if status in {"pass", "present", "satisfied", "ok", "success"}:
            return True
    return False


def _facet_present(method: dict[str, Any], facet: str) -> bool:
    if facet == "method_refs":
        return bool(_normalize_ref_mapping(method.get("method_refs")) or _method_id(method))
    if facet == "method_result_refs":
        return bool(
            _normalize_ref_mapping(method.get("method_result_refs")) or _result_refs(method)
        )
    if facet.endswith("_refs"):
        return bool(_normalize_ref_mapping(method.get(facet)))
    if facet == "assumptions":
        return _has_assumptions(method)
    if facet == "uncertainty_interval":
        return bool(
            _status_pass(method.get("uncertainty") or method.get("uncertainty_envelope"))
            or _normalize_ref_mapping(method.get("uncertainty_refs"))
        )
    if facet == "sensitivity_or_transportability":
        return bool(
            _status_pass(method.get("sensitivity"))
            or _normalize_ref_mapping(method.get("sensitivity_refs"))
            or _mapping(method.get("transportability_limits"))
            or _has_validity_surface(method, "transportability", "falsification")
        )
    if facet == "missingness_diagnostics":
        return bool(
            _status_pass(method.get("missingness"))
            or _status_pass(method.get("missingness_handling"))
            or _normalize_ref_mapping(method.get("missingness_refs"))
        )
    if facet == "analytical_proof_surfaces":
        return bool(
            _has_validity_surface(method)
            or _normalize_ref_mapping(method.get("analytical_proof_refs"))
            or _normalize_ref_mapping(method.get("proof_refs"))
            or _normalize_ref_mapping(method.get("certificate_refs"))
        )
    payload = _mapping(method.get(facet))
    if _status_pass(payload) or _normalize_ref_mapping(payload):
        return True
    if facet == "heterogeneity_evidence":
        return bool(
            _status_pass(method.get("distributional_evidence"))
            or _status_pass(method.get("heterogeneity"))
            or _has_ref_or_mapping(method, "distributional_evidence", "heterogeneity")
            or _normalize_ref_mapping(method.get("distributional_refs"))
            or _normalize_ref_mapping(method.get("heterogeneity_refs"))
            or _normalize_ref_mapping(method.get("subgroup_effect_refs"))
        )
    if facet == "implementation_feasibility":
        return bool(
            _normalize_ref_mapping(method.get("implementation_feasibility_refs"))
            or _normalize_ref_mapping(method.get("delivery_capacity_refs"))
            or _normalize_ref_mapping(method.get("agency_readiness_refs"))
        )
    return False


def _missing_obligation_facets(
    method: dict[str, Any],
    *,
    facets: tuple[str, ...],
) -> list[str]:
    return [facet for facet in facets if not _facet_present(method, facet)]


def _dynamic_method_obligation_requirement(expectation: str) -> dict[str, Any]:
    expectation_token = expectation.casefold()
    if any(marker in expectation_token for marker in _HETEROGENEITY_EXPECTATION_MARKERS):
        facets = (
            "method_refs",
            "method_result_refs",
            "heterogeneity_evidence",
            "uncertainty_interval",
            "sensitivity_or_transportability",
            "limitation_refs",
        )
    elif any(marker in expectation_token for marker in _SENSITIVITY_EXPECTATION_MARKERS):
        facets = (
            "method_refs",
            "method_result_refs",
            "sensitivity_or_transportability",
            "limitation_refs",
        )
    elif any(marker in expectation_token for marker in _CORE_ESTIMATION_EXPECTATION_MARKERS):
        facets = (
            "method_refs",
            "method_result_refs",
            "assumptions",
            "uncertainty_interval",
            "missingness_diagnostics",
        )
    elif "coverage_gap" in expectation_token:
        facets = (
            "method_refs",
            "method_result_refs",
            "missingness_diagnostics",
            "heterogeneity_evidence",
        )
    else:
        facets = ("method_refs", "method_result_refs", "uncertainty_interval")
    return {
        "requirement_id": f"foundry.method.{expectation_token}",
        "facets": facets,
    }


def _method_obligation_requirement(expectation: str) -> dict[str, Any]:
    return dict(
        _POLICY_METHOD_OBLIGATION_REQUIREMENTS.get(expectation)
        or _dynamic_method_obligation_requirement(expectation)
    )


def _method_matches_obligation(method: dict[str, Any], expectation: str) -> bool:
    if _generic_execution_candidate(method):
        return False
    if expectation in _CROSS_CUTTING_METHOD_OBLIGATIONS:
        return True
    return expectation in _method_expectations(method)


def _build_method_obligations(
    *,
    selected_methods: list[dict[str, Any]],
    expected_method_expectations: set[str],
) -> list[dict[str, Any]]:
    obligations: list[dict[str, Any]] = []
    for expectation in sorted(expected_method_expectations):
        requirement = _method_obligation_requirement(expectation)
        facets = tuple(str(facet) for facet in requirement.get("facets") or ())
        matching_methods = [
            method
            for method in selected_methods
            if isinstance(method, dict)
            and _method_matches_obligation(method, expectation)
        ]
        satisfied_method_ids: list[str] = []
        missing_facets: set[str] = set(facets)
        for method in matching_methods:
            missing_for_method = _missing_obligation_facets(method, facets=facets)
            if not missing_for_method:
                method_id = _method_id(method)
                if method_id:
                    satisfied_method_ids.append(method_id)
                missing_facets.clear()
            else:
                missing_facets.intersection_update(missing_for_method)
        obligations.append(
            {
                "requirement_id": str(requirement["requirement_id"]),
                "expectation": expectation,
                "status": "satisfied" if satisfied_method_ids else "missing",
                "selected_method_refs": satisfied_method_ids,
                "missing_facets": sorted(missing_facets) if not satisfied_method_ids else [],
            }
        )
    return obligations


def _method_obligation_issues(
    obligations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for obligation in obligations:
        if obligation.get("status") == "satisfied":
            continue
        expectation = _text(obligation.get("expectation"))
        missing = ", ".join(str(item) for item in obligation.get("missing_facets") or [])
        issues.append(
            _issue(
                code="method_obligation_missing",
                method_id=expectation,
                message=(
                    f"Expected Foundry method obligation {expectation or '<missing>'} "
                    f"is missing required facets: {missing or '<none recorded>'}."
                ),
                next_action=(
                    "Select a named analytical method before claim drafting and persist "
                    "method refs, objective/tradeoff refs, uncertainty, sensitivity, "
                    "limitations, and obligation-specific evidence."
                ),
            )
        )
    return issues


def _method_independence_report(selected_methods: list[dict[str, Any]]) -> dict[str, Any]:
    signatures: dict[tuple[str, ...], list[str]] = {}
    independent = 0
    for method in selected_methods:
        method_id = _method_id(method) or "<missing>"
        lineage_refs = tuple(sorted(_simulation_assumption_lineage_refs(method).values()))
        if lineage_refs:
            signatures.setdefault(lineage_refs, []).append(method_id)
        else:
            independent += 1

    collapse_reasons = [
        {
            "reason_code": "shared_simulation_assumption_lineage",
            "simulation_assumption_lineage_refs": list(lineage_refs),
            "method_refs": method_ids,
            "effective_independent_count": 1,
            "raw_method_count": len(method_ids),
        }
        for lineage_refs, method_ids in signatures.items()
        if len(method_ids) > 1
    ]
    independent += len(signatures)
    return {
        "raw_method_count": len(selected_methods),
        "effective_independent_method_count": independent,
        "collapse_reasons": collapse_reasons,
    }


def _method_independence_issues(
    independence_report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not independence_report.get("collapse_reasons"):
        return []
    return [
        _issue(
            code="method_independence_collapsed_by_shared_assumptions",
            severity="warn",
            message=(
                "Multiple Foundry method outputs share simulation assumption lineage "
                "and cannot count as fully independent method evidence."
            ),
            next_action=(
                "Report effective method independence and collapse reasons instead of "
                "raw method counts."
            ),
        )
    ]


def _has_point_estimate(method: dict[str, Any]) -> bool:
    result_summary = method.get("result_summary")
    if not isinstance(result_summary, dict):
        return False
    estimate_keys = {
        "effect_estimate",
        "point_estimate",
        "estimate",
        "ate",
        "att",
        "coefficient",
        "mean_effect",
    }
    return any(key in result_summary for key in estimate_keys)


def _sample_size_diagnostics(method: dict[str, Any]) -> tuple[float | None, float | None]:
    diagnostics = method.get("input_diagnostics")
    if not isinstance(diagnostics, dict):
        return None, None
    try:
        sample_size = float(diagnostics.get("sample_size"))
    except (TypeError, ValueError):
        sample_size = None
    try:
        minimum = float(
            diagnostics.get("min_required_sample_size")
            or diagnostics.get("minimum_sample_size")
            or diagnostics.get("min_effective_sample_size")
        )
    except (TypeError, ValueError):
        minimum = None
    return sample_size, minimum


def _degradation_status(method: dict[str, Any]) -> str | None:
    degradation = method.get("degradation") or method.get("degrade")
    if not isinstance(degradation, dict):
        return None
    status = _text(degradation.get("status")).casefold()
    if status in {"degraded", "fail", "failed", "blocked", "insufficient_data"}:
        return status
    return None


def _has_degradation(method: dict[str, Any]) -> bool:
    return _degradation_status(method) is not None


def _validate_method(
    method: dict[str, Any],
    *,
    expected_method_expectations: set[str],
    foundry_input_refs: dict[str, str],
) -> list[dict[str, Any]]:
    method_id = _method_id(method)
    issues: list[dict[str, Any]] = []
    expectations = _method_expectations(method)

    if not method_id:
        issues.append(
            _issue(
                code="method_id_missing",
                message="Selected Foundry method is missing method_id.",
                next_action="Persist method_id or method_fqn in the Foundry method report.",
            )
        )

    if expected_method_expectations:
        if not expectations.intersection(expected_method_expectations):
            issues.append(
                _issue(
                    code="method_family_not_expected",
                    method_id=method_id,
                    message=(
                        f"Method {method_id or '<missing>'} does not match expected "
                        "golden scenario method expectations."
                    ),
                    next_action=(
                        "Select an appropriate Foundry method or update the scenario "
                        "method expectation contract."
                    ),
                )
            )
        if (
            "causal_effect_estimation" in expected_method_expectations
            and _generic_simulation_candidate(method)
        ):
            issues.append(
                _issue(
                    code="generic_simulation_false_pass",
                    method_id=method_id,
                    message=(
                        "Generic Foundry simulation output cannot satisfy an expected "
                        "analytical causal method family."
                    ),
                    next_action=(
                        "Select an executed causal/econometric method with IR "
                        "identification and proof surfaces, or explicitly reject the "
                        "generic simulation candidate."
                    ),
                )
            )
        elif (
            _has_serious_method_expectations(expected_method_expectations)
            and _generic_execution_candidate(method)
        ):
            issues.append(
                _issue(
                    code="generic_method_not_admissible",
                    method_id=method_id,
                    message=(
                        "Generic Foundry execution output cannot satisfy serious policy "
                        "method obligations without a named analytical method."
                    ),
                    next_action=(
                        "Select and execute a registered method that declares the "
                        "required scenario method expectations and persists obligation "
                        "refs before claim drafting."
                    ),
                )
            )

    if "causal_effect_estimation" in expectations or (
        "causal_effect_estimation" in expected_method_expectations
        and expectations.intersection(expected_method_expectations)
    ):
        if not _mapping(method.get("identification_requirements")):
            issues.append(
                _issue(
                    code="method_identification_requirements_missing",
                    method_id=method_id,
                    message=(
                        f"Method {method_id or '<missing>'} is missing identification "
                        "requirements."
                    ),
                    next_action=(
                        "Emit the estimand and identification requirements selected by "
                        "the Foundry method-validity registry."
                    ),
                )
            )
        if not _mapping(method.get("transportability_limits")):
            issues.append(
                _issue(
                    code="method_transportability_limits_missing",
                    method_id=method_id,
                    message=(
                        f"Method {method_id or '<missing>'} is missing transportability "
                        "limits."
                    ),
                    next_action=(
                        "Emit target-population and support limits before using the "
                        "method result for policy closeout."
                    ),
                )
            )
        if not _mapping(method.get("specification_space")):
            issues.append(
                _issue(
                    code="method_specification_space_missing",
                    method_id=method_id,
                    message=(
                        f"Method {method_id or '<missing>'} is missing specification "
                        "space."
                    ),
                    next_action=(
                        "Record the primary specification and robustness alternatives."
                    ),
                )
            )
        if not _result_refs(method):
            issues.append(
                _issue(
                    code="method_result_refs_missing",
                    method_id=method_id,
                    message=f"Method {method_id or '<missing>'} is missing result refs.",
                    next_action=(
                        "Persist method-result refs from the executed Foundry method."
                    ),
                )
            )
        issues.extend(_registry_surface_issues(method, method_id=method_id))

    input_refs = method.get("input_refs")
    if not isinstance(input_refs, dict) or not input_refs:
        issues.append(
            _issue(
                code="method_input_refs_missing",
                method_id=method_id,
                message=f"Method {method_id or '<missing>'} is missing input refs.",
                next_action="Record data snapshot/input binding refs used by the method.",
            )
        )
    elif foundry_input_refs:
        method_input_refs = _normalize_ref_mapping(input_refs)
        for key in ("data_snapshot_ref", "input_bindings_ref"):
            expected_ref = foundry_input_refs.get(key)
            if not expected_ref:
                continue
            actual_ref = method_input_refs.get(key)
            if not actual_ref:
                issues.append(
                    _issue(
                        code="method_input_ref_missing",
                        method_id=method_id,
                        message=(
                            f"Method {method_id or '<missing>'} is missing Foundry input "
                            f"reference {key}."
                        ),
                        next_action="Record the exact data snapshot and input bindings used.",
                    )
                )
            elif actual_ref != expected_ref:
                issues.append(
                    _issue(
                        code="method_input_ref_mismatch",
                        method_id=method_id,
                        message=(
                            f"Method {method_id or '<missing>'} references {key}={actual_ref}, "
                            f"but Foundry used {expected_ref}."
                        ),
                        next_action=(
                            "Regenerate the method report from the same Foundry execution "
                            "inputs instead of stale or synthetic bindings."
                        ),
                    )
                )

    assumptions = method.get("assumptions") or method.get("assumption_card")
    if not (
        (isinstance(assumptions, list) and assumptions)
        or (isinstance(assumptions, dict) and assumptions)
    ):
        issues.append(
            _issue(
                code="method_assumptions_missing",
                method_id=method_id,
                message=f"Method {method_id or '<missing>'} is missing assumptions.",
                next_action="Persist method assumptions in the workflow report.",
            )
        )

    method_output_refs = _method_output_refs(method)
    assumption_gate_refs = _assumption_gate_refs(method)
    runtime_assumption_gates = _runtime_assumption_gates(method)
    if method_output_refs and not assumption_gate_refs:
        issues.append(
            _issue(
                code="method_assumption_gate_refs_missing",
                method_id=method_id,
                message=(
                    f"Method {method_id or '<missing>'} emits method outputs without "
                    "runtime assumption gate refs."
                ),
                next_action=(
                    "Record assumption gates before using method outputs for "
                    "claim-bound policy authority."
                ),
            )
        )
    failed_gates = [
        gate.get("gate_ref") or gate.get("assumption")
        for gate in runtime_assumption_gates
        if _text(gate.get("status")).casefold() in {"fail", "failed", "block", "blocked"}
    ]
    if failed_gates:
        issues.append(
            _issue(
                code="method_assumption_gate_failed",
                method_id=method_id,
                message=f"Method {method_id or '<missing>'} has failing assumption gates.",
                next_action=(
                    "Reject, degrade, or rerun the method before binding its outputs "
                    "to claims."
                ),
            )
        )

    uncertainty = method.get("uncertainty") or method.get("uncertainty_envelope")
    if not _status_pass(uncertainty):
        code = (
            "point_estimate_without_uncertainty"
            if _has_point_estimate(method)
            else "method_uncertainty_missing"
        )
        issues.append(
            _issue(
                code=code,
                method_id=method_id,
                message=(
                    f"Method {method_id or '<missing>'} has no passing uncertainty "
                    "diagnostics."
                ),
                next_action="Attach uncertainty interval/envelope before policy approval.",
            )
        )
    if method_output_refs and not _uncertainty_envelope_refs(method):
        issues.append(
            _issue(
                code="method_uncertainty_refs_missing",
                method_id=method_id,
                message=(
                    f"Method {method_id or '<missing>'} emits outputs without "
                    "uncertainty envelope refs."
                ),
                next_action=(
                    "Persist uncertainty envelope refs alongside method outputs before "
                    "claims consume them."
                ),
            )
        )

    if method_output_refs and not _limitation_refs(method):
        issues.append(
            _issue(
                code="method_limitation_refs_missing",
                method_id=method_id,
                message=f"Method {method_id or '<missing>'} emits outputs without limitation refs.",
                next_action=(
                    "Record transportability, scope, degradation, or other method "
                    "limitation refs before policy closeout."
                ),
            )
        )

    if not _status_pass(method.get("missingness")):
        issues.append(
            _issue(
                code="method_missingness_diagnostics_missing",
                method_id=method_id,
                message=f"Method {method_id or '<missing>'} is missing missingness diagnostics.",
                next_action="Record missingness diagnostics or explicit not-applicable rationale.",
            )
        )

    if not _status_pass(method.get("sensitivity")):
        issues.append(
            _issue(
                code="method_sensitivity_missing",
                method_id=method_id,
                message=f"Method {method_id or '<missing>'} is missing sensitivity evidence.",
                next_action="Run sensitivity diagnostics or record why they are not applicable.",
            )
        )

    sample_size, minimum = _sample_size_diagnostics(method)
    if sample_size is not None and minimum is not None and sample_size < minimum:
        degradation_status = _degradation_status(method)
        if degradation_status is None:
            issues.append(
                _issue(
                    code="insufficient_data_without_degrade",
                    method_id=method_id,
                    message=(
                        f"Method {method_id or '<missing>'} has sample_size={sample_size:g} "
                        f"below minimum={minimum:g} without explicit degrade/fail status."
                    ),
                    next_action=(
                        "Mark the method as degraded/failed or choose a method suitable "
                        "for the available data."
                    ),
                )
            )
        else:
            issues.append(
                _issue(
                    code=(
                        "insufficient_data_failed"
                        if degradation_status in {"fail", "failed", "blocked"}
                        else "insufficient_data_degraded"
                    ),
                    method_id=method_id,
                    severity=(
                        "fail" if degradation_status in {"fail", "failed", "blocked"} else "warn"
                    ),
                    message=(
                        f"Method {method_id or '<missing>'} has sample_size={sample_size:g} "
                        f"below minimum={minimum:g} and is explicitly {degradation_status}."
                    ),
                    next_action=(
                        "Treat this method output as degraded/failing in policy approval "
                        "or rerun with sufficient data."
                    ),
                )
            )

    if (
        _method_family(method).casefold() == "simulation"
        and not _simulation_assumption_lineage_refs(method)
    ):
        issues.append(
            _issue(
                code="simulation_assumption_lineage_missing",
                method_id=method_id,
                message=(
                    f"Simulation method {method_id or '<missing>'} has no simulation "
                    "assumption lineage refs."
                ),
                next_action=(
                    "Attach scenario, DGP, behavioral, or take-up assumption lineage "
                    "before simulation output is used as method evidence."
                ),
            )
        )

    return issues


def _as_list(value: object) -> list[object]:
    if isinstance(value, list | tuple):
        return list(value)
    return []


def _first_mapping(*values: object) -> dict[str, Any]:
    for value in values:
        candidate = _mapping(value)
        if candidate:
            return candidate
    return {}


def _report_payload(output: dict[str, Any]) -> dict[str, Any]:
    method_result = _mapping(output.get("method_result"))
    for candidate in (
        output.get("causal_report"),
        output.get("report"),
        method_result.get("report"),
        method_result,
    ):
        payload = _mapping(candidate)
        if payload and (
            "method" in payload
            or "method_id" in payload
            or "point_estimate" in payload
            or "confidence_interval" in payload
        ):
            return payload
    return {}


def _evidence_payload(output: dict[str, Any]) -> dict[str, Any]:
    return _mapping(output.get("method_evidence") or output.get("evidence"))


def _result_payload(output: dict[str, Any]) -> dict[str, Any]:
    return _mapping(output.get("method_result") or output.get("result"))


def _method_id_from_output(
    output: dict[str, Any],
    *,
    report: dict[str, Any],
    evidence: dict[str, Any],
    result: dict[str, Any],
) -> str:
    return _text(
        output.get("method_id")
        or output.get("method_fqn")
        or evidence.get("method_fqn")
        or evidence.get("method_id")
        or result.get("method_fqn")
        or result.get("method_id")
        or report.get("method_fqn")
        or report.get("method")
        or output.get("simulation_method")
    )


def _infer_method_family(
    method_id: str,
    *,
    report: dict[str, Any],
    evidence: dict[str, Any],
    output: dict[str, Any],
) -> str:
    explicit = _text(
        output.get("method_family")
        or report.get("method_family")
        or evidence.get("method_family")
    )
    if explicit:
        return explicit
    haystack = " ".join(
        _text(value).casefold()
        for value in (
            method_id,
            report.get("method"),
            report.get("estimand"),
            evidence.get("method_fqn"),
        )
    )
    if "causal" in haystack or "estimand" in report or "n_treated" in report:
        return "causal_effect_estimation"
    if "econometric" in haystack:
        return "econometric_estimation"
    if "microsim" in haystack:
        return "microsimulation"
    if "simulation" in haystack or method_id == "foundry.execute":
        return "simulation"
    return "method_execution"


def _assumptions_from_payloads(
    *,
    report: dict[str, Any],
    evidence: dict[str, Any],
    result: dict[str, Any],
) -> list[Any]:
    assumptions = _first_mapping(
        report.get("assumptions"),
        result.get("assumptions"),
        _mapping(evidence.get("artifacts")).get("assumptions"),
    )
    if assumptions:
        return sorted(str(key) for key in assumptions)
    for value in (
        report.get("assumptions"),
        result.get("assumptions"),
        _mapping(evidence.get("artifacts")).get("assumptions"),
    ):
        values = [item for item in _as_list(value) if _text(item)]
        if values:
            return values
    return []


def _uncertainty_from_payloads(
    *,
    report: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    explicit = _first_mapping(
        report.get("uncertainty"),
        report.get("uncertainty_envelope"),
        result.get("uncertainty"),
        result.get("uncertainty_envelope"),
    )
    if explicit:
        return explicit
    interval = report.get("confidence_interval")
    standard_error = report.get("standard_error")
    if isinstance(interval, list | tuple) or standard_error is not None:
        payload: dict[str, Any] = {
            "status": "pass",
            "source": "causal_effect_report",
        }
        if isinstance(interval, list | tuple):
            payload["interval"] = list(interval)
        if report.get("confidence_level") is not None:
            payload["confidence_level"] = report.get("confidence_level")
        if standard_error is not None:
            payload["standard_error"] = standard_error
        return payload
    return {}


def _missingness_from_payloads(
    *,
    report: dict[str, Any],
    evidence: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    metadata = _mapping(report.get("metadata"))
    artifacts = _mapping(evidence.get("artifacts"))
    explicit = _first_mapping(
        report.get("missingness"),
        report.get("missingness_diagnostics"),
        result.get("missingness"),
        result.get("missingness_diagnostics"),
        metadata.get("missingness"),
        artifacts.get("missingness"),
    )
    if explicit:
        return explicit
    handling = _first_mapping(
        report.get("missingness_handling"),
        result.get("missingness_handling"),
        metadata.get("missingness_handling"),
        artifacts.get("missingness_handling"),
    )
    if handling:
        payload = {
            "status": handling.get("status") or "pass",
            "handling": handling.get("strategy") or handling.get("method"),
        }
        if handling.get("missing_rate") is not None:
            payload["missing_rate"] = handling["missing_rate"]
        return payload
    for diagnostic in _as_list(report.get("diagnostics")):
        item = _mapping(diagnostic)
        name = _text(item.get("test_name") or item.get("name")).casefold()
        if "missing" not in name:
            continue
        details = _mapping(item.get("details"))
        payload = {
            "status": "pass" if bool(item.get("passed")) else "fail",
            "diagnostic": item.get("test_name") or item.get("name"),
        }
        if "missing_rate" in details:
            payload["missing_rate"] = details["missing_rate"]
        return payload
    if metadata.get("missingness_not_applicable_rationale"):
        return {
            "status": "not_applicable",
            "rationale": metadata.get("missingness_not_applicable_rationale"),
        }
    return {}


def _sensitivity_from_payloads(
    *,
    output: dict[str, Any],
    report: dict[str, Any],
    evidence: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    metadata = _mapping(report.get("metadata"))
    artifacts = _mapping(evidence.get("artifacts"))
    explicit = _first_mapping(
        output.get("sensitivity_result"),
        report.get("sensitivity"),
        report.get("sensitivity_diagnostics"),
        result.get("sensitivity"),
        result.get("sensitivity_diagnostics"),
        metadata.get("sensitivity"),
        metadata.get("sensitivity_auto"),
        artifacts.get("sensitivity"),
    )
    if explicit:
        status = _text(explicit.get("status")).casefold()
        if status == "completed":
            explicit = {**explicit, "status": "pass"}
        return explicit
    refutations = _as_list(report.get("refutation_results"))
    if refutations:
        return {
            "status": "pass",
            "refutation_count": len(refutations),
        }
    if metadata.get("sensitivity_not_applicable_rationale"):
        return {
            "status": "not_applicable",
            "rationale": metadata.get("sensitivity_not_applicable_rationale"),
        }
    return {}


def _input_diagnostics_from_payloads(
    *,
    report: dict[str, Any],
    evidence: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    metadata = _mapping(report.get("metadata"))
    artifacts = _mapping(evidence.get("artifacts"))
    explicit = _first_mapping(
        report.get("input_diagnostics"),
        result.get("input_diagnostics"),
        artifacts.get("input_diagnostics"),
    )
    diagnostics = dict(explicit)
    sample_size = (
        report.get("sample_size")
        if report.get("sample_size") is not None
        else diagnostics.get("sample_size")
    )
    if sample_size is not None:
        diagnostics["sample_size"] = sample_size
    minimum = (
        metadata.get("min_required_sample_size")
        or metadata.get("minimum_sample_size")
        or artifacts.get("min_required_sample_size")
        or diagnostics.get("min_required_sample_size")
    )
    if minimum is not None:
        diagnostics["min_required_sample_size"] = minimum
    if diagnostics and "status" not in diagnostics:
        diagnostics["status"] = "pass"
    return diagnostics


def _degradation_from_payloads(
    *,
    output: dict[str, Any],
    report: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    explicit = _first_mapping(
        output.get("degradation"),
        output.get("degrade"),
        report.get("degradation"),
        result.get("degradation"),
    )
    if explicit:
        return explicit
    status = _text(report.get("status")).casefold()
    if status and status not in {"success", "pass", "passed", "ok"}:
        return {
            "status": "fail",
            "reason": report.get("status_reason") or status,
        }
    return {}


def _result_summary_from_payloads(report: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    explicit = _mapping(result.get("result_summary") or report.get("result_summary"))
    if explicit:
        return explicit
    summary: dict[str, Any] = {}
    for key in (
        "status",
        "estimand",
        "point_estimate",
        "effect_estimate",
        "standard_error",
        "confidence_interval",
        "confidence_level",
        "p_value",
        "inference_method",
    ):
        if key in report:
            summary[key] = report[key]
    return summary


def _result_refs_from_output(output: dict[str, Any]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for key, value in output.items():
        if key.endswith("_ref"):
            ref = _ref_id(value)
            if ref:
                refs[str(key)] = ref
    return refs


def _selected_method_from_output(
    output: dict[str, Any],
    *,
    foundry_input_refs: dict[str, str],
) -> dict[str, Any]:
    report = _report_payload(output)
    evidence = _evidence_payload(output)
    result = _result_payload(output)
    method_id = _method_id_from_output(
        output,
        report=report,
        evidence=evidence,
        result=result,
    )
    output_input_refs = _normalize_ref_mapping(output.get("input_refs"))
    input_refs = {**foundry_input_refs, **output_input_refs}
    method_family = _infer_method_family(
        method_id,
        report=report,
        evidence=evidence,
        output=output,
    )
    result_refs = _result_refs_from_output(output)
    method_result_refs = {
        key: value
        for key, value in result_refs.items()
        if key.endswith("result_ref") or key.endswith("_result_ref")
    }
    missingness = _missingness_from_payloads(
        report=report,
        evidence=evidence,
        result=result,
    )
    return {
        "method_id": method_id,
        "method_family": method_family,
        "validity_registry": _registry_entry_for_method({"method_family": method_family}),
        "input_refs": input_refs,
        "result_refs": result_refs,
        "method_result_refs": method_result_refs,
        "method_refs": _merge_ref_mappings(
            output.get("method_refs"),
            report.get("method_refs"),
            evidence.get("method_refs"),
            result.get("method_refs"),
        ),
        "objective_tradeoff_refs": _merge_ref_mappings(
            output.get("objective_tradeoff_refs"),
            report.get("objective_tradeoff_refs"),
            evidence.get("objective_tradeoff_refs"),
            result.get("objective_tradeoff_refs"),
        ),
        "uncertainty_refs": _merge_ref_mappings(
            output.get("uncertainty_refs"),
            report.get("uncertainty_refs"),
            evidence.get("uncertainty_refs"),
            result.get("uncertainty_refs"),
        ),
        "assumption_gate_refs": _merge_ref_mappings(
            output.get("assumption_gate_refs"),
            report.get("assumption_gate_refs"),
            evidence.get("assumption_gate_refs"),
            result.get("assumption_gate_refs"),
        ),
        "runtime_assumption_gates": (
            _as_list(output.get("runtime_assumption_gates"))
            or _as_list(report.get("runtime_assumption_gates"))
            or _as_list(evidence.get("runtime_assumption_gates"))
            or _as_list(result.get("runtime_assumption_gates"))
        ),
        "sensitivity_refs": _merge_ref_mappings(
            output.get("sensitivity_refs"),
            report.get("sensitivity_refs"),
            evidence.get("sensitivity_refs"),
            result.get("sensitivity_refs"),
        ),
        "limitation_refs": _merge_ref_mappings(
            output.get("limitation_refs"),
            report.get("limitation_refs"),
            evidence.get("limitation_refs"),
            result.get("limitation_refs"),
        ),
        "simulation_assumption_lineage_refs": _merge_ref_mappings(
            output.get("simulation_assumption_lineage_refs"),
            report.get("simulation_assumption_lineage_refs"),
            evidence.get("simulation_assumption_lineage_refs"),
            result.get("simulation_assumption_lineage_refs"),
            output.get("assumption_lineage_refs"),
            result.get("assumption_lineage_refs"),
        ),
        "distributional_evidence": _first_mapping(
            output.get("distributional_evidence"),
            report.get("distributional_evidence"),
            evidence.get("distributional_evidence"),
            result.get("distributional_evidence"),
        ),
        "implementation_feasibility": _first_mapping(
            output.get("implementation_feasibility"),
            report.get("implementation_feasibility"),
            evidence.get("implementation_feasibility"),
            result.get("implementation_feasibility"),
        ),
        "assumptions": _assumptions_from_payloads(
            report=report,
            evidence=evidence,
            result=result,
        ),
        "identification_requirements": _identification_requirements_from_payloads(
            method_family=method_family,
            output=output,
            report=report,
            evidence=evidence,
            result=result,
        ),
        "uncertainty": _uncertainty_from_payloads(report=report, result=result),
        "missingness": missingness,
        "missingness_handling": _missingness_handling_from_payloads(
            report=report,
            evidence=evidence,
            result=result,
            missingness=missingness,
        ),
        "sensitivity": _sensitivity_from_payloads(
            output=output,
            report=report,
            evidence=evidence,
            result=result,
        ),
        "input_diagnostics": _input_diagnostics_from_payloads(
            report=report,
            evidence=evidence,
            result=result,
        ),
        "degradation": _degradation_from_payloads(
            output=output,
            report=report,
            result=result,
        ),
        "transportability_limits": _transportability_limits_from_payloads(
            method_family=method_family,
            output=output,
            report=report,
            evidence=evidence,
            result=result,
        ),
        "specification_space": _specification_space_from_payloads(
            method_family=method_family,
            output=output,
            report=report,
            evidence=evidence,
            result=result,
        ),
        "validity_surfaces": _validity_surfaces_from_payloads(
            method_family=method_family,
            output=output,
            report=report,
            evidence=evidence,
            result=result,
        ),
        "result_summary": _result_summary_from_payloads(report, result),
    }


def _candidate_method_families(
    *,
    candidate_methods: list[dict[str, Any]],
    selected_methods: list[dict[str, Any]],
    rejected_methods: list[dict[str, Any]],
) -> list[str]:
    families = {
        _method_family(method).casefold()
        for method in [*candidate_methods, *selected_methods, *rejected_methods]
        if isinstance(method, dict) and _method_family(method)
    }
    return sorted(families)


def _rejection_row(
    method: dict[str, Any],
    *,
    reason_code: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "method_id": _method_id(method),
        "method_family": _method_family(method),
        "reason_code": reason_code,
        "reason": reason,
        "result_refs": _result_refs(method),
    }


def _method_matches_expected(method: dict[str, Any], expected: set[str]) -> bool:
    if not expected:
        return True
    return bool(_method_expectations(method).intersection(expected))


def _reconcile_selected_methods(
    selected_methods: list[dict[str, Any]],
    *,
    expected_method_expectations: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for method in selected_methods:
        if (
            _has_serious_method_expectations(expected_method_expectations)
            and _generic_execution_candidate(method)
        ):
            rejected.append(
                _rejection_row(
                    method,
                    reason_code="generic_method_not_admissible",
                    reason=(
                        "Generic Foundry execution is not a named analytical method "
                        "for serious scenario method obligations."
                    ),
                )
            )
            continue
        selected.append(method)
    return selected, rejected


def _select_methods_after_execution(
    candidates: list[dict[str, Any]],
    *,
    expected_method_expectations: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for method in candidates:
        if (
            "causal_effect_estimation" in expected_method_expectations
            and _generic_simulation_candidate(method)
        ):
            rejected.append(
                _rejection_row(
                    method,
                    reason_code="generic_simulation_not_valid_for_expected_method",
                    reason=(
                        "Generic simulation output is not an analytical causal method "
                        "for the expected method family."
                    ),
                )
            )
            continue
        if (
            _has_serious_method_expectations(expected_method_expectations)
            and _generic_execution_candidate(method)
        ):
            rejected.append(
                _rejection_row(
                    method,
                    reason_code="generic_method_not_admissible",
                    reason=(
                        "Generic Foundry execution is not a named analytical method "
                        "for the expected policy method obligations."
                    ),
                )
            )
            continue
        if _method_matches_expected(method, expected_method_expectations):
            selected.append(method)
            continue
        rejected.append(
            _rejection_row(
                method,
                reason_code="method_family_not_expected",
                reason="Executed method family did not match the expected method contract.",
            )
        )
    return selected, rejected


def _selection_issues_from_rejections(
    *,
    selected_methods: list[dict[str, Any]],
    rejected_methods: list[dict[str, Any]],
    expected_method_expectations: set[str],
) -> list[dict[str, Any]]:
    if selected_methods:
        return []
    has_causal_generic_rejection = any(
        _text(method.get("reason_code"))
        == "generic_simulation_not_valid_for_expected_method"
        for method in rejected_methods
    )
    has_generic_method_rejection = any(
        _text(method.get("reason_code"))
        in {"generic_method_execution_not_admissible", "generic_method_not_admissible"}
        for method in rejected_methods
    )
    issues: list[dict[str, Any]] = []
    if (
        "causal_effect_estimation" in expected_method_expectations
        and has_causal_generic_rejection
    ):
        issues.append(
            _issue(
                code="generic_simulation_false_pass",
                method_id="foundry.execute",
                message=(
                    "Generic Foundry simulation reported pass-like output but no executed "
                    "analytical causal method was selected."
                ),
                next_action=(
                    "Reject the generic simulation as causal evidence and rerun with a "
                    "registered causal method that emits identification, transportability, "
                    "falsification, and proof surfaces."
                ),
            )
        )
    if has_generic_method_rejection:
        issues.append(
            _issue(
                code="generic_method_not_admissible",
                method_id="foundry.execute",
                message=(
                    "Generic Foundry execution reported pass-like output but no named "
                    "analytical method satisfied the scenario method obligations."
                ),
                next_action=(
                    "Reject generic execution as policy method authority and rerun with "
                    "a registered analytical method selected from the scenario contract."
                ),
            )
        )
    return issues


def build_foundry_method_report(
    *,
    selected_methods: list[dict[str, Any]],
    candidate_methods: list[dict[str, Any]] | None = None,
    rejected_methods: list[dict[str, Any]] | None = None,
    foundry_input_refs: Mapping[str, Any] | None = None,
    expected_method_expectations: list[str] | None = None,
    method_requirements: list[Mapping[str, Any] | Any] | None = None,
    canary_kind: str = "production",
    spine_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a strict Foundry method-quality report from selected methods."""
    normalized_foundry_input_refs = _normalize_ref_mapping(foundry_input_refs or {})
    normalized_method_requirements = normalize_method_requirements(method_requirements)
    expected = {
        _text(expectation).casefold()
        for expectation in (expected_method_expectations or [])
        if _text(expectation)
    }
    for requirement in normalized_method_requirements:
        expected.update(
            _text(expectation).casefold()
            for expectation in requirement.method_expectations
            if _text(expectation)
        )
    normalized_candidate_methods = list(candidate_methods or selected_methods)
    normalized_rejected_methods = list(rejected_methods or [])
    selected_methods, reconciled_rejections = _reconcile_selected_methods(
        list(selected_methods),
        expected_method_expectations=expected,
    )
    requirement_selection_report: dict[str, Any] | None = None
    if normalized_method_requirements:
        requirement_selection_report = select_method_candidates_for_requirements(
            candidate_methods=selected_methods,
            method_requirements=normalized_method_requirements,
        )
        selected_methods = [
            method
            for method in requirement_selection_report.get("selected_methods", [])
            if isinstance(method, dict)
        ]
        normalized_rejected_methods.extend(
            method
            for method in requirement_selection_report.get("rejected_methods", [])
            if isinstance(method, dict)
        )
    selected_methods = [
        _enrich_method_surfaces(method)
        for method in selected_methods
        if isinstance(method, dict)
    ]
    normalized_rejected_methods = [*normalized_rejected_methods, *reconciled_rejections]
    method_obligations = _build_method_obligations(
        selected_methods=selected_methods,
        expected_method_expectations=expected,
    )
    method_independence = _method_independence_report(selected_methods)
    issues: list[dict[str, Any]] = []
    issues.extend(
        _selection_issues_from_rejections(
            selected_methods=selected_methods,
            rejected_methods=normalized_rejected_methods,
            expected_method_expectations=expected,
        )
    )
    if requirement_selection_report is not None:
        issues.extend(
            issue
            for issue in requirement_selection_report.get("issues", [])
            if isinstance(issue, dict)
        )
    issues.extend(_method_obligation_issues(method_obligations))
    issues.extend(_method_independence_issues(method_independence))
    if not selected_methods:
        issues.append(
            _issue(
                code="no_selected_methods",
                message="Foundry method report has no selected methods.",
                next_action="Record at least one selected Foundry method.",
            )
        )

    for method in selected_methods:
        if not isinstance(method, dict):
            continue
        issues.extend(
            _validate_method(
                method,
                expected_method_expectations=expected,
                foundry_input_refs=normalized_foundry_input_refs,
            )
        )

    status = _status_from_issues(issues)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "capability_reality_status": "implemented",
        "runtime_authority_envelope": _authority_envelope(),
        "canary_kind": canary_kind,
        "foundry_input_refs": normalized_foundry_input_refs,
        "expected_method_expectations": sorted(expected),
        "method_requirements": [
            requirement.model_dump(mode="json")
            for requirement in normalized_method_requirements
        ],
        "method_requirement_statuses": (
            dict(requirement_selection_report.get("method_requirement_statuses") or {})
            if requirement_selection_report is not None
            else {}
        ),
        "candidate_methods": normalized_candidate_methods,
        "candidate_method_families": _candidate_method_families(
            candidate_methods=normalized_candidate_methods,
            selected_methods=selected_methods,
            rejected_methods=normalized_rejected_methods,
        ),
        "method_obligations": method_obligations,
        "method_independence": method_independence,
        "selected_methods": list(selected_methods),
        "rejected_methods": normalized_rejected_methods,
        "issues": issues,
        "blocking_issue_count": sum(1 for issue in issues if issue.get("severity") == "fail"),
        "summary": {
            "candidate_method_count": len(normalized_candidate_methods),
            "selected_method_count": len(selected_methods),
            "rejected_method_count": len(normalized_rejected_methods),
            "method_ids": [
                _method_id(method)
                for method in selected_methods
                if isinstance(method, dict) and _method_id(method)
            ],
            "method_result_refs": [
                {
                    "method_id": _method_id(method),
                    "refs": _result_refs(method),
                }
                for method in selected_methods
                if isinstance(method, dict) and _result_refs(method)
            ],
            "method_output_ref_count": sum(
                len(_method_output_refs(method))
                for method in selected_methods
                if isinstance(method, dict)
            ),
            "assumption_gate_ref_count": sum(
                len(_assumption_gate_refs(method))
                for method in selected_methods
                if isinstance(method, dict)
            ),
            "uncertainty_envelope_ref_count": sum(
                len(_uncertainty_envelope_refs(method))
                for method in selected_methods
                if isinstance(method, dict)
            ),
            "limitation_ref_count": sum(
                len(_limitation_refs(method))
                for method in selected_methods
                if isinstance(method, dict)
            ),
            "effective_independent_method_count": method_independence[
                "effective_independent_method_count"
            ],
            "method_independence_collapse_reasons": method_independence["collapse_reasons"],
            "method_obligation_statuses": {
                str(obligation["expectation"]): str(obligation["status"])
                for obligation in method_obligations
            },
            "method_requirement_statuses": (
                dict(requirement_selection_report.get("method_requirement_statuses") or {})
                if requirement_selection_report is not None
                else {}
            ),
        },
    }
    if spine_context is not None:
        from polisyos.core import contracts as core_contracts

        report.update(
            core_contracts.build_producer_spine_binding_fields(
                component="foundry",
                spine_context=spine_context,
                candidate_refs=[
                    _method_id(method)
                    for method in selected_methods
                    if isinstance(method, dict)
                ],
                blocker_refs=[issue.get("code") for issue in issues],
            )
        )
    return report


def normalize_foundry_method_report(
    report: dict[str, Any],
    *,
    foundry_input_refs: Mapping[str, Any] | None = None,
    expected_method_expectations: list[str] | None = None,
    method_requirements: list[Mapping[str, Any] | Any] | None = None,
    canary_kind: str = "production",
) -> dict[str, Any]:
    """Recompute method-quality status from selected method diagnostics."""
    if not isinstance(report, dict):
        return build_foundry_method_report(
            selected_methods=[],
            foundry_input_refs=foundry_input_refs,
            expected_method_expectations=expected_method_expectations,
            method_requirements=method_requirements,
            canary_kind=canary_kind,
        )
    selected_methods = [
        method for method in report.get("selected_methods", []) if isinstance(method, dict)
    ]
    candidate_methods = [
        method for method in report.get("candidate_methods", []) if isinstance(method, dict)
    ]
    rejected_methods = [
        method for method in report.get("rejected_methods", []) if isinstance(method, dict)
    ]
    expected = expected_method_expectations or report.get("expected_method_expectations") or []
    expected = [_text(value) for value in expected if _text(value)] if isinstance(
        expected,
        list,
    ) else []
    normalized = build_foundry_method_report(
        selected_methods=selected_methods,
        candidate_methods=candidate_methods or None,
        rejected_methods=rejected_methods or None,
        foundry_input_refs=foundry_input_refs or report.get("foundry_input_refs"),
        expected_method_expectations=expected,
        method_requirements=method_requirements or report.get("method_requirements"),
        canary_kind=canary_kind,
    )
    return {**report, **normalized}


def build_foundry_method_report_from_execution_outputs(
    *,
    method_outputs: list[dict[str, Any]],
    foundry_input_refs: Mapping[str, Any] | None = None,
    expected_method_expectations: list[str] | None = None,
    method_requirements: list[Mapping[str, Any] | Any] | None = None,
    canary_kind: str = "production",
) -> dict[str, Any]:
    """Build a method-quality report from executed method outputs and Foundry refs."""
    normalized_foundry_refs = _normalize_ref_mapping(foundry_input_refs or {})
    expected = {
        _text(expectation).casefold()
        for expectation in (expected_method_expectations or [])
        if _text(expectation)
    }
    candidate_methods = [
        _selected_method_from_output(_mapping(output), foundry_input_refs=normalized_foundry_refs)
        for output in method_outputs
        if isinstance(output, Mapping)
    ]
    selected_methods, rejected_methods = _select_methods_after_execution(
        candidate_methods,
        expected_method_expectations=expected,
    )
    return build_foundry_method_report(
        selected_methods=selected_methods,
        candidate_methods=candidate_methods,
        rejected_methods=rejected_methods,
        foundry_input_refs=normalized_foundry_refs,
        expected_method_expectations=expected_method_expectations,
        method_requirements=method_requirements,
        canary_kind=canary_kind,
    )


def _state_foundry_input_refs(state: object) -> dict[str, str]:
    inputs = _state_section(state, "inputs")
    params = _state_section(state, "params")
    auto_refs = _mapping(params.get("auto_data_source_refs"))
    refs: dict[str, str] = {}
    for key in _FOUNDRY_INPUT_REF_KEYS:
        ref = _ref_id(inputs.get(key)) or _ref_id(auto_refs.get(key)) or _ref_id(params.get(key))
        if ref:
            refs[key] = ref
    return refs


def _state_expected_method_expectations(state: object) -> list[str]:
    params = _state_section(state, "params")
    expected = params.get("expected_method_expectations")
    if isinstance(expected, list):
        return [_text(item) for item in expected if _text(item)]
    scenario_contract = _mapping(params.get("golden_scenario_contract"))
    evidence_contract = _mapping(scenario_contract.get("expected_evidence_contract"))
    method_expectations = evidence_contract.get("foundry_method_expectations")
    if isinstance(method_expectations, list):
        return [_text(item) for item in method_expectations if _text(item)]
    return []


def _artifact_payload_from_sections(
    *,
    store: object,
    artifacts: dict[str, Any],
    reports: dict[str, Any],
    params: dict[str, Any],
    key: str,
) -> tuple[str | None, dict[str, Any]]:
    ref_value = artifacts.get(key) or reports.get(key) or params.get(key)
    ref = _ref_id(ref_value)
    return ref, _load_json_artifact(store, ref_value) or {}


def _method_outputs_from_state(store: object, state: object) -> list[dict[str, Any]]:
    artifacts = _state_section(state, "artifacts_index")
    reports = _state_section(state, "reports_index")
    params = _state_section(state, "params")
    outputs: list[dict[str, Any]] = []

    causal_result_ref, causal_result = _artifact_payload_from_sections(
        store=store,
        artifacts=artifacts,
        reports=reports,
        params=params,
        key="causal_method_result_ref",
    )
    causal_evidence_ref, causal_evidence = _artifact_payload_from_sections(
        store=store,
        artifacts=artifacts,
        reports=reports,
        params=params,
        key="causal_method_evidence_ref",
    )
    causal_report_ref, causal_report = _artifact_payload_from_sections(
        store=store,
        artifacts=artifacts,
        reports=reports,
        params=params,
        key="causal_report_ref",
    )
    sensitivity_ref, sensitivity_result = _artifact_payload_from_sections(
        store=store,
        artifacts=artifacts,
        reports=reports,
        params=params,
        key="sensitivity_result_ref",
    )
    if any((causal_result_ref, causal_evidence_ref, causal_report_ref, causal_result)):
        outputs.append(
            {
                "method_result_ref": causal_result_ref,
                "method_evidence_ref": causal_evidence_ref,
                "causal_report_ref": causal_report_ref,
                "sensitivity_result_ref": sensitivity_ref,
                "method_result": causal_result,
                "method_evidence": causal_evidence,
                "causal_report": causal_report,
                "sensitivity_result": sensitivity_result,
                "method_fqn": params.get("causal_method_fqn"),
            }
        )

    query_result_ref, query_result = _artifact_payload_from_sections(
        store=store,
        artifacts=artifacts,
        reports=reports,
        params=params,
        key="causal_query_method_result_ref",
    )
    query_evidence_ref, query_evidence = _artifact_payload_from_sections(
        store=store,
        artifacts=artifacts,
        reports=reports,
        params=params,
        key="causal_query_method_evidence_ref",
    )
    query_report_ref, query_report = _artifact_payload_from_sections(
        store=store,
        artifacts=artifacts,
        reports=reports,
        params=params,
        key="causal_query_result_ref",
    )
    if any((query_result_ref, query_evidence_ref, query_report_ref, query_result)):
        outputs.append(
            {
                "method_result_ref": query_result_ref,
                "method_evidence_ref": query_evidence_ref,
                "causal_report_ref": query_report_ref,
                "method_result": query_result,
                "method_evidence": query_evidence,
                "causal_report": query_report,
            }
        )

    simulation_ref, simulation_result = _artifact_payload_from_sections(
        store=store,
        artifacts=artifacts,
        reports=reports,
        params=params,
        key="simulation_result_ref",
    )
    if not outputs and (simulation_ref or simulation_result):
        outputs.append(
            {
                "simulation_result_ref": simulation_ref,
                "method_id": "foundry.execute",
                "method_family": "simulation",
                "method_result": simulation_result,
            }
        )

    if not outputs:
        raw_outputs = params.get("foundry_method_outputs")
        if isinstance(raw_outputs, list):
            outputs.extend(_mapping(item) for item in raw_outputs if isinstance(item, Mapping))

    return outputs


def build_foundry_method_report_from_state(
    store: object,
    state: object,
    *,
    expected_method_expectations: list[str] | None = None,
    canary_kind: str = "production",
) -> dict[str, Any]:
    """Build a method-quality report from a final Scientist state."""
    expected = expected_method_expectations
    if expected is None:
        expected = _state_expected_method_expectations(state)
    return build_foundry_method_report_from_execution_outputs(
        method_outputs=_method_outputs_from_state(store, state),
        foundry_input_refs=_state_foundry_input_refs(state),
        expected_method_expectations=expected,
        canary_kind=canary_kind,
    )


def expected_method_expectations_from_state(state: object) -> list[str]:
    """Return the scenario or caller-declared Foundry method expectations for a state."""
    return _state_expected_method_expectations(state)


def build_foundry_method_obligation_report_from_state(
    store: object,
    state: object,
    *,
    expected_method_expectations: list[str] | None = None,
    canary_kind: str = "production",
) -> dict[str, Any]:
    """Build a pre-execution report that records unmet method obligations."""
    expected = expected_method_expectations
    if expected is None:
        expected = _state_expected_method_expectations(state)
    report = build_foundry_method_report(
        selected_methods=[],
        candidate_methods=[],
        rejected_methods=[],
        foundry_input_refs=_state_foundry_input_refs(state),
        expected_method_expectations=expected,
        canary_kind=canary_kind,
    )
    report["report_phase"] = "method_obligation_preflight"
    report["method_obligation_request"] = {
        "requested_before_claims": True,
        "expected_method_expectations": list(report["expected_method_expectations"]),
    }
    return report


def _lineage_input_ref(role: str, artifact_id: str) -> InputRef | None:
    try:
        return InputRef(artifact_id=artifact_id, role=role)
    except (TypeError, ValueError):
        return None


def _method_report_lineage_inputs(report: dict[str, Any]) -> list[InputRef]:
    inputs: list[InputRef] = []
    seen: set[tuple[str, str]] = set()

    def _append(role: str, artifact_id: object) -> None:
        ref = _ref_id(artifact_id)
        if not ref or (role, ref) in seen:
            return
        input_ref = _lineage_input_ref(role, ref)
        if input_ref is None:
            return
        seen.add((role, ref))
        inputs.append(input_ref)

    for role, artifact_id in _normalize_ref_mapping(report.get("foundry_input_refs")).items():
        _append(role, artifact_id)
    for index, method in enumerate(report.get("selected_methods") or []):
        if not isinstance(method, Mapping):
            continue
        result_refs = _normalize_ref_mapping(method.get("result_refs"))
        for role, artifact_id in result_refs.items():
            _append(f"method_{index}:{role}", artifact_id)
    return inputs


def _authority_envelope() -> dict[str, tuple[str, ...] | str]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "authoritative_for": (
            "method_validity",
            "selected_method_refs",
            "rejected_method_refs",
            "runtime_assumption_gates",
            "method_output_refs",
            "uncertainty_envelope_refs",
            "method_limitations",
        ),
        "may_not_use_for": (
            "legal_authority",
            "source_family_satisfaction",
            "academic_support_strength",
            "participation_representativeness",
            "claim_support_without_claim_registry_bridge",
            "closeout_pass",
        ),
    }


def persist_foundry_method_report(store: object, report: dict[str, Any]) -> ArtifactRef:
    """Persist a Foundry method-quality report as a CAS artifact."""
    return store.put_json(
        _jsonable(report),
        ArtifactWriteOptions(
            kind=REPORT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.MethodQualityReport", version="1.0"),
            inputs=_method_report_lineage_inputs(report),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def persist_foundry_method_report_for_state(
    store: object,
    state: object,
    *,
    expected_method_expectations: list[str] | None = None,
    canary_kind: str = "production",
) -> tuple[ArtifactRef, dict[str, Any]]:
    """Build and persist the method-quality report for a final Scientist state."""
    report = build_foundry_method_report_from_state(
        store,
        state,
        expected_method_expectations=expected_method_expectations,
        canary_kind=canary_kind,
    )
    return persist_foundry_method_report(store, report), report


def persist_foundry_method_obligation_report_for_state(
    store: object,
    state: object,
    *,
    expected_method_expectations: list[str] | None = None,
    canary_kind: str = "production",
) -> tuple[ArtifactRef, dict[str, Any]]:
    """Persist a pre-execution method-obligation report for serious policy workflows."""
    report = build_foundry_method_obligation_report_from_state(
        store,
        state,
        expected_method_expectations=expected_method_expectations,
        canary_kind=canary_kind,
    )
    return persist_foundry_method_report(store, report), report


__all__ = [
    "OBLIGATION_REPORT_REF_KEY",
    "REPORT_KIND",
    "REPORT_REF_KEY",
    "SCHEMA_VERSION",
    "build_foundry_method_obligation_report_from_state",
    "build_foundry_method_report",
    "build_foundry_method_report_from_execution_outputs",
    "build_foundry_method_report_from_state",
    "expected_method_expectations_from_state",
    "normalize_foundry_method_report",
    "persist_foundry_method_obligation_report_for_state",
    "persist_foundry_method_report",
    "persist_foundry_method_report_for_state",
]
