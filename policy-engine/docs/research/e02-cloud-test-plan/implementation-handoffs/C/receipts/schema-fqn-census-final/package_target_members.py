"""Read-only exact-path census for the frozen DFK candidate archives."""
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import zipfile
from pathlib import Path
from typing import Any

CANDIDATE = "8ac2c232445eb78b1689fe2f6fb5e1830ccd5b35"
TREE = "ec6137a453d3aafdfd46e1c6304e4cf3a9de3da5"
SDIST_PREFIX = "policy_engine-0.1.0/"

TARGETS: dict[str, tuple[str, ...]] = {
    "LA-005": ("src/polisyos/foundry/domain/schema.py",),
    "LA-006": (
        "src/polisyos/foundry/domain/mechanisms/__init__.py",
        "src/polisyos/foundry/domain/mechanisms/README.md",
    ),
    "LA-026": ("src/polisyos/data_forge/kernel/schemas/codegen.py",),
    "LA-027": (
        "src/polisyos/data_forge/kernel/pipeline/schemas/__init__.py",
        "src/polisyos/data_forge/kernel/pipeline/schemas/README.md",
    ),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_archive", type=Path)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("sdist", type=Path)
    args = parser.parse_args()

    with tarfile.open(args.source_archive, "r:") as archive:
        source_members: dict[str, bytes] = {}
        for member in archive.getmembers():
            if member.isfile() and member.name.startswith("policy-engine/"):
                stream = archive.extractfile(member)
                assert stream is not None
                source_members[member.name.removeprefix("policy-engine/")] = stream.read()

    with zipfile.ZipFile(args.wheel) as wheel:
        wheel_members = {
            name: wheel.read(name)
            for name in wheel.namelist()
            if not name.endswith("/")
        }

    with tarfile.open(args.sdist, "r:gz") as sdist:
        sdist_members: dict[str, bytes] = {}
        for member in sdist.getmembers():
            if member.isfile() and member.name.startswith(SDIST_PREFIX):
                stream = sdist.extractfile(member)
                assert stream is not None
                sdist_members[member.name.removeprefix(SDIST_PREFIX)] = stream.read()

    def wheel_path(source_path: str) -> str:
        if source_path.startswith("src/polisyos/"):
            return "polisyos/" + source_path.removeprefix("src/polisyos/")
        return source_path

    path_checks: dict[str, list[dict[str, Any]]] = {}
    for finding_id, source_paths in TARGETS.items():
        checks = []
        for source_path in source_paths:
            package_path = wheel_path(source_path)
            source_bytes = source_members.get(source_path)
            wheel_bytes = wheel_members.get(package_path)
            sdist_bytes = sdist_members.get(source_path)
            checks.append(
                {
                    "source_path": source_path,
                    "wheel_path": package_path,
                    "present_in_source_archive": source_bytes is not None,
                    "present_in_wheel": wheel_bytes is not None,
                    "present_in_sdist": sdist_bytes is not None,
                    "wheel_bytes_equal_source": (
                        source_bytes == wheel_bytes
                        if source_bytes is not None and wheel_bytes is not None
                        else None
                    ),
                    "sdist_bytes_equal_source": (
                        source_bytes == sdist_bytes
                        if source_bytes is not None and sdist_bytes is not None
                        else None
                    ),
                }
            )
        path_checks[finding_id] = checks

    tombstone_prefixes = {
        "source_archive": "src/polisyos/foundry/domain/mechanisms/",
        "wheel": "polisyos/foundry/domain/mechanisms/",
        "sdist": "src/polisyos/foundry/domain/mechanisms/",
    }
    all_source_paths = set(source_members)
    all_wheel_paths = set(wheel_members)
    all_sdist_paths = set(sdist_members)
    tombstone_package_presence = {
        "source_archive": any(path.startswith(tombstone_prefixes["source_archive"]) for path in all_source_paths),
        "wheel": any(path.startswith(tombstone_prefixes["wheel"]) for path in all_wheel_paths),
        "sdist": any(path.startswith(tombstone_prefixes["sdist"]) for path in all_sdist_paths),
    }

    def artifact(path: Path) -> dict[str, Any]:
        return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)}

    report = {
        "schema": "polisyos.e02.dfk.package-target-members.v1",
        "candidate_commit": CANDIDATE,
        "candidate_tree": TREE,
        "inputs": {
            "git_archive": artifact(args.source_archive),
            "wheel": artifact(args.wheel),
            "sdist": artifact(args.sdist),
        },
        "complete_file_denominator": {
            "git_archive_project_files": len(source_members),
            "wheel_members_including_metadata": len(wheel_members),
            "wheel_payload_files_excluding_dist_info": sum(
                ".dist-info/" not in name for name in wheel_members
            ),
            "sdist_project_members_including_pkg_info": len(sdist_members),
        },
        "tombstone_files_under_prefix_present": tombstone_package_presence,
        "finding_paths": path_checks,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
