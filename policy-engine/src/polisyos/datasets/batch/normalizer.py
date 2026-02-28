"""Stage 2: Normalize raw source payloads to a DCAT-like canonical form."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.knowledge.types import DatasetRecord, DistributionRecord

_INDICATOR_RE = re.compile(
    r"\b(GDP|GNP|CPI|PPI|HDI|unemployment|inflation|poverty|gini|population|fertility|mortality|"
    r"import|export|trade|debt|deficit|surplus|revenue|expenditure|literacy|enrollment|CO2|emissions|energy)\b",
    re.IGNORECASE,
)


def _stable_id(*parts: str, size: int = 20) -> str:
    canon = "|".join(parts)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:size]


def _distribution_id(dataset_id: str, url: str, fmt: str) -> str:
    return _stable_id(dataset_id, url, fmt)


def extract_variables(raw: dict) -> list[str]:
    variables: list[str] = []
    for key in ("id", "dataset_id", "indicator_id", "indicator_code", "code", "dataflow_id"):
        value = raw.get(key)
        if value:
            variables.append(str(value))

    extras = raw.get("extras")
    if isinstance(extras, list):
        for item in extras:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).lower()
            if key in {"indicator", "variable", "measure"}:
                value = item.get("value")
                if value:
                    variables.append(str(value))

    text = (
        f"{raw.get('title', '')} "
        f"{raw.get('name', '')} "
        f"{raw.get('description', '')} "
        f"{raw.get('notes', '')}"
    )
    for match in _INDICATOR_RE.finditer(text):
        token = match.group(0).upper()
        if token not in variables:
            variables.append(token)
    return variables


def _map_metrics(raw: dict, metrics_map: dict[str, dict] | None) -> list[str]:
    if not metrics_map:
        return []
    text = f"{raw.get('title', '')} {raw.get('name', '')} {raw.get('description', '')}".lower()
    codes = {str(raw.get(k, "")).upper() for k in ("id", "dataset_id", "indicator_id", "dataflow_id") if raw.get(k)}

    matched: list[str] = []
    for metric_id, spec in metrics_map.items():
        keywords = [str(v).lower() for v in spec.get("keywords", [])]
        if any(k in text for k in keywords):
            matched.append(metric_id)
            continue
        for code_key in ("sdmx_concepts", "worldbank_indicators", "eurostat_codes"):
            code_set = {str(v).upper() for v in spec.get(code_key, [])}
            if codes & code_set:
                matched.append(metric_id)
                break
    return matched


def _normalize_sdmx(raw: dict, *, source: str, metrics_map: dict[str, dict] | None) -> DatasetRecord:
    dataset_id = str(raw.get("id") or raw.get("dataflow_id") or "")
    agency = str(raw.get("agencyID") or raw.get("agency_id") or "")
    dedup_key = f"{source}|{agency}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)
    dist = DistributionRecord(
        id=_distribution_id(rid, "", "SDMX-JSON"),
        format="SDMX-JSON",
        connector_type="sdmx",
        connector_params={"dataflow_id": dataset_id, "agency_id": agency},
    )
    return DatasetRecord(
        id=rid,
        title=str(raw.get("name") or dataset_id),
        description=str(raw.get("description") or ""),
        publisher=agency or source,
        variables=extract_variables(raw),
        formats=["SDMX-JSON"],
        distributions=[dist],
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=agency,
        dataset_id=dataset_id,
        dedup_key=dedup_key,
    )


def _normalize_worldbank(raw: dict, *, metrics_map: dict[str, dict] | None) -> DatasetRecord:
    dataset_id = str(raw.get("id", ""))
    agency = "WB"
    source = "worldbank"
    dedup_key = f"{source}|{agency}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)
    dist = DistributionRecord(
        id=_distribution_id(rid, dataset_id, "JSON"),
        url=f"https://api.worldbank.org/v2/country/all/indicator/{dataset_id}?format=json",
        format="JSON",
        connector_type="worldbank",
        connector_params={"indicator_id": dataset_id},
    )
    return DatasetRecord(
        id=rid,
        title=str(raw.get("name") or dataset_id),
        description=str(raw.get("sourceNote") or ""),
        publisher="World Bank",
        themes=[str((raw.get("source") or {}).get("value", ""))] if isinstance(raw.get("source"), dict) else [],
        variables=extract_variables(raw),
        spatial="WORLD",
        license="CC-BY-4.0",
        formats=["JSON"],
        distributions=[dist],
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=agency,
        dataset_id=dataset_id,
        dedup_key=dedup_key,
    )


def _normalize_ukons(raw: dict, *, metrics_map: dict[str, dict] | None) -> DatasetRecord:
    dataset_id = str(raw.get("id") or "")
    source = "ukons"
    agency = "ONS"
    dedup_key = f"{source}|{agency}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)
    return DatasetRecord(
        id=rid,
        title=str(raw.get("title") or dataset_id),
        description=str(raw.get("description") or ""),
        publisher="ONS",
        keywords=list(raw.get("keywords") or []),
        variables=extract_variables(raw),
        formats=["JSON"],
        distributions=[
            DistributionRecord(
                id=_distribution_id(rid, dataset_id, "JSON"),
                format="JSON",
                connector_type="ukons",
                connector_params={"dataset_id": dataset_id},
            )
        ],
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=agency,
        dataset_id=dataset_id,
        dedup_key=dedup_key,
    )


def _normalize_indicator_api(
    raw: dict,
    *,
    source: str,
    agency: str,
    endpoint: str,
    connector_type: str,
    metrics_map: dict[str, dict] | None,
) -> DatasetRecord:
    dataset_id = str(
        raw.get("id")
        or raw.get("ID")
        or raw.get("IndicatorCode")
        or raw.get("code")
        or raw.get("Code")
        or raw.get("indicator")
        or raw.get("indicatorCode")
        or ""
    )
    title = str(
        raw.get("name")
        or raw.get("Name")
        or raw.get("title")
        or raw.get("Title")
        or raw.get("IndicatorName")
        or raw.get("description")
        or dataset_id
    )
    description = str(
        raw.get("description")
        or raw.get("Description")
        or raw.get("Definition")
        or raw.get("sourceNote")
        or ""
    )

    dedup_key = f"{source}|{agency}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)
    dist = DistributionRecord(
        id=_distribution_id(rid, endpoint, "JSON"),
        url=endpoint,
        format="JSON",
        connector_type=connector_type,
        connector_params={"indicator_id": dataset_id},
    )
    return DatasetRecord(
        id=rid,
        title=title,
        description=description,
        publisher=agency,
        variables=extract_variables(raw),
        formats=["JSON"],
        distributions=[dist],
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=agency,
        dataset_id=dataset_id,
        dedup_key=dedup_key,
    )


def _normalize_ckan(raw: dict, *, source: str, metrics_map: dict[str, dict] | None) -> DatasetRecord:
    dataset_id = str(raw.get("id") or raw.get("name") or "")
    org = raw.get("organization") if isinstance(raw.get("organization"), dict) else {}
    agency = str(org.get("name") or source)
    dedup_key = f"{source}|{agency}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)

    resources = raw.get("resources") if isinstance(raw.get("resources"), list) else []
    dists = [
        DistributionRecord(
            id=_distribution_id(rid, str(res.get("url", "")), str(res.get("format", ""))),
            url=str(res.get("url") or ""),
            format=str(res.get("format") or ""),
            name=str(res.get("name") or ""),
            connector_type="rest_json",
            connector_params={"resource_id": str(res.get("id") or "")},
        )
        for res in resources
        if isinstance(res, dict)
    ]

    tags = [str(t.get("name") or "") for t in (raw.get("tags") or []) if isinstance(t, dict)]
    return DatasetRecord(
        id=rid,
        title=str(raw.get("title") or dataset_id),
        description=str(raw.get("notes") or raw.get("description") or ""),
        publisher=agency,
        themes=[t for t in tags if t],
        keywords=list(raw.get("keywords") or []),
        variables=extract_variables(raw),
        spatial=str(raw.get("spatial") or ""),
        temporal_start=raw.get("temporal_start"),
        temporal_end=raw.get("temporal_end"),
        license=str(raw.get("license_id") or ""),
        formats=[str(res.get("format") or "") for res in resources if isinstance(res, dict)],
        distributions=dists,
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=agency,
        dataset_id=dataset_id,
        dedup_key=dedup_key,
    )


def normalize_raw_sources(config: DatasetBatchConfig, *, metrics_map: dict[str, dict] | None = None) -> dict[str, int]:
    """Normalize latest raw snapshots to per-source JSONL files."""
    source_dirs = sorted([p for p in config.raw_dir.iterdir() if p.is_dir()]) if config.raw_dir.exists() else []
    counts: dict[str, int] = {}

    started_at = datetime.now(UTC).isoformat()
    artifacts: list[Path] = []
    for source_dir in source_dirs:
        latest_snapshots = sorted([p for p in source_dir.iterdir() if p.is_dir()])
        if not latest_snapshots:
            continue
        latest = latest_snapshots[-1]
        payload = latest / "payload.jsonl"
        rows = []
        if payload.exists():
            with open(payload, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))

        source = source_dir.name
        records: list[DatasetRecord] = []
        for row in rows:
            try:
                if source in {"oecd", "imf", "ecb", "eurostat", "undata", "ilo", "unicef"}:
                    rec = _normalize_sdmx(row, source=source, metrics_map=metrics_map)
                elif source == "worldbank":
                    rec = _normalize_worldbank(row, metrics_map=metrics_map)
                elif source == "ukons":
                    rec = _normalize_ukons(row, metrics_map=metrics_map)
                elif source == "who":
                    rec = _normalize_indicator_api(
                        row,
                        source=source,
                        agency="WHO",
                        endpoint="https://ghoapi.azureedge.net/api/Indicator",
                        connector_type="who",
                        metrics_map=metrics_map,
                    )
                elif source == "unesco_uis":
                    rec = _normalize_indicator_api(
                        row,
                        source=source,
                        agency="UNESCO_UIS",
                        endpoint="https://api.uis.unesco.org/api/public/definitions/indicators",
                        connector_type="unesco_uis",
                        metrics_map=metrics_map,
                    )
                elif source == "unpd":
                    rec = _normalize_indicator_api(
                        row,
                        source=source,
                        agency="UNPD",
                        endpoint="https://population.un.org/dataportalapi/api/v1/indicators/",
                        connector_type="unpd",
                        metrics_map=metrics_map,
                    )
                elif source == "data_gov_ua":
                    rec = _normalize_ckan(row, source=source, metrics_map=metrics_map)
                else:
                    rec = _normalize_ckan(row, source=source, metrics_map=metrics_map)
                records.append(rec)
            except Exception:
                continue

        out_path = config.normalized_dir / f"{source}.jsonl"
        with open(out_path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(rec.model_dump_json() + "\n")
        counts[source] = len(records)
        artifacts.append(out_path)

    write_stage_manifest(
        manifest_path=config.manifests_dir / "normalize.json",
        stage="normalize",
        status="ok",
        metrics={"sources": len(counts), "records": sum(counts.values())},
        artifacts=artifacts,
        started_at=started_at,
    )
    return counts


# Backward-compatible API used by existing tests

def map_to_polisyos_metrics(raw: dict, metrics_map: dict[str, dict] | None = None) -> list[str]:
    return _map_metrics(raw, metrics_map)


def normalize_ckan(raw: dict, source_portal: str, metrics_map: dict | None = None) -> DatasetRecord:
    return _normalize_ckan(raw, source=source_portal, metrics_map=metrics_map)


def normalize_worldbank(raw: dict, metrics_map: dict | None = None) -> DatasetRecord:
    return _normalize_worldbank(raw, metrics_map=metrics_map)


def normalize_to_dcat(raw: dict, source_portal: str, connector_type: str, metrics_map: dict | None = None) -> DatasetRecord:
    if connector_type == "worldbank":
        return _normalize_worldbank(raw, metrics_map=metrics_map)
    if connector_type in {"sdmx", "undata"}:
        return _normalize_sdmx(raw, source=source_portal, metrics_map=metrics_map)
    if connector_type in {"who", "unesco_uis", "unpd"}:
        agency_map = {"who": "WHO", "unesco_uis": "UNESCO_UIS", "unpd": "UNPD"}
        return _normalize_indicator_api(
            raw,
            source=source_portal,
            agency=agency_map.get(connector_type, source_portal.upper()),
            endpoint="",
            connector_type=connector_type,
            metrics_map=metrics_map,
        )
    if connector_type == "ukons":
        return _normalize_ukons(raw, metrics_map=metrics_map)
    return _normalize_ckan(raw, source=source_portal, metrics_map=metrics_map)
