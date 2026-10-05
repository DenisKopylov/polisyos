"""Strict canonical evaluation-mode vocabulary for attempted evaluations."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import get_args

from polisyos.pdc import EvaluationMode, EvaluationModeResolution

_MISSING = "polisyos.eval_safety.evaluation_mode_missing@1.0.0"
_INVALID = "polisyos.eval_safety.evaluation_mode_unknown@1.0.0"
_MODES = frozenset(get_args(EvaluationMode))
EVAL_SAFETY_REQUIRED_MODES = frozenset(
    {"sandbox_pilot", "field_pilot", "deployment"}
)
DATA_TRUST_REQUIRED_MODES = frozenset({"retrospective", "measurement_audit"})


class ExecutionIntentBand(StrEnum):
    """Owner dispatch bands for every canonical evaluation intent."""

    CANDIDATE_ONLY = "candidate_only"
    SIMULATE_ONLY_ATTEMPT = "simulate_only_attempt"
    DATA_TRUST_REQUIRED = "data_trust_required"
    EVAL_SAFETY_REQUIRED = "eval_safety_required"
    NOT_ESTABLISHED = "not_established"


def resolve_execution_intent_band(
    *,
    attempt_present: bool,
    mode_resolution: EvaluationModeResolution,
) -> ExecutionIntentBand:
    """Map the canonical mode owner result to one stable execution band.

    The function does not admit authority. It only prevents consumers from
    maintaining their own divergent mode-to-owner tables.
    """

    if not attempt_present:
        return ExecutionIntentBand.CANDIDATE_ONLY
    if mode_resolution.status != "accepted" or mode_resolution.canonical_mode is None:
        return ExecutionIntentBand.NOT_ESTABLISHED
    mode = mode_resolution.canonical_mode
    if mode == "simulate_only":
        return ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT
    if mode in DATA_TRUST_REQUIRED_MODES:
        return ExecutionIntentBand.DATA_TRUST_REQUIRED
    if mode in EVAL_SAFETY_REQUIRED_MODES:
        return ExecutionIntentBand.EVAL_SAFETY_REQUIRED
    return ExecutionIntentBand.NOT_ESTABLISHED


def execution_intent_band_for_mode(mode: str | None) -> ExecutionIntentBand:
    """Resolve the band for a canonical mode already carried by a runtime leaf."""

    if mode == "candidate_only":
        return ExecutionIntentBand.CANDIDATE_ONLY
    resolution = resolve_evaluation_mode(mode)
    if resolution.status != "accepted":
        return ExecutionIntentBand.NOT_ESTABLISHED
    return resolve_execution_intent_band(
        attempt_present=True,
        mode_resolution=resolution,
    )


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


__all__ = [
    "DATA_TRUST_REQUIRED_MODES",
    "EVAL_SAFETY_REQUIRED_MODES",
    "EvaluationMode",
    "EvaluationModeResolution",
    "ExecutionIntentBand",
    "execution_intent_band_for_mode",
    "resolve_evaluation_mode",
    "resolve_execution_intent_band",
]
