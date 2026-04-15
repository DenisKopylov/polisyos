#!/usr/bin/env python3
"""Record API response fixtures for connector integration tests.

Usage::

    # List available source profiles
    python scripts/record_fixtures.py --list

    # Record a single fixture
    python scripts/record_fixtures.py --profile worldbank_wdi --dataset "NY.GDP.MKTP.CD"

    # Record all Wave-1 sources
    python scripts/record_fixtures.py --wave 1

    # Record all waves
    python scripts/record_fixtures.py --wave all
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tools._lib.imports import repo_root_from, ensure_repo_import_roots

sys.path.insert(0, str(repo_root_from(__file__)))

PRODUCT_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

FIXTURE_ROOT = PRODUCT_ROOT / "tests" / "fabric" / "connectors" / "sources" / "fixtures"

# Wave definitions: list of (profile_id, connector_id, dataset_id, description)
WAVE_1_TARGETS = [
    ("worldbank_wdi", "worldbank.wdi", "NY.GDP.MKTP.CD", "GDP current USD"),
    ("worldbank_wdi", "worldbank.wdi", "SP.POP.TOTL", "Total population"),
    ("eurostat_public", "eurostat.data", "nama_10_gdp", "GDP and main components"),
    ("ukons_public", "ukons.datasets", "cpih01", "CPIH index"),
    ("ecb_sdmx", "sdmx.source", "ECB.EXR", "Exchange rates"),
    ("oecd_sdmx", "sdmx.source", "OECD.QNA", "Quarterly national accounts"),
]

WAVE_2_TARGETS = [
    ("imf_sdmx", "sdmx.source", "IMF.IFS", "International Financial Statistics"),
    ("bis_sdmx", "sdmx.source", "BIS.CBS", "Consolidated banking statistics"),
    ("data_gov_uk", "ckan.catalog", "gdp", "UK GDP datasets catalog"),
    ("data_gov_us", "ckan.catalog", "population", "US population datasets catalog"),
]

WAVE_3_TARGETS = [
    ("nyc_opendata", "socrata.soda", "erm2-nwe9", "NYC 311 complaints"),
    ("opendatasoft_public", "opendatasoft.ods", "world-population", "World population"),
    ("wikidata_sparql", "sparql.endpoint", "countries", "Countries query"),
]

ALL_WAVES = {1: WAVE_1_TARGETS, 2: WAVE_2_TARGETS, 3: WAVE_3_TARGETS}


def _profile_to_headers(profile) -> dict[str, str]:
    """Extract headers from a SourceProfile."""
    return dict(profile.headers)


async def _record_http(url: str, headers: dict[str, str], timeout: float = 30.0) -> tuple[int, dict[str, str], bytes]:
    """Make a real HTTP GET request and return (status, headers, body)."""
    import aiohttp

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            body = await resp.read()
            resp_headers = {k: v for k, v in resp.headers.items()}
            return resp.status, resp_headers, body


def _save_raw_fixture(fixture_dir: Path, filename: str, body: bytes) -> Path:
    """Save raw JSON response body as a fixture file."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    path = fixture_dir / filename
    try:
        parsed = json.loads(body)
        path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    except (json.JSONDecodeError, UnicodeDecodeError):
        path.write_bytes(body)
    return path


def _save_simulator_fixture(
    fixture_dir: Path,
    filename: str,
    status: int,
    headers: dict[str, str],
    body: bytes,
    request_url: str,
    connector_id: str,
    dataset_id: str,
) -> Path:
    """Save in SimulatorFixture format (base64-encoded body)."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    path = fixture_dir / filename
    fixture_data = {
        "status_code": status,
        "headers": headers,
        "body": base64.b64encode(body).decode(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "request_url": request_url,
        "request_method": "GET",
        "request_hash": "",
        "connector_id": connector_id,
        "dataset_id": dataset_id,
    }
    path.write_text(json.dumps(fixture_data, indent=2), encoding="utf-8")
    return path


def _build_url(profile, dataset_id: str) -> str:
    """Build the request URL for a given profile and dataset."""
    family = profile.connector_family
    base = profile.base_url.rstrip("/")

    if family == "worldbank":
        return f"{base}/country/all/indicator/{dataset_id}?format=json&page=1&per_page=100"
    elif family == "eurostat":
        return f"{base}/{dataset_id}?format=JSON&lang=en"
    elif family == "ukons":
        return f"{base}/datasets/{dataset_id}"
    elif family == "sdmx":
        agency = dict(profile.headers).get("X-SDMX-AgencyID", "")
        return f"{base}/data/{dataset_id}?detail=dataonly&lastNObservations=10"
    elif family == "ckan":
        return f"{base}/api/3/action/package_search?q={dataset_id}&rows=5"
    elif family == "socrata":
        return f"{base}/resource/{dataset_id}.json?$limit=50"
    elif family == "opendatasoft":
        return f"{base}/api/explore/v2.1/catalog/datasets/{dataset_id}/records?limit=20"
    elif family == "sparql":
        query = "SELECT ?country ?countryLabel WHERE { ?country wdt:P31 wd:Q6256. SERVICE wikibase:label { bd:serviceParam wikibase:language 'en'. } } LIMIT 50"
        from urllib.parse import quote
        return f"{base}/sparql?query={quote(query)}&format=json"
    else:
        return base


async def record_single(
    profile_id: str,
    connector_id: str,
    dataset_id: str,
    description: str,
    *,
    verbose: bool = True,
) -> bool:
    """Record a single fixture. Returns True on success."""
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    registry = SourceProfileRegistry.get_instance()
    profile = registry.get(profile_id)
    if profile is None:
        print(f"  SKIP {profile_id}: profile not found")
        return False

    url = _build_url(profile, dataset_id)
    headers = _profile_to_headers(profile)

    # Use connector namespace as fixture directory
    namespace = profile.connector_family
    safe_dataset = dataset_id.replace("/", "_").replace(".", "_").lower()

    if verbose:
        print(f"  Recording {profile_id}/{dataset_id} ({description})...")
        print(f"    URL: {url[:100]}...")

    started = time.monotonic()
    try:
        status, resp_headers, body = await _record_http(url, headers)
    except Exception as exc:
        print(f"  FAIL {profile_id}/{dataset_id}: {type(exc).__name__}: {exc}")
        return False

    elapsed = time.monotonic() - started
    body_size = len(body)

    # Save raw fixture
    raw_dir = FIXTURE_ROOT / namespace
    raw_path = _save_raw_fixture(raw_dir, f"{safe_dataset}_response.json", body)

    # Save simulator fixture
    sim_dir = FIXTURE_ROOT / namespace / "simulator"
    sim_path = _save_simulator_fixture(
        sim_dir,
        f"{safe_dataset}.json",
        status,
        resp_headers,
        body,
        url,
        connector_id,
        dataset_id,
    )

    if verbose:
        status_icon = "OK" if 200 <= status < 300 else "WARN"
        print(f"    {status_icon} status={status} size={body_size:,}b time={elapsed:.1f}s")
        print(f"    Raw:  {raw_path.relative_to(FIXTURE_ROOT.parent.parent.parent.parent)}")
        print(f"    Sim:  {sim_path.relative_to(FIXTURE_ROOT.parent.parent.parent.parent)}")

    return 200 <= status < 300


async def record_wave(wave_num: int | str, *, verbose: bool = True) -> tuple[int, int]:
    """Record fixtures for a wave. Returns (success_count, total_count)."""
    if wave_num == "all":
        targets = []
        for w in sorted(ALL_WAVES.keys()):
            targets.extend(ALL_WAVES[w])
    else:
        targets = ALL_WAVES.get(int(wave_num), [])

    if not targets:
        print(f"No targets defined for wave {wave_num}")
        return 0, 0

    success = 0
    for profile_id, connector_id, dataset_id, desc in targets:
        ok = await record_single(profile_id, connector_id, dataset_id, desc, verbose=verbose)
        if ok:
            success += 1

    return success, len(targets)


def list_profiles() -> None:
    """Print all available source profiles."""
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    registry = SourceProfileRegistry.get_instance()
    print("Available source profiles:")
    for profile in registry.list_all():
        print(f"  {profile.profile_id:25s} [{profile.connector_family:12s}] {profile.base_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Record API fixtures for connector tests")
    parser.add_argument("--list", action="store_true", help="List available source profiles")
    parser.add_argument("--profile", type=str, help="Source profile ID")
    parser.add_argument("--dataset", type=str, help="Dataset ID to fetch")
    parser.add_argument("--wave", type=str, help="Wave number (1, 2, 3) or 'all'")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")

    args = parser.parse_args()

    if args.list:
        list_profiles()
        return

    if args.wave:
        success, total = asyncio.run(record_wave(args.wave, verbose=not args.quiet))
        print(f"\nRecorded {success}/{total} fixtures successfully.")
        sys.exit(0 if success == total else 1)

    if args.profile and args.dataset:
        ok = asyncio.run(
            record_single(args.profile, "unknown", args.dataset, "manual", verbose=not args.quiet)
        )
        sys.exit(0 if ok else 1)

    parser.print_help()


if __name__ == "__main__":
    main()
