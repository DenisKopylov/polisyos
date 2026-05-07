#!/usr/bin/env python3
"""Validate a GCP worker without launching the Lex processing pipeline."""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
from io import TextIOWrapper
from pathlib import Path

import zstandard as zstd


def _memory_gb() -> float | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    for line in meminfo.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            kb = int(line.split()[1])
            return round(kb / (1024 * 1024), 2)
    return None


def _check_tcp(host: str, port: int, timeout: float) -> dict[str, object]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"ok": True}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def _preview_manifest(path: Path, limit: int = 3) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    dctx = zstd.ZstdDecompressor()
    with path.open("rb") as raw_fh, dctx.stream_reader(raw_fh) as reader:
        text_reader = TextIOWrapper(reader, encoding="utf-8")
        for _ in range(limit):
            line = text_reader.readline()
            if not line:
                break
            payload = json.loads(line)
            rows.append(
                {
                    "doc_id": payload.get("doc_id"),
                    "status": payload.get("status"),
                    "text_length": payload.get("text_length"),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--status-pass", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--account-num", type=int, required=True)
    args = parser.parse_args()

    report = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "status_pass": args.status_pass,
        "shard_index": args.shard_index,
        "account_num": args.account_num,
        "memory_gb": _memory_gb(),
        "manifest_exists": args.manifest.exists(),
        "manifest_size_bytes": args.manifest.stat().st_size if args.manifest.exists() else 0,
        "summary_exists": args.summary.exists(),
        "gonka_keys_loaded": len(
            [
                key
                for key in os.environ
                if key == "GONKA_API_KEY" or key.startswith("GONKA_API_KEY_")
            ]
        ),
        "imports": {},
        "network": {
            "gonka_tcp_443": _check_tcp("api.gonkagate.com", 443, timeout=5.0),
        },
        "manifest_preview": [],
        "errors": [],
    }

    for module_name in (
        "polisyos.data_forge.domains.legal.batch.cli",
        "polisyos.data_forge.domains.legal.batch.pipeline",
        "polisyos.data_forge.domains.legal.batch.xml_parser",
    ):
        try:
            __import__(module_name)
            report["imports"][module_name] = "ok"
        except Exception as exc:  # pragma: no cover - preflight diagnostic
            report["imports"][module_name] = f"error: {exc}"
            report["errors"].append(f"import:{module_name}:{exc}")

    if args.manifest.exists():
        try:
            report["manifest_preview"] = _preview_manifest(args.manifest)
        except Exception as exc:  # pragma: no cover - preflight diagnostic
            report["errors"].append(f"manifest:{exc}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(json.dumps({"output": str(args.output), "errors": report["errors"]}, ensure_ascii=False))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
