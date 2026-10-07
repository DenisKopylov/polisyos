"""Run workspace gates without the thread caps excluded by this E02 task.

Run from policy-engine with its configured interpreter. This changes only the
operational gate invocation; no repository implementation file is modified.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PRODUCT_ROOT = next(parent for parent in Path(__file__).parents if parent.name == "policy-engine")
sys.path.insert(0, str(PRODUCT_ROOT))

from tools.devx.workspace import ci_parity, verify  # noqa: E402


def main() -> int:
    """Preserve the declared gate steps while leaving numerical threads uncapped."""
    parser = argparse.ArgumentParser()
    parser.add_argument("gate", choices=("verify", "ci-parity"))
    args, gate_args = parser.parse_known_args()
    verify.PYTEST_NUMERICAL_ENV = {}
    if args.gate == "verify":
        return verify.main(gate_args)

    original_run = ci_parity.run_command

    def run_without_nested_caps(spec: ci_parity.CommandSpec) -> None:
        argv = list(spec.argv)
        if "tools.devx.workspace.verify" in argv:
            nested_args = argv[argv.index("tools.devx.workspace.verify") + 1 :]
            result = verify.main(nested_args)
            if result:
                raise subprocess.CalledProcessError(result, argv)
            return
        original_run(spec)

    ci_parity.run_command = run_without_nested_caps
    return ci_parity.main(gate_args)


if __name__ == "__main__":
    raise SystemExit(main())
