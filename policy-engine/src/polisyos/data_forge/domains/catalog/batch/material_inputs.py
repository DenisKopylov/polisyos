"""Content snapshots shared by catalog policy readers and producer receipts."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class _MaterialFileSnapshot:
    path: Path
    raw: bytes | None
    selected: bool = True

    def generation_member(self, role: str) -> tuple[str, bytes]:
        """Bind file presence separately from the exact current file bytes."""
        presence = (
            "unselected" if not self.selected else ("present" if self.raw is not None else "absent")
        )
        return (f"{role}:{self.path}:{presence}", self.raw if self.raw is not None else b"")


def _material_file_snapshot(
    path: Path, *, required: bool = False, selected: bool = True
) -> _MaterialFileSnapshot:
    """Read one current file; preserve optional absence and propagate other errors."""
    resolved = path.resolve()
    if not selected:
        return _MaterialFileSnapshot(path=resolved, raw=None, selected=False)
    try:
        raw = resolved.read_bytes()
    except FileNotFoundError:
        if required:
            raise
        raw = None
    return _MaterialFileSnapshot(path=resolved, raw=raw)


@lru_cache(maxsize=32)
def _material_yaml_snapshot(snapshot: _MaterialFileSnapshot) -> object:
    """Parse UTF-8 YAML with a cache keyed by path, presence and current bytes."""
    if snapshot.raw is None:
        return None
    import yaml

    return yaml.safe_load(snapshot.raw.decode("utf-8"))


class WVSIndicatorRegistryError(ValueError):
    """A present WVS registry does not satisfy the reader schema."""


def _wvs_indicator_registry_from_snapshot(
    snapshot: _MaterialFileSnapshot,
) -> dict[str, dict[str, Any]] | None:
    """Return normalized WVS entries, or ``None`` only for a missing file.

    The reader schema follows the checked-in generator and the fields consumed by
    the current catalog readers. Sparse legacy entries remain valid, while a
    present empty, malformed, or wrongly typed registry cannot select fallback.
    """
    if snapshot.raw is None:
        return None

    import yaml
    from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

    def _has_duplicate_mapping_keys(node: Node, visited: set[int]) -> bool:
        if id(node) in visited:
            return False
        visited.add(id(node))
        if isinstance(node, MappingNode):
            seen_keys: set[tuple[str, str]] = set()
            for key_node, value_node in node.value:
                if key_node.tag != "tag:yaml.org,2002:merge" and isinstance(key_node, ScalarNode):
                    identity = (key_node.tag, key_node.value)
                    if identity in seen_keys:
                        return True
                    seen_keys.add(identity)
                if _has_duplicate_mapping_keys(key_node, visited) or _has_duplicate_mapping_keys(
                    value_node, visited
                ):
                    return True
        elif isinstance(node, SequenceNode):
            return any(_has_duplicate_mapping_keys(item, visited) for item in node.value)
        return False

    try:
        decoded = snapshot.raw.decode("utf-8")
        yaml_root = yaml.compose(decoded)
        if yaml_root is not None and _has_duplicate_mapping_keys(yaml_root, set()):
            raise WVSIndicatorRegistryError(
                f"Invalid WVS indicator registry at {snapshot.path}: duplicate YAML mapping key"
            )
        document = _material_yaml_snapshot(snapshot)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise WVSIndicatorRegistryError(
            f"Invalid WVS indicator registry at {snapshot.path}: invalid UTF-8 or YAML"
        ) from exc

    if not isinstance(document, dict):
        raise WVSIndicatorRegistryError(
            f"Invalid WVS indicator registry at {snapshot.path}: root must be a mapping"
        )
    if "version" in document and (type(document["version"]) is not int or document["version"] != 1):
        raise WVSIndicatorRegistryError(
            f"Invalid WVS indicator registry at {snapshot.path}: version must be 1"
        )
    raw_indicators = document.get("indicators")
    if not isinstance(raw_indicators, dict) or not raw_indicators:
        raise WVSIndicatorRegistryError(
            f"Invalid WVS indicator registry at {snapshot.path}: "
            "indicators must be a non-empty mapping"
        )

    normalized: dict[str, dict[str, Any]] = {}
    for raw_code, raw_spec in raw_indicators.items():
        if not isinstance(raw_code, str) or not raw_code.strip():
            raise WVSIndicatorRegistryError(
                f"Invalid WVS indicator registry at {snapshot.path}: "
                "indicator codes must be non-empty strings"
            )
        code = raw_code.strip().upper()
        if code in normalized:
            raise WVSIndicatorRegistryError(
                f"Invalid WVS indicator registry at {snapshot.path}: "
                f"duplicate normalized code {code}"
            )
        if not isinstance(raw_spec, dict) or not raw_spec:
            raise WVSIndicatorRegistryError(
                f"Invalid WVS indicator registry at {snapshot.path}: "
                f"{code} must have a non-empty mapping"
            )

        recognized_fields = {
            "title",
            "response_type",
            "aggregation",
            "waves",
            "sub_items",
            "canonical_candidates",
        }
        if not recognized_fields.intersection(raw_spec):
            raise WVSIndicatorRegistryError(
                f"Invalid WVS indicator registry at {snapshot.path}: {code} has no supported fields"
            )
        for field_name in ("title", "response_type", "aggregation"):
            if field_name in raw_spec and (
                not isinstance(raw_spec[field_name], str) or not raw_spec[field_name].strip()
            ):
                raise WVSIndicatorRegistryError(
                    f"Invalid WVS indicator registry at {snapshot.path}: "
                    f"{code}.{field_name} must be a non-empty string"
                )
        if "waves" in raw_spec:
            waves = raw_spec["waves"]
            if not isinstance(waves, list) or any(
                type(wave) is not int or wave < 1 for wave in waves
            ):
                raise WVSIndicatorRegistryError(
                    f"Invalid WVS indicator registry at {snapshot.path}: "
                    f"{code}.waves must be a list of positive integers"
                )
        for field_name in ("sub_items", "canonical_candidates"):
            if field_name not in raw_spec:
                continue
            values = raw_spec[field_name]
            if field_name == "canonical_candidates" and isinstance(values, str):
                values = [values]
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise WVSIndicatorRegistryError(
                    f"Invalid WVS indicator registry at {snapshot.path}: "
                    f"{code}.{field_name} must contain non-empty strings"
                )

        normalized[code] = raw_spec
    return normalized
