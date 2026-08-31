"""Behavioral falsifiers for the DS18 historical obligation lineage."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ATLAS_DIR = Path(__file__).resolve().parent
CHECKER_PATH = ATLAS_DIR / "check_frontend_disposition_register.py"
REGISTER_PATH = ATLAS_DIR / "frontend-disposition-register.json"

_SPEC = importlib.util.spec_from_file_location(
    "ds18_time_semantics_lineage_checker",
    CHECKER_PATH,
)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Unable to import disposition checker from {CHECKER_PATH}")
checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(checker)


def _register() -> dict[str, object]:
    return json.loads(REGISTER_PATH.read_text(encoding="utf-8"))


def _fresh_coverage() -> dict[str, object]:
    stored = _register()["ds18_time_semantics_coverage"]
    assert isinstance(stored, dict)  # noqa: S101 - governed fixture
    fresh = checker._build_ds18_time_semantics_coverage(
        checker._ds18_time_semantics_scan(),
        frontend_freeze_commit=stored["frontend_freeze_commit"],
    )
    assert isinstance(fresh, dict)  # noqa: S101 - typed builder result
    return fresh


def _root(
    coverage: dict[str, object],
    *,
    path: str,
    root_id: str,
) -> dict[str, object]:
    files = coverage["files"]
    assert isinstance(files, list)  # noqa: S101 - test fixture guard
    for file_row in files:
        assert isinstance(file_row, dict)  # noqa: S101 - governed fixture
        if file_row["path"] != path:
            continue
        roots = file_row["roots"]
        assert isinstance(roots, list)  # noqa: S101 - governed fixture
        for root in roots:
            assert isinstance(root, dict)  # noqa: S101 - governed fixture
            if root["root_id"] == root_id:
                return root
    raise AssertionError(f"missing governed root: {path}#{root_id}")


def _first_nondecision_root(coverage: dict[str, object]) -> dict[str, object]:
    files = coverage["files"]
    assert isinstance(files, list)  # noqa: S101 - governed fixture
    return next(
        root
        for file_row in files
        if isinstance(file_row, dict)
        for root in file_row["roots"]
        if isinstance(root, dict)
        and root.get("classification") == "non_decision_bearing"
    )


def _admit_as_unrelated_direct(
    root: dict[str, object],
    *,
    evidence: object,
) -> None:
    root["classification"] = "decision_bearing"
    root["behavioral_evidence"] = copy.deepcopy(evidence)
    root["temporal_binding"] = "strict_non_jsx_projection"
    root["temporal_obligation"] = "as_of_epoch_validity"
    root.pop("non_decision_reason", None)


def test_complete_lineage_pins_the_77_plus_17_plus_32_composition() -> None:
    data = _register()
    assert checker._schema_errors(data, checker.SCHEMA_PATH) == []  # noqa: S101
    coverage = data["ds18_time_semantics_coverage"]
    assert isinstance(coverage, dict)  # noqa: S101 - governed fixture
    assert (  # noqa: S101 - mapping is generated from pinned Git blobs
        checker._build_ds18_time_semantics_lineage(coverage)
        == coverage["historical_lineage"]
    )
    errors: list[str] = []

    summary = checker._validate_ds18_time_semantics_lineage(coverage, errors)

    assert errors == []  # noqa: S101
    assert summary == {  # noqa: S101
        "current_obligated_root_count": 126,
        "freeze_obligated_root_count": 77,
        "landing_deltas": {"DS15": 17, "DS17": 32},
        "source_reconciliations": {
            "Task-D-dashboard-freeze": {
                "entered": 0,
                "exited": 0,
                "rebound": 9,
            }
        },
    }


def test_same_total_swap_rejects_loss_of_a_frozen_obligation() -> None:
    data = _register()
    coverage = data["ds18_time_semantics_coverage"]
    assert isinstance(coverage, dict)  # noqa: S101 - governed fixture
    frozen = _root(
        coverage,
        path=(
            "apps/runtime-dashboard/src/features/artifacts/bureaucratic/"
            "export/export-html.ts"
        ),
        root_id="exportBureaucraticHtml:html_template:38:10",
    )
    evidence = frozen["behavioral_evidence"]
    frozen["classification"] = "non_decision_bearing"
    frozen["behavioral_evidence"] = []
    frozen["non_decision_reason"] = "synthetic same-total swap"
    frozen.pop("temporal_binding", None)
    frozen.pop("temporal_obligation", None)
    _admit_as_unrelated_direct(_first_nondecision_root(coverage), evidence=evidence)

    current_only_errors: list[str] = []
    checker._validate_ds18_time_semantics_coverage_core(
        coverage,
        checker._ds18_time_semantics_scan(),
        current_only_errors,
        post_freeze_is_landing_red=True,
    )
    assert current_only_errors == []  # noqa: S101 - proves the scalar proxy gap

    lineage_errors: list[str] = []
    checker._validate_ds18_time_semantics_lineage(coverage, lineage_errors)

    assert any(  # noqa: S101
        error.startswith("ds18_time_semantics_frozen_obligation_missing:")
        for error in lineage_errors
    )


def test_unassigned_post_freeze_obligation_is_rejected() -> None:
    data = _register()
    coverage = data["ds18_time_semantics_coverage"]
    assert isinstance(coverage, dict)  # noqa: S101 - governed fixture
    evidence = _root(
        coverage,
        path=(
            "apps/runtime-dashboard/src/features/artifacts/bureaucratic/"
            "export/export-html.ts"
        ),
        root_id="exportBureaucraticHtml:html_template:38:10",
    )["behavioral_evidence"]
    _admit_as_unrelated_direct(_first_nondecision_root(coverage), evidence=evidence)
    coverage["decision_bearing_root_count"] = 49
    coverage["obligated_root_count"] = 127
    coverage["covered_root_count"] = 127

    errors: list[str] = []
    checker._validate_ds18_time_semantics_lineage(coverage, errors)

    assert any(  # noqa: S101
        error.startswith("ds18_time_semantics_unreconciled_current_obligation:")
        for error in errors
    )


def test_forged_historical_coordinate_is_rejected() -> None:
    coverage = _register()["ds18_time_semantics_coverage"]
    assert isinstance(coverage, dict)  # noqa: S101 - governed fixture
    lineage = coverage["historical_lineage"]
    assert isinstance(lineage, dict)  # noqa: S101 - governed fixture
    freeze = lineage["freeze"]
    assert isinstance(freeze, dict)  # noqa: S101 - governed fixture
    freeze["checkpoint_commit"] = "0" * 40

    errors: list[str] = []
    checker._validate_ds18_time_semantics_lineage(coverage, errors)

    assert any(  # noqa: S101
        error.startswith(
            "ds18_time_semantics_lineage_coordinate_unresolvable:freeze:"
        )
        for error in errors
    )


def test_landing_identity_is_bound_to_the_ratified_composition() -> None:
    coverage = _register()["ds18_time_semantics_coverage"]
    assert isinstance(coverage, dict)  # noqa: S101 - governed fixture
    lineage = coverage["historical_lineage"]
    assert isinstance(lineage, dict)  # noqa: S101 - governed fixture
    landings = lineage["landings"]
    assert isinstance(landings, list)  # noqa: S101 - governed fixture
    first = landings[0]
    assert isinstance(first, dict)  # noqa: S101 - governed fixture
    first["slice_id"] = "DS99"

    errors: list[str] = []
    checker._validate_ds18_time_semantics_lineage(coverage, errors)

    assert "ds18_time_semantics_lineage_composition_identity_drift" in errors  # noqa: S101


def test_dashboard_source_freeze_reconciles_exact_mapping_rebindings() -> None:
    fresh = _fresh_coverage()

    lineage = checker._build_ds18_time_semantics_lineage(fresh)
    reconciliations = lineage["source_reconciliations"]
    assert isinstance(reconciliations, list)  # noqa: S101 - typed artifact
    assert len(reconciliations) == 1  # noqa: S101 - one frozen source landing
    reconciliation = reconciliations[0]
    assert reconciliation["landing_id"] == "Task-D-dashboard-freeze"  # noqa: S101
    assert reconciliation["source_checkpoint_commit"] == (  # noqa: S101
        "03c5783609271c27d6f3d212b76dda7eddef2074"
    )
    assert reconciliation["source_file_count_summary"] == 623  # noqa: S101
    assert reconciliation["root_count_summary"] == 759  # noqa: S101
    assert reconciliation["obligation_count_summary"] == 126  # noqa: S101
    assert reconciliation["entered_root_count"] == 0  # noqa: S101
    assert reconciliation["exited_root_count"] == 0  # noqa: S101
    assert reconciliation["rebound_root_count"] == 9  # noqa: S101
    assert reconciliation["obligation_manifest_sha256"] == (  # noqa: S101
        "sha256:296faa4e6569dae3b101a695245eeca2908d98fd923d89a70384170c4c04bc3f"
    )

    fresh["historical_lineage"] = lineage
    errors: list[str] = []
    summary = checker._validate_ds18_time_semantics_lineage(fresh, errors)

    assert errors == []  # noqa: S101
    assert summary == {  # noqa: S101
        "current_obligated_root_count": 126,
        "freeze_obligated_root_count": 77,
        "landing_deltas": {"DS15": 17, "DS17": 32},
        "source_reconciliations": {
            "Task-D-dashboard-freeze": {
                "entered": 0,
                "exited": 0,
                "rebound": 9,
            }
        },
    }


def test_source_reconciliation_cannot_substitute_a_different_source_root() -> None:
    coverage = _register()["ds18_time_semantics_coverage"]
    assert isinstance(coverage, dict)  # noqa: S101 - governed fixture
    lineage = coverage["historical_lineage"]
    assert isinstance(lineage, dict)  # noqa: S101 - governed fixture
    reconciliations = lineage["source_reconciliations"]
    assert isinstance(reconciliations, list)  # noqa: S101 - governed fixture
    reconciliation = reconciliations[0]
    assert isinstance(reconciliation, dict)  # noqa: S101 - governed fixture
    reconciliation["source_root"] = "apps/runtime-dashboard/src/features"

    errors: list[str] = []
    checker._validate_ds18_time_semantics_lineage(coverage, errors)

    assert (  # noqa: S101
        "ds18_time_semantics_source_summary_drift:"
        "Task-D-dashboard-freeze:source_root"
    ) in errors


def test_focused_validator_rejects_a_scalar_composition_rule() -> None:
    coverage = _register()["ds18_time_semantics_coverage"]
    assert isinstance(coverage, dict)  # noqa: S101 - governed fixture
    lineage = coverage["historical_lineage"]
    assert isinstance(lineage, dict)  # noqa: S101 - governed fixture
    lineage["composition_rule"] = "current obligations equal 126"

    errors: list[str] = []
    checker._validate_ds18_time_semantics_lineage(coverage, errors)

    assert "ds18_time_semantics_lineage_composition_rule_drift" in errors  # noqa: S101


def test_focused_validator_rejects_a_selector_identity_proxy() -> None:
    coverage = _register()["ds18_time_semantics_coverage"]
    assert isinstance(coverage, dict)  # noqa: S101 - governed fixture
    lineage = coverage["historical_lineage"]
    assert isinstance(lineage, dict)  # noqa: S101 - governed fixture
    lineage["selector_identity"] = "root count"

    errors: list[str] = []
    checker._validate_ds18_time_semantics_lineage(coverage, errors)

    assert "ds18_time_semantics_lineage_selector_identity_drift" in errors  # noqa: S101


def test_source_checkpoint_binds_current_scanner_and_manifest_bytes() -> None:
    coverage = _register()["ds18_time_semantics_coverage"]
    assert isinstance(coverage, dict)  # noqa: S101 - governed fixture
    lineage = coverage["historical_lineage"]
    assert isinstance(lineage, dict)  # noqa: S101 - governed fixture
    reconciliations = lineage["source_reconciliations"]
    assert isinstance(reconciliations, list)  # noqa: S101 - governed fixture
    reconciliation = reconciliations[0]
    assert isinstance(reconciliation, dict)  # noqa: S101 - governed fixture

    try:
        errors = checker._ds18_source_checkpoint_errors(
            reconciliation,
            coverage,
            current_artifact_loader=lambda _path: b"synthetic drift",
        )
    except TypeError:  # missing injection seam is the pre-fix behavior
        errors = []

    assert any(  # noqa: S101
        error.startswith("ds18_time_semantics_source_current_artifact_drift:")
        for error in errors
    )
