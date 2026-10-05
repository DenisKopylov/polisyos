from __future__ import annotations

import pytest
from pydantic import ValidationError

import polisyos.scientist.methods.backtesting.composition_bridge as composition_bridge_module
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir.analytics.alignment_certification import AlignmentVerificationConfig
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    EdgeSource,
    GraphType,
)
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.cross_graph import SCMFragment, load_composition_certificate
from polisyos.ir.artifacts import normalize_artifact_ref
from polisyos.ir.registry.refs import CompositionCertificateRef
from polisyos.scientist.methods.backtesting.composition_bridge import (
    replay_fragment_composition_case,
)


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


def _proxy_replay_inputs():
    return {
        "fragments": [
            _fragment("gov_a", interface_variables=["RL.EST"], outputs=["RL.EST"]),
            _fragment("gov_b", interface_variables=["GE.EST"], inputs=["GE.EST"]),
        ],
        "fragment_graphs": {
            "gov_a": _graph(["tax", "RL.EST"], [_edge("tax", "RL.EST")]),
            "gov_b": _graph(["GE.EST", "wages"], [_edge("GE.EST", "wages")]),
        },
    }


def test_replay_core_refs_read_back_from_reopened_filesystem_store(monkeypatch, tmp_path):
    observed = []
    execute = composition_bridge_module.ReconcileCausalGraphNode.execute

    def _capture_native_outcome(self, ctx, state):
        outcome = execute(self, ctx, state)
        observed.append(outcome)
        return outcome

    monkeypatch.setattr(
        composition_bridge_module.ReconcileCausalGraphNode, "execute", _capture_native_outcome
    )
    root = tmp_path / "cas_readback"
    result = replay_fragment_composition_case(**_proxy_replay_inputs(), cas_root=str(root))
    outcome = observed[0]
    assert outcome.status == "ok"
    assert all(isinstance(ref, ArtifactRef) for ref in outcome.state.artifacts_index.values())
    assert all(result.persisted_artifacts.values())

    reopened = build_artifact_store(ArtifactStoreConfig(root=str(root)))
    for ref in outcome.state.artifacts_index.values():
        manifest = reopened.get_manifest(ref.artifact_id)
        assert manifest.kind == ref.kind
        assert manifest.media_type == ref.media_type
        assert reopened.get_bytes(ref.artifact_id)
    certificate = load_composition_certificate(
        ensure_ir_artifact_store(reopened),
        CompositionCertificateRef.model_validate(
            normalize_artifact_ref(outcome.state.artifacts_index["composition_certificate_ref"])
        ),
    )
    assert (
        composition_bridge_module.normalize_composition_certificate(certificate)
        == result.composition_certificate_signature
    )
    assert certificate.status == result.composition_status == "deferred"


@pytest.mark.parametrize(
    "ref_key",
    [
        "composition_certificate_ref",
        "alignment_report_ref",
        "interface_mapping_ref",
        "reconciled_causal_graph_ref",
        "composition_failure_card_bundle_ref",
    ],
)
@pytest.mark.parametrize(
    "mutation", [{"kind": "ir.wrong_artifact_kind"}, {"media_type": "text/plain"}]
)
def test_replay_rejects_mismatched_native_ref_contract(monkeypatch, tmp_path, ref_key, mutation):
    execute = composition_bridge_module.ReconcileCausalGraphNode.execute

    def _mutate_native_outcome(self, ctx, state):
        outcome = execute(self, ctx, state)
        assert outcome.status == "ok"
        ref = outcome.state.artifacts_index[ref_key]
        assert isinstance(ref, ArtifactRef)
        outcome.state.artifacts_index[ref_key] = ref.model_copy(update=mutation)
        return outcome

    monkeypatch.setattr(
        composition_bridge_module.ReconcileCausalGraphNode, "execute", _mutate_native_outcome
    )
    with pytest.raises(ValidationError) as raised:
        replay_fragment_composition_case(
            **_proxy_replay_inputs(), cas_root=str(tmp_path / "cas_mismatched_ref")
        )
    assert {error["type"] for error in raised.value.errors()} == {"literal_error"}


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
    captured_contexts = []
    context_type = composition_bridge_module.ClaimCapableExecutionContext

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

    def _claim_context(*args, **kwargs):
        context = context_type(*args, **kwargs)
        captured_contexts.append(context)
        return context

    monkeypatch.setattr(
        composition_bridge_module,
        "_default_composition_store_factory",
        _unexpected_default,
    )
    monkeypatch.setattr(
        composition_bridge_module,
        "ClaimCapableExecutionContext",
        _claim_context,
    )

    result = replay_fragment_composition_case(
        fragments=fragments,
        fragment_graphs=fragment_graphs,
        precompute_alignment=True,
        cas_root=str(tmp_path / "cas_injected"),
        store_factory=_store_factory,
    )

    assert captured_roots == [tmp_path / "cas_injected"]
    assert len(captured_contexts) == 1
    assert captured_contexts[0].claim_ledger_owner is not None
    assert result.persisted_artifacts["composition_certificate"] is True
