"""Run complete consumer-removal variants sequentially without repeated bootstrap."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys

from _build.gy_gaps import c3_consumer_removal


def main() -> int:
    owner = importlib.import_module("polisyos.runtime.quality.workspace.foundry_consumption")
    tests = importlib.import_module(
        "tests.unit.runtime.quality.test_workspace_foundry_consumption"
    )
    originals = (
        owner.verify_recorded_panel_method_input,
        owner._verify_method_replay,
        owner.FoundryMethodOutputConsumer._require_verified_consumption,
        tests._method_owner_case,
    )
    results = []
    for property_name in ("binding", "replay", "emission"):
        out = io.StringIO()
        err = io.StringIO()
        try:
            sys.argv = ["c3_consumer_removal", property_name]
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = c3_consumer_removal.main()
        finally:
            (
                owner.verify_recorded_panel_method_input,
                owner._verify_method_replay,
                owner.FoundryMethodOutputConsumer._require_verified_consumption,
                tests._method_owner_case,
            ) = originals
        print(json.dumps({
            "variant": property_name, "returncode": rc,
            "stdout": out.getvalue(), "stderr": err.getvalue(),
        }), flush=True)
        results.append(rc)
    # A successful removal experiment is expected to retain a failing test status.
    # The complete per-variant identities are read from each unmodified pytest output.
    return 1 if results == [1, 1, 1] else 2


if __name__ == "__main__":
    raise SystemExit(main())
