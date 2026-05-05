#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from tools.lib.fs import atomic_write_text

from .inventory_legacy_runs import collect_inventory


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive legacy runs directory into deterministic tarball with report.",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("runs"),
        help="Legacy runs root to archive.",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=Path("_build/.tmp/legacy_runs_archive"),
        help="Directory where archive artifact/report are stored.",
    )
    parser.add_argument(
        "--delete-source",
        action="store_true",
        help="Delete source runs-root after a successful archive write.",
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info


def _archive_runs(runs_root: Path, output_path: Path) -> None:
    with tarfile.open(output_path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        archive.add(
            runs_root,
            arcname=runs_root.name,
            recursive=True,
            filter=_tar_filter,
        )


def main() -> int:
    args = _parse_args()
    runs_root = args.runs_root.resolve()
    archive_dir = args.archive_dir.resolve()
    archive_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_path = archive_dir / f"legacy_runs_{timestamp}.tar.gz"
    report_path = archive_dir / f"legacy_runs_{timestamp}.report.json"

    inventory = collect_inventory(runs_root)
    if runs_root.exists():
        _archive_runs(runs_root, archive_path)
        archive_sha256 = _sha256(archive_path)
        archive_size = archive_path.stat().st_size
    else:
        archive_path.write_bytes(b"")
        archive_sha256 = _sha256(archive_path)
        archive_size = 0

    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "runs_root": str(runs_root),
        "archive_path": str(archive_path),
        "archive_sha256": archive_sha256,
        "archive_size_bytes": archive_size,
        "rows": [asdict(row) for row in inventory],
    }
    atomic_write_text(
        report_path,
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if args.delete_source and runs_root.exists():
        shutil.rmtree(runs_root)
        report["source_deleted"] = True
        atomic_write_text(
            report_path,
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
