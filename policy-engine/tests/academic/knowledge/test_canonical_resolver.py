from __future__ import annotations

import duckdb

from polisyos.academic.knowledge.canonical_resolver import CanonicalVariableResolver
from polisyos.academic.knowledge.skg_store import ensure_skg_schema


def test_canonical_resolver_prefers_exact_and_synonym_matches(tmp_path) -> None:
    db_path = tmp_path / "resolver.duckdb"
    with duckdb.connect(str(db_path)) as con:
        ensure_skg_schema(con)
        con.execute(
            """
            INSERT INTO ac_skg_variable_synonyms(synonym, canonical_name, method, confidence, approved)
            VALUES ('fiscal revenue', 'tax.revenue', 'manual', 1.0, TRUE)
            """
        )

    with duckdb.connect(str(db_path), read_only=False) as con:
        resolver = CanonicalVariableResolver.from_connection(con)
        exact = resolver.resolve("tax.revenue")
        synonym = resolver.resolve("fiscal revenue")

    assert exact.canonical_name == "tax_revenue"
    assert exact.method in {"exact", "exact_alias"}
    assert synonym.canonical_name == "tax.revenue"
    assert synonym.method == "synonym"


def test_canonical_resolver_uses_local_embedding_similarity(tmp_path) -> None:
    db_path = tmp_path / "resolver.duckdb"
    with duckdb.connect(str(db_path)) as con:
        ensure_skg_schema(con)
        resolver = CanonicalVariableResolver.from_connection(con)
        result = resolver.resolve("government effectiveness")
        resolver.persist_resolution(con, result)

        cached = con.execute(
            "SELECT canonical_name, approved FROM ac_skg_canonization_cache WHERE raw_name = ?",
            ["government effectiveness"],
        ).fetchone()

    assert result.canonical_name in {
        "institutional_quality.government_effectiveness",
        "governance.government_effectiveness",
    }
    assert result.method in {"embedding", "exact", "synonym"}
    assert cached is not None


def test_canonical_resolver_hybrid_similarity_handles_pluralized_near_match() -> None:
    resolver = CanonicalVariableResolver(
        approved_names={"tax.revenue", "education_outcomes.test_scores"},
        approved_synonyms={},
    )

    result = resolver.resolve("tax revenues")

    assert result.canonical_name == "tax.revenue"
    assert result.method == "embedding"
    assert result.confidence >= 0.75


def test_canonical_resolver_uses_runtime_registry_for_policyos_terms() -> None:
    resolver = CanonicalVariableResolver.from_connection(duckdb.connect(":memory:"))

    result = resolver.resolve(
        "teacher_coaching_program",
        need_type="causal_edge",
        runtime_priority=True,
    )

    assert result.canonical_name == "education.teacher_coaching"
    assert result.approved is True
    assert result.method in {"synonym", "embedding", "exact"}
