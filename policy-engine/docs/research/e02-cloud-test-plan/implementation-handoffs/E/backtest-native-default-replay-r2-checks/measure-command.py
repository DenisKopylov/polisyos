from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import time


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


_write_stdout("command=" + json.dumps(sys.argv[1:]), flush=True)
_write_stdout("PYTHONPATH=" + os.environ.get("PYTHONPATH", ""), flush=True)
start = time.monotonic()
process = subprocess.run(sys.argv[1:])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
usage = resource.getrusage(resource.RUSAGE_CHILDREN)
_write_stdout(
    "measured="
    + json.dumps(
        {
            "exit_code": process.returncode,
            "wall_seconds": time.monotonic() - start,
            "user_seconds": usage.ru_utime,
            "system_seconds": usage.ru_stime,
            "max_rss_kib": usage.ru_maxrss,
        }
    ),
    flush=True,
)
sys.exit(process.returncode)
