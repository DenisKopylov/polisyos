"""Budget ledger intake, syscall faults, and real process interruption controls."""

from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware


def _exhausted() -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))},
        spent={"run": Decimal("10")},
    )


@pytest.mark.parametrize("field", ["schema_version", "revision", "updated_at", "state"])
def test_missing_snapshot_field_never_defaults_into_permission(tmp_path: Path, field: str) -> None:
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(_exhausted())
    payload = json.loads(path.read_text())
    del payload[field]
    path.write_text(json.dumps(payload))
    before = path.read_bytes()

    for read in (
        ledger.load,
        ledger.snapshot,
        lambda: BudgetMiddleware(_exhausted(), ledger=ledger),
    ):
        with pytest.raises(ValueError):
            read()
    with pytest.raises(ValueError):
        ledger.record_spend("run", Decimal("1"))
    assert path.read_bytes() == before


@pytest.mark.parametrize("field", list(BudgetState.model_fields))
def test_missing_budget_map_refuses_all_existing_file_paths(tmp_path: Path, field: str) -> None:
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(_exhausted())
    middleware = BudgetMiddleware(_exhausted(), ledger=ledger)
    payload = json.loads(path.read_text())
    del payload["state"][field]
    path.write_text(json.dumps(payload))
    before = path.read_bytes()

    with pytest.raises(ValueError):
        middleware.pre_check("protected-node")
    with pytest.raises(ValueError):
        BudgetMiddleware(_exhausted(), ledger=ledger)
    with pytest.raises(ValueError):
        ledger.record_spend("run", Decimal("1"))
    assert path.read_bytes() == before


@pytest.mark.parametrize("raw", ["", " \n", '{"state":', "{}", '{"revision":1}'])
def test_corruption_differs_from_absent_bootstrap(tmp_path: Path, raw: str) -> None:
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path)
    middleware = BudgetMiddleware(_exhausted(), ledger=ledger)
    with pytest.raises(BudgetExhaustedError):
        middleware.pre_check("protected-node")
    path.write_text(raw)
    with pytest.raises(ValueError):
        middleware.pre_check("protected-node")
    with pytest.raises(ValueError):
        BudgetMiddleware(_exhausted(), ledger=ledger)
    assert path.read_text() == raw


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", True, None, []])
@pytest.mark.parametrize("field", ["spent", "reserved", "provider_spent", "limits"])
def test_invalid_persisted_amounts_never_admit_consumer(
    tmp_path: Path, field: str, value: object
) -> None:
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(_exhausted())
    payload = json.loads(path.read_text())
    payload["state"][field]["run"] = (
        {"key": "run", "max_usd": value} if field == "limits" else value
    )
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        BudgetMiddleware(_exhausted(), ledger=ledger)


def test_legacy_contract_metadata_upgrade_preserves_complete_state(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(_exhausted())
    payload = json.loads(path.read_text())
    for field in ("canonical_contract", "coordination_mode", "ledger_id"):
        payload.pop(field)
    path.write_text(json.dumps(payload))

    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    with pytest.raises(BudgetExhaustedError):
        middleware.pre_check("protected-node")
    assert ledger.snapshot().revision == 0
    assert ledger.snapshot().state.spent["run"] == Decimal("10")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("revision", True),
        ("revision", "1"),
        ("revision", -1),
        ("updated_at", None),
        ("updated_at", "invalid"),
        ("updated_at", 0),
    ],
)
def test_invalid_snapshot_identity_is_not_reconstructed(
    tmp_path: Path, field: str, value: object
) -> None:
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(_exhausted())
    payload = json.loads(path.read_text())
    payload[field] = value
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        BudgetMiddleware(_exhausted(), ledger=ledger)


def test_explicit_complete_unlimited_budget_remains_supported(tmp_path: Path) -> None:
    ledger = FileBudgetLedger(tmp_path / "budget.json")
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    middleware.pre_check("unbounded-node")
    assert middleware.reserve_safe("run", Decimal("10")) is True
    assert ledger.load().limits == {}


def test_complete_large_snapshot_uses_same_intake_on_reopen_and_mutation(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path)
    state = _exhausted()
    state.provider_spent = {f"provider-{i}-{'x' * 80}": Decimal("0") for i in range(12_000)}
    ledger.load_or_bootstrap(state)
    assert path.stat().st_size > 1_000_000
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    with pytest.raises(BudgetExhaustedError):
        middleware.pre_check("protected-node")
    ledger.record_spend("run", Decimal("1"))
    assert ledger.snapshot().revision == 1
    assert ledger.load().spent["run"] == Decimal("11")


def test_invalid_producer_amount_never_replaces_last_valid_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(_exhausted())
    before = path.read_bytes()
    with pytest.raises(ValueError):
        ledger.record_spend("run", Decimal("-1"))
    assert path.read_bytes() == before
    with pytest.raises(BudgetExhaustedError):
        BudgetMiddleware(BudgetState(), ledger=ledger).pre_check("protected-node")


@pytest.mark.parametrize("field", ["amount", "applied_amount"])
def test_invalid_journal_amount_is_refused_with_valid_totals(tmp_path: Path, field: str) -> None:
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(_exhausted())
    ledger.record_spend("run", Decimal("1"))
    payload = json.loads(path.read_text())
    payload["recent_mutations"][-1][field] = "-1"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        BudgetMiddleware(BudgetState(), ledger=ledger)


@pytest.mark.parametrize("boundary", ["temp-fsync", "replace", "directory-fsync"])
def test_syscall_failure_leaves_valid_old_or_new_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(_exhausted())
    before = path.read_bytes()
    real_fsync = os.fsync
    fsync_calls = 0

    def fsync(fd: int) -> None:
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == (2 if boundary == "directory-fsync" else 1):
            raise OSError("injected fsync failure")
        real_fsync(fd)

    def replace(source: object, target: object) -> None:
        raise OSError("injected replace failure")

    with monkeypatch.context() as fault:
        fault.setattr(
            os,
            "replace" if boundary == "replace" else "fsync",
            (replace if boundary == "replace" else fsync),
        )
        with pytest.raises(OSError):
            ledger.record_spend("run", Decimal("5"))

    snapshot = ledger.snapshot()
    expected = Decimal("15") if boundary == "directory-fsync" else Decimal("10")
    assert snapshot.state.spent["run"] == expected
    assert snapshot.revision == (1 if boundary == "directory-fsync" else 0)
    if boundary != "directory-fsync":
        assert path.read_bytes() == before
    with pytest.raises(BudgetExhaustedError):
        BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path)).pre_check("protected-node")
    assert list(tmp_path.glob(".budget.json.tmp-*")) == []


_CRASH_WRITER = """
import os, sys
from decimal import Decimal
from pathlib import Path
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
path, boundary = Path(sys.argv[1]), sys.argv[2]
real_fsync, real_replace = os.fsync, os.replace
fsync_calls = 0
def pause():
    print('boundary', flush=True)
    sys.stdin.readline()
def fsync(fd):
    global fsync_calls
    fsync_calls += 1
    if boundary == 'temp-write' and fsync_calls == 1:
        pause()
    real_fsync(fd)
    if (boundary == 'temp-fsync' and fsync_calls == 1 or
            boundary == 'directory-fsync' and fsync_calls == 2):
        pause()
def replace(source, target):
    real_replace(source, target)
    if boundary == 'replace':
        pause()
os.fsync, os.replace = fsync, replace
if len(sys.argv) > 3:
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    FileBudgetLedger(path).load_or_bootstrap(BudgetState(
        limits={'run': BudgetLimit(key='run', max_usd=Decimal('10'))},
        spent={'run': Decimal('10')},
    ))
else:
    FileBudgetLedger(path).record_spend('run', Decimal('5'))
"""


def _kill_writer_at_boundary(path: Path, boundary: str, *, bootstrap: bool = False) -> None:
    writer = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _CRASH_WRITER,
            str(path),
            boundary,
            *(["bootstrap"] if bootstrap else []),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert writer.stdout is not None
        assert select.select([writer.stdout], [], [], 15)[0], (
            "writer did not reach syscall boundary"
        )
        assert writer.stdout.readline().strip() == "boundary"
        writer.kill()
        stdout, stderr = writer.communicate(timeout=15)
        assert writer.returncode == -signal.SIGKILL, (stdout, stderr)
    finally:
        if writer.poll() is None:
            writer.kill()
            writer.communicate(timeout=15)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux SIGKILL/process receipt")
@pytest.mark.parametrize("boundary", ["temp-write", "temp-fsync", "replace", "directory-fsync"])
def test_sigkill_writer_reopens_old_or_new_state_in_consumer(tmp_path: Path, boundary: str) -> None:
    path = tmp_path / "budget.json"
    FileBudgetLedger(path).load_or_bootstrap(_exhausted())
    _kill_writer_at_boundary(path, boundary)
    ledger = FileBudgetLedger(path)
    expected = Decimal("15") if boundary in {"replace", "directory-fsync"} else Decimal("10")
    assert ledger.snapshot().state.spent["run"] == expected
    assert ledger.snapshot().revision == (1 if expected == Decimal("15") else 0)
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    for _ in range(3):
        with pytest.raises(BudgetExhaustedError):
            middleware.pre_check("protected-node")
    assert ledger.load().spent["run"] == expected


@pytest.mark.skipif(sys.platform != "linux", reason="Linux SIGKILL/process receipt")
@pytest.mark.parametrize("boundary", ["temp-write", "temp-fsync", "replace", "directory-fsync"])
def test_first_publication_crash_keeps_absence_or_complete_bootstrap(
    tmp_path: Path, boundary: str
) -> None:
    path = tmp_path / "budget.json"
    _kill_writer_at_boundary(path, boundary, bootstrap=True)
    assert path.exists() == (boundary in {"replace", "directory-fsync"})
    middleware = BudgetMiddleware(_exhausted(), ledger=FileBudgetLedger(path))
    with pytest.raises(BudgetExhaustedError):
        middleware.pre_check("protected-node")
    assert middleware.budget_state.spent["run"] == Decimal("10")


_CONCURRENT_WRITER = """
import sys
from pathlib import Path
from decimal import Decimal
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
ledger = FileBudgetLedger(Path(sys.argv[1]))
sys.stdin.readline()
for _ in range(10):
    ledger.record_spend('run', Decimal('1'))
    observed = ledger.load()
    assert observed.limits['run'].max_usd == Decimal('40')
    assert observed.spent['run'] >= Decimal('1')
"""


def test_concurrent_process_mutations_preserve_all_spend_and_consumer_limit(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(
        BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("40"))},
            spent={"run": Decimal("0")},
        )
    )
    writers = [
        subprocess.Popen(
            [sys.executable, "-c", _CONCURRENT_WRITER, str(path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(4)
    ]
    try:
        for writer in writers:
            assert writer.stdin is not None
            writer.stdin.write("start\n")
            writer.stdin.flush()
        for writer in writers:
            stdout, stderr = writer.communicate(timeout=30)
            assert writer.returncode == 0, (stdout, stderr)
    finally:
        for writer in writers:
            if writer.poll() is None:
                writer.kill()
                writer.communicate(timeout=15)

    assert ledger.snapshot().revision == 40
    assert ledger.load().spent["run"] == Decimal("40")
    with pytest.raises(BudgetExhaustedError):
        BudgetMiddleware(BudgetState(), ledger=ledger).pre_check("protected-node")
