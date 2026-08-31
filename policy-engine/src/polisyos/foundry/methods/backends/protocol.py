"""Define shared protocols and implementations for concrete method backends.

`MethodRunner` is the execution-side counterpart to the declarative
`MethodSignature` ABI. Runners accept a protocol-compliant method class plus
materialized state/params, invoke the implementation on a concrete backend,
and return `MethodResult` with timing, solver status, and reproducibility
metadata. This module also owns generic text-embedding backends used by
Foundry methods and typed Scientist consumers.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, cast, runtime_checkable

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.backends.validated import ValidatedBound
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature


@runtime_checkable
class EmbedderProtocol(Protocol):
    """Define the common interface for text-embedding implementations."""

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - protocol
        """Embed a batch of texts into fixed-size vectors."""
        ...

    @property
    def dim(self) -> int:  # pragma: no cover - protocol
        """Return the embedding dimensionality."""
        ...


_TOKENIZE_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    """Tokenize text case-insensitively on Unicode word boundaries."""
    return _TOKENIZE_RE.findall(text.lower())


class TFIDFEmbedder:
    """Build dependency-free, fixed-size TF-IDF text embeddings.

    Call :meth:`fit` before :meth:`embed` to establish the vocabulary and
    inverse-document-frequency weights.
    """

    def __init__(self, max_features: int = 512) -> None:
        self._max_features = max_features
        self._vocab: dict[str, int] = {}
        self._idf: list[float] = []
        self._fitted = False

    @property
    def dim(self) -> int:
        """Return the fitted vocabulary size or configured pre-fit capacity."""
        return len(self._vocab) if self._fitted else self._max_features

    def fit(self, corpus: list[str]) -> None:
        """Build the vocabulary and inverse-document-frequency weights."""
        if not corpus:
            self._fitted = True
            return

        n_docs = len(corpus)
        document_frequency: Counter[str] = Counter()
        for text in corpus:
            for token in set(_tokenize(text)):
                document_frequency[token] += 1

        top_terms = [
            term for term, _count in document_frequency.most_common(self._max_features)
        ]
        self._vocab = {term: index for index, term in enumerate(top_terms)}
        self._idf = [
            math.log(n_docs / (1 + document_frequency.get(term, 0))) for term in top_terms
        ]
        self._fitted = True

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts as L2-normalized TF-IDF vectors."""
        if not self._fitted:
            raise RuntimeError("TFIDFEmbedder.fit() must be called before embed()")

        results: list[list[float]] = []
        vocab_size = len(self._vocab)
        for text in texts:
            if vocab_size == 0:
                results.append([0.0])
                continue

            tokens = _tokenize(text)
            term_frequency: Counter[str] = Counter(tokens)
            token_count = len(tokens) or 1
            vector = [0.0] * vocab_size
            for token, count in term_frequency.items():
                index = self._vocab.get(token)
                if index is not None:
                    vector[index] = (count / token_count) * self._idf[index]

            norm = math.sqrt(sum(value * value for value in vector))
            if norm > 0:
                vector = [value / norm for value in vector]
            results.append(vector)
        return results


class SentenceTransformerEmbedder:
    """Adapt the optional sentence-transformers backend to `EmbedderProtocol`."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for SentenceTransformerEmbedder.  "
                "Install it with: pip install sentence-transformers"
            ) from None
        self._model = SentenceTransformer(model_name)
        self._dim = cast("int", self._model.get_sentence_embedding_dimension())

    @property
    def dim(self) -> int:
        """Return the model's sentence-embedding dimensionality."""
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts with the configured sentence-transformer model."""
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [embedding.tolist() for embedding in embeddings]


class SolverStatus(str, Enum):
    """Normalize solver termination statuses reported by optimization backends."""

    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    TIMEOUT = "timeout"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MethodTiming:
    """Record wall/CPU/compile timings for one method execution."""

    wall_time_ms: float
    cpu_time_ms: float | None = None
    compile_time_ms: float | None = None


@dataclass(frozen=True, slots=True)
class ReproducibilityInfo:
    """Capture backend, determinism, seed, and solver metadata for replay audits."""

    backend: ComputeBackend
    determinism_tier: DeterminismTier
    seed: int | None = None
    library_versions: Mapping[str, str] = field(default_factory=dict)
    solver_status: SolverStatus | None = None
    solver_gap: float | None = None
    solver_iterations: int | None = None
    fingerprint: str | None = None
    observed_tolerance_budget: Mapping[str, Any] = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True, slots=True)
class MethodResult:
    """Wrap backend output together with declared slot outputs and diagnostics.

    `output` is the backend-native return value from `pure_step`, while
    `slot_outputs` is the optional dematerialized view aligned to
    `MethodSignature.output_slots`. `artifacts` carries backend-specific
    sidecar payloads that can later be persisted as provenance evidence.
    `cross_backend_equivalence_ref` points at an external certificate artifact
    that captures the runtime-specific backend-equivalence contract, while
    `validated_bound` carries the complementary critical-numerics certificate.
    """

    output: Any
    timing: MethodTiming
    reproducibility: ReproducibilityInfo
    cross_backend_equivalence_ref: str | None = None
    slot_outputs: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    validated_bound: ValidatedBound | None = None


class MethodRunner(Protocol):
    """Execute one method class on a concrete backend runtime.

    Implementations should be deterministic according to the advertised
    `ReproducibilityInfo.determinism_tier` for identical state, params, seed,
    and runtime stack.
    """

    @property
    def supported_backends(self) -> frozenset[ComputeBackend]: ...

    def is_available(self) -> bool: ...

    def execute(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        seed: int,
    ) -> MethodResult:
        """Run one method invocation and return a structured result envelope."""
        ...
