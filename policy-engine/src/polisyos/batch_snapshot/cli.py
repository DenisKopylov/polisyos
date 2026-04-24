"""CLI to finalize a unified pipeline snapshot manifest."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.batch_common.hashing import sha256_file
from polisyos.common.logger import get_logger

logger = get_logger(__name__)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def finalize_snapshot(snapshot_root: Path, *, update_latest_symlink: bool = True) -> Path:
    """Create `<snapshot_root>/snapshot_manifest.json` from pipeline publish manifests."""
    pipelines = ("datasets", "academic", "lex")
    pipeline_manifests: dict[str, dict[str, Any]] = {}
    artifacts: list[dict[str, str]] = []

    for name in pipelines:
        manifest_path = snapshot_root / name / "publish" / "manifest.json"
        manifest = _load_json(manifest_path)
        pipeline_manifests[name] = manifest
        for item in manifest.get("artifacts", []):
            path = Path(item.get("path", ""))
            if path.exists():
                artifacts.append(
                    {
                        "pipeline": name,
                        "path": str(path),
                        "sha256": item.get("sha256") or sha256_file(path),
                    }
                )

    out = {
        "kind": "snapshot",
        "snapshot_root": str(snapshot_root),
        "generated_at": datetime.now(UTC).isoformat(),
        "pipelines": pipeline_manifests,
        "artifacts": artifacts,
    }

    out_path = snapshot_root / "snapshot_manifest.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    if update_latest_symlink:
        latest = snapshot_root.parent / "policyos_snapshot_latest"
        try:
            if latest.is_symlink() or latest.exists():
                latest.unlink()
            latest.symlink_to(snapshot_root.name)
        except OSError as exc:
            logger.warning("Failed to update latest symlink: %s", exc)

    return out_path


def main() -> None:
    """Main helper."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="Unified snapshot utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    finalize = sub.add_parser("finalize", help="Aggregate datasets/academic/lex publish manifests")
    finalize.add_argument("--snapshot-root", required=True)
    finalize.add_argument("--no-latest-symlink", action="store_true")

    args = parser.parse_args()
    if args.command == "finalize":
        finalize_snapshot(
            Path(args.snapshot_root),
            update_latest_symlink=not args.no_latest_symlink,
        )


if __name__ == "__main__":
    main()
