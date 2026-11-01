"""Real process-entry unknown errors remain terminal at both retry consumers.

This is the native worker/channel/error boundary, not Darwin's closed builtin
timeout-node admission or Linux process-tree qualification. SQLite rows observe
physical entries; they do not represent billed or atomic external effects.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import os
from pathlib import Path

import pytest

from polisyos.core import run as core_run
from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import RetryExhaustedError
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.retry import (
    RetryPolicy,
    execute_with_retry_async,
    execute_with_retry_sync,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from tests._helpers.process_unknown_failure import (
    FailureKind,
    ProcessErrorBridge,
    create_entry_database,
    read_entries,
)


def _invoke(
    mode: str,
    node: ProcessErrorBridge,
    context: ExecutionContext,
    state: ExperimentState,
    policy: RetryPolicy,
) -> NodeOutcome:
    if mode == "sync":
        return execute_with_retry_sync(
            node, context, state, retry_policy=policy, timeout_s=None, alias="ipc_boundary"
        )
    return asyncio.run(
        execute_with_retry_async(
            node, context, state, retry_policy=policy, timeout_s=None, alias="ipc_boundary"
        )
    )


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    "kind,remove_encoder_guard,expected_entries",
    [
        ("known_transient", False, 3),
        ("wrapped_unknown", False, 1),
        ("wrapped_unknown", True, 3),
        ("grouped_unknown", False, 1),
        ("forwarded_unknown", False, 1),
    ],
    ids=[
        "known-retry-positive",
        "unknown-terminal",
        "encoder-removal",
        "grouped-unknown",
        "forwarded-unknown",
    ],
)
def test_process_unknown_cause_survives_real_channel_and_retry(
    tmp_path: Path,
    mode: str,
    kind: FailureKind,
    remove_encoder_guard: bool,
    expected_entries: int,
) -> None:
    """Physical entries and actual decoded locators distinguish unknown from transient."""
    database_path = tmp_path / "entries.sqlite"
    create_entry_database(database_path)
    store = FileSystemCAS(tmp_path / "parent-cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    run_id = f"R_process_unknown_{mode}"
    run = core_run.RunContext.start(store, registry.bundle_ref, run_id=run_id)
    context = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    state = ExperimentState(run_id=run_id)
    node = ProcessErrorBridge(
        tmp_path / "children", database_path, kind, remove_encoder_guard=remove_encoder_guard
    )
    policy = RetryPolicy(
        max_retries=2,
        backoff_base_s=0.1,
        jitter="none",
        retry_on=["fixture.transient", "node.exception", "node.worker_outcome_unknown"],
    )
    children_before = {process.pid for process in mp.active_children()}
    try:
        with pytest.raises(RetryExhaustedError) as caught:
            _invoke(mode, node, context, state, policy)

        entries = read_entries(database_path)
        assert len(entries) == expected_entries, (node.payloads, str(caught.value.__cause__))
        assert len(node.payloads) == len(node.decoded) == len(node.child_pids) == expected_entries
        assert {entry[0] for entry in entries} == set(node.child_pids)
        assert all(entry[0] != os.getpid() for entry in entries)
        assert all(entry[1] == run_id and entry[3] == kind for entry in entries)
        assert "failed_worker_write" not in state.params
        for index, (payload, decoded) in enumerate(zip(node.payloads, node.decoded, strict=True)):
            if kind != "known_transient" and not remove_encoder_guard:
                assert payload["code"] == "node.worker_outcome_unknown"
                assert payload["category"] == "fatal"
                locators = decoded.child_unknowns
                assert len(locators) == 1
                assert isinstance(locators[0], core_run.ChildOutcomeUnknownError)
                assert locators[0].run_id == entries[index][1]
                assert str(locators[0].run_dir) == entries[index][2]
                assert locators[0].run_dir.is_dir()
            else:
                assert payload["code"] == "fixture.transient"
                assert payload["category"] == "transient"
                assert decoded.child_unknowns == ()
        assert not ({process.pid for process in mp.active_children()} - children_before)
    finally:
        run.suspend_for_resume()
