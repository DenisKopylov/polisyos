from __future__ import annotations

import hashlib

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.pdc import OperationClass
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


def test_governed_requirement_artifacts_become_constraint_store_entries() -> None:
    snapshot = ConstraintStoreIngestor().ingest(
        snapshot_id="constraint-store-phase2",
        grammar_expansion_ref="pdc://phase2/grammar",
        artifacts=[
            {
                "artifact_ref": "obligation://legal-authority",
                "source_kind": "obligation",
                "status": "block",
                "consumer_ref": "ESTIMATE",
                "reason": "Legal authority must be verified.",
            },
            {
                "artifact_ref": "participation://affected-firms",
                "source_kind": "participation_requirement",
                "status": "limit",
                "consumer_ref": "SIMULATE",
                "reason": "Affected firms were not sampled.",
            },
            {
                "artifact_ref": "method-requirement://causal-identification",
                "source_kind": "method_requirement",
                "status": "block",
                "consumer_ref": "VERIFY",
                "reason": "Identification method required.",
            },
        ],
    )

    assert len(snapshot.constraint_records) == 3
    assert set(snapshot.hard_constraint_ids) >= {
        "phase2.obligation.legal-authority",
        "phase2.method_requirement.causal-identification",
    }
    assert snapshot.governance_owned_gap_ids == [
        "phase2.obligation.legal-authority",
        "phase2.method_requirement.causal-identification",
    ]


def test_constraint_ingestor_rejects_free_text_inferred_constraints() -> None:
    with pytest.raises(ValueError, match="governed artifact"):
        ConstraintStoreIngestor().ingest(
            snapshot_id="constraint-store-phase2",
            grammar_expansion_ref="pdc://phase2/grammar",
            artifacts=[
                {
                    "text": "probably needs public consultation",
                    "source_kind": "free_text",
                    "status": "block",
                    "consumer_ref": "VERIFY",
                    "reason": "inferred",
                }
            ],
        )


def test_constraint_store_snapshot_is_consumed_by_phase2_authority_gate() -> None:
    snapshot = ConstraintStoreIngestor().ingest(
        snapshot_id="constraint-store-phase2",
        grammar_expansion_ref="pdc://phase2/grammar",
        artifacts=[
            {
                "artifact_ref": "obligation://legal-authority",
                "source_kind": "obligation",
                "status": "block",
                "consumer_ref": "VERIFY",
                "reason": "Legal authority must be verified.",
            },
            {
                "artifact_ref": "participation://affected-firms",
                "source_kind": "participation_requirement",
                "status": "limit",
                "consumer_ref": "ESTIMATE",
                "reason": "Affected firms were not sampled.",
            },
        ],
    )

    decision = evaluate_constraint_store_for_phase2(snapshot)

    assert decision.blocks_promotion is True
    assert decision.downgrades_authority is True
    assert decision.blocking_constraint_ids == ["phase2.obligation.legal-authority"]
    assert decision.limiting_constraint_ids == ["phase2.participation_requirement.affected-firms"]
