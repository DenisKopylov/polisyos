"""
RAG helpers for multipass drafter quality improvements.

Design goals:
- API-first embedding strategy (provider callback as primary path).
- Deterministic retrieval and snapshot persistence in CAS.
- Zero coupling to local model inference in default configuration.
"""

from __future__ import annotations

import io
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.agent.protocols import ProblemFrame as AgentProblemFrame

logger = get_logger(__name__)

_RAG_ARTIFACT_LOAD_ERRORS = (
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)
_RAG_IMPORT_ERRORS = (ImportError, ModuleNotFoundError)

RAG_ENTRIES_KIND = "scientist.rag_entries.v1"
RAG_VECTORS_KIND = "scientist.rag_vectors.v1"
RAG_SNAPSHOT_KIND = "scientist.rag_snapshot.v1"
RAG_SCHEMA_VERSION = "1.0"


def _as_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _normalize_text(raw: str) -> str:
    collapsed = re.sub(r"\s+", " ", raw).strip()
    return collapsed


class EmbeddingBackend(Protocol):
    """Embedding backend protocol."""

    @property
    def dimension(self) -> int: ...

    def encode(self, texts: list[str]) -> np.ndarray: ...


class ProviderEmbeddingBackend:
    """
    Provider/API embedding backend.

    The callback should call an external embedding API and return vectors.
    """

    def __init__(
        self,
        embed_fn: Callable[[list[str]], Sequence[Sequence[float]]],
        *,
        dimension: int,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be > 0")
        self._embed_fn = embed_fn
        self._dimension = int(dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    def encode(self, texts: list[str]) -> np.ndarray:
        payload = self._embed_fn(texts)
        arr = np.asarray(payload, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[0] != len(texts):
            raise ValueError("embedding backend returned invalid shape")
        if arr.shape[1] != self._dimension:
            raise ValueError(
                f"embedding dimension mismatch: expected {self._dimension}, got {arr.shape[1]}"
            )
        return _l2_normalize(arr)


class HashEmbeddingBackend:
    """
    Deterministic lightweight fallback backend.

    This backend is intentionally simple and dependency-free.
    """

    def __init__(self, *, dimension: int = 256) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be > 0")
        self._dimension = int(dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self._dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            tokens = _tokenize(text)
            if not tokens:
                continue
            for token in tokens:
                idx = hash(token) % self._dimension
                vectors[row, idx] += 1.0
        return _l2_normalize(vectors)


def _tokenize(text: str) -> list[str]:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return []
    return re.findall(r"[a-z0-9_]+", normalized)


def _l2_normalize(arr: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return (arr / norms).astype(np.float32)


@dataclass(frozen=True, slots=True)
class RAGCaseEntry:
    """RAG case entry data model."""

    decision_packet_ref: str
    trinity_bundle_ref: str
    run_id: str
    domain: str
    problem_text: str
    problem_summary: str
    intervention_summary: str
    lesson_learned: str
    confidence: float
    indexed_at: str


@dataclass(frozen=True, slots=True)
class RAGSearchResult:
    """RAG search result data model."""

    entry: RAGCaseEntry
    similarity: float


class RAGConfig(BaseModel):
    """Runtime configuration for RAG injection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    embedding_backend: str = "provider"
    similarity_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    top_k: int = Field(default=3, ge=1, le=10)
    domain_filter: bool = True
    max_few_shot_chars: int = Field(default=6000, ge=400, le=20000)
    max_entries: int = Field(default=10_000, ge=100)
    freeze_snapshot_per_run: bool = True
    cas_root: str = ".polisyos"

    @classmethod
    def from_env(cls) -> RAGConfig:
        kwargs: dict[str, Any] = {}
        kwargs["enabled"] = _as_bool(os.getenv("POLISYOS_RAG_ENABLED"), default=False)
        backend = os.getenv("POLISYOS_RAG_EMBEDDING_BACKEND")
        if backend:
            kwargs["embedding_backend"] = backend.strip().lower()
        threshold = os.getenv("POLISYOS_RAG_THRESHOLD")
        if threshold:
            kwargs["similarity_threshold"] = float(threshold)
        top_k = os.getenv("POLISYOS_RAG_TOP_K")
        if top_k:
            kwargs["top_k"] = int(top_k)
        domain_filter = os.getenv("POLISYOS_RAG_DOMAIN_FILTER")
        if domain_filter is not None:
            kwargs["domain_filter"] = _as_bool(domain_filter, default=True)
        max_chars = os.getenv("POLISYOS_RAG_MAX_FEW_SHOT_CHARS")
        if max_chars:
            kwargs["max_few_shot_chars"] = int(max_chars)
        max_entries = os.getenv("POLISYOS_RAG_MAX_ENTRIES")
        if max_entries:
            kwargs["max_entries"] = int(max_entries)
        freeze = os.getenv("POLISYOS_RAG_FREEZE_SNAPSHOT_PER_RUN")
        if freeze is not None:
            kwargs["freeze_snapshot_per_run"] = _as_bool(freeze, default=True)
        cas_root = os.getenv("POLISYOS_RAG_CAS_ROOT")
        if cas_root:
            kwargs["cas_root"] = cas_root
        return cls(**kwargs)


class ProblemFrameTextualizer:
    """Textualizer for both scientist-agent and canonical IR problem frames."""

    @staticmethod
    def to_text(problem_frame: Any) -> str:
        if isinstance(problem_frame, AgentProblemFrame):
            return ProblemFrameTextualizer._from_agent_problem_frame(problem_frame)
        return ProblemFrameTextualizer._from_unknown_problem_frame(problem_frame)

    @staticmethod
    def _from_agent_problem_frame(problem_frame: AgentProblemFrame) -> str:
        chunks: list[str] = []
        chunks.append(f"domain:{problem_frame.domain}")
        chunks.append(problem_frame.problem_statement)
        if problem_frame.goals:
            chunks.append("goals: " + "; ".join(problem_frame.goals[:8]))
        if problem_frame.constraints:
            chunks.append("constraints: " + "; ".join(problem_frame.constraints[:8]))
        if problem_frame.actors:
            chunks.append("actors: " + "; ".join(problem_frame.actors[:8]))
        return _normalize_text(" | ".join(chunks))[:1500]

    @staticmethod
    def _from_unknown_problem_frame(problem_frame: Any) -> str:
        if isinstance(problem_frame, dict):
            domain = str(problem_frame.get("domain", ""))
            narrative = str(
                problem_frame.get("narrative", "") or problem_frame.get("problem_id", "")
            )
            return _normalize_text(f"domain:{domain} | {narrative}")[:1500]

        domain = str(getattr(problem_frame, "domain", ""))
        narrative = str(
            getattr(problem_frame, "narrative", "")
            or getattr(problem_frame, "problem_statement", "")
            or getattr(problem_frame, "problem_id", "")
        )
        return _normalize_text(f"domain:{domain} | {narrative}")[:1500]


def _extract_domain(problem_frame: Any) -> str:
    value = getattr(problem_frame, "domain", "")
    if hasattr(value, "value"):
        return str(value.value).lower()
    return str(value).lower()


def _extract_problem_summary(problem_frame: Any) -> str:
    if isinstance(problem_frame, AgentProblemFrame):
        return _normalize_text(problem_frame.problem_statement)[:320]
    narrative = getattr(problem_frame, "narrative", None)
    if isinstance(narrative, str) and narrative.strip():
        return _normalize_text(narrative)[:320]
    pid = getattr(problem_frame, "problem_id", None)
    if isinstance(pid, str) and pid.strip():
        return pid[:320]
    return "Problem"


class CASRAGIndex:
    """In-memory RAG index with CAS persistence."""

    def __init__(
        self,
        embedder: EmbeddingBackend,
        *,
        similarity_threshold: float = 0.5,
    ) -> None:
        self._embedder = embedder
        self._threshold = float(similarity_threshold)
        self._entries: list[RAGCaseEntry] = []
        self._vectors = np.zeros((0, embedder.dimension), dtype=np.float32)
        self._seen_packet_refs: set[str] = set()
        self._domain_index: dict[str, list[int]] = {}
        self._snapshot_ref: str | None = None

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def snapshot_ref(self) -> str | None:
        return self._snapshot_ref

    def add_entry(self, entry: RAGCaseEntry, *, vector: np.ndarray | None = None) -> bool:
        if entry.decision_packet_ref in self._seen_packet_refs:
            return False

        encoded = vector
        if encoded is None:
            encoded = self._embedder.encode([entry.problem_text])
        if encoded.ndim == 1:
            encoded = encoded.reshape(1, -1)
        if encoded.shape[1] != self._embedder.dimension:
            raise ValueError("embedding dimension mismatch")
        encoded = _l2_normalize(encoded)

        idx = len(self._entries)
        self._entries.append(entry)
        self._seen_packet_refs.add(entry.decision_packet_ref)
        self._vectors = np.vstack([self._vectors, encoded]).astype(np.float32)
        self._domain_index.setdefault(entry.domain, []).append(idx)
        return True

    def search(
        self,
        problem_frame: Any,
        *,
        top_k: int = 3,
        domain_filter: bool = True,
        similarity_threshold: float | None = None,
        exclude_run_id: str | None = None,
    ) -> list[RAGSearchResult]:
        if self.size == 0:
            return []
        threshold = self._threshold if similarity_threshold is None else float(similarity_threshold)
        query_text = ProblemFrameTextualizer.to_text(problem_frame)
        query_vec = self._embedder.encode([query_text])[0]
        query_vec = _l2_normalize(query_vec.reshape(1, -1))[0]

        candidate_indices = list(range(self.size))
        if domain_filter:
            domain = _extract_domain(problem_frame)
            by_domain = self._domain_index.get(domain, [])
            if by_domain:
                candidate_indices = list(by_domain)

        if not candidate_indices:
            return []

        matrix = self._vectors[candidate_indices]
        scores = matrix @ query_vec

        ranked: list[tuple[int, float]] = []
        for local_idx, score in enumerate(scores.tolist()):
            idx = candidate_indices[local_idx]
            entry = self._entries[idx]
            if exclude_run_id and entry.run_id == exclude_run_id:
                continue
            score_f = float(score)
            if score_f < threshold:
                continue
            ranked.append((idx, score_f))

        ranked.sort(key=lambda item: (-item[1], self._entries[item[0]].decision_packet_ref))
        results: list[RAGSearchResult] = []
        for idx, score in ranked[:top_k]:
            results.append(RAGSearchResult(entry=self._entries[idx], similarity=score))
        return results

    def build_from_cas(self, cas: FileSystemCAS, *, max_entries: int = 10_000) -> int:
        indexed = 0
        for artifact_id in cas.iter_artifact_ids():
            if indexed >= max_entries:
                break
            try:
                manifest = cas.get_manifest(artifact_id)
            except _RAG_ARTIFACT_LOAD_ERRORS:
                continue
            if manifest.kind != "scientist.decision_packet":
                continue
            try:
                payload = from_canonical_bytes(cas.get_bytes(artifact_id))
            except _RAG_ARTIFACT_LOAD_ERRORS:
                continue
            entry = self._entry_from_decision_packet_payload(cas, payload, str(artifact_id))
            if entry is None:
                continue
            if self.add_entry(entry):
                indexed += 1
        return indexed

    def _entry_from_decision_packet_payload(
        self,
        cas: FileSystemCAS,
        payload: Any,
        decision_packet_ref: str,
    ) -> RAGCaseEntry | None:
        if not isinstance(payload, dict):
            return None

        run_id = str(payload.get("run_id") or "")
        governance = payload.get("governance")
        verdict = ""
        if isinstance(governance, dict):
            verdict = str(governance.get("verdict", "")).strip().upper()
        if verdict not in {"APPROVE", "APPROVED", "PASS"}:
            return None

        inputs = payload.get("inputs")
        if not isinstance(inputs, dict):
            return None
        trinity_ref = inputs.get("trinity_bundle_ref")
        trinity_ref_str = str(trinity_ref or "")
        if not trinity_ref_str.startswith("sha256:"):
            return None

        try:
            trinity_aid = ArtifactID.model_validate(trinity_ref_str)
            trinity_payload = from_canonical_bytes(cas.get_bytes(trinity_aid))
            trinity = TrinityBundle.model_validate(trinity_payload)
        except _RAG_ARTIFACT_LOAD_ERRORS:
            return None

        problem = trinity.problem_frame
        policy = trinity.policy_spec

        intervention_kinds: list[str] = []
        for intervention in policy.interventions[:5]:
            intervention_kinds.append(str(intervention.kind))
        intervention_summary = (
            ", ".join(intervention_kinds) if intervention_kinds else "No interventions"
        )

        metrics = payload.get("simulation_results")
        lesson = "No simulation summary"
        if isinstance(metrics, dict):
            numeric_items: list[str] = []
            for key, value in sorted(metrics.items()):
                if isinstance(value, (int, float)):
                    numeric_items.append(f"{key}={value:.4f}")
                if len(numeric_items) >= 3:
                    break
            if numeric_items:
                lesson = "; ".join(numeric_items)

        confidence = 0.7
        if isinstance(governance, dict):
            issues = governance.get("issues")
            if isinstance(issues, list):
                blockers = 0
                warnings = 0
                for issue in issues:
                    if not isinstance(issue, dict):
                        continue
                    severity = str(issue.get("severity", "")).lower()
                    if severity == "blocker":
                        blockers += 1
                    elif severity == "warning":
                        warnings += 1
                if blockers > 0:
                    confidence = 0.5
                elif warnings > 0:
                    confidence = 0.7
                else:
                    confidence = 0.9

        problem_text = ProblemFrameTextualizer.to_text(
            {
                "domain": problem.domain.value,
                "narrative": problem.narrative or problem.problem_id,
            }
        )
        return RAGCaseEntry(
            decision_packet_ref=decision_packet_ref,
            trinity_bundle_ref=trinity_ref_str,
            run_id=run_id,
            domain=problem.domain.value,
            problem_text=problem_text,
            problem_summary=_extract_problem_summary(problem),
            intervention_summary=intervention_summary[:500],
            lesson_learned=lesson[:220],
            confidence=confidence,
            indexed_at=_utc_now(),
        )

    def save(self, cas: FileSystemCAS) -> str:
        entries_payload = [asdict(item) for item in self._entries]
        entries_ref = cas.put_json(
            {"schema_version": RAG_SCHEMA_VERSION, "entries": entries_payload},
            PutOptions(
                kind=RAG_ENTRIES_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.rag_entries", version=RAG_SCHEMA_VERSION
                ),
                producer=ProducerInfo(component="scientist.agent.rag", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

        vectors_buf = io.BytesIO()
        np.save(vectors_buf, self._vectors, allow_pickle=False)
        vectors_bytes = vectors_buf.getvalue()
        vectors_ref = cas.put_bytes(
            vectors_bytes,
            PutOptions(
                kind=RAG_VECTORS_KIND,
                media_type="application/octet-stream",
                schema=SchemaInfo(
                    name="polisyos.scientist.rag_vectors", version=RAG_SCHEMA_VERSION
                ),
                producer=ProducerInfo(component="scientist.agent.rag", version="1.0"),
            ),
        )

        snapshot_payload = {
            "schema_version": RAG_SCHEMA_VERSION,
            "created_at": _utc_now(),
            "embedder_dimension": self._embedder.dimension,
            "threshold": self._threshold,
            "count": self.size,
            "entries_ref": str(entries_ref.artifact_id),
            "vectors_ref": str(vectors_ref.artifact_id),
        }
        snapshot_ref = cas.put_json(
            snapshot_payload,
            PutOptions(
                kind=RAG_SNAPSHOT_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.rag_snapshot", version=RAG_SCHEMA_VERSION
                ),
                producer=ProducerInfo(component="scientist.agent.rag", version="1.0"),
                inputs=[
                    InputRef(artifact_id=entries_ref.artifact_id, role="entries"),
                    InputRef(artifact_id=vectors_ref.artifact_id, role="vectors"),
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        self._snapshot_ref = str(snapshot_ref.artifact_id)
        return self._snapshot_ref

    @classmethod
    def load(
        cls,
        cas: FileSystemCAS,
        *,
        snapshot_ref: str,
        embedder: EmbeddingBackend,
    ) -> CASRAGIndex:
        snapshot_aid = ArtifactID.model_validate(snapshot_ref)
        snapshot_payload = from_canonical_bytes(cas.get_bytes(snapshot_aid))
        if not isinstance(snapshot_payload, dict):
            raise ValueError("invalid rag snapshot payload")

        entries_ref = ArtifactID.model_validate(str(snapshot_payload["entries_ref"]))
        vectors_ref = ArtifactID.model_validate(str(snapshot_payload["vectors_ref"]))

        entries_payload = from_canonical_bytes(cas.get_bytes(entries_ref))
        if not isinstance(entries_payload, dict):
            raise ValueError("invalid rag entries payload")
        raw_entries = entries_payload.get("entries", [])
        if not isinstance(raw_entries, list):
            raise ValueError("invalid rag entries payload")
        entries: list[RAGCaseEntry] = []
        for item in raw_entries:
            if not isinstance(item, dict):
                continue
            entries.append(RAGCaseEntry(**item))

        vectors_bytes = cas.get_bytes(vectors_ref)
        vectors_buf = io.BytesIO(vectors_bytes)
        vectors = np.load(vectors_buf, allow_pickle=False)
        if vectors.ndim != 2:
            raise ValueError("invalid rag vector matrix")
        if vectors.shape[1] != embedder.dimension:
            raise ValueError(
                f"rag snapshot dimension mismatch: snapshot={vectors.shape[1]} embedder={embedder.dimension}"
            )
        vectors = vectors.astype(np.float32)

        instance = cls(
            embedder=embedder,
            similarity_threshold=float(snapshot_payload.get("threshold", 0.5)),
        )
        instance._entries = entries
        instance._vectors = vectors
        instance._seen_packet_refs = {item.decision_packet_ref for item in entries}
        domain_index: dict[str, list[int]] = {}
        for idx, entry in enumerate(entries):
            domain_index.setdefault(entry.domain, []).append(idx)
        instance._domain_index = domain_index
        instance._snapshot_ref = snapshot_ref
        return instance

    def stats(self) -> dict[str, Any]:
        domain_counts = {domain: len(indices) for domain, indices in self._domain_index.items()}
        return {
            "size": self.size,
            "dimension": self._embedder.dimension,
            "threshold": self._threshold,
            "snapshot_ref": self._snapshot_ref,
            "domains": domain_counts,
        }


def find_latest_rag_snapshot_ref(cas: FileSystemCAS) -> str | None:
    """Find latest rag snapshot ref helper."""
    latest_ref: str | None = None
    latest_created = ""
    for artifact_id in cas.iter_artifact_ids():
        try:
            manifest = cas.get_manifest(artifact_id)
        except _RAG_ARTIFACT_LOAD_ERRORS:
            continue
        if manifest.kind != RAG_SNAPSHOT_KIND:
            continue
        created = manifest.created_at.isoformat()
        if created >= latest_created:
            latest_created = created
            latest_ref = str(artifact_id)
    return latest_ref


def build_or_load_rag_index(
    cas: FileSystemCAS,
    *,
    config: RAGConfig,
    embedder: EmbeddingBackend,
) -> CASRAGIndex:
    """Build or load rag index."""
    latest_ref = find_latest_rag_snapshot_ref(cas)
    if latest_ref:
        try:
            return CASRAGIndex.load(cas, snapshot_ref=latest_ref, embedder=embedder)
        except _RAG_ARTIFACT_LOAD_ERRORS:
            logger.warning("Failed to load RAG snapshot %s; rebuilding", latest_ref)

    index = CASRAGIndex(embedder=embedder, similarity_threshold=config.similarity_threshold)
    indexed = index.build_from_cas(cas, max_entries=config.max_entries)
    if indexed > 0:
        index.save(cas)
    return index


def format_few_shot_block(
    results: list[RAGSearchResult],
    *,
    max_chars: int = 6000,
) -> str:
    """Format few shot block helper."""
    if not results:
        return ""

    lines = [
        "## SIMILAR PAST DECISIONS (reference only, do not copy verbatim)",
        "",
    ]
    for idx, result in enumerate(results, start=1):
        entry = result.entry
        block = [
            "---",
            (
                f"Example {idx} [similarity={result.similarity:.2f}, "
                f"confidence={entry.confidence:.2f}, domain={entry.domain}]"
            ),
            f"Problem: {entry.problem_summary}",
            f"Successful approach: {entry.intervention_summary}",
            f"Key lesson: {entry.lesson_learned}",
        ]
        candidate = "\n".join(lines + block)
        if len(candidate) > max_chars:
            break
        lines.extend(block)

    lines.extend(
        [
            "---",
            "IMPORTANT: adapt to the current constraints and context.",
        ]
    )
    return "\n".join(lines)


def build_default_embedder(
    config: RAGConfig,
    *,
    provider_embed_fn: Callable[[list[str]], Sequence[Sequence[float]]] | None = None,
    provider_dimension: int = 256,
) -> EmbeddingBackend:
    """Build default embedder."""
    backend = config.embedding_backend.strip().lower()
    if backend == "provider" and provider_embed_fn is not None:
        return ProviderEmbeddingBackend(provider_embed_fn, dimension=provider_dimension)
    if backend == "provider":
        logger.warning(
            "RAG provider backend selected but no provider callback supplied; using hash"
        )
    return HashEmbeddingBackend(dimension=provider_dimension)
