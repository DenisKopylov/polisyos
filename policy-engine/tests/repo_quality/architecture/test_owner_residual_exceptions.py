"""Exercise the retained exception boundary without changing closed gate source."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from tools.quality.validation import repository_structure_phase0 as structure

PRODUCT = Path(__file__).resolve().parents[3]


def _lex_case() -> tuple[dict, dict]:
    tracked = structure._tracked_entries(structure._git_root(PRODUCT))
    inventory = structure.collect_inventory(PRODUCT, tracked_paths=tracked)
    exception = next(
        entry
        for entry in structure._load_structure_exceptions(PRODUCT, tracked)
        if entry["id"] == "loose-root-lex-follow-up"
    )
    finding = next(
        item
        for item in structure.gate_loose_files(PRODUCT, inventory, tracked)
        if structure._finding_matches_exception(item, exception)
    )
    return finding, copy.deepcopy(exception)


def test_expired_exception_preserves_real_finding_and_refusal(tmp_path: Path) -> None:
    finding, exception = _lex_case()
    exception["sunset"] = "2026-01-02"
    result = structure._apply_structure_exceptions([finding], [exception])
    receipt = tmp_path / "expired-exception.json"
    receipt.write_text(json.dumps(result), encoding="utf-8")
    reopened = json.loads(receipt.read_text(encoding="utf-8"))
    assert finding in reopened, "expired exception suppressed the real Lex finding"
    assert any(
        item.get("id") == exception["id"]
        and item["message"] == "Structure remediation exception is expired."
        for item in reopened
    ), "expiry did not produce its own refusal"


def test_absent_and_wrong_scope_exceptions_do_not_suppress_real_finding(tmp_path: Path) -> None:
    finding, exception = _lex_case()
    exception["sunset"] = "2099-01-01"
    assert structure._apply_structure_exceptions([finding], [exception]) == []
    exception["match"]["package"] = "scholar"
    results = {
        "absent": structure._apply_structure_exceptions([finding], []),
        "wrong_scope": structure._apply_structure_exceptions([finding], [exception]),
    }
    receipt = tmp_path / "scope-refusals.json"
    receipt.write_text(json.dumps(results), encoding="utf-8")
    reopened = json.loads(receipt.read_text(encoding="utf-8"))
    assert reopened == {"absent": [finding], "wrong_scope": [finding]}
