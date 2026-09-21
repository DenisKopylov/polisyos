"""Identity-preserving migrations for persisted Runtime run manifests.

The path-only migration normalizes references to the manifest's declared
``run_root``.  It validates every source before returning any output so the
caller can keep atomic publication and leave an existing destination intact
when a reference is missing, ambiguous, or outside the permitted root.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


class RunManifestPathMigrationError(ValueError):
    """Raised when a RunManifest path cannot be migrated without guessing."""


def _source_root(manifest: dict[str, Any], manifest_path: Path) -> tuple[Path, str]:
    """Resolve the declared root while preserving its persisted spelling."""
    default_root = manifest_path.resolve().parent.parent
    declared_root = manifest.get("run_root")
    if declared_root is None:
        root_value = str(default_root)
        root = default_root
    elif isinstance(declared_root, str) and declared_root:
        root_value = declared_root
        root = Path(declared_root)
    else:
        raise RunManifestPathMigrationError("run_manifest run_root must be a non-empty string")

    resolved_root = root.resolve(strict=False)
    if not resolved_root.exists() or not resolved_root.is_dir():
        raise RunManifestPathMigrationError(
            f"run_manifest declared run_root does not exist as a directory: {root}"
        )
    return resolved_root, root_value


def _resolve_source(candidate: Path, root: Path, *, label: str) -> Path:
    """Resolve one source and enforce real-path containment and existence."""
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RunManifestPathMigrationError(
            f"run_manifest {label} resolves outside declared run_root: {candidate}"
        ) from exc
    if not resolved.exists():
        raise RunManifestPathMigrationError(
            f"run_manifest {label} source does not exist: {candidate}"
        )
    return resolved


def _canonical_reference(
    artifact: dict[str, Any],
    root: Path,
    *,
    index: int,
) -> str:
    """Validate one artifact identity and return its root-relative spelling."""
    path_value = artifact.get("path")
    relative_value = artifact.get("relative_path")
    candidates: list[tuple[str, Path]] = []

    if path_value is not None:
        if not isinstance(path_value, str) or not path_value:
            raise RunManifestPathMigrationError(
                f"run_manifest artifact {index} path must be a non-empty string"
            )
        path = Path(path_value)
        candidates.append(
            (
                "artifact path",
                path if path.is_absolute() else root / path,
            )
        )

    if relative_value is not None:
        if not isinstance(relative_value, str) or not relative_value:
            raise RunManifestPathMigrationError(
                f"run_manifest artifact {index} relative_path must be a non-empty string"
            )
        relative = Path(relative_value)
        candidates.append(("artifact relative_path", root / relative))

    if not candidates:
        raise RunManifestPathMigrationError(
            f"run_manifest artifact {index} has no path identity"
        )

    resolved_candidates = [
        _resolve_source(candidate, root, label=f"artifact {index} {label}")
        for label, candidate in candidates
    ]
    first = resolved_candidates[0]
    if any(candidate != first for candidate in resolved_candidates[1:]):
        raise RunManifestPathMigrationError(
            f"run_manifest artifact {index} path and relative_path identify different sources"
        )
    return first.relative_to(root).as_posix()


def migrate_run_manifest_paths(
    data: dict[str, Any],
    *,
    manifest_path: Path,
    target_version: str | None = None,
) -> dict[str, Any]:
    """Normalize RunManifest artifact refs without changing their identity.

    This is deliberately a path-only operation.  It does not copy files or
    accept external absolute references.  Versioned RunManifest conversion
    needs a separate, explicit profile; passing ``target_version`` therefore
    fails closed instead of silently ignoring ``--to``.

    Args:
        data: Parsed JSON/YAML RunManifest mapping.
        manifest_path: Location of the input manifest, used only as the
            backwards-compatible default root when ``run_root`` is absent.
        target_version: Optional CLI target.  Any value is rejected for this
            path-only profile.

    Returns:
        A deep-copied manifest with validated root-relative artifact paths.

    Raises:
        RunManifestPathMigrationError: If the profile is unsupported or any
            artifact source cannot be proven to remain the same object.
    """
    if target_version is not None:
        raise RunManifestPathMigrationError(
            "run_manifest path-only migration does not support --to; "
            "use an explicit versioned profile"
        )
    if not isinstance(data, dict):
        raise RunManifestPathMigrationError("run_manifest payload must be an object")

    artifacts = data.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise RunManifestPathMigrationError("run_manifest artifacts must be a list")

    root, persisted_root = _source_root(data, manifest_path)
    migrated = deepcopy(data)
    migrated["run_root"] = persisted_root
    migrated_artifacts: list[dict[str, Any]] = []

    # Complete preflight happens before the caller publishes any output.
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise RunManifestPathMigrationError(
                f"run_manifest artifact entry {index} must be an object"
            )
        updated = deepcopy(artifact)
        canonical = _canonical_reference(artifact, root, index=index)
        updated["relative_path"] = canonical
        if artifact.get("path") is not None:
            updated["path"] = canonical
        migrated_artifacts.append(updated)

    migrated["artifacts"] = migrated_artifacts
    return migrated


__all__ = ["RunManifestPathMigrationError", "migrate_run_manifest_paths"]
