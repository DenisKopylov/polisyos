"""Behavior tests for distributional causal-justification helpers."""

from __future__ import annotations

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.distributional import (
    DistributionalCouplingStatus,
    DistributionalJustification,
    DistributionalProofTarget,
    load_causal_assumption_card,
    load_distributional_proof_artifact,
)
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    load_negative_certificate,
)
from polisyos.ir.registry.refs import NegativeCertificateRef
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _distributional_theorem_family,
    _persist_distributional_assumption_cards,
    _persist_distributional_proof_artifacts,
    _resolve_distributional_justification,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF


def test_identified_marginal_keeps_coupling_scenario_and_persists_proofs(
    execution_context,
    minimal_state,
    cas_store,
    artifact_ref_factory,
) -> None:
    source_ref = artifact_ref_factory(kind="scientist.distributional_source")
    inputs = [InputRef(artifact_id=source_ref.artifact_id, role="distributional_source")]
    graph_ref = persist_causal_graph_model(
        ensure_ir_artifact_store(cas_store),
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["policy_shock", "income"],
            edges=[
                CausalEdge(
                    src="policy_shock",
                    dst="income",
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                )
            ],
        ),
        inputs=inputs,
    )
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = graph_ref
    state.params["distributional_treatment_variable"] = "policy_shock"

    resolution = _resolve_distributional_justification(
        execution_context,
        state,
        outcome_name="income",
        weighting_mode="uniform",
    )
    assert resolution.marginal_justification is DistributionalJustification.IDENTIFIED
    assert resolution.coupling_justification is DistributionalJustification.SCENARIO
    assert resolution.proof_bundle is not None
    assert resolution.coupling_negative_certificate is not None

    theorem_family = _distributional_theorem_family(
        proof_bundle=resolution.proof_bundle,
        metadata=resolution.metadata,
    )
    cards = _persist_distributional_assumption_cards(
        execution_context,
        inputs=inputs,
        marginal_assumptions=resolution.causal_assumptions,
        coupling_assumptions=resolution.coupling_assumptions,
        marginal_justification=resolution.marginal_justification,
        default_theorem_family=theorem_family,
    )
    marginal_ref, coupling_ref = _persist_distributional_proof_artifacts(
        execution_context,
        inputs=inputs,
        proof_bundle=resolution.proof_bundle,
        metadata=resolution.metadata,
        marginal_justification=resolution.marginal_justification,
        coupling_justification=resolution.coupling_justification,
        marginal_assumption_refs=cards.marginal_refs,
        coupling_assumption_refs=cards.coupling_refs,
        coupling_negative_certificate=resolution.coupling_negative_certificate,
    )

    assert marginal_ref is not None
    assert coupling_ref is not None
    store = ensure_ir_artifact_store(cas_store)
    marginal = load_distributional_proof_artifact(store, marginal_ref)
    coupling = load_distributional_proof_artifact(store, coupling_ref)
    assert marginal.target is DistributionalProofTarget.CDF
    assert coupling.target is DistributionalProofTarget.COUPLING
    assert coupling.coupling_status is DistributionalCouplingStatus.SCENARIO_ONLY
    negative_ref = NegativeCertificateRef.model_validate(
        coupling.metadata["negative_certificate_ref"]
    )
    negative = load_negative_certificate(store, negative_ref)
    assert negative.blocking_type is BlockingType.COUPLING_NOT_IDENTIFIED

    assumption_cards = [load_causal_assumption_card(store, ref) for ref in cards.all_refs]
    assert any(card.scope == "coupling" for card in assumption_cards)
    assert any(card.scope == "estimation" for card in assumption_cards)

    density_ratio = _resolve_distributional_justification(
        execution_context,
        state,
        outcome_name="income",
        weighting_mode="density_ratio",
    )
    assert density_ratio.marginal_justification is resolution.marginal_justification
    assert density_ratio.coupling_justification is resolution.coupling_justification
    assert "uniform_weighting_used" in resolution.causal_assumptions
    assert "uniform_weighting_used" not in density_ratio.causal_assumptions


def test_missing_treatment_or_graph_never_upgrades_to_identified(
    execution_context,
    minimal_state,
    cas_store,
) -> None:
    graph_ref = persist_causal_graph_model(
        ensure_ir_artifact_store(cas_store),
        CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["policy_shock", "income"],
            edges=[
                CausalEdge(
                    src="policy_shock",
                    dst="income",
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                )
            ],
        ),
    )
    missing_treatment = minimal_state.model_copy(deep=True)
    missing_treatment.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = graph_ref
    unresolved = _resolve_distributional_justification(
        execution_context,
        missing_treatment,
        outcome_name="income",
        weighting_mode="uniform",
    )

    assert unresolved.marginal_justification is DistributionalJustification.SCENARIO
    assert unresolved.coupling_justification is DistributionalJustification.SCENARIO
    assert unresolved.proof_bundle is None
    assert unresolved.metadata["proof_kernel"]["reason"] == "missing_treatment_variable"

    missing_graph = minimal_state.model_copy(deep=True)
    missing_graph.params["distributional_treatment_variable"] = "policy_shock"
    unresolved_graph = _resolve_distributional_justification(
        execution_context,
        missing_graph,
        outcome_name="income",
        weighting_mode="uniform",
    )
    assert unresolved_graph.marginal_justification is DistributionalJustification.SCENARIO
    assert unresolved_graph.proof_bundle is None
    assert unresolved_graph.metadata["proof_kernel"]["reason"] == "missing_reconciled_causal_graph"
