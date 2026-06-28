"""Expose the stable Core platform surface with lazy package imports.

The Core package owns CAS artifacts, component discovery, registry assembly,
security/observability primitives, and cross-layer contracts shared by runtime
and domain subsystems. Subpackages are imported lazily so `import polisyos.core`
remains safe in CLI/bootstrap paths that do not need optional heavy dependencies.

Only names listed in `__all__` are considered stable package-level API.
"""

from __future__ import annotations

import importlib
from typing import Any

_SUBPACKAGES = (
    "artifacts",
    "backends",
    "cache",
    "canon",
    "components",
    "contracts",
    "discovery",
    "errors",
    "evaluation",
    "llm",
    "observability",
    "pipeline",
    "registry",
    "resilience",
    "run",
)
_LAZY_EXPORTS = {
    "SECRET_AND_PII_SCAN_SCOPES": ("polisyos.core.llm", "SECRET_AND_PII_SCAN_SCOPES"),
    "SECRET_PII_DETECTOR_VERSION": ("polisyos.core.llm", "SECRET_PII_DETECTOR_VERSION"),
    "PromptSanitizer": ("polisyos.core.llm", "PromptSanitizer"),
    "SecretAndPIIScanReport": ("polisyos.core.llm", "SecretAndPIIScanReport"),
    "SecretPIIScanResult": ("polisyos.core.llm", "SecretPIIScanResult"),
    "scan_secret_and_pii": ("polisyos.core.llm", "scan_secret_and_pii"),
}
__all__ = [
    "SECRET_AND_PII_SCAN_SCOPES",
    "SECRET_PII_DETECTOR_VERSION",
    "PromptSanitizer",
    "SecretAndPIIScanReport",
    "SecretPIIScanResult",
    "artifacts",
    "backends",
    "cache",
    "canon",
    "components",
    "contracts",
    "discovery",
    "errors",
    "evaluation",
    "llm",
    "observability",
    "pipeline",
    "registry",
    "resilience",
    "run",
    "scan_secret_and_pii",
]


def __getattr__(name: str) -> Any:
    """Import one exported Core subpackage on first attribute access.

    Args:
        name: Subpackage name listed in `__all__`.

    Returns:
        The imported module cached on the package namespace.

    Raises:
        AttributeError: If `name` is not part of the stable facade surface.
    """
    if name in _SUBPACKAGES:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    if name in _LAZY_EXPORTS:
        module_name, attr_name = _LAZY_EXPORTS[name]
        value = getattr(importlib.import_module(module_name), attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return regular globals plus lazily exported subpackage names."""
    return sorted(list(globals().keys()) + __all__)
