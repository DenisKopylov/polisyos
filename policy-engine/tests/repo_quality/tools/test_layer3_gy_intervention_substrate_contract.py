"""Exercise the S3 report envelope over the real owner's retained behavior run."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from tools.quality.validation import check_layer3_gy_intervention_substrate_contract as contract


@pytest.fixture
def emitted_payload(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replay the actual wrapper with the complete run-emitted behavior as input."""
    from polisyos.runtime.quality import intervention_substrate

    root = Path(__file__).resolve().parents[3]
    saved = json.loads((root / contract.OUTPUT_PATH).read_text(encoding="utf-8"))
    monkeypatch.setattr(
        intervention_substrate,
        "intervention_substrate_behavior_report",
        lambda _root: copy.deepcopy(saved["behavior_report"]),
    )
    return contract.build_live_payload(root)


def _validate_equal_saved_and_live(
    payload: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    path = tmp_path / contract.OUTPUT_PATH
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(contract, "build_live_payload", lambda _root: copy.deepcopy(payload))
    return contract.validate(tmp_path)


def test_actual_wrapper_marks_its_constructed_report(
    emitted_payload: dict[str, Any],
) -> None:
    assert emitted_payload.get("synthetic") is True


def test_actual_marked_report_remains_valid(
    emitted_payload: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _validate_equal_saved_and_live(emitted_payload, tmp_path, monkeypatch)
    assert result["status"] == "pass", result
    assert result["behavior_status"] == "pass"


@pytest.mark.parametrize("invalid_marker", ["absent", False, None])
def test_validator_refuses_equal_unmarked_live_and_saved_report(
    emitted_payload: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_marker: str | bool | None,
) -> None:
    if invalid_marker == "absent":
        emitted_payload.pop("synthetic", None)
    else:
        emitted_payload["synthetic"] = invalid_marker
    result = _validate_equal_saved_and_live(emitted_payload, tmp_path, monkeypatch)
    assert result["behavior_status"] == "pass"
    assert result["status"] == "fail", result
    assert {issue["code"] for issue in result["issues"]} == {
        "intervention_substrate_report_synthetic_marker_missing"
    }
