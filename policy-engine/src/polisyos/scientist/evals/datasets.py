"""Dataset split taxonomy and freshness policy for Scientist benchmark authority."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistryEntry

__all__ = [
    "BENCHMARK_AUTHORITY_SPLIT_NAMES",
    "BenchmarkDatasetDescriptor",
    "BenchmarkSplitName",
    "BenchmarkStalenessPolicy",
    "BenchmarkVisibility",
    "entry_staleness_reasons",
    "stale_entries_for_refs",
]


class BenchmarkSplitName(StrEnum):
    """Phase 1.5 split names documented by the benchmark authority."""

    PUBLIC = "public"
    PRIVATE = "private"
    HIDDEN_HOLDOUT = "hidden_holdout"
    ROTATING_CHALLENGE = "rotating_challenge"
    SENTINEL = "sentinel"
    ADVERSARIAL = "adversarial"
    SELECTION = "selection"


class BenchmarkVisibility(StrEnum):
    """Visibility category for benchmark data and refs."""

    PUBLIC = "public"
    PRIVATE = "private"
    HIDDEN = "hidden"


BENCHMARK_AUTHORITY_SPLIT_NAMES: tuple[str, ...] = tuple(
    item.value for item in BenchmarkSplitName
)


class BenchmarkDatasetDescriptor(BaseModel):
    """Metadata for one policy-domain benchmark pack or split."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    split_name: BenchmarkSplitName
    visibility: BenchmarkVisibility
    artifact_ref: ArtifactRef | None = None
    benchmark_revision: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkStalenessPolicy(BaseModel):
    """Expiry windows for benchmark splits used in default-enable decisions."""

    model_config = ConfigDict(extra="forbid")

    ttl_days_by_split: dict[str, int] = Field(
        default_factory=lambda: {
            BenchmarkSplitName.SELECTION.value: 180,
            BenchmarkSplitName.PUBLIC.value: 180,
            BenchmarkSplitName.PRIVATE.value: 120,
            BenchmarkSplitName.HIDDEN_HOLDOUT.value: 120,
            BenchmarkSplitName.ROTATING_CHALLENGE.value: 30,
            BenchmarkSplitName.SENTINEL.value: 90,
            BenchmarkSplitName.ADVERSARIAL.value: 60,
        }
    )

    def ttl_for_split(self, split_type: str) -> int:
        """Return max acceptable age in days for a split."""

        return int(self.ttl_days_by_split.get(str(split_type), 90))


def stale_entries_for_refs(
    entries: list[BenchmarkRegistryEntry],
    refs: list[ArtifactRef],
    *,
    policy: BenchmarkStalenessPolicy | None = None,
    now: datetime | None = None,
) -> list[str]:
    """Return stable stale labels for entries matching the given artifact refs."""

    ref_ids = {str(ref.artifact_id) for ref in refs}
    active_policy = policy or BenchmarkStalenessPolicy()
    active_now = (now or datetime.now(UTC)).astimezone(UTC)
    stale: list[str] = []
    for entry in entries:
        if str(entry.artifact_ref.artifact_id) not in ref_ids:
            continue
        stale.extend(entry_staleness_reasons(entry, policy=active_policy, now=active_now))
    return sorted(set(stale))


def entry_staleness_reasons(
    entry: BenchmarkRegistryEntry,
    *,
    policy: BenchmarkStalenessPolicy | None = None,
    now: datetime | None = None,
) -> list[str]:
    """Return staleness reasons for one registry entry."""

    active_policy = policy or BenchmarkStalenessPolicy()
    active_now = (now or datetime.now(UTC)).astimezone(UTC)
    reasons: list[str] = []
    metadata = dict(entry.metadata or {})
    revision_status = str(metadata.get("revision_status") or "").strip().lower()
    if revision_status in {"stale", "retired", "revoked"}:
        reasons.append(_stale_label(entry, f"revision_{revision_status}"))
    expires_at = _parse_datetime(metadata.get("expires_at"))
    if expires_at is not None and expires_at < active_now:
        reasons.append(_stale_label(entry, "expired"))
    created_at = entry.created_at.astimezone(UTC)
    ttl_days = active_policy.ttl_for_split(entry.split_type)
    if created_at + timedelta(days=ttl_days) < active_now:
        reasons.append(_stale_label(entry, f"ttl_exceeded_{ttl_days}d"))
    return reasons


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _stale_label(entry: BenchmarkRegistryEntry, reason: str) -> str:
    return f"{entry.split_type}:{entry.suite_id or '<no-suite>'}:{reason}"
