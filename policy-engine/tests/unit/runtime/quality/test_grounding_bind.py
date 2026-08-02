from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_SCHEMA_VERSION,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
    replace_reference_edge,
)
from polisyos.runtime.quality.grounding_bind import (
    CalibrationStratumRecord,
    GroundingBindGate,
    GroundingBindPolicy,
    GroundingCalibrationLedger,
    GroundingDecisionCertificate,
    recompute_grounding_decision_content_hash,
    recompute_grounding_relation_content_hash,
    resolve_grounding_decision_promotability,
    resolve_grounding_decision_promotability_for_contract_testing,
)
from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine


def test_calibrated_exact_robust_singleton_binds_and_records_risk() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-bind")

    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)

    assert decision.decision == "bind"
    assert decision.decisive_reason == "bind_eligible"
    assert decision.authority_scope == "contract_testing"
    assert decision.production_promotable is False
    assert decision.cg1_certificate_id == cg1.certificate_id
    assert decision.cg1_content_hash == cg1.content_hash
    assert decision.reference_epoch == reference.reference_epoch
    assert decision.reference_hash == reference.reference_hash
    assert decision.risk_ledger.total_spend <= decision.risk_ledger.delta_ground_budget
    assert decision.calibration.status == "calibrated"
    assert decision.calibration.owner_validated is True
    assert decision.calibration.calibration_source == "cg2_contract_seed_anchor"
    assert decision.safe_t.safe_atom_ids == (decision.bound_atom_id,)
    assert not decision.open_obligations


def test_public_policy_rejects_bind_authority_knobs() -> None:
    unsafe_policy_kwargs = [
        {"calibration_source": "cg2_contract_seed_anchor"},
        {"disable_calibration_owner_validation": True},
        {"disable_certificate_revalidation": True},
        {"disable_content_hash_check": True},
        {"disable_robust_singleton_check": True},
        {"disable_false_analog_hard_abstain": True},
        {"disable_exact_spec_only_rule": True},
        {"disable_calibration_freeze": True},
        {"disable_epoch_binding": True},
        {"risk_component_bounds": {"delta_monitor": 0.0}},
    ]
    for kwargs in unsafe_policy_kwargs:
        with pytest.raises(ValueError):
            GroundingBindPolicy(**kwargs)


def test_fabricated_caller_calibration_is_rejected_and_freezes_bind() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-fake-cal")
    fabricated = GroundingCalibrationLedger(
        records=(
            CalibrationStratumRecord(
                operator_family="tax_relief_rate",
                reference_region="global",
                relation_type="exact",
                status="calibrated",
                reference_epoch=reference.reference_epoch,
                sample_count=0,
            ),
        )
    )

    decision = GroundingBindGate(reference).certificate_for(
        cg1,
        calibration_ledger=fabricated,
    )

    assert decision.decision == "abstain"
    assert decision.decisive_reason == "cold_start_conservative"
    assert decision.calibration.status == "cold_start"
    assert decision.calibration.owner_validated is False
    assert "caller_calibration_not_owner_validated" in decision.calibration.validation_reasons


def test_spoofed_caller_calibration_still_freezes_bind() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-spoof-cal")
    anchor_id = (
        f"cg2_contract_seed_anchor:{reference.reference_epoch}:"
        "tax_relief_rate:global:exact"
    )
    spoofed = CalibrationStratumRecord(
        operator_family="tax_relief_rate",
        reference_region="global",
        relation_type="exact",
        status="calibrated",
        reference_epoch=reference.reference_epoch,
        sample_count=999,
        provenance="cg2_contract_seed_anchor",
        owner_anchor_id=anchor_id,
        evidence_hash=gy_content_hash(
            {
                "owner_anchor_id": anchor_id,
                "operator_family": "tax_relief_rate",
                "reference_epoch": reference.reference_epoch,
                "reference_region": "global",
                "relation_type": "exact",
                "sample_count": 999,
            }
        ),
    ).with_content_hash()

    decision = GroundingBindGate(reference).certificate_for(
        cg1,
        calibration_ledger=GroundingCalibrationLedger(
            records=(spoofed,),
            ledger_id="spoofed_caller_ledger",
        ),
    )

    assert decision.decision == "abstain"
    assert decision.decisive_reason == "cold_start_conservative"
    assert decision.calibration.status == "cold_start"
    assert decision.calibration.owner_validated is False
    assert "caller_calibration_not_owner_validated" in decision.calibration.validation_reasons


def test_cold_start_exact_freezes_bind() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-cold")

    decision = GroundingBindGate(reference).certificate_for(cg1)

    assert decision.decision == "abstain"
    assert decision.decisive_reason == "cold_start_conservative"
    assert decision.calibration.status == "cold_start"
    assert decision.safe_t.safe_atom_ids


def test_tampered_certificate_fails_closed_before_bind() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-tamper")
    tampered = cg1.model_copy(update={"raw_text_hash": "sha256:" + "0" * 64})

    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(tampered)

    assert decision.decision == "abstain"
    assert decision.decisive_reason == "tampered_cg1_certificate"
    assert decision.revalidation.content_hash_valid is False


def test_forged_selected_relation_is_replayed_against_live_reference() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    exact = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-forged")
    false_proposal = engine.certificate_for(_false_analog_probe(), proposal_id="cg2-false")
    forged_payload = exact.model_dump(mode="json")
    forged_payload["proposal_signature"] = false_proposal.proposal_signature
    forged_payload["raw_text_hash"] = false_proposal.raw_text_hash
    forged_payload["content_hash"] = recompute_grounding_relation_content_hash(
        exact.model_copy(
            update={
                "proposal_signature": false_proposal.proposal_signature,
                "raw_text_hash": false_proposal.raw_text_hash,
            }
        )
    )
    forged = exact.__class__.model_validate(forged_payload)

    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(forged)

    assert decision.decision == "abstain"
    assert decision.decisive_reason == "relation_revalidation_mismatch"
    assert decision.revalidation.replayed_selected_relation != "exact"


def test_contested_support_is_not_a_robust_singleton() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    atom = _tax_atom(engine)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-contested")
    live_reference = _with_contested_edge(reference, atom.edge_scope[0])

    decision = GroundingBindGate.for_contract_testing(
        live_reference,
        calibration_seed_anchor=True,
        disable_certificate_revalidation=True,
        disable_epoch_binding=True,
    ).certificate_for(cg1)

    assert cg1.selected_relation == "exact"
    assert decision.decision == "abstain"
    assert decision.decisive_reason == "robust_singleton_empty"
    assert decision.safe_t.safe_atom_ids == ()
    assert any(item.reason == "support_not_confirmed" for item in decision.safe_t.candidates)


def test_multiple_safe_atoms_abstain_without_picking_one() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-ambiguous")
    selected_atom = cg1.cross_modal_witnesses["selected_pair"]["atom_id"]
    payload = cg1.model_dump(mode="json")
    duplicate_atom = f"{selected_atom}_duplicate"
    payload["atom_signature_or_bundle"][duplicate_atom] = {
        **payload["atom_signature_or_bundle"][selected_atom],
        "countercandidate_reason": None,
        "is_adversarial_countercandidate": False,
    }
    selected_result = next(
        item
        for item in payload["relation_set"]["candidate_results"]
        if item["atom_id"] == selected_atom and item["selected_relation"] == "exact"
    )
    payload["relation_set"]["candidate_results"].append(
        {**selected_result, "atom_id": duplicate_atom}
    )
    cg1 = _with_recomputed_content_hash(cg1, payload)

    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
        disable_certificate_revalidation=True,
    ).certificate_for(cg1)

    assert cg1.selected_relation == "exact"
    assert decision.decision == "abstain"
    assert decision.decisive_reason == "robust_singleton_ambiguous"
    assert len(decision.safe_t.safe_atom_ids) > 1
    assert decision.bound_atom_id is None


def test_false_analog_hard_abstains_even_when_cg1_hands_off_novel() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_false_analog_probe(), proposal_id="cg2-false-hard")

    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)

    assert cg1.selected_relation == "novel-candidate"
    assert cg1.critical_contradictions
    assert decision.decision == "abstain"
    assert decision.decisive_reason == "false_analog_hard_abstain"


def test_false_analog_hard_abstain_mutation_is_causal_when_other_obligations_close() -> None:
    """Removing only the veto reaches the independent DTO safety invariant."""

    reference = _reference()
    engine = GroundingRelationEngine(reference)
    probe = _pure_synonym_probe(engine)
    signature = probe["signature"]
    assert isinstance(signature, dict)
    signature["sign"] = "increase" if signature.get("sign") != "increase" else "decrease"
    signature["admissibility"] = "passed"
    cg1 = engine.certificate_for(probe, proposal_id="cg2-false-causal")

    baseline = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)
    mutated_gate = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
        disable_false_analog_hard_abstain=True,
    )

    assert cg1.critical_contradictions
    assert baseline.decisive_reason == "false_analog_hard_abstain"
    with pytest.raises(
        ValidationError,
        match="bind_certificate_requires_robust_singleton",
    ) as exc_info:
        mutated_gate.certificate_for(cg1)
    unsafe = exc_info.value.errors(include_url=False)[0]["input"]
    assert unsafe["decision"] == "bind"
    assert unsafe["decisive_reason"] == "bind_eligible"
    assert unsafe["open_obligations"] == []
    assert all(item["status"] == "closed" for item in unsafe["obligations"])


def test_candidate_unverified_obligation_abstains() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-open")
    payload = cg1.model_dump(mode="json")
    payload["proposal_signature"]["hypotheses"][0]["signature"][
        "admissibility"
    ] = "candidate_unverified"
    cg1 = _with_recomputed_content_hash(cg1, payload)

    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
        disable_certificate_revalidation=True,
    ).certificate_for(cg1)

    assert cg1.selected_relation == "exact"
    assert decision.decision == "abstain"
    assert decision.decisive_reason == "open_obligation"
    assert "admissibility_closed" in decision.open_obligations


def test_unsafe_bind_decision_certificate_cannot_be_deserialized() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-dto")
    decision = GroundingBindGate(reference).certificate_for(cg1)
    payload = decision.model_dump(mode="json")
    payload["decision"] = "bind"
    payload["decisive_reason"] = "bind_eligible"
    payload["bound_atom_id"] = decision.safe_t.safe_atom_ids[0]
    payload["production_promotable"] = True
    payload["content_hash"] = recompute_grounding_decision_content_hash(payload)
    payload["certificate_id"] = (
        f"cg2_cert_{payload['content_hash'].removeprefix('sha256:')[:16]}"
    )

    with pytest.raises(
        ValueError,
        match="promotable_certificate_requires_calibrated_stratum",
    ):
        decision.__class__.model_validate(payload)


def test_bind_decision_certificate_rejects_caller_supplied_calibration_source() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-dto-caller")
    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)
    payload = decision.model_dump(mode="json")
    payload["calibration"]["calibration_source"] = "caller_supplied_unvalidated"
    payload["content_hash"] = recompute_grounding_decision_content_hash(payload)
    payload["certificate_id"] = (
        f"cg2_cert_{payload['content_hash'].removeprefix('sha256:')[:16]}"
    )

    with pytest.raises(ValueError, match="bind_certificate_rejects_caller_supplied"):
        decision.__class__.model_validate(payload)


def test_decision_certificate_rejects_bogus_content_hash() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-dto-hash")
    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)
    payload = decision.model_dump(mode="json")
    payload["content_hash"] = "sha256:" + "2" * 64
    payload["certificate_id"] = "cg2_cert_2222222222222222"

    with pytest.raises(ValueError, match="decision_certificate_content_hash_mismatch"):
        GroundingDecisionCertificate.model_validate(payload)


def test_forged_promotable_production_certificate_resolves_non_promotable() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-dto-forge")
    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)
    payload = decision.model_dump(mode="json")
    payload["authority_scope"] = "production"
    payload["production_promotable"] = True
    payload["calibration"]["calibration_source"] = "fabricated_production_anchor_store"
    payload["calibration"]["status"] = "calibrated"
    payload["calibration"]["owner_validated"] = True
    payload["calibration"]["owned_anchor_id"] = "fabricated_production_anchor"
    payload["calibration"]["owned_anchor_content_hash"] = "sha256:" + "3" * 64
    payload["calibration"]["validation_reasons"] = ["owned_calibration_anchor_validated"]
    payload["content_hash"] = recompute_grounding_decision_content_hash(payload)
    payload["certificate_id"] = (
        f"cg2_cert_{payload['content_hash'].removeprefix('sha256:')[:16]}"
    )

    forged = GroundingDecisionCertificate.model_validate(payload)
    resolution = resolve_grounding_decision_promotability(forged, reference)

    assert forged.production_promotable is True
    assert resolution.promotable is False
    assert resolution.reason == "owned_anchor_missing"


def test_contract_testing_bind_resolves_non_promotable() -> None:
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="cg2-dto-test")
    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)

    resolution = resolve_grounding_decision_promotability_for_contract_testing(
        decision,
        reference,
    )

    assert decision.decision == "bind"
    assert decision.production_promotable is False
    assert resolution.store_authority_scope == "contract_testing"
    assert resolution.promotable is False
    assert resolution.reason == "non_production_anchor_scope"


def _reference(*, include_duplicate_tax_alias: bool = False) -> CredalReference:
    edges = [
        _operator_edge("tax_relief_rate", minimum=0.0, maximum=0.5, unit="ratio"),
        _target_edge("tax_relief_rate", "global.tax_rate"),
        _lex_edge("tax_relief_statute", "tax_relief_rate"),
        _operator_edge("budget_allocation_multiplier", minimum=0.0, maximum=2.0, unit="ratio"),
        _target_edge("budget_allocation_multiplier", "government.balance"),
        _lex_edge("budget_law", "budget_allocation_multiplier"),
        _world_slot("global.tax_rate", unit="ratio"),
        _world_slot("government.balance", unit="usd"),
        _world_slot("household_cells.disposable_income", unit="usd"),
        _world_slot("household_cells.transfer_intensity", unit="ratio"),
        _policy_slot("tax_slot", "global.tax_rate"),
        _policy_slot("budget_slot", "government.balance"),
        _policy_slot("transfer_slot", "household_cells.transfer_intensity"),
    ]
    if include_duplicate_tax_alias:
        edges.extend(
            [
                _operator_edge("tax_credit_rate", minimum=0.0, maximum=0.5, unit="ratio"),
                _target_edge("tax_credit_rate", "global.tax_rate"),
                _lex_edge("tax_credit_statute", "tax_credit_rate"),
            ]
        )
    edge_index = {edge.key: edge for edge in edges}
    component_versions = {
        "L2": "unit-l2",
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


def _operator_edge(
    op: str,
    *,
    minimum: float,
    maximum: float,
    unit: str,
) -> CredalReferenceEdge:
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
            AdmissibleCompletion(
                "fixed",
                {"law_token": law_token, "knob_id": op},
                "unit_test_lex_map",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _world_slot(slot: str, *, unit: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="WMR_WORLD_SLOT",
        edge_id=slot,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion("fixed", {"world_slot": slot}, "unit_test_wmr_slot"),
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
                "unit_test_policy_slot",
            ),
        ),
        provenance={"owner": "WMR", "source": "unit"},
    ).with_content_hash()


def _component_hash(edges: list[CredalReferenceEdge], *, prefix: str) -> str:
    return gy_content_hash(
        [
            edge.content_hash
            for edge in sorted(edges, key=lambda item: item.key)
            if edge.modality.startswith(prefix)
        ]
    )


def _with_contested_edge(reference: CredalReference, edge_key_text: str) -> CredalReference:
    modality, edge_id = edge_key_text.split("::", 1)
    old = reference.essential_edges[(modality, edge_id)]
    contested = CredalReferenceEdge(
        modality=old.modality,
        edge_id=old.edge_id,
        status="contested",
        admissible_completions=(
            AdmissibleCompletion("alternative", {"edge_id": old.edge_id}, "unit_contested"),
            AdmissibleCompletion("may_not_exist", {"edge_id": old.edge_id}, "unit_contested"),
        ),
        provenance=old.provenance,
        unit=old.unit,
        scale=old.scale,
    ).with_content_hash()
    return replace_reference_edge(reference, contested)


def _tax_atom(engine: GroundingRelationEngine) -> object:
    return next(
        item
        for item in engine.reference_atoms
        if item.signature.op == "tax_relief_rate" and "global.tax_rate" in item.signature.X_do
    )


def _pure_synonym_probe(engine: GroundingRelationEngine) -> dict[str, object]:
    atom = _tax_atom(engine)
    signature = atom.signature.model_dump(mode="json")
    signature["op"] = "tax_credit_rate"
    signature["effect_path"] = [
        "tax_credit_rate",
        *list(atom.signature.X_do),
        *list(atom.signature.outcome),
    ]
    signature["modal_claims"] = {
        "NL": {
            "op": "tax_credit_rate",
            "target": atom.signature.X_do[0],
            "outcome": atom.signature.outcome[0],
            "estimand": atom.signature.estimand,
        },
        "L6": {"knob": "tax_relief_rate"},
        "do_AST": {"op": "tax_credit_rate", "target": atom.signature.X_do[0]},
        "method": {
            "treatment_op": "tax_credit_rate",
            "treatment_target": atom.signature.X_do[0],
            "outcome": atom.signature.outcome[0],
            "estimand": atom.signature.estimand,
        },
    }
    return {
        "raw_text": "levy credit-rate alias for the exact same tax relief do-query.",
        "signature": signature,
    }


def _false_analog_probe() -> dict[str, object]:
    return {
        "raw_text": "tax relief rate with the wrong sign but similar fiscal language",
        "signature": {
            "op": "tax_relief_rate",
            "target": ["global.tax_rate"],
            "sign": "increase",
            "params": {"rate": 0.08},
            "x_do": {"rate": 0.08},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": [
                "tax_relief_rate",
                "global.tax_rate",
                "government.balance",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "candidate_unverified",
            "modal_claims": {
                "NL": {
                    "op": "tax_relief_rate",
                    "target": "global.tax_rate",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                }
            },
        },
    }


def _with_recomputed_content_hash(cg1: object, payload: dict[str, object]) -> object:
    provisional = cg1.__class__.model_validate(payload)
    payload["content_hash"] = recompute_grounding_relation_content_hash(provisional)
    payload["certificate_id"] = (
        f"cg1_cert_{str(payload['content_hash']).removeprefix('sha256:')[:16]}"
    )
    return cg1.__class__.model_validate(payload)
