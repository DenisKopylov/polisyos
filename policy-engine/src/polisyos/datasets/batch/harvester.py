"""Stage 1: source-driven harvest with wave support and raw manifests."""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp

from polisyos.batch_common.manifest import write_raw_manifest, write_stage_manifest
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.source_registry import SourceSpec

logger = logging.getLogger(__name__)


def _utc_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _latest_snapshot_dir(source_root: Path) -> Path | None:
    if not source_root.exists():
        return None
    dirs = sorted([p for p in source_root.iterdir() if p.is_dir()])
    return dirs[-1] if dirs else None


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


async def harvest_sources(config: DatasetBatchConfig) -> dict[str, list[dict]]:
    """Harvest all enabled sources in selected wave."""
    registry = config.load_registry()
    specs = registry.enabled_sources(wave=config.wave)

    started_at = datetime.now(UTC).isoformat()
    out: dict[str, list[dict]] = {}

    # Wave C is intentionally serial-only and heavy (CKAN data.gov.ua).
    for spec in specs:
        rows = await harvest_one_source(spec, config)
        out[spec.name] = rows

    stage_manifest = config.manifests_dir / "harvest.json"
    write_stage_manifest(
        manifest_path=stage_manifest,
        stage="harvest",
        status="ok",
        metrics={"wave": config.wave or "ALL", "sources": len(specs), "records": sum(len(v) for v in out.values())},
        artifacts=[],
        started_at=started_at,
    )
    return out


async def harvest_one_source(spec: SourceSpec, config: DatasetBatchConfig) -> list[dict]:
    """Harvest one source with optional resume from latest raw snapshot."""
    source_root = config.raw_dir / spec.name
    latest_dir = _latest_snapshot_dir(source_root)
    latest_payload = latest_dir / "payload.jsonl" if latest_dir else None

    if config.resume and latest_payload and latest_payload.exists():
        logger.info("Using cached raw snapshot for %s: %s", spec.name, latest_payload)
        return _read_jsonl(latest_payload)

    logger.info("Harvesting source %s (%s)", spec.name, spec.endpoint)
    if spec.family == "ckan":
        rows = await _harvest_ckan(spec.endpoint, config.max_datasets_per_source, config.harvest_timeout)
    elif spec.family == "worldbank":
        rows = await _harvest_worldbank(spec.endpoint, config.max_datasets_per_source, config.harvest_timeout)
    elif spec.family == "ukons":
        rows = await _harvest_ukons(spec.endpoint, config.max_datasets_per_source, config.harvest_timeout)
    elif spec.family == "undata":
        rows = await _harvest_undata(spec, config.harvest_timeout)
    elif spec.family == "sdmx":
        rows = await _harvest_sdmx_dataflows(spec, config.harvest_timeout)
    elif spec.family == "who":
        rows = await _harvest_who_indicators(spec.endpoint, config.max_datasets_per_source, config.harvest_timeout)
    elif spec.family == "uis":
        rows = await _harvest_uis_indicators(spec.endpoint, config.max_datasets_per_source, config.harvest_timeout)
    elif spec.family == "wvs":
        rows = await _harvest_wvs(spec.endpoint, config.max_datasets_per_source, config.harvest_timeout)
    elif spec.family == "unpd":
        rows = await _harvest_unpd_indicators(spec.endpoint, config.max_datasets_per_source, config.harvest_timeout)
    else:
        logger.warning("Unknown source family '%s' for %s", spec.family, spec.name)
        rows = []

    ts_dir = source_root / _utc_slug()
    payload_path = ts_dir / "payload.jsonl"
    manifest_path = ts_dir / "manifest.json"
    _write_jsonl(payload_path, rows)

    write_raw_manifest(
        manifest_path=manifest_path,
        source=spec.name,
        endpoint=spec.endpoint,
        payload_path=payload_path,
        count=len(rows),
        filters={
            "agency_prefix": spec.agency_prefix,
            "agency_allowlist": list(spec.agency_allowlist),
            "exclude_agencies": list(spec.exclude_agencies),
            "wave": spec.wave,
        },
        parser_version="2",
    )
    return rows


async def _harvest_ckan(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    start = 0
    per_page = 100
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(rows) < limit:
            params = {"rows": per_page, "start": start, "include_private": "false"}
            async with session.get(endpoint, params=params) as resp:
                if resp.status != 200:
                    break
                data = await resp.json(content_type=None)
            result = data.get("result", {}) if isinstance(data, dict) else {}
            batch = result.get("results", []) if isinstance(result, dict) else []
            if not batch:
                break
            rows.extend([r for r in batch if isinstance(r, dict)])
            total = int(result.get("count", 0))
            start += per_page
            if start >= min(total, limit):
                break
    return rows[:limit]


async def _harvest_worldbank(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    page = 1
    per_page = 1000
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(rows) < limit:
            params = {"format": "json", "per_page": per_page, "page": page}
            async with session.get(endpoint, params=params) as resp:
                if resp.status != 200:
                    break
                data = await resp.json(content_type=None)
            if not isinstance(data, list) or len(data) < 2:
                break
            batch = data[1] if isinstance(data[1], list) else []
            if not batch:
                break
            rows.extend([r for r in batch if isinstance(r, dict)])
            total = int(data[0].get("total", 0)) if isinstance(data[0], dict) else 0
            page += 1
            if len(rows) >= min(limit, total or limit):
                break
    return rows[:limit]


async def _harvest_ukons(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    per_page = 50
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(rows) < limit:
            params = {"offset": offset, "limit": per_page}
            async with session.get(endpoint, params=params) as resp:
                if resp.status != 200:
                    break
                data = await resp.json(content_type=None)
            items = data.get("items", []) if isinstance(data, dict) else []
            if not items:
                break
            rows.extend([r for r in items if isinstance(r, dict)])
            offset += per_page
    return rows[:limit]


async def _harvest_undata(spec: SourceSpec, timeout_s: int) -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(spec.endpoint, headers={"Accept": "text/json"}) as resp:
            if resp.status != 200:
                return []
            payload = await resp.json(content_type=None)

    refs = payload.get("references", {}) if isinstance(payload, dict) else {}
    rows: list[dict] = []
    if isinstance(refs, dict):
        for value in refs.values():
            if isinstance(value, dict):
                rows.append(value)
            elif isinstance(value, list):
                rows.extend([v for v in value if isinstance(v, dict)])

    allow = set(spec.agency_allowlist)
    exclude = set(spec.exclude_agencies)
    filtered: list[dict] = []
    for row in rows:
        agency = str(row.get("agencyID", ""))
        if allow and agency not in allow:
            continue
        if agency in exclude:
            continue
        filtered.append(row)
    return filtered


async def _harvest_sdmx_dataflows(spec: SourceSpec, timeout_s: int) -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(spec.endpoint, headers={"Accept": "application/xml"}) as resp:
            if resp.status != 200:
                return []
            content = await resp.read()

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    rows: list[dict] = []
    for elem in root.iter():
        tag = elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag
        if tag != "Dataflow":
            continue
        row = {
            "id": elem.attrib.get("id", ""),
            "agencyID": elem.attrib.get("agencyID", ""),
            "version": elem.attrib.get("version", ""),
            "name": "",
            "description": "",
        }
        for child in elem:
            ctag = child.tag.split("}", 1)[1] if "}" in child.tag else child.tag
            if ctag == "Name" and not row["name"]:
                row["name"] = (child.text or "").strip()
            elif ctag == "Description" and not row["description"]:
                row["description"] = (child.text or "").strip()

        agency = str(row.get("agencyID", ""))
        if spec.agency_prefix and not agency.startswith(spec.agency_prefix):
            continue
        rows.append(row)
    return rows


async def _harvest_who_indicators(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    next_url: str | None = endpoint
    timeout = aiohttp.ClientTimeout(total=timeout_s)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        while next_url and len(rows) < limit:
            async with session.get(next_url, headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    break
                payload = await resp.json(content_type=None)
            batch = payload.get("value", []) if isinstance(payload, dict) else []
            if not isinstance(batch, list) or not batch:
                break
            rows.extend([row for row in batch if isinstance(row, dict)])
            next_url = payload.get("@odata.nextLink") if isinstance(payload, dict) else None
    return rows[:limit]


async def _harvest_uis_indicators(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(endpoint, headers={"Accept": "application/json"}) as resp:
            if resp.status != 200:
                return []
            payload = await resp.json(content_type=None)

    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            rows = [row for row in payload["data"] if isinstance(row, dict)]
        elif isinstance(payload.get("items"), list):
            rows = [row for row in payload["items"] if isinstance(row, dict)]
        else:
            rows = [payload]
    else:
        rows = []
    return rows[:limit]


async def _harvest_wvs(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(endpoint, headers={"Accept": "application/json"}) as resp:
            if resp.status != 200:
                return []
            payload = await resp.json(content_type=None)

    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            rows = [row for row in payload["data"] if isinstance(row, dict)]
        elif isinstance(payload.get("items"), list):
            rows = [row for row in payload["items"] if isinstance(row, dict)]
        elif isinstance(payload.get("results"), list):
            rows = [row for row in payload["results"] if isinstance(row, dict)]
        else:
            rows = [payload]
    else:
        rows = []
    return rows[:limit]


async def _harvest_unpd_indicators(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    next_url: str | None = endpoint
    page = 1

    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(rows) < limit:
            if next_url:
                request_url = next_url
                params: dict[str, Any] | None = None
            else:
                request_url = endpoint
                params = {"page": page}
            async with session.get(request_url, params=params, headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    break
                payload = await resp.json(content_type=None)

            if not isinstance(payload, dict):
                break
            batch = payload.get("data", [])
            if not isinstance(batch, list) or not batch:
                break
            rows.extend([row for row in batch if isinstance(row, dict)])

            next_url = (
                payload.get("next")
                or payload.get("nextPage")
                or payload.get("next_page")
                or payload.get("nextPageUrl")
            )
            if not next_url:
                page += 1
            if len(batch) == 0:
                break

    return rows[:limit]
