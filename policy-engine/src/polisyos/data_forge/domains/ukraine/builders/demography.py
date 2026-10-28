"""Household, labor, and demographic enrichment builders for Ukraine."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    HouseholdDiagnosticPanelBasis,
    NormalizedArtifactManifest,
    SourceSnapshotManifest,
    directory_tree_entries,
)
from polisyos.data_forge.domains.ukraine.models import PipelineConfig, StageId
from polisyos.data_forge.kernel.io import ensure_dirs
from polisyos.ir import TimeFrequency
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    SourceConfidenceTier,
)

from .common import (
    OBSERVATION_FRAME_COLUMNS,
    StageBuildResult,
    _coerce_string_series,
    _normalize_region_code_value,
    _regime_for_period_id,
    _safe_numeric_series,
)
from .io import (
    _load_optional_source_frame,
    _load_source_frame,
    _manifest_path,
    _stage_dir,
    _write_frame,
    _write_json,
)
from .observation import (
    UKRAINE_PERIOD_PROJECTION_VERSION,
    _period_series_to_iso_bounds,  # noqa: F401 - compatibility binding
    project_ukraine_observation_periods,
)


def _weighted_average_series(values: pd.Series, weights: pd.Series) -> float:
    numeric_values = pd.to_numeric(values, errors="coerce").fillna(0.0).astype(float)
    numeric_weights = (
        pd.to_numeric(weights, errors="coerce").fillna(1.0).astype(float).clip(lower=0.0)
    )
    weight_sum = float(numeric_weights.sum())
    if weight_sum <= 1e-12:
        return float(numeric_values.mean()) if len(numeric_values) else 0.0
    return float(np.average(numeric_values, weights=numeric_weights))


def _aggregate_labor_micro_panel(labor: pd.DataFrame) -> pd.DataFrame:
    if labor.empty:
        return pd.DataFrame(
            columns=[
                "region_code",
                "period_id",
                "micro_participation_rate",
                "micro_employment_rate",
                "micro_informal_employment_rate",
                "micro_sample_weight",
                "micro_respondent_count",
            ]
        )
    frame = labor.copy()
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(
        _normalize_region_code_value
    )
    frame["period_id"] = _coerce_string_series(frame, "period_id", fill="")
    frame["weight"] = pd.to_numeric(frame.get("weight", 1.0), errors="coerce").fillna(1.0)
    frame["participation_rate"] = pd.to_numeric(
        frame.get("participation_rate", 0.0), errors="coerce"
    ).fillna(0.0)
    frame["employment_flag"] = pd.to_numeric(
        frame.get("employment_flag", 0.0), errors="coerce"
    ).fillna(0.0)
    frame["informal_employment_flag"] = pd.to_numeric(
        frame.get("informal_employment_flag", 0.0),
        errors="coerce",
    ).fillna(0.0)
    rows: list[dict[str, Any]] = []
    for (region_code, period_id), group in frame.groupby(["region_code", "period_id"], sort=False):
        rows.append(
            {
                "region_code": region_code,
                "period_id": period_id,
                "micro_participation_rate": _weighted_average_series(
                    group["participation_rate"], group["weight"]
                ),
                "micro_employment_rate": _weighted_average_series(
                    group["employment_flag"], group["weight"]
                ),
                "micro_informal_employment_rate": _weighted_average_series(
                    group["informal_employment_flag"],
                    group["weight"],
                ),
                "micro_sample_weight": float(group["weight"].sum()),
                "micro_respondent_count": len(group),
            }
        )
    return pd.DataFrame.from_records(rows)


def _aggregate_household_income_panel(household: pd.DataFrame) -> pd.DataFrame:
    if household.empty:
        return pd.DataFrame(
            columns=[
                "region_code",
                "period_id",
                "household_income_mean",
                "household_weight_sum",
            ]
        )
    frame = household.copy()
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(
        _normalize_region_code_value
    )
    frame["period_id"] = _coerce_string_series(frame, "period_id", fill="")
    frame["weight"] = pd.to_numeric(frame.get("weight", 1.0), errors="coerce").fillna(1.0)
    frame["income"] = pd.to_numeric(frame.get("income", 0.0), errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    for (region_code, period_id), group in frame.groupby(["region_code", "period_id"], sort=False):
        rows.append(
            {
                "region_code": region_code,
                "period_id": period_id,
                "household_income_mean": _weighted_average_series(group["income"], group["weight"]),
                "household_weight_sum": float(group["weight"].sum()),
            }
        )
    return pd.DataFrame.from_records(rows)


def _aggregate_employment_admin_panel(employment_service: pd.DataFrame) -> pd.DataFrame:
    if employment_service.empty:
        return pd.DataFrame(
            columns=[
                "region_code",
                "period_id",
                "admin_employment_count",
                "vacancies",
                "admin_employment_rate_proxy",
            ]
        )
    frame = employment_service.copy()
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(
        _normalize_region_code_value
    )
    frame["period_id"] = _coerce_string_series(frame, "period_id", fill="")
    frame["employment_count"] = pd.to_numeric(
        frame.get("employment_count", 0.0), errors="coerce"
    ).fillna(0.0)
    frame["vacancies"] = pd.to_numeric(frame.get("vacancies", 0.0), errors="coerce").fillna(0.0)
    aggregated = frame.groupby(["region_code", "period_id"], as_index=False).agg(
        admin_employment_count=("employment_count", "sum"),
        vacancies=("vacancies", "sum"),
    )
    aggregated["admin_employment_rate_proxy"] = aggregated.groupby("period_id")[
        "admin_employment_count"
    ].transform(lambda series: series / max(float(series.max()), 1.0))
    return aggregated


def _extract_macro_labor_panel(macro: pd.DataFrame) -> pd.DataFrame:
    if macro.empty or "metric_id" not in macro.columns or "observed_value" not in macro.columns:
        return pd.DataFrame(columns=["region_code", "period_id", "macro_labor_signal"])
    frame = macro.copy()
    frame["metric_id"] = _coerce_string_series(frame, "metric_id", fill="")
    frame = frame.loc[
        frame["metric_id"].str.contains(
            "labor|employment|unemployment|wage", case=False, regex=True
        )
    ]
    if frame.empty:
        return pd.DataFrame(columns=["region_code", "period_id", "macro_labor_signal"])
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(
        _normalize_region_code_value
    )
    frame["period_id"] = _coerce_string_series(frame, "period_id", fill="")
    frame["observed_value"] = pd.to_numeric(frame["observed_value"], errors="coerce").fillna(0.0)
    return frame.groupby(["region_code", "period_id"], as_index=False).agg(
        macro_labor_signal=("observed_value", "mean")
    )


def _build_calibrated_household_cells(household: pd.DataFrame) -> pd.DataFrame:
    if household.empty:
        return pd.DataFrame(
            columns=[
                "cell_id",
                "region_code",
                "period_id",
                "period_start",
                "period_end",
                "period_disposition",
                "period_reason",
                "period_projection_version",
                "household_income_mean",
                "market_income_mean",
                "total_expenditure_mean",
                "household_weight_sum",
                "measurement_bias_flag",
                "trust_weight",
            ]
        )
    frame = household.copy()
    frame["cell_id"] = _coerce_string_series(
        frame, "cell_id", fill="cell::00::household_distribution"
    )
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(
        _normalize_region_code_value
    )
    frame["period_id"] = (
        frame["period_id"].astype("string")
        if "period_id" in frame.columns
        else pd.Series(pd.NA, index=frame.index, dtype="string")
    )
    frame["weight"] = pd.to_numeric(frame.get("weight", 1.0), errors="coerce").fillna(1.0)
    frame["income"] = pd.to_numeric(frame.get("income", 0.0), errors="coerce").fillna(0.0)
    frame["market_income"] = pd.to_numeric(
        frame.get("market_income", frame["income"]), errors="coerce"
    ).fillna(0.0)
    frame["total_expenditure"] = pd.to_numeric(
        frame.get("total_expenditure", frame["income"]),
        errors="coerce",
    ).fillna(0.0)
    rows: list[dict[str, Any]] = []
    for (cell_id, region_code, period_id), group in frame.groupby(
        ["cell_id", "region_code", "period_id"], sort=False, dropna=False
    ):
        rows.append(
            {
                "cell_id": cell_id,
                "region_code": region_code,
                "period_id": period_id,
                "household_income_mean": _weighted_average_series(group["income"], group["weight"]),
                "market_income_mean": _weighted_average_series(
                    group["market_income"], group["weight"]
                ),
                "total_expenditure_mean": _weighted_average_series(
                    group["total_expenditure"], group["weight"]
                ),
                "household_weight_sum": float(group["weight"].sum()),
                "measurement_bias_flag": False,
                "trust_weight": 0.95,
            }
        )
    cells = pd.DataFrame.from_records(rows)
    start, end, disposition, reason = project_ukraine_observation_periods(
        cells["period_id"], time_grain=TimeFrequency.MONTH
    )
    cells["period_start"] = start
    cells["period_end"] = end
    cells["period_disposition"] = disposition
    cells["period_reason"] = reason
    cells["period_projection_version"] = UKRAINE_PERIOD_PROJECTION_VERSION
    return cells


def _build_household_distribution_observation_panel(
    calibrated_household_cells: pd.DataFrame,
) -> pd.DataFrame:
    if calibrated_household_cells.empty:
        return pd.DataFrame(columns=OBSERVATION_FRAME_COLUMNS)
    original_index = calibrated_household_cells.index
    frame = calibrated_household_cells.reset_index(drop=True).copy()
    frame["cell_id"] = _coerce_string_series(
        frame, "cell_id", fill="cell::00::household_distribution"
    )
    frame["region_code"] = _coerce_string_series(frame, "region_code", fill="00").map(
        _normalize_region_code_value
    )
    frame["period_id"] = _coerce_string_series(frame, "period_id", fill="")
    period_start, period_end, period_disposition, period_reason = (
        project_ukraine_observation_periods(frame["period_id"], time_grain=TimeFrequency.MONTH)
    )
    regime_values = [
        _regime_for_period_id(period_id) if disposition == "valid" else (None, None)
        for period_id, disposition in zip(frame["period_id"], period_disposition, strict=True)
    ]
    observations = pd.DataFrame(
        {
            "observation_id": [
                f"obs.household_distribution.household_income_mean.{idx:08d}"
                for idx in range(len(frame))
            ],
            "family": ObservationFamily.HOUSEHOLD_DISTRIBUTION.value,
            "time_grain": TimeFrequency.MONTH.value,
            "period_id": frame["period_id"],
            "period_start": period_start,
            "period_end": period_end,
            "period_disposition": period_disposition,
            "period_reason": period_reason,
            "period_projection_version": UKRAINE_PERIOD_PROJECTION_VERSION,
            "entity_scope": EntityScope.CELL.value,
            "entity_id": frame["cell_id"].astype("string"),
            "cell_id": frame["cell_id"].astype("string"),
            "region_code": frame["region_code"].astype("string"),
            "sector_id": pd.Series(["household_distribution"] * len(frame), dtype="string"),
            "metric_id": pd.Series(["household_income_mean"] * len(frame), dtype="string"),
            "observed_value": pd.to_numeric(frame["household_income_mean"], errors="coerce")
            .fillna(0.0)
            .astype(float),
            "unit": pd.Series(["unit"] * len(frame), dtype="string"),
            "coverage_estimate": 0.97,
            "measurement_bias_flag": frame.get(
                "measurement_bias_flag",
                pd.Series([False] * len(frame), index=frame.index),
            )
            .fillna(False)
            .astype(bool),
            "censoring_mask": False,
            "trust_weight": pd.to_numeric(frame.get("trust_weight", 0.95), errors="coerce")
            .fillna(0.95)
            .astype(float),
            "lag_days_estimate": 0,
            "source_id": pd.Series(["household_microdata"] * len(frame), dtype="string"),
            "source_version": pd.Series(["v1"] * len(frame), dtype="string"),
            "regime_id": pd.Series([item[0] for item in regime_values], dtype="string"),
            "shock_mask": False,
            "schema_regime_id": pd.Series([item[1] for item in regime_values], dtype="string"),
            "identification_mode": pd.Series(
                [IdentificationMode.POINT_IDENTIFIED.value] * len(frame), dtype="string"
            ),
            "source_confidence_tier": pd.Series(
                [SourceConfidenceTier.CORE.value] * len(frame), dtype="string"
            ),
            "proxy_source_id": pd.Series([None] * len(frame), dtype="string"),
        }
    )
    for column in OBSERVATION_FRAME_COLUMNS:
        if column not in observations.columns:
            observations[column] = None
    observations.index = original_index
    return observations[OBSERVATION_FRAME_COLUMNS]


def build_household_diagnostic_panel(household: pd.DataFrame) -> pd.DataFrame:
    """Aggregate only normalized, quarter-identified rows for candidate diagnostics."""
    columns = [
        "family",
        "metric_id",
        "region_code",
        "quarter_id",
        "period_start",
        "period_end",
        "time_grain",
        "observed_value",
        "unit",
        "source_snapshot_id",
        "source_record_hashes",
        "contributor_count",
        "population_coverage",
        "custody",
        "currentness",
    ]
    required = {
        "quarter_id",
        "region_code",
        "income",
        "weight",
        "source_snapshot_id",
        "record_hash",
    }
    if household.empty or not required.issubset(household.columns):
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for (region_code, quarter_id), group in household.groupby(
        ["region_code", "quarter_id"], dropna=True, sort=True
    ):
        values = pd.to_numeric(group["income"], errors="coerce")
        weights = pd.to_numeric(group["weight"], errors="coerce")
        valid = values.notna() & weights.notna() & (weights > 0)
        if not bool(valid.any()):
            continue
        contributors = group.loc[valid]
        source_ids = sorted(set(contributors["source_snapshot_id"].astype(str)))
        record_hashes = sorted(contributors["record_hash"].astype(str).tolist())
        if (
            len(source_ids) != 1
            or not record_hashes
            or any(len(value) != 64 for value in record_hashes)
        ):
            continue
        period = pd.Period(str(quarter_id), freq="Q")
        rows.append(
            {
                "family": ObservationFamily.HOUSEHOLD_DISTRIBUTION.value,
                "metric_id": "observed_value",
                "region_code": str(region_code),
                "quarter_id": str(quarter_id),
                "period_start": period.start_time.date().isoformat(),
                "period_end": period.end_time.date().isoformat(),
                "time_grain": TimeFrequency.QUARTER.value,
                "observed_value": float(np.average(values[valid], weights=weights[valid])),
                "unit": None,
                "source_snapshot_id": source_ids[0],
                "source_record_hashes": record_hashes,
                "contributor_count": len(record_hashes),
                "population_coverage": None,
                "custody": "not_established",
                "currentness": "not_established",
            }
        )
    return pd.DataFrame.from_records(rows, columns=columns)


def _build_household_diagnostic_basis(
    config: PipelineConfig,
    household: pd.DataFrame,
    panel_path: Any,
    panel: pd.DataFrame,
) -> HouseholdDiagnosticPanelBasis:
    """Bind D3 panel to its raw snapshot, normalized artifact, and row denominator."""
    source_id = "household_microdata"
    source_manifest_path = (
        config.build_root.manifests_dir / source_id / "source_snapshot_manifest.json"
    )
    normalized_manifest_path = (
        config.build_root.manifests_dir / source_id / config.sources[source_id].manifest_name
    )
    panel_artifact = ArtifactRecord.from_path(panel_path, row_count=len(panel))
    common: dict[str, Any] = {
        "source_row_count": len(household),
        "source_record_hashes": sorted(household["record_hash"].astype(str).tolist())
        if "record_hash" in household.columns
        else [],
        "panel_artifact": panel_artifact,
    }
    if not source_manifest_path.is_file() or not normalized_manifest_path.is_file():
        return HouseholdDiagnosticPanelBasis(status="incomplete", **common)
    source_bytes = source_manifest_path.read_bytes()
    normalized_bytes = normalized_manifest_path.read_bytes()
    snapshot = SourceSnapshotManifest.model_validate(json.loads(source_bytes))
    normalized = NormalizedArtifactManifest.model_validate(json.loads(normalized_bytes))
    if not snapshot.raw_artifacts:
        return HouseholdDiagnosticPanelBasis(status="incomplete", **common)
    raw = snapshot.raw_artifacts[0]
    from pathlib import Path

    raw_path = Path(raw.path)
    normalized_path = Path(normalized.normalized_artifact.path)
    raw_record = ArtifactRecord.from_path(raw_path)
    normalized_record = ArtifactRecord.from_path(normalized_path, row_count=len(household))
    snapshot_ids = (
        set(household["source_snapshot_id"].astype(str))
        if "source_snapshot_id" in household
        else set()
    )
    complete = bool(
        raw_path.is_dir()
        and raw.sha256
        and raw_record.sha256 == raw.sha256
        and normalized_record.sha256 == normalized.normalized_artifact.sha256
        and normalized.normalized_artifact.row_count == len(household)
        and snapshot_ids == {raw.sha256}
        and snapshot.raw_tree_entries
        and directory_tree_entries(raw_path) == snapshot.raw_tree_entries
    )
    return HouseholdDiagnosticPanelBasis(
        status="complete" if complete else "incomplete",
        raw_directory=raw_record,
        raw_tree_entries=snapshot.raw_tree_entries,
        source_snapshot_manifest_path=str(source_manifest_path),
        source_snapshot_manifest_sha256=hashlib.sha256(source_bytes).hexdigest(),
        normalized_manifest_path=str(normalized_manifest_path),
        normalized_manifest_sha256=hashlib.sha256(normalized_bytes).hexdigest(),
        normalized_artifact=normalized_record,
        source_snapshot_id=raw.sha256,
        **common,
    )


def _series_correlation(left: pd.Series, right: pd.Series) -> float:
    joined = pd.concat(
        [pd.to_numeric(left, errors="coerce"), pd.to_numeric(right, errors="coerce")],
        axis=1,
    ).dropna()
    if len(joined) < 2:
        return 0.0
    corr = joined.iloc[:, 0].corr(joined.iloc[:, 1])
    if pd.isna(corr):
        return 0.0
    return float(corr)


def _weighted_mape_frame(
    frame: pd.DataFrame,
    *,
    observed_column: str,
    predicted_column: str,
    weight_column: str,
) -> float:
    if frame.empty:
        return 1.0
    observed = (
        pd.to_numeric(frame[observed_column], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    )
    predicted = (
        pd.to_numeric(frame[predicted_column], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    )
    weights = pd.to_numeric(frame[weight_column], errors="coerce").fillna(1.0).to_numpy(dtype=float)
    denominator = np.maximum(np.abs(observed), 1e-9)
    if weights.sum() <= 1e-12:
        return float(np.mean(np.abs(observed - predicted) / denominator))
    return float(np.average(np.abs(observed - predicted) / denominator, weights=weights))


def _build_labor_validation_artifacts(
    *,
    labor: pd.DataFrame,
    household: pd.DataFrame,
    employment_service: pd.DataFrame,
    macro: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    labor_micro_panel = _aggregate_labor_micro_panel(labor)
    household_panel = _aggregate_household_income_panel(household)
    employment_panel = _aggregate_employment_admin_panel(employment_service)
    macro_panel = _extract_macro_labor_panel(macro)

    validation_panel = (
        labor_micro_panel.merge(
            employment_panel,
            on=["region_code", "period_id"],
            how="outer",
        )
        .merge(
            household_panel,
            on=["region_code", "period_id"],
            how="left",
        )
        .merge(
            macro_panel,
            on=["region_code", "period_id"],
            how="left",
        )
    )
    if validation_panel.empty:
        validation_panel = pd.DataFrame(
            columns=[
                "region_code",
                "period_id",
                "micro_participation_rate",
                "micro_employment_rate",
                "micro_informal_employment_rate",
                "micro_sample_weight",
                "micro_respondent_count",
                "admin_employment_count",
                "vacancies",
                "admin_employment_rate_proxy",
                "household_income_mean",
                "household_weight_sum",
                "macro_labor_signal",
            ]
        )

    micro_periods = sorted(
        labor_micro_panel.get("period_id", pd.Series(dtype="string"))
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    admin_periods = sorted(
        employment_panel.get("period_id", pd.Series(dtype="string"))
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    micro_regions = sorted(
        labor_micro_panel.get("region_code", pd.Series(dtype="string"))
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    admin_regions = sorted(
        employment_panel.get("region_code", pd.Series(dtype="string"))
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    temporal_overlap_periods = sorted(set(micro_periods) & set(admin_periods))
    regional_overlap_codes = sorted(set(micro_regions) & set(admin_regions))
    overlap = validation_panel.dropna(
        subset=["micro_employment_rate", "admin_employment_rate_proxy"],
    ).copy()
    if overlap.empty:
        rationale: list[str] = []
        if not temporal_overlap_periods:
            rationale.append("no_temporal_overlap_between_micro_and_admin_labor_panels")
        if not regional_overlap_codes:
            rationale.append("no_region_overlap_between_micro_and_admin_labor_panels")
        if not rationale:
            rationale.append("no_overlap_between_micro_and_admin_labor_panels")
        report = {
            "schema_version": "1.0",
            "family": ObservationFamily.LABOR_MARKET.value,
            "bias_validated": False,
            "promotion_allowed": False,
            "overlap_rows": 0,
            "employment_correlation": 0.0,
            "employment_wmape": 1.0,
            "macro_correlation": 0.0,
            "micro_period_min": micro_periods[0] if micro_periods else None,
            "micro_period_max": micro_periods[-1] if micro_periods else None,
            "admin_period_min": admin_periods[0] if admin_periods else None,
            "admin_period_max": admin_periods[-1] if admin_periods else None,
            "temporal_overlap_period_count": len(temporal_overlap_periods),
            "regional_overlap_count": len(regional_overlap_codes),
            "rationale": rationale,
        }
        corrected_panel = employment_panel.copy()
        if not corrected_panel.empty:
            corrected_panel["corrected_employment_rate"] = corrected_panel[
                "admin_employment_rate_proxy"
            ]
            corrected_panel["measurement_bias_flag"] = True
            corrected_panel["trust_weight"] = 0.55
        else:
            corrected_panel = pd.DataFrame(
                columns=[
                    "region_code",
                    "period_id",
                    "corrected_employment_rate",
                    "measurement_bias_flag",
                    "trust_weight",
                ]
            )
        return validation_panel, corrected_panel, report

    overlap["validation_weight"] = pd.to_numeric(
        overlap.get("micro_sample_weight", 1.0),
        errors="coerce",
    ).fillna(1.0)
    overlap["correction_factor"] = np.where(
        overlap["admin_employment_rate_proxy"].to_numpy(dtype=float) > 1e-9,
        overlap["micro_employment_rate"].to_numpy(dtype=float)
        / np.maximum(overlap["admin_employment_rate_proxy"].to_numpy(dtype=float), 1e-9),
        1.0,
    )
    overlap["correction_factor"] = np.clip(overlap["correction_factor"], 0.25, 4.0)
    employment_correlation = _series_correlation(
        overlap["micro_employment_rate"],
        overlap["admin_employment_rate_proxy"],
    )
    employment_wmape = _weighted_mape_frame(
        overlap,
        observed_column="micro_employment_rate",
        predicted_column="admin_employment_rate_proxy",
        weight_column="validation_weight",
    )
    macro_overlap = overlap.dropna(subset=["macro_labor_signal"]).copy()
    if not macro_overlap.empty:
        macro_scaled = pd.to_numeric(macro_overlap["macro_labor_signal"], errors="coerce").fillna(
            0.0
        )
        macro_scaled = macro_scaled / max(float(macro_scaled.max()), 1.0)
        macro_correlation = _series_correlation(
            macro_scaled, macro_overlap["micro_employment_rate"]
        )
    else:
        macro_correlation = 0.0

    bias_validated = bool(
        len(overlap) >= 4
        and employment_correlation >= 0.60
        and employment_wmape <= 0.35
        and (macro_correlation >= 0.40 or macro_overlap.empty)
    )

    correction_by_region = overlap.groupby("region_code", as_index=False).agg(
        region_correction_factor=("correction_factor", "median")
    )
    corrected_panel = employment_panel.merge(correction_by_region, on="region_code", how="left")
    corrected_panel["region_correction_factor"] = corrected_panel[
        "region_correction_factor"
    ].fillna(float(np.median(overlap["correction_factor"])) if not overlap.empty else 1.0)
    corrected_panel["corrected_employment_rate"] = np.clip(
        corrected_panel["admin_employment_rate_proxy"].to_numpy(dtype=float)
        * corrected_panel["region_correction_factor"].to_numpy(dtype=float),
        0.0,
        1.0,
    )
    corrected_panel["measurement_bias_flag"] = not bias_validated
    corrected_panel["trust_weight"] = 0.90 if bias_validated else 0.65

    report = {
        "schema_version": "1.0",
        "family": ObservationFamily.LABOR_MARKET.value,
        "bias_validated": bias_validated,
        "promotion_allowed": bias_validated,
        "overlap_rows": len(overlap),
        "employment_correlation": float(employment_correlation),
        "employment_wmape": float(employment_wmape),
        "macro_correlation": float(macro_correlation),
        "median_correction_factor": float(np.median(overlap["correction_factor"]))
        if not overlap.empty
        else 1.0,
        "rationale": (
            ["labor_proxy_promoted_via_bias_validation"]
            if bias_validated
            else ["labor_proxy_remains_proxy_until_bias_validation_improves"]
        ),
    }
    return validation_panel, corrected_panel, report


def build_d3_stage(config: PipelineConfig) -> StageBuildResult:
    """Build D3 household, labor, and distress enrichment artifacts."""

    build_root = config.build_root
    stage_dir = _stage_dir(build_root, StageId.D3)
    ensure_dirs(stage_dir)
    outputs: dict[str, ArtifactRecord] = {}
    warnings: list[str] = []

    household = _load_source_frame(config, "household_microdata")
    labor = _load_source_frame(config, "labor_force_microdata")
    pfu = _load_source_frame(config, "pfu_debt")
    wage = _load_source_frame(config, "wage_arrears")
    distress = _load_source_frame(config, "distress_events")
    employment_service = _load_optional_source_frame(
        config,
        "employment_service",
        columns=[
            "agent_id",
            "region_code",
            "period_id",
            "employment_count",
            "vacancies",
        ],
    )
    if employment_service is None:
        employment_service = pd.DataFrame(
            columns=[
                "agent_id",
                "region_code",
                "period_id",
                "employment_count",
                "vacancies",
            ]
        )
    macro = _load_optional_source_frame(
        config,
        "macro_nbu_derzhstat",
        columns=["metric_id", "observed_value", "region_code", "period_id"],
    )
    if macro is None:
        macro = pd.DataFrame(columns=["metric_id", "observed_value", "region_code", "period_id"])

    if household.empty:
        household = pd.DataFrame({"market_income": [100.0], "feature_0": [1.0]})
    household_numeric = household.select_dtypes(include=["number"]).fillna(0.0)
    household_feature_cols = list(household_numeric.columns[:4]) or ["feature_0"]
    household_features = household_numeric[household_feature_cols].to_numpy(dtype=float)
    household_contract = {
        "market_income": _safe_numeric_series(
            household,
            "market_income" if "market_income" in household.columns else household_feature_cols[0],
        ).to_numpy(dtype=float),
        "weights": np.ones(len(household), dtype=float),
        "household_ids": np.asarray(
            [f"hh::{idx:05d}" for idx in range(len(household))], dtype=object
        ),
        "features": household_features,
        "feature_names": household_feature_cols,
        "metadata": {"stage": "d3", "producer_stage": "d3"},
    }
    microsim_contract_path = stage_dir / "microsim_survey_contract_v1.json"
    _write_json(microsim_contract_path, household_contract)
    outputs["microsim_survey_contract_v1.json"] = ArtifactRecord.from_path(microsim_contract_path)

    corrected_firms = pfu.assign(
        selection_term=np.log1p(_safe_numeric_series(pfu, "debt_amount", fill=0.0))
    ).assign(
        corrected_exit_bias=lambda frame: frame["selection_term"]
        / (frame["selection_term"].max() or 1.0)
    )
    outputs["corrected_firm_panels.parquet"] = _write_frame(
        stage_dir / "corrected_firm_panels.parquet",
        corrected_firms,
    )

    survival_frame = pd.DataFrame(
        {
            "duration": np.maximum(
                _safe_numeric_series(distress, "months_to_event", fill=12.0), 1.0
            ),
            "event": (_safe_numeric_series(distress, "event_flag", fill=1.0) > 0.0).astype(int),
            "risk_signal": _safe_numeric_series(
                pfu.reindex(distress.index), "debt_amount", fill=0.0
            ),
            "wage_arrears": _safe_numeric_series(
                wage.reindex(distress.index), "arrears_amount", fill=0.0
            ),
        }
    )
    outputs["survival_hazard_estimates.parquet"] = _write_frame(
        stage_dir / "survival_hazard_estimates.parquet",
        survival_frame,
    )

    labor_validation_panel, labor_corrected_panel, labor_bias_validation = (
        _build_labor_validation_artifacts(
            labor=labor,
            household=household,
            employment_service=employment_service,
            macro=macro,
        )
    )
    outputs["labor_validation_panel.parquet"] = _write_frame(
        stage_dir / "labor_validation_panel.parquet",
        labor_validation_panel,
    )
    outputs["labor_market_corrected_panel.parquet"] = _write_frame(
        stage_dir / "labor_market_corrected_panel.parquet",
        labor_corrected_panel,
    )
    labor_bias_validation_path = _write_json(
        stage_dir / "labor_bias_validation.json",
        labor_bias_validation,
    )
    outputs["labor_bias_validation.json"] = ArtifactRecord.from_path(labor_bias_validation_path)

    calibrated_household_cells = _build_calibrated_household_cells(household)
    outputs["calibrated_household_cells.parquet"] = _write_frame(
        stage_dir / "calibrated_household_cells.parquet",
        calibrated_household_cells,
    )

    household_diagnostic_panel = build_household_diagnostic_panel(household)
    household_diagnostic_panel_path = stage_dir / "household_candidate_panel.parquet"
    outputs["household_candidate_panel.parquet"] = _write_frame(
        household_diagnostic_panel_path, household_diagnostic_panel
    )
    household_diagnostic_basis = _build_household_diagnostic_basis(
        config, household, household_diagnostic_panel_path, household_diagnostic_panel
    )
    household_diagnostic_basis_path = stage_dir / "household_candidate_basis.json"
    _write_json(household_diagnostic_basis_path, household_diagnostic_basis)
    outputs["household_candidate_basis.json"] = ArtifactRecord.from_path(
        household_diagnostic_basis_path
    )

    lesson_registry_path = stage_dir / "lesson_registry_seed_v1.json"
    _write_json(
        lesson_registry_path,
        {
            "schema_version": "1.0",
            "lessons": [
                {
                    "lesson_id": "lesson::data_quality::household_weights",
                    "status": "success",
                    "message": "Household microdata contract generated for server-side calibration.",
                },
                {
                    "lesson_id": "lesson::data_quality::labor_bias_validation",
                    "status": "success"
                    if labor_bias_validation.get("bias_validated")
                    else "warning",
                    "message": (
                        "Labor proxy promoted via bias validation."
                        if labor_bias_validation.get("bias_validated")
                        else "Labor proxy remains provisional until bias validation improves."
                    ),
                },
            ],
        },
    )
    outputs["lesson_registry_seed_v1.json"] = ArtifactRecord.from_path(lesson_registry_path)

    for source_id in ("logistics_mobility_displacement", "land_cadastre"):
        source = config.sources[source_id]
        source_path = config.build_root.normalized_dir / source_id / source.normalized_artifact
        if not source_path.exists():
            skipped_path = _manifest_path(build_root, f"{source_id}_skipped_source_manifest.json")
            _write_json(
                skipped_path,
                {
                    "source_id": source_id,
                    "reason": source.optional_reason or "optional_source_not_configured",
                },
            )
            outputs[skipped_path.name] = ArtifactRecord.from_path(skipped_path)
            warnings.append(f"optional source skipped: {source_id}")

    return StageBuildResult(
        outputs=outputs,
        warnings=warnings,
        metrics={
            "household_rows": len(household),
            "labor_rows": len(labor),
            "distress_rows": len(distress),
            "labor_validation_overlap_rows": int(labor_bias_validation.get("overlap_rows", 0)),
            "labor_bias_validated": bool(labor_bias_validation.get("bias_validated", False)),
        },
        manifest_paths=[lesson_registry_path, labor_bias_validation_path],
    )


__all__ = ("build_d3_stage",)
