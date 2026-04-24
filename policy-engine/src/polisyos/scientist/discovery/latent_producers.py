"""Automatic Stage 9.1/9.2 latent producer paths for discovery hypotheses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.ir.analytics.causal_discovery import (
    LATENT_CARDINALITY_EVIDENCE_KEY,
    LATENT_CARDINALITY_FAILURE_REASONS_KEY,
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    LatentAssumptionCard,
    LatentBlockProposal,
    LatentBlockStatus,
    LatentCardinalityEvidencePayload,
    LatentCardinalityIdentificationSpec,
    LatentCausalRole,
    LatentDiscoveryBundle,
    LatentGraphStatus,
    LatentIdentifiabilityStatus,
    LatentTrustLevel,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.scientist.latent_separation import (
    SEPARATION_DIAGNOSTIC_INPUTS_KEY,
    LatentSeparationDiagnosticInputs,
    LatentSeparationEnvironmentInput,
    LatentSeparationMeasurementInput,
    LatentSeparationProxyInput,
    certify_latent_separation_trust,
    latent_separation_assumption_surfaces,
    latent_separation_falsification_surfaces,
    metadata_with_computed_latent_separation,
    separation_diagnostics_payload,
)


def produce_latent_discovery_bundle(
    report: CausalDiscoveryReport,
    *,
    graph: CausalGraphModel | None = None,
) -> LatentDiscoveryBundle | None:
    """Produce or enrich a research-only latent bundle from discovery report evidence."""

    working_graph = graph or report.resolved_graph or report.graph
    bundle = report.latent_discovery
    report_metadata = dict(report.metadata)

    cardinality_payload = _resolve_cardinality_payload(report_metadata, bundle)
    if cardinality_payload is not None:
        bundle = _apply_cardinality_payload(bundle, cardinality_payload, graph=working_graph)

    separation_inputs = _resolve_separation_inputs(
        report_metadata,
        report.algebraic_constraints,
        bundle=bundle,
    )
    if separation_inputs is not None:
        bundle = _apply_separation_inputs(bundle, separation_inputs)

    return bundle


def _resolve_cardinality_payload(
    report_metadata: Mapping[str, Any],
    bundle: LatentDiscoveryBundle | None,
) -> LatentCardinalityEvidencePayload | None:
    payload = LatentCardinalityEvidencePayload.from_metadata(report_metadata)
    if payload is not None:
        return payload
    if bundle is None:
        return None
    payload = LatentCardinalityEvidencePayload.from_metadata(bundle.metadata)
    if payload is not None:
        return payload
    spec = bundle.latent_cardinality_spec()
    if spec is None:
        return None
    return LatentCardinalityEvidencePayload(
        model_class=spec.model_class,
        inducing_environments=list(bundle.inducing_environments),
        falsification_tests=list(bundle.falsification_tests),
        assumption_cards=list(bundle.assumption_cards),
        latent_blocks=list(spec.latent_blocks),
        latent_candidates=list(spec.latent_candidates),
        ambiguity_notes=list(spec.ambiguity_notes),
        metadata=dict(spec.metadata),
    )


def _apply_cardinality_payload(
    bundle: LatentDiscoveryBundle | None,
    payload: LatentCardinalityEvidencePayload,
    *,
    graph: CausalGraphModel,
) -> LatentDiscoveryBundle:
    treated_blocks: list[LatentBlockProposal] = []
    failure_reasons: list[str] = list(payload.prerequisites_missing)
    for block in payload.latent_blocks:
        normalized_block, block_failures = _normalize_cardinality_block(
            block,
            graph=graph,
            treatment_variable=payload.treatment_variable,
            outcome_variable=payload.outcome_variable,
            model_class=payload.model_class,
        )
        treated_blocks.append(normalized_block)
        failure_reasons.extend(block_failures)

    spec = LatentCardinalityIdentificationSpec(
        model_class=payload.model_class,
        identifiability_status=_latent_identifiability_status(treated_blocks),
        latent_blocks=treated_blocks,
        latent_candidates=list(payload.latent_candidates),
        ambiguity_notes=list(payload.ambiguity_notes),
        metadata=dict(payload.metadata),
    )
    generated = spec.to_bundle(
        inducing_environments=_cardinality_environments(payload, treated_blocks),
        falsification_tests=_cardinality_falsification_tests(payload, treated_blocks),
        assumption_cards=_cardinality_assumption_cards(payload, treated_blocks),
        trust_level=bundle.trust_level if bundle is not None else LatentTrustLevel.RESEARCH,
        no_promotion_reasons=_dedupe_strings(
            [
                *(list(bundle.no_promotion_reasons) if bundle is not None else []),
                "latent_discovery_proof_only",
                *failure_reasons,
            ]
        ),
        metadata={
            **spec.bundle_metadata(),
            LATENT_CARDINALITY_EVIDENCE_KEY: payload.model_dump(mode="json"),
            LATENT_CARDINALITY_FAILURE_REASONS_KEY: _dedupe_strings(failure_reasons),
        },
        treatment_variable=payload.treatment_variable,
        outcome_variable=payload.outcome_variable,
    )
    return _merge_latent_bundles(bundle, generated)


def _normalize_cardinality_block(
    block: LatentBlockProposal,
    *,
    graph: CausalGraphModel,
    treatment_variable: str,
    outcome_variable: str,
    model_class: str,
) -> tuple[LatentBlockProposal, list[str]]:
    evidence = block.evidence
    role = block.role
    candidate_role = block.candidate_role
    requested_role = role if role is not LatentCausalRole.UNKNOWN else candidate_role
    role_supported = _role_supported_by_graph(
        graph,
        anchor_variables=block.anchor_variables,
        treatment_variable=treatment_variable,
        outcome_variable=outcome_variable,
        role=requested_role,
    )
    evidence_updates: dict[str, Any] = {}
    if requested_role in {LatentCausalRole.CONFOUNDER, LatentCausalRole.MEDIATOR}:
        evidence_updates["role_rule_supported"] = role_supported
    evidence = evidence.model_copy(update=evidence_updates) if evidence_updates else evidence

    missing: list[str] = []
    if not evidence.gin_supported:
        missing.append("gin_supported")
    if not evidence.atomic_structure_supported:
        missing.append("atomic_structure_supported")
    if not evidence.shift_localized:
        missing.append("shift_localized")
    if not evidence.minimal_decomposition_supported:
        missing.append("minimal_decomposition_supported")
    if evidence.pure_child_count is None or evidence.pure_child_count < (2 * block.block_size):
        missing.append("pure_children")
    if evidence.neighbor_count is None or evidence.neighbor_count < (2 * block.block_size + 1):
        missing.append("neighbors")
    if evidence.rank is None or evidence.rank < block.block_size:
        missing.append("rank")
    if (
        requested_role in {LatentCausalRole.CONFOUNDER, LatentCausalRole.MEDIATOR}
        and not role_supported
    ):
        missing.append("role_rule_supported")
    if requested_role is LatentCausalRole.MODERATOR:
        if model_class != "ME-LiNGLaH-S-Int":
            missing.append("moderator_model_class")
        if not evidence.interaction_signature_supported:
            missing.append("interaction_signature_supported")

    normalized_role = role
    normalized_candidate_role = candidate_role
    if requested_role is LatentCausalRole.MODERATOR and missing:
        normalized_role = LatentCausalRole.UNKNOWN
        normalized_candidate_role = LatentCausalRole.MODERATOR
    graph_status = (
        LatentGraphStatus.IDENTIFIED
        if role_supported
        and requested_role in {LatentCausalRole.CONFOUNDER, LatentCausalRole.MEDIATOR}
        else block.graph_status
    )
    if graph_status is LatentGraphStatus.UNKNOWN and block.anchor_variables:
        graph_status = LatentGraphStatus.PARTIAL
    status = (
        LatentBlockStatus.IDENTIFIED
        if not missing and requested_role is not None
        else LatentBlockStatus.PARTIAL
    )
    if requested_role is None:
        status = LatentBlockStatus.PARTIAL
    reason = None
    if missing:
        reason = "prerequisites_missing:" + ",".join(sorted(set(missing)))

    normalized_block = block.model_copy(
        update={
            "role": normalized_role,
            "candidate_role": normalized_candidate_role,
            "status": status,
            "graph_status": graph_status,
            "evidence": evidence,
            "reason_not_identified": reason,
        }
    )
    return normalized_block, [f"{block.latent_id}:{value}" for value in sorted(set(missing))]


def _latent_identifiability_status(
    blocks: list[LatentBlockProposal],
) -> LatentIdentifiabilityStatus:
    if not blocks:
        return LatentIdentifiabilityStatus.SUSPECTED_ONLY
    if all(block.status is LatentBlockStatus.IDENTIFIED for block in blocks):
        return LatentIdentifiabilityStatus.FULL
    if any(block.status is LatentBlockStatus.IDENTIFIED for block in blocks):
        return LatentIdentifiabilityStatus.PARTIAL_OR_FULL
    if any(block.status is LatentBlockStatus.PARTIAL for block in blocks):
        return LatentIdentifiabilityStatus.PARTIAL
    return LatentIdentifiabilityStatus.SUSPECTED_ONLY


def _cardinality_environments(
    payload: LatentCardinalityEvidencePayload,
    blocks: list[LatentBlockProposal],
) -> list[str]:
    environments = list(payload.inducing_environments)
    if environments:
        return _dedupe_strings(environments)
    for block in blocks:
        for contrast in block.informative_environment_contrasts:
            environments.extend(_environments_from_contrast(contrast))
    return _dedupe_strings(environments)


def _cardinality_falsification_tests(
    payload: LatentCardinalityEvidencePayload,
    blocks: list[LatentBlockProposal],
) -> list[str]:
    if payload.falsification_tests:
        return _dedupe_strings(payload.falsification_tests)
    tests = ["latent_cardinality:environment_holdout"]
    for block in blocks:
        tests.extend(
            [
                f"latent_cardinality:gin_support:{block.latent_id}",
                f"latent_cardinality:rank_separation:{block.latent_id}",
                f"latent_cardinality:graph_placement:{block.latent_id}",
            ]
        )
    return _dedupe_strings(tests)


def _cardinality_assumption_cards(
    payload: LatentCardinalityEvidencePayload,
    blocks: list[LatentBlockProposal],
) -> list[LatentAssumptionCard]:
    if payload.assumption_cards:
        return list(payload.assumption_cards)
    cards = [
        LatentAssumptionCard(
            assumption_id="latent_cardinality_model_class",
            title=f"{payload.model_class} theorem envelope",
            description=(
                "Latent cardinality claims stay in the narrow multi-environment "
                "linear non-Gaussian class with localized shifts and pure children."
            ),
            falsification_hook="latent_cardinality:environment_holdout",
        )
    ]
    for block in blocks:
        cards.append(
            LatentAssumptionCard(
                assumption_id=f"latent_cardinality_{block.latent_id}",
                title=f"Latent block {block.latent_id}",
                description=(
                    f"Block {block.latent_id} requires pure children, rank separation, "
                    "and graph-placement support inside the declared theorem class."
                ),
                falsification_hook=f"latent_cardinality:graph_placement:{block.latent_id}",
            )
        )
    return cards


def _resolve_separation_inputs(
    report_metadata: Mapping[str, Any],
    algebraic_constraints: AlgebraicConstraintReport | None,
    *,
    bundle: LatentDiscoveryBundle | None,
) -> LatentSeparationDiagnosticInputs | None:
    existing_inputs = LatentSeparationDiagnosticInputs.from_mapping(
        _latent_mapping_value(
            report_metadata,
            SEPARATION_DIAGNOSTIC_INPUTS_KEY,
            "separation_diagnostics_inputs",
            "latent_separation_inputs",
        )
    )
    if existing_inputs is None and bundle is not None:
        existing_inputs = LatentSeparationDiagnosticInputs.from_mapping(
            _latent_mapping_value(
                bundle.metadata,
                SEPARATION_DIAGNOSTIC_INPUTS_KEY,
                "separation_diagnostics_inputs",
                "latent_separation_inputs",
            )
        )

    measurement = _measurement_input_from_report(report_metadata, algebraic_constraints)
    proxy = _proxy_input_from_report(report_metadata)
    environment = _environment_input_from_report(report_metadata)
    design = dict(existing_inputs.design if existing_inputs is not None else {})
    design.update(
        dict(
            _latent_mapping_value(
                report_metadata,
                "latent_separation_design",
                "separation_design",
            )
            or {}
        )
    )
    candidate_latent_nodes = list(
        existing_inputs.candidate_latent_nodes if existing_inputs is not None else []
    )
    if bundle is not None and bundle.proposed_latent_nodes:
        candidate_latent_nodes = list(bundle.proposed_latent_nodes)
    if not candidate_latent_nodes:
        nodes = report_metadata.get("latent_candidate_nodes")
        if isinstance(nodes, list):
            candidate_latent_nodes = [str(value) for value in nodes if str(value).strip()]

    if measurement is None and proxy is None and environment is None and existing_inputs is None:
        return None

    prerequisites_missing: list[str] = list(
        existing_inputs.prerequisites_missing if existing_inputs is not None else []
    )
    if not candidate_latent_nodes:
        prerequisites_missing.append("candidate_latent_nodes_missing")
    design_preview = dict(design)
    if measurement is not None and measurement.repeated_indicator_blocks:
        design_preview.setdefault(
            "repeated_indicator_blocks",
            list(measurement.repeated_indicator_blocks),
        )
    if proxy is not None and proxy.proxy_blocks:
        design_preview.setdefault("proxy_blocks", list(proxy.proxy_blocks))
    if environment is not None:
        if environment.environments:
            design_preview.setdefault("environments", list(environment.environments))
        if environment.n_env is not None:
            design_preview["n_env"] = int(environment.n_env)
    if _count_design_blocks(design_preview.get("proxy_blocks")) < 2:
        prerequisites_missing.append("two_proxy_blocks_required")
    if _count_design_blocks(design_preview.get("repeated_indicator_blocks")) < 1:
        prerequisites_missing.append("repeated_indicator_block_required")
    if _environment_count_from_design(design_preview) < 2:
        prerequisites_missing.append("multi_environment_required")

    return LatentSeparationDiagnosticInputs(
        candidate_latent_nodes=_dedupe_strings(candidate_latent_nodes),
        data=dict(existing_inputs.data if existing_inputs is not None else {}),
        design=design,
        measurement_block=measurement
        or (existing_inputs.measurement_block if existing_inputs is not None else None),
        proxy_block=proxy or (existing_inputs.proxy_block if existing_inputs is not None else None),
        environment_block=environment
        or (existing_inputs.environment_block if existing_inputs is not None else None),
        replication=(
            dict(existing_inputs.replication)
            if existing_inputs is not None and existing_inputs.replication is not None
            else None
        ),
        prerequisites_missing=_dedupe_strings(prerequisites_missing),
        metadata=dict(existing_inputs.metadata if existing_inputs is not None else {}),
    )


def _apply_separation_inputs(
    bundle: LatentDiscoveryBundle | None,
    inputs: LatentSeparationDiagnosticInputs,
) -> LatentDiscoveryBundle | None:
    if bundle is None and (
        not inputs.candidate_latent_nodes or not _separation_environments(inputs)
    ):
        return None

    metadata = dict(bundle.metadata if bundle is not None else {})
    metadata[SEPARATION_DIAGNOSTIC_INPUTS_KEY] = inputs.model_dump(mode="json")
    metadata = metadata_with_computed_latent_separation(metadata)
    diagnostics = separation_diagnostics_payload(metadata)
    certified_trust = certify_latent_separation_trust(
        metadata,
        fallback=bundle.trust_level if bundle is not None else LatentTrustLevel.RESEARCH,
    )
    trust_level = _max_trust_level(
        bundle.trust_level if bundle is not None else LatentTrustLevel.RESEARCH,
        certified_trust,
    )
    generated = LatentDiscoveryBundle(
        proposed_latent_nodes=(
            list(bundle.proposed_latent_nodes)
            if bundle is not None
            else list(inputs.candidate_latent_nodes)
        ),
        inducing_environments=(
            list(bundle.inducing_environments)
            if bundle is not None and bundle.inducing_environments
            else _separation_environments(inputs)
        ),
        identification_conditions=(
            list(bundle.identification_conditions)
            if bundle is not None and bundle.identification_conditions
            else _separation_identification_conditions(diagnostics)
        ),
        falsification_tests=_dedupe_strings(
            [
                *(list(bundle.falsification_tests) if bundle is not None else []),
                *latent_separation_falsification_surfaces(diagnostics),
            ]
        ),
        trust_level=trust_level,
        assumption_cards=_merge_assumption_cards(
            list(bundle.assumption_cards) if bundle is not None else [],
            _separation_assumption_cards(diagnostics),
        ),
        readiness_cap=bundle.readiness_cap if bundle is not None else "proof_only",
        human_gate_required=True if bundle is None else bool(bundle.human_gate_required),
        promotion_allowed=False if bundle is None else bool(bundle.promotion_allowed),
        no_promotion_reasons=_dedupe_strings(
            [
                *(list(bundle.no_promotion_reasons) if bundle is not None else []),
                "latent_discovery_proof_only",
                *[
                    f"latent_separation_prerequisite_missing:{value}"
                    for value in inputs.prerequisites_missing
                ],
            ]
        ),
        not_for_decision_support=True if bundle is None else bool(bundle.not_for_decision_support),
        promotion_evidence=bundle.promotion_evidence if bundle is not None else None,
        metadata=metadata,
    )
    return generated


def _measurement_input_from_report(
    report_metadata: Mapping[str, Any],
    algebraic_constraints: AlgebraicConstraintReport | None,
) -> LatentSeparationMeasurementInput | None:
    raw = _latent_mapping_value(
        report_metadata,
        "latent_separation_measurement",
        "measurement_block",
    )
    if isinstance(raw, Mapping):
        return LatentSeparationMeasurementInput.model_validate(raw)
    if algebraic_constraints is None:
        return None
    tested = int(
        algebraic_constraints.tested_by_family.get(AlgebraicConstraintFamily.TETRAD.value, 0)
    )
    violated = int(
        algebraic_constraints.violated_by_family.get(AlgebraicConstraintFamily.TETRAD.value, 0)
    )
    if tested <= 0 and AlgebraicConstraintFamily.TETRAD not in algebraic_constraints.families_run:
        return None
    repeated_blocks = _repeated_indicator_blocks_from_constraints(algebraic_constraints)
    invariance_test = report_metadata.get("measurement_invariance_test")
    return LatentSeparationMeasurementInput(
        status="passed" if violated == 0 and invariance_test else None,
        tetrad_test="single_signal_tetrad_passed"
        if violated == 0
        else "single_signal_tetrad_failed",
        invariance_test=(
            str(invariance_test)
            if str(invariance_test or "").strip()
            else "measurement_invariance_unresolved"
        ),
        repeated_indicator_blocks=repeated_blocks,
        metadata={"source": "algebraic_constraints"},
    )


def _proxy_input_from_report(
    report_metadata: Mapping[str, Any],
) -> LatentSeparationProxyInput | None:
    raw = _latent_mapping_value(
        report_metadata,
        "latent_separation_proxy",
        "proxy_block",
    )
    if isinstance(raw, Mapping):
        return LatentSeparationProxyInput.model_validate(raw)

    bridge_report = report_metadata.get("bridge_plausibility_report")
    proxy_boundary = report_metadata.get("proxy_boundary")
    fidelity_payload = report_metadata.get("embedding_fidelity_certificate")
    if (
        not isinstance(bridge_report, Mapping)
        and not isinstance(proxy_boundary, Mapping)
        and not isinstance(fidelity_payload, Mapping)
    ):
        return None

    flagged_proxies: list[str] = []
    if isinstance(proxy_boundary, Mapping):
        for value in list(proxy_boundary.get("flagged_proxies", []) or []):
            text = str(value).strip()
            if text:
                flagged_proxies.append(text)

    severity = None
    fallback = None
    if isinstance(bridge_report, Mapping):
        severity = bridge_report.get("severity") or bridge_report.get(
            "bridge_plausibility_severity"
        )
        fallback = bridge_report.get("fallback_disposition") or bridge_report.get(
            "bridge_fallback_disposition"
        )
    bridge_test = _bridge_test_from_report_metadata(severity=severity, fallback=fallback)
    if bridge_test is None and flagged_proxies:
        bridge_test = "proximal_bridge_failed"
    if bridge_test is None and not isinstance(fidelity_payload, Mapping):
        return None

    return LatentSeparationProxyInput(
        bridge_test=bridge_test or "proximal_bridge_unresolved",
        bridge_stability=str(
            report_metadata.get("bridge_stability")
            or ("cross_environment_unstable" if flagged_proxies else "cross_environment_unresolved")
        ),
        flagged_proxies=_dedupe_strings(flagged_proxies),
        bridge_plausibility_severity=str(severity) if severity is not None else None,
        bridge_fallback_disposition=str(fallback) if fallback is not None else None,
        embedding_family=(
            str(fidelity_payload.get("family"))
            if isinstance(fidelity_payload, Mapping) and fidelity_payload.get("family") is not None
            else None
        ),
        embedding_dim=(
            int(fidelity_payload.get("metadata", {}).get("embedding_dim"))
            if isinstance(fidelity_payload, Mapping)
            and isinstance(fidelity_payload.get("metadata"), Mapping)
            and fidelity_payload.get("metadata", {}).get("embedding_dim") is not None
            else None
        ),
        representation_faithfulness_status=(
            str(fidelity_payload.get("status"))
            if isinstance(fidelity_payload, Mapping) and fidelity_payload.get("status") is not None
            else None
        ),
        separator_recoverability=(
            {
                str(key): float(value)
                for key, value in fidelity_payload.get("recoverability_scores", {}).items()
            }
            if isinstance(fidelity_payload, Mapping)
            and isinstance(fidelity_payload.get("recoverability_scores"), Mapping)
            else {}
        ),
        residual_dependence_scores=(
            {
                str(key): float(value)
                for key, value in fidelity_payload.get("residual_dependence_scores", {}).items()
            }
            if isinstance(fidelity_payload, Mapping)
            and isinstance(fidelity_payload.get("residual_dependence_scores"), Mapping)
            else {}
        ),
        collision_rate=(
            float(fidelity_payload.get("collision_rate"))
            if isinstance(fidelity_payload, Mapping)
            and fidelity_payload.get("collision_rate") is not None
            else None
        ),
        effect_drift_z=(
            float(fidelity_payload.get("effect_drift_z"))
            if isinstance(fidelity_payload, Mapping)
            and fidelity_payload.get("effect_drift_z") is not None
            else None
        ),
        effective_sample_size=(
            float(fidelity_payload.get("effective_sample_size"))
            if isinstance(fidelity_payload, Mapping)
            and fidelity_payload.get("effective_sample_size") is not None
            else None
        ),
        representation_recommended_action=(
            str(fidelity_payload.get("recommended_action"))
            if isinstance(fidelity_payload, Mapping)
            and fidelity_payload.get("recommended_action") is not None
            else None
        ),
        representation_failure_modes=(
            [
                str(value)
                for value in list(fidelity_payload.get("failure_modes", []) or [])
                if str(value).strip()
            ]
            if isinstance(fidelity_payload, Mapping)
            else []
        ),
        proxy_blocks=_proxy_blocks_from_report_metadata(report_metadata, proxy_boundary),
        metadata={
            "source": (
                "bridge_plausibility+embedding_fidelity"
                if isinstance(fidelity_payload, Mapping)
                else "bridge_plausibility"
            )
        },
    )


def _environment_input_from_report(
    report_metadata: Mapping[str, Any],
) -> LatentSeparationEnvironmentInput | None:
    raw = _latent_mapping_value(
        report_metadata,
        "latent_separation_environment",
        "environment_block",
    )
    if isinstance(raw, Mapping):
        return LatentSeparationEnvironmentInput.model_validate(raw)

    regime = report_metadata.get("regime_shift_discovery")
    if not isinstance(regime, Mapping):
        return None

    residual_invariance = report_metadata.get("residual_invariance")
    post_calibration_shift = report_metadata.get("post_calibration_shift")
    route_to_latent_aware = regime.get("route_to_latent_aware_discovery")
    if residual_invariance is None and bool(route_to_latent_aware):
        residual_invariance = "post_calibration_residual_invariance_failed"
    if post_calibration_shift is None and bool(route_to_latent_aware):
        post_calibration_shift = "not_restored"

    return LatentSeparationEnvironmentInput(
        residual_invariance=(
            str(residual_invariance)
            if str(residual_invariance or "").strip()
            else "post_calibration_residual_invariance_unresolved"
        ),
        post_calibration_shift=(
            str(post_calibration_shift)
            if str(post_calibration_shift or "").strip()
            else "unresolved"
        ),
        environments=[
            str(value) for value in list(regime.get("environments", []) or []) if str(value).strip()
        ],
        n_env=int(regime.get("n_environments", 0) or 0) or None,
        shift_type_label=str(regime.get("shift_type_label") or "") or None,
        certification_level=str(regime.get("shift_certification_level") or "") or None,
        route_to_latent_aware_discovery=(
            bool(route_to_latent_aware) if route_to_latent_aware is not None else None
        ),
        metadata={"source": "regime_shift_discovery"},
    )


def _repeated_indicator_blocks_from_constraints(
    algebraic_constraints: AlgebraicConstraintReport,
) -> list[str]:
    blocks: list[str] = []
    for preview in list(algebraic_constraints.implied_constraints_preview) + list(
        algebraic_constraints.violated_constraints_preview
    ):
        metadata = getattr(preview, "metadata", {}) or {}
        block_id = str(metadata.get("block_id") or metadata.get("source_block_id") or "").strip()
        if block_id and block_id not in blocks:
            blocks.append(block_id)
    if blocks:
        return blocks
    if algebraic_constraints.tested_by_family.get(AlgebraicConstraintFamily.TETRAD.value, 0):
        return ["tetrad_block_0"]
    return []


def _bridge_test_from_report_metadata(
    *,
    severity: object,
    fallback: object,
) -> str | None:
    severity_token = _normalize_token(severity)
    fallback_token = _normalize_token(fallback)
    if not severity_token and not fallback_token:
        return None
    if severity_token in {"green", "yellow"} and fallback_token not in {
        "require_bounds",
        "block_point_estimate",
    }:
        return "proximal_bridge_solved"
    if severity_token in {"red", "critical"}:
        return "proximal_bridge_failed"
    if fallback_token in {"require_bounds", "block_point_estimate", "import_failed"}:
        return "proximal_bridge_failed"
    return None


def _proxy_blocks_from_report_metadata(
    report_metadata: Mapping[str, Any],
    proxy_boundary: Mapping[str, Any] | None,
) -> list[str]:
    values = report_metadata.get("proxy_blocks")
    if isinstance(values, list):
        output = [str(value) for value in values if str(value).strip()]
        if output:
            return output
    if isinstance(proxy_boundary, Mapping):
        observed = proxy_boundary.get("observed_proxies")
        if isinstance(observed, list):
            return [str(value) for value in observed if str(value).strip()]
    return []


def _apply_graph_role_rules(
    graph: CausalGraphModel,
    *,
    anchor_variables: list[str],
    treatment_variable: str,
    outcome_variable: str,
) -> tuple[bool, bool]:
    if not anchor_variables:
        return False, False
    confounder = any(
        _is_ancestor(graph, anchor, treatment_variable)
        and _is_ancestor(graph, anchor, outcome_variable)
        for anchor in anchor_variables
    )
    mediator = any(
        _is_ancestor(graph, treatment_variable, anchor)
        and _is_ancestor(graph, anchor, outcome_variable)
        for anchor in anchor_variables
    )
    return confounder, mediator


def _role_supported_by_graph(
    graph: CausalGraphModel,
    *,
    anchor_variables: list[str],
    treatment_variable: str,
    outcome_variable: str,
    role: LatentCausalRole | None,
) -> bool:
    confounder, mediator = _apply_graph_role_rules(
        graph,
        anchor_variables=anchor_variables,
        treatment_variable=treatment_variable,
        outcome_variable=outcome_variable,
    )
    if role is LatentCausalRole.CONFOUNDER:
        return confounder
    if role is LatentCausalRole.MEDIATOR:
        return mediator
    return False


def _is_ancestor(graph: CausalGraphModel, start: str, target: str) -> bool:
    if start == target or start not in set(graph.nodes) or target not in set(graph.nodes):
        return False
    adjacency: dict[str, set[str]] = {node: set() for node in graph.nodes}
    for edge in graph.edges:
        adjacency.setdefault(edge.src, set()).add(edge.dst)
    frontier = [start]
    seen: set[str] = set()
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        for child in adjacency.get(current, ()):
            if child == target:
                return True
            frontier.append(child)
    return False


def _merge_latent_bundles(
    existing: LatentDiscoveryBundle | None,
    generated: LatentDiscoveryBundle,
) -> LatentDiscoveryBundle:
    if existing is None:
        return generated
    metadata = dict(existing.metadata)
    metadata.update(generated.metadata)
    return existing.model_copy(
        update={
            "proposed_latent_nodes": _dedupe_strings(
                [*existing.proposed_latent_nodes, *generated.proposed_latent_nodes]
            ),
            "inducing_environments": _dedupe_strings(
                [*existing.inducing_environments, *generated.inducing_environments]
            ),
            "identification_conditions": _dedupe_strings(
                [*existing.identification_conditions, *generated.identification_conditions]
            ),
            "falsification_tests": _dedupe_strings(
                [*existing.falsification_tests, *generated.falsification_tests]
            ),
            "trust_level": _max_trust_level(existing.trust_level, generated.trust_level),
            "assumption_cards": _merge_assumption_cards(
                list(existing.assumption_cards),
                list(generated.assumption_cards),
            ),
            "human_gate_required": bool(
                existing.human_gate_required or generated.human_gate_required
            ),
            "promotion_allowed": bool(existing.promotion_allowed),
            "no_promotion_reasons": _dedupe_strings(
                [*existing.no_promotion_reasons, *generated.no_promotion_reasons]
            ),
            "not_for_decision_support": bool(existing.not_for_decision_support),
            "metadata": metadata,
        }
    )


def _merge_assumption_cards(
    left: list[LatentAssumptionCard],
    right: list[LatentAssumptionCard],
) -> list[LatentAssumptionCard]:
    output: list[LatentAssumptionCard] = []
    seen: set[str] = set()
    for card in [*left, *right]:
        key = card.assumption_id or card.title
        if key in seen:
            continue
        seen.add(key)
        output.append(card)
    return output


def _separation_environments(inputs: LatentSeparationDiagnosticInputs) -> list[str]:
    environments = list(inputs.design.get("environments", []) or [])
    if environments:
        return _dedupe_strings(str(value) for value in environments)
    if inputs.environment_block is not None and inputs.environment_block.environments:
        return _dedupe_strings(inputs.environment_block.environments)
    return []


def _separation_identification_conditions(
    diagnostics: Mapping[str, Any] | None,
) -> list[str]:
    payload = separation_diagnostics_payload(diagnostics)
    if payload is None:
        return ["latent_separation:unsupported"]
    conditions = [
        f"latent_separation_resolution:{payload.get('resolution_label', 'unresolved')}",
        *latent_separation_assumption_surfaces(payload),
    ]
    return _dedupe_strings(conditions)


def _separation_assumption_cards(
    diagnostics: Mapping[str, Any] | None,
) -> list[LatentAssumptionCard]:
    payload = separation_diagnostics_payload(diagnostics)
    description = (
        "Latent separation uses repeated indicators, proxy evidence, and "
        "cross-environment diagnostics under a research-only gate."
        if payload is not None
        else "Latent separation prerequisites are incomplete, so the claim remains research-only."
    )
    return [
        LatentAssumptionCard(
            assumption_id="latent_separation_scope",
            title="Stage 9.2 separation scope",
            description=description,
            falsification_hook="latent_separation:single_signal_tetrad",
        )
    ]


def _max_trust_level(left: LatentTrustLevel, right: LatentTrustLevel) -> LatentTrustLevel:
    rank = {
        LatentTrustLevel.RESEARCH: 0,
        LatentTrustLevel.CONDITIONAL: 1,
        LatentTrustLevel.VALIDATED: 2,
    }
    return right if rank[right] > rank[left] else left


def _latent_mapping_value(metadata: Mapping[str, Any], *keys: str) -> Mapping[str, Any] | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _count_design_blocks(value: object) -> int:
    if isinstance(value, Mapping):
        return len(value)
    if isinstance(value, list | tuple | set):
        return len(value)
    return 0


def _environment_count_from_design(design: Mapping[str, Any]) -> int:
    raw = design.get("n_env")
    try:
        if raw is not None:
            return int(raw)
    except (TypeError, ValueError):
        pass
    environments = design.get("environments")
    if isinstance(environments, list | tuple | set):
        return len(environments)
    return 0


def _environments_from_contrast(value: str) -> list[str]:
    text = str(value).strip()
    if not text:
        return []
    if "_vs_" in text:
        return [part for part in text.split("_vs_") if part]
    if " vs " in text:
        return [part.strip() for part in text.split(" vs ") if part.strip()]
    return [text]


def _normalize_token(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _dedupe_strings(values: list[str] | Any) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


__all__ = ["produce_latent_discovery_bundle"]
