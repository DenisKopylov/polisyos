"""End-to-end safety proofs for the split academic claim vocabulary."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PINNED_SNAPSHOT = (
    REPO_ROOT
    / "production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/"
    "scholar_knowledge.duckdb"
)
PINNED_SNAPSHOT_SHA256 = "583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967"
AXIS_FIELDS = (
    "design_family_hint",
    "evidence_strength",
    "claim_extraction_confidence",
    "source_basis",
)
PUBLIC_CLAIM_SYMBOLS = {
    "CausalClaimResult",
    "audit_academic_claim_lineage",
    "find_causal_evidence",
    "get_causal_claims",
    "get_mechanism_evidence",
    "iter_causal_claim_results_v2",
    "load_causal_claim_results_v2",
    "query_claims",
    "search_causal_claims",
}
CENSUS_SYMBOLS = PUBLIC_CLAIM_SYMBOLS | {"REQUIRED_SKG_TABLES"}


class _DeterministicSpanSupportClient:
    async def generate(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        temperature: float | None = None,
        seed: int | None = None,
    ) -> SimpleNamespace:
        del messages, tools, temperature, seed
        return SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(
                    id="task4-span-support",
                    name="layer3_gy_record_span_support_judgment",
                    arguments={
                        "decision": "entails",
                        "confidence": 0.91,
                        "rationale": "deterministic Task-4 fixture",
                    },
                )
            ],
            usage=SimpleNamespace(total_tokens=1),
            raw={"deterministic_replay_key": "task4-vocabulary"},
        )


@dataclass(frozen=True)
class _CensusHit:
    path: str
    line: int
    symbol: str
    operation: str
    disposition: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _axis_payload(value: Any) -> dict[str, object]:
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)
    return {
        key: payload.get(key)
        for field in AXIS_FIELDS
        for key in (field, f"{field}_status")
    }


def _assert_no_generic_strength(value: Any) -> None:
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    if isinstance(payload, dict):
        assert "strength" not in payload
        for nested in payload.values():
            _assert_no_generic_strength(nested)
    elif isinstance(payload, (list, tuple)):
        for nested in payload:
            _assert_no_generic_strength(nested)


def _claim_transport(
    *,
    claim_id: str,
    cause: str,
    effect: str,
    with_axes: bool,
) -> Any:
    from polisyos.data_forge.domains.academic.knowledge.types import (
        ClaimOccurrenceVocabularyTransport,
    )
    from polisyos.ir.analytics.literature import (
        ClaimVocabularyAxisStatus,
        DesignFamily,
        EvidenceStrength,
        SourceBasis,
        VersionedClaimVocabularyEnvelope,
    )

    status = (
        ClaimVocabularyAxisStatus.CANDIDATE
        if with_axes
        else ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    )
    return ClaimOccurrenceVocabularyTransport(
        occurrence={
            "claim_id": claim_id,
            "cause": cause,
            "effect": effect,
            "direction": "positive",
            "mechanism": f"{cause} changes {effect}",
        },
        vocabulary=VersionedClaimVocabularyEnvelope(
            cause=cause,
            effect=effect,
            direction="positive",
            mechanism=f"{cause} changes {effect}",
            design_family_hint=DesignFamily.RCT if with_axes else None,
            design_family_hint_status=status,
            evidence_strength=EvidenceStrength.OBSERVATIONAL if with_axes else None,
            evidence_strength_status=status,
            claim_extraction_confidence=0.37 if with_axes else None,
            claim_extraction_confidence_status=status,
            source_basis=SourceBasis.ABSTRACT_ONLY if with_axes else None,
            source_basis_status=status,
            record_extraction_mode="task4_fixture",
        ),
    )


def _adjudication_fixture(claim_id: str) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "claim_type": "causal_claim",
        "design_family": "rct",
        "causal_credibility": "moderate",
        "risk_of_bias": "unclear",
        "support_status": "supported",
        "source_basis": "abstract_only",
        "paper_asserts_causality_score": 0.8,
        "claim_validity_score": 0.8,
        "adjudication_confidence": 0.8,
        "publishable_edge": True,
    }


def _write_activated_graph(db_path: Path) -> None:
    from polisyos.data_forge.domains.academic.batch.graph_builder import build_graph
    from polisyos.data_forge.domains.academic.knowledge.types import WorkRecord

    transports = (
        _claim_transport(
            claim_id="claim-typed",
            cause="policy.tax_credit",
            effect="economic.employment",
            with_axes=True,
        ),
        _claim_transport(
            claim_id="claim-absent",
            cause="policy.training",
            effect="economic.wages",
            with_axes=False,
        ),
    )
    records = [
        WorkRecord(
            id=f"work-{index}",
            title=f"Task 4 work {index}",
            year=2025,
            trust_score=0.8,
            causal_claims=[transport],
        )
        for index, transport in enumerate(transports, start=1)
    ]
    build_graph(
        records=records,
        db_path=db_path,
        admitted_claim_adjudications={
            claim_id: _adjudication_fixture(claim_id)
            for claim_id in ("claim-typed", "claim-absent")
        },
    )


def _copy_snapshot(source_path: Path, target_path: Path) -> None:
    from polisyos.data_forge.domains.academic.batch import best_snapshot

    target_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(target_path))
    escaped = str(source_path).replace("'", "''")
    try:
        connection.execute(f"ATTACH '{escaped}' AS task4_source (READ_ONLY)")
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog = 'task4_source' AND table_schema = 'main' "
                "ORDER BY table_name"
            ).fetchall()
        ]
        for table in tables:
            best_snapshot._clone_non_skg_table(
                connection,
                source_alias="task4_source",
                table_name=table,
            )
    finally:
        connection.close()


def _all_reader_results(
    db_path: Path,
) -> tuple[dict[str, list[Any]], dict[str, list[Any]]]:
    from polisyos.data_forge.domains.academic.knowledge.search import ScholarKnowledgeGraph
    from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
    from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore
    from polisyos.data_forge.read_api import academic
    from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit
    from polisyos.scientist.agent.tools.knowledge_tools_adapter import (
        build_knowledge_tool_registry,
    )

    store = ScholarKnowledgeStore(db_path, db_path.parent / "index-store")
    query = SKGQuery(db_path, db_path.parent / "index-query")
    search = ScholarKnowledgeGraph(db_path, db_path.parent / "index-search")
    lazy_search = academic.ScholarKnowledgeGraph(db_path, db_path.parent / "index-lazy")
    toolkit = KnowledgeToolkit(scholar_graph=search)
    registry = build_knowledge_tool_registry(toolkit)
    try:
        registry_result = registry.execute(
            "find_causal_evidence",
            {
                "cause": "policy.",
                "effect": "economic.",
                "min_trust": 0.0,
                "support_mode": "exact",
            },
        )
        registry_v1 = registry.execute(
            "find_causal_evidence_v1_audit",
            {
                "cause": "policy.",
                "effect": "economic.",
                "min_trust": 0.0,
            },
        )
        assert registry_result.error is None
        assert registry_v1.error is None
        typed = {
            "store": store.get_causal_claims(
                "policy.", "economic.", min_trust=0.0
            ),
            "skg_query": query.query_claims(
                cause="policy.",
                effect="economic.",
                min_trust=0.0,
            ),
            "search": search.find_causal_evidence(
                "policy.", "economic.", min_trust=0.0
            ),
            "lazy_academic": lazy_search.find_causal_evidence(
                "policy.", "economic.", min_trust=0.0
            ),
            "academic_loader": list(academic.load_causal_claim_results_v2(db_path)),
            "scholar_toolkit": toolkit.find_causal_evidence(
                "policy.", "economic.", min_trust=0.0
            ),
            "tool_registry": registry_result.result,
        }
        v1_audits = {
            "store_v1": store.get_causal_claims_v1_audit(
                "policy.", "economic.", min_trust=0.0
            ),
            "skg_query_v1": query.query_claims_v1_audit(
                cause="policy.", effect="economic.", min_trust=0.0
            ),
            "search_v1": search.find_causal_evidence_v1_audit(
                "policy.", "economic.", min_trust=0.0
            ),
            "lazy_academic_v1": lazy_search.find_causal_evidence_v1_audit(
                "policy.", "economic.", min_trust=0.0
            ),
            "scholar_toolkit_v1": toolkit.find_causal_evidence_v1_audit(
                "policy.", "economic.", min_trust=0.0
            ),
            "tool_registry_v1": registry_v1.result,
        }
        return typed, v1_audits
    finally:
        lazy_search.close()
        search.close()
        query.close()
        store.close()


def _all_legacy_mechanism_results(
    db_path: Path,
) -> tuple[dict[str, list[Any]], dict[str, list[Any]]]:
    """Read one legacy mechanism through every public forwarding layer."""

    from polisyos.data_forge.domains.academic.knowledge.search import ScholarKnowledgeGraph
    from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore
    from polisyos.data_forge.read_api import academic
    from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit
    from polisyos.scientist.agent.tools.knowledge_tools_adapter import (
        build_knowledge_tool_registry,
    )

    store = ScholarKnowledgeStore(db_path, db_path.parent / "legacy-mechanism-store")
    search = ScholarKnowledgeGraph(db_path, db_path.parent / "legacy-mechanism-search")
    lazy_search = academic.ScholarKnowledgeGraph(
        db_path, db_path.parent / "legacy-mechanism-lazy"
    )
    toolkit = KnowledgeToolkit(scholar_graph=search)
    registry = build_knowledge_tool_registry(toolkit)
    try:
        registry_result = registry.execute(
            "get_mechanism_evidence", {"mechanism_name": "legacy mechanism", "top_k": 20}
        )
        registry_v1 = registry.execute(
            "get_mechanism_evidence_v1_audit",
            {"mechanism_name": "legacy mechanism", "top_k": 20, "min_trust": 0.0},
        )
        assert registry_result.error is None
        assert registry_v1.error is None
        typed = {
            "store": store.search_causal_claims("legacy mechanism", min_trust=0.0),
            "search": search.get_mechanism_evidence("legacy mechanism", min_trust=0.0),
            "lazy_academic": lazy_search.get_mechanism_evidence(
                "legacy mechanism", min_trust=0.0
            ),
            "scholar_toolkit": toolkit.get_mechanism_evidence("legacy mechanism", top_k=20),
            "tool_registry": registry_result.result,
        }
        v1_audits = {
            "store_v1": store.search_causal_claims_v1_audit(
                "legacy mechanism", min_trust=0.0
            ),
            "search_v1": search.get_mechanism_evidence_v1_audit(
                "legacy mechanism", min_trust=0.0
            ),
            "lazy_academic_v1": lazy_search.get_mechanism_evidence_v1_audit(
                "legacy mechanism", min_trust=0.0
            ),
            "scholar_toolkit_v1": toolkit.get_mechanism_evidence_v1_audit(
                "legacy mechanism", top_k=20, min_trust=0.0
            ),
            "tool_registry_v1": registry_v1.result,
        }
        return typed, v1_audits
    finally:
        lazy_search.close()
        search.close()
        store.close()


def _tracked_python_paths(root: Path, pattern: str) -> tuple[Path, ...]:
    output = subprocess.run(
        ["git", "ls-files", "-z", pattern],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    return tuple(root / raw.decode("utf-8") for raw in output.split(b"\0") if raw)


def _scope_for_node(tree: ast.AST) -> dict[int, str]:
    scopes: dict[int, str] = {}

    class ScopeVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = ["<module>"]

        def generic_visit(self, node: ast.AST) -> None:
            scopes[id(node)] = ".".join(self.stack)
            super().generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            scopes[id(node)] = ".".join(self.stack)
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            scopes[id(node)] = ".".join(self.stack)
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            scopes[id(node)] = ".".join(self.stack)
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

    ScopeVisitor().visit(tree)
    return scopes


def _operation(node: ast.AST, parent: ast.AST | None) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = node.value
        if re.search(r"\b(select|from|insert|update|create table)\b", text, re.IGNORECASE):
            return "sql"
        if text == "strength":
            return "emitted_key" if isinstance(parent, ast.Dict) else "key_read"
        return "carrier_or_loader"
    if isinstance(node, ast.Attribute):
        return "strength_attribute_read" if node.attr == "strength" else "public_symbol"
    if isinstance(node, ast.Subscript):
        return "strength_key_read"
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return "public_reader_symbol"
    return "symbol_read"


def _is_strength_node(node: ast.AST) -> bool:
    """Return whether a node directly carries the retired generic key."""

    return (
        (isinstance(node, ast.Constant) and node.value == "strength")
        or (isinstance(node, ast.Attribute) and node.attr == "strength")
        or (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == "strength"
        )
        or (isinstance(node, ast.Name) and node.id == "strength" and isinstance(node.ctx, ast.Load))
    )


def _scope_has_claim_semantics(tree: ast.AST, scopes: dict[int, str]) -> set[str]:
    """Construct claim context from AST evidence for each enclosing symbol."""

    semantic_scopes: set[str] = set()
    for node in ast.walk(tree):
        scope = scopes.get(id(node), "<module>")
        text = ""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        elif isinstance(node, ast.Name):
            text = node.id
        elif isinstance(node, ast.Attribute):
            text = node.attr
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            text = node.name
        if (
            "ac_causal_claims" in text
            or text in CENSUS_SYMBOLS
            or "causal_claim" in text.lower()
            or "claim_vocabulary" in text.lower()
        ):
            semantic_scopes.add(scope)
    return semantic_scopes


def _disposition(
    *,
    symbol: str,
    operation: str,
    text: str,
    is_test: bool,
    has_claim_context: bool,
) -> str:
    """Classify by AST operation and enclosing owner, never by a path allowlist."""

    if is_test:
        return "verification_fixture"
    symbol_lower = symbol.lower()
    text_lower = " ".join(text.lower().split())
    is_generic_strength = text == "strength" or operation.startswith("strength_")
    if is_generic_strength and "_project_claim_row" in symbol:
        return "store_owned_physical_legacy_projection"
    if is_generic_strength and "_infer_edge_strength" in symbol:
        return "frozen_edge_producer_over_admitted_v2"
    if is_generic_strength and (
        "EdgeEvidenceSample" in symbol
        or "edge_evidence" in symbol_lower
        or "edge_strength" in symbol_lower
    ):
        return "explicit_graph_edge_evidence_strength"
    if any(
        adapter in symbol
        for adapter in (
            "adapt_legacy_claim_occurrence_transport",
            "adapt_jsonl_work_record_claims",
        )
    ):
        return "provenance_bound_jsonl_legacy_adapter"
    if is_generic_strength and "adapt_legacy_claim_occurrence_as_v2_absence" in symbol:
        return "provenance_bound_jsonl_legacy_adapter"
    if any(
        owner in symbol
        for owner in (
            "_claim_table_schema",
            "_project_claim_row",
            "_select_claim_rows",
            "audit_claim_lineage",
            "iter_causal_claim_results_v2",
            "load_causal_claim_results_v2",
        )
    ):
        return "store_owned_physical_legacy_projection"
    if any(
        marker in symbol_lower
        for marker in (
            "edgeevidencesample",
            "edge_evidence",
            "edge_strength",
            "strongest_strength",
            "aggregate_edge",
            "_derive_l2_causal_edge",
            "_derive_l2_family_edge",
        )
    ):
        return "explicit_graph_edge_evidence_strength"
    if "_clone_non_skg_table" in symbol or "_validate_claim_snapshot_copy_schema" in symbol:
        return "snapshot_schema_copy_or_validation"
    if "preflight_claim_occurrence_vocabulary_copy" in symbol:
        return "snapshot_schema_copy_or_validation"
    if any(marker in symbol for marker in ("serialize_", "_claim_vocabulary_input")):
        return "producer_vocabulary_rejection"
    if any(
        marker in symbol
        for marker in (
            "LegacyFiveFieldClaimOccurrence",
            "CausalClaimResultV1",
            "ClaimOccurrenceVocabularyTransport",
            "_reject_nested_vocabulary",
        )
    ):
        return "typed_claim_contract_or_legacy_adapter"
    if "_entries_from_l2_l3_knowledge_substrates" in symbol:
        return "catalog_path_out_of_scope"
    if "REQUIRED_SKG_TABLES" in symbol or text == "REQUIRED_SKG_TABLES":
        return "currentness_search_table_ref_out_of_scope"
    if "_iter_l2_edges" in symbol and "iter_causal_claim_results_v2" in text:
        return "runtime_public_typed_loader"
    if operation == "sql" and "ac_causal_claims" in text_lower:
        if "count(" in text_lower:
            return "count_only_out_of_scope"
        if re.search(r"\bselect\b[^;]*\bstrength\b", text_lower):
            return "UNPROJECTED_READER"
        if any(
            verb in text_lower
            for verb in ("create table", "insert", "update", "delete", "drop table")
        ):
            return "activated_typed_claim_writer"
        return "typed_v2_reader_non_vocabulary_sql"
    if any(marker in symbol for marker in ("_DDL", "_init_schema", "_truncate", "_flush_all")):
        return "activated_typed_claim_writer"
    if "ac_skg_" in text_lower:
        return "explicit_graph_edge_evidence_strength"
    if any(symbol.endswith(name) for name in PUBLIC_CLAIM_SYMBOLS):
        return "typed_v2_reader_or_public_carrier"
    if any(name in text for name in PUBLIC_CLAIM_SYMBOLS):
        return "typed_v2_reader_or_public_carrier"
    if is_generic_strength and has_claim_context:
        return "UNPROJECTED_READER"
    if is_generic_strength:
        return "unrelated_strength"
    if has_claim_context:
        return "typed_v2_reader_or_public_carrier"
    return "UNCLASSIFIED"


def _claim_census(paths: tuple[Path, ...]) -> tuple[list[_CensusHit], list[str]]:
    hits: list[_CensusHit] = []
    parse_failures: list[str] = []
    for path in paths:
        relative = path.relative_to(REPO_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError as exc:
            parse_failures.append(f"{relative}:{exc.lineno}:{exc.msg}")
            continue
        scopes = _scope_for_node(tree)
        semantic_scopes = _scope_has_claim_semantics(tree, scopes)
        parents = {
            id(child): parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        seen: set[tuple[int, str, str, str]] = set()
        for node in ast.walk(tree):
            text = ""
            parent = parents.get(id(node))
            if isinstance(node, ast.Subscript) and _is_strength_node(node):
                text = "strength"
            elif isinstance(node, ast.Attribute) and (
                node.attr == "strength" or node.attr in CENSUS_SYMBOLS
            ):
                text = node.attr
            elif isinstance(node, ast.Name) and (
                node.id in CENSUS_SYMBOLS or _is_strength_node(node)
            ):
                text = node.id
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in CENSUS_SYMBOLS:
                text = node.name
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if isinstance(parent, ast.Subscript) and parent.slice is node:
                    continue
                if not (
                    "ac_causal_claims" in node.value
                    or node.value == "strength"
                    or any(name in node.value for name in CENSUS_SYMBOLS)
                ):
                    continue
                text = node.value
            else:
                continue
            operation = _operation(node, parent)
            symbol = scopes.get(id(node), "<module>")
            key = (getattr(node, "lineno", 0), symbol, operation, text)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                _CensusHit(
                    path=relative,
                    line=getattr(node, "lineno", 0),
                    symbol=symbol,
                    operation=operation,
                    disposition=_disposition(
                        symbol=symbol,
                        operation=operation,
                        text=text,
                        is_test=relative.startswith("tests/"),
                        has_claim_context=symbol in semantic_scopes,
                    ),
                )
            )
    return hits, parse_failures


def _create_empty_runtime_graph(repo_root: Path) -> Path:
    from polisyos.data_forge.domains.academic.batch.graph_builder import build_graph
    from polisyos.runtime.quality.substrate_registry import DEFAULT_L2_SCHOLAR_KG_PATH

    db_path = repo_root / DEFAULT_L2_SCHOLAR_KG_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    build_graph(records=(), db_path=db_path)
    return db_path


def test_claim_axes_round_trip_through_activated_writer_and_all_public_readers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import ValidationError

    from polisyos.data_forge.domains.academic.batch import graph_builder
    from polisyos.data_forge.domains.academic.knowledge import skg_store
    from polisyos.data_forge.domains.academic.knowledge.skg_store import (
        ingest_openalex_span_grounded_claims,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import WorkRecord
    from polisyos.ir.analytics.literature import (
        DesignFamily,
        EvidenceStrength,
        OpenAlexWorkText,
        SourceBasis,
    )
    from polisyos.runtime.quality.credal_reference import _iter_l2_edges
    from polisyos.runtime.quality.substrate_registry import DEFAULT_L2_SCHOLAR_KG_PATH
    from polisyos.scholar.search.models import SearchQueryTrace

    original_graph_admission = graph_builder.admit_candidate_claim_vocabulary
    graph_admissions: list[Any] = []

    def observed_graph_admission(transport: Any) -> Any:
        graph_admissions.append(transport)
        return original_graph_admission(transport)

    monkeypatch.setattr(graph_builder, "admit_candidate_claim_vocabulary", observed_graph_admission)
    typed_transport = _claim_transport(
        claim_id="claim-forged-graph",
        cause="policy.forged",
        effect="economic.forged",
        with_axes=True,
    )
    forged_transport = typed_transport.model_copy(
        update={
            "vocabulary": typed_transport.vocabulary.model_copy(
                update={"evidence_strength": None}
            )
        }
    )
    rejected_graph_path = tmp_path / "rejected-graph-writer.duckdb"
    with pytest.raises(ValidationError):
        graph_builder.build_graph(
            records=[
                WorkRecord(
                    id="work-forged-graph",
                    title="Forged graph record",
                    causal_claims=[forged_transport],
                )
            ],
            db_path=rejected_graph_path,
            admitted_claim_adjudications={"claim-forged-graph": _adjudication_fixture("claim-forged-graph")},
        )
    assert graph_admissions == [forged_transport]
    rejected_graph = duckdb.connect(str(rejected_graph_path), read_only=True)
    try:
        assert rejected_graph.execute("SELECT count(*) FROM ac_works").fetchone() == (0,)
        assert rejected_graph.execute("SELECT count(*) FROM ac_causal_claims").fetchone() == (0,)
    finally:
        rejected_graph.close()

    writer_path = tmp_path / "activated-writer.duckdb"
    _write_activated_graph(writer_path)
    assert len(graph_admissions) == 3
    runtime_root = tmp_path / "runtime-root"
    copied_path = runtime_root / DEFAULT_L2_SCHOLAR_KG_PATH
    _copy_snapshot(writer_path, copied_path)

    typed_expected = {
        "design_family_hint": "rct",
        "design_family_hint_status": "candidate",
        "evidence_strength": "observational",
        "evidence_strength_status": "candidate",
        "claim_extraction_confidence": pytest.approx(0.37),
        "claim_extraction_confidence_status": "candidate",
        "source_basis": "abstract_only",
        "source_basis_status": "candidate",
    }
    physical = duckdb.connect(str(copied_path), read_only=True)
    try:
        for table in ("ac_causal_claims_raw", "ac_causal_claims"):
            columns = {
                str(row[0])
                for row in physical.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = ?",
                    [table],
                ).fetchall()
            }
            assert "strength" not in columns
            assert "claim_vocabulary_schema_version" in columns
            claim_queries = {
                "ac_causal_claims_raw": (
                    "SELECT id, claim_vocabulary_schema_version, design_family_hint, "
                    "design_family_hint_status, evidence_strength, evidence_strength_status, "
                    "claim_extraction_confidence, claim_extraction_confidence_status, "
                    "source_basis, source_basis_status FROM ac_causal_claims_raw ORDER BY id"
                ),
                "ac_causal_claims": (
                    "SELECT id, claim_vocabulary_schema_version, design_family_hint, "
                    "design_family_hint_status, evidence_strength, evidence_strength_status, "
                    "claim_extraction_confidence, claim_extraction_confidence_status, "
                    "source_basis, source_basis_status FROM ac_causal_claims ORDER BY id"
                ),
            }
            rows = physical.execute(claim_queries[table]).fetchall()
            assert rows == [
                (
                    "claim-absent",
                    "2.0",
                    None,
                    "not_established",
                    None,
                    "not_established",
                    None,
                    "not_established",
                    None,
                    "not_established",
                ),
                (
                    "claim-typed",
                    "2.0",
                    "rct",
                    "candidate",
                    "observational",
                    "candidate",
                    pytest.approx(0.37),
                    "candidate",
                    "abstract_only",
                    "candidate",
                ),
            ]
    finally:
        physical.close()

    reader_results, v1_audits = _all_reader_results(copied_path)
    absence_expected = {
        key: "not_established" if key.endswith("_status") else None
        for field in AXIS_FIELDS
        for key in (field, f"{field}_status")
    }
    for route, results in reader_results.items():
        assert results, route
        assert len(results) == 2, route
        if isinstance(results[0], dict):
            typed = next(result for result in results if result["id"] == "claim-typed")
            absence = next(result for result in results if result["id"] == "claim-absent")
        else:
            typed = next(result for result in results if result.id == "claim-typed")
            absence = next(result for result in results if result.id == "claim-absent")
        assert _axis_payload(typed) == typed_expected, route
        assert _axis_payload(absence) == absence_expected, route
        _assert_no_generic_strength(typed)
        _assert_no_generic_strength(absence)

    for route, results in v1_audits.items():
        assert len(results) == 2, route
        for result in results:
            payload = result if isinstance(result, dict) else result.model_dump(mode="json")
            assert payload.get("strength") is None, route
            assert payload["limitation"] == "ambiguous_legacy_vocabulary", route

    from polisyos.data_forge.read_api import academic

    absence = next(
        result
        for result in academic.load_causal_claim_results_v2(copied_path)
        if result.id == "claim-absent"
    )
    assert _axis_payload(absence) == absence_expected
    _assert_no_generic_strength(absence)

    runtime_claims = [edge for edge in _iter_l2_edges(runtime_root) if edge.modality == "L2_CAUSAL_CLAIM"]
    assert {edge.edge_id for edge in runtime_claims} == {"claim-typed", "claim-absent"}
    runtime_typed = next(edge for edge in runtime_claims if edge.edge_id == "claim-typed")
    runtime_absence = next(edge for edge in runtime_claims if edge.edge_id == "claim-absent")
    assert _axis_payload(runtime_typed.admissible_completions[0].value) == typed_expected
    assert _axis_payload(runtime_absence.admissible_completions[0].value) == absence_expected
    _assert_no_generic_strength(runtime_typed.to_payload())
    _assert_no_generic_strength(runtime_absence.to_payload())

    fixture = json.loads(
        (
            REPO_ROOT
            / "tests/fixtures/scholar/openalex/credit_guarantee_firm_survival.json"
        ).read_text(encoding="utf-8")
    )
    work = OpenAlexWorkText.from_openalex_work(fixture["results"][0])
    client = _DeterministicSpanSupportClient()
    from polisyos.ir.analytics.literature import CausalClaim, EvidenceSpan

    span_text = work.abstract_text
    span_start = work.source_text.index(span_text)
    support_span = EvidenceSpan(
        span_id="task4-local-span",
        text=span_text,
        source_ref=work.openalex_id,
        start_char=span_start,
        end_char=span_start + len(span_text),
        content_sha256=work.content_sha256,
    )
    span_claim = CausalClaim(
        claim_id="task4-span-claim",
        cause_variable="loan guarantees",
        effect_variable="firm survival",
        direction="positive",
        claim_text=span_text,
        design_family_hint=DesignFamily.RCT,
        evidence_strength=EvidenceStrength.OBSERVATIONAL,
        claim_extraction_confidence=0.37,
        source_basis=SourceBasis.ABSTRACT_ONLY,
        supporting_spans=[support_span],
        supporting_span_ids=["task4-local-span"],
    )
    span_absence = CausalClaim(
        claim_id="task4-span-absence",
        cause_variable="credit access",
        effect_variable="business continuity",
        claim_text=span_text,
        supporting_spans=[support_span],
        supporting_span_ids=["task4-local-span"],
    )
    original_span_admission = skg_store.preflight_candidate_claim_vocabulary
    span_admissions: list[Any] = []

    def observed_span_admission(transport: Any) -> Any:
        span_admissions.append(transport)
        return original_span_admission(transport)

    monkeypatch.setattr(skg_store, "preflight_candidate_claim_vocabulary", observed_span_admission)
    from polisyos.data_forge.domains.academic.batch import article_extractor

    original_span_serializer = article_extractor.serialize_rich_claim_occurrence_vocabulary
    valid_span_transport = _claim_transport(
        claim_id="task4-forged-span",
        cause="loan guarantees",
        effect="firm survival",
        with_axes=True,
    )
    forged_span_transport = valid_span_transport.model_copy(
        update={
            "vocabulary": valid_span_transport.vocabulary.model_copy(
                update={"evidence_strength": None}
            )
        }
    )

    def forged_span_serializer(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return forged_span_transport

    monkeypatch.setattr(
        article_extractor,
        "serialize_rich_claim_occurrence_vocabulary",
        forged_span_serializer,
    )
    rejected_span_path = tmp_path / "rejected-span-writer.duckdb"
    rejected_span_connection = duckdb.connect(str(rejected_span_path))
    try:
        with pytest.raises(ValidationError):
            ingest_openalex_span_grounded_claims(
                rejected_span_connection,
                work=work,
                claims=[span_claim],
                query_trace=SearchQueryTrace(
                    query_node_id="task4-forged-span",
                    query="forged span admission",
                    perspective="root",
                    provider="openalex",
                    hit_count=1,
                ),
                span_support_client=client,
            )
        assert rejected_span_connection.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = 'ac_skg_articles'"
        ).fetchone() == (0,)
    finally:
        rejected_span_connection.close()
    assert len(span_admissions) == 1
    monkeypatch.setattr(
        article_extractor,
        "serialize_rich_claim_occurrence_vocabulary",
        original_span_serializer,
    )

    span_connection = duckdb.connect(str(tmp_path / "span-writer.duckdb"))
    try:
        report = ingest_openalex_span_grounded_claims(
            span_connection,
            work=work,
            claims=[span_claim, span_absence],
            query_trace=SearchQueryTrace(
                query_node_id="task4-span",
                query="loan guarantees SMEs firm survival impact evaluation",
                perspective="root",
                provider="openalex",
                hit_count=1,
            ),
            span_support_client=client,
        )
        persisted = json.loads(
            span_connection.execute(
                "SELECT extraction_json FROM ac_skg_articles WHERE openalex_id = ?",
                [work.openalex_id],
            ).fetchone()[0]
        )["claims"]
    finally:
        span_connection.close()
    assert len(span_admissions) == 3
    assert report.ingested_claim_count == 2
    persisted_by_id = {item["occurrence"]["claim_id"]: item for item in persisted}
    assert _axis_payload(persisted_by_id["task4-span-claim"]["vocabulary"]) == typed_expected
    assert _axis_payload(persisted_by_id["task4-span-absence"]["vocabulary"]) == absence_expected
    _assert_no_generic_strength(persisted)


def test_legacy_snapshot_reads_as_declared_absence_without_data_write() -> None:
    assert PINNED_SNAPSHOT.is_file()
    before = _sha256(PINNED_SNAPSHOT)
    assert before == PINNED_SNAPSHOT_SHA256

    source = duckdb.connect(str(PINNED_SNAPSHOT), read_only=True)
    try:
        tables = {
            str(row[0])
            for row in source.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
        assert "ac_causal_claims_raw" in tables
        columns = {
            str(row[0])
            for row in source.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'main' AND table_name = 'ac_causal_claims_raw'"
            ).fetchall()
        }
        assert {
            "id",
            "work_id",
            "design_family_hint",
            "strength",
        } <= columns
        assert "claim_vocabulary_schema_version" not in columns
        denominator = source.execute(
            "SELECT count(*) AS total_rows, "
            "count(DISTINCT (id, work_id)) AS distinct_identities, "
            "count(*) FILTER (WHERE id IS NULL OR work_id IS NULL) AS null_identities, "
            "count(*) - count(DISTINCT (id, work_id)) AS duplicate_identities, "
            "count(DISTINCT (id, work_id)) FILTER ("
            "WHERE NULLIF(TRIM(design_family_hint), '') IS NULL "
            "AND LOWER(TRIM(strength)) = 'moderate') AS cohort_identities "
            "FROM ac_causal_claims_raw"
        ).fetchone()
        cohort = {
            (str(row[0]), str(row[1]))
            for row in source.execute(
                "SELECT id, work_id FROM ac_causal_claims_raw "
                "WHERE NULLIF(TRIM(design_family_hint), '') IS NULL "
                "AND LOWER(TRIM(strength)) = 'moderate' ORDER BY id, work_id"
            ).fetchall()
        }
    finally:
        source.close()

    assert denominator == (137_589, 137_589, 0, 0, 69_798)
    assert len(cohort) == 69_798

    from polisyos.data_forge.read_api import academic

    seen: set[tuple[str, str]] = set()
    seen_cohort: set[tuple[str, str]] = set()
    cursor: str | None = None
    total: int | None = None
    while True:
        page = academic.audit_academic_claim_lineage(
            PINNED_SNAPSHOT,
            status="all",
            cursor=cursor,
            limit=500,
        )
        if total is None:
            total = page.total_identities
        assert page.total_identities == total == 137_589
        for item in page.items:
            identity = (item.id, item.work_id)
            assert identity not in seen
            seen.add(identity)
            if identity not in cohort:
                continue
            seen_cohort.add(identity)
            assert item.legacy_strength_label == "moderate"
            assert _axis_payload(item.vocabulary) == {
                key: "not_established" if key.endswith("_status") else None
                for field in AXIS_FIELDS
                for key in (field, f"{field}_status")
            }
        cursor = page.next_cursor
        if cursor is None:
            break
    assert len(seen) == 137_589
    assert seen_cohort == cohort
    assert _sha256(PINNED_SNAPSHOT) == before == PINNED_SNAPSHOT_SHA256


def test_snapshot_copy_replay_remains_legacy_until_projected(tmp_path: Path) -> None:
    from polisyos.data_forge.domains.academic.batch import best_snapshot
    from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore
    from polisyos.data_forge.domains.academic.knowledge.types import adapt_jsonl_work_record_claims

    source_path = tmp_path / "legacy-source.duckdb"
    destination_path = tmp_path / "legacy-destination.duckdb"
    source = duckdb.connect(str(source_path))
    try:
        source.execute("CREATE TABLE ac_works (id VARCHAR PRIMARY KEY, title VARCHAR, year INTEGER)")
        source.execute(
            "CREATE TABLE ac_causal_claims ("
            "id VARCHAR PRIMARY KEY, work_id VARCHAR NOT NULL, cause VARCHAR NOT NULL, "
            "effect VARCHAR NOT NULL, direction VARCHAR, strength VARCHAR, mechanism VARCHAR, "
            "domain VARCHAR, trust_score FLOAT, strong_design_evidence BOOLEAN, "
            "design_quality_tier INTEGER, publish_blockers VARCHAR, candidate_layer VARCHAR)"
        )
        source.execute("INSERT INTO ac_works VALUES ('work-legacy', 'Legacy work', 2020)")
        source.execute(
            "INSERT INTO ac_causal_claims VALUES ("
            "'claim-legacy', 'work-legacy', 'policy.legacy', 'outcome.legacy', "
            "'positive', 'moderate', 'legacy mechanism', '', 0.4, FALSE, NULL, '', 'candidate')"
        )
    finally:
        source.close()

    destination = duckdb.connect(str(destination_path))
    escaped = str(source_path).replace("'", "''")
    try:
        destination.execute(f"ATTACH '{escaped}' AS legacy_source (READ_ONLY)")
        for table in ("ac_works", "ac_causal_claims"):
            best_snapshot._clone_non_skg_table(
                destination,
                source_alias="legacy_source",
                table_name=table,
            )
        columns = {
            str(row[0])
            for row in destination.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'ac_causal_claims'"
            ).fetchall()
        }
    finally:
        destination.close()
    assert "strength" in columns
    assert "claim_vocabulary_schema_version" not in columns

    jsonl_path = tmp_path / "legacy-work.jsonl"
    jsonl_path.write_text(
        json.dumps(
            {
                "id": "work-jsonl",
                "title": "Legacy JSONL work",
                "causal_claims": [
                    {
                        "cause": "policy.jsonl",
                        "effect": "outcome.jsonl",
                        "direction": "negative",
                        "strength": "moderate",
                        "mechanism": "legacy JSONL mechanism",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    replayed = adapt_jsonl_work_record_claims(
        json.loads(jsonl_path.read_text(encoding="utf-8")),
        provenance="legacy_jsonl",
    )
    replay_vocabulary = replayed.causal_claims[0].vocabulary
    assert replay_vocabulary.legacy_strength_label == "moderate"
    assert replay_vocabulary.record_extraction_mode == "deterministic"
    assert _axis_payload(replay_vocabulary) == {
        key: "not_established" if key.endswith("_status") else None
        for field in AXIS_FIELDS
        for key in (field, f"{field}_status")
    }

    store = ScholarKnowledgeStore(destination_path, tmp_path / "legacy-index")
    try:
        projected = store.get_causal_claims("policy.legacy", "outcome.legacy")[0]
    finally:
        store.close()
    assert projected.legacy_strength_label == "moderate"
    assert _axis_payload(projected) == {
        key: "not_established" if key.endswith("_status") else None
        for field in AXIS_FIELDS
        for key in (field, f"{field}_status")
    }
    _assert_no_generic_strength(projected)

    mechanism_results, mechanism_v1_audits = _all_legacy_mechanism_results(destination_path)
    expected_absence = {
        key: "not_established" if key.endswith("_status") else None
        for field in AXIS_FIELDS
        for key in (field, f"{field}_status")
    }
    for route, results in mechanism_results.items():
        assert len(results) == 1, route
        result = results[0]
        assert _axis_payload(result) == expected_absence, route
        _assert_no_generic_strength(result)
    for route, results in mechanism_v1_audits.items():
        assert len(results) == 1, route
        result = results[0]
        payload = result if isinstance(result, dict) else result.model_dump(mode="json")
        assert payload.get("strength") is None, route
        assert payload["limitation"] == "ambiguous_legacy_vocabulary", route

    v1 = ScholarKnowledgeStore(destination_path, tmp_path / "legacy-v1-index")
    try:
        v1_projected = v1.get_causal_claims_v1_audit(
            "policy.legacy", "outcome.legacy"
        )[0]
    finally:
        v1.close()
    assert v1_projected.strength is None
    assert v1_projected.limitation.value == "ambiguous_legacy_vocabulary"


def test_complete_claim_vocabulary_consumer_census_has_no_unprojected_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    record_property: Any,
) -> None:
    source_paths = _tracked_python_paths(REPO_ROOT, "src/**/*.py")
    test_paths = _tracked_python_paths(REPO_ROOT, "tests/**/*.py")
    hits, parse_failures = _claim_census((*source_paths, *test_paths))

    assert not parse_failures
    assert len(source_paths) >= 2_619
    assert len(test_paths) >= 2_495
    assert hits
    unclassified = [hit for hit in hits if hit.disposition == "UNCLASSIFIED"]
    assert not unclassified, "unclassified claim-vocabulary hits: " + repr(unclassified[:30])
    unprojected = [hit for hit in hits if hit.disposition == "UNPROJECTED_READER"]
    assert not unprojected, "unprojected generic-strength readers: " + repr(unprojected)

    source_hits = [hit for hit in hits if hit.path.startswith("src/")]
    dispositions = Counter(hit.disposition for hit in source_hits)
    required_dispositions = {
        "provenance_bound_jsonl_legacy_adapter",
        "store_owned_physical_legacy_projection",
        "frozen_edge_producer_over_admitted_v2",
        "explicit_graph_edge_evidence_strength",
        "count_only_out_of_scope",
        "catalog_path_out_of_scope",
        "currentness_search_table_ref_out_of_scope",
        "runtime_public_typed_loader",
        "typed_v2_reader_or_public_carrier",
    }
    assert required_dispositions <= dispositions.keys(), (
        "missing semantic dispositions: "
        f"{sorted(required_dispositions - dispositions.keys())}"
    )

    direct_generic_claim_sql: list[_CensusHit] = []
    for path in source_paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            normalized = " ".join(node.value.lower().split())
            if re.search(
                r"\bselect\b[^;]*\bstrength\b[^;]*\bfrom\s+ac_causal_claims\b",
                normalized,
            ):
                direct_generic_claim_sql.append(
                    _CensusHit(
                        path=path.relative_to(REPO_ROOT).as_posix(),
                        line=node.lineno,
                        symbol="sql",
                        operation="direct_claim_strength_sql",
                        disposition="UNPROJECTED_READER",
                    )
                )
    assert not direct_generic_claim_sql

    from polisyos.data_forge.read_api import academic
    from polisyos.runtime.quality.credal_reference import _iter_l2_edges

    runtime_root = tmp_path / "runtime-loader-proof"
    _create_empty_runtime_graph(runtime_root)
    original_loader = getattr(academic, "iter_causal_claim_results_v2", None)
    loader_calls: list[duckdb.DuckDBPyConnection] = []

    def observed_public_loader(
        connection: duckdb.DuckDBPyConnection,
    ) -> Any:
        loader_calls.append(connection)
        if original_loader is None:
            return iter(())
        return original_loader(connection)

    monkeypatch.setattr(
        academic,
        "iter_causal_claim_results_v2",
        observed_public_loader,
        raising=False,
    )
    list(_iter_l2_edges(runtime_root))
    assert len(loader_calls) == 1

    inventory = [
        {
            "path": hit.path,
            "line": hit.line,
            "symbol": hit.symbol,
            "operation": hit.operation,
            "disposition": hit.disposition,
        }
        for hit in hits
    ]
    record_property("claim_vocabulary_census_inventory", json.dumps(inventory, sort_keys=True))
    print(
        "claim_vocabulary_census "
        f"source_python={len(source_paths)} test_python={len(test_paths)} "
        f"candidates={len({hit.path for hit in hits})} hits={len(hits)} "
        f"dispositions={dict(sorted(dispositions.items()))} inventory={json.dumps(inventory)}"
    )
    assert "source_python=" in capsys.readouterr().out
