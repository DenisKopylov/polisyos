from __future__ import annotations

import json
from collections import UserDict
from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType

import pytest

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import credal_reference as credal_owner
from polisyos.runtime.quality import grounding_relation as grounding_owner
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
)
from polisyos.runtime.quality.grounding_relation import (
    AxisEntailmentWitness,
    AxisWitnessProvider,
    CandidateRelationResult,
    GroundingCandidateAtom,
    GroundingEnginePolicy,
    GroundingRelationEngine,
    HypothesisSolverAttempt,
    MechanisticSignature,
    ParsedProposal,
    SolverStatus,
    _aggregate_solver_status,
    _DuckDbReferenceFtsIndex,
    _rank_candidate_results,
    _SolverResult,
    grounding_candidate_semantic_sort_key,
    parse_n4_proposal,
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


def _record_cp_sat_parameters(monkeypatch):
    """Observe the parameters passed to the real CP-SAT solver."""
    from ortools.sat.python import cp_model

    real_solver = cp_model.CpSolver
    observed: list[tuple[int, float]] = []

    class RecordingSolver:
        def __init__(self) -> None:
            self._solver = real_solver()
            self.parameters = self._solver.parameters

        def Solve(self, model, solution_callback=None):  # noqa: N802 - OR-Tools API
            observed.append(
                (
                    self.parameters.num_search_workers,
                    self.parameters.max_time_in_seconds,
                )
            )
            return self._solver.Solve(model, solution_callback)

        def __getattr__(self, name: str):
            return getattr(self._solver, name)

    monkeypatch.setattr(cp_model, "CpSolver", RecordingSolver)
    return observed


def test_synonym_alias_resolves_without_surface_exact_match(monkeypatch) -> None:
    from polisyos.common.config import build_process_bootstrap_config

    observed = _record_cp_sat_parameters(monkeypatch)
    engine = _engine()
    cert = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="unit-synonym")

    assert cert.solver_status == "SAT"
    assert cert.selected_relation == "exact"
    assert cert.recommended_transition == "shadow"
    assert cert.axis_witnesses
    assert _axis_relations(cert)["op"] == "equivalent"
    assert _axis_relations(cert)["target"] == "equivalent"
    expected_workers = build_process_bootstrap_config().cp_sat_num_search_workers
    assert observed
    assert all(workers == expected_workers == 1 for workers, _ in observed)
    assert all(timeout == 5.0 for _, timeout in observed)


def test_cp_sat_unknown_remains_unknown_under_worker_budget(monkeypatch) -> None:
    from ortools.sat.python import cp_model

    from polisyos.common.config import build_process_bootstrap_config

    real_solver = cp_model.CpSolver
    observed: list[tuple[int, float]] = []

    class UnknownSolver:
        def __init__(self) -> None:
            self._solver = real_solver()
            self.parameters = self._solver.parameters

        def Solve(self, model, solution_callback=None):  # noqa: N802 - OR-Tools API
            del model, solution_callback
            observed.append(
                (
                    self.parameters.num_search_workers,
                    self.parameters.max_time_in_seconds,
                )
            )
            return cp_model.UNKNOWN

        def __getattr__(self, name: str):
            return getattr(self._solver, name)

    monkeypatch.setattr(cp_model, "CpSolver", UnknownSolver)
    engine = _engine()
    proposal = parse_n4_proposal(
        _pure_synonym_probe(engine),
        proposal_id="unit-cp-sat-unknown",
        reference=engine.reference,
    )

    result = engine._solve_joint_cross_modal(proposal.hypotheses[0])

    expected_workers = build_process_bootstrap_config().cp_sat_num_search_workers
    assert result.status == "UNKNOWN"
    assert result.unsat_core == ("cp_sat_timeout_or_unknown",)
    assert result.cross_modal_witnesses is not None
    assert result.cross_modal_witnesses["solver"] == "ortools_cp_sat"
    assert observed == [(expected_workers, 5.0)]


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ((), "UNKNOWN"),
        (("UNSAT",), "UNSAT"),
        (("UNSAT", "UNSAT"), "UNSAT"),
        (("SAT",), "SAT"),
        (("SAT", "UNKNOWN"), "SAT"),
        (("UNSAT", "UNKNOWN"), "UNKNOWN"),
        (("UNKNOWN", "UNKNOWN"), "UNKNOWN"),
    ],
)
def test_hypothesis_solver_status_aggregation_is_existential_and_lossless(
    statuses: tuple[SolverStatus, ...], expected: SolverStatus
) -> None:
    attempts = tuple(
        HypothesisSolverAttempt(
            hypothesis_id=f"proposal:h{index}",
            solver="ortools_cp_sat",
            solver_status=status,
            native_status=f"native:{status}",
            unsat_core=(f"reason:{index}",) if status != "SAT" else (),
        )
        for index, status in enumerate(statuses)
    )

    assert _aggregate_solver_status(attempts) == expected
    assert tuple(attempt.hypothesis_id for attempt in attempts) == tuple(
        f"proposal:h{index}" for index in range(len(statuses))
    )
    assert tuple(attempt.solver_status for attempt in attempts) == statuses


def test_unknown_attempt_is_not_laundered_when_no_candidate_is_selected(monkeypatch) -> None:
    engine = _engine()
    observed_hypotheses: list[str] = []

    def unknown_attempt(hypothesis):
        observed_hypotheses.append(hypothesis.hypothesis_id)
        return _SolverResult(
            status="UNKNOWN",
            native_status="forced-unknown-removal-probe",
            unsat_core=("cp_sat_timeout_or_unknown",),
            cross_modal_witnesses={
                "solver": "ortools_cp_sat",
                "status": "forced-unknown-removal-probe",
            },
        )

    monkeypatch.setattr(engine, "_solve_joint_cross_modal", unknown_attempt)
    certificate = engine.certificate_for(_unknown_probe(), proposal_id="unit-unknown-removal")

    pair_results = certificate.relation_set["candidate_results"]
    assert certificate.solver_status == "UNKNOWN"
    assert certificate.selected_relation == "unknown"
    assert certificate.shadow_only is True
    assert certificate.no_bind_admit_promote is True
    assert observed_hypotheses == [attempt.hypothesis_id for attempt in certificate.solver_attempts]
    assert len(certificate.solver_attempts) == 1
    assert certificate.solver_attempts[0].solver_status == "UNKNOWN"
    assert certificate.solver_attempts[0].native_status == "forced-unknown-removal-probe"
    assert certificate.solver_attempts[0].unsat_core == ("cp_sat_timeout_or_unknown",)
    assert pair_results
    assert {row["solver_status"] for row in pair_results} == {"UNKNOWN"}
    assert any(row["unresolved_axes"] for row in pair_results)


@pytest.mark.parametrize(
    ("attempt_status", "expected_transition"),
    [("SAT", "shadow"), ("UNKNOWN", "quarantine")],
)
def test_empty_candidate_set_uses_the_actual_solver_attempt(
    monkeypatch, attempt_status: SolverStatus, expected_transition: str
) -> None:
    engine = _engine()
    monkeypatch.setattr(
        engine,
        "retrieve_candidates",
        lambda parsed, *, include_adversarial_countercandidates=True: (),
    )
    monkeypatch.setattr(
        engine,
        "_solve_joint_cross_modal",
        lambda hypothesis: _SolverResult(
            status=attempt_status,
            unsat_core=("cp_sat_timeout_or_unknown",) if attempt_status != "SAT" else (),
            cross_modal_witnesses={
                "solver": "ortools_cp_sat",
                "status": f"forced-{attempt_status.lower()}-empty-candidate-control",
            },
        ),
    )

    certificate = engine.certificate_for(_unknown_probe(), proposal_id="unit-empty-candidates")

    assert certificate.solver_status == attempt_status
    assert certificate.selected_relation == "unknown"
    assert certificate.recommended_transition == expected_transition
    assert certificate.candidate_atom_ids == ()
    assert certificate.relation_set["candidate_results"] == []
    assert len(certificate.solver_attempts) == 1
    assert certificate.solver_attempts[0].solver_status == attempt_status
    assert certificate.solver_attempts[0].unsat_core == (
        ("cp_sat_timeout_or_unknown",) if attempt_status != "SAT" else ()
    )


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


def test_joint_cross_modal_inconsistency_blocks_with_unsat_core(monkeypatch) -> None:
    from polisyos.common.config import build_process_bootstrap_config

    observed = _record_cp_sat_parameters(monkeypatch)
    cert = _engine().certificate_for(_greedy_inconsistent_probe(), proposal_id="unit-greedy")

    assert cert.selected_relation == "blocked"
    assert cert.solver_status == "UNSAT"
    assert cert.unsat_core_if_any
    assert any("budget_law" in item for item in cert.unsat_core_if_any)
    assert any(
        "knob_maps_to(tax_relief_rate, government.balance)" in item
        for item in cert.unsat_core_if_any
    )
    expected_workers = build_process_bootstrap_config().cp_sat_num_search_workers
    assert observed
    assert all(workers == expected_workers == 1 for workers, _ in observed)
    assert all(timeout == 5.0 for _, timeout in observed)


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


def test_certificate_identity_is_invariant_to_persisted_edge_mapping_order() -> None:
    reference = _reference()
    sorted_edges = dict(sorted(reference.essential_edges.items()))
    assert tuple(reference.essential_edges) != tuple(sorted_edges)
    reordered = replace(reference, essential_edges=sorted_edges)
    assert reordered == reference
    assert reordered.reference_hash == reference.reference_hash

    original_engine = GroundingRelationEngine(reference)
    proposal = _pure_synonym_probe(original_engine)
    original = original_engine.certificate_for(
        proposal,
        proposal_id="unit-persisted-edge-order",
    )
    reordered_certificate = GroundingRelationEngine(reordered).certificate_for(
        proposal,
        proposal_id="unit-persisted-edge-order",
    )

    assert reordered_certificate.candidate_atom_ids == original.candidate_atom_ids
    assert reordered_certificate.certificate_id == original.certificate_id
    assert reordered_certificate.content_hash == original.content_hash


def test_candidate_selection_is_invariant_to_content_id_readdressing() -> None:
    """WMR-only atom rehashes cannot select a different semantic witness."""

    budget = _tied_candidate(
        atom_id="cg0_atom_ffffffffffffffff",
        op="budget_allocation_multiplier",
        target="government.balance",
    )
    procurement = _tied_candidate(
        atom_id="cg0_atom_0000000000000000",
        op="procurement_shock_intensity",
        target="cells.distress_score",
    )
    readdressed_budget = budget.model_copy(update={"atom_id": "cg0_atom_0000000000000000"})
    readdressed_procurement = procurement.model_copy(
        update={"atom_id": "cg0_atom_ffffffffffffffff"}
    )

    first = _selected_tied_semantics((budget, procurement))
    readdressed = _selected_tied_semantics((readdressed_procurement, readdressed_budget))

    assert first == readdressed
    assert first == (
        "budget_allocation_multiplier",
        ("government.balance",),
        ("op", "sign", "effect_path"),
    )


def test_candidate_retrieval_order_is_invariant_to_content_id_readdressing() -> None:
    """Retrieval prioritization uses causal semantics after equal owner scores."""

    class _AllCandidateHits:
        indexed_edge_count = 2

        def search(self, query: str, *, limit: int) -> list[dict[str, str]]:
            del query, limit
            return [
                {"edge_key": "L6_KNOB_OPERATOR:budget_allocation_multiplier"},
                {"edge_key": "L6_KNOB_OPERATOR:procurement_shock_intensity"},
            ]

    budget = _tied_candidate(
        atom_id="cg0_atom_ffffffffffffffff",
        op="budget_allocation_multiplier",
        target="government.balance",
    )
    procurement = _tied_candidate(
        atom_id="cg0_atom_0000000000000000",
        op="procurement_shock_intensity",
        target="cells.distress_score",
    )
    engine = _engine()
    engine._reference_atoms = (procurement, budget)
    engine._fts_index = _AllCandidateHits()  # type: ignore[assignment]
    parsed = parse_n4_proposal(
        {"raw_text": "unregistered neutral probe", "signature": {}},
        proposal_id="unit-retrieval-readdress",
        reference=engine.reference,
    )

    retrieved = engine.retrieve_candidates(
        parsed,
        include_adversarial_countercandidates=False,
    )

    assert [candidate.signature.op for candidate in retrieved] == [
        "budget_allocation_multiplier",
        "procurement_shock_intensity",
    ]


def test_candidate_semantic_key_excludes_provenance_but_not_relation_axes() -> None:
    """The tie-break recomputes relation semantics without epoch identities."""

    candidate = _tied_candidate(
        atom_id="cg0_atom_0000000000000000",
        op="budget_allocation_multiplier",
        target="government.balance",
    )
    readdressed_signature = candidate.signature.model_copy(
        update={
            "evidence": ("WMR_WORLD_SLOT:reissued",),
            "wm_version": "sha256:" + "b" * 64,
        }
    )
    provenance_only = candidate.model_copy(
        update={
            "atom_id": "cg0_atom_ffffffffffffffff",
            "edge_scope": ("WMR_WORLD_SLOT:reissued",),
            "reference_lift": {"reissued": {"content_hash": "sha256:" + "c" * 64}},
            "retrieval_reasons": ("reissued_owner_evidence",),
            "signature": readdressed_signature,
        }
    )
    semantic_change = provenance_only.model_copy(
        update={"signature": readdressed_signature.model_copy(update={"unit": "index"})}
    )

    assert grounding_candidate_semantic_sort_key(candidate) == (
        grounding_candidate_semantic_sort_key(provenance_only)
    )
    assert grounding_candidate_semantic_sort_key(candidate) != (
        grounding_candidate_semantic_sort_key(semantic_change)
    )


def test_alias_resolution_is_the_decisive_contract_property() -> None:
    engine = GroundingRelationEngine(
        _reference(),
        policy=GroundingEnginePolicy(disable_alias_resolution=True),
    )
    cert = engine.certificate_for(_pure_synonym_probe(_engine()), proposal_id="unit-alias-disabled")

    assert cert.selected_relation != "exact"


def _engine() -> GroundingRelationEngine:
    return GroundingRelationEngine(_reference())


def _tied_candidate(
    *,
    atom_id: str,
    op: str,
    target: str,
) -> GroundingCandidateAtom:
    return GroundingCandidateAtom(
        atom_id=atom_id,
        signature=MechanisticSignature(
            op=op,
            X_do=(target,),
            sign="increase",
            outcome=(target,),
            effect_path=(op, target),
            estimand="average_treatment_effect",
            wm_version="sha256:" + "a" * 64,
            evidence=(f"L6_KNOB_OPERATOR:{op}",),
        ),
        edge_scope=(f"L6_KNOB_OPERATOR:{op}",),
        retrieved_as_neighbor=True,
        retrieval_reasons=("unit_equal_score",),
        retrieval_score=0.5,
    )


def _selected_tied_semantics(
    candidates: tuple[GroundingCandidateAtom, GroundingCandidateAtom],
) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
    results = tuple(
        CandidateRelationResult(
            hypothesis_id="hypothesis_unit",
            atom_id=candidate.atom_id,
            selected_relation="false-analog",
            solver_status="SAT",
            axis_witnesses=(),
            critical_contradictions=(
                ("op", "sign", "effect_path")
                if candidate.signature.op == "budget_allocation_multiplier"
                else ("op", "effect_path")
            ),
            retrieval_reasons=candidate.retrieval_reasons,
            retrieval_score=candidate.retrieval_score,
        )
        for candidate in candidates
    )
    candidate_by_id = {candidate.atom_id: candidate for candidate in candidates}
    ranked = _rank_candidate_results(results, candidate_by_id)
    selected = ranked[0]
    atom = candidate_by_id[selected.atom_id]
    return (
        atom.signature.op,
        atom.signature.X_do,
        selected.critical_contradictions,
    )


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
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
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


def _empty_hypothesis_proposal(raw_text: str) -> ParsedProposal:
    return ParsedProposal(
        proposal_id="unit-empty-hypothesis-proposal",
        raw_text=raw_text,
        raw_text_hash=gy_content_hash(raw_text),
        canonical_ast={"ast_kind": "unit_empty_hypothesis"},
        hypotheses=(),
    )


def _legacy_plain_json_value(value: object) -> object:
    """Restore pre-freeze JSON containers without calling production helpers."""

    if isinstance(value, Mapping):
        return {key: _legacy_plain_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_legacy_plain_json_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_legacy_plain_json_value(item) for item in value)
    return value


def _legacy_completion_payload(completion: AdmissibleCompletion) -> dict[str, object]:
    """Rebuild completion JSON from its source fields, without production helpers."""

    return {
        "completion_kind": completion.completion_kind,
        "reason": completion.reason,
        "value": _legacy_plain_json_value(completion.value),
    }


def _legacy_edge_search_text(edge: CredalReferenceEdge) -> str:
    """Build the prior FTS text from ordinary mapping/list JSON values."""

    return " ".join(
        (
            edge.modality,
            edge.edge_id,
            edge.status,
            edge.unit or "",
            json.dumps(
                [
                    _legacy_completion_payload(completion)
                    for completion in edge.admissible_completions
                ],
                sort_keys=True,
                default=str,
            ),
            json.dumps(
                _legacy_plain_json_value(edge.provenance),
                sort_keys=True,
                default=str,
            ),
        )
    )


def _legacy_fts_search(reference, query: str, limit: int) -> list[dict[str, object]]:
    """Keep the prior whole-frame DuckDB path as a small-fixture oracle."""
    import duckdb
    import pandas as pd

    docs = {"doc_id": [], "edge_id": [], "modality": [], "text": []}
    for edge in reference.essential_edges.values():
        docs["doc_id"].append(grounding_owner._edge_key_text(edge.key))
        docs["modality"].append(edge.modality)
        docs["edge_id"].append(edge.edge_id)
        docs["text"].append(_legacy_edge_search_text(edge))
    con = duckdb.connect(":memory:")
    try:
        con.register("cg0_reference_edge_rows", pd.DataFrame(docs))
        con.execute(
            """
            CREATE TABLE cg0_reference_edges AS
            SELECT doc_id, modality, edge_id, text FROM cg0_reference_edge_rows
            """
        )
        con.execute("PRAGMA create_fts_index('cg0_reference_edges', 'doc_id', 'text')")
        safe_query = " ".join(sorted(grounding_owner._tokens(query)))[:800]
        if not safe_query:
            return []
        rows = con.execute(
            """
            SELECT doc_id, modality, edge_id,
                   fts_main_cg0_reference_edges.match_bm25(doc_id, ?) AS score
            FROM cg0_reference_edges
            WHERE score IS NOT NULL
            ORDER BY score DESC, doc_id
            LIMIT ?
            """,
            [safe_query, int(limit)],
        ).fetchall()
        return [
            {
                "edge_key": grounding_owner._edge_key_text((str(row[1]), str(row[2]))),
                "score": float(row[3] or 0.0),
            }
            for row in rows
        ]
    finally:
        con.close()


def test_legacy_fts_corpus_reconstructs_completion_source_fields() -> None:
    """Every legal completion literal retains raw nested JSON FTS serialization."""

    raw_fixed_value = {
        "optional_signal": None,
        "nested": {"labels": ["fixed", None], "weight": 0.25},
    }
    raw_partial_value = {
        "optional_signal": {"owner": None},
        "nested": {"labels": ["partial", "candidate"], "weight": 0.75},
    }
    raw_provenance = {"source": None, "route": ["L3", "WMR"]}
    raw_completions = [
        {"completion_kind": "fixed", "reason": "unit-fixed", "value": raw_fixed_value},
        {
            "completion_kind": "alternative",
            "reason": "unit-alternative",
            "value": raw_partial_value,
        },
        {"completion_kind": "may_exist", "reason": "unit-may-exist", "value": raw_fixed_value},
        {
            "completion_kind": "may_not_exist",
            "reason": "unit-may-not-exist",
            "value": raw_partial_value,
        },
        {"completion_kind": "partial", "reason": "unit-partial", "value": raw_fixed_value},
        {"completion_kind": "excluded", "reason": "unit-excluded", "value": raw_partial_value},
    ]
    expected_text = " ".join(
        (
            "L6_KNOB_OPERATOR",
            "unit-source-fields",
            "confirmed",
            "",
            json.dumps(raw_completions, sort_keys=True, default=str),
            json.dumps(raw_provenance, sort_keys=True, default=str),
        )
    )
    edge = CredalReferenceEdge(
        modality="L6_KNOB_OPERATOR",
        edge_id="unit-source-fields",
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion("fixed", raw_fixed_value, "unit-fixed"),
            AdmissibleCompletion("alternative", raw_partial_value, "unit-alternative"),
            AdmissibleCompletion("may_exist", raw_fixed_value, "unit-may-exist"),
            AdmissibleCompletion("may_not_exist", raw_partial_value, "unit-may-not-exist"),
            AdmissibleCompletion("partial", raw_fixed_value, "unit-partial"),
            AdmissibleCompletion("excluded", raw_partial_value, "unit-excluded"),
        ),
        provenance=raw_provenance,
    )
    raw_fixed_value["nested"]["labels"].append("caller-mutation")
    raw_partial_value["nested"]["labels"].append("caller-mutation")
    raw_provenance["route"].append("caller-mutation")

    assert grounding_owner._edge_search_text(edge) == expected_text
    assert _legacy_edge_search_text(edge) == expected_text


def test_batched_fts_index_preserves_full_edge_set_and_legacy_results(monkeypatch) -> None:
    monkeypatch.setattr(grounding_owner, "_REFERENCE_FTS_INSERT_BATCH_SIZE", 2)
    reference = _reference()
    index = _DuckDbReferenceFtsIndex(reference)

    hits = index.search("tax_relief_rate", limit=80)

    assert hits
    assert index.reference_edge_set_complete is True
    assert index.indexed_edge_count == len(reference.essential_edges)
    assert index._con is not None
    actual_documents = [
        (str(row[0]), str(row[1]))
        for row in index._con.execute(
            "SELECT doc_id, text FROM cg0_reference_edges ORDER BY doc_id"
        ).fetchall()
    ]
    expected_documents = sorted(
        (
            grounding_owner._edge_key_text(edge.key),
            _legacy_edge_search_text(edge),
        )
        for edge in reference.essential_edges.values()
    )
    assert actual_documents == expected_documents
    assert [doc_id for doc_id, _text in actual_documents] == sorted(
        grounding_owner._edge_key_text(edge.key) for edge in reference.essential_edges.values()
    )
    assert hits == _legacy_fts_search(reference, "tax_relief_rate", limit=80)


def test_fts_text_preserves_legacy_nested_mapping_json() -> None:
    """A frozen mapping retains the exact text the old JSON path emitted."""

    original_edge = next(iter(_reference().essential_edges.values()))
    raw_provenance = {
        "owner": "L2",
        "signals": {"empty": None, "status": True},
    }
    expected_provenance = json.dumps(raw_provenance, sort_keys=True, default=str)
    edge = replace(original_edge, provenance=raw_provenance)
    expected = " ".join(
        (
            edge.modality,
            edge.edge_id,
            edge.status,
            edge.unit or "",
            json.dumps(
                [completion.to_payload() for completion in edge.admissible_completions],
                sort_keys=True,
                default=str,
            ),
            expected_provenance,
        )
    )

    actual = grounding_owner._edge_search_text(edge)
    assert actual == expected
    assert "mappingproxy" not in actual


def test_fts_text_preserves_generic_mapping_default_str_wire_and_captured_identity() -> None:
    """The FTS corpus matches old JSON fallback for generic Mapping implementations."""

    raw_completion_data = {"owner": "completion-before", "status": True}
    raw_completion = UserDict(raw_completion_data)
    raw_provenance_data = {"owner": "provenance-before", "status": True}
    raw_provenance = MappingProxyType(raw_provenance_data)
    expected_completion_value = json.loads(
        json.dumps(raw_completion, ensure_ascii=False, sort_keys=True, default=str)
    )
    expected_provenance_value = json.loads(
        json.dumps(raw_provenance, ensure_ascii=False, sort_keys=True, default=str)
    )
    original_edge = next(iter(_reference().essential_edges.values()))
    completion = AdmissibleCompletion(
        "fixed",
        raw_completion,
        "generic mapping serializer discriminator",
    )
    edge = replace(
        original_edge,
        edge_id="generic-mapping-wire-edge",
        admissible_completions=(completion,),
        provenance=raw_provenance,
    ).with_content_hash()
    expected_text = " ".join(
        (
            edge.modality,
            edge.edge_id,
            edge.status,
            edge.unit or "",
            json.dumps(
                [
                    {
                        "completion_kind": "fixed",
                        "reason": "generic mapping serializer discriminator",
                        "value": expected_completion_value,
                    }
                ],
                sort_keys=True,
                default=str,
            ),
            json.dumps(raw_provenance, sort_keys=True, default=str),
        )
    )

    assert edge.to_payload()["admissible_completions"][0]["value"] == expected_completion_value
    assert edge.to_payload()["provenance"] == expected_provenance_value
    assert grounding_owner._edge_search_text(edge) == expected_text
    captured_hash = edge.content_hash

    raw_completion_data["owner"] = "completion-after"
    raw_provenance_data["owner"] = "provenance-after"

    assert edge.content_hash == captured_hash
    assert edge.to_payload()["admissible_completions"][0]["value"] == expected_completion_value
    assert edge.to_payload()["provenance"] == expected_provenance_value
    assert grounding_owner._edge_search_text(edge) == expected_text


@pytest.mark.parametrize("raw_text", ["", "!!!"])
def test_cold_empty_or_tokenless_query_does_not_claim_index_coverage(raw_text: str) -> None:
    engine = _engine()
    parsed = _empty_hypothesis_proposal(raw_text)
    candidates = engine.retrieve_candidates(parsed, include_adversarial_countercandidates=False)

    assert engine._fts_index is not None
    assert engine._fts_index._con is None
    assert engine._fts_index.indexed_edge_count == 0
    assert engine._fts_index.reference_edge_set_complete is False
    assert len(candidates) == 1

    certificate = engine._certificate_for_parsed(parsed, candidates)
    coverage = certificate.relation_set["known_space_coverage"]
    assert certificate.selected_relation == "unknown"
    assert certificate.solver_status == "UNKNOWN"
    assert certificate.shadow_only is True
    assert certificate.no_bind_admit_promote is True
    assert coverage["retrieval_indexed_edge_count"] == 0
    assert coverage["atom_universe_count"] > coverage["base_candidate_count"]
    assert coverage["coverage_sufficient"] is False


def test_fts_text_captures_mutable_bytes_fallback_before_hash_and_cache_use() -> None:
    """A bytes subclass cannot revise selected JSON or FTS text after capture."""

    class MutableBytesFallback(bytes):
        display: str

        def __new__(cls, value: bytes, display: str) -> MutableBytesFallback:
            instance = super().__new__(cls, value)
            instance.display = display
            return instance

        def __str__(self) -> str:
            return self.display

    source_value = MutableBytesFallback(b"owner-bytes", "owner-bytes-before")
    raw_provenance = {"owner-fallback": source_value}
    original_edge = next(iter(_reference().essential_edges.values()))
    expected_text = " ".join(
        (
            original_edge.modality,
            "mutable-bytes-fallback-edge",
            original_edge.status,
            original_edge.unit or "",
            json.dumps(
                [
                    {
                        "completion_kind": completion.completion_kind,
                        "reason": completion.reason,
                        "value": _legacy_plain_json_value(completion.value),
                    }
                    for completion in original_edge.admissible_completions
                ],
                sort_keys=True,
                default=str,
            ),
            json.dumps(raw_provenance, sort_keys=True, default=str),
        )
    )
    edge = replace(
        original_edge,
        edge_id="mutable-bytes-fallback-edge",
        provenance=raw_provenance,
    ).with_content_hash()
    captured_hash = edge.content_hash

    assert grounding_owner._edge_search_text(edge) == expected_text
    source_value.display = "owner-bytes-after"

    assert edge.to_payload()["provenance"] == {"owner-fallback": "owner-bytes-before"}
    assert edge.content_hash == captured_hash
    assert grounding_owner._edge_search_text(edge) == expected_text


def test_zero_hit_query_can_claim_coverage_only_after_full_index_build() -> None:
    engine = _engine()
    query = "qzxvlymno"
    parsed = _empty_hypothesis_proposal(query)
    candidates = engine.retrieve_candidates(parsed, include_adversarial_countercandidates=False)

    assert engine._fts_index is not None
    assert engine._fts_index.reference_edge_set_complete is True
    assert engine._fts_index.indexed_edge_count == len(engine.reference.essential_edges)
    assert engine._fts_index.search(query, limit=80) == []
    assert len(candidates) == 1
    assert candidates[0].atom_id == engine.reference_atoms[0].atom_id
    assert candidates[0].retrieval_reasons == ("coverage_floor_full_reference_seen",)

    certificate = engine._certificate_for_parsed(parsed, candidates)
    coverage = certificate.relation_set["known_space_coverage"]
    assert certificate.selected_relation == "unknown"
    assert coverage["retrieval_indexed_edge_count"] == len(engine.reference.essential_edges)
    assert coverage["coverage_sufficient"] is True


@pytest.mark.parametrize("mutation", ["missing_row", "duplicate_row"])
def test_incomplete_fts_document_set_fails_coverage_with_source_count_unchanged(
    mutation: str,
    monkeypatch,
) -> None:
    reference = _reference()
    original_batches = grounding_owner._iter_reference_fts_document_batches

    def changed_batches(selected_reference):
        rows = [row for batch in original_batches(selected_reference) for row in batch]
        if mutation == "missing_row":
            rows.pop()
        else:
            rows[-1] = rows[0]
        batch_size = grounding_owner._REFERENCE_FTS_INSERT_BATCH_SIZE
        for offset in range(0, len(rows), batch_size):
            yield rows[offset : offset + batch_size]

    monkeypatch.setattr(grounding_owner, "_iter_reference_fts_document_batches", changed_batches)
    engine = GroundingRelationEngine(reference)
    parsed = _empty_hypothesis_proposal("token-absent-from-every-source-edge")
    candidates = engine.retrieve_candidates(parsed, include_adversarial_countercandidates=False)

    assert engine._fts_index is not None
    assert len(reference.essential_edges) > 0
    assert engine._fts_index.reference_edge_set_complete is False
    assert engine._fts_index._con is not None
    actual_count, distinct_count = engine._fts_index._con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT doc_id) FROM cg0_reference_edges"
    ).fetchone()
    expected_actual_count = (
        len(reference.essential_edges) - 1
        if mutation == "missing_row"
        else len(reference.essential_edges)
    )
    assert actual_count == expected_actual_count
    assert distinct_count == len(reference.essential_edges) - 1
    assert candidates

    certificate = engine._certificate_for_parsed(parsed, candidates)
    coverage = certificate.relation_set["known_space_coverage"]
    assert coverage["reference_edge_count"] == len(reference.essential_edges)
    assert coverage["retrieval_indexed_edge_count"] == actual_count
    assert coverage["coverage_sufficient"] is False


@pytest.mark.parametrize("mutation", ["foreign_id", "duplicate_id"])
def test_atom_count_alone_does_not_establish_the_full_candidate_universe(
    mutation: str,
) -> None:
    engine = _engine()
    parsed = _empty_hypothesis_proposal("")
    atoms = engine.reference_atoms
    if mutation == "foreign_id":
        candidates = (
            *atoms[:-1],
            atoms[-1].model_copy(update={"atom_id": "cg0_atom_ffffffffffffffff"}),
        )
    else:
        candidates = (*atoms[:-1], atoms[0])
    certificate = engine._certificate_for_parsed(parsed, candidates)
    coverage = certificate.relation_set["known_space_coverage"]

    assert len(candidates) == len(atoms)
    assert coverage["atom_universe_count"] == len(atoms)
    assert coverage["retrieval_indexed_edge_count"] == 0
    assert coverage["coverage_sufficient"] is False


def test_coverage_summary_reuses_the_engine_reference_basis(monkeypatch) -> None:
    real_atom_builder = grounding_owner._reference_atoms_from_cg0
    real_slot_reader = grounding_owner._writable_wmr_slots
    atom_builds = 0
    slot_reads = 0

    def record_atom_build(
        reference: CredalReference,
        *,
        writable_slots: tuple[str, ...] | None = None,
    ) -> list[GroundingCandidateAtom]:
        nonlocal atom_builds
        atom_builds += 1
        return real_atom_builder(reference, writable_slots=writable_slots)

    def record_slot_read(reference):
        nonlocal slot_reads
        slot_reads += 1
        return real_slot_reader(reference)

    monkeypatch.setattr(grounding_owner, "_reference_atoms_from_cg0", record_atom_build)
    monkeypatch.setattr(grounding_owner, "_writable_wmr_slots", record_slot_read)
    engine = _engine()
    certificates = (
        engine.certificate_for(_pure_synonym_probe(engine), proposal_id="unit-summary-exact"),
        engine.certificate_for(_false_analog_probe(), proposal_id="unit-summary-novel"),
    )
    coverage = [certificate.relation_set["known_space_coverage"] for certificate in certificates]

    assert atom_builds == 1
    assert slot_reads == 1
    assert [certificate.selected_relation for certificate in certificates] == [
        "exact",
        "novel-candidate",
    ]
    assert all(certificate.solver_status == "SAT" for certificate in certificates)
    assert all(certificate.shadow_only for certificate in certificates)
    assert all(certificate.no_bind_admit_promote for certificate in certificates)
    assert len({item["atom_universe_count"] for item in coverage}) == 1
    assert all(item["atom_universe_count"] == len(engine.reference_atoms) for item in coverage)
    assert all(item["registered_operator_count"] == 2 for item in coverage)
    assert all(item["writable_wmr_slot_count"] == 3 for item in coverage)
    assert all(item["coverage_sufficient"] is True for item in coverage)
    assert engine._fts_index is not None
    assert engine._fts_index.reference_edge_set_complete is True


def test_reference_coverage_caches_are_scoped_to_epoch_and_component_versions() -> None:
    reference = _reference()
    component_versions = dict(reference.component_versions)
    component_versions.update(
        {
            "L2": "unit-l2-reissued",
            "L3": "unit-l3-reissued",
            "WMR": "unit-wmr-reissued",
        }
    )
    as_of = "2026-06-30"
    reference_hash = credal_owner._reference_hash(
        component_versions=component_versions,
        edge_index=reference.essential_edges,
        as_of=as_of,
        schema_version=reference.schema_version,
    )
    reissued_reference = CredalReference(
        schema_version=reference.schema_version,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of=as_of,
        component_versions=component_versions,
        essential_edges=reference.essential_edges,
    )
    current_engine = GroundingRelationEngine(reference)
    reissued_engine = GroundingRelationEngine(reissued_reference)
    current_basis = current_engine._reference_coverage_basis()
    reissued_basis = reissued_engine._reference_coverage_basis()
    proposal = _empty_hypothesis_proposal("tax_relief_rate")
    current_candidates = current_engine.retrieve_candidates(
        proposal,
        include_adversarial_countercandidates=False,
    )
    reissued_candidates = reissued_engine.retrieve_candidates(
        proposal,
        include_adversarial_countercandidates=False,
    )
    current_certificate = current_engine._certificate_for_parsed(proposal, current_candidates)
    reissued_certificate = reissued_engine._certificate_for_parsed(proposal, reissued_candidates)

    assert reference.reference_hash != reissued_reference.reference_hash
    assert reference.as_of != reissued_reference.as_of
    assert current_basis is not reissued_basis
    assert current_basis.atom_ids != reissued_basis.atom_ids
    assert current_engine._reference_atoms is not reissued_engine._reference_atoms
    assert current_engine._fts_index is not None
    assert reissued_engine._fts_index is not None
    assert current_engine._fts_index is not reissued_engine._fts_index
    assert current_engine._fts_index._con is not reissued_engine._fts_index._con
    assert current_engine._fts_index.reference_edge_set_complete is True
    assert reissued_engine._fts_index.reference_edge_set_complete is True
    assert current_engine._fts_index.search("tax_relief_rate", limit=80) == (
        reissued_engine._fts_index.search("tax_relief_rate", limit=80)
    )
    assert current_certificate.candidate_atom_ids != reissued_certificate.candidate_atom_ids
    assert current_certificate.relation_set["known_space_coverage"]["coverage_sufficient"] is True
    assert reissued_certificate.relation_set["known_space_coverage"]["coverage_sufficient"] is True


def test_engine_caches_remain_bound_to_same_cardinality_reference_capture() -> None:
    """Warm basis caches cannot drift when caller-owned source maps are changed."""

    original = _reference()
    source_edges = dict(original.essential_edges)
    source_versions = dict(original.component_versions)
    captured = replace(
        original,
        component_versions=source_versions,
        essential_edges=source_edges,
    )
    engine = GroundingRelationEngine(captured)
    atoms = engine.reference_atoms
    coverage_basis = engine._reference_coverage_basis()
    source_key = next(iter(source_edges))
    original_edge = source_edges[source_key]
    source_edges[source_key] = replace(original_edge, content_hash=f"sha256:{'f' * 64}")
    source_versions["WMR"] = "caller-reissued-without-new-reference"

    assert len(source_edges) == len(captured.essential_edges)
    assert engine.reference_atoms is atoms
    assert engine._reference_coverage_basis() is coverage_basis
    assert engine.reference.essential_edges[source_key] is original_edge
    assert engine.reference.component_versions["WMR"] == "unit-wmr"


def test_engine_and_fts_reference_bindings_reject_same_size_rebinding() -> None:
    """Warm caches and FTS rows remain tied to one immutable reference capture."""

    original = _reference()
    engine = GroundingRelationEngine(original)
    atoms = engine.reference_atoms
    coverage_basis = engine._reference_coverage_basis()
    parsed = _empty_hypothesis_proposal("tax relief rate")
    engine.retrieve_candidates(parsed, include_adversarial_countercandidates=False)
    index = engine._fts_index
    assert isinstance(index, _DuckDbReferenceFtsIndex)
    assert index.reference_edge_set_complete is True
    assert index.indexed_edge_count == len(original.essential_edges)

    source_key, selected_edge = next(iter(original.essential_edges.items()))
    changed_edge = replace(
        selected_edge,
        provenance={**dict(selected_edge.provenance), "rebind_probe": "changed"},
        content_hash="",
    )
    replacement = credal_owner.replace_reference_edge(original, changed_edge)
    assert len(replacement.essential_edges) == len(original.essential_edges)
    assert replacement.reference_epoch != original.reference_epoch
    assert replacement.essential_edges[source_key].provenance["rebind_probe"] == "changed"

    reference_attribute = "reference"
    with pytest.raises(AttributeError):
        setattr(engine, reference_attribute, replacement)
    with pytest.raises(AttributeError):
        setattr(index, reference_attribute, replacement)

    assert engine.reference is original
    assert engine.reference_atoms is atoms
    assert engine._reference_coverage_basis() is coverage_basis
    assert index.reference is original
    assert index.reference_edge_set_complete is True
    assert index.indexed_edge_count == len(original.essential_edges)


def test_installed_no_lexical_indexes_report_zero_incomplete_retrieval() -> None:
    """Bounded wrappers satisfy the shared protocol without claiming FTS rows."""

    from polisyos.runtime.quality.grounding_active_controller import (
        _NoLexicalReferenceIndex,
    )
    from polisyos.runtime.quality.grounding_phrasing_defense import (
        _BoundedReferenceIndex,
    )

    reference = _reference()
    parsed = parse_n4_proposal(
        {"raw_text": "unregistered neutral probe", "signature": {}},
        proposal_id="unit-no-lexical-index-protocol",
        reference=reference,
    )
    for index_type in (_NoLexicalReferenceIndex, _BoundedReferenceIndex):
        engine = GroundingRelationEngine(reference)
        index = index_type(reference)
        engine._fts_index = index

        assert index.indexed_edge_count == 0
        assert index.reference_edge_set_complete is False
        assert index.search("unregistered probe", limit=5) == []
        certificate = engine._certificate_for_parsed(parsed, ())
        coverage = certificate.relation_set["known_space_coverage"]
        assert coverage["retrieval_indexed_edge_count"] == 0
        assert coverage["coverage_sufficient"] is False


def test_fts_hash_and_lookup_share_one_stateful_fallback_capture() -> None:
    """Hashing, FTS, and direct lookups consume one captured fallback value."""

    class StatefulFallback:
        def __init__(self, label: str, calls: list[str]) -> None:
            self.label = label
            self.calls = calls

        def __str__(self) -> str:
            self.calls.append(self.label)
            return f"{self.label}-{len(self.calls)}"

    expected_calls: list[str] = []
    expected_completion_value = json.loads(
        json.dumps({"opaque": StatefulFallback("completion", expected_calls)}, default=str)
    )
    expected_provenance = json.loads(
        json.dumps({"opaque": StatefulFallback("provenance", expected_calls)}, default=str)
    )
    assert expected_calls == ["completion", "provenance"]

    actual_calls: list[str] = []
    completion = AdmissibleCompletion(
        "fixed",
        {"opaque": StatefulFallback("completion", actual_calls)},
        "single-capture probe",
    )
    edge = CredalReferenceEdge(
        modality="L2_CAUSAL_EDGE",
        edge_id="single-capture-stateful-fallback",
        status="confirmed",
        admissible_completions=(completion,),
        provenance={"opaque": StatefulFallback("provenance", actual_calls)},
    ).with_content_hash()

    expected_completion = {
        "completion_kind": "fixed",
        "reason": "single-capture probe",
        "value": expected_completion_value,
    }
    expected_hash = gy_content_hash(
        {
            "admissible_completions": [expected_completion],
            "edge_id": edge.edge_id,
            "modality": edge.modality,
            "provenance": expected_provenance,
            "scale": None,
            "status": edge.status,
            "unit": edge.unit,
        }
    )
    expected_fts_text = " ".join(
        (
            edge.modality,
            edge.edge_id,
            edge.status,
            edge.unit or "",
            json.dumps([expected_completion], sort_keys=True, default=str),
            json.dumps(expected_provenance, sort_keys=True, default=str),
        )
    )

    assert edge.content_hash == expected_hash
    assert completion.value["opaque"] == expected_completion_value["opaque"]
    assert edge.provenance["opaque"] == expected_provenance["opaque"]
    assert edge.to_payload()["admissible_completions"][0]["value"] == expected_completion_value
    assert edge.to_payload()["provenance"] == expected_provenance
    assert grounding_owner._edge_search_text(edge) == expected_fts_text
    assert edge.with_content_hash().content_hash == expected_hash
    assert actual_calls == ["completion", "provenance"]
