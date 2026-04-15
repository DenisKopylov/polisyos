#!/usr/bin/env python3
"""Resumable server-side harvest for Spending contracts grouped by disposerId.

The Spending contracts endpoint behaves inconsistently on broad queries:

- global date windows are truncated even for single-day slices
- disposerId queries usually return the full response, but large disposers can
  still be silently capped around 1000 rows while exposing a larger `count`

To keep the raw layer honest, this harvester uses the following strategy:

1. query a disposerId directly
2. if `count <= returned_docs`, keep the payload as one complete slice
3. otherwise recursively split by `signDate` until every saved slice is complete

This gives us resumable, bounded raw artifacts without pretending that a
truncated payload is the full contract history for a disposer.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import io
import json
import math
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from tools._lib.imports import repo_root_from
from typing import Any
from urllib.parse import urlencode

import duckdb

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root_from(__file__)))

from tools._lib.fs import atomic_write_bytes, atomic_write_json, exclusive_lock, write_json_exclusive


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Ukraine data storage root.")
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent requests to the Spending contracts endpoint.",
    )
    parser.add_argument(
        "--max-time",
        type=int,
        default=30,
        help="Maximum wall time per curl request in seconds.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on the number of disposer ids to fetch.",
    )
    parser.add_argument(
        "--ids-file",
        type=Path,
        default=None,
        help="Optional newline-delimited or JSON list of disposer ids.",
    )
    return parser


@dataclass(frozen=True)
class HarvestResult:
    disposer_id: str
    size_bytes: int
    document_count: int
    slice_count: int
    error: str | None = None
    skipped_existing: bool = False


def _normalize_disposer_id(value: object) -> str | None:
    digits = "".join(ch for ch in str(value or "").strip() if ch.isdigit())
    return digits or None


def _load_disposer_ids(root: Path, *, ids_file: Path | None, limit: int | None) -> list[str]:
    if ids_file is not None:
        raw = ids_file.read_text(encoding="utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            values = [line.strip() for line in raw.splitlines() if line.strip()]
        else:
            if isinstance(payload, list):
                values = [str(item) for item in payload]
            else:
                raise ValueError(f"ids file must be a list or newline-delimited text: {ids_file}")
        normalized = []
        for value in values:
            disposer_id = _normalize_disposer_id(value)
            if disposer_id is not None:
                normalized.append(disposer_id)
        return normalized[:limit] if limit is not None else normalized

    spending_path = root / "normalized" / "spending_full" / "budget_flows_monthly_sparse.parquet"
    if not spending_path.exists():
        raise FileNotFoundError(f"missing normalized Spending artifact: {spending_path}")
    con = duckdb.connect()
    query = """
        SELECT source_agent_id, sum(amount) AS total_amount
        FROM read_parquet(?)
        WHERE source_agent_id IS NOT NULL AND trim(source_agent_id) <> ''
        GROUP BY 1
        ORDER BY total_amount DESC
    """
    try:
        rows = con.execute(query, [str(spending_path)]).fetchall()
    finally:
        con.close()
    disposer_ids: list[str] = []
    seen: set[str] = set()
    for raw_id, _ in rows:
        disposer_id = _normalize_disposer_id(raw_id)
        if disposer_id is None or disposer_id in seen:
            continue
        disposer_ids.append(disposer_id)
        seen.add(disposer_id)
        if limit is not None and len(disposer_ids) >= limit:
            break
    return disposer_ids


def _disposer_root(raw_root: Path, disposer_id: str) -> Path:
    return raw_root / "contracts_by_disposer" / disposer_id[:2] / disposer_id


def _completion_marker(raw_root: Path, disposer_id: str) -> Path:
    return _disposer_root(raw_root, disposer_id) / "_complete.json"


def _slice_destination(
    raw_root: Path,
    disposer_id: str,
    *,
    start: dt.date | None,
    end: dt.date | None,
    document_start: dt.date | None = None,
    document_end: dt.date | None = None,
    amount_from: float | None = None,
    amount_to: float | None = None,
) -> Path:
    base_dir = _disposer_root(raw_root, disposer_id)
    parts: list[str] = []
    if start is not None and end is not None:
        parts.append(f"sign_{start.isoformat()}_{end.isoformat()}")
    if document_start is not None and document_end is not None:
        parts.append(f"doc_{document_start.isoformat()}_{document_end.isoformat()}")
    if amount_from is not None or amount_to is not None:
        lower = "min" if amount_from is None else f"{amount_from:.2f}"
        upper = "max" if amount_to is None else f"{amount_to:.2f}"
        parts.append(f"amt_{lower}_{upper}")
    if not parts:
        return base_dir / "full.json.gz"
    safe_name = "__".join(parts).replace("/", "-")
    return base_dir / f"{safe_name}.json.gz"


def _save_payload(destination: Path, payload: bytes) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as handle:
        handle.write(payload)
    atomic_write_bytes(destination, buffer.getvalue())
    return destination.stat().st_size


def _load_json_object(path: Path, *, kind: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{kind} contains invalid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{kind} must be a JSON object: {path}")
    return data


def _payload_documents(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        documents = data.get("documents")
        if isinstance(documents, list):
            return [item for item in documents if isinstance(item, dict)]
        data_items = data.get("data")
        if isinstance(data_items, list):
            return [item for item in data_items if isinstance(item, dict)]
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _payload_declared_count(data: Any, *, docs: list[dict[str, Any]]) -> int:
    if isinstance(data, dict):
        try:
            return int(data.get("count") or len(docs))
        except (TypeError, ValueError):
            return len(docs)
    return len(docs)


def _parse_iso_date(value: object) -> dt.date | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _payload_date_range(docs: list[dict[str, Any]], field: str) -> tuple[dt.date, dt.date] | None:
    dates = [_parse_iso_date(item.get(field)) for item in docs]
    parsed = sorted(date for date in dates if date is not None)
    if not parsed:
        return None
    return parsed[0], parsed[-1]


def _payload_amount_values(docs: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for item in docs:
        raw = item.get("currencyAmountUAH")
        if raw in (None, ""):
            raw = item.get("amount")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(value)
    return sorted(values)


def _intersect_date_range(
    observed: tuple[dt.date, dt.date] | None,
    lower: dt.date | None,
    upper: dt.date | None,
) -> tuple[dt.date, dt.date] | None:
    if observed is None:
        return None
    start, end = observed
    if lower is not None:
        start = max(start, lower)
    if upper is not None:
        end = min(end, upper)
    if start > end:
        return None
    return start, end


def _amount_split_bounds(
    values: list[float],
    *,
    amount_from: float | None,
    amount_to: float | None,
) -> tuple[float, float, float] | None:
    if not values:
        return None
    lower = values[0] if amount_from is None else max(values[0], amount_from)
    upper = values[-1] if amount_to is None else min(values[-1], amount_to)
    if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
        return None
    pivot = values[len(values) // 2]
    pivot = min(max(pivot, lower), upper)
    if pivot <= lower:
        pivot = lower + ((upper - lower) / 2.0)
    if pivot >= upper:
        pivot = lower + ((upper - lower) / 2.0)
    if pivot <= lower or pivot >= upper:
        return None
    return lower, pivot, upper


def _fetch_payload(
    *,
    disposer_id: str,
    max_time: int,
    sign_date_from: dt.date | None = None,
    sign_date_to: dt.date | None = None,
    document_date_from: dt.date | None = None,
    document_date_to: dt.date | None = None,
    amount_from: float | None = None,
    amount_to: float | None = None,
) -> tuple[bytes | None, Any | None, str | None]:
    params = {"disposerId": disposer_id}
    if sign_date_from is not None:
        params["signDateFrom"] = sign_date_from.isoformat()
    if sign_date_to is not None:
        params["signDateTo"] = sign_date_to.isoformat()
    if document_date_from is not None:
        params["documentDateFrom"] = document_date_from.isoformat()
    if document_date_to is not None:
        params["documentDateTo"] = document_date_to.isoformat()
    if amount_from is not None:
        params["amountFrom"] = f"{amount_from:.2f}"
    if amount_to is not None:
        params["amountTo"] = f"{amount_to:.2f}"
    url = "http://api.spending.gov.ua/api/v2/disposers/contracts?" + urlencode(params)
    last_error = "unknown fetch failure"
    for _attempt in range(3):
        command = [
            "curl",
            "--fail",
            "--location",
            "--retry",
            "4",
            "--retry-all-errors",
            "--connect-timeout",
            "10",
            "--max-time",
            str(max(10, max_time)),
            "-A",
            "Mozilla/5.0",
            url,
        ]
        completed = subprocess.run(command, capture_output=True, check=False)
        if completed.returncode != 0:
            last_error = (completed.stderr or completed.stdout).decode("utf-8", "replace")[-2000:]
            continue
        payload = completed.stdout
        if not payload.strip().startswith((b"{", b"[")):
            last_error = "unexpected non-json payload"
            continue
        try:
            data = json.loads(payload.decode("utf-8", "replace"))
        except json.JSONDecodeError as exc:
            last_error = f"json decode failed: {exc}"
            continue
        return payload, data, None
    return None, None, last_error


def _harvest_slice(
    *,
    raw_root: Path,
    disposer_id: str,
    max_time: int,
    sign_date_from: dt.date | None = None,
    sign_date_to: dt.date | None = None,
    document_date_from: dt.date | None = None,
    document_date_to: dt.date | None = None,
    amount_from: float | None = None,
    amount_to: float | None = None,
    depth: int = 0,
) -> tuple[int, int, int, str | None]:
    destination = _slice_destination(
        raw_root,
        disposer_id,
        start=sign_date_from,
        end=sign_date_to,
        document_start=document_date_from,
        document_end=document_date_to,
        amount_from=amount_from,
        amount_to=amount_to,
    )
    if destination.exists() and destination.stat().st_size > 0:
        with gzip.open(destination, "rt", encoding="utf-8") as handle:
            cached = json.load(handle)
        docs = _payload_documents(cached)
        return destination.stat().st_size, len(docs), 1, None

    payload, data, error = _fetch_payload(
        disposer_id=disposer_id,
        max_time=max_time,
        sign_date_from=sign_date_from,
        sign_date_to=sign_date_to,
        document_date_from=document_date_from,
        document_date_to=document_date_to,
        amount_from=amount_from,
        amount_to=amount_to,
    )
    if error is not None:
        return 0, 0, 0, error

    docs = _payload_documents(data)
    declared_count = _payload_declared_count(data, docs=docs)
    if declared_count <= len(docs):
        size_bytes = _save_payload(destination, payload or b"[]")
        return size_bytes, len(docs), 1, None

    sign_date_range = _intersect_date_range(
        _payload_date_range(docs, "signDate"),
        sign_date_from,
        sign_date_to,
    )
    if sign_date_range is not None and sign_date_range[0] < sign_date_range[1]:
        start, end = sign_date_range
        midpoint = start + dt.timedelta(days=(end - start).days // 2)
        left = _harvest_slice(
            raw_root=raw_root,
            disposer_id=disposer_id,
            max_time=max_time,
            sign_date_from=start,
            sign_date_to=midpoint,
            document_date_from=document_date_from,
            document_date_to=document_date_to,
            amount_from=amount_from,
            amount_to=amount_to,
            depth=depth + 1,
        )
        if left[3] is not None:
            return left
        right_start = midpoint + dt.timedelta(days=1)
        right = _harvest_slice(
            raw_root=raw_root,
            disposer_id=disposer_id,
            max_time=max_time,
            sign_date_from=right_start,
            sign_date_to=end,
            document_date_from=document_date_from,
            document_date_to=document_date_to,
            amount_from=amount_from,
            amount_to=amount_to,
            depth=depth + 1,
        )
        if right[3] is not None:
            return right
        return left[0] + right[0], left[1] + right[1], left[2] + right[2], None

    document_date_range = _intersect_date_range(
        _payload_date_range(docs, "documentDate"),
        document_date_from,
        document_date_to,
    )
    if document_date_range is not None and document_date_range[0] < document_date_range[1]:
        start, end = document_date_range
        midpoint = start + dt.timedelta(days=(end - start).days // 2)
        left = _harvest_slice(
            raw_root=raw_root,
            disposer_id=disposer_id,
            max_time=max_time,
            sign_date_from=sign_date_from,
            sign_date_to=sign_date_to,
            document_date_from=start,
            document_date_to=midpoint,
            amount_from=amount_from,
            amount_to=amount_to,
            depth=depth + 1,
        )
        if left[3] is not None:
            return left
        right_start = midpoint + dt.timedelta(days=1)
        right = _harvest_slice(
            raw_root=raw_root,
            disposer_id=disposer_id,
            max_time=max_time,
            sign_date_from=sign_date_from,
            sign_date_to=sign_date_to,
            document_date_from=right_start,
            document_date_to=end,
            amount_from=amount_from,
            amount_to=amount_to,
            depth=depth + 1,
        )
        if right[3] is not None:
            return right
        return left[0] + right[0], left[1] + right[1], left[2] + right[2], None

    amount_split = _amount_split_bounds(
        _payload_amount_values(docs),
        amount_from=amount_from,
        amount_to=amount_to,
    )
    if amount_split is not None:
        lower, pivot, upper = amount_split
        left = _harvest_slice(
            raw_root=raw_root,
            disposer_id=disposer_id,
            max_time=max_time,
            sign_date_from=sign_date_from,
            sign_date_to=sign_date_to,
            document_date_from=document_date_from,
            document_date_to=document_date_to,
            amount_from=lower,
            amount_to=pivot,
            depth=depth + 1,
        )
        if left[3] is not None:
            return left
        right = _harvest_slice(
            raw_root=raw_root,
            disposer_id=disposer_id,
            max_time=max_time,
            sign_date_from=sign_date_from,
            sign_date_to=sign_date_to,
            document_date_from=document_date_from,
            document_date_to=document_date_to,
            amount_from=round(pivot + 0.01, 2),
            amount_to=upper,
            depth=depth + 1,
        )
        if right[3] is not None:
            return right
        return left[0] + right[0], left[1] + right[1], left[2] + right[2], None

    observed_sign_range = _payload_date_range(docs, "signDate")
    observed_document_range = _payload_date_range(docs, "documentDate")
    amount_values = _payload_amount_values(docs)
    if observed_sign_range is None and observed_document_range is None and not amount_values:
        partial_path = destination.with_name(destination.stem + ".partial.json.gz")
        _save_payload(partial_path, payload or b"[]")
        return 0, 0, 0, "declared count exceeds returned docs and payload has no signDate range"
    partial_path = destination.with_name(destination.stem + ".partial.json.gz")
    _save_payload(partial_path, payload or b"[]")
    range_hint = ""
    if sign_date_range is not None:
        range_hint = f"sign={sign_date_range[0].isoformat()}..{sign_date_range[1].isoformat()}"
    elif document_date_range is not None:
        range_hint = f"document={document_date_range[0].isoformat()}..{document_date_range[1].isoformat()}"
    elif amount_split is not None:
        range_hint = f"amount={amount_split[0]:.2f}..{amount_split[2]:.2f}"
    return (
        0,
        0,
        0,
        f"slice still truncated after sign/document/amount splitting {range_hint} ({len(docs)}/{declared_count})",
    )


def _harvest_disposer(disposer_id: str, *, raw_root: Path, max_time: int) -> HarvestResult:
    completion_marker = _completion_marker(raw_root, disposer_id)
    if completion_marker.exists():
        try:
            metadata = _load_json_object(completion_marker, kind="completion marker")
        except ValueError as exc:
            return HarvestResult(
                disposer_id=disposer_id,
                size_bytes=0,
                document_count=0,
                slice_count=0,
                error=str(exc),
            )
        slice_paths = list(_disposer_root(raw_root, disposer_id).glob("*.json.gz"))
        if not slice_paths:
            return HarvestResult(
                disposer_id=disposer_id,
                size_bytes=0,
                document_count=0,
                slice_count=0,
                error=f"completion marker exists but no payload slices found for disposerId={disposer_id}",
            )
        return HarvestResult(
            disposer_id=disposer_id,
            size_bytes=int(metadata.get("size_bytes") or 0),
            document_count=int(metadata.get("document_count") or 0),
            slice_count=int(metadata.get("slice_count") or 0),
            skipped_existing=True,
        )

    size_bytes, document_count, slice_count, error = _harvest_slice(
        raw_root=raw_root,
        disposer_id=disposer_id,
        max_time=max_time,
    )
    if error is not None:
        return HarvestResult(
            disposer_id=disposer_id,
            size_bytes=0,
            document_count=0,
            slice_count=0,
            error=error,
        )

    marker_payload = {
        "disposer_id": disposer_id,
        "document_count": document_count,
        "finished_at": dt.datetime.now(dt.UTC).isoformat(),
        "size_bytes": size_bytes,
        "slice_count": slice_count,
    }
    completion_marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        write_json_exclusive(completion_marker, marker_payload)
    except FileExistsError:
        metadata = _load_json_object(completion_marker, kind="completion marker")
        return HarvestResult(
            disposer_id=disposer_id,
            size_bytes=int(metadata.get("size_bytes") or size_bytes),
            document_count=int(metadata.get("document_count") or document_count),
            slice_count=int(metadata.get("slice_count") or slice_count),
            skipped_existing=True,
        )
    return HarvestResult(
        disposer_id=disposer_id,
        size_bytes=size_bytes,
        document_count=document_count,
        slice_count=slice_count,
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    contracts_root = args.root / "raw" / "spending_full"
    state_path = args.root / "manifests" / "spending_contracts_harvest_state.json"
    lock_path = args.root / "manifests" / "spending_contracts_harvest.lock"
    state_path.parent.mkdir(parents=True, exist_ok=True)

    lock_content = f"pid={os.getpid()}\nstarted_at={dt.datetime.now(dt.UTC).isoformat()}\n"
    try:
        with exclusive_lock(lock_path, content=lock_content):
            disposer_ids = _load_disposer_ids(args.root, ids_file=args.ids_file, limit=args.limit)
            pending: list[str] = []
            completed_existing = 0
            for disposer_id in disposer_ids:
                if _completion_marker(contracts_root, disposer_id).exists():
                    completed_existing += 1
                    continue
                pending.append(disposer_id)

            lock = threading.Lock()
            state: dict[str, object] = {
                "started_at": dt.datetime.now(dt.UTC).isoformat(),
                "workers": args.workers,
                "max_time_s": args.max_time,
                "total_ids": len(disposer_ids),
                "completed_existing": completed_existing,
                "completed_count": completed_existing,
                "failed_count": 0,
                "failed_ids": {},
                "last_completed_id": None,
                "last_updated_at": None,
                "pending_count": len(pending),
                "slice_count": 0,
                "document_count": 0,
                "status": "running",
            }
            atomic_write_json(state_path, state)

            def _record(result: HarvestResult) -> None:
                with lock:
                    if result.error is None:
                        state["completed_count"] = int(state["completed_count"]) + (0 if result.skipped_existing else 1)
                        state["document_count"] = int(state["document_count"]) + result.document_count
                        state["slice_count"] = int(state["slice_count"]) + result.slice_count
                        state["last_completed_id"] = result.disposer_id
                    else:
                        failed_ids = dict(state["failed_ids"])
                        failed_ids[result.disposer_id] = result.error
                        state["failed_ids"] = failed_ids
                        state["failed_count"] = len(failed_ids)
                    completed_count = int(state["completed_count"])
                    failed_count = int(state["failed_count"])
                    state["pending_count"] = max(0, len(disposer_ids) - completed_count - failed_count)
                    state["last_updated_at"] = dt.datetime.now(dt.UTC).isoformat()
                    atomic_write_json(state_path, state)
                    if result.error is None:
                        prefix = "[skip]" if result.skipped_existing else "[ok]"
                        print(
                            f"{prefix} disposerId={result.disposer_id} docs={result.document_count} "
                            f"slices={result.slice_count} size={result.size_bytes}",
                            flush=True,
                        )
                    else:
                        print(f"[fail] disposerId={result.disposer_id}: {result.error}", flush=True)

            with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
                futures = [
                    executor.submit(_harvest_disposer, disposer_id, raw_root=contracts_root, max_time=args.max_time)
                    for disposer_id in pending
                ]
                for future in cf.as_completed(futures):
                    _record(future.result())

            state["finished_at"] = dt.datetime.now(dt.UTC).isoformat()
            state["status"] = "completed" if not state["failed_ids"] else "completed_with_failures"
            atomic_write_json(state_path, state)
            return 0 if not state["failed_ids"] else 1
    except FileExistsError as exc:
        print(f"ERROR: harvest already in progress: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
