from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_best_in_class_phase1_0 as gate

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_scientist_best_in_class_phase1_0_gate_passes_repo(tmp_path: Path) -> None:
    output_json = tmp_path / "phase1-0-gate.json"

    exit_code = gate.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output",
            str(output_json),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["assessment_id"] == "scientist_best_in_class_phase1_0"
    assert payload["passes_all"] is True
    assert payload["category_results"]["capability_readiness_matrix_complete"] is True
    assert payload["category_results"]["historical_plan_map_complete"] is True
    assert any(
        item["item_id"] == "SCIENTIST_SOTA_ROADMAP:WS5.1"
        for item in payload["historical_items"]
    )


def test_scientist_best_in_class_phase1_0_gate_fails_on_missing_mapping(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(
        tmp_path,
        omitted_capability="research_dag",
        omitted_historical_item="SCIENTIST_AGENT_SOTA_ROADMAP:PHASE0",
    )
    output_json = tmp_path / "phase1-0-gate.json"

    exit_code = gate.main(
        [
            "--repo-root",
            str(tmp_path),
            "--output",
            str(output_json),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["passes_all"] is False
    assert "missing_capability:research_dag" in payload["notes"]
    assert "missing_historical_mapping:SCIENTIST_AGENT_SOTA_ROADMAP:PHASE0" in payload["notes"]


def _write_minimal_repo(
    repo_root: Path,
    *,
    omitted_capability: str | None = None,
    omitted_historical_item: str | None = None,
) -> None:
    (repo_root / "src/polisyos/scientist/engine").mkdir(parents=True)
    (repo_root / "tests/scientist/engine").mkdir(parents=True)
    (repo_root / "docs/reference/scientist").mkdir(parents=True)
    (repo_root / "docs/archive/plans").mkdir(parents=True)
    (repo_root / "docs/plans/active").mkdir(parents=True)

    (repo_root / "docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md").write_text(
        "# Scientist Best-in-Class Plan\n",
        encoding="utf-8",
    )

    capability_rows = "\n".join(
        f"| `{capability_id}` | `closed` | fake | fake | fake |"
        for capability_id in gate.REQUIRED_CAPABILITY_IDS
        if capability_id != omitted_capability
    )
    (repo_root / gate.READINESS_DOC).write_text(
        "\n".join(
            [
                "# Scientist Best-in-Class Readiness",
                "",
                "SCIENTIST_BEST_IN_CLASS_PLAN.md",
                "",
                "| Capability id | Readiness | Current source of truth | Evidence | Next |",
                "| --- | --- | --- | --- | --- |",
                capability_rows,
                "",
                "| Phase | Current status | Acceptance surface |",
                "| --- | --- | --- |",
                "| Phase 1.0 | `closed` | fake |",
                "| Phase 1.1 | `still_gated` | fake |",
                "| Phase 1.7 | `still_gated` | fake |",
                "| Phase 2.9 | `research_first` | fake |",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (repo_root / "docs/reference/scientist/index.md").write_text(
        "# Scientist\n",
        encoding="utf-8",
    )
    (repo_root / gate.INVENTORY_DOC).write_text(
        _minimal_inventory_text(omitted_historical_item=omitted_historical_item),
        encoding="utf-8",
    )

    (repo_root / "docs/archive/plans/SCIENTIST_SOTA_ROADMAP.md").write_text(
        "# Archived\n\n### WS5.1 - Circuit Breaker\n",
        encoding="utf-8",
    )
    (repo_root / "docs/SCIENTIST_AUDIT_REMEDIATION_PLAN.md").write_text(
        "# Audit\n\n### WS-0A. Async correctness\n",
        encoding="utf-8",
    )
    (repo_root / "docs/archive/plans/SCIENTIST_AGENT_SOTA_ROADMAP.md").write_text(
        "# Archived\n\n### Phase 0: Fix correctness\n",
        encoding="utf-8",
    )
    (repo_root / "docs/archive/plans/SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT.md").write_text(
        "# Archived\n\n### Phase A - Funnel First\n",
        encoding="utf-8",
    )


def _minimal_inventory_text(*, omitted_historical_item: str | None) -> str:
    historical_rows = {
        "SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-0A": "| `SCIENTIST_AUDIT_REMEDIATION_PLAN:WS-0A` | `closed` | fake | fake |",
        "SCIENTIST_SOTA_ROADMAP:WS5.1": "| `SCIENTIST_SOTA_ROADMAP:WS5.1` | `closed` | fake | fake |",
        "SCIENTIST_AGENT_SOTA_ROADMAP:PHASE0": "| `SCIENTIST_AGENT_SOTA_ROADMAP:PHASE0` | `closed` | fake | fake |",
        "SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT:PHASE_A": "| `SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT:PHASE_A` | `closed` | fake | fake |",
    }
    rendered_rows = "\n".join(
        row for item_id, row in historical_rows.items() if item_id != omitted_historical_item
    )
    return "\n".join(
        [
            "# Scientist Capability Inventory",
            "",
            "| Surface | Source roots | Current role | Reference and tests |",
            "| --- | --- | --- | --- |",
            "| `engine` | `src/polisyos/scientist/engine/**` | fake | fake |",
            "",
            "| Test surface | Coverage role |",
            "| --- | --- |",
            "| `tests/scientist/engine/**` | fake |",
            "",
            "| Reference page | Current role |",
            "| --- | --- |",
            "| [best-in-class-readiness.md](best-in-class-readiness.md) | fake |",
            "| [index.md](index.md) | fake |",
            "| [scientist-capability-inventory.md](scientist-capability-inventory.md) | fake |",
            "",
            "| Historical item | Status | Current reference or gate | Reconciliation note |",
            "| --- | --- | --- | --- |",
            rendered_rows,
            "",
        ]
    )
