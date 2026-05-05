"""Runtime-safe read API for shadow legal Data Forge artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ._lazy import lazy_dir, load_lazy_export

if TYPE_CHECKING:
    import duckdb

_LEGAL_DOMAIN = "polisyos.data_forge.domains.legal"
_EXPORTS = {
    "BatchConfig": "polisyos.data_forge.domains.legal.batch.config",
    "DocSourcePropsV1": "polisyos.data_forge.domains.legal.corpus.index",
    "GonkaClientPool": "polisyos.data_forge.domains.legal.batch.spo_client",
    "LEGAL_BATCH_RUNTIME_MODULE": _LEGAL_DOMAIN,
    "LegalShadowArtifact": _LEGAL_DOMAIN,
    "LegalShadowBundle": _LEGAL_DOMAIN,
    "LegalShadowDiff": _LEGAL_DOMAIN,
    "LegalStageManifest": _LEGAL_DOMAIN,
    "NPADocument": "polisyos.data_forge.domains.legal.batch.xml_parser",
    "ProgressTracker": "polisyos.data_forge.domains.legal.batch.progress",
    "ProvisionEntryV1": "polisyos.data_forge.domains.legal.corpus.index",
    "ProvisionIndexV1": "polisyos.data_forge.domains.legal.corpus.index",
    "SPO_LIGHT_BATCH_SYSTEM_PROMPT": "polisyos.data_forge.domains.legal.batch.spo_prompts",
    "SPO_LIGHT_SYSTEM_PROMPT": "polisyos.data_forge.domains.legal.batch.spo_prompts",
    "VersionEntryV1": "polisyos.data_forge.domains.legal.corpus.index",
    "VersionIndexV1": "polisyos.data_forge.domains.legal.corpus.index",
    "_group_items_by_request_budget": "polisyos.data_forge.domains.legal.batch.spo_utils",
    "build_spo_light_batch_user_prompt": "polisyos.data_forge.domains.legal.batch.spo_prompts",
    "build_spo_light_user_prompt": "polisyos.data_forge.domains.legal.batch.spo_prompts",
    "compare_lex_shadow_bundles": _LEGAL_DOMAIN,
    "export_normative_claim_sets": "polisyos.data_forge.domains.legal.batch.claim_bridge",
    "iter_documents": "polisyos.data_forge.domains.legal.batch.xml_parser",
    "load_doc_source_props": "polisyos.data_forge.domains.legal.corpus.index",
    "load_lex_shadow_bundle": _LEGAL_DOMAIN,
    "load_provision_index": "polisyos.data_forge.domains.legal.corpus.index",
    "load_version_index": "polisyos.data_forge.domains.legal.corpus.index",
    "resolve_active_version": "polisyos.data_forge.domains.legal.corpus.versioning",
    "run_batch_pipeline": "polisyos.data_forge.domains.legal.batch.pipeline",
}

_FACT_SELECT_FIELDS: tuple[tuple[str, str], ...] = (
    ("fact_id", "''"),
    ("subject_en", "''"),
    ("predicate", "''"),
    ("object_en", "''"),
    ("fact_text", "''"),
    ("confidence", "0.0"),
    ("norm_type", "''"),
    ("action_canon", "''"),
    ("norm_type_canon", "''"),
    ("condition_text_uk", "''"),
    ("exception_text_uk", "''"),
    ("procedure_text_uk", "''"),
    ("thresholds_json", "'[]'"),
    ("source_quote_uk", "''"),
    ("doc_name", "''"),
    ("doc_reestr_code", "''"),
    ("provision_anchor", "''"),
    ("provision_citation", "''"),
)


@dataclass(frozen=True, slots=True)
class LegalKnowledgeGraphFact:
    """Runtime-facing Legal graph fact returned by the Data Forge read API."""

    fact_id: str
    subject_name: str
    predicate: str
    object_name: str
    fact_text: str
    confidence: float
    norm_type: str
    action_canon: str = ""
    norm_type_canon: str = ""
    condition_text_uk: str = ""
    exception_text_uk: str = ""
    procedure_text_uk: str = ""
    thresholds_json: str = ""
    source_quote_uk: str = ""
    doc_name: str = ""
    doc_reestr_code: str = ""
    provision_anchor: str = ""
    provision_citation: str = ""
    similarity: float = 1.0


def __getattr__(name: str) -> object:
    """Lazily resolve legal exports without importing domain internals at module import."""
    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())


def __dir__() -> list[str]:
    """Return public legal read_api names without resolving exports."""
    return lazy_dir(globals(), _EXPORTS)


def search_legal_knowledge_graph(
    *,
    output_dir: str | Path,
    query: str,
    top_k: int,
) -> list[LegalKnowledgeGraphFact]:
    """Search a published Legal knowledge graph without importing legacy Lex facades."""

    import duckdb

    output_path = Path(output_dir)
    con = duckdb.connect(str(output_path / "lex_knowledge_graph.duckdb"), read_only=True)
    try:
        table_name = _select_default_fact_table(con)
        available_columns = _table_columns(con, table_name)
        selected = _select_sql(available_columns=available_columns)
        search_columns = [
            column_name
            for column_name in (
                "fact_text",
                "subject_en",
                "object_en",
                "condition_text_uk",
                "exception_text_uk",
                "source_quote_uk",
            )
            if column_name in available_columns
        ]
        if not search_columns:
            return []
        text_clause = " OR ".join(f"{column_name} ILIKE ?" for column_name in search_columns)
        pattern = f"%{query}%"
        rows = con.execute(
            f"""
            SELECT {selected}
            FROM {table_name}
            WHERE ({text_clause})
            LIMIT ?
            """,  # noqa: S608 - table and selected columns are fixed by this module.
            [*[pattern] * len(search_columns), top_k],
        ).fetchall()
        return [_to_legal_graph_fact(row) for row in rows]
    finally:
        con.close()


def _select_default_fact_table(con: duckdb.DuckDBPyConnection) -> str:
    if _table_exists(con, "lex_fact_grounded"):
        return "lex_fact_grounded"
    return "lex_facts"


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [table_name],
    ).fetchone()
    return bool(row and row[0])


def _table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    rows = con.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = ?
        """,
        [table_name],
    ).fetchall()
    return {str(row[0]) for row in rows}


def _select_sql(*, available_columns: set[str]) -> str:
    selected: list[str] = []
    for column_name, default_sql in _FACT_SELECT_FIELDS:
        if column_name in available_columns:
            selected.append(column_name)
        else:
            selected.append(f"{default_sql} AS {column_name}")
    return ", ".join(selected)


def _to_legal_graph_fact(row: tuple[object, ...]) -> LegalKnowledgeGraphFact:
    return LegalKnowledgeGraphFact(
        fact_id=str(row[0] or ""),
        subject_name=str(row[1] or ""),
        predicate=str(row[2] or ""),
        object_name=str(row[3] or ""),
        fact_text=str(row[4] or ""),
        confidence=float(row[5] or 0.0),
        norm_type=str(row[6] or ""),
        action_canon=str(row[7] or ""),
        norm_type_canon=str(row[8] or ""),
        condition_text_uk=str(row[9] or ""),
        exception_text_uk=str(row[10] or ""),
        procedure_text_uk=str(row[11] or ""),
        thresholds_json=str(row[12] or ""),
        source_quote_uk=str(row[13] or ""),
        doc_name=str(row[14] or ""),
        doc_reestr_code=str(row[15] or ""),
        provision_anchor=str(row[16] or ""),
        provision_citation=str(row[17] or ""),
        similarity=1.0,
    )


__all__ = sorted((*_EXPORTS, "LegalKnowledgeGraphFact", "search_legal_knowledge_graph"))
