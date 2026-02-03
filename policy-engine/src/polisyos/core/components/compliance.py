from __future__ import annotations

from .ids import ComponentId
from .metadata import ComponentMetadata


def validate_component_id(value: str) -> ComponentId:
    """Parse and validate a ComponentId string."""
    return ComponentId.parse(value)


def validate_metadata(metadata: ComponentMetadata) -> None:
    """Basic validation hook for ComponentMetadata."""
    _ = metadata.component_id
