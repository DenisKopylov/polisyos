"""Capability flags used to advertise what a discovered component can do."""

from __future__ import annotations

from enum import IntFlag, auto


class Capability(IntFlag):
    """Capabilities advertised by a component."""

    # Type capabilities
    IR_FRAGMENT = auto()
    FOUNDRY_METHOD = auto()
    FABRIC_CONNECTOR = auto()
    SCHOLAR_EXTRACTOR = auto()
    LEX_EXTRACTOR = auto()
    LEX_EVALUATOR = auto()
    SCIENTIST_NODE = auto()
    NORM_PACK_PROVIDER = auto()
    DATA_FORGE_DOMAIN = auto()
    RUNTIME_MIDDLEWARE = auto()

    # Cross-cutting capabilities
    CAS_READ = auto()
    CAS_WRITE = auto()
    FABRIC_QUERY = auto()
    FABRIC_WRITE = auto()
    FOUNDRY_COMPILE = auto()
    FOUNDRY_EXECUTE = auto()
    LEX_EVALUATE = auto()
    SCHOLAR_ENRICH = auto()


Capabilities = Capability


def capabilities_from_flags(*flags: Capability) -> Capability:
    """Fold one or more capability flags into the composite bitmask stored on a component."""
    caps = Capability(0)
    for flag in flags:
        caps |= flag
    return caps


def flags_from_capabilities(caps: Capability) -> list[Capability]:
    """Expand a capability bitmask back into the individual advertised flags it contains."""
    return [flag for flag in Capability if flag in caps]
