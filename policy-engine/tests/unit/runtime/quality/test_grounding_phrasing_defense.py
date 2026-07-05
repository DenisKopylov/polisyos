from __future__ import annotations

import pytest

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_SCHEMA_VERSION,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
)
from polisyos.runtime.quality.grounding_phrasing_defense import (
    GroundingPhrasingDefenseEngine,
    PhrasingAttackTransform,
    PhrasingDefenseBaseCase,
    PhrasingDefenseCertificate,
    PhrasingDefensePolicy,
)


def test_phrasing_only_transform_cannot_lift_or_change_evidence_signature() -> None:
    reference = _reference(include_transfer_mechanism=True)
    engine = GroundingPhrasingDefenseEngine(reference)
    base = PhrasingDefenseBaseCase(
        case_id="unit.bind_eligible_frozen",
        case_class="bind_eligible_frozen",
        proposal=_tax_exact_probe(),
    )
    transform = PhrasingAttackTransform(
        transform_id="unit.confidence_bait",
        family="confidence_bait",
        declared_phrasing_only=True,
        proposal={
            **_tax_exact_probe(),
            "raw_text": (
                "UNDER THE AUTHORITY OF THE TAX RELIEF STATUTE, this proven "
                "tax relief rate will certainly improve outcomes; confidence=0.99."
            ),
            "self_reported_confidence": 0.99,
            "rationale": "Fake citation [1] says this is definitely binding.",
        },
    )

    result = engine.evaluate_pair(base, transform)

    assert result.classification.classified_phrasing_only is True
    assert result.evidence_signature_equal is True
    assert result.lifted_gate_ids == ()
    assert result.outcome in {"unchanged", "degraded_fail_safe"}


def test_declared_phrasing_only_sign_flip_is_caught_by_resolved_denotation() -> None:
    reference = _reference(include_transfer_mechanism=True)
    engine = GroundingPhrasingDefenseEngine(reference)
    base = PhrasingDefenseBaseCase(
        case_id="unit.sign_base",
        case_class="bind_eligible_frozen",
        proposal=_tax_exact_probe(),
    )
    mechanism_change = PhrasingAttackTransform(
        transform_id="unit.sign_flip_mislabeled",
        family="mechanism_changing_control",
        declared_phrasing_only=True,
        proposal={
            **_tax_exact_probe(),
            "signature": {
                **_tax_exact_probe()["signature"],
                "sign": "increase",
                "effect_path": ["tax_relief_rate", "global.tax_rate", "government.balance"],
            },
        },
    )

    result = engine.evaluate_pair(base, mechanism_change)

    assert result.classification.classified_phrasing_only is False
    assert result.classification.harness_label_trusted is False
    assert "sign" in result.classification.denotation_diff_axes
    assert result.evidence_signature_equal is False
    assert result.outcome == "mechanism_changed_control"


def test_proxy_gap_risk_quarantines_surface_mimic_without_admitting_it() -> None:
    reference = _reference(include_transfer_mechanism=False)
    engine = GroundingPhrasingDefenseEngine(reference)

    run = engine.run_pipeline(
        _tax_surface_transfer_no_evidence_probe(),
        proposal_id="unit.proxy_gap.capture",
    )
    risk = engine.detect_proxy_gap(run)
    handoff = engine.quarantine_handoff(risk) if risk else None

    assert risk is not None
    assert risk.disposition == "quarantine"
    assert risk.quarantine_action == "adversarial_validate"
    assert handoff is not None
    assert handoff.front == "quarantine"
    assert handoff.integration_status == "handoff_artifact_n6_direct_intake_not_wired"
    assert run.decisions.cg2_decision != "bind"
    assert run.decisions.cg3_decision != "admit_new_lever"

    mirror = engine.run_pipeline(_tax_exact_probe(), proposal_id="unit.proxy_gap.mirror")
    assert engine.detect_proxy_gap(mirror) is None


def test_signature_only_operator_mimic_quarantines_but_registered_alias_mirror_does_not() -> None:
    reference = _reference(include_transfer_mechanism=False)
    engine = GroundingPhrasingDefenseEngine(reference)

    mimic = engine.run_pipeline(
        _tax_unregistered_mimic_probe("tax relief rate adjustment"),
        proposal_id="unit.proxy_gap.tax_relief_rate_adjustment",
    )
    mimic_risk = engine.detect_proxy_gap(mimic)

    assert mimic.decisions.cg1_relation == "novel-candidate"
    assert mimic.decisions.cg2_decision != "bind"
    assert mimic.decisions.cg3_decision == "non_new"
    assert mimic.evidence_signature.cg3_denotation_match_kind == "signature_only"
    assert mimic.evidence_signature.cg3_mechanism_status == "open"
    assert mimic.evidence_signature.cg3_data_trust_status == "open"
    assert mimic_risk is not None
    assert mimic_risk.disposition == "quarantine"
    assert mimic_risk.not_admissible_while_quarantined is True
    assert mimic_risk.not_bindable_while_quarantined is True

    alias = engine.run_pipeline(
        _tax_unregistered_mimic_probe("tax_credit_rate"),
        proposal_id="unit.proxy_gap.tax_credit_rate_alias",
    )
    assert alias.evidence_signature.cg3_denotation_match_kind == "resolved_proof"
    assert engine.detect_proxy_gap(alias) is None


def test_full_matrix_records_non_vacuous_consumed_intermediate_diffs() -> None:
    reference = _reference(include_transfer_mechanism=True)
    engine = GroundingPhrasingDefenseEngine(reference)
    base_cases = (
        PhrasingDefenseBaseCase(
            case_id="unit.dict_tax",
            case_class="bind_eligible_frozen",
            proposal=_tax_exact_probe(),
        ),
        PhrasingDefenseBaseCase(
            case_id="unit.text_tax",
            case_class="bind_eligible_frozen",
            proposal="tax relief rate lowers the global tax-rate setting.",
        ),
    )

    certificate = engine.evaluate_attack_matrix(base_cases)

    assert certificate.matrix_summary.cg1_proof_mode == "full"
    assert certificate.matrix_summary.consumed_intermediate_diff_counts["raw_text"] > 0
    assert certificate.matrix_summary.consumed_intermediate_diff_counts["retrieval"] > 0
    assert certificate.matrix_summary.self_vacuous is False
    assert certificate.matrix_summary.total_lifted == 0


def test_certificate_is_content_addressed_deterministic_and_mutation_scoped() -> None:
    reference = _reference(include_transfer_mechanism=True)
    base_cases = (
        PhrasingDefenseBaseCase(
            case_id="unit.bind_eligible_frozen",
            case_class="bind_eligible_frozen",
            proposal=_tax_exact_probe(),
        ),
        PhrasingDefenseBaseCase(
            case_id="unit.acquire",
            case_class="acquire",
            proposal=_novel_transfer_probe(),
        ),
    )
    engine = GroundingPhrasingDefenseEngine(reference)

    first = engine.evaluate_attack_matrix(base_cases)
    second = engine.evaluate_attack_matrix(base_cases)
    forged = first.model_dump(mode="json")
    forged["content_hash"] = "sha256:" + "9" * 64
    forged["certificate_id"] = "cg4_cert_9999999999999999"

    assert first.content_hash == second.content_hash
    assert first.matrix_summary.total_lifted == 0
    assert first.authority_scope == "production"
    with pytest.raises(ValueError, match="phrasing_defense_certificate_content_hash_mismatch"):
        PhrasingDefenseCertificate.model_validate(forged)

    mutation = GroundingPhrasingDefenseEngine.for_contract_testing(
        reference,
        allow_surface_lift=True,
    ).evaluate_attack_matrix(base_cases)
    assert mutation.authority_scope == "contract_testing"
    assert mutation.production_authoritative is False

    surface_base = PhrasingDefenseBaseCase(
        case_id="unit.surface_mutation_base",
        case_class="acquire",
        proposal={
            "proposal_id": "unit.surface_mutation_unrelated",
            "raw_text": "opaque adjustment writes an unowned audit slot.",
            "signature": {
                "op": "opaque_resilience_buffer",
                "target": ["audit.unowned_surface_slot"],
                "sign": "increase",
                "params": {"rate": 0.2},
                "x_do": {"rate": 0.2},
                "scope": "audit",
                "population": "audit",
                "unit": "ratio",
                "outcome": ["audit.unowned_outcome"],
                "effect_path": [
                    "opaque_resilience_buffer",
                    "audit.unowned_surface_slot",
                    "audit.unowned_outcome",
                ],
                "estimand": "average_treatment_effect",
                "admissibility": "passed",
                "modal_claims": _modal_claims(
                    op="opaque_resilience_buffer",
                    target="audit.unowned_surface_slot",
                    outcome="audit.unowned_outcome",
                    do_value={"rate": 0.2},
                ),
            },
        },
    )
    surface_transform = PhrasingAttackTransform(
        transform_id="unit.surface_high_affinity",
        family="confidence_bait",
        declared_phrasing_only=True,
        proposal={
            **surface_base.proposal,
            "raw_text": (
                "tax relief rate tax credit rate tax relief statute lowers the "
                "global tax-rate setting."
            ),
        },
    )
    surface_pair = GroundingPhrasingDefenseEngine.for_contract_testing(
        reference,
        allow_surface_lift=True,
    ).evaluate_pair(surface_base, surface_transform)
    assert surface_pair.lifted_gate_ids


def test_production_policy_exposes_no_defense_authority_knobs() -> None:
    reference = _reference(include_transfer_mechanism=True)

    for kwargs in (
        {"surface_threshold": 0.1},
        {"allow_surface_lift": True},
        {"whitelisted_transform_ids": ("x",)},
        {"declared_not_proxy_gap": True},
    ):
        with pytest.raises(ValueError):
            PhrasingDefensePolicy(**kwargs)

    with pytest.raises(TypeError):
        GroundingPhrasingDefenseEngine(reference, surface_threshold=0.1)  # type: ignore[call-arg]


def _reference(*, include_transfer_mechanism: bool) -> CredalReference:
    edges = [
        _operator_edge("tax_relief_rate", minimum=0.0, maximum=0.5, unit="ratio"),
        _target_edge("tax_relief_rate", "global.tax_rate"),
        _lex_edge("tax_relief_statute", "tax_relief_rate"),
        _world_slot("global.tax_rate", unit="ratio", slot_role="policy_input"),
        _world_slot("government.balance", unit="usd"),
        _world_slot("household_cells.transfer_intensity", unit="ratio", slot_role="policy_input"),
        _world_slot("household_cells.disposable_income", unit="usd"),
        _policy_slot("tax_slot", "global.tax_rate"),
        _policy_slot("transfer_slot", "household_cells.transfer_intensity"),
        _policy_slot("income_slot", "household_cells.disposable_income"),
    ]
    if include_transfer_mechanism:
        edges.append(
            _causal_claim(
                "household_cells.transfer_intensity",
                "household_cells.disposable_income",
            )
        )
    edge_index = {edge.key: edge for edge in edges}
    component_versions = {
        "L2": _component_hash(edges, prefix="L2_"),
        "L3": "unit-l3",
        "L6": _component_hash(edges, prefix="L6_"),
        "WMR": "unit-wmr",
    }
    reference_hash = gy_content_hash(
        {
            "component_versions": component_versions,
            "edges": [edge.to_payload() for edge in sorted(edges, key=lambda item: item.key)],
        }
    )
    return CredalReference(
        schema_version=CREDAL_REFERENCE_SCHEMA_VERSION,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of="2026-06-29",
        component_versions=component_versions,
        essential_edges=edge_index,
    )


def _operator_edge(op: str, *, minimum: float, maximum: float, unit: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_KNOB_OPERATOR",
        edge_id=op,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "operator_kind": op,
                    "parameter_domain": {
                        "kind": "range",
                        "max_value": maximum,
                        "min_value": minimum,
                        "unit": unit,
                        "value_type": "float",
                    },
                },
                "unit_test_operator",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
        unit=unit,
    ).with_content_hash()


def _target_edge(op: str, target: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_KNOB_WORLD_SLOT",
        edge_id=op,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "operator_kind": op,
                    "target_world_slots": [target],
                    "world_model_record_id": "unit-wmr",
                },
                "unit_test_target",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _lex_edge(law_token: str, op: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_LEX_INTERVENTION_MAP",
        edge_id=law_token,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion("fixed", {"law_token": law_token, "knob_id": op}, "unit_lex"),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _world_slot(slot: str, *, unit: str, slot_role: str = "state") -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="WMR_WORLD_SLOT",
        edge_id=slot,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"slot_role": slot_role, "world_slot": slot},
                "unit_wmr_slot",
            ),
        ),
        provenance={"owner": "WMR", "source": "unit"},
        unit=unit,
    ).with_content_hash()


def _policy_slot(policy_slot: str, world_slot: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="WMR_POLICY_SLOT_MAP",
        edge_id=f"{policy_slot}:{world_slot}",
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"policy_slot": policy_slot, "world_slot": world_slot},
                "unit_policy_slot",
            ),
        ),
        provenance={"owner": "WMR", "source": "unit"},
    ).with_content_hash()


def _causal_claim(source: str, outcome: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L2_CAUSAL_CLAIM",
        edge_id=f"{source}->{outcome}",
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "confidence": 0.92,
                    "direction": "positive",
                    "dst": outcome,
                    "source": source,
                    "src": source,
                    "target": outcome,
                    "trust_score": 0.92,
                },
                "unit_l2_claim",
            ),
        ),
        provenance={"owner": "L2", "source": "unit", "trust_score": 0.92},
    ).with_content_hash()


def _component_hash(edges: list[CredalReferenceEdge], *, prefix: str) -> str:
    return gy_content_hash(
        [edge.to_payload() for edge in edges if edge.modality.startswith(prefix.rstrip("_"))]
    )


def _tax_exact_probe() -> dict[str, object]:
    return {
        "proposal_id": "unit.tax_relief_exact",
        "raw_text": "tax relief rate lowers the global tax-rate setting.",
        "signature": {
            "op": "tax_relief_rate",
            "target": ["global.tax_rate"],
            "sign": "decrease",
            "params": {"rate": 0.1},
            "x_do": {"rate": 0.1},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": ["tax_relief_rate", "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="tax_relief_rate",
                target="global.tax_rate",
                outcome="government.balance",
                do_value={"rate": 0.1},
            ),
        },
    }


def _tax_unregistered_mimic_probe(op: str) -> dict[str, object]:
    return {
        "proposal_id": f"unit.tax_mimic.{op}",
        "raw_text": f"{op} lowers the global tax-rate setting.",
        "signature": {
            "op": op,
            "target": ["global.tax_rate"],
            "sign": "decrease",
            "params": {"rate": 0.1},
            "x_do": {"rate": 0.1},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": [op, "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op=op,
                target="global.tax_rate",
                outcome="government.balance",
                do_value={"rate": 0.1},
            ),
        },
    }


def _tax_surface_transfer_no_evidence_probe() -> dict[str, object]:
    probe = _novel_transfer_probe()
    return {
        **probe,
        "proposal_id": "unit.proxy_gap.tax_named_transfer",
        "raw_text": (
            "tax relief rate tax relief statute tax credit exact fiscal lever for "
            "household transfer intensity"
        ),
    }


def _novel_transfer_probe() -> dict[str, object]:
    return {
        "proposal_id": "unit.novel.transfer",
        "raw_text": "household transfer intensity increases disposable income.",
        "signature": {
            "op": "household_transfer_adjustment",
            "target": ["household_cells.transfer_intensity"],
            "sign": "increase",
            "params": {"rate": 0.25},
            "x_do": {"rate": 0.25},
            "scope": "households",
            "population": "households",
            "unit": "ratio",
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "household_transfer_adjustment",
                "household_cells.transfer_intensity",
                "household_cells.disposable_income",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="household_transfer_adjustment",
                target="household_cells.transfer_intensity",
                outcome="household_cells.disposable_income",
                do_value={"rate": 0.25},
            ),
        },
    }


def _modal_claims(
    *,
    op: str,
    target: str,
    outcome: str,
    do_value: dict[str, float],
) -> dict[str, dict[str, object]]:
    return {
        "NL": {
            "op": op,
            "target": target,
            "outcome": outcome,
            "estimand": "average_treatment_effect",
        },
        "do_AST": {"op": op, "target": target, "do_value": do_value},
        "method": {
            "treatment_op": op,
            "treatment_target": target,
            "outcome": outcome,
            "estimand": "average_treatment_effect",
        },
    }
