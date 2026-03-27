"""Academic prior mining narrowed by discovery priors."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.academic.knowledge.skg_query import SKGQuery
from polisyos.ir.analytics.cross_graph import (
    EvidenceSourceKind,
    EvidenceSourceState,
)
from polisyos.scientist.discovery.priors import (
    GraphPriorBundle,
    PriorKnowledgeBundle,
    PriorKnowledgeSupport,
)
from polisyos.scientist.evidence_sources import (
    build_path_source_status,
    update_source_status,
)


class PriorMinerConfig(BaseModel):
    """Runtime configuration for academic prior mining."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    academic_db_path: str | None = None
    academic_index_dir: str | None = None
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = Field(default=256, ge=1)
    domain: str | None = None
    support_mode: str = Field(default="hybrid", min_length=1)


class PriorMiner:
    """Mine academic support rows for discovery-selected prior edges."""

    def __init__(
        self,
        *,
        config: PriorMinerConfig | None = None,
    ) -> None:
        self._config = config or PriorMinerConfig()

    @property
    def config(self) -> PriorMinerConfig:
        return self._config

    def mine(self, bundle: GraphPriorBundle) -> PriorKnowledgeBundle:
        target_edge_keys = _target_edge_keys(bundle)
        academic_status = build_path_source_status(
            EvidenceSourceKind.ACADEMIC,
            self._config.academic_db_path,
            detail="discovery_prior_mining",
        )
        if not target_edge_keys:
            return PriorKnowledgeBundle(
                query_edge_keys=[],
                source_statuses={"academic": academic_status},
                warnings=["no_target_edges_for_prior_mining"],
                metadata={"build_status": "no_target_edges"},
            )

        db_path = str(self._config.academic_db_path or "").strip()
        if not db_path:
            return PriorKnowledgeBundle(
                status="degraded",
                query_edge_keys=sorted(target_edge_keys),
                unresolved_edges=sorted(target_edge_keys),
                source_statuses={"academic": academic_status},
                warnings=["academic_db_path_not_configured"],
                metadata={"build_status": "missing_academic_db_path"},
            )

        if academic_status.status is EvidenceSourceState.MISSING_PATH:
            return PriorKnowledgeBundle(
                status="degraded",
                query_edge_keys=sorted(target_edge_keys),
                unresolved_edges=sorted(target_edge_keys),
                source_statuses={"academic": academic_status},
                warnings=[f"academic_db_path_missing:{db_path}"],
                metadata={
                    "build_status": "missing_academic_db_path_on_disk",
                    "academic_db_path": db_path,
                },
            )

        index_dir = str(self._config.academic_index_dir or "").strip() or None
        query: SKGQuery | None = None
        try:
            query = SKGQuery(db_path=db_path, index_dir=index_dir or ".")
            variables = sorted({node for edge_key in target_edge_keys for node in _edge_nodes(edge_key)})
            rows = query.query_prior_for_variables(
                variables,
                min_confidence=self._config.min_confidence,
                limit=self._config.limit,
                domain=self._config.domain,
                edge_layer=self._config.support_mode,
            )
            version_id = query.latest_skg_version_id()
            snapshot_ref = query.skg_snapshot_ref(version_id=version_id)
        except Exception as exc:
            failed_status = update_source_status(
                academic_status,
                state=EvidenceSourceState.QUERY_FAILED,
                detail=f"{type(exc).__name__}:{exc}",
                warnings=[f"academic_prior_query_failed:{type(exc).__name__}:{exc}"],
            )
            return PriorKnowledgeBundle(
                status="degraded",
                query_edge_keys=sorted(target_edge_keys),
                unresolved_edges=sorted(target_edge_keys),
                source_statuses={"academic": failed_status},
                warnings=[f"academic_prior_query_failed:{type(exc).__name__}:{exc}"],
                metadata={
                    "build_status": "skg_query_failed",
                    "academic_db_path": db_path,
                },
            )
        finally:
            if query is not None:
                query.close()

        support_rows: list[PriorKnowledgeSupport] = []
        matched_keys: set[str] = set()
        for row in rows:
            edge_key = _row_edge_key(row)
            if edge_key not in target_edge_keys:
                continue
            matched_keys.add(edge_key)
            support_rows.append(
                PriorKnowledgeSupport(
                    edge_key=edge_key,
                    src=str(row["src"]),
                    dst=str(row["dst"]),
                    direction=str(row.get("direction") or "mixed"),
                    confidence=float(row.get("confidence") or 0.0),
                    n_articles=int(row.get("n_articles") or 0),
                    evidence_strength=str(row.get("evidence_strength") or "unknown"),
                    candidate_layer=str(row.get("candidate_layer") or self._config.support_mode),
                    article_refs=[str(item) for item in row.get("article_refs", [])],
                    quality_signals=dict(row.get("quality_signals") or {}),
                    metadata={
                        "domain": self._config.domain,
                        "support_mode": self._config.support_mode,
                    },
                )
            )

        unresolved = sorted(target_edge_keys - matched_keys)
        provenance_refs = [snapshot_ref] if snapshot_ref else []
        academic_status = update_source_status(
            academic_status,
            state=EvidenceSourceState.AVAILABLE,
            provenance_refs=provenance_refs,
            detail="academic_support_loaded",
        )
        return PriorKnowledgeBundle(
            status="ok",
            support_mode=f"academic_{self._config.support_mode}",
            query_edge_keys=sorted(target_edge_keys),
            support_rows=support_rows,
            unresolved_edges=unresolved,
            skg_version_id=version_id,
            skg_snapshot_ref=snapshot_ref,
            provenance_refs=provenance_refs,
            source_statuses={"academic": academic_status},
            warnings=[],
            metadata={
                "academic_db_path": db_path,
                "academic_index_dir": index_dir,
                "build_status": "ok",
                "n_support_rows": len(support_rows),
            },
        )


def _target_edge_keys(bundle: GraphPriorBundle) -> set[str]:
    edge_keys = {edge.edge_key for edge in bundle.required_edges}
    edge_keys.update(edge.edge_key for edge in bundle.high_confidence_edges)
    for disputed in bundle.disputed_edges:
        edge_keys.update(edge.edge_key for edge in disputed.candidate_edges)
    return edge_keys


def _row_edge_key(row: dict[str, object]) -> str:
    edge_key = f"{row['src']}->{row['dst']}"
    lag = row.get("lag")
    if lag not in (None, "", 0):
        edge_key = f"{edge_key}@lag={int(lag)}"
    return edge_key


def _edge_nodes(edge_key: str) -> tuple[str, str]:
    base, _, _ = edge_key.partition("@lag=")
    src, _, dst = base.partition("->")
    return src, dst


__all__ = [
    "PriorMiner",
    "PriorMinerConfig",
]
