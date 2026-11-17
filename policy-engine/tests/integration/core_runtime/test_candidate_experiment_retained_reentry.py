"""Opt-in historical reentry over paid, retained candidate experiment outputs.

This uses the maintained retained-runtime composition, including a new demo IdP
and ordinary SQLite schema/WAL bookkeeping. Canonical CAS bootstrap calls must
be idempotent: no added member or changed owner generation is allowed. The reader
then refuses CAS writes, never resumes the failed job or supplies a current grant,
and preserves every old SQL row, selected input and physical-ledger byte.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any

import pytest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sql_rows(database: Path) -> dict[str, tuple[int, str]]:
    """Fingerprint every row of every existing table without retaining payloads."""
    result = {}
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for (name,) in tables:
            quoted = '"' + name.replace('"', '""') + '"'
            rows = connection.execute("SELECT * FROM " + quoted).fetchall()  # noqa: S608 -- quoted sqlite_master identifier, never a value expression.
            row_hashes = sorted(
                hashlib.sha256(
                    json.dumps(
                        [
                            {"sqlite_blob_hex": value.hex()} if isinstance(value, bytes) else value
                            for value in row
                        ],
                        ensure_ascii=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
                for row in rows
            )
            result[name] = (
                len(rows),
                hashlib.sha256("\n".join(row_hashes).encode()).hexdigest(),
            )
    return result


def _selected_paths(cas: Path, selector: dict[str, Any]) -> tuple[Path, Path]:
    digest = selector["artifact_id"].removeprefix("sha256:")
    profile = selector["manifest_profile_sha256"].removeprefix("sha256:")
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert re.fullmatch(r"[0-9a-f]{64}", profile)
    directory = cas / "artifacts/sha256" / digest[:2] / digest[2:4]
    return (
        directory / (digest + ".blob"),
        directory / (digest + ".view." + profile + ".manifest.json"),
    )


def _selected_input_pins(cas: Path, commission: dict[str, Any]) -> dict[Path, str]:
    """Pin selected records plus their complete direct manifest-input denominator."""
    selected = [
        commission[name]
        for name in (
            "policy_ref",
            "candidate_action_ref",
            "checkpoint_ref",
            "reentry_ref",
            "n5_execution_ref",
            "n5_result_ref",
        )
    ]
    parents = []
    for selector in selected:
        _blob, manifest = _selected_paths(cas, selector)
        for edge in json.loads(manifest.read_bytes())["inputs"]:
            parents.append(edge.get("ref", edge))
    return {
        path: _sha256(path)
        for selector in [*selected, *parents]
        for path in _selected_paths(cas, selector)
    }


def _artifact_members(cas: Path) -> set[str]:
    """Census artifact member names, including ownership and transaction metadata."""
    root = cas / "artifacts"
    assert root.is_dir() and not root.is_symlink()
    members = set()

    def refuse_incomplete_census(error: OSError) -> None:
        raise error

    for directory, directories, files in os.walk(
        root, followlinks=False, onerror=refuse_incomplete_census
    ):
        for name in [*directories, *files]:
            path = Path(directory) / name
            assert not path.is_symlink()
            members.add(path.relative_to(root).as_posix())
    return members


def _owner_metadata_pins(cas: Path) -> dict[str, str]:
    """Pin the actual current owner pointer and selected immutable generation."""
    root = cas / "artifacts/ownership"
    pointer = root / "index.json"
    value = json.loads(pointer.read_bytes())
    paths = [pointer]
    if value["schema_version"] == "policyos.artifact_ownership_index_pointer.v1":
        generation = value["generation_sha256"]
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", generation)
        selected = root / "generations" / (generation.removeprefix("sha256:") + ".json")
        assert "sha256:" + _sha256(selected) == generation
        paths.append(selected)
    else:
        # A legacy index has a detached signature rather than a generation pointer.
        paths.append(root / "index.signature.json")
    return {path.relative_to(root).as_posix(): _sha256(path) for path in paths}


@pytest.fixture
def retained_reentry_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Recompose retained owners, allowing no new work or changed old facts."""
    commission_path = os.environ.get("POLISYOS_TEST_RETAINED_CANDIDATE_COMMISSION")
    if not commission_path:
        pytest.skip("explicit retained candidate commission was not supplied")
    # Both paired processes load/resolve the same plugin targets before this cut.
    # OFF disables only the observer's own events, preserving equal import setup.
    timing_mode = os.environ.get("POLISYOS_TEST_RETAINED_TIMING_MODE")
    if timing_mode is not None:
        from tests._helpers import candidate_reentry_timing as timing

        assert timing_mode in {"off", "on"}
        observer = timing._observer
        assert observer is not None and observer.status == "active"
        assert observer.profile == "generic_model_input_owner"
        assert observer.snapshot()["target_resolution"] == "complete"
        assert sys.monitoring.get_tool(4) == "e02-candidate-reentry-timing"
        if timing_mode == "off":
            observer.cleanup()
            observer.flush()
            assert observer.cleanup_status == "complete"
            assert sys.monitoring.get_events(4) == 0
            assert sys.monitoring.get_tool(4) is None
            assert all(
                sys.monitoring.get_local_events(4, code) == 0 for code in observer.codes.values()
            )
        else:
            assert sys.monitoring.get_events(4) == sys.monitoring.events.PY_UNWIND
        record_property("retained_timing_mode", timing_mode)
        record_property("retained_timing_target_count", len(observer.codes))
    commission = json.loads(Path(commission_path).resolve(strict=True).read_bytes())
    fixture = Path(commission["retained_case_root"]).resolve(strict=True)
    database = fixture / ".polisyos/control_plane.sqlite3"
    cas = fixture / "cas"
    ledger = cas / "runs/.runtime/llm-cost-ledger.json"
    sql_before = _sql_rows(database)
    ledger_before = ledger.read_bytes()
    assert hashlib.sha256(ledger_before).hexdigest() == commission["ledger_sha256"]
    selected_before = _selected_input_pins(cas, commission)
    members_before = _artifact_members(cas)
    owner_before = _owner_metadata_pins(cas)

    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.llm.traced_client import TracedLLMClient
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.http.services.control_worker import ControlWorker
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope
    from polisyos.scientist.orchestration.engine import BudgetMiddleware
    from tests._helpers.candidate_experiment_retained_recovery import retained_candidate_runtime

    unexpected_effects: list[str] = []
    bootstrap_open = True
    bootstrap_cas_calls: dict[str, int] = {}

    def refuse_effect(*_args: Any, **_kwargs: Any) -> Any:
        unexpected_effects.append("unexpected_candidate_reentry_effect")
        raise AssertionError("historical_reentry_attempted_new_work_or_write")

    # Normal setup may request idempotent publication of existing verifier
    # provenance. Delegate to the original owner only during bootstrap, then
    # require complete member-name and owner-generation equality before reads.
    # No work, action, lease, provider or budget write is allowed in either phase.
    for owner, methods in (
        (JointSimulationHorizonController, ("run",)),
        (ControlWorker, ("start", "dispatch_once")),
        (TracedLLMClient, ("invoke", "ainvoke", "generate")),
        (WorldBankWDIAcquisitionExecutionPort, ("execute", "execute_candidate_experiment")),
        (BudgetMiddleware, ("reserve_safe", "reserve_invocation_safe", "record_spend_safe")),
        (
            ControlPlaneStore,
            ("lease_next_job", "mark_running", "append_event", "append_diagnostic_event"),
        ),
    ):
        for method in methods:
            monkeypatch.setattr(owner, method, refuse_effect)

    def bootstrap_writer(original: Callable[..., Any], method: str) -> Callable[..., Any]:
        @wraps(original)
        def invoke(*args: Any, **kwargs: Any) -> Any:
            if not bootstrap_open:
                return refuse_effect(*args, **kwargs)
            bootstrap_cas_calls[method] = bootstrap_cas_calls.get(method, 0) + 1
            return original(*args, **kwargs)

        return invoke

    for method in ("put_bytes", "put_json", "record_artifact_owner"):
        original = getattr(FileSystemCAS, method)
        monkeypatch.setattr(FileSystemCAS, method, bootstrap_writer(original, method))

    def assert_old_facts_unchanged(phase: str) -> None:
        members_after = _artifact_members(cas)
        owner_after = _owner_metadata_pins(cas)
        checks = {
            "artifact_members_unchanged": members_after == members_before,
            "owner_metadata_unchanged": owner_after == owner_before,
            "ledger_bytes_unchanged": ledger.read_bytes() == ledger_before,
            "all_sql_rows_unchanged": _sql_rows(database) == sql_before,
            "selected_facts_unchanged": (
                {path: _sha256(path) for path in selected_before} == selected_before
            ),
        }
        observation = {
            "phase": phase,
            "bootstrap_cas_calls": bootstrap_cas_calls,
            "artifact_member_count_before": len(members_before),
            "artifact_member_count_after": len(members_after),
            "added_artifact_members": sorted(members_after - members_before),
            "removed_artifact_members": sorted(members_before - members_after),
            "owner_metadata_before": owner_before,
            "owner_metadata_after": owner_after,
            "checks": checks,
        }
        compact = json.dumps(observation, sort_keys=True, separators=(",", ":"))
        record_property("retained_preservation_" + phase, compact)
        print(compact, flush=True)  # noqa: T201 -- complete compact bootstrap/preservation result.
        assert all(checks.values()), "retained_candidate_old_facts_changed"

    # Original R4's maintained run_genuine_candidate_experiment_scenario sets
    # this exact value; the production default remains 1.5 seconds.
    assert commission["cas_guard_timeout_seconds"] == 3.0
    record_property(
        "cas_guard_profile_basis",
        "retained R4 run_genuine_candidate_experiment_scenario: CAS=3s; production default unchanged",
    )
    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "3")
    try:
        with retained_candidate_runtime(
            fixture_root=fixture,
            job_id=commission["action_job_id"],
            output_root=tmp_path / "retained-runtime",
            monkeypatch=monkeypatch,
        ) as runtime:
            bootstrap_open = False
            assert_old_facts_unchanged("bootstrap")
            control = runtime["control"]
            assert control._worker is None
            store = control._artifact_store
            guard = getattr(store, "_guard", None)
            assert guard is not None
            assert guard._timeout_seconds == commission["cas_guard_timeout_seconds"]
            with (
                tenant_scope(
                    None, tenant_id=commission["tenant_id"], cell_id=commission["cell_id"]
                ),
                catalog_serving_source_scope(control.catalog_serving_source),
            ):
                job = control._control_store.get_job(commission["action_job_id"])
                assert job.state == commission["expected_original_job_state"]
                assert job.attempt == commission["expected_original_attempt"]
                assert job.lease_owner is None and job.lease_expires_at is None
                yield commission, runtime
    finally:
        bootstrap_open = False
        assert_old_facts_unchanged("final")
        assert not unexpected_effects


def test_paid_candidate_reentry_reopens_historically_without_new_work(
    retained_reentry_runtime: tuple[dict[str, Any], dict[str, Any]],
    record_property: Callable[[str, object], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reopen the actual completed reentry while preserving the failed history."""
    from polisyos.core.artifacts import ArtifactOwnershipError, ArtifactRef
    from polisyos.runtime.quality import generation_cycle as generation_cycle_module
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoop
    from polisyos.runtime.quality.candidate_source_reentry_history import (
        verify_candidate_experiment_source_reentry_history,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from tests._helpers.candidate_experiment_served_execution import (
        _build_candidate_experiment_world_growth_bridge,
    )

    commission, runtime = retained_reentry_runtime
    observed_cut = datetime.now(UTC)
    assert runtime["authority_valid_until"] < observed_cut
    record_property(
        "retained_historical_authority_cut",
        json.dumps(
            {
                "original_authority_valid_until": runtime["authority_valid_until"].isoformat(),
                "observed_cut": observed_cut.isoformat(),
                "original_authority_expired": True,
            },
            sort_keys=True,
        ),
    )
    control = runtime["control"]
    store = control._artifact_store
    loop = AcquisitionRouteLoop(
        control_store=control._control_store,
        artifact_store=store,
        event_log=control._diagnostic_event_log,
        core_source_resolver=control.resolve_completed_control_job_core_run_source,
        tenant_id=commission["tenant_id"],
        cell_id=commission["cell_id"],
        action_outcome_reader=control.acquisition_route_sink,
    )
    origin = loop.resolve_candidate_experiment_predecessor_origin(
        run_id=commission["run_id"],
        predecessor_terminal_ref=None,
        expected_action_generation=commission["action_generation"],
        historical_policy_ref=ArtifactRef.model_validate(commission["policy_ref"]),
        historical_action_job_id=commission["action_job_id"],
    )
    bridge = _build_candidate_experiment_world_growth_bridge(
        control_service=control, authority=runtime["policy_owner"].issuer.authority
    )

    def selected_key(ref: ArtifactRef) -> tuple[str, str | None]:
        return str(ref.artifact_id), ref.manifest_profile_sha256

    v5_record_reads: list[tuple[tuple[str, str | None], str | None]] = []
    public_v5_resolutions: list[tuple[str, str | None]] = []
    joint_result_reads: list[tuple[str, str | None]] = []
    paired_v5_resolutions: list[tuple[tuple[str, str | None], ...]] = []
    original_pair_resolver = (
        GenerationSourceRepository._resolve_selected_candidate_simulation_v5_pair
    )
    original_record_reader = GenerationSourceRepository._read_candidate_simulation_v5_record
    original_v5_resolver = GenerationSourceRepository.resolve_candidate_simulation_v5
    original_result_reader = generation_cycle_module.load_joint_simulation_result

    def count_v5_record_read(
        repository: GenerationSourceRepository, **kwargs: Any
    ) -> Any:
        v5_record_reads.append(
            (selected_key(kwargs["ref"]), kwargs.get("expected_job_id"))
        )
        return original_record_reader(repository, **kwargs)

    def count_public_v5_resolution(
        repository: GenerationSourceRepository, **kwargs: Any
    ) -> Any:
        public_v5_resolutions.append(selected_key(kwargs["ref"]))
        return original_v5_resolver(repository, **kwargs)

    def count_pair_resolution(
        repository: GenerationSourceRepository, **kwargs: Any
    ) -> Any:
        paired_v5_resolutions.append(
            tuple(
                selected_key(kwargs[name])
                for name in ("source_ref", "input_ref", "execution_ref")
            )
        )
        return original_pair_resolver(repository, **kwargs)

    def count_joint_result_read(ref: ArtifactRef, **kwargs: Any) -> Any:
        joint_result_reads.append(selected_key(ref))
        return original_result_reader(ref, **kwargs)

    monkeypatch.setattr(
        GenerationSourceRepository,
        "_read_candidate_simulation_v5_record",
        count_v5_record_read,
    )
    monkeypatch.setattr(
        GenerationSourceRepository,
        "resolve_candidate_simulation_v5",
        count_public_v5_resolution,
    )
    monkeypatch.setattr(
        GenerationSourceRepository,
        "_resolve_selected_candidate_simulation_v5_pair",
        count_pair_resolution,
    )
    monkeypatch.setattr(
        generation_cycle_module,
        "load_joint_simulation_result",
        count_joint_result_read,
    )
    receipt = verify_candidate_experiment_source_reentry_history(
        bridge=bridge,
        origin=origin,
        receipt_ref=ArtifactRef.model_validate(commission["reentry_ref"]),
        expected_selected_action_ref=ArtifactRef.model_validate(commission["candidate_action_ref"]),
    )
    assert receipt.run_id == commission["run_id"]
    assert receipt.action_job_id == commission["action_job_id"]
    assert receipt.source_job_id == commission["source_job_id"]
    assert receipt.action_generation == commission["action_generation"]
    assert receipt.authority_purpose == "candidate_simulation"
    assert receipt.observed_admission is receipt.publication_authority is False
    assert receipt.limitations
    assert receipt.source_run_currentness.status == "not_established"
    assert receipt.continuation_currentness.status == "not_established"
    assert receipt.n5_execution_ref == ArtifactRef.model_validate(commission["n5_execution_ref"])
    assert receipt.n5_result_ref == ArtifactRef.model_validate(commission["n5_result_ref"])
    assert receipt.n4_source_ref is not None
    assert receipt.n5_input_ref is not None
    assert all(
        ref.manifest_profile_sha256 is not None
        for ref in (
            receipt.n4_source_ref,
            receipt.n5_input_ref,
            receipt.n5_execution_ref,
            receipt.n5_result_ref,
        )
    )
    input_key = selected_key(receipt.n5_input_ref)
    execution_key = selected_key(receipt.n5_execution_ref)
    result_key = selected_key(receipt.n5_result_ref)
    assert [entry for entry in v5_record_reads if entry[0] == input_key] == [
        (input_key, receipt.action_job_id)
    ]
    assert [entry for entry in v5_record_reads if entry[0] == execution_key] == [
        (execution_key, receipt.action_job_id)
    ]
    assert not any(ref in {input_key, execution_key} for ref in public_v5_resolutions)
    assert [ref for ref in joint_result_reads if ref == result_key] == [result_key]
    assert paired_v5_resolutions == [
        (
            selected_key(receipt.n4_source_ref),
            input_key,
            execution_key,
        )
    ]
    record_property(
        "retained_v5_history_selected_reads",
        json.dumps(
            {
                "input_record_reads": 1,
                "execution_record_reads": 1,
                "result_reads": 1,
                "individual_v5_resolutions": 0,
                "paired_resolutions": len(paired_v5_resolutions),
                "expected_job_id": receipt.action_job_id,
            },
            sort_keys=True,
        ),
    )
    assert len(receipt.continued_generation_run.cycles) == commission["expected_continued_cycles"]
    assert receipt.new_cycle.simulation.status == "joint_simulated"
    # A warm historical reader must still honor the exact selected
    # profile; it cannot fall back to this blob's default manifest.
    unavailable_profile = ArtifactRef.model_validate(commission["reentry_ref"])
    unavailable_profile = unavailable_profile.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "0" * 64}
    )
    with pytest.raises(ArtifactOwnershipError, match="verify_manifest"):
        verify_candidate_experiment_source_reentry_history(
            bridge=bridge,
            origin=origin,
            receipt_ref=unavailable_profile,
            expected_selected_action_ref=ArtifactRef.model_validate(
                commission["candidate_action_ref"]
            ),
        )
    snapshot = control._llm_producer_settlement_store.snapshot_safe()
    profile = snapshot.invocation_profiles[commission["run_id"]]
    assert (profile.total_units, profile.protected_units) == (7, 1)
    rows = [
        row
        for row in snapshot.invocation_reservations.values()
        if row.run_id == commission["run_id"] and row.profile_digest == profile.profile_digest
    ]
    assert (
        sum(row.units for row in rows if row.status == "completed")
        == commission["expected_completed_standard_units"]
    )
    assert (
        sum(row.units for row in rows if row.status == "reserved")
        == commission["expected_pending_units"]
    )
    assert all(row.purpose == "standard" for row in rows)
    record_property("historical_reentry_ref", str(commission["reentry_ref"]))
    record_property("new_n5_calls", 0)


def test_retained_selected_policy_inventory_uses_complete_profiles(
    retained_reentry_runtime: tuple[dict[str, Any], dict[str, Any]],
    record_property: Callable[[str, object], None],
) -> None:
    """Measure the canonical scoped policy selector without source/N6 replay."""
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.http.resilience import _BlockingDependencyWaitTimeoutError
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        POLICY_EVENT,
        POLICY_PRODUCER,
        list_current_candidate_unpriced_policy_bindings,
    )

    commission, runtime = retained_reentry_runtime
    control = runtime["control"]
    expected = ArtifactRef.model_validate(commission["policy_ref"])
    scope = runtime["policy"].scope
    assert (scope.tenant_id, scope.cell_id, scope.run_id, scope.source_job_id) == (
        commission["tenant_id"],
        commission["cell_id"],
        commission["run_id"],
        commission["source_job_id"],
    )
    events = control._diagnostic_event_log.list_events(
        run_id=scope.run_id, job_id=scope.source_job_id, limit=500
    )
    assert len(events) < 500
    selected_events = [
        row.event
        for row in events
        if row.event.event_type == POLICY_EVENT
        and row.event.payload_ref == str(expected.artifact_id)
    ]
    assert len(selected_events) == 1
    event = selected_events[0]
    assert event.event_source == event.producer_component == POLICY_PRODUCER
    assert (event.tenant_id, event.cell_id, event.run_id, event.job_id) == (
        scope.tenant_id,
        scope.cell_id,
        scope.run_id,
        scope.source_job_id,
    )
    assert event.event_subject == f"run/{scope.run_id}/candidate/{scope.candidate_id}"
    for index in range(3):
        observation: dict[str, Any] = {
            "call_index": index + 1,
            "cas_guard_timeout_seconds": commission["cas_guard_timeout_seconds"],
            "timing_output_configured": bool(os.environ.get("E02_REENTRY_TIMING_OUTPUT")),
            "timing_mode": os.environ.get("POLISYOS_TEST_RETAINED_TIMING_MODE"),
            "timing_global_events": sys.monitoring.get_events(4),
            "scoped_event_count": len(events),
            "selected_policy_event_id": event.event_id,
            "selected_policy_payload_id": event.payload_ref,
            "inventory_entry_count": "not_established_no_port_instrumentation",
        }
        start = time.perf_counter()
        try:
            bindings = list_current_candidate_unpriced_policy_bindings(
                control_service=control,
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
                run_id=scope.run_id,
                source_job_id=scope.source_job_id,
                candidate_id=scope.candidate_id,
            )
        except _BlockingDependencyWaitTimeoutError as error:
            observation.update(
                classification="ERROR",
                elapsed_seconds=time.perf_counter() - start,
                exception_type=type(error).__module__ + "." + type(error).__qualname__,
                error_code=error.code,
                wait_diagnostic=_BlockingDependencyWaitTimeoutError.diagnostic(error),
            )
            compact = json.dumps(observation, sort_keys=True, separators=(",", ":"))
            record_property("retained_policy_inventory_call_" + str(index + 1), compact)
            print(compact, flush=True)  # noqa: T201 -- compact deciding wait evidence.
            raise
        observation["elapsed_seconds"] = time.perf_counter() - start
        assert expected in tuple(binding.policy_ref for binding in bindings)
        assert all(
            (
                binding.scope.tenant_id,
                binding.scope.cell_id,
                binding.scope.run_id,
                binding.scope.source_job_id,
                binding.scope.candidate_id,
            )
            == (
                scope.tenant_id,
                scope.cell_id,
                scope.run_id,
                scope.source_job_id,
                scope.candidate_id,
            )
            for binding in bindings
        )
        observation.update(
            classification="PASS",
            selected_binding_count=len(bindings),
            selected_profiles=[binding.policy_ref.model_dump(mode="json") for binding in bindings],
        )
        compact = json.dumps(observation, sort_keys=True, separators=(",", ":"))
        record_property("retained_policy_inventory_call_" + str(index + 1), compact)
        print(compact, flush=True)  # noqa: T201 -- compact deciding inventory evidence.
