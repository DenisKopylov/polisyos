#!/usr/bin/env python3
"""Operate the Foundry-owned dependency profile without minting authority.

``sync`` preserves the production cutoff-first refusal and performs no write.
``diagnose`` recomputes the dependency-only discriminant and observes the
current interpreter read-only. ``regenerate-owner`` is the sole surgical owner
mechanism for rebinding tracked dependency bytes to the purpose admission.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Literal

from packaging.markers import default_environment

from polisyos.foundry.methods.catalog.dependency_authority import (
    AbsoluteRequestPath,
    MethodCatalogDependencyAuthorityRequest,
    build_production_method_catalog_dependency_authority,
)
from polisyos.foundry.methods.catalog.dependency_evidence import (
    DigestDomain,
    domain_digest,
)
from polisyos.foundry.methods.catalog.dependency_profile import (
    DependencyProfileDiscriminant,
    MethodCatalogDependencyProfileDeclaration,
    declaration_ref,
    diagnose_dependency_environment,
    load_dependency_profile_registry,
    observe_installed_distributions,
    resolve_dependency_discriminant,
    resolve_profile_declaration,
    resolve_profile_declaration_for_purpose,
)

_PRODUCT_ROOT = Path(__file__).resolve().parents[3]
_QUALITY_RELATIVE = Path("architecture/production_quality")
_PROFILE_RELATIVE = _QUALITY_RELATIVE / "method_catalog_dependency_profiles.toml"
_AUTHORITY_RELATIVE = _QUALITY_RELATIVE / "method_catalog_dependency_authority.toml"
_AUTHORITY_PURPOSE = "n8_method_catalog_reconstruction"
_GIT_BIN = shutil.which("git")
_DEPENDENCY_SOURCE_PATHS = (
    _PROFILE_RELATIVE,
    _AUTHORITY_RELATIVE,
    _QUALITY_RELATIVE / "method_catalog_dependency_digest_domains.toml",
    Path("pyproject.toml"),
    Path("uv.lock"),
    Path("src/polisyos/foundry/methods/catalog/dependency_profile.py"),
    Path("src/polisyos/foundry/methods/catalog/dependency_evidence.py"),
    Path("tools/devx/foundry/sync_dependency_profile.py"),
)


def _add_purpose_and_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--authority-purpose",
        choices=(_AUTHORITY_PURPOSE,),
        required=True,
    )
    parser.add_argument("--tracked-source-root", type=Path, required=True)
    parser.add_argument("--source-freeze", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)

    sync = commands.add_parser("sync", help="return the production preflight refusal")
    _add_purpose_and_source_arguments(sync)
    sync.add_argument("--production-data-root", type=Path, required=True)
    sync.add_argument("--production-data-appointment", type=Path, required=True)
    sync.add_argument("--environment-root", type=Path, required=True)
    sync.add_argument("--python-bin", type=Path, required=True)
    sync.add_argument("--uv-bin", type=Path, required=True)
    sync.add_argument("--uv-cache-dir", type=Path, required=True)
    sync.add_argument("--offline", action="store_true", required=True)
    sync.add_argument("--receipt", type=Path, required=True)

    diagnose = commands.add_parser(
        "diagnose",
        help="read dependency bytes and report a non-decisive diagnostic",
    )
    _add_purpose_and_source_arguments(diagnose)

    regenerate = commands.add_parser(
        "regenerate-owner",
        help="rebind the owner declaration and purpose row to tracked bytes",
    )
    regenerate.add_argument(
        "--authority-purpose",
        choices=(_AUTHORITY_PURPOSE,),
        required=True,
    )
    regenerate.add_argument("--tracked-source-root", type=Path, required=True)
    action = regenerate.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", action="store_true")
    action.add_argument("--corrupt-field-drift-check", action="store_true")
    return parser


def _normalized_argv(argv: list[str] | None) -> list[str]:
    raw = list(sys.argv[1:] if argv is None else argv)
    modes = {"sync", "diagnose", "regenerate-owner"}
    if not raw or raw[0] not in modes:
        return ["sync", *raw]
    return raw


def _source_freeze_matches(root: Path, source_freeze: str) -> bool:
    if _GIT_BIN is None or re.fullmatch(r"[0-9a-f]{40}", source_freeze) is None:
        return False
    try:
        observed = subprocess.run(  # noqa: S603
            [_GIT_BIN, "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(  # noqa: S603
            [
                _GIT_BIN,
                "diff",
                "--quiet",
                source_freeze,
                "--",
                *(path.as_posix() for path in _DEPENDENCY_SOURCE_PATHS),
            ],
            cwd=root,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return observed == source_freeze


def _owner_purpose_row(
    authority_bytes: bytes,
    *,
    authority_purpose: str,
) -> dict[str, object]:
    wire = tomllib.loads(authority_bytes.decode("utf-8"))
    rows = wire.get("purpose_admissions")
    if type(rows) is not list:
        raise ValueError("authority purpose admission denominator is missing")
    matches = tuple(
        row
        for row in rows
        if type(row) is dict and row.get("authority_purpose") == authority_purpose
    )
    if len(matches) != 1:
        raise ValueError("authority purpose must resolve to exactly one owner row")
    return matches[0]


def _replace_exact_once(raw: bytes, old: str, new: str) -> bytes:
    old_bytes = old.encode("utf-8")
    if raw.count(old_bytes) != 1:
        raise ValueError("owner field must occur exactly once before regeneration")
    return raw.replace(old_bytes, new.encode("utf-8"), 1)


def _regenerated_owner_bytes(
    root: Path,
    *,
    authority_purpose: str,
    pyproject_bytes: bytes | None = None,
) -> tuple[bytes, bytes, MethodCatalogDependencyProfileDeclaration]:
    profile_path = root / _PROFILE_RELATIVE
    authority_path = root / _AUTHORITY_RELATIVE
    profile_bytes = profile_path.read_bytes()
    authority_bytes = authority_path.read_bytes()
    registry = load_dependency_profile_registry(profile_path)
    purpose_row = _owner_purpose_row(
        authority_bytes,
        authority_purpose=authority_purpose,
    )
    profile_id = purpose_row.get("profile_id")
    if type(profile_id) is not str:
        raise ValueError("owner profile identity is invalid")
    current = resolve_profile_declaration(registry, profile_id=profile_id)
    source_pyproject = (
        (root / "pyproject.toml").read_bytes()
        if pyproject_bytes is None
        else pyproject_bytes
    )
    updated = current.model_copy(
        update={
            "pyproject_ref": domain_digest(DigestDomain.PYPROJECT, source_pyproject),
            "lockfile_ref": domain_digest(
                DigestDomain.UV_LOCK,
                (root / "uv.lock").read_bytes(),
            ),
        }
    )
    current_reference = declaration_ref(current)
    updated_reference = declaration_ref(updated)
    regenerated_profile = _replace_exact_once(
        profile_bytes,
        current.pyproject_ref.value,
        updated.pyproject_ref.value,
    )
    regenerated_profile = _replace_exact_once(
        regenerated_profile,
        current.lockfile_ref.value,
        updated.lockfile_ref.value,
    )
    regenerated_authority = _replace_exact_once(
        authority_bytes,
        current_reference.artifact_id,
        updated_reference.artifact_id,
    )
    regenerated_authority = _replace_exact_once(
        regenerated_authority,
        current_reference.semantic_hash.value,
        updated_reference.semantic_hash.value,
    )
    return regenerated_profile, regenerated_authority, updated


def _run_sync(args: argparse.Namespace) -> int:
    if args.tracked_source_root.resolve() != _PRODUCT_ROOT.resolve():
        print(json.dumps({"status": "rejected", "code": "tracked_source_root_mismatch"}))
        return 1
    request = MethodCatalogDependencyAuthorityRequest(
        authority_purpose=args.authority_purpose,
        expected_source_freeze_commit=args.source_freeze,
        production_data_root=AbsoluteRequestPath(value=args.production_data_root),
        environment_root=AbsoluteRequestPath(value=args.environment_root),
    )
    result = build_production_method_catalog_dependency_authority().resolve(request)
    print(result.model_dump_json(exclude_none=False))
    return 1


def _run_diagnose(args: argparse.Namespace) -> int:
    root = args.tracked_source_root.resolve()
    if root != _PRODUCT_ROOT.resolve():
        print(json.dumps({"status": "rejected", "code": "tracked_source_root_mismatch"}))
        return 1
    if not _source_freeze_matches(root, args.source_freeze):
        print(json.dumps({"status": "rejected", "code": "source_freeze_mismatch"}))
        return 1
    profile_path = root / _PROFILE_RELATIVE
    authority_path = root / _AUTHORITY_RELATIVE
    declaration = resolve_profile_declaration_for_purpose(
        load_dependency_profile_registry(profile_path),
        authority_registry_bytes=authority_path.read_bytes(),
        authority_purpose=args.authority_purpose,
    )
    marker_environment = default_environment()
    marker_environment["extra"] = ""
    resolved = resolve_dependency_discriminant(
        declaration,
        pyproject_bytes=(root / "pyproject.toml").read_bytes(),
        lockfile_bytes=(root / "uv.lock").read_bytes(),
        marker_environment=marker_environment,
    )
    if not isinstance(resolved, DependencyProfileDiscriminant):
        print(resolved.model_dump_json(exclude_none=False))
        return 1
    diagnostic = diagnose_dependency_environment(
        discriminant=resolved,
        observed_distributions=observe_installed_distributions(resolved),
    )
    print(
        json.dumps(
            {
                "decision_role": "ambient_non_decisive",
                "authority_admission": "forbidden",
                "diagnostic": diagnostic.model_dump(mode="json"),
            },
            sort_keys=True,
        )
    )
    return 0 if diagnostic.status == "pass" else 1


def _run_regenerate_owner(args: argparse.Namespace) -> int:
    root = args.tracked_source_root.resolve()
    profile_path = root / _PROFILE_RELATIVE
    authority_path = root / _AUTHORITY_RELATIVE
    proposed_profile, proposed_authority, declaration = _regenerated_owner_bytes(
        root,
        authority_purpose=args.authority_purpose,
    )
    if args.corrupt_field_drift_check:
        corrupt_profile, corrupt_authority, _declaration = _regenerated_owner_bytes(
            root,
            authority_purpose=args.authority_purpose,
            pyproject_bytes=(root / "pyproject.toml").read_bytes()
            + b"\n# corrupt-byte-probe\n",
        )
        stale = (
            corrupt_profile != profile_path.read_bytes()
            or corrupt_authority != authority_path.read_bytes()
        )
        print(
            json.dumps(
                {
                    "status": "rejected" if stale else "incorrectly_current",
                    "code": "tracked_dependency_bytes_stale" if stale else "probe_failed",
                },
                sort_keys=True,
            )
        )
        return 1 if stale else 0
    current = (
        proposed_profile == profile_path.read_bytes()
        and proposed_authority == authority_path.read_bytes()
    )
    if args.check:
        print(
            json.dumps(
                {
                    "status": "current" if current else "stale",
                    "profile_id": declaration.profile_id,
                },
                sort_keys=True,
            )
        )
        return 0 if current else 1
    if args.write:
        profile_path.write_bytes(proposed_profile)
        authority_path.write_bytes(proposed_authority)
        print(json.dumps({"status": "regenerated"}, sort_keys=True))
        return 0
    reference = declaration_ref(declaration)
    print(
        json.dumps(
            {
                "profile_id": declaration.profile_id,
                "pyproject_sha256": declaration.pyproject_ref.value,
                "uv_lock_sha256": declaration.lockfile_ref.value,
                "declaration_artifact_id": reference.artifact_id,
                "declaration_semantic_hash": reference.semantic_hash.value,
            },
            sort_keys=True,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run one explicit Foundry dependency-profile operation.

    Args:
        argv: Optional argument vector. Legacy vectors without a mode retain
            the cutoff-first ``sync`` behavior.

    Returns:
        Zero only for a successful read-only diagnosis, a current/regenerated
        owner row, or a proposal. Refusals and stale/corrupt checks return one.
    """

    args = _parser().parse_args(_normalized_argv(argv))
    mode: Literal["sync", "diagnose", "regenerate-owner"] = args.mode
    if mode == "sync":
        return _run_sync(args)
    if mode == "diagnose":
        return _run_diagnose(args)
    return _run_regenerate_owner(args)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
