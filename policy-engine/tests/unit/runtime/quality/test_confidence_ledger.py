from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import importlib.util
import inspect
import json
import os
import select
import shutil
import subprocess
import sys
import threading
import time
import types
from collections.abc import Callable
from fractions import Fraction
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactIntegrityError,
    FileSystemCAS,
    PutOptions,
)
from polisyos.fabric.io.atomic import atomic_write_json
from polisyos.pdc import PromotionObligationClass
from polisyos.runtime.quality import confidence_ledger as ledger_module
from polisyos.runtime.quality.confidence_ledger import (
    CONDITIONAL_VALIDITY_CLAUSE,
    ConfidenceLedgerCheck,
    ConfidenceLedgerError,
    ConfidenceLedgerSession,
    ConfidenceRiskBudgetScope,
    N9PromotionCertificateProjection,
    OwnerCertificateEvidence,
    OwnerCertificateVerification,
    PredictableClaimSpec,
    RationalSpec,
    load_confidence_ledger_registry,
    project_confidence_ledger_semantic_receipt,
    project_n9_promotion_certificate,
    project_n12_epoch_reference,
    recompute_confidence_owner_evidence_hash,
    validate_confidence_ledger_receipt,
)


def _test_source_root() -> Path:
    """Find the product checkout when this test is staged in an evidence bundle."""

    test_path = Path(__file__).resolve()
    for parent in test_path.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src/polisyos").is_dir():
            return parent
        product_root = parent / "policy-engine"
        if (product_root / "pyproject.toml").is_file() and (product_root / "src/polisyos").is_dir():
            return product_root
    return test_path.parents[4]


REPO_ROOT = _test_source_root()
_HASH_1 = "sha256:" + "1" * 64
_HASH_2 = "sha256:" + "2" * 64


def _scope(
    *,
    owner_projection_hash: str = _HASH_1,
    owner_scope_key: str = "design-problem:durable-ledger-test",
    authority_purpose: str = "n9_promotion",
) -> ConfidenceRiskBudgetScope:
    return ConfidenceRiskBudgetScope(
        scope_owner_ref="polisyos.runtime.quality.promotion_sequence",
        authority_purpose=authority_purpose,
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


def _install_loaded_deployment(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    drift_after_state_load: bool = False,
) -> None:
    """Install all bytes used to identify a test-loaded policy-engine checkout."""

    _install_canonical_registry(repo_root)
    shutil.copytree(
        REPO_ROOT / "src",
        repo_root / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    if drift_after_state_load:
        ledger_source = repo_root / "src/polisyos/runtime/quality/confidence_ledger.py"
        source = ledger_source.read_text(encoding="utf-8")
        anchor = "        return derived_head, root, events\n\n    def _scope_artifact_refs_locked("
        injected = (
            '        drift_marker = self._state_root / "inject-deployment-drift-on-load"\n'
            "        if drift_marker.is_file():\n"
            "            drift_source = (\n"
            "                self._authority_repo_root\n"
            '                / "src/polisyos/core/canon/canon_json.py"\n'
            "            )\n"
            "            drift_source.write_bytes(\n"
            '                drift_source.read_bytes() + b"\\n# source-bound mid-operation drift\\n"\n'
            "            )\n"
            "            drift_marker.unlink()\n" + anchor
        )
        assert source.count(anchor) == 1
        ledger_source.write_text(source.replace(anchor, injected), encoding="utf-8")
    for relative in (Path("pyproject.toml"), Path("uv.lock")):
        target = repo_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / relative).read_bytes())

    original_root = REPO_ROOT.resolve()
    code_by_module: dict[str, dict[str, types.CodeType]] = {}
    original_source_by_module: dict[str, Path] = {}
    for module_name, relative_path in ledger_module._IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE:
        source_path = (repo_root / relative_path).resolve()
        loader = SourceFileLoader(module_name, str(source_path))
        spec = importlib.util.spec_from_loader(module_name, loader, origin=str(source_path))
        module = sys.modules[module_name]
        original_source_by_module[module_name] = (original_root / relative_path).resolve()
        assert spec is not None
        monkeypatch.setattr(module, "__spec__", spec)
        monkeypatch.setattr(module, "__loader__", loader)
        monkeypatch.setattr(module, "__file__", str(source_path))
        module_code = compile(
            source_path.read_bytes(),
            str(source_path),
            "exec",
            dont_inherit=True,
            optimize=sys.flags.optimize,
        )
        assert isinstance(module_code, types.CodeType)
        compiled_by_digest: dict[str, types.CodeType] = {}

        def index_code(
            code: types.CodeType,
            compiled_by_digest: dict[str, types.CodeType],
        ) -> None:
            digest = ledger_module._content_hash(ledger_module._normalize_code_object(code))
            compiled_by_digest.setdefault(digest, code)
            for constant in code.co_consts:
                if isinstance(constant, types.CodeType):
                    index_code(constant, compiled_by_digest)

        index_code(module_code, compiled_by_digest)
        code_by_module[module_name] = compiled_by_digest

    seen_functions: set[int] = set()
    seen_classes: set[int] = set()

    def relocate_function(function: object, *, module_name: str) -> None:
        if not isinstance(function, types.FunctionType):
            return
        if function.__module__ == module_name and id(function) not in seen_functions:
            seen_functions.add(id(function))
            current_path = Path(function.__code__.co_filename).resolve()
            if current_path == original_source_by_module[module_name]:
                digest = ledger_module._content_hash(
                    ledger_module._normalize_code_object(function.__code__)
                )
                relocated_code = code_by_module[module_name].get(digest)
                if drift_after_state_load and module_name == ledger_module.__name__:
                    relocated_code = next(
                        (
                            code
                            for code in code_by_module[module_name].values()
                            if code.co_qualname == function.__qualname__
                        ),
                        None,
                    )
                assert relocated_code is not None, (module_name, function.__qualname__)
                assert function.__code__.co_freevars == relocated_code.co_freevars
                monkeypatch.setattr(function, "__code__", relocated_code)
        relocate_function(getattr(function, "__wrapped__", None), module_name=module_name)

    def relocate_class(cls: type[object], *, module_name: str) -> None:
        if id(cls) in seen_classes or cls.__module__ != module_name:
            return
        seen_classes.add(id(cls))
        for value in vars(cls).values():
            if isinstance(value, (classmethod, staticmethod)):
                relocate_function(value.__func__, module_name=module_name)
            elif isinstance(value, property):
                for accessor in (value.fget, value.fset, value.fdel):
                    relocate_function(accessor, module_name=module_name)
            elif isinstance(value, types.FunctionType):
                relocate_function(value, module_name=module_name)
            elif isinstance(value, type):
                relocate_class(value, module_name=module_name)

    for module_name, _relative_path in ledger_module._IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE:
        module = sys.modules[module_name]
        for value in vars(module).values():
            if isinstance(value, types.FunctionType):
                relocate_function(value, module_name=module_name)
            elif isinstance(value, type):
                relocate_class(value, module_name=module_name)

    monkeypatch.setattr(ledger_module, "_IMPORT_TIME_OWNER_ROOT", repo_root.resolve())
    relocated_manifest, relocated_consistent = ledger_module._loaded_code_manifest(
        repo_root.resolve(), ledger_module._IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE
    )
    assert relocated_consistent is True

    def remap_source_root(value: object) -> object:
        if isinstance(value, str) and (
            value == original_root.as_posix() or value.startswith(original_root.as_posix() + "/")
        ):
            return repo_root.resolve().as_posix() + value[len(original_root.as_posix()) :]
        if isinstance(value, list):
            return [remap_source_root(item) for item in value]
        if isinstance(value, dict):
            return {key: remap_source_root(item) for key, item in value.items()}
        return value

    original_projection = json.loads(
        ledger_module._loaded_code_evidence_projection(
            ledger_module._IMPORT_TIME_LOADED_CODE_MANIFEST
        )
    )
    expected_relocated_projection = remap_source_root(original_projection)
    actual_projection = json.loads(
        ledger_module._loaded_code_evidence_projection(relocated_manifest)
    )
    if not drift_after_state_load:
        assert actual_projection == expected_relocated_projection
    monkeypatch.setattr(ledger_module, "_IMPORT_TIME_LOADED_CODE_MANIFEST", relocated_manifest)
    monkeypatch.setattr(ledger_module, "_IMPORT_TIME_LOADED_CODE_CONSISTENT", True)
    if drift_after_state_load:
        monkeypatch.setattr(
            ledger_module,
            "_IMPORT_TIME_DEPLOYMENT_BASELINE",
            ledger_module._deployment_baseline(repo_root.resolve()),
        )
        monkeypatch.setattr(
            ledger_module,
            "_IMPORT_TIME_DEPLOYMENT_QUICK_FENCE",
            ledger_module._deployment_quick_fence(repo_root.resolve()),
        )


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
    ref = session._put_ledger_json(
        stored.model_dump(mode="json"),
        contract_id="event",
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


def _append_and_fsync(path: Path, payload: bytes) -> None:
    with path.open("ab") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def test_torn_first_wal_record_is_truncated_to_empty_verified_prefix(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    assert session._journal_path.stat().st_size == 0
    _append_and_fsync(session._journal_path, b'{"schema_version":"torn')

    reopened = sessions()

    assert reopened.receipt().events == ()
    assert reopened._journal_path.read_bytes() == b""


def test_torn_intent_tail_is_removed_after_complete_committed_prefix(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    expected = session.receipt()
    verified_prefix = session._journal_path.read_bytes()
    _append_and_fsync(session._journal_path, b'{"record_type":"intent","payload":')

    reopened = sessions()

    assert reopened.receipt() == expected
    assert reopened._journal_path.read_bytes() == verified_prefix


def test_torn_commit_tail_replays_complete_intent_and_commits_it(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    receipt = session.receipt()
    payload = receipt.model_dump(mode="json")
    artifact_ref = ledger_module._cas_json_artifact_ref(payload)
    with session._exclusive_lock():
        session._append_scope_journal_intent(
            artifact_kind="receipt",
            artifact_ref=artifact_ref,
            payload=payload,
        )
    _append_and_fsync(
        session._journal_path,
        b'{"record_type":"commit","artifact_ref":"sha256:torn',
    )

    reopened = sessions()

    assert reopened.receipt() == receipt
    assert reopened._artifact_store.has(artifact_ref)
    assert reopened._journal_path.read_bytes().endswith(b"\n")


def test_complete_invalid_wal_line_is_not_repaired_or_truncated(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    _append_and_fsync(session._journal_path, b'{"complete":"but-invalid"}\n')
    corrupted = session._journal_path.read_bytes()

    with pytest.raises(ConfidenceLedgerError, match="ledger_scope_journal_invalid"):
        sessions()

    assert session._journal_path.read_bytes() == corrupted


def test_cached_wal_prefix_rewrite_fails_closed(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    original = session._journal_path.read_bytes()
    rewritten = bytes([original[0] ^ 1]) + original[1:]
    with session._journal_path.open("r+b") as handle:
        handle.write(rewritten)
        handle.flush()
        os.fsync(handle.fileno())

    with pytest.raises(ConfidenceLedgerError, match="ledger_scope_journal_rollback_detected"):
        session.receipt()


def test_wal_shrink_below_cached_offset_is_not_torn_tail_repair(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    original_size = session._journal_path.stat().st_size
    with session._journal_path.open("r+b") as handle:
        handle.truncate(original_size - 1)
        handle.flush()
        os.fsync(handle.fileno())

    with pytest.raises(ConfidenceLedgerError, match="ledger_scope_journal_rollback_detected"):
        session.receipt()

    assert session._journal_path.stat().st_size == original_size - 1


def test_complete_wal_record_hash_mismatch_is_not_repaired(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    previous_hash = ledger_module._scope_journal_genesis_hash(session.risk_scope.scope_id)
    payload = {
        "schema_version": ledger_module.CONFIDENCE_LEDGER_SCHEMA_VERSION,
        "scope_id": session.risk_scope.scope_id,
        "revision": len(session._journal_records) + 1,
        "previous_record_hash": previous_hash,
        "record_type": "commit",
        "artifact_kind": "event",
        "artifact_ref": _HASH_1,
        "payload": None,
        "record_hash": "sha256:" + "0" * 64,
    }
    _append_and_fsync(
        session._journal_path,
        f"{ledger_module._canonical_json(payload)}\n".encode(),
    )
    corrupted = session._journal_path.read_bytes()

    with pytest.raises(ConfidenceLedgerError, match="ledger_scope_journal_invalid"):
        session.receipt()

    assert session._journal_path.read_bytes() == corrupted


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
        blob, manifest = session._artifact_store._paths(ArtifactID.model_validate(event.event_ref))
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


def test_deployment_identity_changes_for_closure_member_but_ignores_unrelated_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    closure_paths = {
        Path(relative_path)
        for _module_name, relative_path in ledger_module._resolve_authority_import_closure(
            repo_root,
            ledger_module.__name__,
        )
    }
    source_paths = sorted(
        (path.relative_to(repo_root) for path in (repo_root / "src/polisyos").rglob("*.py")),
        key=Path.as_posix,
    )
    inside = repo_root / next(
        path
        for path in source_paths
        if path in closure_paths
        and path != Path("src/polisyos/runtime/quality/confidence_ledger.py")
    )
    outside = repo_root / next(path for path in source_paths if path not in closure_paths)

    original = ledger_module._policy_engine_deployment_identity(repo_root)
    inside_bytes = inside.read_bytes()
    inside.write_bytes(inside_bytes + b"\n# imported authority drift\n")
    assert ledger_module._policy_engine_deployment_identity(repo_root) != original
    inside.write_bytes(inside_bytes)

    outside.write_bytes(outside.read_bytes() + b"\n# unrelated source drift\n")
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


def test_steady_state_lock_keeps_deployment_fence_and_replays_loaded_code_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loaded code is replayed while unrelated deployment-root hashing stays lazy."""

    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    deployment_source_reads: list[Path] = []
    imported_source_reads: list[Path] = []
    import_root = REPO_ROOT
    read_bytes = Path.read_bytes

    def track_source_reads(path: Path) -> bytes:
        if path.is_relative_to(repo_root / "src/polisyos"):
            deployment_source_reads.append(path)
        if path.is_relative_to(import_root / "src/polisyos"):
            imported_source_reads.append(path)
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", track_source_reads)

    session.observe_history()
    session.receipt()

    expected_deployment_sources = {
        (repo_root / relative_path).resolve()
        for _module_name, relative_path in ledger_module._IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE
    }
    expected_imported_sources = {
        (import_root / "src/polisyos/runtime/quality/confidence_ledger.py").resolve()
    }
    assert set(deployment_source_reads) == expected_deployment_sources
    assert set(imported_source_reads) == expected_imported_sources


def test_deployment_quick_fence_rehashes_once_then_poisons_changed_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    full_recomputations = 0
    deployment_baseline = ledger_module._deployment_baseline

    def count_full_recomputation(root: Path) -> str:
        nonlocal full_recomputations
        full_recomputations += 1
        return deployment_baseline(root)

    monkeypatch.setattr(ledger_module, "_deployment_baseline", count_full_recomputation)
    source = repo_root / "src/polisyos/core/canon/canon_json.py"
    source.write_bytes(source.read_bytes() + b"\n# quick-fence content drift\n")

    with pytest.raises(ConfidenceLedgerError, match="canonical_deployment_identity_invalid"):
        session.observe_history()

    assert full_recomputations == 1


def test_content_equal_metadata_churn_refreshes_quick_fence_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    full_recomputations = 0
    deployment_baseline = ledger_module._deployment_baseline

    def count_full_recomputation(root: Path) -> str:
        nonlocal full_recomputations
        full_recomputations += 1
        return deployment_baseline(root)

    monkeypatch.setattr(ledger_module, "_deployment_baseline", count_full_recomputation)
    source = repo_root / "src/polisyos/core/canon/canon_json.py"
    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    session.observe_history()
    session.receipt()

    assert full_recomputations == 1


def test_canonical_session_rejects_closure_drift_but_ignores_unrelated_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_root = tmp_path / "kernel-authority-repo"
    _install_loaded_deployment(first_root, monkeypatch)
    first = ConfidenceLedgerSession.from_repo(first_root, risk_scope=_scope())
    first_closure_paths = {
        Path(relative_path)
        for _module_name, relative_path in ledger_module._resolve_authority_import_closure(
            first_root,
            ledger_module.__name__,
        )
    }
    inside = first_root / next(
        path
        for path in sorted(first_closure_paths, key=Path.as_posix)
        if path != Path("src/polisyos/runtime/quality/confidence_ledger.py")
    )
    inside.write_bytes(inside.read_bytes() + b"\n# imported authority drift\n")
    with pytest.raises(ConfidenceLedgerError, match="canonical_deployment_identity_invalid"):
        first.observe_history()

    second_root = tmp_path / "module-authority-repo"
    _install_loaded_deployment(second_root, monkeypatch)
    second = ConfidenceLedgerSession.from_repo(
        second_root,
        risk_scope=_scope(owner_scope_key="design-problem:module-set-drift"),
    )
    expected_history = second.observe_history()
    second_closure_paths = {
        Path(relative_path)
        for _module_name, relative_path in ledger_module._resolve_authority_import_closure(
            second_root,
            ledger_module.__name__,
        )
    }
    outside = next(
        path
        for path in sorted(
            (second_root / "src/polisyos").rglob("*.py"),
            key=lambda candidate: candidate.as_posix(),
        )
        if path.relative_to(second_root) not in second_closure_paths
    )
    outside.write_bytes(outside.read_bytes() + b"\n# unrelated source drift\n")

    assert second.observe_history() == expected_history
    assert second.receipt().events == ()


def test_from_repo_rejects_disk_mutation_after_authority_dependency_was_imported(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "isolated-authority-repo"
    shutil.copytree(REPO_ROOT / "src", repo_root / "src")
    shutil.copytree(REPO_ROOT / "architecture", repo_root / "architecture")
    for relative in (Path("pyproject.toml"), Path("uv.lock")):
        target = repo_root / relative
        target.write_bytes((REPO_ROOT / relative).read_bytes())
    script = """
import sys
from pathlib import Path

from polisyos.runtime.quality.confidence_ledger import (
    ConfidenceLedgerError,
    ConfidenceLedgerSession,
    ConfidenceRiskBudgetScope,
)

repo_root = Path(sys.argv[1]).resolve()
dependency = repo_root / "src/polisyos/core/canon/canon_json.py"
dependency.write_bytes(dependency.read_bytes() + b"\\n# changed after import\\n")
scope = ConfidenceRiskBudgetScope(
    scope_owner_ref="polisyos.runtime.quality.promotion_sequence",
    authority_purpose="n9_promotion",
    owner_scope_key="design-problem:loaded-code-mismatch",
    owner_projection_hash="sha256:" + "1" * 64,
    epoch_ref=None,
    model_ref=None,
    rule_ref="policyos.layer3.gy.n9.v1",
    schema_ref="policyos.runtime.design_problem.v1",
)
try:
    ConfidenceLedgerSession.from_repo(repo_root, risk_scope=scope)
except ConfidenceLedgerError as exc:
    print(exc.code)
    raise SystemExit(0 if exc.code == "canonical_loaded_runtime_mismatch" else 2)
raise SystemExit(3)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")

    completed = subprocess.run(
        [sys.executable, "-c", script, str(repo_root)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "canonical_loaded_runtime_mismatch"


def test_from_repo_rejects_dependency_loaded_before_its_source_changes(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "isolated-authority-repo"
    shutil.copytree(REPO_ROOT / "src", repo_root / "src")
    shutil.copytree(REPO_ROOT / "architecture", repo_root / "architecture")
    for relative in (Path("pyproject.toml"), Path("uv.lock")):
        target = repo_root / relative
        target.write_bytes((REPO_ROOT / relative).read_bytes())
    script = """
import ast
import sys
from pathlib import Path

import polisyos.core.canon.canon_json

repo_root = Path(sys.argv[1]).resolve()
dependency = repo_root / "src/polisyos/core/canon/canon_json.py"
source = dependency.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(dependency))
provider = next(
    node
    for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "to_canonical_bytes"
)
returned = next(node for node in provider.body if isinstance(node, ast.Return))
source_bytes = source.encode("utf-8")
lines = source_bytes.splitlines(keepends=True)
assert returned.end_lineno is not None and returned.end_col_offset is not None
start = sum(map(len, lines[: returned.lineno - 1])) + returned.col_offset
end = sum(map(len, lines[: returned.end_lineno - 1])) + returned.end_col_offset
changed = (
    source_bytes[:start]
    + b"return None  # source changed after dependency import"
    + source_bytes[end:]
).decode("utf-8")
assert changed != source
dependency.write_text(changed, encoding="utf-8")

from polisyos.runtime.quality import confidence_ledger as ledger

assert not ledger._IMPORT_TIME_LOADED_CODE_CONSISTENT
scope = ledger.ConfidenceRiskBudgetScope(
    scope_owner_ref="polisyos.runtime.quality.promotion_sequence",
    authority_purpose="n9_promotion",
    owner_scope_key="design-problem:old-loaded-dependency",
    owner_projection_hash="sha256:" + "1" * 64,
    epoch_ref=None,
    model_ref=None,
    rule_ref="policyos.layer3.gy.n9.v1",
    schema_ref="policyos.runtime.design_problem.v1",
)
try:
    ledger.ConfidenceLedgerSession.from_repo(repo_root, risk_scope=scope)
except ledger.ConfidenceLedgerError as exc:
    print(exc.code)
    raise SystemExit(0 if exc.code == "canonical_loaded_runtime_mismatch" else 2)
raise SystemExit(3)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")

    completed = subprocess.run(
        [sys.executable, "-c", script, str(repo_root)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "canonical_loaded_runtime_mismatch"


def test_source_decorator_factory_argument_binding_is_typed_and_exact() -> None:
    source = ast.parse(
        "def factory(required, /, optional=1, *, flag=False):\n    pass\n"
        "@factory('source', 2, flag=True)\n"
        "def target():\n    pass\n"
    )
    factory_node, target_node = source.body
    assert isinstance(factory_node, ast.FunctionDef)
    assert isinstance(target_node, ast.FunctionDef)
    assert ledger_module._source_decorator_factory_captures(
        factory_node,
        target_node.decorator_list[0],
        terminal=lambda: None,
    ) == {"required": "source", "optional": 2, "flag": True}

    duplicate_source = ast.parse(
        "def duplicate_factory(value=0):\n    pass\n"
        "@duplicate_factory(1, value=2)\n"
        "def duplicate_target():\n    pass\n"
    )
    duplicate_factory, duplicate_target = duplicate_source.body
    assert isinstance(duplicate_factory, ast.FunctionDef)
    assert isinstance(duplicate_target, ast.FunctionDef)
    assert (
        ledger_module._source_decorator_factory_captures(
            duplicate_factory,
            duplicate_target.decorator_list[0],
            terminal=lambda: None,
        )
        is None
    )


def test_rebound_closure_owned_callable_fails_closed_for_every_session_mode(
    tmp_path: Path,
) -> None:
    probe_source = """
from contextlib import contextmanager
from functools import lru_cache, wraps

def _default_metrics(*args, **kwargs):
    return None

class AuthzInput:
    @classmethod
    def for_http_request(cls):
        return cls()

    @classmethod
    def for_cas_artifact(cls):
        return cls()

def _transactional_read(
    *,
    profile_argument_index: int | None = None,
    signature_surface: bool = False,
):
    def decorate(method):
        @wraps(method)
        def wrapped(*args, **kwargs):
            if signature_surface and profile_argument_index == -1:
                raise AssertionError("unreachable wrapper control")
            return method(*args, **kwargs)
        return wrapped
    return decorate

def _positional_read(
    profile_argument_index: int | None = None,
    /,
    signature_surface: bool = False,
):
    def decorate(method):
        @wraps(method)
        def wrapped(*args, **kwargs):
            if signature_surface and profile_argument_index == -1:
                raise AssertionError("unreachable wrapper control")
            return method(*args, **kwargs)
        return wrapped
    return decorate

def _unsafe_replacement(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        return "bypassed-transaction"
    return wrapped

class DatabaseBackend:
    @_transactional_read(profile_argument_index=None, signature_surface=False)
    def transaction(self):
        return None

    @_positional_read(None, signature_surface=False)
    def positional_transaction(self):
        return None

    @contextmanager
    def tenant_scope(self):
        yield None

class LRUCache:
    def __init__(self):
        self._max_size = 1

    @property
    def max_size(self):
        return self._max_size

    @max_size.setter
    def max_size(self, value):
        self._max_size = value

@lru_cache(maxsize=1)
def get_security_settings():
    return None
"""
    script = """
import importlib.util
import json
import sys
import tempfile
import types
from functools import lru_cache
from pathlib import Path

from polisyos.core.artifacts import FileSystemCAS

probe_name = "polisyos._gy_di1_closure_probe"
probe_path = Path.cwd() / "src/polisyos/_gy_di1_closure_probe.py"
spec = importlib.util.spec_from_file_location(probe_name, probe_path)
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
sys.modules[probe_name] = probe
spec.loader.exec_module(probe)

mutation = sys.argv[1]
if mutation == "foreign":
    def replacement(*args, **kwargs):
        return "foreign-rebound"
    probe._default_metrics = replacement
elif mutation == "local_swap":
    probe._default_metrics = probe.AuthzInput.for_http_request.__func__
elif mutation == "deleted":
    del probe._default_metrics
elif mutation == "class_swap":
    probe.AuthzInput.for_http_request = classmethod(
        probe.AuthzInput.for_cas_artifact.__func__
    )
elif mutation == "class_deleted":
    del probe.AuthzInput.for_http_request
elif mutation == "class_descriptor_swap":
    original = vars(probe.AuthzInput)["for_http_request"]
    probe.AuthzInput.for_http_request = staticmethod(original.__func__)
elif mutation == "decorated_swap":
    probe.DatabaseBackend.transaction = vars(probe.DatabaseBackend)["tenant_scope"]
elif mutation == "decorated_unwrapped":
    original = vars(probe.DatabaseBackend)["transaction"]
    probe.DatabaseBackend.transaction = original.__wrapped__
elif mutation == "decorated_deleted":
    del probe.DatabaseBackend.transaction
elif mutation == "property_roles_swapped":
    original = vars(probe.LRUCache)["max_size"]
    probe.LRUCache.max_size = property(
        fget=original.fset,
        fset=original.fget,
    )
elif mutation == "lru_policy_rewritten":
    original = probe.get_security_settings
    probe.get_security_settings = lru_cache(maxsize=8, typed=True)(
        original.__wrapped__
    )
elif mutation == "decorated_forged_wrapper":
    original = vars(probe.DatabaseBackend)["transaction"]
    probe.DatabaseBackend.transaction = probe._unsafe_replacement(original.__wrapped__)
elif mutation == "decorated_foreign_globals":
    original = vars(probe.DatabaseBackend)["transaction"]
    foreign_globals = dict(probe.__dict__)
    probe.DatabaseBackend.transaction = types.FunctionType(
        original.__code__,
        foreign_globals,
        original.__name__,
        original.__defaults__,
        original.__closure__,
    )
    probe.DatabaseBackend.transaction.__dict__.update(original.__dict__)
elif mutation in {
    "decorated_closure_argument_changed",
    "decorated_closure_target_changed",
    "decorated_unsupported_literal_changed",
}:
    original = vars(probe.DatabaseBackend)["transaction"]
    def make_cell(value):
        return (lambda: value).__closure__[0]
    replacement_value = (
        "not-a-bool"
        if mutation == "decorated_closure_argument_changed"
        else None
        if mutation == "decorated_unsupported_literal_changed"
        else vars(probe.DatabaseBackend)["tenant_scope"].__wrapped__
    )
    replacement_name = (
        "signature_surface"
        if mutation in {
            "decorated_closure_argument_changed",
            "decorated_unsupported_literal_changed",
        }
        else "method"
    )
    closure = [
        make_cell(replacement_value) if name == replacement_name else cell
        for name, cell in zip(original.__code__.co_freevars, original.__closure__)
    ]
    replacement = types.FunctionType(
        original.__code__,
        original.__globals__,
        original.__name__,
        original.__defaults__,
        tuple(closure),
    )
    replacement.__dict__.update(original.__dict__)
    probe.DatabaseBackend.transaction = replacement
elif mutation == "valid":
    pass
else:
    raise AssertionError(mutation)

from polisyos.runtime.quality import confidence_ledger as ledger

if mutation == "valid":
    print(json.dumps({
        "consistent": ledger._IMPORT_TIME_LOADED_CODE_CONSISTENT,
        "identity": ledger.capture_loaded_deployment_identity().model_dump(mode="json"),
    }))
    raise SystemExit(0)

repo_root = Path.cwd()
scope = ledger.ConfidenceRiskBudgetScope(
    scope_owner_ref="polisyos.runtime.quality.promotion_sequence",
    authority_purpose="n9_promotion",
    owner_scope_key="design-problem:rebound-admission",
    owner_projection_hash="sha256:" + "1" * 64,
    epoch_ref=None,
    model_ref=None,
    rule_ref="policyos.layer3.gy.n9.v1",
    schema_ref="policyos.runtime.design_problem.v1",
)

results = []
with tempfile.TemporaryDirectory() as temporary:
    temporary_root = Path(temporary)
    for session_mode in ("verification", "authority"):
        if session_mode == "verification":
            open_session = lambda: ledger.ConfidenceLedgerSession._for_verification(
                repo_root,
                risk_scope=scope,
                artifact_store=FileSystemCAS(temporary_root / "cas"),
                state_root=temporary_root / "state",
            )
        else:
            open_session = lambda: ledger.ConfidenceLedgerSession.from_repo(
                repo_root,
                risk_scope=scope,
            )
        try:
            open_session()
        except ledger.ConfidenceLedgerError as exc:
            results.append(exc.code)
        else:
            results.append("admitted")
print(json.dumps(results))
"""

    for mutation in (
        "foreign",
        "local_swap",
        "deleted",
        "class_swap",
        "class_deleted",
        "class_descriptor_swap",
        "decorated_swap",
        "decorated_unwrapped",
        "decorated_deleted",
        "property_roles_swapped",
        "lru_policy_rewritten",
        "decorated_forged_wrapper",
        "decorated_foreign_globals",
        "decorated_closure_argument_changed",
        "decorated_closure_target_changed",
        "decorated_unsupported_literal_changed",
    ):
        checkout = tmp_path / mutation / "policy-engine"
        shutil.copytree(REPO_ROOT / "src", checkout / "src")
        for relative in (Path("pyproject.toml"), Path("uv.lock")):
            target = checkout / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO_ROOT / relative).read_bytes())
        (checkout / "architecture").symlink_to(
            REPO_ROOT / "architecture",
            target_is_directory=True,
        )
        probe_path = checkout / "src/polisyos/_gy_di1_closure_probe.py"
        mutation_probe_source = probe_source
        if mutation == "decorated_unsupported_literal_changed":
            mutation_probe_source = mutation_probe_source.replace(
                "@_transactional_read(profile_argument_index=None, signature_surface=False)",
                "@_transactional_read(profile_argument_index=None, signature_surface=...)",
            )
        probe_path.write_text(mutation_probe_source, encoding="utf-8")
        entry_path = checkout / "src/polisyos/runtime/quality/confidence_ledger.py"
        entry_path.write_bytes(
            entry_path.read_bytes() + b"\nimport polisyos._gy_di1_closure_probe\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(checkout / "src")
        completed = subprocess.run(
            [sys.executable, "-c", script, mutation],
            cwd=checkout,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert json.loads(completed.stdout.strip().splitlines()[-1]) == [
            "canonical_loaded_runtime_mismatch",
            "canonical_loaded_runtime_mismatch",
        ]

    valid_checkout = tmp_path / "valid-local-decorator" / "policy-engine"
    shutil.copytree(REPO_ROOT / "src", valid_checkout / "src")
    for relative in (Path("pyproject.toml"), Path("uv.lock")):
        target = valid_checkout / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / relative).read_bytes())
    (valid_checkout / "architecture").symlink_to(
        REPO_ROOT / "architecture",
        target_is_directory=True,
    )
    probe_path = valid_checkout / "src/polisyos/_gy_di1_closure_probe.py"
    probe_path.write_text(probe_source, encoding="utf-8")
    entry_path = valid_checkout / "src/polisyos/runtime/quality/confidence_ledger.py"
    entry_path.write_bytes(entry_path.read_bytes() + b"\nimport polisyos._gy_di1_closure_probe\n")
    valid_env = os.environ.copy()
    valid_env["PYTHONPATH"] = str(valid_checkout / "src")
    valid_completed = subprocess.run(
        [sys.executable, "-c", script, "valid"],
        cwd=valid_checkout,
        env=valid_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert valid_completed.returncode == 0, valid_completed.stdout + valid_completed.stderr
    valid_observation = json.loads(valid_completed.stdout.strip().splitlines()[-1])
    assert valid_observation["consistent"] is True
    assert valid_observation["identity"]["status"] == "established"


def test_deployment_identity_manifest_is_complete_and_import_order_independent() -> None:
    """The declared authority closure, not import chronology, owns E12 identity."""

    script = """
import json
import sys
import tempfile
from pathlib import Path

if sys.argv[1] == "depth_first":
    import tools.quality.validation.check_layer3_gy_depth_n_universality_contract

from polisyos.runtime.quality import confidence_ledger as ledger
from polisyos.core.artifacts import FileSystemCAS

manifest = json.loads(ledger._IMPORT_TIME_LOADED_CODE_MANIFEST)
scope = ledger.ConfidenceRiskBudgetScope(
    scope_owner_ref="polisyos.runtime.quality.promotion_sequence",
    authority_purpose="n9_promotion",
    owner_scope_key="design-problem:import-order-verification",
    owner_projection_hash="sha256:" + "1" * 64,
    epoch_ref=None,
    model_ref=None,
    rule_ref="policyos.layer3.gy.n9.v1",
    schema_ref="policyos.runtime.design_problem.v1",
)
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    session = ledger.ConfidenceLedgerSession._for_verification(
        Path.cwd(),
        risk_scope=scope,
        artifact_store=FileSystemCAS(root / "cas"),
        state_root=root / "state",
    )
print(json.dumps({
    "closure": [name for name, _path in ledger._IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE],
    "identity": ledger._policy_engine_deployment_identity(Path.cwd()),
    "manifest_keys": sorted(manifest),
    "verification_identity": session.deployment_identity,
    "public_session_identity": session.deployment_identity,
}, sort_keys=True))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")

    payloads = []
    for mode in ("confidence_first", "depth_first"):
        completed = subprocess.run(
            [sys.executable, "-c", script, mode],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        payloads.append(json.loads(completed.stdout))

    for payload in payloads:
        assert payload["manifest_keys"] == payload["closure"]
        assert payload["verification_identity"] == payload["identity"]
        assert payload["public_session_identity"] == payload["identity"]
    assert payloads[0]["identity"] == payloads[1]["identity"]


def test_authority_import_closure_includes_every_live_repository_import_binding() -> None:
    """Executed repository import bindings cannot escape the derived closure."""

    closure = dict(
        ledger_module._resolve_authority_import_closure(
            REPO_ROOT,
            ledger_module.__name__,
        )
    )
    source_root = REPO_ROOT / "src/polisyos"
    providers: dict[str, str] = {}
    for owner_name, relative_path in closure.items():
        owner = sys.modules[owner_name]
        tree = ast.parse(
            (REPO_ROOT / relative_path).read_bytes(),
            filename=relative_path,
        )
        bound_names: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                bound_names.update(
                    alias.asname or alias.name.partition(".")[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                bound_names.update(
                    alias.asname or alias.name for alias in node.names if alias.name != "*"
                )
        for bound_name in bound_names:
            value = vars(owner).get(bound_name)
            provider_name = (
                value.__name__
                if isinstance(value, types.ModuleType)
                else getattr(value, "__module__", None)
            )
            if not isinstance(provider_name, str):
                continue
            provider = sys.modules.get(provider_name)
            origin = getattr(provider, "__file__", None)
            if not isinstance(origin, str):
                continue
            try:
                provider_relative = Path(origin).resolve().relative_to(source_root)
            except ValueError:
                continue
            providers[provider_name] = (Path("src/polisyos") / provider_relative).as_posix()

    assert providers.items() <= closure.items()


def test_authority_import_closure_tracks_nested_runtime_but_not_type_only_imports(
    tmp_path: Path,
) -> None:
    """Executable nested edges enter closure while type-only edges stay outside."""

    repo_root = tmp_path / "closure-repo"
    shutil.copytree(REPO_ROOT / "src", repo_root / "src")
    modules: dict[str, Path] = {}
    for source_path in sorted(
        (repo_root / "src/polisyos").rglob("*.py"),
        key=lambda candidate: candidate.as_posix(),
    ):
        parts = list(source_path.relative_to(repo_root / "src").parts)
        if parts[-1] == "__init__.py":
            parts.pop()
        else:
            parts[-1] = source_path.stem
        modules[".".join(parts)] = source_path.relative_to(repo_root)

    baseline = dict(
        ledger_module._resolve_authority_import_closure(
            repo_root,
            ledger_module.__name__,
        )
    )
    runtime_target = next(
        module_name for module_name in sorted(modules) if module_name not in baseline
    )
    entry_path = repo_root / baseline[ledger_module.__name__]
    entry_path.write_bytes(
        entry_path.read_bytes()
        + (f"\ndef _nested_runtime_import_probe() -> None:\n    import {runtime_target}\n").encode()
    )
    with_runtime = dict(
        ledger_module._resolve_authority_import_closure(
            repo_root,
            ledger_module.__name__,
        )
    )
    assert with_runtime[runtime_target] == modules[runtime_target].as_posix()

    type_only_target = next(
        module_name for module_name in sorted(modules) if module_name not in with_runtime
    )
    entry_path.write_bytes(
        entry_path.read_bytes() + (f"\nif TYPE_CHECKING:\n    import {type_only_target}\n").encode()
    )
    with_type_only = dict(
        ledger_module._resolve_authority_import_closure(
            repo_root,
            ledger_module.__name__,
        )
    )
    assert type_only_target not in with_type_only


def _write_literal_pep562_closure_repo(
    repo_root: Path,
) -> tuple[Path, Path]:
    """Write a tiny source-only repository with two literal facade exports."""

    package_root = repo_root / "src/polisyos"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "provider_one.py").write_text(
        "class One:\n    pass\nclass Two:\n    pass\n",
        encoding="utf-8",
    )
    (package_root / "provider_two.py").write_text(
        "class Two:\n    pass\n",
        encoding="utf-8",
    )
    (package_root / "unreferenced.py").write_text(
        "class Unreferenced:\n    pass\n",
        encoding="utf-8",
    )
    facade_path = package_root / "facade.py"
    facade_path.write_text(
        "from importlib import import_module as _load\n"
        "_EXPORTS: dict[str, tuple[str, str]] = {\n"
        '    "One": ("polisyos.provider_one", "One"),\n'
        "}\n"
        "_ALIASES = {\n"
        '    "Two": ("polisyos.provider_two", "Two"),\n'
        "}\n"
        "def __getattr__(name):\n"
        '    if name == "One":\n'
        "        module_name, attribute_name = _EXPORTS[name]\n"
        "    else:\n"
        "        module_name, attribute_name = _ALIASES[name]\n"
        "    module = _load(module_name)\n"
        "    return getattr(module, attribute_name)\n",
        encoding="utf-8",
    )
    (package_root / "entry.py").write_text(
        "from polisyos.facade import One, Two\n",
        encoding="utf-8",
    )
    return repo_root, facade_path


def test_authority_import_closure_indexes_all_literal_pep562_aliases_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real closure resolves every alias from one exact-byte facade index."""

    repo_root, facade_path = _write_literal_pep562_closure_repo(tmp_path / "literal-pep562-repo")
    facade_bytes = facade_path.read_bytes()
    original_parse = ledger_module.ast.parse
    facade_parse_inputs: list[bytes] = []

    def recording_parse(
        source: str | bytes,
        filename: str = "<unknown>",
        mode: str = "exec",
        **kwargs: object,
    ) -> ast.AST:
        if filename == "src/polisyos/facade.py":
            assert isinstance(source, bytes)
            facade_parse_inputs.append(source)
        return original_parse(source, filename=filename, mode=mode, **kwargs)

    original_indexer = ledger_module._literal_module_getattr_provider_index
    indexed_trees: list[ast.Module] = []

    def recording_indexer(tree: ast.Module) -> ledger_module._LiteralModuleGetattrProviderIndex:
        indexed_trees.append(tree)
        return original_indexer(tree)

    monkeypatch.setattr(ledger_module.ast, "parse", recording_parse)
    monkeypatch.setattr(
        ledger_module,
        "_literal_module_getattr_provider_index",
        recording_indexer,
    )

    closure = dict(
        ledger_module._resolve_authority_import_closure(
            repo_root,
            "polisyos.entry",
        )
    )

    assert closure["polisyos.provider_one"] == "src/polisyos/provider_one.py"
    assert closure["polisyos.provider_two"] == "src/polisyos/provider_two.py"
    assert "polisyos.unreferenced" not in closure
    assert facade_parse_inputs == [facade_bytes]
    assert len(indexed_trees) == 1


def test_authority_import_closure_provider_removal_probe_keeps_source_markers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing provider resolution loses closure edges while facade markers stay."""

    repo_root, facade_path = _write_literal_pep562_closure_repo(
        tmp_path / "literal-pep562-removal-repo"
    )
    facade_source = facade_path.read_text(encoding="utf-8")
    assert "__getattr__" in facade_source
    assert "_EXPORTS" in facade_source
    assert "_ALIASES" in facade_source
    assert "polisyos.provider_one" in facade_source
    assert "polisyos.provider_two" in facade_source

    index_calls = 0

    def index_without_providers(
        tree: ast.Module,
    ) -> ledger_module._LiteralModuleGetattrProviderIndex:
        nonlocal index_calls
        assert tree.body
        index_calls += 1
        return ledger_module._LiteralModuleGetattrProviderIndex(
            providers_by_export=types.MappingProxyType({}),
            invalid_exports=frozenset(),
        )

    monkeypatch.setattr(
        ledger_module,
        "_literal_module_getattr_provider_index",
        index_without_providers,
    )
    closure = dict(
        ledger_module._resolve_authority_import_closure(
            repo_root,
            "polisyos.entry",
        )
    )

    assert index_calls == 1
    assert "polisyos.facade" in closure
    assert "polisyos.provider_one" not in closure
    assert "polisyos.provider_two" not in closure


def test_authority_import_closure_rereads_same_path_after_equal_metadata_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each provider query sees changed bytes even when path metadata is unchanged."""

    repo_root, facade_path = _write_literal_pep562_closure_repo(
        tmp_path / "literal-pep562-fresh-read-repo"
    )
    original_bytes = facade_path.read_bytes()
    changed_bytes = original_bytes.replace(
        b'"Two": ("polisyos.provider_two", "Two")',
        b'"Two": ("polisyos.provider_one", "Two")',
        1,
    )
    assert changed_bytes != original_bytes
    assert len(changed_bytes) == len(original_bytes)

    original_parse = ledger_module.ast.parse
    facade_parse_inputs: list[bytes] = []

    def recording_parse(
        source: str | bytes,
        filename: str = "<unknown>",
        mode: str = "exec",
        **kwargs: object,
    ) -> ast.AST:
        if filename == "src/polisyos/facade.py":
            assert isinstance(source, bytes)
            facade_parse_inputs.append(source)
        return original_parse(source, filename=filename, mode=mode, **kwargs)

    original_provider = ledger_module._literal_module_getattr_provider
    provider_queries = 0

    def mutate_after_first_provider_query(
        repo_root_arg: Path,
        module_name: str,
        export_name: str,
        *,
        directory_entries: dict[Path, frozenset[str]],
        source_index: ledger_module._AuthorityImportClosureSourceIndex | None = None,
    ) -> str | None:
        nonlocal provider_queries
        result = original_provider(
            repo_root_arg,
            module_name,
            export_name,
            directory_entries=directory_entries,
            source_index=source_index,
        )
        provider_queries += 1
        if provider_queries == 1:
            before = facade_path.stat()
            facade_path.write_bytes(changed_bytes)
            os.utime(
                facade_path,
                ns=(before.st_atime_ns, before.st_mtime_ns),
            )
            after = facade_path.stat()
            assert after.st_size == before.st_size
            assert after.st_mtime_ns == before.st_mtime_ns
        return result

    monkeypatch.setattr(ledger_module.ast, "parse", recording_parse)
    monkeypatch.setattr(
        ledger_module,
        "_literal_module_getattr_provider",
        mutate_after_first_provider_query,
    )

    closure = dict(
        ledger_module._resolve_authority_import_closure(
            repo_root,
            "polisyos.entry",
        )
    )

    assert provider_queries == 2
    assert facade_path.read_bytes() == changed_bytes
    assert facade_parse_inputs == [original_bytes, changed_bytes]
    assert closure["polisyos.provider_one"] == "src/polisyos/provider_one.py"
    assert "polisyos.provider_two" not in closure


def test_authority_import_closure_fails_closed_on_dynamic_pep562_provider(
    tmp_path: Path,
) -> None:
    """An unknown provider expression is not treated as a literal closure edge."""

    repo_root, facade_path = _write_literal_pep562_closure_repo(
        tmp_path / "literal-pep562-dynamic-repo"
    )
    facade_source = facade_path.read_text(encoding="utf-8")
    facade_source = facade_source.replace(
        '("polisyos.provider_one", "One")',
        '(choose_provider(), "One")',
        1,
    )
    facade_path.write_text(facade_source, encoding="utf-8")

    with pytest.raises(
        ConfidenceLedgerError,
        match="non-literal repository re-export",
    ):
        ledger_module._resolve_authority_import_closure(
            repo_root,
            "polisyos.entry",
        )


def _write_import_module_pep562_closure_repo(repo_root: Path) -> tuple[Path, Path]:
    """Write a source-only package with literal lazy provider branches."""

    package = repo_root / "src/polisyos"
    facade = package / "facade"
    facade.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "entry.py").write_text(
        "from polisyos.facade import One, AliasOne, Two\n",
        encoding="utf-8",
    )
    (facade / "provider_one.py").write_text(
        "class One:\n    pass\nclass AliasOne:\n    pass\nclass Two:\n    pass\n",
        encoding="utf-8",
    )
    (facade / "provider_two.py").write_text("class Two:\n    pass\n", encoding="utf-8")
    (facade / "unreferenced.py").write_text(
        "class Unreferenced:\n    pass\n",
        encoding="utf-8",
    )
    facade_path = facade / "__init__.py"
    facade_path.write_text(
        "from importlib import import_module as _load\n"
        "import importlib as _importlib\n"
        "def __getattr__(name):\n"
        '    if name in {"One", "AliasOne"}:\n'
        '        module = _load("polisyos.facade.provider_one")\n'
        "        return getattr(module, name)\n"
        '    if name == "Two":\n'
        '        module = _importlib.import_module("polisyos.facade.provider_two")\n'
        "        return getattr(module, name)\n"
        "    raise AttributeError(name)\n",
        encoding="utf-8",
    )
    return repo_root, facade_path


def test_authority_import_closure_includes_core_lazy_profile_providers() -> None:
    """The real Core facade providers enter loaded-deployment identity closure."""

    closure = dict(
        ledger_module._resolve_authority_import_closure(REPO_ROOT, ledger_module.__name__)
    )
    assert closure["polisyos.core.artifacts.canonical_profile"] == (
        "src/polisyos/core/artifacts/canonical_profile.py"
    )
    assert closure["polisyos.common.canonical_profile"] == (
        "src/polisyos/common/canonical_profile.py"
    )


def test_authority_import_closure_indexes_literal_import_module_facades(tmp_path: Path) -> None:
    """Literal name sets and both importlib call forms resolve their providers."""

    repo, _facade = _write_import_module_pep562_closure_repo(tmp_path / "import-module-pep562-repo")
    closure = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert closure["polisyos.facade.provider_one"] == "src/polisyos/facade/provider_one.py"
    assert closure["polisyos.facade.provider_two"] == "src/polisyos/facade/provider_two.py"
    assert "polisyos.facade.unreferenced" not in closure


def test_authority_import_closure_provider_removal_keeps_markers_but_loses_edges(
    tmp_path: Path,
) -> None:
    """Removing dispatch leaves marker strings but loses provider edges."""

    repo, facade = _write_import_module_pep562_closure_repo(
        tmp_path / "import-module-pep562-removal-repo"
    )
    initial = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert "polisyos.facade.provider_one" in initial
    assert "polisyos.facade.provider_two" in initial
    source = facade.read_text(encoding="utf-8")
    markers = (
        "__getattr__",
        "_load",
        "polisyos.facade.provider_one",
        "_importlib.import_module",
        "polisyos.facade.provider_two",
        '"One", "AliasOne"',
    )
    assert all(marker in source for marker in markers)
    removed = source.replace("return getattr(module, name)", "raise AttributeError(name)", 2)
    assert removed != source and removed.count("return getattr(module, name)") == 0
    facade.write_text(removed, encoding="utf-8")
    assert all(marker in facade.read_text(encoding="utf-8") for marker in markers)
    without_dispatch = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert "polisyos.facade.provider_one" not in without_dispatch
    assert "polisyos.facade.provider_two" not in without_dispatch


def test_authority_import_closure_recomputes_dynamic_provider_after_equal_metadata_change(
    tmp_path: Path,
) -> None:
    """New exact bytes change provider closure despite equal file metadata."""

    repo, facade = _write_import_module_pep562_closure_repo(
        tmp_path / "import-module-pep562-fresh-read-repo"
    )
    first = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert "polisyos.facade.provider_two" in first
    original = facade.read_bytes()
    changed = original.replace(
        b'"polisyos.facade.provider_two"',
        b'"polisyos.facade.provider_one"',
        1,
    )
    assert changed != original and len(changed) == len(original)
    before = facade.stat()
    facade.write_bytes(changed)
    os.utime(facade, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = facade.stat()
    assert after.st_size == before.st_size and after.st_mtime_ns == before.st_mtime_ns
    second = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert "polisyos.facade.provider_one" in second
    assert "polisyos.facade.provider_two" not in second


def test_authority_import_closure_fails_closed_on_dynamic_import_module_provider(
    tmp_path: Path,
) -> None:
    """A literal export guard cannot turn a dynamic module expression into proof."""

    repo, facade = _write_import_module_pep562_closure_repo(
        tmp_path / "import-module-pep562-dynamic-repo"
    )
    source = facade.read_text(encoding="utf-8")
    changed = source.replace(
        '_load("polisyos.facade.provider_one")',
        "_load(provider_module_name)",
        1,
    )
    assert changed != source
    facade.write_text(changed, encoding="utf-8")
    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def _core_profile_dispatch_source() -> str:
    """Read the actual Core profile-export branch for source-only closure fixtures."""

    facade_path = REPO_ROOT / "src/polisyos/core/artifacts/__init__.py"
    source = facade_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(facade_path))
    getattr_function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__"
    )
    parameter_name = getattr_function.args.args[0].arg
    dispatch = next(
        node
        for node in getattr_function.body
        if isinstance(node, ast.If)
        and "load_core_json_artifact"
        in ledger_module._literal_getattr_dispatch_names(node.test, parameter_name)
    )
    segment = ast.get_source_segment(source, dispatch)
    assert segment is not None
    return segment


def _write_core_profile_provider_closure_repo(
    repo_root: Path,
) -> tuple[Path, Path, dict[str, Path]]:
    """Write the actual Core lazy branch with Core/common profile providers."""

    package = repo_root / "src/polisyos"
    artifacts = package / "core/artifacts"
    common = package / "common"
    artifacts.mkdir(parents=True)
    common.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "core/__init__.py").write_text("", encoding="utf-8")
    (common / "__init__.py").write_text("", encoding="utf-8")
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "closure-fixture"\n', encoding="utf-8"
    )
    (repo_root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (package / "entry.py").write_text(
        "from polisyos.core.artifacts import load_core_json_artifact\n",
        encoding="utf-8",
    )
    dispatch = _core_profile_dispatch_source()
    indented_dispatch = "\n".join("    " + line for line in dispatch.splitlines())
    facade_path = artifacts / "__init__.py"
    facade_path.write_text(
        "from importlib import import_module\n"
        "from typing import Any\n\n"
        "def __getattr__(name: str) -> Any:\n"
        + indented_dispatch
        + "\n    raise AttributeError(name)\n",
        encoding="utf-8",
    )
    core_profile = artifacts / "canonical_profile.py"
    core_profile.write_text(
        "from polisyos.common.canonical_profile import COMMON_PROFILE_REVISION\n"
        'CANONICAL_PROFILE_REVISION = "alpha"\n'
        "load_core_json_artifact = object()\n",
        encoding="utf-8",
    )
    common_profile = common / "canonical_profile.py"
    common_profile.write_text('COMMON_PROFILE_REVISION = "alpha"\n', encoding="utf-8")
    return (
        repo_root,
        facade_path,
        {
            "polisyos.core.artifacts.canonical_profile": core_profile,
            "polisyos.common.canonical_profile": common_profile,
        },
    )


def test_authority_import_closure_actual_core_dispatch_removal_keeps_markers(
    tmp_path: Path,
) -> None:
    """Removing real facade dispatch loses providers while source markers remain."""

    repo, facade, _providers = _write_core_profile_provider_closure_repo(
        tmp_path / "actual-core-facade-removal-repo"
    )
    source = facade.read_text(encoding="utf-8")
    markers = (
        "def __getattr__",
        "load_core_json_artifact",
        'import_module(".canonical_profile", __name__)',
        "getattr(canonical_profile, name)",
    )
    assert all(marker in source for marker in markers)
    with_dispatch = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert "polisyos.core.artifacts.canonical_profile" in with_dispatch
    assert "polisyos.common.canonical_profile" in with_dispatch

    without_dispatch = source.replace(
        "return getattr(canonical_profile, name)",
        "raise AttributeError(name)  # getattr(canonical_profile, name)",
        1,
    )
    assert without_dispatch != source
    assert all(marker in without_dispatch for marker in markers)
    facade.write_text(without_dispatch, encoding="utf-8")
    without_edges = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert "polisyos.core.artifacts.canonical_profile" not in without_edges
    assert "polisyos.common.canonical_profile" not in without_edges


def test_authority_import_closure_hashes_core_and_common_profile_bytes_after_equal_metadata_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both actual provider bodies affect deployment identity despite equal stat metadata."""

    repo, _facade, providers = _write_core_profile_provider_closure_repo(
        tmp_path / "actual-profile-provider-bytes-repo"
    )
    closure = ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")
    assert dict(closure)["polisyos.core.artifacts.canonical_profile"] == (
        "src/polisyos/core/artifacts/canonical_profile.py"
    )
    assert dict(closure)["polisyos.common.canonical_profile"] == (
        "src/polisyos/common/canonical_profile.py"
    )
    monkeypatch.setattr(ledger_module, "__name__", "polisyos.entry")
    monkeypatch.setattr(ledger_module, "_IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE", closure)
    previous_baseline = ledger_module._deployment_baseline(repo)

    for module_name, provider_path in providers.items():
        original = provider_path.read_bytes()
        before = provider_path.stat()
        if module_name == "polisyos.core.artifacts.canonical_profile":
            marker = b'CANONICAL_PROFILE_REVISION = "alpha"'
            replacement = b'CANONICAL_PROFILE_REVISION = "bravo"'
        else:
            marker = b'COMMON_PROFILE_REVISION = "alpha"'
            replacement = b'COMMON_PROFILE_REVISION = "bravo"'
        changed = original.replace(marker, replacement, 1)
        assert changed != original and len(changed) == len(original)
        provider_path.write_bytes(changed)
        os.utime(provider_path, ns=(before.st_atime_ns, before.st_mtime_ns))
        after = provider_path.stat()
        assert after.st_size == before.st_size
        assert after.st_mtime_ns == before.st_mtime_ns
        assert ledger_module._resolve_authority_import_closure(repo, "polisyos.entry") == closure
        current_baseline = ledger_module._deployment_baseline(repo)
        assert current_baseline != previous_baseline
        previous_baseline = current_baseline


def test_authority_import_closure_fails_closed_on_conditional_importlib_alias(
    tmp_path: Path,
) -> None:
    """Conditional import aliases do not prove the getter's provider target."""

    repo, facade = _write_import_module_pep562_closure_repo(
        tmp_path / "conditional-importlib-alias-repo"
    )
    source = facade.read_text(encoding="utf-8")
    changed = source.replace(
        "from importlib import import_module as _load\n",
        "if TYPE_CHECKING:\n    from importlib import import_module as _load\n",
        1,
    )
    assert changed != source
    facade.write_text(changed, encoding="utf-8")
    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_authority_import_closure_fails_closed_on_conditional_provider_assignment(
    tmp_path: Path,
) -> None:
    """An import assigned only below another condition is not the getter proof."""

    repo, facade = _write_import_module_pep562_closure_repo(
        tmp_path / "conditional-provider-assignment-repo"
    )
    source = facade.read_text(encoding="utf-8")
    changed = source.replace(
        '        module = _load("polisyos.facade.provider_one")\n',
        '        if provider_enabled:\n            module = _load("polisyos.facade.provider_one")\n',
        1,
    )
    assert changed != source
    facade.write_text(changed, encoding="utf-8")
    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_authority_import_closure_fails_closed_on_shadowed_getattr(
    tmp_path: Path,
) -> None:
    """A local callable named getattr cannot stand in for builtin attribute lookup."""

    repo, facade = _write_import_module_pep562_closure_repo(
        tmp_path / "shadowed-getattr-provider-repo"
    )
    source = facade.read_text(encoding="utf-8")
    changed = source.replace(
        "def __getattr__(name):\n",
        "def __getattr__(name):\n    getattr = choose_getter\n",
        1,
    )
    assert changed != source
    facade.write_text(changed, encoding="utf-8")
    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_authority_import_closure_fails_closed_when_importlib_alias_is_shadowed(
    tmp_path: Path,
) -> None:
    """A local binding cannot impersonate the imported importlib loader."""

    repo, facade = _write_import_module_pep562_closure_repo(
        tmp_path / "shadowed-importlib-alias-provider-repo"
    )
    baseline = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert baseline["polisyos.facade.provider_one"] == "src/polisyos/facade/provider_one.py"

    source = facade.read_text(encoding="utf-8")
    changed = source.replace(
        '        module = _load("polisyos.facade.provider_one")\n',
        '        _load = choose_import\n        module = _load("polisyos.facade.provider_one")\n',
        1,
    )
    assert changed != source
    facade.write_text(changed, encoding="utf-8")
    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


@pytest.mark.parametrize("route", ["map-free", "map-backed"])
@pytest.mark.parametrize(
    ("binding_kind", "module_binding"),
    [
        pytest.param("function", "def _load(name):\n    return None\n", id="function"),
        pytest.param(
            "async-function", "async def _load(name):\n    return None\n", id="async-function"
        ),
        pytest.param("class", "class _load:\n    pass\n", id="class"),
        pytest.param(
            "exception-capture",
            "try:\n    raise RuntimeError\nexcept RuntimeError as _load:\n    pass\n",
            id="exception-capture",
        ),
        pytest.param(
            "match-capture",
            'match "shadow":\n    case _load:\n        pass\n',
            id="match-capture",
        ),
    ],
)
def test_authority_import_closure_rejects_module_scope_helper_rebinding(
    tmp_path: Path,
    route: str,
    binding_kind: str,
    module_binding: str,
) -> None:
    """Every executable module binding form invalidates a loader alias."""

    if route == "map-free":
        repo, facade = _write_import_module_pep562_closure_repo(
            tmp_path / f"module-{binding_kind}-{route}"
        )
        baseline = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
        assert baseline["polisyos.facade.provider_one"] == ("src/polisyos/facade/provider_one.py")
    else:
        repo, facade = _write_literal_pep562_closure_repo(
            tmp_path / f"module-{binding_kind}-{route}"
        )
        baseline = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
        assert baseline["polisyos.provider_one"] == "src/polisyos/provider_one.py"

    source = facade.read_text(encoding="utf-8")
    marker = "def __getattr__(name):\n"
    assert source.count(marker) == 1
    changed = source.replace(marker, module_binding + marker, 1)
    assert changed != source
    assert "from importlib import import_module as _load" in changed
    assert "def __getattr__(name):" in changed
    facade.write_text(changed, encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_source_scope_bound_names_covers_module_binding_forms_without_imports() -> None:
    """The shared source-scope census includes non-Name binders and can exclude imports."""

    tree = ast.parse(
        "from importlib import import_module as _imported\n"
        "def _function():\n    def _nested():\n        pass\n"
        "async def _async_function():\n    pass\n"
        "class _class:\n    pass\n"
        "try:\n    pass\nexcept Exception as _exception_capture:\n    pass\n"
        "match object():\n    case _match_capture:\n        pass\n"
    )
    names_without_imports = ledger_module._source_scope_bound_names(
        tree.body,
        include_imports=False,
    )
    names_with_imports = ledger_module._source_scope_bound_names(tree.body)
    assert {
        "_function",
        "_async_function",
        "_class",
        "_exception_capture",
        "_match_capture",
    } <= names_without_imports
    assert "_nested" not in names_without_imports
    assert "_imported" not in names_without_imports
    assert "_imported" in names_with_imports


def test_authority_import_closure_rejects_unknown_star_import_binding() -> None:
    """A star import cannot prove it leaves a selected loader alias untouched."""

    tree = ast.parse(
        "from importlib import import_module as _load\n"
        "from polisyos.optional import *\n"
        "def __getattr__(name):\n"
        '    module = _load("polisyos.provider")\n'
        "    return getattr(module, name)\n"
    )
    getter = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "__getattr__"
    )
    assert ledger_module._literal_import_helper_bindings(tree, getter) == (frozenset(), frozenset())


def test_authority_import_closure_fails_closed_when_literal_map_dispatcher_is_shadowed(
    tmp_path: Path,
) -> None:
    """Literal map values do not prove a provider when the admitted loader is shadowed."""

    repo, facade = _write_literal_pep562_closure_repo(tmp_path / "shadowed-map-dispatcher-repo")
    baseline = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert baseline["polisyos.provider_one"] == "src/polisyos/provider_one.py"

    source = facade.read_text(encoding="utf-8")
    changed = source.replace(
        "    module = _load(module_name)\n",
        "    _load = choose_import\n    module = _load(module_name)\n",
        1,
    )
    assert changed != source
    facade.write_text(changed, encoding="utf-8")
    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


@pytest.mark.parametrize(
    "replacement",
    [
        pytest.param(
            "module = choose_import(module_name)",
            id="unrecognized-loader",
        ),
        pytest.param(
            "module = __import__(module_name, fromlist=[attribute_name])",
            id="builtin-import-has-different-return-semantics",
        ),
        pytest.param(
            "module = _load(module_name, __name__)",
            id="relative-package-argument-is-not-map-proof",
        ),
    ],
)
def test_literal_map_rows_do_not_authorize_unproven_getter_loader(
    tmp_path: Path,
    replacement: str,
) -> None:
    """Literal rows remain candidates until the supported importer flow returns them."""

    repo, facade = _write_literal_pep562_closure_repo(tmp_path / "literal-map-unproven-loader")
    source = facade.read_text(encoding="utf-8")
    if replacement == "module = _load(module_name, __name__)":
        source = source.replace('"polisyos.provider_one"', '".provider_one"')
        source = source.replace('"polisyos.provider_two"', '".provider_two"')
    anchor = "    module = _load(module_name)\n"
    changed = source.replace(anchor, f"    {replacement}\n", 1)
    assert changed != source
    assert all(marker in changed for marker in ("_EXPORTS", "_ALIASES", "def __getattr__"))
    facade.write_text(changed, encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_literal_map_rows_do_not_seed_provider_without_getter_binding(
    tmp_path: Path,
) -> None:
    """Map markers and rows alone cannot bind a requested module attribute."""

    repo, facade = _write_literal_pep562_closure_repo(
        tmp_path / "literal-map-candidate-without-binding"
    )
    source = facade.read_text(encoding="utf-8")
    marker = "def __getattr__(name):\n"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        marker
        + '    if name == "One":\n'
        + "        return object()\n"
        + "    if False:\n"
        + "        module = _load(_EXPORTS[name][0])\n"
        + "        return getattr(module, name)\n",
        1,
    )
    assert all(
        marker in source for marker in ("_EXPORTS", "def __getattr__", "getattr(module, name)")
    )
    facade.write_text(source, encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_relative_direct_getter_requires_implicit_package_name_binding(
    tmp_path: Path,
) -> None:
    """A spelling named ``__name__`` is not trusted if the module rebinds it."""

    repo, facade, _providers = _write_core_profile_provider_closure_repo(
        tmp_path / "relative-getter-rebound-package-name"
    )
    source = facade.read_text(encoding="utf-8")
    marker = "from importlib import import_module\n"
    changed = source.replace(marker, marker + '__name__ = "polisyos.counterfeit"\n', 1)
    assert changed != source
    assert 'import_module(".canonical_profile", __name__)' in changed
    facade.write_text(changed, encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


@pytest.mark.parametrize(
    ("anchor", "mutation"),
    [
        pytest.param(
            "from importlib import import_module\n",
            'globals()["__name__"] = "polisyos.counterfeit"\n',
            id="module-initializer",
        ),
        pytest.param(
            "def __getattr__(name: str) -> Any:\n",
            '    globals()["__name__"] = "polisyos.counterfeit"\n',
            id="getter-execution",
        ),
    ],
)
def test_relative_direct_getter_rejects_namespace_write_through_globals(
    tmp_path: Path,
    anchor: str,
    mutation: str,
) -> None:
    """A globals subscript cannot replace the implicit package owner unnoticed."""

    repo, facade, _providers = _write_core_profile_provider_closure_repo(
        tmp_path / "relative-getter-globals-package-write"
    )
    source = facade.read_text(encoding="utf-8")
    changed = source.replace(anchor, anchor + mutation, 1)
    assert changed != source
    assert 'import_module(".canonical_profile", __name__)' in changed
    facade.write_text(changed, encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_map_free_getter_refuses_nested_opaque_expression_effect(
    tmp_path: Path,
) -> None:
    """An opaque nested call cannot be hidden by overwriting its result alias."""

    repo, facade = _write_import_module_pep562_closure_repo(
        tmp_path / "map-free-nested-opaque-effect"
    )
    source = facade.read_text(encoding="utf-8")
    anchor = '        module = _load("polisyos.facade.provider_one")\n'
    replacement = "        _discarded = (_opaque_mutator(),)\n        _discarded = ()\n" + anchor
    changed = source.replace(anchor, replacement, 1)
    assert changed != source
    assert all(
        marker in changed
        for marker in (
            "__getattr__",
            "_load",
            "polisyos.facade.provider_one",
            "getattr(module, name)",
        )
    )
    facade.write_text(changed, encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_owner_closure_adds_literal_dynamic_but_not_type_only_imports(
    tmp_path: Path,
) -> None:
    """Owner mode widens import kinds without widening into typing-only arms."""

    repo_root = tmp_path / "owner-closure-repo"
    package_root = repo_root / "src/polisyos"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    for module_name in ("runtime_dep", "type_dep", "dynamic_dep"):
        (package_root / f"{module_name}.py").write_text("", encoding="utf-8")
    (package_root / "entry.py").write_text(
        """
import importlib
from typing import TYPE_CHECKING

import polisyos.runtime_dep

if TYPE_CHECKING:
    import polisyos.type_dep

def load_dynamic() -> object:
    return importlib.import_module("polisyos.dynamic_dep")
""",
        encoding="utf-8",
    )

    runtime_closure = dict(
        ledger_module._resolve_authority_import_closure(
            repo_root,
            "polisyos.entry",
        )
    )
    owner_closure = dict(
        ledger_module._resolve_authority_import_closure(
            repo_root,
            "polisyos.entry",
            include_tools=True,
        )
    )

    assert "polisyos.runtime_dep" in runtime_closure
    assert "polisyos.dynamic_dep" not in runtime_closure
    assert "polisyos.type_dep" not in runtime_closure
    assert "polisyos.runtime_dep" in owner_closure
    assert "polisyos.dynamic_dep" in owner_closure
    assert "polisyos.type_dep" not in owner_closure


def test_authority_session_paths_do_not_invoke_unadmitted_literal_dynamic_imports() -> None:
    """A derived dynamic target may stay outside only while the real path is dormant."""

    script = """
import ast
import importlib
import json
import tempfile
from pathlib import Path

import_module_calls = []
original_import_module = importlib.import_module
def recording_import_module(name, package=None):
    import_module_calls.append(name)
    return original_import_module(name, package)
importlib.import_module = recording_import_module

from polisyos.runtime.quality import confidence_ledger as ledger
from polisyos.core.artifacts import FileSystemCAS

repo_root = Path.cwd()
closure = dict(
    ledger._resolve_authority_import_closure(repo_root, ledger.__name__)
)
literal_dynamic_refs = set()
for relative_path in closure.values():
    tree = ast.parse((repo_root / relative_path).read_bytes())
    for node in ledger._runtime_ast_nodes(tree):
        if not isinstance(node, ast.Call):
            continue
        dynamic_ref = ledger._literal_dynamic_import_ref(node)
        if isinstance(dynamic_ref, str) and dynamic_ref.startswith("polisyos."):
            literal_dynamic_refs.add(dynamic_ref)
unadmitted = literal_dynamic_refs - closure.keys()
assert unadmitted
deployment_identity = ledger._policy_engine_deployment_identity(repo_root)

scope = ledger.ConfidenceRiskBudgetScope(
    scope_owner_ref="polisyos.runtime.quality.promotion_sequence",
    authority_purpose="n9_promotion",
    owner_scope_key=(
        "design-problem:dynamic-import-residual:"
        + deployment_identity.rpartition(":")[2]
    ),
    owner_projection_hash="sha256:" + "1" * 64,
    epoch_ref=None,
    model_ref=None,
    rule_ref="policyos.layer3.gy.n9.v1",
    schema_ref="polisyos.runtime.design_problem.v1",
)
with tempfile.TemporaryDirectory() as temporary:
    temporary_root = Path(temporary)
    ledger.ConfidenceLedgerSession._for_verification(
        repo_root,
        risk_scope=scope,
        artifact_store=FileSystemCAS(temporary_root / "cas"),
        state_root=temporary_root / "state",
    )
    ledger.ConfidenceLedgerSession.from_repo(repo_root, risk_scope=scope)

observed = set(import_module_calls) & unadmitted
print(json.dumps({
    "literal_dynamic_ref_count": len(literal_dynamic_refs),
    "unadmitted_count": len(unadmitted),
    "observed": sorted(observed),
}, sort_keys=True))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert payload["literal_dynamic_ref_count"] == payload["unadmitted_count"]
    assert payload["unadmitted_count"] > 0
    assert payload["observed"] == []


def test_loaded_code_manifest_fails_closed_on_missing_declared_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared closure member cannot disappear behind a partial manifest."""

    module_name, relative_path = next(
        row
        for row in reversed(ledger_module._IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE)
        if row[0] != ledger_module.__name__ and row[0] in sys.modules
    )
    monkeypatch.delitem(sys.modules, module_name)

    with pytest.raises(
        ConfidenceLedgerError,
        match="canonical_loaded_runtime_mismatch",
    ):
        ledger_module._loaded_code_manifest(
            REPO_ROOT,
            ((module_name, relative_path),),
        )


def test_code_normalization_cache_reuses_only_code_objects_within_one_context() -> None:
    """Memoize immutable nested code trees without memoizing function bindings."""

    module_code = compile(
        "def outer(flag):\n"
        "    def inner(value=3):\n"
        "        return value + 1 if flag else value\n"
        "    return inner\n",
        "<code-normalization-cache-test>",
        "exec",
    )
    code_objects: list[types.CodeType] = []

    def collect(code: types.CodeType) -> None:
        code_objects.append(code)
        for constant in code.co_consts:
            if isinstance(constant, types.CodeType):
                collect(constant)

    collect(module_code)
    expected = ledger_module._normalize_code_object(module_code)
    cache = ledger_module._CodeNormalizationCache()

    cached = ledger_module._normalize_code_object(module_code, code_cache=cache)
    count_after_first = len(cache._normalized_by_identity)
    repeated = ledger_module._normalize_code_object(module_code, code_cache=cache)
    independent = ledger_module._CodeNormalizationCache()
    separate_pass = ledger_module._normalize_code_object(module_code, code_cache=independent)

    assert cached == expected
    assert repeated is cached
    assert count_after_first == len(code_objects)
    assert len(cache._normalized_by_identity) == count_after_first
    assert separate_pass == expected
    assert separate_pass is not cached


def test_loaded_code_integrity_parses_each_source_content_once_per_assertion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The full check shares ASTs without merging distinct UTF-8 parsing contracts."""

    expected_contents = {
        ledger_module._bytes_hash((REPO_ROOT / relative_path).read_bytes())
        for _module_name, relative_path in ledger_module._IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE
    }
    parse_counts: dict[str, int] = {}
    original_parse = ledger_module.ast.parse

    def counted_parse(source: str | bytes, *args: object, **kwargs: object) -> ast.AST:
        source_bytes = source if isinstance(source, bytes) else source.encode("utf-8")
        digest = ledger_module._bytes_hash(source_bytes)
        parse_counts[digest] = parse_counts.get(digest, 0) + 1
        return original_parse(source, *args, **kwargs)

    monkeypatch.setattr(ledger_module.ast, "parse", counted_parse)

    ledger_module._assert_ledger_artifact_contracts_current()

    assert set(parse_counts) == expected_contents
    ledger_hash = ledger_module._bytes_hash(
        (REPO_ROOT / "src/polisyos/runtime/quality/confidence_ledger.py").read_bytes()
    )
    assert parse_counts[ledger_hash] == 2
    assert {digest: count for digest, count in parse_counts.items() if digest != ledger_hash} == {
        digest: 1 for digest in expected_contents if digest != ledger_hash
    }


def test_loaded_code_manifest_rejects_source_changes_during_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Source-derived AST evidence cannot be paired with different ending bytes."""

    source_path = ledger_module._LEDGER_MODULE_SOURCE_PATH
    original_read_bytes = Path.read_bytes
    source_reads = 0

    def changed_on_second_read(path: Path) -> bytes:
        nonlocal source_reads
        content = original_read_bytes(path)
        if path.resolve() == source_path:
            source_reads += 1
            if source_reads == 2:
                return content + b"\n# changed while loaded-code analysis was running\n"
        return content

    monkeypatch.setattr(Path, "read_bytes", changed_on_second_read)

    with pytest.raises(ConfidenceLedgerError, match="canonical_loaded_runtime_mismatch"):
        ledger_module._loaded_code_manifest(
            REPO_ROOT,
            ((ledger_module.__name__, "src/polisyos/runtime/quality/confidence_ledger.py"),),
        )

    assert source_reads == 2


def test_loaded_code_manifest_uses_pinned_source_bytes_not_loader_code_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing loader.get_code cannot substitute for compiling pinned source bytes."""

    from polisyos.core.artifacts import store as store_module

    closure = ((store_module.__name__, "src/polisyos/core/artifacts/store.py"),)
    original_manifest, original_consistent = ledger_module._loaded_code_manifest(
        REPO_ROOT,
        closure,
    )
    if not original_consistent:
        pytest.fail("baseline loaded code should match its pinned source")
    spec = store_module.__spec__
    if spec is None:
        pytest.fail("store module must have a source spec")
    loader = spec.loader
    if not isinstance(loader, SourceFileLoader):
        pytest.fail("store module must use the source loader")

    def forged_code(_module_name: str) -> types.CodeType:
        return compile("pass\n", "<forged-loader-code>", "exec")

    monkeypatch.setattr(loader, "get_code", forged_code)
    current_manifest, current_consistent = ledger_module._loaded_code_manifest(
        REPO_ROOT,
        closure,
    )
    if not current_consistent:
        pytest.fail("loader.get_code must not control the source-bound manifest")
    if current_manifest != original_manifest:
        pytest.fail("source-bound manifest changed after loader.get_code was forged")


def test_selected_importer_alias_rebind_refuses_before_cas_and_fresh_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persisted read is valid, while rebinding the protected writer stops before bytes."""

    repo_root = tmp_path / "source-bound-authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    scope = _scope(owner_scope_key=f"design-problem:source-bound-importer:{time.time_ns()}")

    first = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=scope)
    first_check = first.execute_check(_prepare(first, request_key="source-bound-positive"))
    first_receipt = first.receipt()
    reopened = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=scope)
    reopened_receipt = reopened.receipt()
    if reopened_receipt.head_event_id != first_receipt.head_event_id:
        pytest.fail("fresh public reader did not reopen the persisted head")
    if reopened_receipt.events[-1].event_ref != first_receipt.events[-1].event_ref:
        pytest.fail("fresh public reader did not reopen the persisted event ref")
    if first_check.event_ref != first_receipt.events[-1].event_ref:
        pytest.fail("producer result did not bind to the persisted event")

    prepared = _prepare(reopened, request_key="source-bound-alias-rebind")
    state_root = repo_root / ".polisyos"

    def snapshot_state() -> dict[str, str]:
        return {
            path.relative_to(state_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(state_root.rglob("*"))
            if path.is_file()
        }

    before = snapshot_state()
    monkeypatch.setattr(ledger_module, "atomic_write_json", lambda *_args, **_kwargs: None)
    with pytest.raises(ConfidenceLedgerError) as exc_info:
        reopened.execute_check(prepared)
    if exc_info.value.code != "canonical_loaded_runtime_mismatch":
        pytest.fail("rebound importer must fail with the typed runtime mismatch")
    if snapshot_state() != before:
        pytest.fail("rebound importer changed canonical storage before refusal")


def test_loaded_code_manifest_rechecks_live_loader_and_callable_slot_after_prior_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prior passing manifest does not authorize a later loader or slot mutation."""

    from polisyos.core.artifacts import store as store_module

    relative_path = "src/polisyos/core/artifacts/store.py"
    closure = ((store_module.__name__, relative_path),)
    original_manifest, original_consistent = ledger_module._loaded_code_manifest(
        REPO_ROOT,
        closure,
    )
    assert original_consistent is True
    slots = json.loads(original_manifest)[store_module.__name__]["loader_owned_callable_slots"]
    target_qualname, target_row = next(
        (qualname, row)
        for qualname, row in sorted(slots.items())
        if row["owner_path"] and row["matches_loader_slot"] is True
    )
    owner: object = store_module
    for component in target_row["owner_path"]:
        owner = getattr(owner, component)
    binding_name = target_qualname.rsplit(".", 1)[-1]

    monkeypatch.delattr(owner, binding_name)
    _changed_manifest, changed_consistent = ledger_module._loaded_code_manifest(
        REPO_ROOT,
        closure,
    )

    assert changed_consistent is False


def test_loaded_code_manifest_rejects_live_code_patch_after_prior_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh manifest compares live code even when the slot itself remains present."""

    from polisyos.core.artifacts import store as store_module

    relative_path = "src/polisyos/core/artifacts/store.py"
    closure = ((store_module.__name__, relative_path),)
    _manifest, original_consistent = ledger_module._loaded_code_manifest(REPO_ROOT, closure)
    assert original_consistent is True

    target = store_module.FileSystemCAS.put_bytes
    original_code = target.__code__
    replacement_module_code = compile(
        "def put_bytes(self, data, opts, *, return_selected_profile=False):\n    return None\n",
        original_code.co_filename,
        "exec",
    )
    replacement_code = next(
        constant
        for constant in replacement_module_code.co_consts
        if isinstance(constant, types.CodeType) and constant.co_name == "put_bytes"
    ).replace(
        co_name=original_code.co_name,
        co_qualname=original_code.co_qualname,
        co_filename=original_code.co_filename,
        co_firstlineno=original_code.co_firstlineno,
    )
    monkeypatch.setattr(target, "__code__", replacement_code)

    _changed_manifest, changed_consistent = ledger_module._loaded_code_manifest(REPO_ROOT, closure)

    assert changed_consistent is False


def test_loaded_code_manifest_rejects_removed_live_loader_after_prior_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A previous positive does not survive loss of the module's real loader."""

    from polisyos.core.artifacts import store as store_module

    relative_path = "src/polisyos/core/artifacts/store.py"
    closure = ((store_module.__name__, relative_path),)
    _manifest, original_consistent = ledger_module._loaded_code_manifest(REPO_ROOT, closure)
    assert original_consistent is True
    assert store_module.__spec__ is not None
    monkeypatch.setattr(store_module.__spec__, "loader", object())

    with pytest.raises(ConfidenceLedgerError, match="canonical_loaded_runtime_mismatch"):
        ledger_module._loaded_code_manifest(REPO_ROOT, closure)


def test_integrity_assertion_rechecks_live_function_defaults_after_prior_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only code objects are memoized; live function defaults are observed again."""

    ledger_module._assert_ledger_artifact_contracts_current()
    function = ledger_module._normalize_function_binding
    changed_kwdefaults = dict(function.__kwdefaults__ or {})
    assert "seen" in changed_kwdefaults
    changed_kwdefaults["seen"] = frozenset()
    monkeypatch.setattr(function, "__kwdefaults__", changed_kwdefaults)

    with pytest.raises(ConfidenceLedgerError, match="canonical_loaded_runtime_mismatch"):
        ledger_module._assert_ledger_artifact_contracts_current()


def test_source_derived_transactional_closures_cover_live_cas_and_every_declared_method(
    tmp_path: Path,
) -> None:
    """A real CAS read and every source-declared wrapper reconcile to loader code."""

    from polisyos.core.artifacts import store as store_module

    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        b"source-derived transactional closure",
        PutOptions(kind="test.source-derived", media_type="application/octet-stream"),
    )
    assert store.has(ref)
    assert store.get_bytes(ref) == b"source-derived transactional closure"
    assert store.verify(ref).ok

    relative_path = "src/polisyos/core/artifacts/store.py"
    source_tree = ast.parse((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
    owner = next(
        node
        for node in source_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "FileSystemCAS"
    )
    declared = {
        node.name
        for node in owner.body
        if isinstance(node, ast.FunctionDef)
        and any(
            (isinstance(decorator, ast.Name) and decorator.id == "_transactional_read")
            or (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Name)
                and decorator.func.id == "_transactional_read"
            )
            for decorator in node.decorator_list
        )
    }
    assert declared

    raw_manifest, consistent = ledger_module._loaded_code_manifest(
        REPO_ROOT,
        ((store_module.__name__, relative_path),),
    )
    assert consistent
    module_row = json.loads(raw_manifest)[store_module.__name__]
    slots = module_row["loader_owned_callable_slots"]
    assert {f"FileSystemCAS.{name}" for name in declared} <= set(slots)
    assert all(slots[f"FileSystemCAS.{name}"]["matches_loader_slot"] for name in declared)


def test_every_transactional_wrapper_capture_and_imported_reference_poison_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every wrapper cell and a poisoned imported selector type reject admission."""

    from polisyos.core.artifacts import store as store_module

    relative_path = "src/polisyos/core/artifacts/store.py"
    original = store_module.FileSystemCAS._load_verified_snapshot
    freevars = original.__code__.co_freevars
    closure = original.__closure__ or ()
    assert len(freevars) == len(closure)
    assert freevars

    def make_cell(value: object) -> object:
        return (lambda: value).__closure__[0]

    def poisoned_value(value: object) -> object:
        if value is original.__wrapped__:
            return None
        if type(value) is bool:
            return not value
        if type(value) is int:
            return value + 1
        if type(value) is str:
            return value + "__tampered__"
        if isinstance(value, inspect.Signature):
            return inspect.Signature()
        if isinstance(value, inspect.Parameter):
            return inspect.Parameter(
                name=value.name + "__tampered__",
                kind=value.kind,
            )
        return object()

    for index, name in enumerate(freevars):
        cells = list(closure)
        cells[index] = make_cell(poisoned_value(closure[index].cell_contents))
        replacement = types.FunctionType(
            original.__code__,
            original.__globals__,
            original.__name__,
            original.__defaults__,
            tuple(cells),
        )
        replacement.__module__ = original.__module__
        replacement.__qualname__ = original.__qualname__
        replacement.__doc__ = original.__doc__
        replacement.__kwdefaults__ = original.__kwdefaults__
        replacement.__annotations__ = dict(original.__annotations__)
        replacement.__dict__.update(original.__dict__)
        with monkeypatch.context() as mutation:
            mutation.setattr(
                store_module.FileSystemCAS,
                "_load_verified_snapshot",
                replacement,
            )
            _manifest, consistent = ledger_module._loaded_code_manifest(
                REPO_ROOT,
                ((store_module.__name__, relative_path),),
            )
            assert not consistent, f"tampered closure cell admitted: {name}"

    with monkeypatch.context() as mutation:
        mutation.setattr(store_module, "ArtifactRef", str)
        _manifest, consistent = ledger_module._loaded_code_manifest(
            REPO_ROOT,
            ((store_module.__name__, relative_path),),
        )
        assert not consistent


def test_rehashed_closure_manifest_cannot_narrow_authority_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A self-consistent substitute closure is not authority evidence."""

    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    resolved_closure = ledger_module._resolve_authority_import_closure(
        repo_root,
        ledger_module.__name__,
    )
    removed_module = next(
        module_name
        for module_name, _relative_path in reversed(resolved_closure)
        if module_name != ledger_module.__name__
    )
    forged_closure = tuple(row for row in resolved_closure if row[0] != removed_module)
    forged_manifest = json.loads(ledger_module._IMPORT_TIME_LOADED_CODE_MANIFEST)
    del forged_manifest[removed_module]
    monkeypatch.setattr(
        ledger_module,
        "_IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE",
        forged_closure,
    )
    monkeypatch.setattr(
        ledger_module,
        "_IMPORT_TIME_LOADED_CODE_MANIFEST",
        ledger_module._canonical_json(forged_manifest),
    )
    monkeypatch.setattr(ledger_module, "_IMPORT_TIME_LOADED_CODE_CONSISTENT", True)

    with pytest.raises(
        ConfidenceLedgerError,
        match="canonical_loaded_runtime_mismatch",
    ):
        ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())


def test_rehashed_loaded_code_manifest_cannot_replace_runtime_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A complete manifest with forged content is not runtime evidence."""

    forged_manifest = json.loads(ledger_module._IMPORT_TIME_LOADED_CODE_MANIFEST)
    module_name = min(forged_manifest)
    forged_manifest[module_name]["source_hash"] = "sha256:" + "0" * 64
    monkeypatch.setattr(
        ledger_module,
        "_IMPORT_TIME_LOADED_CODE_MANIFEST",
        ledger_module._canonical_json(forged_manifest),
    )
    monkeypatch.setattr(ledger_module, "_IMPORT_TIME_LOADED_CODE_CONSISTENT", True)

    with pytest.raises(
        ConfidenceLedgerError,
        match="canonical_loaded_runtime_mismatch",
    ):
        ledger_module._admit_loaded_runtime(REPO_ROOT)


def test_mid_operation_deployment_drift_poison_is_irreversible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch, drift_after_state_load=True)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    history = session.observe_history()
    kernel = repo_root / "src/polisyos/core/canon/canon_json.py"
    kernel_bytes = kernel.read_bytes()
    drift_marker = session._state_root / "inject-deployment-drift-on-load"
    drift_marker.touch()
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


def test_unavailable_mid_operation_deployment_identity_does_not_poison_recovered_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail closed on an unreadable snapshot without recording unobserved drift."""

    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch, drift_after_state_load=True)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    history = session.observe_history()
    kernel = repo_root / "src/polisyos/core/canon/canon_json.py"
    kernel_bytes = kernel.read_bytes()
    drift_marker = session._state_root / "inject-deployment-drift-on-load"
    drift_marker.touch()
    original_read_bytes = Path.read_bytes
    snapshot_read_failures = 0

    def fail_once_for_changed_kernel(path: Path) -> bytes:
        nonlocal snapshot_read_failures
        if (
            path.resolve() == kernel.resolve()
            and snapshot_read_failures == 0
            and path.stat().st_size > len(kernel_bytes)
        ):
            snapshot_read_failures += 1
            # Model an atomic repair/replacement winning the race before the
            # enclosing operation performs its final integrity check.
            path.write_bytes(kernel_bytes)
            raise OSError("transient source snapshot read failure")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_once_for_changed_kernel)
    try:
        with pytest.raises(
            ConfidenceLedgerError,
            match="canonical_deployment_identity_invalid",
        ):
            session.prepare_check(
                history_token=history,
                request_key="request://unit/unavailable-mid-operation-snapshot",
                obligation_class=PromotionObligationClass.CALIBRATION,
                instrument_id="constant_unit_e_process",
                certificate_ref="construction://constant-unit-e-process/unavailable",
                claim=_claim(),
            )
    finally:
        kernel.write_bytes(kernel_bytes)

    assert snapshot_read_failures == 1
    recovered = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    recovered.observe_history()


def test_deployment_drift_poison_rejects_equal_expected_and_observed_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())

    with (
        session._exclusive_lock(),
        pytest.raises(ConfidenceLedgerError, match="deployment_drift_poison_invalid"),
    ):
        session._persist_deployment_drift_poison_locked(session._deployment_identity)


def test_historical_deployment_drift_poison_is_terminal_for_newer_session_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "authority-repo"
    _install_loaded_deployment(repo_root, monkeypatch)
    session = ConfidenceLedgerSession.from_repo(repo_root, risk_scope=_scope())
    observed = ledger_module._identity(
        "policy-engine-deployment",
        {"status": "changed"},
    )
    with session._exclusive_lock():
        session._persist_deployment_drift_poison_locked(observed)

    object.__setattr__(
        session,
        "_deployment_identity",
        ledger_module._identity("policy-engine-deployment", {"status": "newer"}),
    )

    with pytest.raises(ConfidenceLedgerError, match="deployment_drift_poisoned"):
        session._assert_no_deployment_drift_poison_locked()


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
    anchor_blob, anchor_manifest = session._artifact_store._paths(
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
        blob, manifest = session._artifact_store._paths(ArtifactID.model_validate(artifact_ref))
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


def test_prior_scope_inventory_failure_is_not_treated_as_absence(
    tmp_path: Path,
) -> None:
    factory = _SessionFactory(tmp_path)
    primer = factory(scope=_scope(owner_scope_key="design-problem:inventory-primer"))
    anchor_ref = ledger_module._cas_json_artifact_ref(primer._scope_anchor_payload())
    blob, manifest = factory.store._paths(ArtifactID.model_validate(anchor_ref))
    blob.unlink()
    manifest.unlink()

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        factory(scope=_scope(owner_scope_key="design-problem:inventory-unknown-target"))

    assert exc_info.value.code == "prior_scope_membership_not_established"
    assert "cas_inventory_blob_missing" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ArtifactIntegrityError)


_SCOPE_BOUND_LEDGER_CONTRACTS = tuple(
    contract_id
    for contract_id, contract in ledger_module._LEDGER_ARTIFACT_CONTRACTS.items()
    if contract.scope_bound
)


@pytest.mark.parametrize("contract_id", _SCOPE_BOUND_LEDGER_CONTRACTS)
def test_prior_scope_inventory_rejects_minimal_rehashed_payload_for_every_scope_contract(
    tmp_path: Path,
    contract_id: str,
) -> None:
    factory = _SessionFactory(tmp_path)
    target_scope = _scope(owner_scope_key=f"design-problem:minimal-{contract_id}")
    target = factory(scope=target_scope)
    _remove_scope_bootstrap_artifacts(target)

    contract = ledger_module._ledger_artifact_contract(contract_id)
    assert contract.scope_bound
    forged = {"scope_id": target_scope.scope_id}
    forged_ref = target._put_ledger_json(forged, contract_id=contract_id)
    artifact_ref = str(forged_ref.artifact_id)
    manifest = target._artifact_store.get_manifest(artifact_ref)
    assert artifact_ref == ledger_module._cas_json_artifact_ref(forged)
    assert manifest.kind == contract.kind
    assert manifest.artifact_schema == contract.schema
    assert manifest.producer == contract.producer
    assert manifest.media_type == contract.media_type

    changed_projection = target_scope.model_copy(update={"owner_projection_hash": _HASH_2})
    with pytest.raises(ConfidenceLedgerError) as exc_info:
        factory(scope=changed_projection)

    assert exc_info.value.code == "prior_scope_membership_not_established"
    assert not target._head_path.exists()
    assert not target._scope_tombstone_path.exists()


_LEDGER_CONTRACT_MUTATION_FIELDS = (
    "kind",
    "schema",
    "producer",
    "media_type",
    "scope_bound",
    "payload_model",
)


def _changed_ledger_contract(
    contract: ledger_module._LedgerArtifactContract, field_name: str
) -> ledger_module._LedgerArtifactContract:
    if field_name == "kind":
        return dataclasses.replace(contract, kind=contract.kind + ".forged")
    if field_name == "schema":
        return dataclasses.replace(
            contract,
            schema=ledger_module.artifacts.SchemaInfo(
                name=contract.schema.name + ".forged",
                version=contract.schema.version,
            ),
        )
    if field_name == "producer":
        return dataclasses.replace(
            contract,
            producer=ledger_module.artifacts.ProducerInfo(
                component="forged.confidence.ledger",
                version=contract.producer.version,
            ),
        )
    if field_name == "media_type":
        return dataclasses.replace(contract, media_type="text/plain")
    if field_name == "scope_bound":
        return dataclasses.replace(contract, scope_bound=not contract.scope_bound)
    replacement_model = (
        ledger_module.ConfidenceLedgerRoot if contract.payload_model is None else None
    )
    if replacement_model is contract.payload_model:
        replacement_model = ledger_module.ConfidenceLedgerRegistry
    return dataclasses.replace(contract, payload_model=replacement_model)


@pytest.mark.parametrize("contract_id", tuple(ledger_module._LEDGER_ARTIFACT_CONTRACTS))
@pytest.mark.parametrize("field_name", _LEDGER_CONTRACT_MUTATION_FIELDS)
def test_import_pinned_contract_rejects_each_registry_derived_mutation(
    tmp_path: Path,
    contract_id: str,
    field_name: str,
) -> None:
    original = ledger_module._LEDGER_ARTIFACT_CONTRACTS
    changed = dict(original)
    changed[contract_id] = _changed_ledger_contract(changed[contract_id], field_name)
    ledger_module._LEDGER_ARTIFACT_CONTRACTS = types.MappingProxyType(changed)
    factory = _SessionFactory(tmp_path)
    scope = _scope(owner_scope_key=f"design-problem:contract-{contract_id}-{field_name}")
    try:
        with pytest.raises(ConfidenceLedgerError) as exc_info:
            ledger_module._assert_ledger_artifact_contracts_current()
        assert exc_info.value.code == "canonical_loaded_runtime_mismatch"
        with pytest.raises(ConfidenceLedgerError) as admission_info:
            factory(scope=scope)
        assert admission_info.value.code == "canonical_loaded_runtime_mismatch"
        assert not factory.state_root.exists()
    finally:
        ledger_module._LEDGER_ARTIFACT_CONTRACTS = original


@pytest.mark.parametrize(
    "binding_name",
    [
        "_LEDGER_PRODUCER",
        "_LEDGER_ARTIFACT_MEDIA_TYPE",
        "_SCOPE_ANCHOR_SCHEMA",
        "_CAS_CANON_SPEC",
        "CONFIDENCE_LEDGER_SCHEMA_VERSION",
        "CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION",
    ],
)
def test_import_pinned_global_dependency_rejects_runtime_rebinding(
    binding_name: str,
) -> None:
    original = getattr(ledger_module, binding_name)
    replacements: dict[str, object] = {
        "_LEDGER_PRODUCER": ledger_module.artifacts.ProducerInfo(
            component="forged.confidence.ledger", version="1.0.0"
        ),
        "_LEDGER_ARTIFACT_MEDIA_TYPE": "text/plain",
        "_SCOPE_ANCHOR_SCHEMA": ledger_module.artifacts.SchemaInfo(
            name="forged.scope-anchor", version="9.9.9"
        ),
        "_CAS_CANON_SPEC": ledger_module.canon.CanonSpec(exclude_none=True),
        "CONFIDENCE_LEDGER_SCHEMA_VERSION": "policyos.runtime.confidence_ledger.forged",
        "CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION": "policyos.runtime.confidence_ledger.registry.forged",
    }
    setattr(ledger_module, binding_name, replacements[binding_name])
    try:
        with pytest.raises(ConfidenceLedgerError) as exc_info:
            ledger_module._assert_ledger_artifact_contracts_current()
        assert exc_info.value.code == "canonical_loaded_runtime_mismatch"
    finally:
        setattr(ledger_module, binding_name, original)


@pytest.mark.parametrize("contract_id", tuple(ledger_module._LEDGER_ARTIFACT_CONTRACTS))
@pytest.mark.parametrize("field_name", _LEDGER_CONTRACT_MUTATION_FIELDS)
def test_registry_mutation_after_admission_fails_before_any_new_head_or_tombstone(
    tmp_path: Path,
    contract_id: str,
    field_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _SessionFactory(tmp_path)
    scope = _scope(owner_scope_key=f"design-problem:after-admission-{contract_id}-{field_name}")
    session = factory(scope=scope)
    previous_head = session._head_path.read_bytes()
    previous_tombstone = session._scope_tombstone_path.read_bytes()
    changed = dict(ledger_module._LEDGER_ARTIFACT_CONTRACTS)
    changed[contract_id] = _changed_ledger_contract(changed[contract_id], field_name)
    monkeypatch.setattr(
        ledger_module, "_LEDGER_ARTIFACT_CONTRACTS", types.MappingProxyType(changed)
    )

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        session.receipt()

    assert exc_info.value.code == "canonical_loaded_runtime_mismatch"
    assert session._head_path.read_bytes() == previous_head
    assert session._scope_tombstone_path.read_bytes() == previous_tombstone


def test_transitive_registered_model_field_mutation_fails_before_receipt_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _SessionFactory(tmp_path)
    session = factory(scope=_scope(owner_scope_key="design-problem:model-field-currentness"))
    previous_head = session._head_path.read_bytes()
    previous_tombstone = session._scope_tombstone_path.read_bytes()
    models = ledger_module._ledger_model_dependencies(ledger_module._LEDGER_ARTIFACT_CONTRACTS)
    model = next(item for item in models if item.model_fields)
    field_name = next(iter(model.model_fields))
    monkeypatch.delitem(model.model_fields, field_name)

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        session.receipt()

    assert exc_info.value.code == "canonical_loaded_runtime_mismatch"
    assert session._head_path.read_bytes() == previous_head
    assert session._scope_tombstone_path.read_bytes() == previous_tombstone


@pytest.mark.parametrize(
    "binding_name",
    [
        "_IMPORT_TIME_LEDGER_CONTRACT_SOURCE_HASH",
        "_IMPORT_TIME_LEDGER_CONTRACT_PROJECTION",
        "_IMPORT_TIME_LEDGER_MODEL_PROJECTION",
        "_IMPORT_TIME_LEDGER_CANON_PROJECTION",
        "_IMPORT_TIME_LEDGER_SNAPSHOT_PROJECTION",
        "_IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS",
        "_IMPORT_TIME_LEDGER_CANON_SPEC",
    ],
)
def test_import_time_contract_snapshot_rebinding_fails_before_admission(
    tmp_path: Path,
    binding_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _SessionFactory(tmp_path)
    replacement: object = {
        "_IMPORT_TIME_LEDGER_CONTRACT_SOURCE_HASH": "sha256:" + "0" * 64,
        "_IMPORT_TIME_LEDGER_CONTRACT_PROJECTION": "{}",
        "_IMPORT_TIME_LEDGER_MODEL_PROJECTION": "{}",
        "_IMPORT_TIME_LEDGER_CANON_PROJECTION": "{}",
        "_IMPORT_TIME_LEDGER_SNAPSHOT_PROJECTION": "{}",
        "_IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS": types.MappingProxyType({}),
        "_IMPORT_TIME_LEDGER_CANON_SPEC": ledger_module.canon.CanonSpec(exclude_none=True),
    }[binding_name]
    monkeypatch.setattr(ledger_module, binding_name, replacement)

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        factory(scope=_scope(owner_scope_key=f"design-problem:rebound-{binding_name}"))

    assert exc_info.value.code == "canonical_loaded_runtime_mismatch"
    assert not factory.state_root.exists()


@pytest.mark.parametrize("nested_binding", ["schema.name", "producer.component"])
def test_mutated_import_pinned_contract_fields_fail_before_receipt_replay(
    tmp_path: Path,
    nested_binding: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _SessionFactory(tmp_path)
    session = factory(scope=_scope(owner_scope_key=f"design-problem:pinned-{nested_binding}"))
    previous_head = session._head_path.read_bytes()
    previous_tombstone = session._scope_tombstone_path.read_bytes()
    pinned_event = ledger_module._IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS["event"]
    owner, attribute = nested_binding.split(".", maxsplit=1)
    monkeypatch.setattr(getattr(pinned_event, owner), attribute, "forged.contract.value")

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        session.receipt()

    assert exc_info.value.code == "canonical_loaded_runtime_mismatch"
    assert session._head_path.read_bytes() == previous_head
    assert session._scope_tombstone_path.read_bytes() == previous_tombstone


def test_transitive_registered_model_config_mutation_fails_before_receipt_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _SessionFactory(tmp_path)
    session = factory(scope=_scope(owner_scope_key="design-problem:model-config-currentness"))
    previous_head = session._head_path.read_bytes()
    previous_tombstone = session._scope_tombstone_path.read_bytes()
    model = next(
        item
        for item in ledger_module._ledger_model_dependencies(
            ledger_module._LEDGER_ARTIFACT_CONTRACTS
        )
        if item.model_config.get("extra") != "allow"
    )
    original_extra = model.model_config.get("extra")
    assert original_extra != "allow"
    monkeypatch.setitem(model.model_config, "extra", "allow")

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        session.receipt()

    assert exc_info.value.code == "canonical_loaded_runtime_mismatch"
    assert session._head_path.read_bytes() == previous_head
    assert session._scope_tombstone_path.read_bytes() == previous_tombstone
    assert model.model_config["extra"] == "allow"


def test_post_admission_rebased_contract_baseline_fails_before_prior_membership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rebinding both contract snapshots cannot make a genuine orphan disappear."""

    factory = _SessionFactory(tmp_path)
    target_scope = _scope(owner_scope_key="design-problem:rebased-contract-baseline")
    target = factory(scope=target_scope)
    target.execute_check(_prepare(target))
    event_witnesses = _scope_event_cas_witnesses(target)
    _remove_scope_bootstrap_artifacts(target)
    target._journal_path.unlink(missing_ok=True)
    _assert_scope_event_cas_witnesses_unchanged(target, event_witnesses)

    changed = dict(ledger_module._LEDGER_ARTIFACT_CONTRACTS)
    changed["event"] = dataclasses.replace(changed["event"], scope_bound=False)
    rebound_contracts = types.MappingProxyType(changed)
    rebound_snapshot = ledger_module._snapshot_ledger_contracts(rebound_contracts)
    monkeypatch.setattr(ledger_module, "_LEDGER_ARTIFACT_CONTRACTS", rebound_contracts)
    monkeypatch.setattr(
        ledger_module,
        "_IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS",
        rebound_snapshot,
    )

    contract_projection = ledger_module._runtime_ledger_contract_projection()
    model_projection = ledger_module._ledger_model_projection(rebound_contracts)
    snapshot_projection = ledger_module._runtime_ledger_snapshot_projection(rebound_snapshot)
    monkeypatch.setattr(
        ledger_module,
        "_IMPORT_TIME_LEDGER_CONTRACT_PROJECTION",
        contract_projection,
    )
    monkeypatch.setattr(
        ledger_module,
        "_IMPORT_TIME_LEDGER_MODEL_PROJECTION",
        model_projection,
    )
    monkeypatch.setattr(
        ledger_module,
        "_IMPORT_TIME_LEDGER_SNAPSHOT_PROJECTION",
        snapshot_projection,
    )

    guard = ledger_module._assert_ledger_artifact_contracts_current
    defaults = list(guard.__defaults__ or ())
    assert len(defaults) >= 7
    defaults[2] = contract_projection
    defaults[3] = model_projection
    defaults[5] = rebound_snapshot
    defaults[6] = snapshot_projection
    monkeypatch.setattr(guard, "__defaults__", tuple(defaults))

    # A fresh caller exercises constructor/admission with the old manifest still
    # pinned; the same session would fail earlier at its stale in-memory WAL offset.
    changed_scope = target_scope.model_copy(update={"owner_projection_hash": _HASH_2})
    assert changed_scope.scope_id == target_scope.scope_id
    with pytest.raises(ConfidenceLedgerError) as exc_info:
        factory(scope=changed_scope)

    assert exc_info.value.code == "canonical_loaded_runtime_mismatch"
    assert exc_info.value.detail == "runtime ledger contract differs from its source declaration"
    assert not target._head_path.exists()
    assert not target._scope_tombstone_path.exists()
    _assert_scope_event_cas_witnesses_unchanged(target, event_witnesses)


def test_pinned_contract_survives_guard_removal_for_genuine_orphan_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _SessionFactory(tmp_path)
    target_scope = _scope(owner_scope_key="design-problem:contract-orphan-event")
    target = factory(scope=target_scope)
    target.execute_check(_prepare(target))
    _remove_scope_bootstrap_artifacts(target)
    target._journal_path.unlink(missing_ok=True)
    original = ledger_module._LEDGER_ARTIFACT_CONTRACTS
    changed = dict(original)
    changed["event"] = dataclasses.replace(changed["event"], scope_bound=False)
    monkeypatch.setattr(
        ledger_module, "_LEDGER_ARTIFACT_CONTRACTS", types.MappingProxyType(changed)
    )
    monkeypatch.setattr(ledger_module, "_assert_ledger_artifact_contracts_current", lambda: None)

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        factory(scope=target_scope.model_copy(update={"owner_projection_hash": _HASH_2}))

    assert exc_info.value.code == "ledger_head_reset_detected"
    assert not target._head_path.exists()
    assert not target._scope_tombstone_path.exists()
    assert any(
        manifest.kind == original["event"].kind
        for _artifact_id, manifest in (
            (artifact_id, target._artifact_store.get_manifest(artifact_id))
            for artifact_id in target._artifact_store.iter_artifact_ids()
        )
    )


def _journal_payload_for_scope_test(
    session: ConfidenceLedgerSession,
    artifact_kind: str,
) -> tuple[str, dict[str, Any]]:
    if artifact_kind == "event":
        session.execute_check(_prepare(session))
    elif artifact_kind == "receipt":
        session.persist_receipt(session.receipt())
    elif artifact_kind == "deployment_drift_poison":
        observed = ledger_module._identity(
            "policy-engine-deployment",
            {"scope_wal_test": session.risk_scope.owner_scope_key},
        )
        if observed == session._deployment_identity:
            observed = ledger_module._identity(
                "policy-engine-deployment",
                {"scope_wal_test": session.risk_scope.owner_scope_key, "retry": True},
            )
        with session._exclusive_lock():
            session._persist_deployment_drift_poison_locked(observed)
    else:
        raise AssertionError(f"unexpected artifact kind: {artifact_kind}")
    intent = next(
        record
        for record in session._journal_records
        if record.record_type == "intent" and record.artifact_kind == artifact_kind
    )
    assert intent.payload is not None
    return intent.artifact_ref, intent.payload


def _scope_event_cas_witnesses(
    session: ConfidenceLedgerSession,
) -> dict[str, tuple[dict[str, Any], tuple[tuple[str | None, str, str], ...]]]:
    """Bind genuine in-memory event intents to every visible owner-CAS view."""

    store = session._artifact_store
    inventory = store.inventory_snapshot()
    assert inventory.verdict == "pass", inventory.reason

    event_contract = ledger_module._IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS["event"]
    journal_payloads: dict[str, dict[str, Any]] = {}
    for record in session._journal_records:
        if record.record_type != "intent" or record.artifact_kind != "event":
            continue
        assert record.payload is not None
        artifact_id = ArtifactID.model_validate(record.artifact_ref)
        artifact_ref = str(artifact_id)
        previous = journal_payloads.setdefault(artifact_ref, dict(record.payload))
        assert previous == record.payload
    assert journal_payloads

    witnesses: dict[str, tuple[dict[str, Any], tuple[tuple[str | None, str, str], ...]]] = {}
    for artifact_ref, journal_payload in journal_payloads.items():
        payload, scope_id = session._validate_ledger_artifact_payload(
            contract_id="event",
            artifact_ref=artifact_ref,
            payload=journal_payload,
            require_cas=True,
            expected_scope_id=session._risk_scope.scope_id,
        )
        assert payload == journal_payload
        assert scope_id == session._risk_scope.scope_id

        artifact_id = ArtifactID.model_validate(artifact_ref)
        event_entries = tuple(
            entry
            for entry in inventory.entries
            if ArtifactID.model_validate(
                getattr(entry.artifact_ref, "artifact_id", entry.artifact_ref)
            )
            == artifact_id
            and entry.manifest.kind == event_contract.kind
        )
        assert event_entries
        assert any(
            getattr(entry.artifact_ref, "manifest_profile_sha256", None) is None
            for entry in event_entries
        )
        assert any(
            getattr(entry.artifact_ref, "manifest_profile_sha256", None) is not None
            for entry in event_entries
        )

        default_bytes = store.get_bytes(artifact_id)
        assert hashlib.sha256(default_bytes).hexdigest() == artifact_id.hex
        assert json.loads(default_bytes) == payload
        view_receipts: list[tuple[str | None, str, str]] = []
        for entry in event_entries:
            profile = getattr(entry.artifact_ref, "manifest_profile_sha256", None)
            view_bytes = store.get_bytes(entry.artifact_ref)
            assert view_bytes == default_bytes
            assert hashlib.sha256(view_bytes).hexdigest() == artifact_id.hex
            assert json.loads(view_bytes) == payload
            assert entry.blob_sha256 == "sha256:" + artifact_id.hex
            view_receipts.append((profile, entry.manifest_sha256, entry.blob_sha256))
        witnesses[artifact_ref] = (
            payload,
            tuple(sorted(view_receipts, key=lambda view: view[0] or "")),
        )
    return witnesses


def _assert_scope_event_cas_witnesses_unchanged(
    session: ConfidenceLedgerSession,
    witnesses: dict[str, tuple[dict[str, Any], tuple[tuple[str | None, str, str], ...]]],
) -> None:
    """Re-read captured event bytes and all views without consulting mutable ledger guards."""

    store = session._artifact_store
    inventory = store.inventory_snapshot()
    assert inventory.verdict == "pass", inventory.reason
    event_contract = ledger_module._IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS["event"]

    for artifact_ref, (payload, expected_views) in witnesses.items():
        artifact_id = ArtifactID.model_validate(artifact_ref)
        event_entries = tuple(
            entry
            for entry in inventory.entries
            if ArtifactID.model_validate(
                getattr(entry.artifact_ref, "artifact_id", entry.artifact_ref)
            )
            == artifact_id
            and entry.manifest.kind == event_contract.kind
        )
        actual_views = tuple(
            sorted(
                (
                    (
                        getattr(entry.artifact_ref, "manifest_profile_sha256", None),
                        entry.manifest_sha256,
                        entry.blob_sha256,
                    )
                    for entry in event_entries
                ),
                key=lambda view: view[0] or "",
            )
        )
        assert actual_views == expected_views

        default_bytes = store.get_bytes(artifact_id)
        assert hashlib.sha256(default_bytes).hexdigest() == artifact_id.hex
        assert json.loads(default_bytes) == payload
        for entry in event_entries:
            view_bytes = store.get_bytes(entry.artifact_ref)
            assert view_bytes == default_bytes
            assert json.loads(view_bytes) == payload


def _remove_scope_bootstrap_artifacts(session: ConfidenceLedgerSession) -> None:
    registry_ref = ledger_module._cas_json_artifact_ref(session._registry.source_payload())
    root_ref = ledger_module._cas_json_artifact_ref(session._expected_root_binding(registry_ref))
    anchor_ref = ledger_module._cas_json_artifact_ref(session._scope_anchor_payload())
    store = session._artifact_store
    bootstrap_refs = (
        (
            anchor_ref,
            ledger_module._IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS["scope_anchor"],
        ),
        (root_ref, ledger_module._IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS["root"]),
    )
    for artifact_ref, contract in bootstrap_refs:
        artifact_id = ArtifactID.model_validate(artifact_ref)
        inventory = store.inventory_snapshot(artifact_id)
        assert inventory.verdict == "pass", inventory.reason
        views = tuple(
            entry
            for entry in inventory.entries
            if ArtifactID.model_validate(
                getattr(entry.artifact_ref, "artifact_id", entry.artifact_ref)
            )
            == artifact_id
        )
        assert views
        assert all(
            entry.manifest.kind == contract.kind
            and entry.manifest.artifact_schema == contract.schema
            and entry.manifest.producer == contract.producer
            and entry.manifest.media_type == contract.media_type
            for entry in views
        )
        profiles = {getattr(entry.artifact_ref, "manifest_profile_sha256", None) for entry in views}
        assert None in profiles
        for profile in profiles:
            store._member_path(artifact_id, "manifest", profile).unlink(missing_ok=True)
            store._member_path(artifact_id, "signature", profile).unlink(missing_ok=True)
        store._member_path(artifact_id, "blob", None).unlink(missing_ok=True)
    session._head_path.unlink(missing_ok=True)
    session._scope_tombstone_path.unlink(missing_ok=True)


def _same_scope_valid_variant(artifact_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if artifact_kind == "event":
        stored = ledger_module._StoredLedgerEvent.model_validate(payload)
        check = stored.check.model_copy(
            update={"proof_detail": stored.check.proof_detail + " forged-but-rehashed"}
        )
        check = check.model_copy(update={"check_id": ledger_module._recompute_check_id(check)})
        stored = stored.model_copy(update={"check": check})
        stored = stored.model_copy(update={"event_id": ledger_module._recompute_event_id(stored)})
        return stored.model_dump(mode="json")
    if artifact_kind == "receipt":
        receipt = ledger_module.ConfidenceLedgerReceipt.model_validate(payload)
        deployment = ledger_module._identity(
            "policy-engine-deployment",
            {"same_scope_wal_test": "receipt-variant"},
        )
        if deployment == receipt.deployment_identity:
            deployment = ledger_module._identity(
                "policy-engine-deployment",
                {"same_scope_wal_test": "receipt-variant", "retry": True},
            )
        receipt = receipt.model_copy(update={"deployment_identity": deployment})
        receipt = receipt.model_copy(
            update={
                "receipt_id": ledger_module._identity(
                    "confidence-ledger",
                    receipt.model_dump(mode="json", exclude={"receipt_id"}),
                )
            }
        )
        return receipt.model_dump(mode="json")
    poison = ledger_module._DeploymentDriftPoison.model_validate(payload)
    observed = ledger_module._identity(
        "policy-engine-deployment",
        {"same_scope_wal_test": "poison-variant"},
    )
    if observed == poison.expected_deployment_identity:
        observed = ledger_module._identity(
            "policy-engine-deployment",
            {"same_scope_wal_test": "poison-variant", "retry": True},
        )
    poison = poison.model_copy(update={"observed_deployment_identity": observed})
    poison = poison.model_copy(
        update={
            "poison_id": ledger_module._identity(
                "confidence-deployment-drift-poison",
                poison.model_dump(mode="json", exclude={"poison_id"}),
            )
        }
    )
    return poison.model_dump(mode="json")


@pytest.mark.parametrize(
    "artifact_kind",
    ["event", "receipt", "deployment_drift_poison"],
)
def test_scope_wal_rejects_foreign_scope_artifacts_for_every_contract(
    tmp_path: Path,
    artifact_kind: str,
) -> None:
    factory = _SessionFactory(tmp_path)
    target_scope = _scope(owner_scope_key="design-problem:wal-target")
    target = factory(scope=target_scope)
    foreign = factory(scope=_scope(owner_scope_key="design-problem:wal-foreign"))
    artifact_ref, payload = _journal_payload_for_scope_test(foreign, artifact_kind)
    _remove_scope_bootstrap_artifacts(target)
    with target._exclusive_lock():
        target._append_scope_journal_intent(
            artifact_kind=artifact_kind, artifact_ref=artifact_ref, payload=payload
        )
        target._append_scope_journal_commit(artifact_kind=artifact_kind, artifact_ref=artifact_ref)

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        factory(scope=target_scope)

    assert exc_info.value.code == "ledger_scope_journal_invalid"


@pytest.mark.parametrize(
    "artifact_kind",
    ["event", "receipt", "deployment_drift_poison"],
)
def test_scope_wal_rejects_wrong_manifest_kind_for_every_contract(
    tmp_path: Path,
    artifact_kind: str,
) -> None:
    factory = _SessionFactory(tmp_path)
    target_scope = _scope(owner_scope_key="design-problem:wal-kind-target")
    target = factory(scope=target_scope)
    artifact_ref, payload = _journal_payload_for_scope_test(target, artifact_kind)
    variant = _same_scope_valid_variant(artifact_kind, payload)
    expected_kind, schema = ledger_module._journal_artifact_contract(artifact_kind)
    wrong_kind = expected_kind + ".untrusted"
    wrong_ref = target._artifact_store.put_json(
        variant,
        ledger_module.artifacts.PutOptions(
            kind=wrong_kind,
            media_type="application/json",
            schema=schema,
            producer=ledger_module._LEDGER_PRODUCER,
        ),
        canon_spec=ledger_module._CAS_CANON_SPEC,
    )
    wrong_artifact_ref = str(wrong_ref.artifact_id)
    manifest = target._artifact_store.get_manifest(wrong_artifact_ref)
    assert manifest.kind == wrong_kind
    assert manifest.artifact_schema == schema
    assert manifest.producer == ledger_module._LEDGER_PRODUCER
    assert wrong_artifact_ref != artifact_ref
    with target._exclusive_lock():
        target._append_scope_journal_intent(
            artifact_kind=artifact_kind,
            artifact_ref=wrong_artifact_ref,
            payload=variant,
        )
        target._append_scope_journal_commit(
            artifact_kind=artifact_kind,
            artifact_ref=wrong_artifact_ref,
        )
    _remove_scope_bootstrap_artifacts(target)

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        factory(scope=target_scope)

    assert exc_info.value.code == "ledger_scope_journal_invalid"


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
                blob, manifest = child._artifact_store._paths(
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


def test_caller_supplied_all_one_trace_is_not_a_coverage_argument(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        _prepare(
            session,
            instrument_id="constant_unit_e_process",
            certificate_ref="caller-trace://all-one-realization",
            claim=_claim(role="promotion"),
        )

    check = session.receipt().checks[0]
    assert exc_info.value.code == "certificate_role_not_permitted"
    assert check.instrument_family == "e_process"
    assert check.anytime_valid is True
    assert check.outcome == "preflight_refusal"
    assert check.supports_obligation is False
    assert check.eligible_for_promotion is False
    assert check.spend.fraction == 0


def test_adaptive_claim_selection_requires_conditional_validity_given_prior_filtration(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    stale_history = session.observe_history()
    prior = session.execute_check(_prepare(session))
    adaptive_claim = _claim(claim_ref=f"claim://unit/adaptive-after-{prior.outcome}")

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        session.prepare_check(
            history_token=stale_history,
            request_key="request://unit/adaptive/stale",
            obligation_class=PromotionObligationClass.CALIBRATION,
            instrument_id="constant_unit_e_process",
            certificate_ref="construction://constant-unit-e-process/adaptive-stale",
            claim=adaptive_claim,
        )

    assert exc_info.value.code == "ledger_head_conflict"
    current_history = session.observe_history()
    prepared = session.prepare_check(
        history_token=current_history,
        request_key="request://unit/adaptive/current",
        obligation_class=PromotionObligationClass.CALIBRATION,
        instrument_id="constant_unit_e_process",
        certificate_ref="construction://constant-unit-e-process/adaptive-current",
        claim=adaptive_claim,
    )
    receipt = session.receipt()

    assert prepared.filtration_ref == current_history.filtration_ref
    assert prepared.precheck_history_hash == current_history.precheck_history_hash
    assert prepared.claim_ref == adaptive_claim.claim_ref
    assert receipt.conditionality_clause == CONDITIONAL_VALIDITY_CLAUSE
    assert receipt.maintained_assumptions == (
        "obligation_completeness",
        "validator_soundness",
    )


def test_every_valid_history_prefix_preserves_the_delta_bound_at_user_stop(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    prior_total = Fraction()
    budget = session.registry.policy.delta.fraction

    for index in range(3):
        prepared = _prepare(
            session,
            request_key=f"request://unit/anytime-stop/{index}",
            certificate_ref=f"construction://constant-unit-e-process/anytime-stop/{index}",
        )
        prepared_receipt = validate_confidence_ledger_receipt(
            session.receipt(),
            session=session,
        )
        started = session.start_check(prepared)
        started_receipt = validate_confidence_ledger_receipt(
            session.receipt(),
            session=session,
        )
        session.execute_check(started)
        completed_receipt = validate_confidence_ledger_receipt(
            session.receipt(),
            session=session,
        )

        assert prepared_receipt.total_spend.fraction == prior_total
        assert prior_total < started_receipt.total_spend.fraction <= budget
        assert completed_receipt.total_spend == started_receipt.total_spend
        assert prepared_receipt.within_budget is True
        assert started_receipt.within_budget is True
        assert completed_receipt.within_budget is True
        prior_total = completed_receipt.total_spend.fraction


def test_claim_instrument_and_slot_are_bound_before_outcome_is_observed(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    claim = _claim(claim_ref="claim://unit/pre-outcome-binding")
    prepared = _prepare(
        session,
        certificate_ref="construction://constant-unit-e-process/pre-outcome-binding",
        claim=claim,
    )
    started = session.start_check(prepared)

    assert started.outcome == "started"
    assert started.claim_ref == claim.claim_ref
    assert started.instrument_id == "constant_unit_e_process"
    assert started.instrument_definition_hash is not None
    assert started.execution_ordinal == 0
    assert started.schedule_query_index == 0
    assert started.spend.fraction > 0
    assert started.claim_execution_binding_hash != prepared.claim_execution_binding_hash
    assert started.good_event_id is None

    completed = session.execute_check(started)

    assert completed.outcome == "not_supported"
    assert completed.request_fingerprint == started.request_fingerprint
    assert completed.claim_execution_binding_hash == started.claim_execution_binding_hash
    assert completed.execution_ordinal == started.execution_ordinal
    assert completed.schedule_query_index == started.schedule_query_index
    assert completed.spend == started.spend


def test_certificate_cannot_be_rebound_to_a_different_claim_snapshot_or_polarity(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    request_key = "request://unit/immutable-certificate-binding"
    certificate_ref = "construction://constant-unit-e-process/immutable-binding"
    original = _prepare(
        session,
        request_key=request_key,
        certificate_ref=certificate_ref,
    )
    rebound_claims = (
        _claim(claim_ref="claim://unit/different-snapshot"),
        _claim(role="admission", polarity="confident_wrong_admission"),
    )

    for rebound_claim in rebound_claims:
        with pytest.raises(ConfidenceLedgerError) as exc_info:
            session.prepare_check(
                history_token=session.observe_history(),
                request_key=request_key,
                obligation_class=PromotionObligationClass.CALIBRATION,
                instrument_id="constant_unit_e_process",
                certificate_ref=certificate_ref,
                claim=rebound_claim,
            )
        assert exc_info.value.code == "idempotency_binding_mismatch"

    current = session.receipt().checks[0]
    assert current.request_fingerprint == original.request_fingerprint
    assert current.claim_ref == original.claim_ref
    assert current.claim_polarity == "conformance_only"


def test_probabilistic_refusal_burns_against_confident_wrong_refusal_event(
    sessions: _SessionFactory,
) -> None:
    registry = load_confidence_ledger_registry(
        REPO_ROOT / "architecture/production_quality/confidence_ledger.toml"
    )
    payload = registry.source_payload()
    constant_e_process = next(
        item
        for item in payload["instruments"]
        if item["instrument_id"] == "constant_unit_e_process"
    )
    constant_e_process["certificate_roles"].append("refusal")
    session = sessions(registry_source=payload)
    prepared = _prepare(
        session,
        obligation_class=PromotionObligationClass.DATA,
        instrument_id="constant_unit_e_process",
        certificate_ref="construction://constant-unit-e-process/refusal",
        claim=_claim(role="refusal", polarity="confident_wrong_refusal"),
    )
    started = session.start_check(prepared)

    assert started.claim_polarity == "confident_wrong_refusal"
    assert started.spend.fraction > 0
    assert session.receipt().total_spend == started.spend
    assert started.supports_obligation is False

    completed = session.execute_check(started)
    expected_good_event_id = ledger_module._identity(
        "confidence-good-event",
        {
            "execution_id": completed.execution_id,
            "spend": completed.spend,
            "protected_error": "confident_wrong_refusal",
        },
    )

    assert completed.outcome == "not_supported"
    assert completed.good_event_id == expected_good_event_id
    assert completed.supports_obligation is False
    assert completed.eligible_for_promotion is False
    assert session.receipt().total_spend == started.spend


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


def test_marginal_split_conformal_interval_is_not_adaptive_promotion_certificate(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        _prepare(
            session,
            instrument_id="split_conformal_interval",
            certificate_ref="foundry://split-conformal/marginal-coverage",
            claim=_claim(role="promotion"),
        )

    check = session.receipt().checks[0]
    assert exc_info.value.code == "non_anytime_valid"
    assert check.instrument_family == "marginal_conformal_interval"
    assert check.anytime_valid is False
    assert check.outcome == "preflight_refusal"
    assert check.spend.fraction == 0
    assert check.eligible_for_promotion is False


def test_foundry_anytime_valid_label_without_owner_theorem_is_refused(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        _prepare(
            session,
            instrument_id="foundry_empirical_confidence_sequence",
            certificate_ref="foundry://confidence-sequence?anytime_valid=true",
            claim=_claim(role="promotion"),
        )

    check = session.receipt().checks[0]
    assert exc_info.value.code == "non_anytime_valid"
    assert check.instrument_family == "empirical_confidence_proxy"
    assert check.proof_profile_id == "fixed_time_ineligible"
    assert check.anytime_valid is False
    assert check.refusal_code == "non_anytime_valid"
    assert check.spend.fraction == 0


def test_ir_sensitivity_e_value_is_not_resolved_as_betting_e_value(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        _prepare(
            session,
            instrument_id="causal_sensitivity_e_value",
            certificate_ref="ir://analytics/sensitivity/e-value-result",
            claim=_claim(role="promotion"),
        )

    check = session.receipt().checks[0]
    assert exc_info.value.code == "non_anytime_valid"
    assert check.instrument_family == "unmeasured_confounding_robustness_metric"
    assert check.instrument_family != "e_value"
    assert check.anytime_valid is False
    assert check.spend.fraction == 0
    assert check.eligible_for_promotion is False


def test_ddm_online_fdr_decision_is_not_a_promotion_ledger_receipt(
    sessions: _SessionFactory,
) -> None:
    session = sessions()

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        _prepare(
            session,
            instrument_id="ddm_online_fdr_controller",
            certificate_ref="ddm://online-fdr/reject-decision",
            claim=_claim(role="promotion"),
        )

    projection = project_n9_promotion_certificate(session.receipt(), session=session)
    assert exc_info.value.code == "non_anytime_valid"
    assert projection.total_spend.fraction == 0
    assert len(projection.promotion_rows) == 1
    row = projection.promotion_rows[0]
    assert row.instrument_family == "false_discovery_rate_controller"
    assert row.outcome == "preflight_refusal"
    assert row.anytime_valid is False
    assert row.supports_obligation is False
    assert row.eligible_for_promotion is False


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
        certificate_evidence_hash=recompute_confidence_owner_evidence_hash(evidence),
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
            certificate_evidence_hash=recompute_confidence_owner_evidence_hash(evidence),
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
            certificate_evidence_hash=recompute_confidence_owner_evidence_hash(value),
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
    assert n9.scope_anchor_ref == receipt.scope_anchor_ref
    assert n9.head_event_id == receipt.head_event_id
    assert n9.head_event_ref == receipt.head_event_ref
    assert receipt.deployment_identity.startswith("policy-engine-deployment:sha256:")
    assert n9.deployment_identity == receipt.deployment_identity
    assert n12.deployment_identity == receipt.deployment_identity
    assert n12.scope_anchor_ref == receipt.scope_anchor_ref
    assert n12.risk_scope == session.risk_scope
    with pytest.raises(ConfidenceLedgerError, match="conditionality_clause_missing"):
        validate_confidence_ledger_receipt(
            receipt.model_copy(update={"conditionality_clause": "unconditional"}),
            session=session,
        )


def test_semantic_receipt_projection_is_stable_across_physical_lock_identities(
    tmp_path: Path,
) -> None:
    scope = _scope(authority_purpose="n11_probabilistic_conformance")
    first_session = _SessionFactory(tmp_path / "first")(scope=scope)
    second_session = _SessionFactory(tmp_path / "second")(scope=scope)
    first_session.execute_check(_prepare(first_session))
    second_session.execute_check(_prepare(second_session))
    first_receipt = validate_confidence_ledger_receipt(
        first_session.receipt(),
        session=first_session,
    )
    second_receipt = validate_confidence_ledger_receipt(
        second_session.receipt(),
        session=second_session,
    )

    first_lock = first_receipt.checks[0].owner_invocation_lock_identity
    second_lock = second_receipt.checks[0].owner_invocation_lock_identity
    assert first_lock is not None
    assert second_lock is not None
    assert first_lock.inode != second_lock.inode
    assert first_receipt.model_dump_json() != second_receipt.model_dump_json()

    first_projection = project_confidence_ledger_semantic_receipt(
        first_receipt,
        session=first_session,
        projection_scope="n11_conformance_append_lineage",
    )
    second_projection = project_confidence_ledger_semantic_receipt(
        second_receipt,
        session=second_session,
        projection_scope="n11_conformance_append_lineage",
    )

    assert first_projection == second_projection
    assert first_projection.checks[0].owner_invocation_claim_projection_hash is not None
    assert first_projection.checks[0].good_event_id == first_receipt.checks[0].good_event_id


def test_semantic_receipt_projection_rejects_scope_authority_mismatch(
    sessions: _SessionFactory,
) -> None:
    real_scope = _scope(authority_purpose="n11_real_n10_n13b_accounting")
    session = sessions(scope=real_scope)
    session.execute_check(_prepare(session))

    with pytest.raises(
        ConfidenceLedgerError,
        match="semantic_projection_scope_authority_mismatch",
    ):
        project_confidence_ledger_semantic_receipt(
            session.receipt(),
            session=session,
            projection_scope="n11_conformance_append_lineage",
        )


def test_semantic_receipt_projection_excludes_physical_ledger_identities(
    sessions: _SessionFactory,
) -> None:
    session = sessions(scope=_scope(authority_purpose="n11_probabilistic_conformance"))
    session.execute_check(_prepare(session))
    receipt = session.receipt()
    projection = project_confidence_ledger_semantic_receipt(
        receipt,
        session=session,
        projection_scope="n11_conformance_append_lineage",
    )

    def nested_keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value).union(*(nested_keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(nested_keys(item) for item in value))
        return set()

    physical_fields = {
        "check_id",
        "claim_execution_binding_hash",
        "event_id",
        "event_ref",
        "filtration_ref",
        "head_event_id",
        "head_event_ref",
        "ledger_root_id",
        "ledger_root_ref",
        "owner_invocation_claim_id",
        "owner_invocation_lock_identity",
        "parent_event_id",
        "parent_event_ref",
        "precheck_history_hash",
        "prepared_event_id",
        "receipt_id",
        "registry_artifact_ref",
        "started_event_id",
    }
    raw_keys = nested_keys(receipt.model_dump(mode="json"))
    semantic_keys = nested_keys(projection.model_dump(mode="json"))

    assert physical_fields <= raw_keys
    assert physical_fields.isdisjoint(semantic_keys)
    assert projection.risk_scope == session.risk_scope
    assert projection.scope_id == session.risk_scope.scope_id
    assert projection.checks[0].owner_invocation_claim_projection_hash is not None
    assert projection.checks[0].good_event_id is not None


def test_n9_projection_excludes_conformance_and_non_promotion_rows(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    n9 = project_n9_promotion_certificate(session.receipt(), session=session)

    assert n9.promotion_rows == ()


def test_n9_projection_model_rejects_stale_self_hash_and_unknown_fields(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    projection = project_n9_promotion_certificate(session.receipt(), session=session)
    payload = projection.model_dump(mode="json")

    assert N9PromotionCertificateProjection.model_validate(payload) == projection

    tampered = copy.deepcopy(payload)
    tampered["deployment_identity"] = "policy-engine-deployment:sha256:" + "f" * 64
    with pytest.raises(ValueError, match="projection_hash"):
        N9PromotionCertificateProjection.model_validate(tampered)

    unrecognized = copy.deepcopy(payload)
    unrecognized["projection_scope"] = "untrusted_verification_extension"
    with pytest.raises(ValueError, match="literal_error"):
        N9PromotionCertificateProjection.model_validate(unrecognized)


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
    assert n12.scope_anchor_ref == session.receipt().scope_anchor_ref


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


def test_zero_mass_schedule_is_valid_and_cannot_support_promotion(
    sessions: _SessionFactory,
) -> None:
    registry = load_confidence_ledger_registry(
        REPO_ROOT / "architecture/production_quality/confidence_ledger.toml"
    )
    payload = registry.source_payload()
    payload["schedule_profiles"].append(
        {
            "profile_id": "zero_mass_basel_square",
            "proof_kernel_id": "basel_square_v1",
            "mass": {"numerator": 0, "denominator": 1},
        }
    )
    session = sessions(
        registry_source=payload,
        schedule_profile_id="zero_mass_basel_square",
    )

    completed = session.execute_check(_prepare(session))
    receipt = session.receipt()

    assert completed.spend.fraction == 0
    assert completed.supports_obligation is False
    assert completed.eligible_for_promotion is False
    assert receipt.total_spend.fraction == 0
    assert receipt.within_budget is True


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


def test_exact_rational_basel_slot_is_below_declared_ideal_weight(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    started = session.start_check(_prepare(session))
    delta = session.registry.policy.delta.fraction
    obligation_weight = session.registry.obligation_weights[PromotionObligationClass.CALIBRATION]
    executable_coefficient = Fraction(6 * 113**2, 355**2)
    expected_slot = delta * obligation_weight * executable_coefficient

    # Exact rational upper enclosure of pi at 50 decimal places. Dividing by
    # its square gives a strict rational lower witness for the symbolic ideal.
    pi_upper = Fraction(
        314159265358979323846264338327950288419716939937511,
        10**50,
    )
    ideal_coefficient_lower_witness = Fraction(6, 1) / pi_upper**2

    assert started.spend.fraction == expected_slot
    assert executable_coefficient == Fraction(76614, 126025)
    assert executable_coefficient < ideal_coefficient_lower_witness
    assert expected_slot < delta * obligation_weight * ideal_coefficient_lower_witness


def test_upward_rounded_schedule_rendering_is_rejected(
    sessions: _SessionFactory,
) -> None:
    session = sessions()
    session.execute_check(_prepare(session))
    receipt = session.receipt()
    check = receipt.checks[0]
    decimal_scale = 10**48
    downward_rendering = Fraction(check.spend_decimal)
    upward_rendering = downward_rendering + Fraction(1, decimal_scale)
    scaled_upward = upward_rendering * decimal_scale
    assert scaled_upward.denominator == 1
    whole, decimals = divmod(scaled_upward.numerator, decimal_scale)
    upward_text = f"{whole}.{decimals:048d}"

    assert downward_rendering <= check.spend.fraction < upward_rendering
    forged_check = check.model_copy(update={"spend_decimal": upward_text})
    forged_receipt = receipt.model_copy(update={"checks": (forged_check,)})

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        validate_confidence_ledger_receipt(forged_receipt, session=session)

    assert exc_info.value.code == "spend_decimal_drift"


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


def test_loaded_deployment_identity_capture_is_typed_and_uses_owner_snapshot() -> None:
    """The run-start observation commits the loaded manifest and lock baseline."""

    observation = ledger_module.capture_loaded_deployment_identity()

    assert observation.status == "established"
    assert observation.reason_code is None
    assert observation.deployment_identity == ledger_module._deployment_identity_from_baseline(
        ledger_module._IMPORT_TIME_DEPLOYMENT_BASELINE
    )


def test_loaded_deployment_identity_capture_does_not_rescan_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After owner import, run identity reads only its admitted snapshot."""

    def unavailable(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("source_checkout_must_not_be_required_for_identity_observation")

    monkeypatch.setattr(ledger_module, "_loaded_policy_engine_root", unavailable)
    monkeypatch.setattr(ledger_module, "_deployment_baseline", unavailable)
    monkeypatch.setattr(ledger_module, "_loaded_code_manifest", unavailable)

    observation = ledger_module.capture_loaded_deployment_identity()

    assert observation.status == "established"
    assert observation.deployment_identity == ledger_module._deployment_identity_from_baseline(
        ledger_module._IMPORT_TIME_DEPLOYMENT_BASELINE
    )


def test_loaded_deployment_identity_absence_is_a_typed_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An inconsistent import snapshot is unavailable, never a guessed identity."""

    monkeypatch.setattr(ledger_module, "_IMPORT_TIME_LOADED_CODE_CONSISTENT", False)

    observation = ledger_module.capture_loaded_deployment_identity()

    assert observation.status == "not_established"
    assert observation.deployment_identity is None
    assert observation.reason_code == "canonical_loaded_runtime_mismatch"


def test_import_time_identity_failure_is_sticky_and_blocks_authority(
    tmp_path: Path,
) -> None:
    """A typed first-capture failure stays unavailable across consumers and source repair."""

    repo_root = tmp_path / "isolated-import-failure-repo"
    shutil.copytree(
        REPO_ROOT / "src",
        repo_root / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(
        REPO_ROOT / "architecture",
        repo_root / "architecture",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for relative in (Path("pyproject.toml"), Path("uv.lock")):
        (repo_root / relative).write_bytes((REPO_ROOT / relative).read_bytes())

    script = r"""
import importlib
import json
import sys
from pathlib import Path

repo_root = Path.cwd().resolve()
facade_path = repo_root / "src/polisyos/fabric/__init__.py"
original_facade = facade_path.read_bytes()
source = original_facade.decode("utf-8")
original_row = '    "atomic_write_json": ("polisyos.fabric.io.atomic", "atomic_write_json"),'
changed_row = '    "atomic_write_json": ("polisyos.fabric.io.atomic", "atomic_write_json_changed"),'
assert source.count(original_row) == 1

# Load the real lazy facade first, then change its selected source binding. The
# confidence-ledger owner must turn the resulting typed source/runtime mismatch
# into an unavailable snapshot while allowing its candidate module to import.
import polisyos.fabric
facade_path.write_text(source.replace(original_row, changed_row, 1), encoding="utf-8")
from polisyos.runtime.quality import confidence_ledger as ledger

assert ledger._IMPORT_TIME_LOADED_CODE_CONSISTENT is False
failure = ledger._IMPORT_TIME_DEPLOYMENT_IDENTITY_FAILURE
assert isinstance(failure, tuple) and len(failure) == 2
assert failure[0] == "canonical_loaded_runtime_mismatch"
assert isinstance(failure[1], str) and failure[1]
observation = ledger.capture_loaded_deployment_identity()
assert observation.status == "not_established"
assert observation.deployment_identity is None
assert observation.reason_code == "canonical_loaded_runtime_mismatch"

# Repair the source bytes after the failed import. The immutable first-capture
# outcome must remain unavailable, without calling any resolver again.
facade_path.write_bytes(original_facade)
forbidden_calls = []
def forbidden(name):
    def fail(*args, **kwargs):
        forbidden_calls.append(name)
        raise AssertionError("unavailable_snapshot_must_not_retry:" + name)
    return fail

for name in (
    "_resolve_authority_import_closure",
    "_stable_deployment_snapshot",
    "_import_authority_closure_modules",
    "_source_facade_runtime_projection",
    "_loaded_code_manifest",
    "_deployment_baseline",
    "_deployment_quick_fence",
    "_assert_loaded_runtime_matches_import_baseline",
    "_assert_ledger_artifact_contracts_current",
    "load_confidence_ledger_registry",
    "build_artifact_store",
):
    setattr(ledger, name, forbidden(name))

def assert_unavailable(call):
    try:
        call()
    except ledger.ConfidenceLedgerError as exc:
        assert exc.code == "canonical_loaded_runtime_mismatch"
        assert failure[0] in exc.detail and failure[1] in exc.detail
    else:
        raise AssertionError("unavailable_import_snapshot_admitted_authority")

scope = ledger.ConfidenceRiskBudgetScope(
    scope_owner_ref="polisyos.runtime.quality.promotion_sequence",
    authority_purpose="n9_promotion",
    owner_scope_key="design-problem:sticky-import-failure",
    owner_projection_hash="sha256:" + "1" * 64,
    epoch_ref=None,
    model_ref=None,
    rule_ref="policyos.layer3.gy.n9.v1",
    schema_ref="policyos.runtime.design_problem.v1",
)
state_root = repo_root / ".isolated-sticky-import-failure-state"
assert_unavailable(lambda: ledger.ConfidenceLedgerSession.from_repo(repo_root, risk_scope=scope))
assert_unavailable(
    lambda: ledger.ConfidenceLedgerSession(
        registry=None,
        risk_scope=scope,
        schedule_profile_id=None,
        artifact_store=None,
        state_root=state_root / "normal",
        certificate_resolver=None,
        certificate_verifier=None,
    )
)
assert_unavailable(
    lambda: ledger.ConfidenceLedgerSession._for_verification(
        repo_root,
        risk_scope=scope,
        artifact_store=None,
        state_root=state_root / "verification",
    )
)

# A direct private canonical initializer cannot bypass the common snapshot gate.
private = object.__new__(ledger.ConfidenceLedgerSession)
assert_unavailable(
    lambda: private._initialize(
        registry=None,
        risk_scope=scope,
        schedule_profile_id=None,
        artifact_store=None,
        state_root=state_root / "direct",
        certificate_resolver=None,
        certificate_verifier=None,
        authority_provenance="canonical_repo",
        authority_repo_root=repo_root,
        deployment_identity="sha256:" + "2" * 64,
        deployment_quick_fence=(),
    )
)
assert not (state_root / "normal").exists()
assert not (state_root / "verification").exists()
assert not (state_root / "direct").exists()
assert not (repo_root / ".polisyos/cas").exists()
assert not (repo_root / ".polisyos/runtime/confidence_ledger").exists()

# Even a field-forged object cannot project authority while the source snapshot
# remains unavailable.
forged = object.__new__(ledger.ConfidenceLedgerSession)
object.__setattr__(forged, "_authority_repo_root", repo_root)
assert forged.is_authority_session is False

from polisyos.runtime.quality.promotion_sequence import CanonicalN9PromotionPort
port = CanonicalN9PromotionPort(repo_root=repo_root)
refusal = port.deployment_identity_refusal("sha256:" + "3" * 64)
assert refusal == "confidence_ledger_refused:canonical_loaded_runtime_mismatch"
assert ledger.capture_loaded_deployment_identity().status == "not_established"
assert forbidden_calls == []

# Removal control: the failure markers remain, but re-raising the original
# typed error makes the candidate import fail instead of yielding a held state.
ledger_path = repo_root / "src/polisyos/runtime/quality/confidence_ledger.py"
ledger_source = ledger_path.read_text(encoding="utf-8")
marker = "    except ConfidenceLedgerError as exc:\n        # A failed first capture is terminal for this process."
assert ledger_source.count(marker) == 1
mutant = ledger_source.replace(
    marker,
    "    except ConfidenceLedgerError as exc:\n        raise\n        # A failed first capture is terminal for this process.",
    1,
)
assert "_IMPORT_TIME_LOADED_CODE_CONSISTENT = False" in mutant
assert "_IMPORT_TIME_DEPLOYMENT_IDENTITY_FAILURE" in mutant
ledger_path.write_text(mutant, encoding="utf-8")
facade_path.write_text(source.replace(original_row, changed_row, 1), encoding="utf-8")
try:
    importlib.reload(ledger)
except Exception as exc:
    assert type(exc).__name__ == "ConfidenceLedgerError"
    assert getattr(exc, "code", None) == "canonical_loaded_runtime_mismatch"
else:
    raise AssertionError("removing_import_failure_boundary_still_imported")

print(json.dumps({
    "candidate_imported": True,
    "failure_code": failure[0],
    "failure_detail": failure[1],
    "identity_status_after_source_restore": observation.status,
    "n9_refusal": refusal,
    "blocked_entrypoints": ["from_repo", "constructor", "_for_verification", "_initialize"],
    "side_effect_calls": forbidden_calls,
    "removal_control": "typed import failure propagates",
}, sort_keys=True))
"""
    environment = os.environ.copy()
    prior_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(repo_root / "src"), prior_pythonpath) if value
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert result["candidate_imported"] is True
    assert result["failure_code"] == "canonical_loaded_runtime_mismatch"
    assert result["identity_status_after_source_restore"] == "not_established"
    assert result["n9_refusal"] == "confidence_ledger_refused:canonical_loaded_runtime_mismatch"
    assert result["side_effect_calls"] == []
    assert result["removal_control"] == "typed import failure propagates"
    print(json.dumps(result, sort_keys=True))


def test_canonical_from_repo_rejects_runtime_contract_mutation_before_cas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical consumer refuses source divergence before constructing CAS."""
    changed = dict(ledger_module._LEDGER_ARTIFACT_CONTRACTS)
    changed["registry"] = dataclasses.replace(
        changed["registry"],
        kind=changed["registry"].kind + ".forged",
    )
    monkeypatch.setattr(
        ledger_module,
        "_LEDGER_ARTIFACT_CONTRACTS",
        types.MappingProxyType(changed),
    )
    store_builder_calls: list[ledger_module.ArtifactStoreConfig] = []

    def unexpected_store_builder(
        config: ledger_module.ArtifactStoreConfig,
    ) -> ledger_module.artifacts.ArtifactStore:
        store_builder_calls.append(config)
        raise AssertionError("source mismatch must be refused before CAS construction")

    monkeypatch.setattr(ledger_module, "build_artifact_store", unexpected_store_builder)
    risk_scope = _scope(
        owner_scope_key=f"design-problem:source-derived-canonical-admission:{time.time_ns()}"
    )
    scope_hex = risk_scope.scope_id.rsplit(":", 1)[-1]
    state_root = REPO_ROOT / ".polisyos/runtime/confidence_ledger"
    head_path = state_root / f"{scope_hex}.head.json"
    tombstone_path = state_root / f"{scope_hex}.scope.json"
    assert not head_path.exists()
    assert not tombstone_path.exists()

    with pytest.raises(ConfidenceLedgerError) as exc_info:
        ConfidenceLedgerSession.from_repo(REPO_ROOT, risk_scope=risk_scope)

    assert exc_info.value.code == "canonical_loaded_runtime_mismatch"
    assert exc_info.value.detail == "runtime ledger contract differs from its source declaration"
    assert store_builder_calls == []
    assert not head_path.exists()
    assert not tombstone_path.exists()


def test_import_manifest_root_rebinding_cannot_hide_genuine_orphan_event_on_fresh_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Any,
) -> None:
    """A fresh caller cannot reset after same-scope events outlive local pointers and WAL."""

    factory = _SessionFactory(tmp_path)
    target_scope = _scope(owner_scope_key="design-problem:manifest-root-orphan-event")
    target = factory(scope=target_scope)
    target.execute_check(_prepare(target))
    event_witnesses = _scope_event_cas_witnesses(target)
    _remove_scope_bootstrap_artifacts(target)
    target._journal_path.unlink(missing_ok=True)
    _assert_scope_event_cas_witnesses_unchanged(target, event_witnesses)

    original_manifest = ledger_module._IMPORT_TIME_LOADED_CODE_MANIFEST
    original_closure = ledger_module._IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE
    original_consistency = ledger_module._IMPORT_TIME_LOADED_CODE_CONSISTENT
    assert original_manifest
    assert original_consistency is True

    changed = dict(ledger_module._LEDGER_ARTIFACT_CONTRACTS)
    original_event_contract = changed["event"]
    changed["event"] = dataclasses.replace(original_event_contract, scope_bound=False)
    rebound_contracts = types.MappingProxyType(changed)
    rebound_snapshot = ledger_module._snapshot_ledger_contracts(rebound_contracts)
    monkeypatch.setattr(ledger_module, "_LEDGER_ARTIFACT_CONTRACTS", rebound_contracts)
    monkeypatch.setattr(
        ledger_module,
        "_IMPORT_TIME_LEDGER_ARTIFACT_CONTRACTS",
        rebound_snapshot,
    )

    contract_projection = ledger_module._runtime_ledger_contract_projection()
    model_projection = ledger_module._ledger_model_projection(rebound_contracts)
    snapshot_projection = ledger_module._runtime_ledger_snapshot_projection(rebound_snapshot)
    monkeypatch.setattr(
        ledger_module,
        "_IMPORT_TIME_LEDGER_CONTRACT_PROJECTION",
        contract_projection,
    )
    monkeypatch.setattr(
        ledger_module,
        "_IMPORT_TIME_LEDGER_MODEL_PROJECTION",
        model_projection,
    )
    monkeypatch.setattr(
        ledger_module,
        "_IMPORT_TIME_LEDGER_SNAPSHOT_PROJECTION",
        snapshot_projection,
    )

    guard = ledger_module._assert_ledger_artifact_contracts_current
    defaults = list(guard.__defaults__ or ())
    assert len(defaults) >= 10
    defaults[2] = contract_projection
    defaults[3] = model_projection
    defaults[5] = rebound_snapshot
    defaults[6] = snapshot_projection
    monkeypatch.setattr(guard, "__defaults__", tuple(defaults))

    # This is the minimum remaining rebind: preserve the import-time closure and
    # consistency fact, but replace the mutable expected code manifest with the
    # exact current output from the guard's already-captured source-owned helper.
    loaded_code_manifest_fn = defaults[8]
    assert callable(loaded_code_manifest_fn)
    current_manifest, current_consistency = loaded_code_manifest_fn(
        ledger_module._IMPORT_TIME_OWNER_ROOT,
        original_closure,
    )
    assert current_consistency is True
    assert current_manifest != original_manifest
    monkeypatch.setattr(ledger_module, "_IMPORT_TIME_LOADED_CODE_MANIFEST", current_manifest)
    assert ledger_module._IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE is original_closure
    assert ledger_module._IMPORT_TIME_LOADED_CODE_CONSISTENT is original_consistency

    # Exercise fresh production admission only after every profile view is coherent,
    # the global owner inventory passes, and genuine target-scope event bytes are
    # independently read and bound to the retained content-addressed refs.
    changed_scope = target_scope.model_copy(update={"owner_projection_hash": _HASH_2})
    assert changed_scope.scope_id == target_scope.scope_id
    assert not target._head_path.exists()
    assert not target._scope_tombstone_path.exists()
    assert not target._journal_path.exists()
    record_property(
        "fresh_manifest_rebind_boundary",
        "fresh factory after pointer/WAL absence; global owner CAS inventory passes; "
        "all typed target-scope event refs, default/profile reads, blob hashes, and "
        "manifest-view hashes are preserved",
    )
    record_property(
        "fresh_manifest_rebind_event_refs",
        ",".join(sorted(event_witnesses)),
    )

    admission_error: Exception | None = None
    try:
        factory(scope=changed_scope)
    except Exception as exc:
        admission_error = exc

    if admission_error is None:
        record_property("fresh_manifest_rebind_refusal_code", "returned_without_refusal")
        record_property("fresh_manifest_rebind_refusal_detail", "fresh factory returned")
        _assert_scope_event_cas_witnesses_unchanged(target, event_witnesses)
        pytest.fail("fresh admission returned despite retained orphan events")
    if isinstance(admission_error, ConfidenceLedgerError):
        record_property("fresh_manifest_rebind_refusal_code", str(admission_error.code))
        record_property("fresh_manifest_rebind_refusal_detail", str(admission_error.detail))
    else:
        record_property("fresh_manifest_rebind_refusal_code", "untyped_exception")
        record_property(
            "fresh_manifest_rebind_refusal_detail",
            f"{type(admission_error).__name__}: {admission_error}",
        )
    _assert_scope_event_cas_witnesses_unchanged(target, event_witnesses)
    if not isinstance(admission_error, ConfidenceLedgerError):
        raise admission_error

    assert not target._head_path.exists()
    assert not target._scope_tombstone_path.exists()
    assert admission_error.code == "canonical_loaded_runtime_mismatch"


@pytest.mark.parametrize(
    "mutation",
    ["non_event_kind", "schema_binding", "added_row", "removed_row", "schema_version"],
)
def test_source_projection_covers_complete_registry_and_schema_quantity(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The source projection detects table and semantic changes beyond one event flag."""
    source_bytes = ledger_module._LEDGER_MODULE_SOURCE_PATH.read_bytes()
    source_projection = ledger_module._source_ledger_contract_projection(source_bytes)
    assert source_projection == ledger_module._runtime_ledger_contract_projection()
    changed = dict(ledger_module._LEDGER_ARTIFACT_CONTRACTS)

    if mutation == "non_event_kind":
        changed["registry"] = dataclasses.replace(
            changed["registry"],
            kind=changed["registry"].kind + ".forged",
        )
    elif mutation == "schema_binding":
        contract_id = "registry"
        contract = changed[contract_id]
        binding_name = next(
            name
            for name, value in vars(ledger_module).items()
            if name.endswith("_SCHEMA") and value is contract.schema
        )
        rebound_schema = ledger_module.artifacts.SchemaInfo(
            name=contract.schema.name,
            version=contract.schema.version + ".forged",
        )
        monkeypatch.setattr(ledger_module, binding_name, rebound_schema)
        changed[contract_id] = dataclasses.replace(contract, schema=rebound_schema)
    elif mutation == "added_row":
        changed["unmodeled_source_row"] = changed["registry"]
    elif mutation == "removed_row":
        del changed["registry"]
    else:
        monkeypatch.setattr(
            ledger_module,
            "CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION",
            ledger_module.CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION + ".forged",
        )

    monkeypatch.setattr(
        ledger_module,
        "_LEDGER_ARTIFACT_CONTRACTS",
        types.MappingProxyType(changed),
    )
    assert source_projection != ledger_module._runtime_ledger_contract_projection()


def test_source_literal_contract_mode_and_existing_unknown_mode_are_distinct() -> None:
    """Exercise the real source projection and preserve fail-closed AST parsing."""

    source_path = ledger_module._LEDGER_MODULE_SOURCE_PATH
    source_bytes = source_path.read_bytes()
    tree = ast.parse(source_bytes, filename=str(source_path))

    class _ModuleFunctionCollector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.names: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.names.append(node.name)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.names.append(node.name)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            del node

    collector = _ModuleFunctionCollector()
    collector.visit(tree)
    assert len(collector.names) == len(set(collector.names))

    literal = ast.parse("'typed source value'", mode="eval").body
    assert ledger_module._source_literal(literal, expected_type=str) == "typed source value"
    with pytest.raises(ValueError, match="required literal"):
        ledger_module._source_literal(literal, expected_type=bool)

    unknown = ast.parse("runtime_name", mode="eval").body
    assert ledger_module._source_literal(unknown) is ledger_module._UNSUPPORTED_SOURCE_LITERAL
    with pytest.raises(ValueError, match="required literal"):
        ledger_module._source_literal(unknown, expected_type=str)

    declared = ledger_module._source_ledger_contract_projection(source_bytes)
    assert declared == ledger_module._runtime_ledger_contract_projection()


def _write_runtime_facade_map_fixture(
    tmp_path: Path,
    *,
    mutate_during_import: bool,
) -> tuple[Path, str, str]:
    """Write a real-import fixture with one source-owned lazy export map."""

    repo_root = tmp_path / "facade-map-runtime-repo"
    package_name = "_n11_facade_" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:12]
    package = repo_root / "src" / "polisyos" / package_name
    package.mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "facade-fixture"\n', encoding="utf-8"
    )
    (repo_root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "entry.py").write_text(
        f"from polisyos.{package_name}.facade import One\n",
        encoding="utf-8",
    )
    (package / "facade.py").write_text(
        "from importlib import import_module as _load\n\n"
        "_LAZY_EXPORTS = {\n"
        f'    "One": ("polisyos.{package_name}.provider_one", "One"),\n'
        "}\n\n"
        "def __getattr__(name: str):\n"
        "    if name not in _LAZY_EXPORTS:\n"
        "        raise AttributeError(name)\n"
        "    module_name, attribute_name = _LAZY_EXPORTS[name]\n"
        "    module = _load(module_name)\n"
        "    value = getattr(module, attribute_name)\n"
        "    globals()[name] = value\n"
        "    return value\n",
        encoding="utf-8",
    )
    initializer = f"import polisyos.{package_name}.mutator\n" if mutate_during_import else ""
    (package / "provider_one.py").write_text(
        initializer + "class One:\n    pass\n",
        encoding="utf-8",
    )
    (package / "provider_two.py").write_text("class One:\n    pass\n", encoding="utf-8")
    if mutate_during_import:
        (package / "mutator.py").write_text(
            f"from polisyos.{package_name}.facade import _LAZY_EXPORTS\n"
            "_LAZY_EXPORTS['One'] = "
            f"('polisyos.{package_name}.provider_two', 'One')\n",
            encoding="utf-8",
        )
    return repo_root, package_name, f"polisyos.{package_name}.entry"


def test_source_facade_projection_rejects_import_initializer_map_mutation_in_fresh_process(
    tmp_path: Path,
) -> None:
    """A closure initializer cannot replace a source-owned provider mapping."""

    repo_root, package_name, entry_module = _write_runtime_facade_map_fixture(
        tmp_path,
        mutate_during_import=True,
    )
    script = r"""
import ast
import importlib.util
import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
product_source = Path(sys.argv[2])
candidate_source = Path(sys.argv[3])
package_name = sys.argv[4]
entry_module = sys.argv[5]
sys.path.insert(0, str(product_source))
import polisyos
polisyos.__path__.append(str(repo_root / "src" / "polisyos"))
spec = importlib.util.spec_from_file_location("r7_candidate_ledger", candidate_source)
ledger = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ledger
spec.loader.exec_module(ledger)
closure = ledger._resolve_authority_import_closure(repo_root, entry_module)
ledger._import_authority_closure_modules(closure)
facade_name = f"polisyos.{package_name}.facade"
facade = sys.modules[facade_name]
source = (repo_root / "src" / "polisyos" / package_name / "facade.py").read_bytes()
tree = ast.parse(source)
map_names = ledger._literal_facade_mapping_names(tree)
source_maps, complete = ledger._literal_facade_mapping_values(tree, map_names)
assert complete
static_target = source_maps["_LAZY_EXPORTS"]["One"]
live_target = vars(facade)["_LAZY_EXPORTS"]["One"]
try:
    ledger._source_facade_runtime_projection(repo_root, closure)
except ledger.ConfidenceLedgerError as exc:
    print(json.dumps({
        "code": exc.code,
        "closure_has_selected_provider": f"polisyos.{package_name}.provider_one" in dict(closure),
        "closure_has_mutated_target": f"polisyos.{package_name}.provider_two" in dict(closure),
        "live_target": live_target,
        "static_target": static_target,
    }, sort_keys=True))
else:
    raise AssertionError("runtime map mutation was admitted")
"""
    environment = os.environ.copy()
    prior_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(REPO_ROOT / "src"), prior_pythonpath) if value
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(repo_root),
            str(REPO_ROOT / "src"),
            str(Path(ledger_module.__file__).resolve()),
            package_name,
            entry_module,
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    observation = json.loads(result.stdout)
    assert observation == {
        "code": "canonical_loaded_runtime_mismatch",
        "closure_has_selected_provider": True,
        "closure_has_mutated_target": False,
        "live_target": [f"polisyos.{package_name}.provider_two", "One"],
        "static_target": [f"polisyos.{package_name}.provider_one", "One"],
    }


def test_source_facade_projection_reconciles_full_core_contracts_map_and_fails_closed_on_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All Core contract exports bind to source and live map drift blocks reuse."""

    closure = ledger_module._resolve_authority_import_closure(REPO_ROOT, ledger_module.__name__)
    ledger_module._import_authority_closure_modules(closure)
    projection, _supplemental = ledger_module._source_facade_runtime_projection(
        REPO_ROOT,
        closure,
    )
    facades = {row["module"]: row for row in json.loads(projection)["facades"]}
    current_map_counts = {
        module_name: sum(len(values["$dict"]) for values in row["maps"].values())
        for module_name, row in facades.items()
    }
    assert current_map_counts == {
        "polisyos.core": 118,
        "polisyos.fabric": 58,
        "polisyos.ir": 496,
    }
    contracts_closure = ledger_module._resolve_authority_import_closure(
        REPO_ROOT,
        (ledger_module.__name__, "polisyos.core.contracts"),
    )
    ledger_module._import_authority_closure_modules(contracts_closure)
    contracts_projection, _contracts_supplemental = ledger_module._source_facade_runtime_projection(
        REPO_ROOT,
        contracts_closure,
    )
    contracts_facades = {row["module"]: row for row in json.loads(contracts_projection)["facades"]}
    contracts_row = contracts_facades["polisyos.core.contracts"]
    contracts = contracts_row["maps"]["_LAZY_IMPORTS"]["$dict"]
    owners = contracts_row["map_owners"]
    if len(owners) != len(contracts):
        pytest.fail("every source map row must have an owner projection")
    if {row["export"] for row in owners} != set(contracts):
        pytest.fail("owner projection must cover exactly the source map exports")
    if not all(row["provider_path"].startswith("src/polisyos/") for row in owners):
        pytest.fail("every owner provider must resolve inside the PolicyOS source tree")
    if not all(row["source_owner_status"] == "recomputed" for row in owners):
        pytest.fail("every map row must reconcile to its source owner")
    if not all(status == "recomputed" for status in contracts_row["map_transfer_status"].values()):
        pytest.fail("every source map transfer must be recomputed")
    if len(contracts) != sum(len(mapping["$dict"]) for mapping in contracts_row["maps"].values()):
        pytest.fail("owner projection must reconcile the complete source map set")

    owner_checker = ledger_module._repository_module_exports_symbol
    monkeypatch.setattr(
        ledger_module,
        "_repository_module_exports_symbol",
        lambda *_args, **_kwargs: False,
    )
    with pytest.raises(ConfidenceLedgerError, match="canonical_loaded_runtime_mismatch"):
        ledger_module._source_facade_runtime_projection(REPO_ROOT, contracts_closure)
    monkeypatch.setattr(ledger_module, "_repository_module_exports_symbol", owner_checker)

    facade = sys.modules["polisyos.core"]
    source_path = REPO_ROOT / "src/polisyos/core/__init__.py"
    source_text = source_path.read_text(encoding="utf-8")
    live_map = vars(facade)["_LAZY_EXPORTS"]
    original_map = dict(live_map)
    export, original_target = next(iter(original_map.items()))
    target = ledger_module._literal_facade_provider_target(export, original_target)
    assert target is not None
    assert "_LAZY_EXPORTS" in source_text and "import_module" in source_text
    assert export in source_text and target[0] in source_text

    monkeypatch.setattr(ledger_module, "_assert_ledger_artifact_contracts_current", lambda: None)
    monkeypatch.setattr(ledger_module, "_IMPORT_TIME_AUTHORITY_IMPORT_CLOSURE", closure)
    try:
        live_map[export] = (target[0], "_r7_wrong_cached_owner")
        with pytest.raises(ConfidenceLedgerError, match="canonical_loaded_runtime_mismatch"):
            ledger_module._assert_loaded_runtime_matches_import_baseline(REPO_ROOT)
    finally:
        live_map.clear()
        live_map.update(original_map)

    provider = importlib.import_module(target[0])
    expected_value = vars(provider)[target[1]]
    original_cached = vars(facade).get(export, ledger_module._STATIC_FACADE_UNKNOWN)
    assert getattr(facade, export) is expected_value
    try:
        vars(facade)[export] = object()
        with pytest.raises(ConfidenceLedgerError, match="canonical_loaded_runtime_mismatch"):
            ledger_module._source_facade_runtime_projection(REPO_ROOT, closure)
    finally:
        if original_cached is ledger_module._STATIC_FACADE_UNKNOWN:
            vars(facade).pop(export, None)
        else:
            vars(facade)[export] = original_cached


# R8 restores the R6 whole-class behavioral controls alongside R7 projection tests.


def _write_generated_mapping_pep562_closure_repo(repo_root: Path) -> tuple[Path, Path]:
    """Write a source-only facade whose lazy map is built from literal groups."""

    package = repo_root / "src/polisyos"
    facade = package / "facade"
    facade.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "entry.py").write_text(
        "from polisyos.facade import One, AliasOne, Two\n",
        encoding="utf-8",
    )
    (facade / "provider_one.py").write_text(
        "class One:\n    pass\nclass AliasOne:\n    pass\n",
        encoding="utf-8",
    )
    (facade / "provider_two.py").write_text("class Two:\n    pass\n", encoding="utf-8")
    (facade / "provider_wrong.py").write_text("class Unrelated:\n    pass\n", encoding="utf-8")
    facade_path = facade / "__init__.py"
    facade_path.write_text(
        "import importlib\n"
        '_MODULE_SYMBOLS = {".provider_one": ("One", "AliasOne"), '
        '".provider_two": ("Two",)}\n'
        "_LAZY_IMPORTS = {}\n"
        "for _relative, _symbols in _MODULE_SYMBOLS.items():\n"
        '    _full = f"polisyos.facade{_relative}"\n'
        "    for _symbol in _symbols:\n"
        "        _LAZY_IMPORTS[_symbol] = _full\n"
        "def __getattr__(name):\n"
        "    if name not in _LAZY_IMPORTS:\n"
        "        raise AttributeError(name)\n"
        "    module = importlib.import_module(_LAZY_IMPORTS[name])\n"
        "    value = getattr(module, name)\n"
        "    return value\n",
        encoding="utf-8",
    )
    return repo_root, facade_path


def test_authority_import_closure_accepts_unknown_branch_when_all_returns_bind_same_export(
    tmp_path: Path,
) -> None:
    """A bounded unknown branch is safe when every normal return is the same binding."""

    repo, facade = _write_generated_mapping_pep562_closure_repo(
        tmp_path / "generated-pep562-same-return-branches"
    )
    source = facade.read_text(encoding="utf-8")
    anchor = "    return value\n"
    replacement = "    if RUNTIME_OVERRIDE:\n        return value\n" + anchor
    source = "from os import name as RUNTIME_OVERRIDE\n" + source
    changed = source.replace(anchor, replacement, 1)
    assert changed != source
    facade.write_text(changed, encoding="utf-8")

    closure = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert closure["polisyos.facade.provider_one"] == "src/polisyos/facade/provider_one.py"


@pytest.mark.parametrize(
    "deferred",
    [
        pytest.param(
            "def _deferred():\n    _opaque_call()\n",
            id="function-body",
        ),
        pytest.param(
            "_deferred = lambda: _opaque_call()\n",
            id="lambda-body",
        ),
    ],
)
def test_authority_import_closure_does_not_execute_deferred_initializer_bodies(
    tmp_path: Path,
    deferred: str,
) -> None:
    """Deferred function and lambda bodies do not poison module initialization maps."""

    repo, facade = _write_generated_mapping_pep562_closure_repo(
        tmp_path / "generated-pep562-deferred-expression-body"
    )
    source = facade.read_text(encoding="utf-8")
    marker = "_LAZY_IMPORTS = {}\n"
    assert source.count(marker) == 1
    source = source.replace(marker, deferred + marker, 1)
    facade.write_text(source, encoding="utf-8")

    closure = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert closure["polisyos.facade.provider_one"] == "src/polisyos/facade/provider_one.py"
    assert closure["polisyos.facade.provider_two"] == "src/polisyos/facade/provider_two.py"


def test_authority_import_closure_keeps_same_selected_name_reassignment(
    tmp_path: Path,
) -> None:
    """A provably identity-preserving parameter write keeps the selected binding."""

    repo, facade = _write_generated_mapping_pep562_closure_repo(
        tmp_path / "generated-pep562-same-selected-name"
    )
    source = facade.read_text(encoding="utf-8").replace(
        "    module = importlib.import_module(_LAZY_IMPORTS[name])\n",
        '    if name == "One":\n        name = "One"\n'
        "    module = importlib.import_module(_LAZY_IMPORTS[name])\n",
        1,
    )
    assert 'name = "One"' in source
    facade.write_text(source, encoding="utf-8")

    closure = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert closure["polisyos.facade.provider_one"] == "src/polisyos/facade/provider_one.py"


@pytest.mark.parametrize(
    "intermediate_name",
    [
        "_full",
        "_module",
        "_MODULE_SYMBOLS alias",
        "conditional mutable alias",
        "nested mutable alias",
    ],
)
def test_authority_import_closure_propagates_unknown_module_branch_intermediaries(
    tmp_path: Path,
    intermediate_name: str,
) -> None:
    """Unknown writes to map-building intermediaries cannot leave a stale map green."""

    repo, facade = _write_generated_mapping_pep562_closure_repo(
        tmp_path / f"generated-pep562-unknown-intermediate-{intermediate_name}"
    )
    source = facade.read_text(encoding="utf-8")
    if intermediate_name == "nested mutable alias":
        source = source.replace(
            "_LAZY_IMPORTS = {}\n",
            "_ALIAS = [_MODULE_SYMBOLS]\n"
            "if RUNTIME_OVERRIDE:\n"
            '    _ALIAS[0][".provider_one"] = ("Two",)\n'
            "_LAZY_IMPORTS = {}\n",
            1,
        )
    elif intermediate_name == "_MODULE_SYMBOLS alias":
        source = source.replace(
            "_LAZY_IMPORTS = {}\n",
            "_ALIAS = _MODULE_SYMBOLS\n"
            "if RUNTIME_OVERRIDE:\n"
            '    _ALIAS[".provider_one"] = ("Two",)\n'
            "_LAZY_IMPORTS = {}\n",
            1,
        )
    elif intermediate_name == "conditional mutable alias":
        source = source.replace(
            "_LAZY_IMPORTS = {}\n",
            "_ALIAS = None\n"
            "if RUNTIME_OVERRIDE:\n"
            "    _ALIAS = _MODULE_SYMBOLS\n"
            "if True:\n"
            '    _ALIAS[".provider_one"] = ("Two",)\n'
            "_LAZY_IMPORTS = {}\n",
            1,
        )
    else:
        if intermediate_name == "_module":
            source = source.replace("_full", "_module")
        assignment = f'    {intermediate_name} = f"polisyos.facade{{_relative}}"\n'
        assert source.count(assignment) == 1
        source = source.replace(
            assignment,
            assignment
            + "    if RUNTIME_OVERRIDE:\n"
            + f'        {intermediate_name} = "polisyos.facade.provider_wrong"\n',
            1,
        )
    assert "_LAZY_IMPORTS" in source and "getattr(module, name)" in source
    facade.write_text(source, encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


@pytest.mark.parametrize(
    "initializer",
    [
        pytest.param("_result = _mutate_provider_map()\n", id="assignment-rhs"),
        pytest.param("_result: object = _mutate_provider_map()\n", id="annotated-assignment-rhs"),
        pytest.param("if _mutate_provider_map():\n    pass\n", id="branch-test"),
        pytest.param("for _item in _mutate_provider_map():\n    pass\n", id="loop-iterable"),
        pytest.param("_result = (_mutate_provider_map(),)\n", id="nested-container"),
        pytest.param(
            '_MODULE_SYMBOLS[_mutate_provider_map()] = ("One",)\n',
            id="assignment-target-index",
        ),
        pytest.param(
            "def _trigger(value=_mutate_provider_map()):\n    pass\n",
            id="function-default",
        ),
        pytest.param(
            "@(_mutate_provider_map() or (lambda value: value))\ndef _trigger():\n    pass\n",
            id="function-decorator",
        ),
        pytest.param(
            "_callback = lambda value=_mutate_provider_map(): None\n",
            id="lambda-default",
        ),
    ],
)
def test_authority_import_closure_refuses_opaque_effect_in_evaluated_initializer_expression(
    tmp_path: Path,
    initializer: str,
) -> None:
    """Every evaluated opaque initializer call invalidates the derived provider map."""

    repo, facade = _write_generated_mapping_pep562_closure_repo(
        tmp_path / "generated-pep562-opaque-expression-effect"
    )
    provider_two = repo / "src/polisyos/facade/provider_two.py"
    provider_two.write_text(
        "class One:\n    pass\nclass AliasOne:\n    pass\nclass Two:\n    pass\n",
        encoding="utf-8",
    )
    source = facade.read_text(encoding="utf-8")
    marker = "_LAZY_IMPORTS = {}\n"
    assert source.count(marker) == 1
    prelude = (
        "_ALIAS = _MODULE_SYMBOLS\n"
        "def _mutate_provider_map():\n"
        "    _ALIAS.clear()\n"
        '    _ALIAS[".provider_two"] = ("One", "AliasOne", "Two")\n'
        "    return ()\n"
    )
    source = source.replace(marker, prelude + initializer + marker, 1)
    assert all(
        item in source
        for item in (
            "_MODULE_SYMBOLS",
            "_LAZY_IMPORTS",
            "def __getattr__",
            "getattr(module, name)",
            "_ALIAS.clear()",
        )
    )
    facade.write_text(source, encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


@pytest.mark.parametrize(
    "insertion",
    [
        "before_selected_return",
        "after_selected_return_value",
        "unknown_alternate_return",
    ],
)
def test_authority_import_closure_rejects_alternate_normal_return_for_mapped_export(
    tmp_path: Path,
    insertion: str,
) -> None:
    """Every reachable normal return for a mapped name must preserve its provider."""

    repo, facade = _write_generated_mapping_pep562_closure_repo(
        tmp_path / f"generated-pep562-alternate-return-{insertion}"
    )
    source = facade.read_text(encoding="utf-8")
    if insertion == "before_selected_return":
        anchor = "    module = importlib.import_module(_LAZY_IMPORTS[name])\n"
        replacement = '    if name == "One":\n        return object()\n' + anchor
    elif insertion == "after_selected_return_value":
        anchor = "    return value\n"
        replacement = '    if name == "One":\n        return object()\n' + anchor
    else:
        anchor = "    return value\n"
        replacement = "    if RUNTIME_OVERRIDE:\n        return object()\n" + anchor
        source = source.replace("def __getattr__(name):\n", "def __getattr__(name):\n", 1)
        source = (
            "def _runtime_override():\n    return True\nRUNTIME_OVERRIDE = _runtime_override()\n"
            + source
        )
    changed = source.replace(anchor, replacement, 1)
    assert changed != source
    assert "_LAZY_IMPORTS" in changed and "getattr(module, name)" in changed
    facade.write_text(changed, encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_authority_import_closure_rejects_reassigned_selected_name_alias(
    tmp_path: Path,
) -> None:
    """An alias reassignment cannot return a different mapped export as the request."""

    repo, facade = _write_generated_mapping_pep562_closure_repo(
        tmp_path / "generated-pep562-reassigned-selected-name-alias"
    )
    source = facade.read_text(encoding="utf-8").replace(
        "    module = importlib.import_module(_LAZY_IMPORTS[name])\n"
        "    value = getattr(module, name)\n",
        "    selected = name\n"
        '    if selected == "One":\n        selected = "Two"\n'
        "    module = importlib.import_module(_LAZY_IMPORTS[selected])\n"
        "    value = getattr(module, selected)\n",
        1,
    )
    assert "_LAZY_IMPORTS[selected]" in source
    facade.write_text(source, encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


@pytest.mark.parametrize(
    "mutation",
    [
        ("wrong_existing_target",),
        ("removed_target_binding",),
        ("missing_map_entry",),
        ("dynamic_target",),
        ("rebound_imported_module",),
        ("rebound_extracted_value",),
        ("reassigned_selected_name",),
        ("branch_reassigned_selected_name",),
    ],
)
def test_authority_import_closure_rejects_unbound_generated_map_targets(
    tmp_path: Path,
    mutation: str,
) -> None:
    """A source map cannot claim an owner whose file does not bind the requested name."""

    repo, facade = _write_generated_mapping_pep562_closure_repo(
        tmp_path / f"generated-pep562-{mutation}"
    )
    markers = ("_MODULE_SYMBOLS", "_LAZY_IMPORTS", "def __getattr__", "getattr(module, name)")
    expected_error = "repository re-export target does not bind"
    if mutation == "wrong_existing_target":
        source = facade.read_text(encoding="utf-8").replace(
            '".provider_one": ("One", "AliasOne")',
            '".provider_wrong": ("One", "AliasOne")',
            1,
        )
        facade.write_text(source, encoding="utf-8")
    elif mutation == "missing_map_entry":
        source = facade.read_text(encoding="utf-8").replace(
            '".provider_one": ("One", "AliasOne")',
            '".provider_one": ("AliasOne",)',
            1,
        )
        facade.write_text(source, encoding="utf-8")
        expected_error = "missing repository re-export binding"
    elif mutation == "dynamic_target":
        source = facade.read_text(encoding="utf-8").replace(
            "_LAZY_IMPORTS[_symbol] = _full",
            "_LAZY_IMPORTS[_symbol] = choose_target(_full)",
            1,
        )
        facade.write_text(source, encoding="utf-8")
        expected_error = "non-literal repository re-export"
    elif mutation == "rebound_imported_module":
        source = facade.read_text(encoding="utf-8").replace(
            "    module = importlib.import_module(_LAZY_IMPORTS[name])\n"
            "    value = getattr(module, name)\n",
            "    module = importlib.import_module(_LAZY_IMPORTS[name])\n"
            '    module = importlib.import_module("polisyos.facade.provider_wrong")\n'
            "    value = getattr(module, name)\n",
            1,
        )
        facade.write_text(source, encoding="utf-8")
        expected_error = "non-literal repository re-export"
    elif mutation == "rebound_extracted_value":
        source = facade.read_text(encoding="utf-8").replace(
            "    value = getattr(module, name)\n    return value\n",
            "    value = getattr(module, name)\n    value = None\n    return value\n",
            1,
        )
        facade.write_text(source, encoding="utf-8")
        expected_error = "non-literal repository re-export"
    elif mutation == "reassigned_selected_name":
        source = facade.read_text(encoding="utf-8").replace(
            "    module = importlib.import_module(_LAZY_IMPORTS[name])\n",
            '    name = "Two"\n    module = importlib.import_module(_LAZY_IMPORTS[name])\n',
            1,
        )
        expected_error = "non-literal repository re-export"
    elif mutation == "branch_reassigned_selected_name":
        source = facade.read_text(encoding="utf-8").replace(
            "    module = importlib.import_module(_LAZY_IMPORTS[name])\n",
            '    if name == "One" and RUNTIME_OVERRIDE:\n'
            '        name = "Two"\n'
            "    module = importlib.import_module(_LAZY_IMPORTS[name])\n",
            1,
        )
        expected_error = "non-literal repository re-export"
    else:
        provider = repo / "src/polisyos/facade/provider_one.py"
        source = provider.read_text(encoding="utf-8").replace(
            "class One:\n    pass\n",
            "class RemovedOne:\n    pass\n",
            1,
        )
        provider.write_text(source, encoding="utf-8")
        source = facade.read_text(encoding="utf-8")
    assert all(marker in source for marker in markers)

    with pytest.raises(
        ConfidenceLedgerError,
        match=expected_error,
    ):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_authority_import_closure_resolves_finite_source_built_facade_maps(
    tmp_path: Path,
) -> None:
    """The real import consumer receives owners from a finite generated export map."""

    repo, _facade = _write_generated_mapping_pep562_closure_repo(
        tmp_path / "finite-generated-pep562-repo"
    )
    closure = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert closure["polisyos.facade.provider_one"] == "src/polisyos/facade/provider_one.py"
    assert closure["polisyos.facade.provider_two"] == "src/polisyos/facade/provider_two.py"
    assert "polisyos.facade.provider_wrong" not in closure


def test_authority_import_closure_refuses_unknown_dict_comprehension_source_map(
    tmp_path: Path,
) -> None:
    """A dynamic DictComp cannot certify exports or execute its source call."""

    repo, facade = _write_generated_mapping_pep562_closure_repo(
        tmp_path / "generated-pep562-unknown-dict-comprehension"
    )
    source = facade.read_text(encoding="utf-8")
    literal_map = (
        '_MODULE_SYMBOLS = {".provider_one": ("One", "AliasOne"), ".provider_two": ("Two",)}\n'
    )
    dynamic_map = (
        "def _unknown_groups():\n"
        '    raise AssertionError("source analysis must not execute this call")\n'
        "_MODULE_SYMBOLS = {module: symbols for module, symbols in _unknown_groups()}\n"
    )
    assert source.count(literal_map) == 1
    facade.write_text(source.replace(literal_map, dynamic_map, 1), encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_authority_import_closure_tracks_local_selected_name_alias(
    tmp_path: Path,
) -> None:
    """A simple local alias carries the selected export through the finite flow."""

    repo, facade = _write_generated_mapping_pep562_closure_repo(
        tmp_path / "generated-pep562-selected-name-alias"
    )
    source = facade.read_text(encoding="utf-8").replace(
        "    module = importlib.import_module(_LAZY_IMPORTS[name])\n"
        "    value = getattr(module, name)\n",
        "    selected = name\n"
        "    module = importlib.import_module(_LAZY_IMPORTS[selected])\n"
        "    value = getattr(module, selected)\n",
        1,
    )
    assert "_LAZY_IMPORTS[selected]" in source
    facade.write_text(source, encoding="utf-8")

    closure = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert closure["polisyos.facade.provider_one"] == "src/polisyos/facade/provider_one.py"
    assert closure["polisyos.facade.provider_two"] == "src/polisyos/facade/provider_two.py"


def test_core_contract_facade_missing_parser_row_fails_the_actual_provider_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing row in the complete runtime map cannot pass as an absent provider."""

    facade = REPO_ROOT / "src/polisyos/core/contracts/__init__.py"
    tree = ast.parse(facade.read_bytes(), filename=facade.relative_to(REPO_ROOT).as_posix())
    original_indexer = ledger_module._literal_module_getattr_provider_index
    complete = original_indexer(tree)
    incomplete = ledger_module._LiteralModuleGetattrProviderIndex(
        providers_by_export=types.MappingProxyType(
            {
                name: provider
                for name, provider in complete.providers_by_export.items()
                if name != "CatalogRunProfile"
            }
        ),
        invalid_exports=complete.invalid_exports,
        provider_symbols_by_export=complete.provider_symbols_by_export,
        generated_mapping_dispatch=complete.generated_mapping_dispatch,
    )
    assert complete.generated_mapping_dispatch
    monkeypatch.setattr(
        ledger_module,
        "_literal_module_getattr_provider_index",
        lambda _tree: incomplete,
    )

    with pytest.raises(ConfidenceLedgerError, match="missing repository re-export binding"):
        ledger_module._literal_module_getattr_provider(
            REPO_ROOT,
            "polisyos.core.contracts",
            "CatalogRunProfile",
            directory_entries={},
            source_index=ledger_module._AuthorityImportClosureSourceIndex({}, {}),
        )


def _write_tuple_unpacked_pep562_repo(repo_root: Path) -> tuple[Path, Path]:
    """Write a lazy facade that unpacks a selected finite map row before import."""

    package = repo_root / "src/polisyos"
    facade = package / "facade"
    facade.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "entry.py").write_text(
        "from polisyos.facade import One, AliasOne, Two\n",
        encoding="utf-8",
    )
    (facade / "provider_one.py").write_text(
        "class One:\n    pass\nclass AliasOne:\n    pass\n",
        encoding="utf-8",
    )
    (facade / "provider_two.py").write_text("class Two:\n    pass\n", encoding="utf-8")
    (facade / "provider_wrong.py").write_text("class Unrelated:\n    pass\n", encoding="utf-8")
    facade_path = facade / "__init__.py"
    facade_path.write_text(
        "import importlib\n"
        "_LAZY_EXPORTS = {\n"
        '    "One": ("polisyos.facade.provider_one", "One"),\n'
        '    "AliasOne": ("polisyos.facade.provider_one", "AliasOne"),\n'
        '    "Two": ("polisyos.facade.provider_two", "Two"),\n'
        "}\n"
        "def __getattr__(name):\n"
        "    if name not in _LAZY_EXPORTS:\n"
        "        raise AttributeError(name)\n"
        "    module_name, symbol_name = _LAZY_EXPORTS[name]\n"
        "    module = importlib.import_module(module_name)\n"
        "    value = getattr(module, symbol_name)\n"
        "    return value\n",
        encoding="utf-8",
    )
    return repo_root, facade_path


def test_authority_import_closure_resolves_tuple_unpacked_map_import_flow(
    tmp_path: Path,
) -> None:
    """A selected map pair remains bound through destructuring, import, and getattr."""

    repo, facade = _write_tuple_unpacked_pep562_repo(tmp_path / "tuple-unpacked-map-import-flow")
    closure = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert closure["polisyos.facade.provider_one"] == "src/polisyos/facade/provider_one.py"
    assert closure["polisyos.facade.provider_two"] == "src/polisyos/facade/provider_two.py"
    assert "polisyos.facade.provider_wrong" not in closure

    source = facade.read_text(encoding="utf-8")
    markers = ("_LAZY_EXPORTS", "module_name, symbol_name", "importlib.import_module", "getattr")
    assert all(marker in source for marker in markers)
    removed = source.replace(
        "    value = getattr(module, symbol_name)\n",
        "    raise AttributeError(name)\n",
        1,
    )
    assert removed != source and all(marker in removed for marker in markers)
    facade.write_text(removed, encoding="utf-8")
    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("reassigned_component", id="reassigned-component"),
        pytest.param("opaque_unpack", id="opaque-unpack"),
        pytest.param("unknown_branch", id="unknown-branch"),
    ],
)
def test_authority_import_closure_refuses_unproven_tuple_unpacked_map_flow(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Map-flow markers cannot replace exact component and return-path proof."""

    repo, facade = _write_tuple_unpacked_pep562_repo(tmp_path / f"tuple-unpacked-map-{mutation}")
    source = facade.read_text(encoding="utf-8")
    anchor = "    module_name, symbol_name = _LAZY_EXPORTS[name]\n"
    assert source.count(anchor) == 1
    if mutation == "reassigned_component":
        changed = source.replace(
            anchor,
            anchor + '    module_name = "polisyos.facade.provider_wrong"\n',
            1,
        )
    elif mutation == "opaque_unpack":
        changed = source.replace(
            anchor,
            "    module_name, symbol_name = select_pair(_LAZY_EXPORTS[name])\n",
            1,
        )
    else:
        changed = source.replace(
            anchor,
            anchor
            + "    if RUNTIME_OVERRIDE:\n"
            + '        module_name = "polisyos.facade.provider_wrong"\n',
            1,
        )
    assert changed != source
    assert all(
        marker in changed
        for marker in ("_LAZY_EXPORTS", "importlib.import_module", "getattr", "return value")
    )
    facade.write_text(changed, encoding="utf-8")

    with pytest.raises(ConfidenceLedgerError, match="non-literal repository re-export"):
        ledger_module._resolve_authority_import_closure(repo, "polisyos.entry")


def test_core_contract_generated_facade_map_binds_every_export_to_source_owner() -> None:
    """The complete runtime Core export map reconciles to source-bound providers."""

    facade = REPO_ROOT / "src/polisyos/core/contracts/__init__.py"
    tree = ast.parse(facade.read_bytes(), filename=facade.relative_to(REPO_ROOT).as_posix())
    provider_index = ledger_module._literal_module_getattr_provider_index(tree)
    assert provider_index.invalid_exports == frozenset()
    assert provider_index.providers_by_export["CatalogRunProfile"] == frozenset(
        {"polisyos.core.contracts.control"}
    )

    getattr_function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__"
    )
    parameter_name = getattr_function.args.args[0].arg
    mapping_names = frozenset(
        node.value.id
        for node in ast.walk(getattr_function)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and isinstance(node.slice, ast.Name)
        and node.slice.id == parameter_name
    )
    source_maps, invalid_maps = ledger_module._static_facade_mapping_values(tree, mapping_names)
    assert invalid_maps == frozenset()
    lazy_exports = source_maps["_LAZY_IMPORTS"]
    if not lazy_exports:
        pytest.fail("Core contracts source facade must expose its lazy export map")

    runtime_facade = importlib.import_module("polisyos.core.contracts")
    assert Path(runtime_facade.__file__).resolve() == facade.resolve()
    assert lazy_exports == runtime_facade._LAZY_IMPORTS
    assert len(runtime_facade.__all__) == len(set(runtime_facade.__all__))
    assert set(runtime_facade.__all__) <= set(lazy_exports) | set(runtime_facade._SUBMODULES)
    expected_providers = {
        export_name: frozenset({provider}) for export_name, provider in lazy_exports.items()
    }
    assert dict(provider_index.providers_by_export) == expected_providers
    assert dict(provider_index.provider_symbols_by_export or {}) == {
        export_name: frozenset({export_name}) for export_name in lazy_exports
    }

    source_index = ledger_module._AuthorityImportClosureSourceIndex({}, {})
    directory_entries: dict[Path, frozenset[str]] = {}
    for symbol, providers in expected_providers.items():
        assert len(providers) == 1, symbol
        target_symbols = (provider_index.provider_symbols_by_export or {}).get(
            symbol,
            frozenset({symbol}),
        )
        assert len(target_symbols) == 1, symbol
        provider = next(iter(providers))
        assert ledger_module._repository_module_exports_symbol(
            REPO_ROOT,
            provider,
            next(iter(target_symbols)),
            directory_entries=directory_entries,
            source_index=source_index,
        ), (symbol, provider, target_symbols)

    assert (
        ledger_module._literal_module_getattr_provider(
            REPO_ROOT,
            "polisyos.core.contracts",
            "CatalogRunProfile",
            directory_entries=directory_entries,
            source_index=source_index,
        )
        == "polisyos.core.contracts.control"
    )


def test_from_parent_child_import_still_resolves_the_python_submodule_route(
    tmp_path: Path,
) -> None:
    """ImportFrom child auto-import remains distinct from parent getattr binding."""

    repo = tmp_path / "import-from-child-repo"
    package = repo / "src/polisyos"
    parent = package / "parent"
    parent.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (parent / "__init__.py").write_text("", encoding="utf-8")
    (parent / "child.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "entry.py").write_text("from polisyos.parent import child\n", encoding="utf-8")

    closure = dict(ledger_module._resolve_authority_import_closure(repo, "polisyos.entry"))
    assert closure["polisyos.parent.child"] == "src/polisyos/parent/child.py"


def test_repository_module_exports_symbol_requires_runtime_binding_not_child_or_annotation(
    tmp_path: Path,
) -> None:
    """A child file and annotation-only name do not bind parent runtime attributes."""

    repo = tmp_path / "runtime-binding-repo"
    package = repo / "src/polisyos"
    parent = package / "parent"
    parent.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (parent / "__init__.py").write_text("", encoding="utf-8")
    (parent / "child.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "annotated.py").write_text("Symbol: object\n", encoding="utf-8")
    source_index = ledger_module._AuthorityImportClosureSourceIndex({}, {})

    assert not ledger_module._repository_module_exports_symbol(
        repo,
        "polisyos.parent",
        "child",
        directory_entries={},
        source_index=source_index,
    )
    assert not ledger_module._repository_module_exports_symbol(
        repo,
        "polisyos.annotated",
        "Symbol",
        directory_entries={},
        source_index=source_index,
    )


def test_source_facade_projection_tracks_lexical_imports_and_temporary_module_aliases(
    tmp_path: Path,
) -> None:
    """Bind selected imports to their actual lexical scope and final consumer."""

    repo_root = tmp_path / "source-runtime-binding-repo"
    package_name = "_n11_scope_" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:12]
    package_root = repo_root / "src" / "polisyos" / package_name
    (package_root / "common").mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "source-runtime-binding-fixture"\n', encoding="utf-8"
    )
    (repo_root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "facade.py").write_text(
        "import importlib as _importlib\n"
        "_LAZY_EXPORTS = {\n"
        f'    "One": ("polisyos.{package_name}.provider", "One"),\n'
        "}\n"
        "def __getattr__(name):\n"
        "    if name not in _LAZY_EXPORTS:\n"
        "        raise AttributeError(name)\n"
        "    module_name, symbol_name = _LAZY_EXPORTS[name]\n"
        "    return getattr(_importlib.import_module(module_name), symbol_name)\n",
        encoding="utf-8",
    )
    (package_root / "provider.py").write_text("class One:\n    pass\n", encoding="utf-8")
    (package_root / "common" / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "common" / "timestamps.py").write_text(
        "def parse_iso_date(value):\n    return value\n", encoding="utf-8"
    )
    (package_root / "local_good.py").write_text(
        f"def load():\n    from polisyos.{package_name}.facade import One as _one\n    return _one\n",
        encoding="utf-8",
    )
    (package_root / "local_rebound.py").write_text(
        f"def load():\n    from polisyos.{package_name}.facade import One as _one\n"
        "    _one = object()\n    return _one\n",
        encoding="utf-8",
    )
    (package_root / "local_nested_capture.py").write_text(
        f"def load():\n    from polisyos.{package_name}.facade import One as _one\n"
        "    def captured():\n        return _one\n"
        "    return _one\n",
        encoding="utf-8",
    )
    (package_root / "local_nested_nonlocal_rebound.py").write_text(
        f"def load():\n    from polisyos.{package_name}.facade import One as _one\n"
        "    def rebind():\n        nonlocal _one\n        _one = object()\n"
        "    rebind()\n    return _one\n",
        encoding="utf-8",
    )
    (package_root / "local_nested_shadowed.py").write_text(
        f"def load():\n    from polisyos.{package_name}.facade import One as _one\n"
        "    def echo(_one):\n        return _one\n"
        "    return echo(_one)\n",
        encoding="utf-8",
    )
    (package_root / "local_owner_rebound.py").write_text(
        f"def load():\n    from polisyos.{package_name}.facade import One as _one\n"
        "    return _one\n"
        "def replacement():\n    return None\n"
        "load = replacement\n",
        encoding="utf-8",
    )
    (package_root / "local_owner_code_mutated.py").write_text(
        f"def load():\n    from polisyos.{package_name}.facade import One as _one\n"
        "    return _one\n"
        "def replacement():\n    return None\n",
        encoding="utf-8",
    )
    (package_root / "class_method_good.py").write_text(
        f"class Owner:\n    @classmethod\n    def load(cls):\n"
        f"        from polisyos.{package_name}.facade import One as _one\n"
        "        return cls, _one\n",
        encoding="utf-8",
    )
    (package_root / "module_good.py").write_text(
        f"from polisyos.{package_name}.common import timestamps as _common_timestamps\n"
        "parse_iso_date = _common_timestamps.parse_iso_date\n"
        "del _common_timestamps\n"
        "def normalize(value):\n    return parse_iso_date(value)\n",
        encoding="utf-8",
    )
    (package_root / "module_rebound.py").write_text(
        f"from polisyos.{package_name}.common import timestamps as _common_timestamps\n"
        "parse_iso_date = _common_timestamps.parse_iso_date\n"
        "del _common_timestamps\n"
        "parse_iso_date = object()\n",
        encoding="utf-8",
    )

    script = r"""
import importlib
import importlib.util
import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
product_source = Path(sys.argv[2])
candidate_source = Path(sys.argv[3])
package_name = sys.argv[4]
sys.path.insert(0, str(product_source))
import polisyos
polisyos.__path__.append(str(repo_root / "src" / "polisyos"))
spec = importlib.util.spec_from_file_location("n11_scope_candidate_ledger", candidate_source)
ledger = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ledger
spec.loader.exec_module(ledger)
observations = {}
for entry_name in (
    "local_good",
    "local_rebound",
    "local_nested_capture",
    "local_nested_nonlocal_rebound",
    "local_nested_shadowed",
    "local_owner_rebound",
    "local_owner_code_mutated",
    "class_method_good",
    "module_good",
    "module_rebound",
):
    module_name = f"polisyos.{package_name}.{entry_name}"
    closure = ledger._resolve_authority_import_closure(repo_root, module_name)
    ledger._import_authority_closure_modules(closure)
    imported = sys.modules[module_name]
    owner_identity_preserved = None
    if entry_name in {"local_owner_rebound", "local_owner_code_mutated"}:
        original_owner = imported.load
        if entry_name == "local_owner_rebound":
            imported.load = imported.replacement
        else:
            imported.load.__code__ = imported.replacement.__code__
        owner_identity_preserved = imported.load is original_owner
    try:
        projection, supplemental = ledger._source_facade_runtime_projection(repo_root, closure)
    except ledger.ConfidenceLedgerError as exc:
        observations[entry_name] = {"status": "refused", "code": exc.code, "detail": exc.detail}
        if owner_identity_preserved is not None:
            observations[entry_name]["same_owner_object"] = owner_identity_preserved
        continue
    bindings = json.loads(projection)["bindings"]
    observations[entry_name] = {
        "status": "admitted",
        "bindings": bindings,
        "supplemental": supplemental,
        "local_value": (
            f"{imported.load().__module__}.{imported.load().__name__}"
            if entry_name in {"local_good", "local_nested_shadowed"}
            else None
        ),
        "module_alias_absent": "_common_timestamps" not in vars(imported),
        "module_value": imported.normalize("2026-10-17") if entry_name == "module_good" else None,
    }
print(json.dumps(observations, sort_keys=True, default=str))
"""
    environment = os.environ.copy()
    prior_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(REPO_ROOT / "src"), prior_pythonpath) if value
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(repo_root),
            str(REPO_ROOT / "src"),
            str(Path(ledger_module.__file__).resolve()),
            package_name,
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    observations = json.loads(result.stdout)
    assert observations["local_good"]["status"] == "admitted"
    assert observations["local_good"]["local_value"] == (f"polisyos.{package_name}.provider.One")
    local_binding = next(
        row
        for row in observations["local_good"]["bindings"]
        if row["facade"] == f"polisyos.{package_name}.facade" and row["export"] == "One"
    )
    assert local_binding["importers"] == [
        {
            "module": f"polisyos.{package_name}.local_good",
            "name": "_one",
            "scope": "function_local",
            "owner": "load",
            "line": "2",
        }
    ]
    assert observations["local_rebound"]["status"] == "refused"
    assert observations["local_rebound"]["code"] == "canonical_loaded_runtime_mismatch"
    for entry_name in ("local_nested_capture", "local_nested_nonlocal_rebound"):
        assert observations[entry_name]["status"] == "refused"
        assert observations[entry_name]["code"] == "canonical_loaded_runtime_mismatch"
    assert observations["local_nested_shadowed"]["status"] == "admitted"
    assert observations["local_nested_shadowed"]["local_value"] == (
        f"polisyos.{package_name}.provider.One"
    )
    for entry_name in ("local_owner_rebound", "local_owner_code_mutated"):
        assert observations[entry_name]["status"] == "refused"
        assert observations[entry_name]["code"] == "canonical_loaded_runtime_mismatch"
    assert observations["local_owner_rebound"]["same_owner_object"] is False
    assert observations["local_owner_code_mutated"]["same_owner_object"] is True
    assert observations["class_method_good"]["status"] == "admitted"
    class_method_binding = next(
        row
        for row in observations["class_method_good"]["bindings"]
        if row["facade"] == f"polisyos.{package_name}.facade" and row["export"] == "One"
    )
    assert class_method_binding["importers"] == [
        {
            "module": f"polisyos.{package_name}.class_method_good",
            "name": "_one",
            "scope": "function_local",
            "owner": "Owner.load",
            "line": "4",
        }
    ]

    assert observations["module_good"]["status"] == "admitted"
    assert observations["module_good"]["module_alias_absent"] is True
    assert observations["module_good"]["module_value"] == "2026-10-17"
    module_binding = next(
        row
        for row in observations["module_good"]["bindings"]
        if row["facade"] == f"polisyos.{package_name}.module_good"
        and row["export"] == "parse_iso_date"
    )
    assert module_binding["provider"] == f"polisyos.{package_name}.common.timestamps"
    assert module_binding["importers"][0]["scope"] == "module_value"
    assert observations["module_rebound"]["status"] == "refused"
    assert observations["module_rebound"]["code"] == "canonical_loaded_runtime_mismatch"
