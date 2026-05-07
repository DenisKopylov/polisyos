from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.scientist.evals.datasets import (
    BENCHMARK_AUTHORITY_SPLIT_NAMES,
    BenchmarkSplitName,
    entry_staleness_reasons,
)
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistryEntry

from .test_authority import _ref


def test_split_taxonomy_includes_required_phase1_5_names() -> None:
    assert {
        "public",
        "private",
        "hidden_holdout",
        "rotating_challenge",
        "sentinel",
        "adversarial",
    }.issubset(set(BENCHMARK_AUTHORITY_SPLIT_NAMES))


def test_rotating_challenge_entry_becomes_stale_after_ttl() -> None:
    entry = BenchmarkRegistryEntry(
        split_type=BenchmarkSplitName.ROTATING_CHALLENGE.value,
        artifact_ref=_ref("rotating"),
        suite_id="rotating-v1",
        created_at=datetime.now(UTC) - timedelta(days=45),
    )

    reasons = entry_staleness_reasons(entry)

    assert reasons == ["rotating_challenge:rotating-v1:ttl_exceeded_30d"]
