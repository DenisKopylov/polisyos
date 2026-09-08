"""Exercise canonical-byte ownership through the actual formatter and DS11 check."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def run(command: list[str], cwd: Path) -> dict[str, object]:
    """Capture one real owner invocation, including its complete result."""
    started = time.monotonic()
    result = subprocess.run(  # noqa: S603 — fixed local owner commands.
        command, cwd=cwd, capture_output=True, text=True, check=False
    )
    return {
        "argv": command,
        "cwd": str(cwd),
        "PATH": os.environ.get("PATH"),
        "PYTHONPATH": os.environ.get("PYTHONPATH"),
        "returncode": result.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    """Remove the writer boundary and require the unchanged freshness check red."""
    root = Path.cwd()
    dashboard = root / "apps/runtime-dashboard"
    artifact = dashboard / "public/atlas/trust-claim-posture.v1.json"
    config = dashboard / ".prettierignore"
    writer_bytes = artifact.read_bytes()
    config_bytes = config.read_bytes()
    entry = b"/public/atlas/trust-claim-posture.v1.json\n"
    if config_bytes.count(entry) != 1:
        raise ValueError("ownership_entry_ambiguous")
    formatter = [
        "corepack", "pnpm", "exec", "prettier", "--write", "--ignore-unknown",
        "public/atlas/trust-claim-posture.v1.json",
    ]
    checker = [
        sys.executable, "-m", "tools.quality.validation.check_trust_claim_posture",
        "--repo-root", ".", "--check",
    ]
    records: dict[str, object] = {}
    try:
        records["with_owner_boundary"] = run(formatter, dashboard)
        records["boundary_preserves_writer_bytes"] = artifact.read_bytes() == writer_bytes
        config.write_bytes(config_bytes.replace(entry, b""))
        records["without_owner_boundary"] = run(formatter, dashboard)
        formatted = artifact.read_bytes()
        records["removal_changes_bytes"] = formatted != writer_bytes
        records["removal_preserves_all_parsed_values"] = (
            json.loads(formatted) == json.loads(writer_bytes)
        )
        records["real_check_after_removal"] = run(checker, root)
    finally:
        config.write_bytes(config_bytes)
        artifact.write_bytes(writer_bytes)
    records["writer_sha256"] = hashlib.sha256(writer_bytes).hexdigest()
    records["restored_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    records["artifact_restored_exactly"] = artifact.read_bytes() == writer_bytes
    records["configuration_restored_exactly"] = config.read_bytes() == config_bytes
    sys.stdout.write(json.dumps(records, indent=2) + "\n")
    if not all(records[key] is True for key in (
        "boundary_preserves_writer_bytes", "removal_changes_bytes",
        "removal_preserves_all_parsed_values", "artifact_restored_exactly",
        "configuration_restored_exactly",
    )):
        raise ValueError("formatter_ownership_property_not_established")
    if any(records[key]["returncode"] != 0 for key in (  # type: ignore[index]
        "with_owner_boundary", "without_owner_boundary"
    )):
        raise ValueError("formatter_command_failed")
    checked = records["real_check_after_removal"]
    if checked["returncode"] != 1 or (  # type: ignore[index]
        "ValueError: DS11-GENERATED-DRIFT" not in checked["stderr"]  # type: ignore[index]
    ):
        raise ValueError("unchanged_owner_did_not_refuse_formatted_bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
