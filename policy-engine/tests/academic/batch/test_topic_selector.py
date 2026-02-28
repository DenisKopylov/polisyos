from __future__ import annotations

import asyncio

from polisyos.academic.openalex.selector import select_topic_works
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
