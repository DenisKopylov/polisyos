#!/usr/bin/env python3
"""Resumable server-side harvest of detailed Prozorro contract records."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
import urllib.request
from pathlib import Path


def _fetch_json(url: str) -> dict[str, object]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "policy-engine/ukraine-data-harvester"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Ukraine data storage root.")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=500,
        help="Maximum feed pages to hydrate in this run. Use 0 or a negative value for no page cap.",
    )
    parser.add_argument("--sleep-seconds", type=float, default=0.1)
    parser.add_argument("--detail-sleep-seconds", type=float, default=0.02)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    feed_root = args.root / "raw" / "prozorro_full" / "contracts_feed"
    details_root = args.root / "raw" / "prozorro_full" / "contracts_details"
    state_path = args.root / "manifests" / "prozorro_contract_details_state.json"
    details_root.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    state: dict[str, object] = {
        "started_at": dt.datetime.now(dt.UTC).isoformat(),
        "completed_pages": 0,
        "completed_contracts": 0,
        "failures": [],
        "status": "running",
    }
    if state_path.exists():
        state.update(json.loads(state_path.read_text(encoding="utf-8")))

    completed_pages = int(state.get("completed_pages", 0))
    completed_contracts = int(state.get("completed_contracts", 0))
    page_budget = args.max_pages if args.max_pages > 0 else None
    pages_processed = 0

    feed_pages = sorted(feed_root.glob("page_*.json"))
    for feed_page in feed_pages[completed_pages:]:
        if page_budget is not None and pages_processed >= page_budget:
            break
        page_no = int(feed_page.stem.split("_")[-1])
        detail_page = details_root / feed_page.name
        if detail_page.exists():
            completed_pages = page_no
            state["completed_pages"] = completed_pages
            state["last_updated_at"] = dt.datetime.now(dt.UTC).isoformat()
            state_path.write_text(
                json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
            )
            pages_processed += 1
            continue

        payload = json.loads(feed_page.read_text(encoding="utf-8"))
        contracts = payload.get("data", [])
        if not isinstance(contracts, list):
            contracts = []
        hydrated_contracts: list[dict[str, object]] = []
        for contract_stub in contracts:
            if not isinstance(contract_stub, dict):
                continue
            contract_id = str(contract_stub.get("id") or "").strip()
            if not contract_id:
                continue
            url = f"https://public.api.openprocurement.org/api/2.5/contracts/{contract_id}"
            try:
                contract_payload = _fetch_json(url)
            except Exception as exc:
                state["failures"].append(
                    {
                        "page_no": page_no,
                        "contract_id": contract_id,
                        "error": str(exc),
                        "at": dt.datetime.now(dt.UTC).isoformat(),
                    }
                )
                state["status"] = "paused_on_error"
                state["last_updated_at"] = dt.datetime.now(dt.UTC).isoformat()
                state_path.write_text(
                    json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
                )
                return 1
            data = contract_payload.get("data")
            if isinstance(data, dict):
                hydrated_contracts.append(data)
                completed_contracts += 1
            if args.detail_sleep_seconds > 0:
                time.sleep(args.detail_sleep_seconds)

        detail_page.write_text(
            json.dumps(
                {
                    "contracts": hydrated_contracts,
                    "source_page": feed_page.name,
                    "hydrated_at": dt.datetime.now(dt.UTC).isoformat(),
                },
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        completed_pages = page_no
        pages_processed += 1
        state["completed_pages"] = completed_pages
        state["completed_contracts"] = completed_contracts
        state["last_updated_at"] = dt.datetime.now(dt.UTC).isoformat()
        state["status"] = "running"
        state_path.write_text(
            json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(
            f"[ok] detail_page={page_no} contracts={len(hydrated_contracts)} completed_contracts={completed_contracts}",
            flush=True,
        )
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    state["status"] = "completed" if completed_pages >= len(feed_pages) else "checkpoint_reached"
    state["finished_at"] = dt.datetime.now(dt.UTC).isoformat()
    state["completed_pages"] = completed_pages
    state["completed_contracts"] = completed_contracts
    state_path.write_text(
        json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
