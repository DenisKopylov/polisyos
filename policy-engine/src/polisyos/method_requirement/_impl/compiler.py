"""Compiler for claim-bound method validity requirements."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.ir.observation import IdentificationMode, identification_mode_origin_for_rule

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
        source_facet_contexts = _source_facet_contexts(claim)
        explicit_mode_facets = _explicit_identification_mode_facets(
            claim,
            source_facet_contexts,
        )
        explicit_modes = {row["identification_mode"] for row in explicit_mode_facets}
        if len(explicit_modes) > 1:
            raise ValueError("method_requirement_explicit_identification_modes_conflict")
        identification_class = _identification_class(
            claim,
            method_needs,
            tokens,
            explicit_modes,
        )
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
        method_expectations = _dedupe(
            [
                *method_expectations,
                *(row["identification_mode"] for row in explicit_mode_facets),
            ]
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
                "source_facet_contexts": source_facet_contexts,
                "explicit_identification_mode_facets": explicit_mode_facets,
                "identification_mode_limitations": _identification_mode_limitations(
                    source_facet_contexts
                ),
                "identification_class_semantics": (
                    "required_method_capability_not_identification_evidence"
                ),
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


def _explicit_identification_mode_facets(
    claim: Mapping[str, Any],
    source_facet_contexts: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Read and validate mode bindings carried by linked claim preconditions."""

    output: list[dict[str, str]] = []
    seen: dict[str, str] = {}
    contexts_by_ref = {
        _text(context.get("facet_ref")): context
        for context in source_facet_contexts
        if _text(context.get("facet_ref"))
    }
    for precondition in _precondition_rows(claim):
        metadata = precondition.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        facets = metadata.get("explicit_identification_mode_facets", [])
        if not isinstance(facets, list):
            raise ValueError("method_requirement_identification_mode_binding_invalid")
        for facet in facets:
            if not isinstance(facet, Mapping):
                raise ValueError("method_requirement_identification_mode_binding_invalid")
            facet_ref = _required_text(facet.get("facet_ref"), field_name="facet_ref")
            try:
                mode = IdentificationMode(
                    _required_text(
                        facet.get("identification_mode"),
                        field_name="identification_mode",
                    )
                )
            except ValueError as exc:
                raise ValueError("method_requirement_identification_mode_unknown") from exc
            precondition_facet_refs = _string_list(precondition.get("facet_refs"))
            if precondition_facet_refs and facet_ref not in precondition_facet_refs:
                raise ValueError("method_requirement_identification_mode_binding_unlinked")
            context = contexts_by_ref.get(facet_ref)
            origin, rule_ref, source_class = _mode_binding_context(facet, context)
            if context is not None:
                context_value = _text(context.get("value"))
                if context_value and context_value != mode.value:
                    raise ValueError("method_requirement_identification_mode_binding_mismatch")
            if source_class in {"llm_candidate", "llm_critic", "llm_drafter"}:
                raise ValueError("method_requirement_identification_mode_binding_not_deterministic")
            if origin in {"default_point", "inferred_sequential", "not_established"}:
                raise ValueError("method_requirement_identification_mode_binding_not_explicit")
            if origin not in {"explicit_policy_spec", "declared_constraint"}:
                raise ValueError("method_requirement_identification_mode_origin_invalid")
            if origin == "explicit_policy_spec" and not rule_ref:
                raise ValueError("method_requirement_identification_mode_origin_unbound")
            if origin == "declared_constraint" and rule_ref:
                raise ValueError("method_requirement_identification_mode_origin_mismatch")
            prior_mode = seen.get(facet_ref)
            if prior_mode is not None and prior_mode != mode.value:
                raise ValueError("method_requirement_identification_mode_binding_conflict")
            if prior_mode is None:
                row = {
                    "facet_ref": facet_ref,
                    "identification_mode": mode.value,
                    "identification_mode_origin": origin,
                    "source_class": source_class,
                }
                if rule_ref:
                    row["derivation_rule_ref"] = rule_ref
                output.append(row)
                seen[facet_ref] = mode.value

    # The source context is the bound producer record; the precondition metadata is
    # a projection. Reconstruct strict bindings from the source context so deleting
    # only that projection cannot silently weaken a declared PolicySpec constraint.
    precondition_facet_refs = {
        facet_ref
        for precondition in _precondition_rows(claim)
        for facet_ref in _string_list(precondition.get("facet_refs"))
    }
    output_by_ref = {row["facet_ref"]: row for row in output}
    for context in source_facet_contexts:
        if _text(context.get("facet_type")) != "method_need":
            continue
        facet_ref = _required_text(context.get("facet_ref"), field_name="facet_ref")
        origin, rule_ref, source_class = _mode_binding_context({}, context)
        if source_class in {"llm_candidate", "llm_critic", "llm_drafter"}:
            if facet_ref in output_by_ref:
                raise ValueError("method_requirement_identification_mode_binding_not_deterministic")
            continue
        if origin in {"default_point", "inferred_sequential", "not_established"}:
            if facet_ref in output_by_ref:
                raise ValueError("method_requirement_identification_mode_binding_not_explicit")
            continue
        if origin not in {"explicit_policy_spec", "declared_constraint"}:
            continue
        if facet_ref not in precondition_facet_refs:
            raise ValueError("method_requirement_identification_mode_binding_unlinked")
        try:
            mode = IdentificationMode(
                _required_text(context.get("value"), field_name="identification_mode")
            )
        except ValueError as exc:
            raise ValueError("method_requirement_identification_mode_unknown") from exc
        prior = output_by_ref.get(facet_ref)
        if prior is not None:
            if prior["identification_mode"] != mode.value:
                raise ValueError("method_requirement_identification_mode_binding_mismatch")
            continue
        row = {
            "facet_ref": facet_ref,
            "identification_mode": mode.value,
            "identification_mode_origin": origin,
            "source_class": source_class,
        }
        if rule_ref:
            row["derivation_rule_ref"] = rule_ref
        output.append(row)
        output_by_ref[facet_ref] = row
        seen[facet_ref] = mode.value
    return output


def _mode_binding_context(
    binding: Mapping[str, Any],
    context: Mapping[str, Any] | None,
) -> tuple[str, str, str]:
    """Resolve mode origin from the linked typed context and reconcile its binding."""

    context_metadata: Mapping[str, Any] = {}
    source_class = _text(binding.get("source_class"))
    if context is not None:
        context_metadata_value = context.get("metadata")
        if not isinstance(context_metadata_value, Mapping):
            raise ValueError("method_requirement_source_facet_context_invalid")
        context_metadata = context_metadata_value
        context_source_class = _text(context.get("source_class"))
        if context_source_class:
            if source_class and source_class != context_source_class:
                raise ValueError("method_requirement_identification_mode_source_mismatch")
            source_class = context_source_class

    binding_rule_ref = _text(binding.get("derivation_rule_ref"))
    context_rule_ref = _text(context_metadata.get("derivation_rule_ref"))
    if binding_rule_ref and context_rule_ref and binding_rule_ref != context_rule_ref:
        raise ValueError("method_requirement_identification_mode_rule_mismatch")
    rule_ref = context_rule_ref or binding_rule_ref
    binding_origin = _text(binding.get("identification_mode_origin"))
    context_origin = _text(context_metadata.get("identification_mode_origin"))
    if binding_origin and context_origin and binding_origin != context_origin:
        raise ValueError("method_requirement_identification_mode_origin_mismatch")
    supplied_origin = context_origin or binding_origin

    grammar_marked = any(
        key in context_metadata
        for key in (
            "case_id",
            "intent_id",
            "source_intent_sha256",
            "source_intervention_sha256",
            "grammar_case_schema_version",
        )
    )
    if rule_ref:
        origin = identification_mode_origin_for_rule(rule_ref)
    elif grammar_marked or source_class in {"llm_candidate", "llm_critic", "llm_drafter"}:
        origin = "not_established"
    else:
        # Historical direct typed precondition fixtures have no grammar provenance.
        # Their mode is a caller constraint, not identification evidence.
        origin = "declared_constraint"
    mode_value = _text(context.get("value")) if context is not None else ""
    mode_value = mode_value or _text(binding.get("identification_mode"))
    if origin == "default_point" and mode_value != IdentificationMode.POINT_IDENTIFIED.value:
        raise ValueError("method_requirement_identification_mode_origin_value_mismatch")
    if origin == "inferred_sequential" and mode_value != IdentificationMode.SEQUENTIAL.value:
        raise ValueError("method_requirement_identification_mode_origin_value_mismatch")
    if supplied_origin and supplied_origin != origin:
        raise ValueError("method_requirement_identification_mode_origin_mismatch")
    return origin, rule_ref, source_class


def _source_facet_contexts(claim: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Preserve claim-linked facet provenance for method consumers and audit surfaces."""

    claim_metadata = claim.get("metadata")
    if not isinstance(claim_metadata, Mapping):
        return []
    rows = claim_metadata.get("source_facet_contexts", [])
    if not isinstance(rows, list):
        raise ValueError("method_requirement_source_facet_context_invalid")
    claim_facet_refs = set(_string_list(claim.get("facet_refs")))
    output: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("method_requirement_source_facet_context_invalid")
        facet_ref = _required_text(row.get("facet_ref"), field_name="facet_ref")
        if facet_ref not in claim_facet_refs:
            raise ValueError("method_requirement_source_facet_context_unlinked")
        copied = dict(row)
        if _text(copied.get("facet_type")) == "method_need":
            metadata = copied.get("metadata")
            if not isinstance(metadata, Mapping):
                raise ValueError("method_requirement_source_facet_context_invalid")
            copied_metadata = dict(metadata)
            origin, _, _ = _mode_binding_context({}, copied)
            supplied_origin = _text(copied_metadata.get("identification_mode_origin"))
            if supplied_origin and supplied_origin != origin:
                raise ValueError("method_requirement_identification_mode_origin_mismatch")
            copied_metadata["identification_mode_origin"] = origin
            copied["metadata"] = copied_metadata
        output.append(copied)
    return output


def _identification_mode_limitations(
    source_facet_contexts: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Keep unknown grammar mode provenance visible without turning it into a mode gate."""

    limitations: list[dict[str, str]] = []
    for context in source_facet_contexts:
        if _text(context.get("facet_type")) != "method_need":
            continue
        origin, rule_ref, _ = _mode_binding_context({}, context)
        if origin != "not_established":
            continue
        limitation = {
            "code": "identification_mode_origin_not_established",
            "facet_ref": _text(context.get("facet_ref")),
            "identification_mode": _text(context.get("value")),
            "origin": origin,
        }
        if rule_ref:
            limitation["derivation_rule_ref"] = rule_ref
        limitations.append(limitation)
    return limitations


def _claim_tokens(claim: Mapping[str, Any], method_needs: Sequence[str]) -> set[str]:
    """Derive method semantics from typed claim inputs, text, and closed metadata fields."""

    values: list[object] = [
        claim.get("claim_type"),
        claim.get("claim_family"),
        claim.get("claim_use"),
        claim.get("text"),
        *method_needs,
    ]
    metadata = claim.get("metadata")
    if isinstance(metadata, Mapping):
        # This is the only legacy free-form metadata field with an established
        # semantic consumer. Audit, source, and future metadata remain provenance.
        strategic_response = metadata.get("strategic_response")
        if strategic_response is not None:
            values.extend(("strategic_response", strategic_response))
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
    explicit_modes: set[str],
) -> MethodIdentificationClass:
    support_status = _text(claim.get("support_status")).casefold()
    if "negative_certificate" in method_needs or support_status == "refuted":
        return MethodIdentificationClass.NEGATIVE_CERTIFICATE
    if IdentificationMode.BOUNDS_ONLY.value in explicit_modes:
        return MethodIdentificationClass.BOUNDS
    if IdentificationMode.PARTIALLY_IDENTIFIED.value in explicit_modes:
        return MethodIdentificationClass.PARTIAL
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
        rationale=("Claim requires simulation DGP lineage and calibration." if required else ""),
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
