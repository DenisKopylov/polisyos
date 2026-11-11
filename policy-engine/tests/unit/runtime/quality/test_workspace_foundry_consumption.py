from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, get_args

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


def _assert_claim_grammar_warnings_match_source_context(claim: Mapping[str, Any]) -> None:
    claim_metadata = claim["metadata"]
    contexts = claim_metadata["source_facet_contexts"]
    expected = set()
    for context in contexts:
        metadata = context["metadata"]
        codes = metadata.get("grammar_limitations", ())
        messages = metadata.get("grammar_limitation_messages", ())
        details = metadata.get("grammar_limitation_details", ())
        for code, message, detail in zip(codes, messages, details, strict=True):
            expected.add(
                json.dumps(
                    [code, message, dict(detail), metadata.get("semantic_scope_provenance")],
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
    observed = {
        json.dumps(
            [
                row["code"],
                row["message"],
                row["details"],
                row["semantic_scope_provenance"],
            ],
            ensure_ascii=False,
            sort_keys=True,
        )
        for row in claim_metadata["grammar_limitation_records"]
    }
    assert observed == expected
    context_refs = {row["facet_ref"] for row in contexts}
    assert all(
        set(row["source_facet_refs"]).issubset(context_refs)
        for row in claim_metadata["grammar_limitation_records"]
    )


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


def test_foundry_input_resolution_uses_selected_profile_to_recover_kind(tmp_path):
    """A selected lineage edge can recover its own kind when defaults differ."""
    from types import SimpleNamespace

    from polisyos.core.artifacts import InputRef
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions

    store = FileSystemCAS(tmp_path / "selected-input-kind")
    source_bytes = b'{"source":"same-content"}'
    default_ref = store.put_bytes(
        source_bytes,
        ArtifactWriteOptions(
            kind="test.foundry.default-kind",
            media_type="application/json",
        ),
    )
    selected_ref = store.put_bytes(
        source_bytes,
        ArtifactWriteOptions(
            kind="test.foundry.selected-kind",
            media_type="application/json",
        ),
    )
    assert default_ref.artifact_id == selected_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None
    result_ref = store.put_bytes(
        b'{"result":true}',
        ArtifactWriteOptions(
            kind="test.foundry.method-result",
            media_type="application/json",
            inputs=[
                InputRef(
                    artifact_id=selected_ref.artifact_id,
                    role="input:observations",
                    manifest_profile_sha256=selected_ref.manifest_profile_sha256,
                )
            ],
        ),
    )
    result_manifest = store.get_manifest(result_ref)

    resolved = constraint_owner._verified_method_input_refs(
        store,
        result_manifest,
        SimpleNamespace(inputs={}, artifacts_index={}),
        None,
    )

    assert resolved["observations"].kind == "test.foundry.selected-kind"
    assert resolved["observations"].manifest_profile_sha256 == selected_ref.manifest_profile_sha256
    assert store.get_bytes(resolved["observations"]) == source_bytes


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
    "changed_member",
    [
        "result",
        "evidence",
        "input_lineage",
        "seed",
        "cost",
        "timing",
        "manifest_profile",
    ],
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
    elif changed_member == "manifest_profile":
        changed_profile = _rewrite_artifact(
            store,
            original_evidence,
            lambda payload: None,
            inputs=[
                InputRef(
                    artifact_id=original_result.artifact_id,
                    role="tampered_method_result",
                )
            ],
        )
        assert changed_profile.artifact_id == original_evidence.artifact_id
        assert changed_profile.manifest_profile_sha256 != original_evidence.manifest_profile_sha256
        state.artifacts_index["causal_method_evidence_ref"] = changed_profile
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
        "manifest_profile": "foundry_method_artifact_identity_mismatch",
        "cost": "foundry_method_cost_attribution_mismatch",
        "timing": "foundry_method_timing_observation_invalid",
    }[changed_member]
    with pytest.raises(ValueError, match=expected_reason):
        _consume_case(store, binding, state)


def test_method_evidence_semantic_projection_retains_attempt_cost_and_provenance(
    recorded_panel_owner,
):
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.foundry.methods.backends.dispatch import (
        estimate_method_execution_cost_usd,
    )
    from polisyos.foundry.methods.backends.protocol import MethodTiming
    from polisyos.foundry.methods.base import ComputeBackend

    store, _, state = _method_owner_case(recorded_panel_owner)
    original_ref = state.artifacts_index["causal_method_evidence_ref"]
    original_raw = store.get_bytes(original_ref.artifact_id)
    original_payload = from_canonical_bytes(original_raw)
    original_cost = original_payload["artifacts"]["cost_attribution"]
    original_timing = MethodTiming(
        wall_time_ms=original_cost["wall_time_ms"],
        cpu_time_ms=original_cost["cpu_time_ms"],
        compile_time_ms=original_cost["compile_time_ms"],
    )
    assert original_cost["estimated_cost_usd"] == estimate_method_execution_cost_usd(
        backend=ComputeBackend(original_cost["backend"]),
        timing=original_timing,
    )

    changed_wall_time_ms = float(original_cost["wall_time_ms"]) + 7.0
    changed_timing = MethodTiming(
        wall_time_ms=changed_wall_time_ms,
        cpu_time_ms=original_cost["cpu_time_ms"],
        compile_time_ms=original_cost["compile_time_ms"],
    )
    changed_cost_usd = estimate_method_execution_cost_usd(
        backend=ComputeBackend(original_cost["backend"]),
        timing=changed_timing,
    )

    def change_attempt_cost(payload):
        cost = payload["artifacts"]["cost_attribution"]
        cost["wall_time_ms"] = changed_wall_time_ms
        cost["estimated_cost_usd"] = changed_cost_usd

    changed_cost_ref = _rewrite_artifact(store, original_ref, change_attempt_cost)
    changed_cost_raw = store.get_bytes(changed_cost_ref.artifact_id)
    changed_cost_payload = from_canonical_bytes(changed_cost_raw)
    assert changed_cost_ref.artifact_id != original_ref.artifact_id
    assert changed_cost_payload["result_ref"] == original_payload["result_ref"]
    assert (
        changed_cost_payload["artifacts"]["cost_attribution"]["wall_time_ms"]
        != (original_cost["wall_time_ms"])
    )
    assert changed_cost_payload["artifacts"]["cost_attribution"]["estimated_cost_usd"] == (
        changed_cost_usd
    )
    assert original_raw != changed_cost_raw
    assert constraint_owner._method_evidence_semantics(original_raw) == (
        constraint_owner._method_evidence_semantics(changed_cost_raw)
    )

    changed_semantic_ref = _rewrite_artifact(
        store,
        original_ref,
        lambda payload: payload["reproducibility"].update(
            {"seed": int(payload["reproducibility"]["seed"] or 0) + 1}
        ),
    )
    changed_semantic_raw = store.get_bytes(changed_semantic_ref.artifact_id)
    assert constraint_owner._method_evidence_semantics(original_raw) != (
        constraint_owner._method_evidence_semantics(changed_semantic_raw)
    )


@pytest.mark.parametrize(
    "changed_member", ["authority", "record", "constructed", "new_consumer", "store"]
)
def test_foundry_emission_refuses_unverified_or_changed_consumption(
    recorded_panel_owner,
    changed_member,
):
    from polisyos.runtime.quality.workspace.foundry_consumption import (
        FoundryConsumptionResult,
    )

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
        PutOptions(
            kind="scientist.method_result.causal.inference",
            media_type="application/json",
        ),
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


def test_method_result_evidence_join_rejects_same_bytes_other_selected_profile(
    recorded_panel_owner,
):
    store, binding, state = _method_owner_case(recorded_panel_owner)
    selected_ref = state.artifacts_index["causal_method_result_ref"]
    alternate_ref = _different_profile_artifact_view(store, selected_ref)
    assert alternate_ref.artifact_id == selected_ref.artifact_id
    assert alternate_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256
    assert store.get_bytes(alternate_ref) == store.get_bytes(selected_ref)
    state.artifacts_index["causal_method_result_ref"] = alternate_ref

    with pytest.raises(ValueError, match="foundry_method_artifact_identity_mismatch"):
        _consume_case(store, binding, state)


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
        workspace_id="ws-missing-constraints",
        design_problem=_constraint_canonical_problem(),
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


def test_selected_component_graph_preserves_modes_to_every_causal_consumer() -> None:
    from datetime import UTC, datetime
    from hashlib import sha256

    from polisyos.foundry.methods.selection import select_method_candidates_for_requirements
    from polisyos.ir.observation import IdentificationMode
    from polisyos.method_requirement import compile_method_validity_requirements
    from polisyos.obligation_graph import (
        ComplexityBudget,
        GovernedObligationRule,
        compile_obligation_graph,
    )
    from polisyos.policy_grammar import PolicyGrammarCompiler, facet_snapshots_for_obligation_graph
    from polisyos.scientist.policy_design import compile_claim_decomposition
    from tests.unit.policy_grammar.test_component_policy_grammar import (
        _authority,
        _intent,
        _refs,
    )

    case = PolicyGrammarCompiler().compile(
        intent=_intent(),
        authority_profile=_authority(),
        concept_spine_refs=_refs(),
    )
    facet_rows = facet_snapshots_for_obligation_graph(case)
    modes = (IdentificationMode.SEQUENTIAL, IdentificationMode.BOUNDS_ONLY)
    rules = [
        GovernedObligationRule(
            rule_id=f"rule:causal-mode:{mode.value}",
            rule_family="causal_effect",
            rule_version="2026.11",
            logic_hash="sha256:" + sha256(mode.value.encode()).hexdigest(),
            owner="team-evidence",
            scope="national",
            authority_level="governed",
            evidence_basis="registered rule",
            public_revalidation_effect="review_affected_claim",
            obligation_text=f"Review the causal method contract for {mode.value}.",
            authority_profile="candidate",
            temporal_window="case_lifecycle",
            remedy_path="source_evidence",
            required_facets={"method_need": mode.value},
        )
        for mode in modes
    ]
    graph = compile_obligation_graph(
        run_id="run_w6d_selected_component_graph",
        facets=facet_rows,
        governed_rules=rules,
        generated_at=datetime(2026, 11, 11, tzinfo=UTC),
        complexity_budget=ComplexityBudget(max_frontier_items=8),
    )
    assert {row.bundle_key.component_id for row in graph.blocking_frontier} == {
        "delivery",
        "financing",
    }

    claim_input = constraint_owner._claim_decomposition_input_from_selected_graph(
        run_id=graph.run_id,
        intent="Assess the composed policy's causal effects.",
        graph=graph,
        concept_spine_refs=["concept://declared-action"],
        authority_profile_refs=[case.authority_profile.profile_id],
    )
    frontier_by_component = {row.bundle_key.component_id: row for row in graph.blocking_frontier}
    obligations_by_id = {row.obligation_id: row for row in claim_input.obligations}
    facet_by_id = {row.facet_id: row for row in claim_input.facets}
    for component_id, frontier in frontier_by_component.items():
        obligation = obligations_by_id[frontier.frontier_id]
        assert set(obligation.facet_refs) == set(frontier.metadata["component_facet_refs"])
        assert all(
            facet_by_id[facet_ref].metadata["component_id"] == component_id
            for facet_ref in obligation.facet_refs
        )

    assert all(
        "grammar_limitations" in row.metadata
        and "grammar_limitation_details" in row.metadata
        and row.metadata.get("semantic_scope_provenance") == "not_established"
        for row in claim_input.facets
    )
    ledger = compile_claim_decomposition(claim_input)
    causal_claims = [row for row in ledger.claims if row.claim_type.value == "causal"]
    assert len(causal_claims) == 4
    for claim in causal_claims:
        _assert_claim_grammar_warnings_match_source_context(claim.model_dump(mode="python"))
        mode_refs = [
            ref for ref in claim.facet_refs if facet_by_id[ref].facet_type == "method_need"
        ]
        assert len(mode_refs) == 1
        mode_facet = facet_by_id[mode_refs[0]]
        assert mode_facet.metadata["component_id"] in {"delivery", "financing"}
        assert mode_facet.value in {
            IdentificationMode.SEQUENTIAL.value,
            IdentificationMode.BOUNDS_ONLY.value,
        }
        assert any(
            precondition.method_need == mode_facet.value
            and mode_facet.facet_id in precondition.facet_refs
            for precondition in claim.method_need_preconditions
        )
        source_context = next(
            row
            for row in claim.metadata["source_facet_contexts"]
            if row["facet_ref"] == mode_facet.facet_id
        )
        assert source_context["metadata"] == mode_facet.metadata

    method_artifact = compile_method_validity_requirements(
        run_id=ledger.run_id,
        claims=ledger.claims,
    )
    causal_claim_ids = {row.claim_id for row in causal_claims}
    causal_requirements = [
        row for row in method_artifact.requirements if row.claim_id in causal_claim_ids
    ]
    assert len(causal_requirements) == len(causal_claims)
    assert all(requirement.metadata["source_facet_contexts"] for requirement in causal_requirements)
    candidates = []
    for mode in modes:
        candidates.append(
            {
                "method_id": f"causal.{mode.value}.runtime",
                "method_family": "causal_effect_estimation",
                "method_expectations": ["causal_effect_estimation", mode.value],
                "truthfulness_status": "runtime_consistent",
                "runtime_assumption_gates": [
                    {"assumption": "identification_assumptions", "status": "pass"},
                    {"assumption": "overlap_or_support", "status": "pass"},
                    {"assumption": "missingness_process", "status": "pass"},
                    {"assumption": "simulation_dgp_lineage", "status": "pass"},
                ],
                "uncertainty_refs": {
                    "uncertainty_envelope_ref": "sha256:" + sha256(mode.value.encode()).hexdigest()
                },
                "limitation_refs": {
                    "method_limitation_ref": "sha256:"
                    + sha256((mode.value + "limit").encode()).hexdigest()
                },
                "method_result_refs": {
                    "method_result_ref": "sha256:"
                    + sha256((mode.value + "result").encode()).hexdigest()
                },
            }
        )

    selection = select_method_candidates_for_requirements(
        candidate_methods=candidates,
        method_requirements=causal_requirements,
    )

    assert selection["status"] == "pass", selection
    assert set(selection["method_requirement_statuses"]) == {
        row.requirement_id for row in causal_requirements
    }
    assert set(selection["method_requirement_statuses"].values()) == {"satisfied"}
    selected_by_requirement = {
        requirement_ref: row["method_id"]
        for row in selection["selected_methods"]
        for requirement_ref in row["method_requirement_refs"]
    }
    assert set(selected_by_requirement) == {row.requirement_id for row in causal_requirements}
    for requirement in causal_requirements:
        mode = requirement.metadata["explicit_identification_mode_facets"][0]["identification_mode"]
        assert selected_by_requirement[requirement.requirement_id] == (f"causal.{mode}.runtime")


def test_selected_v1_graph_binds_single_case_method_mode_through_selector() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal
    from hashlib import sha256

    from polisyos.foundry.methods.selection import select_method_candidates_for_requirements
    from polisyos.ir.governance.policy_composition import PolicyLayerLevel
    from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.observation.contracts import IdentificationMode
    from polisyos.method_requirement import compile_method_validity_requirements
    from polisyos.obligation_graph import (
        ComplexityBudget,
        GovernedObligationRule,
        compile_obligation_graph,
    )
    from polisyos.policy_grammar import (
        PolicyGrammarCompiler,
        PolicyGrammarIntent,
        facet_snapshots_for_obligation_graph,
    )
    from polisyos.scientist.policy_design import compile_claim_decomposition
    from tests.unit.policy_grammar.test_universal_policy_grammar_compiler import (
        _authority_profile,
        _concept_spine_refs,
    )

    intent = PolicyGrammarIntent.from_problem_policy(
        intent_id="lane01_ec02_v1_sequential_case",
        problem_frame=ProblemFrame(
            problem_id="lane01_ec02_v1_sequential_problem",
            domain=ProblemDomain.HEALTHCARE,
            narrative=(
                "Phase a mobile clinic vaccination service for rural children during 2026 "
                "with public-service delivery, budget funding, and monitoring for coverage."
            ),
        ),
        policy_spec=PolicySpec(
            policy_id="lane01_ec02_v1_sequential_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="lane01_ec02_v1_mobile_clinic",
                    kind="service",
                    target=SelectorPredicate(
                        field="population",
                        operator="==",
                        value="children",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=12),
                    params={"monthly_budget": Decimal("1000")},
                    target_population_type="children",
                    target_region_ids=["rural"],
                    identification_mode=IdentificationMode.SEQUENTIAL,
                )
            ],
        ),
    )
    case = PolicyGrammarCompiler().compile(
        intent=intent,
        authority_profile=_authority_profile(PolicyLayerLevel.LOCAL),
        concept_spine_refs=_concept_spine_refs(intent.intent_id),
    )
    facets = facet_snapshots_for_obligation_graph(case)
    method_mode = IdentificationMode.SEQUENTIAL
    rule = GovernedObligationRule(
        rule_id="rule:causal-mode:sequential-v1",
        rule_family="causal_effect",
        rule_version="2026.11",
        logic_hash="sha256:" + sha256(method_mode.value.encode()).hexdigest(),
        owner="team-evidence",
        scope="national",
        authority_level="governed",
        evidence_basis="registered rule",
        public_revalidation_effect="review_affected_claim",
        obligation_text="Review the causal method contract for the selected policy case.",
        authority_profile="candidate",
        temporal_window="case_lifecycle",
        remedy_path="source_evidence",
        required_facets={"method_need": method_mode.value},
    )
    graph = compile_obligation_graph(
        run_id="run_w6d_selected_v1_graph",
        facets=facets,
        governed_rules=[rule],
        generated_at=datetime(2026, 11, 11, tzinfo=UTC),
        complexity_budget=ComplexityBudget(max_frontier_items=8),
    )
    assert len(graph.blocking_frontier) == 1
    frontier = graph.blocking_frontier[0]
    assert frontier.bundle_key.component_id is None
    candidate_metadata = frontier.metadata["candidate_metadata_refs"][frontier.candidate_refs[0]]
    selected_case_refs = tuple(candidate_metadata["selected_case_facet_refs"])
    assert set(candidate_metadata["matched_facet_refs"]) == {
        facet["facet_id"] for facet in facets if facet["facet_type"] == "method_need"
    }
    assert len(selected_case_refs) == len(facets)
    assert candidate_metadata["selected_case_binding"] == {
        "case_id": case.case_id,
        "scope": facets[0]["scope"],
        "authority_profile": facets[0]["authority_profile"],
        "temporal_window": facets[0]["temporal_window"],
    }

    claim_input = constraint_owner._claim_decomposition_input_from_selected_graph(
        run_id=graph.run_id,
        intent="Assess the causal effects of the selected policy case.",
        graph=graph,
        concept_spine_refs=[case.concept_spine_ref],
        authority_profile_refs=[case.authority_profile.profile_id],
    )
    selected_obligation = next(
        row for row in claim_input.obligations if row.obligation_id == frontier.frontier_id
    )
    assert set(selected_obligation.facet_refs) == set(selected_case_refs)

    ledger = compile_claim_decomposition(claim_input)
    facet_by_id = {row.facet_id: row for row in claim_input.facets}
    causal_claims = [row for row in ledger.claims if row.claim_type.value == "causal"]
    assert causal_claims
    for claim in causal_claims:
        _assert_claim_grammar_warnings_match_source_context(claim.model_dump(mode="python"))
        linked_mode_refs = [
            ref for ref in claim.facet_refs if facet_by_id[ref].facet_type == "method_need"
        ]
        assert len(linked_mode_refs) == 1
        assert any(
            precondition.method_need == method_mode.value
            and linked_mode_refs[0] in precondition.facet_refs
            for precondition in claim.method_need_preconditions
        )

    requirement_artifact = compile_method_validity_requirements(
        run_id=ledger.run_id,
        claims=ledger.claims,
    )
    causal_claim_ids = {claim.claim_id for claim in causal_claims}
    causal_requirements = [
        row for row in requirement_artifact.requirements if row.claim_id in causal_claim_ids
    ]
    assert len(causal_requirements) == len(causal_claims)
    assert all(
        row.metadata["explicit_identification_mode_facets"][0]["identification_mode"]
        == method_mode.value
        for row in causal_requirements
    )

    def candidate(mode: IdentificationMode) -> dict[str, object]:
        digest = sha256(mode.value.encode()).hexdigest()
        return {
            "method_id": f"causal.{mode.value}.runtime",
            "method_family": "causal_effect_estimation",
            "method_expectations": ["causal_effect_estimation", mode.value],
            "truthfulness_status": "runtime_consistent",
            "runtime_assumption_gates": [
                {"assumption": "identification_assumptions", "status": "pass"},
                {"assumption": "overlap_or_support", "status": "pass"},
                {"assumption": "missingness_process", "status": "pass"},
                {"assumption": "simulation_dgp_lineage", "status": "pass"},
            ],
            "uncertainty_refs": {"uncertainty_envelope_ref": f"sha256:{digest}"},
            "limitation_refs": {
                "method_limitation_ref": f"sha256:{sha256((mode.value + 'limit').encode()).hexdigest()}"
            },
            "method_result_refs": {
                "method_result_ref": f"sha256:{sha256((mode.value + 'result').encode()).hexdigest()}"
            },
        }

    selection = select_method_candidates_for_requirements(
        candidate_methods=[candidate(IdentificationMode.SEQUENTIAL)],
        method_requirements=causal_requirements,
    )
    assert selection["status"] == "pass", selection
    assert set(selection["method_requirement_statuses"].values()) == {"satisfied"}

    removal_control = select_method_candidates_for_requirements(
        candidate_methods=[candidate(IdentificationMode.POINT_IDENTIFIED)],
        method_requirements=causal_requirements,
    )
    assert removal_control["status"] == "fail"
    assert set(removal_control["method_requirement_statuses"].values()) == {"missing"}
    assert all(
        row["reason_code"] == "identification_mode_unsupported"
        for row in removal_control["rejected_methods"]
    )

    candidate_ref = frontier.candidate_refs[0]
    missing_candidate_graph = graph.model_copy(
        update={
            "candidate_ledger": tuple(
                row for row in graph.candidate_ledger if row.candidate_id != candidate_ref
            )
        }
    )
    with pytest.raises(ValueError, match="constraint_frontier_candidate_ledger_mismatch"):
        constraint_owner._claim_decomposition_input_from_selected_graph(
            run_id=graph.run_id,
            intent="Assess the causal effects of the selected policy case.",
            graph=missing_candidate_graph,
            concept_spine_refs=[case.concept_spine_ref],
            authority_profile_refs=[case.authority_profile.profile_id],
        )

    changed_candidate_graph = graph.model_copy(
        update={
            "candidate_ledger": tuple(
                row.model_copy(
                    update={
                        "metadata": {
                            **row.metadata,
                            "selected_case_facet_refs": ("unrelated:facet",),
                        }
                    }
                )
                if row.candidate_id == candidate_ref
                else row
                for row in graph.candidate_ledger
            )
        }
    )
    with pytest.raises(ValueError, match="constraint_frontier_candidate_metadata_mismatch"):
        constraint_owner._claim_decomposition_input_from_selected_graph(
            run_id=graph.run_id,
            intent="Assess the causal effects of the selected policy case.",
            graph=changed_candidate_graph,
            concept_spine_refs=[case.concept_spine_ref],
            authority_profile_refs=[case.authority_profile.profile_id],
        )

    unbound_candidate_metadata = dict(candidate_metadata)
    unbound_candidate_metadata.pop("selected_case_facet_refs")
    unbound_candidate_metadata.pop("selected_case_binding")
    unbound_frontier_metadata = dict(frontier.metadata)
    unbound_frontier_metadata["candidate_metadata_refs"] = {
        **dict(frontier.metadata["candidate_metadata_refs"]),
        frontier.candidate_refs[0]: unbound_candidate_metadata,
    }
    unbound_frontier = frontier.model_copy(update={"metadata": unbound_frontier_metadata})
    with pytest.raises(ValueError, match="constraint_frontier_identification_mode_binding"):
        constraint_owner._selected_frontier_facet_refs(
            unbound_frontier,
            graph.facets,
        )


def test_v1_frontier_with_unbound_explicit_method_facet_refuses_default_point() -> None:
    from types import SimpleNamespace

    frontier = SimpleNamespace(
        bundle_key=SimpleNamespace(component_id=None, family="causal_effect"),
        metadata={},
        candidate_refs=(),
    )
    mode_facet = SimpleNamespace(facet_id="case:method_need", facet_type="method_need", metadata={})

    with pytest.raises(ValueError, match="constraint_frontier_identification_mode_binding"):
        constraint_owner._selected_frontier_facet_refs(frontier, [mode_facet])


def test_oversized_compiled_population_is_a_typed_refusal_with_fresh_cas_basis(
    tmp_path,
):
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.ir.governance.policy_composition import PolicyLayerLevel
    from polisyos.pdc._impl.layer2_design_search import ConstraintStoreSnapshot
    from tests.unit.policy_grammar.test_universal_policy_grammar_compiler import (
        _authority_profile,
        _concept_spine_refs,
    )

    store = FileSystemCAS(tmp_path / "constraints")
    owner = ConstraintStoreIngestor(store=store)
    source = store.put_json(
        {"source_id": "unverified-constraint-source"},
        PutOptions(kind="fixture.constraint_source", media_type="application/json"),
    )
    problem = _constraint_canonical_problem().model_copy(
        update={
            "problem_statement": (
                "Provide a means-tested housing voucher subsidy for low-income renters in "
                "Kyiv oblast through municipal service centres, with annual appropriations."
            )
        }
    )
    basis = constraint_owner.Phase2RequirementBasis(
        authority_profile=_authority_profile(PolicyLayerLevel.LOCAL),
        concept_spine_refs=_concept_spine_refs(problem.design_problem_id),
        source_refs=(source,),
    )

    result = owner.produce(
        workspace_id="ws-constraint-population-budget",
        design_problem=problem,
        basis=basis,
    )
    packet_raw = owner.require(result, workspace_id=result.workspace_id)
    packet = from_canonical_bytes(packet_raw)
    canonical_limit = ConstraintStoreSnapshot.model_json_schema()["properties"][
        "constraint_records"
    ]["maxItems"]

    assert canonical_limit == 40
    assert result.decision.blocks_promotion is True
    assert result.decision.downgrades_authority is True
    assert "constraint_population_budget_exceeded" in packet["missing_basis"]
    assert "constraint_source_authority_verification_missing" in packet["missing_basis"]
    assert packet["snapshot"] is None
    assert packet["population"] is not None
    assert packet["decision"]["blocks_promotion"] is True
    assert packet["decision"]["downgrades_authority"] is True

    parent_refs = {ref["role"]: ref["artifact_id"] for ref in packet["parent_refs"]}
    assert parent_refs["constraint_source"] == str(source.artifact_id)
    assert "obligation_graph" in parent_refs
    assert "claim_ledger" in parent_refs
    assert "method_preflight" in parent_refs
    assert "constraint_snapshot_basis" in parent_refs
    failure = packet["failure"]
    assert failure["type"] == "constraint_population_budget_exceeded"
    assert failure["actual_count"] == 108
    assert failure["max_items"] == canonical_limit
    assert failure["snapshot_basis_ref"] == parent_refs["constraint_snapshot_basis"]

    fresh_store = FileSystemCAS(tmp_path / "constraints")
    snapshot_raw = fresh_store.get_bytes(failure["snapshot_basis_ref"])
    snapshot_payload = from_canonical_bytes(snapshot_raw)["source_payload"]
    assert len(snapshot_payload["constraint_records"]) == 108
    assert failure["snapshot_basis_sha256"] == hashlib.sha256(snapshot_raw).hexdigest()
    assert from_canonical_bytes(fresh_store.get_bytes(result.artifact_ref.artifact_id)) == packet

    decision = evaluate_constraint_store_for_phase2(
        result, owner=owner, workspace_id=result.workspace_id
    )
    assert decision.blocks_promotion is True
    assert "constraint_population_budget_exceeded" in decision.blocking_constraint_ids


@pytest.mark.parametrize(
    "mutation", ["nested_decision", "deserialized", "new_owner", "wrong_workspace"]
)
def test_constraint_admission_cannot_be_recreated_or_mutated(tmp_path, mutation):
    store = FileSystemCAS(tmp_path / "constraints")
    owner = ConstraintStoreIngestor(store=store)
    result = owner.produce(
        workspace_id="ws-constraint-custody",
        design_problem=_constraint_canonical_problem(),
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
        workspace_id="ws-constraint-corruption",
        design_problem=_constraint_canonical_problem(),
    )
    artifact_id = str(result.artifact_ref.artifact_id)
    original = store.get_bytes
    mutation_count = 0

    def altered(ref):
        nonlocal mutation_count
        raw = original(ref)
        received_id = str(getattr(ref, "artifact_id", ref))
        if received_id == artifact_id:
            packet = from_canonical_bytes(raw)
            packet["decision"]["blocks_promotion"] = not packet["decision"]["blocks_promotion"]
            changed = to_canonical_bytes(packet, CanonSpec(forbid_floats=False, exclude_none=False))
            if changed == raw:
                raise AssertionError("constraint decision mutation did not change bytes")
            mutation_count += 1
            return changed
        return raw

    monkeypatch.setattr(store, "get_bytes", altered)
    with pytest.raises(ValueError, match="artifact_byte_or_manifest_identity_mismatch"):
        evaluate_constraint_store_for_phase2(result, owner=owner, workspace_id=result.workspace_id)
    assert mutation_count == 1


def test_method_consumption_binds_constraint_custody_and_uses_sealed_decision(
    recorded_panel_owner,
):
    from polisyos.core.canon import from_canonical_bytes

    store, binding, state = _method_owner_case(recorded_panel_owner)
    owner = ConstraintStoreIngestor(store=store)
    admission = owner.produce(
        workspace_id="ws-c3-direct-method-owner",
        design_problem=_constraint_canonical_problem(),
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


def test_actual_phase2_loop_records_constraint_refusal_before_earlier_source_block(
    tmp_path,
):
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
        method_quality,
        "build_foundry_method_report_from_execution_outputs",
        real_report,
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
        to_canonical_bytes(report_calls[-1][1], CanonSpec(forbid_floats=False, exclude_none=False))
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
    "mutation",
    ["deserialized", "different_owner", "different_store", "changed_payload"],
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
        method_quality,
        "build_foundry_method_report_from_execution_outputs",
        removed_selection,
    )
    with pytest.raises(ValueError, match="constraint_store_recomputation_mismatch"):
        consumer.bind_constraints(consumption=consumption, owner=owner, admission=admission)


def test_method_manifest_drift_cannot_be_reinterpreted_during_constraint_admission(
    recorded_panel_owner, monkeypatch
):
    from polisyos.core import artifacts as core_artifacts
    from polisyos.core.artifacts import ProducerInfo

    _, _, state, consumer, consumption, owner, preflight = _post_method_constraints(
        recorded_panel_owner
    )
    store = owner._store
    original = store.get_manifest
    target_ref = core_artifacts.ArtifactRef.model_validate(
        state.artifacts_index["causal_method_evidence_ref"]
    )
    changed_selector = (str(target_ref.artifact_id), target_ref.manifest_profile_sha256)
    assert changed_selector[1] is not None
    mutation_hits = []

    def changed_manifest(artifact_ref):
        manifest = original(artifact_ref)
        selector = (
            str(getattr(artifact_ref, "artifact_id", artifact_ref)),
            getattr(artifact_ref, "manifest_profile_sha256", None),
        )
        if selector == changed_selector:
            mutation_hits.append(selector)
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
    assert mutation_hits, "the exact selected manifest mutation did not run"
    assert set(mutation_hits) == {changed_selector}


def test_profile_addressed_method_evidence_resolver_returns_typed_fail_closed_basis(
    recorded_panel_owner, monkeypatch
):
    from polisyos.core import artifacts as core_artifacts
    from polisyos.core.artifacts import ProducerInfo
    from polisyos.core.canon import from_canonical_bytes

    _, _, state, consumer, consumption, owner, preflight = _post_method_constraints(
        recorded_panel_owner
    )
    store = owner._store
    original = store.get_manifest_by_profile
    target_ref = core_artifacts.ArtifactRef.model_validate(
        state.artifacts_index["causal_method_evidence_ref"]
    )
    changed_selector = (str(target_ref.artifact_id), target_ref.manifest_profile_sha256)
    assert changed_selector[1] is not None
    mutation_hits = []
    marker_preservation = []
    changed_producer = ProducerInfo(
        component="c3-profile-resolver-probe", version="unverified-substitution"
    )

    def changed_profile_manifest(artifact_id, profile_sha256):
        manifest = original(artifact_id, profile_sha256)
        selector = (str(getattr(artifact_id, "artifact_id", artifact_id)), profile_sha256)
        if selector == changed_selector:
            before = manifest.model_dump(mode="json")
            altered = manifest.model_copy(update={"producer": changed_producer})
            after = altered.model_dump(mode="json")
            mutation_hits.append(selector)
            marker_preservation.append((before, after))
            return altered
        return manifest

    monkeypatch.setattr(store, "get_manifest_by_profile", changed_profile_manifest)
    admission = owner.reconcile_method(preflight, method_owner=consumer, consumption=consumption)
    assert mutation_hits, "the exact profile-addressed manifest mutation did not run"
    assert set(mutation_hits) == {changed_selector}
    assert marker_preservation
    for before, after in marker_preservation:
        assert before["producer"] != after["producer"]
        assert after["producer"] == changed_producer.model_dump(mode="json")
        assert {key: value for key, value in before.items() if key != "producer"} == {
            key: value for key, value in after.items() if key != "producer"
        }

    assert admission.missing_basis == ("constraint_requirement_basis_unverified",)
    assert admission.decision.blocks_promotion is True
    assert admission.decision.downgrades_authority is True
    packet = from_canonical_bytes(owner.require(admission, workspace_id=admission.workspace_id))
    assert packet["evaluation_phase"] == "post_execution_reconciliation"
    assert packet["missing_basis"] == ["constraint_requirement_basis_unverified"]
    assert packet["failure"] == {
        "type": "ValueError",
        "reason": "selected manifest profile digest does not match its lineage edge",
    }
    assert packet["method_report_ref"] is None
    assert packet["method_consumption_hash"] is None
    assert packet["snapshot"] is None
    assert packet["population"] is None
    assert packet["decision"] == {
        "blocks_promotion": True,
        "downgrades_authority": True,
        "blocking_constraint_ids": ["constraint_requirement_basis_unverified"],
        "limiting_constraint_ids": [],
        "warning_constraint_ids": [],
    }


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
            {"source": name},
            PutOptions(kind="test.source", media_type="application/json"),
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
        {"actual_source": True},
        PutOptions(kind="test.source", media_type="application/json"),
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
                options,
                producer=ProducerInfo(component="unverified.owner", version="1.0"),
            )
        else:
            options = replace(
                options,
                inputs=[InputRef(artifact_id=source.artifact_id, role="different_role")],
            )
        return put(payload, options, **kwargs)

    monkeypatch.setattr(store, "put_json", altered_put)
    with pytest.raises(ValueError, match="constraint_emission_readback_mismatch"):
        owner._persist(kind, {"same_content": True, "parent_refs": parents}, parents)


def _profiled_synthetic_data_snapshot(store):
    """Persist a selected snapshot with an intentionally profileless parent selector."""
    from polisyos.core.artifacts import artifact_manifest_profile_sha256
    from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
    from tests.unit.foundry.data_plane.test_bindings_multiscale import (
        SYNTHETIC_MULTISCALE_PAYLOAD,
    )

    payload_ref = store.put_json(
        SYNTHETIC_MULTISCALE_PAYLOAD,
        PutOptions(kind="fabric.synthetic_multiscale_payload", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    alternate_parent_view = _different_profile_artifact_view(store, payload_ref)
    default_parent_profile = artifact_manifest_profile_sha256(store.get_manifest(payload_ref))
    assert alternate_parent_view.artifact_id == payload_ref.artifact_id
    assert alternate_parent_view.manifest_profile_sha256 != default_parent_profile
    snapshot_ref = store.put_json(
        DataSnapshot(data_ref=payload_ref),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[InputRef(artifact_id=payload_ref.artifact_id, role="data_ref")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return DataSnapshotRef.model_validate(snapshot_ref.model_dump(mode="python"))


def _different_profile_artifact_view(store, artifact_ref):
    """Create a same-bytes, same-schema CAS view with a different owner profile."""
    from polisyos.core.artifacts.manifest import ProducerInfo

    manifest = store.get_manifest(artifact_ref)
    return store.put_bytes(
        store.get_bytes(artifact_ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=ProducerInfo(component="tests.synthetic_profile_alias", version="1"),
            inputs=manifest.inputs,
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )


def _different_profile_snapshot_view(store, snapshot_ref):
    """Create a same-bytes snapshot view with a different owner profile."""
    from polisyos.core.contracts.fabric import DataSnapshotRef

    alternate = _different_profile_artifact_view(store, snapshot_ref)
    return DataSnapshotRef.model_validate(alternate.model_dump(mode="python"))


def _staged_method_case(recorded_panel_owner, tmp_path):
    """Real owners over an engineering cassette; no canonical or safety claim."""
    import json
    from pathlib import Path

    from polisyos.data_forge.domains.ukraine.manifests import (
        ArtifactRecord,
        BuildRunManifest,
    )
    from polisyos.foundry.data_plane import (
        load_ukraine_foundry_intake,
        materialize_method_contract,
    )
    from polisyos.scientist.compute import MethodBackend
    from tests.unit.foundry.data_plane.test_bindings_multiscale import (
        _ukraine_intake_manifests,
    )

    _, store, _, _ = recorded_panel_owner
    bound = _produce_recorded(recorded_panel_owner)
    snapshot_ref = _profiled_synthetic_data_snapshot(store)
    root = tmp_path / "staged-source"
    root.mkdir()
    paths = _ukraine_intake_manifests(root, data_snapshot_ref=snapshot_ref)
    manifest = BuildRunManifest.model_validate_json(paths["d2"].read_bytes())
    selected = next(
        row
        for row in manifest.outputs
        if Path(row.path).name == "panel_observational_contract.json"
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
        cas_root=store.root,
        method_fqn=bound.receipt.method_fqn,
        method_version=None,
        input_state=materialize_method_contract(
            contract_target=bound.contract_target,
            contract_payload=bound.contract_payload,
        ),
        method_params={"n_placebo_runs": 0},
        seed=17,
        input_refs=refs,
    )
    state = ExperimentState(
        run_id="c3-staged-readback",
        observational_data_ref=bound.observational_data_ref,
        causal_method_fqn=bound.receipt.method_fqn,
        causal_method_params={"n_placebo_runs": 0},
        params={"random_seed": 17},
        inputs={
            "ukraine_selected_foundry_method_contract_ref": refs[
                "ukraine_selected_method_contract"
            ],
            "ukraine_foundry_method_input_bundle_ref": refs["ukraine_method_input_bundle"],
        },
        artifacts_index={
            "ukraine_foundry_intake_receipt_ref": refs["ukraine_intake_receipt"],
            "foundry_input_binding_receipt_ref": bound.binding_receipt_ref,
            "causal_method_result_ref": actual.exec_artifacts.result_ref,
            "causal_method_evidence_ref": actual.exec_artifacts.evidence_ref,
        },
    )
    return store, bound, state, root, paths, snapshot_ref


def _staged_consumer(store, root, paths, snapshot_ref):
    """Construct the explicit source binding used by the actual intake owner."""
    import inspect

    from polisyos.runtime.quality.workspace import foundry_consumption as owner

    kwargs = {"store": store}
    if "staged_input_source" in inspect.signature(owner.FoundryMethodOutputConsumer).parameters:
        kwargs["staged_input_source"] = owner.StagedFoundryInputSource(
            allowed_root=root,
            stage_manifests=tuple(sorted(paths.items())),
            data_snapshot_ref=snapshot_ref,
        )
    return owner.FoundryMethodOutputConsumer(**kwargs)


def _staged_snapshot_selector_contract(store, snapshot_ref, core_artifacts):
    from polisyos.runtime.quality.workspace.scientist_node_adapters import (
        _reference_closure,
    )

    source_closure = _reference_closure(store, snapshot_ref, "staged_data_snapshot_test_source")
    source_refs = tuple(binding.artifact_ref for binding in source_closure)
    source_selector_views = {core_artifacts.artifact_ref_identity_key(ref) for ref in source_refs}
    expected_resolved_views = set()
    for source_ref in source_refs:
        manifest = store.get_manifest(source_ref)
        resolved_ref = core_artifacts.ArtifactRef(
            artifact_id=source_ref.artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=core_artifacts.artifact_manifest_profile_sha256(manifest),
        )
        expected_resolved_views.add(core_artifacts.artifact_ref_identity_key(resolved_ref))
    expected_artifact_ids = {view[0] for view in source_selector_views}
    assert source_selector_views
    assert all(view[3] is not None for view in expected_resolved_views)
    return (
        source_refs,
        source_selector_views,
        expected_resolved_views,
        expected_artifact_ids,
    )


def test_staged_intake_real_owner_is_consumed_without_weakening_measurement(
    recorded_panel_owner, tmp_path, monkeypatch
):
    from polisyos.core import artifacts as core_artifacts
    from polisyos.core.artifacts.manifest import InputRef
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.pdc import ArtifactRef as PDCArtifactRef
    from polisyos.pdc import MethodOutputConsumptionRecord

    store, bound, state, root, paths, snapshot_ref = _staged_method_case(
        recorded_panel_owner, tmp_path
    )
    snapshot_manifest = store.get_manifest(snapshot_ref)
    snapshot_edge = next(edge for edge in snapshot_manifest.inputs if edge.role == "data_ref")
    snapshot_body = DataSnapshot.model_validate_json(store.get_bytes(snapshot_ref))
    assert snapshot_ref.manifest_profile_sha256 is not None
    assert snapshot_edge.manifest_profile_sha256 is None
    assert snapshot_body.data_ref.manifest_profile_sha256 is None
    (
        source_refs,
        source_selector_views,
        expected_resolved_views,
        expected_artifact_ids,
    ) = _staged_snapshot_selector_contract(store, snapshot_ref, core_artifacts)
    assert any(ref.manifest_profile_sha256 is None for ref in source_refs)
    assert any(ref.manifest_profile_sha256 is not None for ref in source_refs)

    original_import_subgraph = FileSystemCAS.import_subgraph
    import_reports = []

    def record_import_subgraph(replay_store, source, *, verify_integrity=False):
        report = original_import_subgraph(
            replay_store,
            source,
            verify_integrity=verify_integrity,
        )
        import_reports.append(report)
        return report

    monkeypatch.setattr(FileSystemCAS, "import_subgraph", record_import_subgraph)
    consumer = _staged_consumer(store, root, paths, snapshot_ref)
    result = _consume_case(store, bound, state, consumer=consumer)
    assert len(import_reports) == 1
    import_report = import_reports[0]
    imported_selector_views = {
        core_artifacts.artifact_ref_identity_key(ref) for ref in import_report.imported_refs
    }
    verified_views = {
        core_artifacts.artifact_ref_identity_key(ref)
        for ref in import_report.integrity_verified_refs
    }
    expected_imported_views = source_selector_views | expected_resolved_views
    assert source_selector_views != expected_resolved_views
    assert source_selector_views & expected_resolved_views
    assert imported_selector_views == expected_imported_views
    assert import_report.integrity_verification_requested
    assert not import_report.verification_failed
    assert not import_report.skipped_entries
    assert set(import_report.received_artifact_ids) == expected_artifact_ids
    assert verified_views == expected_resolved_views
    assert result.method_replay_verified
    assert result.authority_boundary.evidence_kind == "measurement"
    assert result.authority_boundary.decision_grade == "descriptive_only"
    assert "causal_identification" in result.authority_boundary.may_not_use_for
    result_ref = core_artifacts.ArtifactRef.model_validate(
        state.artifacts_index["causal_method_result_ref"]
    )
    evidence_ref = core_artifacts.ArtifactRef.model_validate(
        state.artifacts_index["causal_method_evidence_ref"]
    )
    result_pdc_ref = result.record.consumed_method_output_refs[0]
    evidence_pdc_ref = result.record.consumed_method_evidence_refs[0]
    assert result_pdc_ref.manifest_profile_sha256 == result_ref.manifest_profile_sha256
    assert evidence_pdc_ref.manifest_profile_sha256 == evidence_ref.manifest_profile_sha256
    evidence_manifest = store.get_manifest(evidence_ref)
    assert evidence_manifest.inputs == [
        InputRef(
            artifact_id=result_ref.artifact_id,
            role="method_result",
            manifest_profile_sha256=result_ref.manifest_profile_sha256,
        )
    ]
    intake_manifest = store.get_manifest(
        state.artifacts_index["ukraine_foundry_intake_receipt_ref"]
    )
    snapshot_edge = next(edge for edge in intake_manifest.inputs if edge.role == "data_snapshot")
    assert snapshot_edge.manifest_profile_sha256 == snapshot_ref.manifest_profile_sha256
    ref = consumer.persist_consumption(store=store, consumption=result)

    # Follow the actual owner readback from a fresh loop consumer and traverse
    # the persisted record and its selected CAS parents through a reopened CAS.
    from polisyos.runtime.quality.workspace.loop import WorkspaceLoop
    from polisyos.runtime.quality.workspace.scientist_node_adapters import _read_binding

    loop = WorkspaceLoop(artifact_store=store)
    loop._phase2_method_readbacks[id(ref)] = (ref, consumer, result, store)
    owner_seal = from_canonical_bytes(loop.readback_method_consumption(ref))
    reader = FileSystemCAS.open_existing_read_only(store.root)
    persisted_raw = reader.get_bytes(ref.artifact_id)
    assert ref.content_hash == "sha256:" + hashlib.sha256(persisted_raw).hexdigest()
    persisted_payload = from_canonical_bytes(persisted_raw)
    assert persisted_payload["schema_version"] == "policyos.gy.phase2.foundry.v3"
    persisted_payload.pop("schema_version")
    assert persisted_payload == owner_seal
    persisted_record = MethodOutputConsumptionRecord.model_validate(persisted_payload["record"])
    persisted_input_binding_ref = PDCArtifactRef.model_validate(
        persisted_payload["input_binding_receipt_ref"]
    )
    persisted_manifest = reader.get_manifest(ref.artifact_id)
    profiles_by_role = {
        edge.role: edge.manifest_profile_sha256 for edge in persisted_manifest.inputs
    }
    assert profiles_by_role["method_result"] == result_ref.manifest_profile_sha256
    assert profiles_by_role["method_evidence"] == evidence_ref.manifest_profile_sha256
    assert profiles_by_role["measurement_root"] == (
        result.authority_boundary.evidence_basis.producer_roots[0].manifest_profile_sha256
    )
    input_binding_edges = [
        edge for edge in persisted_manifest.inputs if edge.role == "input_binding"
    ]
    expected_input_binding_edge = InputRef(
        artifact_id=persisted_input_binding_ref.artifact_id,
        role="input_binding",
        manifest_profile_sha256=(persisted_input_binding_ref.manifest_profile_sha256),
    )
    # This exact fresh-CAS join fails if the persisted edge is removed, duplicated,
    # assigned another role, or bound to another artifact/profile view.
    assert input_binding_edges == [expected_input_binding_edge]

    for role, refs in (
        ("method_result", persisted_record.consumed_method_output_refs),
        ("method_evidence", persisted_record.consumed_method_evidence_refs),
        ("measurement_root", persisted_record.measurement_root_refs),
        ("input_binding", [persisted_input_binding_ref]),
    ):
        for pdc_ref in refs:
            selector = pdc_ref.manifest_profile_sha256
            selected_manifest = (
                core_artifacts.resolve_manifest_by_profile(reader, pdc_ref.artifact_id, selector)
                if selector is not None
                else reader.get_manifest(pdc_ref.artifact_id)
            )
            core_ref = core_artifacts.ArtifactRef(
                artifact_id=pdc_ref.artifact_id,
                kind=selected_manifest.kind,
                media_type=selected_manifest.media_type,
                manifest_profile_sha256=selector,
            )
            binding, _, verified_manifest = _read_binding(
                reader,
                core_ref,
                "fresh_consumption_reader:" + role,
                require_profiled_json=role in {"method_result", "method_evidence"},
            )
            assert binding.content_hash == pdc_ref.content_hash
            if selector is not None:
                assert (
                    core_artifacts.artifact_manifest_profile_sha256(verified_manifest) == selector
                )


@pytest.mark.parametrize(
    "selector_mutation",
    ["missing_requested", "missing_resolved", "foreign_profile"],
)
def test_staged_intake_rejects_import_selector_drift_when_other_report_fields_pass(
    recorded_panel_owner, tmp_path, monkeypatch, selector_mutation
):
    from dataclasses import replace as dataclass_replace

    from polisyos.core import artifacts as core_artifacts

    store, bound, state, root, paths, snapshot_ref = _staged_method_case(
        recorded_panel_owner, tmp_path
    )
    (
        source_refs,
        source_selector_views,
        expected_resolved_views,
        expected_artifact_ids,
    ) = _staged_snapshot_selector_contract(store, snapshot_ref, core_artifacts)
    expected_imported_views = source_selector_views | expected_resolved_views
    profileless_refs = [ref for ref in source_refs if ref.manifest_profile_sha256 is None]
    assert len(profileless_refs) == 1
    profileless_ref = profileless_refs[0]
    requested_key = core_artifacts.artifact_ref_identity_key(profileless_ref)
    resolved_key = next(view for view in expected_resolved_views if view[:3] == requested_key[:3])
    assert requested_key != resolved_key

    foreign_ref = None
    if selector_mutation == "foreign_profile":
        foreign_ref = _different_profile_artifact_view(store, profileless_ref)
        foreign_key = core_artifacts.artifact_ref_identity_key(foreign_ref)
        assert foreign_ref.artifact_id == profileless_ref.artifact_id
        assert store.get_bytes(foreign_ref) == store.get_bytes(profileless_ref)
        assert foreign_key[:3] == requested_key[:3]
        assert foreign_key not in expected_imported_views

    actual_reports = []
    mutated_reports = []
    mutated_selector_views = []
    original_import_subgraph = FileSystemCAS.import_subgraph

    def mutate_imported_selectors(replay_store, source, *, verify_integrity=False):
        report = original_import_subgraph(
            replay_store,
            source,
            verify_integrity=verify_integrity,
        )
        actual_reports.append(report)
        actual_selector_views = {
            core_artifacts.artifact_ref_identity_key(ref) for ref in report.imported_refs
        }
        assert actual_selector_views == expected_imported_views

        if selector_mutation == "missing_requested":
            changed_refs = tuple(
                ref
                for ref in report.imported_refs
                if core_artifacts.artifact_ref_identity_key(ref) != requested_key
            )
        elif selector_mutation == "missing_resolved":
            changed_refs = tuple(
                ref
                for ref in report.imported_refs
                if core_artifacts.artifact_ref_identity_key(ref) != resolved_key
            )
        else:
            assert foreign_ref is not None
            changed_refs = (*report.imported_refs, foreign_ref)

        changed_report = dataclass_replace(report, imported_refs=changed_refs)
        mutated_reports.append(changed_report)
        mutated_selector_views.append(
            {core_artifacts.artifact_ref_identity_key(ref) for ref in changed_report.imported_refs}
        )
        return changed_report

    monkeypatch.setattr(
        FileSystemCAS,
        "import_subgraph",
        mutate_imported_selectors,
    )
    consumer = _staged_consumer(store, root, paths, snapshot_ref)
    with pytest.raises(
        ValueError,
        match="foundry_staged_intake_snapshot_import_incomplete",
    ):
        _consume_case(store, bound, state, consumer=consumer)

    assert len(actual_reports) == 1
    assert len(mutated_reports) == 1
    report = actual_reports[0]
    mutated_report = mutated_reports[0]
    assert report.integrity_verification_requested
    assert not report.verification_failed
    assert not report.skipped_entries
    assert set(report.received_artifact_ids) == expected_artifact_ids
    verified_views = {
        core_artifacts.artifact_ref_identity_key(ref) for ref in report.integrity_verified_refs
    }
    assert verified_views == expected_resolved_views
    assert mutated_report.integrity_verification_requested
    assert mutated_report.integrity_verified_refs == report.integrity_verified_refs
    assert mutated_report.received_artifact_ids == report.received_artifact_ids
    assert mutated_report.verification_failed == report.verification_failed
    assert mutated_report.skipped_entries == report.skipped_entries

    if selector_mutation == "missing_requested":
        assert mutated_selector_views == [expected_imported_views - {requested_key}]
    elif selector_mutation == "missing_resolved":
        assert mutated_selector_views == [expected_imported_views - {resolved_key}]
    else:
        assert foreign_ref is not None
        foreign_key = core_artifacts.artifact_ref_identity_key(foreign_ref)
        assert mutated_selector_views == [expected_imported_views | {foreign_key}]


def test_staged_intake_refuses_same_bytes_under_a_different_snapshot_profile(
    recorded_panel_owner, tmp_path
):
    store, bound, state, root, paths, snapshot_ref = _staged_method_case(
        recorded_panel_owner, tmp_path
    )
    alternate_ref = _different_profile_snapshot_view(store, snapshot_ref)
    assert alternate_ref.artifact_id == snapshot_ref.artifact_id
    assert alternate_ref.manifest_profile_sha256 != snapshot_ref.manifest_profile_sha256
    consumer = _staged_consumer(store, root, paths, alternate_ref)
    with pytest.raises(ValueError):
        _consume_case(store, bound, state, consumer=consumer)


def test_staged_intake_refuses_other_view_for_profileless_parent_selector(
    recorded_panel_owner, tmp_path, monkeypatch
):
    from polisyos.core.artifacts import artifact_manifest_profile_sha256
    from polisyos.core.contracts.fabric import DataSnapshot

    store, bound, state, root, paths, snapshot_ref = _staged_method_case(
        recorded_panel_owner, tmp_path
    )
    snapshot_body = DataSnapshot.model_validate_json(store.get_bytes(snapshot_ref))
    parent_ref = snapshot_body.data_ref
    assert parent_ref.manifest_profile_sha256 is None
    default_manifest = store.get_manifest(parent_ref)
    default_profile = artifact_manifest_profile_sha256(default_manifest)
    alternate_ref = _different_profile_artifact_view(store, parent_ref)
    assert alternate_ref.artifact_id == parent_ref.artifact_id
    assert alternate_ref.manifest_profile_sha256 != default_profile
    assert store.get_bytes(alternate_ref) == store.get_bytes(parent_ref)

    original_export = store.export_subgraph

    def export_with_other_profile(artifact_ids, target, *, compress=True, include_manifests=True):
        replaced_count = 0
        substituted = []
        for ref in artifact_ids:
            if (
                str(ref.artifact_id) == str(parent_ref.artifact_id)
                and ref.manifest_profile_sha256 is None
            ):
                substituted.append(alternate_ref)
                replaced_count += 1
            else:
                substituted.append(ref)
        assert replaced_count == 1
        return original_export(
            substituted,
            target,
            compress=compress,
            include_manifests=include_manifests,
        )

    monkeypatch.setattr(store, "export_subgraph", export_with_other_profile)
    consumer = _staged_consumer(store, root, paths, snapshot_ref)
    with pytest.raises(ValueError, match="foundry_staged_intake_snapshot_import_incomplete"):
        _consume_case(store, bound, state, consumer=consumer)


def test_staged_intake_requires_explicit_profiled_snapshot_source(recorded_panel_owner, tmp_path):
    from polisyos.runtime.quality.workspace import foundry_consumption as owner

    store, bound, state, root, paths, _snapshot_ref = _staged_method_case(
        recorded_panel_owner, tmp_path
    )
    source = owner.StagedFoundryInputSource(
        allowed_root=root,
        stage_manifests=tuple(sorted(paths.items())),
        data_snapshot_ref=None,
    )
    consumer = owner.FoundryMethodOutputConsumer(store=store, staged_input_source=source)
    with pytest.raises(ValueError, match="foundry_staged_intake_source_data_snapshot_missing"):
        _consume_case(store, bound, state, consumer=consumer)


def test_workspace_phase2_transports_verified_staged_input_owner_refs(
    recorded_panel_owner, tmp_path, monkeypatch
):
    import inspect

    from polisyos.foundry import InputContractMethodSelection
    from polisyos.runtime.quality.workspace import foundry_consumption as owner
    from polisyos.runtime.quality.workspace import loop as loop_owner
    from tests.unit.runtime.quality.test_design_problem import _design_problem

    store, bound, offered, root, paths, snapshot_ref = _staged_method_case(
        recorded_panel_owner, tmp_path
    )
    source_fields = {
        "allowed_root": root,
        "stage_manifests": tuple(sorted(paths.items())),
        "data_snapshot_ref": snapshot_ref,
    }
    kwargs = {"artifact_store": store}
    if "staged_foundry_inputs" in inspect.signature(loop_owner.WorkspaceLoop).parameters:
        kwargs["staged_foundry_inputs"] = owner.StagedFoundryInputBinding(
            source=owner.StagedFoundryInputSource(**source_fields),
            state=offered,
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
        loop_owner,
        "_phase2_value_method_selection",
        lambda *args, **arguments: selected.model_dump(mode="json"),
    )
    problem = _design_problem(runtime_hints={"causal_method_fqn": bound.receipt.method_fqn})
    loop = loop_owner.WorkspaceLoop(**kwargs)
    state = loop._phase2_state(
        workspace_id="c3-staged-transport",
        intent=problem.to_workspace_intent(),
        design_problem=problem,
    )
    for key in (
        "ukraine_foundry_method_input_bundle_ref",
        "ukraine_selected_foundry_method_contract_ref",
    ):
        assert state.inputs.get(key) == offered.inputs[key]
    key = "ukraine_foundry_intake_receipt_ref"
    assert state.artifacts_index.get(key) == offered.artifacts_index[key]
    assert state.observational_data_ref == bound.observational_data_ref


@pytest.mark.parametrize(
    "mutation", ["source_output", "source_status", "bundle_body", "intake_lineage"]
)
def test_staged_intake_owner_readback_refuses_decisive_mutation(
    recorded_panel_owner, tmp_path, mutation, monkeypatch
):
    import json
    from pathlib import Path

    from polisyos.core.artifacts import InputRef

    store, bound, state, root, paths, snapshot_ref = _staged_method_case(
        recorded_panel_owner, tmp_path
    )
    consumer = _staged_consumer(store, root, paths, snapshot_ref)
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
            store,
            old,
            lambda payload: payload["contracts"].pop(next(iter(payload["contracts"]))),
        )
        state.inputs["ukraine_foundry_method_input_bundle_ref"] = changed
        result_ref = state.artifacts_index["causal_method_result_ref"]
        result_manifest = store.get_manifest(result_ref.artifact_id)
        changed_result = _rewrite_artifact(
            store,
            result_ref,
            lambda payload: None,
            inputs=[
                InputRef(artifact_id=changed.artifact_id, role=item.role)
                if item.artifact_id == old.artifact_id
                else item
                for item in result_manifest.inputs
            ],
        )
        state.artifacts_index["causal_method_result_ref"] = changed_result
        state.artifacts_index["causal_method_evidence_ref"] = _rewrite_artifact(
            store,
            state.artifacts_index["causal_method_evidence_ref"],
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


def _assert_workspace_context_reaches_actual_causal_safety_refusal(
    recorded_panel_owner, state=None
):
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
            artifact_id="polisyos.test.c3." + kind,
            artifact_type=kind,
            content_hash="sha256:" + "1" * 64,
            schema_ref="polisyos.test." + kind + ".v1",
            uri="test://c3/" + kind,
            version="1.0",
        )

    if state is None:
        state = ExperimentState(
            run_id="c3-refusal-context",
            observational_data_ref=bound.observational_data_ref,
            causal_method_fqn=bound.receipt.method_fqn,
        )
    from polisyos.core import artifacts

    actual_refs = tuple(
        ArtifactRef(
            artifact_id=str(ref.artifact_id),
            artifact_type="observations",
            content_hash=str(ref.artifact_id),
            schema_ref="polisyos.test.observations.v1",
            uri="cas://" + str(ref.artifact_id),
            version="1.0",
        )
        for ref in (
            artifacts.ArtifactRef.model_validate(raw)
            for raw in (
                state.observational_data_ref,
                state.inputs.get("ukraine_selected_foundry_method_contract_ref"),
                state.inputs.get("ukraine_foundry_method_input_bundle_ref"),
                state.artifacts_index.get("ukraine_foundry_intake_receipt_ref"),
            )
            if raw is not None
        )
    )
    context = EvaluationExecutionContext(
        intake_ref=fixture_ref("intake"),
        evaluator_owner_id=node.spec.metadata.component_id,
        design_problem_ref="sha256:" + "2" * 64,
        evaluation_mode="field_pilot",
        candidate_ref=fixture_ref("candidate"),
        world_model_record_ref=fixture_ref("world_model"),
        target_population_scope_ref=fixture_ref("population"),
        rule_version="polisyos.test.c3.v1",
        intended_start_at=datetime(2026, 9, 9, tzinfo=UTC),
        evaluation_input_refs=actual_refs,
        evaluation_input_provenance=tuple(
            EvaluationInputProvenance(
                input_ref=ref,
                input_class="real_world",
                predicate_provenance="recomputed",
            )
            for ref in actual_refs
        ),
        eval_safety_certificate_ref=None,
        eval_safety_revision_head_ref=None,
    )

    class RefusingVerifier:
        calls = 0

        def require_admission(self, supplied, challenge):
            self.calls += 1
            assert supplied == context
            return EvalSafetyConsumerAdmissionReceipt(
                status="blocked",
                intake_ref=supplied.intake_ref,
                certificate_ref=None,
                current_revision_head_ref=None,
                execution_context_hash=evaluation_execution_context_hash(supplied),
                challenge=challenge,
                blocker_codes=("polisyos.eval_safety.verifier_unappointed@1.0.0",),
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
    assert outcome.error.details["blocker_codes"] == [
        "polisyos.eval_safety.verifier_unappointed@1.0.0"
    ]


def test_workspace_context_reaches_actual_causal_safety_refusal(recorded_panel_owner):
    _assert_workspace_context_reaches_actual_causal_safety_refusal(recorded_panel_owner)


def test_validated_staged_refs_reach_actual_causal_safety_refusal(recorded_panel_owner, tmp_path):
    from polisyos.core import artifacts
    from polisyos.runtime.quality.workspace.scientist_node_adapters import (
        _validated_node_state,
    )

    _, _, state, _, _, _ = _staged_method_case(recorded_panel_owner, tmp_path)
    validated = _validated_node_state(state)
    assert all(
        isinstance(ref, artifacts.ArtifactRef)
        for mapping in (
            validated.inputs,
            validated.artifacts_index,
        )
        for ref in mapping.values()
    )
    _assert_workspace_context_reaches_actual_causal_safety_refusal(recorded_panel_owner, validated)


def test_staged_result_lineage_cannot_hide_supplied_intake_by_removing_state_slots(
    recorded_panel_owner,
    tmp_path,
):
    import json

    store, bound, state, _, paths, _snapshot_ref = _staged_method_case(
        recorded_panel_owner, tmp_path
    )
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


@pytest.mark.parametrize(
    "mutation",
    [
        "source_object",
        "root_type",
        "manifest_container",
        "row_type",
        "stage_type",
        "stage_empty",
        "path_type",
        "duplicate_stage",
        "snapshot_kind",
        "snapshot_profileless",
        "snapshot_missing",
    ],
)
def test_staged_intake_malformed_transport_is_typed_refusal(
    recorded_panel_owner, tmp_path, mutation
):
    from polisyos.runtime.quality.workspace import foundry_consumption as owner

    store, bound, state, root, paths, snapshot_ref = _staged_method_case(
        recorded_panel_owner, tmp_path
    )
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
        if mutation == "snapshot_kind":
            snapshot_source = snapshot_ref.model_copy(update={"kind": "fabric.other_snapshot"})
        elif mutation == "snapshot_profileless":
            snapshot_source = snapshot_ref.model_copy(update={"manifest_profile_sha256": None})
        elif mutation == "snapshot_missing":
            snapshot_source = None
        else:
            snapshot_source = snapshot_ref
        source = owner.StagedFoundryInputSource(
            allowed_root=root,
            stage_manifests=rows,
            data_snapshot_ref=snapshot_source,
        )
    consumer = owner.FoundryMethodOutputConsumer(store=store, staged_input_source=source)
    with pytest.raises(ValueError, match="foundry_staged_intake_source"):
        _consume_case(store, bound, state, consumer=consumer)


@pytest.mark.parametrize(
    "remaining_slot",
    [
        "ukraine_selected_foundry_method_contract_ref",
        "ukraine_foundry_method_input_bundle_ref",
        "ukraine_foundry_intake_receipt_ref",
    ],
)
def test_staged_manifest_presence_requires_complete_intake(
    recorded_panel_owner, tmp_path, remaining_slot
):
    store, bound, state, _, _, _ = _staged_method_case(recorded_panel_owner, tmp_path)
    for mapping, slots in (
        (
            state.inputs,
            (
                "ukraine_selected_foundry_method_contract_ref",
                "ukraine_foundry_method_input_bundle_ref",
            ),
        ),
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

    store, bound, offered, root, paths, snapshot_ref = _staged_method_case(
        recorded_panel_owner, tmp_path
    )
    offered = offered.model_copy(deep=True)
    missing_slot = "ukraine_foundry_method_input_bundle_ref"
    del offered.inputs[missing_slot]
    binding = owner.StagedFoundryInputBinding(
        source=owner.StagedFoundryInputSource(
            allowed_root=root,
            stage_manifests=tuple(sorted(paths.items())),
            data_snapshot_ref=snapshot_ref,
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


def test_candidate_requirement_refusal_and_status_survive_fresh_cas_replay(
    tmp_path,
) -> None:
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.data_requirement import (
        PolicyGrammarConceptSpineRefs,
        UniversalAuthorityProfile,
    )
    from polisyos.ir.governance.policy_composition import PolicyLayerLevel

    store = FileSystemCAS(tmp_path / "constraints")
    owner = ConstraintStoreIngestor(store=store)
    source = store.put_json(
        {"source_id": "unverified-constraint-source"},
        PutOptions(kind="fixture.constraint_source", media_type="application/json"),
    )
    basis = constraint_owner.Phase2RequirementBasis(
        authority_profile=UniversalAuthorityProfile(
            profile_id="llm_constraint_candidate",
            authority_type=PolicyLayerLevel.FEDERAL,
            source_classification="llm_candidate",
            authoritative_for=("compilation_facets",),
        ),
        concept_spine_refs=PolicyGrammarConceptSpineRefs(
            concept_spine_ref="cas://concept-spine/constraint-candidate",
            jurisdiction_spine_ref="cas://jurisdiction/constraint-candidate",
            canonical_concept_refs=("concept://constraint-candidate",),
        ),
        source_refs=(source,),
    )

    problem = _constraint_canonical_problem().model_copy(
        update={
            "problem_statement": (
                "Provide a means-tested housing voucher subsidy for low-income renters in "
                "Kyiv oblast through municipal service centres, with annual appropriations."
            )
        }
    )
    result = owner.produce(
        workspace_id="ws-candidate-constraint-refusal",
        design_problem=problem,
        basis=basis,
    )
    packet = from_canonical_bytes(owner.require(result, workspace_id=result.workspace_id))
    assert result.decision.blocks_promotion is True
    assert "constraint_source_authority_verification_missing" in packet["missing_basis"]
    assert "constraint_grammar_not_admitted" in packet["missing_basis"]

    parent_refs = {ref["role"]: ref["artifact_id"] for ref in packet["parent_refs"]}
    assert parent_refs["constraint_source"] == str(source.artifact_id)
    assert "obligation_graph" not in parent_refs
    grammar = from_canonical_bytes(store.get_bytes(parent_refs["grammar_compilation"]))
    assert grammar["source_payload"]["status"] == "candidate_unverified"

    fresh_store = FileSystemCAS(tmp_path / "constraints")
    replayed = from_canonical_bytes(fresh_store.get_bytes(result.artifact_ref.artifact_id))
    assert replayed == packet
    assert replayed["decision"]["blocks_promotion"] is True
    assert replayed["missing_basis"] == [
        "constraint_source_authority_verification_missing",
        "constraint_grammar_not_admitted",
    ]


def test_plain_text_default_point_does_not_reject_real_did_as_explicit_mode() -> None:
    """Default and explicit POINT share a value but have different constraint origins."""

    from datetime import UTC, datetime
    from decimal import Decimal

    import numpy as np

    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.foundry.methods.catalog.causal.did import StandardDifferenceInDifferences
    from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
    from polisyos.foundry.methods.causal import ensure_causal_methods_registered
    from polisyos.foundry.methods.selection import select_method_candidates_for_requirements
    from polisyos.foundry.validation.method_quality import _selected_method_from_output
    from polisyos.ir.governance.policy_composition import PolicyLayerLevel
    from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.observation import IdentificationMode
    from polisyos.method_requirement import compile_method_validity_requirements
    from polisyos.obligation_graph import (
        ComplexityBudget,
        GovernedObligationRule,
        compile_obligation_graph,
    )
    from polisyos.policy_grammar import (
        PolicyGrammarCompiler,
        PolicyGrammarIntent,
        facet_snapshots_for_obligation_graph,
    )
    from polisyos.scientist.policy_design import compile_claim_decomposition
    from tests.unit.policy_grammar.test_universal_policy_grammar_compiler import (
        _authority_profile,
        _concept_spine_refs,
    )

    authority = _authority_profile(PolicyLayerLevel.LOCAL)
    compiler = PolicyGrammarCompiler()
    default_intent = PolicyGrammarIntent(
        intent_id="lane01_ec02_default_point",
        text=(
            "Provide a vaccination service for rural children in 2026 with budget funding "
            "and coverage monitoring."
        ),
        domain=ProblemDomain.HEALTHCARE,
    )
    explicit_intent = PolicyGrammarIntent.from_problem_policy(
        intent_id="lane01_ec02_explicit_point",
        problem_frame=ProblemFrame(
            problem_id="lane01_ec02_explicit_point_problem",
            domain=ProblemDomain.HEALTHCARE,
            narrative="Improve vaccination coverage for rural children.",
        ),
        policy_spec=PolicySpec(
            policy_id="lane01_ec02_explicit_point_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="lane01_ec02_vaccination_service",
                    kind="service",
                    target=SelectorPredicate(
                        field="population",
                        operator="==",
                        value="selected",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=12),
                    params={"monthly_budget": Decimal("1000")},
                    target_population_type="children",
                    target_region_ids=["rural"],
                    identification_mode=IdentificationMode.POINT_IDENTIFIED,
                )
            ],
        ),
    )

    def compile_route(intent: PolicyGrammarIntent, run_id: str):
        case = compiler.compile(
            intent=intent,
            authority_profile=authority,
            concept_spine_refs=_concept_spine_refs(intent.intent_id),
        )
        facets = facet_snapshots_for_obligation_graph(case)
        mode = case.facets.method_need.value
        rule = GovernedObligationRule(
            rule_id=f"rule:lane01-ec02:{run_id}",
            rule_family="causal_effect",
            rule_version="2026.11",
            logic_hash="sha256:" + hashlib.sha256(run_id.encode()).hexdigest(),
            owner="team-evidence",
            scope="national",
            authority_level="governed",
            evidence_basis="registered rule",
            public_revalidation_effect="review_affected_claim",
            obligation_text="Review the causal method requirement for this policy case.",
            authority_profile="candidate",
            temporal_window="case_lifecycle",
            remedy_path="source_evidence",
            required_facets={"method_need": mode.value},
        )
        graph = compile_obligation_graph(
            run_id=run_id,
            facets=facets,
            governed_rules=[rule],
            generated_at=datetime(2026, 11, 11, tzinfo=UTC),
            complexity_budget=ComplexityBudget(max_frontier_items=4),
        )
        claim_input = constraint_owner._claim_decomposition_input_from_selected_graph(
            run_id=run_id,
            intent="Assess the vaccination policy's causal effects.",
            graph=graph,
            concept_spine_refs=[case.concept_spine_ref],
            authority_profile_refs=[case.authority_profile.profile_id],
        )
        ledger = compile_claim_decomposition(claim_input)
        causal_claims = [claim for claim in ledger.claims if claim.claim_type.value == "causal"]
        artifact = compile_method_validity_requirements(
            run_id=ledger.run_id,
            claims=ledger.claims,
        )
        causal_claim_ids = {claim.claim_id for claim in causal_claims}
        causal_requirements = [
            row for row in artifact.requirements if row.claim_id in causal_claim_ids
        ]
        method_facet = next(row for row in claim_input.facets if row.facet_type == "method_need")
        return method_facet, causal_claims, causal_requirements

    default_facet, default_claims, default_requirements = compile_route(
        default_intent,
        "run_lane01_ec02_default_point",
    )
    explicit_facet, explicit_claims, explicit_requirements = compile_route(
        explicit_intent,
        "run_lane01_ec02_explicit_point",
    )

    assert default_facet.value == explicit_facet.value == IdentificationMode.POINT_IDENTIFIED.value
    assert default_facet.metadata["identification_mode_origin"] == "default_point"
    assert explicit_facet.metadata["identification_mode_origin"] == "explicit_policy_spec"
    assert default_claims and explicit_claims
    assert all(
        row.metadata["explicit_identification_mode_facets"] == [] for row in default_requirements
    )
    assert all(
        row.metadata["identification_class_semantics"]
        == "required_method_capability_not_identification_evidence"
        for row in default_requirements
    )
    assert all(
        row.metadata["source_facet_contexts"]
        and any(
            context["facet_type"] == "method_need"
            and context["metadata"]["identification_mode_origin"] == "default_point"
            for context in row.metadata["source_facet_contexts"]
        )
        for row in default_requirements
    )
    assert all(
        row.metadata["explicit_identification_mode_facets"][0]["identification_mode_origin"]
        == "explicit_policy_spec"
        for row in explicit_requirements
    )

    # Exercise the actual registered NumPy DiD implementation and its execution-output
    # adapter; this candidate has no declared point_identified mode expectation.
    ensure_causal_methods_registered()
    outcome = np.tile(np.arange(10, dtype=float), (8, 1))
    outcome[:3, 5:] += 3.0
    data = PanelObservationalData(
        outcome=outcome,
        treatment=np.array([1, 1, 1, 0, 0, 0, 0, 0]),
        time_treatment=5,
        unit_ids=np.arange(8),
    )
    dispatched = MethodDispatcher.get_instance().dispatch(
        method_class=StandardDifferenceInDifferences,
        signature=StandardDifferenceInDifferences.signature,
        state=data,
        params={},
        seed=17,
    )
    actual_did = _selected_method_from_output(dict(dispatched.output), foundry_input_refs={})
    assert actual_did["method_id"] == "difference_in_differences"
    assert "method_expectations" not in actual_did
    treated_change = outcome[:3, 5:].mean() - outcome[:3, :5].mean()
    control_change = outcome[3:, 5:].mean() - outcome[3:, :5].mean()
    independent_did = treated_change - control_change
    assert independent_did == pytest.approx(3.0)
    assert dispatched.output["report"].point_estimate == pytest.approx(independent_did)

    default_selection = select_method_candidates_for_requirements(
        candidate_methods=[actual_did],
        method_requirements=default_requirements,
    )
    default_reasons = {row["reason_code"] for row in default_selection["rejected_methods"]}
    assert "identification_mode_unsupported" not in default_reasons

    explicit_selection = select_method_candidates_for_requirements(
        candidate_methods=[actual_did],
        method_requirements=explicit_requirements,
    )
    assert explicit_selection["status"] == "fail"
    assert explicit_selection["selected_methods"] == []
    assert all(
        row["reason_code"] == "identification_mode_unsupported"
        for row in explicit_selection["rejected_methods"]
    )

    # The source-facet context is the producer-bound record. Removing only the
    # redundant precondition projection must retain the explicit PolicySpec gate.
    stripped_explicit_claims = []
    for claim in explicit_claims:
        stripped_preconditions = []
        for precondition in claim.method_need_preconditions:
            metadata = dict(precondition.metadata)
            metadata.pop("explicit_identification_mode_facets", None)
            stripped_preconditions.append(precondition.model_copy(update={"metadata": metadata}))
        stripped_explicit_claims.append(
            claim.model_copy(update={"method_need_preconditions": stripped_preconditions})
        )
    stripped_artifact = compile_method_validity_requirements(
        run_id="run_lane01_ec02_explicit_point_projection_removed",
        claims=stripped_explicit_claims,
    )
    explicit_claim_ids = {claim.claim_id for claim in explicit_claims}
    stripped_requirements = [
        row for row in stripped_artifact.requirements if row.claim_id in explicit_claim_ids
    ]
    assert stripped_requirements
    assert all(
        row.metadata["explicit_identification_mode_facets"]
        and all(
            binding["identification_mode_origin"] == "explicit_policy_spec"
            for binding in row.metadata["explicit_identification_mode_facets"]
        )
        for row in stripped_requirements
    )
    stripped_selection = select_method_candidates_for_requirements(
        candidate_methods=[actual_did],
        method_requirements=stripped_requirements,
    )
    assert stripped_selection["status"] == "fail"
    assert all(
        row["reason_code"] == "identification_mode_unsupported"
        for row in stripped_selection["rejected_methods"]
    )

    # The selector must preserve the same constraint if its own secondary
    # requirement projection is removed after compilation.
    stripped_selector_requirements = []
    for requirement in explicit_requirements:
        metadata = dict(requirement.metadata)
        metadata["explicit_identification_mode_facets"] = []
        stripped_selector_requirements.append(requirement.model_copy(update={"metadata": metadata}))
    selector_removal = select_method_candidates_for_requirements(
        candidate_methods=[actual_did],
        method_requirements=stripped_selector_requirements,
    )
    assert selector_removal["status"] == "fail"
    assert all(
        row["reason_code"] == "identification_mode_unsupported"
        for row in selector_removal["rejected_methods"]
    )
