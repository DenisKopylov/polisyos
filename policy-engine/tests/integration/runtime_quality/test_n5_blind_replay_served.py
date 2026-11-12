"""Explicitly admitted real-source NCM original and blind candidate replay."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from polisyos.core import artifacts
from polisyos.core.canon import CanonSpec
from polisyos.runtime.quality.n5_replay_appointment import (
    N5ReplayAppointment,
    N5ReplayComparatorProfile,
    N5ReplayDeployedComponent,
    N5ReplayScope,
    N5ReplayUseQuery,
)
from polisyos.runtime.quality.n5_replay_execution import (
    N5BlindReplayExecution,
    N5OriginalProducerAction,
    N5ReplayLauncherSigningService,
    _read_blind_action,
    produce_n5_replay_basis_for_original,
    run_appointed_n5_replay,
    run_original_n5_producer,
)
from polisyos.runtime.quality.n5_replay_numerical_projection import (
    N5_NUMERICAL_RESULT_PROJECTION_SCHEMA,
    N5_REPLAY_EXCLUDED_TIME_IDENTITY_PATHS,
)
from tests.unit.runtime.quality.test_n5_replay_appointment import (
    _write,
)
from tests.unit.runtime.quality.test_n5_replay_appointment import (
    demonstration_test_trust_root as _demonstration_test_trust_root,
)


@pytest.fixture
def demo_trust_root_fixture(tmp_path: Path) -> object:
    """Construct the shared demonstration-only signing fixture in this module."""
    return _demonstration_test_trust_root.__wrapped__(tmp_path)


@pytest.mark.integration
def test_retained_source_fresh_original_and_blind_repeat(
    tmp_path: Path, demo_trust_root_fixture: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise real source, fresh processes, separate ledgers, and parent comparison.

    This costly selector requires an explicitly admitted retained V5 source and
    must run alone under the repository process budget and frozen source image.
    """
    selector_path = os.environ.get("POLISYOS_N5_REPLAY_SOURCE_SELECTOR")
    cas_path = os.environ.get("POLISYOS_N5_REPLAY_SOURCE_CAS")
    if not selector_path or not cas_path:
        pytest.skip("explicit retained source and CAS admission required")
    selected = json.loads(Path(selector_path).read_text(encoding="utf-8"))
    source_ref = artifacts.ArtifactRef.model_validate(selected["input"]["ref"])
    tenant_id, cell_id = selected["tenant_id"], selected["cell_id"]
    store = artifacts.FileSystemCAS(Path(cas_path)).for_tenant(tenant_id, cell_id)
    preserved_path = os.environ.get("POLISYOS_N5_REPLAY_ORIGINAL_LEDGER")
    preserved = Path(preserved_path).read_bytes() if preserved_path else None
    suffix = uuid4().hex
    original_workspace = tmp_path / "original"
    action = N5OriginalProducerAction(
        source_input_ref=source_ref,
        source_run_id=selected["run_id"],
        source_job_id=selected["job_id"],
        producer_run_id=f"original-{suffix}",
        producer_job_id=f"original-job-{suffix}",
        tenant_id=tenant_id,
        cell_id=cell_id,
        cas_root=str(Path(cas_path).resolve()),
        ledger_path=str(original_workspace / "original-ledger.json"),
        quota_units=2,
    )
    original = run_original_n5_producer(action=action, workspace=original_workspace)
    assert len(original.execution.operation_ids) == 2
    assert original.execution.pid != os.getpid()
    scope = N5ReplayScope(
        tenant_id=tenant_id,
        cell_id=cell_id,
        accepting_organization="demo-accepting-organization",
        scope_id=f"demo-{suffix}",
    )
    basis = produce_n5_replay_basis_for_original(
        store=store,
        original_execution_ref=original.execution_ref,
        scope=scope,
        producer_instance_id=f"candidate-original-{suffix}",
        produced_at=datetime.now(UTC),
    )
    demo = demo_trust_root_fixture
    demo.store = store
    demo.now = datetime.now(UTC)
    demo.state = replace(
        demo.state, config=demo.state.config.model_copy(update={"authorized_scopes": (scope,)})
    )
    launcher = _write(
        store,
        (Path(__file__).resolve().parents[3] / "tools" / "authority").read_bytes(),
        "runtime.quality.n5_replay_launcher_profile",
    )
    intent = artifacts.load_core_json_artifact(store, basis.statement.numerical_intent_ref)
    component = N5ReplayDeployedComponent(
        launcher_profile_ref=launcher,
        execution_profile_ref=basis.statement.execution_profile_ref,
        component_provenance_ref=artifacts.ArtifactRef.model_validate(
            intent["production_image_ref"]
        ),
    )
    demo.state = replace(demo.state, component=component)
    comparator = N5ReplayComparatorProfile(
        numerical_projection_schema=N5_NUMERICAL_RESULT_PROJECTION_SCHEMA,
        excluded_time_identity_paths=N5_REPLAY_EXCLUDED_TIME_IDENTITY_PATHS,
    )
    comparator_ref = store.put_json(
        comparator.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="runtime.quality.n5_replay_comparator_profile", media_type="application/json"
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
        return_selected_profile=True,
    )
    producer_ref = demo.signed(
        basis.statement, "producer", "runtime.quality.n5_original_producer_seal"
    )
    appointment = N5ReplayAppointment(
        scope=scope,
        launcher_identity="demo://launcher",
        launcher_key_id=demo.signers["launcher"].key_id,
        launcher_profile_ref=launcher,
        comparator_ref=comparator_ref,
        comparator_content_hash=str(comparator_ref.artifact_id),
        supported_tiers=("STRICT_CPU",),
        allocated_capacity_units=2,
        attempt_limit=2,
        valid_from=demo.now - timedelta(minutes=1),
        valid_until=demo.now + timedelta(hours=1),
        configured_independence="same_organization_separate_function",
    )
    demo.install_appointment(appointment)
    query = N5ReplayUseQuery(
        scope=scope,
        original_producer_evidence_ref=producer_ref,
        execution_profile_ref=basis.statement.execution_profile_ref,
        comparator_ref=comparator_ref,
        tier="STRICT_CPU",
        replay_seed_schedule_hash=basis.statement.seed_schedule_hash,
        planned_physical_units=2,
        replay_run_id=f"replay-{suffix}",
        replay_job_id=f"replay-job-{suffix}",
    )
    service = N5ReplayLauncherSigningService(
        signer=demo.signers["launcher"],
        signing_profile_ref=_write(store, b"demo-launcher-profile", "test.n5.signing_profile"),
        signer_provenance_ref=_write(store, b"demo-launcher", "test.n5.signer_provenance"),
        launcher_instance_id=f"demo-launcher-{suffix}",
    )
    comparison, comparison_ref = run_appointed_n5_replay(
        resolver=demo.resolver(), query=query, launcher_signing_service=service
    )
    assert comparison.status == "equal"
    assert comparison.protected_use_allowed is False
    assert comparison.child_pid != original.execution.pid
    assert comparison.child_pid != os.getpid()
    assert comparison.replay_result_ref != original.execution.result_ref
    assert store.verify(comparison_ref).ok
    child = artifacts.validate_core_model_json_artifact(
        N5BlindReplayExecution, store, comparison.child_execution_ref
    )
    action_bytes = store.get_bytes(child.action_ref)
    assert (
        _read_blind_action(store, child.action_ref, child.action_hash).launch_spec.source_run_id
        == selected["run_id"]
    )
    for forbidden in (
        "original_execution_ref",
        "original_result_ref",
        "numerical_result_projection_hash",
    ):
        assert forbidden not in action_bytes.decode("utf-8")
    assert store.verify(child.ledger_snapshot_ref).ok
    if preserved is not None:
        assert Path(preserved_path).read_bytes() == preserved

    # A fresh occurrence with the same numerical basis must reuse the signed
    # completion after native revalidation, with no child or ledger mutation.
    from polisyos.runtime.quality import n5_replay_execution as replay_owner

    managed_worker = replay_owner._run_managed_worker

    def only_native_preflight(command, *args, **kwargs):
        if "n5-replay-profile-preflight" not in command:
            raise AssertionError("completed semantic hit launched numerical work")
        return managed_worker(command, *args, **kwargs)

    monkeypatch.setattr(replay_owner, "_run_managed_worker", only_native_preflight)
    claim_dir = store.root.parent / ".n5-replay-attempts" / comparison.attempt_key
    before_ledger = (claim_dir / "diagnostic-ledger.json").read_bytes()
    before_state = (claim_dir / "state.json").read_bytes()
    later_query = query.model_copy(
        update={"replay_run_id": f"reuse-{suffix}", "replay_job_id": f"reuse-job-{suffix}"}
    )
    reused, reused_ref = run_appointed_n5_replay(resolver=demo.resolver(), query=later_query)
    assert reused == comparison and reused_ref == comparison_ref
    assert (claim_dir / "diagnostic-ledger.json").read_bytes() == before_ledger
    assert (claim_dir / "state.json").read_bytes() == before_state
    for role in ("issuer", "admin", "launcher"):
        revoked = demo.state.config.model_copy(
            update={"revoked_key_ids": (demo.signers[role].key_id,)}
        )
        original_state = demo.state
        try:
            demo.state = replace(demo.state, config=revoked)
            with pytest.raises(ValueError):
                run_appointed_n5_replay(resolver=demo.resolver(), query=later_query)
        finally:
            demo.state = original_state
    assert (claim_dir / "diagnostic-ledger.json").read_bytes() == before_ledger
    assert (claim_dir / "state.json").read_bytes() == before_state

    # A discovered completion can never trigger a replacement numerical attempt
    # when its native journal is absent or nonterminal.
    state_path = claim_dir / "state.json"
    held_state_path = claim_dir / "state.held"
    state_path.rename(held_state_path)
    try:
        with pytest.raises(ValueError, match="completed_attempt_not_established"):
            run_appointed_n5_replay(resolver=demo.resolver(), query=later_query)
        active = json.loads(before_state)
        active.update(status="active", history=[])
        state_path.write_text(json.dumps(active), encoding="utf-8")
        with pytest.raises(ValueError, match="completed_attempt_not_established"):
            run_appointed_n5_replay(resolver=demo.resolver(), query=later_query)
    finally:
        state_path.unlink(missing_ok=True)
        held_state_path.rename(state_path)
    ledger_path = claim_dir / "diagnostic-ledger.json"
    ledger_path.write_bytes(b"{}")
    try:
        with pytest.raises(ValueError):
            run_appointed_n5_replay(resolver=demo.resolver(), query=later_query)
    finally:
        ledger_path.write_bytes(before_ledger)
    assert state_path.read_bytes() == before_state

    # The pointer and signed claim are both untrusted until the real source,
    # result, and accounting closure has been reopened.
    from polisyos.runtime.quality import n5_replay_appointment as appointment_owner

    pointer_path = claim_dir / "completed-evidence.json"
    before_pointer = pointer_path.read_bytes()
    evidence_ref = artifacts.ArtifactRef.model_validate_json(before_pointer)
    record, _, _, _ = demo.resolver()._signed(
        evidence_ref,
        appointment_owner.N5AppointedReplayRecordV2,
        "appointed_launcher",
        appointment_owner._trust(demo.state.config),
    )
    changed_projection = _write(
        store, b"changed result", "runtime.quality.n5_numerical_result_projection_bytes"
    )
    wrong_original = _write(
        store, b"wrong source execution", "runtime.quality.n5_original_producer_execution"
    )
    for changes in (
        {"original_execution_ref": wrong_original},
        {
            "replay_result_projection_ref": changed_projection,
            "replay_result_projection_hash": str(changed_projection.artifact_id),
        },
    ):
        forged = appointment_owner.N5AppointedReplayRecordV2.model_validate(
            record.model_copy(update={"publication_id": uuid4().hex, **changes}).model_dump()
        )
        forged_ref = demo.signed(forged, "launcher", "runtime.quality.n5_appointed_replay_record")
        pointer_path.write_text(forged_ref.model_dump_json(), encoding="utf-8")
        try:
            with pytest.raises(ValueError):
                run_appointed_n5_replay(resolver=demo.resolver(), query=later_query)
        finally:
            pointer_path.write_bytes(before_pointer)
    pointer_path.unlink()
    try:
        with pytest.raises(ValueError):
            run_appointed_n5_replay(resolver=demo.resolver(), query=later_query)
    finally:
        pointer_path.write_bytes(before_pointer)
    assert ledger_path.read_bytes() == before_ledger
    assert state_path.read_bytes() == before_state

    # Losing only the publication pointer is recoverable from the completed
    # exact occurrence; a new signed statement is emitted without new work.
    pointer_path.unlink()
    recovered, recovered_ref = run_appointed_n5_replay(
        resolver=demo.resolver(), query=query, launcher_signing_service=service
    )
    assert recovered == comparison and recovered_ref == comparison_ref
    assert pointer_path.is_file()
    assert ledger_path.read_bytes() == before_ledger
    assert state_path.read_bytes() == before_state
