"""Public claims conflicts package API."""
from __future__ import annotations

from .detect import detect_conflicts
from .key import compare_v1, conflict_key_v1, normalize_text_v1, value_signature_v1
from .policies import DEFAULT_POLICY, ConflictPolicy, get_conflict_policy
from .resolve import rank_conflict_candidates, resolve_conflicts
from .types import (
    ConflictDetectOptions,
    ConflictDetectResult,
    ConflictResolveOptions,
    ConflictResolveResult,
    RankedClaim,
)

__all__ = [
    "ConflictDetectOptions",
    "ConflictDetectResult",
    "ConflictPolicy",
    "ConflictResolveOptions",
    "ConflictResolveResult",
    "DEFAULT_POLICY",
    "RankedClaim",
    "compare_v1",
    "conflict_key_v1",
    "detect_conflicts",
    "get_conflict_policy",
    "normalize_text_v1",
    "rank_conflict_candidates",
    "resolve_conflicts",
    "value_signature_v1",
]
