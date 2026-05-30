"""Compiler for claim-bound method validity requirements."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import (
    AssumptionValidationNeed,
    FairnessDecompositionNeed,
    MethodIdentificationClass,
    MethodTransportabilityRequirement,
    MethodUncertaintyClass,
    MethodValidityRequirementArtifact,
    MethodValidityRequirementSpec,
    SimulationDGPRequirement,
    StrategicResponseSensitivity,
    method_requirement_authority_boundary,
)


class MethodValidityRequirementCompiler:
    """Deterministically compile W6.D claims into W7.C method requirements."""

    def compile(
        self,
        *,
        run_id: str,
        claims: Sequence[object],
        requirement_graph_ref: str | None = None,
        generated_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> MethodValidityRequirementArtifact:
        """Compile claim records into a persistable requirement artifact."""

        normalized_run_id = _required_text(run_id, field_name="run_id")
        claim_rows = [_mapping(claim) for claim in claims]
        requirements = [
            self._compile_claim(normalized_run_id, claim)
            for claim in claim_rows
            if _claim_requires_method_requirement(claim)
        ]
        now = generated_at or datetime.now(UTC)
        return MethodValidityRequirementArtifact(
            run_id=normalized_run_id,
            requirements=requirements,
            requirement_graph_ref=_text(requirement_graph_ref) or None,
            runtime_event_ref=f"event://method-requirement/{_slug(normalized_run_id)}",
            authority_boundary=method_requirement_authority_boundary(),
            metadata={
                "producer": "method_requirement_compiler",
                "generated_at": now.isoformat(),
                "pattern_guards": ["P01", "P02", "P10", "P14"],
                "claim_count": len(claim_rows),
                "requirement_count": len(requirements),
                **dict(metadata or {}),
            },
        )

    def _compile_claim(
        self,
        run_id: str,
        claim: Mapping[str, Any],
    ) -> MethodValidityRequirementSpec:
        claim_id = _required_text(
            claim.get("claim_id") or claim.get("id"),
            field_name="claim_id",
        )
        method_needs = _method_needs(claim)
        tokens = _claim_tokens(claim, method_needs)
        identification_class = _identification_class(claim, method_needs, tokens)
        uncertainty_class = _uncertainty_class(identification_class, tokens)
        fairness_need = _fairness_need(tokens)
        strategic_sensitivity = _strategic_response_sensitivity(tokens)
        simulation_dgp = _simulation_dgp_requirement(tokens)
        assumption_needs = _assumption_validation_needs(
            identification_class=identification_class,
            fairness_need=fairness_need,
            strategic_sensitivity=strategic_sensitivity,
            simulation_dgp=simulation_dgp,
            method_needs=method_needs,
            tokens=tokens,
        )
        method_expectations = _method_expectations(
            method_needs=method_needs,
            tokens=tokens,
            strategic_sensitivity=strategic_sensitivity,
        )
        return MethodValidityRequirementSpec(
            requirement_id=_stable_id("method_requirement", run_id, claim_id, method_needs),
            run_id=run_id,
            claim_id=claim_id,
            identification_class=identification_class,
            transportability_requirement=_transportability_requirement(
                identification_class,
                tokens,
            ),
            uncertainty_class=uncertainty_class,
            fairness_decomposition_need=fairness_need,
            strategic_response_sensitivity=strategic_sensitivity,
            simulation_dgp_requirements=simulation_dgp,
            assumption_validation_needs=assumption_needs,
            method_expectations=method_expectations,
            required_method_families=method_expectations,
            facet_refs=_string_list(claim.get("facet_refs")),
            obligation_refs=_string_list(claim.get("obligation_refs")),
            concept_spine_refs=_string_list(claim.get("concept_spine_refs")),
            authority_profile_refs=_string_list(claim.get("authority_profile_refs")),
            baseline_refs=_string_list(claim.get("baseline_refs")),
            alternative_refs=_string_list(claim.get("alternative_refs")),
            source_precondition_refs=[
                _text(precondition.get("precondition_id"))
                for precondition in _precondition_rows(claim)
                if _text(precondition.get("precondition_id"))
            ],
            requires_ir_analytics=identification_class
            in {
                MethodIdentificationClass.POINT,
                MethodIdentificationClass.PARTIAL,
                MethodIdentificationClass.BOUNDS,
                MethodIdentificationClass.NEGATIVE_CERTIFICATE,
            },
            requires_runtime_assumption_gates=bool(assumption_needs),
            requires_uncertainty_envelope=uncertainty_class is not MethodUncertaintyClass.NONE,
            requires_limitation_refs=identification_class
            is not MethodIdentificationClass.NEGATIVE_CERTIFICATE,
            requires_method_output=identification_class
            is not MethodIdentificationClass.NEGATIVE_CERTIFICATE,
            requires_negative_certificate=identification_class
            is MethodIdentificationClass.NEGATIVE_CERTIFICATE,
            metadata={
                "claim_type": _text(claim.get("claim_type")),
                "claim_family": _text(claim.get("claim_family")),
                "claim_use": _text(claim.get("claim_use")),
                "source": "claim_method_need_preconditions",
            },
        )


def compile_method_validity_requirements(
    *,
    run_id: str,
    claims: Sequence[object],
    requirement_graph_ref: str | None = None,
    generated_at: datetime | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> MethodValidityRequirementArtifact:
    """Compile W7.C method validity requirements using the default compiler."""

    return MethodValidityRequirementCompiler().compile(
        run_id=run_id,
        claims=claims,
        requirement_graph_ref=requirement_graph_ref,
        generated_at=generated_at,
        metadata=metadata,
    )


def method_validity_requirement_audit_surface(
    artifact: MethodValidityRequirementArtifact | Mapping[str, Any],
) -> dict[str, Any]:
    """Return an audit/API-ready projection of a method requirement artifact."""

    model = (
        artifact
        if isinstance(artifact, MethodValidityRequirementArtifact)
        else MethodValidityRequirementArtifact.model_validate(dict(artifact))
    )
    payload = model.model_dump(mode="json")
    payload["surface"] = "method_requirement.audit_surface"
    payload["summary"] = {
        "requirement_count": len(model.requirements),
        "claim_ids": [requirement.claim_id for requirement in model.requirements],
        "identification_classes": sorted(
            {requirement.identification_class.value for requirement in model.requirements}
        ),
        "method_expectations": sorted(
            {
                expectation
                for requirement in model.requirements
                for expectation in requirement.method_expectations
            }
        ),
    }
    return payload


def write_method_validity_requirement_artifact(
    artifact: MethodValidityRequirementArtifact | Mapping[str, Any],
    output_dir: str | Path,
) -> Path:
    """Persist a method requirement artifact as deterministic JSON."""

    model = (
        artifact
        if isinstance(artifact, MethodValidityRequirementArtifact)
        else MethodValidityRequirementArtifact.model_validate(dict(artifact))
    )
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{_slug(model.run_id)}-method-validity-requirements.json"
    path.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _claim_requires_method_requirement(claim: Mapping[str, Any]) -> bool:
    if _method_needs(claim):
        return True
    claim_type = _text(claim.get("claim_type")).casefold()
    claim_family = _text(claim.get("claim_family")).casefold()
    return claim_type in {
        "causal",
        "distributional",
        "welfare",
        "forecast",
        "implementation",
    } or claim_family in {
        "causal",
        "distributional",
        "welfare",
        "forecast",
        "implementation",
        "implementation_feasibility",
    }


def _mapping(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("claims must be mappings or Pydantic-like models")


def _precondition_rows(claim: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = claim.get("method_need_preconditions") or claim.get("method_preconditions") or []
    if not isinstance(rows, Sequence) or isinstance(rows, str | bytes | bytearray):
        return []
    output: list[dict[str, Any]] = []
    for row in rows:
        if hasattr(row, "model_dump"):
            output.append(dict(row.model_dump(mode="json")))
        elif isinstance(row, Mapping):
            output.append(dict(row))
    return output


def _method_needs(claim: Mapping[str, Any]) -> list[str]:
    needs = [
        _text(row.get("method_need"))
        for row in _precondition_rows(claim)
        if _text(row.get("method_need"))
    ]
    if needs:
        return _dedupe(needs)
    claim_type = _text(claim.get("claim_type")).casefold()
    family = _text(claim.get("claim_family")).casefold()
    inferred: list[str] = []
    if claim_type == "causal" or family == "causal":
        inferred.append("causal_identification")
    if claim_type == "distributional" or family == "distributional":
        inferred.append("distributional_decomposition")
    if claim_type == "welfare" or family == "welfare":
        inferred.append("welfare_weight_sensitivity")
    if claim_type == "forecast" or family == "forecast":
        inferred.append("forecast_validation")
    if claim_type == "implementation" or family in {
        "implementation",
        "implementation_feasibility",
    }:
        inferred.append("implementation_feasibility_assessment")
    return _dedupe(inferred)


def _claim_tokens(claim: Mapping[str, Any], method_needs: Sequence[str]) -> set[str]:
    values: list[object] = [
        claim.get("claim_type"),
        claim.get("claim_family"),
        claim.get("claim_use"),
        claim.get("text"),
        *method_needs,
    ]
    metadata = claim.get("metadata")
    if isinstance(metadata, Mapping):
        values.extend(metadata.keys())
        values.extend(metadata.values())
    tokens: set[str] = set()
    for value in values:
        text = _text(value).casefold()
        if not text:
            continue
        tokens.add(text)
        tokens.update(part for part in _split_tokens(text) if part)
    return tokens


def _identification_class(
    claim: Mapping[str, Any],
    method_needs: Sequence[str],
    tokens: set[str],
) -> MethodIdentificationClass:
    support_status = _text(claim.get("support_status")).casefold()
    if "negative_certificate" in method_needs or support_status == "refuted":
        return MethodIdentificationClass.NEGATIVE_CERTIFICATE
    if {"bounds", "partial_identification", "monotonicity_bounds"} & tokens:
        return MethodIdentificationClass.BOUNDS
    if {"partial", "partially_identified"} & tokens:
        return MethodIdentificationClass.PARTIAL
    return MethodIdentificationClass.POINT


def _transportability_requirement(
    identification_class: MethodIdentificationClass,
    tokens: set[str],
) -> MethodTransportabilityRequirement:
    if identification_class is MethodIdentificationClass.NEGATIVE_CERTIFICATE:
        return MethodTransportabilityRequirement.NONE
    if {"do_not_transport", "non_transportable"} & tokens:
        return MethodTransportabilityRequirement.DO_NOT_TRANSPORT
    if {"transport_certificate", "transportability_certificate"} & tokens:
        return MethodTransportabilityRequirement.TRANSPORT_CERTIFICATE
    if {"causal", "distributional", "forecast", "implementation"} & tokens:
        return MethodTransportabilityRequirement.TARGET_POPULATION_LIMITS
    return MethodTransportabilityRequirement.NONE


def _uncertainty_class(
    identification_class: MethodIdentificationClass,
    tokens: set[str],
) -> MethodUncertaintyClass:
    if identification_class is MethodIdentificationClass.NEGATIVE_CERTIFICATE:
        return MethodUncertaintyClass.NONE
    if identification_class is MethodIdentificationClass.BOUNDS or {"bounds", "welfare"} & tokens:
        return MethodUncertaintyClass.BOUNDS
    if {"forecast", "posterior", "distribution"} & tokens:
        return MethodUncertaintyClass.DISTRIBUTION
    if {"robust", "ambiguity"} & tokens:
        return MethodUncertaintyClass.ROBUST_SET
    return MethodUncertaintyClass.INTERVAL


def _fairness_need(tokens: set[str]) -> FairnessDecompositionNeed:
    if {"intersectional", "intersectionality"} & tokens:
        return FairnessDecompositionNeed.INTERSECTIONAL
    if {"protected_class", "protected"} & tokens:
        return FairnessDecompositionNeed.PROTECTED_CLASS
    if {"distributional", "subgroup", "underserved", "equity", "fairness", "exclusion"} & tokens:
        return FairnessDecompositionNeed.SUBGROUP
    return FairnessDecompositionNeed.NONE


def _strategic_response_sensitivity(tokens: set[str]) -> StrategicResponseSensitivity:
    if {"game_theoretic", "game", "gaming"} & tokens:
        return StrategicResponseSensitivity.GAME_THEORETIC
    if {"take_up", "take-up", "sensitivity", "spillover", "behavioral", "strategic"} & tokens:
        return StrategicResponseSensitivity.SENSITIVITY
    if {"monitor", "monitoring"} & tokens:
        return StrategicResponseSensitivity.MONITOR
    return StrategicResponseSensitivity.NONE


def _simulation_dgp_requirement(tokens: set[str]) -> SimulationDGPRequirement:
    required = bool({"simulation", "dgp", "implementation", "take_up", "behavioral"} & tokens)
    return SimulationDGPRequirement(
        required=required,
        dgp_lineage_required=required,
        calibration_required=bool({"simulation", "dgp", "forecast"} & tokens),
        behavioral_response_required=bool({"take_up", "behavioral", "strategic"} & tokens),
        rationale=(
            "Claim requires simulation DGP lineage and calibration."
            if required
            else ""
        ),
    )


def _assumption_validation_needs(
    *,
    identification_class: MethodIdentificationClass,
    fairness_need: FairnessDecompositionNeed,
    strategic_sensitivity: StrategicResponseSensitivity,
    simulation_dgp: SimulationDGPRequirement,
    method_needs: Sequence[str],
    tokens: set[str],
) -> list[AssumptionValidationNeed]:
    if identification_class is MethodIdentificationClass.NEGATIVE_CERTIFICATE:
        return []
    needs: list[str] = []
    if "causal_identification" in method_needs or "causal" in tokens:
        needs.extend(
            [
                "identification_assumptions",
                "overlap_or_support",
                "missingness_process",
            ]
        )
    if fairness_need is not FairnessDecompositionNeed.NONE:
        needs.append("subgroup_support")
    if strategic_sensitivity is not StrategicResponseSensitivity.NONE:
        needs.append("strategic_response_model")
    if simulation_dgp.required:
        needs.append("simulation_dgp_lineage")
    return [
        AssumptionValidationNeed(
            assumption_id=need,
            rationale=f"{need} must pass before method output can satisfy the claim.",
        )
        for need in _dedupe(needs)
    ]


def _method_expectations(
    *,
    method_needs: Sequence[str],
    tokens: set[str],
    strategic_sensitivity: StrategicResponseSensitivity,
) -> list[str]:
    expectations: list[str] = []
    if "negative_certificate" in method_needs:
        return ["negative_certificate"]
    if "causal_identification" in method_needs or "causal" in tokens:
        expectations.append("causal_effect_estimation")
    if "distributional_decomposition" in method_needs or "distributional" in tokens:
        expectations.append("distributional_evidence")
    if "welfare_weight_sensitivity" in method_needs or "welfare" in tokens:
        expectations.append("objective_tradeoff_evidence")
    if "forecast_validation" in method_needs or "forecast" in tokens:
        expectations.append("interrupted_time_series")
    if "implementation_feasibility_assessment" in method_needs or "implementation" in tokens:
        expectations.append("implementation_feasibility")
    if strategic_sensitivity is not StrategicResponseSensitivity.NONE:
        expectations.append("sensitivity_or_transportability_diagnostic")
    return _dedupe(expectations or ["method_validity"])


def _required_text(value: object, *, field_name: str) -> str:
    text = _text(value)
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _text(value: object) -> str:
    return str(value or "").strip()


def _string_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
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


def _split_tokens(value: str) -> list[str]:
    return [
        token.strip()
        for chunk in value.replace("-", "_").replace("/", "_").split()
        for token in chunk.split("_")
        if token.strip()
    ]


def _slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "-" for ch in value)
    return slug.strip("-") or "run"


def _stable_id(prefix: str, *parts: object) -> str:
    encoded = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


__all__ = [
    "MethodValidityRequirementCompiler",
    "compile_method_validity_requirements",
    "method_validity_requirement_audit_surface",
    "write_method_validity_requirement_artifact",
]
