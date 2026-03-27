"""LLM call provenance record."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LLMCallRecord(BaseModel):
    """Records provenance metadata for a single LLM API call."""
    model_config = ConfigDict(extra="forbid")

    call_id: str
    model_id: str
    temperature: float
    seed: int | None = None
    system_prompt_hash: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: Decimal | None = None
    trace_id: str | None = None
    span_id: str | None = None
    node_alias: str | None = None
    timestamp: datetime
