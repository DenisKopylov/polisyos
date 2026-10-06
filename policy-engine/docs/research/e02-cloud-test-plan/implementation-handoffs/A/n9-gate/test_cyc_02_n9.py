"""Scratch witness for the bounded CYC-02/N9 consumer finding.

This is intentionally NOT a B05 closure test. The direct public N9 path uses
an existing explicitly test-only owner appointment; no production signer or
currentness positive is supplied.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.quality.generation_cycle as generation_cycle_module
import polisyos.runtime.quality.promotion_sequence as promotion_sequence_module
from polisyos.core.contracts.chronology import _canonical_raw_bytes
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    JointSimulationPort,
    _DefaultSimulationBoundFoundryValuePort,
    _summary_with_value_observation,
    load_joint_simulation_result,
)
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.runtime.quality.promotion_sequence import (
    CanonicalN9PromotionPort,
    CanonicalPromotionReceipt,
)
from tests.unit.runtime.quality.test_generation_cycle import (
    REPO_ROOT,
    _canonical_loaded_deployment_identity,
    _open_world_summary,
    _owner_n5_case_with_selected_ncm_ref,
    _positive_epoch_admitted_batch,
    _runtime_ncm_fixture_store,
)


def _float_paths(value: Any, path: str = "$") -> list[str]:
    """Enumerate floats recursively, including nested runtime-hint containers."""

    if isinstance(value, float):
        return [path]
    if isinstance(value, Mapping):
        return [
            found
            for key, item in value.items()
            for found in _float_paths(item, f"{path}.{key}")
        ]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [
            found
            for index, item in enumerate(value)
            for found in _float_paths(item, f"{path}[{index}]")
        ]
    return []


def test_public_n9_value_result_is_unchanged_when_persisted_ksim_is_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run the real selected-NCM N5, default N8, pre-N9 refusal, and public N9."""

    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda _repo_root: (),
    )
    store, expected_ncm, ncm_ref = _runtime_ncm_fixture_store(tmp_path)
    try:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            problem, cycle_context, candidate = _owner_n5_case_with_selected_ncm_ref(
                ncm_ref,
                runtime_hints={"joint_simulation_baseline_state": {"firm_survival": 0}},
            )
            problem_ref = cycle_context.design_problem_ref
            hint_float_paths = _float_paths(problem.runtime_hints)
            assert hint_float_paths == []
            canonical_problem = _canonical_raw_bytes(problem.model_dump(mode="json"))
            canonical_problem_sha256 = hashlib.sha256(canonical_problem).hexdigest()
            assert problem_ref == "sha256:" + canonical_problem_sha256
            print(
                "N9_INPUT_IDENTITY="
                + json.dumps(
                    {
                        "problem_ref": problem_ref,
                        "canonical_problem_sha256": canonical_problem_sha256,
                        "runtime_hints_float_paths": hint_float_paths,
                        "world_model_record_id": cycle_context.world_model_record.world_model_record_id,
                        "world_model_record_content_hash": cycle_context.world_model_record.content_hash,
                        "candidate_id": candidate.candidate_id,
                        "atom_ids": [atom.intervention_id for atom in candidate.intervention_atoms],
                        "selected_outcomes": [problem.outcome_of_interest.target_variable],
                        "selected_ncm_ref": ncm_ref,
                    },
                    sort_keys=True,
                )
            )

            n5_port = JointSimulationPort(
                repo_root=REPO_ROOT,
                cycle_substrate_context=cycle_context,
                artifact_store=store,
            )
            with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
                n5_request = n5_port._build_joint_simulation_request(
                    candidate=candidate,
                    problem=problem,
                )
                assert n5_request.engine_plan[0].ncm_spec == expected_ncm
                simulation = n5_port(
                    candidate=candidate,
                    problem=problem,
                    cycle_index=0,
                )
                assert simulation.status == "joint_simulated", {
                    "status": simulation.status,
                    "blockers": simulation.authority_blockers,
                    "diagnostics": simulation.diagnostics,
                }
                assert simulation.simulation_result_ref is not None
                reopened = load_joint_simulation_result(
                    simulation.simulation_result_ref,
                    store=store,
                    expected_world_model_record_content_hash=(
                        cycle_context.world_model_record.content_hash
                    ),
                    expected_atom_ids=tuple(
                        atom.intervention_id for atom in candidate.intervention_atoms
                    ),
                    expected_selected_outcomes=(problem.outcome_of_interest.target_variable,),
                )
                value_port = _DefaultSimulationBoundFoundryValuePort(
                    repo_root=tmp_path,
                    cycle_substrate_context=cycle_context,
                    artifact_store=store,
                )(
                    candidate=candidate,
                    simulation=simulation,
                    problem=problem,
                    cycle_index=0,
                )
                runtime = PromotionRuntime(store=store)

            assert reopened.uncertainty_kind == "K_sim"
            assert "simulation_only_k_sim_not_world_evidence" in (
                reopened.promotion_ready_value_packet["authority_blockers"]
            )
            assert value_port.status == "value_conditional"
            assert value_port.value_receipt is None
            assert value_port.value_ref == str(simulation.simulation_result_ref.artifact_id)
            assert "simulation_only_k_sim_not_world_evidence" in value_port.authority_blockers

            summary = _summary_with_value_observation(
                _open_world_summary(candidate.candidate_id).model_copy(
                    update={
                        "content_hash": generation_cycle_module._candidate_content_hash(candidate),
                    }
                ),
                simulation=simulation,
                value_port=value_port,
                counterexample_ref="pdc://e02/n9_gate/conditional_value",
            )
            assert summary.value_status == "value_conditional"
            assert summary.value_ref == str(simulation.simulation_result_ref.artifact_id)
            assert summary.value_receipt is None

            n5_manifest = store.get_manifest(simulation.simulation_result_ref.artifact_id)
            print(
                "N9_PROBE_CAS_INPUTS="
                + json.dumps(
                    {
                        "problem_ref": problem_ref,
                        "canonical_problem_sha256": hashlib.sha256(canonical_problem).hexdigest(),
                        "runtime_hints_float_paths": hint_float_paths,
                        "world_model_record_id": (
                            cycle_context.world_model_record.world_model_record_id
                        ),
                        "world_model_record_content_hash": (
                            cycle_context.world_model_record.content_hash
                        ),
                        "candidate_id": candidate.candidate_id,
                        "atom_ids": [
                            atom.intervention_id for atom in candidate.intervention_atoms
                        ],
                        "selected_outcomes": [problem.outcome_of_interest.target_variable],
                        "selected_ncm_ref": ncm_ref,
                        "selected_ncm_matches_fixture": n5_request.engine_plan[0].ncm_spec
                        == expected_ncm,
                        "n5_result_ref": simulation.simulation_result_ref.model_dump(
                            mode="json"
                        ),
                        "n5_result_manifest_inputs": [
                            item.model_dump(mode="json")
                            if hasattr(item, "model_dump")
                            else str(item)
                            for item in n5_manifest.inputs
                        ],
                        "uncertainty_kind": reopened.uncertainty_kind,
                        "n8_status": value_port.status,
                        "n8_value_receipt": value_port.value_receipt,
                        "n8_blockers": value_port.authority_blockers,
                    },
                    sort_keys=True,
                    default=str,
                )
            )

            # Observe the production-composed pre-N9 gate itself. A refusal here
            # records the actual gate result; it is not counted as a N9 invocation.
            gate_calls: list[str] = []
            real_gate = runtime.epoch_validity_gate.reconcile_before_n9

            def counted_gate(*, subject_ref: Any) -> Any:
                gate_calls.append(str(subject_ref))
                return real_gate(subject_ref=subject_ref)

            monkeypatch.setattr(runtime.epoch_validity_gate, "reconcile_before_n9", counted_gate)

            n9_calls: list[object] = []
            real_n9_call = CanonicalN9PromotionPort.__call__

            def counted_n9_call(
                self: CanonicalN9PromotionPort,
                *,
                admitted_batch: Any,
                problem: Any,
                deployment_identity: str | None,
            ) -> Any:
                n9_calls.append(admitted_batch)
                return real_n9_call(
                    self,
                    admitted_batch=admitted_batch,
                    problem=problem,
                    deployment_identity=deployment_identity,
                )

            monkeypatch.setattr(CanonicalN9PromotionPort, "__call__", counted_n9_call)
            controller = GenerationCycleController(
                promotion_runtime=runtime,
                repo_root=REPO_ROOT,
            )
            with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
                pre_n9 = controller._promote_completed_generation(
                    summaries=(summary,),
                    problem=problem,
                    deployment_identity=_canonical_loaded_deployment_identity(),
                )
            assert pre_n9.status == "not_promoted"
            assert pre_n9.reason == "epoch_validity_refused:policy_admission_missing"
            assert len(gate_calls) == 1
            assert n9_calls == []

            # Existing test-only appointment exposes the public N9 consumer. It
            # supplies no production signer/currentness positive and cannot close B05.
            with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
                admitted_batch = _positive_epoch_admitted_batch(
                    runtime=runtime,
                    problem=problem,
                    summaries=(summary,),
                )
                n9 = CanonicalN9PromotionPort(
                    promotion_runtime=runtime,
                    epoch_n9_evidence_resolver=runtime.epoch_n9_evidence_resolver,
                    repo_root=REPO_ROOT,
                )
                identity = _canonical_loaded_deployment_identity()
                baseline = n9(
                    admitted_batch=admitted_batch,
                    problem=problem,
                    deployment_identity=identity,
                )
            assert len(n9_calls) == 1
            assert n9_calls[0] is admitted_batch
            assert baseline.status == "not_promoted"
            assert baseline.receipts
            baseline_receipt = CanonicalPromotionReceipt.model_validate(baseline.receipts[0])
            assert baseline_receipt.promoted is False
            assert baseline_receipt.owner_projection.candidate_summary.value_ref == str(
                simulation.simulation_result_ref.artifact_id
            )
            baseline_value_obligation = next(
                row
                for row in baseline_receipt.obligations
                if row.obligation_class.value == "value"
            )
            assert baseline_value_obligation.gate_id.value == "n8_value"
            assert baseline_value_obligation.status.value == "failed"
            assert baseline_value_obligation.detail == "N8 value receipt is missing."

            # R1: preserve the same K_sim ref and N8 markers, deny its CAS bytes,
            # and invoke public N9 again. Matching obligations means N9 uses the
            # carried N8 receipt/status, not a content-bound K_sim discriminator.
            n5_artifact_id = str(simulation.simulation_result_ref.artifact_id)
            real_get_bytes = runtime.store.get_bytes
            n5_reads: list[str] = []

            def deny_n5_read(artifact_ref: Any = None, *args: Any, **kwargs: Any) -> bytes:
                ref = artifact_ref if artifact_ref is not None else kwargs.get("artifact_id")
                artifact_id = str(getattr(ref, "artifact_id", ref))
                if artifact_id == n5_artifact_id:
                    n5_reads.append(artifact_id)
                    raise AssertionError("N9 attempted to read the removed K_sim CAS property")
                return real_get_bytes(artifact_ref, *args, **kwargs)

            monkeypatch.setattr(runtime.store, "get_bytes", deny_n5_read)
            with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
                without_ksim_bytes = n9(
                    admitted_batch=admitted_batch,
                    problem=problem,
                    deployment_identity=identity,
                )
            assert len(n9_calls) == 2
            assert n9_calls[1] is admitted_batch
            assert n5_reads == []
            assert without_ksim_bytes.status == baseline.status
            assert without_ksim_bytes.certified_candidate_ids == baseline.certified_candidate_ids
            assert without_ksim_bytes.receipts
            removed_receipt = CanonicalPromotionReceipt.model_validate(
                without_ksim_bytes.receipts[0]
            )
            assert removed_receipt.promoted is False
            removed_value_obligation = next(
                row
                for row in removed_receipt.obligations
                if row.obligation_class.value == "value"
            )
            assert removed_value_obligation == baseline_value_obligation
            assert removed_receipt.refusal_reasons == baseline_receipt.refusal_reasons
            assert len(gate_calls) == 1
            print(
                "N9_GATE_WITNESS="
                + json.dumps(
                    {
                        "production_gate_calls": gate_calls,
                        "production_gate_result": pre_n9.reason,
                        "production_n9_calls_after_gate": 0,
                        "direct_public_n9_calls": len(n9_calls),
                        "test_only_admission": True,
                        "public_n9_status": baseline.status,
                        "public_n9_value_obligation": {
                            "gate_id": baseline_value_obligation.gate_id.value,
                            "status": baseline_value_obligation.status.value,
                            "detail": baseline_value_obligation.detail,
                        },
                        "cas_removed_n9_status": without_ksim_bytes.status,
                        "cas_removed_n5_reads": n5_reads,
                        "same_value_obligation_after_cas_removal": (
                            removed_value_obligation == baseline_value_obligation
                        ),
                        "production_signed_currentness_positive": False,
                    },
                    sort_keys=True,
                    default=str,
                )
            )
    finally:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            store.close()
