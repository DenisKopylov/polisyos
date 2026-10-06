from __future__ import annotations

import collections
import hashlib
import json
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).parent
ARCHIVE = ROOT / "candidate.tar"
WHEEL = ROOT / "dist" / "policy_engine-0.1.0-py3-none-any.whl"
SDIST = ROOT / "dist" / "policy_engine-0.1.0.tar.gz"
OUT = ROOT / "package-inventory.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def suffix(path: str) -> str:
    name = PurePosixPath(path).name
    if name == "py.typed":
        return "py.typed"
    if name.endswith(".d.ts"):
        return ".d.ts"
    return PurePosixPath(name).suffix or "<none>"


def counts(paths: list[str]) -> dict[str, int]:
    return dict(sorted(collections.Counter(suffix(path) for path in paths).items()))


def pathset_digest(paths: list[str]) -> str:
    return digest("\n".join(sorted(paths)).encode())


with tarfile.open(ARCHIVE, "r:") as archive:
    archive_files = {
        member.name.removeprefix("policy-engine/"): archive.extractfile(member).read()
        for member in archive.getmembers()
        if member.isfile() and member.name.startswith("policy-engine/")
    }

with zipfile.ZipFile(WHEEL) as wheel_file:
    wheel_all = {
        item.filename: wheel_file.read(item.filename)
        for item in wheel_file.infolist()
        if not item.is_dir()
    }
wheel_payload = {path: data for path, data in wheel_all.items() if ".dist-info/" not in path}

with tarfile.open(SDIST, "r:gz") as sdist_file:
    sdist_all = {
        member.name: sdist_file.extractfile(member).read()
        for member in sdist_file.getmembers()
        if member.isfile()
    }
prefixes = {PurePosixPath(path).parts[0] for path in sdist_all}
assert len(prefixes) == 1, prefixes
prefix = prefixes.pop() + "/"
sdist = {
    path.removeprefix(prefix): data
    for path, data in sdist_all.items()
    if path.startswith(prefix)
}

source_packages: dict[str, bytes] = {}
for path, data in archive_files.items():
    if path.startswith("src/polisyos/"):
        source_packages["polisyos/" + path.removeprefix("src/polisyos/")] = data
    elif path.startswith("tools/"):
        source_packages[path] = data

force_source = "architecture/production_quality/method_catalog_dependency_digest_domains.toml"
force_dest = "polisyos/foundry/methods/catalog/_resources/method_catalog_dependency_digest_domains.toml"
assert force_source in archive_files
source_packages[force_dest] = archive_files[force_source]

wheel_source_mismatches: list[str] = []
wheel_unmapped: list[str] = []
wheel_sdist_missing: list[str] = []
wheel_sdist_mismatches: list[str] = []
for path, data in sorted(wheel_payload.items()):
    if path not in source_packages:
        wheel_unmapped.append(path)
    elif data != source_packages[path]:
        wheel_source_mismatches.append(path)
    if path == force_dest:
        candidates = [force_source]
    elif path.startswith("polisyos/"):
        candidates = ["src/polisyos/" + path.removeprefix("polisyos/")]
    else:
        candidates = [path]
    available = [candidate for candidate in candidates if candidate in sdist]
    if not available:
        wheel_sdist_missing.append(path)
    elif not any(data == sdist[candidate] for candidate in available):
        wheel_sdist_mismatches.append(path)

sdist_mismatches = [
    path for path, data in sorted(sdist.items()) if path in archive_files and data != archive_files[path]
]
sdist_generated = sorted(path for path in sdist if path not in archive_files)
sdist_missing = sorted(set(archive_files) - set(sdist))
source_readmes = {
    path for path in archive_files if PurePosixPath(path).name.casefold().startswith("readme")
}
sdist_readmes = {
    path for path in sdist if PurePosixPath(path).name.casefold().startswith("readme")
}
source_package_readmes = {
    path
    for path in source_packages
    if PurePosixPath(path).name.casefold().startswith("readme")
}
wheel_readmes = {
    path
    for path in wheel_payload
    if PurePosixPath(path).name.casefold().startswith("readme")
}

entry_text = next(
    (data.decode() for path, data in wheel_all.items() if path.endswith(".dist-info/entry_points.txt")),
    "",
)
entry_groups: dict[str, list[list[str]]] = {}
current_group: str | None = None
for line in entry_text.splitlines():
    line = line.strip()
    if not line:
        continue
    if line.startswith("[") and line.endswith("]"):
        current_group = line[1:-1]
        entry_groups[current_group] = []
    elif current_group is not None and "=" in line:
        name, value = (part.strip() for part in line.split("=", 1))
        entry_groups[current_group].append([name, value])

changed_paths = (
    "src/polisyos/runtime/quality/explanation_reliability.py",
    "tests/unit/runtime/quality/test_berl_warrant_reliability.py",
)
changed_map = []
for path in changed_paths:
    data = archive_files[path]
    wheel_path = "polisyos/" + path.removeprefix("src/polisyos/") if path.startswith("src/polisyos/") else None
    wheel_data = wheel_payload.get(wheel_path) if wheel_path else None
    sdist_data = sdist.get(path)
    changed_map.append(
        {
            "source_path": "policy-engine/" + path,
            "source_sha256": digest(data),
            "source_bytes": len(data),
            "sdist_path": path if sdist_data is not None else None,
            "sdist_sha256": digest(sdist_data) if sdist_data is not None else None,
            "sdist_byte_identical": sdist_data == data if sdist_data is not None else None,
            "wheel_path": wheel_path if wheel_data is not None else None,
            "wheel_sha256": digest(wheel_data) if wheel_data is not None else None,
            "wheel_byte_identical": wheel_data == data if wheel_data is not None else None,
        }
    )

with zipfile.ZipFile(WHEEL) as wheel_file:
    metadata_path = next(path for path in wheel_all if path.endswith(".dist-info/METADATA"))
    metadata_lines = wheel_all[metadata_path].decode().splitlines()

receipt = {
    "candidate": {
        "commit": "87999f69c5f99d69ee2622ef00cd7f4e04d7d572",
        "tree": "0280403e6837c5b220ac748a7674f4e5830ba0ab",
        "base": "999f56c443e3b4ef74d849828641836a8f335b3d",
    },
    "source_archive": {
        "sha256": digest(ARCHIVE.read_bytes()),
        "bytes": ARCHIVE.stat().st_size,
        "source_files": len(archive_files),
    },
    "source_denominators": {
        "all_policy_engine_files": len(archive_files),
        "all_policy_engine_suffix_counts": counts(sorted(archive_files)),
        "src_polisyos_files": sum(path.startswith("src/polisyos/") for path in archive_files),
        "tools_files": sum(path.startswith("tools/") for path in archive_files),
        "package_payload_files": len(source_packages),
        "all_readmes": len(source_readmes),
        "package_root_readmes": len(source_package_readmes),
        "readmes_outside_package_roots": len(source_readmes - source_package_readmes),
    },
    "sdist": {
        "sha256": digest(SDIST.read_bytes()),
        "bytes": SDIST.stat().st_size,
        "members": len(sdist_all),
        "project_members": len(sdist),
        "exact_source_members": sum(path in archive_files and data == archive_files[path] for path, data in sdist.items()),
        "generated_members": sdist_generated,
        "source_omission_count": len(sdist_missing),
        "source_omission_suffix_counts": counts(sdist_missing),
        "mismatches": sdist_mismatches,
        "all_source_readmes_included": source_readmes == sdist_readmes,
        "source_readme_omissions": sorted(source_readmes - sdist_readmes),
    },
    "wheel": {
        "sha256": digest(WHEEL.read_bytes()),
        "bytes": WHEEL.stat().st_size,
        "members": len(wheel_all),
        "payload_members": len(wheel_payload),
        "exact_package_payload_paths": len(source_packages),
        "source_mismatches": wheel_source_mismatches,
        "unmapped_payload": wheel_unmapped,
        "all_wheel_payload_in_sdist": not wheel_sdist_missing and not wheel_sdist_mismatches,
        "missing_from_sdist": wheel_sdist_missing,
        "sdist_mismatches": wheel_sdist_mismatches,
        "package_readmes": len(wheel_readmes),
        "package_readme_omissions": sorted(source_package_readmes - wheel_readmes),
        "apps_packages_payload_members": sum(path.startswith(("apps/", "packages/")) for path in wheel_payload),
        "entry_points_groups": {name: len(values) for name, values in entry_groups.items()},
        "entry_points_total": sum(len(values) for values in entry_groups.values()),
        "base_requires_dist": [line for line in metadata_lines if line.startswith("Requires-Dist:") and "; extra" not in line],
    },
    "forced_resource": {
        "source_path": force_source,
        "wheel_path": force_dest,
        "byte_identical": wheel_payload.get(force_dest) == archive_files[force_source],
    },
    "changed_path_byte_map": changed_map,
}
OUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps(receipt, indent=2, sort_keys=True))
