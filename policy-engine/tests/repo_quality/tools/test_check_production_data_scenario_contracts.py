from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from polisyos.runtime.quality.scenario_evidence_contract import (
    normalize_scenario_evidence_contract,
)
from tools.quality.validation import check_production_data_scenario_contracts as checker


def test_checker_does_not_pass_when_zero_data_requirements_have_unknown_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = {
        "scenario_id": "no-data-basis",
        "text": "A neutral public policy statement.",
        "domain": "healthcare",
        "expected_evidence_contract": {"admissible_data_source_families": []},
    }
    evidence_contract = normalize_scenario_evidence_contract(scenario).to_dict()
    monkeypatch.setattr(
        checker,
        "load_quality_scenario_contract",
        lambda _scenario_id: {"scenario_evidence_contract": evidence_contract},
    )
    production_data_root = tmp_path / "production_data"
    production_data_root.mkdir()
    (production_data_root / "manifest.json").write_text(
        json.dumps({"bundles": {}}),
        encoding="utf-8",
    )

    report = checker.build_report(
        repo_root=Path(__file__).resolve().parents[3],
        production_data_root=production_data_root,
        scenario="no-data-basis",
    )

    assert report["status"] == "candidate"
    assert report["summary"]["requirements"] == 0
    assert report["requirement_basis"]["state"] == "not_established"
    assert report["requirement_basis"]["basis_grade"] == "not_established"
    assert report["authority_eligible"] is False
    assert any(
        item["code"] == "production_data_requirement_basis_not_established"
        and item["status"] == "candidate"
        for item in report["findings"]
    )
