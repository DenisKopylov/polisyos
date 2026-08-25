"""Behavioral tests for the policy-free epoch validity cascade."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.runtime.quality.epoch_validity_cascade import (
    AdvisoryPerturbationEvent,
    DerivationRecipeBinding,
    EpochCertificateBinding,
    EpochDependencyDenominatorReceipt,
    EpochDependencyEdge,
    EpochDependencyGraph,
    EpochPerturbationAdjudicationReceipt,
    EpochTransitionSigningNonReceipt,
    EpochValidityTransitionArtifact,
    EpochValidityTransitionProducer,
    NoEpochTransitionSigningAuthority,
    OwnerAdjudicatedTargetDisposition,
    _framed_semantic_hash,
    _semantic_hash,
    bind_certificate_to_epoch,
    build_epoch_validity_transition,
    resolve_owner_target_dispositions,
)
from polisyos.runtime.quality.semantic_epoch import SemanticEpochManifest


def _digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


def _ref(label: str, *, kind: str = "test.artifact") -> artifacts.ArtifactRef:
    return artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID(_digest(label)),
        kind=kind,
        media_type="application/octet-stream",
    )


def _graph(
    *targets: artifacts.ArtifactRef,
    authority_purpose: str = "decision_validity",
) -> EpochDependencyGraph:
    source = _ref("source")
    edges = tuple(
        EpochDependencyEdge(
            source_ref=source,
            target_ref=target,
            relation="invalidates",
            authority_purpose=authority_purpose,
        )
        for target in targets
    )
    return EpochDependencyGraph(
        edges=edges,
        denominator_ref=_semantic_hash("polisyos.epoch.dependency-graph.v1", {"edges": edges}),
    )


def test_outer_query_context_uses_the_frozen_canonicalization_domain() -> None:
    with pytest.raises(ValueError, match="float"):
        _framed_semantic_hash("outer", {"value": 0.5})

    assert _framed_semantic_hash("outer", {"value": None}) != _framed_semantic_hash("outer", {})


def test_recipe_binding_cannot_project_execution() -> None:
    calls: list[str] = []

    class _ExecutableLookingRecipe(DerivationRecipeBinding):
        def execute(self) -> None:
            calls.append("executed")

    recipe = _ExecutableLookingRecipe(
        recipe_ref=_ref("recipe", kind="epoch.derivation_recipe"),
        recipe_content_hash=_digest("recipe-content"),
        recipe_schema_profile_ref=_digest("recipe-schema"),
        input_roles=("certificate",),
    )
    epoch = SemanticEpochManifest.model_construct(epoch_ref=_digest("epoch"))

    binding = bind_certificate_to_epoch(
        certificate_ref=_ref("certificate", kind="decision.certificate"),
        certificate_content_hash=_digest("certificate-content"),
        epoch=epoch,
        input_certificate_refs=(),
        recipe=recipe,
        canonical_producer_ref="producer://decision-validity",
        authority_purpose="decision_validity",
        native_coordinate_refs=(_digest("valid"),),
        rule_schema_profile_refs=(_digest("rule"),),
    )

    assert binding.epoch_ref == _digest("epoch")
    assert hasattr(recipe, "execute")
    assert calls == []
    assert not hasattr(binding, "execute")

    source_root = Path(__file__).resolve().parents[4] / "src"
    execution_calls: list[str] = []
    parsed_files = 0
    for source_path in source_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        parsed_files += 1
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            receiver = node.func.value
            if (
                node.func.attr in {"execute", "run", "invoke"}
                and isinstance(receiver, ast.Name)
                and "recipe" in receiver.id.lower()
            ):
                execution_calls.append(
                    f"{source_path.relative_to(source_root)}:{node.lineno}:"
                    f"{receiver.id}.{node.func.attr}"
                )
    assert parsed_files > 0
    assert execution_calls == []


def test_certificate_binding_hash_governs_every_authority_input() -> None:
    recipe = DerivationRecipeBinding(
        recipe_ref=_ref("recipe", kind="epoch.derivation_recipe"),
        recipe_content_hash=_digest("recipe-content"),
        recipe_schema_profile_ref=_digest("recipe-schema"),
        input_roles=("certificate",),
    )
    binding = bind_certificate_to_epoch(
        certificate_ref=_ref("certificate", kind="decision.certificate"),
        certificate_content_hash=_digest("certificate-content"),
        epoch=SemanticEpochManifest.model_construct(epoch_ref=_digest("epoch")),
        input_certificate_refs=(_ref("input", kind="decision.certificate"),),
        recipe=recipe,
        canonical_producer_ref="producer://decision-validity",
        authority_purpose="decision_validity",
        native_coordinate_refs=(_digest("valid"),),
        rule_schema_profile_refs=(_digest("rule"),),
    )
    mutations = {
        "certificate_ref": _ref("other-certificate", kind="decision.certificate"),
        "certificate_content_hash": _digest("other-certificate-content"),
        "epoch_ref": _digest("other-epoch"),
        "input_certificate_refs": (),
        "recipe": recipe.model_copy(update={"recipe_content_hash": _digest("other-recipe")}),
        "canonical_producer_ref": "producer://other",
        "authority_purpose": "claim_lifecycle",
        "native_coordinate_refs": (_digest("other-valid"),),
        "rule_schema_profile_refs": (_digest("other-rule"),),
    }

    for field, value in mutations.items():
        payload = binding.model_dump(mode="python")
        payload[field] = value
        with pytest.raises(
            ValueError,
            match="epoch_certificate_binding_content_mismatch",
        ):
            EpochCertificateBinding.model_validate(payload)


def test_same_advisory_event_follows_changed_canonical_owner_disposition() -> None:
    target = _ref("owner-target")
    graph = _graph(target)
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("owner-event"),
        target_ref=target,
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )

    def owner(disposition: str, evidence: str) -> OwnerAdjudicatedTargetDisposition:
        return OwnerAdjudicatedTargetDisposition(
            target_ref=target,
            event_ref=event.event_ref,
            disposition=disposition,
            owner_evidence_ref=_ref(evidence),
            owner_evidence_content_hash=_digest(f"{evidence}-content"),
            authority_purpose="decision_validity",
            predicate_class="independently_reconciled",
        )

    first = resolve_owner_target_dispositions(
        advisory_events=(event,),
        owner_dispositions=(owner("invalidate", "owner-first"),),
        dependency_graph=graph,
    )
    second = resolve_owner_target_dispositions(
        advisory_events=(event,),
        owner_dispositions=(owner("annotation_only", "owner-second"),),
        dependency_graph=graph,
    )

    assert first.rows[0].disposition == "invalidate"
    assert second.rows[0].disposition == "annotation_only"
    assert first.vector_content_hash != second.vector_content_hash


def test_linked_invalidation_preserves_historically_authentic_certificate_bytes() -> None:
    recipe = DerivationRecipeBinding(
        recipe_ref=_ref("history-recipe", kind="epoch.derivation_recipe"),
        recipe_content_hash=_digest("history-recipe-content"),
        recipe_schema_profile_ref=_digest("history-recipe-schema"),
        input_roles=("certificate",),
    )
    binding = bind_certificate_to_epoch(
        certificate_ref=_ref("historical-certificate", kind="decision.certificate"),
        certificate_content_hash=_digest("historical-certificate-content"),
        epoch=SemanticEpochManifest.model_construct(epoch_ref=_digest("historical-epoch")),
        input_certificate_refs=(),
        recipe=recipe,
        canonical_producer_ref="producer://decision-validity",
        authority_purpose="decision_validity",
        native_coordinate_refs=(_digest("historical-valid"),),
        rule_schema_profile_refs=(_digest("historical-rule"),),
    )
    original_bytes = binding.model_dump_json()
    target = binding.certificate_ref
    graph = _graph(target)
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("later-invalidation"),
        target_ref=target,
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("later-epoch"),
    )
    owner = OwnerAdjudicatedTargetDisposition(
        target_ref=target,
        event_ref=event.event_ref,
        disposition="invalidate",
        owner_evidence_ref=_ref("later-owner"),
        owner_evidence_content_hash=_digest("later-owner-content"),
        authority_purpose="decision_validity",
        predicate_class="independently_reconciled",
    )

    vector = resolve_owner_target_dispositions(
        advisory_events=(event,),
        owner_dispositions=(owner,),
        dependency_graph=graph,
    )

    assert vector.rows[0].disposition == "invalidate"
    assert EpochCertificateBinding.model_validate_json(original_bytes) == binding
    assert binding.epoch_ref == _digest("historical-epoch")


def test_owner_dispositions_preserve_mixed_append_only_history() -> None:
    first = _ref("target-a")
    second = _ref("target-b")
    graph = _graph(first, second)
    event_a = AdvisoryPerturbationEvent(
        event_ref=_ref("event-a"),
        target_ref=first,
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )
    event_b = AdvisoryPerturbationEvent(
        event_ref=_ref("event-b"),
        target_ref=second,
        event_kind="annotation_only",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )
    owner_a = OwnerAdjudicatedTargetDisposition(
        target_ref=first,
        event_ref=event_a.event_ref,
        disposition="invalidate",
        owner_evidence_ref=_ref("owner-a"),
        owner_evidence_content_hash=_digest("owner-a-content"),
        authority_purpose="decision_validity",
        predicate_class="independently_reconciled",
    )
    owner_b = OwnerAdjudicatedTargetDisposition(
        target_ref=second,
        event_ref=event_b.event_ref,
        disposition="annotation_only",
        owner_evidence_ref=_ref("owner-b"),
        owner_evidence_content_hash=_digest("owner-b-content"),
        authority_purpose="decision_validity",
        predicate_class="independently_reconciled",
    )

    vector = resolve_owner_target_dispositions(
        advisory_events=(event_b, event_a),
        owner_dispositions=(owner_a, owner_b),
        dependency_graph=graph,
    )

    assert {row.disposition for row in vector.rows} == {
        "annotation_only",
        "invalidate",
    }
    assert tuple(str(row.target_ref.artifact_id) for row in vector.rows) == tuple(
        sorted(str(row.target_ref.artifact_id) for row in vector.rows)
    )

    conflicting = owner_a.model_copy(update={"disposition": "reissue"})
    contested = resolve_owner_target_dispositions(
        advisory_events=(event_a,),
        owner_dispositions=(owner_a, conflicting),
        dependency_graph=_graph(first),
    )
    assert contested.rows[0].disposition == "contested"


def test_owner_disposition_cannot_nominate_a_target_outside_denominator() -> None:
    target = _ref("target")
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("event"),
        target_ref=target,
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("epoch"),
    )
    owner = OwnerAdjudicatedTargetDisposition(
        target_ref=target,
        event_ref=event.event_ref,
        disposition="invalidate",
        owner_evidence_ref=_ref("owner"),
        owner_evidence_content_hash=_digest("owner-content"),
        authority_purpose="decision_validity",
        predicate_class="independently_reconciled",
    )

    with pytest.raises(ValueError, match="outside_dependency_denominator"):
        resolve_owner_target_dispositions(
            advisory_events=(event,),
            owner_dispositions=(owner,),
            dependency_graph=_graph(_ref("other")),
        )


def test_disposition_requires_exact_target_and_authority_purpose() -> None:
    target = _ref("target")
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("event"),
        target_ref=target,
        event_kind="invalidate",
        authority_purpose="claim_lifecycle",
        observed_epoch_ref=_digest("epoch"),
    )
    owner = OwnerAdjudicatedTargetDisposition(
        target_ref=target,
        event_ref=event.event_ref,
        disposition="invalidate",
        owner_evidence_ref=_ref("owner"),
        owner_evidence_content_hash=_digest("owner-content"),
        authority_purpose="claim_lifecycle",
        predicate_class="independently_reconciled",
    )

    with pytest.raises(ValueError, match="advisory_event_authority_purpose_mismatch"):
        resolve_owner_target_dispositions(
            advisory_events=(event,),
            owner_dispositions=(owner,),
            dependency_graph=_graph(target),
        )

    accepted_event = event.model_copy(update={"authority_purpose": "decision_validity"})
    with pytest.raises(ValueError, match="owner_disposition_authority_purpose_mismatch"):
        resolve_owner_target_dispositions(
            advisory_events=(accepted_event,),
            owner_dispositions=(owner,),
            dependency_graph=_graph(target),
        )

    wrong_kind = target.model_copy(update={"kind": "wrong.kind"})
    with pytest.raises(ValueError, match="outside_dependency_denominator"):
        resolve_owner_target_dispositions(
            advisory_events=(accepted_event.model_copy(update={"target_ref": wrong_kind}),),
            owner_dispositions=(),
            dependency_graph=_graph(target),
        )


def test_disposition_vector_is_invariant_to_transport_order() -> None:
    target = _ref("target")
    events = tuple(
        AdvisoryPerturbationEvent(
            event_ref=_ref(f"event-{index}"),
            target_ref=target,
            event_kind="invalidate",
            authority_purpose="decision_validity",
            observed_epoch_ref=_digest("epoch"),
        )
        for index in range(2)
    )
    owners = tuple(
        OwnerAdjudicatedTargetDisposition(
            target_ref=target,
            event_ref=event.event_ref,
            disposition="invalidate",
            owner_evidence_ref=_ref(f"owner-{index}"),
            owner_evidence_content_hash=_digest(f"owner-{index}-content"),
            authority_purpose="decision_validity",
            predicate_class="independently_reconciled",
        )
        for index, event in enumerate(events)
    )

    forward = resolve_owner_target_dispositions(
        advisory_events=events,
        owner_dispositions=owners,
        dependency_graph=_graph(target),
    )
    reverse = resolve_owner_target_dispositions(
        advisory_events=tuple(reversed(events)),
        owner_dispositions=tuple(reversed(owners)),
        dependency_graph=_graph(target),
    )

    assert reverse == forward
    assert reverse.vector_content_hash == forward.vector_content_hash


def test_exact_graph_propagates_to_descendants_and_stops_at_sibling() -> None:
    root = _ref("root")
    child = _ref("child")
    grandchild = _ref("grandchild")
    sibling = _ref("sibling")
    edges = (
        EpochDependencyEdge(
            source_ref=root,
            target_ref=child,
            relation="invalidates",
            authority_purpose="decision_validity",
        ),
        EpochDependencyEdge(
            source_ref=child,
            target_ref=grandchild,
            relation="invalidates",
            authority_purpose="decision_validity",
        ),
        EpochDependencyEdge(
            source_ref=root,
            target_ref=sibling,
            relation="unaffected_sibling",
            authority_purpose="claim_lifecycle",
        ),
    )
    graph = EpochDependencyGraph(
        edges=edges,
        denominator_ref=_semantic_hash("polisyos.epoch.dependency-graph.v1", {"edges": edges}),
    )
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("root-event"),
        target_ref=root,
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )
    owners = tuple(
        OwnerAdjudicatedTargetDisposition(
            target_ref=target,
            event_ref=event.event_ref,
            disposition="invalidate",
            owner_evidence_ref=_ref(f"owner-{label}"),
            owner_evidence_content_hash=_digest(f"owner-{label}-content"),
            authority_purpose="decision_validity",
            predicate_class="independently_reconciled",
        )
        for label, target in (("child", child), ("grandchild", grandchild))
    )

    vector = resolve_owner_target_dispositions(
        advisory_events=(event,),
        owner_dispositions=owners,
        dependency_graph=graph,
    )
    by_target = {str(row.target_ref.artifact_id): row for row in vector.rows}

    assert by_target[str(child.artifact_id)].disposition == "invalidate"
    assert by_target[str(grandchild.artifact_id)].disposition == "invalidate"
    assert by_target[str(sibling.artifact_id)].disposition == "unchanged"
    assert by_target[str(child.artifact_id)].advisory_event_refs == (event.event_ref,)
    assert by_target[str(grandchild.artifact_id)].advisory_event_refs == (event.event_ref,)

    with pytest.raises(ValueError, match="outside_dependency_denominator"):
        resolve_owner_target_dispositions(
            advisory_events=(event.model_copy(update={"target_ref": _ref("root-copy")}),),
            owner_dispositions=(),
            dependency_graph=graph,
        )


def test_annotation_cannot_cancel_an_authority_transition() -> None:
    target = _ref("annotation-target")
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("annotation-event"),
        target_ref=target,
        event_kind="annotation_only",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )
    owner_rows = (
        OwnerAdjudicatedTargetDisposition(
            target_ref=target,
            event_ref=event.event_ref,
            disposition="annotation_only",
            owner_evidence_ref=_ref("annotation-owner"),
            owner_evidence_content_hash=_digest("annotation-owner-content"),
            authority_purpose="decision_validity",
            predicate_class="independently_reconciled",
        ),
        OwnerAdjudicatedTargetDisposition(
            target_ref=target,
            event_ref=event.event_ref,
            disposition="invalidate",
            owner_evidence_ref=_ref("invalidate-owner"),
            owner_evidence_content_hash=_digest("invalidate-owner-content"),
            authority_purpose="decision_validity",
            predicate_class="independently_reconciled",
        ),
    )

    vector = resolve_owner_target_dispositions(
        advisory_events=(event,),
        owner_dispositions=owner_rows,
        dependency_graph=_graph(target),
    )

    assert vector.rows[0].disposition == "invalidate"


def test_dependency_and_adjudication_receipts_bind_complete_denominators() -> None:
    target = _ref("bound-target")
    graph = _graph(target)
    dependency_payload = {
        "certificate_bindings": (),
        "dependency_graph": graph,
        "target_refs": (target,),
    }
    dependency = EpochDependencyDenominatorReceipt(
        denominator_ref=_semantic_hash(
            "polisyos.epoch.dependency-denominator.v1", dependency_payload
        ),
        **dependency_payload,
        predicate_class="independently_reconciled",
    )
    assert dependency.target_refs == (target,)
    with pytest.raises(ValueError, match="epoch_dependency_target_denominator_mismatch"):
        EpochDependencyDenominatorReceipt.model_validate(
            {**dependency.model_dump(mode="json"), "target_refs": []}
        )

    event = AdvisoryPerturbationEvent(
        event_ref=_ref("bound-event"),
        target_ref=target,
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )
    owner = OwnerAdjudicatedTargetDisposition(
        target_ref=target,
        event_ref=event.event_ref,
        disposition="invalidate",
        owner_evidence_ref=_ref("bound-owner"),
        owner_evidence_content_hash=_digest("bound-owner-content"),
        authority_purpose="decision_validity",
        predicate_class="independently_reconciled",
    )
    adjudication_payload = {
        "advisory_events": (event,),
        "owner_dispositions": (owner,),
    }
    receipt = EpochPerturbationAdjudicationReceipt(
        denominator_ref=_semantic_hash(
            "polisyos.epoch.perturbation-adjudication-denominator.v1",
            adjudication_payload,
        ),
        **adjudication_payload,
        predicate_class="independently_reconciled",
    )
    assert receipt.owner_dispositions == (owner,)
    with pytest.raises(ValueError, match="epoch_perturbation_adjudication_denominator_mismatch"):
        EpochPerturbationAdjudicationReceipt.model_validate(
            {
                **receipt.model_dump(mode="json"),
                "owner_dispositions": [],
            }
        )


def test_signed_transition_preimage_binds_owner_purpose_and_both_denominators() -> None:
    target = _ref("transition-target")
    graph = _graph(target)
    vector = resolve_owner_target_dispositions(
        advisory_events=(),
        owner_dispositions=(),
        dependency_graph=graph,
    )
    adjudication_denominator_ref = _digest("transition-adjudication-denominator")

    transition = build_epoch_validity_transition(
        previous_epoch=SemanticEpochManifest.model_construct(epoch_ref=_digest("epoch-old")),
        current_epoch=SemanticEpochManifest.model_construct(epoch_ref=_digest("epoch-new")),
        certificates=(),
        dependency_graph=graph,
        target_vector=vector,
        dependency_denominator_ref=graph.denominator_ref,
        adjudication_denominator_ref=adjudication_denominator_ref,
        requested_query_context_ref=_digest("transition-query"),
        authority_purpose="decision_validity",
    )

    assert transition.dependency_denominator_ref == graph.denominator_ref
    assert transition.adjudication_denominator_ref == adjudication_denominator_ref
    assert transition.authority_purpose == "decision_validity"
    for field, mutation, diagnostic in (
        (
            "dependency_denominator_ref",
            _digest("other-dependency-denominator"),
            "epoch_validity_transition_dependency_denominator_mismatch",
        ),
        (
            "adjudication_denominator_ref",
            _digest("other-adjudication-denominator"),
            "epoch_validity_transition_content_mismatch",
        ),
        ("authority_purpose", "claim_lifecycle", "epoch_validity_transition_content_mismatch"),
    ):
        payload = transition.model_dump(mode="json")
        payload[field] = mutation
        with pytest.raises(ValueError, match=diagnostic):
            EpochValidityTransitionArtifact.model_validate(payload)


def test_unappointed_transition_signer_returns_typed_negative_before_owner_reads() -> None:
    class NoOwnerCalls:
        def __getattr__(self, name: str):
            raise AssertionError(f"unappointed signer must precede owner read: {name}")

    producer = EpochValidityTransitionProducer(
        dependency_inventory=NoOwnerCalls(),  # type: ignore[arg-type]
        adjudications=NoOwnerCalls(),  # type: ignore[arg-type]
        epoch_history=NoOwnerCalls(),  # type: ignore[arg-type]
        signed_artifacts=NoOwnerCalls(),  # type: ignore[arg-type]
        signing_authority=NoEpochTransitionSigningAuthority(),
    )

    result = producer.produce_and_persist(
        previous_epoch_ref=_ref("previous-epoch"),
        current_epoch_receipt_ref=_ref("current-receipt"),
        requested_query_context_ref=_digest("transition-query"),
        authority_purpose="decision_validity",
    )

    assert result == EpochTransitionSigningNonReceipt(
        status="not_established",
        code="epoch_transition_signer_not_established",
        predicate_class="not_established",
    )
