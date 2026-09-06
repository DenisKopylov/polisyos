"""Strict canonical evaluation-mode vocabulary for attempted evaluations."""

from __future__ import annotations

import hashlib
from typing import get_args

from polisyos.pdc import EvaluationMode, EvaluationModeResolution

_MISSING = "polisyos.eval_safety.evaluation_mode_missing@1.0.0"
_INVALID = "polisyos.eval_safety.evaluation_mode_unknown@1.0.0"
_MODES = frozenset(get_args(EvaluationMode))


def resolve_evaluation_mode(token: str | None) -> EvaluationModeResolution:
    """Resolve a mode without trimming, aliasing, or simulation fallback."""

    digest = "sha256:" + hashlib.sha256(
        ("<missing>" if token is None else token).encode("utf-8")
    ).hexdigest()
    if token is None or token == "":
        return EvaluationModeResolution(
            status="missing",
            canonical_mode=None,
            blocker_code=_MISSING,
            source_token_hash=digest,
        )
    if token not in _MODES:
        return EvaluationModeResolution(
            status="invalid",
            canonical_mode=None,
            blocker_code=_INVALID,
            source_token_hash=digest,
        )
    return EvaluationModeResolution(
        status="accepted",
        canonical_mode=token,
        blocker_code=None,
        source_token_hash=digest,
    )


__all__ = ["EvaluationMode", "EvaluationModeResolution", "resolve_evaluation_mode"]
