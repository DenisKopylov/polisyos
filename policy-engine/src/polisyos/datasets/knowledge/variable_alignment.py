"""Variable alignment utilities for canonical SKG vars -> dataset vars."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class AlignmentMethod(str, Enum):
    EXACT = "exact"
    SEMANTIC = "semantic"
    META_ANALYTIC = "meta_analytic"


class VariableAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_var: str
    dataset_var: str
    dataset_id: str
    method: AlignmentMethod
    confidence: float
    evidence: str
    is_proxy: bool = False
    proxy_penalty: float = 0.0


def load_seed_alignments(path: Path) -> list[VariableAlignment]:
    """Load exact seed alignments from YAML."""
    with open(path, "r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    if not isinstance(payload, dict):
        raise ValueError("seed alignments payload must be a mapping")

    raw = payload.get("alignments", [])
    if not isinstance(raw, list):
        raise ValueError("'alignments' must be a list")

    out: list[VariableAlignment] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            VariableAlignment(
                canonical_var=str(item.get("canonical_var", "")).strip(),
                dataset_var=str(item.get("dataset_var", "")).strip(),
                dataset_id=str(item.get("dataset_id", "")).strip(),
                method=AlignmentMethod(str(item.get("method", "exact")).strip().lower()),
                confidence=float(item.get("confidence", 0.0)),
                evidence=str(item.get("evidence", "")).strip(),
                is_proxy=bool(item.get("is_proxy", False)),
                proxy_penalty=float(item.get("proxy_penalty", 0.0)),
            )
        )
    return out


def align_semantic(*_args, **_kwargs) -> list[VariableAlignment]:
    """Placeholder for embedding-based alignment (out of scope in 0b)."""
    raise NotImplementedError("AlignmentMethod.SEMANTIC is deferred beyond phase 0b.")


def align_meta_analytic(*_args, **_kwargs) -> list[VariableAlignment]:
    """Placeholder for SKG/meta-analytic alignment (out of scope in 0b)."""
    raise NotImplementedError("AlignmentMethod.META_ANALYTIC is deferred beyond phase 0b.")


__all__ = [
    "AlignmentMethod",
    "VariableAlignment",
    "load_seed_alignments",
    "align_semantic",
    "align_meta_analytic",
]
