"""Exercise bounded terminal bytes and the shared actual-transfer budget."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import BaseModel

from polisyos.core.artifacts import PutOptions, SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.canonical_profile import (
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.core.trace import RunTerminality
from polisyos.core.trace.record import TraceRecord
from polisyos.runtime.http.services import debug_registered_sql
from polisyos.runtime.http.services.adapters.core_run import (
    _bounded_terminal_json_read,
    _bounded_terminal_trace_facts,
    _iter_bounded_terminal_bytes,
)
from polisyos.scientist.nodes.builtins.decide import (
    policy_runtime_method_metrics as metrics,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
    _BoundedExecutionSourceReader,
    _ProjectionReadBudget,
)


def test_terminal_trace_consumes_actual_bytes_at_the_shared_limit(
    tmp_path: Path,
) -> None:
    """A byte below the actual trace refuses; exact and above preserve every line."""
    path = tmp_path / "trace.jsonl"
    raw = b'{"a":1}\n{"b":"x"}\n'
    path.write_bytes(raw)

    def read(cap: int) -> tuple[list[str], int]:
        budget = _ProjectionReadBudget(max_bytes=cap)
        fd = os.open(path, os.O_RDONLY)
        try:
            return list(_iter_bounded_terminal_bytes(fd, budget)), budget.observed_bytes
        finally:
            os.close(fd)

    with pytest.raises(ValueError, match="terminal_trace_aggregate_budget_exceeded"):
        read(len(raw) - 1)
    assert read(len(raw)) == (['{"a":1}', '{"b":"x"}'], len(raw))
    assert read(len(raw) + 1) == (['{"a":1}', '{"b":"x"}'], len(raw))

    path.write_bytes(b"x" * (2 * 1024 * 1024 + 1) + b"\n")
    with pytest.raises(ValueError, match="terminal_trace_record_exceeds_bound"):
        read(3 * 1024 * 1024)


def test_bounded_trace_retains_the_existing_lifecycle_contract(tmp_path: Path) -> None:
    """The streaming path still requires the actual leading/final owner facts."""
    root = tmp_path / "runs"
    run_id = "R_bounded_trace"
    directory = root / run_id
    directory.mkdir(parents=True)
    trace = directory / "trace.jsonl"
    start = TraceRecord(
        run_id=run_id,
        tenant_id="t",
        cell_id="c",
        phase="core",
        event="RUN_STARTED",
        run_terminality=RunTerminality.NON_TERMINAL,
    )
    end = TraceRecord(
        run_id=run_id,
        tenant_id="t",
        cell_id="c",
        phase="core",
        event="RUN_FINALIZED",
        run_terminality=RunTerminality.TERMINAL,
    )
    raw = (start.model_dump_json() + "\n" + end.model_dump_json() + "\n").encode()
    trace.write_bytes(raw)
    budget = _ProjectionReadBudget(max_bytes=len(raw))
    owner, terminal = _bounded_terminal_trace_facts(root, run_id, read_attempts=None, budget=budget)
    assert owner == start and terminal == end
    assert budget.observed_bytes == len(raw)

    trace.write_text(start.model_dump_json() + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="RUN_FINALIZED"):
        _bounded_terminal_trace_facts(
            root, run_id, read_attempts=None, budget=_ProjectionReadBudget()
        )


def test_real_selected_json_and_child_phases_share_one_byte_budget(
    tmp_path: Path,
) -> None:
    """A real CAS member charges selection, verification, and payload transfers."""
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        {"message": "selected terminal payload"},
        PutOptions(
            kind="test.terminal_budget",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.tests.TerminalBudget", version="1.0"),
        ),
        canon_spec=CanonSpec(),
        return_selected_profile=True,
    )
    limits = CoreJsonReadLimits(
        max_bytes=4_096, max_depth=16, max_elements=100, max_manifest_bytes=8_192
    )
    observed = _ProjectionReadBudget()
    first = _bounded_terminal_json_read(store, ref, observed, limits=limits)
    assert first.value == {"message": "selected terminal payload"}
    exact = observed.observed_bytes
    assert exact > len(first.raw_payload_bytes)

    for cap in (exact, exact + 1):
        parent = _ProjectionReadBudget(max_bytes=cap)
        phase = _ProjectionReadBudget(parent=parent)
        read = _bounded_terminal_json_read(store, ref, phase, limits=limits)
        assert read.value == first.value
        assert phase.observed_bytes == parent.observed_bytes == exact
    parent = _ProjectionReadBudget(max_bytes=exact - 1)
    phase = _ProjectionReadBudget(parent=parent)
    with pytest.raises(ValueError):
        _bounded_terminal_json_read(store, ref, phase, limits=limits)
    assert parent.observed_bytes == phase.observed_bytes

    oversized = CoreJsonReadLimits(
        max_bytes=4, max_depth=16, max_elements=100, max_manifest_bytes=8_192
    )
    with pytest.raises(ValueError, match="bounded_read_refused"):
        _bounded_terminal_json_read(store, ref, _ProjectionReadBudget(), limits=oversized)


def test_typed_validation_refusal_charges_real_successful_transfer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A typed refusal cannot erase bytes already transferred by the Core reader."""

    class RequiredNumber(BaseModel):
        required_number: int

    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        {"actual": "valid JSON but not the required model"},
        PutOptions(
            kind="test.invalid_typed_model",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.tests.ActualPayload", version="1.0"),
        ),
        canon_spec=CanonSpec(),
        return_selected_profile=True,
    )
    receipts = []
    read = metrics.read_core_json_artifact_bounded

    def observe(*args, **kwargs):
        receipt = read(*args, **kwargs)
        receipts.append(receipt)
        return receipt

    monkeypatch.setattr(metrics, "read_core_json_artifact_bounded", observe)
    parent = _ProjectionReadBudget()
    phase = _ProjectionReadBudget(parent=parent)
    with pytest.raises(ValueError, match="typed_model_invalid"):
        _BoundedExecutionSourceReader(store, phase).read_typed_model(RequiredNumber, ref)
    assert len(receipts) == 1
    assert receipts[0].observed_source_bytes > 0
    assert parent.observed_bytes == phase.observed_bytes == receipts[0].observed_source_bytes


def test_actual_binary_state_ref_and_failed_comparison_charge_owner_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NPZ-like bytes admit without JSON canon; mismatch still charges actual reads."""
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        b"good",
        PutOptions(kind="foundry.state_blob", media_type="application/x-npz"),
        return_selected_profile=True,
    )
    manifest_reads = []
    member_attempts = []
    mode = {"wrong_manifest_digest": False}
    read_manifest = debug_registered_sql.read_core_manifest_profile_bounded
    open_member = store.open_member_bounded

    def observe_manifest(*args, **kwargs):
        receipt = read_manifest(*args, **kwargs)
        manifest_reads.append(receipt)
        return receipt

    def observe_member(*args, **kwargs):
        if mode["wrong_manifest_digest"]:
            kwargs["expected_manifest_sha256"] = "0" * 64
        attempt = open_member(*args, **kwargs)
        member_attempts.append(attempt)
        return attempt

    monkeypatch.setattr(
        debug_registered_sql, "read_core_manifest_profile_bounded", observe_manifest
    )
    monkeypatch.setattr(store, "open_member_bounded", observe_member)
    parent = _ProjectionReadBudget()
    phase = _ProjectionReadBudget(parent=parent)
    debug_registered_sql._require_bound_blob(store, state_ref=ref, expected=b"good", budget=phase)
    assert (
        parent.observed_bytes
        == phase.observed_bytes
        == (
            manifest_reads[-1].observed_source_bytes
            + member_attempts[-1].usage.observed_source_bytes
        )
    )
    assert member_attempts[-1].usage.payload_integrity_verified is True

    refused_parent = _ProjectionReadBudget()
    refused = _ProjectionReadBudget(parent=refused_parent)
    with pytest.raises(ValueError, match="bound_state_bytes_mismatch"):
        debug_registered_sql._require_bound_blob(
            store, state_ref=ref, expected=b"bad!", budget=refused
        )
    expected_usage = (
        manifest_reads[-1].observed_source_bytes + member_attempts[-1].usage.observed_source_bytes
    )
    assert expected_usage > 0
    assert refused_parent.observed_bytes == refused.observed_bytes == expected_usage

    # A real selected manifest is read again in member.__enter__; an integrity
    # refusal there must retain that transfer even though no member is yielded.
    mode["wrong_manifest_digest"] = True
    enter_parent = _ProjectionReadBudget()
    enter_phase = _ProjectionReadBudget(parent=enter_parent)
    with pytest.raises(ValueError, match="cas_member_manifest_changed"):
        debug_registered_sql._require_bound_blob(
            store, state_ref=ref, expected=b"good", budget=enter_phase
        )
    expected_enter_usage = (
        manifest_reads[-1].observed_source_bytes + member_attempts[-1].usage.observed_source_bytes
    )
    assert member_attempts[-1].usage.observed_manifest_verification_bytes > 0
    assert enter_parent.observed_bytes == enter_phase.observed_bytes == expected_enter_usage


def test_invalid_binary_manifest_still_charges_its_real_selected_transfer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A forged binary schema is refused after its measured manifest transfer."""
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        b"good",
        PutOptions(
            kind="foundry.state_blob",
            media_type="application/x-npz",
            schema=SchemaInfo(name="forged.binary.schema", version="1.0"),
        ),
        return_selected_profile=True,
    )
    receipts = []
    read_manifest = metrics.read_core_manifest_profile_bounded

    def observe(*args, **kwargs):
        receipt = read_manifest(*args, **kwargs)
        receipts.append(receipt)
        return receipt

    monkeypatch.setattr(metrics, "read_core_manifest_profile_bounded", observe)
    parent = _ProjectionReadBudget()
    phase = _ProjectionReadBudget(parent=parent)
    with pytest.raises(ValueError, match="state_blob_manifest_identity_mismatch"):
        _BoundedExecutionSourceReader(store, phase)._read_bound_state_blob_manifest(
            input_ref_from_artifact_ref(ref, role="state_blob"),
            ref,
            max_manifest_bytes=phase.max_manifest_bytes,
        )
    assert len(receipts) == 1 and receipts[0].observed_source_bytes > 0
    assert parent.observed_bytes == phase.observed_bytes == receipts[0].observed_source_bytes


def test_unknown_core_transfer_invalidates_the_parent_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An owner refusal with unknown bytes cannot become a zero-byte exact receipt."""

    class AnyModel(BaseModel):
        value: int

    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        {"value": 1},
        PutOptions(
            kind="test.unknown_usage",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.tests.UnknownUsage", version="1.0"),
        ),
        canon_spec=CanonSpec(),
        return_selected_profile=True,
    )

    def unknown_usage(*args, **kwargs):
        raise CoreJsonReadBoundsRefusalError(
            "simulated_owner_usage_unavailable",
            limits=None,
            max_manifest_bytes=4096,
            observed_manifest_bytes=None,
            observed_bytes=None,
            observed_depth=0,
            observed_elements=0,
            source_usage_complete=False,
        )

    monkeypatch.setattr(metrics, "read_core_json_artifact_bounded", unknown_usage)
    parent = _ProjectionReadBudget()
    phase = _ProjectionReadBudget(parent=parent)
    with pytest.raises(ValueError, match="core_store_transfer_accounting_not_established"):
        _BoundedExecutionSourceReader(store, phase).read_typed_model(AnyModel, ref)
    assert parent.observed_bytes == phase.observed_bytes == 0
    assert not parent.source_usage_established and not phase.source_usage_established
    assert parent.remaining_bytes == phase.remaining_bytes == 0
