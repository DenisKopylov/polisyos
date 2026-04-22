#!/usr/bin/env python3
"""Split Queue 3 current manifests into five priority waves with six shards."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TextIO

import zstandard as zstd
from tools._lib.imports import repo_root_from

WORKSPACE_ROOT = repo_root_from(__file__)
REPO_ROOT = WORKSPACE_ROOT.parent

APPENDIX_SIGNALS = (
    "додат",
    "зміни, що вносяться",
    "изменения, которые вносятся",
    "перелік",
    "форма",
    "правила",
    "інструкц",
    "инструкц",
    "методик",
    "тариф",
    "регламент",
)
PROGRAM_SIGNALS = (
    "програми",
    "плану заходів",
    "план заходів",
    "план пріоритетних дій",
    "бюджетної декларації",
    "бюджетна декларація",
)
SANCTION_SIGNALS = (
    "санкці",
    "обмежувальних заходів",
    "спеціальних економічних",
)
AGENCY_SIGNALS = (
    "комітет",
    "коміс",
    "служб",
    "агентств",
    "фонд",
    "казначейств",
    "інспекц",
    "адміністрац",
)

WAVE_SPECS = {
    "queue3_wave1_state_core_current": {
        "priority_rank": 1,
        "description": "State core: VRU, codes, President non-sanctions, NBU.",
        "rule_summary": (
            "All VRU acts, exact codes, President acts except sanctions, "
            "all NBU acts."
        ),
    },
    "queue3_wave2_exec_priority_current": {
        "priority_rank": 2,
        "description": "High-value executive: concise modern CMU acts.",
        "rule_summary": (
            "CMU 2014+ acts under 40k chars, excluding sanctions and heavy "
            "programmatic/appended acts."
        ),
    },
    "queue3_wave3_fast_regulatory_current": {
        "priority_rank": 3,
        "description": "Fast useful regulation: modern ministry and agency acts.",
        "rule_summary": (
            "Modern ministry/agency acts under 25k chars, plus short non-heavy "
            "CMU acts not already captured."
        ),
    },
    "queue3_wave4_general_tail_current": {
        "priority_rank": 4,
        "description": "General current tail: useful but lower-priority remainder.",
        "rule_summary": (
            "All remaining current acts not classified as state core, executive "
            "priority, fast regulation, or explicit defer-last."
        ),
    },
    "queue3_wave5_defer_heavy_current": {
        "priority_rank": 5,
        "description": "Defer last: legacy, sanctions, giant appendixed acts.",
        "rule_summary": (
            "Pre-1992 legacy, sanctions, very heavy appendixed/programmatic acts, "
            "and giant technical rulebooks."
        ),
    },
}


@dataclass(frozen=True)
class Candidate:
    doc_id: str
    wave_name: str
    text_length: int
    weight: int
    sort_bucket: int
    doc_type: str
    publisher_label: str
    year: int | None
    appendix_risk: bool
    sanctions_risk: bool


@dataclass
class WaveSummary:
    wave_name: str
    priority_rank: int
    description: str
    rule_summary: str
    shard_count: int
    total_docs: int = 0
    total_weight: int = 0
    total_chars: int = 0
    shard_docs: list[int] = field(default_factory=list)
    shard_weight: list[int] = field(default_factory=list)
    shard_chars: list[int] = field(default_factory=list)
    top_doc_types: list[dict[str, Any]] = field(default_factory=list)
    top_publishers: list[dict[str, Any]] = field(default_factory=list)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item is not None)
    return str(value)


def _publisher_label(payload: dict[str, Any]) -> str:
    publishers = payload.get("publisher")
    if isinstance(publishers, list) and publishers:
        return " | ".join(str(item) for item in publishers if item is not None)
    text = _normalize_text(publishers)
    return text or "unknown"


def _year_of(payload: dict[str, Any]) -> int | None:
    raw = _normalize_text(payload.get("date_acc")).strip()
    if len(raw) >= 4 and raw[-4:].isdigit():
        return int(raw[-4:])
    return None


def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(token in haystack for token in needles)


def _appendix_risk(payload: dict[str, Any]) -> bool:
    haystack = (
        _normalize_text(payload.get("name")).lower()
        + " "
        + _normalize_text(payload.get("doc_type")).lower()
    )
    return _contains_any(haystack, APPENDIX_SIGNALS)


def _wave_for_queue3(payload: dict[str, Any]) -> tuple[str, int]:
    name = _normalize_text(payload.get("name"))
    lname = name.lower()
    publisher = _publisher_label(payload).lower()
    doc_type = _normalize_text(payload.get("doc_type")).lower()
    text_length = int(payload.get("text_length") or len(_normalize_text(payload.get("text"))))
    year = _year_of(payload)

    is_vru = "верховна рада україни" in publisher
    is_president = "президент україни" in publisher
    is_nbu = "національн" in publisher and "банк" in publisher
    is_cmu = "кабінет міністрів україни" in publisher
    is_ministry = "міністер" in publisher
    is_agency = _contains_any(publisher, AGENCY_SIGNALS)
    is_legacy = year is not None and year < 1992
    is_sanctions = _contains_any(lname, SANCTION_SIGNALS)
    is_program = _contains_any(lname, PROGRAM_SIGNALS)
    is_code = "кодекс україни" in lname or "кодекс" in doc_type
    appendix_risk = _appendix_risk(payload)
    is_heavy = text_length >= 200_000
    is_medium_heavy = text_length >= 80_000

    if is_code:
        return "queue3_wave1_state_core_current", 0
    if is_vru:
        return "queue3_wave1_state_core_current", 1
    if is_president and not is_sanctions:
        return "queue3_wave1_state_core_current", 2
    if is_nbu:
        return "queue3_wave1_state_core_current", 3

    if (
        is_cmu
        and year is not None
        and year >= 2014
        and text_length < 40_000
        and not is_sanctions
        and not is_program
        and not appendix_risk
    ):
        return "queue3_wave2_exec_priority_current", 0 if text_length < 20_000 else 1

    if (
        ((is_ministry or is_agency) and year is not None and year >= 2014 and text_length < 25_000)
        or (is_cmu and text_length < 20_000 and not is_program and not appendix_risk)
    ) and not is_sanctions:
        return "queue3_wave3_fast_regulatory_current", 0 if is_cmu else 1

    if (
        is_legacy
        or is_sanctions
        or is_heavy
        or is_program
        or (appendix_risk and is_medium_heavy)
        or text_length >= 120_000
    ):
        return "queue3_wave5_defer_heavy_current", 0 if is_sanctions else 1

    return "queue3_wave4_general_tail_current", 0 if text_length < 20_000 else 1


def _candidate_weight(payload: dict[str, Any]) -> int:
    text_length = int(payload.get("text_length") or len(_normalize_text(payload.get("text"))))
    weight = max(1, math.ceil(max(text_length, 1) / 2000))
    if _appendix_risk(payload):
        weight += 2
    lname = _normalize_text(payload.get("name")).lower()
    if _contains_any(lname, SANCTION_SIGNALS):
        weight += 3
    if text_length > 20_000:
        weight += 2
    elif text_length > 10_000:
        weight += 1
    return weight


def _iter_manifest_records(source_dir: Path) -> tuple[Path, str, dict[str, Any]]:
    for manifest_path in sorted(source_dir.glob("*.jsonl.zst")):
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


def _wave_sort_key(candidate: Candidate) -> tuple[Any, ...]:
    return (candidate.sort_bucket, candidate.text_length, candidate.doc_id)


def _assign_wave_shards(
    candidates: list[Candidate],
    *,
    shard_count: int,
) -> tuple[dict[str, int], WaveSummary]:
    wave_name = candidates[0].wave_name
    spec = WAVE_SPECS[wave_name]
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
        payloads.sort(key=_wave_sort_key)
        for candidate in payloads:
            assignments[candidate.doc_id] = shard_index

    doc_type_counter = Counter(item.doc_type for item in candidates)
    publisher_counter = Counter(item.publisher_label for item in candidates)
    summary = WaveSummary(
        wave_name=wave_name,
        priority_rank=spec["priority_rank"],
        description=spec["description"],
        rule_summary=spec["rule_summary"],
        shard_count=shard_count,
        total_docs=len(candidates),
        total_weight=sum(item.weight for item in candidates),
        total_chars=sum(item.text_length for item in candidates),
        shard_docs=[len(items) for items in shard_payloads],
        shard_weight=shard_weight,
        shard_chars=shard_chars,
        top_doc_types=[
            {"doc_type": doc_type, "count": count}
            for doc_type, count in doc_type_counter.most_common(10)
        ],
        top_publishers=[
            {"publisher": publisher, "count": count}
            for publisher, count in publisher_counter.most_common(10)
        ],
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
    parser.add_argument("--source-queue-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--wave-shards", type=int, default=6)
    parser.add_argument("--gcs-output-root", default="")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    source_dir = args.source_queue_dir.resolve()
    if not source_dir.exists():
        raise FileNotFoundError(f"Source queue dir does not exist: {source_dir}")

    output_root = (args.output_root / args.snapshot_label / args.campaign_label).resolve()
    if output_root.exists():
        if not args.overwrite:
            raise FileExistsError(f"Output root already exists: {output_root}")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    candidates: dict[str, Candidate] = {}
    total_source_rows = 0
    for _manifest_path, _raw, payload in _iter_manifest_records(source_dir):
        doc_id = str(payload.get("doc_id") or "")
        if not doc_id:
            continue
        total_source_rows += 1
        text_length = int(payload.get("text_length") or len(_normalize_text(payload.get("text"))))
        wave_name, sort_bucket = _wave_for_queue3(payload)
        candidates[doc_id] = Candidate(
            doc_id=doc_id,
            wave_name=wave_name,
            text_length=text_length,
            weight=_candidate_weight(payload),
            sort_bucket=sort_bucket,
            doc_type=_normalize_text(payload.get("doc_type")) or "unknown",
            publisher_label=_publisher_label(payload),
            year=_year_of(payload),
            appendix_risk=_appendix_risk(payload),
            sanctions_risk=_contains_any(_normalize_text(payload.get("name")).lower(), SANCTION_SIGNALS),
        )

    total_source_docs = len(candidates)
    total_source_chars = sum(candidate.text_length for candidate in candidates.values())
    duplicate_source_rows = total_source_rows - total_source_docs

    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates.values():
        grouped[candidate.wave_name].append(candidate)

    assignments: dict[str, tuple[str, int]] = {}
    wave_summaries: dict[str, WaveSummary] = {}
    for wave_name in WAVE_SPECS:
        wave_candidates = grouped.get(wave_name, [])
        if not wave_candidates:
            continue
        wave_assignments, summary = _assign_wave_shards(wave_candidates, shard_count=args.wave_shards)
        wave_summaries[wave_name] = summary
        assignments.update({doc_id: (wave_name, shard_index) for doc_id, shard_index in wave_assignments.items()})

    writers: dict[tuple[str, int], contextlib.AbstractContextManager[TextIO]] = {}
    handles: dict[tuple[str, int], TextIO] = {}
    try:
        for wave_name in WAVE_SPECS:
            for shard_index in range(args.wave_shards):
                shard_name = f"shard_{shard_index:02d}_of_{args.wave_shards:02d}.jsonl.zst"
                shard_path = output_root / wave_name / shard_name
                manager = _zstd_writer(shard_path)
                writers[(wave_name, shard_index)] = manager
                handles[(wave_name, shard_index)] = manager.__enter__()

        for _manifest_path, raw, payload in _iter_manifest_records(source_dir):
            doc_id = str(payload.get("doc_id") or "")
            assignment = assignments.get(doc_id)
            if assignment is None:
                continue
            wave_name, shard_index = assignment
            handles[(wave_name, shard_index)].write(raw + "\n")
    finally:
        while writers:
            _, manager = writers.popitem()
            manager.__exit__(None, None, None)

    for wave_name, summary in wave_summaries.items():
        _write_summary(
            output_root / wave_name / "summary.json",
            {
                "wave_name": wave_name,
                "source_queue_name": source_dir.name,
                "status_pass": "current",
                "priority_rank": summary.priority_rank,
                "description": summary.description,
                "rule_summary": summary.rule_summary,
                "shard_count": summary.shard_count,
                "total_docs": summary.total_docs,
                "total_weight": summary.total_weight,
                "total_chars": summary.total_chars,
                "shard_docs": summary.shard_docs,
                "shard_weight": summary.shard_weight,
                "shard_chars": summary.shard_chars,
                "top_doc_types": summary.top_doc_types,
                "top_publishers": summary.top_publishers,
            },
        )

    total_wave_docs = sum(summary.total_docs for summary in wave_summaries.values())
    total_wave_chars = sum(summary.total_chars for summary in wave_summaries.values())
    if total_wave_docs != total_source_docs or total_wave_chars != total_source_chars:
        raise RuntimeError(
            "Wave totals do not match source totals: "
            f"docs {total_wave_docs} vs {total_source_docs}, "
            f"chars {total_wave_chars} vs {total_source_chars}"
        )

    _write_summary(
        output_root / "campaign_summary.json",
        {
            "snapshot_label": args.snapshot_label,
            "campaign_label": args.campaign_label,
            "source_queue_name": source_dir.name,
            "source_queue_dir": str(source_dir),
            "source_row_count": total_source_rows,
            "source_unique_doc_ids": total_source_docs,
            "source_duplicate_rows": duplicate_source_rows,
            "wave_shard_count": args.wave_shards,
            "total_docs": total_source_docs,
            "total_chars": total_source_chars,
            "waves": {wave_name: asdict(summary) for wave_name, summary in wave_summaries.items()},
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
