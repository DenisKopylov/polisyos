#!/usr/bin/env python3
"""Python implementation of the complete INT-R6 locale leaf census."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


SCHEMA_VERSION = "policyos.research.task_l.locale_leaf_census.v1"
DECODER_ID = "python.json.object_pairs_hook"


class LocaleCensusError(ValueError):
    """Raised when a locale member is unreadable or structurally ambiguous."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class LocaleCensusMismatchError(AssertionError):
    """Raised when two independently produced census reports disagree."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _unique_object(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LocaleCensusError("python_json_duplicate_key", key)
        result[key] = value
    return result


def _pointer(parts: tuple[str, ...]) -> str:
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


def _flatten(value: object, *, parts: tuple[str, ...] = ()) -> dict[str, str]:
    if isinstance(value, dict):
        flattened: dict[str, str] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise LocaleCensusError("python_json_non_string_key", _pointer(parts))
            flattened.update(_flatten(value[key], parts=(*parts, key)))
        return flattened
    if isinstance(value, list):
        flattened = {}
        for index, item in enumerate(value):
            flattened.update(_flatten(item, parts=(*parts, str(index))))
        return flattened
    if not isinstance(value, str):
        raise LocaleCensusError(
            "python_json_non_string_leaf",
            f"{_pointer(parts)}:{type(value).__name__}",
        )
    return {_pointer(parts): value}


def _digest_rows(rows: Sequence[tuple[str, str]]) -> str:
    encoded = "\n".join(
        json.dumps([path, value], ensure_ascii=False, separators=(",", ":")) for path, value in rows
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _parse_locale(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise LocaleCensusError(
            "python_locale_unreadable", f"{path.name}:{type(exc).__name__}"
        ) from exc
    try:
        parsed = json.loads(text, object_pairs_hook=_unique_object)
    except LocaleCensusError:
        raise
    except json.JSONDecodeError as exc:
        raise LocaleCensusError(
            "python_json_decode_error", f"{path.name}:{exc.lineno}:{exc.colno}"
        ) from exc
    if not isinstance(parsed, dict):
        raise LocaleCensusError("python_locale_root_not_object", path.name)
    return _flatten(parsed)


def build_report(directory: Path) -> dict[str, object]:
    """Parse every directory member and return a complete identity census."""

    directory = directory.resolve()
    try:
        entries = sorted(directory.iterdir(), key=lambda path: path.name)
    except OSError as exc:
        raise LocaleCensusError("python_locale_directory_unreadable", type(exc).__name__) from exc
    unexpected = [path.name for path in entries if not path.is_file() or path.suffix != ".json"]
    if unexpected:
        raise LocaleCensusError("python_locale_entry_ambiguous", repr(unexpected))
    if not entries:
        raise LocaleCensusError("python_locale_directory_empty", directory.as_posix())

    leaves: dict[str, dict[str, str]] = {}
    for path in entries:
        locale = path.stem
        if locale in leaves:
            raise LocaleCensusError("python_locale_identity_duplicate", locale)
        leaves[locale] = _parse_locale(path)
    if "en" not in leaves:
        raise LocaleCensusError("python_reference_locale_missing", "en")

    all_path_sets = [set(locale_leaves) for locale_leaves in leaves.values()]
    union = set().union(*all_path_sets)
    intersection = set.intersection(*all_path_sets)
    locale_reports: dict[str, dict[str, object]] = {}
    for locale, locale_leaves in sorted(leaves.items()):
        rows = sorted(locale_leaves.items())
        path_rows = [(path, "") for path, _ in rows]
        locale_reports[locale] = {
            "leaf_count": len(rows),
            "path_digest": _digest_rows(path_rows),
            "path_value_digest": _digest_rows(rows),
        }

    english = leaves["en"]
    comparisons: dict[str, dict[str, int]] = {}
    for locale, target in sorted(leaves.items()):
        if locale == "en":
            continue
        common = sorted(set(english) & set(target))
        comparisons[locale] = {
            "common_leaf_count": len(common),
            "missing_from_target_count": len(set(english) - set(target)),
            "target_only_count": len(set(target) - set(english)),
            "identical_value_count": sum(english[path] == target[path] for path in common),
            "different_value_count": sum(english[path] != target[path] for path in common),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "decoder_id": DECODER_ID,
        "decoder_implementation": "stdlib json with duplicate-key object-pairs hook",
        "directory_files": [path.name for path in entries],
        "directory_file_count": len(entries),
        "union_leaf_count": len(union),
        "intersection_leaf_count": len(intersection),
        "locales": locale_reports,
        "comparisons_to_en": comparisons,
    }


def _semantic_report(report: Mapping[str, object]) -> dict[str, object]:
    return {
        key: copy_value
        for key, copy_value in report.items()
        if key not in {"decoder_id", "decoder_implementation"}
    }


def reconcile_reports(
    first: Mapping[str, object], second: Mapping[str, object]
) -> dict[str, object]:
    """Require exact agreement while preserving distinct decoder provenance."""

    if first.get("decoder_id") == second.get("decoder_id"):
        raise LocaleCensusMismatchError(
            "decoder_independence_not_established", repr(first.get("decoder_id"))
        )
    first_semantic = _semantic_report(first)
    second_semantic = _semantic_report(second)
    if first_semantic != second_semantic:
        raise LocaleCensusMismatchError(
            "parser_reports_disagree",
            json.dumps(
                {"first": first_semantic, "second": second_semantic},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    canonical = json.dumps(
        first_semantic,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "status": "independently_reconciled",
        "decoder_ids": [first.get("decoder_id"), second.get("decoder_id")],
        "directory_file_count": first_semantic["directory_file_count"],
        "census_digest": "sha256:" + hashlib.sha256(canonical).hexdigest(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Print the census as canonical-key JSON; ambiguous input exits two."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print("usage: locale_census.py LOCALE_DIRECTORY", file=sys.stderr)  # noqa: T201
        return 2
    try:
        report = build_report(Path(arguments[0]))
    except LocaleCensusError as exc:
        print(f"{exc.code}: {exc.detail}", file=sys.stderr)  # noqa: T201
        return 2
    print(  # noqa: T201
        json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
