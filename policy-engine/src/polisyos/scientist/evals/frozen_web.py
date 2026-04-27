"""Frozen-web benchmark pack contracts for deep research evals."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef

__all__ = [
    "FrozenWebDocument",
    "FrozenWebHarnessConfig",
    "FrozenWebPack",
    "FrozenWebTask",
    "FrozenWebVisibility",
]


class FrozenWebVisibility(StrEnum):
    """Visibility for frozen-web benchmark assets."""

    PUBLIC = "public"
    PRIVATE = "private"
    HIDDEN = "hidden"


class FrozenWebDocument(BaseModel):
    """One frozen source document used by an eval task."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    content_ref: ArtifactRef
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    visibility: FrozenWebVisibility = FrozenWebVisibility.PRIVATE
    untrusted_source_text: bool = True


class FrozenWebTask(BaseModel):
    """One multi-hop deep research task over frozen documents."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected_source_ids: list[str] = Field(default_factory=list)
    answer_key_ref: ArtifactRef | None = None
    visibility: FrozenWebVisibility = FrozenWebVisibility.PRIVATE


class FrozenWebPack(BaseModel):
    """RetroSearch-like frozen-web pack for offline deep research evaluation."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    documents: list[FrozenWebDocument] = Field(default_factory=list)
    tasks: list[FrozenWebTask] = Field(default_factory=list)
    hidden_holdout_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _expected_sources_exist(self) -> FrozenWebPack:
        source_ids = {item.document_id for item in self.documents}
        missing = sorted(
            {
                source_id
                for task in self.tasks
                for source_id in task.expected_source_ids
                if source_id not in source_ids
            }
        )
        if missing:
            raise ValueError(f"frozen web tasks reference unknown documents: {missing}")
        return self


class FrozenWebHarnessConfig(BaseModel):
    """Execution contract for offline frozen-web evaluation harnesses."""

    model_config = ConfigDict(extra="forbid")

    max_documents_per_task: int = Field(default=16, ge=1, le=256)
    max_extracted_chars_per_document: int = Field(default=20_000, ge=512, le=500_000)
    allow_live_web: bool = False

    @model_validator(mode="after")
    def _live_web_stays_off(self) -> FrozenWebHarnessConfig:
        if self.allow_live_web:
            raise ValueError("frozen web eval harness must not use live web in Phase 1.5")
        return self
