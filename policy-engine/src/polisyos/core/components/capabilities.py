from __future__ import annotations

from enum import IntFlag, auto


class Capability(IntFlag):
    """Capabilities advertised by a component."""

    CAS_READ = auto()
    CAS_WRITE = auto()
    FABRIC_QUERY = auto()
    FABRIC_WRITE = auto()
    FOUNDRY_COMPILE = auto()
    FOUNDRY_EXECUTE = auto()
    LEX_EVALUATE = auto()
    SCHOLAR_ENRICH = auto()
    SCIENTIST_NODE = auto()


Capabilities = Capability


def capabilities_from_flags(*flags: Capability) -> Capability:
    caps = Capability(0)
    for flag in flags:
        caps |= flag
    return caps


def flags_from_capabilities(caps: Capability) -> list[Capability]:
    return [flag for flag in Capability if flag in caps]
