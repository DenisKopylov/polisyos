#!/usr/bin/env python3
"""Resumable server-side harvest of the Prozorro public contracts feed."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
import urllib.parse
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
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5000,
        help="Maximum pages to fetch in this run. Use 0 or a negative value for no page cap.",
    )
    parser.add_argument("--sleep-seconds", type=float, default=0.1)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    feed_root = args.root / "raw" / "prozorro_full" / "contracts_feed"
    state_path = args.root / "manifests" / "prozorro_contract_feed_state.json"
    feed_root.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    state: dict[str, object] = {
        "started_at": dt.datetime.now(dt.UTC).isoformat(),
        "limit": args.limit,
        "completed_pages": 0,
        "last_offset": None,
        "failures": [],
    }
    if state_path.exists():
        state.update(json.loads(state_path.read_text(encoding="utf-8")))

    offset = state.get("last_offset")
    completed_pages = int(state.get("completed_pages", 0))

    page_budget = args.max_pages if args.max_pages > 0 else None
    pages_processed = 0

    while page_budget is None or pages_processed < page_budget:
        page_no = completed_pages + 1
        params = {"limit": str(args.limit)}
        if offset:
            params["offset"] = str(offset)
        url = "https://public.api.openprocurement.org/api/2.5/contracts?" + urllib.parse.urlencode(
            params
        )
        try:
            payload = _fetch_json(url)
        except Exception as exc:
            state["failures"].append(
                {
                    "page_no": page_no,
                    "offset": offset,
                    "error": str(exc),
                    "at": dt.datetime.now(dt.UTC).isoformat(),
                }
            )
            state["status"] = "paused_on_error"
            state_path.write_text(
                json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
            )
            return 1

        page_path = feed_root / f"page_{page_no:07d}.json"
        page_path.write_text(
            json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8"
        )
        next_page = payload.get("next_page") or {}
        offset = next_page.get("offset")
        completed_pages = page_no
        pages_processed += 1
        state["completed_pages"] = completed_pages
        state["last_offset"] = offset
        state["last_updated_at"] = dt.datetime.now(dt.UTC).isoformat()
        state["status"] = "running"
        state_path.write_text(
            json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(
            f"[ok] page={page_no} items={len(payload.get('data', []))} offset={offset}",
            flush=True,
        )
        if not offset:
            state["status"] = "completed"
            state["finished_at"] = dt.datetime.now(dt.UTC).isoformat()
            state_path.write_text(
                json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
            )
            return 0
        time.sleep(max(0.0, args.sleep_seconds))

    state["status"] = "checkpoint_reached"
    state["finished_at"] = dt.datetime.now(dt.UTC).isoformat()
    state_path.write_text(
        json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
