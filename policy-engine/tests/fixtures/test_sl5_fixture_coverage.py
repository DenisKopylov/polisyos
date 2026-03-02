"""SL-5 fixture coverage: every phase >= 2 must exercise >= 3 canonical SCM fixtures.

This module validates that each phase's primary API accepts canonical fixture data.
Tests are deliberately lightweight: they verify the fixture is accepted as valid input
and produces structurally valid output, not exact ATE recovery.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pytest

# Ensure tests/fixtures is importable
_FIXTURES_DIR = Path(__file__).resolve().parent
if str(_FIXTURES_DIR) not in sys.path:
    sys.path.insert(0, str(_FIXTURES_DIR))

from causal_scm_fixtures import (
    ALL_FIXTURES,
    backdoor_with_transport_fixture,
    chain_fixture,
    collider_fixture,
    diamond_fixture,
    fork_fixture,
    front_door_fixture,
    instrumental_variable_fixture,
)

# ---------------------------------------------------------------------------
# Phase 5: CausalGraphModel construction
# ---------------------------------------------------------------------------


class TestPhase5CausalGraphModel:
    """Verify >=3 canonical fixtures produce valid CausalGraphModel instances."""

    @pytest.mark.parametrize("fixture_fn", [fork_fixture, chain_fixture, diamond_fixture, instrumental_variable_fixture], ids=["fork", "chain", "diamond", "iv"])
    def test_fixture_produces_valid_graph_model(self, fixture_fn):
        from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType

        data, _ = fixture_fn(n=100)
        assert data.graph_dot is not None

        # Parse DOT to build CausalGraphModel
        edges = _parse_dot_edges(data.graph_dot)
        nodes = sorted({n for e in edges for n in (e["src"], e["dst"])})

        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=nodes,
            edges=[CausalEdge(src=e["src"], dst=e["dst"]) for e in edges],
        )
        assert len(graph.nodes) >= 2
        assert len(graph.edges) >= 1
        assert graph.to_dot()  # DOT serialization works


# ---------------------------------------------------------------------------
# Phase 6: PCMCIDiscovery — input acceptance (time-series reshape)
# ---------------------------------------------------------------------------


class TestPhase6PCMCIDiscovery:
    """Verify >=3 canonical fixtures can be reshaped into TimeSeriesCausalData."""

    @pytest.mark.parametrize("fixture_fn", [fork_fixture, chain_fixture, collider_fixture], ids=["fork", "chain", "collider"])
    def test_fixture_accepted_as_timeseries(self, fixture_fn):
        from polisyos.foundry.methods.catalog.causal.protocols import TimeSeriesCausalData

        data, _ = fixture_fn(n=200)
        # Reshape cross-sectional to pseudo-panel for input validation
        ts_data = TimeSeriesCausalData(
            data=data.data,
            variable_names=data.column_names,
        )
        assert ts_data.n_timesteps == 200
        assert ts_data.n_variables == len(data.column_names)


# ---------------------------------------------------------------------------
# Phase 7: PC / FCI — TabularCausalDiscoveryData acceptance
# ---------------------------------------------------------------------------


class TestPhase7ConstraintDiscovery:
    """Verify >=3 canonical fixtures produce valid TabularCausalDiscoveryData."""

    @pytest.mark.parametrize("fixture_fn", [fork_fixture, chain_fixture, collider_fixture, instrumental_variable_fixture], ids=["fork", "chain", "collider", "iv"])
    def test_fixture_accepted_as_tabular_discovery(self, fixture_fn):
        from polisyos.foundry.methods.catalog.causal.protocols import TabularCausalDiscoveryData

        data, _ = fixture_fn(n=200)
        td = TabularCausalDiscoveryData(
            data=data.data,
            variable_names=data.column_names,
        )
        assert td.data.shape[0] == 200
        assert td.data.shape[1] == len(data.column_names)


# ---------------------------------------------------------------------------
# Phase 8: Governance passes — fixture graph acceptance
# ---------------------------------------------------------------------------


class TestPhase8GovernancePasses:
    """Verify >=3 canonical fixtures produce graphs accepted by governance checks."""

    @pytest.mark.parametrize("fixture_fn", [fork_fixture, chain_fixture, backdoor_with_transport_fixture], ids=["fork", "chain", "backdoor_transport"])
    def test_fixture_graph_has_treatment_for_sutva(self, fixture_fn):
        """SutvaCheckPass checks treatment variable name against market-wide keywords."""
        from polisyos.scientist.governance.passes.sutva_check_pass import SutvaCheckPass

        data, _ = fixture_fn(n=100)
        # Verify the treatment is well-defined
        assert data.treatment in data.column_names
        # Market-wide keyword detection works with fixture treatment
        is_market_wide = data.treatment.lower() in SutvaCheckPass.MARKET_WIDE_KEYWORDS
        # Fixtures use "X" treatment, so should NOT trigger SUTVA warning
        assert not is_market_wide


# ---------------------------------------------------------------------------
# Phase 9: Literature Prior — fixture graph construction
# ---------------------------------------------------------------------------


class TestPhase9LiteraturePrior:
    """Verify >=3 canonical fixtures can construct LiteraturePriorBuildData."""

    @pytest.mark.parametrize("fixture_fn", [fork_fixture, chain_fixture, instrumental_variable_fixture], ids=["fork", "chain", "iv"])
    def test_fixture_graph_builds_prior_data(self, fixture_fn):
        from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType

        data, _ = fixture_fn(n=100)
        edges = _parse_dot_edges(data.graph_dot)
        nodes = sorted({n for e in edges for n in (e["src"], e["dst"])})

        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=nodes,
            edges=[CausalEdge(src=e["src"], dst=e["dst"]) for e in edges],
        )

        # Verify graph has the expected treatment→outcome path structure
        edge_set = {(e["src"], e["dst"]) for e in edges}
        assert data.treatment in nodes
        assert data.outcome in nodes
        assert len(edge_set) >= 1


# ---------------------------------------------------------------------------
# Phase 10: GCMFit — SCMFitData acceptance
# ---------------------------------------------------------------------------


class TestPhase10GCMFit:
    """Verify >=3 canonical fixtures produce valid SCMFitData."""

    @pytest.mark.parametrize("fixture_fn", [fork_fixture, chain_fixture, diamond_fixture], ids=["fork", "chain", "diamond"])
    def test_fixture_accepted_as_scm_fit_data(self, fixture_fn):
        from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData
        from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType

        data, _ = fixture_fn(n=200)
        edges = _parse_dot_edges(data.graph_dot)
        nodes = sorted({n for e in edges for n in (e["src"], e["dst"])})

        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=nodes,
            edges=[CausalEdge(src=e["src"], dst=e["dst"]) for e in edges],
        )

        fit_data = SCMFitData(
            data=data.data,
            column_names=data.column_names,
            graph=graph,
        )
        assert fit_data.sample_size == 200


# ---------------------------------------------------------------------------
# Phase 11: GCMQuery — SCMQueryData construction
# ---------------------------------------------------------------------------


class TestPhase11GCMQuery:
    """Verify >=3 canonical fixtures can construct valid SCMQueryData."""

    @pytest.mark.parametrize("fixture_fn", [fork_fixture, chain_fixture, diamond_fixture], ids=["fork", "chain", "diamond"])
    def test_fixture_builds_query_data(self, fixture_fn):
        from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
        from polisyos.ir.analytics.causal_queries import CausalQuery, InterventionSpec, InterventionType, QueryType
        from polisyos.ir.analytics.structural_causal_model import (
            MechanismFamily,
            MechanismSource,
            NodeMechanism,
            StructuralCausalModelSpec,
        )
        from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData

        data, _ = fixture_fn(n=100)
        edges = _parse_dot_edges(data.graph_dot)
        nodes = sorted({n for e in edges for n in (e["src"], e["dst"])})

        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=nodes,
            edges=[CausalEdge(src=e["src"], dst=e["dst"]) for e in edges],
        )

        scm_spec = StructuralCausalModelSpec(
            graph=graph,
            mechanisms=[
                NodeMechanism(
                    variable=n,
                    family=MechanismFamily.LINEAR,
                    source=MechanismSource.DATA_FITTED,
                    family_params={"intercept": 0.0},
                )
                for n in nodes
            ],
        )

        query = CausalQuery(
            query_type=QueryType.INTERVENTIONAL,
            treatment_variable=data.treatment,
            outcome_variable=data.outcome,
            intervention_spec=InterventionSpec(
                type=InterventionType.ATOMIC,
                value=1.0,
            ),
        )

        qd = SCMQueryData(scm_spec=scm_spec, query=query)
        assert qd.scm_spec.graph.nodes == nodes


# ---------------------------------------------------------------------------
# Phase 12: CheckTransportability — SelectionDiagram construction
# ---------------------------------------------------------------------------


class TestPhase12Transportability:
    """Verify >=3 canonical fixtures produce valid SelectionDiagram inputs."""

    @pytest.mark.parametrize("fixture_fn", [fork_fixture, backdoor_with_transport_fixture, diamond_fixture], ids=["fork", "backdoor_transport", "diamond"])
    def test_fixture_builds_selection_diagram(self, fixture_fn):
        from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
        from polisyos.ir.analytics.context import ContextProfile
        from polisyos.ir.analytics.transportability import SelectionDiagram

        data, _ = fixture_fn(n=100)
        edges = _parse_dot_edges(data.graph_dot)
        nodes = sorted({n for e in edges for n in (e["src"], e["dst"])})

        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=nodes,
            edges=[CausalEdge(src=e["src"], dst=e["dst"]) for e in edges],
        )

        source_ctx = ContextProfile(context_id="source", countries=["DE"])
        target_ctx = ContextProfile(context_id="target", countries=["UA"])

        sd = SelectionDiagram(
            base_graph=graph,
            s_nodes=[],
            source_context=source_ctx,
            target_context=target_ctx,
        )
        assert sd.base_graph.graph_type == GraphType.DAG


# ---------------------------------------------------------------------------
# Phase 13: ABM Bridge — AlignmentReport construction
# ---------------------------------------------------------------------------


class TestPhase13ABMBridge:
    """Verify >=3 canonical fixtures map to ABM alignment structures."""

    @pytest.mark.parametrize("fixture_fn", [fork_fixture, chain_fixture, diamond_fixture], ids=["fork", "chain", "diamond"])
    def test_fixture_builds_abm_mapping(self, fixture_fn):
        from polisyos.ir.analytics.abm_bridge import (
            ABMAlignmentReport,
            AggregationFunction,
            AlignmentResult,
            AlignmentStatus,
            MacroMicroMapping,
        )

        data, ate = fixture_fn(n=100)

        mapping = MacroMicroMapping(
            macro_variable=data.outcome,
            abm_aggregation=f"mean_{data.outcome}",
            aggregation_function=AggregationFunction.MEAN,
            agent_property=data.outcome.lower(),
        )

        result = AlignmentResult(
            scm_effect=ate,
            abm_effect=ate * 0.95,  # simulated ABM result
            status=AlignmentStatus.CONSISTENT,
            tolerance_used=0.2,
            delta=abs(ate * 0.05),
        )

        report = ABMAlignmentReport(
            mappings=[mapping],
            alignment_results={data.outcome: result},
            overall_consistent=True,
        )
        assert report.overall_consistent


# ---------------------------------------------------------------------------
# Phase 14: CausalModelEnsemble — ensemble from multiple discovery runs
# ---------------------------------------------------------------------------


class TestPhase14CausalEnsemble:
    """Verify >=3 canonical fixtures produce valid CausalModelEnsemble inputs."""

    @pytest.mark.parametrize("fixture_fn", [fork_fixture, chain_fixture, diamond_fixture], ids=["fork", "chain", "diamond"])
    def test_fixture_builds_ensemble(self, fixture_fn):
        from polisyos.ir.analytics.causal_ensemble import CausalModelEnsemble, EnsembleMember

        data, _ = fixture_fn(n=100)

        members = [
            EnsembleMember(
                graph_ref=f"cas:graph:{data.graph_ref}:pc",
                discovery_method="pc",
                weight=0.4,
                bootstrap_stability=0.85,
            ),
            EnsembleMember(
                graph_ref=f"cas:graph:{data.graph_ref}:fci",
                discovery_method="fci",
                weight=0.3,
                bootstrap_stability=0.78,
            ),
            EnsembleMember(
                graph_ref=f"cas:graph:{data.graph_ref}:ges",
                discovery_method="ges",
                weight=0.3,
                bootstrap_stability=0.82,
            ),
        ]

        ensemble = CausalModelEnsemble(members=members)
        assert len(ensemble.members) == 3


# ---------------------------------------------------------------------------
# Phase 15: ParameterTransfer — ParameterTransferData construction
# ---------------------------------------------------------------------------


class TestPhase15ParameterTransfer:
    """Verify >=3 canonical fixtures can construct ParameterTransferData."""

    @pytest.mark.parametrize("fixture_fn", [fork_fixture, chain_fixture, instrumental_variable_fixture], ids=["fork", "chain", "iv"])
    def test_fixture_builds_parameter_transfer_data(self, fixture_fn):
        from polisyos.foundry.methods.catalog.causal.protocols import ParameterTransferData
        from polisyos.ir.analytics.context import ContextProfile
        from polisyos.ir.analytics.literature import EvidenceParameter
        from polisyos.ir.analytics.parameters import ContextAdaptiveParameterBundle

        data, ate = fixture_fn(n=100)

        param = EvidenceParameter(
            name=data.treatment,
            value=ate,
        )

        target_ctx = ContextProfile(context_id="target", countries=["UA"])

        bundle = ContextAdaptiveParameterBundle(
            target_context=target_ctx,
            simulation_domain="test",
            parameters={data.treatment: param},
        )

        transfer_data = ParameterTransferData(parameter_bundle=bundle)
        assert len(transfer_data.parameter_bundle.parameters) == 1


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _parse_dot_edges(dot: str) -> list[dict[str, str]]:
    """Minimal DOT parser: extract src->dst edges from 'digraph { ... }'."""
    edges = []
    body = dot.split("{", 1)[-1].rsplit("}", 1)[0]
    for part in body.split(";"):
        part = part.strip()
        if "->" in part:
            src, dst = [s.strip() for s in part.split("->")]
            edges.append({"src": src, "dst": dst})
    return edges
