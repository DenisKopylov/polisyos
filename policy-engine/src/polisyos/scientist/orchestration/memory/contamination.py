"""Hidden-eval and canary contamination guards for reusable memory."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.evals.leakage import detect_benchmark_contamination
from polisyos.scientist.methods.search.lessons import LessonCard

FORBIDDEN_MEMORY_KEY_TOKENS: tuple[str, ...] = (
    "hidden_benchmark",
    "hidden_eval",
    "hidden_holdout",
    "private_eval",
    "hidden_suite",
    "sentinel_answer",
    "canary",
)


class MemoryContaminationFinding(BaseModel):
    """One hidden-eval/canary token found in reusable-memory payload."""

    model_config = ConfigDict(extra="forbid")

    token_kind: str = Field(min_length=1)
    token: str = Field(min_length=1)
    severity: str = Field(default="block", pattern="^(warning|block)$")
    message: str = Field(min_length=1)


class MemoryContaminationPolicy(BaseModel):
    """Explicit hidden identifiers that must never enter reusable memory."""

    model_config = ConfigDict(extra="forbid")

    hidden_ref_ids: set[str] = Field(default_factory=set)
    hidden_suite_ids: set[str] = Field(default_factory=set)
    canary_tokens: set[str] = Field(default_factory=set)


def lesson_payload_for_contamination(lesson: LessonCard) -> dict[str, Any]:
    """Return the memory-relevant lesson payload scanned before reuse."""

    return lesson.model_dump(mode="json")


def detect_memory_contamination(
    payload: Any,
    *,
    policy: MemoryContaminationPolicy | None = None,
) -> list[MemoryContaminationFinding]:
    """Detect hidden benchmark ids, suite ids, canaries and hidden metadata keys."""

    active_policy = policy or MemoryContaminationPolicy()
    findings: list[MemoryContaminationFinding] = [
        MemoryContaminationFinding(
            token_kind=finding.token_kind,
            token=finding.token,
            severity=finding.severity,
            message=finding.message,
        )
        for finding in detect_benchmark_contamination(
            payload,
            hidden_ref_ids=active_policy.hidden_ref_ids,
            hidden_suite_ids=active_policy.hidden_suite_ids,
        )
    ]
    rendered = json.dumps(payload, sort_keys=True, default=str)
    for canary in sorted(active_policy.canary_tokens):
        if canary and canary in rendered:
            findings.append(
                MemoryContaminationFinding(
                    token_kind="canary",
                    token=canary,
                    message="hidden eval canary token appeared in reusable memory payload",
                )
            )
    findings.extend(_detect_forbidden_keys(payload))
    return _dedupe_findings(findings)


def assert_reusable_memory_clean(
    payload: Any,
    *,
    policy: MemoryContaminationPolicy | None = None,
) -> None:
    """Raise when reusable memory contains hidden eval ids or canaries."""

    findings = detect_memory_contamination(payload, policy=policy)
    if findings:
        tokens = ", ".join(f"{finding.token_kind}:{finding.token}" for finding in findings)
        raise ValueError(f"reusable memory contamination detected: {tokens}")


def _detect_forbidden_keys(value: Any, *, path: str = "payload") -> list[MemoryContaminationFinding]:
    findings: list[MemoryContaminationFinding] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            for token in FORBIDDEN_MEMORY_KEY_TOKENS:
                if token in lowered:
                    findings.append(
                        MemoryContaminationFinding(
                            token_kind="metadata_key",
                            token=key_text,
                            message=f"hidden eval metadata key cannot enter reusable memory: {path}.{key_text}",
                        )
                    )
            findings.extend(_detect_forbidden_keys(item, path=f"{path}.{key_text}"))
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            findings.extend(_detect_forbidden_keys(item, path=f"{path}[{index}]"))
    return findings


def _dedupe_findings(
    findings: list[MemoryContaminationFinding],
) -> list[MemoryContaminationFinding]:
    seen: set[tuple[str, str, str]] = set()
    output: list[MemoryContaminationFinding] = []
    for finding in findings:
        key = (finding.token_kind, finding.token, finding.message)
        if key in seen:
            continue
        seen.add(key)
        output.append(finding)
    return output


__all__ = [
    "FORBIDDEN_MEMORY_KEY_TOKENS",
    "MemoryContaminationFinding",
    "MemoryContaminationPolicy",
    "assert_reusable_memory_clean",
    "detect_memory_contamination",
    "lesson_payload_for_contamination",
]
