from __future__ import annotations

import inspect
import json
import os
import select
import threading
import time
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactID, FileSystemCAS
from polisyos.fabric.io.atomic import atomic_write_json
from polisyos.pdc import PromotionObligationClass, gy_content_hash
from polisyos.runtime.quality import confidence_ledger as ledger_module
from polisyos.runtime.quality.confidence_ledger import (
    CONDITIONAL_VALIDITY_CLAUSE,
    ConfidenceLedgerCheck,
    ConfidenceLedgerError,
    ConfidenceLedgerSession,
    ConfidenceRiskBudgetScope,
    OwnerCertificateEvidence,
    OwnerCertificateVerification,
    PredictableClaimSpec,
    RationalSpec,
    load_confidence_ledger_registry,
    project_n9_promotion_certificate,
    project_n12_epoch_reference,
    validate_confidence_ledger_receipt,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
_HASH_1 = "sha256:" + "1" * 64
_HASH_2 = "sha256:" + "2" * 64


def _scope(
    *,
    owner_projection_hash: str = _HASH_1,
    owner_scope_key: str = "design-problem:durable-ledger-test",
) -> ConfidenceRiskBudgetScope:
    return ConfidenceRiskBudgetScope(
        scope_owner_ref="polisyos.runtime.quality.promotion_sequence",
        authority_purpose="n9_promotion",
        owner_scope_key=owner_scope_key,
        owner_projection_hash=owner_projection_hash,
        epoch_ref=None,
        model_ref=None,
        rule_ref="policyos.layer3.gy.n9.v1",
        schema_ref="policyos.runtime.design_problem.v1",
    )


def _claim(
    *,
    role: str = "promotion_conformance",
    polarity: str | None = None,
    claim_ref: str = "claim://unit/promotion",
) -> PredictableClaimSpec:
    if polarity is None:
        polarity = {
            "promotion": "false_accept",
            "promotion_conformance": "conformance_only",
            "refusal": "confident_wrong_refusal",
            "acquisition": "confident_wrong_refusal",
            "admission": "confident_wrong_admission",
        }[role]
    return PredictableClaimSpec(
        claim_ref=claim_ref,
        null_ref="null://unit/no-valid-promotion",
        claim_scope_ref="claim-scope://unit/candidate",
        data_window_ref="data-window://unit/frozen-before-check",
        certificate_role=role,
        claim_polarity=polarity,
    )


class _SessionFactory:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.store = FileSystemCAS(root / "cas")
        self.state_root = root / "state"

    def __call__(
        self,
        *,
        scope: ConfidenceRiskBudgetScope | None = None,
        resolver: Callable[[ConfidenceLedgerCheck], OwnerCertificateEvidence] | None = None,
        verifier: Callable[[OwnerCertificateEvidence], OwnerCertificateVerification] | None = None,
        registry_source: object | None = None,
        schedule_profile_id: str | None = None,
    ) -> ConfidenceLedgerSession:
        return ConfidenceLedgerSession._for_verification(
            REPO_ROOT,
            risk_scope=scope or _scope(),
            artifact_store=self.store,
            state_root=self.state_root,
            certificate_resolver=resolver,
            certificate_verifier=verifier,
            registry_source=registry_source,
            schedule_profile_id=schedule_profile_id,
        )


@pytest.fixture
def sessions(tmp_path: Path) -> _SessionFactory:
    return _SessionFactory(tmp_path)


def _install_canonical_registry(repo_root: Path) -> None:
    target = repo_root / "architecture/production_quality/confidence_ledger.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        (REPO_ROOT / "architecture/production_quality/confidence_ledger.toml").read_bytes()
    )


def _install_loaded_deployment(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Install all bytes used to identify a test-loaded policy-engine checkout."""

    _install_canonical_registry(repo_root)
    for relative in (
        Path("pyproject.toml"),
        Path("uv.lock"),
        Path("src/polisyos/__init__.py"),
        Path("src/polisyos/core/canon/canon_json.py"),
        Path("src/polisyos/runtime/quality/confidence_ledger.py"),
    ):
        target = repo_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / relative).read_bytes())
    monkeypatch.setattr(ledger_module, "_loaded_policy_engine_root", lambda: repo_root)


def _prepare(
    session: ConfidenceLedgerSession,
    *,
    request_key: str = "request://unit/1",
    obligation_class: PromotionObligationClass = PromotionObligationClass.CALIBRATION,
    instrument_id: str = "constant_unit_e_process",
    certificate_ref: str = "construction://constant-unit-e-process/1",
    certificate_class: str | None = None,
    claim: PredictableClaimSpec | None = None,
):
    return session.prepare_check(
        history_token=session.observe_history(),
        request_key=request_key,
        obligation_class=obligation_class,
        instrument_id=instrument_id,
        certificate_ref=certificate_ref,
        certificate_class=certificate_class,
        claim=claim or _claim(),
    )


def _replace_canonical_head_check(
    session: ConfidenceLedgerSession,
    forged_check: ConfidenceLedgerCheck,
) -> None:
    """Rehash a forged latest event and install it as the canonical mutable head."""

    receipt = session.receipt()
    previous = receipt.events[-1]
    stored = ledger_module._StoredLedgerEvent(
        schema_version=previous.schema_version,
        event_type=previous.event_type,
        scope_id=previous.scope_id,
        ledger_root_id=previous.ledger_root_id,
        revision=previous.revision,
        parent_event_id=previous.parent_event_id,
        parent_event_ref=previous.parent_event_ref,
        event_id=previous.event_id,
        check=forged_check,
    )
    event_id = ledger_module._recompute_event_id(stored)
    updates: dict[str, object] = {"event_id": event_id}
    if previous.event_type == "prepared":
        updates["prepared_event_id"] = event_id
    revised = forged_check.model_copy(update=updates)
    revised = revised.model_copy(update={"check_id": ledger_module._recompute_check_id(revised)})
    stored = stored.model_copy(update={"event_id": event_id, "check": revised})
    ref = session._put_json(
        stored.model_dump(mode="json"),
        kind="runtime.quality.confidence_ledger.event",
        schema=ledger_module._EVENT_SCHEMA,
    )
    head = ledger_module._LedgerHead(
        schema_version=receipt.schema_version,
        scope_id=receipt.scope_id,
        scope_anchor_ref=receipt.scope_anchor_ref,
        authority_provenance=receipt.authority_provenance,
        ledger_root_id=receipt.ledger_root_id,
        ledger_root_ref=receipt.ledger_root_ref,
        head_event_id=event_id,
        head_event_ref=str(ref.artifact_id),
        revision=previous.revision,
    )
    atomic_write_json(session._head_path, head.model_dump(mode="json"))


def _wait_for_children(pids: tuple[int, ...], *, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    pending = set(pids)
    while pending and time.monotonic() < deadline:
        for pid in tuple(pending):
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited == 0:
                continue
            pending.remove(pid)
            assert os.waitstatus_to_exitcode(status) == 0
        if pending:
            time.sleep(0.01)
    if pending:
        for pid in pending:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        pytest.fail(f"child processes did not finish: {sorted(pending)}")


def test_started_probabilistic_check_burns_before_outcome_and_survives_restart(
    sessions: _SessionFactory,
) -> None:
    first = sessions()
    prepared = _prepare(first)
    started = first.start_check(prepared)

    restarted = sessions()
    receipt = restarted.receipt()

    assert started.execution_ordinal == 0
    assert started.spend.fraction > 0
    assert receipt.total_spend == started.spend
    assert receipt.checks[0].execution_status == "started"
    assert receipt.head_event_id == started.event_id
    assert receipt.scope_id == _scope().scope_id


def test_orphan_started_event_fast_forwards_head_and_preserves_burn(
    sessions: _SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = sessions()
    prepared = _prepare(session)
    real_atomic_write_json = ledger_module.atomic_write_json

    def fail_started_head_write(path: Path, payload: object) -> None:
        if Path(path) == session._head_path:
            raise OSError("injected head write failure after CAS append")
        real_atomic_write_json(path, payload)

    monkeypatch.setattr(ledger_module, "atomic_write_json", fail_started_head_write)
    with pytest.raises(OSError, match="injected head write failure"):
        session.start_check(prepared)
    monkeypatch.setattr(ledger_module, "atomic_write_json", real_atomic_write_json)

    restarted = sessions()
    receipt = restarted.receipt()

    assert len(receipt.events) == 2
    assert receipt.events[-1].event_type == "started"
    assert receipt.checks[0].outcome == "started"
    assert receipt.total_spend.fraction > 0
    assert receipt.head_event_id == receipt.events[-1].event_id


def test_retry_adopts_exact_lock_created_before_started_event_crash(
    sessions: _SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = sessions()
    prepared = _prepare(session)
    real_append = ConfidenceLedgerSession._append_event_locked
    injected = False

    def fail_after_lock_creation(
        current: ConfidenceLedgerSession,
        *,
        head: object,
        root: object,
        event_type: str,
        check: ConfidenceLedgerCheck,
    ) -> object:
        nonlocal injected
        if current is session and event_type == "started" and not injected:
            injected = True
            raise OSError("injected crash after invocation lock creation")
        return real_append(
            current,
            head=head,
            root=root,
            event_type=event_type,
            check=check,
        )

    monkeypatch.setattr(
        ConfidenceLedgerSession,
        "_append_event_locked",
        fail_after_lock_creation,
    )
    with pytest.raises(OSError, match="after invocation lock creation"):
        session.start_check(prepared)
    monkeypatch.setattr(
        ConfidenceLedgerSession,
        "_append_event_locked",
        real_append,
    )

    started = sessions().start_check(prepared)

    assert started.outcome == "started"
    assert started.owner_invocation_lock_identity is not None
    assert started.spend.fraction > 0


def test_multi_transition_session_performs_only_one_full_cas_reconciliation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _SessionFactory(tmp_path)
    calls = 0
    real_iter = factory.store.iter_artifact_ids

    def counted_iter() -> list[ArtifactID]:
        nonlocal calls
        calls += 1
        return real_iter()

    monkeypatch.setattr(factory.store, "iter_artifact_ids", counted_iter)
    session = factory()
    for index in range(3):
        session.execute_check(
            _prepare(
                session,
                request_key=f"request://unit/bounded-scan/{index}",
                certificate_ref=(f"construction://constant-unit-e-process/bounded-scan/{index}"),
            )
        )

    assert calls <= 1


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork semantics")
def test_open_session_recovers_writer_killed_after_event_cas_before_journal_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _SessionFactory(tmp_path)
    writer = factory()
    prepared = _prepare(writer)
    already_open = factory()
    ready_read, ready_write = os.pipe()
    release_read, release_write = os.pipe()
    real_commit = ConfidenceLedgerSession._append_scope_journal_commit

    def stop_before_started_commit(
        current: ConfidenceLedgerSession,
        *,
        artifact_kind: str,
        artifact_ref: str,
    ) -> None:
        if artifact_kind == "event" and current is writer:
            os.write(ready_write, b"1")
            readable, _, _ = select.select([release_read], [], [], 5.0)
            if not readable:
                raise RuntimeError("test journal release timed out")
            os.read(release_read, 1)
        real_commit(
            current,
            artifact_kind=artifact_kind,
            artifact_ref=artifact_ref,
        )

    monkeypatch.setattr(
        ConfidenceLedgerSession,
        "_append_scope_journal_commit",
        stop_before_started_commit,
    )
    pid = os.fork()
    if pid == 0:
        os.close(ready_read)
        os.close(release_write)
        try:
            writer.start_check(prepared)
        except BaseException:
            os._exit(2)
        os._exit(0)
    os.close(ready_write)
    os.close(release_read)
    try:
        readable, _, _ = select.select([ready_read], [], [], 5.0)
        assert readable, "writer did not reach the post-CAS journal boundary"
        assert os.read(ready_read, 1) == b"1"
        os.kill(pid, 9)
        os.waitpid(pid, 0)

        recovered = already_open.receipt()
    finally:
        os.close(release_write)
        os.close(ready_read)

    assert recovered.checks[0].outcome == "started"
    assert recovered.total_spend.fraction > 0
    assert len(recovered.events) == 2


def test_valid_older_head_is_fast_forwarded_to_unique_maximal_lineage(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    older_head = json.loads(session._head_path.read_text(encoding="utf-8"))
    session.execute_check(
        _prepare(
            session,
            request_key="request://unit/after-rollback",
            certificate_ref="construction://constant-unit-e-process/after-rollback",
        )
    )
    maximal = session.receipt()
    atomic_write_json(session._head_path, older_head)

    restarted = sessions()
    recovered = restarted.receipt()

    assert recovered == maximal
    persisted_head = json.loads(session._head_path.read_text(encoding="utf-8"))
    assert persisted_head["head_event_id"] == maximal.head_event_id
    assert persisted_head["revision"] == len(maximal.events)


def test_persisted_receipt_witness_prevents_deleted_events_from_resetting_spend(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    witnessed = session.receipt()
    session.persist_receipt(witnessed)
    assert witnessed.total_spend.fraction > 0
    for event in witnessed.events:
        blob, manifest = session._artifact_store.get_paths(
            ArtifactID.model_validate(event.event_ref)
        )
        blob.unlink()
        manifest.unlink()
    session._head_path.unlink()

    with pytest.raises(ConfidenceLedgerError, match="ledger_receipt_witness_invalid"):
        sessions()


def test_valid_older_persisted_receipt_remains_a_prefix_of_longer_lineage(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    older = session.receipt()
    session.persist_receipt(older)
    session.execute_check(
        _prepare(
            session,
            request_key="request://unit/after-persisted-prefix",
            certificate_ref="construction://constant-unit-e-process/after-prefix",
        )
    )
    maximal = session.receipt()

    assert sessions().receipt() == maximal
    assert tuple(maximal.events[: len(older.events)]) == older.events


@pytest.mark.parametrize("invalid_manifest_field", ["producer", "schema"])
def test_invalid_same_scope_receipt_manifest_fails_closed(
    sessions: _SessionFactory,
    invalid_manifest_field: str,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    receipt = session.receipt()
    producer = ledger_module._LEDGER_PRODUCER
    schema = ledger_module._RECEIPT_SCHEMA
    if invalid_manifest_field == "producer":
        producer = ledger_module.artifacts.ProducerInfo(
            component="forged.confidence.ledger", version="1.0.0"
        )
    else:
        schema = ledger_module.artifacts.SchemaInfo(
            name="forged.confidence-ledger-receipt", version="1.0.0"
        )
    session._artifact_store.put_json(
        receipt.model_dump(mode="json"),
        ledger_module.artifacts.PutOptions(
            kind="runtime.quality.confidence_ledger.receipt",
            media_type="application/json",
            schema=schema,
            producer=producer,
        ),
        canon_spec=ledger_module._CAS_CANON_SPEC,
    )

    with pytest.raises(ConfidenceLedgerError, match="ledger_receipt_witness_invalid"):
        sessions()


def test_authority_opener_exposes_no_caller_selectable_storage_or_registry() -> None:
    parameters = inspect.signature(ConfidenceLedgerSession.from_repo).parameters

    assert "artifact_store" not in parameters
    assert "state_root" not in parameters
    assert "registry_source" not in parameters
    assert "certificate_resolver" not in parameters
    assert "certificate_verifier" not in parameters
    assert "authority_session" not in inspect.signature(ConfidenceLedgerSession).parameters


def test_registry_only_temporary_root_cannot_mint_canonical_authority(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "registry-only-repo"
    _install_canonical_registry(repo_root)

    with pytest.raises(ConfidenceLedgerError, match="canonical_deployment_identity_invalid"):
        ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())

    verification = ConfidenceLedgerSession._for_verification(
        REPO_ROOT,
        risk_scope=_scope(owner_scope_key="design-problem:verification-still-available"),
        artifact_store=FileSystemCAS(tmp_path / "verification-cas"),
        state_root=tmp_path / "verification-state",
    )
    assert verification.is_authority_session is False


def test_canonical_authority_reopen_continues_one_budget_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    first = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    initial = first.execute_check(_prepare(first))

    reopened = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    second = reopened.execute_check(
        _prepare(
            reopened,
            request_key="request://unit/canonical-reopen-2",
            certificate_ref="construction://constant-unit-e-process/reopen-2",
        )
    )

    assert first.is_authority_session is True
    assert (initial.execution_ordinal, second.execution_ordinal) == (0, 1)


def test_deleted_canonical_head_is_rebuilt_from_the_maximal_event_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    session.execute_check(_prepare(session))
    expected = session.receipt()
    session._head_path.unlink()

    reopened = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())

    assert reopened.receipt() == expected
    assert reopened._head_path.exists()


def test_canonical_session_fails_closed_when_loaded_deployment_bytes_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    source = repo_root / "src/polisyos/runtime/quality/confidence_ledger.py"
    source.write_bytes(source.read_bytes() + b"\n# deployment drift\n")

    with pytest.raises(ConfidenceLedgerError, match="canonical_deployment_identity_invalid"):
        session.observe_history()


def test_deployment_identity_covers_every_python_module_addition_and_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    original = ledger_module._policy_engine_deployment_identity(repo_root)
    kernel = repo_root / "src/polisyos/core/canon/canon_json.py"
    kernel_bytes = kernel.read_bytes()
    kernel.write_bytes(kernel_bytes + b"\n# imported kernel drift\n")
    assert ledger_module._policy_engine_deployment_identity(repo_root) != original
    kernel.write_bytes(kernel_bytes)
    added = repo_root / "src/polisyos/new_authority_kernel.py"
    added.write_text("AUTHORITY = 'candidate'\n", encoding="utf-8")
    with_addition = ledger_module._policy_engine_deployment_identity(repo_root)
    assert with_addition != original
    added.unlink()
    assert ledger_module._policy_engine_deployment_identity(repo_root) == original


def test_deployment_identity_binds_uv_lock_and_python_runtime_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    original = ledger_module._policy_engine_deployment_identity(repo_root)
    uv_lock = repo_root / "uv.lock"
    uv_lock_bytes = uv_lock.read_bytes()
    uv_lock.write_bytes(uv_lock_bytes + b"\n# dependency drift\n")
    assert ledger_module._policy_engine_deployment_identity(repo_root) != original
    uv_lock.write_bytes(uv_lock_bytes)
    runtime = ledger_module._python_runtime_manifest()
    monkeypatch.setattr(
        ledger_module,
        "_python_runtime_manifest",
        lambda: {**runtime, "cache_tag": f"{runtime['cache_tag']}-drift"},
    )
    assert ledger_module._policy_engine_deployment_identity(repo_root) != original


def test_canonical_session_is_invalidated_by_direct_kernel_or_module_set_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_root = tmp_path / "kernel-authority-repo"
    _install_loaded_deployment(first_root, monkeypatch)
    first = ConfidenceLedgerSession.from_repo(first_root, risk_scope=_scope())
    kernel = first_root / "src/polisyos/core/canon/canon_json.py"
    kernel.write_bytes(kernel.read_bytes() + b"\n# imported kernel drift\n")
    with pytest.raises(ConfidenceLedgerError, match="canonical_deployment_identity_invalid"):
        first.observe_history()

    second_root = tmp_path / "module-authority-repo"
    _install_loaded_deployment(second_root, monkeypatch)
    second = ConfidenceLedgerSession.from_repo(
        second_root,
        risk_scope=_scope(owner_scope_key="design-problem:module-set-drift"),
    )
    added = second_root / "src/polisyos/new_authority_kernel.py"
    added.write_text("AUTHORITY = 'candidate'\n", encoding="utf-8")
    with pytest.raises(ConfidenceLedgerError, match="canonical_deployment_identity_invalid"):
        second.observe_history()


def test_mid_operation_deployment_drift_poison_is_irreversible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    history = session.observe_history()
    kernel = repo_root / "src/polisyos/core/canon/canon_json.py"
    kernel_bytes = kernel.read_bytes()
    real_load = ConfidenceLedgerSession._load_state_locked
    injected = False

    def load_then_drift(
        current: ConfidenceLedgerSession,
    ) -> tuple[object, object, object]:
        nonlocal injected
        loaded = real_load(current)
        if current is session and not injected:
            kernel.write_bytes(kernel_bytes + b"\n# drift after lock entry\n")
            injected = True
        return loaded

    monkeypatch.setattr(ConfidenceLedgerSession, "_load_state_locked", load_then_drift)
    try:
        with pytest.raises(ConfidenceLedgerError, match="canonical_deployment_identity_invalid"):
            session.prepare_check(
                history_token=history,
                request_key="request://unit/mid-operation-drift",
                obligation_class=PromotionObligationClass.CALIBRATION,
                instrument_id="constant_unit_e_process",
                certificate_ref="construction://constant-unit-e-process/drift",
                claim=_claim(),
            )
    finally:
        kernel.write_bytes(kernel_bytes)

    with pytest.raises(ConfidenceLedgerError, match="deployment_drift_poisoned"):
        ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())


def test_deleted_head_cannot_reset_same_scope_with_changed_owner_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    spent = session.execute_check(_prepare(session))
    session._head_path.unlink()

    with pytest.raises(ConfidenceLedgerError, match="ledger_scope_binding_mismatch"):
        ConfidenceLedgerSession.from_repo(
            repo_root,
            risk_scope=_scope(owner_projection_hash=_HASH_2),
        )

    assert spent.spend.fraction > 0


def test_missing_anchor_and_head_cannot_reset_same_scope_with_changed_root_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    spent = session.execute_check(_prepare(session))
    anchor_ref = ledger_module._cas_json_artifact_ref(session._scope_anchor_payload())
    anchor_blob, anchor_manifest = session._artifact_store.get_paths(
        ArtifactID.model_validate(anchor_ref)
    )
    session._head_path.unlink()
    anchor_blob.unlink()
    anchor_manifest.unlink()

    with pytest.raises(ConfidenceLedgerError, match="ledger_head_reset_detected"):
        ConfidenceLedgerSession.from_repo(
            repo_root,
            risk_scope=_scope(owner_projection_hash=_HASH_2),
        )

    assert spent.spend.fraction > 0


def test_surviving_spend_event_prevents_reset_after_pointer_artifacts_are_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    spent = session.execute_check(_prepare(session))
    receipt = session.receipt()
    anchor_ref = ledger_module._cas_json_artifact_ref(session._scope_anchor_payload())
    for artifact_ref in (anchor_ref, receipt.ledger_root_ref):
        blob, manifest = session._artifact_store.get_paths(ArtifactID.model_validate(artifact_ref))
        blob.unlink()
        manifest.unlink()
    session._head_path.unlink()
    session._scope_tombstone_path.unlink()

    with pytest.raises(ConfidenceLedgerError, match="ledger_head_reset_detected"):
        ConfidenceLedgerSession.from_repo(
            repo_root,
            risk_scope=_scope(owner_projection_hash=_HASH_2),
        )

    assert spent.spend.fraction > 0


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork semantics")
def test_cross_process_negative_scope_membership_is_never_cached(
    tmp_path: Path,
) -> None:
    factory = _SessionFactory(tmp_path)
    factory(scope=_scope(owner_scope_key="design-problem:cache-primer"))
    target_scope = _scope(owner_scope_key="design-problem:cross-process-target")
    pid = os.fork()
    if pid == 0:
        try:
            child_factory = _SessionFactory(tmp_path)
            child = child_factory(scope=target_scope)
            child.execute_check(_prepare(child))
            receipt = child.receipt()
            for artifact_ref in (
                ledger_module._cas_json_artifact_ref(child._scope_anchor_payload()),
                receipt.ledger_root_ref,
            ):
                blob, manifest = child._artifact_store.get_paths(
                    ArtifactID.model_validate(artifact_ref)
                )
                blob.unlink()
                manifest.unlink()
            child._head_path.unlink()
            child._scope_tombstone_path.unlink()
        except BaseException:
            os._exit(2)
        os._exit(0)
    _wait_for_children((pid,))

    with pytest.raises(ConfidenceLedgerError, match="ledger_head_reset_detected"):
        factory(scope=target_scope.model_copy(update={"owner_projection_hash": _HASH_2}))


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork semantics")
def test_unlinked_held_lock_cannot_admit_replacement_writer(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    ready_read, ready_write = os.pipe()
    release_read, release_write = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(ready_read)
        os.close(release_write)
        try:
            with session._exclusive_lock():
                os.write(ready_write, b"1")
                readable, _, _ = select.select([release_read], [], [], 5.0)
                if not readable:
                    os._exit(3)
                os.read(release_read, 1)
        except BaseException:
            os._exit(2)
        os._exit(0)
    os.close(ready_write)
    os.close(release_read)
    try:
        readable, _, _ = select.select([ready_read], [], [], 5.0)
        assert readable, "child did not acquire the original lock"
        assert os.read(ready_read, 1) == b"1"
        session._lock_path.unlink()

        with pytest.raises(ConfidenceLedgerError, match="ledger_lock_identity_invalid"):
            sessions()
    finally:
        os.write(release_write, b"1")
        os.close(release_write)
        os.close(ready_read)
        _wait_for_children((pid,))


def test_verification_session_authority_provenance_is_immutable(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    with pytest.raises(AttributeError, match="session_authority_provenance_immutable"):
        session._is_authority_session = True

    assert session.is_authority_session is False
    assert not hasattr(session, "__dict__")


def test_canonical_session_owner_callbacks_cannot_be_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())

    with pytest.raises(AttributeError, match="session_authority_provenance_immutable"):
        session._certificate_resolver = lambda check: _deterministic_evidence(
            check.claim_execution_binding_hash
        )
    with pytest.raises(AttributeError, match="session_authority_provenance_immutable"):
        session._certificate_verifier = _deterministic_verification

    assert session.is_authority_session is True


def test_confidence_ledger_session_cannot_be_subclassed_for_authority_spoofing() -> None:
    with pytest.raises(TypeError, match="confidence_ledger_session_is_final"):

        class _ForgedAuthoritySession(ConfidenceLedgerSession):
            pass


def test_crash_recovery_never_reexecutes_and_next_start_uses_fresh_ordinal(
    sessions: _SessionFactory,
) -> None:
    first = sessions()
    started = first.start_check(_prepare(first))

    restarted = sessions()
    recovered = restarted.recover_started(started)
    second = restarted.start_check(
        _prepare(
            restarted,
            request_key="request://unit/2",
            certificate_ref="construction://constant-unit-e-process/2",
        )
    )

    assert recovered.outcome == "recovered_crash"
    assert second.execution_ordinal == 1
    assert restarted.receipt().total_spend.fraction == (
        started.spend.fraction + second.spend.fraction
    )


def test_same_process_recovery_cannot_close_a_live_owner_invocation(
    sessions: _SessionFactory,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    results: list[ConfidenceLedgerCheck | BaseException] = []

    def resolver(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        entered.set()
        if not release.wait(5.0):
            raise RuntimeError("test resolver release timed out")
        return _deterministic_evidence(check.claim_execution_binding_hash)

    claimant = sessions(resolver=resolver, verifier=_deterministic_verification)
    started = claimant.start_check(
        _prepare(
            claimant,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )

    def execute() -> None:
        try:
            results.append(claimant.execute_check(started))
        except BaseException as exc:  # pragma: no cover - asserted below.
            results.append(exc)

    worker = threading.Thread(target=execute, daemon=True)
    worker.start()
    assert entered.wait(5.0), "owner resolver did not start"
    try:
        with pytest.raises(ConfidenceLedgerError, match="owner_invocation_still_live"):
            sessions(
                resolver=resolver,
                verifier=_deterministic_verification,
            ).recover_started(started)
    finally:
        release.set()
        worker.join(5.0)
    assert not worker.is_alive()
    assert len(results) == 1
    assert isinstance(results[0], ConfidenceLedgerCheck)
    assert results[0].outcome == "supported"


def test_recursive_same_thread_recovery_observes_live_invocation(
    sessions: _SessionFactory,
) -> None:
    recovery_codes: list[str] = []
    session: ConfidenceLedgerSession

    def resolver(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        try:
            session.recover_started(check)
        except ConfidenceLedgerError as exc:
            recovery_codes.append(exc.code)
        return _deterministic_evidence(check.claim_execution_binding_hash)

    session = sessions(resolver=resolver, verifier=_deterministic_verification)
    completed = session.execute_check(
        _prepare(
            session,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )

    assert recovery_codes == ["owner_invocation_still_live"]
    assert completed.outcome == "supported"


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork semantics")
def test_cross_process_recovery_cannot_close_a_live_owner_invocation(
    tmp_path: Path,
) -> None:
    ready_read, ready_write = os.pipe()
    release_read, release_write = os.pipe()

    def resolver(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        os.write(ready_write, b"1")
        readable, _, _ = select.select([release_read], [], [], 5.0)
        if not readable:
            raise RuntimeError("test resolver release timed out")
        os.read(release_read, 1)
        return _deterministic_evidence(check.claim_execution_binding_hash)

    factory = _SessionFactory(tmp_path)
    claimant = factory(resolver=resolver, verifier=_deterministic_verification)
    started = claimant.start_check(
        _prepare(
            claimant,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )
    pid = os.fork()
    if pid == 0:
        os.close(ready_read)
        os.close(release_write)
        try:
            claimant.execute_check(started)
        except BaseException:
            os._exit(2)
        os._exit(0)
    os.close(ready_write)
    os.close(release_read)
    try:
        readable, _, _ = select.select([ready_read], [], [], 5.0)
        assert readable, "owner resolver did not start"
        assert os.read(ready_read, 1) == b"1"
        with pytest.raises(ConfidenceLedgerError, match="owner_invocation_still_live"):
            factory(
                resolver=resolver,
                verifier=_deterministic_verification,
            ).recover_started(started)
    finally:
        os.write(release_write, b"1")
        os.close(release_write)
        os.close(ready_read)
        _wait_for_children((pid,))

    assert factory().receipt().checks[0].outcome == "supported"


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork semantics")
def test_replaced_lock_for_crash_open_claim_fails_closed(tmp_path: Path) -> None:
    ready_read, ready_write = os.pipe()
    release_read, release_write = os.pipe()

    def resolver(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        os.write(ready_write, b"1")
        readable, _, _ = select.select([release_read], [], [], 5.0)
        if not readable:
            raise RuntimeError("test resolver release timed out")
        os.read(release_read, 1)
        return _deterministic_evidence(check.claim_execution_binding_hash)

    factory = _SessionFactory(tmp_path)
    claimant = factory(resolver=resolver, verifier=_deterministic_verification)
    started = claimant.start_check(
        _prepare(
            claimant,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )
    pid = os.fork()
    if pid == 0:
        os.close(ready_read)
        os.close(release_write)
        try:
            claimant.execute_check(started)
        except BaseException:
            os._exit(2)
        os._exit(0)
    os.close(ready_write)
    os.close(release_read)
    readable, _, _ = select.select([ready_read], [], [], 5.0)
    assert readable, "owner resolver did not start"
    assert os.read(ready_read, 1) == b"1"
    os.kill(pid, 9)
    os.waitpid(pid, 0)
    os.close(release_write)
    os.close(ready_read)
    execution_hex = started.execution_id.rsplit(":", 1)[-1]
    lock_path = factory.state_root / "owner_invocations" / f"{execution_hex}.lock"
    assert lock_path.exists()
    lock_path.unlink()
    lock_path.touch(mode=0o600)

    with pytest.raises(ConfidenceLedgerError, match="owner_invocation_lock_invalid"):
        factory(
            resolver=resolver,
            verifier=_deterministic_verification,
        ).recover_started(started)


def test_started_check_retry_cannot_invoke_owner_twice(
    sessions: _SessionFactory,
) -> None:
    calls = {"resolver": 0}

    def resolver(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        calls["resolver"] += 1
        return _deterministic_evidence(check.claim_execution_binding_hash)

    session = sessions(resolver=resolver, verifier=_deterministic_verification)
    started = session.start_check(
        _prepare(
            session,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )

    session.execute_check(started)
    completed = session.execute_check(started)

    assert completed.outcome == "supported"
    assert calls["resolver"] == 1


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork semantics")
def test_fork_contenders_share_one_durable_owner_invocation_claim(
    tmp_path: Path,
) -> None:
    calls_path = tmp_path / "owner-calls.log"

    def resolver(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        fd = os.open(calls_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, b"called\n")
        finally:
            os.close(fd)
        time.sleep(0.2)
        return _deterministic_evidence(check.claim_execution_binding_hash)

    factory = _SessionFactory(tmp_path / "fork-ledger")
    session = factory(resolver=resolver, verifier=_deterministic_verification)
    started = session.start_check(
        _prepare(
            session,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )
    gate_read, gate_write = os.pipe()
    pids: list[int] = []
    for _ in range(2):
        pid = os.fork()
        if pid == 0:
            os.close(gate_write)
            try:
                readable, _, _ = select.select([gate_read], [], [], 5.0)
                if not readable:
                    os._exit(3)
                os.read(gate_read, 1)
                try:
                    session.execute_check(started)
                except ConfidenceLedgerError as exc:
                    if exc.code != "duplicate_execution_conflict":
                        os._exit(4)
            except BaseException:
                os._exit(2)
            os._exit(0)
        pids.append(pid)
    os.close(gate_read)
    os.write(gate_write, b"12")
    os.close(gate_write)
    _wait_for_children(tuple(pids))

    assert calls_path.read_text(encoding="utf-8").splitlines() == ["called"]
    assert (
        factory(resolver=resolver, verifier=_deterministic_verification).receipt().checks[0].outcome
        == "supported"
    )


def test_restarted_session_cannot_execute_a_durable_started_check(
    sessions: _SessionFactory,
) -> None:
    calls = {"resolver": 0}

    def resolver(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        calls["resolver"] += 1
        return _deterministic_evidence(check.claim_execution_binding_hash)

    first = sessions(resolver=resolver, verifier=_deterministic_verification)
    started = first.start_check(
        _prepare(
            first,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )
    restarted = sessions(resolver=resolver, verifier=_deterministic_verification)

    with pytest.raises(ConfidenceLedgerError, match="duplicate_execution_conflict"):
        restarted.execute_check(started)

    assert calls["resolver"] == 0


def test_cancelled_prepared_attempt_has_no_ordinal_and_spends_zero(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    prepared = _prepare(session)

    completed = session.cancel_prepared(prepared, detail="user stopped before execution")
    receipt = session.receipt()

    assert completed.started_event_id is None
    assert receipt.checks[0].execution_ordinal is None
    assert receipt.checks[0].spend.fraction == 0
    assert receipt.total_spend.fraction == 0


def test_nonrejecting_constant_unit_e_process_burns_but_cannot_promote(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    completed = session.execute_check(_prepare(session))
    check = session.receipt().checks[0]

    assert completed.outcome == "not_supported"
    assert check.spend.fraction > 0
    assert check.anytime_valid is True
    assert check.supports_obligation is False
    assert check.eligible_for_promotion is False


@pytest.mark.parametrize("outcome", ["owner_refused", "owner_error"])
def test_started_owner_refusal_or_error_does_not_refund_slot(
    sessions: _SessionFactory,
    outcome: str,
) -> None:
    session = sessions()
    started = session.start_check(_prepare(session))

    session.record_owner_failure(
        started,
        outcome=outcome,
        code="owner_failed_after_start",
        detail="measured failure",
    )

    check = session.receipt().checks[0]
    assert check.spend == started.spend
    assert check.outcome == outcome
    assert check.eligible_for_promotion is False


def test_unknown_instrument_preflight_fails_closed_without_start_or_spend(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    with pytest.raises(ConfidenceLedgerError, match="unknown_instrument") as exc_info:
        _prepare(session, instrument_id="absent_instrument")

    receipt = session.receipt()
    assert exc_info.value.code == "unknown_instrument"
    assert receipt.total_spend.fraction == 0
    assert receipt.checks[0].execution_ordinal is None
    assert receipt.checks[0].outcome == "preflight_refusal"


@pytest.mark.parametrize(
    ("instrument_id", "code"),
    [
        ("bayesian_credible_interval", "coverage_argument_missing"),
        ("fixed_time_confidence_interval", "non_anytime_valid"),
        ("owner_verified_confidence_sequence", "owner_theorem_unavailable"),
        ("causal_sensitivity_e_value", "non_anytime_valid"),
    ],
)
def test_ineligible_instrument_is_typed_preflight_refusal_without_spend(
    sessions: _SessionFactory,
    instrument_id: str,
    code: str,
) -> None:
    session = sessions()

    with pytest.raises(ConfidenceLedgerError, match=code):
        _prepare(
            session,
            instrument_id=instrument_id,
            claim=_claim(role="promotion"),
        )

    check = session.receipt().checks[0]
    assert check.outcome == "preflight_refusal"
    assert check.refusal_code == code
    assert check.spend.fraction == 0


def test_bayesian_credible_interval_without_coverage_argument_is_typed_refusal(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        _prepare(
            session,
            instrument_id="bayesian_credible_interval",
            claim=_claim(role="promotion"),
        )

    assert exc_info.value.code == "coverage_argument_missing"
    assert session.receipt().checks[0].refusal_code == "coverage_argument_missing"


def test_non_anytime_valid_instrument_cannot_support_promotion(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        _prepare(
            session,
            instrument_id="fixed_time_confidence_interval",
            claim=_claim(role="promotion"),
        )

    assert exc_info.value.code == "non_anytime_valid"
    assert session.receipt().checks[0].eligible_for_promotion is False


def test_certificate_role_and_error_polarity_are_bound_and_checked(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    with pytest.raises(ValueError, match="certificate_role_polarity_mismatch"):
        _prepare(
            session,
            claim=_claim(
                role="acquisition",
                polarity="false_accept",
            ),
        )

    assert session.receipt().total_spend.fraction == 0


def test_instrument_rejects_certificate_role_not_registered_for_it(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    with pytest.raises(ConfidenceLedgerError, match="certificate_role_not_permitted"):
        _prepare(
            session,
            claim=_claim(
                role="admission",
                polarity="confident_wrong_admission",
            ),
        )


def test_stale_history_token_cannot_fork_canonical_head(
    sessions: _SessionFactory,
) -> None:
    first = sessions()
    second = sessions()
    stale = second.observe_history()
    first.execute_check(_prepare(first))

    with pytest.raises(ConfidenceLedgerError, match="ledger_head_conflict"):
        second.prepare_check(
            history_token=stale,
            request_key="request://stale/fork",
            obligation_class=PromotionObligationClass.CALIBRATION,
            instrument_id="constant_unit_e_process",
            certificate_ref="construction://constant-unit-e-process/stale",
            claim=_claim(),
        )


def test_prepared_check_cannot_start_after_canonical_head_advances(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    stale_prepared = _prepare(
        session,
        request_key="request://unit/prepared-before-intervening-outcome",
        certificate_ref="construction://constant-unit-e-process/stale-prepared",
    )
    session.execute_check(
        _prepare(
            session,
            request_key="request://unit/intervening-outcome",
            certificate_ref="construction://constant-unit-e-process/intervening",
        )
    )

    with pytest.raises(ConfidenceLedgerError, match="ledger_head_conflict"):
        session.start_check(stale_prepared)


def test_same_scope_cannot_mint_fresh_root_with_changed_owner_projection(
    sessions: _SessionFactory,
) -> None:
    original = sessions()
    original.execute_check(_prepare(original))

    with pytest.raises(ConfidenceLedgerError, match="ledger_scope_binding_mismatch"):
        sessions(scope=_scope(owner_projection_hash=_HASH_2))


def test_same_scope_cannot_reset_budget_by_selecting_another_registry(
    sessions: _SessionFactory,
) -> None:
    original = sessions()
    original.execute_check(_prepare(original))
    registry = load_confidence_ledger_registry(
        REPO_ROOT / "architecture/production_quality/confidence_ledger.toml"
    )
    payload = registry.source_payload()
    payload["policy"]["default_schedule_profile_id"] = "half_mass_basel_square"

    with pytest.raises(ConfidenceLedgerError, match="ledger_scope_binding_mismatch"):
        sessions(registry_source=payload)


def test_rehashed_forged_instrument_registry_fails_content_binding(
    sessions: _SessionFactory,
) -> None:
    original = sessions()
    original.execute_check(_prepare(original))
    registry = load_confidence_ledger_registry(
        REPO_ROOT / "architecture/production_quality/confidence_ledger.toml"
    )
    forged = registry.source_payload()
    forged["instruments"][0]["instrument_family"] = "rehashed_forged_family"

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        sessions(registry_source=forged)

    assert exc_info.value.code in {
        "ledger_scope_binding_mismatch",
        "registry_binding_invalid",
    }


def test_registry_content_hash_is_recomputed_not_trusted(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    check = session.execute_check(_prepare(session))

    assert check.registry_content_hash == session.registry.content_hash


def test_rehashed_canonical_event_cannot_relabel_registered_instrument_definition(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    completed = session.receipt().checks[0]
    forged = completed.model_copy(
        update={
            "instrument_family": "confidence_sequence",
            "proof_profile_id": "owner_theorem_unavailable",
            "instrument_definition_hash": _HASH_2,
            "proof_profile_hash": _HASH_2,
            "anytime_valid": False,
        }
    )
    _replace_canonical_head_check(session, forged)

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        sessions()

    assert exc_info.value.code == "ledger_event_fork_detected"


def test_rehashed_canonical_event_cannot_forge_prior_head_filtration(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    prepared = _prepare(session)
    forged = prepared.model_copy(
        update={
            "filtration_ref": "confidence-ledger://forged/revision/999",
            "precheck_history_hash": _HASH_2,
            "claim_execution_binding_hash": ledger_module._content_hash(
                {
                    "request_fingerprint": prepared.request_fingerprint,
                    "history": _HASH_2,
                    "execution": None,
                    "spend": RationalSpec(numerator=0, denominator=1),
                }
            ),
        }
    )
    _replace_canonical_head_check(session, forged)

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        sessions()

    assert exc_info.value.code == "ledger_event_fork_detected"


def test_pure_structural_validator_recomputes_registry_schedule_and_chain(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    receipt = session.receipt()

    validated = ledger_module.validate_confidence_ledger_receipt_structure(
        receipt,
        registry=session.registry,
    )

    assert validated == receipt
    assert (
        ledger_module.recompute_confidence_schedule_projection_hash(
            session.registry,
            schedule_profile_id=receipt.schedule_profile_id,
        )
        == receipt.schedule_projection_hash
    )


def test_completed_idempotent_request_is_returned_without_new_execution(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    first_prepared = _prepare(session)
    first = session.execute_check(first_prepared)
    current = session.observe_history()

    repeated_prepared = session.prepare_check(
        history_token=current,
        request_key="request://unit/1",
        obligation_class=PromotionObligationClass.CALIBRATION,
        instrument_id="constant_unit_e_process",
        certificate_ref="construction://constant-unit-e-process/1",
        claim=_claim(),
    )
    repeated = session.execute_check(repeated_prepared)

    assert repeated == first
    started = [event for event in session.receipt().events if event.event_type == "started"]
    assert len(started) == 2
    assert sum(event.check.owner_invocation_claim_id is not None for event in started) == 1


def test_reused_request_key_with_different_binding_is_corruption(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))

    with pytest.raises(ConfidenceLedgerError, match="idempotency_binding_mismatch"):
        _prepare(
            session,
            request_key="request://unit/1",
            claim=_claim(claim_ref="claim://unit/different"),
        )


def test_retry_after_observed_output_gets_fresh_ordinal_and_burn(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    first = session.start_check(_prepare(session))
    session.record_owner_failure(
        first,
        outcome="owner_error",
        code="first_attempt_failed",
        detail="observed owner error",
    )
    second = session.start_check(
        _prepare(
            session,
            request_key="request://unit/retry-2",
            certificate_ref="construction://constant-unit-e-process/retry-2",
        )
    )

    assert (first.execution_ordinal, second.execution_ordinal) == (0, 1)
    assert session.receipt().total_spend.fraction == (first.spend.fraction + second.spend.fraction)


def test_schedule_recomputation_follows_execution_order_not_request_sort_order(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    first = session.execute_check(
        _prepare(
            session,
            request_key="request://unit/z-first",
            certificate_ref="construction://constant-unit-e-process/z-first",
        )
    )
    second = session.execute_check(
        _prepare(
            session,
            request_key="request://unit/a-second",
            certificate_ref="construction://constant-unit-e-process/a-second",
        )
    )

    receipt = session.receipt()
    validated = validate_confidence_ledger_receipt(receipt, session=session)

    assert tuple(check.request_key for check in receipt.checks) == (
        "request://unit/a-second",
        "request://unit/z-first",
    )
    assert (first.schedule_query_index, second.schedule_query_index) == (0, 1)
    assert validated == receipt


def test_schedule_query_index_is_the_global_executed_check_ordinal(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    first = session.execute_check(
        _prepare(
            session,
            request_key="request://unit/calibration-first",
            obligation_class=PromotionObligationClass.CALIBRATION,
            certificate_ref="construction://constant-unit-e-process/calibration",
        )
    )
    second = session.execute_check(
        _prepare(
            session,
            request_key="request://unit/data-second",
            obligation_class=PromotionObligationClass.DATA,
            certificate_ref="construction://constant-unit-e-process/data",
        )
    )

    assert (first.execution_ordinal, second.execution_ordinal) == (0, 1)
    assert (first.schedule_query_index, second.schedule_query_index) == (0, 1)


def _deterministic_evidence(
    binding_hash: str,
    *,
    certificate_class: str | None = "owner_data_gap",
    obligation_class: PromotionObligationClass = PromotionObligationClass.DATA,
    certificate_role: str = "refusal",
    claim_polarity: str = "confident_wrong_refusal",
    owner_ref: str = (
        "tools.quality.validation.layer3_gy_n13a_acquisition_census.extract_route_projection"
    ),
) -> OwnerCertificateEvidence:
    return OwnerCertificateEvidence(
        certificate_ref="certificate://deterministic/1",
        instrument_id="deterministic_owner_proof",
        obligation_class=obligation_class,
        certificate_role=certificate_role,
        claim_polarity=claim_polarity,
        owner_ref=owner_ref,
        owner_projection={"evidence_kind": "owner_data_gap", "status": "verified"},
        certificate_class=certificate_class,
        claim_execution_binding_hash=binding_hash,
    )


def _deterministic_verification(
    evidence: OwnerCertificateEvidence,
) -> OwnerCertificateVerification:
    assert evidence.owner_projection["status"] == "verified"
    return OwnerCertificateVerification(
        verifier_ref=(
            "tools.quality.validation."
            "check_layer3_gy_depth_n_universality_contract.validate_payload"
        ),
        verifier_projection={"owner_projection_recomputed": True},
        certificate_evidence_hash=gy_content_hash(evidence.model_dump(mode="json")),
        claim_execution_binding_hash=evidence.claim_execution_binding_hash,
        supports_obligation=True,
    )


def test_deterministic_proof_executes_at_unique_ordinal_with_zero_spend_and_reverification(
    sessions: _SessionFactory,
) -> None:
    calls = {"resolver": 0, "verifier": 0}

    def resolver(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        calls["resolver"] += 1
        assert check.certificate_ref == "certificate://deterministic/1"
        return _deterministic_evidence(check.claim_execution_binding_hash)

    def verifier(value: OwnerCertificateEvidence) -> OwnerCertificateVerification:
        calls["verifier"] += 1
        return _deterministic_verification(value)

    session = sessions(resolver=resolver, verifier=verifier)
    prepared = _prepare(
        session,
        obligation_class=PromotionObligationClass.DATA,
        instrument_id="deterministic_owner_proof",
        certificate_ref="certificate://deterministic/1",
        certificate_class="owner_data_gap",
        claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
    )
    completed = session.execute_check(prepared)
    before_validate = dict(calls)
    receipt = session.receipt()
    validated = validate_confidence_ledger_receipt(receipt, session=session)

    assert completed.outcome == "supported"
    assert validated.checks[0].execution_ordinal == 0
    assert validated.checks[0].spend.fraction == 0
    assert validated.checks[0].supports_obligation is True
    assert validated.checks[0].eligible_for_promotion is False
    assert calls["resolver"] > before_validate["resolver"]
    assert calls["verifier"] > before_validate["verifier"]


def test_deterministic_evidence_without_independent_verifier_fails_closed(
    sessions: _SessionFactory,
) -> None:
    session = sessions(
        resolver=lambda check: _deterministic_evidence(check.claim_execution_binding_hash),
        verifier=None,
    )
    prepared = _prepare(
        session,
        obligation_class=PromotionObligationClass.DATA,
        instrument_id="deterministic_owner_proof",
        certificate_ref="certificate://deterministic/1",
        certificate_class="owner_data_gap",
        claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
    )

    completed = session.execute_check(prepared)

    assert completed.outcome == "refused"
    assert completed.refusal_code == "owner_reverification_failed"
    assert session.receipt().checks[0].eligible_for_promotion is False


def test_deterministic_proof_without_registered_certificate_class_fails_closed(
    sessions: _SessionFactory,
) -> None:
    calls = {"resolver": 0}

    def resolver(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        calls["resolver"] += 1
        return _deterministic_evidence(check.claim_execution_binding_hash)

    session = sessions(resolver=resolver, verifier=_deterministic_verification)

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        _prepare(
            session,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )

    assert exc_info.value.code == "certificate_class_route_missing"
    assert session.receipt().total_spend.fraction == 0
    assert calls["resolver"] == 0


@pytest.mark.parametrize(
    ("certificate_class", "obligation_class", "certificate_role", "claim_polarity"),
    [
        (
            "estimand_binding_refusal",
            PromotionObligationClass.DATA,
            "refusal",
            "confident_wrong_refusal",
        ),
        (
            "owner_acquisition_route",
            PromotionObligationClass.DATA,
            "refusal",
            "confident_wrong_refusal",
        ),
        (
            "admission_passport",
            PromotionObligationClass.DATA,
            "refusal",
            "confident_wrong_refusal",
        ),
    ],
)
def test_certificate_class_route_binds_obligation_role_and_polarity(
    sessions: _SessionFactory,
    certificate_class: str,
    obligation_class: PromotionObligationClass,
    certificate_role: str,
    claim_polarity: str,
) -> None:
    session = sessions()

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        _prepare(
            session,
            obligation_class=obligation_class,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class=certificate_class,
            claim=_claim(role=certificate_role, polarity=claim_polarity),
        )

    assert exc_info.value.code == "certificate_class_route_mismatch"


def test_registered_owner_and_verifier_provenance_cannot_be_self_attested(
    sessions: _SessionFactory,
) -> None:
    def forged_verifier(
        evidence: OwnerCertificateEvidence,
    ) -> OwnerCertificateVerification:
        return OwnerCertificateVerification(
            verifier_ref="forged://verifier/distinct-string",
            verifier_projection={"forged_support": True},
            certificate_evidence_hash=gy_content_hash(evidence.model_dump(mode="json")),
            claim_execution_binding_hash=evidence.claim_execution_binding_hash,
            supports_obligation=True,
        )

    session = sessions(
        resolver=lambda check: _deterministic_evidence(
            check.claim_execution_binding_hash,
            owner_ref="forged://owner/distinct-string",
        ),
        verifier=forged_verifier,
    )

    completed = session.execute_check(
        _prepare(
            session,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )

    assert completed.outcome == "refused"
    assert completed.refusal_code == "owner_verifier_provenance_mismatch"


def test_deterministic_owner_and_verifier_must_be_distinct(
    sessions: _SessionFactory,
) -> None:
    def verifier(value: OwnerCertificateEvidence) -> OwnerCertificateVerification:
        return OwnerCertificateVerification(
            verifier_ref=value.owner_ref,
            verifier_projection={"owner_projection_recomputed": True},
            certificate_evidence_hash=gy_content_hash(value.model_dump(mode="json")),
            claim_execution_binding_hash=value.claim_execution_binding_hash,
            supports_obligation=True,
        )

    session = sessions(
        resolver=lambda check: _deterministic_evidence(check.claim_execution_binding_hash),
        verifier=verifier,
    )
    completed = session.execute_check(
        _prepare(
            session,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )

    assert completed.outcome == "refused"
    assert completed.refusal_code == "owner_and_verifier_must_be_distinct"


def test_owner_certificate_replay_against_different_execution_is_rejected(
    sessions: _SessionFactory,
) -> None:
    session = sessions(
        resolver=lambda _check: _deterministic_evidence(_HASH_2),
        verifier=_deterministic_verification,
    )

    completed = session.execute_check(
        _prepare(
            session,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )

    assert completed.outcome == "refused"
    assert completed.refusal_code == "claim_execution_binding_invalid"


def test_old_valid_prefix_cannot_authorize_after_head_advances(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    old = session.receipt()
    session.execute_check(
        _prepare(
            session,
            request_key="request://unit/2",
            certificate_ref="construction://constant-unit-e-process/2",
        )
    )

    with pytest.raises(ConfidenceLedgerError, match="receipt_not_canonical_head"):
        validate_confidence_ledger_receipt(old, session=session)


def test_over_spend_is_rejected_even_when_receipt_is_rehashed(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    receipt = session.receipt()
    forged = receipt.model_copy(
        update={
            "total_spend": RationalSpec(numerator=1, denominator=1),
            "total_spend_decimal": "1",
            "within_budget": False,
        }
    )

    with pytest.raises(ConfidenceLedgerError, match="over_spend"):
        validate_confidence_ledger_receipt(forged, session=session)


def test_executed_check_without_schedule_slot_fails_closed(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    receipt = session.receipt()
    check = receipt.checks[0].model_copy(update={"schedule_query_index": None})

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        validate_confidence_ledger_receipt(
            receipt.model_copy(update={"checks": (check,)}),
            session=session,
        )

    assert exc_info.value.code == "schedule_slot_missing"


def test_forged_spend_row_is_recomputed_from_schedule(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    receipt = session.receipt()
    forged_spend = RationalSpec(numerator=1, denominator=999)
    check = receipt.checks[0].model_copy(
        update={"spend": forged_spend, "spend_decimal": "0.001001"}
    )
    forged = receipt.model_copy(
        update={
            "checks": (check,),
            "total_spend": forged_spend,
            "total_spend_decimal": "0.001001",
        }
    )

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        validate_confidence_ledger_receipt(forged, session=session)

    assert exc_info.value.code == "forged_spend_row"


def test_spend_recorded_for_unstarted_check_is_rejected(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    prepared = _prepare(session)
    session.cancel_prepared(prepared)
    receipt = session.receipt()
    check = receipt.checks[0].model_copy(
        update={
            "spend": RationalSpec(numerator=1, denominator=10_000),
            "spend_decimal": "0.0001",
        }
    )
    forged = receipt.model_copy(update={"checks": (check,)})

    with pytest.raises(ConfidenceLedgerError, match="spend_for_unexecuted_check"):
        validate_confidence_ledger_receipt(forged, session=session)


def test_deterministic_nonzero_spend_is_rejected(
    sessions: _SessionFactory,
) -> None:
    def resolver(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        return _deterministic_evidence(check.claim_execution_binding_hash)

    session = sessions(
        resolver=resolver,
        verifier=_deterministic_verification,
    )
    session.execute_check(
        _prepare(
            session,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )
    receipt = session.receipt()
    check = receipt.checks[0].model_copy(
        update={
            "spend": RationalSpec(numerator=1, denominator=10_000),
            "spend_decimal": "0.0001",
        }
    )

    with pytest.raises(ConfidenceLedgerError, match="deterministic_proof_nonzero_spend"):
        validate_confidence_ledger_receipt(
            receipt.model_copy(update={"checks": (check,)}),
            session=session,
        )


def test_rehashed_supported_deterministic_row_without_owner_binding_is_rejected(
    sessions: _SessionFactory,
) -> None:
    session = sessions(
        resolver=lambda check: _deterministic_evidence(check.claim_execution_binding_hash),
        verifier=_deterministic_verification,
    )
    session.execute_check(
        _prepare(
            session,
            obligation_class=PromotionObligationClass.DATA,
            instrument_id="deterministic_owner_proof",
            certificate_ref="certificate://deterministic/1",
            certificate_class="owner_data_gap",
            claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
        )
    )
    completed = session.receipt().checks[0]
    _replace_canonical_head_check(
        session,
        completed.model_copy(update={"owner_binding": None}),
    )

    with pytest.raises(ConfidenceLedgerError, match="ledger_event_fork_detected"):
        sessions(
            resolver=lambda check: _deterministic_evidence(check.claim_execution_binding_hash),
            verifier=_deterministic_verification,
        )


def test_duplicate_schedule_slot_is_rejected(sessions: _SessionFactory) -> None:
    session = sessions()
    session.execute_check(
        _prepare(
            session,
            request_key="request://unit/ordinal-0",
            certificate_ref="construction://constant-unit-e-process/ordinal-0",
        )
    )
    session.execute_check(
        _prepare(
            session,
            request_key="request://unit/ordinal-1",
            obligation_class=PromotionObligationClass.DATA,
            certificate_ref="construction://constant-unit-e-process/ordinal-1",
        )
    )
    receipt = session.receipt()
    first, second = receipt.checks
    second = second.model_copy(update={"execution_ordinal": first.execution_ordinal})

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        validate_confidence_ledger_receipt(
            receipt.model_copy(update={"checks": (first, second)}),
            session=session,
        )

    assert exc_info.value.code == "duplicate_schedule_slot"


def test_conditionality_clause_is_required_in_receipt_and_both_projections(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    receipt = session.receipt()
    n9 = project_n9_promotion_certificate(receipt, session=session)
    n12 = project_n12_epoch_reference(receipt, session=session)

    assert receipt.conditionality_clause == CONDITIONAL_VALIDITY_CLAUSE
    assert n9.conditionality_clause == CONDITIONAL_VALIDITY_CLAUSE
    assert n12.conditionality_clause == CONDITIONAL_VALIDITY_CLAUSE
    assert n9.scope_id == receipt.scope_id
    assert n9.head_event_id == receipt.head_event_id
    assert n9.head_event_ref == receipt.head_event_ref
    assert receipt.deployment_identity.startswith("policy-engine-deployment:sha256:")
    assert n9.deployment_identity == receipt.deployment_identity
    assert n12.deployment_identity == receipt.deployment_identity
    with pytest.raises(ConfidenceLedgerError, match="conditionality_clause_missing"):
        validate_confidence_ledger_receipt(
            receipt.model_copy(update={"conditionality_clause": "unconditional"}),
            session=session,
        )


def test_n9_projection_excludes_conformance_and_non_promotion_rows(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    n9 = project_n9_promotion_certificate(session.receipt(), session=session)

    assert n9.promotion_rows == ()


def test_n12_projection_carries_explicit_epoch_placeholders(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    n12 = project_n12_epoch_reference(session.receipt(), session=session)

    assert n12.epoch_ref is None
    assert n12.model_ref is None
    assert n12.rule_ref == "policyos.layer3.gy.n9.v1"
    assert n12.schema_ref == "policyos.runtime.design_problem.v1"
    assert n12.validity == "epoch_not_implemented"


def test_obligation_budget_split_is_total_over_n9_taxonomy() -> None:
    registry = load_confidence_ledger_registry(
        REPO_ROOT / "architecture/production_quality/confidence_ledger.toml"
    )

    assert set(registry.obligation_weights) == set(PromotionObligationClass)
    assert sum(registry.obligation_weights.values()) == 1


def test_custom_predictable_schedule_profile_accounts_end_to_end(tmp_path: Path) -> None:
    default_factory = _SessionFactory(tmp_path / "default")
    half_factory = _SessionFactory(tmp_path / "half")
    default = default_factory()
    half = half_factory(
        scope=ConfidenceRiskBudgetScope(
            scope_owner_ref=_scope().scope_owner_ref,
            authority_purpose=_scope().authority_purpose,
            owner_scope_key="design-problem:half-schedule",
            owner_projection_hash=_HASH_1,
            epoch_ref=None,
            model_ref=None,
            rule_ref=_scope().rule_ref,
            schema_ref=_scope().schema_ref,
        ),
        schedule_profile_id="half_mass_basel_square",
    )

    default_started = default.start_check(_prepare(default))
    half_started = half.start_check(_prepare(half))

    assert half_started.spend.fraction * 2 == default_started.spend.fraction


def test_schedule_mass_above_one_is_rejected() -> None:
    registry = load_confidence_ledger_registry(
        REPO_ROOT / "architecture/production_quality/confidence_ledger.toml"
    )
    payload = registry.source_payload()
    payload["schedule_profiles"].append(
        {
            "profile_id": "overspend",
            "proof_kernel_id": "basel_square_v1",
            "mass": {"numerator": 2, "denominator": 1},
        }
    )

    with pytest.raises(ValueError, match="schedule_total_mass_above_one"):
        load_confidence_ledger_registry(payload)


def test_fraction_display_is_48_decimal_digit_directed_downward() -> None:
    scale = 10**48
    just_below_one_quantum = Fraction(10**100 - 1, 10**148)
    repeating = Fraction(2, 3)

    assert ledger_module._fraction_display(just_below_one_quantum) == "0"
    rendered = ledger_module._fraction_display(repeating)
    assert rendered == "0." + "6" * 48
    rendered_fraction = Fraction(int(rendered.replace(".", "")), scale)
    assert rendered_fraction <= repeating
    assert repeating - rendered_fraction < Fraction(1, scale)


def test_registry_cannot_self_declare_new_proof_theorem() -> None:
    registry = load_confidence_ledger_registry(
        REPO_ROOT / "architecture/production_quality/confidence_ledger.toml"
    )
    payload = registry.source_payload()
    payload["proof_profiles"].append(
        {
            "profile_id": "forged_theorem",
            "proof_kernel_id": "registry_authored_anytime_theorem_v999",
            "guarantee_kind": "confidence_sequence",
            "deterministic": False,
            "anytime_valid": True,
            "permits_obligation_satisfaction": True,
        }
    )

    with pytest.raises(ValueError, match="unknown_instrument_proof_kernel"):
        load_confidence_ledger_registry(payload)


def test_registry_cannot_self_declare_owner_verifier_kernel() -> None:
    registry = load_confidence_ledger_registry(
        REPO_ROOT / "architecture/production_quality/confidence_ledger.toml"
    )
    payload = registry.source_payload()
    payload["certificate_class_routes"][0]["verifier_kernel_id"] = (
        "registry_authored_owner_verifier_v999"
    )

    with pytest.raises(ValueError, match="unknown_owner_verifier_kernel"):
        load_confidence_ledger_registry(payload)
