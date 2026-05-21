from __future__ import annotations

# ruff: noqa: S101
import json
from copy import deepcopy
from pathlib import Path

import pytest

from polisyos.runtime.quality.multiverse_specification_curve import (
    MULTIVERSE_SPECIFICATION_CURVE_SCHEMA_VERSION,
    MultiverseSpecificationCurveError,
    build_multiverse_specification_curve_record,
    validate_multiverse_specification_curve_record,
)
from tests._helpers.hds_quality import sha

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    REPO_ROOT
    / "schemas/runtime_quality/policy_design_multiverse_specification_curve_v1.schema.json"
)


def _source_outputs() -> dict[str, list[dict[str, object]]]:
    return {
        "scientist_doe_outputs": [
            {
                "experiment_id": "doe.factorial.twfe",
                "specification_id": "twfe-baseline",
                "estimate": 0.041,
                "standard_error": 0.011,
                "decision": "defensible",
                "drivers": {
                    "model_family": "two_way_fixed_effects",
                    "covariate_set": "baseline",
                },
                "evidence_ref": sha("1"),
            }
        ],
        "scientist_discovery_outputs": [
            {
                "hypothesis_id": "discovery.event-study",
                "spec_id": "event-study-bank-controls",
                "effect_estimate": 0.037,
                "se": 0.012,
                "decision": "defensible",
                "drivers": {
                    "model_family": "event_study",
                    "covariate_set": "bank_controls",
                },
                "evidence_ref": sha("2"),
            }
        ],
        "foundry_sensitivity_outputs": [
            {
                "specification_ids": ["matched-did", "trimmed-panel"],
                "estimates": [0.029, 0.018],
                "standard_errors": [0.01, 0.014],
                "sensitivity_axes": ["matching", "sample_trim"],
                "metadata": {"model_family": "sensitivity_sweep"},
                "evidence_ref": sha("3"),
            }
        ],
        "backtesting_outputs": [
            {
                "scenario_id": "pretrend-placebo",
                "specification_id": "placebo-pretrend",
                "estimate": -0.024,
                "standard_error": 0.009,
                "decision": "rejected",
                "rejection_reason": "Historical pre-period placebo failed.",
                "drivers": {
                    "model_family": "placebo_backtest",
                    "backtest_scenario": "pretrend",
                },
                "evidence_ref": sha("4"),
            }
        ],
    }


def _previous_wave_refs() -> dict[str, list[str]]:
    return {
        "portfolio_design_refs": ["portfolio-rec-1"],
        "evidence_line_refs": ["line-data"],
        "independence_map_refs": ["independence-map-rec-1"],
    }


def test_multiverse_projection_records_all_producer_surfaces() -> None:
    outputs = _source_outputs()

    record = build_multiverse_specification_curve_record(
        curve_id="multiverse-rec-1",
        claim_id="rec_1",
        portfolio_id="portfolio-rec-1",
        evidence_ref=sha("a"),
        runtime_event_ref=sha("b"),
        previous_wave_refs=_previous_wave_refs(),
        **outputs,
    )

    assert record["schema_version"] == MULTIVERSE_SPECIFICATION_CURVE_SCHEMA_VERSION
    assert record["curve_id"] == "multiverse-rec-1"
    assert record["claim_ids"] == ["rec_1"]
    assert record["source_kind_counts"] == {
        "backtesting": 1,
        "foundry_sensitivity": 2,
        "scientist_discovery": 1,
        "scientist_doe": 1,
    }
    assert [item["specification_id"] for item in record["defensible_specifications"]] == [
        "event-study-bank-controls",
        "matched-did",
        "trimmed-panel",
        "twfe-baseline",
    ]
    assert [item["specification_id"] for item in record["rejected_specifications"]] == [
        "placebo-pretrend"
    ]
    assert record["result_distribution"]["n_specifications"] == 5
    assert record["result_distribution"]["sign_counts"] == {
        "negative": 1,
        "positive": 4,
        "zero": 0,
    }
    assert record["drivers_of_divergence"][0]["axis"] == "model_family"
    assert record["claim_markers"] == [
        {
            "claim_id": "rec_1",
            "marker": "fragile",
            "reason_codes": ["rejected_specifications_diverge"],
        }
    ]
    assert record["previous_wave_refs"] == _previous_wave_refs()


def test_multiverse_validation_rejects_cherry_picked_agreeing_specifications() -> None:
    outputs = _source_outputs()
    record = build_multiverse_specification_curve_record(
        curve_id="multiverse-rec-1",
        claim_id="rec_1",
        portfolio_id="portfolio-rec-1",
        evidence_ref=sha("a"),
        runtime_event_ref=sha("b"),
        previous_wave_refs=_previous_wave_refs(),
        **outputs,
    )
    cherry_picked = deepcopy(record)
    cherry_picked["claim_markers"] = [
        {
            "claim_id": "rec_1",
            "marker": "robust",
            "reason_codes": ["defensible_specifications_agree"],
        }
    ]

    with pytest.raises(
        MultiverseSpecificationCurveError,
        match="policy_design_multiverse_cherry_picked_agreement",
    ):
        validate_multiverse_specification_curve_record(cherry_picked)


def test_multiverse_validation_requires_previous_wave_refs() -> None:
    outputs = _source_outputs()
    record = build_multiverse_specification_curve_record(
        curve_id="multiverse-rec-1",
        claim_id="rec_1",
        portfolio_id="portfolio-rec-1",
        evidence_ref=sha("a"),
        runtime_event_ref=sha("b"),
        previous_wave_refs=_previous_wave_refs(),
        **outputs,
    )
    record.pop("previous_wave_refs")

    with pytest.raises(
        MultiverseSpecificationCurveError,
        match="policy_design_multiverse_previous_wave_refs_missing",
    ):
        validate_multiverse_specification_curve_record(record)


def test_multiverse_validation_rejects_static_runtime_refs() -> None:
    outputs = _source_outputs()
    record = build_multiverse_specification_curve_record(
        curve_id="multiverse-rec-1",
        claim_id="rec_1",
        portfolio_id="portfolio-rec-1",
        evidence_ref=sha("a"),
        runtime_event_ref=sha("b"),
        previous_wave_refs=_previous_wave_refs(),
        **outputs,
    )
    record["evidence_ref"] = "repo://architecture/static_inventory.json"

    with pytest.raises(
        MultiverseSpecificationCurveError,
        match="policy_design_multiverse_evidence_ref_invalid",
    ):
        validate_multiverse_specification_curve_record(record)


def test_multiverse_specification_curve_json_schema_names_required_surfaces() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"]["const"] == (
        MULTIVERSE_SPECIFICATION_CURVE_SCHEMA_VERSION
    )
    assert set(schema["required"]) >= {
        "curve_id",
        "claim_ids",
        "portfolio_id",
        "specification_records",
        "defensible_specifications",
        "rejected_specifications",
        "result_distribution",
        "drivers_of_divergence",
        "claim_markers",
    }
