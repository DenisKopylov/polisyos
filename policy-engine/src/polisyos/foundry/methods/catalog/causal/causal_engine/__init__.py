"""Compatibility surface for the Phase 4.1 CausalEngine split."""

from __future__ import annotations

from . import artifacts as _artifacts
from .api import CausalEngine

_FACADE_METADATA_KEYS = frozenset(
    {
        "__all__",
        "__annotations__",
        "__builtins__",
        "__cached__",
        "__doc__",
        "__file__",
        "__loader__",
        "__name__",
        "__package__",
        "__path__",
        "__spec__",
        "__warningregistry__",
        "_FACADE_METADATA_KEYS",
        "_artifacts",
        "CausalEngine",
    }
)
for _facade_name in tuple(globals()):
    if _facade_name not in _FACADE_METADATA_KEYS:
        globals().pop(_facade_name, None)
del _facade_name
del _FACADE_METADATA_KEYS

DataReadinessBlockedError = _artifacts.DataReadinessBlockedError
_make_dummy_identification_result = _artifacts._make_dummy_identification_result
id_star_algorithm = _artifacts.id_star_algorithm
id_with_oracle_fallback = _artifacts.id_with_oracle_fallback
idc_star_algorithm = _artifacts.idc_star_algorithm
mz_id_algorithm = _artifacts.mz_id_algorithm

del _artifacts

__all__ = ["CausalEngine", "DataReadinessBlockedError"]
