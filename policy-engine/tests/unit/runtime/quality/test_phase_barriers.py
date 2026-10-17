from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.runtime.quality.phase_barriers import (
    PhaseBarrierError,
    PhaseBarrierId,
    PhaseBarrierLedger,
    PhaseBarrierRecord,
    _execution_owner_binding_from_admission,
    _reconcile_phase_barrier_subjects,
    _validated_execution_owner_binding,
    latest_barrier_record,
)


def _record(
    barrier_id: PhaseBarrierId,
    *,
    run_id: str = "run-a",
    tenant_id: str = "tenant-a",
    profile: str = "production",
) -> PhaseBarrierRecord:
    return PhaseBarrierRecord.pass_record(
        barrier_id=barrier_id,
        run_id=run_id,
        tenant_id=tenant_id,
        profile=profile,
        evidence_refs=(f"event://barrier/{barrier_id.value}",),
    )


@pytest.mark.parametrize(
    ("field", "foreign_value"),
    [("run_id", "run-b"), ("tenant_id", "tenant-b"), ("profile", "governed")],
)
def test_latest_barrier_reconciles_full_candidate_identity_before_selection(
    field: str,
    foreign_value: str,
) -> None:
    selected = _record(PhaseBarrierId.POLICY_INTENT_CANONICALIZATION)
    foreign = _record(
        PhaseBarrierId.FABRIC_DATA_BACKING,
        **{field: foreign_value},
    )

    with pytest.raises(PhaseBarrierError) as error:
        latest_barrier_record(
            selected.barrier_id,
            barriers=(selected, foreign),
        )

    assert error.value.code == "phase_barrier_scope_mismatch"
    assert error.value.field == field


def test_latest_barrier_reconciles_mixed_duplicate_before_latest_selection() -> None:
    old = _record(PhaseBarrierId.LEX_LEGAL_COMPATIBILITY)
    latest_foreign = _record(
        PhaseBarrierId.LEX_LEGAL_COMPATIBILITY,
        tenant_id="tenant-b",
    )

    with pytest.raises(PhaseBarrierError) as error:
        latest_barrier_record(
            PhaseBarrierId.LEX_LEGAL_COMPATIBILITY,
            barriers=(old, latest_foreign),
        )

    assert error.value.code == "phase_barrier_scope_mismatch"
    assert error.value.field == "tenant_id"


def test_owner_binding_requires_complete_current_job_identity() -> None:
    binding = {
        "job_id": "job-a",
        "run_id": "run-a",
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "requested_execution_profile": "production",
        "effective_execution_profile": "production",
        "attempt": 2,
        "lease_owner": "worker-a",
    }

    assert _validated_execution_owner_binding(binding, expected={"job_id": "job-a"}) == binding
    assert (
        _validated_execution_owner_binding(
            binding,
            expected={"attempt": 1},
        )
        is None
    )
    assert _validated_execution_owner_binding({**binding, "attempt": True}) is None
    assert (
        _validated_execution_owner_binding(
            {key: value for key, value in binding.items() if key != "tenant_id"}
        )
        is None
    )


def test_owner_binding_is_projected_only_from_current_admitted_job_and_scope() -> None:
    job = SimpleNamespace(
        job_id="job-a",
        run_id="run-a",
        state="running",
        requested_execution_profile="production",
        effective_execution_profile="production",
        attempt=3,
        lease_owner="worker-a",
    )
    scope = SimpleNamespace(
        status="established",
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    admission = SimpleNamespace(job=job, scope=scope, attempt=3)

    binding = _execution_owner_binding_from_admission(
        admission,
        expected_job_id="job-a",
        expected_run_id="run-a",
        expected_effective_profile="production",
        expected_scope={"tenant_id": "tenant-a", "cell_id": "cell-a"},
    )

    assert binding == {
        "job_id": "job-a",
        "run_id": "run-a",
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "requested_execution_profile": "production",
        "effective_execution_profile": "production",
        "attempt": 3,
        "lease_owner": "worker-a",
    }
    assert (
        _execution_owner_binding_from_admission(
            admission,
            expected_job_id="job-a",
            expected_run_id="run-a",
            expected_scope={"tenant_id": "foreign-tenant"},
        )
        is None
    )
    assert (
        _execution_owner_binding_from_admission(
            SimpleNamespace(
                job=SimpleNamespace(**{**vars(job), "requested_execution_profile": None}),
                scope=scope,
                attempt=3,
            ),
            expected_job_id="job-a",
            expected_run_id="run-a",
        )
        is None
    )


def test_reconciliation_matches_requested_profile_not_only_candidate_consensus() -> None:
    record = _record(PhaseBarrierId.POLICY_INTENT_CANONICALIZATION)

    with pytest.raises(PhaseBarrierError) as error:
        _reconcile_phase_barrier_subjects((record,), expected_profile="research")

    assert error.value.code == "phase_barrier_scope_mismatch"
    assert error.value.field == "profile"


def test_ledger_reconciles_only_records_in_the_requested_run(tmp_path: Path) -> None:
    ledger = PhaseBarrierLedger(tmp_path / "phase-barriers.jsonl")
    selected = _record(PhaseBarrierId.POLICY_INTENT_CANONICALIZATION)
    unrelated = _record(
        PhaseBarrierId.FABRIC_DATA_BACKING,
        run_id="run-unrelated",
        tenant_id="tenant-other",
        profile="research",
    )
    ledger.append(unrelated)
    ledger.append(selected)

    assert (
        ledger.latest(
            run_id="run-a",
            barrier_id=PhaseBarrierId.POLICY_INTENT_CANONICALIZATION,
        )
        == selected
    )


def test_ledger_rejects_scope_mismatch_inside_the_requested_run(tmp_path: Path) -> None:
    ledger = PhaseBarrierLedger(tmp_path / "phase-barriers.jsonl")
    ledger.append(_record(PhaseBarrierId.POLICY_INTENT_CANONICALIZATION))
    ledger.append(
        _record(
            PhaseBarrierId.FABRIC_DATA_BACKING,
            tenant_id="tenant-b",
        )
    )

    with pytest.raises(PhaseBarrierError) as error:
        ledger.latest(
            run_id="run-a",
            barrier_id=PhaseBarrierId.POLICY_INTENT_CANONICALIZATION,
        )

    assert error.value.code == "phase_barrier_scope_mismatch"
    assert error.value.field == "tenant_id"
