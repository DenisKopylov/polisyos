from __future__ import annotations

import hashlib
import importlib
import importlib.metadata as metadata
import json
import sys
import tarfile
import zipfile
from pathlib import Path


BASE = Path(
    "/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/"
    ".tmp/e02-C2/raw/installed/schema-b8"
)
ARCHIVE = BASE / "candidate.tar"
WHEEL = BASE / "dist/policy_engine-0.1.0-py3-none-any.whl"
ROOT = BASE / "source/policy-engine"
MODULES = {
    "tools.quality.validation.schema_fqn_census": (
        "policy-engine/tools/quality/validation/schema_fqn_census.py",
        "tools/quality/validation/schema_fqn_census.py",
    ),
    "tools.lib.fs": ("policy-engine/tools/lib/fs.py", "tools/lib/fs.py"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


require(Path.cwd().resolve() == Path("/tmp").resolve(), f"unexpected cwd {Path.cwd()}")
before = list(sys.path)
distribution = metadata.distribution("policy-engine")
site = Path(distribution.locate_file("")).resolve()
loaded = {name: importlib.import_module(name) for name in MODULES}
with tarfile.open(ARCHIVE, "r:") as archive, zipfile.ZipFile(WHEEL) as wheel:
    rows = []
    for module_name, (archive_path, wheel_path) in MODULES.items():
        module = loaded[module_name]
        origin = Path(module.__file__).resolve()
        archive_stream = archive.extractfile(archive_path)
        require(archive_stream is not None, f"archive member missing: {archive_path}")
        archive_bytes = archive_stream.read()
        wheel_bytes = wheel.read(wheel_path)
        installed_bytes = origin.read_bytes()
        require(origin.is_relative_to(site), f"{module_name} imported outside site-packages: {origin}")
        require(archive_bytes == wheel_bytes == installed_bytes, f"{module_name} installed byte mismatch")
        rows.append(
            {
                "module": module_name,
                "origin": str(origin),
                "source_archive_member": archive_path,
                "wheel_member": wheel_path,
                "sha256": digest(installed_bytes),
                "archive_wheel_installed_byte_identity": True,
            }
        )
require(list(sys.path) == before, "module imports changed sys.path")
require(str(ROOT) not in sys.path, "candidate source checkout was injected into sys.path")
distributions = {dist.metadata["Name"].lower() for dist in metadata.distributions() if dist.metadata.get("Name")}
print(
    json.dumps(
        {
            "cwd": str(Path.cwd()),
            "isolated": bool(sys.flags.isolated),
            "python": sys.executable,
            "distribution_version": distribution.version,
            "site_packages": str(site),
            "pytest_present": "pytest" in distributions,
            "jsonschema_present": "jsonschema" in distributions,
            "sys_path_unchanged": True,
            "source_checkout_absent_from_sys_path": True,
            "modules": rows,
        },
        sort_keys=True,
    )
)
