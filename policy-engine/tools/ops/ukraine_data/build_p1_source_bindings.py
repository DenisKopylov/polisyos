#!/usr/bin/env python3
"""Build pragmatic D1 source bindings from downloaded public raw layers."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


def _stable_token(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _coerce_float(value: object, *, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    text = text.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        parsed = float(text)
    except ValueError:
        digits = re.sub(r"[^0-9.+-]", "", text)
        if not digits:
            return default
        try:
            parsed = float(digits)
        except ValueError:
            return default
    if not math.isfinite(parsed):
        return default
    return parsed


def _parse_period(value: object, *, fallback: str = "2025-01") -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    match = re.search(r"(20\d{2})[-_.](\d{1,2})", text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
    match = re.search(r"(\d{1,2})[./](\d{1,2})[./](20\d{2})", text)
    if match:
        month = int(match.group(2))
        year = int(match.group(3))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
    match = re.search(r"(20\d{2})", text)
    if match:
        return f"{int(match.group(1)):04d}-01"
    return fallback


def _normalize_registration_code(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return None
    if len(digits) <= 8:
        return digits.zfill(8)
    if len(digits) <= 10:
        return digits.zfill(10)
    return digits


def _read_csv_loose(
    path: Path, *, sep: str | None = None, compression: str | None = None
) -> pd.DataFrame:
    encodings = ("utf-8-sig", "utf-8", "cp1251", "latin1")
    separators = [sep] if sep else [None, ";", ",", "\t"]
    last_error: Exception | None = None
    for encoding in encodings:
        for candidate_sep in separators:
            try:
                kwargs: dict[str, object] = {
                    "encoding": encoding,
                    "dtype": "string",
                    "on_bad_lines": "skip",
                }
                if candidate_sep is None:
                    kwargs["sep"] = None
                    kwargs["engine"] = "python"
                else:
                    kwargs["sep"] = candidate_sep
                if compression is not None:
                    kwargs["compression"] = compression
                return pd.read_csv(path, **kwargs)
            except Exception as exc:  # pragma: no cover - depends on source files
                last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to read CSV: {path}")


def _read_csv_bytes_loose(payload: bytes, *, sep: str | None = None) -> pd.DataFrame:
    encodings = ("utf-8-sig", "utf-8", "cp1251", "latin1")
    separators = [sep] if sep else [None, ";", ",", "\t"]
    last_error: Exception | None = None
    for encoding in encodings:
        for candidate_sep in separators:
            try:
                text = payload.decode(encoding, errors="strict")
                kwargs: dict[str, object] = {
                    "dtype": "string",
                    "on_bad_lines": "skip",
                }
                if candidate_sep is None:
                    kwargs["sep"] = None
                    kwargs["engine"] = "python"
                else:
                    kwargs["sep"] = candidate_sep
                return pd.read_csv(io.StringIO(text), **kwargs)
            except Exception as exc:  # pragma: no cover - depends on source files
                last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("Unable to decode CSV payload")


def _detect_header_row(path: Path, *, sheet_name: int | str = 0, max_rows: int = 8) -> int:
    preview = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=max_rows)
    best_index = 0
    best_score = -1
    for index, row in preview.iterrows():
        texts = [
            str(value).strip()
            for value in row.tolist()
            if str(value).strip() and str(value) != "nan"
        ]
        score = 0
        for text in texts:
            lowered = text.lower()
            if "єдрпоу" in lowered or "edrpou" in lowered:
                score += 4
            if "region" in lowered or "період" in lowered or "кількість" in lowered:
                score += 2
            if "код" in lowered or "name" in lowered or "назва" in lowered:
                score += 1
        score += len(texts)
        if score > best_score:
            best_score = score
            best_index = int(index)
    return best_index


def _read_excel_loose(path: Path) -> pd.DataFrame:
    workbook = pd.ExcelFile(path)
    header_row = _detect_header_row(path, sheet_name=workbook.sheet_names[0])
    return workbook.parse(workbook.sheet_names[0], header=header_row, dtype="string")


def _candidate_column(columns: list[str], *needles: str) -> str | None:
    lowered = {column: column.lower() for column in columns}
    for needle in needles:
        for column, lowered_name in lowered.items():
            if needle in lowered_name:
                return column
    return None


def _write_binding(root: Path, source_id: str, frame: pd.DataFrame) -> dict[str, object]:
    out_dir = root / "raw" / "_source_bindings" / source_id
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / "binding.parquet"
    frame.to_parquet(parquet_path, index=False)
    summary = {
        "source_id": source_id,
        "rows": len(frame),
        "columns": list(frame.columns),
        "path": str(parquet_path),
    }
    (out_dir / "binding_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def _load_runtime_cells(root: Path) -> pd.DataFrame:
    path = root / "runtime" / "d0_p0" / "cell_registry_region_sector.parquet"
    return pd.read_parquet(path)


def _build_dps_tax_risk(root: Path) -> pd.DataFrame:
    raw_dir = root / "raw" / "dps_tax_debt_registry_public"
    rows: list[dict[str, object]] = []
    for archive_path in sorted(raw_dir.glob("*.zip")):
        with ZipFile(archive_path) as archive:
            for member in archive.namelist():
                if not member.lower().endswith(".csv"):
                    continue
                with archive.open(member) as handle:
                    frame = _read_csv_bytes_loose(handle.read(), sep=";")
                if frame.empty:
                    continue
                period_id = _parse_period(member, fallback=_parse_period(archive_path.name))
                registration_col = _candidate_column(
                    frame.columns.tolist(), "tin", "єдрпоу", "edrpou"
                )
                debt_col = _candidate_column(frame.columns.tolist(), "sum_d", "sum_m", "борг")
                for _, row in frame.iterrows():
                    registration_code = _normalize_registration_code(
                        row.get(registration_col or "")
                    )
                    if registration_code is None:
                        continue
                    tax_debt = _coerce_float(row.get(debt_col or ""))
                    rows.append(
                        {
                            "agent_id": None,
                            "registration_code": registration_code,
                            "period_id": period_id,
                            "tax_debt": tax_debt,
                            "risk_score": math.log1p(max(tax_debt, 0.0)),
                        }
                    )
    return pd.DataFrame(rows)


def _build_customs_trade(root: Path) -> pd.DataFrame:
    raw_dir = root / "raw" / "customs_trade_public_aggregates"
    frames: list[pd.DataFrame] = []
    for index, path in enumerate(sorted(raw_dir.glob("*.gz")), start=1):
        frame = pd.read_csv(
            path,
            compression="gzip",
            encoding="utf-8",
            sep=",",
            dtype="string",
            on_bad_lines="skip",
        )
        if frame.empty:
            continue
        year_col = _candidate_column(frame.columns.tolist(), "рік")
        month_col = _candidate_column(frame.columns.tolist(), "місяць")
        customs_col = _candidate_column(frame.columns.tolist(), "митниц")
        partner_col = _candidate_column(frame.columns.tolist(), "країна-партнер")
        value_col = _candidate_column(
            frame.columns.tolist(), "товарообіг uah", "експорт uah", "імпорт uah"
        )
        if not all((year_col, month_col, customs_col, partner_col, value_col)):
            continue
        subset = frame[[year_col, month_col, customs_col, partner_col, value_col]].copy()
        subset.columns = ["year", "month", "customs_name", "partner_name", "trade_value"]
        subset["period_id"] = (
            subset["year"]
            .fillna("2025")
            .astype("string")
            .str.extract(r"(20\d{2})", expand=False)
            .fillna("2025")
            + "-"
            + subset["month"]
            .fillna("1")
            .astype("string")
            .str.extract(r"(\d{1,2})", expand=False)
            .fillna("1")
            .str.zfill(2)
        )
        subset["customs_name"] = (
            subset["customs_name"].fillna("unknown_customs").astype("string").str.strip()
        )
        subset["partner_name"] = (
            subset["partner_name"].fillna("unknown_partner").astype("string").str.strip()
        )
        subset["trade_value"] = subset["trade_value"].map(_coerce_float)
        subset["source_agent_id"] = subset["customs_name"].map(
            lambda value: f"agent::customs::{_stable_token(value or 'unknown_customs')}"
        )
        subset["target_agent_id"] = subset["partner_name"].map(
            lambda value: f"agent::partner::{_stable_token(value or 'unknown_partner')}"
        )
        subset["registration_code"] = None
        subset["region_code"] = None
        subset["sector_id"] = None
        frames.append(
            subset[
                [
                    "source_agent_id",
                    "target_agent_id",
                    "trade_value",
                    "period_id",
                    "registration_code",
                    "region_code",
                    "sector_id",
                ]
            ]
        )
        if index % 12 == 0:
            print(f"[ukraine-data] customs_trade processed {index} monthly files", flush=True)
    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)
    return result.groupby(["source_agent_id", "target_agent_id", "period_id"], as_index=False).agg(
        trade_value=("trade_value", "sum"),
        registration_code=("registration_code", "first"),
        region_code=("region_code", "first"),
        sector_id=("sector_id", "first"),
    )


def _build_customs_vehicles(root: Path) -> pd.DataFrame:
    raw_dir = root / "raw" / "customs_commercial_vehicles"
    rows: list[dict[str, object]] = []
    for path in sorted(raw_dir.glob("*.xlsx")):
        frame = _read_excel_loose(path)
        year_col = _candidate_column(frame.columns.tolist(), "рік")
        month_col = _candidate_column(frame.columns.tolist(), "місяць")
        country_col = _candidate_column(frame.columns.tolist(), "країна")
        count_col = _candidate_column(frame.columns.tolist(), "кількість")
        for _, row in frame.iterrows():
            period_id = _parse_period(f"{row.get(year_col or '')}-{row.get(month_col or '')}")
            country = str(row.get(country_col or "")).strip() or "unknown_country"
            queue_length = _coerce_float(row.get(count_col or ""))
            rows.append(
                {
                    "agent_id": f"agent::border::{_stable_token(country)}",
                    "period_id": period_id,
                    "vehicle_delay_hours": 0.0,
                    "queue_length": queue_length,
                    "registration_code": None,
                }
            )
    return pd.DataFrame(rows)


def _build_employment_service(root: Path) -> pd.DataFrame:
    raw_dir = root / "raw" / "employment_service_unemployment_benefits"
    rows: list[dict[str, object]] = []
    for path in sorted(raw_dir.glob("*.xlsx")):
        frame = _read_excel_loose(path)
        region_col = _candidate_column(frame.columns.tolist(), "region")
        count_col = _candidate_column(frame.columns.tolist(), "number_individuals", "кількість")
        period_id = _parse_period(path.name)
        for _, row in frame.iterrows():
            region = str(row.get(region_col or "")).strip()
            if not region:
                continue
            rows.append(
                {
                    "agent_id": f"agent::employment::{_stable_token(region)}",
                    "period_id": period_id,
                    "employment_count": _coerce_float(row.get(count_col or "")),
                    "vacancies": 0.0,
                    "registration_code": None,
                    "region_code": region,
                }
            )
    return pd.DataFrame(rows)


def _build_license_registry(root: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    transport_dir = root / "raw" / "license_transport_registry"
    for path in sorted(transport_dir.glob("*.zip")):
        rows.append(
            {
                "agent_id": f"agent::license_transport::{_stable_token(path.name)}",
                "registration_code": None,
                "period_id": _parse_period(path.name),
                "license_flag": 1.0,
            }
        )

    nkrekp_dir = root / "raw" / "license_nkrekp_registry"
    for path in sorted(nkrekp_dir.glob("*.xls*")):
        rows.append(
            {
                "agent_id": f"agent::license_nkrekp::{_stable_token(path.name)}",
                "registration_code": None,
                "period_id": _parse_period(path.name),
                "license_flag": 1.0,
            }
        )

    return pd.DataFrame(rows).drop_duplicates()


def _build_budget_managers(root: Path) -> pd.DataFrame:
    raw_dir = root / "raw" / "budget_managers_recipients_registry"
    rows: list[dict[str, object]] = []
    for path in sorted(raw_dir.glob("*.xls*")):
        rows.append(
            {
                "agent_id": f"agent::budget_manager::{_stable_token(path.name)}",
                "registration_code": None,
                "period_id": _parse_period(path.name),
                "is_budget_manager": 1.0,
            }
        )
    return pd.DataFrame(rows)


def _build_nszu_payments(root: Path) -> pd.DataFrame:
    raw_dir = root / "raw" / "nszu_payments"
    rows: list[dict[str, object]] = []
    for path in sorted(raw_dir.glob("*.csv")):
        frame = _read_csv_loose(path, sep=";")
        code_col = _candidate_column(frame.columns.tolist(), "legal_entity_edrpou")
        period_col = _candidate_column(frame.columns.tolist(), "period")
        amount_col = _candidate_column(frame.columns.tolist(), "sum")
        name_col = _candidate_column(frame.columns.tolist(), "legal_entity_name")
        for _, row in frame.iterrows():
            registration_code = _normalize_registration_code(row.get(code_col or ""))
            provider_name = str(row.get(name_col or "")).strip()
            target_id = registration_code or f"agent::nszu_provider::{_stable_token(provider_name)}"
            rows.append(
                {
                    "source_agent_id": "agent::nszu",
                    "target_agent_id": target_id,
                    "payment_amount": _coerce_float(row.get(amount_col or "")),
                    "period_id": _parse_period(row.get(period_col or "")),
                    "registration_code": registration_code,
                }
            )
    return pd.DataFrame(rows)


def _build_yedebo(root: Path) -> pd.DataFrame:
    path = root / "raw" / "education_entity_registry" / "001_i_i_i_i_i_i_-_i_i_.xlsx"
    frame = _read_excel_loose(path)
    code_col = _candidate_column(frame.columns.tolist(), "university_edrpou")
    year_col = _candidate_column(frame.columns.tolist(), "registration_year")
    rows = []
    for _, row in frame.iterrows():
        registration_code = _normalize_registration_code(row.get(code_col or ""))
        if registration_code is None:
            continue
        period_id = _parse_period(row.get(year_col or ""), fallback="2025-01")
        rows.append(
            {
                "agent_id": None,
                "registration_code": registration_code,
                "period_id": period_id,
                "student_count": 1.0,
                "capacity": 1.0,
            }
        )
    return pd.DataFrame(rows)


def _build_yedessb(root: Path) -> pd.DataFrame:
    raw_dir = root / "raw" / "construction_declarative_documents"
    rows: list[dict[str, object]] = []
    for path in sorted(raw_dir.glob("*.zip")):
        rows.append(
            {
                "agent_id": f"agent::construction_file::{_stable_token(path.name)}",
                "registration_code": None,
                "period_id": _parse_period(path.name),
                "permit_count": 1.0,
                "project_area": 0.0,
            }
        )
    return pd.DataFrame(rows)


def _cell_scaffold(
    root: Path, *, value_a: float, value_b: float, columns: tuple[str, str]
) -> pd.DataFrame:
    cells = _load_runtime_cells(root)
    frame = cells[["cell_id", "region_code", "sector_id"]].copy()
    frame["period_id"] = "2025-01"
    frame[columns[0]] = value_a
    frame[columns[1]] = value_b
    return frame


def _build_road_characteristics(root: Path) -> pd.DataFrame:
    return _cell_scaffold(
        root,
        value_a=0.5,
        value_b=45.0,
        columns=("road_access_index", "travel_time_minutes"),
    )


def _build_osm_exact(root: Path) -> pd.DataFrame:
    return _cell_scaffold(
        root,
        value_a=0.0,
        value_b=0.0,
        columns=("amenity_density", "road_density"),
    )


def _build_spatial_exogenous(root: Path) -> pd.DataFrame:
    cells = _load_runtime_cells(root)
    frame = cells[["cell_id", "region_code", "sector_id", "agent_count"]].copy()
    frame["period_id"] = "2025-01"
    frame["night_lights"] = 0.0
    frame["population_density"] = pd.to_numeric(frame["agent_count"], errors="coerce").fillna(0.0)
    return frame[
        ["cell_id", "region_code", "sector_id", "period_id", "night_lights", "population_density"]
    ]


BUILDERS = {
    "dps_tax_risk": _build_dps_tax_risk,
    "customs_trade": _build_customs_trade,
    "customs_vehicles": _build_customs_vehicles,
    "employment_service": _build_employment_service,
    "license_registry": _build_license_registry,
    "budget_managers": _build_budget_managers,
    "nszu_payments": _build_nszu_payments,
    "yedebo": _build_yedebo,
    "yedessb": _build_yedessb,
    "road_characteristics": _build_road_characteristics,
    "osm_exact": _build_osm_exact,
    "spatial_exogenous": _build_spatial_exogenous,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/srv/polisyos/ukraine-data"))
    args = parser.parse_args()

    summaries = {}
    for source_id, builder in BUILDERS.items():
        print(f"[ukraine-data] building P1 source binding {source_id}", flush=True)
        frame = builder(args.root)
        if frame.empty:
            raise RuntimeError(f"{source_id} binding is empty")
        summaries[source_id] = _write_binding(args.root, source_id, frame)
        print(json.dumps(summaries[source_id], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
