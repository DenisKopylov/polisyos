"""Tests for polisyos.scientist.orchestration.engine.retry — RetryPolicy + wrappers."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import multiprocessing as mp
import os
import signal
import subprocess
import sys
import threading
import time as _time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import BoundedLivenessConfig
from polisyos.core.run.context import RunContext
from polisyos.core.run.manifest import RunManifest
from polisyos.scientist.orchestration.engine import retry as retry_module
from polisyos.scientist.orchestration.engine.context import ClaimCapableExecutionContext
from polisyos.scientist.orchestration.engine.errors import NodeTimeoutError, RetryExhaustedError
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.orchestration.engine.retry import (
    RetryPolicy,
    _backoff_delay,
    _node_execute_worker,
    _should_retry,
    execute_with_retry_async,
    execute_with_retry_sync,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def state():
    return ExperimentState(run_id="test-run")


@pytest.fixture
def ctx():
    c = MagicMock()
    c.run = MagicMock()
    c.run.emit = MagicMock()
    return c


def _ok_outcome(state):
    return NodeOutcome(status="ok", state=state, events=[], artifacts=[])


def _fail_outcome(state, code="node.exception"):
    return NodeOutcome(
        status="fail",
        state=state,
        events=[],
        artifacts=[],
        error=NodeError(code=code, message="fail"),
    )


def _select_timeout_test_route(monkeypatch, route: str) -> None:
    """Select a route that this platform actually admits for the tested input."""
    if route.endswith("-fork"):
        if retry_module._timeout_worker_start_method() != "fork":
            pytest.skip("native Linux fork timeout worker required")
        return
    if route == "thread" or route.endswith("-thread"):
        if sys.platform == "darwin":
            pytest.skip("Darwin timed execution admits canonical spawn nodes, not thread fallback")
        monkeypatch.setattr(retry_module, "_timeout_worker_start_method", lambda: None)


class _ControlledThreadDeadline:
    """Control one timeout test's worker-start and deadline phases."""

    def __init__(self, monkeypatch):
        self._monkeypatch = monkeypatch
        self.current = 0.0
        self.deadline = None
        self.expired_deadline = None
        self.future = None
        self.completed = None
        self.worker_completed_at = None
        self.started_observed = False
        self.sleep_calls = []
        self.backoff_requests = []
        self._submission_count = 0

    def monotonic(self):
        return self.current

    def sleep(self, delay):
        self.sleep_calls.append(delay)
        self.current += delay
        if self.deadline is not None and self.current >= self.deadline:
            self.expired_deadline = self.deadline

    def observe_first_attempt(
        self, started, *, expire_after_start=False, wait_for_completion=False
    ):
        """Install one real worker-start barrier and a controlled retry clock."""
        self._monkeypatch.setattr(retry_module, "time", self)
        submit = retry_module._submit_thread_attempt

        def submit_and_observe(*args, **kwargs):
            result = submit(*args, **kwargs)
            self._submission_count += 1
            if self._submission_count != 1:
                return result
            self.future = result[0]
            self.completed = result[2]
            self.deadline = args[3] if len(args) > 3 else kwargs["deadline"]
            assert started.wait(timeout=2.0), "timeout worker did not pass its start barrier"
            self.started_observed = True
            if expire_after_start:
                self.current = self.deadline
                self.expired_deadline = self.deadline
            if wait_for_completion:
                self.future.result(timeout=2.0)
                self.worker_completed_at = self.completed[0]
            return result

        self._monkeypatch.setattr(retry_module, "_submit_thread_attempt", submit_and_observe)
        retry_delay = retry_module._retry_delay_sync

        def record_backoff(delay, deadline):
            self.backoff_requests.append((delay, deadline))
            return retry_delay(delay, deadline)

        self._monkeypatch.setattr(retry_module, "_retry_delay_sync", record_backoff)


@pytest.fixture
def controlled_thread_deadline(monkeypatch):
    """Provide deterministic start and backoff phases for timeout-thread tests."""
    return _ControlledThreadDeadline(monkeypatch)


# ---------------------------------------------------------------------------
# RetryPolicy model
# ---------------------------------------------------------------------------


class TestRetryPolicy:
    def test_defaults(self):
        p = RetryPolicy()
        assert p.max_retries == 0
        assert p.backoff_base_s == 1.0
        assert p.backoff_factor == 2.0
        assert p.retry_on == ["node.exception"]

    def test_max_retries_bounds(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RetryPolicy(max_retries=-1)
        with pytest.raises(ValidationError):
            RetryPolicy(max_retries=6)

    def test_backoff_base_bounds(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RetryPolicy(backoff_base_s=0.01)
        with pytest.raises(ValidationError):
            RetryPolicy(backoff_base_s=61.0)

    def test_extra_field_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RetryPolicy(unknown=True)

    def test_custom_retry_on(self):
        p = RetryPolicy(retry_on=["node.exception", "node.invalid_outcome"])
        assert "node.invalid_outcome" in p.retry_on


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestShouldRetry:
    def test_matching_code(self):
        err = NodeError(code="node.exception", message="boom")
        policy = RetryPolicy(retry_on=["node.exception"])
        assert _should_retry(err, policy) is True

    def test_non_matching_code(self):
        err = NodeError(code="node.invalid_outcome", message="bad")
        policy = RetryPolicy(retry_on=["node.exception"])
        assert _should_retry(err, policy) is False

    def test_none_error(self):
        policy = RetryPolicy()
        assert _should_retry(None, policy) is False


class TestBackoffDelay:
    def test_first_attempt(self):
        p = RetryPolicy(backoff_base_s=1.0, backoff_factor=2.0, jitter="none")
        assert _backoff_delay(0, p) == 1.0

    def test_second_attempt(self):
        p = RetryPolicy(backoff_base_s=1.0, backoff_factor=2.0, jitter="none")
        assert _backoff_delay(1, p) == 2.0

    def test_third_attempt(self):
        p = RetryPolicy(backoff_base_s=1.0, backoff_factor=2.0, jitter="none")
        assert _backoff_delay(2, p) == 4.0

    def test_custom_base(self):
        p = RetryPolicy(backoff_base_s=0.5, backoff_factor=3.0, jitter="none")
        assert _backoff_delay(1, p) == 1.5

    def test_jitter_full(self):
        p = RetryPolicy(backoff_base_s=1.0, backoff_factor=2.0, jitter="full")
        delays = [_backoff_delay(0, p) for _ in range(100)]
        assert all(0 <= d <= 1.0 for d in delays)

    def test_jitter_equal(self):
        p = RetryPolicy(backoff_base_s=1.0, backoff_factor=2.0, jitter="equal")
        delays = [_backoff_delay(0, p) for _ in range(100)]
        assert all(0.5 <= d <= 1.0 for d in delays)

    def test_jitter_default_is_full(self):
        p = RetryPolicy()
        assert p.jitter == "full"


# ---------------------------------------------------------------------------
# execute_with_retry_sync
# ---------------------------------------------------------------------------


class TestExecuteWithRetrySync:
    def test_attempt_store_preserves_typed_refs_and_refuses_revoked_persistence(self):
        from polisyos.ir.artifacts import normalize_artifact_ref

        ref = ArtifactRef(
            artifact_id="sha256:" + "0" * 64,
            kind="ir.context_adaptive_parameter_bundle",
            media_type="application/json",
        )
        state = ExperimentState(run_id="run", artifacts_index={"graph": ref})
        authority = retry_module._AttemptAuthority()
        attempt_state = retry_module._AttemptModelFacade(state, authority)
        selected_ref = attempt_state.artifacts_index["graph"]
        assert normalize_artifact_ref(selected_ref) == normalize_artifact_ref(ref)

        class _RecordingStore:
            def __init__(self) -> None:
                self.put_calls: list[tuple[bytes, object]] = []

            def put_bytes(self, data: bytes, options: object) -> ArtifactRef:
                self.put_calls.append((data, options))
                return ref

        store = _RecordingStore()
        attempt_store = retry_module._AttemptFacade(
            store,
            authority,
            write_methods=frozenset({"put_bytes"}),
            raise_on_revoked_write=True,
        )
        assert attempt_store.put_bytes(b"on-time", {}) is ref
        authority.revoke()
        with pytest.raises(retry_module._AttemptWriteDeniedError) as denied:
            attempt_store.put_bytes(b"late", {})
        assert denied.value.code == "attempt_write_revoked"
        assert denied.value.reason_code == "attempt_write_revoked"
        assert store.put_calls == [(b"on-time", {})]

    def test_attempt_store_rejects_non_artifact_refs_from_typed_writers(self) -> None:
        class _MalformedStore:
            def put_bytes(
                self,
                data: bytes,
                opts: object,
                *,
                return_selected_profile: bool = False,
            ) -> object:
                return object()

            def put_json(
                self,
                obj: object,
                opts: object,
                canon_spec: object = None,
                *,
                return_selected_profile: bool = False,
            ) -> object:
                return object()

        facade = retry_module._AttemptFacade(
            _MalformedStore(),
            retry_module._AttemptAuthority(),
            write_methods=frozenset({"put_bytes", "put_json"}),
        )

        with pytest.raises(TypeError, match="artifact_store_write_returned_invalid_ref"):
            facade.put_bytes(b"payload", object())
        with pytest.raises(TypeError, match="artifact_store_write_returned_invalid_ref"):
            facade.put_json({"payload": True}, object())

    def test_attempt_model_facade_preserves_model_type_view_and_read_only_class(self) -> None:
        target = ExperimentState(run_id="model-facade")
        facade = retry_module._AttemptModelFacade(target, retry_module._AttemptAuthority())

        assert isinstance(facade, ExperimentState)
        with pytest.raises(AttributeError):
            facade.__class__ = dict

    def test_attempt_model_facade_normalizes_typed_artifact_refs(self) -> None:
        from polisyos.ir.artifacts import normalize_artifact_ref

        target = ArtifactRef(
            artifact_id="sha256:" + "1" * 64,
            kind="ir.context_adaptive_parameter_bundle",
            media_type="application/json",
        )
        authority = retry_module._AttemptAuthority()

        for facade_type in (
            retry_module._AttemptModelFacade,
            retry_module._AttemptManifestFacade,
        ):
            facade = facade_type(target, authority)
            assert isinstance(facade, ArtifactRef)
            assert normalize_artifact_ref(facade) == normalize_artifact_ref(target)

    def test_execution_context_store_views_preserve_profile_kwargs_and_authority(self):
        from types import SimpleNamespace

        from polisyos.ir.artifacts import normalize_artifact_ref
        from polisyos.scientist.orchestration.engine.context import ExecutionContext

        ref = ArtifactRef(
            artifact_id="sha256:" + "1" * 64,
            kind="ir.context_adaptive_parameter_bundle",
            media_type="application/json",
        )

        class _RecordingStore:
            def __init__(self) -> None:
                self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

            def put_bytes(
                self,
                data: bytes,
                opts: object,
                *,
                return_selected_profile: bool = False,
            ) -> ArtifactRef:
                self.calls.append(
                    (
                        "put_bytes",
                        (data, opts),
                        {"return_selected_profile": return_selected_profile},
                    )
                )
                return ref

            def put_json(
                self,
                obj: object,
                opts: object,
                canon_spec: object = None,
                *,
                return_selected_profile: bool = False,
            ) -> ArtifactRef:
                self.calls.append(
                    (
                        "put_json",
                        (obj, opts),
                        {
                            "canon_spec": canon_spec,
                            "return_selected_profile": return_selected_profile,
                        },
                    )
                )
                return ref

            def record_artifact_owner(
                self,
                artifact_id: str,
                *,
                tenant_id: str | None = None,
                cell_id: str | None = None,
                writer: str | None = None,
            ) -> None:
                self.calls.append(
                    (
                        "record_artifact_owner",
                        (artifact_id,),
                        {"tenant_id": tenant_id, "cell_id": cell_id, "writer": writer},
                    )
                )

        store = _RecordingStore()

        class _RecordingSink:
            def __init__(self) -> None:
                self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

            def emit(self, *args: object, **kwargs: object) -> None:
                self.calls.append((args, kwargs))

        manifest = SimpleNamespace(status="running", errors=[{"nested": {"events": []}}])
        trace_sink = _RecordingSink()
        audit_sink = _RecordingSink()
        run_emit_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        run = SimpleNamespace(
            store=store,
            run_manifest=manifest,
            trace=trace_sink,
            _audit_sink=audit_sink,
            emit=lambda *args, **kwargs: run_emit_calls.append((args, kwargs)),
        )
        target = ExecutionContext(store=store, run=run, logger=MagicMock())
        authority = retry_module._AttemptAuthority()
        attempt = retry_module._build_attempt_context(target, authority)

        assert isinstance(attempt, ExecutionContext)
        store_views = (attempt.store, attempt.run.store)
        assert store_views[0] is store_views[1]
        assert store_views[0]._target is store
        for view in store_views:
            assert view.put_bytes(b"bytes", object(), return_selected_profile=True) is ref
            assert view.put_json({"value": 1}, object(), return_selected_profile=True) is ref
            assert (
                view.record_artifact_owner(
                    ref.artifact_id,
                    tenant_id="tenant",
                    cell_id="cell",
                    writer="attempt-test",
                )
                is None
            )
        assert normalize_artifact_ref(store_views[0].put_json({"ref": True}, object())) == (
            normalize_artifact_ref(ref)
        )
        selected_profile_calls = [
            kwargs["return_selected_profile"]
            for method, _args, kwargs in store.calls
            if method in {"put_bytes", "put_json"}
        ]
        assert selected_profile_calls == [True, True, True, True, False]
        call_count = len(store.calls)
        assert call_count == 7

        authority.revoke()
        for view in store_views:
            for write in (
                lambda view=view: view.put_bytes(b"late", object(), return_selected_profile=True),
                lambda view=view: view.put_json(
                    {"late": True}, object(), return_selected_profile=True
                ),
                lambda view=view: view.record_artifact_owner(ref.artifact_id),
            ):
                with pytest.raises(retry_module._AttemptWriteDeniedError) as denied:
                    write()
                assert denied.value.code == "attempt_write_revoked"
                assert denied.value.reason_code == "attempt_write_revoked"
        assert len(store.calls) == call_count

        for field_name, original in (("store", attempt.store), ("run", attempt.run)):
            with pytest.raises(AttributeError):
                setattr(attempt, field_name, store)
            with pytest.raises(AttributeError):
                delattr(attempt, field_name)
            assert getattr(attempt, field_name) is original

        for field_name in ("store", "run_manifest", "trace", "_audit_sink"):
            original = getattr(attempt.run, field_name)
            with pytest.raises(AttributeError):
                setattr(attempt.run, field_name, store)
            with pytest.raises(AttributeError):
                delattr(attempt.run, field_name)
            assert getattr(attempt.run, field_name) is original

        attempt.run.run_manifest.status = "late"
        attempt.run.run_manifest.errors[0]["nested"]["events"].append("late")
        attempt.run.trace.emit({"late": True})
        attempt.run._audit_sink.emit({"late": True})
        attempt.run.emit("late", "LATE_WRITE")
        assert manifest.status == "running"
        assert manifest.errors == [{"nested": {"events": []}}]
        assert trace_sink.calls == []
        assert audit_sink.calls == []
        assert run_emit_calls == []

    def test_generic_attempt_context_cannot_rebind_mutation_facades(self):
        from types import SimpleNamespace

        class _RecordingStore:
            def __init__(self) -> None:
                self.calls: list[tuple[object, object]] = []

            def put_json(self, payload: object, options: object) -> object:
                self.calls.append((payload, options))
                return payload

        store = _RecordingStore()
        run = SimpleNamespace(
            store=store,
            run_manifest=SimpleNamespace(status="running"),
            trace=SimpleNamespace(emit=lambda record: None),
            _audit_sink=SimpleNamespace(emit=lambda record: None),
            emit=lambda *args, **kwargs: None,
        )
        target = SimpleNamespace(
            store=store,
            run=run,
            audit=SimpleNamespace(append=lambda **kwargs: None),
            claim_ledger_owner=SimpleNamespace(persist_candidate_ledger=lambda **kwargs: None),
        )
        authority = retry_module._AttemptAuthority()
        attempt = retry_module._build_attempt_context(target, authority)

        assert isinstance(attempt, retry_module._AttemptContext)
        store_view = attempt.store
        run_view = attempt.run
        assert run_view.store is store_view
        for field_name, replacement in (
            ("store", store),
            ("run", run),
            ("audit", target.audit),
            ("claim_ledger_owner", target.claim_ledger_owner),
        ):
            with pytest.raises(AttributeError, match="cannot be rebound"):
                setattr(attempt, field_name, replacement)
            with pytest.raises(AttributeError, match="cannot be removed"):
                delattr(attempt, field_name)
        assert attempt.store is store_view
        assert attempt.run is run_view
        assert run_view.store is store_view
        for field_name in ("store", "run_manifest", "trace", "_audit_sink"):
            original = getattr(run_view, field_name)
            with pytest.raises(AttributeError, match="cannot be rebound"):
                setattr(run_view, field_name, store)
            with pytest.raises(AttributeError, match="cannot be removed"):
                delattr(run_view, field_name)
            assert getattr(run_view, field_name) is original

        assert attempt.store.put_json({"on_time": True}, object()) == {"on_time": True}
        authority.revoke()
        with pytest.raises(retry_module._AttemptWriteDeniedError) as denied:
            attempt.run.store.put_json({"late": True}, object())
        assert denied.value.code == "attempt_write_revoked"
        assert denied.value.reason_code == "attempt_write_revoked"
        assert len(store.calls) == 1
        assert store.calls[0][0] == {"on_time": True}

    def test_attempt_context_preserves_claim_capable_context_type(self):
        target = ClaimCapableExecutionContext(
            store=MagicMock(),
            run=MagicMock(),
            logger=MagicMock(),
            claim_ledger_owner=MagicMock(),
        )
        authority = retry_module._AttemptAuthority()

        attempt = retry_module._build_attempt_context(target, authority)

        assert isinstance(attempt, ClaimCapableExecutionContext)
        assert attempt.claim_ledger_owner is not target.claim_ledger_owner
        authority.revoke()
        attempt.claim_ledger_owner.persist_candidate_ledger(ledger="late")
        target.claim_ledger_owner.persist_candidate_ledger.assert_not_called()

    def test_engine_node_manifest_snapshot_detaches_class_owned_mutable_values(self):
        from types import SimpleNamespace

        class _Manifest:
            status = "running"
            errors = [{"nested": {"events": []}}]

        manifest = _Manifest()
        target = SimpleNamespace(run_manifest=manifest)
        view = retry_module._EngineNodeRunView(
            target, _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN
        )

        snapshot = view.run_manifest
        assert type(snapshot) is type(manifest)
        snapshot.errors[0]["nested"]["events"].append("snapshot")

        assert manifest.errors == [{"nested": {"events": []}}]

    def test_engine_node_manifest_snapshot_preserves_typed_model_and_detaches_data(self):
        from types import SimpleNamespace

        from polisyos.core.artifacts.manifest import EnvInfo, GitInfo, ProducerInfo
        from polisyos.core.components.ids import ComponentId

        manifest = RunManifest(
            run_id="run",
            registry_bundle=ArtifactRef(
                artifact_id="sha256:" + "0" * 64,
                kind="registry",
                media_type="application/json",
            ),
            producer=ProducerInfo(
                component=ComponentId("scientist.test@1.0.0"),
                version="1",
                git=GitInfo(commit="1" * 40),
            ),
            env=EnvInfo(
                python="3.14",
                platform="test",
                deps_lock_hash="sha256:" + "0" * 64,
            ),
            errors=[{"nested": {"events": []}}],
        )
        target = SimpleNamespace(run_manifest=manifest)
        view = retry_module._EngineNodeRunView(
            target, _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN
        )

        snapshot = view.run_manifest
        assert type(snapshot) is RunManifest
        assert type(snapshot.registry_bundle) is type(manifest.registry_bundle)
        assert type(snapshot.registry_bundle.artifact_id) is type(
            manifest.registry_bundle.artifact_id
        )
        assert type(snapshot.producer) is type(manifest.producer)
        assert type(snapshot.producer.component) is type(manifest.producer.component)
        assert type(snapshot.producer.git) is type(manifest.producer.git)
        assert type(snapshot.env) is type(manifest.env)
        assert snapshot == manifest
        assert snapshot.model_fields_set == manifest.model_fields_set
        snapshot.status = "snapshot-only"
        snapshot.errors[0]["nested"]["events"].append("snapshot")

        assert manifest.status == "running"
        assert manifest.errors == [{"nested": {"events": []}}]

    def test_engine_node_manifest_snapshot_peels_bounded_exact_attempt_facades(self):
        from types import SimpleNamespace

        for depth in (1, 2, 5, 8):
            manifest = RunManifest(
                run_id=f"run-{depth}",
                registry_bundle=ArtifactRef(
                    artifact_id="sha256:" + "0" * 64,
                    kind="registry",
                    media_type="application/json",
                ),
                errors=[{"nested": {"events": []}}],
            )
            authority = retry_module._AttemptAuthority()
            target = SimpleNamespace(run_manifest=manifest)
            for _ in range(depth):
                target = retry_module._AttemptRunFacade(
                    target,
                    authority,
                    store=object(),
                )
            view = retry_module._EngineNodeRunView(
                target,
                _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
            )

            snapshot = view.run_manifest
            assert type(snapshot) is RunManifest
            assert snapshot is not manifest
            assert snapshot == manifest
            snapshot.errors[0]["nested"]["events"].append("detached")
            assert manifest.errors == [{"nested": {"events": []}}]

    def test_engine_node_manifest_snapshot_rejects_bad_attempt_facade_chains(self):
        from types import SimpleNamespace

        manifest = RunManifest(
            run_id="run",
            registry_bundle=ArtifactRef(
                artifact_id="sha256:" + "0" * 64,
                kind="registry",
                media_type="application/json",
            ),
        )
        authority = retry_module._AttemptAuthority()

        cyclic = retry_module._AttemptManifestFacade(manifest, authority)
        object.__setattr__(cyclic, "_target", cyclic)
        cyclic_view = retry_module._EngineNodeRunView(
            SimpleNamespace(run_manifest=cyclic),
            _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
        )
        with pytest.raises(
            TypeError,
            match="run_manifest_snapshot_attempt_facade_cycle",
        ):
            _ = cyclic_view.run_manifest

        overdepth: object = manifest
        for _ in range(retry_module._MAX_EXACT_WORKER_RUN_FACADE_DEPTH + 1):
            overdepth = retry_module._AttemptManifestFacade(overdepth, authority)
        overdepth_view = retry_module._EngineNodeRunView(
            SimpleNamespace(run_manifest=overdepth),
            _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
        )
        with pytest.raises(
            TypeError,
            match="run_manifest_snapshot_attempt_facade_depth_exceeded",
        ):
            _ = overdepth_view.run_manifest

        spoof_reads: list[str] = []

        class _SpoofManifestFacade(retry_module._AttemptManifestFacade):
            def __getattribute__(self, name: str):
                spoof_reads.append(name)
                return super().__getattribute__(name)

        spoofed = _SpoofManifestFacade(manifest, authority)
        spoofed_view = retry_module._EngineNodeRunView(
            SimpleNamespace(run_manifest=spoofed),
            _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
        )
        with pytest.raises(
            TypeError,
            match="run_manifest_snapshot_record_type_unsupported",
        ):
            _ = spoofed_view.run_manifest
        assert spoof_reads == []

    def test_engine_node_manifest_snapshot_rejects_cycles_and_copy_hooks(self):
        from types import SimpleNamespace

        cyclic: list[object] = []
        cyclic.append(cyclic)

        class _CyclicManifest:
            errors = [{"cycle": cyclic}]

        cyclic_target = SimpleNamespace(run_manifest=_CyclicManifest())
        cyclic_view = retry_module._EngineNodeRunView(
            cyclic_target, _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN
        )
        with pytest.raises(TypeError, match="run_manifest_snapshot_cycle"):
            _ = cyclic_view.run_manifest
        assert cyclic[0] is cyclic

        hook_calls: list[str] = []

        class _UnsafeValue:
            def __deepcopy__(self, memo):
                del memo
                hook_calls.append("called")
                return self

        class _HookManifest:
            errors = [{"value": _UnsafeValue()}]

        hook_target = SimpleNamespace(run_manifest=_HookManifest())
        hook_view = retry_module._EngineNodeRunView(
            hook_target, _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN
        )
        with pytest.raises(TypeError, match="run_manifest_snapshot_record_type_unsupported"):
            _ = hook_view.run_manifest
        assert hook_calls == []

        typed_manifest = RunManifest(
            run_id="run",
            registry_bundle=ArtifactRef(
                artifact_id="sha256:" + "0" * 64,
                kind="registry",
                media_type="application/json",
            ),
            errors=[{"value": _UnsafeValue()}],
        )
        typed_view = retry_module._EngineNodeRunView(
            SimpleNamespace(run_manifest=typed_manifest),
            _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
        )
        with pytest.raises(TypeError):
            _ = typed_view.run_manifest
        assert hook_calls == []

        typed_cycle: list[object] = []
        typed_cycle.append(typed_cycle)
        cyclic_manifest = RunManifest(
            run_id="run",
            registry_bundle=ArtifactRef(
                artifact_id="sha256:" + "0" * 64,
                kind="registry",
                media_type="application/json",
            ),
            errors=[{"cycle": typed_cycle}],
        )
        cyclic_model_view = retry_module._EngineNodeRunView(
            SimpleNamespace(run_manifest=cyclic_manifest),
            _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
        )
        with pytest.raises(TypeError):
            _ = cyclic_model_view.run_manifest
        assert typed_cycle[0] is typed_cycle

        from pydantic import BaseModel, model_serializer

        serializer_calls: list[str] = []

        class _MutatingSerializer(BaseModel):
            value: int = 0

            @model_serializer
            def serialize(self) -> dict[str, int]:
                serializer_calls.append("called")
                self.value += 1
                return {"value": self.value}

        serializer_value = _MutatingSerializer()
        serialized_manifest = RunManifest(
            run_id="run",
            registry_bundle=ArtifactRef(
                artifact_id="sha256:" + "0" * 64,
                kind="registry",
                media_type="application/json",
            ),
            errors=[{"nested": serializer_value}],
        )
        serializer_view = retry_module._EngineNodeRunView(
            SimpleNamespace(run_manifest=serialized_manifest),
            _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
        )
        with pytest.raises(TypeError, match="run_manifest_snapshot_model_type_unsupported"):
            _ = serializer_view.run_manifest
        assert serializer_calls == []
        assert serializer_value.value == 0

        class_spoof_calls: list[str] = []

        class _ClassSpoof:
            @property
            def __class__(self):
                class_spoof_calls.append("called")
                return BaseModel

        spoof_manifest = RunManifest(
            run_id="run",
            registry_bundle=ArtifactRef(
                artifact_id="sha256:" + "0" * 64,
                kind="registry",
                media_type="application/json",
            ),
            errors=[{"nested": _ClassSpoof()}],
        )
        spoof_view = retry_module._EngineNodeRunView(
            SimpleNamespace(run_manifest=spoof_manifest),
            _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
        )
        with pytest.raises(TypeError):
            _ = spoof_view.run_manifest
        assert class_spoof_calls == []

        storage_calls: list[str] = []

        class _DictSpoof:
            @property
            def __dict__(self) -> dict[str, object] | None:
                storage_calls.append("called")
                return None

        storage_manifest = RunManifest(
            run_id="run",
            registry_bundle=ArtifactRef(
                artifact_id="sha256:" + "0" * 64,
                kind="registry",
                media_type="application/json",
            ),
            errors=[{"nested": _DictSpoof()}],
        )
        storage_view = retry_module._EngineNodeRunView(
            SimpleNamespace(run_manifest=storage_manifest),
            _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
        )
        with pytest.raises(TypeError):
            _ = storage_view.run_manifest
        assert storage_calls == []

        metaclass_calls: list[str] = []

        class _MutatingMeta(type):
            def __getattribute__(cls, name: str):
                if name in {"__dict__", "__mro__"}:
                    metaclass_calls.append(name)
                return type.__getattribute__(cls, name)

            def __eq__(cls, other: object) -> bool:
                metaclass_calls.append("eq")
                return False

            def __hash__(cls) -> int:
                metaclass_calls.append("hash")
                return type.__hash__(cls)

        class _CustomMetaRecord(metaclass=_MutatingMeta):
            pass

        meta_manifest = RunManifest(
            run_id="run",
            registry_bundle=ArtifactRef(
                artifact_id="sha256:" + "0" * 64,
                kind="registry",
                media_type="application/json",
            ),
            errors=[{"nested": _CustomMetaRecord()}],
        )
        metaclass_calls.clear()
        meta_view = retry_module._EngineNodeRunView(
            SimpleNamespace(run_manifest=meta_manifest),
            _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
        )
        with pytest.raises(TypeError, match="run_manifest_snapshot_model_type_unsupported"):
            _ = meta_view.run_manifest
        assert metaclass_calls == []

    def test_claim_capable_execute_preserves_type_and_manifest_authority(
        self, state, monkeypatch, controlled_thread_deadline
    ):
        class _RecordingStore:
            def __init__(self) -> None:
                self.put_json_calls: list[tuple[object, object]] = []

            def put_json(self, payload: object, options: object) -> object:
                self.put_json_calls.append((payload, options))
                return object()

        class _RecordingAudit:
            def __init__(self) -> None:
                self.append_calls: list[dict[str, object]] = []
                self.emit_calls: list[object] = []

            def append(self, **kwargs: object) -> None:
                self.append_calls.append(kwargs)

            def emit(self, record: object) -> None:
                self.emit_calls.append(record)

            def close(self) -> None:
                return None

        class _RecordingRun:
            def __init__(self, audit_sink: _RecordingAudit) -> None:
                self.emit_calls: list[tuple[object, ...]] = []
                self.run_manifest = type(
                    "_Manifest",
                    (),
                    {
                        "status": "running",
                        "errors": [{"nested": {"events": []}}],
                    },
                )()
                self._audit_sink = audit_sink

            def emit(self, *args: object, **kwargs: object) -> None:
                self.emit_calls.append((*args, kwargs))

        class _RecordingClaimOwner:
            def __init__(self) -> None:
                self.persist_calls: list[dict[str, object]] = []

            def persist_candidate_ledger(self, **kwargs: object) -> object:
                self.persist_calls.append(kwargs)
                return object()

        store = _RecordingStore()
        run_audit = _RecordingAudit()
        run = _RecordingRun(run_audit)
        audit = _RecordingAudit()
        claim_owner = _RecordingClaimOwner()
        ctx = ClaimCapableExecutionContext(
            store=store,
            run=run,
            logger=MagicMock(),
            audit=audit,
            claim_ledger_owner=claim_owner,
        )
        started = threading.Event()
        release = threading.Event()
        completed = threading.Event()
        worker_errors: list[BaseException] = []

        class _LateClaimNode:
            def execute(self, passed_ctx, passed_state):
                try:
                    assert isinstance(passed_ctx, ClaimCapableExecutionContext)
                    started.set()
                    release.wait(timeout=1.0)
                    passed_ctx.run.run_manifest.status = "late"
                    passed_ctx.run.run_manifest.errors[0]["nested"]["events"].append("late")
                    with pytest.raises(retry_module._AttemptWriteDeniedError) as denied:
                        passed_ctx.store.put_json({"late": "write"}, object())
                    assert denied.value.code == "attempt_write_revoked"
                    assert denied.value.reason_code == "attempt_write_revoked"
                    passed_ctx.run.emit("late", "LATE_WRITE")
                    with pytest.raises(AttributeError):
                        passed_ctx.run._audit_sink.emit({"late": "audit"})
                    passed_ctx.audit.append(action="late")
                    passed_ctx.claim_ledger_owner.persist_candidate_ledger(ledger="late")
                    return _ok_outcome(passed_state)
                except BaseException as exc:
                    worker_errors.append(exc)
                    raise
                finally:
                    completed.set()

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        _select_timeout_test_route(monkeypatch, "thread")
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.retry.get_shared_executor",
            lambda: executor,
        )
        controlled_thread_deadline.observe_first_attempt(started, expire_after_start=True)
        try:
            with pytest.raises(NodeTimeoutError):
                execute_with_retry_sync(
                    _LateClaimNode(),
                    ctx,
                    state,
                    retry_policy=RetryPolicy(),
                    timeout_s=0.01,
                    alias="late-claim",
                )
            assert started.wait(timeout=0.5)
            release.set()
            assert completed.wait(timeout=0.5)
            assert worker_errors == [], repr(worker_errors)
        finally:
            release.set()
            executor.shutdown(wait=True, cancel_futures=True)

        assert run.run_manifest.status == "running"
        assert run.run_manifest.errors == [{"nested": {"events": []}}]
        assert store.put_json_calls == []
        assert run.emit_calls == []
        assert run_audit.emit_calls == []
        assert audit.append_calls == []
        assert claim_owner.persist_calls == []

        class _OnTimeClaimNode:
            def execute(self, passed_ctx, passed_state):
                assert isinstance(passed_ctx, ClaimCapableExecutionContext)
                passed_ctx.run.run_manifest.status = "on_time"
                passed_ctx.run.run_manifest.errors[0]["nested"]["events"].append("on_time")
                passed_ctx.store.put_json({"on_time": True}, object())
                passed_ctx.run.emit("on-time", "ON_TIME")
                with pytest.raises(AttributeError):
                    passed_ctx.run._audit_sink.emit({"on_time": "audit"})
                passed_ctx.audit.append(action="on_time")
                passed_ctx.claim_ledger_owner.persist_candidate_ledger(ledger="on_time")
                return _ok_outcome(passed_state)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            result = execute_with_retry_sync(
                _OnTimeClaimNode(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.5,
                alias="on-time-claim",
            )
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

        assert result.status == "ok"
        assert run.run_manifest.status == "running"
        assert run.run_manifest.errors == [{"nested": {"events": []}}]
        assert store.put_json_calls
        assert run.emit_calls
        assert run_audit.emit_calls == []
        assert audit.append_calls
        assert claim_owner.persist_calls == [{"ledger": "on_time"}]

    def test_attempt_facade_does_not_claim_selected_writer_for_legacy_target(self):
        from polisyos.core.artifacts.protocol import _require_return_selected_profile_writer

        class _LegacyStore:
            def __init__(self) -> None:
                self.calls: list[tuple[object, ...]] = []

            def put_json(self, obj: object, opts: object, canon_spec: object = None) -> object:
                self.calls.append((obj, opts, canon_spec))
                return object()

        store = _LegacyStore()
        facade = retry_module._AttemptFacade(
            store,
            retry_module._AttemptAuthority(None),
            write_methods=frozenset({"put_json"}),
        )

        with pytest.raises(
            NotImplementedError, match="artifact_store_return_selected_profile_unsupported"
        ):
            _require_return_selected_profile_writer(facade, "put_json")
        assert store.calls == []

    def test_claim_capable_execute_preserves_real_run_sinks_on_time(self, state, monkeypatch):
        class _RecordingStore:
            def put_json(self, payload: object, options: object) -> object:
                return object()

        class _RecordingTrace:
            def __init__(self) -> None:
                self.emit_calls: list[object] = []

            def emit(self, record: object) -> None:
                self.emit_calls.append(record)

        class _RecordingAuditSink:
            def __init__(self) -> None:
                self.emit_calls: list[object] = []

            def emit(self, record: object) -> None:
                self.emit_calls.append(record)

            def close(self) -> None:
                return None

        class _RecordingClaimOwner:
            def persist_candidate_ledger(self, **kwargs: object) -> object:
                return object()

        store = _RecordingStore()
        trace = _RecordingTrace()
        audit_sink = _RecordingAuditSink()
        run = RunContext(
            store=store,
            trace=trace,
            run_manifest=RunManifest(
                run_id="run",
                registry_bundle=ArtifactRef(
                    artifact_id="sha256:" + "0" * 64,
                    kind="registry",
                    media_type="application/json",
                ),
            ),
            _audit_sink=audit_sink,
        )
        ctx = ClaimCapableExecutionContext(
            store=store,
            run=run,
            logger=MagicMock(),
            claim_ledger_owner=_RecordingClaimOwner(),
        )
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        _select_timeout_test_route(monkeypatch, "thread")
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.retry.get_shared_executor",
            lambda: executor,
        )

        class _OnTimeRunNode:
            def execute(self, passed_ctx, passed_state):
                assert isinstance(passed_ctx, ClaimCapableExecutionContext)
                passed_ctx.run.emit("on-time", "ON_TIME")
                return _ok_outcome(passed_state)

        try:
            result = execute_with_retry_sync(
                _OnTimeRunNode(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.5,
                alias="on-time-run",
            )
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

        assert result.status == "ok"
        assert len(trace.emit_calls) == 1
        assert len(audit_sink.emit_calls) == 1

    def test_fast_path_no_retry_no_timeout(self, ctx, state):
        """With default policy, delegates directly to node.execute()."""
        node = MagicMock()
        node.execute.return_value = _ok_outcome(state)
        result = execute_with_retry_sync(
            node,
            ctx,
            state,
            retry_policy=RetryPolicy(),
            timeout_s=None,
            alias="a",
        )
        assert result.status == "ok"
        node.execute.assert_called_once()

    def test_succeeds_after_retries(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = [
            _fail_outcome(state, code="node.exception"),
            _fail_outcome(state, code="node.exception"),
            _ok_outcome(state),
        ]
        policy = RetryPolicy(max_retries=3, backoff_base_s=0.1, backoff_factor=1.0)
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            result = execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="a",
            )
        assert result.status == "ok"
        assert node.execute.call_count == 3

    def test_exhausts_retries_on_fail_outcome(self, ctx, state):
        node = MagicMock()
        node.execute.return_value = _fail_outcome(state, code="node.exception")
        policy = RetryPolicy(max_retries=2, backoff_base_s=0.1, backoff_factor=1.0)
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            result = execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="a",
            )
        # Returns last fail outcome (not raises) because the loop exits with the outcome
        assert result.status == "fail"
        assert node.execute.call_count == 3  # 1 + 2 retries

    def test_exception_retry_then_exhausted(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = RuntimeError("boom")
        policy = RetryPolicy(max_retries=2, backoff_base_s=0.1, backoff_factor=1.0)
        with (
            patch("polisyos.scientist.orchestration.engine.retry.time.sleep"),
            pytest.raises(RetryExhaustedError),
        ):
            execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="a",
            )
        assert node.execute.call_count == 3

    def test_retry_on_filter(self, ctx, state):
        """Node fails with code not in retry_on → no retry."""
        node = MagicMock()
        node.execute.return_value = _fail_outcome(state, code="node.invalid_outcome")
        policy = RetryPolicy(max_retries=2, retry_on=["node.exception"])
        result = execute_with_retry_sync(
            node,
            ctx,
            state,
            retry_policy=policy,
            timeout_s=None,
            alias="a",
        )
        assert result.status == "fail"
        assert node.execute.call_count == 1  # No retry

    def test_backoff_timing(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = [
            _fail_outcome(state, code="node.exception"),
            _fail_outcome(state, code="node.exception"),
            _ok_outcome(state),
        ]
        policy = RetryPolicy(
            max_retries=3,
            backoff_base_s=1.0,
            backoff_factor=2.0,
            jitter="none",
        )
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep") as mock_sleep:
            execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="a",
            )
        assert mock_sleep.call_count == 2
        # First backoff: 1.0 * 2^0 = 1.0
        assert mock_sleep.call_args_list[0][0][0] == pytest.approx(1.0)
        # Second backoff: 1.0 * 2^1 = 2.0
        assert mock_sleep.call_args_list[1][0][0] == pytest.approx(2.0)

    @pytest.mark.skipif(
        retry_module._timeout_worker_start_method() != "fork",
        reason="arbitrary-node timeout is verified on the native Linux fork route",
    )
    def test_timeout_raises(self, ctx, state):
        import time as _time

        node = MagicMock()
        node.execute.side_effect = lambda *a, **kw: (_time.sleep(5), _ok_outcome(state))[1]
        with pytest.raises(NodeTimeoutError):
            execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.1,
                alias="a",
            )

    def test_thread_timeout_helper_revokes_late_state_and_owner_writes(
        self, ctx, state, monkeypatch, controlled_thread_deadline
    ):
        """The explicit thread helper revokes writes after its deadline."""

        class _RecordingStore:
            def __init__(self) -> None:
                self.put_json_calls: list[object] = []

            def put_json(self, payload: object, options: object) -> object:
                self.put_json_calls.append((payload, options))
                return object()

        class _RecordingRun:
            def __init__(self) -> None:
                self.emit_calls: list[tuple[object, ...]] = []

            def emit(self, *args: object, **kwargs: object) -> None:
                self.emit_calls.append((*args, kwargs))

        class _RecordingAudit:
            def __init__(self) -> None:
                self.append_calls: list[dict[str, object]] = []

            def append(self, **kwargs: object) -> None:
                self.append_calls.append(kwargs)

            def close(self) -> None:
                return None

        class _RecordingClaimOwner:
            def __init__(self) -> None:
                self.persist_calls: list[dict[str, object]] = []

            def persist_candidate_ledger(self, **kwargs: object) -> object:
                self.persist_calls.append(kwargs)
                return object()

        recording_store = _RecordingStore()
        recording_run = _RecordingRun()
        recording_run.run_manifest = type("_Manifest", (), {"status": "running"})()
        recording_audit = _RecordingAudit()
        recording_claim_owner = _RecordingClaimOwner()
        ctx.store = recording_store
        ctx.run = recording_run
        ctx.audit = recording_audit
        ctx.claim_ledger_owner = recording_claim_owner

        started = threading.Event()
        release = threading.Event()
        completed = threading.Event()
        worker_errors: list[BaseException] = []

        class _LateAuthorityNode:
            def execute(self, passed_ctx, passed_state):
                started.set()
                release.wait(timeout=1.0)
                try:
                    passed_state.params["late_write"] = "unauthorised"
                    passed_ctx.run.run_manifest.status = "late"
                    with pytest.raises(retry_module._AttemptWriteDeniedError) as denied:
                        passed_ctx.store.put_json({"late": "write"}, object())
                    assert denied.value.code == "attempt_write_revoked"
                    assert denied.value.reason_code == "attempt_write_revoked"
                    passed_ctx.run.emit("late-authority", "LATE_WRITE")
                    passed_ctx.audit.append(run_id="run", actor="node", action="late")
                    passed_ctx.claim_ledger_owner.persist_candidate_ledger(ledger="late")
                    return _ok_outcome(passed_state)
                except BaseException as exc:
                    worker_errors.append(exc)
                    raise
                finally:
                    completed.set()

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.retry.get_shared_executor",
            lambda: executor,
        )
        controlled_thread_deadline.observe_first_attempt(started, expire_after_start=True)

        try:
            with pytest.raises(NodeTimeoutError):
                asyncio.run(
                    retry_module._execute_with_timeout_thread_async(
                        _LateAuthorityNode(),
                        ctx,
                        state,
                        timeout_s=0.01,
                    )
                )
            assert started.wait(timeout=0.5)
            release.set()
            assert completed.wait(timeout=0.5)
        finally:
            release.set()
            executor.shutdown(wait=True, cancel_futures=True)

        assert state.params == {}
        assert recording_run.run_manifest.status == "running"
        assert recording_store.put_json_calls == []
        assert recording_run.emit_calls == []
        assert recording_audit.append_calls == []
        assert recording_claim_owner.persist_calls == []

        class _SuccessfulAuthorityNode:
            def execute(self, passed_ctx, passed_state):
                passed_state.params["on_time"] = True
                manifest_snapshot = passed_ctx.run.run_manifest
                manifest_snapshot.status = "on_time"
                assert passed_ctx.run.run_manifest.status == "running"
                passed_ctx.store.put_json({"on_time": True}, object())
                passed_ctx.run.emit("on-time", "ON_TIME")
                passed_ctx.audit.append(run_id="run", actor="node", action="on_time")
                passed_ctx.claim_ledger_owner.persist_candidate_ledger(ledger="on_time")
                return _ok_outcome(passed_state)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            result = asyncio.run(
                retry_module._execute_with_timeout_thread_async(
                    _SuccessfulAuthorityNode(),
                    ctx,
                    state,
                    timeout_s=0.5,
                )
            )
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

        assert result.status == "ok"
        assert recording_run.run_manifest.status == "running"
        assert recording_store.put_json_calls
        assert recording_run.emit_calls
        assert recording_audit.append_calls
        assert recording_claim_owner.persist_calls

    @pytest.mark.asyncio
    async def test_async_timeout_revokes_late_owner_writes(self, ctx, state):
        """A non-cooperative async attempt loses write authority on timeout."""

        class _RecordingStore:
            def __init__(self) -> None:
                self.put_json_calls: list[object] = []

            def put_json(self, payload: object, options: object) -> object:
                self.put_json_calls.append((payload, options))
                return object()

        class _RecordingRun:
            def __init__(self) -> None:
                self.emit_calls: list[tuple[object, ...]] = []
                self.run_manifest = type("_Manifest", (), {"status": "running"})()

            def emit(self, *args: object, **kwargs: object) -> None:
                self.emit_calls.append((*args, kwargs))

        class _RecordingAudit:
            def __init__(self) -> None:
                self.append_calls: list[dict[str, object]] = []

            def append(self, **kwargs: object) -> None:
                self.append_calls.append(kwargs)

            def close(self) -> None:
                return None

        class _RecordingClaimOwner:
            def __init__(self) -> None:
                self.persist_calls: list[dict[str, object]] = []

            def persist_candidate_ledger(self, **kwargs: object) -> object:
                self.persist_calls.append(kwargs)
                return object()

        recording_store = _RecordingStore()
        recording_run = _RecordingRun()
        recording_audit = _RecordingAudit()
        recording_claim_owner = _RecordingClaimOwner()
        ctx.store = recording_store
        ctx.run = recording_run
        ctx.audit = recording_audit
        ctx.claim_ledger_owner = recording_claim_owner

        started = asyncio.Event()
        release = asyncio.Event()
        completed = asyncio.Event()
        worker_errors: list[BaseException] = []

        class _LateAsyncAuthorityNode:
            async def execute_async(self, passed_ctx, passed_state):
                started.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
                try:
                    passed_state.params["late_write"] = "unauthorised"
                    passed_ctx.run.run_manifest.status = "late"
                    with pytest.raises(retry_module._AttemptWriteDeniedError) as denied:
                        passed_ctx.store.put_json({"late": "write"}, object())
                    assert denied.value.code == "attempt_write_revoked"
                    assert denied.value.reason_code == "attempt_write_revoked"
                    passed_ctx.run.emit("late-authority", "LATE_WRITE")
                    passed_ctx.audit.append(run_id="run", actor="node", action="late")
                    passed_ctx.claim_ledger_owner.persist_candidate_ledger(ledger="late")
                    return _ok_outcome(passed_state)
                except BaseException as exc:
                    worker_errors.append(exc)
                    raise
                finally:
                    completed.set()

        result_task = asyncio.create_task(
            execute_with_retry_async(
                _LateAsyncAuthorityNode(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.01,
                alias="late-async-write",
            )
        )

        async def _release_later() -> None:
            await asyncio.sleep(0.05)
            release.set()

        release_task = asyncio.create_task(_release_later())
        await started.wait()
        assert started.is_set()
        with pytest.raises(NodeTimeoutError):
            await result_task
        await release_task
        await asyncio.wait_for(completed.wait(), timeout=0.5)
        assert worker_errors == [], repr(worker_errors)

        assert state.params == {}
        assert recording_run.run_manifest.status == "running"
        assert recording_store.put_json_calls == []
        assert recording_run.emit_calls == []
        assert recording_audit.append_calls == []
        assert recording_claim_owner.persist_calls == []

    def test_timeout_path_uses_shared_executor(self, tmp_path, ctx, state, monkeypatch):
        from polisyos.common.async_tools import _SharedExecutor

        effects = tmp_path / "worker-thread"
        caller = threading.get_ident()

        class Node:
            def execute(self, passed_ctx, passed_state):
                assert passed_ctx is not ctx
                assert passed_state is not state
                effects.write_text(str(threading.get_ident()))
                return _ok_outcome(passed_state)

        with _SharedExecutor(max_workers=4) as executor:
            _select_timeout_test_route(monkeypatch, "thread")
            monkeypatch.setattr(retry_module, "get_shared_executor", lambda: executor)
            result = execute_with_retry_sync(
                Node(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.5,
                alias="actual-shared-thread",
            )
        assert result.status == "ok"
        assert int(effects.read_text()) != caller

    def test_default_policy_zero_retries_no_retry(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=None,
                alias="a",
            )
        assert node.execute.call_count == 1

    def test_node_retry_events_emitted(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = [
            _fail_outcome(state, code="node.exception"),
            _ok_outcome(state),
        ]
        policy = RetryPolicy(max_retries=2, backoff_base_s=0.1, backoff_factor=1.0)
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="step_a",
            )
        # Check NODE_RETRY event was emitted
        retry_calls = [c for c in ctx.run.emit.call_args_list if c[0][1] == "NODE_RETRY"]
        assert len(retry_calls) == 1
        assert retry_calls[0][1]["metrics"]["attempt"] == 1

    def test_bounded_liveness_config_clamps_retry_ceiling(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = [
            _fail_outcome(state, code="node.exception"),
            _fail_outcome(state, code="node.exception"),
            _ok_outcome(state),
        ]
        policy = RetryPolicy(max_retries=3, backoff_base_s=0.1, backoff_factor=1.0)
        liveness_config = BoundedLivenessConfig(
            config_id="bounded-liveness.test.v1",
            owner="team-runtime-quality",
            version="2026-05-22",
            default_deadline_s=30.0,
            default_retry_ceiling=3,
            producer_retry_ceiling_overrides={"scientist.node.step_a": 1},
            feature_flag="universal_pdc_bounded_liveness",
            rollback_path="restore previous governed config artifact",
            promotion_evidence_ref="artifact://bounded-liveness/evidence",
        )

        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            result = execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="step_a",
                liveness_config=liveness_config,
            )

        assert result.status == "fail"
        assert node.execute.call_count == 2


# ---------------------------------------------------------------------------
# execute_with_retry_async
# ---------------------------------------------------------------------------


class TestExecuteWithRetryAsync:
    @pytest.mark.asyncio
    async def test_fast_path(self, ctx, state):
        node = MagicMock()
        node.execute.return_value = _ok_outcome(state)
        result = await execute_with_retry_async(
            node,
            ctx,
            state,
            retry_policy=RetryPolicy(),
            timeout_s=None,
            alias="a",
        )
        assert result.status == "ok"

    @pytest.mark.asyncio
    async def test_sync_execution_uses_shared_executor_bridge(self, ctx, state):
        node = MagicMock()
        node.execute.return_value = _ok_outcome(state)

        async def _bridge(func, *args, **kwargs):
            assert kwargs.pop("unbounded") is True
            return func(*args, **kwargs)

        with patch(
            "polisyos.scientist.orchestration.engine.retry.run_blocking_async",
            new=AsyncMock(side_effect=_bridge),
        ) as bridge:
            result = await execute_with_retry_async(
                node,
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=None,
                alias="a",
            )

        assert result.status == "ok"
        bridge.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        retry_module._timeout_worker_start_method() != "fork",
        reason="arbitrary-node timeout is verified on the native Linux fork route",
    )
    async def test_timeout_raises(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = lambda *a, **kw: (_time.sleep(5), _ok_outcome(state))[1]
        with pytest.raises(NodeTimeoutError):
            await execute_with_retry_async(
                node,
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.1,
                alias="a",
            )

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        retry_module._timeout_worker_start_method() != "fork",
        reason="native Linux fork worker required",
    )
    async def test_timeout_does_not_leave_child_process(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = lambda *a, **kw: (_time.sleep(5), _ok_outcome(state))[1]

        with pytest.raises(NodeTimeoutError):
            await execute_with_retry_async(
                node,
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.1,
                alias="a",
            )

        assert [child for child in mp.active_children() if child.name.startswith("Process-")] == []

    @pytest.mark.asyncio
    async def test_retry_succeeds(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = [
            _fail_outcome(state, code="node.exception"),
            _ok_outcome(state),
        ]
        policy = RetryPolicy(max_retries=2, backoff_base_s=0.1, backoff_factor=1.0)
        result = await execute_with_retry_async(
            node,
            ctx,
            state,
            retry_policy=policy,
            timeout_s=None,
            alias="a",
        )
        assert result.status == "ok"
        assert node.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_exception_retry_exhausted(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = RuntimeError("boom")
        policy = RetryPolicy(max_retries=1, backoff_base_s=0.1, backoff_factor=1.0)
        with pytest.raises(RetryExhaustedError):
            await execute_with_retry_async(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="a",
            )


class TestRetryTimeoutWorker:
    def test_timeout_worker_does_not_swallow_system_exit(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = SystemExit("stop-now")
        result_queue = MagicMock()

        with pytest.raises(SystemExit, match="stop-now"):
            _node_execute_worker(node, ctx, state, result_queue)

        result_queue.put.assert_not_called()


@pytest.mark.parametrize("preparation", ["context", "execute_lookup"])
@pytest.mark.parametrize("expired", [False, True], ids=["on-time", "expired"])
def test_worker_preparation_cannot_enter_body_after_absolute_deadline(
    tmp_path, ctx, state, monkeypatch, preparation, expired
):
    """The final body guard includes context projection and callable lookup."""
    from types import SimpleNamespace

    effects = tmp_path / "physical-body"
    clock = [0.0]
    monkeypatch.setattr(retry_module, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    project_context = retry_module._node_facing_context

    def prepare_context(worker_ctx):
        node_ctx = project_context(worker_ctx)
        if preparation == "context":
            clock[0] = 2.0 if expired else 0.5
        return node_ctx

    class Node:
        @property
        def execute(self):
            if preparation == "execute_lookup":
                clock[0] = 2.0 if expired else 0.5
            return self._execute

        def _execute(self, passed_ctx, passed_state):
            effects.write_text("body")
            return _ok_outcome(passed_state)

    monkeypatch.setattr(retry_module, "_node_facing_context", prepare_context)
    result_queue = MagicMock()

    def invoke():
        _node_execute_worker(Node(), ctx, state, result_queue, compute_deadline=1.0)

    if expired:
        with pytest.raises(NodeTimeoutError) as timeout:
            invoke()
        assert timeout.value.code == "node.timeout"
        assert timeout.value.details["execution_state"] == "not_started"
        result_queue.put.assert_not_called()
        assert not effects.exists()
    else:
        invoke()
        assert effects.read_text() == "body"
        assert result_queue.put.call_args.args[0][0] == "ok"


class _PayloadTransportNode:
    """Return a deterministic result large enough to exercise Queue backpressure."""

    def __init__(self, payload_size: int) -> None:
        self.payload_size = payload_size

    def execute(self, _ctx, passed_state):
        result_state = passed_state.model_copy(deep=True)
        result_state.params["payload"] = "x" * self.payload_size
        return _ok_outcome(result_state)


@pytest.mark.skipif(
    retry_module._timeout_worker_start_method() != "fork",
    reason="native Linux fork worker unavailable",
)
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("payload_size", [64, 1024 * 1024], ids=["small", "one-mib"])
def test_fork_transport_drains_small_and_large_outcomes(ctx, state, mode, payload_size) -> None:
    """A fork worker delivers results without joining before Queue drain."""
    node = _PayloadTransportNode(payload_size)
    kwargs = {"retry_policy": RetryPolicy(), "timeout_s": 2.0, "alias": "payload-wire"}

    if mode == "sync":
        result = execute_with_retry_sync(node, ctx, state, **kwargs)
    else:
        result = asyncio.run(execute_with_retry_async(node, ctx, state, **kwargs))

    assert result.status == "ok"
    assert result.state.params["payload"] == "x" * payload_size


@pytest.mark.skipif(
    retry_module._timeout_worker_start_method() != "fork",
    reason="native Linux fork worker unavailable",
)
def test_linux_fork_receipt_stages_trace_and_parent_admits_run_operations(tmp_path) -> None:
    """An inherited worker returns exact trace and RunContext operations to its parent."""
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.trace.record import TraceRecord
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.protocol import NodeSpec

    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(
        store=store,
        registry_bundle=bundle.bundle_ref,
        run_id="R_linux_fork_receipt",
    )
    context = ExecutionContext(store=store, run=run, logger=MagicMock())
    input_ref = store.put_json(
        {"kind": "fork-worker-input", "value": 1},
        PutOptions(
            kind="scientist.test.fork_worker_input",
            media_type="application/json",
            schema=SchemaInfo(name="scientist.test.ForkWorkerInput", version="1.0"),
        ),
        return_selected_profile=True,
    )
    assert input_ref.manifest_profile_sha256 is not None
    assert store.verify(input_ref).ok
    parent_pid = os.getpid()

    class ReceiptNode:
        spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.test.fork_receipt@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                capabilities=Capability.SCIENTIST_NODE,
                display_name="Fork receipt test",
                description="Exercises parent-admitted worker events.",
            ),
            state_reads=["params"],
            state_writes=["params"],
        )

        def execute(self, worker_context, worker_state):
            assert os.getpid() != parent_pid
            assert isinstance(worker_context.run, RunContext)
            with pytest.raises(ValueError, match="timeout_worker_run_lifecycle_not_owned"):
                worker_context.run.finalize()
            with pytest.raises(ValueError, match="timeout_worker_run_lifecycle_not_owned"):
                worker_context.run.suspend_for_resume()
            worker_context.run.emit(
                "scientist.node.fork-receipt",
                "NODE_FORK_RECEIPT_EMITTED",
                metrics={"worker_pid": os.getpid()},
            )
            worker_context.run.add_input(input_ref)
            worker_state.params["fork_worker_pid"] = os.getpid()
            return _ok_outcome(worker_state)

    result = execute_with_retry_sync(
        ReceiptNode(),
        context,
        ExperimentState(run_id="R_linux_fork_receipt"),
        retry_policy=RetryPolicy(),
        timeout_s=3.0,
        alias="fork-receipt",
        dispatch_params={"source": "invocation"},
    )

    assert result.status == "ok"
    assert result.state.params["fork_worker_pid"] != parent_pid
    assert not run._closed and not run._suspended and run._active_lease is not None
    assert input_ref in run.run_manifest.inputs
    records = [
        TraceRecord.model_validate_json(line) for line in run.trace_path.read_text().splitlines()
    ]
    worker_event = next(record for record in records if record.event == "NODE_FORK_RECEIPT_EMITTED")
    assert worker_event.metrics["worker_pid"] == result.state.params["fork_worker_pid"]
    assert sum(record.event == "WORKER_INVOCATION_STARTED" for record in records) == 1
    assert sum(record.event == "WORKER_INVOCATION_COMPLETED" for record in records) == 1
    receipt_ids = {
        record.worker_invocation_id for record in records if record.worker_invocation_id is not None
    }
    assert len(receipt_ids) == 1


@pytest.mark.skipif(
    retry_module._timeout_worker_start_method() != "fork",
    reason="native Linux fork worker unavailable",
)
@pytest.mark.parametrize(
    ("operation", "access_path"),
    [
        ("finalize", "facade_alias"),
        ("suspend_for_resume", "facade_alias"),
        ("finalize", "raw_context_alias"),
        ("suspend_for_resume", "raw_context_alias"),
        ("finalize", "class_dispatch"),
        ("suspend_for_resume", "class_dispatch"),
    ],
)
def test_linux_fork_worker_core_owner_refuses_inherited_lifecycle(
    tmp_path: Path,
    operation: str,
    access_path: str,
) -> None:
    """A fork worker can stage events but cannot reach or terminalize its parent run."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.trace.record import TraceRecord
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.protocol import NodeSpec

    run_id = f"R_fork_lifecycle_{operation}_{access_path}"
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(
        store=store,
        registry_bundle=bundle.bundle_ref,
        run_id=run_id,
    )
    context = ExecutionContext(store=store, run=run, logger=MagicMock())
    parent_pid = os.getpid()

    class LifecycleNode:
        spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.test.fork_lifecycle@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                capabilities=Capability.SCIENTIST_NODE,
                display_name="Fork lifecycle owner test",
                description="Exercises Core lifecycle ownership from an inherited worker.",
            ),
            state_reads=["params"],
            state_writes=["params"],
        )

        def execute(
            self,
            worker_context: ExecutionContext,
            worker_state: ExperimentState,
        ) -> NodeOutcome:
            worker_state.params["fork_worker_pid"] = os.getpid()
            worker_run = worker_context.run
            target_access = "not_attempted"
            if access_path == "raw_context_alias":
                target = worker_run
                try:
                    target_name = "_target"
                    for _ in range(2):
                        target = getattr(target, target_name)
                except AttributeError:
                    target_access = "refused"
                else:
                    target_access = "admitted"
            try:
                if access_path == "class_dispatch":
                    if operation == "finalize":
                        RunContext.finalize(worker_run)
                    else:
                        RunContext.suspend_for_resume(worker_run)
                elif operation == "finalize":
                    worker_run.finalize()
                else:
                    worker_run.suspend_for_resume()
            except ValueError as exc:
                refusal = str(exc)
            else:
                refusal = "lifecycle_transition_was_admitted"

            worker_state.params["lifecycle_refusal"] = refusal
            worker_state.params["target_access"] = target_access
            worker_context.run.emit(
                "scientist.node.fork-lifecycle",
                "NODE_FORK_LIFECYCLE_REFUSED",
                metrics={"worker_pid": os.getpid()},
            )
            return _ok_outcome(worker_state)

    result = execute_with_retry_sync(
        LifecycleNode(),
        context,
        ExperimentState(run_id=run_id),
        retry_policy=RetryPolicy(),
        timeout_s=3.0,
        alias="fork-lifecycle",
        dispatch_params={"operation": operation, "access_path": access_path},
    )

    assert result.status == "ok"
    assert result.state.params["fork_worker_pid"] != parent_pid
    assert result.state.params["lifecycle_refusal"] == "timeout_worker_run_lifecycle_not_owned"
    if access_path == "raw_context_alias":
        assert result.state.params["target_access"] == "refused"
    assert not run._closed and not run._suspended and run._active_lease is not None
    trace_path = run.trace_path
    assert trace_path is not None
    records = [
        TraceRecord.model_validate_json(line) for line in trace_path.read_text().splitlines()
    ]
    refused = [record for record in records if record.event == "NODE_FORK_LIFECYCLE_REFUSED"]
    assert len(refused) == 1
    assert refused[0].metrics["worker_pid"] == result.state.params["fork_worker_pid"]
    assert not store.root.joinpath("runs", run_id, "finalized.json").exists()

    run.finalize(status="ok")


class _BrokenResultQueue:
    """A result channel that fails every send; success must never be fabricated."""

    def __init__(self) -> None:
        self.attempts = 0

    def put(self, _value) -> None:
        self.attempts += 1
        raise OSError("result channel closed")


def test_timeout_worker_node_outcome_is_admitted_at_the_execution_boundary(ctx, state) -> None:
    class _MalformedNode:
        def execute(self, _ctx, _state) -> object:
            return {"status": "ok"}

    with pytest.raises(retry_module._CompletedAttemptError) as invalid_result:
        retry_module._execute_capture_failure(_MalformedNode(), ctx, state)
    assert isinstance(invalid_result.value.error, TypeError)
    assert str(invalid_result.value.error) == "node execution must return a NodeOutcome"


def test_worker_result_drain_rejects_malformed_queue_frames() -> None:
    class _LiveWorker:
        def is_alive(self) -> bool:
            return True

    class _MalformedQueue:
        def get(self, *, timeout: float) -> object:
            return ("ok",)

    completed_at = _time.monotonic()
    completion_time = type("Completion", (), {"value": completed_at})()
    with pytest.raises(RuntimeError, match="timeout_worker_result_frame_invalid"):
        retry_module._drain_result_sync(
            _LiveWorker(),
            _MalformedQueue(),
            compute_deadline=completed_at + 1.0,
            completion_time=completion_time,
        )


def test_process_factory_uses_the_admitted_platform_context() -> None:
    start_method = retry_module._timeout_worker_start_method()
    assert start_method is not None
    process_context = mp.get_context(start_method)

    assert retry_module._process_factory(process_context) is process_context.Process
    with pytest.raises(NodeTimeoutError, match="process_context_process_factory_unavailable"):
        retry_module._process_factory(mp.context.BaseContext())


@pytest.mark.parametrize("malformed_factory", [None, 3, object()])
def test_process_factory_rejects_present_non_callable_factory(
    malformed_factory: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process_context = mp.get_context(retry_module._timeout_worker_start_method() or "spawn")
    monkeypatch.setattr(process_context, "Process", malformed_factory)

    with pytest.raises(NodeTimeoutError, match="process_context_process_factory_unavailable"):
        retry_module._process_factory(process_context)


def test_process_group_lookup_refuses_missing_worker_pid() -> None:
    class _Ready:
        def is_set(self) -> bool:
            return True

    class _StartedWithoutPid:
        pid = None

        def is_alive(self) -> bool:
            return True

    assert (
        retry_module._owned_process_group_id(
            _StartedWithoutPid(),
            _Ready(),
            deadline=_time.monotonic() + 1.0,
        )
        is None
    )


def test_worker_send_failure_is_fail_closed(ctx, state) -> None:
    node = _PayloadTransportNode(64)
    result_queue = _BrokenResultQueue()

    with pytest.raises(RuntimeError, match="failed to send result"):
        _node_execute_worker(node, ctx, state, result_queue)

    assert result_queue.attempts >= 2


class _SerializationFailureOutcome:
    def model_dump(self, *, mode: str):
        raise TypeError(f"cannot serialize in {mode} mode")


class _SerializationFailureNode:
    def execute(self, _ctx, _state):
        return _SerializationFailureOutcome()


def test_serialization_failure_is_not_reported_as_success(ctx, state) -> None:
    """The worker reports a failed outcome serialization as an error payload."""
    messages: list[tuple[str, object]] = []

    class _RecordingResultQueue:
        def put(self, message: tuple[str, object]) -> None:
            messages.append(message)

    _node_execute_worker(_SerializationFailureNode(), ctx, state, _RecordingResultQueue())

    assert len(messages) == 1
    status, payload = messages[0]
    assert status == "error"
    assert isinstance(payload, dict)
    assert "TypeError: cannot serialize in python mode" in str(payload.get("message"))


class _ExitedWorker:
    """Minimal process double for a result arriving after the compute window."""

    def is_alive(self) -> bool:
        return False

    @property
    def exitcode(self) -> int:
        return 0


class _StoppedProcessHandle:
    def is_alive(self) -> bool:
        return False

    def join(self, *, timeout: float) -> None:
        _ = timeout


def test_unknown_process_group_cleanup_is_not_reported_complete() -> None:
    """A stopped worker without a group cannot prove descendants are gone."""
    assert retry_module._terminate_owned_process(_StoppedProcessHandle(), None) is False


class _ImmediateResultQueue:
    def get(self, *, timeout: float):
        _ = timeout
        return ("ok", {})

    def get_nowait(self):
        return ("ok", {})


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("expired", [False, True], ids=["early-exit", "expired"])
def test_late_worker_completion_is_not_delivery_success(mode, expired) -> None:
    """A dead worker alone cannot prove computation met its deadline."""
    process = _ExitedWorker()
    result_queue = _ImmediateResultQueue()
    compute_deadline = _time.monotonic() + (-1.0 if expired else 1.0)

    def invoke():
        if mode == "sync":
            retry_module._drain_result_sync(
                process,
                result_queue,
                compute_deadline=compute_deadline,
            )
        else:
            asyncio.run(
                retry_module._drain_result_async(
                    process,
                    result_queue,
                    compute_deadline=compute_deadline,
                )
            )

    expected = retry_module._WorkerComputeTimeout if expired else retry_module._WorkerProcessExited
    with pytest.raises(expected):
        invoke()


class _DescendantProcessNode:
    """Keep an owned descendant alive long enough to exercise group cleanup."""

    def __init__(self, pid_path) -> None:
        self.pid_path = pid_path

    def execute(self, _ctx, _state):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.pid_path.write_text(str(child.pid))
        _time.sleep(30)
        raise AssertionError("timeout should terminate the worker first")


@pytest.mark.skipif(
    retry_module._timeout_worker_start_method() != "fork",
    reason="native Linux fork worker unavailable",
)
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_timeout_cleans_owned_process_descendant(tmp_path, ctx, state, mode) -> None:
    """Timeout cleanup owns the worker group and does not leave descendants."""
    pid_path = tmp_path / "descendant-pid"
    node = _DescendantProcessNode(pid_path)
    descendant_pid: int | None = None

    try:

        def invoke():
            kwargs = {
                "retry_policy": RetryPolicy(),
                "timeout_s": 0.5,
                "alias": "descendant-cleanup",
            }
            if mode == "sync":
                execute_with_retry_sync(node, ctx, state, **kwargs)
            else:
                asyncio.run(execute_with_retry_async(node, ctx, state, **kwargs))

        with pytest.raises(NodeTimeoutError):
            invoke()
        assert pid_path.exists()
        descendant_pid = int(pid_path.read_text())
        with pytest.raises(ProcessLookupError):
            os.kill(descendant_pid, 0)
    finally:
        if descendant_pid is not None:
            try:
                os.kill(descendant_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


class _ExitedWorkerWithDescendantNode:
    """Exit the worker while leaving a descendant in its owned process group."""

    def __init__(self, pid_path) -> None:
        self.pid_path = pid_path

    def execute(self, _ctx, _state):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.pid_path.write_text(str(child.pid))
        os._exit(0)


@pytest.mark.skipif(
    retry_module._timeout_worker_start_method() != "fork",
    reason="native Linux fork worker unavailable",
)
def test_cleanup_kills_descendant_after_worker_exit(tmp_path, ctx, state) -> None:
    """Cleanup must still reap an owned group after its worker has exited."""
    pid_path = tmp_path / "exited-worker-descendant-pid"
    node = _ExitedWorkerWithDescendantNode(pid_path)
    descendant_pid: int | None = None

    try:
        with pytest.raises(NodeTimeoutError):
            retry_module._execute_with_timeout_process(
                node,
                ctx,
                state,
                timeout_s=0.5,
            )
        assert pid_path.exists()
        descendant_pid = int(pid_path.read_text())
        for _ in range(20):
            try:
                os.kill(descendant_pid, 0)
            except ProcessLookupError:
                break
            _time.sleep(0.05)
        else:
            pytest.fail("owned descendant survived worker cleanup")
    finally:
        if descendant_pid is not None:
            try:
                os.kill(descendant_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


class _OutputAwareTransportNode:
    def __init__(self, outcome, worker_pid_path):
        self.outcome = outcome
        self.worker_pid_path = worker_pid_path

    def execute(self, ctx, state):
        import os

        self.worker_pid_path.write_text(str(os.getpid()))
        return self.outcome


@pytest.mark.skipif(
    retry_module._timeout_worker_start_method() != "fork",
    reason="native Linux fork worker unavailable",
)
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_output_aware_fork_retry_preserves_complete_outcome(tmp_path, ctx, mode) -> None:
    import asyncio
    import os

    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.scientist.orchestration.engine import OutputAwareNodeOutcome
    from tests.unit.scientist.orchestration.engine.runner.test_serialization import (
        _output_aware_transport_outcome,
    )

    outcome = _output_aware_transport_outcome(FileSystemCAS(tmp_path / "cas"))
    worker_pid_path = tmp_path / "actual-worker-pid"
    node = _OutputAwareTransportNode(outcome, worker_pid_path)
    kwargs = {"retry_policy": RetryPolicy(), "timeout_s": 10.0, "alias": "output-aware-wire"}
    if mode == "sync":
        restored = execute_with_retry_sync(node, ctx, outcome.state, **kwargs)
    else:
        restored = asyncio.run(execute_with_retry_async(node, ctx, outcome.state, **kwargs))
    assert int(worker_pid_path.read_text()) != os.getpid()
    assert type(restored) is OutputAwareNodeOutcome
    assert restored.model_dump(mode="json") == outcome.model_dump(mode="json")


class _OwnedProcessTreeNode:
    """Run a real new-session, TERM-resistant grandchild with observable writes."""

    def __init__(self, directory, *, finish):
        self.directory = directory
        self.finish = finish

    def execute(self, _ctx, state):
        effects = self.directory / "grandchild-effects.txt"
        identities = self.directory / "process-identities.json"
        leaf = (
            "import os,signal,time\n"
            "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
            f"f=open({str(effects)!r},'a',buffering=1)\n"
            "while True:\n f.write('effect\\n')\n time.sleep(.002)\n"
        )
        ancestor = (
            "import json,os,signal,subprocess,sys,time; "
            "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
            f"p=subprocess.Popen([sys.executable,'-c',{leaf!r}],start_new_session=True); "
            f"open({str(identities)!r},'w').write(json.dumps([os.getppid(),os.getpid(),p.pid])); "
            "time.sleep(30)"
        )
        subprocess.Popen([sys.executable, "-c", ancestor], start_new_session=True)
        deadline = _time.monotonic() + 2
        while not effects.exists() or not effects.stat().st_size:
            if _time.monotonic() >= deadline:
                raise RuntimeError("real grandchild did not enter its filesystem effect")
            _time.sleep(0.001)
        if self.finish:
            return _ok_outcome(state)
        _time.sleep(30)
        return _ok_outcome(state)


def _assert_real_tree_reaped(directory):
    import json

    pids = json.loads((directory / "process-identities.json").read_text())
    assert len(pids) == 3 and len(set(pids)) == 3
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    effects = directory / "grandchild-effects.txt"
    observed = effects.read_bytes()
    assert observed.startswith(b"effect\n")
    _time.sleep(0.02)
    assert effects.read_bytes() == observed


def _caller_subreaper_flag():
    import ctypes

    flag = ctypes.c_int()
    assert ctypes.CDLL(None).prctl(37, ctypes.byref(flag), 0, 0, 0) == 0
    return flag.value


@pytest.fixture
def owned_tree_dir(tmp_path):
    """Keep failed negative controls from leaving running effect producers."""
    import json

    try:
        yield tmp_path
    finally:
        identities = tmp_path / "process-identities.json"
        if identities.exists():
            for pid in reversed(json.loads(identities.read_text())):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child subreaper contract")
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("finish", [True, False], ids=["returned", "expired"])
def test_owned_supervisor_reaps_real_new_session_grandchild(
    owned_tree_dir, ctx, state, mode, finish
):
    tmp_path = owned_tree_dir
    original_flag = _caller_subreaper_flag()
    node = _OwnedProcessTreeNode(tmp_path, finish=finish)
    kwargs = {"retry_policy": RetryPolicy(), "timeout_s": 0.3, "alias": "actual-tree"}
    if finish:
        outcome = (
            execute_with_retry_sync(node, ctx, state, **kwargs)
            if mode == "sync"
            else asyncio.run(execute_with_retry_async(node, ctx, state, **kwargs))
        )
        assert outcome.status == "ok"
    else:

        def invoke():
            if mode == "sync":
                return execute_with_retry_sync(node, ctx, state, **kwargs)
            return asyncio.run(execute_with_retry_async(node, ctx, state, **kwargs))

        with pytest.raises(NodeTimeoutError) as expired:
            invoke()
    _assert_real_tree_reaped(tmp_path)
    if not finish:
        assert expired.value.details["execution_state"] == "owned_processes_reaped"
        assert expired.value.details["cleanup_complete"] is True
    assert _caller_subreaper_flag() == original_flag


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child subreaper contract")
def test_owned_supervisor_reaps_tree_on_async_caller_cancellation(owned_tree_dir, ctx, state):
    tmp_path = owned_tree_dir
    original_flag = _caller_subreaper_flag()

    async def exercise():
        task = asyncio.create_task(
            execute_with_retry_async(
                _OwnedProcessTreeNode(tmp_path, finish=False),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=5,
                alias="cancel-tree",
            )
        )
        deadline = _time.monotonic() + 2
        effects = tmp_path / "grandchild-effects.txt"
        while not effects.exists() or not effects.stat().st_size:
            assert _time.monotonic() < deadline
            await asyncio.sleep(0.002)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    _assert_real_tree_reaped(tmp_path)
    assert _caller_subreaper_flag() == original_flag


@pytest.mark.skipif(sys.platform != "linux", reason="Linux owned-process-tree supervisor")
def test_authenticated_cancel_reaps_owned_child_and_fences_fresh_job(
    owned_tree_dir, ctx, state, runtime_api_env, monkeypatch
):
    """Real route permission and worker lease loss stop the owned process tree."""
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
    from polisyos.runtime.http import deployment_security
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobExecutionAdmissionError,
        ControlJobLeaseLostError,
    )
    from polisyos.runtime.http.services.control_worker import ControlWorker
    from tests._helpers.runtime_http import deployment_security_config_mapping
    from tests.unit.runtime.http.test_control_plane_store import (
        _job_creation_event,
        _job_execution_scope,
    )
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _fixture_bearer,
        _install_authorization_audit_capture,
    )

    fixture_config = runtime_api_env["app"].state.runtime_container.config
    assert fixture_config.catalog_source_selection is not None
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
        repo_root=fixture_config.repo_root,
        catalog_source_selection=fixture_config.catalog_source_selection,
    )
    tenant = runtime_api_env["tenant_a"]
    bearer = _fixture_bearer("cancellation-authorized")
    provider.put_claim(
        bearer,
        UserIdentityClaims(
            sub="runtime-canary",
            tenant_id=tenant,
            cell_id=cell.cell_id,
            roles=frozenset({PolicyOSRole.ADMIN}),
            mfa_verified=True,
            iss="https://idp.example",
            aud="polisyos-runtime",
            exp=9_999_999_999,
            iat=1,
            jti="cancellation-test-jwt",
        ),
    )
    denied_bearer = _fixture_bearer("cancellation-denied")
    other_tenant_bearer = _fixture_bearer("cancellation-other-tenant")
    for token, subject, claim_tenant in (
        (denied_bearer, "ungranted-actor", tenant),
        (other_tenant_bearer, "runtime-canary", runtime_api_env["tenant_b"]),
    ):
        provider.put_claim(
            token,
            UserIdentityClaims(
                sub=subject,
                tenant_id=claim_tenant,
                cell_id=cell.cell_id,
                roles=frozenset({PolicyOSRole.ADMIN}),
                mfa_verified=True,
                iss="https://idp.example",
                aud="polisyos-runtime",
                exp=9_999_999_999,
                iat=1,
                jti=f"cancellation-test-{subject}-{claim_tenant}",
            ),
        )
    config = deployment_security_config_mapping(owned_tree_dir)
    registry_path = owned_tree_dir / "cancellation-cells.json"
    registry_path.write_text(
        json.dumps(
            {
                "cells": [cell.model_dump(mode="json")],
                "tenants": [
                    {
                        "tenant_id": tenant,
                        "name": "Cancellation test tenant",
                        "tier": cell.tier.value,
                        "region": cell.region,
                        "cell_id": cell.cell_id,
                    },
                    {
                        "tenant_id": runtime_api_env["tenant_b"],
                        "name": "Cancellation other test tenant",
                        "tier": cell.tier.value,
                        "region": cell.region,
                        "cell_id": cell.cell_id,
                    },
                ],
            }
        )
    )
    config["cell_registry_path"] = str(registry_path)
    principals = config["service_principals"]
    assert isinstance(principals, list)
    principals[0].update(
        {
            "tenant_id": tenant,
            "cell_id": cell.cell_id,
            "permissions": ["runs.view", "jobs.cancel"],
        }
    )
    principals.append({**principals[0], "tenant_id": runtime_api_env["tenant_b"]})
    security = deployment_security.build_deployment_security(
        deployment_security.DeploymentSecurityConfig.from_mapping(config)
    )
    client.app.state.runtime_deployment_principal_grants = security.principal_grants
    _install_authorization_audit_capture(client)
    headers = {"Authorization": f"Bearer {bearer}", "X-Tenant-ID": tenant}

    with client:
        service = client.app.state.runtime_container.control_service
        assert service is not None
        if service._worker is not None:
            service._worker.stop()
        store = service._control_store
        scope = _job_execution_scope()
        scope["tenant_id"], scope["cell_id"] = tenant, cell.cell_id
        cas = FileSystemCAS(runtime_api_env["cas_root"])
        manifest = cas.put_json(
            {"fixture": "c57-process-ownership"},
            ArtifactWriteOptions(
                kind="runtime.capability_manifest",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.test.C57Manifest", version="1.0"),
            ),
        )
        manifest_id = str(manifest.artifact_id)
        creation = _job_creation_event(execution_scope=scope)
        creation["capability_manifest_ref"] = manifest_id
        job = store.create_job(
            job_id="job_execution_admission",
            kind="workflow_run",
            run_id="run_execution_admission",
            pipeline_id=None,
            requested_execution_profile=None,
            effective_execution_profile="dev",
            policy_flags={"candidate": True},
            capability_manifest_ref=manifest_id,
            payload_ref="sha256:payload-b",
            submitted_by="denis",
            creation_event_payload=creation,
        )

        def handler(_job):
            execute_with_retry_sync(
                _OwnedProcessTreeNode(owned_tree_dir, finish=False),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=30,
                alias="authenticated-cancellation",
            )
            pytest.fail("interrupted owned computation returned a result")

        worker = ControlWorker(
            store=store, handler=handler, worker_id="cancel-test-worker", lease_seconds=2
        )
        errors = []

        def dispatch():
            try:
                worker.dispatch_once()
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=dispatch, daemon=True)
        thread.start()
        try:
            effects = owned_tree_dir / "grandchild-effects.txt"
            deadline = _time.monotonic() + 30
            while not effects.exists() or not effects.stat().st_size:
                assert thread.is_alive() and _time.monotonic() < deadline
                _time.sleep(0.01)
            running = store.get_job(job.job_id)
            assert running is not None and running.state == "running"
            assert (
                client.get(f"/api/v1/control/jobs/{job.job_id}", headers=headers).status_code == 200
            )
            body = {
                "operation_id": "cancel-owned-child",
                "expected_lease_owner": running.lease_owner,
                "expected_attempt": running.attempt,
            }
            for token, claim_tenant in (
                (denied_bearer, tenant),
                (other_tenant_bearer, runtime_api_env["tenant_b"]),
            ):
                denied = client.post(
                    f"/api/v1/control/jobs/{job.job_id}/cancel",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Tenant-ID": claim_tenant,
                    },
                    json=body,
                )
                assert denied.status_code == 403, denied.text
                assert store.get_job(job.job_id).state == "running"

            inactive = client.post(
                f"/api/v1/control/jobs/{job.job_id}/cancel", headers=headers, json=body
            )
            assert inactive.status_code == 503, inactive.text
            assert store.get_job(job.job_id).state == "running"
            client.app.state.control_job_cancellation_rollout_enabled = True

            # The proof observed here is produced by the actual route dependency.
            # Reusing it with a different body must be refused before mutation.
            original_cancel = service.cancel_job
            observed_proofs = []

            def intercept(*, job_id, request, authorization_proof, request_id=None):
                observed_proofs.append(authorization_proof)
                with pytest.raises(ControlJobExecutionAdmissionError):
                    store.cancel_job(
                        job_id=job_id,
                        authorization_proof=authorization_proof,
                        operation_id="substituted-operation",
                        expected_lease_owner=request.expected_lease_owner,
                        expected_attempt=request.expected_attempt,
                    )
                return original_cancel(
                    job_id=job_id,
                    request=request,
                    authorization_proof=authorization_proof,
                    request_id=request_id,
                )

            monkeypatch.setattr(service, "cancel_job", intercept)
            response = client.post(
                f"/api/v1/control/jobs/{job.job_id}/cancel",
                headers=headers,
                json=body,
            )
            assert response.status_code == 200, response.text
            assert response.json()["state"] == "cancelled"
            repeated = client.post(
                f"/api/v1/control/jobs/{job.job_id}/cancel",
                headers=headers,
                json=body,
            )
            assert repeated.status_code == 200, repeated.text
            with pytest.raises(ControlJobExecutionAdmissionError):
                store.cancel_job(
                    job_id=job.job_id,
                    authorization_proof=observed_proofs[0],
                    operation_id=body["operation_id"],
                    expected_lease_owner=body["expected_lease_owner"],
                    expected_attempt=body["expected_attempt"],
                )
            thread.join(timeout=10)
            assert not thread.is_alive() and not errors
            _assert_real_tree_reaped(owned_tree_dir)
            fresh = client.get(f"/api/v1/control/jobs/{job.job_id}", headers=headers)
            assert fresh.status_code == 200
            assert fresh.json()["state"] == "cancelled"
            assert fresh.json()["physical_stop_status"] == "not_established"
            assert store.get_cancelled_job_verified_record(job.job_id).attempt == running.attempt
            with pytest.raises(ControlJobLeaseLostError):
                store.complete_job(
                    job_id=job.job_id,
                    expected_lease_owner=running.lease_owner,
                    expected_attempt=running.attempt,
                )
            with pytest.raises(ControlJobLeaseLostError):
                store.upsert_progress(job_id=job.job_id, progress={"state": "running"})
        finally:
            worker.stop()
            thread.join(timeout=3)


def test_framed_result_reader_never_blocks_on_an_actual_partial_pipe():
    channel = retry_module._WorkerResultChannel(mp.get_context("fork"))
    try:
        os.write(channel._writer.fileno(), (100).to_bytes(8, "big") + b"abc")
        started = _time.monotonic()
        with pytest.raises(retry_module.queue.Empty):
            channel.get_nowait()
        assert _time.monotonic() - started < 0.05
        channel.close_writer()
        with pytest.raises(EOFError):
            channel.get_nowait()
    finally:
        channel.close()


@pytest.mark.skipif(
    retry_module._timeout_worker_start_method() != "fork",
    reason="process-start failure transport is verified on the native Linux fork route",
)
def test_real_process_start_failure_preserves_original_error_and_no_body_effect(
    tmp_path, ctx, state, monkeypatch
):
    entered = tmp_path / "entered.txt"

    class Node:
        def execute(self, _ctx, passed_state):
            entered.write_text("physical body")
            return _ok_outcome(passed_state)

    def denied(_process):
        raise OSError("actual process start denied")

    monkeypatch.setattr(mp.get_context("fork").Process, "start", denied)
    with pytest.raises(OSError, match="actual process start denied"):
        retry_module._execute_with_timeout_process(Node(), ctx, state, timeout_s=0.1)
    assert not entered.exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child subreaper contract")
def test_supervisor_setup_failure_is_transported_without_starting_node(
    tmp_path, ctx, state, monkeypatch
):
    entered = tmp_path / "entered.txt"

    class Node:
        def execute(self, _ctx, passed_state):
            entered.write_text("physical body")
            return _ok_outcome(passed_state)

    def denied():
        raise OSError("subreaper capability denied")

    monkeypatch.setattr(retry_module, "_enable_child_subreaper", denied)
    before = _caller_subreaper_flag()
    with pytest.raises(RuntimeError, match="subreaper capability denied"):
        retry_module._execute_with_timeout_process(Node(), ctx, state, timeout_s=0.5)
    assert not entered.exists()
    assert _caller_subreaper_flag() == before


@pytest.mark.skipif(sys.platform != "linux", reason="actual Linux RLIMIT descriptor oracle")
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("preparation", ["cold", "synchronize", "shared"])
def test_worker_setup_fault_closes_real_pipe_descriptors(tmp_path, mode, preparation):
    """Every preparation failure releases owned Pipe ends, with traceback retained."""
    effects = tmp_path / "node.effects"
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("_retry_setup_probe.py")),
            mode,
            preparation,
            str(effects),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    assert observed["failure"]["type"] == "OSError", observed
    assert observed["failure"]["errno"] == 24, observed
    assert observed["retained_exception"] is True, observed
    assert observed["new_descriptors"] == [], observed
    assert observed["after"] == observed["before"], observed
    assert observed["body_effect"] is False, observed
    assert not effects.exists()


_BOUNDARY_ROUTES = [
    "sync",
    "async-sync",
    "sync-thread",
    "async-thread",
    "sync-fork",
    "async-fork",
    "genuine-async",
]


def _invoke_boundary(route, node, ctx, state, **kwargs):
    if route.startswith("async") or route == "genuine-async":
        return asyncio.run(execute_with_retry_async(node, ctx, state, **kwargs))
    return execute_with_retry_sync(node, ctx, state, **kwargs)


@pytest.mark.parametrize("route", _BOUNDARY_ROUTES)
@pytest.mark.parametrize(
    "kind",
    [
        "permanent",
        "provider_timeout",
        "returned_permanent",
        "custom_transient",
        "filtered_transient",
    ],
)
def test_canonical_retry_boundary_uses_actual_attempt_files(
    tmp_path, ctx, state, monkeypatch, route, kind
):
    """Error shape and boundary preserve category/code and actual retry count."""
    _select_timeout_test_route(monkeypatch, route)
    import contextvars

    attempt_file = tmp_path / "attempts.txt"
    owner = contextvars.ContextVar("run_boundary_owner", default="missing")
    token = owner.set("captured-owner")

    class ProviderError(ConnectionError):
        code = "provider.transient"

    class Node:
        def execute(self, passed_ctx, passed_state):
            with attempt_file.open("a") as stream:
                stream.write(owner.get() + "\n")
            attempt = len(attempt_file.read_text().splitlines())
            if attempt == 1:
                if kind == "permanent":
                    raise ValueError("same diagnostic")
                if kind == "provider_timeout":
                    raise TimeoutError("same diagnostic")
                if kind == "returned_permanent":
                    return _fail_outcome(passed_state, code="node.invalid_state")
                if kind in {"custom_transient", "filtered_transient"}:
                    raise ProviderError("same diagnostic")
            return _ok_outcome(passed_state)

    class AsyncNode(Node):
        async def execute_async(self, passed_ctx, passed_state):
            return self.execute(passed_ctx, passed_state)

    kwargs = dict(
        retry_policy=RetryPolicy(
            max_retries=1,
            backoff_base_s=0.1,
            jitter="none",
            retry_on=["provider.transient"] if kind == "custom_transient" else ["node.exception"],
        ),
        timeout_s=None if route in {"sync", "async-sync"} else 1.0,
        alias="canonical-boundary",
    )
    node = (AsyncNode if route == "genuine-async" else Node)()
    try:
        if kind in {"permanent", "filtered_transient"}:
            with pytest.raises(RetryExhaustedError):
                _invoke_boundary(route, node, ctx, state, **kwargs)
        else:
            outcome = _invoke_boundary(route, node, ctx, state, **kwargs)
            assert outcome.status == ("fail" if kind == "returned_permanent" else "ok")
    finally:
        owner.reset(token)
    expected = 2 if kind in {"provider_timeout", "custom_transient"} else 1
    assert attempt_file.read_text().splitlines() == ["captured-owner"] * expected


@pytest.mark.parametrize(
    "route", ["sync-thread", "async-thread", "sync-fork", "async-fork", "genuine-async"]
)
def test_whole_invocation_deadline_includes_retry_backoff(tmp_path, ctx, state, monkeypatch, route):
    """A retry cannot enter user code after its one invocation budget expired."""
    _select_timeout_test_route(monkeypatch, route)
    attempts = tmp_path / "attempts.txt"

    class Node:
        def execute(self, passed_ctx, passed_state):
            with attempts.open("a") as stream:
                stream.write("attempt\n")
            if len(attempts.read_text().splitlines()) == 1:
                raise ConnectionError("retryable provider failure")
            return _ok_outcome(passed_state)

    class AsyncNode(Node):
        async def execute_async(self, passed_ctx, passed_state):
            return self.execute(passed_ctx, passed_state)

    start = _time.monotonic()
    with pytest.raises(NodeTimeoutError):
        _invoke_boundary(
            route,
            (AsyncNode if route == "genuine-async" else Node)(),
            ctx,
            state,
            retry_policy=RetryPolicy(max_retries=2, backoff_base_s=1.0, jitter="none"),
            timeout_s=0.5,
            alias="single-deadline",
        )
    assert attempts.read_text().splitlines() == ["attempt"]
    assert _time.monotonic() - start < 1.2


def test_unconfigured_sync_bridge_has_no_implicit_timeout(ctx, state, monkeypatch):
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_DEFAULT_TIMEOUT_SECONDS", 0.005)

    class Node:
        def execute(self, passed_ctx, passed_state):
            _time.sleep(0.02)
            return _ok_outcome(passed_state)

    result = asyncio.run(
        execute_with_retry_async(
            Node(),
            ctx,
            state,
            retry_policy=RetryPolicy(),
            timeout_s=None,
            alias="explicit-unbounded",
        )
    )
    assert result.status == "ok"


def test_event_loop_block_cannot_publish_owned_write_after_deadline(tmp_path, ctx, state):
    effects = tmp_path / "owned.json"

    class Store:
        def put_json(self, payload, options):
            effects.write_text(json.dumps(payload))

    ctx.store = Store()

    class Node:
        async def execute_async(self, passed_ctx, passed_state):
            _time.sleep(0.04)
            passed_ctx.store.put_json({"late": True}, None)
            return _ok_outcome(passed_state)

    with pytest.raises(NodeTimeoutError):
        asyncio.run(
            execute_with_retry_async(
                Node(), ctx, state, retry_policy=RetryPolicy(), timeout_s=0.01, alias="blocked-loop"
            )
        )
    assert not effects.exists()


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_absolute_deadline_refuses_admission_after_expiry(tmp_path, ctx, state, mode):
    effects = tmp_path / "physical-body"

    class Node:
        def execute(self, passed_ctx, passed_state):
            effects.write_text("body")
            return _ok_outcome(passed_state)

    with pytest.raises(NodeTimeoutError):
        _invoke_boundary(
            mode,
            Node(),
            ctx,
            state,
            retry_policy=RetryPolicy(max_retries=1),
            timeout_s=1.0,
            deadline_monotonic=_time.monotonic() - 0.001,
            alias="expired-before-admission",
        )
    assert not effects.exists()


@pytest.mark.skipif(
    retry_module._timeout_worker_start_method() != "fork",
    reason="native Linux fork process admission required",
)
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_process_setup_cannot_admit_worker_after_absolute_deadline(
    tmp_path, ctx, state, monkeypatch, mode
):
    """A constructor delay must not admit even the supervisor after expiry."""
    effects = tmp_path / "physical-body"
    starts = []
    process_factory = retry_module._process_factory

    def delayed_factory(context):
        original = process_factory(context)

        def construct(**kwargs):
            process = original(**kwargs)
            start = process.start

            def observed_start():
                starts.append(process)
                start()

            process.start = observed_start
            _time.sleep(0.03)
            return process

        return construct

    class Node:
        def execute(self, passed_ctx, passed_state):
            effects.write_text("body")
            return _ok_outcome(passed_state)

    monkeypatch.setattr(retry_module, "_process_factory", delayed_factory)
    execute = (
        retry_module._execute_with_timeout_process
        if mode == "sync"
        else retry_module._execute_with_timeout_process_async
    )

    def invoke():
        result = execute(Node(), ctx, state, timeout_s=0.01)
        if mode == "async":
            return asyncio.run(result)
        return result

    with pytest.raises(NodeTimeoutError) as expired:
        invoke()
    assert expired.value.details["execution_state"] == "not_started"
    assert starts == []
    assert not effects.exists()


@pytest.mark.skipif(sys.platform != "linux", reason="native Linux owned-process supervisor")
def test_supervisor_scheduled_after_deadline_never_enters_node(tmp_path, ctx, state):
    """An admitted supervisor cannot admit node code after scheduling delay."""
    effects = tmp_path / "physical-body"

    class Node:
        def execute(self, passed_ctx, passed_state):
            effects.write_text("body")
            return _ok_outcome(passed_state)

    context = mp.get_context("fork")
    channel = retry_module._WorkerResultChannel(context)
    ready = context.Event()
    completed_at = context.Value("d", 0.0)
    cleanup_complete = context.Value("b", False)
    process = context.Process(
        target=retry_module._node_execute_supervisor,
        args=(
            Node(),
            ctx,
            state,
            channel,
            ready,
            completed_at,
            _time.monotonic() - 0.01,
            cleanup_complete,
        ),
    )
    try:
        process.start()
        channel.close_writer()
        process.join(timeout=2)
        assert not process.is_alive()
        assert process.exitcode == 0
        assert ready.is_set()
        assert cleanup_complete.value
        assert not effects.exists()
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        process.close()
        channel.close()


@pytest.mark.parametrize("termination", ["deadline", "cancellation"])
@pytest.mark.asyncio
async def test_queued_async_thread_attempt_never_enters_body_after_termination(
    tmp_path, ctx, state, monkeypatch, termination
):
    from polisyos.common.async_tools import _SharedExecutor

    _select_timeout_test_route(monkeypatch, "thread")
    executor = _SharedExecutor(max_workers=4)
    occupied = threading.Barrier(5)
    release = threading.Event()
    effects = tmp_path / "physical-body"

    def blocker():
        occupied.wait(timeout=2)
        release.wait(timeout=2)

    blockers = [executor.submit(blocker) for _ in range(4)]
    occupied.wait(timeout=2)
    monkeypatch.setattr(retry_module, "get_shared_executor", lambda: executor)

    class Node:
        def execute(self, passed_ctx, passed_state):
            effects.write_text("physical execution after owner return")
            return _ok_outcome(passed_state)

    try:
        task = asyncio.create_task(
            execute_with_retry_async(
                Node(),
                ctx,
                state,
                retry_policy=RetryPolicy(max_retries=2),
                timeout_s=0.03 if termination == "deadline" else 1.0,
                alias="queued",
            )
        )
        if termination == "cancellation":
            # Admit the real queued job before cancelling its async owner.
            for _ in range(100):
                if executor._work_queue.qsize() > 0:
                    break
                await asyncio.sleep(0.001)
            assert executor._work_queue.qsize() > 0
            task.cancel()
        with pytest.raises(
            NodeTimeoutError if termination == "deadline" else asyncio.CancelledError
        ):
            await task
        # Same-turn release falsifies deferred asyncio-only Future cancellation.
        release.set()
        for future in blockers:
            future.result(timeout=2)
        executor.shutdown(wait=True, cancel_futures=True)
        assert not effects.exists()
    finally:
        release.set()
        executor.shutdown(wait=True, cancel_futures=True)


@pytest.mark.skipif(
    retry_module._timeout_worker_start_method() != "fork",
    reason="control-exception transport is verified on the native Linux fork route",
)
@pytest.mark.parametrize("late", [False, True], ids=["before-deadline", "after-deadline"])
@pytest.mark.parametrize("control", ["SystemExit", "KeyboardInterrupt", "SystemExitUnsupported"])
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_real_process_preserves_control_exception_without_retry(tmp_path, mode, control, late):
    effects = tmp_path / "attempts"
    script = """import asyncio,json,multiprocessing,os,sys,time
from pathlib import Path
from unittest.mock import MagicMock
from polisyos.core.errors import PolicyOSError
from polisyos.scientist.orchestration.engine import retry as retry_module
from polisyos.scientist.orchestration.engine.retry import RetryPolicy, execute_with_retry_sync, execute_with_retry_async
from polisyos.scientist.orchestration.engine.state import ExperimentState
path=Path(sys.argv[1]); mode, control, late=sys.argv[2:]
class Node:
 def execute(self,ctx,state):
  with path.open('a') as stream:stream.write(json.dumps(dict(pid=os.getpid(),entered_at=time.monotonic()))+'\\n')
  if late=='yes':time.sleep(.75)
  if control=='SystemExit':raise SystemExit(17)
  if control=='SystemExitUnsupported':raise SystemExit(object())
  raise KeyboardInterrupt()
# This witness is about control propagation from a running worker. Resolve the
# actual cold parent/worker context imports before the unchanged .5s deadline.
# Cold admission expiry and late worker admission have separate negative tests.
ctx=MagicMock(); state=ExperimentState(run_id='R_control')
preflight=time.monotonic()
retry_module._build_fork_worker_receipt_binding(Node(),ctx,state,alias='actual-control',timeout_s=.5,dispatch_params=None)
retry_module._node_facing_context(ctx)
preflight_s=time.monotonic()-preflight
kwargs=dict(retry_policy=RetryPolicy(max_retries=2),timeout_s=.5,alias='actual-control')
invoked_at=time.monotonic()
try:
 if mode=='sync':execute_with_retry_sync(Node(),ctx,state,**kwargs)
 else:asyncio.run(execute_with_retry_async(Node(),ctx,state,**kwargs))
except BaseException as exc:
 attempts=[json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
 print(json.dumps(dict(type=type(exc).__name__,code=getattr(exc,'code',None),cause_code=getattr(exc.__cause__,'code',None),cause_category=getattr(exc.__cause__,'category',None),details=exc.to_dict()['details'] if isinstance(exc,PolicyOSError) else {},attempts=attempts,parent_pid=os.getpid(),invoked_at=invoked_at,preflight_s=preflight_s,live_children=[p.pid for p in multiprocessing.active_children()])))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(effects), mode, control, "yes" if late else "no"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    if late:
        assert observed["type"] == "NodeTimeoutError", observed
        assert observed["details"]["cleanup_complete"] is True, observed
    elif control == "SystemExitUnsupported":
        assert observed["type"] == "RetryExhaustedError", observed
        assert observed["cause_code"] == "node.control_unsupported", observed
        assert observed["cause_category"] == "fatal", observed
    else:
        assert observed["type"] == control, observed
        assert observed["code"] == (17 if control == "SystemExit" else None), observed
    assert len(observed["attempts"]) == 1, observed
    attempt = observed["attempts"][0]
    assert attempt["pid"] != observed["parent_pid"], observed
    assert 0 <= attempt["entered_at"] - observed["invoked_at"] < 0.5, observed
    assert observed["live_children"] == []


def test_expired_retry_budget_preserves_spend_without_failed_branch(
    tmp_path, ctx, state, monkeypatch, controlled_thread_deadline
):
    from decimal import Decimal
    from types import SimpleNamespace

    started = threading.Event()
    effects = tmp_path / "attempts"

    class Node:
        spec = SimpleNamespace(
            metadata=SimpleNamespace(component_id="actual-costed-retry"),
            state_writes=["params", "budgets"],
        )

        def execute(self, passed_ctx, passed_state):
            started.set()
            with effects.open("a") as stream:
                stream.write("attempt\n")
            passed_state.params["failed_change"] = True
            passed_state.budgets["run_spent_usd"] = Decimal("0.25")
            return _fail_outcome(passed_state)

    _select_timeout_test_route(monkeypatch, "thread")
    controlled_thread_deadline.observe_first_attempt(started, wait_for_completion=True)
    with pytest.raises(NodeTimeoutError):
        execute_with_retry_sync(
            Node(),
            ctx,
            state,
            retry_policy=RetryPolicy(max_retries=2, backoff_base_s=0.1, jitter="none"),
            timeout_s=0.03,
            alias="spent-without-continuation",
        )

    clock = controlled_thread_deadline
    assert clock.started_observed
    assert clock.deadline is not None
    assert clock.worker_completed_at is not None
    assert clock.worker_completed_at < clock.deadline
    assert len(clock.backoff_requests) == 1
    requested_delay, backoff_deadline = clock.backoff_requests[0]
    assert requested_delay == pytest.approx(0.1)
    assert backoff_deadline == clock.deadline
    assert clock.sleep_calls == [pytest.approx(0.03)]
    assert clock.expired_deadline == clock.deadline
    assert effects.read_text().splitlines() == ["attempt"]
    assert state.params == {}
    assert state.budgets["run_spent_usd"] == Decimal("0.25")


@pytest.mark.asyncio
async def test_unbounded_thread_cancellation_revokes_owned_writes_but_cannot_stop_raw_effects(
    tmp_path, ctx, state, monkeypatch
):
    from polisyos.common import async_tools

    executor = async_tools._SharedExecutor(max_workers=4)
    monkeypatch.setattr(async_tools, "get_shared_executor", lambda: executor)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    raw = tmp_path / "raw-effect"
    owned = tmp_path / "owned-effect"

    class Store:
        def put_json(self, payload, options):
            owned.write_text("owner write admitted")

    ctx.store = Store()

    class Node:
        def execute(self, passed_ctx, passed_state):
            started.set()
            release.wait(timeout=2)
            raw.write_text("already running arbitrary user effect")
            with pytest.raises(retry_module._AttemptWriteDeniedError) as denied:
                passed_ctx.store.put_json({}, None)
            assert denied.value.code == "attempt_write_revoked"
            assert denied.value.reason_code == "attempt_write_revoked"
            finished.set()
            return _ok_outcome(passed_state)

    try:
        task = asyncio.create_task(
            execute_with_retry_async(
                Node(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=None,
                alias="unbounded-cancel",
            )
        )
        for _ in range(100):
            if started.is_set():
                break
            await asyncio.sleep(0.001)
        assert started.is_set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        assert finished.wait(timeout=2)
        assert raw.read_text() == "already running arbitrary user effect"
        assert not owned.exists()
    finally:
        release.set()
        executor.shutdown(wait=True, cancel_futures=True)


def test_completed_provider_error_cannot_emit_retry_after_publication_deadline(tmp_path, state):
    from polisyos.core.trace.record import TraceRecord
    from polisyos.core.trace.sink import JsonlTraceSink
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

    trace_path = tmp_path / "trace.jsonl"
    run = RunContext(
        store=MagicMock(),
        trace=JsonlTraceSink(trace_path),
        run_manifest=RunManifest(
            run_id="R_late_error",
            registry_bundle=ArtifactRef(
                artifact_id="sha256:" + "0" * 64, kind="registry", media_type="application/json"
            ),
        ),
    )
    context = ExecutionContext(store=run.store, run=run, logger=MagicMock())

    class Node:
        async def execute_async(self, passed_ctx, passed_state):
            # The provider finishes on time. Its consumer wakes only after this
            # real event-loop callback has consumed the publication budget.
            asyncio.get_running_loop().call_soon(_time.sleep, 0.04)
            raise ConnectionError("provider completed before blocked delivery")

    with pytest.raises(NodeTimeoutError):
        asyncio.run(
            execute_with_retry_async(
                Node(),
                context,
                state,
                retry_policy=RetryPolicy(max_retries=1, backoff_base_s=0.1),
                timeout_s=0.01,
                alias="late-error",
            )
        )
    records = (
        [TraceRecord.model_validate_json(line) for line in trace_path.read_text().splitlines()]
        if trace_path.exists()
        else []
    )
    assert [record for record in records if record.event == "NODE_RETRY"] == []


@pytest.mark.parametrize(
    "payload", [{"kind": "unknown"}, {}, {"kind": "SystemExit", "code": {"opaque": True}}]
)
def test_real_framed_control_reject_is_typed_terminal(payload):
    channel = retry_module._WorkerResultChannel(mp.get_context("fork"))
    try:
        channel.put(("control", payload))
        status, received = channel.get(timeout=0.1)
        assert status == "control"
        error = retry_module._worker_control_error(received)
        assert isinstance(error, RuntimeError)
        assert error.category == "fatal"
        assert error.code == "node.control_protocol"
        assert (
            retry_module._should_retry_exception(
                error, RetryPolicy(max_retries=1, retry_on=["node.control_protocol"])
            )
            is False
        )
    finally:
        channel.close()


_SPEND_ROUTES = (
    "sync-direct",
    "sync-fork",
    "sync-thread",
    "async-fork",
    "async-thread",
    "async-provider",
    "async-provider-unbounded",
    "async-sync-unbounded",
)


@pytest.mark.parametrize("route", _SPEND_ROUTES)
@pytest.mark.parametrize("terminal", [False, True])
def test_completed_failed_spend_settles_without_ordinary_branch(
    route, terminal, tmp_path, monkeypatch
):
    from decimal import Decimal

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.protocol import NodeSpec

    _select_timeout_test_route(monkeypatch, route)
    effects = tmp_path / "attempts.jsonl"
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id="R_spend")
    context = ExecutionContext(store=store, run=run, logger=MagicMock())
    initial = ExperimentState(run_id="R_spend", budgets={"llm_spent_usd": Decimal(5)})

    class Provider:
        spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.known_spend@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="known spend",
                description="Real completed failure settlement",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["budgets", "params"],
            state_writes=["budgets", "params"],
        )

        def execute(self, passed_ctx, passed_state):
            ordinal = len(effects.read_text().splitlines()) + 1 if effects.exists() else 1
            before = passed_state.budgets["llm_spent_usd"]
            passed_state.budgets["llm_spent_usd"] += Decimal(2 if ordinal == 1 else 1)
            with effects.open("a") as stream:
                stream.write(
                    json.dumps(
                        {
                            "ordinal": ordinal,
                            "pid": os.getpid(),
                            "before": str(before),
                            "dirty_before": passed_state.params.get("failed_dirty"),
                        }
                    )
                    + "\n"
                )
            if ordinal == 1 or terminal:
                passed_state.params["failed_dirty"] = "must not publish"
                raise TimeoutError("completed provider error with known spend")
            passed_state.params["success"] = True
            return _ok_outcome(passed_state)

    class AsyncProvider(Provider):
        async def execute_async(self, passed_ctx, passed_state):
            await asyncio.sleep(0)
            return self.execute(passed_ctx, passed_state)

    node = AsyncProvider() if "provider" in route else Provider()
    finite = route not in {"sync-direct", "async-provider-unbounded", "async-sync-unbounded"}
    kwargs = dict(
        retry_policy=RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none"),
        timeout_s=2.0 if finite else None,
        deadline_monotonic=_time.monotonic() + 2 if finite else None,
        alias=route,
    )
    if route in {"sync-fork", "async-fork"}:
        kwargs["dispatch_params"] = {}

    def invoke_with(call_kwargs):
        if route.startswith("sync-"):
            return execute_with_retry_sync(node, context, initial, **call_kwargs)
        return asyncio.run(execute_with_retry_async(node, context, initial, **call_kwargs))

    def invoke():
        return invoke_with(kwargs)

    if route in {"sync-fork", "async-fork"}:
        unbound_kwargs = {**kwargs, "dispatch_params": None}
        with pytest.raises(NodeTimeoutError) as unbound:
            invoke_with(unbound_kwargs)
        assert unbound.value.code == "node.timeout_worker_unsupported"
        assert unbound.value.details["reason"] == "fork_dispatch_params_not_bound"
        assert not effects.exists()

    if terminal:
        with pytest.raises(RetryExhaustedError) as caught:
            invoke()
        settled = initial
        if "fork" not in route:
            assert isinstance(caught.value.__cause__, TimeoutError)
    else:
        settled = invoke().state
        assert settled.params == {"success": True}
        assert initial.budgets["llm_spent_usd"] == Decimal(5)
    attempts = [json.loads(line) for line in effects.read_text().splitlines()]
    assert [entry["ordinal"] for entry in attempts] == [1, 2]
    assert [entry["before"] for entry in attempts] == ["5", "5"]
    assert [entry["dirty_before"] for entry in attempts] == [None, None]
    assert settled.budgets["llm_spent_usd"] == Decimal(8)
    assert "failed_dirty" not in settled.params
    from polisyos.core.trace.record import TraceRecord

    assert run._trace_path is not None
    records = [
        TraceRecord.model_validate_json(line) for line in run._trace_path.read_text().splitlines()
    ]
    retry_events = [record for record in records if record.event == "NODE_RETRY"]
    assert len(retry_events) == 1
    assert retry_events[0].metrics["failed_cost_usd"] == 2.0
    if terminal:
        dead_letters = [record for record in records if record.event == "NODE_DEAD_LETTER"]
        assert len(dead_letters) == 1
        assert dead_letters[0].metrics["failed_cost_usd"] == 3.0
        persisted = json.loads(store.get_bytes(dead_letters[0].refs.outputs[0]))
        assert persisted["attempts"] == 2
        assert persisted["alias"] == route
    assert mp.active_children() == []


@pytest.mark.parametrize("corruption", ["version", "hash", "identity", "negative", "other-budget"])
def test_real_framed_failed_spend_wire_rejects_corrupt_projection(corruption):
    import base64
    from decimal import Decimal

    from polisyos.scientist.orchestration.engine.runner.serialization import (
        DeserializationError,
        serialize_state_safe,
    )

    budgets = {"llm_spent_usd": Decimal(2)}
    run_id = "R_spend"
    if corruption == "identity":
        run_id = "R_other"
    elif corruption == "negative":
        budgets["llm_spent_usd"] = Decimal(-2)
    elif corruption == "other-budget":
        budgets = {"unrelated_budget": Decimal(2)}
    wire, _ = serialize_state_safe(ExperimentState(run_id=run_id, budgets=budgets))
    if corruption == "version":
        wire = b"\x02" + wire[1:]
    elif corruption == "hash":
        wire = wire[:-1] + bytes([wire[-1] ^ 1])
    payload = {
        "message": "provider error",
        "category": "transient",
        "code": "node.exception",
        "known_spend_state_v1": base64.b64encode(wire).decode("ascii"),
    }
    channel = retry_module._WorkerResultChannel(mp.get_context("fork"))
    try:
        channel.put(("error", payload))
        status, received = channel.get(timeout=0.1)
        assert status == "error"
        rejection = DeserializationError if corruption in {"version", "hash"} else ValueError
        with pytest.raises(rejection):
            retry_module._worker_node_error(received, expected_run_id="R_spend")
    finally:
        channel.close()


@pytest.mark.parametrize("route", ["thread", "async"])
def test_late_failed_spend_stays_unknown_after_owner_timeout(
    route, tmp_path, ctx, monkeypatch, controlled_thread_deadline
):
    from decimal import Decimal

    initial = ExperimentState(run_id="R_late_spend", budgets={"llm_spent_usd": Decimal(5)})
    release, started, finished = threading.Event(), threading.Event(), threading.Event()
    effects = tmp_path / "late-spend"
    started_at: list[float] = []

    class Node:
        def body(self, passed_state):
            passed_state.budgets["llm_spent_usd"] += Decimal(2)
            effects.write_text(str(passed_state.budgets["llm_spent_usd"]))
            finished.set()
            raise TimeoutError("late completed failure")

        def execute(self, passed_ctx, passed_state):
            if route == "thread":
                started_at.append(retry_module.time.monotonic())
            started.set()
            release.wait(timeout=2)
            return self.body(passed_state)

    class AsyncNode(Node):
        async def execute_async(self, passed_ctx, passed_state):
            started.set()
            while not release.is_set():
                await asyncio.sleep(0.001)
            return self.body(passed_state)

    if route == "thread":
        _select_timeout_test_route(monkeypatch, route)
        controlled_thread_deadline.observe_first_attempt(started, expire_after_start=True)

    async def invoke():
        with pytest.raises(NodeTimeoutError):
            await execute_with_retry_async(
                AsyncNode() if route == "async" else Node(),
                ctx,
                initial,
                retry_policy=RetryPolicy(max_retries=1),
                timeout_s=0.03,
                alias="late-spend",
            )
        assert started.is_set()
        assert not finished.is_set()
        assert not effects.exists()
        if route == "thread":
            assert len(started_at) == 1
            assert controlled_thread_deadline.expired_deadline is not None
            assert started_at[0] < controlled_thread_deadline.expired_deadline
            assert controlled_thread_deadline.current >= controlled_thread_deadline.expired_deadline
            assert controlled_thread_deadline.future is not None
            assert not controlled_thread_deadline.future.done()
        assert initial.budgets["llm_spent_usd"] == Decimal(5)
        release.set()
        for _ in range(100):
            if finished.is_set():
                break
            await asyncio.sleep(0.001)
        assert finished.is_set()
        if route == "thread":
            assert controlled_thread_deadline.future is not None
            for _ in range(100):
                if controlled_thread_deadline.future.done():
                    break
                await asyncio.sleep(0.001)
            assert controlled_thread_deadline.future.done()
        else:
            await asyncio.sleep(0)
        assert effects.read_text() == "7"
        assert initial.budgets["llm_spent_usd"] == Decimal(5)

    try:
        asyncio.run(invoke())
    finally:
        release.set()


@pytest.mark.asyncio
async def test_unbounded_sync_fast_path_preserves_original_error_and_known_spend(ctx):
    from decimal import Decimal

    initial = ExperimentState(run_id="R_fast_spend", budgets={"llm_spent_usd": Decimal(5)})
    original = TimeoutError("known provider failure")

    class Node:
        def execute(self, passed_ctx, passed_state):
            passed_state.budgets["llm_spent_usd"] += Decimal(2)
            passed_state.params["failed_dirty"] = True
            raise original

    with pytest.raises(TimeoutError) as caught:
        await execute_with_retry_async(
            Node(), ctx, initial, retry_policy=RetryPolicy(), timeout_s=None, alias="fast-spend"
        )
    assert caught.value is original
    assert initial.budgets["llm_spent_usd"] == Decimal(7)
    assert initial.params == {}


def test_attempt_view_stages_only_typed_worker_receipt_run_writes(tmp_path):
    """Stage input/output through an attempt facade without exposing parent lifecycle."""
    import logging

    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.worker_lifecycle import WorkerLifecycleCapability
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

    class MemoryTrace:
        def __init__(self):
            self.records = []

        def emit(self, record):
            self.records.append(record.model_copy(deep=True))

        def emit_many(self, records):
            self.records.extend(record.model_copy(deep=True) for record in records)

    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    run_id = "R_attempt_worker_receipt_composition"
    parent_run = RunContext.start(
        store=store,
        registry_bundle=registry.bundle_ref,
        run_id=run_id,
        run_dir=store.root / "runs" / run_id,
    )
    parent_capability = WorkerLifecycleCapability.for_parent(parent_run)
    snapshot = parent_capability.snapshot()
    invocation_id = "a" * 64
    dispatch_sha256 = "b" * 64
    binding = parent_capability.bind_dispatch(
        invocation_id=invocation_id,
        dispatch_sha256=dispatch_sha256,
    )
    staged = MemoryTrace()
    worker_capability = WorkerLifecycleCapability.for_worker_context(
        store=store,
        trace=staged,
        run_manifest=snapshot.run_manifest,
        trace_path=snapshot.trace_path,
        owner_snapshot_ref=snapshot.owner_snapshot_ref,
        access_scope=snapshot.access_scope,
        tenant_id=snapshot.tenant_id,
        cell_id=snapshot.cell_id,
        invocation_id=invocation_id,
        dispatch_sha256=dispatch_sha256,
    )
    worker_view = worker_capability.worker_view()
    worker_context = ExecutionContext(
        store=store,
        run=worker_view,
        logger=logging.getLogger("test.attempt_worker_receipt_composition"),
    )
    inner_authority = retry_module._AttemptAuthority(deadline_monotonic=_time.monotonic() + 5.0)
    attempt_context = retry_module._build_attempt_context(
        worker_context,
        inner_authority,
    )
    outer_authority = retry_module._AttemptAuthority(deadline_monotonic=_time.monotonic() + 5.0)
    nested_attempt_context = retry_module._AttemptContext(
        attempt_context,
        outer_authority,
    )
    node_context = retry_module._node_facing_context(nested_attempt_context)
    assert retry_module._resolve_exact_worker_run_view(nested_attempt_context.run) is worker_view
    assert retry_module._resolve_exact_worker_run_view(worker_view) is worker_view

    input_ref = store.put_json(
        {"input": "staged"},
        PutOptions(
            kind="scientist.test.attempt_worker_input",
            media_type="application/json",
            schema=SchemaInfo(name="scientist.test.AttemptWorkerInput", version="1.0"),
        ),
        return_selected_profile=True,
    )
    output_ref = store.put_json(
        {"output": "staged"},
        PutOptions(
            kind="scientist.test.attempt_worker_output",
            media_type="application/json",
            schema=SchemaInfo(name="scientist.test.AttemptWorkerOutput", version="1.0"),
        ),
        return_selected_profile=True,
    )
    node_context.run.add_input(input_ref)
    node_context.run.add_output(output_ref)
    assert [record.event for record in staged.records] == [
        "RUN_INPUT_ADDED",
        "RUN_OUTPUT_ADDED",
    ]
    assert parent_run.run_manifest.inputs == []
    assert parent_run.run_manifest.outputs == []

    for name in (
        "finalize",
        "suspend_for_resume",
        "merge_worker_events",
        "_active_lease",
        "_owner_snapshot_ref",
        "_worker_lifecycle_capability",
        "_EngineNodeRunView__target",
        "_EngineNodeRunView__stage_worker_receipt_writes",
    ):
        with pytest.raises(AttributeError):
            getattr(node_context.run, name)
    with pytest.raises(AttributeError):
        RunContext.add_output(node_context.run, output_ref)
    for operation in (RunContext.finalize, RunContext.suspend_for_resume):
        with pytest.raises(AttributeError):
            operation(node_context.run)
    with pytest.raises(AttributeError):
        RunContext.merge_worker_events(
            node_context.run,
            invocation_id=invocation_id,
            dispatch_sha256=dispatch_sha256,
            owner_snapshot_ref=snapshot.owner_snapshot_ref,
            records=staged.records,
        )

    parent_capability.admit_worker_events(binding, staged.records)
    assert parent_run.run_manifest.inputs == [input_ref]
    assert parent_run.run_manifest.outputs == [output_ref]
    assert parent_run.read_runtime_owner_output_refs() == (output_ref,)

    before_revocation = len(staged.records)
    inner_authority.revoke()
    node_context.run.add_input(input_ref)
    node_context.run.add_output(output_ref)
    outer_authority.revoke()
    node_context.run.add_input(input_ref)
    node_context.run.add_output(output_ref)
    expired = retry_module._AttemptAuthority(deadline_monotonic=_time.monotonic() - 1.0)
    expired_context = retry_module._node_facing_context(
        retry_module._build_attempt_context(worker_context, expired)
    )
    expired_context.run.add_input(input_ref)
    expired_context.run.add_output(output_ref)
    assert len(staged.records) == before_revocation

    class SiblingAttemptRunFacade(retry_module._AttemptRunFacade):
        pass

    sibling = SiblingAttemptRunFacade(
        worker_view,
        retry_module._AttemptAuthority(deadline_monotonic=_time.monotonic() + 5.0),
        store,
    )
    assert retry_module._resolve_exact_worker_run_view(sibling) is None
    forged = retry_module._AttemptRunFacade(
        object(),
        retry_module._AttemptAuthority(deadline_monotonic=_time.monotonic() + 5.0),
        store,
    )
    assert retry_module._resolve_exact_worker_run_view(forged) is None
    cyclic = retry_module._AttemptRunFacade(
        worker_view,
        retry_module._AttemptAuthority(deadline_monotonic=_time.monotonic() + 5.0),
        store,
    )
    object.__setattr__(cyclic, "_target", cyclic)
    assert retry_module._resolve_exact_worker_run_view(cyclic) is None
    deep: object = worker_view
    for _ in range(retry_module._MAX_EXACT_WORKER_RUN_FACADE_DEPTH + 1):
        deep = retry_module._AttemptRunFacade(
            deep,
            retry_module._AttemptAuthority(deadline_monotonic=_time.monotonic() + 5.0),
            store,
        )
    assert retry_module._resolve_exact_worker_run_view(deep) is None

    ordinary_attempt = retry_module._build_attempt_context(
        ExecutionContext(
            store=store,
            run=parent_run,
            logger=logging.getLogger("test.ordinary_attempt_run"),
        ),
        retry_module._AttemptAuthority(deadline_monotonic=_time.monotonic() + 5.0),
    )
    ordinary_node = retry_module._node_facing_context(ordinary_attempt)
    for name in ("add_input", "add_output"):
        with pytest.raises(AttributeError):
            getattr(ordinary_node.run, name)
    with pytest.raises(AttributeError, match="add_output"):
        type(ordinary_node.run).add_output(ordinary_node.run, output_ref)

    with pytest.raises(TypeError, match="created by the executor"):
        retry_module._EngineNodeRunView(
            worker_view,
            _token=object(),
            stage_worker_receipt_writes=True,
        )
    with pytest.raises(TypeError, match="requires the typed attempt view"):
        retry_module._EngineNodeRunView(
            worker_view,
            _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
            stage_worker_receipt_writes=True,
        )
    with pytest.raises(TypeError, match="requires the typed attempt view"):
        retry_module._EngineNodeRunView(
            ordinary_attempt.run,
            _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
            stage_worker_receipt_writes=True,
        )
    parent_run.suspend_for_resume()


def test_engine_node_run_view_exposes_only_artifact_tenant_context_reader() -> None:
    from types import SimpleNamespace

    from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo

    expected = ArtifactTenantContextInfo(
        tenant_id="tenant-facade-reader",
        cell_id="cell-facade-reader",
    )
    calls: list[str] = []

    def read_context() -> ArtifactTenantContextInfo:
        calls.append("read")
        return expected

    view = retry_module._EngineNodeRunView(
        SimpleNamespace(artifact_tenant_context=read_context),
        _token=retry_module._ENGINE_NODE_RUN_VIEW_TOKEN,
    )

    assert view.artifact_tenant_context() == expected
    assert calls == ["read"]
    with pytest.raises(AttributeError):
        _ = view._owner_snapshot_ref
