"""Execute the real CR1 package worker CLI and inspect its persisted custody result."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile

from tests.unit.runtime.quality.test_adaptation_transition import (
    _api,
    _assert_one_publication,
    _request,
    _runtime,
)

if __name__ == "__main__":
    raw = Path("docs/superpowers/journals/gy-builders/b/raw").resolve()
    raw.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="cli-smoke-", dir=raw))
    api = _api()
    runtime = _runtime(api, root)
    ticket = runtime.submit(_request(api))
    command = [sys.executable, "-m", "polisyos.runtime.quality.adaptation_transition",
               "--root", str(root), "--tenant", "tenant-1", "--cell", "cell-1",
               "process", ticket]
    sys.stdout.write("COMMAND " + " ".join(command) + "\n")
    run = subprocess.run(command, check=False, text=True, capture_output=True, timeout=240)
    sys.stdout.write(run.stdout)
    sys.stdout.write(run.stderr)
    assert run.returncode == 0, run.returncode
    decision = json.loads(run.stdout)
    assert decision["status"] == "failed_safe"
    assert decision["missing_role"] == "appointed_policy_rollback_authority"
    assert decision["appointed_signer"] is None and decision["execution_authorized"] is False
    _assert_one_publication(root)
    sys.stdout.write("CLI custody readback: one SQL publication, matching complete CAS set.\n")
