"""Read-only Ukraine/NPA pre-sharding contracts shared with Legal cutover."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, cast

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel

UkraineLexShardPass = Literal["current", "historical"]

CURRENT_STATUSES = frozenset({"Чинний", "Не набрав чинності"})
HISTORICAL_STATUSES = frozenset(
    {"Втратив чинність", "Втратив чинність частково", "Дію призупинено"}
)


class UkraineLexShardEntry(DataForgeModel):
    """One shard entry emitted by the NPA pre-sharding helper."""

    shard_index: int = Field(ge=0)
    path: str = Field(min_length=1)
    docs: int = Field(ge=0)
    text_chars: int = Field(ge=0)
    jsonl_bytes: int = Field(ge=0)
    compressed_bytes: int = Field(ge=0)
    avg_text_chars: float = Field(ge=0.0)
    statuses: dict[str, int] = Field(default_factory=dict)


class UkraineLexShardPassSummary(DataForgeModel):
    """Aggregate counts for one current/historical pre-shard pass."""

    total_docs: int = Field(ge=0)
    total_text_chars: int = Field(ge=0)
    total_compressed_bytes: int = Field(ge=0)
    shards: tuple[UkraineLexShardEntry, ...] = Field(default_factory=tuple)
    balance: dict[str, float | int] = Field(default_factory=dict)


class UkraineLexPreShardSummary(DataForgeModel):
    """Typed summary for immutable NPA pre-sharded corpus artifacts."""

    cards_path: str = Field(min_length=1)
    texts_path: str = Field(min_length=1)
    snapshot_label: str = Field(min_length=1)
    shard_count: int = Field(ge=1)
    compression_level: int = Field(ge=1)
    processed_docs: int = Field(ge=0)
    skipped_other_statuses: dict[str, int] = Field(default_factory=dict)
    passes: dict[UkraineLexShardPass, UkraineLexShardPassSummary]


class UkraineLexPreShardDiff(DataForgeModel):
    """Small differential report for two pre-shard summaries."""

    processed_docs_delta: int
    changed_passes: tuple[UkraineLexShardPass, ...] = Field(default_factory=tuple)
    shard_doc_deltas: dict[str, int] = Field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        """Return whether the summaries differ in document counts."""

        return bool(self.processed_docs_delta or self.changed_passes or self.shard_doc_deltas)


def infer_lex_snapshot_label(cards_path: str | Path, texts_path: str | Path) -> str:
    """Infer the snapshot suffix used by the pre-sharding helper."""

    for path in (Path(cards_path), Path(texts_path)):
        stem = path.stem
        if "_" in stem:
            return stem.rsplit("_", 1)[-1]
    return "snapshot"


def lex_pre_shard_index(doc_id: str, shard_count: int) -> int:
    """Assign a document id to the same deterministic pre-shard bucket as Legal."""

    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    digest = hashlib.sha1(doc_id.encode("utf-8"), usedforsecurity=False).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def lex_pre_shard_pass_name(status: str) -> UkraineLexShardPass | None:
    """Map an NPA status to the current/historical pre-shard pass."""

    if status in CURRENT_STATUSES:
        return "current"
    if status in HISTORICAL_STATUSES:
        return "historical"
    return None


def load_lex_pre_shard_summary(path: str | Path) -> UkraineLexPreShardSummary:
    """Load a pre-shard ``summary.json`` file or a directory containing it."""

    summary_path = Path(path)
    if summary_path.is_dir():
        summary_path = summary_path / "summary.json"
    payload = cast("dict[str, object]", json.loads(summary_path.read_text(encoding="utf-8")))
    return UkraineLexPreShardSummary.model_validate(payload)


def compare_lex_pre_shard_summaries(
    baseline: UkraineLexPreShardSummary,
    candidate: UkraineLexPreShardSummary,
) -> UkraineLexPreShardDiff:
    """Compare document-count semantics for two pre-shard summaries."""

    changed_passes: list[UkraineLexShardPass] = []
    shard_doc_deltas: dict[str, int] = {}
    for pass_name in ("current", "historical"):
        left = baseline.passes[pass_name]
        right = candidate.passes[pass_name]
        if left.total_docs != right.total_docs:
            changed_passes.append(pass_name)
        left_docs = {item.shard_index: item.docs for item in left.shards}
        right_docs = {item.shard_index: item.docs for item in right.shards}
        for shard_index in sorted(set(left_docs) | set(right_docs)):
            delta = right_docs.get(shard_index, 0) - left_docs.get(shard_index, 0)
            if delta:
                shard_doc_deltas[f"{pass_name}/shard_{shard_index:02d}"] = delta
    return UkraineLexPreShardDiff(
        processed_docs_delta=candidate.processed_docs - baseline.processed_docs,
        changed_passes=tuple(changed_passes),
        shard_doc_deltas=shard_doc_deltas,
    )


__all__ = [
    "CURRENT_STATUSES",
    "HISTORICAL_STATUSES",
    "UkraineLexPreShardDiff",
    "UkraineLexPreShardSummary",
    "UkraineLexShardEntry",
    "UkraineLexShardPass",
    "UkraineLexShardPassSummary",
    "compare_lex_pre_shard_summaries",
    "infer_lex_snapshot_label",
    "lex_pre_shard_index",
    "lex_pre_shard_pass_name",
    "load_lex_pre_shard_summary",
]
