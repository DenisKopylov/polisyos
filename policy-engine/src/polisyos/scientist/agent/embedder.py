"""Text embedding abstractions for vector-based search and memory.

Provides a protocol and two implementations:
* ``TFIDFEmbedder`` — lightweight, no external model dependencies.
* ``SentenceTransformerEmbedder`` — optional, uses sentence-transformers.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbedderProtocol(Protocol):
    """Protocol for text embedding implementations."""

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - protocol
        """Embed a batch of texts into fixed-size vectors."""
        ...

    @property
    def dim(self) -> int:  # pragma: no cover - protocol
        """Embedding dimensionality."""
        ...


_TOKENIZE_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    return _TOKENIZE_RE.findall(text.lower())


class TFIDFEmbedder:
    """Lightweight TF-IDF based embedder.

    No external model dependencies — builds a vocabulary from a corpus
    and produces fixed-size embeddings using TF-IDF weights.

    Call ``fit()`` before ``embed()``.
    """

    def __init__(self, max_features: int = 512) -> None:
        self._max_features = max_features
        self._vocab: dict[str, int] = {}
        self._idf: list[float] = []
        self._fitted = False

    @property
    def dim(self) -> int:
        return len(self._vocab) if self._fitted else self._max_features

    def fit(self, corpus: list[str]) -> None:
        """Build vocabulary and compute IDF from a corpus."""
        if not corpus:
            self._fitted = True
            return

        # Count document frequency per term
        n_docs = len(corpus)
        df: Counter[str] = Counter()
        for text in corpus:
            tokens = set(_tokenize(text))
            for token in tokens:
                df[token] += 1

        # Select top-k features by document frequency
        top_terms = [t for t, _ in df.most_common(self._max_features)]
        self._vocab = {term: idx for idx, term in enumerate(top_terms)}

        # Compute IDF: log(N / (1 + df))
        self._idf = [
            math.log(n_docs / (1 + df.get(term, 0)))
            for term in top_terms
        ]
        self._fitted = True

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using TF-IDF vectors.

        Returns zero vectors for empty or unknown texts.
        """
        if not self._fitted:
            raise RuntimeError("TFIDFEmbedder.fit() must be called before embed()")

        results: list[list[float]] = []
        vocab_size = len(self._vocab)

        for text in texts:
            if vocab_size == 0:
                results.append([0.0])
                continue

            tokens = _tokenize(text)
            tf: Counter[str] = Counter(tokens)
            total = len(tokens) or 1

            vec = [0.0] * vocab_size
            for token, count in tf.items():
                idx = self._vocab.get(token)
                if idx is not None:
                    vec[idx] = (count / total) * self._idf[idx]

            # L2 normalise
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]

            results.append(vec)
        return results


class SentenceTransformerEmbedder:
    """Optional embedding via sentence-transformers.

    Import-guarded: requires ``sentence-transformers`` to be installed.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for SentenceTransformerEmbedder.  "
                "Install it with: pip install sentence-transformers"
            ) from None
        self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_sentence_embedding_dimension()

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [e.tolist() for e in embeddings]
