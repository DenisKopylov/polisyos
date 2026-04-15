#!/usr/bin/env python3
"""Build priority queue manifests for the Lex production pipeline."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tools._lib.imports import repo_root_from
from typing import Any, TextIO

import zstandard as zstd

WORKSPACE_ROOT = repo_root_from(__file__)
DEFAULT_PRE_SHARDED_ROOT = WORKSPACE_ROOT / "data" / "data_lex" / "pre_sharded"
APPENDIX_SIGNALS = (
    "додат",
    "зміни, що вносяться",
    "изменения, которые вносятся",
    "порядок",
    "положення",
    "положение",
    "перелік",
    "форма",
    "правила",
    "інструкц",
    "инструкц",
    "методик",
    "тариф",
    "регламент",
)
KMU_SIGNALS = (
    "кабінет міністрів",
    "кабинет министров",
    "кму",
)


@dataclass(frozen=True)
class Candidate:
    doc_id: str
    queue_name: str
    status_pass: str
    category: str
    family: str
    text_length: int
    is_kmu: bool
    appendix_risk: bool
    weight: int


@dataclass
class QueueSummary:
    queue_name: str
    status_pass: str
    shard_count: int
    total_docs: int = 0
    total_weight: int = 0
    total_chars: int = 0
    shard_docs: list[int] = field(default_factory=list)
    shard_weight: list[int] = field(default_factory=list)
    shard_chars: list[int] = field(default_factory=list)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item is not None)
    return str(value)


def _doc_category(payload: dict[str, Any]) -> str:
    doc_type = _normalize_text(payload.get("doc_type")).lower()
    if "кодекс" in doc_type:
        return "code"
    if "конституц" in doc_type:
        return "constitution"
    if "закон" in doc_type:
        return "law"
    if "міжнарод" in doc_type and "догов" in doc_type:
        return "treaty"
    if "угод" in doc_type and ("міжнарод" in doc_type or "міждерж" in doc_type):
        return "treaty"
    if "протокол" in doc_type:
        return "protocol"
    if "постан" in doc_type:
        return "resolution"
    if "розпоряджен" in doc_type:
        return "directive"
    if "указ" in doc_type:
        return "decree"
    if "наказ" in doc_type:
        return "order"
    if "рішен" in doc_type or "решени" in doc_type:
        return "decision"
    return "other"


def _doc_family(category: str) -> str:
    if category in {"constitution", "law", "code"}:
        return "law"
    if category in {"treaty", "protocol"}:
        return "treaty_protocol"
    if category == "order":
        return "order"
    if category in {"resolution", "decree", "decision", "directive"}:
        return "decree_resolution"
    return "other"


def _is_kmu(payload: dict[str, Any]) -> bool:
    publisher = _normalize_text(payload.get("publisher")).lower()
    return any(token in publisher for token in KMU_SIGNALS)


def _appendix_risk(payload: dict[str, Any]) -> bool:
    haystack = (
        _normalize_text(payload.get("name")).lower()
        + " "
        + _normalize_text(payload.get("doc_type")).lower()
    )
    return any(token in haystack for token in APPENDIX_SIGNALS)


def _candidate_weight(*, text_length: int, family: str, appendix_risk: bool) -> int:
    weight = max(1, math.ceil(max(text_length, 1) / 2000))
    if family == "order":
        weight += 2
    elif family == "decree_resolution":
        weight += 1
    if appendix_risk:
        weight += 2
    if text_length > 20_000:
        weight += 2
    elif text_length > 10_000:
        weight += 1
    return weight


def _queue_name_for_current(payload: dict[str, Any], *, family: str, text_length: int, is_kmu: bool) -> str:
    if family in {"law", "treaty_protocol"}:
        return "queue1_core_current"
    if (is_kmu and text_length <= 5_000) or text_length <= 2_000:
        return "queue2_fast_useful_current"
    return "queue3_tail_current"


def _queue_sort_key(candidate: Candidate) -> tuple[Any, ...]:
    if candidate.queue_name == "queue1_core_current":
        family_rank = 0 if candidate.category in {"code", "constitution"} else 1 if candidate.family == "law" else 2
        return (family_rank, -candidate.text_length, candidate.doc_id)
    if candidate.queue_name == "queue2_fast_useful_current":
        return (candidate.text_length, 0 if candidate.is_kmu else 1, candidate.doc_id)
    if candidate.queue_name == "queue3_tail_current":
        if candidate.text_length <= 5_000:
            bucket = 0
        elif candidate.text_length <= 10_000:
            bucket = 1
        elif candidate.text_length <= 20_000:
            bucket = 2
        else:
            bucket = 3
        return (bucket, 1 if candidate.appendix_risk else 0, candidate.text_length, candidate.doc_id)
    return (candidate.text_length, candidate.doc_id)


def _iter_manifest_records(manifest_dir: Path) -> tuple[Path, str, dict[str, Any]]:
    for manifest_path in sorted(manifest_dir.glob("*.jsonl.zst")):
        with manifest_path.open("rb") as fh:
            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(fh) as reader:
                text_reader: TextIO = io.TextIOWrapper(reader, encoding="utf-8")
                for line in text_reader:
                    raw = line.strip()
                    if not raw:
                        continue
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise ValueError(f"Expected JSON object in {manifest_path}")
                    yield manifest_path, raw, payload


def _gcloud_ls(pattern: str) -> list[str]:
    completed = subprocess.run(
        ["gcloud", "storage", "ls", "-r", pattern],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").lower()
        if "no URLs matched" in stderr or "matched no objects" in stderr or "one or more URLs matched no objects" in stderr:
            return []
        raise RuntimeError(f"gcloud storage ls failed for {pattern}: {completed.stderr.strip()}")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _processed_doc_ids(cache_roots: list[str]) -> set[str]:
    doc_ids: set[str] = set()
    for root in cache_roots:
        normalized = root.rstrip("/")
        for uri in _gcloud_ls(f"{normalized}/**/domains/*.json"):
            name = Path(uri).name
            if name.endswith(".json"):
                doc_ids.add(name[:-5])
    return doc_ids


def _assign_queue_shards(
    candidates: list[Candidate],
    *,
    shard_count: int,
) -> tuple[dict[str, int], QueueSummary]:
    queue_name = candidates[0].queue_name
    status_pass = candidates[0].status_pass
    shard_payloads: list[list[Candidate]] = [[] for _ in range(shard_count)]
    shard_weight = [0 for _ in range(shard_count)]
    shard_chars = [0 for _ in range(shard_count)]
    assignments: dict[str, int] = {}

    for candidate in sorted(candidates, key=lambda item: (-item.weight, -item.text_length, item.doc_id)):
        shard_index = min(
            range(shard_count),
            key=lambda idx: (shard_weight[idx], shard_chars[idx], len(shard_payloads[idx]), idx),
        )
        shard_payloads[shard_index].append(candidate)
        shard_weight[shard_index] += candidate.weight
        shard_chars[shard_index] += candidate.text_length

    for shard_index, payloads in enumerate(shard_payloads):
        payloads.sort(key=_queue_sort_key)
        for candidate in payloads:
            assignments[candidate.doc_id] = shard_index

    summary = QueueSummary(
        queue_name=queue_name,
        status_pass=status_pass,
        shard_count=shard_count,
        total_docs=len(candidates),
        total_weight=sum(item.weight for item in candidates),
        total_chars=sum(item.text_length for item in candidates),
        shard_docs=[len(items) for items in shard_payloads],
        shard_weight=shard_weight,
        shard_chars=shard_chars,
    )
    return assignments, summary


@contextlib.contextmanager
def _zstd_writer(path: Path) -> TextIO:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        cctx = zstd.ZstdCompressor(level=6)
        with cctx.stream_writer(fh) as writer:
            text_writer = io.TextIOWrapper(writer, encoding="utf-8")
            try:
                yield text_writer
            finally:
                text_writer.flush()


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-label", required=True)
    parser.add_argument("--campaign-label", required=True)
    parser.add_argument("--pre-sharded-root", type=Path, default=DEFAULT_PRE_SHARDED_ROOT)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--gcs-output-root", default="")
    parser.add_argument("--current-processed-cache-root", action="append", default=[])
    parser.add_argument("--history-processed-cache-root", action="append", default=[])
    parser.add_argument("--queue1-shards", type=int, default=6)
    parser.add_argument("--queue2-shards", type=int, default=6)
    parser.add_argument("--queue3-shards", type=int, default=6)
    parser.add_argument("--history-shards", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    snapshot_root = args.pre_sharded_root / args.snapshot_label
    current_root = snapshot_root / "current"
    history_root = snapshot_root / "historical"
    output_root = args.output_root / args.snapshot_label / args.campaign_label
    output_root.mkdir(parents=True, exist_ok=True)

    current_processed = _processed_doc_ids(list(args.current_processed_cache_root))
    history_processed = _processed_doc_ids(list(args.history_processed_cache_root))

    current_candidates: dict[str, Candidate] = {}
    history_candidates: dict[str, Candidate] = {}

    for _manifest_path, _raw, payload in _iter_manifest_records(current_root):
        doc_id = str(payload.get("doc_id") or "")
        if not doc_id or doc_id in current_processed:
            continue
        category = _doc_category(payload)
        family = _doc_family(category)
        text_length = int(payload.get("text_length") or len(_normalize_text(payload.get("text"))))
        is_kmu = _is_kmu(payload)
        appendix_risk = _appendix_risk(payload)
        queue_name = _queue_name_for_current(payload, family=family, text_length=text_length, is_kmu=is_kmu)
        current_candidates[doc_id] = Candidate(
            doc_id=doc_id,
            queue_name=queue_name,
            status_pass="current",
            category=category,
            family=family,
            text_length=text_length,
            is_kmu=is_kmu,
            appendix_risk=appendix_risk,
            weight=_candidate_weight(text_length=text_length, family=family, appendix_risk=appendix_risk),
        )

    for _manifest_path, _raw, payload in _iter_manifest_records(history_root):
        doc_id = str(payload.get("doc_id") or "")
        if not doc_id or doc_id in history_processed:
            continue
        category = _doc_category(payload)
        family = _doc_family(category)
        text_length = int(payload.get("text_length") or len(_normalize_text(payload.get("text"))))
        appendix_risk = _appendix_risk(payload)
        history_candidates[doc_id] = Candidate(
            doc_id=doc_id,
            queue_name="history_parallel",
            status_pass="history",
            category=category,
            family=family,
            text_length=text_length,
            is_kmu=False,
            appendix_risk=appendix_risk,
            weight=max(1, math.ceil(max(text_length, 1) / 4000)),
        )

    queue_specs = {
        "queue1_core_current": args.queue1_shards,
        "queue2_fast_useful_current": args.queue2_shards,
        "queue3_tail_current": args.queue3_shards,
        "history_parallel": args.history_shards,
    }

    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in current_candidates.values():
        grouped[candidate.queue_name].append(candidate)
    for candidate in history_candidates.values():
        grouped[candidate.queue_name].append(candidate)

    assignments: dict[str, tuple[str, int]] = {}
    queue_summaries: dict[str, QueueSummary] = {}
    for queue_name, shard_count in queue_specs.items():
        queue_candidates = grouped.get(queue_name, [])
        if not queue_candidates:
            continue
        queue_assignments, summary = _assign_queue_shards(queue_candidates, shard_count=shard_count)
        queue_summaries[queue_name] = summary
        assignments.update({doc_id: (queue_name, shard_index) for doc_id, shard_index in queue_assignments.items()})

    writers: dict[tuple[str, int], contextlib.AbstractContextManager[TextIO]] = {}
    handles: dict[tuple[str, int], TextIO] = {}
    try:
        for queue_name, summary in queue_summaries.items():
            for shard_index in range(summary.shard_count):
                shard_name = f"shard_{shard_index:02d}_of_{summary.shard_count:02d}.jsonl.zst"
                shard_path = output_root / queue_name / shard_name
                manager = _zstd_writer(shard_path)
                writers[(queue_name, shard_index)] = manager
                handles[(queue_name, shard_index)] = manager.__enter__()

        for _manifest_path, raw, payload in _iter_manifest_records(current_root):
            doc_id = str(payload.get("doc_id") or "")
            assignment = assignments.get(doc_id)
            if assignment is None:
                continue
            queue_name, shard_index = assignment
            if queue_summaries[queue_name].status_pass != "current":
                continue
            handles[(queue_name, shard_index)].write(raw + "\n")

        for _manifest_path, raw, payload in _iter_manifest_records(history_root):
            doc_id = str(payload.get("doc_id") or "")
            assignment = assignments.get(doc_id)
            if assignment is None:
                continue
            queue_name, shard_index = assignment
            if queue_summaries[queue_name].status_pass != "history":
                continue
            handles[(queue_name, shard_index)].write(raw + "\n")
    finally:
        while writers:
            _, manager = writers.popitem()
            manager.__exit__(None, None, None)

    for queue_name, summary in queue_summaries.items():
        _write_summary(
            output_root / queue_name / "summary.json",
            {
                "queue_name": queue_name,
                "status_pass": summary.status_pass,
                "shard_count": summary.shard_count,
                "total_docs": summary.total_docs,
                "total_weight": summary.total_weight,
                "total_chars": summary.total_chars,
                "shard_docs": summary.shard_docs,
                "shard_weight": summary.shard_weight,
                "shard_chars": summary.shard_chars,
            },
        )

    _write_summary(
        output_root / "campaign_summary.json",
        {
            "snapshot_label": args.snapshot_label,
            "campaign_label": args.campaign_label,
            "current_processed_doc_ids": len(current_processed),
            "history_processed_doc_ids": len(history_processed),
            "queues": {queue_name: asdict(summary) for queue_name, summary in queue_summaries.items()},
        },
    )

    if args.gcs_output_root:
        subprocess.run(
            ["gcloud", "storage", "rsync", "-r", str(output_root), args.gcs_output_root.rstrip("/")],
            check=True,
        )

    print(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
