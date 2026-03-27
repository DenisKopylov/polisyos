"""Tests for TFIDFEmbedder — WS5 neural search support."""
from __future__ import annotations

import math
import sys

import pytest

sys.path.insert(0, "src")

from polisyos.scientist.agent.embedder import TFIDFEmbedder


class TestFitAndEmbed:
    def test_fit_and_embed(self) -> None:
        corpus = [
            "fiscal policy tax reform",
            "monetary policy interest rates",
            "public health spending budget",
        ]
        embedder = TFIDFEmbedder(max_features=64)
        embedder.fit(corpus)

        vectors = embedder.embed(["tax reform policy"])
        assert len(vectors) == 1
        assert len(vectors[0]) == embedder.dim
        assert embedder.dim > 0


class TestEmbedWithoutFit:
    def test_embed_without_fit_raises(self) -> None:
        embedder = TFIDFEmbedder()
        with pytest.raises(RuntimeError, match="fit.*must be called"):
            embedder.embed(["some text"])


class TestEmbedEmptyCorpus:
    def test_embed_empty_corpus(self) -> None:
        embedder = TFIDFEmbedder()
        embedder.fit([])
        # Should not raise; returns zero-like vectors
        vectors = embedder.embed(["some text"])
        assert len(vectors) == 1


class TestL2Normalised:
    def test_l2_normalised(self) -> None:
        corpus = [
            "fiscal policy tax reform budget",
            "monetary policy interest rates central bank",
            "public health spending budget allocation",
            "education reform school funding",
        ]
        embedder = TFIDFEmbedder(max_features=128)
        embedder.fit(corpus)

        vectors = embedder.embed(["tax reform fiscal policy"])
        vec = vectors[0]
        norm = math.sqrt(sum(v * v for v in vec))

        # Non-zero vector should have unit norm (approximately)
        if norm > 0:
            assert abs(norm - 1.0) < 1e-6, f"Expected unit norm, got {norm}"
