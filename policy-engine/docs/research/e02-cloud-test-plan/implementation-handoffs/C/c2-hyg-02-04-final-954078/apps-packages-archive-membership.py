"""Reconcile apps/ and packages/ source roots against exact native artifacts."""

from __future__ import annotations

import hashlib
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

RAW = Path(
    "/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/"
    ".tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2"
)
SOURCE = RAW / "sdist_source-extract/source/policy-engine"
WHEEL = RAW / "dist-wheel/policy_engine-0.1.0-py3-none-any.whl"
SDIST = RAW / "dist-sdist/policy_engine-0.1.0.tar.gz"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source_paths = {
        path.relative_to(SOURCE).as_posix(): path
        for root in (SOURCE / "apps", SOURCE / "packages")
        for path in root.rglob("*")
        if path.is_file()
    }
    expected_readmes = {
        path for path in source_paths if PurePosixPath(path).name.lower() == "readme.md"
    }
    with tarfile.open(SDIST, "r:gz") as archive:
        members = {
            name.removeprefix("policy_engine-0.1.0/"): archive.extractfile(name).read()
            for name in archive.getnames()
            if name.startswith(("policy_engine-0.1.0/apps/", "policy_engine-0.1.0/packages/"))
            and archive.getmember(name).isfile()
        }
    actual_readmes = set(members)
    non_readmes = sorted(name for name in actual_readmes if name not in expected_readmes)
    mismatched_readmes = sorted(
        name for name in expected_readmes.intersection(actual_readmes)
        if members[name] != source_paths[name].read_bytes()
    )
    missing_readmes = sorted(expected_readmes - actual_readmes)
    with zipfile.ZipFile(WHEEL) as archive:
        wheel_members = [
            name for name in archive.namelist()
            if name.startswith(("apps/", "packages/")) and not name.endswith("/")
        ]
    apps = sum(name.startswith("apps/") for name in source_paths)
    packages = sum(name.startswith("packages/") for name in source_paths)
    result = {
        "source_files": {"apps": apps, "packages": packages, "total": len(source_paths)},
        "sdist_apps_packages_members": len(actual_readmes),
        "sdist_readme_exception_paths": sorted(actual_readmes),
        "sdist_non_readme_or_unexpected_paths": non_readmes,
        "sdist_missing_readmes": missing_readmes,
        "sdist_readme_byte_mismatches": mismatched_readmes,
        "wheel_apps_or_packages_payload_paths": sorted(wheel_members),
        "source_sdist_wheel_sha256": {
            "source_archive": digest(RAW / "sdist_source.tar"),
            "sdist": digest(SDIST),
            "wheel": digest(WHEEL),
        },
    }
    print(result)
    if non_readmes or missing_readmes or mismatched_readmes or wheel_members:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
