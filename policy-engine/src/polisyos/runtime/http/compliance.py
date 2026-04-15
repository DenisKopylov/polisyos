"""Compliance queries, export, and retention for runtime audit trails."""
from __future__ import annotations

import csv
import gzip
import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from polisyos.common.serialization import fast_json_dumps

if TYPE_CHECKING:
    from collections.abc import Iterable

AuditStream = Literal["access", "mutation", "all"]
AuditOutputFormat = Literal["json", "jsonl", "csv"]


@dataclass(frozen=True, slots=True)
class RuntimeAuditQuery:
    """Filter runtime audit trails for compliance-oriented questions."""

    stream: AuditStream = "all"
    tenant_id: str | None = None
    actor: str | None = None
    resource_id: str | None = None
    endpoint: str | None = None
    operation: str | None = None
    outcome: str | None = None
    since: float | None = None
    until: float | None = None


@dataclass(frozen=True, slots=True)
class RuntimeAuditRetentionResult:
    """Describe one retention pass over runtime audit streams."""

    scanned: int
    kept: int
    archived: int
    archive_paths: tuple[Path, ...]
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "kept": self.kept,
            "archived": self.archived,
            "archive_paths": [str(path) for path in self.archive_paths],
            "dry_run": self.dry_run,
        }


def runtime_audit_paths(cas_root: Path | str) -> dict[str, Path]:
    root = Path(cas_root) / "runtime" / "audit"
    return {
        "access": root / "access.jsonl",
        "mutation": root / "mutations.jsonl",
    }


def parse_audit_time(value: str | None) -> float | None:
    """Parse seconds-since-epoch or ISO-8601 audit filter values."""
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        return float(raw)
    except ValueError:
        pass
    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("Audit timestamps must be timezone-aware")
    return parsed.timestamp()


def query_runtime_audit(
    cas_root: Path | str,
    query: RuntimeAuditQuery,
) -> list[dict[str, Any]]:
    """Return audit entries matching actor/tenant/resource/time filters."""
    entries = [
        entry
        for _stream, entry in iter_runtime_audit_entries(cas_root, stream=query.stream)
        if _matches_query(entry, query)
    ]
    return sorted(entries, key=lambda entry: float(entry.get("timestamp", 0.0)))


def iter_runtime_audit_entries(
    cas_root: Path | str,
    *,
    stream: AuditStream = "all",
) -> Iterable[tuple[str, dict[str, Any]]]:
    paths = runtime_audit_paths(cas_root)
    selected = paths.items() if stream == "all" else ((stream, paths[stream]),)
    for stream_name, path in selected:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                payload.setdefault("audit_stream", stream_name)
                yield stream_name, payload


def summarize_runtime_audit(entries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build a compact actor/tenant/resource summary for compliance reports."""
    total = 0
    by_actor: dict[str, int] = {}
    by_tenant: dict[str, int] = {}
    by_operation: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    resources: set[str] = set()
    for entry in entries:
        total += 1
        actor = str(entry.get("actor") or "")
        tenant = str(entry.get("tenant_id") or "")
        operation = str(entry.get("operation") or "")
        outcome = str(entry.get("outcome") or "")
        resource_id = _entry_resource_id(entry)
        _increment(by_actor, actor or "<unknown>")
        _increment(by_tenant, tenant or "<unknown>")
        _increment(by_operation, operation or "<unknown>")
        _increment(by_outcome, outcome or "<unknown>")
        if resource_id:
            resources.add(resource_id)
    return {
        "total": total,
        "by_actor": dict(sorted(by_actor.items())),
        "by_tenant": dict(sorted(by_tenant.items())),
        "by_operation": dict(sorted(by_operation.items())),
        "by_outcome": dict(sorted(by_outcome.items())),
        "resource_count": len(resources),
        "resources": sorted(resources),
    }


def write_runtime_audit_report(
    entries: list[dict[str, Any]],
    output_path: Path | str,
    *,
    output_format: AuditOutputFormat = "json",
) -> None:
    """Write filtered runtime audit entries as JSON, JSONL, or CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": summarize_runtime_audit(entries),
            "entries": entries,
        }
        _atomic_write_text(path, fast_json_dumps(payload, sort_keys=True) + "\n")
        return
    if output_format == "jsonl":
        _atomic_write_text(
            path,
            "".join(fast_json_dumps(entry, sort_keys=True) + "\n" for entry in entries),
        )
        return
    if output_format == "csv":
        _write_csv(path, entries)
        return
    raise ValueError(f"Unsupported audit output format: {output_format}")


def apply_runtime_audit_retention(
    cas_root: Path | str,
    *,
    retention_days: int,
    archive_dir: Path | str | None = None,
    now: float | None = None,
    dry_run: bool = False,
) -> RuntimeAuditRetentionResult:
    """Archive audit entries older than the retention window and keep recent rows."""
    if retention_days < 1:
        raise ValueError("retention_days must be >= 1")
    current = time.time() if now is None else now
    cutoff = current - (retention_days * 24 * 60 * 60)
    archive_root = Path(archive_dir) if archive_dir is not None else (
        Path(cas_root) / "runtime" / "audit" / "archive"
    )
    scanned = kept = archived = 0
    archive_paths: list[Path] = []
    audit_paths = runtime_audit_paths(cas_root)
    for stream_name in ("access", "mutation"):
        path = audit_paths[stream_name]
        if not path.exists():
            continue
        entries = [
            payload
            for _stream, payload in iter_runtime_audit_entries(cas_root, stream=stream_name)
        ]
        expired = [entry for entry in entries if float(entry.get("timestamp", current)) < cutoff]
        fresh = [entry for entry in entries if float(entry.get("timestamp", current)) >= cutoff]
        scanned += len(entries)
        kept += len(fresh)
        archived += len(expired)
        if not expired:
            continue
        archive_path = archive_root / (
            f"{stream_name}-{datetime.fromtimestamp(current, UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl.gz"
        )
        archive_paths.append(archive_path)
        if dry_run:
            continue
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(archive_path, "wt", encoding="utf-8") as handle:
            for entry in expired:
                handle.write(fast_json_dumps(entry, sort_keys=True) + "\n")
        _atomic_write_text(
            path,
            "".join(fast_json_dumps(entry, sort_keys=True) + "\n" for entry in fresh),
        )
    return RuntimeAuditRetentionResult(
        scanned=scanned,
        kept=kept,
        archived=archived,
        archive_paths=tuple(archive_paths),
        dry_run=dry_run,
    )


def _matches_query(entry: dict[str, Any], query: RuntimeAuditQuery) -> bool:
    timestamp = float(entry.get("timestamp", 0.0))
    if query.since is not None and timestamp < query.since:
        return False
    if query.until is not None and timestamp > query.until:
        return False
    if query.tenant_id and str(entry.get("tenant_id") or "") != query.tenant_id:
        return False
    if query.actor and str(entry.get("actor") or "") != query.actor:
        return False
    if query.endpoint and str(entry.get("endpoint") or "") != query.endpoint:
        return False
    if query.operation and str(entry.get("operation") or "") != query.operation:
        return False
    if query.outcome and str(entry.get("outcome") or "") != query.outcome:
        return False
    if query.resource_id and query.resource_id != _entry_resource_id(entry):
        resource_ids = entry.get("resource_ids")
        if not isinstance(resource_ids, list) or query.resource_id not in resource_ids:
            return False
    return True


def _entry_resource_id(entry: dict[str, Any]) -> str:
    resource_id = entry.get("resource_id")
    if isinstance(resource_id, str) and resource_id:
        return resource_id
    resource_ids = entry.get("resource_ids")
    if isinstance(resource_ids, list):
        for item in resource_ids:
            if isinstance(item, str) and item:
                return item
    return ""


def _increment(bucket: dict[str, int], key: str) -> None:
    bucket[key] = bucket.get(key, 0) + 1


def _write_csv(path: Path, entries: list[dict[str, Any]]) -> None:
    fieldnames = [
        "audit_stream",
        "timestamp",
        "request_id",
        "tenant_id",
        "actor",
        "method",
        "endpoint",
        "operation",
        "resource_kind",
        "resource_id",
        "outcome",
        "status_code",
        "idempotency_key",
    ]
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=str(path.parent),
        delete=False,
    ) as handle:
        tmp_path = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            row = {name: entry.get(name, "") for name in fieldnames}
            row["resource_id"] = _entry_resource_id(entry)
            writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _atomic_write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        delete=False,
    ) as handle:
        tmp_path = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


__all__ = [
    "AuditOutputFormat",
    "AuditStream",
    "RuntimeAuditQuery",
    "RuntimeAuditRetentionResult",
    "apply_runtime_audit_retention",
    "iter_runtime_audit_entries",
    "parse_audit_time",
    "query_runtime_audit",
    "runtime_audit_paths",
    "summarize_runtime_audit",
    "write_runtime_audit_report",
]
