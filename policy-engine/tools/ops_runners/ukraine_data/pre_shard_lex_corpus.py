#!/usr/bin/env python3
"""Pre-materialize the ЄДРНПА corpus into per-pass shard JSONL.ZST manifests.

This helper keeps the pipeline's card/text join semantics by reusing
``iter_documents(...)`` from the Lex XML parser and the same shard assignment
rule as ``BatchConfig.is_doc_in_shard(...)``.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

import zstandard as zstd

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.data_forge.domains.ukraine.sharding import (  # noqa: E402
    CURRENT_STATUSES as CURRENT_STATUSES,
)
from polisyos.data_forge.domains.ukraine.sharding import (
    HISTORICAL_STATUSES as HISTORICAL_STATUSES,
)
from polisyos.data_forge.domains.ukraine.sharding import (
    infer_lex_snapshot_label,
    lex_pre_shard_index,
    lex_pre_shard_pass_name,
)
from polisyos.data_forge.read_api.legal import NPADocument, iter_documents

from tools.lib.fs import atomic_write_json


def _infer_snapshot_label(cards_path: Path, texts_path: Path) -> str:
    return infer_lex_snapshot_label(cards_path, texts_path)


def _shard_index(doc_id: str, shard_count: int) -> int:
    return lex_pre_shard_index(doc_id, shard_count)


def _pass_name(status: str) -> str | None:
    return lex_pre_shard_pass_name(status)


def _serialize_doc(doc: NPADocument) -> bytes:
    payload = {
        "doc_id": doc.card.doc_id,
        "reestr_code": doc.card.reestr_code,
        "date_acc": doc.card.date_acc,
        "reestr_date": doc.card.reestr_date,
        "status": doc.card.status,
        "doc_type": doc.card.doc_type,
        "name": doc.card.name,
        "publisher": list(doc.card.publisher),
        "number": doc.card.number,
        "publication": list(doc.card.publication),
        "keywords": list(doc.card.keywords),
        "reg_date": doc.card.reg_date,
        "reg_number": doc.card.reg_number,
        "text": doc.text,
        "text_length": len(doc.text),
    }
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


@dataclass
class ShardStats:
    docs: int = 0
    text_chars: int = 0
    jsonl_bytes: int = 0
    statuses: Counter[str] = field(default_factory=Counter)

    def to_json(self, compressed_bytes: int) -> dict[str, object]:
        avg_text_chars = round(self.text_chars / self.docs, 2) if self.docs else 0.0
        return {
            "docs": self.docs,
            "text_chars": self.text_chars,
            "jsonl_bytes": self.jsonl_bytes,
            "compressed_bytes": compressed_bytes,
            "avg_text_chars": avg_text_chars,
            "statuses": dict(self.statuses),
        }


@dataclass
class ShardWriter:
    path: Path
    temp_path: Path
    compressor: zstd.ZstdCompressionWriter
    raw_stream: TextIO
    stats: ShardStats = field(default_factory=ShardStats)
    closed: bool = field(default=False, init=False)

    def write(self, doc: NPADocument) -> None:
        encoded = _serialize_doc(doc)
        self.compressor.write(encoded)
        self.stats.docs += 1
        self.stats.text_chars += len(doc.text)
        self.stats.jsonl_bytes += len(encoded)
        self.stats.statuses[doc.card.status] += 1

    def close(self, *, publish: bool) -> None:
        if self.closed:
            return
        try:
            self.compressor.flush(zstd.FLUSH_FRAME)
            self.compressor.close()
        finally:
            self.raw_stream.close()
            self.closed = True
        if publish:
            os.replace(self.temp_path, self.path)
        else:
            self.temp_path.unlink(missing_ok=True)


def _open_writers(
    output_root: Path,
    *,
    shard_count: int,
    compression_level: int,
) -> dict[tuple[str, int], ShardWriter]:
    writers: dict[tuple[str, int], ShardWriter] = {}
    try:
        for pass_name in ("current", "historical"):
            pass_dir = output_root / pass_name
            pass_dir.mkdir(parents=True, exist_ok=True)
            for shard_idx in range(shard_count):
                path = pass_dir / f"shard_{shard_idx:02d}_of_{shard_count:02d}.jsonl.zst"
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=pass_dir,
                    prefix=f".{path.stem}.",
                    suffix=".tmp",
                    delete=False,
                ) as handle:
                    temp_path = Path(handle.name)
                raw = temp_path.open("wb")
                cctx = zstd.ZstdCompressor(level=compression_level, threads=-1)
                writers[(pass_name, shard_idx)] = ShardWriter(
                    path=path,
                    temp_path=temp_path,
                    compressor=cctx.stream_writer(raw),
                    raw_stream=raw,
                )
    except Exception:
        for writer in writers.values():
            try:
                writer.close(publish=False)
            except Exception:
                pass
        raise
    return writers


def _summarize_pass(
    pass_name: str,
    writers: dict[tuple[str, int], ShardWriter],
    shard_count: int,
) -> dict[str, object]:
    shard_entries: list[dict[str, object]] = []
    docs_values: list[int] = []
    chars_values: list[int] = []
    bytes_values: list[int] = []

    for shard_idx in range(shard_count):
        writer = writers[(pass_name, shard_idx)]
        compressed_bytes = writer.path.stat().st_size if writer.path.exists() else 0
        shard_payload = writer.stats.to_json(compressed_bytes=compressed_bytes)
        shard_payload["shard_index"] = shard_idx
        shard_payload["path"] = str(writer.path)
        shard_entries.append(shard_payload)
        docs_values.append(writer.stats.docs)
        chars_values.append(writer.stats.text_chars)
        bytes_values.append(compressed_bytes)

    total_docs = sum(docs_values)
    total_chars = sum(chars_values)
    total_bytes = sum(bytes_values)
    mean_docs = (total_docs / shard_count) if shard_count else 0.0
    mean_chars = (total_chars / shard_count) if shard_count else 0.0
    mean_bytes = (total_bytes / shard_count) if shard_count else 0.0

    return {
        "total_docs": total_docs,
        "total_text_chars": total_chars,
        "total_compressed_bytes": total_bytes,
        "shards": shard_entries,
        "balance": {
            "docs_min": min(docs_values) if docs_values else 0,
            "docs_max": max(docs_values) if docs_values else 0,
            "docs_spread_pct_of_mean": round(
                (((max(docs_values) - min(docs_values)) / mean_docs) * 100.0) if mean_docs else 0.0,
                2,
            ),
            "text_chars_min": min(chars_values) if chars_values else 0,
            "text_chars_max": max(chars_values) if chars_values else 0,
            "text_chars_spread_pct_of_mean": round(
                (((max(chars_values) - min(chars_values)) / mean_chars) * 100.0)
                if mean_chars
                else 0.0,
                2,
            ),
            "compressed_bytes_min": min(bytes_values) if bytes_values else 0,
            "compressed_bytes_max": max(bytes_values) if bytes_values else 0,
            "compressed_bytes_spread_pct_of_mean": round(
                (((max(bytes_values) - min(bytes_values)) / mean_bytes) * 100.0)
                if mean_bytes
                else 0.0,
                2,
            ),
        },
    }


def run(
    cards_path: Path,
    texts_path: Path,
    output_root: Path,
    *,
    shard_count: int,
    compression_level: int,
) -> Path:
    if shard_count <= 0:
        raise ValueError("--shard-count must be positive")
    writers = _open_writers(
        output_root,
        shard_count=shard_count,
        compression_level=compression_level,
    )
    skipped_other_status = Counter()
    processed = 0
    publish_outputs = False

    try:
        for doc in iter_documents(cards_path, texts_path):
            pass_name = _pass_name(doc.card.status)
            if pass_name is None:
                skipped_other_status[doc.card.status] += 1
                continue

            shard_idx = _shard_index(doc.card.doc_id, shard_count)
            writers[(pass_name, shard_idx)].write(doc)
            processed += 1

            if processed % 10_000 == 0:
                print(f"Processed {processed:,} joined docs ...", flush=True)
        publish_outputs = True
    finally:
        for writer in writers.values():
            writer.close(publish=publish_outputs)

    summary = {
        "cards_path": str(cards_path),
        "texts_path": str(texts_path),
        "snapshot_label": _infer_snapshot_label(cards_path, texts_path),
        "shard_count": shard_count,
        "compression_level": compression_level,
        "processed_docs": processed,
        "skipped_other_statuses": dict(skipped_other_status),
        "passes": {
            "current": _summarize_pass("current", writers, shard_count),
            "historical": _summarize_pass("historical", writers, shard_count),
        },
    }
    summary_path = output_root / "summary.json"
    atomic_write_json(summary_path, summary)
    return summary_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, required=True, help="Path to edrnpa_cards XML")
    parser.add_argument("--texts", type=Path, required=True, help="Path to edrnpa_texts XML")
    parser.add_argument(
        "--output-root", type=Path, required=True, help="Output directory for pre-sharded manifests"
    )
    parser.add_argument(
        "--shard-count", type=int, default=6, help="Number of output shards per pass"
    )
    parser.add_argument("--compression-level", type=int, default=6, help="zstd compression level")
    args = parser.parse_args(argv)

    args.output_root.mkdir(parents=True, exist_ok=True)
    summary_path = run(
        args.cards,
        args.texts,
        args.output_root,
        shard_count=args.shard_count,
        compression_level=args.compression_level,
    )
    print(f"Summary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
