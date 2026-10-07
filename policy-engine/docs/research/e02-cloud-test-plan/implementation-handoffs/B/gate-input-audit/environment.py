"""Observe installed metadata against declared direct contributor extras.

No resolver, sync, backend import, test, service or numerical execution occurs.
Only same-project extra references are expanded. External transitive dependency
or ABI/backend availability is not established by this metadata observation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import tomllib
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pyproject", type=Path, required=True)
    args = parser.parse_args()
    raw = args.pyproject.read_bytes()
    project = tomllib.loads(raw.decode())["project"]
    installed: dict[str, list[str]] = {}
    for dist in metadata.distributions():
        name = canonicalize_name(dist.metadata["Name"])
        installed.setdefault(name, []).append(dist.version)
    observed = []
    expanded: set[str] = set()
    pending = ["", "lint", "test", "runtime", "ml", "research", "docs"]
    while pending:
        extra = pending.pop()
        if extra in expanded:
            continue
        expanded.add(extra)
        requirements = (
            project["dependencies"] if not extra else project["optional-dependencies"][extra]
        )
        for literal in requirements:
            requirement = Requirement(literal)
            applicable = requirement.marker is None or requirement.marker.evaluate({"extra": extra})
            if canonicalize_name(requirement.name) == canonicalize_name(project["name"]):
                if applicable:
                    pending.extend(requirement.extras)
                continue
            versions = installed.get(canonicalize_name(requirement.name), [])
            outcome = (
                "excluded_by_declared_marker"
                if not applicable
                else "missing"
                if not versions
                else "ambiguous_distribution"
                if len(versions) != 1
                else "version_mismatch"
                if versions[0] not in requirement.specifier
                else "metadata_satisfies_declared_version"
            )
            observed.append(
                {
                    "extra": extra or "core",
                    "requirement": literal,
                    "installed_versions": versions,
                    "outcome": outcome,
                }
            )
    output = {
        "schema": "policyos.e02.installed_metadata_observation.v1",
        "observation_utc": datetime.now(UTC).isoformat(),
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
        },
        "pyproject": str(args.pyproject),
        "pyproject_sha256": hashlib.sha256(raw).hexdigest(),
        "declared_python": project["requires-python"],
        "python_version_matches": platform.python_version()
        in SpecifierSet(project["requires-python"]),
        "requested_extras": ["lint", "test", "runtime", "ml", "research", "docs"],
        "expanded_same_project_extras": sorted(expanded - {""}),
        "direct_requirements": observed,
        "installed_distribution_denominator": sum(map(len, installed.values())),
        "installed_distributions": dict(sorted(installed.items())),
        "qualification": (
            "actual distribution metadata and direct version constraints only; "
            "no lock equality, external transitive extras, ABI, service or backend runtime proof"
        ),
        "syncs": [],
        "gates_run": [],
    }
    sys.stdout.write(json.dumps(output, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
