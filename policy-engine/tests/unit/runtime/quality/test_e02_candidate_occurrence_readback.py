"""CAS-backed candidate-history replay through the pre-N9 owner seam.

The fixture persists the canonical compiled recursive artifact shape directly
to a temporary CAS and reopens it with a fresh store. It exercises the typed
compiled-run contract and runtime owner seam. Candidate hashes are opaque test
tokens; grounding, value, and completion inputs are test fixtures. This does
not establish source provenance, N5 truth, or deployment currentness, and it
does not claim a public persisted-run resume API. Ready test receipts are
roundtripped under v3/v4; separate real v1/v2 history stays widthless and is
not represented as carrying a ready value receipt.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core import canon
from polisyos.core import contracts as core_contracts
from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions, FileSystemCAS, SchemaInfo
from polisyos.core.contracts.value_outer_set import ValueOuterSet
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.control.generation_cycle import (
    COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    derive_recursive_design_graph,
)
from polisyos.runtime.quality.epoch_validity_cascade import (
    PromotionCandidateOccurrenceStatement,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    CandidateSummary,
    GenerationCycleController,
    GenerationCycleRun,
    ValueGateReceipt,
    _current_candidate_summaries,
)
from polisyos.runtime.quality.open_world_risk import (
    PromotionOwnerQueryContextNonReceipt,
    PromotionRuntime,
    PromotionRuntimeBatch,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveGenerationCycleController,
)
from tests.unit.runtime.quality.historical_artifacts import historical_generation_cycle_v1
from tests.unit.runtime.quality.test_generation_cycle import (
    REPO_ROOT,
    _AlwaysLowGrounding,
    _budget,
    _CurrentValidGrounding,
    _problem,
    _ReadyValuePort,
    _SameCandidateNewBasisGenerator,
)


class _CurrentValidOnSecondCycleGrounding:
    """Use test-only grounding fixtures to let the second cycle reach the owner."""

    def __init__(self) -> None:
        self._initial_gap = _AlwaysLowGrounding()
        self._current_grounding = _CurrentValidGrounding()

    def __call__(
        self,
        *,
        candidate: Any,
        problem: Any,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        grounding = (
            self._initial_gap if cycle_index == 0 else self._current_grounding
        )
        return grounding(
            candidate=candidate,
            problem=problem,
            cycle_index=cycle_index,
            generation_result=generation_result,
        )


def _assert_modern_value_receipt_roundtrips(run: GenerationCycleRun) -> None:
    """Exercise real root and cycle receipts through modern v3/v4 readers."""

    spec = canon.CanonSpec(forbid_floats=False)
    versions = (
        ("v3", "policyos.runtime.generation_cycle_controller.v3"),
        ("v4", "policyos.runtime.generation_cycle_controller.v4"),
    )
    for version, schema_version in versions:
        # Keep the owner-emitted run and all actual value receipts. The v3
        # projection only removes the v4-only source-custody limitation.
        updates: dict[str, Any] = {"schema_version": schema_version}
        if version != "v4":
            updates["source_custody_limitation"] = None
        versioned_run = run.model_copy(update=updates)
        run_payload = versioned_run.model_dump(mode="json")
        run_bytes = canon.to_canonical_bytes(run_payload, spec)
        decoded_run = canon.from_canonical_bytes(run_bytes)
        assert isinstance(decoded_run, dict), version
        replayed_run = GenerationCycleRun.from_persisted_payload(decoded_run)
        assert (
            canon.to_canonical_bytes(replayed_run.model_dump(mode="json"), spec)
            == run_bytes
        ), version

        receipt_locations: list[tuple[str, tuple[str | int, ...]]] = [
            ("root", ("value_port", "value_receipt")),
        ]
        receipt_locations.extend(
            (f"cycle-{index}", ("cycles", index, "value_port", "value_receipt"))
            for index in range(len(run_payload["cycles"]))
        )
        assert len(receipt_locations) == 1 + len(run_payload["cycles"]), version

        for label, path in receipt_locations:
            receipt_payload = _mapping_at_path(run_payload, path)
            outer_payload = receipt_payload["value_outer_set"]
            assert "width" in outer_payload, (version, label)
            receipt_bytes = canon.to_canonical_bytes(receipt_payload, spec)
            decoded_receipt = canon.from_canonical_bytes(receipt_bytes)
            assert isinstance(decoded_receipt, dict), (version, label)
            receipt = ValueGateReceipt.from_persisted_payload(decoded_receipt)
            assert (
                canon.to_canonical_bytes(receipt.model_dump(mode="json"), spec)
                == receipt_bytes
            ), (version, label)

            live_outer_payload = copy.deepcopy(outer_payload)
            if "width" not in live_outer_payload:
                live_outer_payload["width"] = [
                    max(0.0, round(float(upper) - float(lower), 12))
                    for lower, upper in zip(
                        live_outer_payload["lower"],
                        live_outer_payload["upper"],
                        strict=True,
                    )
                ]
            with pytest.raises(ValidationError) as live_width_error:
                ValueOuterSet.model_validate(live_outer_payload)
            assert any(
                "value_outer_set_width_supplied_not_derived" in issue["msg"]
                for issue in live_width_error.value.errors()
            ), (version, label)

            negative_cases = (
                ("tampered_width", _set_width((1.0,)), "value_outer_set_width_tampered"),
                ("boolean_width", _set_width((False,)), "value_outer_set_width_tampered"),
                ("missing_width", _remove_width, "value_outer_set_persisted_width_missing"),
                ("unknown_receipt_field", _add_unknown_receipt_field, "extra_forbidden"),
                ("unknown_value_set_field", _add_unknown_value_set_field, "extra_forbidden"),
            )
            for case_name, mutate, expected in negative_cases:
                altered_payload = copy.deepcopy(run_payload)
                altered_receipt = _mapping_at_path(altered_payload, path)
                mutate(altered_receipt)
                if expected == "extra_forbidden":
                    with pytest.raises(ValidationError) as extra_error:
                        GenerationCycleRun.from_persisted_payload(altered_payload)
                    assert any(
                        issue["type"] == "extra_forbidden"
                        for issue in extra_error.value.errors()
                    ), (version, label, case_name)
                else:
                    with pytest.raises(ValueError, match=expected):
                        GenerationCycleRun.from_persisted_payload(altered_payload)


def _assert_actual_legacy_history_roundtrips() -> None:
    """Replay real widthless v1/v2 history without manufacturing N8 receipts."""

    v1_document = historical_generation_cycle_v1()
    v1_run = v1_document["generation_cycle_run"]
    v2_document = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer3_gy_generation_cycle_contract.json")
        .read_bytes()
    )
    v2_run = v2_document["generation_cycle_run"]
    versions = (("v1", v1_run), ("v2", v2_run))
    spec = canon.CanonSpec(forbid_floats=False)
    for version, payload in versions:
        assert payload["schema_version"].endswith(f".{version}")
        ports = [
            payload.get("value_port"),
            *(cycle.get("value_port") for cycle in payload["cycles"]),
        ]
        assert all(
            isinstance(port, dict) and port.get("value_receipt") is None
            for port in ports
        ), version
        original_bytes = canon.to_canonical_bytes(payload, spec)
        decoded = canon.from_canonical_bytes(original_bytes)
        assert isinstance(decoded, dict), version
        replayed = GenerationCycleRun.from_persisted_payload(decoded)
        assert (
            canon.to_canonical_bytes(replayed.model_dump(mode="json"), spec)
            == original_bytes
        ), version


def _mapping_at_path(value: Any, path: tuple[str | int, ...]) -> dict[str, Any]:
    current = value
    for segment in path:
        current = current[segment]
    assert isinstance(current, dict)
    return current


def _set_width(width: tuple[float | bool, ...]) -> Callable[[dict[str, Any]], None]:
    def mutate(receipt: dict[str, Any]) -> None:
        receipt["value_outer_set"]["width"] = list(width)

    return mutate


def _remove_width(receipt: dict[str, Any]) -> None:
    receipt["value_outer_set"].pop("width")


def _add_unknown_receipt_field(receipt: dict[str, Any]) -> None:
    receipt["unexpected_receipt_field"] = "preserve-strictness"


def _add_unknown_value_set_field(receipt: dict[str, Any]) -> None:
    receipt["value_outer_set"]["unexpected_value_set_field"] = "preserve-strictness"


@pytest.mark.asyncio
async def test_latest_candidate_occurrence_survives_cas_replay_and_pre_n9_readback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replay both fixture appearances and bind only the latest through CAS owners.

    The opaque hashes and test grounding/value/completion fixtures establish no
    source provenance, N5 truth, or deployment-currentness claim. The observed
    refusal is the real pre-N9 policy-admission gate; no signed N9 admission is
    required for this B28 occurrence-binding witness.
    """

    problem = _problem("same_subject_persisted_occurrence")
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    root_ref = f"design-problem://{problem_ref.removeprefix('sha256:')}"
    graph = derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
    )
    generator = _SameCandidateNewBasisGenerator()
    recursive = RecursiveGenerationCycleController.for_contract_testing(
        repo_root=REPO_ROOT,
        cycle_controller_factory=lambda _node_ref, _problem: GenerationCycleController(
            generation_port=generator,
            grounding_port=_CurrentValidOnSecondCycleGrounding(),
            value_port=_ReadyValuePort(),
            repo_root=REPO_ROOT,
        ),
    )
    recursive_run = await recursive.run(
        graph,
        problems_by_node={root_ref: problem},
        budget_state=_budget(),
        recursive_budget=RecursiveCycleBudget(
            max_depth=0,
            max_nodes=1,
            min_cycles_per_leaf=2,
            max_cycles_per_leaf=2,
        ),
    )
    leaf_runs = tuple(
        node.cycle_run
        for node in recursive_run.leaf_nodes
        if node.cycle_run is not None
    )
    assert len(leaf_runs) == 1
    produced_run = leaf_runs[0]
    assert produced_run.terminal_status == "completed"
    assert tuple(
        (row.candidate_id, row.content_hash, row.cycle_index)
        for row in produced_run.candidate_summaries
    ) == (
        ("candidate_same_subject", "sha256:" + "1" * 64, 0),
        ("candidate_same_subject", "sha256:" + "2" * 64, 1),
    )
    _assert_modern_value_receipt_roundtrips(produced_run)
    _assert_actual_legacy_history_roundtrips()

    recursive_payload = recursive_run.model_dump(mode="json", exclude={"leaf_nodes"})
    compiled_payload = {
        "schema_version": COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
        "design_problem_ref": problem_ref,
        "design_problem": problem.model_dump(mode="json"),
        "cycle_substrate_context_ref": None,
        "recursive_run": recursive_payload,
    }
    compiled = CompiledRecursiveGenerationCycleRun.model_validate(
        {**compiled_payload, "content_hash": gy_content_hash(compiled_payload)}
    )

    cas_root = tmp_path / "compiled-run-cas"
    writer = FileSystemCAS(cas_root)
    compiled_ref = writer.put_json(
        compiled.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind="runtime.compiled_recursive_generation_cycle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
                version="1.0",
            ),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )

    # Re-open the same CAS with fresh readers before constructing the consumer.
    read_store = FileSystemCAS(cas_root)
    assert read_store.verify(compiled_ref).ok
    manifest = read_store.get_manifest(compiled_ref)
    assert manifest.kind == "runtime.compiled_recursive_generation_cycle"
    assert manifest.artifact_schema == SchemaInfo(
        name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
        version="1.0",
    )
    raw = read_store.get_bytes(compiled_ref)
    assert str(compiled_ref.artifact_id) == f"sha256:{canon.content_hash(raw)}"
    payload = canon.from_canonical_bytes(raw)
    assert isinstance(payload, dict)
    replayed = CompiledRecursiveGenerationCycleRun.model_validate(payload)
    replayed_runs = tuple(
        node.cycle_run
        for node in replayed.recursive_run.leaf_nodes
        if node.cycle_run is not None
    )
    assert len(replayed_runs) == 1
    replayed_run = replayed_runs[0]
    # Compare the persisted projection: CandidateSummary.value_receipt is an
    # intentionally excluded in-memory cache, not part of the CAS artifact.
    wire_spec = canon.CanonSpec(forbid_floats=False)
    assert canon.to_canonical_bytes(
        replayed_run.model_dump(mode="json"), wire_spec
    ) == canon.to_canonical_bytes(produced_run.model_dump(mode="json"), wire_spec)
    assert tuple(
        (row.candidate_id, row.content_hash, row.cycle_index)
        for row in replayed_run.candidate_summaries
    ) == (
        ("candidate_same_subject", "sha256:" + "1" * 64, 0),
        ("candidate_same_subject", "sha256:" + "2" * 64, 1),
    )
    latest = replayed_run.candidate_summaries[1]
    assert produced_run.candidate_summaries[1].value_receipt is not None
    assert latest.value_receipt is None
    assert _current_candidate_summaries(replayed_run.candidate_summaries) == (latest,)
    front_ids = tuple(
        candidate_id
        for candidate_ids in replayed_run.fronts.candidate_ids_by_front().values()
        for candidate_id in candidate_ids
    )
    assert front_ids == (latest.candidate_id,)

    consumer_runtime = PromotionRuntime(store=read_store)
    consumer = GenerationCycleController(
        promotion_runtime=consumer_runtime,
        repo_root=REPO_ROOT,
    )
    prepared_calls: list[
        tuple[
            tuple[CandidateSummary, ...],
            PromotionRuntimeBatch | PromotionOwnerQueryContextNonReceipt,
        ]
    ] = []
    prepare = consumer_runtime._prepare_completed_generation

    def capture_prepare(
        *, problem: Any, summaries: Sequence[CandidateSummary]
    ) -> PromotionRuntimeBatch | PromotionOwnerQueryContextNonReceipt:
        frozen_summaries = tuple(summaries)
        result = prepare(problem=problem, summaries=frozen_summaries)
        prepared_calls.append((frozen_summaries, result))
        return result

    gate_calls: list[tuple[ArtifactRef, object]] = []
    reconcile = consumer_runtime.epoch_validity_gate.reconcile_before_n9

    def capture_gate(*, subject_ref: ArtifactRef) -> object:
        result = reconcile(subject_ref=subject_ref)
        gate_calls.append((subject_ref, result))
        return result

    monkeypatch.setattr(
        consumer_runtime, "_prepare_completed_generation", capture_prepare
    )
    monkeypatch.setattr(
        consumer_runtime.epoch_validity_gate,
        "reconcile_before_n9",
        capture_gate,
    )
    final_cycle = replayed_run.cycles[-1]
    active_problem = (
        replayed_run.cycles[-2].revision_request.revised_problem
        if len(replayed_run.cycles) > 1
        else replayed.design_problem
    )
    assert (
        gy_content_hash(active_problem.model_dump(mode="json"))
        == final_cycle.design_problem_basis_ref
    )
    next_problem = final_cycle.revision_request.revised_problem
    assert gy_content_hash(next_problem.model_dump(mode="json")) != (
        final_cycle.design_problem_basis_ref
    )
    basis_mismatch = consumer._promote_completed_generation(
        summaries=replayed_run.candidate_summaries,
        problem=next_problem,
        design_problem_basis_ref=final_cycle.design_problem_basis_ref,
        deployment_identity=replayed_run.deployment_identity,
    )
    assert basis_mismatch.reason == (
        "epoch_validity_refused:generation_cycle_promotion_basis_mismatch"
    )
    assert prepared_calls == []
    assert gate_calls == []

    refusal = consumer._promote_completed_generation(
        summaries=replayed_run.candidate_summaries,
        problem=active_problem,
        design_problem_basis_ref=final_cycle.design_problem_basis_ref,
        deployment_identity=replayed_run.deployment_identity,
    )

    assert refusal.reason == "epoch_validity_refused:policy_admission_missing"
    assert len(prepared_calls) == 1
    consumed_summaries, prepared = prepared_calls[0]
    assert consumed_summaries == (latest,)
    assert isinstance(prepared, PromotionRuntimeBatch)
    assert len(gate_calls) == 1
    assert isinstance(
        gate_calls[0][1],
        core_contracts.decision_validity.EpochValidityGateNonReceipt,
    )
    assert gate_calls[0][1].code == "policy_admission_missing"

    bound = prepared.contexts.ordered_bound_members[0]
    occurrence_ref = bound.statement.candidate_occurrence_ref
    occurrence = consumer_runtime.context_repository.resolve_occurrence(
        occurrence_ref=occurrence_ref
    )
    assert isinstance(occurrence, PromotionCandidateOccurrenceStatement)
    assert occurrence.candidate_summary == latest
    assert occurrence.candidate_id == latest.candidate_id
    assert occurrence.candidate_content_hash == latest.content_hash
    assert occurrence.cycle_index == latest.cycle_index == 1

    older = replayed_run.candidate_summaries[0]
    stale_gate = consumer_runtime.prepare_verified_gate(
        batch=prepared,
        ordinal=0,
        summary=older,
    )
    assert isinstance(stale_gate, PromotionOwnerQueryContextNonReceipt)
    assert stale_gate.status == "rejected"
    assert stale_gate.code == "promotion_query_context_binding_mismatch"
