"""Tests for SigmaVariable, SelectionDiagramBuilder, SourceDomainSpec, MultiSourceSelectionDiagram."""
import pytest
from pydantic import ValidationError

from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import (
    MultiSourceSelectionDiagram,
    SelectionDiagram,
    SelectionDiagramBuilder,
    SigmaVariable,
    SNode,
    SNodeOrigin,
    SNodeRole,
    SourceDomainSpec,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dag(edges: list[tuple[str, str]]) -> CausalGraphModel:
    nodes = sorted({n for e in edges for n in e})
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[
            CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for s, d in edges
        ],
    )


def _snode(var: str, severity: str = "medium") -> SNode:
    return SNode(
        target_variable=var,
        context_dimension="programmatic",
        source_value=0.0,
        target_value=1.0,
        delta=1.0,
        severity=severity,
    )


# ---------------------------------------------------------------------------
# SigmaVariable
# ---------------------------------------------------------------------------


class TestSigmaVariable:
    def test_basic_creation(self):
        sv = SigmaVariable(variable_name="X", node_name="S_X")
        assert sv.variable_name == "X"
        assert sv.node_name == "S_X"
        assert sv.is_resolved is False
        assert sv.resolving_adjustment_set == ()
        assert sv.origin == SNodeOrigin.CONTEXT_DELTA

    def test_from_s_node(self):
        sn = _snode("income")
        sv = SigmaVariable.from_s_node(sn)
        assert sv.variable_name == "income"
        assert sv.node_name == "S_income"
        assert sv.origin == SNodeOrigin.CONTEXT_DELTA

    def test_from_s_node_origin_preserved(self):
        sn = SNode(
            target_variable="T",
            context_dimension="legal",
            source_value="old_rule",
            target_value="new_rule",
            delta=1.0,
            severity="high",
            origin=SNodeOrigin.LEGAL,
        )
        sv = SigmaVariable.from_s_node(sn)
        assert sv.origin == SNodeOrigin.LEGAL

    def test_frozen_rejects_mutation(self):
        sv = SigmaVariable(variable_name="X", node_name="S_X")
        with pytest.raises((TypeError, Exception)):
            sv.variable_name = "Y"

    def test_extra_fields_forbidden(self):
        with pytest.raises((ValidationError, Exception)):
            SigmaVariable(variable_name="X", node_name="S_X", unexpected="oops")

    def test_resolved_variant(self):
        sv = SigmaVariable(
            variable_name="Z",
            node_name="S_Z",
            is_resolved=True,
            resolving_adjustment_set=("W", "V"),
        )
        assert sv.is_resolved is True
        assert "W" in sv.resolving_adjustment_set
        assert "V" in sv.resolving_adjustment_set

    def test_round_trip_json(self):
        sv = SigmaVariable(variable_name="X", node_name="S_X", is_resolved=True)
        data = sv.model_dump(mode="json")
        restored = SigmaVariable.model_validate(data)
        assert restored.variable_name == "X"
        assert restored.is_resolved is True


# ---------------------------------------------------------------------------
# SelectionDiagramBuilder
# ---------------------------------------------------------------------------


class TestSelectionDiagramBuilder:
    def test_empty_builder_returns_diagram(self):
        graph = _dag([("X", "Y")])
        diagram = SelectionDiagramBuilder(graph).build()
        assert isinstance(diagram, SelectionDiagram)
        assert diagram.s_nodes == []

    def test_add_single_sigma_variable(self):
        graph = _dag([("X", "Y")])
        diagram = (
            SelectionDiagramBuilder(graph)
            .add_sigma_variable("X")
            .build()
        )
        assert len(diagram.s_nodes) == 1
        assert diagram.s_nodes[0].target_variable == "X"

    def test_add_multiple_sigma_variables(self):
        graph = _dag([("X", "Y"), ("Z", "Y")])
        diagram = (
            SelectionDiagramBuilder(graph)
            .add_sigma_variable("X")
            .add_sigma_variable("Z")
            .build()
        )
        var_names = [sn.target_variable for sn in diagram.s_nodes]
        assert "X" in var_names
        assert "Z" in var_names
        assert len(var_names) == 2

    def test_deduplication(self):
        graph = _dag([("X", "Y")])
        diagram = (
            SelectionDiagramBuilder(graph)
            .add_sigma_variable("X")
            .add_sigma_variable("X")  # duplicate
            .build()
        )
        assert len(diagram.s_nodes) == 1

    def test_severity_high(self):
        graph = _dag([("X", "Y")])
        diagram = (
            SelectionDiagramBuilder(graph)
            .add_sigma_variable("X", severity="high")
            .build()
        )
        assert diagram.s_nodes[0].severity == "high"

    def test_role_mediator(self):
        graph = _dag([("X", "M"), ("M", "Y")])
        diagram = (
            SelectionDiagramBuilder(graph)
            .add_sigma_variable("M", role=SNodeRole.MEDIATOR)
            .build()
        )
        assert diagram.s_nodes[0].role == SNodeRole.MEDIATOR

    def test_build_without_context_uses_defaults(self):
        graph = _dag([("X", "Y")])
        diagram = SelectionDiagramBuilder(graph).add_sigma_variable("X").build()
        assert isinstance(diagram.source_context, ContextProfile)
        assert isinstance(diagram.target_context, ContextProfile)

    def test_build_with_explicit_contexts(self):
        graph = _dag([("X", "Y")])
        sc = ContextProfile(context_id="DE")
        tc = ContextProfile(context_id="FR")
        diagram = (
            SelectionDiagramBuilder(graph)
            .add_sigma_variable("X")
            .build(source_context=sc, target_context=tc)
        )
        assert diagram.source_context.context_id == "DE"
        assert diagram.target_context.context_id == "FR"

    def test_sigma_variables_property(self):
        graph = _dag([("X", "Y")])
        builder = SelectionDiagramBuilder(graph).add_sigma_variable("X")
        svs = builder.sigma_variables
        assert len(svs) == 1
        assert isinstance(svs[0], SigmaVariable)
        assert svs[0].variable_name == "X"

    def test_chaining_returns_builder(self):
        graph = _dag([("X", "Y")])
        builder = SelectionDiagramBuilder(graph)
        result = builder.add_sigma_variable("X")
        assert result is builder

    def test_base_graph_preserved(self):
        graph = _dag([("X", "Y")])
        diagram = SelectionDiagramBuilder(graph).add_sigma_variable("X").build()
        assert diagram.base_graph is graph


# ---------------------------------------------------------------------------
# SourceDomainSpec
# ---------------------------------------------------------------------------


class TestSourceDomainSpec:
    def test_minimal_creation(self):
        spec = SourceDomainSpec(domain_id="study_us")
        assert spec.domain_id == "study_us"
        assert spec.s_nodes == ()
        assert spec.z_interventions == ()
        assert spec.dataset_ref is None
        assert spec.source_context is None

    def test_full_creation(self):
        sn = _snode("X")
        spec = SourceDomainSpec(
            domain_id="rct_2020",
            s_nodes=(sn,),
            z_interventions=("Z",),
            dataset_ref="ds_rct",
        )
        assert spec.domain_id == "rct_2020"
        assert len(spec.s_nodes) == 1
        assert "Z" in spec.z_interventions
        assert spec.dataset_ref == "ds_rct"

    def test_frozen_rejects_mutation(self):
        spec = SourceDomainSpec(domain_id="test")
        with pytest.raises((TypeError, Exception)):
            spec.domain_id = "changed"

    def test_extra_fields_forbidden(self):
        with pytest.raises((ValidationError, Exception)):
            SourceDomainSpec(domain_id="d", unknown_field="oops")

    def test_to_selection_diagram(self):
        graph = _dag([("X", "Y")])
        sn = _snode("X")
        spec = SourceDomainSpec(domain_id="dom1", s_nodes=(sn,))
        diagram = spec.to_selection_diagram(graph)
        assert isinstance(diagram, SelectionDiagram)
        assert len(diagram.s_nodes) == 1
        assert diagram.s_nodes[0].target_variable == "X"
        assert diagram.base_graph is graph

    def test_round_trip_json(self):
        spec = SourceDomainSpec(domain_id="ds1", z_interventions=("A", "B"))
        data = spec.model_dump(mode="json")
        restored = SourceDomainSpec.model_validate(data)
        assert restored.domain_id == "ds1"
        assert "A" in restored.z_interventions


# ---------------------------------------------------------------------------
# MultiSourceSelectionDiagram
# ---------------------------------------------------------------------------


class TestMultiSourceSelectionDiagram:
    def _make_mssd(self) -> MultiSourceSelectionDiagram:
        graph = _dag([("X", "Y"), ("Z", "Y")])
        sn_x = _snode("X")
        sn_z = _snode("Z")
        d1 = SourceDomainSpec(domain_id="dom1", s_nodes=(sn_x,))
        d2 = SourceDomainSpec(domain_id="dom2", s_nodes=(sn_z,), z_interventions=("Z",))
        return MultiSourceSelectionDiagram(
            base_graph=graph,
            domains=(d1, d2),
            target_context=ContextProfile(),
        )

    def test_basic_creation(self):
        mssd = self._make_mssd()
        assert len(mssd.domains) == 2
        assert mssd.domains[0].domain_id == "dom1"
        assert mssd.domains[1].domain_id == "dom2"

    def test_to_selection_diagram_known_domain(self):
        mssd = self._make_mssd()
        diag = mssd.to_selection_diagram("dom1")
        assert isinstance(diag, SelectionDiagram)
        assert diag.s_nodes[0].target_variable == "X"

    def test_to_selection_diagram_second_domain(self):
        mssd = self._make_mssd()
        diag = mssd.to_selection_diagram("dom2")
        assert diag.s_nodes[0].target_variable == "Z"

    def test_to_selection_diagram_unknown_domain_raises(self):
        mssd = self._make_mssd()
        with pytest.raises(KeyError):
            mssd.to_selection_diagram("nonexistent")

    def test_to_source_domains_returns_list(self):
        mssd = self._make_mssd()
        source_domains = mssd.to_source_domains()
        assert len(source_domains) == 2
        ids = [d.domain_id for d in source_domains]
        assert "dom1" in ids
        assert "dom2" in ids

    def test_frozen_rejects_mutation(self):
        mssd = self._make_mssd()
        with pytest.raises((TypeError, Exception)):
            mssd.domains = ()

    def test_extra_fields_forbidden(self):
        graph = _dag([("X", "Y")])
        with pytest.raises((ValidationError, Exception)):
            MultiSourceSelectionDiagram(
                base_graph=graph,
                target_context=ContextProfile(),
                unexpected="oops",
            )

    def test_empty_domains(self):
        graph = _dag([("X", "Y")])
        mssd = MultiSourceSelectionDiagram(
            base_graph=graph,
            domains=(),
            target_context=ContextProfile(),
        )
        assert mssd.to_source_domains() == []

    def test_round_trip_json(self):
        mssd = self._make_mssd()
        data = mssd.model_dump(mode="json")
        restored = MultiSourceSelectionDiagram.model_validate(data)
        assert len(restored.domains) == 2
        assert restored.domains[0].domain_id == "dom1"
