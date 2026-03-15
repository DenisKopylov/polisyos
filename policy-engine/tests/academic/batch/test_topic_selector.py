from __future__ import annotations

import asyncio
import json

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.topic_select import _aggregate_global_candidates
from polisyos.academic.openalex.selector import SelectedTopicWork, select_topic_works
from polisyos.academic.openalex.topic_catalog import TopicEntry


class _FakeClient:
    async def list_works(self, req):  # type: ignore[no-untyped-def]
        # Return deterministic synthetic rows irrespective of filters.
        rows = []
        for i in range(220):
            rows.append(
                {
                    "id": f"https://openalex.org/W{i}",
                    "title": f"Effect of policy {i}",
                    "abstract_inverted_index": {"effect": [0], "policy": [1], "employment": [2]},
                    "cited_by_count": 200 - (i % 200),
                    "fwci": 1.0 + (i % 5),
                    "publication_year": 2020 if i % 3 == 0 else 2014,
                    "type": "article" if i % 11 else "review",
                    "open_access": {"is_oa": i % 2 == 0},
                    "has_fulltext": i % 4 == 0,
                    "authorships": [{"author": {"id": f"https://openalex.org/A{i % 50}"}}],
                    "primary_location": {"source": {"id": f"https://openalex.org/S{i % 40}", "display_name": f"Journal {i % 40}"}},
                }
            )
        return {"results": rows, "meta": {"count": len(rows)}}


def test_select_topic_works_returns_target() -> None:
    topic = TopicEntry(
        topic_id="T1",
        display_name="Policy Topic",
        description="",
        works_count=10_000,
        cited_by_count=100_000,
        policy_block="b",
        policy_subblock="s",
        score_core=1,
        score_domain=1,
        score_context=1,
        source_file="f.csv",
    )
    selected = asyncio.run(
        select_topic_works(
            _FakeClient(),
            topic=topic,
            run_id="run1",
            target_per_topic=150,
            per_page=200,
        )
    )
    assert len(selected) == 150
    assert selected[0].rank == 1
    assert selected[-1].rank == 150
    assert all(s.topic_id == "T1" for s in selected)


def test_aggregate_global_candidates_uses_demand_backlog_boost(tmp_path) -> None:
    backlog_path = tmp_path / "need_backlog.jsonl"
    backlog_path.write_text(
        json.dumps(
            {
                "need_id": "edge_need:1",
                "need_type": "causal_edge_need",
                "priority_weight": 1.0,
                "terms": ["tax compliance"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        selected_unique_budget=1,
        demand_backlog_path=backlog_path,
        demand_backlog_boost=0.25,
    )
    topic = TopicEntry(
        topic_id="T1",
        display_name="Fiscal policy",
        description="",
        works_count=10_000,
        cited_by_count=100_000,
        policy_block="policy core",
        policy_subblock="taxation",
        score_core=1,
        score_domain=0,
        score_context=0,
        source_file="f.csv",
    )
    selected = [
        SelectedTopicWork(
            run_id="run1",
            topic_id="T1",
            topic_display_name="Fiscal policy",
            topic_policy_block="policy core",
            topic_policy_subblock="taxation",
            source_file="f.csv",
            work_id="W_low",
            rank=2,
            selection_score=0.81,
            batch_origin="test",
            selected_at="2026-03-13T00:00:00Z",
            work={
                "id": "W_low",
                "title": "Tax compliance reform under improved enforcement",
                "abstract_inverted_index": {"tax": [0], "compliance": [1], "reform": [2]},
            },
        ),
        SelectedTopicWork(
            run_id="run1",
            topic_id="T1",
            topic_display_name="Fiscal policy",
            topic_policy_block="policy core",
            topic_policy_subblock="taxation",
            source_file="f.csv",
            work_id="W_high",
            rank=1,
            selection_score=0.90,
            batch_origin="test",
            selected_at="2026-03-13T00:00:00Z",
            work={
                "id": "W_high",
                "title": "Macroeconomic commentary note",
                "abstract_inverted_index": {"macro": [0], "commentary": [1]},
            },
        ),
    ]
    topic_lookup = {topic.topic_id: topic}

    selected_global, bucket_counts, demand_metrics = _aggregate_global_candidates(
        config,
        selected,
        topic_lookup,
    )

    assert sum(bucket_counts.values()) == 1
    assert demand_metrics["selected_with_backlog_signal"] == 1
    assert selected_global[0]["work_id"] == "W_low"
    assert selected_global[0]["matched_need_ids"] == ["edge_need:1"]


def test_aggregate_global_candidates_handles_missing_primary_location_source(tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        selected_unique_budget=1,
    )
    topic = TopicEntry(
        topic_id="T1",
        display_name="Fiscal policy",
        description="",
        works_count=10_000,
        cited_by_count=100_000,
        policy_block="policy core",
        policy_subblock="taxation",
        score_core=1,
        score_domain=0,
        score_context=0,
        source_file="f.csv",
    )
    selected = [
        SelectedTopicWork(
            run_id="run1",
            topic_id="T1",
            topic_display_name="Fiscal policy",
            topic_policy_block="policy core",
            topic_policy_subblock="taxation",
            source_file="f.csv",
            work_id="W_null_source",
            rank=1,
            selection_score=0.9,
            batch_origin="test",
            selected_at="2026-03-13T00:00:00Z",
            work={
                "id": "W_null_source",
                "title": "Tax administration and compliance",
                "primary_location": {"source": None},
            },
        )
    ]

    selected_global, bucket_counts, _ = _aggregate_global_candidates(
        config,
        selected,
        {topic.topic_id: topic},
    )

    assert sum(bucket_counts.values()) == 1
    assert selected_global[0]["work_id"] == "W_null_source"
