from __future__ import annotations

import pytest

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_SCHEMA_VERSION,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
)
from polisyos.runtime.quality.grounding_relation import (
    AxisEntailmentWitness,
    AxisWitnessProvider,
    GroundingEnginePolicy,
    GroundingRelationEngine,
)


class AlwaysSupportsWitnessProvider:
    def witness_axis(
        self,
        *,
        axis: str,
        proposal_value: object,
        atom_value: object,
    ) -> AxisEntailmentWitness:
        return AxisEntailmentWitness(
            axis=axis,
            label="supports",
            confidence=0.99,
            witness="unit-test GY-K witness; relation must still be solver/CSP owned",
            source="GY-K.unit",
        )


def test_synonym_alias_resolves_without_surface_exact_match() -> None:
    engine = _engine()
    cert = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="unit-synonym")

    assert cert.solver_status == "SAT"
    assert cert.selected_relation == "exact"
    assert cert.recommended_transition == "shadow"
    assert cert.axis_witnesses
    assert _axis_relations(cert)["op"] == "equivalent"
    assert _axis_relations(cert)["target"] == "equivalent"


def test_concrete_alias_is_certified_specialization() -> None:
    cert = _engine().certificate_for(_synonym_probe(), proposal_id="unit-specialization")

    assert cert.solver_status == "SAT"
    assert cert.selected_relation == "certified-specialization"
    assert cert.residual_constraints
    assert _axis_relations(cert)["params"] == "narrower"


def test_false_analog_is_vetoed_not_bound() -> None:
    cert = _engine().certificate_for(_false_analog_probe(), proposal_id="unit-false")

    assert cert.solver_status == "SAT"
    assert cert.selected_relation == "novel-candidate"
    assert cert.recommended_transition == "handoff_RT3"
    assert "target" in cert.critical_contradictions
    assert any(
        result["selected_relation"] == "false-analog"
        for result in cert.relation_set["candidate_results"]
    )


def test_joint_cross_modal_inconsistency_blocks_with_unsat_core() -> None:
    cert = _engine().certificate_for(_greedy_inconsistent_probe(), proposal_id="unit-greedy")

    assert cert.selected_relation == "blocked"
    assert cert.solver_status == "UNSAT"
    assert cert.unsat_core_if_any
    assert any("budget_law" in item for item in cert.unsat_core_if_any)
    assert any(
        "knob_maps_to(tax_relief_rate, government.balance)" in item
        for item in cert.unsat_core_if_any
    )


def test_gy_k_witness_does_not_decide_relation() -> None:
    provider: AxisWitnessProvider = AlwaysSupportsWitnessProvider()
    cert = GroundingRelationEngine(
        _reference(),
        axis_witness_provider=provider,
    ).certificate_for(_false_analog_probe(), proposal_id="unit-gyk")

    assert cert.selected_relation == "novel-candidate"
    assert sum(1 for witness in cert.axis_witnesses if witness.gy_k_witness) > 0


def test_unknown_unresolved_axis_does_not_over_veto_or_block() -> None:
    cert = _engine().certificate_for(_unknown_probe(), proposal_id="unit-unknown")

    assert cert.solver_status == "SAT"
    assert cert.selected_relation == "unknown"
    assert cert.recommended_transition == "shadow"
    assert "target" in cert.unresolved_axes
    assert not cert.critical_contradictions


def test_shadow_only_contract_rejects_bind_recommendation() -> None:
    engine = GroundingRelationEngine(
        _reference(),
        policy=GroundingEnginePolicy(allow_bind_recommendations=True),
    )

    with pytest.raises(ValueError, match="recommended_transition"):
        engine.certificate_for(
            _pure_synonym_probe(engine),
            proposal_id="unit-bind-forbidden",
        )


def test_certificate_is_deterministic_for_same_reference_epoch() -> None:
    engine = _engine()
    first = engine.certificate_for(
        _pure_synonym_probe(engine),
        proposal_id="unit-deterministic",
    )
    second = engine.certificate_for(
        _pure_synonym_probe(engine),
        proposal_id="unit-deterministic",
    )

    assert first.content_hash == second.content_hash
    assert first.certificate_id == second.certificate_id


def test_alias_resolution_is_the_decisive_contract_property() -> None:
    engine = GroundingRelationEngine(
        _reference(),
        policy=GroundingEnginePolicy(disable_alias_resolution=True),
    )
    cert = engine.certificate_for(_pure_synonym_probe(_engine()), proposal_id="unit-alias-disabled")

    assert cert.selected_relation != "exact"


def _engine() -> GroundingRelationEngine:
    return GroundingRelationEngine(_reference())


def _reference() -> CredalReference:
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
    edge_index = {edge.key: edge for edge in edges}
    reference_hash = gy_content_hash(
        {
            "component_versions": {
                "L2": "unit-l2",
                "L3": "unit-l3",
                "L6": "unit-l6",
                "WMR": "unit-wmr",
            },
            "edges": [edge.to_payload() for edge in sorted(edges, key=lambda item: item.key)],
        }
    )
    return CredalReference(
        schema_version=CREDAL_REFERENCE_SCHEMA_VERSION,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of="2026-06-29",
        component_versions={
            "L2": "unit-l2",
            "L3": "unit-l3",
            "L6": "unit-l6",
            "WMR": "unit-wmr",
        },
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
            AdmissibleCompletion(
                "fixed",
                {"world_slot": slot},
                "unit_test_wmr_slot",
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
                "unit_test_policy_slot",
            ),
        ),
        provenance={"owner": "WMR", "source": "unit"},
    ).with_content_hash()


def _synonym_probe() -> dict[str, object]:
    return {
        "raw_text": "tax credit rate alias lowers tax burden by 8 percent.",
        "signature": {
            "op": "tax_credit_rate",
            "target": ["global.tax_rate"],
            "sign": "decrease",
            "params": {"rate": 0.08},
            "x_do": {"rate": 0.08},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": ["tax_credit_rate", "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "candidate_unverified",
            "modal_claims": {
                "NL": {
                    "op": "tax_credit_rate",
                    "target": "global.tax_rate",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                },
                "L6": {"knob": "tax_relief_rate"},
                "do_AST": {"op": "tax_credit_rate", "target": "global.tax_rate"},
                "method": {
                    "treatment_op": "tax_credit_rate",
                    "treatment_target": "global.tax_rate",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                },
            },
        },
    }


def _pure_synonym_probe(engine: GroundingRelationEngine) -> dict[str, object]:
    atom = next(
        item
        for item in engine.reference_atoms
        if item.signature.op == "tax_relief_rate" and "global.tax_rate" in item.signature.X_do
    )
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
        "raw_text": "household tax credit-like transfer near fiscal relief text",
        "signature": {
            "op": "household_transfer",
            "target": ["household_cells.disposable_income"],
            "sign": "increase",
            "params": {"rate": 0.08},
            "x_do": {"rate": 0.08},
            "scope": "households",
            "population": "households",
            "unit": "usd",
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "household_transfer",
                "household_cells.disposable_income",
                "household_cells.disposable_income",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "candidate_unverified",
            "modal_claims": {
                "NL": {
                    "op": "household_transfer",
                    "target": "household_cells.disposable_income",
                    "outcome": "household_cells.disposable_income",
                    "estimand": "average_treatment_effect",
                }
            },
        },
    }


def _greedy_inconsistent_probe() -> dict[str, object]:
    return {
        "raw_text": "corporate tax credit with household-threshold budget law",
        "signature": {
            "op": "tax_relief_rate",
            "target": ["government.balance"],
            "sign": "decrease",
            "params": {"rate": 0.08},
            "x_do": {"rate": 0.08},
            "scope": "global",
            "population": "all",
            "unit": "usd",
            "outcome": ["government.balance"],
            "effect_path": ["tax_relief_rate", "government.balance", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "candidate_unverified",
            "modal_claims": {
                "NL": {
                    "op": "tax_relief_rate",
                    "target": "government.balance",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                },
                "L3": {"law_token": "budget_law"},
                "L6": {"knob": "tax_relief_rate"},
                "do_AST": {"op": "tax_relief_rate", "target": "government.balance"},
                "method": {
                    "treatment_op": "tax_relief_rate",
                    "treatment_target": "government.balance",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                },
            },
        },
    }


def _unknown_probe() -> dict[str, object]:
    return {
        "raw_text": "tax-credit-like support program with unresolved do target",
        "signature": {
            "op": None,
            "target": [],
            "sign": None,
            "params": {},
            "x_do": {},
            "outcome": [],
            "effect_path": [],
            "estimand": None,
            "admissibility": "candidate_unverified",
            "modal_claims": {"NL": {"op": "", "target": "", "outcome": ""}},
        },
    }


def _axis_relations(certificate: object) -> dict[str, str]:
    return {witness.axis: witness.relation for witness in certificate.axis_witnesses}
