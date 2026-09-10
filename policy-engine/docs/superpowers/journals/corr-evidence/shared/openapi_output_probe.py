"""Emit the real export owner's confined-output/default-removal witness."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch


def _observe(root: Path) -> dict[str, Any]:
    from polisyos.runtime.http.openapi_contract import validate_runtime_openapi_contract
    from tools.ops_runners.runtime import export_runtime_openapi

    root.mkdir()
    output = root / "assigned" / "runtime_api_v1.openapi.json"
    previous = Path.cwd()
    try:
        os.chdir(root)
        with patch.object(sys, "argv", ["export_runtime_openapi", "--output", str(output)]):
            returncode = export_runtime_openapi.main()
    finally:
        os.chdir(previous)
    by_path = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    by_walk = {
        (Path(parent) / filename).relative_to(root).as_posix()
        for parent, _directories, files in os.walk(root)
        for filename in files
    }
    if by_path != by_walk:
        raise ValueError("openapi_output_identity_walks_disagree")
    return {
        "returncode": returncode,
        "all_file_identities": sorted(by_path),
        "independently_enumerated_file_identities": sorted(by_walk),
        "outside_assigned": sorted(path for path in by_path if not path.startswith("assigned/")),
        "schema_hash": hashlib.sha256(output.read_bytes()).hexdigest(),
        "schema_issues": validate_runtime_openapi_contract(json.loads(output.read_bytes())),
    }


def main() -> int:
    """Compare actual valid generation with removal of the explicit CAS binding."""
    from polisyos.runtime.http import app as app_owner
    from tools.ops_runners.runtime import export_runtime_openapi

    original = app_owner.create_runtime_api_app

    def omit_binding(**kwargs: object) -> object:
        kwargs.pop("cas_root", None)
        return original(**kwargs)

    with tempfile.TemporaryDirectory(
        prefix="corr-openapi-strangle-", dir=Path.cwd() / ".tmp"
    ) as name:
        root = Path(name).resolve()
        current = _observe(root / "current")
        with patch.object(app_owner, "create_runtime_api_app", omit_binding):
            removed = _observe(root / "removed")
    flipped = (
        current["returncode"] == removed["returncode"] == 0
        and current["schema_issues"] == removed["schema_issues"] == []
        and current["schema_hash"] == removed["schema_hash"]
        and current["all_file_identities"] == ["assigned/runtime_api_v1.openapi.json"]
        and current["outside_assigned"] == []
        and bool(removed["outside_assigned"])
    )
    packet = {
        "schema_version": "policyos.openapi_export_output_strangle.v1",
        "packet_type": "StrangleReceipt",
        "synthetic": True,
        "predicate_provenance": "recomputed",
        "scope": "generator filesystem confinement; no policy authority",
        "owner": "tools.ops_runners.runtime.export_runtime_openapi",
        "source_sha256": hashlib.sha256(
            Path(export_runtime_openapi.__file__).read_bytes()
        ).hexdigest(),
        "legacy_path": "app_factory_default_working_directory_CAS",
        "default_path": "explicit_temporary_CAS_under_assigned_output_root",
        "default_flipped": flipped,
        "current": current,
        "removed": removed,
    }
    digest = hashlib.sha256(
        json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    sys.stdout.write(json.dumps({**packet, "content_hash": f"sha256:{digest}"}, indent=2) + "\n")
    return 0 if flipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
