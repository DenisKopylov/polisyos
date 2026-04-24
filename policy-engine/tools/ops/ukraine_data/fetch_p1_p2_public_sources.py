#!/usr/bin/env python3
"""Fetch and record public D1/D3 raw source inputs for the Ukraine build stack."""

from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def _iso_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    return slug.strip("._-") or "resource"


def _filename_suffix(url: str) -> str:
    path = urlparse(url).path
    suffixes = Path(path).suffixes
    if suffixes:
        return "".join(suffixes[-2:]) if len(suffixes) > 1 else suffixes[0]
    return ""


def _curl_download(url: str, destination: Path, limit_rate: str | None) -> tuple[bool, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "curl",
        "--fail",
        "--location",
        "--retry",
        "5",
        "--retry-all-errors",
        "--continue-at",
        "-",
        "--output",
        str(destination),
    ]
    if limit_rate:
        command.extend(["--limit-rate", limit_rate])
    command.append(url)
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode == 0:
        return True, ""
    if destination.exists() and destination.stat().st_size == 0:
        destination.unlink()
    detail = (completed.stderr or completed.stdout or "").strip()
    return False, detail[-4000:]


def _fetch_json(url: str, *, attempts: int = 6, sleep_seconds: float = 2.0) -> dict[str, object]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(url, headers={"User-Agent": "policy-engine/ukraine-data-fetcher"})
            with urlopen(request, timeout=60) as response:  # nosec: trusted public endpoint
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - depends on remote endpoint
            last_error = exc
            retriable = False
            if (
                isinstance(exc, http.client.HTTPException)
                or getattr(exc, "code", None) in {429, 500, 502, 503, 504}
                or isinstance(exc, OSError)
            ):
                retriable = True
            if attempt == attempts or not retriable:
                raise
            time.sleep(sleep_seconds * attempt)
    assert last_error is not None
    raise last_error


def _parse_timestamp(value: str | None) -> tuple[int, str]:
    if not value:
        return (0, "")
    candidate = value.replace("Z", "+00:00")
    try:
        return (1, dt.datetime.fromisoformat(candidate).isoformat())
    except ValueError:
        return (1, value)


@dataclass(frozen=True)
class DirectDownloadItem:
    filename: str
    url: str
    note: str | None = None


@dataclass(frozen=True)
class CkanDatasetSpec:
    source_id: str
    title: str
    raw_subdir: str
    package_id: str
    notes: list[str] = field(default_factory=list)
    required: bool = True


@dataclass(frozen=True)
class DirectSourceSpec:
    source_id: str
    title: str
    raw_subdir: str
    items: list[DirectDownloadItem]
    notes: list[str] = field(default_factory=list)
    required: bool = True


@dataclass(frozen=True)
class BlockedSourceSpec:
    source_id: str
    title: str
    reason: str
    notes: list[str] = field(default_factory=list)
    required: bool = True


SourceSpec = CkanDatasetSpec | DirectSourceSpec | BlockedSourceSpec


@dataclass
class DownloadResult:
    filename: str
    url: str
    destination: str
    required: bool
    status: str
    size_bytes: int | None = None
    error: str | None = None
    note: str | None = None


def _build_specs() -> list[SourceSpec]:
    return [
        BlockedSourceSpec(
            source_id="dps_tax_risk_layer",
            title="DPS tax / risk layer",
            reason="partial_public_proxy_only",
            notes=[
                "A full public bulk DPS tax/risk layer was not identified from open endpoints during this pass.",
                "Public proxy layers are fetched separately below; the full risk layer still likely needs credentialed access or another acquisition path.",
            ],
        ),
        CkanDatasetSpec(
            source_id="dps_tax_debt_registry_public",
            title="DPS tax-debt registry public proxy",
            raw_subdir="dps_tax_debt_registry_public",
            package_id="0e347d45-4db5-44ee-a14a-533d7cf17d7b",
            notes=[
                "Official public DPS tax-debt registry as the accessible slice of the broader tax/risk family.",
            ],
        ),
        CkanDatasetSpec(
            source_id="customs_trade_public_aggregates",
            title="Customs trade public aggregates",
            raw_subdir="customs_trade_public_aggregates",
            package_id="scsu-bi-trade-src",
            notes=[
                "Official State Customs Service aggregated trade statistics dataset.",
                "Chosen instead of declaration-level export/import records to keep the parallel fetch safe and compact.",
            ],
        ),
        CkanDatasetSpec(
            source_id="customs_commercial_vehicles",
            title="Customs commercial vehicles",
            raw_subdir="customs_commercial_vehicles",
            package_id="scsu-number-of-foreign-vehicles",
            notes=[
                "Official State Customs Service counts of foreign commercial vehicles entering Ukraine.",
            ],
        ),
        CkanDatasetSpec(
            source_id="employment_service_unemployment_benefits",
            title="Employment service unemployment-benefit panel",
            raw_subdir="employment_service_unemployment_benefits",
            package_id="ceb9a872-95a0-4be1-906e-2509cc02a7a6",
            notes=[
                "Official State Employment Service dataset on registered unemployed who received benefits.",
            ],
        ),
        CkanDatasetSpec(
            source_id="license_transport_registry",
            title="Transport license registry",
            raw_subdir="license_transport_registry",
            package_id="9b29b699-a1cc-462e-bb20-5998607c182f",
            notes=[
                "Official transport licensing registry for passenger and hazardous-goods transport.",
            ],
        ),
        CkanDatasetSpec(
            source_id="license_nkrekp_registry",
            title="NКРЕКП license registry",
            raw_subdir="license_nkrekp_registry",
            package_id="4725d7d2-95aa-4239-a832-7f1d484c4120",
            notes=[
                "Official NКРЕКП licensing registry for regulated utilities / energy activity.",
            ],
        ),
        CkanDatasetSpec(
            source_id="budget_managers_recipients_registry",
            title="Budget managers / recipients registry",
            raw_subdir="budget_managers_recipients_registry",
            package_id="8df43bdf-4417-42b4-bc50-bd296af4058e",
            notes=[
                "Official Treasury registry of budget managers and recipients.",
            ],
        ),
        CkanDatasetSpec(
            source_id="nszu_payments",
            title="NSZU payments",
            raw_subdir="nszu_payments",
            package_id="25a46db9-2f15-4302-9b59-9bd761c80f46",
            notes=[
                "Official NSZU payments under the Program of Medical Guarantees and related funding programs.",
            ],
        ),
        CkanDatasetSpec(
            source_id="nszu_contracts",
            title="NSZU contracts",
            raw_subdir="nszu_contracts",
            package_id="6da6e500-e3c0-4a6a-9cb1-764582b531ee",
            notes=[
                "Official NSZU dataset for active service contracts by medical-service group.",
            ],
        ),
        CkanDatasetSpec(
            source_id="nszu_providers",
            title="NSZU providers",
            raw_subdir="nszu_providers",
            package_id="a1d554df-be4b-4d3f-8063-dd0db4d83ff5",
            notes=[
                "Official NSZU provider registry for entities contracted under the Program of Medical Guarantees.",
            ],
        ),
        CkanDatasetSpec(
            source_id="education_entity_registry",
            title="Education entity registry",
            raw_subdir="education_entity_registry",
            package_id="8781dd10-5504-4157-a79a-aaa99861cec9",
            notes=[
                "Official registry of education entities in ЄДЕБО.",
            ],
        ),
        CkanDatasetSpec(
            source_id="education_admissions_and_graduations",
            title="Education admissions and graduations",
            raw_subdir="education_admissions_and_graduations",
            package_id="8f7d7ba2-1d1f-4de8-a105-660fb5ebb01a",
            notes=[
                "Official higher-education admissions / graduations dataset from ЄДЕБО.",
            ],
        ),
        CkanDatasetSpec(
            source_id="education_documents_registry",
            title="Education documents registry",
            raw_subdir="education_documents_registry",
            package_id="96c889b6-5426-4d92-90ae-6732ecf990d6",
            notes=[
                "Official anonymized education-documents registry from ЄДЕБО.",
            ],
        ),
        CkanDatasetSpec(
            source_id="construction_declarative_documents",
            title="Construction declarative documents",
            raw_subdir="construction_declarative_documents",
            package_id="0c352c5f-786b-4407-9c3d-49cddd63452e",
            notes=[
                "Official declarative construction documents from the construction activity register.",
            ],
        ),
        CkanDatasetSpec(
            source_id="road_spatial_coordinates",
            title="Road spatial coordinates",
            raw_subdir="road_spatial_coordinates",
            package_id="ff3aee7b-159f-43d1-8e4b-241a81be3e09",
            notes=[
                "Official spatial coordinates of public roads of state significance.",
            ],
        ),
        CkanDatasetSpec(
            source_id="road_technical_state",
            title="Road technical state",
            raw_subdir="road_technical_state",
            package_id="72dc7da4-a015-4117-9614-d72ba2c3a6a9",
            notes=[
                "Official technical / operational condition of public roads of state significance.",
            ],
        ),
        DirectSourceSpec(
            source_id="osm_exact_ukraine",
            title="OSM exact Ukraine extract",
            raw_subdir="osm_exact_ukraine",
            notes=[
                "Standard Geofabrik OSM extract for Ukraine.",
                "Non-government source, but the canonical practical raw layer for exact road / geo enrichment.",
            ],
            items=[
                DirectDownloadItem(
                    filename="ukraine-latest.osm.pbf",
                    url="https://download.geofabrik.de/europe/ukraine-latest.osm.pbf",
                ),
                DirectDownloadItem(
                    filename="ukraine.html",
                    url="https://download.geofabrik.de/europe/ukraine.html",
                    note="Human-readable metadata page for the current extract.",
                ),
            ],
        ),
        CkanDatasetSpec(
            source_id="worldpop_population_baseline",
            title="WorldPop Ukraine population baseline",
            raw_subdir="worldpop_population_baseline",
            package_id="worldpop_proxy_metadata",
            required=False,
            notes=[
                "Public WorldPop Ukraine country rasters for 2000-2020.",
                "Resolved from the WorldPop API and fetched as direct GeoTIFF files.",
            ],
        ),
        BlockedSourceSpec(
            source_id="spatial_cell_exogenous_viirs",
            title="VIIRS nighttime lights baseline",
            reason="blocked_large_manual_source",
            notes=[
                "A clean public Ukraine-scoped VIIRS raw download path was not resolved in this pass.",
            ],
        ),
        BlockedSourceSpec(
            source_id="spatial_cell_exogenous_era5",
            title="ERA5 baseline",
            reason="blocked_auth_required",
            notes=[
                "ERA5 bulk acquisition typically requires CDS credentials and a bounded request plan.",
            ],
        ),
        CkanDatasetSpec(
            source_id="household_survey_quarterly_targets_public",
            title="Household survey quarterly public targets",
            raw_subdir="household_survey_quarterly_targets_public",
            package_id="2e31f7a3-b86e-46c4-a2e0-d2bae9a85047",
            notes=[
                "Official quarterly household living-conditions survey outputs as a public proxy for household targets.",
            ],
        ),
        CkanDatasetSpec(
            source_id="household_survey_annual_targets_public",
            title="Household survey annual public targets",
            raw_subdir="household_survey_annual_targets_public",
            package_id="94723478-1eea-4b8c-a409-b7d4fc19bb28",
            notes=[
                "Official annual household living-conditions survey outputs as a public proxy for household targets.",
            ],
        ),
        BlockedSourceSpec(
            source_id="household_microdata_2018",
            title="Household microdata 2018",
            reason="blocked_restricted_microdata",
            notes=[
                "Household microdata are not openly downloadable from the public endpoints used in this pass.",
                "Public household survey targets are fetched separately as proxies.",
            ],
        ),
        CkanDatasetSpec(
            source_id="labor_force_quarterly_targets_public",
            title="Labor-force quarterly public targets",
            raw_subdir="labor_force_quarterly_targets_public",
            package_id="a0f9d88d-4289-436c-8371-6aead27fd3cb",
            notes=[
                "Official quarterly labor-force survey outputs as a public proxy for labor-force targets.",
            ],
        ),
        BlockedSourceSpec(
            source_id="labor_force_microdata_2018_2021",
            title="Labor-force microdata 2018-2021",
            reason="blocked_restricted_microdata",
            notes=[
                "Labor-force microdata are not openly downloadable from the public endpoints used in this pass.",
                "Public labor-force survey targets are fetched separately as proxies.",
            ],
        ),
        CkanDatasetSpec(
            source_id="pfu_debt_registry",
            title="PFU debt registry",
            raw_subdir="pfu_debt_registry",
            package_id="48068edb-ab53-4d90-8ed9-027f46f6355e",
            notes=[
                "Official Pension Fund debtors dataset.",
            ],
        ),
        CkanDatasetSpec(
            source_id="wage_arrears_registry",
            title="Wage arrears registry",
            raw_subdir="wage_arrears_registry",
            package_id="20b9c337-8c46-4461-b005-7e73592e7e49",
            notes=[
                "Official wage arrears registry.",
            ],
        ),
        CkanDatasetSpec(
            source_id="debtor_register",
            title="Unified debtor register",
            raw_subdir="debtor_register",
            package_id="506734bf-2480-448c-a2b4-90b6d06df11e",
            notes=[
                "Official unified debtor register.",
            ],
        ),
        CkanDatasetSpec(
            source_id="bankruptcy_notices",
            title="Bankruptcy notices",
            raw_subdir="bankruptcy_notices",
            package_id="544d4dad-0b6d-4972-b0b8-fb266829770f",
            notes=[
                "Official bankruptcy notices dataset.",
            ],
        ),
        CkanDatasetSpec(
            source_id="border_crossing_points_public",
            title="Border crossing points public proxy",
            raw_subdir="border_crossing_points_public",
            package_id="d3e67d5f-f9b9-426f-8140-718a68d88791",
            required=False,
            notes=[
                "Official public list of active border crossing and control points as a logistics / mobility proxy.",
            ],
        ),
        BlockedSourceSpec(
            source_id="logistics_mobility_displacement",
            title="Logistics / mobility / displacement layers",
            reason="partial_public_proxy_only",
            notes=[
                "Only the public border-crossing-points proxy is fetched automatically in this pass.",
            ],
            required=False,
        ),
        CkanDatasetSpec(
            source_id="land_cadastre_public_proxy",
            title="Land cadastre public proxy",
            raw_subdir="land_cadastre_public_proxy",
            package_id="280458f8-a6e5-4fc1-95ab-c8faf1841577",
            required=False,
            notes=[
                "Public cadastral/open-land layer fetched as an exploratory land-use proxy.",
            ],
        ),
        BlockedSourceSpec(
            source_id="land_cadastre_baseline",
            title="Land cadastre baseline",
            reason="partial_public_proxy_only",
            notes=[
                "Only the public cadastre proxy layer is fetched automatically in this pass.",
            ],
            required=False,
        ),
    ]


def _download_direct_source(
    spec: DirectSourceSpec,
    source_dir: Path,
    skip_existing: bool,
    limit_rate: str | None,
    sleep_seconds: float,
) -> tuple[list[DownloadResult], bool]:
    results: list[DownloadResult] = []
    failed_required = False
    for item in spec.items:
        destination = source_dir / item.filename
        if skip_existing and destination.exists() and destination.stat().st_size > 0:
            results.append(
                DownloadResult(
                    filename=item.filename,
                    url=item.url,
                    destination=str(destination),
                    required=spec.required,
                    status="skipped_existing",
                    size_bytes=destination.stat().st_size,
                    note=item.note,
                )
            )
            continue
        ok, error = _curl_download(item.url, destination, limit_rate=limit_rate)
        status = "downloaded" if ok else ("failed" if spec.required else "optional_failed")
        if not ok and spec.required:
            failed_required = True
        results.append(
            DownloadResult(
                filename=item.filename,
                url=item.url,
                destination=str(destination),
                required=spec.required,
                status=status,
                size_bytes=destination.stat().st_size if destination.exists() else None,
                error=error or None,
                note=item.note,
            )
        )
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return results, failed_required


def _resource_filename(index: int, resource: dict[str, object]) -> str:
    name = _slugify(str(resource.get("name") or resource.get("id") or f"resource_{index:03d}"))
    url = str(resource.get("url") or "")
    suffix = _filename_suffix(url)
    if suffix and not name.endswith(suffix):
        return f"{index:03d}_{name}{suffix}"
    return f"{index:03d}_{name}"


def _download_ckan_source(
    spec: CkanDatasetSpec,
    source_dir: Path,
    skip_existing: bool,
    limit_rate: str | None,
    sleep_seconds: float,
) -> tuple[list[DownloadResult], bool, list[str]]:
    results: list[DownloadResult] = []
    warnings: list[str] = []
    failed_required = False

    if spec.package_id == "worldpop_proxy_metadata":
        metadata_url = "https://hub.worldpop.org/rest/data/pop/wpgp?iso3=UKR"
        metadata_path = source_dir / "package_show.json"
        try:
            metadata_payload = _fetch_json(metadata_url)
            metadata_path.write_text(
                json.dumps(metadata_payload, ensure_ascii=True, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            results.append(
                DownloadResult(
                    filename="package_show.json",
                    url=metadata_url,
                    destination=str(metadata_path),
                    required=spec.required,
                    status="downloaded" if metadata_path.stat().st_size > 0 else "failed",
                    size_bytes=metadata_path.stat().st_size if metadata_path.exists() else None,
                    note="WorldPop API metadata for Ukraine.",
                )
            )
            items = metadata_payload.get("data")
            if not isinstance(items, list):
                warnings.append("WorldPop API returned no data list")
                return results, failed_required, warnings
            selected = [item for item in items if isinstance(item, dict)]
            for index, item in enumerate(selected, start=1):
                data_file = item.get("data_file")
                if not data_file:
                    continue
                popyear = str(item.get("popyear") or f"{index:04d}")
                url = f"https://data.worldpop.org/{data_file}"
                filename = f"{popyear}_{Path(str(data_file)).name}"
                destination = source_dir / filename
                note = "WorldPop Ukraine population raster."
                if skip_existing and destination.exists() and destination.stat().st_size > 0:
                    results.append(
                        DownloadResult(
                            filename=filename,
                            url=url,
                            destination=str(destination),
                            required=spec.required,
                            status="skipped_existing",
                            size_bytes=destination.stat().st_size,
                            note=note,
                        )
                    )
                    continue
                ok, error = _curl_download(url, destination, limit_rate=limit_rate)
                status = "downloaded" if ok else ("failed" if spec.required else "optional_failed")
                if not ok and spec.required:
                    failed_required = True
                results.append(
                    DownloadResult(
                        filename=filename,
                        url=url,
                        destination=str(destination),
                        required=spec.required,
                        status=status,
                        size_bytes=destination.stat().st_size if destination.exists() else None,
                        error=error or None,
                        note=note,
                    )
                )
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
            return results, failed_required, warnings
        except Exception as exc:  # pragma: no cover - depends on remote endpoint
            if spec.required:
                failed_required = True
            results.append(
                DownloadResult(
                    filename="package_show.json",
                    url=metadata_url,
                    destination=str(metadata_path),
                    required=spec.required,
                    status="failed" if spec.required else "optional_failed",
                    error=str(exc),
                    note="WorldPop API metadata for Ukraine.",
                )
            )
            return results, failed_required, warnings

    metadata_url = f"https://data.gov.ua/api/3/action/package_show?id={spec.package_id}"
    metadata_path = source_dir / "package_show.json"
    if skip_existing and metadata_path.exists() and metadata_path.stat().st_size > 0:
        metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        results.append(
            DownloadResult(
                filename="package_show.json",
                url=metadata_url,
                destination=str(metadata_path),
                required=spec.required,
                status="skipped_existing",
                size_bytes=metadata_path.stat().st_size,
                note="CKAN package metadata.",
            )
        )
    else:
        try:
            metadata_payload = _fetch_json(metadata_url)
            metadata_path.write_text(
                json.dumps(metadata_payload, ensure_ascii=True, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            results.append(
                DownloadResult(
                    filename="package_show.json",
                    url=metadata_url,
                    destination=str(metadata_path),
                    required=spec.required,
                    status="downloaded",
                    size_bytes=metadata_path.stat().st_size,
                    note="CKAN package metadata.",
                )
            )
        except Exception as exc:  # pragma: no cover - depends on remote endpoint
            if spec.required:
                failed_required = True
            results.append(
                DownloadResult(
                    filename="package_show.json",
                    url=metadata_url,
                    destination=str(metadata_path),
                    required=spec.required,
                    status="failed" if spec.required else "optional_failed",
                    error=str(exc),
                    note="CKAN package metadata.",
                )
            )
            return results, failed_required, warnings

    payload = metadata_payload.get("result")
    if not isinstance(payload, dict):
        if spec.required:
            failed_required = True
        results.append(
            DownloadResult(
                filename="resources",
                url=metadata_url,
                destination=str(source_dir),
                required=spec.required,
                status="failed" if spec.required else "optional_failed",
                error="package_show missing result payload",
            )
        )
        return results, failed_required, warnings

    resources = payload.get("resources")
    if not isinstance(resources, list):
        warnings.append("package_show returned no resources list")
        return results, failed_required, warnings

    indexed_resources: list[tuple[int, dict[str, object]]] = []
    for index, resource in enumerate(resources, start=1):
        if not isinstance(resource, dict):
            continue
        indexed_resources.append((index, resource))

    indexed_resources.sort(
        key=lambda pair: (
            _parse_timestamp(
                str(
                    pair[1].get("last_modified")
                    or pair[1].get("metadata_modified")
                    or pair[1].get("created")
                )
            ),
            pair[0],
        )
    )

    for index, resource in indexed_resources:
        url = str(resource.get("url") or "")
        if not url:
            warnings.append(f"resource {resource.get('id') or index} missing url")
            continue
        filename = _resource_filename(index, resource)
        destination = source_dir / filename
        note = f"format={resource.get('format') or 'unknown'}"
        if skip_existing and destination.exists() and destination.stat().st_size > 0:
            results.append(
                DownloadResult(
                    filename=filename,
                    url=url,
                    destination=str(destination),
                    required=spec.required,
                    status="skipped_existing",
                    size_bytes=destination.stat().st_size,
                    note=note,
                )
            )
            continue
        ok, error = _curl_download(url, destination, limit_rate=limit_rate)
        status = "downloaded" if ok else ("failed" if spec.required else "optional_failed")
        if not ok and spec.required:
            failed_required = True
        results.append(
            DownloadResult(
                filename=filename,
                url=url,
                destination=str(destination),
                required=spec.required,
                status=status,
                size_bytes=destination.stat().st_size if destination.exists() else None,
                error=error or None,
                note=note,
            )
        )
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return results, failed_required, warnings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Ukraine data storage root.")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Do not re-download files that already exist and are non-empty.",
    )
    parser.add_argument(
        "--limit-rate",
        default="8M",
        help="Optional curl rate limit passed to --limit-rate. Use 0 or empty to disable.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.2,
        help="Sleep interval between resource downloads to keep the fetch gentle.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = args.root
    raw_root = root / "raw"
    manifest_dir = root / "manifests"
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    limit_rate = None if args.limit_rate in {"", "0", "off", "none"} else args.limit_rate

    manifest: dict[str, object] = {
        "created_at": _iso_now(),
        "root": str(root),
        "sources": [],
    }
    overall_failed = False

    for spec in _build_specs():
        if isinstance(spec, BlockedSourceSpec):
            manifest["sources"].append(
                {
                    "source_id": spec.source_id,
                    "title": spec.title,
                    "status": spec.reason,
                    "required": spec.required,
                    "notes": spec.notes,
                    "results": [],
                }
            )
            continue

        source_dir = raw_root / spec.raw_subdir
        source_dir.mkdir(parents=True, exist_ok=True)
        if isinstance(spec, DirectSourceSpec):
            results, failed_required = _download_direct_source(
                spec=spec,
                source_dir=source_dir,
                skip_existing=args.skip_existing,
                limit_rate=limit_rate,
                sleep_seconds=args.sleep_seconds,
            )
            warnings: list[str] = []
        else:
            results, failed_required, warnings = _download_ckan_source(
                spec=spec,
                source_dir=source_dir,
                skip_existing=args.skip_existing,
                limit_rate=limit_rate,
                sleep_seconds=args.sleep_seconds,
            )
        if failed_required:
            overall_failed = True
        manifest["sources"].append(
            {
                "source_id": spec.source_id,
                "title": spec.title,
                "raw_dir": str(source_dir),
                "required": spec.required,
                "notes": spec.notes,
                "warnings": warnings,
                "results": [asdict(result) for result in results],
            }
        )

    manifest["status"] = "completed" if not overall_failed else "completed_with_failures"
    manifest["finished_at"] = _iso_now()
    path = manifest_dir / "p1_p2_public_source_acquisition_manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
    )
    sys.stdout.write(json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0 if not overall_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
