from __future__ import annotations

import hashlib
from typing import get_args

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.pdc import OperationClass
from polisyos.pdc._impl.layer2_design_search import ConstraintRecordStatus
from polisyos.runtime.quality.workspace import foundry_consumption as constraint_owner
from polisyos.runtime.quality.workspace.foundry_consumption import (
    ConstraintStoreIngestor,
    FoundryMethodOutputConsumer,
    evaluate_constraint_store_for_phase2,
)
from polisyos.scientist.orchestration.engine import ExperimentState
from tests.unit.runtime.quality.test_data_forge_binding import (
    _produce_recorded,
)
from tests.unit.runtime.quality.test_data_forge_binding import (
    recorded_panel_owner as _recorded_panel_owner,
)

recorded_panel_owner = _recorded_panel_owner


def _method_owner_case(recorded_panel_owner):
    """Run the actual method owner; this fixture claims no guarded-node admission."""
    from polisyos.foundry.data_plane import materialize_method_contract
    from polisyos.scientist.compute import MethodBackend

    _, store, _, _ = recorded_panel_owner
    binding = _produce_recorded(recorded_panel_owner)
    typed = materialize_method_contract(
        contract_target=binding.contract_target,
        contract_payload=binding.contract_payload,
    )
    params = {"n_placebo_runs": 0}
    actual = MethodBackend().run(
        cas_root=store.root,
        method_fqn=binding.receipt.method_fqn,
        method_version=None,
        input_state=typed,
        method_params=params,
        seed=17,
        input_refs={
            "observations": binding.observational_data_ref,
            "recorded_input_binding": binding.binding_receipt_ref,
        },
    )
    state = ExperimentState(
        run_id="c3-direct-method-owner",
        observational_data_ref=binding.observational_data_ref,
        causal_method_fqn=binding.receipt.method_fqn,
        causal_method_params=params,
        params={"random_seed": 17},
        artifacts_index={
            "causal_method_result_ref": actual.exec_artifacts.result_ref,
            "causal_method_evidence_ref": actual.exec_artifacts.evidence_ref,
        },
    )
    return store, binding, state


def _consume_case(store, binding, state, *, consumer=None):
    consumer = consumer or FoundryMethodOutputConsumer(store=store)
    return consumer.consume_from_state(
        workspace_id="ws-c3-direct-method-owner",
        operation_invocation_id="invoke-c3-direct",
        operation_class=OperationClass.ESTIMATE,
        state=state,
        measurement_root_ref=binding.observational_data_ref,
        binding_receipt_ref=binding.binding_receipt_ref,
    )


def _rewrite_artifact(store, ref, mutate, *, inputs=None):
    from polisyos.core.canon import CanonSpec, from_canonical_bytes

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    mutate(payload)
    manifest = store.get_manifest(ref.artifact_id)
    return store.put_json(
        payload,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            inputs=manifest.inputs if inputs is None else inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def test_foundry_consumer_replays_actual_method_owner_and_preserves_raw_byte_custody(
    recorded_panel_owner,
):
    from polisyos.core.canon import from_canonical_bytes

    store, binding, state = _method_owner_case(recorded_panel_owner)
    consumer = FoundryMethodOutputConsumer(store=store)
    result = _consume_case(store, binding, state, consumer=consumer)
    assert result.input_provenance == "measurement_rooted"
    assert result.authority_boundary.evidence_kind == "measurement"
    assert result.authority_boundary.decision_grade == "descriptive_only"
    assert "causal_identification" in result.authority_boundary.may_not_use_for
    assert "execution_cost_authority" in result.authority_boundary.may_not_use_for
    assert result.input_binding_receipt_ref.artifact_id == str(
        binding.binding_receipt_ref.artifact_id
    )
    assert result.method_replay_verified is True
    root_schema = store.get_manifest(binding.observational_data_ref.artifact_id).artifact_schema
    assert result.record.measurement_root_refs[0].schema_ref == (
        f"{root_schema.name}@{root_schema.version}"
    )
    for ref in (
        *result.record.consumed_method_output_refs,
        *result.record.consumed_method_evidence_refs,
        *result.record.measurement_root_refs,
    ):
        assert (
            ref.content_hash
            == "sha256:"
            + hashlib.sha256(
                store.get_bytes(ref.artifact_id),
            ).hexdigest()
        )
    persisted = consumer.persist_consumption(store=store, consumption=result)
    raw = store.get_bytes(persisted.artifact_id)
    assert persisted.content_hash == "sha256:" + hashlib.sha256(raw).hexdigest()
    payload = from_canonical_bytes(raw)
    assert payload["method_replay_verified"] is True
    assert payload["input_binding_receipt_ref"] == result.input_binding_receipt_ref.model_dump(
        mode="json"
    )


def test_foundry_consumer_refuses_changed_recorded_source_with_receipt_markers_intact(
    recorded_panel_owner,
):
    store, binding, state = _method_owner_case(recorded_panel_owner)
    recorded_panel_owner[2].write_bytes(recorded_panel_owner[2].read_bytes() + b"changed source")
    with pytest.raises(ValueError, match="recorded_source_hash_mismatch"):
        _consume_case(store, binding, state)


@pytest.mark.parametrize(
    "changed_member", ["result", "evidence", "input_lineage", "seed", "cost", "timing"]
)
def test_foundry_consumer_refuses_method_artifact_mutation_with_markers_intact(
    recorded_panel_owner,
    changed_member,
):
    from polisyos.core.artifacts import InputRef

    store, binding, state = _method_owner_case(recorded_panel_owner)
    original_result = state.artifacts_index["causal_method_result_ref"]
    original_evidence = state.artifacts_index["causal_method_evidence_ref"]
    if changed_member == "result":
        changed = _rewrite_artifact(
            store,
            original_result,
            lambda payload: payload["report"]["metadata"].update(
                {"fabricated_text": "never emitted"}
            ),
        )
        state.artifacts_index["causal_method_result_ref"] = changed
        state.artifacts_index["causal_method_evidence_ref"] = _rewrite_artifact(
            store,
            original_evidence,
            lambda payload: payload.update({"result_ref": str(changed.artifact_id)}),
            inputs=[InputRef(artifact_id=changed.artifact_id, role="method_result")],
        )
    elif changed_member == "evidence":
        state.artifacts_index["causal_method_evidence_ref"] = _rewrite_artifact(
            store,
            original_evidence,
            lambda payload: payload["reproducibility"].update({"seed": 999}),
        )
    elif changed_member == "input_lineage":
        state.inputs["ukraine_selected_foundry_method_contract_ref"] = (
            binding.observational_data_ref
        )
    elif changed_member == "seed":
        state.params["random_seed"] = 999
    else:
        state.artifacts_index["causal_method_evidence_ref"] = _rewrite_artifact(
            store,
            original_evidence,
            lambda payload: payload["artifacts"]["cost_attribution"].update(
                {"estimated_cost_usd": 99} if changed_member == "cost" else {"wall_time_ms": -1}
            ),
        )
    expected_reason = {
        "result": "foundry_method_result_replay_mismatch",
        "evidence": "foundry_method_evidence_replay_mismatch",
        "input_lineage": "foundry_selected_contract_lineage_mismatch",
        "seed": "foundry_method_evidence_replay_mismatch",
        "cost": "foundry_method_cost_attribution_mismatch",
        "timing": "foundry_method_timing_observation_invalid",
    }[changed_member]
    with pytest.raises(ValueError, match=expected_reason):
        _consume_case(store, binding, state)


@pytest.mark.parametrize(
    "changed_member", ["authority", "record", "constructed", "new_consumer", "store"]
)
def test_foundry_emission_refuses_unverified_or_changed_consumption(
    recorded_panel_owner,
    changed_member,
):
    from polisyos.runtime.quality.workspace.foundry_consumption import FoundryConsumptionResult

    store, binding, state = _method_owner_case(recorded_panel_owner)
    consumer = FoundryMethodOutputConsumer(store=store)
    result = _consume_case(store, binding, state, consumer=consumer)
    if changed_member == "authority":
        result.authority_boundary.authoritative_for.append("production_recommendation")
    elif changed_member == "record":
        result.record.consumed_method_output_refs.clear()
    elif changed_member == "constructed":
        result = FoundryConsumptionResult.model_validate(result.model_dump(mode="json"))
    elif changed_member == "new_consumer":
        consumer = FoundryMethodOutputConsumer(store=store)
    else:
        store = FileSystemCAS(store.root)
    with pytest.raises(ValueError, match="foundry_consumption_verification_required"):
        consumer.persist_consumption(store=store, consumption=result)


def test_foundry_emission_uses_verified_snapshot_after_guard(recorded_panel_owner, monkeypatch):
    from polisyos.core.canon import from_canonical_bytes

    store, binding, state = _method_owner_case(recorded_panel_owner)
    consumer = FoundryMethodOutputConsumer(store=store)
    result = _consume_case(store, binding, state, consumer=consumer)
    before = result.model_dump(mode="json")
    guard = consumer._require_verified_consumption

    def mutate_after_verification(**kwargs):
        snapshot = guard(**kwargs)
        result.authority_boundary.authoritative_for.append("production_recommendation")
        result.record.consumed_method_output_refs.clear()
        return snapshot

    monkeypatch.setattr(consumer, "_require_verified_consumption", mutate_after_verification)
    persisted = consumer.persist_consumption(store=store, consumption=result)
    payload = from_canonical_bytes(store.get_bytes(persisted.artifact_id))
    assert payload["authority_boundary"] == before["authority_boundary"]
    assert payload["record"] == before["record"]
    assert {str(item.artifact_id) for item in store.get_manifest(persisted.artifact_id).inputs} == {
        ref["artifact_id"]
        for ref in (
            *before["record"]["consumed_method_output_refs"],
            *before["record"]["consumed_method_evidence_refs"],
            *before["record"]["measurement_root_refs"],
            before["input_binding_receipt_ref"],
        )
    }


@pytest.mark.parametrize("measurement_kind", ["ir.observational_data", "invented.measurement"])
def test_foundry_consumer_refuses_nonobservations_and_unrelated_cas_documents(
    tmp_path,
    measurement_kind,
):
    store = FileSystemCAS(tmp_path / "cas")
    root = store.put_json(
        {"not_observations": True},
        PutOptions(kind=measurement_kind, media_type="application/json"),
    )
    result = store.put_json(
        {"unrelated": "result"},
        PutOptions(kind="scientist.method_result.causal.inference", media_type="application/json"),
    )
    evidence = store.put_json(
        {"unrelated": "evidence"},
        PutOptions(kind="scientist.method_evidence", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="run-c3-fake",
        observational_data_ref=root,
        artifacts_index={
            "causal_method_result_ref": result,
            "causal_method_evidence_ref": evidence,
        },
    )

    with pytest.raises(ValueError):
        FoundryMethodOutputConsumer(store=store).consume_from_state(
            workspace_id="ws-c3-fake",
            operation_invocation_id="invoke-c3-fake",
            operation_class=OperationClass.ESTIMATE,
            state=state,
            measurement_root_ref=root,
        )


def _constraint_canonical_problem():
    """Evaluate the existing canonical request constructor, not a copied fixture."""
    import ast
    from pathlib import Path

    from polisyos.runtime.quality.design_problem import DesignProblem

    source = Path("tools/quality/validation/check_layer3_gy_phase2_artifacts.py")
    tree = ast.parse(source.read_text(), filename=str(source))
    builders = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_live_proof_payloads"
    ]
    assert len(builders) == 1
    constructors = [
        node
        for node in builders[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "_design_problem"
    ]
    assert len(constructors) == 1
    module = ast.fix_missing_locations(ast.Module(body=constructors, type_ignores=[]))
    context = {"DesignProblem": DesignProblem}
    # Evaluate only the tracked owner's constructor in its actual DTO context.
    exec(compile(module, str(source), "exec"), context)  # noqa: S102
    return context["_design_problem"]()


@pytest.mark.parametrize("source_kind", sorted(constraint_owner._ALLOWED_CONSTRAINT_SOURCES))
@pytest.mark.parametrize("status", get_args(ConstraintRecordStatus))
def test_constraint_markers_do_not_admit_uncorroborated_source(tmp_path, source_kind, status):
    store = FileSystemCAS(tmp_path / "constraints")
    source = store.put_json(
        {"source_kind": source_kind, "status": status, "not_an_owner_evaluation": True},
        PutOptions(kind="gy.constraint_fixture", media_type="application/json"),
    )
    store.get_bytes(source.artifact_id)
    store.get_manifest(source.artifact_id)
    with pytest.raises(ValueError, match="constraint_requirement_basis_required"):
        ConstraintStoreIngestor().ingest(
            snapshot_id="unverified",
            grammar_expansion_ref=str(source.artifact_id),
            artifacts=[
                {
                    "source_kind": source_kind,
                    "status": status,
                    "artifact_ref": str(source.artifact_id),
                }
            ],
        )


def test_empty_constraint_basis_is_not_an_admitted_empty_population():
    with pytest.raises(ValueError, match="constraint_requirement_basis_required"):
        ConstraintStoreIngestor().ingest(
            snapshot_id="missing", grammar_expansion_ref="unresolved", artifacts=[]
        )


def test_present_constraint_ref_requires_actual_owner_readback(recorded_panel_owner):
    store, binding, state = _method_owner_case(recorded_panel_owner)
    unrelated = store.put_json(
        {"constraint_records": [], "not_a_constraint_evaluation": True},
        PutOptions(kind="gy.constraint_fixture", media_type="application/json"),
    )
    with pytest.raises(ValueError, match="constraint"):
        FoundryMethodOutputConsumer(store=store).consume_from_state(
            workspace_id="ws-unverified-constraint",
            operation_invocation_id="invoke-unverified-constraint",
            operation_class=OperationClass.ESTIMATE,
            state=state,
            measurement_root_ref=binding.observational_data_ref,
            binding_receipt_ref=binding.binding_receipt_ref,
            constraint_store_ref=str(unrelated.artifact_id),
        )


def test_missing_constraint_basis_is_persisted_and_recomputed(tmp_path):
    from polisyos.core.canon import from_canonical_bytes

    store = FileSystemCAS(tmp_path / "constraints")
    owner = ConstraintStoreIngestor(store=store)
    result = owner.produce(
        workspace_id="ws-missing-constraints", design_problem=_constraint_canonical_problem()
    )
    packet = from_canonical_bytes(owner.require(result, workspace_id=result.workspace_id))
    assert "snapshot" in packet
    assert packet["snapshot"] is None
    assert packet["population"] is None
    assert packet["missing_basis"] == ["constraint_requirement_basis_missing"]
    decision = evaluate_constraint_store_for_phase2(
        result, owner=owner, workspace_id=result.workspace_id
    )
    assert decision.blocks_promotion is True
    assert "constraint_requirement_basis_missing" in decision.blocking_constraint_ids
    manifest = store.get_manifest(result.artifact_ref.artifact_id)
    assert len(manifest.inputs) == 1
    assert manifest.inputs[0].role == "design_problem"
    for ref in manifest.inputs:
        store.get_bytes(ref.artifact_id)
        store.get_manifest(ref.artifact_id)


def test_compiled_constraint_preflight_derives_whole_owner_population_without_positive_authority(
    tmp_path,
):
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.ir.governance.policy_composition import PolicyLayerLevel
    from tests.unit.policy_grammar.test_universal_policy_grammar_compiler import (
        _authority_profile,
        _concept_spine_refs,
    )

    store = FileSystemCAS(tmp_path / "constraints")
    owner = ConstraintStoreIngestor(store=store)
    problem = _constraint_canonical_problem()
    basis = constraint_owner.Phase2RequirementBasis(
        authority_profile=_authority_profile(PolicyLayerLevel.LOCAL),
        concept_spine_refs=_concept_spine_refs(problem.design_problem_id),
    )
    result = owner.produce(
        workspace_id="ws-constraint-preflight", design_problem=problem, basis=basis
    )
    packet = from_canonical_bytes(owner.require(result, workspace_id=result.workspace_id))
    assert result.decision.blocks_promotion is True
    assert "constraint_source_authority_verification_missing" in result.missing_basis
    assert "method_validity" in packet["authority_boundary"]["may_not_use_for"]
    parents = {
        ref["role"]: ref["artifact_id"]
        for ref in packet["parent_refs"]
        if ref["role"] in {"obligation_graph", "claim_ledger", "method_preflight"}
    }
    if "obligation_graph" not in parents:
        assert "constraint_grammar_not_admitted" in packet["missing_basis"]
        return
    graph = from_canonical_bytes(store.get_bytes(parents["obligation_graph"]))["source_payload"]
    assert set(packet["population"]["obligation"]) == {
        row["bundle_id"] for row in graph["bundle_ledger"]
    }
    # Actual owner may refuse a non-compilable canonical request. It must not
    # manufacture claims just to keep a method denominator nonempty.
    if "claim_ledger" in parents:
        ledger = from_canonical_bytes(store.get_bytes(parents["claim_ledger"]))["source_payload"]
        assert set(packet["population"]["claim"]) == {row["claim_id"] for row in ledger["claims"]}
        preflight = from_canonical_bytes(store.get_bytes(parents["method_preflight"]))[
            "source_payload"
        ]
        assert set(packet["population"]["method_requirement"]) == set(
            preflight["method_requirement_statuses"]
        )
        if preflight["method_requirement_statuses"]:
            assert all(
                status == "missing" for status in preflight["method_requirement_statuses"].values()
            )
        else:
            assert (
                "constraint_method_requirement_population_not_established"
                in packet["missing_basis"]
            )


@pytest.mark.parametrize(
    "mutation", ["nested_decision", "deserialized", "new_owner", "wrong_workspace"]
)
def test_constraint_admission_cannot_be_recreated_or_mutated(tmp_path, mutation):
    store = FileSystemCAS(tmp_path / "constraints")
    owner = ConstraintStoreIngestor(store=store)
    result = owner.produce(
        workspace_id="ws-constraint-custody", design_problem=_constraint_canonical_problem()
    )
    workspace_id = result.workspace_id
    if mutation == "nested_decision":
        result.decision.blocking_constraint_ids.clear()
    elif mutation == "deserialized":
        result = constraint_owner.Phase2ConstraintAdmission.model_validate(
            result.model_dump(mode="json")
        )
    elif mutation == "new_owner":
        owner = ConstraintStoreIngestor(store=store)
    else:
        workspace_id = "different-workspace"
    with pytest.raises(ValueError, match="constraint_admission_not_owner_verified"):
        evaluate_constraint_store_for_phase2(result, owner=owner, workspace_id=workspace_id)


def test_constraint_readback_rejects_changed_decisive_bytes_with_markers_intact(
    tmp_path, monkeypatch
):
    from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes

    store = FileSystemCAS(tmp_path / "constraints")
    owner = ConstraintStoreIngestor(store=store)
    result = owner.produce(
        workspace_id="ws-constraint-corruption", design_problem=_constraint_canonical_problem()
    )
    artifact_id = str(result.artifact_ref.artifact_id)
    original = store.get_bytes

    def altered(ref):
        raw = original(ref)
        if str(ref) == artifact_id:
            packet = from_canonical_bytes(raw)
            packet["decision"]["blocks_promotion"] = False
            return to_canonical_bytes(packet, CanonSpec(forbid_floats=False, exclude_none=False))
        return raw

    monkeypatch.setattr(store, "get_bytes", altered)
    with pytest.raises(ValueError, match="artifact_byte_or_manifest_identity_mismatch"):
        evaluate_constraint_store_for_phase2(result, owner=owner, workspace_id=result.workspace_id)


def test_method_consumption_binds_constraint_custody_and_uses_sealed_decision(recorded_panel_owner):
    from polisyos.core.canon import from_canonical_bytes

    store, binding, state = _method_owner_case(recorded_panel_owner)
    owner = ConstraintStoreIngestor(store=store)
    admission = owner.produce(
        workspace_id="ws-c3-direct-method-owner", design_problem=_constraint_canonical_problem()
    )
    consumer = FoundryMethodOutputConsumer(store=store)
    result = consumer.consume_from_state(
        workspace_id=admission.workspace_id,
        operation_invocation_id="invoke-constraints",
        operation_class=OperationClass.ESTIMATE,
        state=state,
        measurement_root_ref=binding.observational_data_ref,
        binding_receipt_ref=binding.binding_receipt_ref,
        constraint_store_ref=str(admission.artifact_ref.artifact_id),
        constraint_owner=owner,
        constraint_admission=admission,
    )
    emitted = consumer.persist_consumption(store=store, consumption=result)
    payload = from_canonical_bytes(store.get_bytes(emitted.artifact_id))
    assert payload["constraint_decision"]["blocks_promotion"] is True
    manifest = store.get_manifest(emitted.artifact_id)
    assert {str(ref.artifact_id) for ref in manifest.inputs if ref.role == "constraint_store"} == {
        result.record.constraint_store_ref
    }
    assert result.record.constraint_store_ref != str(admission.artifact_ref.artifact_id)
    post = from_canonical_bytes(store.get_bytes(result.record.constraint_store_ref))
    assert post["evaluation_phase"] == "post_execution_reconciliation"
    assert post["method_report_ref"] is not None


def test_actual_phase2_loop_records_constraint_refusal_before_earlier_source_block(tmp_path):
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.runtime.quality.workspace.loop import WorkspaceLoop

    store = FileSystemCAS(tmp_path / "constraints")
    result = WorkspaceLoop(artifact_store=store).run_intent(_constraint_canonical_problem())
    assert result.constraint_admission is not None
    ref = result.constraint_admission.artifact_ref
    packet = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    assert packet["missing_basis"] == ["constraint_requirement_basis_missing"]
    blockers = [item for item in result.search_blockers if item.blocked_port == "constraint_store"]
    assert {item.missing_input for item in blockers} == set(
        packet["decision"]["blocking_constraint_ids"]
    )
    assert {item.applicability_result_ref for item in blockers} == {str(ref.artifact_id)}
    assert {item.severity for item in blockers} == {"blocks_authority"}


def _post_method_constraints(recorded_panel_owner):
    store, binding, state = _method_owner_case(recorded_panel_owner)
    consumer = FoundryMethodOutputConsumer(store=store)
    consumption = _consume_case(store, binding, state, consumer=consumer)
    owner = ConstraintStoreIngestor(store=store)
    preflight = owner.produce(
        workspace_id=consumption.record.workspace_id,
        design_problem=_constraint_canonical_problem(),
    )
    return store, binding, state, consumer, consumption, owner, preflight


def test_real_method_report_is_reconciled_before_constraint_consumption_without_reexecution(
    recorded_panel_owner, monkeypatch
):
    from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
    from polisyos.foundry.validation import method_quality
    from polisyos.scientist.compute import MethodBackend

    store, binding, state, consumer, consumption, owner, preflight = _post_method_constraints(
        recorded_panel_owner
    )
    report_calls = []
    build = method_quality.build_foundry_method_report_from_execution_outputs

    def real_report(**kwargs):
        result = build(**kwargs)
        report_calls.append((kwargs, result))
        return result

    def duplicate_execution(*args, **kwargs):
        raise AssertionError("Constraint reconciliation may not execute the method twice")

    monkeypatch.setattr(
        method_quality, "build_foundry_method_report_from_execution_outputs", real_report
    )
    monkeypatch.setattr(MethodBackend, "run", duplicate_execution)
    admission = owner.reconcile_method(preflight, method_owner=consumer, consumption=consumption)
    result = consumer.bind_constraints(consumption=consumption, owner=owner, admission=admission)
    emitted = consumer.persist_consumption(store=store, consumption=result)
    packet = from_canonical_bytes(owner.require(admission, workspace_id=admission.workspace_id))
    assert packet["evaluation_phase"] == "post_execution_reconciliation"
    assert packet["population"] is None  # Missing original basis is not an empty population.
    assert packet["missing_basis"] == ["constraint_requirement_basis_missing"]
    assert packet["method_report_ref"] is not None
    assert str(admission.artifact_ref.artifact_id) != str(preflight.artifact_ref.artifact_id)
    actual_result_ref = state.artifacts_index["causal_method_result_ref"]
    actual_evidence_ref = state.artifacts_index["causal_method_evidence_ref"]
    expected_output = {
        "method_result": from_canonical_bytes(store.get_bytes(actual_result_ref.artifact_id)),
        "method_evidence": from_canonical_bytes(store.get_bytes(actual_evidence_ref.artifact_id)),
        "method_result_ref": str(actual_result_ref.artifact_id),
        "method_evidence_ref": str(actual_evidence_ref.artifact_id),
        "input_refs": {"observational_data_ref": str(binding.observational_data_ref.artifact_id)},
    }
    assert report_calls
    assert all(call["method_outputs"] == [expected_output] for call, _ in report_calls)
    report = from_canonical_bytes(store.get_bytes(packet["method_report_ref"]))["source_payload"]
    # Compare the complete owner's declared wire representation. Its native
    # tuple fields become JSON arrays; nulls and every substantive field remain.
    assert report == from_canonical_bytes(
        to_canonical_bytes(
            report_calls[-1][1], CanonSpec(forbid_floats=False, exclude_none=False)
        )
    )
    assert {row["method_id"] for row in report["candidate_methods"]} == {binding.receipt.method_fqn}
    payload = from_canonical_bytes(store.get_bytes(emitted.artifact_id))
    assert payload["record"]["constraint_store_ref"] == str(admission.artifact_ref.artifact_id)
    assert payload["constraint_decision"] == packet["decision"]
    assert "method_validity" in packet["authority_boundary"]["may_not_use_for"]
    assert "causal_identification" in payload["authority_boundary"]["may_not_use_for"]
    assert {
        str(ref.artifact_id)
        for ref in store.get_manifest(emitted.artifact_id).inputs
        if ref.role == "constraint_store"
    } == {str(admission.artifact_ref.artifact_id)}


@pytest.mark.parametrize(
    "mutation", ["deserialized", "different_owner", "different_store", "changed_payload"]
)
def test_post_method_constraint_bridge_refuses_unverified_consumption(
    recorded_panel_owner, tmp_path, mutation
):
    store, _, _, consumer, consumption, owner, preflight = _post_method_constraints(
        recorded_panel_owner
    )
    if mutation == "deserialized":
        consumption = constraint_owner.FoundryConsumptionResult.model_validate(
            consumption.model_dump(mode="json")
        )
    elif mutation == "different_owner":
        consumer = FoundryMethodOutputConsumer(store=store)
    elif mutation == "different_store":
        consumer._store = FileSystemCAS(tmp_path / "different-store")
    else:
        consumption.authority_boundary.authoritative_for.append("method_validity")
    with pytest.raises(ValueError, match="foundry_consumption_verification_required"):
        owner.reconcile_method(preflight, method_owner=consumer, consumption=consumption)


def test_method_report_recomputation_is_consulted_at_constraint_admission(
    recorded_panel_owner, monkeypatch
):
    from polisyos.foundry.validation import method_quality

    _, _, _, consumer, consumption, owner, preflight = _post_method_constraints(
        recorded_panel_owner
    )
    admission = owner.reconcile_method(preflight, method_owner=consumer, consumption=consumption)
    real = method_quality.build_foundry_method_report_from_execution_outputs

    def removed_selection(**kwargs):
        report = real(**kwargs)
        # Keep every schema/authority/producer marker; remove the actual selected method.
        report["selected_methods"] = []
        report["candidate_methods"] = []
        return report

    monkeypatch.setattr(
        method_quality, "build_foundry_method_report_from_execution_outputs", removed_selection
    )
    with pytest.raises(ValueError, match="constraint_store_recomputation_mismatch"):
        consumer.bind_constraints(consumption=consumption, owner=owner, admission=admission)


def test_method_manifest_drift_cannot_be_reinterpreted_during_constraint_admission(
    recorded_panel_owner, monkeypatch
):
    from polisyos.core.artifacts import ProducerInfo

    _, _, state, consumer, consumption, owner, preflight = _post_method_constraints(
        recorded_panel_owner
    )
    store = owner._store
    original = store.get_manifest
    changed_id = str(state.artifacts_index["causal_method_evidence_ref"].artifact_id)

    def changed_manifest(artifact_id):
        manifest = original(artifact_id)
        if str(artifact_id) == changed_id:
            return manifest.model_copy(
                update={
                    "producer": ProducerInfo(
                        component="c3-custody-probe", version="unverified-substitution"
                    )
                }
            )
        return manifest

    monkeypatch.setattr(store, "get_manifest", changed_manifest)
    with pytest.raises(ValueError, match="foundry_consumption_source_custody_changed"):
        owner.reconcile_method(preflight, method_owner=consumer, consumption=consumption)


def test_method_emission_rechecks_the_bound_constraint_owner(recorded_panel_owner, monkeypatch):
    _, _, _, consumer, consumption, owner, preflight = _post_method_constraints(
        recorded_panel_owner
    )
    admission = owner.reconcile_method(preflight, method_owner=consumer, consumption=consumption)
    result = consumer.bind_constraints(consumption=consumption, owner=owner, admission=admission)
    original = owner._recompute

    def removed_missing_basis(raw):
        packet = original(raw)
        # Markers remain, but the decisive ceiling disappeared.
        packet["decision"]["blocks_promotion"] = False
        return packet

    monkeypatch.setattr(owner, "_recompute", removed_missing_basis)
    with pytest.raises(ValueError, match="constraint_store_recomputation_mismatch"):
        consumer.persist_consumption(store=owner._store, consumption=result)


def test_constraint_projection_bytes_bind_the_complete_parent_role_basis(tmp_path):
    from polisyos.core.canon import from_canonical_bytes

    store = FileSystemCAS(tmp_path / "constraints")
    owner = ConstraintStoreIngestor(store=store)
    parents = [
        store.put_json(
            {"source": name}, PutOptions(kind="test.source", media_type="application/json")
        )
        for name in ("first", "second")
    ]
    # The child content is identical. Only real source ancestry changes.
    emitted = [
        owner._persist(
            "gy.constraint_test_projection",
            {"same_content": True},
            [{"artifact_id": str(parent.artifact_id), "role": "source_basis"}],
        )
        for parent in parents
    ]
    assert len({str(ref.artifact_id) for ref in emitted}) == len(parents)
    for child, parent in zip(emitted, parents, strict=True):
        payload = from_canonical_bytes(store.get_bytes(child.artifact_id))
        manifest = store.get_manifest(child.artifact_id)
        expected = [{"artifact_id": str(parent.artifact_id), "role": "source_basis"}]
        assert payload["parent_refs"] == expected
        assert [
            {"artifact_id": str(ref.artifact_id), "role": ref.role} for ref in manifest.inputs
        ] == expected


@pytest.mark.parametrize("kind", ["gy.constraint_store", "gy.constraint_test_projection"])
@pytest.mark.parametrize("mutation", ["raw", "schema", "kind", "producer", "parents"])
def test_every_constraint_emission_requires_actual_full_readback(
    tmp_path, monkeypatch, kind, mutation
):
    from dataclasses import replace

    from polisyos.core.artifacts.manifest import InputRef, ProducerInfo, SchemaInfo
    from polisyos.core.canon import from_canonical_bytes

    store = FileSystemCAS(tmp_path / "constraints")
    owner = ConstraintStoreIngestor(store=store)
    source = store.put_json(
        {"actual_source": True}, PutOptions(kind="test.source", media_type="application/json")
    )
    parents = [{"artifact_id": str(source.artifact_id), "role": "source_basis"}]
    put = store.put_json

    def altered_put(payload, options, **kwargs):
        payload = from_canonical_bytes(constraint_owner._constraint_bytes(payload))
        if mutation == "raw":
            payload["changed_decisive_property"] = True
        elif mutation == "schema":
            options = replace(options, schema=SchemaInfo(name="unverified.schema", version="1.0"))
        elif mutation == "kind":
            options = replace(options, kind="unverified.kind")
        elif mutation == "producer":
            options = replace(
                options, producer=ProducerInfo(component="unverified.owner", version="1.0")
            )
        else:
            options = replace(
                options, inputs=[InputRef(artifact_id=source.artifact_id, role="different_role")]
            )
        return put(payload, options, **kwargs)

    monkeypatch.setattr(store, "put_json", altered_put)
    with pytest.raises(ValueError, match="constraint_emission_readback_mismatch"):
        owner._persist(kind, {"same_content": True, "parent_refs": parents}, parents)


def _staged_method_case(recorded_panel_owner, tmp_path):
    """Real owners over an engineering cassette; no canonical or safety claim."""
    import json
    from pathlib import Path

    from polisyos.data_forge.domains.ukraine.manifests import ArtifactRecord, BuildRunManifest
    from polisyos.foundry.data_plane import load_ukraine_foundry_intake, materialize_method_contract
    from polisyos.scientist.compute import MethodBackend
    from tests.unit.foundry.data_plane.test_bindings_multiscale import _ukraine_intake_manifests

    _, store, _, _ = recorded_panel_owner
    bound = _produce_recorded(recorded_panel_owner)
    root = tmp_path / "staged-source"
    root.mkdir()
    paths = _ukraine_intake_manifests(root)
    manifest = BuildRunManifest.model_validate_json(paths["d2"].read_bytes())
    selected = next(
        row for row in manifest.outputs if Path(row.path).name == "panel_observational_contract.json"
    )
    # The controlled stage consumes this same real recorded-owner cassette.
    # This is fixture setup before production, never recapture after a mutant.
    panel_path = Path(selected.path)
    panel_path.write_text(json.dumps(bound.contract_payload))
    outputs = [
        ArtifactRecord.from_path(panel_path) if row.path == selected.path else row
        for row in manifest.outputs
    ]
    paths["d2"].write_text(manifest.model_copy(update={"outputs": outputs}).model_dump_json())
    intake = load_ukraine_foundry_intake(store, stage_manifests=paths, allowed_root=root)
    refs = {
        "observations": bound.observational_data_ref,
        "recorded_input_binding": bound.binding_receipt_ref,
        "ukraine_selected_method_contract": intake.method_contract_refs["d2_panel_observational"],
        "ukraine_method_input_bundle": intake.method_input_bundle_ref,
        "ukraine_intake_receipt": intake.receipt_ref,
    }
    actual = MethodBackend().run(
        cas_root=store.root, method_fqn=bound.receipt.method_fqn, method_version=None,
        input_state=materialize_method_contract(
            contract_target=bound.contract_target, contract_payload=bound.contract_payload,
        ),
        method_params={"n_placebo_runs": 0}, seed=17, input_refs=refs,
    )
    state = ExperimentState(
        run_id="c3-staged-readback", observational_data_ref=bound.observational_data_ref,
        causal_method_fqn=bound.receipt.method_fqn,
        causal_method_params={"n_placebo_runs": 0}, params={"random_seed": 17},
        inputs={
            "ukraine_selected_foundry_method_contract_ref": refs["ukraine_selected_method_contract"],
            "ukraine_foundry_method_input_bundle_ref": refs["ukraine_method_input_bundle"],
        },
        artifacts_index={
            "ukraine_foundry_intake_receipt_ref": refs["ukraine_intake_receipt"],
            "foundry_input_binding_receipt_ref": bound.binding_receipt_ref,
            "causal_method_result_ref": actual.exec_artifacts.result_ref,
            "causal_method_evidence_ref": actual.exec_artifacts.evidence_ref,
        },
    )
    return store, bound, state, root, paths


def _staged_consumer(store, root, paths):
    """Keep the old-owner red on its actual refusal, not a missing new API."""
    import inspect

    from polisyos.runtime.quality.workspace import foundry_consumption as owner

    kwargs = {"store": store}
    if "staged_input_source" in inspect.signature(owner.FoundryMethodOutputConsumer).parameters:
        kwargs["staged_input_source"] = owner.StagedFoundryInputSource(
            allowed_root=root, stage_manifests=tuple(sorted(paths.items())),
        )
    return owner.FoundryMethodOutputConsumer(**kwargs)


def test_staged_intake_real_owner_is_consumed_without_weakening_measurement(recorded_panel_owner, tmp_path):
    store, bound, state, root, paths = _staged_method_case(recorded_panel_owner, tmp_path)
    consumer = _staged_consumer(store, root, paths)
    result = _consume_case(store, bound, state, consumer=consumer)
    assert result.method_replay_verified
    assert result.authority_boundary.evidence_kind == "measurement"
    assert result.authority_boundary.decision_grade == "descriptive_only"
    assert "causal_identification" in result.authority_boundary.may_not_use_for
    ref = consumer.persist_consumption(store=store, consumption=result)
    assert ref.content_hash == "sha256:" + hashlib.sha256(store.get_bytes(ref.artifact_id)).hexdigest()


def test_workspace_phase2_transports_verified_staged_input_owner_refs(recorded_panel_owner, tmp_path, monkeypatch):
    import inspect

    from polisyos.foundry import InputContractMethodSelection
    from polisyos.runtime.quality.workspace import foundry_consumption as owner
    from polisyos.runtime.quality.workspace import loop as loop_owner
    from tests.unit.runtime.quality.test_design_problem import _design_problem

    store, bound, offered, root, paths = _staged_method_case(recorded_panel_owner, tmp_path)
    source_fields = {"allowed_root": root, "stage_manifests": tuple(sorted(paths.items()))}
    kwargs = {"artifact_store": store}
    if "staged_foundry_inputs" in inspect.signature(loop_owner.WorkspaceLoop).parameters:
        kwargs["staged_foundry_inputs"] = owner.StagedFoundryInputBinding(
            source=owner.StagedFoundryInputSource(**source_fields), state=offered,
        )
    # Reuse the actual fixture owner's measured recipe; this is not a fake DTO
    # or a canonical production run. Current source validation still replays it.
    def recorded_owner(**arguments):
        assert arguments["store"] is store
        assert arguments["method_fqn"] == bound.receipt.method_fqn
        return bound

    monkeypatch.setattr(loop_owner, "produce_recorded_panel_method_input", recorded_owner)
    # Isolate transport here; the separate canonical route test exercises the
    # real method selector. This fixture carries no selection/admission claim.
    selected = InputContractMethodSelection.model_validate(
        {
            "status": "selected",
            "input_contract_id": bound.contract_target["contract_id"],
            "required_output_slots": ["report"],
            "selected_method_fqn": bound.receipt.method_fqn,
            "denominator_established": True,
            "denominator": [bound.receipt.method_fqn],
            "candidates": [{"method_fqn": bound.receipt.method_fqn, "disposition": "eligible"}],
            "ranked_method_fqns": [bound.receipt.method_fqn],
            "context_content_hash": "sha256:" + "3" * 64,
        }
    )
    monkeypatch.setattr(
        loop_owner, "_phase2_value_method_selection",
        lambda *args, **arguments: selected.model_dump(mode="json"),
    )
    problem = _design_problem(runtime_hints={"causal_method_fqn": bound.receipt.method_fqn})
    loop = loop_owner.WorkspaceLoop(**kwargs)
    state = loop._phase2_state(
        workspace_id="c3-staged-transport", intent=problem.to_workspace_intent(), design_problem=problem,
    )
    for key in ("ukraine_foundry_method_input_bundle_ref", "ukraine_selected_foundry_method_contract_ref"):
        assert state.inputs.get(key) == offered.inputs[key]
    key = "ukraine_foundry_intake_receipt_ref"
    assert state.artifacts_index.get(key) == offered.artifacts_index[key]
    assert state.observational_data_ref == bound.observational_data_ref


@pytest.mark.parametrize("mutation", ["source_output", "source_status", "bundle_body", "intake_lineage"])
def test_staged_intake_owner_readback_refuses_decisive_mutation(recorded_panel_owner, tmp_path, mutation, monkeypatch):
    import json
    from pathlib import Path

    from polisyos.core.artifacts import InputRef

    store, bound, state, root, paths = _staged_method_case(recorded_panel_owner, tmp_path)
    consumer = _staged_consumer(store, root, paths)
    if mutation == "source_output":
        manifest = json.loads(paths["d1"].read_bytes())
        output = Path(manifest["outputs"][0]["path"])
        payload = json.loads(output.read_bytes())
        payload["source_content_mutation"] = "not present at intake"
        output.write_text(json.dumps(payload))
    elif mutation == "source_status":
        payload = json.loads(paths["d0_p0"].read_bytes())
        payload["status"] = "failed"
        paths["d0_p0"].write_text(json.dumps(payload))
    elif mutation == "bundle_body":
        # Rebuild the entire CAS result lineage while preserving kind/schema,
        # so the deciding difference is the independently replayed owner body.
        old = state.inputs["ukraine_foundry_method_input_bundle_ref"]
        changed = _rewrite_artifact(
            store, old, lambda payload: payload["contracts"].pop(next(iter(payload["contracts"]))),
        )
        state.inputs["ukraine_foundry_method_input_bundle_ref"] = changed
        result_ref = state.artifacts_index["causal_method_result_ref"]
        result_manifest = store.get_manifest(result_ref.artifact_id)
        changed_result = _rewrite_artifact(
            store, result_ref, lambda payload: None,
            inputs=[InputRef(artifact_id=changed.artifact_id, role=item.role)
                    if item.artifact_id == old.artifact_id else item for item in result_manifest.inputs],
        )
        state.artifacts_index["causal_method_result_ref"] = changed_result
        state.artifacts_index["causal_method_evidence_ref"] = _rewrite_artifact(
            store, state.artifacts_index["causal_method_evidence_ref"],
            lambda payload: payload.update({"result_ref": str(changed_result.artifact_id)}),
            inputs=[InputRef(artifact_id=changed_result.artifact_id, role="method_result")],
        )
    else:
        # Change only persisted ancestry; source bytes and all artifact markers
        # stay intact. Fresh replay must not reuse this poisoned stored manifest.
        original_get = store.get_manifest
        intake_id = state.artifacts_index["ukraine_foundry_intake_receipt_ref"].artifact_id

        def get_manifest(artifact_id):
            manifest = original_get(artifact_id)
            if str(artifact_id) == str(intake_id):
                return manifest.model_copy(update={"inputs": []})
            return manifest

        monkeypatch.setattr(store, "get_manifest", get_manifest)
    with pytest.raises(ValueError):
        _consume_case(store, bound, state, consumer=consumer)


def _assert_workspace_context_reaches_actual_causal_safety_refusal(recorded_panel_owner, state=None):
    """A refusal-only port witness; this constructs no admitted authority."""
    import inspect
    from datetime import UTC, datetime

    from polisyos.pdc import (
        ArtifactRef,
        EvalSafetyConsumerAdmissionReceipt,
        EvaluationExecutionContext,
        EvaluationInputProvenance,
        evaluation_execution_context_hash,
    )
    from polisyos.runtime.quality.workspace.loop import WorkspaceLoop
    from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
        RunCausalEvaluationNode,
    )

    _, store, _, _ = recorded_panel_owner
    bound = _produce_recorded(recorded_panel_owner)
    node = RunCausalEvaluationNode()

    def fixture_ref(kind):
        return ArtifactRef(
            artifact_id="polisyos.test.c3." + kind, artifact_type=kind,
            content_hash="sha256:" + "1" * 64, schema_ref="polisyos.test." + kind + ".v1",
            uri="test://c3/" + kind, version="1.0",
        )

    if state is None:
        state = ExperimentState(
            run_id="c3-refusal-context", observational_data_ref=bound.observational_data_ref,
            causal_method_fqn=bound.receipt.method_fqn,
        )
    from polisyos.core import artifacts

    actual_refs = tuple(ArtifactRef(
        artifact_id=str(ref.artifact_id), artifact_type="observations",
        content_hash=str(ref.artifact_id), schema_ref="polisyos.test.observations.v1",
        uri="cas://" + str(ref.artifact_id), version="1.0",
    ) for ref in (artifacts.ArtifactRef.model_validate(raw) for raw in (
        state.observational_data_ref,
        state.inputs.get("ukraine_selected_foundry_method_contract_ref"),
        state.inputs.get("ukraine_foundry_method_input_bundle_ref"),
        state.artifacts_index.get("ukraine_foundry_intake_receipt_ref"),
    ) if raw is not None))
    context = EvaluationExecutionContext(
        intake_ref=fixture_ref("intake"), evaluator_owner_id=node.spec.metadata.component_id,
        design_problem_ref="sha256:" + "2" * 64, evaluation_mode="field_pilot",
        candidate_ref=fixture_ref("candidate"), world_model_record_ref=fixture_ref("world_model"),
        target_population_scope_ref=fixture_ref("population"), rule_version="polisyos.test.c3.v1",
        intended_start_at=datetime(2026, 9, 9, tzinfo=UTC),
        evaluation_input_refs=actual_refs,
        evaluation_input_provenance=tuple(EvaluationInputProvenance(
            input_ref=ref, input_class="real_world", predicate_provenance="recomputed",
        ) for ref in actual_refs),
        eval_safety_certificate_ref=None, eval_safety_revision_head_ref=None,
    )

    class RefusingVerifier:
        calls = 0

        def require_admission(self, supplied, challenge):
            self.calls += 1
            assert supplied == context
            return EvalSafetyConsumerAdmissionReceipt(
                status="blocked", intake_ref=supplied.intake_ref, certificate_ref=None,
                current_revision_head_ref=None,
                execution_context_hash=evaluation_execution_context_hash(supplied),
                challenge=challenge, blocker_codes=("polisyos.eval_safety.verifier_unappointed@1.0.0",),
                verified_at=datetime(2026, 9, 9, tzinfo=UTC),
            )

    verifier = RefusingVerifier()
    kwargs = {"artifact_store": store}
    if "eval_safety_execution_context" in inspect.signature(WorkspaceLoop).parameters:
        kwargs.update(eval_safety_execution_context=context, eval_safety_verifier=verifier)
    loop = WorkspaceLoop(**kwargs)
    actual_context, _ = loop._phase2_context(workspace_id="c3-refusal-context")
    outcome = node.execute(actual_context, state)
    assert outcome.status == "fail"
    assert verifier.calls == 1
    assert outcome.error.details["blocker_codes"] == ["polisyos.eval_safety.verifier_unappointed@1.0.0"]


def test_workspace_context_reaches_actual_causal_safety_refusal(recorded_panel_owner):
    _assert_workspace_context_reaches_actual_causal_safety_refusal(recorded_panel_owner)


def test_validated_staged_refs_reach_actual_causal_safety_refusal(recorded_panel_owner, tmp_path):
    from polisyos.core import artifacts
    from polisyos.runtime.quality.workspace.scientist_node_adapters import _validated_node_state

    _, _, state, _, _ = _staged_method_case(recorded_panel_owner, tmp_path)
    validated = _validated_node_state(state)
    assert all(isinstance(ref, artifacts.ArtifactRef) for mapping in (
        validated.inputs, validated.artifacts_index,
    ) for ref in mapping.values())
    _assert_workspace_context_reaches_actual_causal_safety_refusal(recorded_panel_owner, validated)


def test_staged_result_lineage_cannot_hide_supplied_intake_by_removing_state_slots(
    recorded_panel_owner, tmp_path,
):
    import json

    store, bound, state, _, paths = _staged_method_case(recorded_panel_owner, tmp_path)
    del state.inputs["ukraine_selected_foundry_method_contract_ref"]
    del state.inputs["ukraine_foundry_method_input_bundle_ref"]
    del state.artifacts_index["ukraine_foundry_intake_receipt_ref"]
    source = json.loads(paths["d0_p0"].read_text())
    source["status"] = "failed"
    paths["d0_p0"].write_text(json.dumps(source))
    # The real method's complete source lineage remains unchanged in CAS.
    # Missing replay context must refuse, even when state declarations vanish.
    with pytest.raises(ValueError):
        _consume_case(store, bound, state, consumer=FoundryMethodOutputConsumer(store=store))


@pytest.mark.parametrize("mutation", [
    "source_object", "root_type", "manifest_container", "row_type",
    "stage_type", "stage_empty", "path_type", "duplicate_stage",
])
def test_staged_intake_malformed_transport_is_typed_refusal(recorded_panel_owner, tmp_path, mutation):
    from polisyos.runtime.quality.workspace import foundry_consumption as owner

    store, bound, state, root, paths = _staged_method_case(recorded_panel_owner, tmp_path)
    rows = tuple(sorted(paths.items()))
    if mutation == "source_object":
        source = {"allowed_root": root, "stage_manifests": rows}
    else:
        if mutation == "root_type":
            root = str(root)
        elif mutation == "manifest_container":
            rows = list(rows)
        elif mutation == "row_type":
            rows = (list(rows[0]), *rows[1:])
        elif mutation == "stage_type":
            rows = ((True, rows[0][1]), *rows[1:])
        elif mutation == "stage_empty":
            rows = (("", rows[0][1]), *rows[1:])
        elif mutation == "path_type":
            rows = ((rows[0][0], str(rows[0][1])), *rows[1:])
        elif mutation == "duplicate_stage":
            rows = (*rows, rows[0])
        source = owner.StagedFoundryInputSource(allowed_root=root, stage_manifests=rows)
    consumer = owner.FoundryMethodOutputConsumer(store=store, staged_input_source=source)
    with pytest.raises(ValueError, match="foundry_staged_intake_source"):
        _consume_case(store, bound, state, consumer=consumer)


@pytest.mark.parametrize("remaining_slot", [
    "ukraine_selected_foundry_method_contract_ref",
    "ukraine_foundry_method_input_bundle_ref",
    "ukraine_foundry_intake_receipt_ref",
])
def test_staged_manifest_presence_requires_complete_intake(recorded_panel_owner, tmp_path, remaining_slot):
    store, bound, state, _, _ = _staged_method_case(recorded_panel_owner, tmp_path)
    for mapping, slots in (
        (state.inputs, ("ukraine_selected_foundry_method_contract_ref", "ukraine_foundry_method_input_bundle_ref")),
        (state.artifacts_index, ("ukraine_foundry_intake_receipt_ref",)),
    ):
        for slot in slots:
            if slot != remaining_slot:
                mapping.pop(slot)
    # No source coordinates were supplied. A remaining part of the manifest
    # must not become the independent recorded-input path by omission.
    with pytest.raises(ValueError, match="foundry_staged_intake_source_verification_missing"):
        _consume_case(store, bound, state)


def test_staged_input_refusal_retains_completed_selection_in_typed_terminal(
    recorded_panel_owner,
    tmp_path,
    monkeypatch,
):
    """Transport-only selection fixture; actual staged installer must refuse it.

    This test does not measure the registry population, grant selection authority,
    run a causal node, or make a canonical C3 success claim.
    """
    from polisyos.foundry import InputContractMethodSelection
    from polisyos.runtime.quality.workspace import foundry_consumption as owner
    from polisyos.runtime.quality.workspace import loop as loop_owner
    from tests.unit.runtime.quality.test_design_problem import _design_problem

    store, bound, offered, root, paths = _staged_method_case(recorded_panel_owner, tmp_path)
    offered = offered.model_copy(deep=True)
    missing_slot = "ukraine_foundry_method_input_bundle_ref"
    del offered.inputs[missing_slot]
    binding = owner.StagedFoundryInputBinding(
        source=owner.StagedFoundryInputSource(
            allowed_root=root,
            stage_manifests=tuple(sorted(paths.items())),
        ),
        state=offered,
    )
    selected = InputContractMethodSelection.model_validate(
        {
            "status": "selected",
            "input_contract_id": bound.contract_target["contract_id"],
            "required_output_slots": ["report"],
            "selected_method_fqn": bound.receipt.method_fqn,
            "denominator_established": True,
            "denominator": [bound.receipt.method_fqn],
            "candidates": [{"method_fqn": bound.receipt.method_fqn, "disposition": "eligible"}],
            "ranked_method_fqns": [bound.receipt.method_fqn],
            "context_content_hash": "sha256:" + "3" * 64,
        }
    )
    # Selection itself is separately verified by the selector owner's tests.
    # Here only its complete typed return must survive a later real refusal.
    monkeypatch.setattr(
        loop_owner,
        "_phase2_value_method_selection",
        lambda *a, **k: selected.model_dump(mode="json"),
    )

    def recorded_owner(**arguments):
        assert arguments["store"] is store
        assert arguments["method_fqn"] == bound.receipt.method_fqn
        return bound

    monkeypatch.setattr(loop_owner, "produce_recorded_panel_method_input", recorded_owner)
    # Context construction is outside this transport test; the real state path
    # refuses before any adapter or safety execution can consult this context.
    monkeypatch.setattr(loop_owner.WorkspaceLoop, "_phase2_context", lambda *a, **k: (None, None))
    actual_installer = loop_owner.install_verified_staged_foundry_inputs
    observed_refusals = []

    def install(**arguments):
        try:
            return actual_installer(**arguments)
        except ValueError as exc:
            observed_refusals.append(str(exc))
            raise

    monkeypatch.setattr(loop_owner, "install_verified_staged_foundry_inputs", install)
    problem = _design_problem(runtime_hints={"causal_method_fqn": bound.receipt.method_fqn})
    result = loop_owner.WorkspaceLoop(
        artifact_store=store,
        staged_foundry_inputs=binding,
    ).run_intent(problem)
    assert observed_refusals == ["foundry_staged_intake_input_missing:" + missing_slot]
    assert result.terminal_state.kind.value == "search_ceiling_repair_required"
    assert result.authority_boundary is None
    assert result.operation_invocations == []
    assert result.artifact_envelopes == []
    assert result.method_output_consumption_ref is None
    assert (
        "foundry_staged_intake_verification_missing:" + observed_refusals[0]
        in result.search_blockers[0].reason
    )
    assert result.phase2_method_selection == selected
