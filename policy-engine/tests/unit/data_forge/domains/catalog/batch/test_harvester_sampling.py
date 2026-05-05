from __future__ import annotations

from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.harvester import (
    _augment_who_rows,
    _prioritize_rows_for_sampling,
)
from polisyos.data_forge.domains.catalog.batch.source_registry import SourceSpec


def test_prioritize_rows_for_sampling_injects_curated_who_health_indicators(tmp_path) -> None:
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snap",
        run_profile="preflight_core",
        max_datasets_per_source=5,
    )
    spec = SourceSpec(
        name="who",
        family="who",
        wave="D",
        endpoint="https://ghoapi.azureedge.net/api/Indicator",
        execution_tier="transport_ready",
        run_lane="empirical",
        publish_blocking=True,
    )
    metrics_map = {
        "health_outcomes": {
            "keywords": ["life expectancy"],
            "who_indicators": ["WHOSIS_000001", "WHOSIS_000002", "WHOSIS_000015"],
        },
        "life_expectancy": {
            "keywords": ["life expectancy"],
            "who_indicators": ["WHOSIS_000001", "WHOSIS_000002", "WHOSIS_000015"],
        },
    }
    rows = [
        {
            "IndicatorCode": "FINPROTECTION_IMP_NP_190_LEVEL_SH",
            "IndicatorName": "Total population pushed below the $1.90 a day poverty line by household health expenditures (%)",
        },
        {
            "IndicatorCode": "GDO_q12x2x1x1_1NGO",
            "IndicatorName": "Majority provider of dementia carer training and education (NGO)",
        },
        {
            "IndicatorCode": "GB_XPD_RSDV",
            "IndicatorName": "Research and development (R&D) expenditure as a proportion of GDP",
        },
    ]

    augmented = _augment_who_rows(rows, metrics_map=metrics_map)
    prioritized = _prioritize_rows_for_sampling(
        augmented, spec=spec, config=config, metrics_map=metrics_map
    )

    top_codes = [
        str(item.get("IndicatorCode") or item.get("id") or "").strip().upper()
        for item in prioritized[:3]
    ]
    assert "WHOSIS_000001" in top_codes
    assert top_codes[0] == "WHOSIS_000001"
    assert "health_outcomes" in prioritized[0]["harvest_metric_candidates"]
    assert "life_expectancy" in prioritized[0]["harvest_metric_candidates"]
