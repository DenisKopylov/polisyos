from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.scientist.agent.failure_index import (
    FailureIndexEntry,
    FailurePatternIndex,
    build_failure_signature,
)


def test_failure_pattern_index_add_and_search() -> None:
    index = FailurePatternIndex()
    signature = build_failure_signature(
        error_code="EMPTY_TARGET",
        category="feasibility",
        location="policy_spec.interventions[0].target",
        message="Target matches 0 agents",
        source_step="critic",
        domain="fiscal",
    )

    for run in range(5):
        index.add_failure(
            signature_id=signature,
            error_code="EMPTY_TARGET",
            category="feasibility",
            domain="fiscal",
            source_step="critic",
            normalized_location="policy_spec.interventions[].target",
            normalized_message="target matches <n> agents",
            remediation_advice="Broaden selector",
            card_ref=f"sha256:{run:064d}",
        )

    results = index.search(
        domain="fiscal",
        error_code="EMPTY_TARGET",
        category="feasibility",
        location="policy_spec.interventions[9].target",
        message="Target matches 0 agents",
        min_occurrence=3,
    )

    assert results
    entry, score = results[0]
    assert entry.occurrence_count == 5
    assert score >= 0.5


def test_failure_pattern_index_garbage_collect() -> None:
    index = FailurePatternIndex()
    now = datetime.now(UTC)
    old_time = (now - timedelta(days=31)).isoformat()

    index.entries = [
        FailureIndexEntry(
            signature_id="sig_old",
            error_code="OLD",
            category="schema",
            domain="fiscal",
            source_step="critic",
            normalized_location="x",
            normalized_message="old",
            remediation_advice="",
            occurrence_count=1,
            first_seen=old_time,
            last_seen=old_time,
        ),
        FailureIndexEntry(
            signature_id="sig_new",
            error_code="NEW",
            category="schema",
            domain="fiscal",
            source_step="critic",
            normalized_location="x",
            normalized_message="new",
            remediation_advice="",
            occurrence_count=1,
            first_seen=now.isoformat(),
            last_seen=now.isoformat(),
        ),
    ]

    removed = index.garbage_collect(max_age_days=30)
    assert removed == 1
    assert len(index.entries) == 1
    assert index.entries[0].error_code == "NEW"
