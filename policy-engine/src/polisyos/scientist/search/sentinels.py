"""Sentinel candidates and deterministic injection protocol."""

from __future__ import annotations

import json
import hashlib
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes

SENTINEL_METADATA_KEY = "__sentinel__"
_SENTINEL_SET_KIND = "scientist.search.sentinel_set"
_SENTINEL_SET_SCHEMA = SchemaInfo(
    name="polisyos.scientist.search.SentinelSet",
    version="1.0",
)


def _stable_candidate_hash(candidate: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in candidate.items()
        if not str(key).startswith("__")
    }
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


class SentinelKind(str, Enum):
    """Sentinel kind public type."""
    CALIBRATION = "calibration"
    REGRESSION = "regression"


class SentinelCandidate(BaseModel):
    """Known-good sentinel candidate used for calibration health checks."""

    model_config = ConfigDict(extra="forbid")

    sentinel_id: str = Field(min_length=1)
    kind: SentinelKind
    candidate: dict[str, Any] = Field(default_factory=dict)
    candidate_hash: str | None = None
    expected_stage_a_pass: bool = True
    expected_stage_b_approve: bool = True
    expected_min_level: int = Field(default=2, ge=0)
    source_candidate_ref: ArtifactRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fill_candidate_hash(self) -> "SentinelCandidate":
        if not self.candidate_hash:
            self.candidate_hash = _stable_candidate_hash(self.candidate)
        return self


class SentinelSet(BaseModel):
    """Set of sentinels with deterministic injection policy."""

    model_config = ConfigDict(extra="forbid")

    set_id: str = Field(min_length=1)
    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    suite_id: str = Field(min_length=1)
    suite_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    sentinels: list[SentinelCandidate] = Field(default_factory=list)
    injection_rate: int = Field(default=20, ge=1)
    pass_rate_floor: float = Field(default=0.9, ge=0.0, le=1.0)


class SentinelObservation(BaseModel):
    """Recorded sentinel pass/fail observation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    sentinel_id: str = Field(min_length=1)
    kind: SentinelKind
    candidate_hash: str = Field(min_length=1)
    final_action: str = Field(min_length=1)
    level_reached: int = Field(ge=0)
    stage_a_passed: bool | None = None
    stage_b_approved: bool | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_outcome(
        cls,
        sentinel: SentinelCandidate,
        outcome: Any,
    ) -> "SentinelObservation":
        stage_results = getattr(outcome, "stage_results", {}) or {}
        sorted_levels = sorted(stage_results)
        level_reached = sorted_levels[-1] if sorted_levels else 0
        stage_a_result = stage_results.get(2) or stage_results.get(1) or stage_results.get(0)
        stage_b_result = None
        for level in sorted_levels:
            if level >= 4:
                stage_b_result = stage_results[level]
                break
        return cls(
            sentinel_id=sentinel.sentinel_id,
            kind=sentinel.kind,
            candidate_hash=sentinel.candidate_hash or "",
            final_action=str(getattr(outcome, "final_action", "unknown")),
            level_reached=level_reached,
            stage_a_passed=(
                None if stage_a_result is None else bool(getattr(stage_a_result, "is_promising", False))
            ),
            stage_b_approved=(
                None if stage_b_result is None else bool(getattr(stage_b_result, "is_promising", False))
            ),
            metadata={"ticket_id": getattr(outcome, "ticket_id", None)},
        )


def extract_sentinel_metadata(candidate: dict[str, Any]) -> dict[str, Any] | None:
    """Extract sentinel metadata helper."""
    raw = candidate.get(SENTINEL_METADATA_KEY)
    return raw if isinstance(raw, dict) else None


def strip_internal_candidate_metadata(candidate: dict[str, Any]) -> dict[str, Any]:
    """Strip internal candidate metadata helper."""
    return {
        key: value
        for key, value in candidate.items()
        if not str(key).startswith("__")
    }


def persist_sentinel_set(
    store: FileSystemCAS,
    sentinel_set: SentinelSet,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist sentinel set helper."""
    return store.put_json(
        sentinel_set,
        PutOptions(
            kind=_SENTINEL_SET_KIND,
            media_type="application/json",
            schema=_SENTINEL_SET_SCHEMA,
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_sentinel_set(store: FileSystemCAS, ref: ArtifactRef | str) -> SentinelSet:
    """Load sentinel set."""
    artifact_id = ref.artifact_id if isinstance(ref, ArtifactRef) else ref
    return SentinelSet.model_validate(from_canonical_bytes(store.get_bytes(artifact_id)))


class SentinelInjector:
    """Wrapper-based deterministic sentinel injection."""

    def __init__(self, sentinel_set: SentinelSet):
        self._sentinel_set = sentinel_set
        self._cursor = 0
        self._regulars_since_last = 0
        self._sentinel_due = False

    def inject_batch(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self._sentinel_set.sentinels:
            return list(candidates)
        injected: list[dict[str, Any]] = []
        for candidate in candidates:
            injected.append(candidate)
            self._regulars_since_last += 1
            if self._regulars_since_last >= self._sentinel_set.injection_rate:
                injected.append(self._decorated_sentinel(self._next_sentinel()))
                self._regulars_since_last = 0
        return injected

    def wrap_candidate_generator(self, generator: Any) -> Any:
        injector = self

        class _WrappedGenerator:
            def generate(self, history, current_best, context):
                if injector._sentinel_due and injector._sentinel_set.sentinels:
                    injector._sentinel_due = False
                    return injector._decorated_sentinel(injector._next_sentinel())
                candidate = generator.generate(history, current_best, context)
                injector._regulars_since_last += 1
                if injector._regulars_since_last >= injector._sentinel_set.injection_rate:
                    injector._regulars_since_last = 0
                    injector._sentinel_due = True
                return candidate

            def generate_batch(self, history, current_best, context, batch_size):
                if hasattr(generator, "generate_batch") and callable(generator.generate_batch):
                    batch = generator.generate_batch(history, current_best, context, batch_size)
                else:
                    batch = [
                        generator.generate(history, current_best, context)
                        for _ in range(batch_size)
                    ]
                return injector.inject_batch(batch)

        return _WrappedGenerator()

    def wrap_batch_generator(self, generator: Any) -> Any:
        return self.wrap_candidate_generator(generator)

    def _next_sentinel(self) -> SentinelCandidate:
        sentinels = self._sentinel_set.sentinels
        sentinel = sentinels[self._cursor % len(sentinels)]
        self._cursor += 1
        return sentinel

    def _decorated_sentinel(self, sentinel: SentinelCandidate) -> dict[str, Any]:
        candidate = strip_internal_candidate_metadata(sentinel.candidate)
        candidate[SENTINEL_METADATA_KEY] = {
            "sentinel_id": sentinel.sentinel_id,
            "sentinel_kind": sentinel.kind.value,
            "candidate_hash": sentinel.candidate_hash,
            "expected_stage_a_pass": sentinel.expected_stage_a_pass,
            "expected_stage_b_approve": sentinel.expected_stage_b_approve,
            "expected_min_level": sentinel.expected_min_level,
            **sentinel.metadata,
        }
        return candidate


__all__ = [
    "SENTINEL_METADATA_KEY",
    "SentinelCandidate",
    "SentinelInjector",
    "SentinelKind",
    "SentinelObservation",
    "SentinelSet",
    "extract_sentinel_metadata",
    "load_sentinel_set",
    "persist_sentinel_set",
    "strip_internal_candidate_metadata",
]
