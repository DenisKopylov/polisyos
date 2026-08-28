"""Strict canonical evaluation-mode vocabulary for attempted evaluations."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

EvaluationMode = Literal[
    "simulate_only",
    "retrospective",
    "measurement_audit",
    "sandbox_pilot",
    "field_pilot",
    "deployment",
]
NamespacedEvaluationModeBlocker = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_.-]+@[0-9]+\.[0-9]+\.[0-9]+$"),
]

_MISSING = "polisyos.eval_safety.evaluation_mode_missing@1.0.0"
_INVALID = "polisyos.eval_safety.evaluation_mode_unknown@1.0.0"
_MODES = frozenset(get_args(EvaluationMode))


class EvaluationModeResolution(BaseModel):
    """Typed result of parsing one untrusted evaluation-mode token."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["accepted", "missing", "invalid"]
    canonical_mode: EvaluationMode | None
    blocker_code: NamespacedEvaluationModeBlocker | None
    source_token_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


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
