"""First-execution source discovery reconciles exact CAS with native history."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest

from polisyos.core import artifacts


def _module():
    name = "polisyos.runtime.quality.epoch_transition_inputs"
    assert importlib.util.find_spec(name) is not None, "native transition source bridge missing"
    return importlib.import_module(name)


def test_source_resolution_uses_native_head_and_direct_predecessor(tmp_path: Path) -> None:
    module = _module()
    from tests.unit.runtime.quality.test_epoch_validity_cascade import _transition_history_fixture

    fixture = _transition_history_fixture(tmp_path)
    resolver = module.CanonicalEpochTransitionSourceResolver(
        artifacts=fixture.store, history=fixture.history
    )
    source = resolver.resolve_transition_source(
        requested_query_context_ref=fixture.current.requested_query_context_ref,
        authority_purpose="decision_validity",
    )
    assert source.previous_epoch_manifest_ref == fixture.previous_ref
    assert source.current_epoch_production_receipt_ref == fixture.current_receipt.receipt_ref


@pytest.mark.parametrize(
    "mutation", ["wrong_query", "stale_head", "corrupt_receipt", "ambiguous_receipt"]
)
def test_source_discovery_refuses_missing_corrupt_or_ambiguous_owner_basis(
    tmp_path: Path, mutation: str
) -> None:
    module = _module()
    from polisyos.runtime.quality import semantic_epoch
    from tests.unit.runtime.quality.test_epoch_validity_cascade import (
        _digest,
        _transition_history_fixture,
    )

    fixture = _transition_history_fixture(tmp_path)
    query = fixture.current.requested_query_context_ref
    if mutation == "wrong_query":
        query = _digest("unknown-query")
    elif mutation == "stale_head":
        query = fixture.previous.requested_query_context_ref
    elif mutation == "corrupt_receipt":
        fixture.store.put_bytes(
            b"fake same-kind receipt",
            artifacts.ArtifactWriteOptions(
                kind="epoch.production_receipt",
                media_type="application/vnd.polisyos.epoch-production-receipt+json",
            ),
        )
    else:
        alternate = semantic_epoch.SemanticEpochProductionReceipt.model_validate(
            fixture.current_receipt.model_dump(exclude={"receipt_ref", "receipt_content_hash"})
        ).model_copy(update={"status": "no_change"})
        semantic_epoch.persist_semantic_epoch_production_receipt(
            store=fixture.store, receipt=alternate
        )
    resolver = module.CanonicalEpochTransitionSourceResolver(
        artifacts=fixture.store, history=fixture.history
    )
    with pytest.raises(ValueError):
        resolver.resolve_transition_source(
            requested_query_context_ref=query, authority_purpose="decision_validity"
        )


def test_complete_monitor_census_retains_review_without_independent_owner_action(
    tmp_path: Path,
) -> None:
    module = _module()
    from polisyos.runtime.quality import epoch_validity_cascade as cascade
    from polisyos.scientist.governance.continuous.monitors import (
        GovernanceMonitorEvent,
        persist_governance_monitor_event,
    )
    from tests.unit.runtime.quality.test_epoch_transition_origin import _producer_fixture

    producer, _, _, fixture, _, kwargs = _producer_fixture(tmp_path)
    dependencies = producer._dependency_inventory.resolve_complete_epoch_dependencies(**kwargs)
    target = dependencies.target_refs[0]
    report_ref = fixture.store.put_bytes(
        b"isolated incident report",
        artifacts.ArtifactWriteOptions(kind="test.incident", media_type="application/octet-stream"),
    )
    monitor = persist_governance_monitor_event(
        fixture.store,
        GovernanceMonitorEvent.model_validate(
            {
                "event_id": "complete-census-incident",
                "decision_packet_ref": target,
                "event_type": "incident",
                "severity": "block",
                "reason": "needs owner review",
                "observed_epoch_ref": fixture.previous.epoch_ref,
                "perturbation": {"source_class": "incident", "incident_report_ref": report_ref},
            }
        ),
    )
    provider = module.CanonicalEpochPerturbationAdjudicationProvider(
        artifacts=fixture.store,
        dependency_inventory=producer._dependency_inventory,
    )
    events = provider.resolve_monitor_advisories(
        authority_purpose=kwargs["authority_purpose"],
        requested_query_context_ref=kwargs["requested_query_context_ref"],
    )
    assert tuple(row.event_ref for row in events) == (monitor.event_ref,)
    with pytest.raises(ValueError, match="native_perturbation_basis_not_established"):
        provider.resolve_complete_owner_adjudications(
            authority_purpose=kwargs["authority_purpose"],
            requested_query_context_ref=kwargs["requested_query_context_ref"],
        )
    vector = cascade.resolve_owner_target_dispositions(
        advisory_events=events,
        owner_dispositions=(),
        dependency_graph=dependencies.dependency_graph,
    )
    assert vector.rows[0].disposition == "review_required"
    fixture.store.put_bytes(
        b"corrupt same-kind event",
        artifacts.ArtifactWriteOptions(
            kind="scientist.governance_monitor_event", media_type="application/json"
        ),
    )
    with pytest.raises(ValueError):
        provider.resolve_monitor_advisories(
            authority_purpose=kwargs["authority_purpose"],
            requested_query_context_ref=kwargs["requested_query_context_ref"],
        )


def test_first_execution_bridge_requires_canonical_output_to_equal_request(tmp_path: Path) -> None:
    module = _module()
    from polisyos.runtime.quality import epoch_validity_cascade as cascade
    from tests.unit.runtime.quality.test_epoch_transition_origin import _producer_fixture
    from tests.unit.runtime.quality.test_epoch_validity_cascade import _ref

    producer, _, _, fixture, _, kwargs = _producer_fixture(tmp_path)
    result = producer.produce_and_persist(**kwargs)
    assert isinstance(result, cascade.PersistedEpochValidityTransition)
    called = []

    def factory(source):
        called.append(source)
        return producer

    bridge = module.EpochTransitionProductionBridge(
        source_resolver=module.CanonicalEpochTransitionSourceResolver(
            artifacts=fixture.store,
            history=fixture.history,
        ),
        producer_factory=factory,
    )
    accepted = bridge.produce_for_requested_transition(
        transition_artifact_ref=result.transition_artifact_ref,
        authority_purpose=kwargs["authority_purpose"],
        requested_query_context_ref=kwargs["requested_query_context_ref"],
    )
    assert accepted == result
    assert called[0].previous_epoch_manifest_ref == fixture.previous_ref
    refused = bridge.produce_for_requested_transition(
        transition_artifact_ref=_ref("wrong-output"),
        authority_purpose=kwargs["authority_purpose"],
        requested_query_context_ref=kwargs["requested_query_context_ref"],
    )
    assert isinstance(refused, cascade.EpochTransitionSigningNonReceipt)


@pytest.mark.parametrize("wrong_source", [False, True])
def test_native_semantic_delta_binds_exact_full_basis_edges_before_event_admission(
    tmp_path: Path,
    wrong_source: bool,
) -> None:
    module = _module()
    from polisyos.runtime.quality import epoch_validity_cascade as cascade
    from tests.unit.runtime.quality.test_epoch_validity_cascade import (
        _digest,
        _transition_history_fixture,
    )

    fixture = _transition_history_fixture(tmp_path)
    target = fixture.store.put_bytes(
        b"isolated full-basis dependency",
        artifacts.ArtifactWriteOptions(
            kind="test.issuance_basis", media_type="application/octet-stream"
        ),
    )
    recipe = fixture.store.put_bytes(
        b"isolated recipe binding",
        artifacts.ArtifactWriteOptions(kind="test.recipe", media_type="application/octet-stream"),
    )
    binding = cascade.bind_certificate_to_epoch(
        certificate_ref=target,
        certificate_content_hash=str(target.artifact_id),
        epoch=fixture.previous,
        input_certificate_refs=(fixture.previous_ref,),
        recipe=cascade.DerivationRecipeBinding(
            recipe_ref=recipe,
            recipe_content_hash=str(recipe.artifact_id),
            recipe_schema_profile_ref=_digest("isolated-profile"),
            input_roles=("semantic_basis",),
        ),
        canonical_producer_ref="isolated-test-owner",
        authority_purpose="decision_validity",
        native_coordinate_refs=(fixture.previous.valid_effect_coordinate_ref,),
        rule_schema_profile_refs=(_digest("isolated-schema"),),
    )
    edges = (
        cascade.EpochDependencyEdge(
            source_ref=fixture.current_ref if wrong_source else fixture.previous_ref,
            target_ref=target,
            relation="invalidates_issuance_basis",
            authority_purpose="decision_validity",
        ),
    )
    graph = cascade.EpochDependencyGraph(
        edges=edges,
        denominator_ref=cascade._semantic_hash(
            "polisyos.epoch.dependency-graph.v1", {"edges": edges}
        ),
    )
    receipt = cascade.EpochDependencyDenominatorReceipt(
        certificate_bindings=(binding,),
        dependency_graph=graph,
        target_refs=(target,),
        denominator_ref=cascade.epoch_dependency_outer_denominator_ref(
            certificate_bindings=(binding,), dependency_graph=graph
        ),
        predicate_class="independently_reconciled",
    )

    class IsolatedIssuanceInventory:
        """Controlled source for the delta algorithm, not an issuance-owner proof."""

        def resolve_complete_epoch_dependencies(self, *, previous_epoch_ref, authority_purpose):
            assert previous_epoch_ref == fixture.previous.epoch_ref
            assert authority_purpose == "decision_validity"
            return receipt

    sources = module.CanonicalEpochTransitionSourceResolver(
        artifacts=fixture.store, history=fixture.history
    )
    query = {
        "authority_purpose": "decision_validity",
        "requested_query_context_ref": fixture.current.requested_query_context_ref,
    }
    dependencies = module.CanonicalEpochDependencyDenominatorProvider(
        issuance_owner=IsolatedIssuanceInventory(),
        source=sources.resolve_transition_source(**query),
    )
    native = module.NativeEpochSemanticBasisDeltaProvider(
        artifacts=fixture.store,
        source_resolver=sources,
        dependency_inventory=dependencies,
    )
    if wrong_source:
        with pytest.raises(ValueError, match="full_basis_dependency_not_established"):
            native.produce_and_persist(**query)
        return
    delta_ref = native.produce_and_persist(**query)
    delta = native.resolve_exact(delta_ref=delta_ref)
    assert delta.affected_target_refs == (target,)
    assert delta.previous_semantic_basis_hash != delta.current_semantic_basis_hash
    assert delta.source.previous_epoch_manifest_ref == fixture.previous_ref
    provider = module.CanonicalEpochPerturbationAdjudicationProvider(
        artifacts=fixture.store,
        dependency_inventory=dependencies,
        native_basis=native,
    )
    with pytest.raises(ValueError, match="semantic_change_event_carrier_not_established"):
        provider.resolve_complete_owner_adjudications(**query)
