#!/usr/bin/env python3
"""Resumable server-side backfill for Spending.gov.ua daily transactions."""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from tools.lib.imports import repo_root_from

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root_from(__file__)))

from tools.lib.fs import (
    atomic_write_bytes,
    atomic_write_json,
    exclusive_lock,
    write_json_exclusive,
)


def _parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value!r}") from exc


def _today_utc() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def _daterange(start: dt.date, end: dt.date) -> list[dt.date]:
    if end < start:
        raise ValueError("end date must be greater than or equal to start date")
    days = (end - start).days
    return [start + dt.timedelta(days=offset) for offset in range(days + 1)]


def _day_destination(raw_root: Path, day: dt.date) -> Path:
    return raw_root / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}.json.gz"


def _completion_marker(raw_root: Path, day: dt.date) -> Path:
    return raw_root / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}._complete.json"


def _state_payload(state: dict[str, object]) -> dict[str, object]:
    payload = dict(state)
    payload["completed_days"] = sorted(set(str(item) for item in payload.get("completed_days", [])))
    payload["failed_days"] = dict(sorted((payload.get("failed_days") or {}).items()))
    return payload


def _write_state(path: Path, state: dict[str, object]) -> None:
    atomic_write_json(path, _state_payload(state))


def _write_gzip_payload(destination: Path, payload: bytes) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as handle:
        handle.write(payload)
    atomic_write_bytes(destination, buffer.getvalue())
    return destination.stat().st_size


def _read_completion_marker(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid completion marker JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"completion marker must be a JSON object: {path}")
    return data


def _fetch_day(
    day: dt.date, destination: Path, completion_marker: Path
) -> tuple[str, int | None, str | None]:
    if completion_marker.exists():
        try:
            metadata = _read_completion_marker(completion_marker)
        except ValueError as exc:
            return day.isoformat(), None, str(exc)
        if destination.exists() and destination.stat().st_size > 0:
            return (
                day.isoformat(),
                int(metadata.get("size_bytes") or destination.stat().st_size),
                None,
            )
        return (
            day.isoformat(),
            None,
            f"completion marker exists but payload is missing: {completion_marker}",
        )

    url = (
        "https://api.spending.gov.ua/api/v2/api/transactions/"
        f"?startdate={day.isoformat()}&enddate={day.isoformat()}"
    )
    command = ["curl", "--fail", "--location", "--retry", "5", "--retry-all-errors", url]
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0:
        return (
            day.isoformat(),
            None,
            (completed.stderr or completed.stdout).decode("utf-8", "replace")[-2000:],
        )
    payload = completed.stdout
    if not payload.strip().startswith((b"{", b"[")):
        return day.isoformat(), None, "unexpected non-json payload"
    try:
        json.loads(payload.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        return day.isoformat(), None, f"json decode failed: {exc}"

    size_bytes = _write_gzip_payload(destination, payload)
    marker_payload = {
        "day": day.isoformat(),
        "size_bytes": size_bytes,
        "finished_at": dt.datetime.now(dt.UTC).isoformat(),
    }
    try:
        write_json_exclusive(completion_marker, marker_payload)
    except FileExistsError:
        # Another runner completed the day between fetch and publish; keep the payload but report the canonical marker size.
        metadata = _read_completion_marker(completion_marker)
        return day.isoformat(), int(metadata.get("size_bytes") or size_bytes), None
    return day.isoformat(), size_bytes, None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Ukraine data storage root.")
    parser.add_argument("--start-date", type=_parse_date, default=dt.date(2015, 9, 1))
    parser.add_argument("--end-date", type=_parse_date, default=_today_utc())
    parser.add_argument("--workers", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    daily_root = args.root / "raw" / "spending_full" / "daily"
    state_path = args.root / "manifests" / "spending_daily_harvest_state.json"
    lock_path = args.root / "manifests" / "spending_daily_harvest.lock"
    state_path.parent.mkdir(parents=True, exist_ok=True)

    lock_content = (
        f"pid={os.getpid() if 'os' in globals() else 'unknown'}\n"
        f"started_at={dt.datetime.now(dt.UTC).isoformat()}\n"
    )
    try:
        with exclusive_lock(lock_path, content=lock_content):
            lock = threading.Lock()
            state: dict[str, object] = {
                "started_at": dt.datetime.now(dt.UTC).isoformat(),
                "start_date": args.start_date.isoformat(),
                "end_date": args.end_date.isoformat(),
                "workers": args.workers,
                "completed_days": [],
                "failed_days": {},
            }

            pending: list[tuple[dt.date, Path, Path]] = []
            for day in _daterange(args.start_date, args.end_date):
                destination = _day_destination(daily_root, day)
                completion_marker = _completion_marker(daily_root, day)
                if (
                    completion_marker.exists()
                    and destination.exists()
                    and destination.stat().st_size > 0
                ):
                    state["completed_days"].append(day.isoformat())
                    continue
                pending.append((day, destination, completion_marker))

            _write_state(state_path, state)

            def _record(day_text: str, size_bytes: int | None, error: str | None) -> None:
                with lock:
                    if error is None:
                        state["completed_days"].append(day_text)
                    else:
                        failed_days = dict(state["failed_days"])
                        failed_days[day_text] = error
                        state["failed_days"] = failed_days
                    state["last_updated_at"] = dt.datetime.now(dt.UTC).isoformat()
                    state["completed_count"] = len(state["completed_days"])
                    state["failed_count"] = len(state["failed_days"])
                    _write_state(state_path, state)
                    if error is None:
                        print(f"[ok] {day_text} -> {size_bytes} bytes", flush=True)
                    else:
                        print(f"[fail] {day_text}: {error}", flush=True)

            with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
                futures = [
                    executor.submit(_fetch_day, day, destination, completion_marker)
                    for day, destination, completion_marker in pending
                ]
                for future in cf.as_completed(futures):
                    day_text, size_bytes, error = future.result()
                    _record(day_text, size_bytes, error)

            state["finished_at"] = dt.datetime.now(dt.UTC).isoformat()
            state["status"] = "completed" if not state["failed_days"] else "completed_with_failures"
            _write_state(state_path, state)
            return 0 if not state["failed_days"] else 1
    except FileExistsError as exc:
        print(f"ERROR: harvest already in progress: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
