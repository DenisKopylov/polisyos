from __future__ import annotations

import pytest

from polisyos.data_forge.domains.legal.source_relation import (
    LegalSourceRelationVerificationMissingError,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import TransportabilityCandidateRequestV1
from polisyos.scientist.nodes.builtins.causal import resolve_transport
from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
    TransportabilityResolutionLoop,
    _resolve_conditional_transport_resource_profile,
)
from polisyos.scientist.nodes.builtins.causal.transport_resolution_inputs import (
    _NullDatasetRegistry,
    _NullSKG,
)


def _loop() -> TransportabilityResolutionLoop:
    return TransportabilityResolutionLoop(
        dataset_registry=_NullDatasetRegistry(),
        legal_kg_db_path=None,
        skg_query=_NullSKG(),
    )


def _inputs() -> tuple[ContextProfile, ContextProfile, CausalGraphModel]:
    source = ContextProfile(context_id="source")
    target = ContextProfile(context_id="target")
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["policy", "income"],
        edges=[CausalEdge(src="policy", dst="income")],
    )
    return source, target, graph


def test_unknown_candidate_profile_is_owner_refused_without_default_limits():
    request = TransportabilityCandidateRequestV1(
        profile_id="unregistered.profile",
        profile_revision="999",
        selection_identity="transport-candidate.standard.v1",
    )

    owner = _resolve_conditional_transport_resource_profile(request)

    assert owner["status"] == "refused"
    assert owner["reason_code"] == "conditional_transport_profile_unsupported"
    assert owner["effective_limits"] is None
    assert owner["effective_limit_units"] is None


def test_candidate_handler_runs_only_after_exact_legal_relation_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target, graph = _inputs()
    monkeypatch.setattr(
        resolve_transport,
        "_evaluate_legal_constraints",
        lambda **kwargs: (_ for _ in ()).throw(LegalSourceRelationVerificationMissingError()),
    )
    seen = []

    def preserve_refusal(refusal):
        seen.append(refusal)
        return refusal

    result = _loop().resolve(
        source_context=source,
        target_context=target,
        causal_graph=graph,
        query_treatment="policy",
        query_outcome="income",
        candidate_refusal_handler=preserve_refusal,
    )

    assert len(seen) == 1
    assert result == seen[0]
    assert result.status.value == "unsupported"
    assert result.transport_mode.value == "none"
    assert result.feasible is False
    assert result.base_confidence == 0.0
    assert result.final_confidence == 0.0
    assert result.transport_formula is None
    assert result.metadata["legal_source_relation_refusal"] == {
        "code": "legal_source_relation_verification_not_established",
        "status": "verification_missing",
    }


def test_candidate_handler_does_not_run_for_an_unrelated_legal_owner_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target, graph = _inputs()
    monkeypatch.setattr(
        resolve_transport,
        "_evaluate_legal_constraints",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("unrelated owner failure")),
    )
    seen = []

    with pytest.raises(RuntimeError, match="unrelated owner failure"):
        _loop().resolve(
            source_context=source,
            target_context=target,
            causal_graph=graph,
            query_treatment="policy",
            query_outcome="income",
            candidate_refusal_handler=seen.append,
        )

    assert seen == []
