"""Runtime-safe read and material-owner API for Legal Data Forge artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, SupportsFloat, SupportsIndex

from ._lazy import lazy_dir, load_lazy_export

if TYPE_CHECKING:
    import duckdb

    from polisyos.data_forge.domains.legal import (
        LEGAL_BATCH_RUNTIME_MODULE as LEGAL_BATCH_RUNTIME_MODULE,
    )
    from polisyos.data_forge.domains.legal import (
        LegalShadowArtifact as LegalShadowArtifact,
    )
    from polisyos.data_forge.domains.legal import (
        LegalShadowBundle as LegalShadowBundle,
    )
    from polisyos.data_forge.domains.legal import (
        LegalShadowDiff as LegalShadowDiff,
    )
    from polisyos.data_forge.domains.legal import (
        LegalStageManifest as LegalStageManifest,
    )
    from polisyos.data_forge.domains.legal import (
        compare_lex_shadow_bundles as compare_lex_shadow_bundles,
    )
    from polisyos.data_forge.domains.legal import (
        load_lex_shadow_bundle as load_lex_shadow_bundle,
    )
    from polisyos.data_forge.domains.legal.batch.amendment_metrics import (
        collect_amendment_quality_metrics as collect_amendment_quality_metrics,
    )
    from polisyos.data_forge.domains.legal.batch.benchmark_fixtures import (
        LegalSearchBenchmarkCase as LegalSearchBenchmarkCase,
    )
    from polisyos.data_forge.domains.legal.batch.benchmark_fixtures import (
        legal_search_benchmark_cases as legal_search_benchmark_cases,
    )
    from polisyos.data_forge.domains.legal.batch.claim_bridge import (
        export_normative_claim_sets as export_normative_claim_sets,
    )
    from polisyos.data_forge.domains.legal.batch.config import (
        BatchConfig as BatchConfig,
    )
    from polisyos.data_forge.domains.legal.batch.pipeline import (
        run_batch_pipeline as run_batch_pipeline,
    )
    from polisyos.data_forge.domains.legal.batch.progress import (
        ProgressTracker as ProgressTracker,
    )
    from polisyos.data_forge.domains.legal.batch.spo_client import (
        GonkaClientPool as GonkaClientPool,
    )
    from polisyos.data_forge.domains.legal.batch.spo_prompts import (
        SPO_LIGHT_BATCH_SYSTEM_PROMPT as SPO_LIGHT_BATCH_SYSTEM_PROMPT,
    )
    from polisyos.data_forge.domains.legal.batch.spo_prompts import (
        SPO_LIGHT_SYSTEM_PROMPT as SPO_LIGHT_SYSTEM_PROMPT,
    )
    from polisyos.data_forge.domains.legal.batch.spo_prompts import (
        build_spo_light_batch_user_prompt as build_spo_light_batch_user_prompt,
    )
    from polisyos.data_forge.domains.legal.batch.spo_prompts import (
        build_spo_light_user_prompt as build_spo_light_user_prompt,
    )
    from polisyos.data_forge.domains.legal.batch.spo_utils import (
        _group_items_by_request_budget as _group_items_by_request_budget,
    )
    from polisyos.data_forge.domains.legal.batch.xml_parser import (
        NPADocument as NPADocument,
    )
    from polisyos.data_forge.domains.legal.batch.xml_parser import (
        iter_documents as iter_documents,
    )
    from polisyos.data_forge.domains.legal.corpus.index import (
        DocSourcePropsV1 as DocSourcePropsV1,
    )
    from polisyos.data_forge.domains.legal.corpus.index import (
        ProvisionEntryV1 as ProvisionEntryV1,
    )
    from polisyos.data_forge.domains.legal.corpus.index import (
        ProvisionIndexV1 as ProvisionIndexV1,
    )
    from polisyos.data_forge.domains.legal.corpus.index import (
        VersionEntryV1 as VersionEntryV1,
    )
    from polisyos.data_forge.domains.legal.corpus.index import (
        VersionIndexV1 as VersionIndexV1,
    )
    from polisyos.data_forge.domains.legal.corpus.index import (
        load_doc_source_props as load_doc_source_props,
    )
    from polisyos.data_forge.domains.legal.corpus.index import (
        load_provision_index as load_provision_index,
    )
    from polisyos.data_forge.domains.legal.corpus.index import (
        load_version_index as load_version_index,
    )
    from polisyos.data_forge.domains.legal.corpus.versioning import (
        resolve_active_version as resolve_active_version,
    )
    from polisyos.data_forge.domains.legal.embedding_projection import (
        LEGAL_EMBEDDING_PROJECTION_RULE_VERSION as LEGAL_EMBEDDING_PROJECTION_RULE_VERSION,
    )
    from polisyos.data_forge.domains.legal.embedding_projection import (
        entity_embedding_text as entity_embedding_text,
    )
    from polisyos.data_forge.domains.legal.embedding_projection import (
        fact_embedding_text as fact_embedding_text,
    )
    from polisyos.data_forge.domains.legal.embedding_projection import (
        provision_embedding_text as provision_embedding_text,
    )
    from polisyos.data_forge.domains.legal.runtime_material import (
        LEGAL_RUNTIME_MATERIAL_RULE_VERSION as LEGAL_RUNTIME_MATERIAL_RULE_VERSION,
    )
    from polisyos.data_forge.domains.legal.runtime_material import (
        LegalRuntimeMaterialError as LegalRuntimeMaterialError,
    )
    from polisyos.data_forge.domains.legal.runtime_material import (
        LegalRuntimeMaterialHandle as LegalRuntimeMaterialHandle,
    )
    from polisyos.data_forge.domains.legal.runtime_material import (
        LegalRuntimeMaterialOwner as LegalRuntimeMaterialOwner,
    )
    from polisyos.data_forge.domains.legal.source_relation import (
        CURRENT_LEGAL_SOURCE_RELATION_DISPOSITION as CURRENT_LEGAL_SOURCE_RELATION_DISPOSITION,
    )
    from polisyos.data_forge.domains.legal.source_relation import (
        LEGAL_SOURCE_RELATION_REFUSAL as LEGAL_SOURCE_RELATION_REFUSAL,
    )
    from polisyos.data_forge.domains.legal.source_relation import (
        LEGAL_SOURCE_RELATION_REFUSAL_CODE as LEGAL_SOURCE_RELATION_REFUSAL_CODE,
    )
    from polisyos.data_forge.domains.legal.source_relation import (
        LegalCandidateTrustTier as LegalCandidateTrustTier,
    )
    from polisyos.data_forge.domains.legal.source_relation import (
        LegalSourceRelationDisposition as LegalSourceRelationDisposition,
    )
    from polisyos.data_forge.domains.legal.source_relation import (
        LegalSourceRelationRefusal as LegalSourceRelationRefusal,
    )
    from polisyos.data_forge.domains.legal.source_relation import (
        LegalSourceRelationRefusalCode as LegalSourceRelationRefusalCode,
    )
    from polisyos.data_forge.domains.legal.source_relation import (
        LegalSourceRelationStatus as LegalSourceRelationStatus,
    )
    from polisyos.data_forge.domains.legal.source_relation import (
        LegalSourceRelationVerificationMissingError as LegalSourceRelationVerificationMissingError,
    )
    from polisyos.data_forge.domains.legal.source_relation import (
        current_legal_source_relation_disposition as current_legal_source_relation_disposition,
    )
    from polisyos.data_forge.domains.legal.source_relation import (
        require_legal_source_relation_verification as require_legal_source_relation_verification,
    )
    from polisyos.data_forge.kernel.embeddings import (
        EmbeddingGenerationRef as EmbeddingGenerationRef,
    )
    from polisyos.data_forge.kernel.embeddings import (
        derive_encoder_identity as derive_encoder_identity,
    )
    from polisyos.data_forge.kernel.embeddings import (
        embedding_generation_matches_encoder as embedding_generation_matches_encoder,
    )
    from polisyos.data_forge.kernel.embeddings import (
        hnsw_index_matches_vectors as hnsw_index_matches_vectors,
    )
    from polisyos.data_forge.kernel.embeddings import (
        legal_embedding_generator_rule_version as legal_embedding_generator_rule_version,
    )
    from polisyos.data_forge.kernel.embeddings import (
        resolve_embedding_generation as resolve_embedding_generation,
    )
    from polisyos.data_forge.kernel.io.generation_basis import (
        GenerationIdentity as GenerationIdentity,
    )
    from polisyos.data_forge.kernel.io.generation_basis import (
        generation_basis_matches_members as generation_basis_matches_members,
    )

_LEGAL_DOMAIN = "polisyos.data_forge.domains.legal"
_LEGAL_SOURCE_RELATION_MODULE = f"{_LEGAL_DOMAIN}.source_relation"
_EXPORTS = {
    "CURRENT_LEGAL_SOURCE_RELATION_DISPOSITION": _LEGAL_SOURCE_RELATION_MODULE,
    "LEGAL_SOURCE_RELATION_REFUSAL": _LEGAL_SOURCE_RELATION_MODULE,
    "LEGAL_SOURCE_RELATION_REFUSAL_CODE": _LEGAL_SOURCE_RELATION_MODULE,
    "LegalCandidateTrustTier": _LEGAL_SOURCE_RELATION_MODULE,
    "LegalSourceRelationDisposition": _LEGAL_SOURCE_RELATION_MODULE,
    "LegalSourceRelationRefusal": _LEGAL_SOURCE_RELATION_MODULE,
    "LegalSourceRelationRefusalCode": _LEGAL_SOURCE_RELATION_MODULE,
    "LegalSourceRelationStatus": _LEGAL_SOURCE_RELATION_MODULE,
    "LegalSourceRelationVerificationMissingError": _LEGAL_SOURCE_RELATION_MODULE,
    "current_legal_source_relation_disposition": _LEGAL_SOURCE_RELATION_MODULE,
    "require_legal_source_relation_verification": _LEGAL_SOURCE_RELATION_MODULE,
    "BatchConfig": "polisyos.data_forge.domains.legal.batch.config",
    "EmbeddingGenerationRef": "polisyos.data_forge.kernel.embeddings",
    "LEGAL_EMBEDDING_PROJECTION_RULE_VERSION": (
        "polisyos.data_forge.domains.legal.embedding_projection"
    ),
    "GenerationIdentity": "polisyos.data_forge.kernel.io.generation_basis",
    "LegalSearchBenchmarkCase": ("polisyos.data_forge.domains.legal.batch.benchmark_fixtures"),
    "LEGAL_RUNTIME_MATERIAL_RULE_VERSION": ("polisyos.data_forge.domains.legal.runtime_material"),
    "LegalRuntimeMaterialError": ("polisyos.data_forge.domains.legal.runtime_material"),
    "LegalRuntimeMaterialHandle": ("polisyos.data_forge.domains.legal.runtime_material"),
    "LegalRuntimeMaterialOwner": ("polisyos.data_forge.domains.legal.runtime_material"),
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
    "collect_amendment_quality_metrics": (
        "polisyos.data_forge.domains.legal.batch.amendment_metrics"
    ),
    "derive_encoder_identity": "polisyos.data_forge.kernel.embeddings",
    "embedding_generation_matches_encoder": "polisyos.data_forge.kernel.embeddings",
    "generation_basis_matches_members": "polisyos.data_forge.kernel.io.generation_basis",
    "entity_embedding_text": "polisyos.data_forge.domains.legal.embedding_projection",
    "fact_embedding_text": "polisyos.data_forge.domains.legal.embedding_projection",
    "export_normative_claim_sets": "polisyos.data_forge.domains.legal.batch.claim_bridge",
    "iter_documents": "polisyos.data_forge.domains.legal.batch.xml_parser",
    "legal_search_benchmark_cases": ("polisyos.data_forge.domains.legal.batch.benchmark_fixtures"),
    "load_doc_source_props": "polisyos.data_forge.domains.legal.corpus.index",
    "load_lex_shadow_bundle": _LEGAL_DOMAIN,
    "load_provision_index": "polisyos.data_forge.domains.legal.corpus.index",
    "load_version_index": "polisyos.data_forge.domains.legal.corpus.index",
    "hnsw_index_matches_vectors": "polisyos.data_forge.kernel.embeddings",
    "legal_embedding_generator_rule_version": "polisyos.data_forge.kernel.embeddings",
    "provision_embedding_text": "polisyos.data_forge.domains.legal.embedding_projection",
    "resolve_embedding_generation": "polisyos.data_forge.kernel.embeddings",
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

    require_relation = load_lazy_export(
        "require_legal_source_relation_verification",
        exports={
            "require_legal_source_relation_verification": (
                "polisyos.data_forge.domains.legal.source_relation"
            )
        },
        module_name=__name__,
        namespace=globals(),
    )
    require_relation()

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


def _confidence_as_float(value: object) -> float:
    """Preserve the read API's ``float(value or 0.0)`` DuckDB scalar behavior."""
    if not value:
        return 0.0
    if isinstance(value, (str, bytes, bytearray, SupportsFloat, SupportsIndex)):
        return float(value)
    raise TypeError(
        f"float() argument must be a string or a real number, not '{type(value).__name__}'"
    )


def _to_legal_graph_fact(row: tuple[object, ...]) -> LegalKnowledgeGraphFact:
    return LegalKnowledgeGraphFact(
        fact_id=str(row[0] or ""),
        subject_name=str(row[1] or ""),
        predicate=str(row[2] or ""),
        object_name=str(row[3] or ""),
        fact_text=str(row[4] or ""),
        confidence=_confidence_as_float(row[5]),
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


__all__: list[str] = sorted((*_EXPORTS, "LegalKnowledgeGraphFact", "search_legal_knowledge_graph"))
