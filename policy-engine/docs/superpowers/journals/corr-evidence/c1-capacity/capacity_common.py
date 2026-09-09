"""Secret-safe local measurement support; no credential becomes an artifact."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from polisyos.data_forge.domains.academic.batch.reextraction_transport import SafeJsonWriter

EVIDENCE = Path("docs/superpowers/journals/corr-evidence/c1-capacity")
OLD = Path("docs/superpowers/journals/corr-evidence/c")


def load_credential() -> str:
    """Locate only the user-designated key without printing names or values."""
    prefix = "sk-3dd7c527"
    values = list(os.environ.values()) + list(dotenv_values(
        "/Users/deniskopylov/polisyos/policy-engine/.env", interpolate=False,
    ).values())
    matches = {
        value.strip() for value in values
        if isinstance(value, str) and value.strip().startswith(prefix)
    }
    if not matches:
        raise ValueError("designated_provider_credential_absent")
    if len(matches) != 1:
        raise ValueError("designated_provider_credential_ambiguous")
    return next(iter(matches))


def digest(value: object) -> str:
    """Bind a canonical JSON value without discarding null or absent fields."""
    return "sha256:" + hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    """Add the pre-outcome declaration's canonical content binding."""
    return {**value, "content_hash": digest(value)}


def read_sealed(path: Path) -> dict[str, Any]:
    """Verify a declaration before interpreting it."""
    data = json.loads(path.read_text())
    unsigned = {key: value for key, value in data.items() if key != "content_hash"}
    if digest(unsigned) != data.get("content_hash"):
        raise ValueError("measurement_declaration_hash_mismatch")
    return data


def local_estimator(model: str, messages: list[dict[str, str]]) -> int:
    """Use the repository estimator from the diagnostics boundary."""
    from polisyos.scientist.orchestration.llm.token_estimator import estimate_request_tokens

    return estimate_request_tokens(messages=messages, model=model, provider_hint="gonka")


def main() -> int:
    """Capture a single deciding command, checking every stream before writing."""
    output, *command = sys.argv[1:]
    writer = SafeJsonWriter(load_credential())
    writer.check_payload(command)
    timeout = float(os.environ.get("GY_CAPTURE_TIMEOUT_SECONDS", "300"))
    started = time.monotonic()
    timed_out = False
    with subprocess.Popen(  # noqa: S603 - explicitly supplied local module argv.
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,
    ) as child:
        try:
            stdout, stderr = child.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGKILL)
            stdout, stderr = child.communicate()
        returncode = child.returncode
    record = {
        "cwd": str(Path.cwd()), "argv": command,
        "PATH": os.environ.get("PATH"), "PYTHONPATH": os.environ.get("PYTHONPATH"),
        "returncode": returncode, "capture_returncode": 124 if timed_out else returncode,
        "elapsed_seconds": time.monotonic() - started, "timeout_seconds": timeout,
        "timed_out": timed_out, "stdout": stdout, "stderr": stderr,
        "credential_scan_before_write": True,
    }
    # On an echo the whole raw record is refused, including stdout/stderr forwarding.
    writer(Path(output), record)
    sys.stdout.write(writer.encode({key: record[key] for key in (
        "argv", "returncode", "capture_returncode", "elapsed_seconds", "timed_out",
    )}))
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return record["capture_returncode"]


if __name__ == "__main__":
    raise SystemExit(main())
