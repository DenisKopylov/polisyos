"""Reconcile independently allocated locale parsers without asserting equivalence.

Parser A belongs to Lex; parser B belongs to verification and uses a separate
grammar implementation. Exact maps are compared in memory, while the emitted
receipt contains only bounded measurements and input/implementation identities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal

from tools.quality.validation import locale_census_independent as parser_b

type Catalogues = dict[str, dict[tuple[str, ...], str]]


def reconcile_catalogues(first: Catalogues, second: Catalogues) -> None:
    """Require valid, nonempty, exactly equal file/path/value denominators.

    Args:
        first: Parser A's complete result.
        second: Independently produced parser B result.

    Raises:
        ValueError: A result is ambiguous or any decisive member differs.
    """
    for result in (first, second):
        if not result or "en.json" not in result:
            raise ValueError("ambiguous: English denominator missing")
        for filename, leaves in result.items():
            if not isinstance(filename, str) or not leaves or not isinstance(leaves, dict):
                raise ValueError("ambiguous: invalid/empty file denominator")
            for path, value in leaves.items():
                if (
                    not isinstance(path, tuple)
                    or not path
                    or any(not isinstance(key, str) for key in path)
                    or not isinstance(value, str)
                ):
                    raise ValueError("ambiguous: unclassified leaf")
    if first.keys() != second.keys():
        raise ValueError("parser_disagreement: complete file identities differ")
    for filename in first:
        if first[filename] != second[filename]:
            raise ValueError(f"parser_disagreement: decisive leaf/path differs in {filename}")


def _byte_identities(directory: Path) -> dict[str, str]:
    """Bind every member; a non-file member cannot disappear from the denominator."""
    try:
        output = {}
        for path in directory.iterdir():
            if not path.is_file() or path.is_symlink() or path.suffix != ".json":
                raise ValueError(f"ambiguous: unsupported member {path.name}")
            output[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return output
    except OSError as exc:
        raise ValueError(f"ambiguous: source read failed: {exc}") from exc


def measure_catalogues(
    directory: Path, *, corrupt_parser: Literal["a", "b"] | None = None
) -> dict[str, object]:
    """Execute both owners, reject disagreement and emit bounded structural facts.

    Args:
        directory: Complete current locale-directory denominator.
        corrupt_parser: Verification fault injection into one output only.

    Returns:
        Recomputed structural receipt with semantic equivalence explicitly false.

    Raises:
        ValueError: Ambiguity, changing inputs or disagreement prevents measurement.
    """
    from polisyos.lex.knowledge import locale_census as parser_a

    before = _byte_identities(directory)
    first = parser_a.read_locale_catalogues(directory)
    between = _byte_identities(directory)
    second = parser_b.read_locale_catalogues(directory)
    after = _byte_identities(directory)
    if before != between or before != after or first.keys() != before.keys():
        raise ValueError("ambiguous: source denominator changed during observation")
    if corrupt_parser is not None:
        target = first if corrupt_parser == "a" else second
        if not target or not all(target.values()):
            raise ValueError("ambiguous: no decisive leaf for corruption witness")
        filename = min(target)
        leaf = min(target[filename])
        target[filename][leaf] += " corrupt-field witness"
    reconcile_catalogues(first, second)
    english = first["en.json"]
    english_paths = set(english)
    catalogues = {}
    for filename, leaves in sorted(first.items()):
        shared = english_paths & leaves.keys()
        catalogues[filename] = {
            "sha256": before[filename],
            "string_leaves": len(leaves),
            "shared_with_english": len(shared),
            "identical_to_english": sum(leaves[path] == english[path] for path in shared),
            "english_paths_missing_here": len(english_paths - leaves.keys()),
            "paths_absent_from_english": len(leaves.keys() - english_paths),
        }
    implementations = {}
    for label, file in (
        ("parser_a", parser_a.__file__),
        ("parser_b", parser_b.__file__),
        ("reconciler", __file__),
    ):
        if file is None:
            raise ValueError("ambiguous: implementation identity unresolved")
        implementations[label] = hashlib.sha256(Path(file).read_bytes()).hexdigest()
    return {
        "schema_version": "polisyos.locale_census.v1",
        "status": "independently_reconciled",
        "path_denominator": f"{directory.resolve()}/*",
        "file_type_denominator": "all direct members; JSON object/string grammar",
        "file_denominator": len(before),
        "catalogues": catalogues,
        "implementation_sha256": implementations,
        "identity_measure": "exact decoded string equality on shared tuple paths",
        "semantic_equivalence_established": False,
        "may_not_use_for": ["translation_quality", "legal_equivalence", "source_authority"],
    }


def main(argv: list[str] | None = None) -> int:
    """Run the current census or recompute and compare an existing receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory", type=Path, default=Path("apps/runtime-dashboard/src/shared/i18n/locales")
    )
    parser.add_argument("--check", action="store_true", help="Recompute the complete census.")
    parser.add_argument(
        "--receipt", type=Path, help="Optional receipt whose decisive fields must match."
    )
    parser.add_argument("--corrupt-parser", choices=("a", "b"))
    args = parser.parse_args(argv)
    try:
        result = measure_catalogues(args.directory, corrupt_parser=args.corrupt_parser)
        if args.receipt is not None:
            expected = json.loads(args.receipt.read_text(encoding="utf-8"))
            if expected != result:
                raise ValueError("receipt_drift: recomputed decisive fields differ")
    except (ValueError, OSError) as exc:
        print(
            json.dumps(
                {
                    "status": "refused",
                    "reason": str(exc),
                    "semantic_equivalence_established": False,
                },
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
