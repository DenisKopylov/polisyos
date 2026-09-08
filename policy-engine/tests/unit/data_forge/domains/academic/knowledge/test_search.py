"""Evidence-contributing populations for numerical literature priors."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import duckdb
import pytest

from polisyos.data_forge.domains.academic.knowledge.search import ScholarKnowledgeGraph
from polisyos.data_forge.domains.academic.knowledge.skg_query import ParameterCandidate, SKGQuery
from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    EVIDENCE_WEIGHTS,
    ensure_skg_schema,
)
from polisyos.ir.analytics.literature import EvidenceParameter, EvidenceStrength


def _graph(tmp_path: Path, rows: list[tuple[float, str]]) -> ScholarKnowledgeGraph:
    """Seed authored test data only; all consumers open the fixture read-only."""
    db_path = tmp_path / "fixture.duckdb"
    with duckdb.connect(str(db_path)) as con:
        ensure_skg_schema(con)
        if rows:
            con.executemany(
                "INSERT INTO ac_skg_simulation_parameters "
                "(numeric_id, openalex_id, canonical_name, estimate_type, point_estimate, "
                "evidence_strength, confidence_interval_json) "
                "VALUES (?, 'W', 'macro.x', 'ate', ?, ?, '[0,2]')",
                [(str(i), value, strength) for i, (value, strength) in enumerate(rows)],
            )
        # A real legacy fallback exists: returning None cannot be a missing-table accident.
        con.execute("CREATE TABLE ac_works AS SELECT 'W' AS id, 'Legacy' AS title, 2026 AS year")
        con.execute(
            "CREATE TABLE ac_parameter_estimates AS SELECT "
            "'old' AS id, 'W' AS work_id, 'macro.x' AS variable_name, 777.0 AS estimate, "
            "NULL::DOUBLE AS ci_low, NULL::DOUBLE AS ci_high, NULL::DOUBLE AS std_error, "
            "'' AS unit, '' AS domain, 'rct' AS study_design, NULL::BIGINT AS sample_size, "
            "'' AS country, NULL::INTEGER AS period_start, NULL::INTEGER AS period_end, "
            "1.0 AS trust_score, '' AS raw_context"
        )
    return ScholarKnowledgeGraph(db_path, tmp_path / "index")


@pytest.mark.parametrize("zero_base_only", [False, True])
def test_all_unknown_numeric_prior_is_not_rescued_by_equal_weights_or_legacy(
    tmp_path, monkeypatch, zero_base_only
) -> None:
    """Catch both the existing unknown prior and its all-zero equal-weight rescue."""
    if zero_base_only:
        monkeypatch.setitem(EVIDENCE_WEIGHTS, "unknown", 0.0)
    graph = _graph(tmp_path, [(10.0, "unknown"), (20.0, "unknown")])
    try:
        assert graph.get_parameter_prior("macro.x") is None
        assert (
            graph.get_parameter_prior("macro.x", prefer_simulation_ready=False).prior_mean == 777.0
        )
        query = SKGQuery(db_path=graph._db_path, index_dir=graph._index_dir)
        try:
            assert [c.parameter.evidence_strength for c in query.query_parameters("macro.x")] == [
                EvidenceStrength.UNKNOWN,
                EvidenceStrength.UNKNOWN,
            ]
        finally:
            query.close()
    finally:
        graph.close()


def test_mixed_numeric_prior_excludes_unknown_from_every_statistic(tmp_path) -> None:
    """Catch zero-weight outliers still changing quantiles, study count or best class."""
    graph = _graph(
        tmp_path,
        [(-1000.0, "unknown"), (10.0, "theoretical"), (20.0, "theoretical"), (2000.0, "unknown")],
    )
    try:
        prior = graph.get_parameter_prior("macro.x")
        assert prior is not None
        assert prior.model_dump() == {
            "variable": "macro.x",
            "prior_mean": 15.0,
            "prior_std": 5.0,
            "prior_low": 11.0,
            "prior_high": 19.0,
            "n_studies": 2,
            "best_design": "theoretical",
            "as_calibration_prior": {"distribution": "normal", "mean": 15.0, "std": 5.0},
        }
    finally:
        graph.close()


def test_numeric_prior_mixed_boundary_preserves_unknown_and_absent_inputs(
    tmp_path, monkeypatch
) -> None:
    """Catch absent/alien adapter input either raising or joining the prior's population."""
    graph = _graph(tmp_path, [])
    strengths = [
        EvidenceStrength.THEORETICAL,
        EvidenceStrength.UNKNOWN,
        None,
        SimpleNamespace(value="alien"),
    ]
    candidates = []
    for value, strength in zip([10.0, -1000.0, 2000.0, 3000.0], strengths, strict=True):
        payload = EvidenceParameter(name="macro.x", value=value).model_dump()
        # Deliberate boundary negative; do not loosen EvidenceParameter's validated contract.
        parameter = cast(
            "EvidenceParameter", SimpleNamespace(**{**payload, "evidence_strength": strength})
        )
        candidates.append(ParameterCandidate(parameter=parameter, source_context=None))
    monkeypatch.setattr(SKGQuery, "query_parameters", lambda *args, **kwargs: candidates)
    try:
        prior = graph.get_parameter_prior("macro.x")
        assert prior is not None
        assert prior.prior_mean == prior.prior_low == prior.prior_high == 10.0
        assert prior.prior_std == 0.01
        assert prior.n_studies == 1
        assert prior.best_design == "theoretical"
        assert [c.parameter.evidence_strength for c in candidates] == strengths
    finally:
        graph.close()


def test_no_numeric_candidates_preserves_separate_trust_prior(tmp_path) -> None:
    """Catch overbroad removal of the independent legacy trust-weighted prior path."""
    graph = _graph(tmp_path, [])
    try:
        prior = graph.get_parameter_prior("macro.x")
        assert prior is not None
        assert prior.prior_mean == 777.0
        assert prior.n_studies == 1
        assert prior.best_design == "rct"
    finally:
        graph.close()
