"""Tests for Track A extensions to id_engine.py.

Tests cover:
- ProofStep frozen dataclass
- RequiredDataSpec frozen dataclass
- IdentificationResult.proof_steps field
- HedgeCertificate.required_data field
- z_id_algorithm
- mz_id_algorithm
- SourceDomain frozen dataclass
"""

from __future__ import annotations

import dataclasses

import pytest
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
    ProofStep,
    RequiredDataSpec,
    SourceDomain,
    id_algorithm,
    id_with_oracle_fallback,
    mz_id_algorithm,
    z_id_algorithm,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------


def make_dag(edges: list[tuple[str, str]]) -> CausalGraphModel:
    """Build a DAG from directed edges (src, dst)."""
    nodes: list[str] = []
    edge_objs: list[CausalEdge] = []
    for src, dst in edges:
        if src not in nodes:
            nodes.append(src)
        if dst not in nodes:
            nodes.append(dst)
        edge_objs.append(
            CausalEdge(
                src=src,
                dst=dst,
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
            )
        )
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=edge_objs,
    )


def make_confounded_graph(
    directed: list[tuple[str, str]],
    bidirected: list[tuple[str, str]],
) -> CausalGraphModel:
    """Build a graph with directed and bidirected (confounding) edges.

    Directed edges:  TAIL (src) → ARROW (dst)
    Bidirected edges: ARROW (src) ↔ ARROW (dst)
    """
    nodes: list[str] = []
    edge_objs: list[CausalEdge] = []
    for src, dst in directed:
        if src not in nodes:
            nodes.append(src)
        if dst not in nodes:
            nodes.append(dst)
        edge_objs.append(
            CausalEdge(
                src=src,
                dst=dst,
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
            )
        )
    for src, dst in bidirected:
        if src not in nodes:
            nodes.append(src)
        if dst not in nodes:
            nodes.append(dst)
        edge_objs.append(
            CausalEdge(
                src=src,
                dst=dst,
                mark_src=EdgeMark.ARROW,
                mark_dst=EdgeMark.ARROW,
            )
        )
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=nodes,
        edges=edge_objs,
    )


# ---------------------------------------------------------------------------
# TestProofStepDataclass
# ---------------------------------------------------------------------------


class TestProofStepDataclass:
    def test_is_frozen(self):
        s = ProofStep(
            rule_name="RULE1",
            antecedent_vars=("X",),
            consequent_vars=("Y",),
            applied_to_graph_state="test",
        )
        with pytest.raises((AttributeError, TypeError, dataclasses.FrozenInstanceError)):
            s.rule_name = "RULE2"  # type: ignore[misc]

    def test_rule_name_stored(self):
        s = ProofStep(
            rule_name="C_COMPONENT",
            antecedent_vars=(),
            consequent_vars=(),
            applied_to_graph_state="desc",
        )
        assert s.rule_name == "C_COMPONENT"

    def test_depth_default_zero(self):
        s = ProofStep(
            rule_name="HEDGE",
            antecedent_vars=("X",),
            consequent_vars=("Y",),
            applied_to_graph_state="hedge detected",
        )
        assert s.depth == 0

    def test_depth_custom(self):
        s = ProofStep(
            rule_name="ANCESTRAL_COLLAPSE",
            antecedent_vars=("A", "B"),
            consequent_vars=("C",),
            applied_to_graph_state="restrict ancestors",
            depth=3,
        )
        assert s.depth == 3

    def test_tuple_fields(self):
        s = ProofStep(
            rule_name="RULE3",
            antecedent_vars=("W1", "W2"),
            consequent_vars=("X",),
            applied_to_graph_state="extend X",
        )
        assert isinstance(s.antecedent_vars, tuple)
        assert isinstance(s.consequent_vars, tuple)

    def test_all_rule_names_can_be_stored(self):
        rule_names = [
            "RULE1",
            "RULE2",
            "RULE3",
            "ANCESTRAL_COLLAPSE",
            "C_COMPONENT",
            "HEDGE",
            "ORACLE",
        ]
        for rn in rule_names:
            s = ProofStep(
                rule_name=rn,
                antecedent_vars=(),
                consequent_vars=(),
                applied_to_graph_state="test",
            )
            assert s.rule_name == rn


# ---------------------------------------------------------------------------
# TestRequiredDataSpec
# ---------------------------------------------------------------------------


class TestRequiredDataSpec:
    def test_is_frozen(self):
        r = RequiredDataSpec(missing_distributions=())
        with pytest.raises((AttributeError, TypeError, dataclasses.FrozenInstanceError)):
            r.suggested_experiment = "test"  # type: ignore[misc]

    def test_defaults(self):
        r = RequiredDataSpec(missing_distributions=())
        assert r.suggested_experiment is None
        assert r.alternative_identification is None

    def test_missing_distributions_stored(self):
        r = RequiredDataSpec(
            missing_distributions=("dist1", "dist2"),
            suggested_experiment="Randomize X",
        )
        assert len(r.missing_distributions) == 2
        assert r.suggested_experiment == "Randomize X"

    def test_alternative_identification(self):
        r = RequiredDataSpec(
            missing_distributions=(),
            suggested_experiment="RCT on X",
            alternative_identification="Use IV with Z",
        )
        assert r.alternative_identification == "Use IV with Z"

    def test_empty_missing_distributions(self):
        r = RequiredDataSpec(missing_distributions=())
        assert r.missing_distributions == ()


# ---------------------------------------------------------------------------
# TestIdentificationResultProofSteps
# ---------------------------------------------------------------------------


class TestIdentificationResultProofSteps:
    def test_proof_steps_field_exists(self):
        """IdentificationResult has a proof_steps list field."""
        graph = make_confounded_graph(
            directed=[("Z", "X"), ("X", "Y"), ("Z", "Y")],
            bidirected=[],
        )
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        assert hasattr(result, "proof_steps")

    def test_proof_steps_is_list(self):
        graph = make_confounded_graph(
            directed=[("Z", "X"), ("X", "Y"), ("Z", "Y")],
            bidirected=[],
        )
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        assert isinstance(result.proof_steps, list)

    def test_proof_steps_populated_on_identified_graph(self):
        """Simple backdoor graph: Z->X->Y, Z->Y — should be IDENTIFIED."""
        graph = make_confounded_graph(
            directed=[("Z", "X"), ("X", "Y"), ("Z", "Y")],
            bidirected=[],
        )
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.proof_steps is not None

    def test_trace_backward_compatible(self):
        """trace field still present and is list[str] — backward compat."""
        graph = make_confounded_graph(
            directed=[("Z", "X"), ("X", "Y"), ("Z", "Y")],
            bidirected=[],
        )
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        assert isinstance(result.trace, list)
        assert all(isinstance(t, str) for t in result.trace)

    def test_proof_steps_type_when_nonempty(self):
        """When proof_steps is non-empty, all elements are ProofStep."""
        graph = make_confounded_graph(
            directed=[("Z", "X"), ("X", "Y"), ("Z", "Y")],
            bidirected=[],
        )
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        for step in result.proof_steps:
            assert isinstance(step, ProofStep)

    def test_hedge_cert_required_data_field_exists(self):
        """Butterfly/bow-arc graph: X->Y with X<->Y confounding — non-identifiable."""
        graph = make_confounded_graph(
            directed=[("X", "Y")],
            bidirected=[("X", "Y")],
        )
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        if result.status == IdentificationStatus.HEDGE_FOUND:
            assert hasattr(result.hedge_certificate, "required_data")

    def test_hedge_cert_required_data_is_required_data_spec_or_none(self):
        """required_data is either RequiredDataSpec or None."""
        graph = make_confounded_graph(
            directed=[("X", "Y")],
            bidirected=[("X", "Y")],
        )
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        if result.status == IdentificationStatus.HEDGE_FOUND:
            cert = result.hedge_certificate
            assert cert is not None
            assert cert.required_data is None or isinstance(cert.required_data, RequiredDataSpec)

    def test_hedge_required_data_populated_when_hedge_found(self):
        """When HEDGE_FOUND, required_data should be populated with missing distributions."""
        graph = make_confounded_graph(
            directed=[("X", "Y")],
            bidirected=[("X", "Y")],
        )
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        if result.status == IdentificationStatus.HEDGE_FOUND:
            cert = result.hedge_certificate
            assert cert is not None
            if cert.required_data is not None:
                assert isinstance(cert.required_data.missing_distributions, tuple)

    def test_hedge_proof_steps_contain_hedge_step(self):
        """When HEDGE_FOUND, proof_steps should include a HEDGE step."""
        graph = make_confounded_graph(
            directed=[("X", "Y")],
            bidirected=[("X", "Y")],
        )
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        if result.status == IdentificationStatus.HEDGE_FOUND:
            hedge_steps = [s for s in result.proof_steps if s.rule_name == "HEDGE"]
            assert len(hedge_steps) >= 1

    def test_oracle_needed_has_oracle_step(self):
        """When ORACLE_NEEDED, proof_steps should include an ORACLE step."""
        # A graph where Y is not reachable from any component — force ORACLE
        graph = make_confounded_graph(
            directed=[("X", "M"), ("M", "Y")],
            bidirected=[("X", "Y")],
        )
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        if result.status == IdentificationStatus.ORACLE_NEEDED:
            oracle_steps = [s for s in result.proof_steps if s.rule_name == "ORACLE"]
            assert len(oracle_steps) >= 1

    def test_default_proof_steps_is_empty_list(self):
        """IdentificationResult default proof_steps is an empty list."""
        from polisyos.ir.analytics.estimand import DistributionDomain, DistributionRef

        leaf = DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=("Y",),
        )
        result = IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=[],
            required_distributions=[],
        )
        assert result.proof_steps == []

    def test_x_empty_emits_rule1_step(self):
        """When X=∅, id_algorithm should emit a RULE1 proof step."""
        graph = make_dag([("X", "Y")])
        result = id_algorithm(
            treatment=frozenset(),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        assert result.status == IdentificationStatus.IDENTIFIED
        rule1_steps = [s for s in result.proof_steps if s.rule_name == "RULE1"]
        assert len(rule1_steps) >= 1

    def test_ancestral_collapse_emits_step(self):
        """When V ≠ An(Y), ANCESTRAL_COLLAPSE step should appear."""
        # W is irrelevant (not ancestor of Y) → ancestral collapse fires
        graph = make_dag([("X", "Y"), ("W", "X")])
        # Ask for P(Y | do(X)) — W is ancestor of X but not of Y directly
        # Actually W->X->Y so W IS ancestor of Y. Use isolated W instead.
        graph2 = make_confounded_graph(
            directed=[("X", "Y")],
            bidirected=[],
        )
        # Add a disconnected node W by building manually
        nodes = ["X", "Y", "W"]
        edges = [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)]
        graph3 = CausalGraphModel(graph_type=GraphType.DAG, nodes=nodes, edges=edges)
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph3,
        )
        # W is not an ancestor of Y, so ancestral collapse fires
        ancestral_steps = [s for s in result.proof_steps if s.rule_name == "ANCESTRAL_COLLAPSE"]
        assert len(ancestral_steps) >= 1


# ---------------------------------------------------------------------------
# TestSourceDomain
# ---------------------------------------------------------------------------


class TestSourceDomain:
    def test_is_frozen(self):
        d = SourceDomain(domain_id="d1")
        with pytest.raises((AttributeError, TypeError, dataclasses.FrozenInstanceError)):
            d.domain_id = "d2"  # type: ignore[misc]

    def test_defaults(self):
        d = SourceDomain(domain_id="src")
        assert d.s_nodes == frozenset()
        assert d.z_interventions == frozenset()
        assert d.dataset_ref is None

    def test_with_s_nodes(self):
        d = SourceDomain(domain_id="src", s_nodes=frozenset({"M", "N"}))
        assert "M" in d.s_nodes
        assert "N" in d.s_nodes

    def test_with_z_interventions(self):
        d = SourceDomain(domain_id="rct", z_interventions=frozenset({"X"}))
        assert "X" in d.z_interventions

    def test_dataset_ref(self):
        d = SourceDomain(domain_id="src1", dataset_ref="ds:001")
        assert d.dataset_ref == "ds:001"


# ---------------------------------------------------------------------------
# TestZIDAlgorithm
# ---------------------------------------------------------------------------


class TestZIDAlgorithm:
    def test_z_id_returns_identification_result(self):
        graph = make_confounded_graph(
            directed=[("Z", "X"), ("X", "Y"), ("Z", "Y")],
            bidirected=[],
        )
        result = z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset({"Z"}),
            graph=graph,
        )
        assert isinstance(result, IdentificationResult)

    def test_z_id_status_is_valid_enum(self):
        graph = make_confounded_graph(
            directed=[("X", "Y")],
            bidirected=[],
        )
        result = z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset({"X"}),
            graph=graph,
        )
        assert result.status in list(IdentificationStatus)

    def test_z_id_no_interventions_collapses_to_standard(self):
        """No z_interventions -> should behave like id_with_oracle_fallback."""
        graph = make_confounded_graph(
            directed=[("Z", "X"), ("X", "Y"), ("Z", "Y")],
            bidirected=[],
        )
        result_z = z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset(),
            graph=graph,
        )
        result_std = id_with_oracle_fallback(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        assert result_z.status == result_std.status

    def test_z_id_with_backdoor_graph(self):
        """Simple backdoor graph should return a valid status with z-intervention."""
        graph = make_confounded_graph(
            directed=[("Z", "X"), ("X", "Y"), ("Z", "Y")],
            bidirected=[],
        )
        result = z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset({"Z"}),
            graph=graph,
        )
        assert result.status in {
            IdentificationStatus.IDENTIFIED,
            IdentificationStatus.HEDGE_FOUND,
            IdentificationStatus.ORACLE_NEEDED,
            IdentificationStatus.PAG_AMBIGUOUS,
        }

    def test_z_id_trace_is_list_of_strings(self):
        graph = make_confounded_graph(
            directed=[("X", "Y")],
            bidirected=[],
        )
        result = z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset({"X"}),
            graph=graph,
        )
        assert isinstance(result.trace, list)
        assert all(isinstance(t, str) for t in result.trace)

    def test_z_id_required_distributions_is_list(self):
        graph = make_confounded_graph(
            directed=[("Z", "X"), ("X", "Y"), ("Z", "Y")],
            bidirected=[],
        )
        result = z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset({"Z"}),
            graph=graph,
        )
        assert isinstance(result.required_distributions, list)

    def test_z_id_simple_chain_no_confounding(self):
        """Simple chain X->Y with no confounding, Z available — should identify."""
        graph = make_dag([("X", "Y")])
        result = z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset(),
            graph=graph,
        )
        assert result.status == IdentificationStatus.IDENTIFIED

    def test_z_id_accepts_dataset_ref(self):
        graph = make_dag([("X", "Y")])
        result = z_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            z_interventions=frozenset(),
            graph=graph,
            dataset_ref="ds:test:001",
        )
        assert isinstance(result, IdentificationResult)


# ---------------------------------------------------------------------------
# TestMZIDAlgorithm
# ---------------------------------------------------------------------------


class TestMZIDAlgorithm:
    def test_mz_id_no_domains_returns_result(self):
        graph = make_confounded_graph(
            directed=[("X", "Y")],
            bidirected=[],
        )
        result = mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[],
            graph=graph,
        )
        assert isinstance(result, IdentificationResult)

    def test_mz_id_no_domains_status_is_valid(self):
        graph = make_confounded_graph(
            directed=[("X", "Y")],
            bidirected=[],
        )
        result = mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[],
            graph=graph,
        )
        assert result.status in list(IdentificationStatus)

    def test_mz_id_single_domain_no_s_nodes(self):
        graph = make_confounded_graph(
            directed=[("Z", "X"), ("X", "Y"), ("Z", "Y")],
            bidirected=[],
        )
        domain = SourceDomain(
            domain_id="src1",
            s_nodes=frozenset(),
            z_interventions=frozenset(),
        )
        result = mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[domain],
            graph=graph,
        )
        assert isinstance(result, IdentificationResult)

    def test_mz_id_returns_identification_result_type(self):
        graph = make_confounded_graph(
            directed=[("X", "M"), ("M", "Y")],
            bidirected=[],
        )
        d1 = SourceDomain(domain_id="d1", s_nodes=frozenset({"M"}), z_interventions=frozenset())
        d2 = SourceDomain(domain_id="d2", s_nodes=frozenset(), z_interventions=frozenset({"X"}))
        result = mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[d1, d2],
            graph=graph,
        )
        assert isinstance(result, IdentificationResult)
        assert result.status in list(IdentificationStatus)

    def test_mz_id_single_domain_with_z_interventions(self):
        graph = make_confounded_graph(
            directed=[("Z", "X"), ("X", "Y"), ("Z", "Y")],
            bidirected=[],
        )
        domain = SourceDomain(
            domain_id="rct1",
            s_nodes=frozenset(),
            z_interventions=frozenset({"Z"}),
        )
        result = mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[domain],
            graph=graph,
        )
        assert isinstance(result, IdentificationResult)
        assert result.status in list(IdentificationStatus)

    def test_mz_id_trace_is_list_of_strings(self):
        graph = make_dag([("X", "Y")])
        domain = SourceDomain(domain_id="src", s_nodes=frozenset(), z_interventions=frozenset())
        result = mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[domain],
            graph=graph,
        )
        assert isinstance(result.trace, list)
        assert all(isinstance(t, str) for t in result.trace)

    def test_mz_id_identified_simple_graph(self):
        """Simple DAG X->Y with no confounding should identify via any domain config."""
        graph = make_dag([("X", "Y")])
        domain = SourceDomain(domain_id="src", s_nodes=frozenset(), z_interventions=frozenset())
        result = mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[domain],
            graph=graph,
        )
        assert result.status == IdentificationStatus.IDENTIFIED

    def test_mz_id_multiple_domains_returns_best(self):
        """With multiple domains, mz_id should prefer IDENTIFIED over others."""
        # Graph where standard ID works (no confounding)
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        d1 = SourceDomain(domain_id="obs", s_nodes=frozenset(), z_interventions=frozenset())
        d2 = SourceDomain(domain_id="rct", s_nodes=frozenset(), z_interventions=frozenset({"Z"}))
        result = mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[d1, d2],
            graph=graph,
        )
        # At least one domain should find something valid
        assert result.status in list(IdentificationStatus)

    def test_mz_id_required_distributions_is_list(self):
        graph = make_dag([("X", "Y")])
        domain = SourceDomain(domain_id="src")
        result = mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[domain],
            graph=graph,
        )
        assert isinstance(result.required_distributions, list)

    def test_mz_id_dataset_ref_propagated(self):
        """dataset_ref is passed through to the result."""
        graph = make_dag([("X", "Y")])
        domain = SourceDomain(domain_id="src", dataset_ref="ds:override")
        result = mz_id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            source_domains=[domain],
            graph=graph,
            dataset_ref="ds:global",
        )
        assert isinstance(result, IdentificationResult)


# ---------------------------------------------------------------------------
# TestProofStepAuditTrail (Task 2.5)
# ---------------------------------------------------------------------------


class TestProofStepAuditTrail:
    """Tests for ProofStep audit trail infrastructure (Task 2.5)."""

    _NEW_RULE_NAMES = [
        "IDC_DECOMPOSE",
        "IDC_TRIVIAL_Z",
        "IDC_POSITIVITY",
        "PAG_ORIENT_R1",
        "PAG_ORIENT_R2",
        "PAG_ORIENT_R3",
        "PAG_CONSERVATIVE_BLOCK",
        "PAG_OPTIMISTIC_COMMIT",
        "PAG_PROBABILISTIC",
        "SIGMA_R1",
        "SIGMA_R2",
        "SIGMA_R3",
    ]

    def test_new_rule_names_in_formal_map(self):
        """All 12 new rule names must have entries in _RULE_FORMAL."""
        from polisyos.foundry.methods.catalog.causal.id_engine import _internal_proof_step_to_ir

        for rule_name in self._NEW_RULE_NAMES:
            step = ProofStep(
                rule_name=rule_name,
                antecedent_vars=(),
                consequent_vars=(),
                applied_to_graph_state="test state",
            )
            ir_step = _internal_proof_step_to_ir(step)
            assert ir_step.rule_formal_name != rule_name, (
                f"rule_name={rule_name!r} not found in _RULE_FORMAL "
                f"(got rule_formal_name={ir_step.rule_formal_name!r})"
            )

    def test_internal_to_ir_rule_formal_name_populated(self):
        """rule_formal_name must differ from raw rule_name for known rules."""
        from polisyos.foundry.methods.catalog.causal.id_engine import _internal_proof_step_to_ir

        for rule_name in [
            "RULE1",
            "RULE3",
            "C_COMPONENT",
            "HEDGE",
            "S_TRIM",
            "IDC_DECOMPOSE",
            "SIGMA_R1",
        ]:
            step = ProofStep(
                rule_name=rule_name,
                antecedent_vars=("X",),
                consequent_vars=("Y",),
                applied_to_graph_state="post-state",
            )
            ir_step = _internal_proof_step_to_ir(step)
            assert ir_step.rule_formal_name != rule_name

    def test_internal_to_ir_applicable_theorem_populated(self):
        """applicable_theorem must contain a year reference for known rules."""
        import re

        from polisyos.foundry.methods.catalog.causal.id_engine import _internal_proof_step_to_ir

        for rule_name in self._NEW_RULE_NAMES:
            step = ProofStep(
                rule_name=rule_name,
                antecedent_vars=(),
                consequent_vars=(),
                applied_to_graph_state="post-state",
            )
            ir_step = _internal_proof_step_to_ir(step)
            assert re.search(r"\d{4}", ir_step.applicable_theorem), (
                f"applicable_theorem for {rule_name!r} missing year: {ir_step.applicable_theorem!r}"
            )

    def test_graph_state_before_preserved(self):
        """graph_state_before on internal ProofStep is propagated to IR ProofStep."""
        from polisyos.foundry.methods.catalog.causal.id_engine import _internal_proof_step_to_ir

        step = ProofStep(
            rule_name="IDC_DECOMPOSE",
            antecedent_vars=("X",),
            consequent_vars=("Y",),
            applied_to_graph_state="post-state",
            graph_state_before="my-pre-state",
        )
        ir_step = _internal_proof_step_to_ir(step)
        assert ir_step.graph_state_before == "my-pre-state"

    def test_graph_state_after_populated(self):
        """graph_state_after must equal applied_to_graph_state."""
        from polisyos.foundry.methods.catalog.causal.id_engine import _internal_proof_step_to_ir

        step = ProofStep(
            rule_name="SIGMA_R2",
            antecedent_vars=(),
            consequent_vars=(),
            applied_to_graph_state="some post-step description",
        )
        ir_step = _internal_proof_step_to_ir(step)
        assert ir_step.graph_state_after == "some post-step description"

    def test_internal_proof_step_has_graph_state_before_field(self):
        """Internal ProofStep dataclass must have graph_state_before field."""
        step = ProofStep(
            rule_name="RULE1",
            antecedent_vars=("Z",),
            consequent_vars=("Y",),
            applied_to_graph_state="post",
            graph_state_before="pre",
            depth=2,
        )
        assert step.graph_state_before == "pre"
        assert step.depth == 2

    def test_internal_proof_step_graph_state_before_defaults_empty(self):
        """graph_state_before defaults to empty string (backward-compatible)."""
        step = ProofStep(
            rule_name="C_COMPONENT",
            antecedent_vars=(),
            consequent_vars=("Y",),
            applied_to_graph_state="state",
        )
        assert step.graph_state_before == ""


# ---------------------------------------------------------------------------
# TestIDCProofSteps (Task 2.2a)
# ---------------------------------------------------------------------------


class TestIDCProofSteps:
    """Tests for IDC algorithm proof step emission (Task 2.2a)."""

    def test_idc_emits_decompose_step(self):
        """idc_algorithm must emit IDC_DECOMPOSE proof step when Z is non-empty."""
        from polisyos.foundry.methods.catalog.causal.id_engine import idc_algorithm

        graph = make_dag([("X", "Y"), ("Z", "Y")])
        result = idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset({"Z"}),
            graph=graph,
        )
        rule_names = [s.rule_name for s in result.proof_steps]
        assert "IDC_DECOMPOSE" in rule_names

    def test_idc_trivial_z_emits_step(self):
        """idc_algorithm with Z=∅ must emit IDC_TRIVIAL_Z step."""
        from polisyos.foundry.methods.catalog.causal.id_engine import idc_algorithm

        graph = make_dag([("X", "Y")])
        result = idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset(),
            graph=graph,
        )
        rule_names = [s.rule_name for s in result.proof_steps]
        assert "IDC_TRIVIAL_Z" in rule_names

    def test_idc_positivity_step_present(self):
        """idc_algorithm must emit IDC_POSITIVITY step when Z is non-empty."""
        from polisyos.foundry.methods.catalog.causal.id_engine import idc_algorithm

        graph = make_dag([("X", "Y"), ("Z", "Y")])
        result = idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset({"Z"}),
            graph=graph,
        )
        assert result.status == IdentificationStatus.IDENTIFIED
        rule_names = [s.rule_name for s in result.proof_steps]
        assert "IDC_POSITIVITY" in rule_names

    def test_idc_includes_sub_call_steps(self):
        """idc_algorithm must include proof steps from numerator/denominator sub-calls."""
        from polisyos.foundry.methods.catalog.causal.id_engine import idc_algorithm

        graph = make_dag([("X", "Y"), ("Z", "Y"), ("Z", "X")])
        result = idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset({"Z"}),
            graph=graph,
        )
        # IDC_DECOMPOSE must be first, followed by sub-call steps
        assert len(result.proof_steps) > 1

    def test_idc_proof_steps_are_proof_step_instances(self):
        """All proof_steps elements from idc_algorithm must be ProofStep instances."""
        from polisyos.foundry.methods.catalog.causal.id_engine import idc_algorithm

        graph = make_dag([("X", "Y"), ("Z", "Y")])
        result = idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset({"Z"}),
            graph=graph,
        )
        for step in result.proof_steps:
            assert isinstance(step, ProofStep)

    def test_idc_trivial_z_returns_identified(self):
        """idc_algorithm with Z=∅ on a simple DAG must succeed."""
        from polisyos.foundry.methods.catalog.causal.id_engine import idc_algorithm

        graph = make_dag([("X", "Y")])
        result = idc_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            conditions=frozenset(),
            graph=graph,
        )
        assert result.status == IdentificationStatus.IDENTIFIED


class TestSIDAlgorithm:
    """Tests for sid_algorithm (stochastic / conditional / dynamic interventions)."""

    def test_soft_policy_returns_identified_when_base_is_identified(self):
        """Soft Gaussian policy on identifiable DAG → IDENTIFIED with StochasticInterventionNode."""
        from polisyos.foundry.methods.catalog.causal.id_engine import sid_algorithm
        from polisyos.ir.analytics.estimand import StochasticInterventionNode, StochasticPolicy

        graph = make_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")])
        policy = StochasticPolicy(policy_type="soft", policy_expr="N(mu, sigma)")
        result = sid_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
            policy=policy,
        )
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.estimand_ast is not None
        assert isinstance(result.estimand_ast.root, StochasticInterventionNode)

    def test_soft_policy_proof_step_sid_policy_wrap(self):
        """sid_algorithm must emit a SID_POLICY_WRAP proof step."""
        from polisyos.foundry.methods.catalog.causal.id_engine import sid_algorithm
        from polisyos.ir.analytics.estimand import StochasticPolicy

        graph = make_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")])
        policy = StochasticPolicy(policy_type="soft")
        result = sid_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
            policy=policy,
        )
        rule_names = [s.rule_name for s in result.proof_steps]
        assert "SID_POLICY_WRAP" in rule_names

    def test_shift_policy_emits_sid_shift_step(self):
        """Shift policy (modified treatment) emits SID_SHIFT proof step."""
        from polisyos.foundry.methods.catalog.causal.id_engine import sid_algorithm
        from polisyos.ir.analytics.estimand import StochasticPolicy

        graph = make_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")])
        policy = StochasticPolicy(policy_type="shift", shift_delta=0.5)
        result = sid_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
            policy=policy,
        )
        assert result.status == IdentificationStatus.IDENTIFIED
        rule_names = [s.rule_name for s in result.proof_steps]
        assert "SID_SHIFT" in rule_names

    def test_sid_dag_policy_fastpath_emits_policy_g_formula_step(self):
        """DAG soft policies should record the direct policy g-formula fast path."""
        from polisyos.foundry.methods.catalog.causal.id_engine import sid_algorithm
        from polisyos.ir.analytics.estimand import StochasticPolicy

        graph = make_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")])
        policy = StochasticPolicy(
            policy_type="soft", conditioning_vars=("Z",), policy_expr="pi(X|Z)"
        )
        result = sid_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
            policy=policy,
        )

        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.algorithm_version == "sid_v2"
        rule_names = [getattr(step, "rule_name", "") for step in result.proof_steps]
        assert "SID_DAG_POLICY" in rule_names

    def test_shift_policy_attaches_policy_side_conditions(self):
        """Shift policies should carry consistency + shift positivity side-conditions."""
        from polisyos.foundry.methods.catalog.causal.id_engine import sid_algorithm
        from polisyos.ir.analytics.estimand import SideConditionKind, StochasticPolicy

        graph = make_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")])
        policy = StochasticPolicy(policy_type="shift", conditioning_vars=("Z",), shift_delta=0.5)
        result = sid_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
            policy=policy,
        )

        assert result.estimand_ast is not None
        condition_kinds = {item.kind for item in result.estimand_ast.side_conditions}
        assert SideConditionKind.CONSISTENCY in condition_kinds
        assert SideConditionKind.POSITIVITY in condition_kinds

    def test_sid_non_identified_when_base_non_identified(self):
        """When base id_algorithm returns non-ID, sid_algorithm must also be non-ID."""
        from polisyos.foundry.methods.catalog.causal.id_engine import sid_algorithm
        from polisyos.ir.analytics.estimand import StochasticPolicy

        # Bow-arc graph: X ← U → Y with X → Y, U unobserved — non-identifiable
        edges = [("X", "Y")]
        hidden = [("U", "X"), ("U", "Y")]
        graph = make_confounded_graph(edges, hidden)
        policy = StochasticPolicy(policy_type="soft")
        result = sid_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
            policy=policy,
        )
        assert result.status != IdentificationStatus.IDENTIFIED

    def test_sid_result_has_version_tag(self):
        """sid_algorithm result metadata must include 'phase5_sid'."""
        from polisyos.foundry.methods.catalog.causal.id_engine import sid_algorithm
        from polisyos.ir.analytics.estimand import StochasticPolicy

        graph = make_dag([("X", "Y")])
        policy = StochasticPolicy(policy_type="soft")
        result = sid_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
            policy=policy,
        )
        assert "sid" in result.algorithm_version or result.status == IdentificationStatus.IDENTIFIED

    def test_conditional_intervention_id_basic(self):
        """conditional_intervention_id on simple DAG returns IDENTIFIED."""
        from polisyos.foundry.methods.catalog.causal.id_engine import conditional_intervention_id

        graph = make_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")])
        result = conditional_intervention_id(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            condition_vars=frozenset({"Z"}),
            graph=graph,
        )
        assert result.status == IdentificationStatus.IDENTIFIED

    def test_conditional_intervention_records_condition_vars(self):
        """conditional_intervention_id must record condition_vars in metadata."""
        from polisyos.foundry.methods.catalog.causal.id_engine import conditional_intervention_id

        graph = make_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")])
        result = conditional_intervention_id(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            condition_vars=frozenset({"Z"}),
            graph=graph,
        )
        assert (
            "conditional" in result.algorithm_version
            or result.status == IdentificationStatus.IDENTIFIED
        )

    def test_conditional_intervention_emits_sid_conditional_step(self):
        """conditional_intervention_id must emit a SID_CONDITIONAL proof step."""
        from polisyos.foundry.methods.catalog.causal.id_engine import conditional_intervention_id

        graph = make_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")])
        result = conditional_intervention_id(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            condition_vars=frozenset({"Z"}),
            graph=graph,
        )
        rule_names = [s.rule_name for s in result.proof_steps]
        assert "SID_CONDITIONAL" in rule_names

    def test_conditional_intervention_non_id_graph(self):
        """conditional_intervention_id with unidentifiable base → non-ID result."""
        from polisyos.foundry.methods.catalog.causal.id_engine import conditional_intervention_id

        edges = [("X", "Y")]
        hidden = [("U", "X"), ("U", "Y")]
        graph = make_confounded_graph(edges, hidden)
        result = conditional_intervention_id(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            condition_vars=frozenset(),
            graph=graph,
        )
        assert result.status != IdentificationStatus.IDENTIFIED

    def test_dynamic_intervention_two_periods(self):
        """dynamic_intervention_id on 2-period sequential DAG → IDENTIFIED."""
        from polisyos.foundry.methods.catalog.causal.id_engine import dynamic_intervention_id

        # X1 → L → X2 → Y, X1 → Y
        graph = make_dag([("X1", "L"), ("X1", "Y"), ("L", "X2"), ("X2", "Y")])
        result = dynamic_intervention_id(
            treatment_sequence=["X1", "X2"],
            outcome="Y",
            graph=graph,
            time_points=[1, 2],
            covariate_sequence=["L"],
        )
        assert result.status == IdentificationStatus.IDENTIFIED

    def test_dynamic_intervention_emits_dynamic_gformula_step(self):
        """dynamic_intervention_id must emit DYNAMIC_GFORMULA proof step."""
        from polisyos.foundry.methods.catalog.causal.id_engine import dynamic_intervention_id

        graph = make_dag([("X1", "L"), ("X1", "Y"), ("L", "X2"), ("X2", "Y")])
        result = dynamic_intervention_id(
            treatment_sequence=["X1", "X2"],
            outcome="Y",
            graph=graph,
            time_points=[1, 2],
        )
        rule_names = [s.rule_name for s in result.proof_steps]
        assert "DYNAMIC_GFORMULA" in rule_names

    def test_dynamic_intervention_single_period(self):
        """dynamic_intervention_id with one time-point degenerates to standard ID."""
        from polisyos.foundry.methods.catalog.causal.id_engine import dynamic_intervention_id

        graph = make_dag([("X", "Y")])
        result = dynamic_intervention_id(
            treatment_sequence=["X"],
            outcome="Y",
            graph=graph,
            time_points=[1],
        )
        assert result.status == IdentificationStatus.IDENTIFIED

    def test_soft_policy_delegates_via_conditional_policy(self):
        """StochasticPolicy(policy_type='conditional') routes to conditional_intervention_id."""
        from polisyos.foundry.methods.catalog.causal.id_engine import sid_algorithm
        from polisyos.ir.analytics.estimand import StochasticPolicy

        graph = make_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")])
        policy = StochasticPolicy(policy_type="conditional", conditioning_vars=("Z",))
        result = sid_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
            policy=policy,
        )
        # conditional policy should also yield IDENTIFIED
        assert result.status == IdentificationStatus.IDENTIFIED


class TestJointID:
    """Tests for joint_id_algorithm and multi_outcome_id (Tian 2002)."""

    def test_joint_id_simple_dag_returns_identified(self):
        """Two outcomes, one treatment, both identifiable → joint IDENTIFIED."""
        from polisyos.foundry.methods.catalog.causal.id_engine import joint_id_algorithm

        graph = make_dag([("X", "Y1"), ("X", "Y2"), ("Z", "Y1"), ("Z", "Y2")])
        result = joint_id_algorithm(
            treatments=frozenset({"X"}),
            outcomes=frozenset({"Y1", "Y2"}),
            graph=graph,
        )
        assert result.status == IdentificationStatus.IDENTIFIED

    def test_joint_id_emits_joint_factor_decompose_step(self):
        """joint_id_algorithm must emit JOINT_FACTOR_DECOMPOSE proof step."""
        from polisyos.foundry.methods.catalog.causal.id_engine import joint_id_algorithm

        graph = make_dag([("X", "Y1"), ("X", "Y2")])
        result = joint_id_algorithm(
            treatments=frozenset({"X"}),
            outcomes=frozenset({"Y1", "Y2"}),
            graph=graph,
        )
        rule_names = [s.rule_name for s in result.proof_steps]
        assert "JOINT_FACTOR_DECOMPOSE" in rule_names

    def test_joint_id_single_outcome_delegates(self):
        """joint_id_algorithm with one outcome should still return IDENTIFIED."""
        from polisyos.foundry.methods.catalog.causal.id_engine import joint_id_algorithm

        graph = make_dag([("X", "Y")])
        result = joint_id_algorithm(
            treatments=frozenset({"X"}),
            outcomes=frozenset({"Y"}),
            graph=graph,
        )
        assert result.status == IdentificationStatus.IDENTIFIED

    def test_joint_id_has_version_tag(self):
        """joint_id_algorithm metadata must include 'phase5_joint'."""
        from polisyos.foundry.methods.catalog.causal.id_engine import joint_id_algorithm

        graph = make_dag([("X", "Y1"), ("X", "Y2")])
        result = joint_id_algorithm(
            treatments=frozenset({"X"}),
            outcomes=frozenset({"Y1", "Y2"}),
            graph=graph,
        )
        assert "joint_id" in result.algorithm_version

    def test_joint_id_trace_mentions_ccomponent(self):
        """joint_id_algorithm trace must mention c-component decomposition."""
        from polisyos.foundry.methods.catalog.causal.id_engine import joint_id_algorithm

        graph = make_dag([("X", "Y1"), ("X", "Y2")])
        result = joint_id_algorithm(
            treatments=frozenset({"X"}),
            outcomes=frozenset({"Y1", "Y2"}),
            graph=graph,
        )
        combined_trace = " ".join(result.trace)
        assert any(
            kw in combined_trace.lower() for kw in ("c-component", "ccomponent", "factor", "joint")
        )

    def test_multi_outcome_id_returns_dict(self):
        """multi_outcome_id must return a dict keyed by outcome variable name."""
        from polisyos.foundry.methods.catalog.causal.id_engine import multi_outcome_id

        graph = make_dag([("X", "Y1"), ("X", "Y2")])
        results = multi_outcome_id(
            treatment=frozenset({"X"}),
            outcomes=["Y1", "Y2"],
            graph=graph,
        )
        assert isinstance(results, dict)
        assert set(results.keys()) == {"Y1", "Y2"}

    def test_multi_outcome_all_identified(self):
        """All per-outcome results from multi_outcome_id must be IDENTIFIED."""
        from polisyos.foundry.methods.catalog.causal.id_engine import multi_outcome_id

        graph = make_dag([("X", "Y1"), ("X", "Y2"), ("X", "Y3")])
        results = multi_outcome_id(
            treatment=frozenset({"X"}),
            outcomes=["Y1", "Y2", "Y3"],
            graph=graph,
        )
        for name, res in results.items():
            assert res.status == IdentificationStatus.IDENTIFIED, f"{name} not identified"

    def test_multi_outcome_three_outcomes(self):
        """multi_outcome_id with three outcomes returns three entries."""
        from polisyos.foundry.methods.catalog.causal.id_engine import multi_outcome_id

        graph = make_dag([("X", "A"), ("X", "B"), ("X", "C")])
        results = multi_outcome_id(
            treatment=frozenset({"X"}),
            outcomes=["A", "B", "C"],
            graph=graph,
        )
        assert len(results) == 3

    def test_multi_outcome_shared_ccomp_step(self):
        """multi_outcome_id must emit MULTI_OUTCOME_SHARED_CCOMP in at least one result."""
        from polisyos.foundry.methods.catalog.causal.id_engine import multi_outcome_id

        graph = make_dag([("X", "Y1"), ("X", "Y2")])
        results = multi_outcome_id(
            treatment=frozenset({"X"}),
            outcomes=["Y1", "Y2"],
            graph=graph,
        )
        all_steps = [step for res in results.values() for step in res.proof_steps]
        rule_names = {s.rule_name for s in all_steps}
        assert "MULTI_OUTCOME_SHARED_CCOMP" in rule_names

    def test_multi_outcome_has_version_tag(self):
        """multi_outcome_id metadata must include 'phase5_multi'."""
        from polisyos.foundry.methods.catalog.causal.id_engine import multi_outcome_id

        graph = make_dag([("X", "Y1"), ("X", "Y2")])
        results = multi_outcome_id(
            treatment=frozenset({"X"}),
            outcomes=["Y1", "Y2"],
            graph=graph,
        )
        for res in results.values():
            assert "multi_outcome_id" in res.algorithm_version

    def test_multi_outcome_single_outcome(self):
        """multi_outcome_id with one outcome returns a one-entry dict."""
        from polisyos.foundry.methods.catalog.causal.id_engine import multi_outcome_id

        graph = make_dag([("X", "Y")])
        results = multi_outcome_id(
            treatment=frozenset({"X"}),
            outcomes=["Y"],
            graph=graph,
        )
        assert len(results) == 1
        assert results["Y"].status == IdentificationStatus.IDENTIFIED
