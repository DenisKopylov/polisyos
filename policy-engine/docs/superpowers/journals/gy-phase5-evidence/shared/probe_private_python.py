"""Exercise the guardrail's exact copied-interpreter station prerequisite."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
import tempfile
import venv
from pathlib import Path


def main() -> None:
    """Retain the original loader failure and verify a library-path-only repair."""
    library = Path(sysconfig.get_config_var("LIBDIR"))
    dylib = library / sysconfig.get_config_var("LDLIBRARY")
    if not dylib.is_file():
        raise RuntimeError("measured_base_python_library_unavailable")
    records = []
    with tempfile.TemporaryDirectory(prefix="gyphase5-python-copy-", dir=".tmp") as scratch:
        private = Path(scratch).resolve() / "environment"
        venv.EnvBuilder(with_pip=False).create(private)
        command = [
            str(private / "bin/python3"),
            "-c",
            "import json,sys; print(json.dumps({'version':sys.version,"
            "'base_prefix':sys.base_prefix,'executable':sys.executable}))",
        ]
        for mode in ("original", "base_library_path"):
            environment = os.environ.copy()
            environment.pop("DYLD_LIBRARY_PATH", None)
            if mode == "base_library_path":
                environment["DYLD_LIBRARY_PATH"] = str(library)
            child = subprocess.run(  # noqa: S603 - actual local copied interpreter.
                command, env=environment, capture_output=True, text=True, check=False
            )
            records.append({
                "mode": mode,
                "argv": command,
                "DYLD_LIBRARY_PATH": environment.get("DYLD_LIBRARY_PATH"),
                "returncode": child.returncode,
                "stdout": child.stdout,
                "stderr": child.stderr,
            })
        sys.stdout.write(json.dumps({
            "library": str(dylib),
            "outer_version": sys.version,
            "records": records,
        }, indent=2) + "\n")
        if records[0]["returncode"] == 0 or records[1]["returncode"] != 0:
            raise RuntimeError("copied_interpreter_station_property_not_established")
        fixed = json.loads(records[1]["stdout"])
        if fixed["version"] != sys.version:
            raise RuntimeError("copied_interpreter_version_changed")


if __name__ == "__main__":
    main()
