from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path

import pytest

from polisyos.core import contracts
from polisyos.data_forge.domains.catalog.knowledge.overlay import _artifact_ref_for_payload
from polisyos.data_forge.read_api import catalog
from tests._helpers.semantic_epoch_native import _emit_admitted_ref, _real_epoch_scenario
from tests.unit.runtime.quality.test_acquisition_executor import _test_positive_production_receipt


@pytest.mark.parametrize("copied_live_context", [False, True])
@pytest.mark.parametrize(
    "operation",
    ["initialize", "admit", "activate", "emit_boundary", "native", "denominator", "verify"],
)
def test_actual_native_mutator_waits_for_terminal_admission_fence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    copied_live_context: bool,
) -> None:
    """A deciding reader excludes every maintained native DB mutation owner."""

    scenario = _real_epoch_scenario(tmp_path)
    production = _test_positive_production_receipt(scenario)
    query = scenario.service.acquisition_owner_query(query=scenario.query)
    native = scenario.overlay.resolve_native_membership(query=query, candidate=scenario.candidate)
    denominator = scenario.overlay.resolve_semantic_candidate_denominator(
        query=query, native_membership=native, candidate=scenario.candidate
    )

    def persisted_ref(value, kind: str):
        payload = contracts.epoch.canonical_epoch_bytes(value)
        return _artifact_ref_for_payload(
            payload=len(payload).to_bytes(8, "big") + payload, kind=kind
        )

    native_ref = persisted_ref(native, "epoch.acquisition_native_membership_receipt")
    denominator_ref = persisted_ref(denominator, "epoch.acquisition_semantic_denominator_receipt")
    entered = threading.Event()
    started = threading.Event()
    original_baseline_check = scenario.overlay._require_baseline_unchanged
    deciding_thread = threading.get_ident()

    def actual_writer_validation():
        identity = original_baseline_check()
        if threading.get_ident() != deciding_thread:
            entered.set()
        return identity

    monkeypatch.setattr(scenario.overlay, "_require_baseline_unchanged", actual_writer_validation)
    actions: dict[str, Callable[[], object]] = {
        "initialize": scenario.overlay.initialize,
        "admit": lambda: scenario.overlay.admit_epoch(
            passport=scenario.passport,
            prepared_epoch=scenario.prepared,
            boundary_candidate=scenario.candidate,
            artifact_store=scenario.store,
            authority=scenario.authority,
        ),
        "activate": lambda: scenario.overlay.activate_semantic_epoch(
            pending_receipt=scenario.pending,
            production_receipt=production,
            artifact_store=scenario.store,
        ),
        "emit_boundary": lambda: _emit_admitted_ref(scenario),
        "native": lambda: scenario.overlay.resolve_native_membership(
            query=query, candidate=scenario.candidate
        ),
        "denominator": lambda: scenario.overlay.resolve_semantic_candidate_denominator(
            query=query, native_membership=native, candidate=scenario.candidate
        ),
        "verify": lambda: scenario.overlay.verify_semantic_projection(
            native_membership_ref=native_ref,
            semantic_denominator_ref=denominator_ref,
            prospective_candidate=scenario.candidate,
        ),
    }

    def invoke_actual_mutator():
        started.set()
        return actions[operation]()

    with ThreadPoolExecutor(max_workers=1) as workers:
        with catalog.acquisition_overlay_admission_fence(scenario.overlay.overlay_path):
            copied = copy_context()
            future = workers.submit(
                copied.run if copied_live_context else lambda fn: fn(), invoke_actual_mutator
            )
            assert started.wait(2), "the actual mutator thread did not start"
            assert not entered.wait(0.25), "native writer entered while terminal fence was held"
            assert not future.done(), "native writer completed before terminal fence release"
        result = future.result(timeout=10)
    assert entered.is_set(), "the real native validation did not run after release"
    assert result is not None


def test_fence_is_reentrant_across_native_instances_and_resolves_physical_aliases(
    tmp_path: Path,
) -> None:
    """Nested bridge/native calls share a fence without reacquiring flock."""

    scenario = _real_epoch_scenario(tmp_path)
    alias = tmp_path / "overlay-alias.duckdb"
    alias.symlink_to(scenario.overlay.overlay_path)
    assert catalog.acquisition_overlay_admission_lock_path(alias) == (
        catalog.acquisition_overlay_admission_lock_path(scenario.overlay.overlay_path)
    )
    with (
        catalog.acquisition_overlay_admission_fence(alias),
        catalog.acquisition_overlay_admission_fence(scenario.overlay.overlay_path),
    ):
        assert scenario.overlay.initialize().content_sha256


@pytest.mark.parametrize("overlay_name", ["catalog", "catalog.duckdb", "catalog.native.duckdb"])
@pytest.mark.asyncio
async def test_runtime_async_handoff_runs_outside_the_short_native_fence(
    tmp_path: Path,
    overlay_name: str,
) -> None:
    """Actual Runtime workers acquire their own exclusive native operation."""

    from polisyos.common.async_tools import run_coro_sync
    from polisyos.runtime.quality.acquisition_world_growth import _reentry_operation_namespace

    scenario = _real_epoch_scenario(tmp_path)
    named_selector = tmp_path / overlay_name
    assert catalog.acquisition_overlay_admission_lock_path(
        _reentry_operation_namespace(named_selector)
    ) != catalog.acquisition_overlay_admission_lock_path(named_selector)
    # The actual worker below uses the exact operation namespace for the real
    # native DB, as resume does; this detects namespace collapse behaviorally.
    operation_path = _reentry_operation_namespace(scenario.overlay.overlay_path)
    query = scenario.service.acquisition_owner_query(query=scenario.query)
    parent_thread = threading.get_ident()
    worker_threads = []

    async def actual_native_owner_call():
        worker_threads.append(threading.get_ident())
        return scenario.overlay.resolve_native_membership(query=query, candidate=scenario.candidate)

    with catalog.acquisition_overlay_admission_fence(operation_path):
        try:
            membership = run_coro_sync(actual_native_owner_call(), timeout_seconds=5)
        except TimeoutError:
            pytest.fail("reentry operation namespace blocked the actual native worker")
    assert worker_threads and worker_threads[0] != parent_thread
    assert membership.assessments


def test_stale_copied_operation_cannot_borrow_a_new_fence_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An escaped old context cannot become a member of a later operation."""

    scenario = _real_epoch_scenario(tmp_path)
    with catalog.acquisition_overlay_admission_fence(scenario.overlay.overlay_path):
        stale = copy_context()
    entered = threading.Event()
    started = threading.Event()
    original = scenario.overlay._require_baseline_unchanged
    parent_thread = threading.get_ident()

    def actual_validation():
        result = original()
        if threading.get_ident() != parent_thread:
            entered.set()
        return result

    monkeypatch.setattr(scenario.overlay, "_require_baseline_unchanged", actual_validation)

    def use_stale_context():
        started.set()
        return stale.run(scenario.overlay.initialize)

    with ThreadPoolExecutor(max_workers=1) as workers:
        with catalog.acquisition_overlay_admission_fence(scenario.overlay.overlay_path):
            future = workers.submit(use_stale_context)
            assert started.wait(2)
            assert not entered.wait(0.25), "stale operation entered the new holder's native owner"
            assert not future.done()
        assert future.result(timeout=10).content_sha256
    assert entered.is_set()
