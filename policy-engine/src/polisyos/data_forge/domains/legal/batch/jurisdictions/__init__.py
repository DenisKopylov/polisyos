"""Jurisdiction plugin registry."""

from polisyos.data_forge.domains.legal.batch.jurisdictions.eu import EUJurisdiction
from polisyos.data_forge.domains.legal.batch.jurisdictions.protocol import JurisdictionPlugin
from polisyos.data_forge.domains.legal.batch.jurisdictions.ua import UkrainianJurisdiction

_REGISTRY: dict[str, type[JurisdictionPlugin]] = {
    "EU": EUJurisdiction,
    "UA": UkrainianJurisdiction,
}


def normalize_jurisdiction_code(code: str | None) -> str:
    """Normalize and validate one explicitly declared jurisdiction code.

    Args:
        code: Jurisdiction code supplied by the caller.

    Returns:
        The normalized registered code.

    Raises:
        ValueError: If the code is absent, blank, or unregistered.
    """
    normalized = code.strip().upper() if code is not None else ""
    if not normalized:
        raise ValueError("jurisdiction code is required")
    if normalized not in _REGISTRY:
        raise ValueError(f"unsupported jurisdiction code: {normalized}")
    return normalized


def get_jurisdiction_plugin(code: str | None) -> JurisdictionPlugin:
    """Return the plugin for one explicitly declared jurisdiction code.

    Args:
        code: Jurisdiction code supplied by the caller.

    Returns:
        The registered jurisdiction plugin.

    Raises:
        ValueError: If the code is absent, blank, or unregistered.
    """
    plugin_cls = _REGISTRY[normalize_jurisdiction_code(code)]
    return plugin_cls()


__all__ = [
    "EUJurisdiction",
    "JurisdictionPlugin",
    "UkrainianJurisdiction",
    "get_jurisdiction_plugin",
    "normalize_jurisdiction_code",
]
