"""Replay baseline, removed enforcement and restoration under one frozen witness."""

from __future__ import annotations

import contextlib
import hashlib
import json
import traceback
from pathlib import Path

from polisyos.runtime.http.services.acquisition_action_service import AcquisitionOwnerExecutionResult
from polisyos.runtime.http.services.acquisition_surface_execution import (
    WorldBankWDIAcquisitionExecutionPort,
)
from tests.integration.core_runtime.test_acquisition_route_execution_binding import (
    _port_fixture,
    _route_closure,
)

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "raw" / "frozen-refusal-wave"
SOURCE = Path(WorldBankWDIAcquisitionExecutionPort.execute.__code__.co_filename)


def witness(mode: str) -> None:
    """Require actual quarantine and refusal for every exercised re-entry input."""
    port, observer, _ = _port_fixture(OUTPUT / mode / "state")
    closure = _route_closure()
    result = port.execute(closure)
    positive_shape = AcquisitionOwnerExecutionResult(
        disposition="world_committed",
        owner_receipt_refs=("sha256:" + "a" * 64,),
        admitted_observation_delta=1,
        overlay_admission_receipt_ref="sha256:" + "b" * 64,
        post_epoch_event_ref="sha256:" + "c" * 64,
    )
    records = []
    for label, operation in (
        ("quarantined", lambda: port.reenter(closure, result)),
        ("resume", lambda: port.resume_reentry(closure, result.owner_receipt_refs)),
        ("shaped_positive", lambda: port.reenter(closure, positive_shape)),
    ):
        try:
            records.append({"input": label, "returned": operation()})
        except Exception as exc:
            records.append({"input": label, "code": getattr(exc, "code", None)})
    print(json.dumps({"result": result.model_dump(mode="json"),
                      "transport_calls": len(observer.calls), "reentry": records}, indent=2))
    assert result.disposition == "quarantined_no_growth"
    assert result.admitted_observation_delta == 0
    assert len(observer.calls) == 1
    assert all(row.get("code") == "acquisition_live_evidence_not_admitted" for row in records)


def main() -> int:
    """Keep production bytes and witness fixed while toggling only enforcement."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source_before = SOURCE.read_bytes()
    witness_bytes = Path(__file__).read_bytes()
    original = WorldBankWDIAcquisitionExecutionPort.__dict__["_raise_reentry_not_admitted"]
    outcomes = {}
    try:
        for mode in ("baseline", "removed", "restored"):
            if mode == "removed":
                WorldBankWDIAcquisitionExecutionPort._raise_reentry_not_admitted = staticmethod(
                    lambda: None
                )
            else:
                WorldBankWDIAcquisitionExecutionPort._raise_reentry_not_admitted = original
            with (OUTPUT / f"{mode}.log").open("w") as handle:
                with contextlib.redirect_stdout(handle), contextlib.redirect_stderr(handle):
                    try:
                        witness(mode)
                    except AssertionError:
                        traceback.print_exc()
                        outcomes[mode] = 1
                    else:
                        outcomes[mode] = 0
    finally:
        WorldBankWDIAcquisitionExecutionPort._raise_reentry_not_admitted = original
    assert SOURCE.read_bytes() == source_before
    assert Path(__file__).read_bytes() == witness_bytes
    result = {
        "authority": "behavioral_fixture_not_production",
        "actual_source": {"path": str(SOURCE), "sha256": hashlib.sha256(source_before).hexdigest()},
        "witness_sha256": hashlib.sha256(witness_bytes).hexdigest(),
        "outcomes": outcomes,
        "production_bytes_unchanged": True,
        "unresolved_by_construction": ["real transport", "institutional appointment", "production positive delta"],
        "logs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUTPUT.glob("*.log"))},
    }
    print(json.dumps(result, indent=2))
    return 0 if outcomes == {"baseline": 0, "removed": 1, "restored": 0} else 1


if __name__ == "__main__":
    raise SystemExit(main())
