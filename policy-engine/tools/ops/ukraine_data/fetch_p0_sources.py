#!/usr/bin/env python3
"""Fetch and record official P0 source inputs for the Ukraine build stack."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _today_utc() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def _iso_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _nbu_exchange_chunk_items() -> list[DownloadItem]:
    today = _today_utc()
    items: list[DownloadItem] = []
    for year in range(2015, today.year + 1):
        start = dt.date(year, 1, 1)
        if year == 2015:
            start = dt.date(2015, 9, 1)
        end = dt.date(year, 12, 31)
        if year == today.year:
            end = today
        items.append(
            DownloadItem(
                filename=f"nbu_exchange_{year}.json",
                url=(
                    "https://bank.gov.ua/NBU_Exchange/exchange_site"
                    f"?start={start.strftime('%Y%m%d')}&end={end.strftime('%Y%m%d')}&json"
                ),
            )
        )
    return items


def _curl_download(url: str, destination: Path) -> tuple[bool, str]:
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
        url,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return True, ""
    if destination.exists() and destination.stat().st_size == 0:
        destination.unlink()
    detail = (completed.stderr or completed.stdout or "").strip()
    return False, detail[-4000:]


@dataclass(frozen=True)
class DownloadItem:
    filename: str
    url: str
    required: bool = True
    note: str | None = None


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    title: str
    raw_subdir: str
    items: list[DownloadItem]
    notes: list[str] = field(default_factory=list)


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
        SourceSpec(
            source_id="edr_current",
            title="ЄДР current bulk dump",
            raw_subdir="edr_current",
            notes=[
                "Official data.gov.ua CKAN bulk resources.",
                "Includes legal entities, FOP, and public formations plus schema zips.",
            ],
            items=[
                DownloadItem(
                    "package_show.json",
                    "https://data.gov.ua/api/3/action/package_show?id=a1799820-195b-4982-8141-6e84f58103e7",
                ),
                DownloadItem(
                    "UO.zip",
                    "https://data.gov.ua/dataset/03cc1239-3988-4451-aa0d-aadb77448714/resource/d40cc921-39bb-44fd-be06-dc02589f45c6/download/uo.zip",
                ),
                DownloadItem(
                    "FOP.zip",
                    "https://data.gov.ua/dataset/03cc1239-3988-4451-aa0d-aadb77448714/resource/c262938f-cce7-4489-a805-2fd7c5a44e0b/download/fop.zip",
                ),
                DownloadItem(
                    "FSU.zip",
                    "https://data.gov.ua/dataset/03cc1239-3988-4451-aa0d-aadb77448714/resource/2b7eeee3-6c29-4ba8-8c35-1618974830eb/download/fsu.zip",
                ),
                DownloadItem(
                    "UO_schema.zip",
                    "https://data.gov.ua/dataset/03cc1239-3988-4451-aa0d-aadb77448714/resource/131e73ef-eeff-4374-aa23-0c7e10d6509c/download/uo_schema.zip",
                ),
                DownloadItem(
                    "FOP_schema.zip",
                    "https://data.gov.ua/dataset/03cc1239-3988-4451-aa0d-aadb77448714/resource/e8908334-5399-4f7c-94c2-9b50b4768e0b/download/fop_schema.zip",
                ),
                DownloadItem(
                    "FSU_schema.zip",
                    "https://data.gov.ua/dataset/03cc1239-3988-4451-aa0d-aadb77448714/resource/0b7f74a4-2a9d-462c-89c5-e6e8254dbd6d/download/fsu_schema.zip",
                ),
            ],
        ),
        SourceSpec(
            source_id="spending_full",
            title="Spending.gov.ua open data APIs",
            raw_subdir="spending_full",
            notes=[
                "Official data.gov.ua CKAN metadata plus live API snapshots.",
                "This fetcher validates access and stores seed raw inputs; full horizon extraction remains a follow-on job.",
            ],
            items=[
                DownloadItem(
                    "package_show.json",
                    "https://data.gov.ua/api/3/action/package_show?id=bff70377-03d0-499e-b703-e37ce25e7e46",
                ),
                DownloadItem(
                    "reports_periods.json",
                    "https://api.spending.gov.ua/api/v2/api/reports/asynch/periods",
                ),
                DownloadItem(
                    "transactions_sample_2023-12-10.json",
                    "https://api.spending.gov.ua/api/v2/api/transactions/?startdate=2023-12-10&enddate=2023-12-10",
                    note="Seed access check for the financial transactions endpoint.",
                ),
                DownloadItem(
                    "contracts_endpoint_seed.json",
                    "https://api.spending.gov.ua/api/v2/disposers/contracts",
                    note="Seed access check for contracts / acts / penalties endpoint.",
                ),
            ],
        ),
        SourceSpec(
            source_id="prozorro_full",
            title="Prozorro public feed seeds",
            raw_subdir="prozorro_full",
            notes=[
                "Official OpenProcurement public API feed seed pages.",
                "Full horizon contract extraction still requires a dedicated cursor/detail crawler.",
            ],
            items=[
                DownloadItem(
                    "tenders_seed_page.json",
                    "https://public.api.openprocurement.org/api/2.5/tenders?limit=100",
                ),
                DownloadItem(
                    "contracts_seed_page.json",
                    "https://public.api.openprocurement.org/api/2.5/contracts?limit=100",
                ),
            ],
        ),
        SourceSpec(
            source_id="macro_nbu_derzhstat",
            title="NBU + Derzhstat macro seeds",
            raw_subdir="macro_nbu_derzhstat",
            notes=[
                "Official NBU historical exchange range plus Derzhstat CPI and national accounts JSON exports.",
                "These are seed macro inputs, not yet the final normalized monthly macro panel.",
            ],
            items=[
                *_nbu_exchange_chunk_items(),
                DownloadItem(
                    "derzhstat_cpi_package_show.json",
                    "https://data.gov.ua/api/3/action/package_show?id=12f4fe34-0759-4271-b1f6-780995f0ec4a",
                ),
                DownloadItem(
                    "derzhstat_cpi_latest.json",
                    "https://data.gov.ua/dataset/12f4fe34-0759-4271-b1f6-780995f0ec4a/resource/9d4280b1-20ce-4aae-a005-24e4b9b7e32c/download/dataset_df_price_change_consumer_goods_service.json",
                ),
                DownloadItem(
                    "derzhstat_quarterly_national_accounts_package_show.json",
                    "https://data.gov.ua/api/3/action/package_show?id=219bbab5-c95a-4aaa-aa3e-b1d477ad8d58",
                ),
                DownloadItem(
                    "derzhstat_quarterly_national_accounts_latest.json",
                    "https://data.gov.ua/dataset/219bbab5-c95a-4aaa-aa3e-b1d477ad8d58/resource/dfa668c3-518f-4cab-bcc5-68395c7d22ef/download/dataset_df_quarterly_national_accounts_latest.json",
                ),
                DownloadItem(
                    "derzhstat_annual_national_accounts_package_show.json",
                    "https://data.gov.ua/api/3/action/package_show?id=762ef585-7e08-4b67-a267-8cef61812947",
                ),
                DownloadItem(
                    "derzhstat_annual_national_accounts_latest.json",
                    "https://data.gov.ua/dataset/762ef585-7e08-4b67-a267-8cef61812947/resource/5c2833b8-80c9-459e-9618-79c69ce086e5/download/dataset_default_integration_sssu_df_annual_national_accounts_latest.json",
                ),
            ],
        ),
        SourceSpec(
            source_id="dps_financials",
            title="Firm fundamentals provisional substitute",
            raw_subdir="dps_financials",
            notes=[
                "Official DPS bulk financial statements were not located from public endpoints during this pass.",
                "This directory stores an official Derzhstat annual financial-statements dataset as a provisional substitute candidate only.",
            ],
            items=[
                DownloadItem(
                    "package_show_derzhstat_financial_statements.json",
                    "https://data.gov.ua/api/3/action/package_show?id=7436ae83-dfc1-4836-9962-8af3e831c522",
                    note="Official Derzhstat annual financial statements dataset metadata.",
                ),
                DownloadItem(
                    "f_i_ric_2022.zip",
                    "https://data.gov.ua/dataset/6456ef0c-985c-4bb7-bf9d-16831161b416/resource/1e93dd50-f137-43f1-a165-6d7fd8f2c329/download/f-i_ric_2022.zip",
                    note="Provisional substitute, not DPS-native.",
                ),
                DownloadItem(
                    "f_ii_ric_2022.zip",
                    "https://data.gov.ua/dataset/6456ef0c-985c-4bb7-bf9d-16831161b416/resource/4cee01d7-a483-4b28-88fb-4dfe770afe2c/download/f-ii_ric_2022.zip",
                    note="Provisional substitute, not DPS-native.",
                ),
                DownloadItem(
                    "f_i_m_ii_m_ric_2022.zip",
                    "https://data.gov.ua/dataset/6456ef0c-985c-4bb7-bf9d-16831161b416/resource/70d2d63c-a3c0-4818-bb7f-f6ab5854c7b0/download/f-i-m-ii-m_ric_2022.zip",
                    note="Provisional substitute, not DPS-native.",
                ),
                DownloadItem(
                    "f_i_ms_ii_ms_ric_2022.zip",
                    "https://data.gov.ua/dataset/6456ef0c-985c-4bb7-bf9d-16831161b416/resource/4d214aeb-b9ae-4d80-a220-3b585bf1e90c/download/f-i-ms-ii-ms_ric_2022.zip",
                    note="Provisional substitute, not DPS-native.",
                ),
            ],
        ),
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Ukraine data storage root on the target server.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Do not re-download files that already exist and are non-empty.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = args.root
    raw_root = root / "raw"
    manifest_dir = root / "manifests"
    log_dir = root / "logs"
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "created_at": _iso_now(),
        "root": str(root),
        "sources": [],
    }
    overall_failed = False

    for spec in _build_specs():
        source_dir = raw_root / spec.raw_subdir
        source_dir.mkdir(parents=True, exist_ok=True)
        results: list[DownloadResult] = []
        for item in spec.items:
            destination = source_dir / item.filename
            if args.skip_existing and destination.exists() and destination.stat().st_size > 0:
                results.append(
                    DownloadResult(
                        filename=item.filename,
                        url=item.url,
                        destination=str(destination),
                        required=item.required,
                        status="skipped_existing",
                        size_bytes=destination.stat().st_size,
                        note=item.note,
                    )
                )
                continue
            ok, error = _curl_download(item.url, destination)
            status = "downloaded" if ok else ("failed" if item.required else "optional_failed")
            if not ok and item.required:
                overall_failed = True
            results.append(
                DownloadResult(
                    filename=item.filename,
                    url=item.url,
                    destination=str(destination),
                    required=item.required,
                    status=status,
                    size_bytes=destination.stat().st_size if destination.exists() else None,
                    error=error or None,
                    note=item.note,
                )
            )
        manifest["sources"].append(
            {
                "source_id": spec.source_id,
                "title": spec.title,
                "raw_dir": str(source_dir),
                "notes": spec.notes,
                "results": [asdict(result) for result in results],
            }
        )

    manifest["status"] = "completed" if not overall_failed else "completed_with_failures"
    manifest["finished_at"] = _iso_now()
    path = manifest_dir / "p0_source_acquisition_manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
    )
    sys.stdout.write(json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True))
    sys.stdout.write("\n")
    return 0 if not overall_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
