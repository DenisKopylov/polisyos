"""Repeat the async trace-recovery discriminator against base and removal control.

Run from the product directory with its source on PYTHONPATH. This is an evidence
harness for the native integration oracle, not an alternative cache consumer.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutionResult
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

BASE = "c40d4acae1ce58b597267255026d9356565828fd"
PRODUCT = Path.cwd()
SOURCE = "policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py"
TEST = PRODUCT / "tests/integration/scientist/test_execution_state_replay.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git(*args: str) -> bytes:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("Git is required to resolve the immutable base")
    # Both callers supply fixed read-only repository commands, never user input.
    return subprocess.check_output([executable, *args])  # noqa: S603


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not resolve the native evidence module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def exercise(mode: str, root: Path) -> None:
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.idempotency import NodeCacheEntry

    test = load_module(f"e02_recovery_oracle_{mode}", TEST)
    observed_nodes = []
    observed_contexts = []
    observed_results = []
    original_node = test._StateOperationsNode
    original_context = test._context
    original_emit = RunContext.emit

    class ObservedNode(original_node):
        def __init__(self) -> None:
            super().__init__()
            observed_nodes.append(self)

    def observed_context(root: Path, run_id: str) -> ExecutionContext:
        context = original_context(root, run_id)
        observed_contexts.append(context)
        return context

    executor_class = test.AsyncWorkflowExecutor
    if mode == "base":
        source = git("show", f"{BASE}:{SOURCE}")
        base_path = root / "base_async_executor.py"
        base_path.write_bytes(source)
        module = load_module(
            "polisyos.scientist.orchestration.engine._e02_base_async_executor", base_path
        )
        executor_class = module.AsyncWorkflowExecutor
    else:

        def emit_without_cache_admission(
            self: RunContext, phase: str, event: str, **kwargs: object
        ) -> None:
            if event != "NODE_CACHE_STORE":
                return original_emit(self, phase, event, **kwargs)
            return None

        RunContext.emit = emit_without_cache_admission

    class ObservedExecutor(executor_class):
        async def execute(
            self, workflow: WorkflowSpec, state: ExperimentState
        ) -> WorkflowExecutionResult:
            result = await super().execute(workflow, state)
            observed_results.append(result)
            return result

    test._StateOperationsNode = ObservedNode
    test._context = observed_context
    test.AsyncWorkflowExecutor = ObservedExecutor
    try:
        try:
            test.test_reopened_cache_matches_cold_assign_delete_and_unrelated_state(root, "async")
        except AssertionError:
            traceback.print_exc(file=sys.stdout)
        else:
            raise AssertionError("the same native positive oracle unexpectedly passed")
        require(len(observed_nodes) == 1, "expected one actual node instance")
        require(observed_nodes[0].calls == 2, "recovery must rerun the unindexed producer")
        require(len(observed_results) == 2, "expected native initial and reopened results")
        require(all(result.report.status == "ok" for result in observed_results), "native ok lost")
        test._assert_operations(observed_results[1].state)
        context = observed_contexts[1]
        entries = [
            NodeCacheEntry.model_validate(
                from_canonical_bytes(context.store.get_bytes(artifact_id))
            )
            for artifact_id in context.store.iter_artifact_ids()
            if context.store.get_manifest(artifact_id).kind == "scientist.node_cache_entry"
        ]
        require(bool(entries), "actual persisted cache artifacts missing")
        require(
            all(entry.state_mutations and entry.journal_proof for entry in entries),
            "native mutation journal proof was removed with the event",
        )
        events = [
            json.loads(line)["event"] for line in context.run.trace_path.read_text().splitlines()
        ]
        require("NODE_OK" in events, "native success event missing")
        require("NODE_CACHE_STORE" not in events, "recovery event unexpectedly present")
        sys.stdout.write(
            json.dumps(
                {
                    "mode": mode,
                    "expected_oracle_failure": "producer reran after reopening (2 != 1)",
                    "persisted_entries_with_journal_proof": len(entries),
                    "native_ok": True,
                    "replay_semantic_state": dict(observed_results[1].state.params),
                },
                sort_keys=True,
            )
            + "\n"
        )
    finally:
        RunContext.emit = original_emit


if __name__ == "__main__":
    sys.stdout.write(
        json.dumps(
            {
                "candidate_sha": git("rev-parse", "HEAD").decode().strip(),
                "base_defining_module_sha": BASE,
                "dependency_identity": (
                    "other production defining modules unchanged between base and candidate"
                ),
                "test_oracle": str(TEST),
                "cwd": str(PRODUCT),
            }
        )
        + "\n"
    )
    with tempfile.TemporaryDirectory(prefix="e02-recovery-controls-") as temporary:
        for mode in ("base", "removed_event"):
            root = Path(temporary) / mode
            root.mkdir()
            exercise(mode, root)
