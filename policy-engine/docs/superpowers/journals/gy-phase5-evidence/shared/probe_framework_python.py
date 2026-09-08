"""Verify copied framework Python without inherited dynamic-loader settings."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def main() -> None:
    """Execute both direct and system-shell children from a real copied venv."""
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("DYLD_")
    }
    records = []
    with tempfile.TemporaryDirectory(prefix="gyphase5-framework-copy-", dir=".tmp") as scratch:
        private = Path(scratch).resolve() / "environment"
        venv.EnvBuilder(with_pip=False).create(private)
        python = str(private / "bin/python3")
        expression = (
            "import json,sys; print(json.dumps({'version':sys.version,'prefix':sys.prefix}))"
        )
        commands = [
            [python, "-c", expression],
            ["/bin/bash", "-c", 'exec "$1" -c "$2"', "probe", python, expression],
        ]
        for command in commands:
            child = subprocess.run(  # noqa: S603 - measured local copied interpreter.
                command, env=environment, capture_output=True, text=True, check=False
            )
            records.append({
                "argv": command,
                "returncode": child.returncode,
                "stdout": child.stdout,
                "stderr": child.stderr,
            })
        sys.stdout.write(json.dumps({
            "outer_executable": sys.executable,
            "outer_version": sys.version,
            "DYLD_environment_keys": [key for key in environment if key.startswith("DYLD_")],
            "records": records,
        }, indent=2) + "\n")
        for record in records:
            if record["returncode"] != 0:
                raise RuntimeError("copied_framework_child_failed")
            result = json.loads(record["stdout"])
            if result["version"] != sys.version or result["prefix"] != str(private):
                raise RuntimeError("copied_framework_child_escaped_private_prefix")


if __name__ == "__main__":
    main()
