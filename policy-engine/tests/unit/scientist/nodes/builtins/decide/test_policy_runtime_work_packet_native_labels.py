from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.funnel.types import FunnelExecutedWorkPacket
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
    _persist_policy_runtime_work_packet,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationArtifact,
    PolicyRuntimeProvenance,
)
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


class _IntLabelSpoof(int):
    label: str

    def __new__(cls, value: int, label: str) -> _IntLabelSpoof:
        instance = int.__new__(cls, value)
        instance.label = label
        return instance

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str) and other == self.label:
            return True
        return int.__eq__(self, other) is True

    __hash__ = int.__hash__


class _StrLabelSpoof(str):
    label: str

    def __new__(cls, value: str, label: str) -> _StrLabelSpoof:
        instance = str.__new__(cls, value)
        instance.label = label
        return instance

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str) and other == self.label:
            return True
        return str.__eq__(self, other) is True

    __hash__ = str.__hash__


def _candidate(candidate_id: str) -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id=f"problem_{candidate_id}",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id=f"policy_{candidate_id}"),
            model_spec=ModelSpec(
                model_id=f"model_{candidate_id}",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        candidate_id=candidate_id,
    )


def _runtime_artifact(
    candidate: PolicyCandidateSchema,
) -> PolicyRuntimeEvaluationArtifact:
    invocation = {
        "evaluation_attempt_id": "attempt:medium",
        "requested_draw_count": 17,
        "requested_draw_source": "effective_estimation_config",
        "effective_estimation_config_sha256": "c" * 64,
    }
    vector = PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        feasible=True,
        metadata={
            "fidelity_observed": "medium",
            "policy_runtime_invocation": invocation,
            "policy_runtime_fiscal_measurement": {
                "usable": False,
                "normalized_value": None,
                "source_values": {},
            },
        },
    )
    provenance = PolicyRuntimeProvenance(
        backend_kind="typed_work_packet_fixture",
        fidelity_mode="medium",
        promotable_source=False,
        notes=("Test fixture; no scientific draw loop is exercised.",),
    )
    return PolicyRuntimeEvaluationArtifact(
        simulation_metrics={"gdp_change": 0.2},
        simulation_results={
            "gdp_change": 0.2,
            "budget_deficit_objective_usable": False,
            "budget_deficit_objective_value": None,
            "bootstrap": {
                **invocation,
                "draw_execution_status": "not_instrumented",
                "attempted_draw_count": None,
                "successful_draw_count": None,
                "failed_draw_count": None,
                "unattempted_draw_count": None,
            },
        },
        evaluation_vector=vector,
        fidelity="medium",
        provenance=provenance,
    )


def _with_draw_source(
    artifact: PolicyRuntimeEvaluationArtifact,
    draw_source: object,
) -> PolicyRuntimeEvaluationArtifact:
    simulation_results = dict(artifact.simulation_results)
    bootstrap = dict(simulation_results["bootstrap"])
    bootstrap["requested_draw_source"] = draw_source
    simulation_results["bootstrap"] = bootstrap

    metadata = dict(artifact.evaluation_vector.metadata)
    invocation = dict(metadata["policy_runtime_invocation"])
    invocation["requested_draw_source"] = draw_source
    metadata["policy_runtime_invocation"] = invocation
    vector = artifact.evaluation_vector.model_copy(update={"metadata": metadata})
    return replace(
        artifact,
        simulation_results=simulation_results,
        evaluation_vector=vector,
    )


def _with_invocation_draw_source(
    artifact: PolicyRuntimeEvaluationArtifact,
    draw_source: object,
) -> PolicyRuntimeEvaluationArtifact:
    metadata = dict(artifact.evaluation_vector.metadata)
    invocation = dict(metadata["policy_runtime_invocation"])
    invocation["requested_draw_source"] = draw_source
    metadata["policy_runtime_invocation"] = invocation
    vector = artifact.evaluation_vector.model_copy(update={"metadata": metadata})
    return replace(artifact, evaluation_vector=vector)


def _without_draw_source(
    artifact: PolicyRuntimeEvaluationArtifact,
) -> PolicyRuntimeEvaluationArtifact:
    simulation_results = dict(artifact.simulation_results)
    bootstrap = dict(simulation_results["bootstrap"])
    bootstrap.pop("requested_draw_source")
    simulation_results["bootstrap"] = bootstrap

    metadata = dict(artifact.evaluation_vector.metadata)
    invocation = dict(metadata["policy_runtime_invocation"])
    invocation.pop("requested_draw_source")
    metadata["policy_runtime_invocation"] = invocation
    vector = artifact.evaluation_vector.model_copy(update={"metadata": metadata})
    return replace(
        artifact,
        simulation_results=simulation_results,
        evaluation_vector=vector,
    )


def _with_requested_draw_count(
    artifact: PolicyRuntimeEvaluationArtifact,
    draw_count: int,
) -> PolicyRuntimeEvaluationArtifact:
    simulation_results = dict(artifact.simulation_results)
    bootstrap = dict(simulation_results["bootstrap"])
    bootstrap["requested_draw_count"] = draw_count
    simulation_results["bootstrap"] = bootstrap

    metadata = dict(artifact.evaluation_vector.metadata)
    invocation = dict(metadata["policy_runtime_invocation"])
    invocation["requested_draw_count"] = draw_count
    metadata["policy_runtime_invocation"] = invocation
    vector = artifact.evaluation_vector.model_copy(update={"metadata": metadata})
    return replace(
        artifact,
        simulation_results=simulation_results,
        evaluation_vector=vector,
    )


def _initial_state(
    store: FileSystemCAS,
    candidate_ref: object,
    *,
    run_id: str,
) -> dict[str, Any]:
    return {
        "store": store,
        "policy_candidate_ref": candidate_ref,
        "pinned_input_signature": f"signature:{run_id}",
        "policy_runtime_work_identity": {
            "candidate_ref": candidate_ref,
            "run_id": run_id,
            "ticket_id": f"ticket:{run_id}",
            "candidate_hash": f"candidate-hash:{run_id}",
        },
    }


def _artifact_id_snapshot(store: FileSystemCAS) -> tuple[str, ...]:
    return tuple(sorted(str(artifact_id) for artifact_id in store.iter_artifact_ids()))


def _assert_refused_without_work_packet(
    tmp_path: Path,
    *,
    candidate_id: str,
    runtime_artifact: PolicyRuntimeEvaluationArtifact,
    fidelity: object = "medium",
    expected_reason: str = "runtime_execution_binding_unavailable",
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate(candidate_id)
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    before = _artifact_id_snapshot(store)

    packet_ref, unavailable_reason = _persist_policy_runtime_work_packet(
        initial_state=_initial_state(
            store,
            candidate_ref,
            run_id=f"run_{candidate_id}",
        ),
        fidelity=fidelity,
        evaluation_attempt_id="attempt:medium",
        runtime_artifact=runtime_artifact,
    )

    assert packet_ref is None
    assert unavailable_reason == expected_reason
    assert _artifact_id_snapshot(store) == before


def test_genuine_requested_draw_source_persists_bound_work_packet(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate("candidate_native_label_positive")
    candidate_ref = persist_policy_candidate_schema(store, candidate)

    packet_ref, unavailable_reason = _persist_policy_runtime_work_packet(
        initial_state=_initial_state(
            store,
            candidate_ref,
            run_id="run_native_label_positive",
        ),
        fidelity="medium",
        evaluation_attempt_id="attempt:medium",
        runtime_artifact=_runtime_artifact(candidate),
    )

    assert unavailable_reason is None
    assert packet_ref is not None
    packet = FunnelExecutedWorkPacket.model_validate(
        from_canonical_bytes(store.get_bytes(packet_ref))
    )
    source_payload = from_canonical_bytes(store.get_bytes(packet.source_result_ref))
    source_metadata = source_payload["metadata"]
    invocation = source_metadata["policy_runtime_invocation"]
    assert packet.requested_draw_count == 17
    assert packet.requested_draw_source == "effective_estimation_config"
    assert invocation["requested_draw_source"] == packet.requested_draw_source
    assert packet.effective_estimation_config_sha256 == "c" * 64


@pytest.mark.parametrize(
    ("draw_source", "serialized_value"),
    [
        pytest.param(
            _IntLabelSpoof(1, "effective_estimation_config"),
            '{"requested_draw_source": 1}',
            id="int-subclass",
        ),
        pytest.param(
            _StrLabelSpoof(
                "untrusted_source_label",
                "effective_estimation_config",
            ),
            '{"requested_draw_source": "untrusted_source_label"}',
            id="str-subclass",
        ),
        pytest.param(
            "unsupported_source_label",
            '{"requested_draw_source": "unsupported_source_label"}',
            id="builtin-invalid-string",
        ),
        pytest.param(
            ["effective_estimation_config"],
            '{"requested_draw_source": ["effective_estimation_config"]}',
            id="malformed-present",
        ),
    ],
)
def test_invalid_requested_draw_source_refuses_before_any_work_packet_write(
    tmp_path: Path,
    draw_source: object,
    serialized_value: str,
) -> None:
    assert json.dumps({"requested_draw_source": draw_source}) == serialized_value
    candidate = _candidate("candidate_native_label_source_invalid")
    artifact = _with_draw_source(_runtime_artifact(candidate), draw_source)

    _assert_refused_without_work_packet(
        tmp_path,
        candidate_id="candidate_native_label_source_invalid",
        runtime_artifact=artifact,
    )


def test_absent_requested_draw_source_refuses_before_any_work_packet_write(
    tmp_path: Path,
) -> None:
    candidate = _candidate("candidate_native_label_source_absent")
    artifact = _without_draw_source(_runtime_artifact(candidate))
    bootstrap = artifact.simulation_results["bootstrap"]
    invocation = artifact.evaluation_vector.metadata["policy_runtime_invocation"]
    assert "requested_draw_source" not in bootstrap
    assert "requested_draw_source" not in invocation

    _assert_refused_without_work_packet(
        tmp_path,
        candidate_id="candidate_native_label_source_absent",
        runtime_artifact=artifact,
    )


def test_invocation_string_subclass_refuses_before_metadata_equality(
    tmp_path: Path,
) -> None:
    candidate = _candidate("candidate_native_label_invocation_spoof")
    spoof = _StrLabelSpoof(
        "untrusted_source_label",
        "effective_estimation_config",
    )
    assert (
        json.dumps({"requested_draw_source": spoof})
        == '{"requested_draw_source": "untrusted_source_label"}'
    )
    artifact = _with_invocation_draw_source(_runtime_artifact(candidate), spoof)

    _assert_refused_without_work_packet(
        tmp_path,
        candidate_id="candidate_native_label_invocation_spoof",
        runtime_artifact=artifact,
    )


@pytest.mark.parametrize(
    ("fidelity", "serialized_value"),
    [
        pytest.param(
            _IntLabelSpoof(1, "medium"),
            '{"fidelity": 1}',
            id="int-subclass",
        ),
        pytest.param(
            _StrLabelSpoof("untrusted_fidelity_label", "medium"),
            '{"fidelity": "untrusted_fidelity_label"}',
            id="str-subclass",
        ),
        pytest.param(
            "partial",
            '{"fidelity": "partial"}',
            id="builtin-invalid-string",
        ),
    ],
)
def test_invalid_fidelity_refuses_before_any_work_packet_write(
    tmp_path: Path,
    fidelity: object,
    serialized_value: str,
) -> None:
    assert json.dumps({"fidelity": fidelity}) == serialized_value
    candidate = _candidate("candidate_native_label_fidelity_invalid")

    _assert_refused_without_work_packet(
        tmp_path,
        candidate_id="candidate_native_label_fidelity_invalid",
        fidelity=fidelity,
        runtime_artifact=_runtime_artifact(candidate),
        expected_reason="unsupported_fidelity",
    )


def test_int_subclass_draw_count_keeps_existing_integer_contract(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate("candidate_native_label_integer_count")
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    artifact = _with_requested_draw_count(
        _runtime_artifact(candidate),
        _IntLabelSpoof(17, "effective_estimation_config"),
    )

    packet_ref, unavailable_reason = _persist_policy_runtime_work_packet(
        initial_state=_initial_state(
            store,
            candidate_ref,
            run_id="run_native_label_integer_count",
        ),
        fidelity="medium",
        evaluation_attempt_id="attempt:medium",
        runtime_artifact=artifact,
    )

    assert unavailable_reason is None
    assert packet_ref is not None
    packet = FunnelExecutedWorkPacket.model_validate(
        from_canonical_bytes(store.get_bytes(packet_ref))
    )
    assert packet.requested_draw_count == 17
