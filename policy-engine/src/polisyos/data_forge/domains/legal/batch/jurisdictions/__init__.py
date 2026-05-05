"""Jurisdiction plugin registry."""

from polisyos.data_forge.domains.legal.batch.jurisdictions.eu import EUJurisdiction
from polisyos.data_forge.domains.legal.batch.jurisdictions.protocol import JurisdictionPlugin
from polisyos.data_forge.domains.legal.batch.jurisdictions.ua import UkrainianJurisdiction

_REGISTRY: dict[str, type[JurisdictionPlugin]] = {
    "EU": EUJurisdiction,
    "UA": UkrainianJurisdiction,
}


def get_jurisdiction_plugin(code: str | None) -> JurisdictionPlugin:
    """Return jurisdiction plugin."""
    normalized = str(code or "UA").strip().upper() or "UA"
    plugin_cls = _REGISTRY.get(normalized, UkrainianJurisdiction)
    return plugin_cls()


__all__ = [
    "EUJurisdiction",
    "JurisdictionPlugin",
    "UkrainianJurisdiction",
    "get_jurisdiction_plugin",
]
