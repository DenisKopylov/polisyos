"""Exercise canonical certificate issuance hooks without inventing recipe authority."""

from __future__ import annotations

import importlib
import importlib.util

import pytest

from polisyos.core import artifacts


def _issuance_module():
    name = "polisyos.runtime.quality.epoch_certificate_issuance"
    assert importlib.util.find_spec(name) is not None, "canonical epoch issuance owner is missing"
    return importlib.import_module(name)


def test_unappointed_issuance_input_does_not_create_binding_or_inventory(tmp_path) -> None:
    """Removing the source refusal would admit fabricated certificate dependencies."""

    module = _issuance_module()
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    owner = module.DecisionPacketEpochIssuanceOwner(store=store, root=tmp_path / "owner")

    result = owner.prepare(run_id="actual-node-run", invocation_input_refs=())

    assert isinstance(result, module.EpochCertificateIssuanceNonReceipt)
    assert result.code == "epoch_certificate_issuance_input_not_established"
    assert owner.enumerate_registered_issuances() == ()
    with pytest.raises(ValueError, match="dependency_denominator_unresolved"):
        owner.resolve_complete_epoch_dependencies(
            previous_epoch_ref="sha256:" + "1" * 64,
            authority_purpose="decision_validity_epoch_transition",
        )


@pytest.mark.parametrize(
    "descriptive_ref",
    [
        None,
        {"artifact_id": "ordinary-display-id", "kind": "description", "media_type": "text/plain"},
        {"artifact_id": "sha256:" + "f" * 64, "kind": "description", "media_type": "text/plain"},
    ],
)
@pytest.mark.parametrize("configured_absence", [False, True])
def test_canonical_packet_node_persists_absence_without_epoch_dependency(
    tmp_path, descriptive_ref, configured_absence
) -> None:
    """Deleting the real builder hook must lose the persisted source nonreceipt."""

    _issuance_module()
    import logging

    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    run = RunContext.start(
        store=store,
        registry_bundle=build_default_registry_bundle(store).bundle_ref,
        run_dir=tmp_path / "run",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(__name__),
        epoch_certificate_issuance_owner=(
            _issuance_module().DecisionPacketEpochIssuanceOwner.for_store(store=store)
            if configured_absence
            else None
        ),
    )
    outcome = BuildDecisionPacketNode().execute(
        ctx,
        ExperimentState(
            run_id=run.run_manifest.run_id,
            params={"fail_on_naked_claims": False, "description": descriptive_ref},
        ),
    )

    assert outcome.status == "ok"
    packet_ref = outcome.state.artifacts_index["decision_packet_ref"]
    from polisyos.core.canon import from_canonical_bytes

    packet = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    envelope = packet["decision_validity_envelope"]
    invocation_ref = artifacts.ArtifactRef.model_validate(
        envelope["data_basis"]["summary"]["epoch_certificate_invocation_ref"]
    )
    invocation = from_canonical_bytes(store.get_bytes(invocation_ref.artifact_id))
    invoked_state = from_canonical_bytes(
        store.get_bytes(artifacts.ArtifactRef.model_validate(invocation["state_ref"]).artifact_id)
    )
    assert invoked_state["params"]["fail_on_naked_claims"] is False
    assert invocation["observation_status"] == "observed_only"
    assert envelope["data_basis"]["summary"]["epoch_certificate_issuance"] == {
        "status": "not_established",
        "code": "epoch_certificate_issuance_input_not_established",
    }
    assert all(
        dependency["kind"] != "semantic_epoch"
        for section in (
            "data_basis",
            "knowledge_basis",
            "normative_basis",
            "transportability_basis",
        )
        for dependency in envelope[section]["dependencies"]
    )


def _configured_fixture(tmp_path):
    """Supply an explicitly test-only verified-input boundary; keep persistence real."""

    module = _issuance_module()
    from polisyos.runtime.quality.epoch_validity_cascade import DerivationRecipeBinding
    from polisyos.runtime.quality.semantic_epoch_store import FileSemanticEpochHistoryRepository
    from tests.unit.runtime.quality.test_epoch_validity_cascade import (
        _append_epoch_manifest,
        _digest,
        _epoch_history_entry,
        _epoch_manifest,
        _epoch_scope,
        _persist_epoch_manifest,
    )

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    history = FileSemanticEpochHistoryRepository(root=tmp_path / "history", artifacts=store)
    scope = _epoch_scope("issuance-test-boundary")
    epoch = _epoch_manifest(
        scope=scope,
        label="actual-fixture-issuance",
        predecessors=(),
        authority_purpose="decision_validity_epoch_transition",
    )
    epoch_ref = _persist_epoch_manifest(store, epoch)
    _append_epoch_manifest(
        history,
        scope=scope,
        manifest=epoch,
        manifest_ref=epoch_ref,
        expected_heads=(),
        resulting_entries=(_epoch_history_entry(epoch, epoch_ref),),
        resulting_heads=(epoch.epoch_ref,),
    )
    source = store.put_bytes(
        b"actual-fixture-source",
        artifacts.ArtifactWriteOptions(kind="test.source", media_type="text/plain"),
    )
    recipe = store.put_bytes(
        b"test-only admitted executable recipe",
        artifacts.ArtifactWriteOptions(kind="test.recipe", media_type="text/plain"),
    )
    provenance = store.put_bytes(
        b"test-only input verifier",
        artifacts.ArtifactWriteOptions(kind="test.verifier", media_type="text/plain"),
    )
    admission = store.put_bytes(
        b"test-only recipe admission",
        artifacts.ArtifactWriteOptions(kind="test.admission", media_type="text/plain"),
    )

    environment = store.put_bytes(
        b"test-only independently admitted complete execution environment",
        artifacts.ArtifactWriteOptions(kind="test.admitted_environment", media_type="text/plain"),
    )
    environment_profile = store.put_bytes(
        b"test-only registered full code/tool/environment closure policy",
        artifacts.ArtifactWriteOptions(kind="test.environment_profile", media_type="text/plain"),
    )

    class Source:
        # This fixture explicitly supplies the privileged independent admission
        # premise; production never derives it from these labels or recipe bytes.
        verifier_provenance_ref = provenance

        def resolve_admitted_execution_closure(self, *, invocation_ref, invocation_content_hash):
            from polisyos.core import canon
            from polisyos.scientist import DecisionPacketInvocationRecord

            assert store.verify(invocation_ref.artifact_id).ok
            assert invocation_content_hash == str(invocation_ref.artifact_id)
            invocation = DecisionPacketInvocationRecord.model_validate(
                canon.from_canonical_bytes(store.get_bytes(invocation_ref.artifact_id))
            )
            assert source in invocation.input_refs
            assert store.verify(environment.artifact_id).ok
            assert store.verify(environment_profile.artifact_id).ok
            assert store.verify(invocation.implementation_ref.artifact_id).ok
            return module.AdmittedDecisionPacketExecutionClosure(
                invocation_ref=invocation_ref,
                invocation_content_hash=invocation_content_hash,
                epoch_manifest_ref=epoch_ref,
                authority_purpose=epoch.authority_purpose,
                requested_query_context_ref=epoch.requested_query_context_ref,
                input_certificate_refs=invocation.input_refs,
                code_source_refs=(invocation.implementation_ref, invocation.loaded_code_ref),
                tool_source_refs=(invocation.node_spec_ref,),
                environment_manifest_ref=environment,
                environment_profile_ref=environment_profile,
                admission_evidence_ref=admission,
                verifier_provenance_ref=provenance,
            )

        def resolve_verified_inputs(self, *, run_id, canonical_producer_ref, invocation_input_refs):
            assert canonical_producer_ref == (
                "polisyos.scientist.nodes.builtins.decide.decision_packet.builder."
                "BuildDecisionPacketNode.execute"
            )
            assert source in invocation_input_refs
            return module.EpochCertificateIssuanceInputs(
                run_id=run_id,
                canonical_producer_ref=canonical_producer_ref,
                epoch_manifest_ref=epoch_ref,
                recipe=DerivationRecipeBinding(
                    recipe_ref=recipe,
                    recipe_content_hash=str(recipe.artifact_id),
                    recipe_schema_profile_ref=_digest("fixture-recipe-profile"),
                    input_roles=("input.source",),
                ),
                input_certificate_refs=invocation_input_refs,
                native_coordinate_refs=(epoch.valid_effect_coordinate_ref,),
                rule_schema_profile_refs=(_digest("fixture-rule-profile"),),
                requested_query_context_ref=epoch.requested_query_context_ref,
                authority_purpose=epoch.authority_purpose,
                admission_evidence_ref=admission,
                verifier_provenance_ref=provenance,
            )

    owner = module.DecisionPacketEpochIssuanceOwner(
        store=store,
        root=tmp_path / "owner",
        history=history,
        input_resolver=Source(),
    )
    return module, store, owner, epoch, source, recipe


def test_issuance_freezes_exact_packet_basis_and_inventory_survives_restart(tmp_path) -> None:
    """Removing finalization or exact source binding loses the real persisted inventory."""

    module, store, owner, epoch, source, opaque_recipe = _configured_fixture(tmp_path)
    packet, envelope = _run_canonical_node(tmp_path, store, owner, source)
    (issued,) = owner.enumerate_registered_issuances()
    prepared = issued.preparation
    assert issued.binding.certificate_ref == packet
    assert issued.binding.certificate_content_hash == str(packet.artifact_id)
    assert issued.binding.epoch_ref == epoch.epoch_ref
    assert issued.binding.recipe.recipe_ref != opaque_recipe
    assert issued.binding.recipe.recipe_ref.kind == "scientist.decision_packet_invocation_recipe"
    dependency = envelope.data_basis.dependencies[0]
    assert dependency.kind.value == "semantic_epoch"
    assert dependency.artifact_id == str(prepared.issuance_basis_ref.artifact_id)

    restarted = module.DecisionPacketEpochIssuanceOwner(store=store, root=tmp_path / "owner")
    assert restarted.enumerate_registered_issuances() == (issued,)
    inventory = restarted.resolve_complete_epoch_dependencies(
        previous_epoch_ref=epoch.epoch_ref,
        authority_purpose=epoch.authority_purpose,
    )
    assert inventory.certificate_bindings == (issued.binding,)
    assert inventory.target_refs == (prepared.issuance_basis_ref,)
    assert inventory.dependency_graph.edges[0].source_ref == issued.epoch_manifest_ref

    from polisyos.scientist.validation.decision_validity import DecisionValidityService

    snapshot = DecisionValidityService(store).persist_epoch_impact_snapshot(
        dependency_keys=(dependency.key,),
        requested_query_context_ref=epoch.requested_query_context_ref,
    )
    assert snapshot.snapshot.targets[0].packet_ref == str(packet.artifact_id)


def test_issuance_refuses_mutated_recipe_before_basis_persistence(tmp_path) -> None:
    """Removing exact recipe-byte verification would accept changed execution inputs."""

    module, store, owner, _, source, recipe = _configured_fixture(tmp_path)
    blob, _ = store._paths(recipe.artifact_id)
    blob.write_bytes(b"changed recipe with original reference")

    with pytest.raises(ValueError, match="epoch_certificate_issuance_evidence_unresolved"):
        owner.prepare(run_id="actual-node-run", invocation_input_refs=(source,))
    assert owner.enumerate_registered_issuances() == ()


def test_copied_issuance_artifact_without_owner_admission_is_not_inventory(tmp_path) -> None:
    """Keeping CAS bytes but deleting the owner admission cannot recreate authority."""

    module, store, owner, _, source, _ = _configured_fixture(tmp_path)
    _run_canonical_node(tmp_path, store, owner, source)
    (issued,) = owner.enumerate_registered_issuances()
    assert store.verify(issued.issuance_receipt_ref.artifact_id).ok
    other_owner = module.DecisionPacketEpochIssuanceOwner(
        store=store, root=tmp_path / "other-owner"
    )
    assert other_owner.enumerate_registered_issuances() == ()


def test_inventory_rechecks_packet_manifest_basis_with_exact_packet_bytes(
    tmp_path, monkeypatch
) -> None:
    """A valid CAS hash does not prove the packet still carries its issued input basis."""

    _, store, owner, _, source, _ = _configured_fixture(tmp_path)
    packet, _ = _run_canonical_node(tmp_path, store, owner, source)
    read_manifest = store.get_manifest

    def omit_packet_inputs(artifact_id):
        manifest = read_manifest(artifact_id)
        if artifact_id == packet.artifact_id:
            return manifest.model_copy(update={"inputs": []})
        return manifest

    monkeypatch.setattr(store, "get_manifest", omit_packet_inputs)
    assert store.get_bytes(packet.artifact_id)
    with pytest.raises(ValueError, match="epoch_certificate_issuance_evidence_unresolved"):
        owner.enumerate_registered_issuances()


def test_prepare_reconciles_native_projection_against_exact_history_bytes(
    tmp_path, monkeypatch
) -> None:
    """Keeping a recomputed declaration cannot authorize a different history projection."""

    _, _, owner, _, source, _ = _configured_fixture(tmp_path)
    read_history = owner._history.resolve_scope_history

    def substituted_projection(**kwargs):
        history = read_history(**kwargs)
        changed = history.entries[0].model_copy(
            update={"predecessor_refs": ("sha256:" + "b" * 64,)}
        )
        return history.model_copy(update={"entries": (changed,)})

    monkeypatch.setattr(owner._history, "resolve_scope_history", substituted_projection)
    with pytest.raises(ValueError, match="epoch_certificate_issuance_evidence_unresolved"):
        owner.prepare(run_id="actual-node-run", invocation_input_refs=(source,))
    assert owner.enumerate_registered_issuances() == ()


def test_inventory_replays_frozen_native_history_evidence(tmp_path) -> None:
    """Admission cannot later forget the exact history bytes that made issuance current."""

    _, store, owner, epoch, source, _ = _configured_fixture(tmp_path)
    history = owner._history.resolve_scope_history(
        scope=epoch.scope_identity, authority_purpose=epoch.authority_purpose
    )
    _run_canonical_node(tmp_path, store, owner, source)
    blob, _ = store._paths(history.history_snapshot_ref.artifact_id)
    blob.write_bytes(b"changed frozen history")
    with pytest.raises(ValueError, match="epoch_certificate_issuance_evidence_unresolved"):
        owner.enumerate_registered_issuances()


def test_unselected_unreadable_issuance_is_not_dropped_from_complete_inventory(tmp_path) -> None:
    """Scope filtering happens after full exact owner readback, never before it."""

    _, store, owner, _, source, recipe = _configured_fixture(tmp_path)
    _run_canonical_node(tmp_path, store, owner, source)
    blob, _ = store._paths(recipe.artifact_id)
    blob.write_bytes(b"corrupted unselected issuance recipe")
    with pytest.raises(ValueError, match="epoch_certificate_issuance_evidence_unresolved"):
        owner.resolve_complete_epoch_dependencies(
            previous_epoch_ref="sha256:" + "b" * 64,
            authority_purpose="a-different-purpose",
        )


def test_malformed_owner_row_is_not_skipped(tmp_path) -> None:
    """One valid admission cannot hide a malformed sibling in the owner denominator."""

    _, store, owner, _, source, _ = _configured_fixture(tmp_path)
    _run_canonical_node(tmp_path, store, owner, source)
    with owner._index.open("ab") as output:
        output.write(b'{"not_an_artifact_ref":true}\n')
    with pytest.raises(ValueError, match="epoch_certificate_issuance_owner_unresolved"):
        owner.enumerate_registered_issuances()


def test_authorial_completion_object_cannot_admit_an_issuance(tmp_path) -> None:
    """An external object cannot replace the canonical node's private execution ticket."""

    _, _, owner, _, _, _ = _configured_fixture(tmp_path)
    with pytest.raises(ValueError, match="epoch_certificate_canonical_execution_not_established"):
        owner.finalize(execution=object())
    assert owner.enumerate_registered_issuances() == ()


def test_opaque_recipe_without_admitted_execution_closure_cannot_issue(tmp_path, monkeypatch):
    """Recipe labels and source bytes cannot stand in for admitted code/tool/environment closure."""

    _, store, owner, _, source, _ = _configured_fixture(tmp_path)
    monkeypatch.delattr(
        type(owner._input_resolver), "resolve_admitted_execution_closure", raising=False
    )
    _, envelope = _run_canonical_node(tmp_path, store, owner, source)
    assert owner.enumerate_registered_issuances() == ()
    assert envelope.data_basis.summary["epoch_certificate_issuance"]["code"] == (
        "epoch_certificate_execution_closure_not_established"
    )


def _run_canonical_node(tmp_path, store, owner, source):
    import logging

    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts.decision_validity import DecisionValidityEnvelope
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.workflows.builder import build_execution_context

    ctx = build_execution_context(
        store,
        build_default_registry_bundle(store).bundle_ref,
        run_id="actual-node-run",
        logger=logging.getLogger(__name__),
        epoch_certificate_issuance_owner=owner,
    )
    outcome = BuildDecisionPacketNode().execute(
        ctx,
        ExperimentState(
            run_id=ctx.run.run_manifest.run_id,
            inputs={"source": source},
            params={"fail_on_naked_claims": False},
        ),
    )
    assert outcome.status == "ok"
    packet_ref = outcome.state.artifacts_index["decision_packet_ref"]
    manifest = store.get_manifest(packet_ref.artifact_id)
    packet = artifacts.ArtifactRef(
        artifact_id=manifest.artifact_id, kind=manifest.kind, media_type=manifest.media_type
    )
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    return packet, DecisionValidityEnvelope.model_validate(payload["decision_validity_envelope"])


def test_invocation_freezes_finite_float_parameters_and_recipe_changes(tmp_path):
    """Equal ArtifactRefs cannot hide changed seed or supplied finite-float parameters."""

    from polisyos.core import canon
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.workflows.builder import build_execution_context

    _, store, owner, _, source, _ = _configured_fixture(tmp_path)
    context = build_execution_context(
        store,
        build_default_registry_bundle(store).bundle_ref,
        run_id="actual-node-run",
        epoch_certificate_issuance_owner=owner,
    )
    invocation_refs = []
    for seed, threshold in ((21, 0.25), (42, 0.75)):
        outcome = BuildDecisionPacketNode().execute(
            context,
            ExperimentState(
                run_id="actual-node-run",
                inputs={"source": source},
                params={
                    "fail_on_naked_claims": False,
                    "random_seed": seed,
                    "observed": {"threshold": threshold, "metric": 0.125},
                },
            ),
        )
        assert outcome.status == "ok"
        packet = canon.from_canonical_bytes(
            store.get_bytes(outcome.state.artifacts_index["decision_packet_ref"].artifact_id)
        )
        ref = artifacts.ArtifactRef.model_validate(
            packet["decision_validity_envelope"]["data_basis"]["summary"][
                "epoch_certificate_invocation_ref"
            ]
        )
        invocation = canon.from_canonical_bytes(store.get_bytes(ref.artifact_id))
        state_ref = artifacts.ArtifactRef.model_validate(invocation["state_ref"])
        state = canon.from_canonical_bytes(store.get_bytes(state_ref.artifact_id))
        assert state["params"]["observed"]["threshold"] == threshold
        assert state["params"]["observed"]["metric"] == 0.125
        assert packet["seed"] == seed
        invocation_refs.append(ref)
    assert invocation_refs[0] != invocation_refs[1]
    rows = owner.enumerate_registered_issuances()
    assert len(rows) == 2
    assert rows[0].binding.recipe != rows[1].binding.recipe


def test_closure_owner_readback_must_match_admission(tmp_path, monkeypatch):
    """An admitted-looking DTO is insufficient when the configured owner cannot read it back."""

    _, store, owner, _, source, _ = _configured_fixture(tmp_path)
    resolver = owner._input_resolver
    resolve = resolver.resolve_admitted_execution_closure
    calls = 0

    def disappear_on_readback(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return resolve(**kwargs)
        return _issuance_module().EpochCertificateIssuanceNonReceipt(
            code="epoch_certificate_execution_closure_not_established"
        )

    monkeypatch.setattr(resolver, "resolve_admitted_execution_closure", disappear_on_readback)
    with pytest.raises(
        ValueError, match="epoch_certificate_execution_closure_admission_unresolved"
    ):
        _run_canonical_node(tmp_path, store, owner, source)
    assert owner.enumerate_registered_issuances() == ()


def test_inventory_rechecks_admitted_environment_with_recipe_shape_unchanged(tmp_path):
    """Removing an influential environment source must invalidate the issued binding."""

    _, store, owner, _, source, _ = _configured_fixture(tmp_path)
    _run_canonical_node(tmp_path, store, owner, source)
    (issued,) = owner.enumerate_registered_issuances()
    basis = owner._read_basis(issued.preparation)
    environment = basis.execution_closure.environment_manifest_ref
    blob, _ = store._paths(environment.artifact_id)
    blob.write_bytes(b"removed admitted environment premise; recipe markers unchanged")
    with pytest.raises(ValueError, match="epoch_certificate_issuance_evidence_unresolved"):
        owner.enumerate_registered_issuances()
