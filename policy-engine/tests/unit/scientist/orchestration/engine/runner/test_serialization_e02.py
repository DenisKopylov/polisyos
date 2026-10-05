"""E02 typed wire bytes through filesystem readback and real tier consumption."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.orchestration.engine.protocol import (
    NodeOutputDisposition,
    OutputAwareNodeOutcome,
)
from polisyos.scientist.orchestration.engine.runner import serialization as wire
from polisyos.scientist.orchestration.engine.runner.state_merge import (
    TierOutcomeAdmissionError,
    merge_tier_outcomes,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState


@pytest.fixture(params=["orjson", "stdlib"])
def backend(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.param == "stdlib":
        monkeypatch.setattr(wire, "_dumps", lambda obj: json.dumps(obj).encode())
        monkeypatch.setattr(wire, "_loads", json.loads)
    else:
        orjson = pytest.importorskip("orjson")
        monkeypatch.setattr(wire, "_dumps", orjson.dumps)
        monkeypatch.setattr(wire, "_loads", orjson.loads)


@pytest.mark.usefixtures("backend")
@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
def test_persisted_typed_outcome_enters_real_tier_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, warm: bool
) -> None:
    """Typed source bytes survive reopen and drive the distributed state consumer."""
    base = ExperimentState(run_id="e02-wire", budgets={"compute": Decimal("7.5000")})
    ref = ArtifactRef(artifact_id="sha256:" + "a" * 64, kind="e02-wire", media_type="text/plain")
    produced = base.model_copy(
        update={"params": {"amount": Decimal("12.3400"), "payload": {"binary": b"\x00\xff"}}}
    )
    outcome = OutputAwareNodeOutcome(
        status="ok",
        state=produced,
        artifacts=[ref],
        output_dispositions=(
            NodeOutputDisposition(output_key="ref", disposition="produced", artifact_ref=ref),
        ),
        supporting_artifacts={"source": ref},
    )
    base_file = tmp_path / "state.wire"
    outcome_file = tmp_path / "outcome.wire"
    base_file.write_bytes(wire.serialize_state(base))
    outcome_file.write_bytes(wire.serialize_outcome(outcome))
    if warm:
        wire.deserialize_state(base_file.read_bytes())
        wire.deserialize_outcome(outcome_file.read_bytes())
    else:
        monkeypatch.setattr(wire, "_WIRE_MODEL_TYPES", None)

    merged = merge_tier_outcomes(
        base_file.read_bytes(),
        {"producer": outcome_file.read_bytes()},
        requested_aliases=["producer"],
    )
    result_file = tmp_path / "merged.wire"
    result_file.write_bytes(merged.state_bytes)
    reopened = wire.deserialize_state(result_file.read_bytes())
    assert reopened.budgets["compute"].as_tuple() == Decimal("7.5000").as_tuple()
    assert reopened.params["amount"].as_tuple() == Decimal("12.3400").as_tuple()
    assert reopened.params["payload"]["binary"] == b"\x00\xff"
    admitted = merged.status_evidence.successful_outcomes["producer"]
    assert type(admitted) is OutputAwareNodeOutcome
    assert admitted.output_dispositions[0].artifact_ref == ref
    assert admitted.supporting_artifacts["source"] == ref

    with pytest.raises(TierOutcomeAdmissionError):
        merge_tier_outcomes(
            base_file.read_bytes(),
            {"foreign": outcome_file.read_bytes()},
            requested_aliases=["producer"],
        )


@pytest.mark.usefixtures("backend")
def test_persisted_safe_wire_rejects_tampered_bytes(tmp_path: Path) -> None:
    """Keeping valid JSON/model markers cannot authorize a modified transport."""
    state = ExperimentState(run_id="e02-wire-safe", budgets={"compute": Decimal("7.5000")})
    payload, _digest = wire.serialize_state_safe(state)
    path = tmp_path / "safe.wire"
    path.write_bytes(payload)
    assert wire.deserialize_state_safe(path.read_bytes()).budgets == state.budgets
    path.write_bytes(payload.replace(b"7.5000", b"8.5000"))
    assert path.read_bytes() != payload
    with pytest.raises(wire.DeserializationError, match="Integrity check failed"):
        wire.deserialize_state_safe(path.read_bytes())
