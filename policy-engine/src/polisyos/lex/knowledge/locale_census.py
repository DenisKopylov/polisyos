"""Complete string-leaf census for Lex multilingual candidate assurance.

This parser owns only catalogue structure/identity measurement, never translation or
legal authority. The independently allocated tool parser shares no parsing helpers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("ambiguous_duplicate_decoded_key")
        key.encode("utf-8", errors="strict")
        result[key] = value
    return result


def read_locale_catalogues(directory: Path) -> dict[str, dict[tuple[str, ...], str]]:
    """Read every direct catalogue member or refuse the ambiguous denominator.

    Args:
        directory: Directory containing only JSON objects with primitive string leaves.

    Returns:
        Complete filename to tuple-addressed string-leaf maps.

    Raises:
        ValueError: Any member is unreadable, non-JSON, ambiguous, or empty.
    """
    result: dict[str, dict[tuple[str, ...], str]] = {}
    try:
        members = sorted(directory.iterdir())
        if not members:
            raise ValueError("ambiguous_empty_directory")
        for member in members:
            if member.is_symlink() or not member.is_file() or member.suffix != ".json":
                raise ValueError(f"ambiguous_member:{member.name}")
            parsed = json.loads(
                member.read_text(encoding="utf-8"), object_pairs_hook=_unique_object
            )
            if not isinstance(parsed, dict):
                raise ValueError("ambiguous_root")
            leaves: dict[tuple[str, ...], str] = {}

            def walk(value: Any, address: tuple[str, ...]) -> None:
                if isinstance(value, str):
                    value.encode("utf-8", errors="strict")
                    leaves[address] = value
                elif isinstance(value, dict) and value:
                    for key, child in value.items():
                        walk(child, (*address, key))
                else:
                    raise ValueError(f"ambiguous_leaf:{member.name}:{address}")

            walk(parsed, ())
            result[member.name] = leaves
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"ambiguous_catalogue:{exc}") from exc
    return result
