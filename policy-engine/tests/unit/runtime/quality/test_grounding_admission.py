from __future__ import annotations

import pytest

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_SCHEMA_VERSION,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
    replace_reference_edge,
)
from polisyos.runtime.quality.grounding_admission import (
    GroundingAdmissionCertificate,
    GroundingAdmissionEngine,
    GroundingAdmissionPolicy,
    apply_grounding_admission_registry_patch,
    recompute_grounding_admission_content_hash,
)
from polisyos.runtime.quality.grounding_bind import GroundingBindGate
from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
)


def test_real_novel_lever_admits_and_records_content_addressed_patch() -> None:
    reference = _reference(include_mechanism=True)
    cg1, cg2 = _cg2_novel(reference, _novel_transfer_probe())

    admission = GroundingAdmissionEngine(reference).decide(
        cg2,
        cg1_certificate=cg1,
    )

    assert cg2.decision == "novel_candidate"
    assert admission.decision == "admit_new_lever"
    assert admission.authority_scope == "production"
    assert admission.production_promotable is True
    assert admission.stable_unique.stable is True
    assert admission.mechanism_witness.status == "closed"
    assert admission.registry_patch is not None
    assert admission.registry_patch.operator_kind == "emergency_cooling_subsidy"
    assert admission.registry_patch.application_status == "shadow_applied"
    assert admission.registry_patch.decision_front_created is False
    assert admission.admission_ledger is not None
    assert admission.admission_ledger.patch_ids == (admission.registry_patch.patch_id,)
    assert admission.delta_adm_ledger.within_budget is True


def test_unknown_or_missing_proof_acquires_and_never_rejects() -> None:
    reference = _reference(include_mechanism=False)
    cg1, cg2 = _cg2_novel(reference, _novel_transfer_probe())

    admission = GroundingAdmissionEngine(reference).decide(
        cg2,
        cg1_certificate=cg1,
    )

    assert admission.decision == "acquire_then_decide"
    assert admission.registry_patch is None
    assert "mechanism_witness" in admission.open_obligations
    assert admission.acquisition_need is not None
    assert admission.acquisition_need.blocker_id == "mechanism_witness_required"
    assert admission.decisive_reject_proof is None


@pytest.mark.parametrize(
    ("probe_id", "reason"),
    [
        ("outcome_wish", "outcome_wish"),
        ("proxy_manipulation", "proxy_manipulation"),
        ("impossible_type", "impossible_type"),
    ],
)
def test_proven_hallucination_subtypes_reject(probe_id: str, reason: str) -> None:
    reference = _reference(include_mechanism=False)
    probe = {
        "outcome_wish": _outcome_wish_probe,
        "proxy_manipulation": _proxy_manipulation_probe,
        "impossible_type": _impossible_type_probe,
    }[probe_id]()
    if probe_id == "proxy_manipulation":
        reference = replace_reference_edge(
            reference,
            _causal_claim(
                "agents.reported_income",
                "household_cells.disposable_income",
                status="confirmed",
            ),
        )
    cg1, cg2 = _cg2_novel(reference, probe)

    admission = GroundingAdmissionEngine(reference).decide(
        cg2,
        cg1_certificate=cg1,
    )

    assert admission.decision == "reject_hallucination"
    assert admission.decisive_reason == reason
    assert admission.decisive_reject_proof == reason
    assert admission.registry_patch is None


def test_paraphrase_routes_non_new_without_registry_pollution() -> None:
    reference = _reference(include_mechanism=True)
    cg1, cg2 = _cg2_novel(reference, _paraphrase_probe())

    admission = GroundingAdmissionEngine(reference).decide(
        cg2,
        cg1_certificate=cg1,
    )

    assert admission.decision == "non_new"
    assert admission.decisive_reason == "novel_irreducible_failed_existing_atom"
    assert admission.registry_patch is None
    assert "novel_irreducible" in admission.open_obligations


def test_fabricated_mechanism_flag_is_not_admission_proof() -> None:
    reference = _reference(include_mechanism=False)
    probe = _novel_transfer_probe()
    signature = dict(probe["signature"])  # type: ignore[index]
    signature["evidence"] = ["mechanism_witness=true", "caller_says_l2_proof"]
    signature["modal_claims"] = {
        **dict(signature["modal_claims"]),  # type: ignore[index]
        "LLM": {"mechanism_witness": True, "rationale": "looks causal"},
    }
    cg1, cg2 = _cg2_novel(reference, {**probe, "signature": signature})

    admission = GroundingAdmissionEngine(reference).decide(
        cg2,
        cg1_certificate=cg1,
    )

    assert admission.decision == "acquire_then_decide"
    assert admission.mechanism_witness.status == "open"
    assert admission.mechanism_witness.evidence.get("caller_claims_ignored") is True
    assert admission.registry_patch is None


def test_ambiguous_multi_completion_acquires_instead_of_picking_one() -> None:
    reference = _with_contested_mechanism(_reference(include_mechanism=True))
    cg1, cg2 = _cg2_novel(reference, _novel_transfer_probe())

    admission = GroundingAdmissionEngine(reference).decide(
        cg2,
        cg1_certificate=cg1,
    )

    assert admission.decision == "acquire_then_decide"
    assert admission.stable_unique.stable is False
    assert admission.stable_unique.reason == "multiple_incompatible_completions"
    assert admission.registry_patch is None


def test_production_policy_exposes_no_admit_authority_knobs() -> None:
    unsafe_kwargs = [
        {"force_admit": True},
        {"disable_mechanism_witness_resolution": True},
        {"disable_stable_unique": True},
        {"delta_adm_budget": 1.0},
        {"mechanism_witness": True},
    ]
    for kwargs in unsafe_kwargs:
        with pytest.raises(ValueError):
            GroundingAdmissionPolicy(**kwargs)


def test_contract_testing_admit_is_scoped_and_non_promotable() -> None:
    reference = _reference(include_mechanism=True)
    cg1, cg2 = _cg2_novel(reference, _novel_transfer_probe())

    admission = GroundingAdmissionEngine.for_contract_testing(
        reference,
        substrate_registry=_substrate_registry(),
    ).decide(cg2, cg1_certificate=cg1)

    assert admission.decision == "admit_new_lever"
    assert admission.authority_scope == "contract_testing"
    assert admission.production_promotable is False
    assert admission.registry_patch is not None
    assert admission.registry_patch.authority_scope == "contract_testing"


def test_admission_certificate_is_deterministic_and_hash_checked() -> None:
    reference = _reference(include_mechanism=True)
    cg1, cg2 = _cg2_novel(reference, _novel_transfer_probe())
    engine = GroundingAdmissionEngine(reference)

    first = engine.decide(cg2, cg1_certificate=cg1)
    second = engine.decide(cg2, cg1_certificate=cg1)
    payload = first.model_dump(mode="json")
    payload["content_hash"] = "sha256:" + "7" * 64
    payload["certificate_id"] = "cg3_cert_7777777777777777"

    assert first.content_hash == second.content_hash
    assert first.certificate_id == second.certificate_id
    with pytest.raises(ValueError, match="admission_certificate_content_hash_mismatch"):
        GroundingAdmissionCertificate.model_validate(payload)


def test_forged_admission_certificate_cannot_patch_registry_without_re_resolution() -> None:
    reference = _reference(include_mechanism=False)
    cg1, cg2 = _cg2_novel(reference, _novel_transfer_probe())
    acquire = GroundingAdmissionEngine(reference).decide(
        cg2,
        cg1_certificate=cg1,
    )
    forged_payload = acquire.model_dump(mode="json")
    forged_payload["decision"] = "admit_new_lever"
    forged_payload["decisive_reason"] = "all_obligations_closed"
    forged_payload["production_promotable"] = True
    forged_payload["content_hash"] = recompute_grounding_admission_content_hash(forged_payload)
    forged_payload["certificate_id"] = (
        f"cg3_cert_{forged_payload['content_hash'].removeprefix('sha256:')[:16]}"
    )
    forged = GroundingAdmissionCertificate.model_validate(forged_payload)

    resolution = apply_grounding_admission_registry_patch(
        forged,
        cg2,
        reference,
        cg1_certificate=cg1,
    )

    assert forged.decision == "admit_new_lever"
    assert resolution.applied is False
    assert resolution.reason == "admission_re_resolution_mismatch"


def test_self_loop_outcome_wish_edge_does_not_admit() -> None:
    reference = replace_reference_edge(
        _reference(include_mechanism=False),
        _causal_claim(
            "household_cells.disposable_income",
            "household_cells.disposable_income",
            status="confirmed",
        ),
    )
    cg1, cg2 = _cg2_novel(reference, _self_loop_outcome_wish_probe())

    admission = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)

    assert admission.decision == "reject_hallucination"
    assert admission.decisive_reason == "outcome_wish"
    assert admission.mechanism_witness.status == "open"
    assert admission.registry_patch is None


def test_proxy_reporting_slot_crafted_edge_does_not_admit() -> None:
    reference = replace_reference_edge(
        _reference(include_mechanism=False),
        _causal_claim(
            "agents.reported_income",
            "household_cells.disposable_income",
            status="confirmed",
        ),
    )
    cg1, cg2 = _cg2_novel(reference, _reported_income_proxy_probe())

    admission = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)

    assert admission.decision == "reject_hallucination"
    assert admission.decisive_reason == "proxy_manipulation"
    assert admission.mechanism_witness.status == "open"
    assert admission.registry_patch is None


def test_spoofed_substrate_registry_is_not_production_authority() -> None:
    reference = _low_trust_mechanism_reference()
    cg1, cg2 = _cg2_novel(reference, _novel_transfer_probe())

    acquire = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)

    assert acquire.decision == "acquire_then_decide"
    assert acquire.decisive_reason == "data_trust_below_floor"
    with pytest.raises(TypeError):
        GroundingAdmissionEngine(reference, substrate_registry=_spoofed_registry())  # type: ignore[call-arg]


def test_proxy_named_real_but_unproven_lever_acquires_not_rejects() -> None:
    reference = _reference(include_mechanism=False)
    cg1, cg2 = _cg2_novel(reference, _proxy_named_real_unproven_probe())

    admission = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)

    assert admission.decision == "acquire_then_decide"
    assert admission.decisive_reason == "mechanism_witness_missing"
    assert admission.decisive_reject_proof is None


def test_denotation_paraphrase_new_name_same_do_query_is_non_new() -> None:
    reference = replace_reference_edge(
        _reference(include_mechanism=False),
        _causal_claim("global.tax_rate", "government.balance", status="confirmed"),
    )
    cg1, cg2 = _cg2_novel(reference, _paraphrase_probe())

    admission = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)

    assert admission.decision == "non_new"
    assert admission.registry_patch is None


def test_unregistered_operator_signature_match_is_graded_signature_only() -> None:
    reference = _reference(include_mechanism=False)
    cg1, cg2 = _cg2_novel(reference, _unregistered_tax_mimic_probe())

    admission = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)

    assert admission.decision == "non_new"
    assert admission.registry_patch is None
    novel = next(item for item in admission.obligations if item.obligation_id == "novel_irreducible")
    assert novel.evidence["existing_atom_match_kind"] == "signature_only"
    assert novel.evidence["operator_denotation_proof"] == "unresolved"
    assert novel.evidence["existing_atom_operator"] == "tax_relief_rate"


def test_multi_hop_confirmed_chain_acquires_as_unverified_composition() -> None:
    reference = _with_edges(
        _reference(include_mechanism=False),
        _causal_claim(
            "household_cells.transfer_intensity",
            "audit.bridge",
            status="confirmed",
        ),
        _causal_claim(
            "audit.bridge",
            "household_cells.disposable_income",
            status="confirmed",
        ),
    )
    cg1, cg2 = _cg2_novel(reference, _novel_transfer_probe())

    admission = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)

    assert admission.decision == "acquire_then_decide"
    assert admission.decisive_reason == "mechanism_composition_unverified"
    assert admission.acquisition_need is not None
    assert admission.acquisition_need.blocker_id == "mechanism_composition_unverified"
    assert admission.mechanism_witness.status == "open"
    assert admission.mechanism_witness.evidence["path_length"] == 2
    assert admission.data_trust.resolved_trust_cap == pytest.approx(0.92)
    assert admission.registry_patch is None


def test_low_trust_hop_uses_minimum_path_trust_and_does_not_admit() -> None:
    reference = _with_edges(
        _reference(include_mechanism=False),
        _causal_claim(
            "household_cells.transfer_intensity",
            "audit.low_trust_bridge",
            status="confirmed",
            trust_score=0.95,
            confidence=0.95,
        ),
        _causal_claim(
            "audit.low_trust_bridge",
            "household_cells.disposable_income",
            status="confirmed",
            trust_score=0.2,
            confidence=0.2,
        ),
    )
    cg1, cg2 = _cg2_novel(reference, _novel_transfer_probe())

    admission = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)

    assert admission.decision == "acquire_then_decide"
    assert admission.decisive_reason == "mechanism_composition_unverified"
    assert admission.mechanism_witness.status == "open"
    assert admission.mechanism_witness.evidence["path_trust_cap"] == pytest.approx(0.2)
    assert admission.data_trust.resolved_trust_cap == pytest.approx(0.2)
    assert admission.data_trust.status == "open"
    assert admission.registry_patch is None


def test_compatibility_derived_denotation_alias_is_non_new() -> None:
    reference = _reference(include_mechanism=True)
    cg1, cg2 = _cg2_novel(reference, _compatibility_derived_alias_probe())

    admission = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)

    assert admission.decision == "non_new"
    assert admission.decisive_reason == "novel_irreducible_failed_existing_atom"
    assert admission.registry_patch is None
    novel = next(item for item in admission.obligations if item.obligation_id == "novel_irreducible")
    assert novel.evidence["existing_atom_match_kind"] == "signature_only"
    assert novel.evidence["operator_denotation_proof"] == "unresolved"


def test_map_mentioned_outcome_slot_is_not_actuatable_without_positive_write_proof() -> None:
    reference = replace_reference_edge(
        _reference(include_mechanism=False),
        _causal_claim(
            "household_cells.disposable_income",
            "government.balance",
            status="confirmed",
        ),
    )
    cg1, cg2 = _cg2_novel(reference, _outcome_like_policy_map_probe())

    admission = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)

    assert admission.decision == "acquire_then_decide"
    assert admission.mechanism_witness.status == "open"
    assert admission.mechanism_witness.evidence["actuatability"]["actuatable"] is False
    assert admission.mechanism_witness.evidence["actuatability"]["reason"] == "no_positive_writability_proof"
    assert "do_semantics" in admission.open_obligations
    assert admission.registry_patch is None


def _cg2_novel(reference: CredalReference, probe: dict[str, object]) -> tuple[object, object]:
    cg1 = GroundingRelationEngine(reference).certificate_for(probe, proposal_id=str(probe["proposal_id"]))
    cg2 = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)
    return cg1, cg2


def _reference(*, include_mechanism: bool) -> CredalReference:
    edges = [
        _operator_edge("tax_relief_rate", minimum=0.0, maximum=0.5, unit="ratio"),
        _target_edge("tax_relief_rate", "global.tax_rate"),
        _lex_edge("tax_relief_statute", "tax_relief_rate"),
        _world_slot("global.tax_rate", unit="ratio"),
        _world_slot("government.balance", unit="usd"),
        _world_slot("household_cells.transfer_intensity", unit="ratio", slot_role="policy_input"),
        _world_slot("household_cells.disposable_income", unit="usd"),
        _world_slot("agents.reported_income", unit="usd", temporal_granularity="flow"),
        _policy_slot("tax_slot", "global.tax_rate"),
        _policy_slot("transfer_slot", "household_cells.transfer_intensity"),
        _policy_slot("income_slot", "household_cells.disposable_income"),
        _policy_slot("reported_income_slot", "agents.reported_income"),
    ]
    if include_mechanism:
        edges.append(
            _causal_claim(
                "household_cells.transfer_intensity",
                "household_cells.disposable_income",
                status="confirmed",
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


def _with_edges(reference: CredalReference, *edges: CredalReferenceEdge) -> CredalReference:
    for edge in edges:
        reference = replace_reference_edge(reference, edge)
    return reference


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


def _world_slot(
    slot: str,
    *,
    unit: str,
    temporal_granularity: str = "stock",
    slot_role: str | None = None,
) -> CredalReferenceEdge:
    value = {
        "slot_id": slot,
        "temporal_granularity": temporal_granularity,
        "world_slot": slot,
    }
    signals = {"temporal_granularity": temporal_granularity}
    if slot_role:
        value["slot_role"] = slot_role
        signals["slot_role"] = slot_role
    return CredalReferenceEdge(
        modality="WMR_WORLD_SLOT",
        edge_id=slot,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                value,
                "unit_test_wmr_slot",
            ),
        ),
        provenance={
            "owner": "WMR",
            "source": "unit",
            "signals": signals,
        },
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


def _causal_claim(
    src: str,
    dst: str,
    *,
    status: str,
    trust_score: float = 0.92,
    confidence: float = 0.91,
) -> CredalReferenceEdge:
    completions = (
        (
            AdmissibleCompletion(
                "fixed",
                {"direction": "positive", "dst": dst, "src": src},
                "unit_mechanism_supported",
            ),
        )
        if status == "confirmed"
        else (
            AdmissibleCompletion(
                "alternative",
                {"direction": "positive", "dst": dst, "src": src},
                "unit_mechanism_contested",
            ),
            AdmissibleCompletion(
                "may_not_exist",
                {"direction": "positive", "dst": dst, "src": src},
                "unit_mechanism_contested",
            ),
        )
    )
    return CredalReferenceEdge(
        modality="L2_CAUSAL_CLAIM",
        edge_id=f"{src}->{dst}",
        status=status,  # type: ignore[arg-type]
        admissible_completions=completions,
        provenance={
            "owner": "L2",
            "source": "ac_causal_claims",
            "signals": {
                "confidence": confidence,
                "strong_design_evidence": True,
                "trust_score": trust_score,
            },
        },
    ).with_content_hash()


def _with_contested_mechanism(reference: CredalReference) -> CredalReference:
    return replace_reference_edge(
        reference,
        _causal_claim(
            "household_cells.transfer_intensity",
            "household_cells.disposable_income",
            status="contested",
        ),
    )


def _low_trust_mechanism_reference() -> CredalReference:
    return replace_reference_edge(
        _reference(include_mechanism=False),
        _causal_claim(
            "household_cells.transfer_intensity",
            "household_cells.disposable_income",
            status="confirmed",
            trust_score=0.2,
            confidence=0.2,
        ),
    )


def _component_hash(edges: list[CredalReferenceEdge], *, prefix: str) -> str:
    return gy_content_hash(
        [
            edge.content_hash
            for edge in sorted(edges, key=lambda item: item.key)
            if edge.modality.startswith(prefix)
        ]
    )


def _substrate_registry() -> object:
    registration = SubstrateRegistration(
        source_id="l2_scholar_kg",
        family_id="l2_scholar_kg_causal_priors_transport",
        layer=SubstrateLayer.L2,
        coverage=SubstrateCoverage(
            coverage_score=0.9,
            coverage_kind="unit_owner_l5",
            coverage_rule_ref="unit://l5/coverage",
        ),
        trust_tier=SubstrateTrustTier(
            tier="high",
            trust_cap=0.9,
            trust_multiplier=0.9,
            min_coverage=0.8,
            max_coverage=1.0,
            authority_ref="unit://l5/trust/high",
        ),
        identification_mode="owner_resolved",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id="unit_l5_schema",
            authority_ref="unit://l5/schema",
        ),
        data_version="unit",
        snapshot_id="unit",
        source_snapshot_id="unit",
        provenance_refs=("unit://l5",),
        authority_refs=("unit://l5/trust/high",),
    )
    return build_substrate_registry(
        (build_substrate_registry_entry(registration),),
        producer_ref="unit.substrate_registry",
        source_catalog_refs=("unit://l5",),
    )


def _spoofed_registry() -> object:
    class _Trust:
        trust_cap = 0.99

    class _Entry:
        layer = "L2"
        family_id = "spoof_causal_family"
        trust_tier = _Trust()
        authority_refs = ("spoof://caller",)

    class _Registry:
        entries = (_Entry(),)

    return _Registry()


def _novel_transfer_probe() -> dict[str, object]:
    return {
        "proposal_id": "cg3.novel.cooling_subsidy",
        "raw_text": "emergency cooling subsidy raises transfer intensity for households.",
        "signature": {
            "op": "emergency_cooling_subsidy",
            "target": ["household_cells.transfer_intensity"],
            "sign": "increase",
            "params": {"rate": 0.4},
            "x_do": {"rate": 0.4},
            "scope": "households",
            "population": "households",
            "unit": "ratio",
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "emergency_cooling_subsidy",
                "household_cells.transfer_intensity",
                "household_cells.disposable_income",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": {
                "NL": {
                    "op": "emergency_cooling_subsidy",
                    "target": "household_cells.transfer_intensity",
                    "outcome": "household_cells.disposable_income",
                    "estimand": "average_treatment_effect",
                },
                "do_AST": {
                    "op": "emergency_cooling_subsidy",
                    "target": "household_cells.transfer_intensity",
                    "do_value": {"rate": 0.4},
                },
            },
        },
    }


def _outcome_wish_probe() -> dict[str, object]:
    probe = _novel_transfer_probe()
    signature = dict(probe["signature"])  # type: ignore[index]
    signature.update(
        {
            "op": None,
            "target": [],
            "x_do": {},
            "effect_path": [],
            "outcome": ["household_cells.disposable_income"],
        }
    )
    return {**probe, "proposal_id": "cg3.reject.outcome_wish", "signature": signature}


def _self_loop_outcome_wish_probe() -> dict[str, object]:
    probe = _novel_transfer_probe()
    signature = dict(probe["signature"])  # type: ignore[index]
    signature.update(
        {
            "op": "raise_household_income_goal",
            "target": ["household_cells.disposable_income"],
            "params": {"goal": 1.0},
            "x_do": {"goal": 1.0},
            "unit": "usd",
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "raise_household_income_goal",
                "household_cells.disposable_income",
                "household_cells.disposable_income",
            ],
            "modal_claims": _modal_claims(
                op="raise_household_income_goal",
                target="household_cells.disposable_income",
                outcome="household_cells.disposable_income",
                do_value={"goal": 1.0},
            ),
        }
    )
    return {**probe, "proposal_id": "cg3.reject.self_loop_outcome_wish", "signature": signature}


def _proxy_manipulation_probe() -> dict[str, object]:
    probe = _novel_transfer_probe()
    signature = dict(probe["signature"])  # type: ignore[index]
    signature.update(
        {
            "op": "reported_income_adjustment",
            "target": ["agents.reported_income"],
            "params": {"reporting_delta": 0.2},
            "x_do": {"reporting_delta": 0.2},
            "unit": "usd",
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "reported_income_adjustment",
                "agents.reported_income",
                "household_cells.disposable_income",
            ],
            "modal_claims": _modal_claims(
                op="reported_income_adjustment",
                target="agents.reported_income",
                outcome="household_cells.disposable_income",
                do_value={"reporting_delta": 0.2},
            ),
        }
    )
    return {**probe, "proposal_id": "cg3.reject.proxy", "signature": signature}


def _reported_income_proxy_probe() -> dict[str, object]:
    probe = _novel_transfer_probe()
    signature = dict(probe["signature"])  # type: ignore[index]
    signature.update(
        {
            "op": "reported_income_adjustment",
            "target": ["agents.reported_income"],
            "params": {"reporting_delta": 0.2},
            "x_do": {"reporting_delta": 0.2},
            "unit": "usd",
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "reported_income_adjustment",
                "agents.reported_income",
                "household_cells.disposable_income",
            ],
            "modal_claims": _modal_claims(
                op="reported_income_adjustment",
                target="agents.reported_income",
                outcome="household_cells.disposable_income",
                do_value={"reporting_delta": 0.2},
            ),
        }
    )
    return {**probe, "proposal_id": "cg3.acquire.reported_income_proxy", "signature": signature}


def _proxy_named_real_unproven_probe() -> dict[str, object]:
    probe = _novel_transfer_probe()
    signature = dict(probe["signature"])  # type: ignore[index]
    signature.update(
        {
            "op": "proxy_means_test_transfer_adjustment",
            "target": ["household_cells.transfer_intensity"],
            "params": {"rate": 0.25},
            "x_do": {"rate": 0.25},
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "proxy_means_test_transfer_adjustment",
                "household_cells.transfer_intensity",
                "household_cells.disposable_income",
            ],
            "modal_claims": _modal_claims(
                op="proxy_means_test_transfer_adjustment",
                target="household_cells.transfer_intensity",
                outcome="household_cells.disposable_income",
                do_value={"rate": 0.25},
            ),
        }
    )
    return {**probe, "proposal_id": "cg3.acquire.proxy_named_real", "signature": signature}


def _impossible_type_probe() -> dict[str, object]:
    probe = _novel_transfer_probe()
    signature = dict(probe["signature"])  # type: ignore[index]
    signature.update(
        {
            "op": "malformed_slot_write",
            "target": ["not-a-world-slot"],
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "malformed_slot_write",
                "not-a-world-slot",
                "household_cells.disposable_income",
            ],
            "modal_claims": _modal_claims(
                op="malformed_slot_write",
                target="not-a-world-slot",
                outcome="household_cells.disposable_income",
                do_value={"rate": 0.1},
            ),
        }
    )
    return {**probe, "proposal_id": "cg3.reject.impossible", "signature": signature}


def _paraphrase_probe() -> dict[str, object]:
    return {
        "proposal_id": "cg3.non_new.tax_support",
        "raw_text": "household tax support changes the tax slot with the same do-query.",
        "signature": {
            "op": "tax_support_rate",
            "target": ["global.tax_rate"],
            "sign": "decrease",
            "params": {"rate": 0.1},
            "x_do": {"rate": 0.1},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": ["tax_support_rate", "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": {
                "NL": {
                    "op": "tax_support_rate",
                    "target": "global.tax_rate",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                },
                "do_AST": {"op": "tax_support_rate", "target": "global.tax_rate"},
            },
        },
    }


def _unregistered_tax_mimic_probe() -> dict[str, object]:
    return {
        "proposal_id": "cg3.non_new.tax_relief_rate_adjustment",
        "raw_text": "tax relief rate adjustment lowers the global tax-rate setting.",
        "signature": {
            "op": "tax relief rate adjustment",
            "target": ["global.tax_rate"],
            "sign": "decrease",
            "params": {"rate": 0.1},
            "x_do": {"rate": 0.1},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": [
                "tax relief rate adjustment",
                "global.tax_rate",
                "government.balance",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="tax relief rate adjustment",
                target="global.tax_rate",
                outcome="government.balance",
                do_value={"rate": 0.1},
            ),
        },
    }


def _compatibility_derived_alias_probe() -> dict[str, object]:
    probe = _novel_transfer_probe()
    signature = dict(probe["signature"])  # type: ignore[index]
    signature.update(
        {
            "op": "transfer_relief_support_rate_alias",
            "sign": "decrease",
            "params": {"rate": 0.2},
            "x_do": {"rate": 0.2},
            "modal_claims": _modal_claims(
                op="transfer_relief_support_rate_alias",
                target="household_cells.transfer_intensity",
                outcome="household_cells.disposable_income",
                do_value={"rate": 0.2},
            ),
        }
    )
    return {
        **probe,
        "proposal_id": "cg3.non_new.compatibility_derived_transfer_alias",
        "signature": signature,
    }


def _outcome_like_policy_map_probe() -> dict[str, object]:
    probe = _novel_transfer_probe()
    signature = dict(probe["signature"])  # type: ignore[index]
    signature.update(
        {
            "op": "direct_disposable_income_control",
            "target": ["household_cells.disposable_income"],
            "params": {"amount": 100.0},
            "x_do": {"amount": 100.0},
            "unit": "usd",
            "outcome": ["government.balance"],
            "effect_path": [
                "direct_disposable_income_control",
                "household_cells.disposable_income",
                "government.balance",
            ],
            "modal_claims": _modal_claims(
                op="direct_disposable_income_control",
                target="household_cells.disposable_income",
                outcome="government.balance",
                do_value={"amount": 100.0},
            ),
        }
    )
    return {**probe, "proposal_id": "cg3.acquire.outcome_like_policy_map", "signature": signature}


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
        "do_AST": {
            "do_value": do_value,
            "op": op,
            "target": target,
        },
    }
