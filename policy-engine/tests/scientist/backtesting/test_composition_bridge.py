from __future__ import annotations

import polisyos.scientist.backtesting.composition_bridge as composition_bridge_module
from polisyos.ir.analytics.alignment_certification import AlignmentVerificationConfig
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
)
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.cross_graph import SCMFragment
from polisyos.scientist.backtesting.composition_bridge import replay_fragment_composition_case


def _edge(src: str, dst: str, *, bidirected: bool = False) -> CausalEdge:
    return CausalEdge(
        src=src,
        dst=dst,
        mark_src=EdgeMark.ARROW if bidirected else EdgeMark.TAIL,
        mark_dst=EdgeMark.ARROW,
        sources=[EdgeSource.DATA],
        combined_confidence=0.8,
    )


def _graph(
    nodes: list[str], edges: list[CausalEdge], *, graph_type: GraphType = GraphType.DAG
) -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=graph_type,
        nodes=nodes,
        edges=edges,
        discovery_method="test_fixture",
    )


def _fragment(
    fragment_id: str,
    *,
    interface_variables: list[str],
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
) -> SCMFragment:
    return SCMFragment(
        fragment_id=fragment_id,
        graph_ref=f"artifact:graph:{fragment_id}",
        semantic_namespace=f"policy.{fragment_id}",
        interface_variables=interface_variables,
        exposed_inputs=list(inputs or []),
        exposed_outputs=list(outputs or []),
        variable_definitions={name: name.replace("_", " ").title() for name in interface_variables},
        variable_units=dict.fromkeys(interface_variables, "unitless"),
    )


def test_replay_fragment_composition_case_returns_persisted_artifacts_and_query_status(
    tmp_path,
) -> None:
    fragments = [
        _fragment(
            "core",
            interface_variables=["employment_rate", "wages"],
            outputs=["employment_rate", "wages"],
        ),
        _fragment(
            "training",
            interface_variables=["employment_rate", "wages"],
            inputs=["employment_rate", "wages"],
        ),
    ]
    fragment_graphs = {
        "core": _graph(
            ["schooling", "employment_rate", "wages"],
            [
                _edge("schooling", "employment_rate"),
                _edge("schooling", "wages"),
                _edge("employment_rate", "wages"),
            ],
        ),
        "training": _graph(
            ["employment_rate", "wages", "training_slots"],
            [_edge("employment_rate", "training_slots")],
        ),
    }
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="employment_rate",
        treatment_value=1.0,
        outcome_variable="wages",
        condition={"schooling": 1.0},
    )

    result = replay_fragment_composition_case(
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        queries=[query],
        precompute_alignment=True,
        cas_root=str(tmp_path / "cas"),
    )

    assert result.node_status == "ok"
    assert result.composition_status == "preserved"
    assert result.composition_structure_status == "valid"
    assert result.composition_review_status == "clear"
    assert result.needs_expert_review is False
    assert result.persisted_artifacts["composition_certificate"] is True
    assert result.persisted_artifacts["composed_graph"] is True
    assert result.alignment_signature is not None
    assert result.interface_mapping_signature is not None
    assert result.composition_certificate_signature is not None
    assert result.composed_graph_signature is not None
    assert set(result.query_statuses.values()) == {"preserved"}
    assert set(result.query_reasons.values()) == {"evaluated"}


def test_replay_fragment_composition_case_surfaces_deferred_proxy_review(tmp_path) -> None:
    fragments = [
        _fragment("gov_a", interface_variables=["RL.EST"], outputs=["RL.EST"]),
        _fragment("gov_b", interface_variables=["GE.EST"], inputs=["GE.EST"]),
    ]
    fragment_graphs = {
        "gov_a": _graph(["tax", "RL.EST"], [_edge("tax", "RL.EST")]),
        "gov_b": _graph(["GE.EST", "wages"], [_edge("GE.EST", "wages")]),
    }

    result = replay_fragment_composition_case(
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        alignment_verification_config=AlignmentVerificationConfig(),
        precompute_alignment=False,
        cas_root=str(tmp_path / "cas_proxy"),
    )

    assert result.node_status == "ok"
    assert result.composition_status == "deferred"
    assert result.composition_structure_status == "valid"
    assert result.composition_review_status == "pending_review"
    assert result.needs_expert_review is True
    assert result.persisted_artifacts["failure_card_bundle"] is True
    assert {card["failure_type"] for card in result.failure_cards} >= {
        "proxy_alignment_pending_review"
    }


def test_replay_fragment_composition_case_detects_disconnected_topology(tmp_path) -> None:
    fragments = [
        _fragment("a", interface_variables=["employment_rate"], outputs=["employment_rate"]),
        _fragment("b", interface_variables=["employment_rate"], inputs=["employment_rate"]),
        _fragment("c", interface_variables=["hospital_occupancy"], outputs=["hospital_occupancy"]),
    ]
    fragment_graphs = {
        "a": _graph(["employment_rate"], []),
        "b": _graph(["employment_rate", "wages"], [_edge("employment_rate", "wages")]),
        "c": _graph(["hospital_occupancy"], []),
    }

    result = replay_fragment_composition_case(
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        precompute_alignment=True,
        cas_root=str(tmp_path / "cas_disconnected"),
    )

    assert result.node_status == "ok"
    assert result.composition_status == "broken"
    assert result.composition_structure_status == "invalid"
    assert result.composition_review_status == "clear"
    assert {card["failure_type"] for card in result.failure_cards} >= {
        "fragment_topology_disconnected"
    }


def test_replay_fragment_composition_case_accepts_injected_store_factory(
    monkeypatch,
    tmp_path,
) -> None:
    fragments = [
        _fragment("core", interface_variables=["employment_rate"], outputs=["employment_rate"]),
        _fragment("training", interface_variables=["employment_rate"], inputs=["employment_rate"]),
    ]
    fragment_graphs = {
        "core": _graph(["employment_rate"], []),
        "training": _graph(["employment_rate", "wages"], [_edge("employment_rate", "wages")]),
    }
    captured_roots = []

    def _unexpected_default(root):
        del root
        raise AssertionError("default composition store factory should not run")

    def _store_factory(root):
        captured_roots.append(root)
        from polisyos.core.artifacts.backends.config import (
            ArtifactStoreConfig,
            build_artifact_store,
        )

        return build_artifact_store(ArtifactStoreConfig(root=str(root)))

    monkeypatch.setattr(
        composition_bridge_module,
        "_default_composition_store_factory",
        _unexpected_default,
    )

    result = replay_fragment_composition_case(
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        precompute_alignment=True,
        cas_root=str(tmp_path / "cas_injected"),
        store_factory=_store_factory,
    )

    assert captured_roots == [tmp_path / "cas_injected"]
    assert result.persisted_artifacts["composition_certificate"] is True
