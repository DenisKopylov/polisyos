#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LegacyRunInventoryRow:
    run_id: str
    manifest_path: str
    manifest_present: bool
    parse_ok: bool
    shape_valid: bool
    status: str | None
    artifact_count: int
    started_at: str | None
    finished_at: str | None
    parse_error: str | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory legacy runs/<id>/manifest.json before P10 removal.",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("runs"),
        help="Root directory containing legacy run folders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output JSON path.",
    )
    return parser.parse_args()


def _is_legacy_manifest_shape(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if "registry_bundle" in payload:
        return False
    return (
        isinstance(payload.get("run_id"), str)
        and isinstance(payload.get("status"), str)
        and isinstance(payload.get("artifacts"), list)
    )


def _artifact_count(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return 0
    return len(artifacts)


def collect_inventory(runs_root: Path) -> list[LegacyRunInventoryRow]:
    rows: list[LegacyRunInventoryRow] = []
    if not runs_root.exists():
        return rows

    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            rows.append(
                LegacyRunInventoryRow(
                    run_id=run_dir.name,
                    manifest_path=str(manifest_path),
                    manifest_present=False,
                    parse_ok=False,
                    shape_valid=False,
                    status=None,
                    artifact_count=0,
                    started_at=None,
                    finished_at=None,
                    parse_error="manifest_missing",
                )
            )
            continue

        raw = manifest_path.read_text(encoding="utf-8")
        payload: Any
        parse_error: str | None = None
        parse_ok = True
        try:
            payload = json.loads(raw)
        except Exception as exc:  # pragma: no cover - parse error branch
            payload = {}
            parse_ok = False
            parse_error = f"{type(exc).__name__}: {exc}"

        run_id = run_dir.name
        status = None
        started_at = None
        finished_at = None
        if isinstance(payload, dict):
            run_id = str(payload.get("run_id") or run_id)
            status = payload.get("status")
            started_at = payload.get("started_at")
            finished_at = payload.get("finished_at")

        rows.append(
            LegacyRunInventoryRow(
                run_id=run_id,
                manifest_path=str(manifest_path),
                manifest_present=True,
                parse_ok=parse_ok,
                shape_valid=_is_legacy_manifest_shape(payload),
                status=str(status) if status is not None else None,
                artifact_count=_artifact_count(payload),
                started_at=str(started_at) if started_at is not None else None,
                finished_at=str(finished_at) if finished_at is not None else None,
                parse_error=parse_error,
            )
        )
    return rows


def _render_payload(rows: list[LegacyRunInventoryRow], runs_root: Path) -> dict[str, Any]:
    return {
        "runs_root": str(runs_root),
        "total_runs": len(rows),
        "manifest_missing_count": sum(1 for row in rows if not row.manifest_present),
        "parse_error_count": sum(1 for row in rows if row.manifest_present and not row.parse_ok),
        "shape_valid_count": sum(1 for row in rows if row.shape_valid),
        "rows": [asdict(row) for row in rows],
    }


def main() -> int:
    args = _parse_args()
    runs_root = args.runs_root.resolve()
    rows = collect_inventory(runs_root)
    payload = _render_payload(rows, runs_root)

    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")

    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
