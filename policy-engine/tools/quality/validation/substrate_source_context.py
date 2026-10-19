"""Bind test-only substrate reads to a selected physical data owner.

The active checkout remains the source of code and frozen evidence. This value
only identifies the physical owner of ``production_data`` for candidate test
inputs; it does not establish permission, authority, or currentness.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

_MANIFEST_REF = "repo://production_data/manifest.json#production_data_root_manifest"


class CandidateSubstrateSourceError(ValueError):
    """Raised when a selected test-source profile no longer matches its inputs."""


@dataclass(frozen=True, slots=True)
class CandidateSubstrateSourceContext:
    """Separate frozen code inputs from one selected candidate data owner."""

    code_root: Path
    source_owner_root: Path
    workspace_root: Path
    manifest_ref: str
    manifest_sha256: str
    source_use: Literal["candidate_test_input_only"] = "candidate_test_input_only"

    @classmethod
    def from_code_root(
        cls,
        code_root: Path,
        *,
        workspace_root: Path,
        source_owner_root: Path | None = None,
    ) -> CandidateSubstrateSourceContext:
        """Create a candidate-only profile from the checkout's data-root link.

        ``source_owner_root`` may make the selected owner explicit, but it must
        resolve to the physical target already named by ``code_root``'s
        ``production_data`` entry. The only external metadata read is the root
        manifest, whose bytes are rebound at every consumer boundary.
        """

        try:
            resolved_code_root = Path(code_root).resolve(strict=True)
            linked_data_root = (resolved_code_root / "production_data").resolve(strict=True)
            resolved_owner_root = (
                Path(source_owner_root).resolve(strict=True)
                if source_owner_root is not None
                else linked_data_root.parent.resolve(strict=True)
            )
            resolved_workspace_root = Path(workspace_root).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise CandidateSubstrateSourceError("selected_substrate_root_unavailable") from exc

        if not resolved_code_root.is_dir():
            raise CandidateSubstrateSourceError("selected_substrate_code_root_not_directory")
        if not linked_data_root.is_dir():
            raise CandidateSubstrateSourceError("selected_substrate_data_root_not_directory")
        if not resolved_owner_root.is_dir():
            raise CandidateSubstrateSourceError("selected_substrate_owner_root_not_directory")
        if (resolved_owner_root / "production_data").resolve(strict=True) != linked_data_root:
            raise CandidateSubstrateSourceError("selected_substrate_owner_root_mismatch")
        if not resolved_workspace_root.is_dir():
            raise CandidateSubstrateSourceError("selected_substrate_workspace_not_directory")
        if _paths_overlap(resolved_workspace_root, resolved_code_root) or _paths_overlap(
            resolved_workspace_root, resolved_owner_root
        ):
            raise CandidateSubstrateSourceError("selected_substrate_workspace_overlaps_source")

        try:
            manifest = (linked_data_root / "manifest.json").resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise CandidateSubstrateSourceError("selected_substrate_manifest_unavailable") from exc
        try:
            relative_manifest = manifest.relative_to(resolved_owner_root)
        except ValueError as exc:
            raise CandidateSubstrateSourceError(
                "selected_substrate_manifest_outside_owner"
            ) from exc
        if (
            relative_manifest.as_posix() != "production_data/manifest.json"
            or not manifest.is_file()
        ):
            raise CandidateSubstrateSourceError("selected_substrate_manifest_path_invalid")
        try:
            manifest_sha256 = _validated_manifest_sha256(manifest)
        except OSError as exc:
            raise CandidateSubstrateSourceError("selected_substrate_manifest_unreadable") from exc

        return cls(
            code_root=resolved_code_root,
            source_owner_root=resolved_owner_root,
            workspace_root=resolved_workspace_root,
            manifest_ref=_MANIFEST_REF,
            manifest_sha256=manifest_sha256,
        )

    def require_workspace_path(self, output_path: Path) -> Path:
        """Resolve one selected-run destination beneath the caller-owned workspace."""

        try:
            resolved_workspace = self.workspace_root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise CandidateSubstrateSourceError("selected_substrate_workspace_unavailable") from exc
        if resolved_workspace != self.workspace_root:
            raise CandidateSubstrateSourceError("selected_substrate_workspace_drift")
        from polisyos.runtime.quality.data_state_substrate import (
            DataStateSubstrateError,
            _require_workspace_output_path,
        )

        try:
            return _require_workspace_output_path(resolved_workspace, output_path)
        except DataStateSubstrateError as exc:
            raise CandidateSubstrateSourceError(
                "selected_substrate_workspace_output_escape"
            ) from exc

    def require_workspace_tree(self, output_root: Path) -> Path:
        """Check a selected output tree and its existing symlink descendants."""

        resolved_workspace = self.workspace_root.resolve(strict=True)
        if resolved_workspace != self.workspace_root:
            raise CandidateSubstrateSourceError("selected_substrate_workspace_drift")
        from polisyos.runtime.quality.data_state_substrate import (
            DataStateSubstrateError,
            _require_workspace_output_tree,
        )

        try:
            return _require_workspace_output_tree(resolved_workspace, output_root)
        except DataStateSubstrateError as exc:
            raise CandidateSubstrateSourceError(
                "selected_substrate_workspace_output_escape"
            ) from exc

    def require_source_owner_root(self, code_root: Path) -> Path:
        """Recheck the selected roots and manifest before a source-owned read."""

        try:
            resolved_code_root = Path(code_root).resolve(strict=True)
            linked_data_root = (resolved_code_root / "production_data").resolve(strict=True)
            resolved_owner_root = self.source_owner_root.resolve(strict=True)
            owner_data_root = (resolved_owner_root / "production_data").resolve(strict=True)
            manifest = (owner_data_root / "manifest.json").resolve(strict=True)
            resolved_workspace_root = self.workspace_root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise CandidateSubstrateSourceError("selected_substrate_profile_unavailable") from exc
        try:
            manifest_sha256 = _validated_manifest_sha256(manifest)
        except OSError as exc:
            raise CandidateSubstrateSourceError("selected_substrate_profile_unavailable") from exc

        if resolved_code_root != self.code_root:
            raise CandidateSubstrateSourceError("selected_substrate_code_root_mismatch")
        if linked_data_root != owner_data_root:
            raise CandidateSubstrateSourceError("selected_substrate_data_link_drift")
        if resolved_workspace_root != self.workspace_root:
            raise CandidateSubstrateSourceError("selected_substrate_workspace_drift")
        if not resolved_workspace_root.is_dir():
            raise CandidateSubstrateSourceError("selected_substrate_workspace_not_directory")
        if _paths_overlap(resolved_workspace_root, resolved_code_root) or _paths_overlap(
            resolved_workspace_root, resolved_owner_root
        ):
            raise CandidateSubstrateSourceError("selected_substrate_workspace_overlaps_source")
        if self.manifest_ref != _MANIFEST_REF:
            raise CandidateSubstrateSourceError("selected_substrate_manifest_ref_invalid")
        try:
            manifest_relative_path = manifest.relative_to(resolved_owner_root)
        except ValueError as exc:
            raise CandidateSubstrateSourceError(
                "selected_substrate_manifest_outside_owner"
            ) from exc
        if manifest_relative_path.as_posix() != "production_data/manifest.json":
            raise CandidateSubstrateSourceError("selected_substrate_manifest_path_invalid")
        if manifest_sha256 != self.manifest_sha256:
            raise CandidateSubstrateSourceError("selected_substrate_manifest_drift")
        if self.source_use != "candidate_test_input_only":
            raise CandidateSubstrateSourceError("selected_substrate_source_use_invalid")
        return resolved_owner_root


def candidate_source_context_for_entrypoint(
    code_root: Path,
    *,
    source_owner_root: Path | None,
    workspace_root: Path | None,
) -> CandidateSubstrateSourceContext | None:
    """Build one selected-root profile only when both non-code roots are supplied.

    The default remains the historical one-root path. Supplying only a data owner
    or only a workspace is ambiguous and therefore refused at every public CLI.
    """

    if source_owner_root is None and workspace_root is None:
        return None
    if source_owner_root is None or workspace_root is None:
        raise CandidateSubstrateSourceError("selected_substrate_roots_require_pair")
    return CandidateSubstrateSourceContext.from_code_root(
        code_root,
        workspace_root=workspace_root,
        source_owner_root=source_owner_root,
    )


def _validated_manifest_sha256(path: Path) -> str:
    """Parse the selected root manifest as a JSON object before binding its bytes."""

    try:
        raw = path.read_bytes()
        value = json.loads(
            raw,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise CandidateSubstrateSourceError("selected_substrate_manifest_invalid") from exc
    if not isinstance(value, dict):
        raise CandidateSubstrateSourceError("selected_substrate_manifest_invalid")
    return hashlib.sha256(raw).hexdigest()


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate members rather than choosing an ambiguous manifest value."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_object_key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    """Reject non-standard NaN and infinity tokens accepted by Python's JSON parser."""

    raise ValueError(f"non_json_constant:{value}")


def _is_within(path: Path, root: Path) -> bool:
    """Return whether ``path`` is ``root`` or one of its descendants."""

    return path == root or path.is_relative_to(root)


def _paths_overlap(first: Path, second: Path) -> bool:
    """Return whether either root contains the other."""

    return _is_within(first, second) or _is_within(second, first)
