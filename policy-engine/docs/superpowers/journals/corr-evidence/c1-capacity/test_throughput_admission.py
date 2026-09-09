"""Synthetic source/verdict mutations exercise the actual throughput admission."""

from __future__ import annotations

import asyncio
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."


class ThroughputAdmissionTests(unittest.TestCase):
    def test_actual_changed_source_and_changed_verdict_are_refused(self) -> None:
        owner = importlib.import_module(PREFIX + "throughput_admission")
        scratch = Path.cwd() / ".tmp"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="throughput-admission-", dir=scratch) as temporary:
            root = Path(temporary)
            for name in (*owner.ADDITIONAL_PATHS, "synthetic-owner.py"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('# {"synthetic": true}\npass\n')
            verdict = root / "verdict.json"
            verdict.write_text(json.dumps({"synthetic": True, "contract_satisfied": True}))
            with patch.object(owner, "_inherited_paths", return_value=("synthetic-owner.py",)):
                plan = {
                    "synthetic": True,
                    "contract_verdict_path": "verdict.json",
                    "contract_verdict_sha256": owner.bytes_digest(verdict.read_bytes()),
                    "execution_source_projection": owner.execution_projection(root),
                }
                owner.require_admitted_execution(plan, root)
                source = root / "synthetic-owner.py"
                original = source.read_bytes()
                source.write_bytes(original + b"# actual mechanism changed\n")
                runner = importlib.import_module(PREFIX + "throughput_runner")
                with (
                    patch.object(runner, "_committed", return_value=plan),
                    patch.object(
                        runner.Path,
                        "cwd",
                        return_value=root,
                    ),
                ):
                    try:
                        asyncio.run(runner._live_worker(Path("declared.json"), 0, root / "output"))
                    except ValueError as exc:
                        if str(exc) != "throughput_execution_source_changed":
                            raise AssertionError(
                                "worker admission refused for wrong reason"
                            ) from exc
                    else:
                        raise AssertionError("real worker entered with changed execution source")
                try:
                    owner.require_admitted_execution(plan, root)
                except ValueError as exc:
                    if str(exc) != "throughput_execution_source_changed":
                        raise AssertionError("source refused for wrong reason") from exc
                else:
                    raise AssertionError("changed actual execution source was admitted")
                source.write_bytes(original)
                # Even a byte-only verdict correction needs a new content-bound declaration.
                verdict.write_bytes(verdict.read_bytes() + b"\n")
                try:
                    owner.require_admitted_execution(plan, root)
                except ValueError as exc:
                    if str(exc) != "throughput_contract_verdict_changed":
                        raise AssertionError("verdict refused for wrong reason") from exc
                else:
                    raise AssertionError("changed successful verdict bytes were admitted")


if __name__ == "__main__":
    unittest.main(verbosity=2)
