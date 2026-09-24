"""Real DS9 custody and crash recovery with the deployed control-store guard."""

from pathlib import Path

import pytest

from polisyos.runtime.http.resilience import guard_runtime_control_store
from tests.unit.runtime.http import test_human_decision_service as cases


@pytest.mark.parametrize("recovery", [False, True])
def test_guarded_store_custodies_record_and_recovers_signed_orphan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recovery: bool
) -> None:
    fixture = cases._signed_current_gate_fixture(tmp_path)
    sink = fixture.service.authority_sink
    guarded = guard_runtime_control_store(sink._reservation_store)
    sink._reservation_store = guarded
    sink._event_log._store = guarded
    monkeypatch.setattr(cases, "_signed_current_gate_fixture", lambda _: fixture)
    try:
        if recovery:
            cases.test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2(
                tmp_path, monkeypatch
            )
        else:
            cases.test_human_decision_persists_custody_signature_not_actor_signature(tmp_path)
    finally:
        guarded._guard.close()
