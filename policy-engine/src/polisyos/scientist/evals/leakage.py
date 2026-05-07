"""Leakage and public-export guards for benchmark authority verdicts."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.search.benchmark_registry import FrontierBenchmarkBundle

__all__ = [
    "BenchmarkContaminationFinding",
    "HIDDEN_BENCHMARK_SPLITS",
    "detect_benchmark_contamination",
    "hidden_benchmark_ref_ids",
    "public_payload_contains_hidden_refs",
    "redact_hidden_benchmark_refs",
]

HIDDEN_BENCHMARK_SPLITS: tuple[str, ...] = ("hidden_holdout", "private")
_REDACTION = "[redacted:hidden_benchmark_ref]"


class BenchmarkContaminationFinding(BaseModel):
    """A hidden benchmark token appeared where a public payload can expose it."""

    model_config = ConfigDict(extra="forbid")

    token_kind: str = Field(min_length=1)
    token: str = Field(min_length=1)
    severity: str = Field(default="block", pattern="^(warning|block)$")
    message: str = Field(min_length=1)


def hidden_benchmark_ref_ids(bundle: FrontierBenchmarkBundle) -> set[str]:
    """Return artifact ids that must not appear in public exports."""

    refs: list[ArtifactRef] = []
    if bundle.hidden_holdout_evaluation_ref is not None:
        refs.append(bundle.hidden_holdout_evaluation_ref)
    return {str(ref.artifact_id) for ref in refs}


def public_payload_contains_hidden_refs(
    payload: Any,
    *,
    hidden_ref_ids: set[str],
) -> bool:
    """Return True when a public payload still contains a hidden benchmark id."""

    if not hidden_ref_ids:
        return False
    rendered = json.dumps(payload, sort_keys=True, default=str)
    return any(ref_id in rendered for ref_id in hidden_ref_ids)


def detect_benchmark_contamination(
    payload: Any,
    *,
    hidden_ref_ids: set[str],
    hidden_suite_ids: set[str] | None = None,
) -> list[BenchmarkContaminationFinding]:
    """Return hidden benchmark tokens found in a public/exportable payload."""

    rendered = json.dumps(payload, sort_keys=True, default=str)
    findings: list[BenchmarkContaminationFinding] = []
    for ref_id in sorted(hidden_ref_ids):
        if ref_id and ref_id in rendered:
            findings.append(
                BenchmarkContaminationFinding(
                    token_kind="artifact_id",
                    token=ref_id,
                    message="hidden benchmark artifact id leaked into public payload",
                )
            )
    for suite_id in sorted(hidden_suite_ids or set()):
        if suite_id and suite_id in rendered:
            findings.append(
                BenchmarkContaminationFinding(
                    token_kind="suite_id",
                    token=suite_id,
                    message="hidden benchmark suite id leaked into public payload",
                )
            )
    return findings


def redact_hidden_benchmark_refs(payload: Any, *, hidden_ref_ids: set[str]) -> Any:
    """Recursively redact hidden benchmark refs from a JSON-like payload."""

    if isinstance(payload, dict):
        return {
            str(key): redact_hidden_benchmark_refs(value, hidden_ref_ids=hidden_ref_ids)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [
            redact_hidden_benchmark_refs(item, hidden_ref_ids=hidden_ref_ids)
            for item in payload
        ]
    if isinstance(payload, str):
        redacted = payload
        for ref_id in sorted(hidden_ref_ids, key=len, reverse=True):
            if ref_id:
                redacted = redacted.replace(ref_id, _REDACTION)
        return redacted
    return payload
