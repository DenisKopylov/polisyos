"""Derive every structured receipt that line-binds regenerated clients.

The primary census discovers explicitly named anchor records. An independent
shape census discovers any target-associated line-coordinate record without
depending on its container or symbol vocabulary. Navigation references remain
a separate population. A mismatch fails closed so a new receipt shape cannot
silently shrink the binding denominator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

DEFAULT_TARGET_PATHS = (
    "schemas/runtime_api_v1.openapi.json",
    "packages/runtime-api-client/types.ts",
    "packages/runtime-api-client/runtimeApiClient.ts",
    "packages/runtime-api-client/runtimeApiClient.js",
    "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
    "packages/runtime-api-client/canonicalRuntimeApiClient.js",
    "apps/runtime-dashboard/src/api/types.ts",
)
STRUCTURED_SUFFIXES = frozenset({".json", ".toml"})
SYMBOL_KEYS = frozenset({"export_symbol", "symbol"})
PATH_SUFFIXES = (".js", ".json", ".py", ".toml", ".ts", ".tsx")


def _walk(value: object, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], object]]:
    """Yield every node in a JSON/TOML value with its stable structural path."""
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def _key_tokens(key: object) -> tuple[str, ...]:
    """Split snake, kebab, and camel-case keys into normalized tokens."""
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
    return tuple(token for token in re.split(r"[^a-z0-9]+", expanded.lower()) if token)


def _line_items(value: Mapping[object, object]) -> list[tuple[str, int]]:
    """Return direct integer fields whose key has a distinct ``line`` token."""
    return sorted(
        (
            (str(key), child)
            for key, child in value.items()
            if "line" in _key_tokens(key)
            and isinstance(child, int)
            and not isinstance(child, bool)
        ),
        key=lambda item: item[0],
    )


def _exact_targets(value: object, target_paths: frozenset[str]) -> frozenset[str]:
    """Return target paths represented as exact string values in ``value``."""
    return frozenset(
        child
        for _, child in _walk(value)
        if isinstance(child, str) and child in target_paths
    )


def _parse_structured(path: Path) -> object:
    """Parse one JSON or TOML candidate without changing its bytes."""
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix == ".toml":
        with path.open("rb") as stream:
            return tomllib.load(stream)
    raise ValueError(f"unsupported structured artifact: {path}")


def _json_pointer(path: tuple[str, ...]) -> str:
    """Encode a structural path as a JSON pointer for stable diagnostics."""
    if not path:
        return ""
    return "/" + "/".join(
        part.replace("~", "~0").replace("/", "~1") for part in path
    )


def _direct_navigation_references(
    value: object,
    *,
    artifact_path: str,
    target_paths: Sequence[str],
) -> list[dict[str, object]]:
    """Enumerate ``target:line`` strings as navigation, never as bindings."""
    patterns = tuple(
        (
            target,
            re.compile(rf"^{re.escape(target)}:(?P<line>[0-9]+)(?:$|[#?])"),
        )
        for target in target_paths
    )
    references: list[dict[str, object]] = []
    for path, child in _walk(value):
        if not isinstance(child, str):
            continue
        for target, pattern in patterns:
            match = pattern.match(child)
            if match is None:
                continue
            references.append(
                {
                    "artifact_path": artifact_path,
                    "line": int(match.group("line")),
                    "pointer": _json_pointer(path),
                    "target_path": target,
                }
            )
            break
    return references


def _associated_targets(
    candidate: Mapping[object, object],
    *,
    document_targets: frozenset[str],
    target_paths: frozenset[str],
) -> frozenset[str]:
    """Associate one coordinate record with regenerated target paths."""
    direct_targets = frozenset(
        child
        for child in candidate.values()
        if isinstance(child, str) and child in target_paths
    )
    if direct_targets:
        return direct_targets
    direct_foreign_paths = tuple(
        child
        for key, child in candidate.items()
        if isinstance(child, str)
        and ("path" in str(key).lower() or child.endswith(PATH_SUFFIXES))
    )
    if direct_foreign_paths:
        return frozenset()
    return document_targets


def _value_at_path(value: object, path: tuple[str, ...]) -> object:
    """Resolve one structural path within a parsed JSON/TOML value."""
    current = value
    for part in path:
        if isinstance(current, Mapping):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:  # pragma: no cover - paths are produced by _walk
            raise KeyError(path)
    return current


def _record_id(value: object, path: tuple[str, ...]) -> str | None:
    """Find the nearest owning record identifier for an enumerated binding."""
    for length in range(len(path) - 1, -1, -1):
        parent = _value_at_path(value, path[:length])
        if not isinstance(parent, Mapping):
            continue
        for preferred in ("unit_id", "debt_id", "record_id", "id"):
            candidate = parent.get(preferred)
            if isinstance(candidate, str):
                return candidate
        for key, candidate in parent.items():
            if str(key).endswith("_id") and isinstance(candidate, str):
                return candidate
    return None


def _anchor_records(
    value: object,
    *,
    artifact_path: str,
    target_paths: frozenset[str],
    explicit: bool,
) -> dict[tuple[str, ...], dict[str, object]]:
    """Discover anchor records by explicit or independent structural rules."""
    document_targets = _exact_targets(value, target_paths)
    records: dict[tuple[str, ...], dict[str, object]] = {}
    for path, candidate in _walk(value):
        if not isinstance(candidate, Mapping) or not path:
            continue
        if explicit and (
            "anchor" not in path[-1].lower()
            or not any(
                key in candidate and isinstance(candidate[key], str)
                for key in SYMBOL_KEYS
            )
        ):
            continue
        lines = _line_items(candidate)
        if not lines:
            continue
        candidate_targets = _associated_targets(
            candidate,
            document_targets=document_targets,
            target_paths=target_paths,
        )
        if not candidate_targets:
            continue
        symbol = next(
            (
                candidate.get(key)
                for key in ("export_symbol", "symbol", "type_name")
                if isinstance(candidate.get(key), str)
            ),
            None,
        )
        records[path] = {
            "artifact_path": artifact_path,
            "field": candidate.get("field")
            if isinstance(candidate.get("field"), str)
            else None,
            "line_bindings": [
                {"key": key, "value": line} for key, line in lines
            ],
            "pointer": _json_pointer(path),
            "record_id": _record_id(value, path),
            "record_name": path[-1],
            "symbol": symbol,
            "target_paths": sorted(candidate_targets),
        }
    return records


def build_report(
    *,
    repo_root: Path,
    target_paths: Sequence[str],
    candidate_paths: Sequence[Path],
) -> dict[str, object]:
    """Build a reconciled census over a complete candidate population.

    Args:
        repo_root: Root against which candidate paths resolve.
        target_paths: Generated files whose line-bound receipts must be found.
        candidate_paths: Complete structured-artifact population to inspect.

    Returns:
        A deterministic JSON-compatible report with per-artifact evidence and
        fail-closed reconciliation errors.
    """
    normalized_targets = tuple(dict.fromkeys(str(path) for path in target_paths))
    target_set = frozenset(normalized_targets)
    normalized_candidates = tuple(
        sorted(
            {
                Path(path)
                for path in candidate_paths
                if Path(path).suffix in STRUCTURED_SUFFIXES
            },
            key=str,
        )
    )
    artifacts: list[dict[str, object]] = []
    bindings: list[dict[str, object]] = []
    navigation_references: list[dict[str, object]] = []
    errors: list[str] = []
    primary_total = 0
    independent_total = 0
    primary_lines_total = 0
    independent_lines_total = 0

    for relative_path in normalized_candidates:
        absolute_path = repo_root / relative_path
        try:
            value = _parse_structured(absolute_path)
        except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
            errors.append(f"parse_error:{relative_path.as_posix()}:{type(error).__name__}")
            continue

        primary = _anchor_records(
            value,
            artifact_path=relative_path.as_posix(),
            target_paths=target_set,
            explicit=True,
        )
        independent = _anchor_records(
            value,
            artifact_path=relative_path.as_posix(),
            target_paths=target_set,
            explicit=False,
        )
        navigation = _direct_navigation_references(
            value,
            artifact_path=relative_path.as_posix(),
            target_paths=normalized_targets,
        )
        if not (primary or independent or navigation):
            continue

        for pointer in sorted(set(primary) ^ set(independent)):
            primary_state = "present" if pointer in primary else "absent"
            independent_state = "present" if pointer in independent else "absent"
            errors.append(
                "anchor_population_mismatch:"
                f"{relative_path.as_posix()}:{_json_pointer(pointer)}:"
                f"primary={primary_state}:independent={independent_state}"
            )
        primary_lines = sum(
            len(record["line_bindings"]) for record in primary.values()
        )
        independent_lines = sum(
            len(record["line_bindings"]) for record in independent.values()
        )
        if primary_lines != independent_lines:
            errors.append(
                "anchor_line_population_mismatch:"
                f"{relative_path.as_posix()}:"
                f"primary={primary_lines}:independent={independent_lines}"
            )
        artifacts.append(
            {
                "path": relative_path.as_posix(),
                "file_type": relative_path.suffix,
                "primary_anchor_records": len(primary),
                "independent_anchor_records": len(independent),
                "line_bindings": independent_lines,
                "navigation_references": len(navigation),
            }
        )
        bindings.extend(independent.values())
        navigation_references.extend(navigation)
        primary_total += len(primary)
        independent_total += len(independent)
        primary_lines_total += primary_lines
        independent_lines_total += independent_lines

    by_suffix = {
        suffix: sum(path.suffix == suffix for path in normalized_candidates)
        for suffix in sorted(STRUCTURED_SUFFIXES)
    }
    candidate_manifest = "\n".join(path.as_posix() for path in normalized_candidates)
    binding_artifacts = {
        binding["artifact_path"] for binding in bindings
    }
    navigation_artifacts = {
        reference["artifact_path"] for reference in navigation_references
    }

    summary = {
        "binding_artifacts": len(binding_artifacts),
        "navigation_artifacts": len(navigation_artifacts),
        "primary_anchor_records": primary_total,
        "independent_anchor_records": independent_total,
        "line_bindings": primary_lines_total,
        "independent_line_bindings": independent_lines_total,
        "navigation_references": len(navigation_references),
    }
    return {
        "schema_version": "generated-client-receipt-census.v2",
        "target_paths": list(normalized_targets),
        "candidate_population": {
            "total": len(normalized_candidates),
            "by_suffix": by_suffix,
            "path_sha256": hashlib.sha256(
                candidate_manifest.encode("utf-8")
            ).hexdigest(),
        },
        "summary": summary,
        "artifacts": sorted(artifacts, key=lambda artifact: str(artifact["path"])),
        "bindings": sorted(
            bindings,
            key=lambda binding: (
                str(binding["artifact_path"]),
                str(binding["pointer"]),
            ),
        ),
        "navigation_references": sorted(
            navigation_references,
            key=lambda reference: (
                str(reference["artifact_path"]),
                str(reference["pointer"]),
            ),
        ),
        "errors": sorted(set(errors)),
    }


def _repository_candidates(repo_root: Path) -> tuple[Path, ...]:
    """Derive every Git-visible JSON/TOML candidate, including new files."""
    git_executable = shutil.which("git")
    if git_executable is None:
        raise FileNotFoundError("git executable is required for receipt discovery")
    result = subprocess.run(  # noqa: S603 - resolved Git binary with fixed arguments
        [
            git_executable,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.json",
            "*.toml",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return tuple(
        sorted(
            (Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw),
            key=str,
        )
    )


def build_repository_report(*, repo_root: Path) -> dict[str, object]:
    """Build the live repository report without a remembered artifact list."""
    candidates = _repository_candidates(repo_root)
    return build_report(
        repo_root=repo_root,
        target_paths=DEFAULT_TARGET_PATHS,
        candidate_paths=candidates,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the census CLI and fail ``--check`` on population disagreement."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--target", action="append", dest="targets")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    candidates = _repository_candidates(arguments.repo_root)
    report = build_report(
        repo_root=arguments.repo_root,
        target_paths=arguments.targets or DEFAULT_TARGET_PATHS,
        candidate_paths=candidates,
    )
    print(json.dumps(report, indent=2, sort_keys=True))  # noqa: T201 - CLI boundary
    return 1 if arguments.check and report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
