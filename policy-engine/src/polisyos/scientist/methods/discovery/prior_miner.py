"""Academic prior mining narrowed by discovery priors."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from polisyos.data_forge.read_api.academic import SKGQuery
from polisyos.ir.analytics.cross_graph import (
    EvidenceSourceKind,
    EvidenceSourceState,
)
from polisyos.scientist.evidence.sources import (
    build_path_source_status,
    update_source_status,
)
from polisyos.scientist.methods.discovery.priors import (
    GraphPriorBundle,
    PriorKnowledgeBundle,
    PriorKnowledgeSupport,
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
            query = SKGQuery(
                db_path=Path(db_path),
                index_dir=Path(index_dir or "."),
            )
            variables = sorted(
                {node for edge_key in target_edge_keys for node in _edge_nodes(edge_key)}
            )
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
                    src=_row_string(row, "src"),
                    dst=_row_string(row, "dst"),
                    direction=_row_string(row, "direction", default="mixed"),
                    confidence=_row_float(row, "confidence"),
                    n_articles=_row_int(row, "n_articles"),
                    evidence_strength=_row_string(row, "evidence_strength", default="unknown"),
                    candidate_layer=_row_string(
                        row,
                        "candidate_layer",
                        default=self._config.support_mode,
                    ),
                    article_refs=_row_string_list(row, "article_refs"),
                    quality_signals=_row_object_map(row, "quality_signals"),
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


def _row_edge_key(row: Mapping[str, object]) -> str:
    src = _row_string(row, "src")
    dst = _row_string(row, "dst")
    lag = _row_int(row, "lag")
    return _cached_row_edge_key(src, dst, lag)


@lru_cache(maxsize=4096)
def _cached_row_edge_key(src: str, dst: str, lag: int) -> str:
    edge_key = f"{src}->{dst}"
    if lag != 0:
        return f"{edge_key}@lag={lag}"
    return edge_key


def _edge_nodes(edge_key: str) -> tuple[str, str]:
    base, _, _ = edge_key.partition("@lag=")
    src, _, dst = base.partition("->")
    return src, dst


def _row_string(
    row: Mapping[str, object],
    key: str,
    *,
    default: str = "",
) -> str:
    value = row.get(key)
    normalized = str(value).strip() if value is not None else ""
    return normalized or default


def _row_int(
    row: Mapping[str, object],
    key: str,
    *,
    default: int = 0,
) -> int:
    value = row.get(key)
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _row_float(
    row: Mapping[str, object],
    key: str,
    *,
    default: float = 0.0,
) -> float:
    value = row.get(key)
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _row_string_list(row: Mapping[str, object], key: str) -> list[str]:
    value = row.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(item) for item in value]


def _row_object_map(row: Mapping[str, object], key: str) -> dict[str, object]:
    value = row.get(key)
    if not isinstance(value, Mapping):
        return {}
    return {str(item_key): item_value for item_key, item_value in value.items()}


__all__ = [
    "PriorMiner",
    "PriorMinerConfig",
]
