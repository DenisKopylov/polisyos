from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class Priority(str, Enum):
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"


class CompatMode(str, Enum):
    STRICT = "strict"
    TOLERANT = "tolerant"


class Lifecycle(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class SchemaMode(str, Enum):
    VALIDATION = "validation"
    SERIALIZATION = "serialization"


@dataclass(frozen=True)
class ABIModelEntry:
    abi_key: str
    fqn: str
    module: str
    schema_file: str
    priority: Priority
    compat_mode: CompatMode = CompatMode.STRICT
    version_field: str | None = "schema_version"
    lifecycle: Lifecycle = Lifecycle.ACTIVE
    aliases: tuple[str, ...] = ()
    allow_missing: bool = False
    schema_mode: SchemaMode = SchemaMode.VALIDATION
    schema_variant_version: str | None = None


# Import the table after defining its public type dependencies above.
from .catalog import (  # noqa: E402
    ABI_MODELS as ABI_MODELS,
)
from .catalog import (  # noqa: E402
    FABRIC_ABI_MODELS as FABRIC_ABI_MODELS,
)
from .catalog import (  # noqa: E402
    IR_ABI_MODELS as IR_ABI_MODELS,
)
from .catalog import (  # noqa: E402
    SCIENTIST_ABI_MODELS as SCIENTIST_ABI_MODELS,
)


def iter_abi_entries(*, include_deprecated: bool = False) -> tuple[ABIModelEntry, ...]:
    if include_deprecated:
        return ABI_MODELS
    return tuple(entry for entry in ABI_MODELS if entry.lifecycle == Lifecycle.ACTIVE)


def select_abi_entries(
    filters: Iterable[str] | None,
    *,
    include_deprecated: bool = False,
) -> tuple[ABIModelEntry, ...]:
    entries = iter_abi_entries(include_deprecated=include_deprecated)
    if not filters:
        return entries

    normalized = tuple(token.strip().lower() for token in filters if token.strip())
    if not normalized:
        return entries

    selected: list[ABIModelEntry] = []
    for entry in entries:
        tags = {
            entry.abi_key.lower(),
            entry.module.lower(),
            entry.priority.value,
            entry.fqn.lower(),
        }
        tags.update(alias.lower() for alias in entry.aliases)
        if any(token in tags for token in normalized):
            selected.append(entry)
            continue
        if any(entry.abi_key.lower().startswith(token) for token in normalized):
            selected.append(entry)

    return tuple(selected)
