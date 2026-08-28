"""Run configuration embedding for cross-run nearest-neighbor search."""

from __future__ import annotations

import hashlib
import json
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.foundry import EmbedderProtocol
    from polisyos.scientist.methods.search.strategies.space import SearchSpace


def compute_space_hash(space: SearchSpace) -> str:
    """Compute a deterministic hash of the search space definition.

    Used to quickly identify structurally identical search spaces.
    """
    spec = []
    for b in space.bounds:
        entry = {
            "name": b.name,
            "lower": b.lower,
            "upper": b.upper,
            "dtype": b.dtype.value if hasattr(b.dtype, "value") else str(b.dtype),
        }
        if b.categories:
            entry["categories"] = list(b.categories)
        spec.append(entry)
    content = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def embed_run_config(
    space: SearchSpace,
    objectives: list[str],
    params_sample: list[dict[str, Any]] | None = None,
    embedder: EmbedderProtocol | None = None,
) -> list[float]:
    """Create a fixed-size embedding of a run configuration.

    If an embedder is provided, uses it to embed a text description
    of the run configuration.  Otherwise, falls back to a simple
    feature-based embedding.

    Parameters
    ----------
    space:
        Search space definition.
    objectives:
        List of objective names.
    params_sample:
        Optional sample of parameter dicts (for richer representation).
    embedder:
        Optional text embedder for semantic embedding.

    Returns
    -------
    list[float]
        Fixed-size embedding vector.
    """
    if embedder is not None:
        return _embed_with_text(space, objectives, params_sample, embedder)
    return _embed_structural(space, objectives, params_sample)


def _embed_with_text(
    space: SearchSpace,
    objectives: list[str],
    params_sample: list[dict[str, Any]] | None,
    embedder: EmbedderProtocol,
) -> list[float]:
    """Create embedding using text description."""
    parts = []
    parts.append(f"Search space with {space.dim} dimensions")
    for b in space.bounds:
        dtype = b.dtype.value if hasattr(b.dtype, "value") else str(b.dtype)
        parts.append(f"Parameter {b.name}: {dtype} [{b.lower}, {b.upper}]")
    parts.append(f"Objectives: {', '.join(objectives)}")
    text = ". ".join(parts)
    embeddings = embedder.embed([text])
    return embeddings[0]


def _embed_structural(
    space: SearchSpace,
    objectives: list[str],
    params_sample: list[dict[str, Any]] | None,
) -> list[float]:
    """Create a simple feature-based embedding (no external model).

    Returns a fixed-size (64-dim) vector encoding:
    * Number of dimensions (normalised)
    * Parameter type distribution
    * Objective count
    * Bound statistics (mean, std of ranges)
    """
    dim = 64
    vec = [0.0] * dim

    # Feature 0: number of dimensions (normalised)
    vec[0] = min(space.dim / 100.0, 1.0)

    # Features 1-4: parameter type counts (normalised)
    from polisyos.scientist.methods.search.strategies.types import ParameterType

    type_counts = dict.fromkeys(ParameterType, 0)
    for b in space.bounds:
        type_counts[b.dtype] = type_counts.get(b.dtype, 0) + 1
    total = max(len(space.bounds), 1)
    vec[1] = type_counts.get(ParameterType.CONTINUOUS, 0) / total
    vec[2] = type_counts.get(ParameterType.INTEGER, 0) / total
    vec[3] = type_counts.get(ParameterType.CATEGORICAL, 0) / total
    vec[4] = type_counts.get(ParameterType.LOG_CONTINUOUS, 0) / total

    # Feature 5: number of objectives
    vec[5] = min(len(objectives) / 10.0, 1.0)

    # Features 6-9: bound range statistics
    ranges = [b.upper - b.lower for b in space.bounds if b.categories is None]
    if ranges:
        vec[6] = sum(ranges) / len(ranges)  # mean range
        mean = vec[6]
        vec[7] = math.sqrt(sum((r - mean) ** 2 for r in ranges) / len(ranges))  # std
        vec[8] = min(ranges)
        vec[9] = max(ranges)

    # Features 10+: hash-based features from objective names
    for i, name in enumerate(objectives[:10]):
        h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
        vec[10 + i] = (h % 1000) / 1000.0

    # Normalise
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]

    return vec
