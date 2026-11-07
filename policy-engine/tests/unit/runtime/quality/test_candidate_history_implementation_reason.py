"""Keep historical replay refusal reasons aligned with the stored live basis."""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ArtifactID, ArtifactRef, artifact_ref_identity_key
from polisyos.runtime.quality import acquisition_evaluation, candidate_source_basis
from polisyos.runtime.quality.joint_simulation_horizon import (
    prepare_joint_simulation_configuration,
)
from polisyos.runtime.quality.n5_execution_basis import (
    N5ExecutionImplementationWitness,
    exact_n5_content_hash,
)


def _witness(input_ref: ArtifactRef) -> N5ExecutionImplementationWitness:
    payload = {
        "schema_version": "N5ExecutionImplementationWitness@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_scope": "same_live_process_loaded_implementation",
        "process_session": "historical-process",
        "input_ref_identity": artifact_ref_identity_key(input_ref),
        "request_content_hash": "sha256:" + "a" * 64,
        "result_without_witness_hash": "sha256:" + "b" * 64,
        "trajectory_hash": "sha256:" + "c" * 64,
        "implementation": {},
        "consumed_configuration_values": None,
        "predicate_provenance": "not_established",
        "reason_codes": ("canonical_loaded_runtime_mismatch",),
    }
    wire_payload = json.loads(json.dumps(payload))
    return N5ExecutionImplementationWitness.model_validate(
        {**wire_payload, "content_hash": exact_n5_content_hash(wire_payload)}
    )


@pytest.mark.parametrize(
    ("historical_read_only", "expected_reason"),
    [
        (True, "n5_prior_live_implementation_not_established"),
        (False, "candidate_evaluation_implementation_not_established"),
    ],
)
def test_unqualified_n5_witness_keeps_scope_specific_refusal_reason(
    monkeypatch: pytest.MonkeyPatch,
    historical_read_only: bool,
    expected_reason: str,
) -> None:
    input_ref = ArtifactRef(
        artifact_id=ArtifactID.model_validate("sha256:" + "1" * 64),
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "2" * 64,
    )
    prior = acquisition_evaluation.ResolvedAcquisitionEvaluation(
        selected=SimpleNamespace(n5_input_ref=input_ref),
        source=None,
        input_record=None,
        execution=None,
        result=object(),
        handoff=None,
    )
    monkeypatch.setattr(
        candidate_source_basis,
        "prepare_candidate_source_basis_values",
        lambda **_kwargs: SimpleNamespace(predicate_provenance="recomputed", reason_codes=()),
    )
    monkeypatch.setattr(
        acquisition_evaluation,
        "read_n5_execution_implementation_witness",
        lambda _result, *, input_ref: _witness(input_ref),
    )
    monkeypatch.setattr(
        acquisition_evaluation,
        "reconcile_live_n5_implementation",
        lambda _result, *, input_ref: _witness(input_ref),
    )

    values, reasons = acquisition_evaluation.recompute_candidate_acquisition_basis_values(
        artifact_store=object(),
        problem=object(),
        preparation_inputs=object(),
        predecessors=(),
        prior=prior,
        prepared_n5_configuration=prepare_joint_simulation_configuration(),
        fresh_limit_usd=Decimal("1"),
        global_limit_usd=Decimal("5"),
        historical_read_only=historical_read_only,
    )

    assert values == {}
    assert reasons == (expected_reason,)
