"""Candidate replay's occurrence-independent seed schedule binding."""

import hashlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import security
from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.quality.n5_replay_appointment import (
    N5BlindReplayLaunchSpecV2,
    N5ReplayDeploymentConfig,
    N5ReplayPublicKey,
    N5ReplayScope,
)
from polisyos.runtime.quality.n5_replay_execution import (
    N5BlindReplayAction,
    N5OriginalProducerAction,
    _begin_attempt,
    _blind_action_bytes,
    _open_diagnostic_budget,
    _process_group_quiescent,
    _read_blind_action,
    _require_observed_executor,
    _run_managed_worker,
    _settle_attempt,
    _worker_result_payload,
    _WorkerLifecycleError,
    execute_blind_n5_replay,
    execute_original_n5_producer,
    n5_replay_seed_schedule_hash,
    preflight_candidate_n5_replay,
)


def test_seed_schedule_ignores_occurrence_labels_but_detects_changed_seeds() -> None:
    first = SimpleNamespace(seed=7, replications=3, run_id="old", objective="first")
    later = SimpleNamespace(seed=7, replications=3, run_id="new", objective="second")
    changed_seed = SimpleNamespace(seed=8, replications=3, run_id="old", objective="first")
    changed_count = SimpleNamespace(seed=7, replications=2, run_id="old", objective="first")
    expected = n5_replay_seed_schedule_hash(first)
    assert n5_replay_seed_schedule_hash(later) == expected
    assert n5_replay_seed_schedule_hash(changed_seed) != expected
    assert n5_replay_seed_schedule_hash(changed_count) != expected


def test_worker_result_transport_ignores_logs_but_refuses_ambiguity() -> None:
    marker = "POLISYOS_N5_WORKER_RESULT="
    assert _worker_result_payload("registered engine\n" + marker + '{"pid":1}\n') == '{"pid":1}'
    with pytest.raises(ValueError, match="worker_result_not_established"):
        _worker_result_payload("registered engine\n")
    with pytest.raises(ValueError, match="worker_result_not_established"):
        _worker_result_payload(marker + "{}\n" + marker + "{}\n")


def _spec() -> N5BlindReplayLaunchSpecV2:
    digest = "sha256:" + "a" * 64

    def ref(kind: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=digest,
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256=digest,
        )

    scope = N5ReplayScope(
        tenant_id="tenant", cell_id="cell", accepting_organization="institution", scope_id="scope"
    )
    return N5BlindReplayLaunchSpecV2(
        scope=scope,
        numerical_intent_ref=ref("intent"),
        numerical_intent_hash=digest,
        selected_candidate_simulation_n5_input_ref=ref(
            "runtime.quality.candidate_simulation_n5_input"
        ),
        source_run_id="source",
        source_job_id="source-job",
        original_run_id="original",
        original_job_id="original-job",
        tenant_id="tenant",
        cell_id="cell",
        declared_numerical_intent_content_hash=digest,
        declared_callable_content_hash=digest,
        production_image_ref=ref("runtime.quality.n5_production_image"),
        production_image_content_hash=digest,
        prepared_configuration_ref=ref("runtime.quality.n5_prepared_configuration"),
        prepared_configuration_content_hash=digest,
        prepared_configuration_hash=digest,
        execution_profile_ref=ref("profile"),
        launcher_profile_ref=ref("launcher"),
        comparator_ref=ref("comparator"),
        tier="STRICT_CPU",
        seed_schedule_hash=digest,
        planned_physical_units=1,
        replay_run_id="replay",
        replay_job_id="replay-job",
    )


def test_unappointed_child_cannot_open_store_or_ledger(tmp_path: Path) -> None:
    action = N5BlindReplayAction(
        launch_spec=_spec(),
        demonstration_trust=N5ReplayDeploymentConfig(),
        component_provenance_ref=_spec().execution_profile_ref,
        cas_root=str(tmp_path / "cas"),
        diagnostic_ledger_path=str(tmp_path / "ledger"),
        quota_units=1,
        attempt_number=1,
    )
    with pytest.raises(ValueError, match="demonstration_trust_not_established"):
        execute_blind_n5_replay(action)
    assert not (tmp_path / "cas").exists()
    assert not (tmp_path / "ledger").exists()
    assert "original_result_ref" not in action.model_dump(mode="json")


def test_blind_action_roundtrip_retains_exact_bytes_and_no_original_result(tmp_path: Path) -> None:
    from polisyos.core import artifacts
    from polisyos.core.canon import CanonSpec

    action = N5BlindReplayAction(
        launch_spec=_spec(),
        demonstration_trust=N5ReplayDeploymentConfig(
            trusted_keys=(
                N5ReplayPublicKey(
                    identity="issuer",
                    organization="institution",
                    function="control",
                    public_key_path=tmp_path / "issuer.pem",
                    roles=("appointment_issuer",),
                ),
            ),
            trust_root_class="demonstration_test_root",
        ),
        component_provenance_ref=_spec().execution_profile_ref,
        cas_root=str(tmp_path / "cas"),
        diagnostic_ledger_path=str(tmp_path / "ledger"),
        quota_units=1,
        attempt_number=1,
    )
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    raw = _blind_action_bytes(action)
    ref = store.put_json(
        action.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="runtime.quality.n5_blind_replay_action",
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=action.schema_version, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
        return_selected_profile=True,
    )
    digest = security.raw_content_hash(raw)
    assert store.get_bytes(ref) == raw
    assert _read_blind_action(store, ref, digest) == action
    for forbidden in (
        "original_execution_ref",
        "original_result_ref",
        "numerical_result_projection_hash",
    ):
        assert forbidden not in raw.decode("utf-8")
    with pytest.raises(ValueError, match="action_ref_invalid"):
        _read_blind_action(store, ref, "sha256:" + "b" * 64)


def test_original_producer_requires_a_distinct_job_and_run(tmp_path: Path) -> None:
    spec = _spec()
    fields = {
        "source_input_ref": spec.selected_candidate_simulation_n5_input_ref,
        "source_run_id": "source-run",
        "source_job_id": "source-job",
        "producer_run_id": "producer-run",
        "producer_job_id": "producer-job",
        "tenant_id": "tenant",
        "cell_id": "cell",
        "cas_root": str(tmp_path / "cas"),
        "ledger_path": str(tmp_path / "ledger"),
        "quota_units": 2,
    }
    assert N5OriginalProducerAction.model_validate(fields).producer_run_id == "producer-run"
    with pytest.raises(ValueError, match="source_producer_scope_invalid"):
        N5OriginalProducerAction.model_validate({**fields, "producer_run_id": "source-run"})
    with pytest.raises(ValueError, match="source_producer_scope_invalid"):
        N5OriginalProducerAction.model_validate({**fields, "producer_job_id": "source-job"})


def test_original_producer_refuses_an_existing_ledger_without_writing(tmp_path: Path) -> None:
    ledger = tmp_path / "original-seven-one-ledger.json"
    before = b"existing original ledger bytes"
    ledger.write_bytes(before)
    spec = _spec()
    action = N5OriginalProducerAction(
        source_input_ref=spec.selected_candidate_simulation_n5_input_ref,
        source_run_id="source-run",
        source_job_id="source-job",
        producer_run_id="producer-run",
        producer_job_id="producer-job",
        tenant_id="tenant",
        cell_id="cell",
        cas_root=str(tmp_path / "cas"),
        ledger_path=str(ledger),
        quota_units=2,
    )
    with pytest.raises(ValueError, match="original_ledger_not_fresh"):
        execute_original_n5_producer(action)
    assert ledger.read_bytes() == before
    assert not (tmp_path / "cas").exists()


def test_partial_plan_and_changed_source_ref_refuse_before_artifact_reads(tmp_path: Path) -> None:
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from polisyos.runtime.quality.n5_candidate_content import CandidateN5ContentRun
    from tests.unit.runtime.quality.test_n5_candidate_content import _replay_test_binding

    spec = _spec()
    _, budget = _replay_test_binding(tmp_path, spec.selected_candidate_simulation_n5_input_ref)
    controller = JointSimulationHorizonController(producer_budget_observer=budget)
    scope = CandidateN5ContentRun(
        controller=controller,
        request=object(),
        input_ref=spec.selected_candidate_simulation_n5_input_ref,
    )
    scope.capture = object()
    scope.configuration = object()
    scope.production_image = object()
    scope.profile = object()
    scope.planned_units = ()
    with pytest.raises(ValueError, match="selected_plan_mismatch"):
        preflight_candidate_n5_replay(scope=scope, spec=spec, store=object(), budget=budget)
    scope.input_ref = spec.selected_candidate_simulation_n5_input_ref.model_copy(
        update={"artifact_id": "sha256:" + "b" * 64}
    )
    scope.planned_units = (("physical-unit", 7),)
    with pytest.raises(ValueError, match="selected_plan_mismatch"):
        preflight_candidate_n5_replay(scope=scope, spec=spec, store=object(), budget=budget)


def test_infrastructure_retry_keeps_charged_units_and_mismatch_is_final(tmp_path: Path) -> None:
    spec = _spec()
    key = "a" * 64
    first = _begin_attempt(tmp_path, key=key, spec=spec, quota=3, limit=2)
    observer, middleware = _open_diagnostic_budget(spec, tmp_path / "diagnostic-ledger.json", 3)
    operation = hashlib.sha256(b"partial-operation").hexdigest()
    request = hashlib.sha256(b"partial-request").hexdigest()
    reservation = observer.reserve_invocation(operation, request)
    assert reservation is not None
    observer.finish_invocation(operation, request, "failed")
    ledger_hash = security.raw_content_hash((tmp_path / "diagnostic-ledger.json").read_bytes())
    _settle_attempt(
        tmp_path,
        first,
        status="infrastructure_error",
        child_pid=42,
        ledger_hash=ledger_hash,
        ledger_revision=middleware.snapshot_safe().revision,
    )
    second = _begin_attempt(tmp_path, key=key, spec=spec, quota=3, limit=2)
    assert second.attempt_number == 2
    reopened, middleware = _open_diagnostic_budget(spec, tmp_path / "diagnostic-ledger.json", 3)
    assert reopened.admit_diagnostic_invocation_only().protected_remaining_units == 2
    assert middleware.snapshot_safe().invocation_reservations[operation].status == "failed"
    executed = _settle_attempt(
        tmp_path,
        second,
        status="executed",
        child_pid=43,
        executor_pid=44,
        executor_created_us=123,
        execution_ref=spec.execution_profile_ref,
        ledger_hash=security.raw_content_hash((tmp_path / "diagnostic-ledger.json").read_bytes()),
        ledger_revision=middleware.snapshot_safe().revision,
    )
    recovered = _begin_attempt(tmp_path, key=key, spec=spec, quota=3, limit=2)
    assert recovered == executed  # Recovery reuses the execution; it does not issue attempt three.
    _settle_attempt(tmp_path, recovered, status="mismatch", comparison_ref=spec.comparator_ref)
    with pytest.raises(ValueError, match="attempt_not_retryable"):
        _begin_attempt(tmp_path, key=key, spec=spec, quota=3, limit=2)


def test_unknown_crash_never_automatically_retries(tmp_path: Path) -> None:
    spec = _spec()
    _begin_attempt(tmp_path, key="b" * 64, spec=spec, quota=2, limit=3)
    with pytest.raises(ValueError, match="attempt_not_retryable"):
        _begin_attempt(tmp_path, key="b" * 64, spec=spec, quota=2, limit=3)


def test_live_process_group_is_not_quiescent() -> None:
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", "import sys; sys.stdin.read()"],
        stdin=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        assert not _process_group_quiescent(process.pid)
    finally:
        process.communicate(timeout=10)
    assert _process_group_quiescent(process.pid)


@pytest.mark.parametrize("exit_code", [0, 17])
def test_managed_worker_retains_output_and_exit(tmp_path: Path, exit_code: int) -> None:
    pid, actual, stdout, observed = _run_managed_worker(
        [
            sys.executable,
            "-c",
            f"import sys; print('out'); print('err', file=sys.stderr); sys.exit({exit_code})",
        ],
        tmp_path,
        "",
        timeout=5,
    )
    assert pid != 0 and actual == exit_code and stdout == "out\n"
    assert pid in observed
    assert (tmp_path / "child-stderr.log").read_text() == "err\n"


def test_managed_worker_stops_owned_descendant_and_retains_logs(tmp_path: Path) -> None:
    code = (
        "import subprocess,sys; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "print('parent', flush=True)"
    )
    with pytest.raises(_WorkerLifecycleError, match="group_not_quiescent"):
        _run_managed_worker([sys.executable, "-c", code], tmp_path, "", timeout=5)
    assert (tmp_path / "child-stdout.log").read_text() == "parent\n"


def test_managed_worker_timeout_retains_logs(tmp_path: Path) -> None:
    with pytest.raises(_WorkerLifecycleError, match="timeout"):
        _run_managed_worker(
            [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(30)"],
            tmp_path,
            "",
            timeout=0.3,
        )
    assert (tmp_path / "child-stdout.log").read_text() == "started\n"


def test_managed_worker_observes_nested_executor_and_rejects_foreign_pid(tmp_path: Path) -> None:
    code = (
        "import subprocess,sys; "
        "subprocess.run([sys.executable, '-c', "
        '"import os,time; print(os.getpid(), flush=True); time.sleep(0.5)"], check=True)'
    )
    leader, status, stdout, observed = _run_managed_worker(
        [sys.executable, "-c", code], tmp_path, "", timeout=5
    )
    executor = int(stdout.strip())
    assert status == 0 and executor != leader
    assert _require_observed_executor(executor, observed) == observed[executor]
    foreign = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    try:
        assert foreign.pid != leader and foreign.pid != executor
        with pytest.raises(ValueError, match="executor_not_observed"):
            _require_observed_executor(foreign.pid, observed)
    finally:
        foreign.terminate()
        foreign.wait(timeout=5)


def test_completed_attempt_retains_execution_times_for_publication_recovery(tmp_path: Path) -> None:
    spec = _spec()
    first = _begin_attempt(tmp_path, key="c" * 64, spec=spec, quota=2, limit=1)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    first = _settle_attempt(tmp_path, first, started_at=start)
    completed = _settle_attempt(
        tmp_path,
        first,
        status="executed",
        finished_at=start,
        child_pid=40,
        executor_pid=41,
        executor_created_us=123,
        execution_ref=spec.execution_profile_ref,
        ledger_hash="sha256:" + "a" * 64,
        ledger_revision=1,
    )
    terminal = _settle_attempt(
        tmp_path, completed, status="equal", comparison_ref=spec.comparator_ref
    )
    assert terminal.started_at == start and terminal.finished_at == start
    assert terminal.executor_pid == 41 and terminal.child_pid == 40


def test_native_preflight_uses_fresh_profile_and_refuses_changed_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from polisyos.runtime.quality.n5_replay_execution import (
        N5ReplayNativePreflightAction,
        N5ReplayNativePreflightObservation,
        _verify_n5_replay_native_preflight,
    )
    from tests.unit.runtime.quality.test_n5_execution_profile import (
        _module,
        _profile_for_module_set,
        _source_image,
    )

    provider = tmp_path / "site-packages" / "replay_provider.py"
    provider.parent.mkdir(parents=True)
    provider.write_bytes(b"selected = True\n")
    recorded = _profile_for_module_set(
        monkeypatch, tmp_path, {"replay_provider": _module("replay_provider", provider)}
    )
    fresh = _profile_for_module_set(monkeypatch, tmp_path, {})
    image = _source_image(tmp_path)
    spec = _spec()
    action = N5ReplayNativePreflightAction(launch_spec=spec, cas_root=str(tmp_path))
    observation = N5ReplayNativePreflightObservation(
        pid=42,
        action_hash=security.raw_content_hash(action.model_dump_json().encode()),
        native_profile=fresh.model_dump(mode="json"),
        production_image=image.model_dump(mode="json"),
        callable_hash=spec.declared_callable_content_hash,
        numerical_intent_hash=spec.declared_numerical_intent_content_hash,
        seed_schedule_hash=spec.seed_schedule_hash,
        planned_units=spec.planned_physical_units,
    )
    _verify_n5_replay_native_preflight(
        action=action, observation=observation, recorded_profile=recorded, recorded_image=image
    )
    provider.write_bytes(b"selected = False\n")
    with pytest.raises(ValueError, match="native_preflight_mismatch"):
        _verify_n5_replay_native_preflight(
            action=action, observation=observation, recorded_profile=recorded, recorded_image=image
        )
    provider.write_bytes(b"selected = True\n")
    changed_settings = _profile_for_module_set(
        monkeypatch, tmp_path, {}, declared_settings={"replications": 4, "numeric_mode": "float64"}
    )
    with pytest.raises(ValueError, match="native_preflight_mismatch"):
        _verify_n5_replay_native_preflight(
            action=action,
            observation=observation.model_copy(
                update={"native_profile": changed_settings.model_dump(mode="json")}
            ),
            recorded_profile=recorded,
            recorded_image=image,
        )


@pytest.mark.parametrize(
    "reuse_path", ["signed_pointer", "lost_ack", "executed_checkpoint", "concurrent_checkpoint"]
)
@pytest.mark.parametrize("drift", ["provider_bytes", "numerical_settings"])
def test_all_recovery_paths_refuse_current_native_drift_without_numerical_work(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, reuse_path: str, drift: str
) -> None:
    from polisyos.runtime.quality import n5_replay_execution as replay
    from tests.unit.runtime.quality.test_n5_execution_profile import (
        _module,
        _profile_for_module_set,
        _source_image,
    )

    provider = tmp_path / "site-packages" / "selected_provider.py"
    provider.parent.mkdir(parents=True)
    provider.write_bytes(b"selected = True\n")
    recorded = _profile_for_module_set(
        monkeypatch, tmp_path, {"selected_provider": _module("selected_provider", provider)}
    )
    settings = (
        {"replications": 4, "numeric_mode": "float64"} if drift == "numerical_settings" else None
    )
    fresh = _profile_for_module_set(monkeypatch, tmp_path, {}, declared_settings=settings)
    image = _source_image(tmp_path)
    spec = _spec()
    workspace = tmp_path / "replay"
    first = _begin_attempt(workspace, key="d" * 64, spec=spec, quota=2, limit=1)
    _, middleware = _open_diagnostic_budget(spec, workspace / "diagnostic-ledger.json", 2)
    ledger = workspace / "diagnostic-ledger.json"
    before_ledger = ledger.read_bytes()
    started = datetime(2026, 1, 1, tzinfo=UTC)
    first = _settle_attempt(workspace, first, started_at=started)
    if reuse_path == "concurrent_checkpoint":
        assert replay._existing_execution_precondition(
            workspace, key="d" * 64, spec=spec, publishing=False
        ) == (False, False)
    executed = _settle_attempt(
        workspace,
        first,
        status="executed",
        finished_at=started,
        child_pid=40,
        executor_pid=41,
        executor_created_us=123,
        execution_ref=spec.execution_profile_ref,
        ledger_hash=security.raw_content_hash(before_ledger),
        ledger_revision=middleware.snapshot_safe().revision,
    )
    selected_attempt = executed
    if reuse_path == "concurrent_checkpoint":
        selected_attempt = _begin_attempt(workspace, key="d" * 64, spec=spec, quota=2, limit=1)
        assert selected_attempt == executed
    if reuse_path not in {"executed_checkpoint", "concurrent_checkpoint"}:
        selected_attempt = _settle_attempt(
            workspace, executed, status="equal", comparison_ref=spec.comparator_ref
        )
    if reuse_path == "signed_pointer":
        (workspace / "completed-evidence.json").write_text(spec.comparator_ref.model_dump_json())
    state_before = (workspace / "state.json").read_bytes()
    if drift == "provider_bytes":
        provider.write_bytes(b"selected = False\n")
    calls = []

    def only_preflight(command, *_args, **_kwargs):
        assert "n5-replay-profile-preflight" in command
        assert "n5-blind-replay" not in command
        action = replay.N5ReplayNativePreflightAction.model_validate_json(
            Path(command[-1]).read_bytes()
        )
        observation = replay.N5ReplayNativePreflightObservation(
            pid=42,
            action_hash=security.raw_content_hash(action.model_dump_json().encode()),
            native_profile=fresh.model_dump(mode="json"),
            production_image=image.model_dump(mode="json"),
            callable_hash=spec.declared_callable_content_hash,
            numerical_intent_hash=spec.declared_numerical_intent_content_hash,
            seed_schedule_hash=spec.seed_schedule_hash,
            planned_units=spec.planned_physical_units,
        )
        calls.append(command)
        return 40, 0, replay._WORKER_RESULT_PREFIX + observation.model_dump_json(), {42: 123}

    monkeypatch.setattr(replay, "_run_managed_worker", only_preflight)
    with pytest.raises(ValueError, match="native_preflight_mismatch"):
        replay._preflight_existing_execution(
            workspace,
            attempt=selected_attempt,
            spec=spec,
            cas_root=str(tmp_path),
            recorded_profile=recorded,
            recorded_image=image,
        )
    assert len(calls) == 1
    assert ledger.read_bytes() == before_ledger
    assert (workspace / "state.json").read_bytes() == state_before


def test_owner_selected_execution_rejects_changed_ledger_before_preflight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from polisyos.runtime.quality import n5_replay_execution as replay

    spec = _spec()
    first = _begin_attempt(tmp_path, key="f" * 64, spec=spec, quota=2, limit=1)
    _, middleware = _open_diagnostic_budget(spec, tmp_path / "diagnostic-ledger.json", 2)
    raw = (tmp_path / "diagnostic-ledger.json").read_bytes()
    executed = _settle_attempt(
        tmp_path,
        first,
        status="executed",
        child_pid=40,
        executor_pid=41,
        executor_created_us=123,
        execution_ref=spec.execution_profile_ref,
        ledger_hash="sha256:" + "0" * 64,
        ledger_revision=middleware.snapshot_safe().revision,
    )
    monkeypatch.setattr(replay, "_run_managed_worker", lambda *_a, **_kw: pytest.fail("launched"))
    with pytest.raises(ValueError, match="attempt_ledger_changed"):
        replay._preflight_existing_execution(
            tmp_path,
            attempt=executed,
            spec=spec,
            cas_root=str(tmp_path),
            recorded_profile=None,
            recorded_image=None,
        )
    assert (tmp_path / "diagnostic-ledger.json").read_bytes() == raw


@pytest.mark.parametrize("state_present", [False, True])
def test_completed_pointer_requires_terminal_state_before_preflight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, state_present: bool
) -> None:
    from polisyos.runtime.quality import n5_replay_execution as replay

    spec = _spec()
    if state_present:
        _begin_attempt(tmp_path, key="e" * 64, spec=spec, quota=2, limit=1)
    (tmp_path / "completed-evidence.json").write_text(spec.comparator_ref.model_dump_json())

    def forbidden(*_args, **_kwargs):
        raise AssertionError("preflight ran before journal refusal")

    monkeypatch.setattr(replay, "_run_managed_worker", forbidden)
    with pytest.raises(ValueError, match="completed_attempt_not_established"):
        replay._existing_execution_precondition(tmp_path, key="e" * 64, spec=spec, publishing=False)
