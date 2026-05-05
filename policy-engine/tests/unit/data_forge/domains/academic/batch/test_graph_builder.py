"""Tests for academic graph builder (DuckDB schema + bulk INSERT)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import duckdb
from polisyos.data_forge.domains.academic.batch.graph_builder import build_graph
from polisyos.data_forge.domains.academic.knowledge.types import EstimateCandidate, WorkRecord


def _make_work(idx: int) -> WorkRecord:
    return WorkRecord(
        id=f"w-{idx}",
        title=f"Study {idx}: Effect of minimum wage",
        abstract=f"This study examines the effect of minimum wage on employment. Study {idx}.",
        year=2020 + (idx % 5),
        cited_by_count=100 + idx * 10,
        journal="American Economic Review",
        is_oa=True,
        full_text_url=f"http://example.com/paper-{idx}.pdf",
        concepts=[{"display_name": "Economics", "level": 0, "score": 0.9}],
        study_design="did",
        trust_score=0.75,
        estimates=[
            EstimateCandidate(
                value=-0.1 + idx * 0.01,
                ci_low=-0.2,
                ci_high=0.0,
                unit="ratio",
                context_snippet="elasticity estimate",
                pattern_name="elasticity_of",
                confidence=0.7,
                variable_hint="min_wage_employment",
            ),
        ],
    )


def test_build_graph_creates_tables() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_scholar.duckdb"
        works = [_make_work(i) for i in range(3)]

        stats = build_graph(
            records=iter(works),
            db_path=db_path,
            insert_batch_size=2,
        )

        assert stats.works == 3
        assert stats.estimates >= 3
        assert stats.claims == 0  # No causal claims in this test data

        con = duckdb.connect(str(db_path), read_only=True)
        work_count = con.execute("SELECT count(*) FROM ac_works").fetchone()[0]
        est_count = con.execute("SELECT count(*) FROM ac_parameter_estimates").fetchone()[0]
        con.close()

        assert work_count == 3
        assert est_count >= 3


def test_build_graph_empty() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_scholar.duckdb"
        stats = build_graph(records=iter([]), db_path=db_path)
        assert stats.works == 0
        assert stats.estimates == 0
