from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    ControlPlaneStore,
)


def _make_store(tmp_path: Path) -> ControlPlaneStore:
    return ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )


def _action_scope() -> dict[str, Any]:
    return {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-a",
        "source_job_id": "source-job",
        "route_id": "sha256:" + "a" * 64,
        "action_generation": 1,
    }


def _receipt_ref(character: str) -> str:
    return "sha256:" + character * 64


def _append_head(
    store: ControlPlaneStore,
    scope: dict[str, Any],
    *,
    receipt_ref: str,
    expected_head_generation: int,
    predecessor_receipt_ref: str | None,
    receipt_phase: str,
) -> AcquisitionActionHeadRecord:
    coarse_phase, recovery_state = {
        "requested": ("requested", "none"),
        "executing": ("executing", "none"),
        "outcome_selected": ("executing", "none"),
        "terminal": ("terminal", "complete"),
    }[receipt_phase]
    return store.advance_acquisition_action_head(
        **scope,
        expected_head_generation=expected_head_generation,
        receipt_ref=receipt_ref,
        receipt_sha256=receipt_ref,
        durable_event_id=f"event-{expected_head_generation + 1}",
        coarse_phase=coarse_phase,
        receipt_phase=receipt_phase,
        recovery_state=recovery_state,
        job_id="action-job",
        predecessor_receipt_ref=predecessor_receipt_ref,
    )


def test_action_head_history_resolves_old_receipt_after_terminal_append(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    requested = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("a"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
    )
    executing = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("b"),
        expected_head_generation=1,
        predecessor_receipt_ref=requested.receipt_ref,
        receipt_phase="executing",
    )
    selected = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("c"),
        expected_head_generation=2,
        predecessor_receipt_ref=executing.receipt_ref,
        receipt_phase="outcome_selected",
    )
    terminal = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("d"),
        expected_head_generation=3,
        predecessor_receipt_ref=selected.receipt_ref,
        receipt_phase="terminal",
    )

    assert store.get_acquisition_action_head(**scope) == terminal
    assert (
        store.get_acquisition_action_head_by_receipt(
            **scope,
            receipt_ref=selected.receipt_ref,
        )
        == selected
    )
    assert (
        store.get_acquisition_action_head_by_receipt(
            **scope,
            receipt_ref=terminal.receipt_ref,
        )
        == terminal
    )
    assert (
        store.get_acquisition_action_head_by_receipt(
            **scope,
            receipt_ref=_receipt_ref("e"),
        )
        is None
    )


@pytest.mark.parametrize(
    ("field", "foreign_value"),
    [
        ("tenant_id", "foreign-tenant"),
        ("cell_id", "foreign-cell"),
        ("run_id", "foreign-run"),
        ("source_job_id", "foreign-source-job"),
        ("route_id", "sha256:" + "d" * 64),
        ("action_generation", 2),
    ],
)
def test_action_head_history_rejects_every_foreign_scope_axis(
    tmp_path: Path,
    field: str,
    foreign_value: str | int,
) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    head = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("b"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
    )

    foreign_scope = {**scope, field: foreign_value}
    assert (
        store.get_acquisition_action_head_by_receipt(
            **foreign_scope,
            receipt_ref=head.receipt_ref,
        )
        is None
    )


def test_action_head_history_returns_no_result_for_ambiguous_receipt(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    repeated_receipt = _receipt_ref("b")
    first = _append_head(
        store,
        scope,
        receipt_ref=repeated_receipt,
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
    )
    second = _append_head(
        store,
        scope,
        receipt_ref=repeated_receipt,
        expected_head_generation=1,
        predecessor_receipt_ref=first.receipt_ref,
        receipt_phase="executing",
    )

    assert store.get_acquisition_action_head(**scope) == second
    assert (
        store.get_acquisition_action_head_by_receipt(
            **scope,
            receipt_ref=repeated_receipt,
        )
        is None
    )


def test_action_head_history_returns_no_result_for_corrupt_receipt_hash_relation(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    scope = _action_scope()
    head = _append_head(
        store,
        scope,
        receipt_ref=_receipt_ref("b"),
        expected_head_generation=0,
        predecessor_receipt_ref=None,
        receipt_phase="requested",
    )
    with sqlite3.connect(tmp_path / "control-plane.sqlite3") as connection:
        connection.execute(
            """
            UPDATE runtime_acquisition_action_heads
            SET receipt_sha256 = ?
            WHERE tenant_id = ? AND cell_id = ? AND run_id = ?
              AND source_job_id = ? AND route_id = ? AND action_generation = ?
              AND head_generation = ?
            """,
            (
                _receipt_ref("c"),
                scope["tenant_id"],
                scope["cell_id"],
                scope["run_id"],
                scope["source_job_id"],
                scope["route_id"],
                scope["action_generation"],
                head.head_generation,
            ),
        )

    assert (
        store.get_acquisition_action_head_by_receipt(
            **scope,
            receipt_ref=head.receipt_ref,
        )
        is None
    )
