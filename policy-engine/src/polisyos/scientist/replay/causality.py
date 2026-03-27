"""Causality analysis for replay diffs — traces input diffs to output diffs."""
from __future__ import annotations

from dataclasses import dataclass

from polisyos.scientist.replay.diff import ReplayDiffResult


@dataclass(frozen=True)
class CausalLink:
    """A link between an input diff and an output diff."""

    input_path: str
    output_path: str
    confidence: float  # 0.0 - 1.0


def analyze_causality(
    input_diff: ReplayDiffResult,
    output_diff: ReplayDiffResult,
) -> list[CausalLink]:
    """Heuristic causality analysis: link input diffs to output diffs.

    Uses path prefix matching and co-occurrence scoring to estimate
    which input changes are likely to have caused output changes.
    """
    if not input_diff.field_diffs or not output_diff.field_diffs:
        return []

    links: list[CausalLink] = []
    input_paths = {d.path for d in input_diff.field_diffs}
    output_paths = {d.path for d in output_diff.field_diffs}

    for in_path in input_paths:
        in_parts = _split_path(in_path)
        for out_path in output_paths:
            out_parts = _split_path(out_path)
            confidence = _compute_confidence(in_parts, out_parts)
            if confidence > 0.0:
                links.append(CausalLink(
                    input_path=in_path,
                    output_path=out_path,
                    confidence=confidence,
                ))

    # Sort by confidence descending, deduplicate low-confidence noise
    links.sort(key=lambda l: l.confidence, reverse=True)
    return [l for l in links if l.confidence >= 0.1]


def _split_path(path: str) -> list[str]:
    """Split a dot/bracket path into segments."""
    result: list[str] = []
    for part in path.replace("[", ".").replace("]", "").split("."):
        if part:
            result.append(part)
    return result


def _compute_confidence(in_parts: list[str], out_parts: list[str]) -> float:
    """Compute causal confidence based on shared path segments."""
    if not in_parts or not out_parts:
        return 0.0

    # Shared prefix length
    shared = 0
    for a, b in zip(in_parts, out_parts):
        if a == b:
            shared += 1
        else:
            break

    if shared == 0:
        # Check for shared segments (non-prefix)
        in_set = set(in_parts)
        out_set = set(out_parts)
        overlap = in_set & out_set
        if overlap:
            return len(overlap) / max(len(in_set), len(out_set)) * 0.3
        return 0.0

    # Prefix-based confidence: longer prefix → higher confidence
    max_depth = max(len(in_parts), len(out_parts))
    return min(1.0, shared / max_depth + 0.2)
