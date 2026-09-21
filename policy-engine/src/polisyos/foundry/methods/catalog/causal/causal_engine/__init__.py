"""Compatibility surface for the Phase 4.1 CausalEngine split."""

from __future__ import annotations

from . import artifacts as _artifacts
from .api import CausalEngine

DataReadinessBlockedError = _artifacts.DataReadinessBlockedError
_make_dummy_identification_result = _artifacts._make_dummy_identification_result
id_star_algorithm = _artifacts.id_star_algorithm
id_with_oracle_fallback = _artifacts.id_with_oracle_fallback
idc_star_algorithm = _artifacts.idc_star_algorithm
mz_id_algorithm = _artifacts.mz_id_algorithm

del _artifacts

__all__ = ["CausalEngine", "DataReadinessBlockedError"]
