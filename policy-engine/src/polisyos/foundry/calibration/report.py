from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, Field, ConfigDict


class CalibrationReport(BaseModel):
    """Артефакт результатов калибровки."""

    model_config = ConfigDict(extra="forbid")

    calibrated_params: Mapping[str, float] = Field(
        default_factory=dict, description="Плоский словарь (node_id.param -> value)."
    )
    total_loss: float
    per_target_loss: Mapping[str, float] = Field(default_factory=dict)
    loss_history: List[float] = Field(default_factory=list)
    series_comparison: Mapping[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Опционально: {target_id: {'real': [...], 'model': [...]}}",
    )
    diagnostics: List[str] = Field(default_factory=list)

