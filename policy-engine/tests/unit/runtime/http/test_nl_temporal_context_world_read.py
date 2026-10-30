"""Real temporal cursor -> actual WMR rows -> context admission witnesses.

The compiler seam stops after resolving the actual context. These tests prove
context input admission, not N5 numerical use, branch replay or full closure.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from traceback import extract_tb
from typing import Any

import duckdb
import pytest

from polisyos.core.artifacts import ArtifactRef, read_core_json_artifact
from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.services.control_plane_store import ControlJobLeaseLostError
from polisyos.runtime.quality.cycle_substrate import (
    build_cycle_substrate_context,
    cycle_job_design_problem_ref,
)
from polisyos.runtime.quality.design_problem import DESIGN_PROBLEM_V3_SCHEMA_VERSION
from polisyos.scientist.orchestration.engine import BudgetLedgerProducerRunBinding
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from tests._helpers.control_worker import dispatch_one_control_job
from tests._helpers.runtime_http import _build_control_service, _valid_intake_for_mode
from tests._helpers.world_model_record import _build_record, _substrate_registry
from tests.unit.runtime.http.control_service_test_support import (
    bound_nl_authorization_proof,
)
from tests.unit.runtime.http.test_control_service_di import _fixture_claims
from tests.unit.runtime.quality.test_cycle_substrate import _design_problem

_STOP = "tc_context_world_read_stopped_after_actual_context_resolver"


class _FixtureContextOwner:
    def __init__(self, world):
        self.world = world
        self.source_pack_content_hash = None

    def admit_context(self, *, problem, **_scope):
        registry = _substrate_registry()
        return build_cycle_substrate_context(
            design_problem_ref=cycle_job_design_problem_ref(problem),
            domain=problem.domain,
            substrate_registry=registry,
            selected_registry_entry_hashes=tuple(
                entry.entry_content_hash for entry in registry.entries
            ),
            world_model_record=self.world,
            intervention_substrate=None,
            candidate_levers=(),
            transport_context=None,
            source_pack_content_hash=self.source_pack_content_hash,
            substrate_input_content_hash=None,
        )


def _problem_for_world(world):
    payload = _design_problem().model_dump(mode="json")
    payload["schema_version"] = DESIGN_PROBLEM_V3_SCHEMA_VERSION
    payload["domain"] = world.policy_domain
    payload["jurisdiction_time"]["region"] = world.region_or_jurisdiction
    payload["candidate_lever_space"]["allowed_operator_kinds"] = ["set_to"]
    payload["candidate_lever_space"]["candidate_levers"] = [
        {
            "lever_id": "fixture_income",
            "operator_kind": "set_to",
            "instrument": "fixture income",
            "target_slot": "agents.income",
        }
    ]
    return type(_design_problem()).model_validate(payload)


async def _exercise(
    tmp_path,
    monkeypatch,
    *,
    scope_change=None,
    corrupt_rows=False,
    probe_retention=False,
    resolve_child=False,
    naive_axis=None,
    replay_missing_rows=False,
    simulate_only=True,
):
    store, built, _model, _registry_ref = _build_record(tmp_path / "world")
    world = built.record
    scope = {
        "snapshot_id": world.fabric_world_ref.snapshot_id,
        "valid_at": world.fabric_world_ref.as_of_valid_time,
        "tx_at": world.fabric_world_ref.as_of_tx_time,
    }
    if scope_change is not None:
        scope = scope_change(scope)
    if corrupt_rows:
        from polisyos.fabric import resolve_world_snapshot

        retained = resolve_world_snapshot(
            Path(world.fabric_world_ref.snapshot_root),
            snapshot_id=world.fabric_world_ref.snapshot_id,
        )
        with duckdb.connect(str(retained.snapshot_path)) as connection:
            connection.execute("UPDATE world.world_nodes SET label = 'hostile changed row'")
    owner = _FixtureContextOwner(world)
    service = _build_control_service(
        tmp_path / "control",
        artifact_store=store,
        cycle_substrate_context_admission_owner=owner,
    )
    # Use the same durable producer owner as the application container. The
    # admitted worker, not this fixture, constructs the scoped run binding.
    producer_store = BudgetMiddleware(
        BudgetState(), ledger=FileBudgetLedger(tmp_path / "control" / "producer-ledger.json")
    )
    service.bind_llm_producer_settlement_store(producer_store)
    assert service.llm_producer_settlement_store is producer_store
    observed: dict[str, Any] = {"phase": "before_compiler_entry"}
    original_fail_attempt = service._fail_control_job_attempt

    def capture_actual_failure(**kwargs):
        # Observe the actual exception before the ordinary worker persists it;
        # preserve its outcome, admission checks, and failure transaction.
        exc = kwargs["exc"]
        observed["failure"] = {
            "phase": observed["phase"],
            "type": type(exc).__name__,
            "message": str(exc)[:500],
            "frames": [
                {
                    "file": frame.filename,
                    "line": frame.lineno,
                    "function": frame.name,
                    "source": frame.line,
                }
                for frame in extract_tb(exc.__traceback__)[-24:]
            ],
        }
        return original_fail_attempt(**kwargs)

    monkeypatch.setattr(service, "_fail_control_job_attempt", capture_actual_failure)
    if replay_missing_rows:
        from polisyos.runtime.http.services.control import (
            temporal_scope as temporal_owner,
        )

        original_world_read = temporal_owner.resolve_temporal_scope_context_world_read
        observed["world_reads"] = []

        def capture_world_read(**kwargs):
            result = original_world_read(**kwargs)
            observed["world_reads"].append(result)
            return result

        monkeypatch.setattr(
            temporal_owner,
            "resolve_temporal_scope_context_world_read",
            capture_world_read,
        )
    try:
        request_context = {
            "temporal_scope_context_world_read_bindings": {"caller-forged": {"status": "verified"}}
        }
        if simulate_only:
            # Existing typed candidate intake selects the server's admitted
            # simulation route; the authenticated job owner issues its scope.
            request_context["evaluation_safety_attempt"] = _valid_intake_for_mode(
                "simulate_only"
            ).model_dump(mode="json")
        request = NaturalLanguageRunRequest.model_validate(
            {
                "request": "Inspect the selected fixture world as a candidate.",
                "llm_model": "simulated-qwen",
                "target_world_scope_profile_id": "tc-fixture-world",
                "temporal_scope": scope,
                "context": request_context,
            }
        )
        claims = _fixture_claims()
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        if naive_axis is not None:
            from polisyos.runtime.http.services.control import (
                temporal_scope as temporal_owner,
            )

            original_resolve_scope = temporal_owner.resolve_temporal_scope_for_job

            def hostile_naive_after_authorized_replay(**kwargs):
                selected = original_resolve_scope(**kwargs)
                selected[naive_axis] = (
                    str(selected[naive_axis]).replace("Z", "").replace("+00:00", "")
                )
                return selected

            # Preserve authorized aware queue/artifact bytes, and isolate the
            # lower consumer from a hostile/shared naive datetime interpretation.
            monkeypatch.setattr(
                temporal_owner,
                "resolve_temporal_scope_for_job",
                hostile_naive_after_authorized_replay,
            )

        async def consume_context(**kwargs):
            observed["phase"] = "compiler_entry_before_producer_check"
            observed["compiler_route"] = {
                "execution_intent": kwargs.get("execution_intent"),
                "n4_proposal_only": kwargs.get("n4_proposal_only"),
                "target_world_scope_profile_id": kwargs.get("target_world_scope_profile_id"),
                "context_resolver_is_none": kwargs.get("cycle_substrate_context_resolver") is None,
                "generic_resolver_is_none": (
                    kwargs.get("generic_cycle_simulation_handoff_resolver") is None
                ),
            }
            # The real compiler seam must be reached under this worker's
            # authenticated current job and the active durable producer owner.
            admission = service._control_store.current_execution_job_admission()
            verified = service._control_store.verify_llm_producer_admission(expected=admission)
            assert verified.scope.status == "established"
            assert verified.scope.actor_authenticated is True
            assert verified.scope.actor_subject == claims.sub
            assert verified.scope.tenant_id == claims.tenant_id
            assert verified.scope.cell_id == claims.cell_id
            binding = kwargs["producer_run_binding"]
            assert type(binding) is BudgetLedgerProducerRunBinding
            assert binding.run_id == verified.job.run_id
            assert binding.control_job_id == verified.job.job_id == launch.job_id
            assert binding.tenant_id == verified.scope.tenant_id
            assert binding.cell_id == verified.scope.cell_id
            assert binding.profile_id == verified.job.effective_execution_profile
            assert producer_store._active_run_binding_for_key(f"nl-run:{binding.run_id}") == binding
            assert producer_store._attempt_attribution_for(binding) == (verified.attempt, None)
            observed["phase"] = "producer_checked_before_context_resolver"
            observed["trusted_at_entry"] = deepcopy(kwargs["trusted_source_context"])
            observed["compiler_at_entry"] = deepcopy(kwargs["context"])
            resolver = kwargs["cycle_substrate_context_resolver"]
            if not simulate_only:
                assert kwargs["execution_intent"] == "candidate_only"
                assert resolver is None
                observed["phase"] = "candidate_only_without_context_resolver"
                raise RuntimeError(_STOP)
            assert kwargs["execution_intent"] == "simulate_only"
            assert resolver is not None
            observed["phase"] = "context_resolver_present"
            root_problem = _problem_for_world(world)
            observed["context"] = resolver(root_problem)
            observed["contexts"] = [observed["context"]]
            if replay_missing_rows:
                first = observed["world_reads"][-1]
                assert first.status == "verified"
                admission = service._control_store.current_execution_job_admission()
                observed["first_binding"] = deepcopy(
                    admission.job.progress["temporal_scope_context_world_read_bindings"][
                        first.invocation_key
                    ]
                )
                from polisyos.fabric import resolve_world_snapshot

                retained = resolve_world_snapshot(
                    Path(world.fabric_world_ref.snapshot_root),
                    snapshot_id=world.fabric_world_ref.snapshot_id,
                )
                with duckdb.connect(str(retained.snapshot_path)) as connection:
                    connection.execute("DELETE FROM world.world_nodes")
                # The same context, job, request, content bytes and selected ref
                # are replayed after the actual Fabric owner rows disappear.
                try:
                    resolver(root_problem)
                except ValueError as refusal:
                    observed["replay_error"] = str(refusal)
                    observed["replay_read"] = observed["world_reads"][-1]
                    observed["after_replay"] = deepcopy(
                        service._control_store.current_execution_job_admission().job.progress[
                            "temporal_scope_context_world_read_bindings"
                        ]
                    )
                    # Let the real job handler record the refusal, rather than
                    # converting a rejected replay into a successful consumer.
                    raise
                raise AssertionError("same-ref replay consumed a changed Fabric view")
            if resolve_child:
                child_fields = root_problem.model_dump(mode="json")
                child_fields["design_problem_id"] += "-child"
                child_fields["problem_statement"] += " Resolve a distinct child input."
                child_problem = type(root_problem).model_validate(child_fields)
                observed["contexts"].append(resolver(child_problem))
                assert resolver(root_problem) == observed["context"]
            if probe_retention:
                admission = service._control_store.current_execution_job_admission()
                before = admission.job.progress["temporal_scope_context_world_read_bindings"]
                service._control_store.update_progress_state(
                    job_id=launch.job_id,
                    state="running",
                    progress={"state": "running"},
                    expected_lease_owner=admission.job.lease_owner,
                    expected_attempt=admission.attempt,
                )
                forged = deepcopy(before)
                forged[next(iter(forged))]["status"] = "forged"
                with pytest.raises(
                    ControlJobLeaseLostError,
                    match="nl_temporal_scope_context_world_read_progress_binding_conflict",
                ):
                    service._control_store.update_progress_state(
                        job_id=launch.job_id,
                        state="running",
                        progress={"temporal_scope_context_world_read_bindings": forged},
                        expected_lease_owner=admission.job.lease_owner,
                        expected_attempt=admission.attempt,
                    )
                # A legitimate same-problem owner reissue gets a distinct
                # retained identity and its OWN actual row verification.
                owner.source_pack_content_hash = "sha256:" + "f" * 64
                reissued = resolver(root_problem)
                assert reissued is not None and reissued != observed["context"]
                observed["contexts"].append(reissued)
                current = service._control_store.current_execution_job_admission()
                after = current.job.progress["temporal_scope_context_world_read_bindings"]
                assert set(before) < set(after)
                assert all(after[key] == value for key, value in before.items())
                owner.source_pack_content_hash = None
            raise RuntimeError(_STOP)

        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", consume_context)
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=launch.job_id,
        )
        response = service.get_job_status(launch.job_id)
        expected_error = (
            "nl_temporal_scope_context_world_read_replay_changed" if replay_missing_rows else _STOP
        )
        assert response.error_message == expected_error, (
            f"tc_phase={observed['phase']}; "
            f"tc_compiler_route={observed.get('compiler_route')!r}; "
            f"tc_actual_failure={observed.get('failure')!r}"
        )
        return service, launch, world, observed, response
    except BaseException:
        service.close()
        raise


def _assert_actual_context_read(response, observed, world):
    bindings = response.progress["temporal_scope_context_world_read_bindings"]
    matching = [
        entry
        for entry in bindings.values()
        if entry["context_content_hash"] == observed["context"].content_hash
    ]
    assert matching
    assert all(entry["status"] == "verified" for entry in matching)
    binding = matching[0]
    assert all(key == entry["invocation_key"] for key, entry in bindings.items())
    assert binding["status"] == "verified"
    assert binding["predicate_basis"] == "recomputed"
    assert binding["consumer_stage"] == "cycle_substrate_context_admission"
    assert binding["world_model_record_hash"] == world.content_hash
    assert binding["content_query_digest"] == world.fabric_world_ref.content_query_digest
    assert binding["content_query_row_count"] == world.fabric_world_ref.content_query_row_count
    assert observed["context"].world_model_record == world
    for field in (
        "n5_numeric_consumption",
        "same_input_closure_membership",
        "immutable_branch_replay",
        "complete_world_row_membership",
        "nl_problem_compiler_consumption",
    ):
        assert binding[field] == "not_established"
    assert binding["query_limit_per_mode"] == 100_000
    return binding


@pytest.mark.asyncio
async def test_candidate_only_retains_temporal_intent_without_simulation_resolver(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _launch, _world, observed, response = await _exercise(
        tmp_path, monkeypatch, simulate_only=False
    )
    try:
        assert observed["phase"] == "candidate_only_without_context_resolver"
        assert observed["compiler_route"]["context_resolver_is_none"] is True
        assert response.progress.get("temporal_scope_request_binding") is not None
        assert response.progress.get("temporal_scope_context_world_read_bindings", {}) == {}
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("resolve_child", [False, True])
async def test_temporal_context_reads_actual_owner_rows_and_fresh_selected_projection(
    tmp_path, monkeypatch: pytest.MonkeyPatch, resolve_child: bool
) -> None:
    service, launch, world, observed, response = await _exercise(
        tmp_path, monkeypatch, probe_retention=True, resolve_child=resolve_child
    )
    try:
        binding = _assert_actual_context_read(response, observed, world)
        bindings = response.progress["temporal_scope_context_world_read_bindings"]
        assert all(context is not None for context in observed["contexts"])
        assert {entry["context_content_hash"] for entry in bindings.values()} == {
            context.content_hash for context in observed["contexts"]
        }
        assert len({entry["context_content_hash"] for entry in bindings.values()}) == (
            3 if resolve_child else 2
        )
        ref_key = "temporal_context_candidate:" + binding["invocation_key"]
        ref = response.runtime_quality_artifact_refs[ref_key]
        assert ref.manifest_profile_sha256 is not None
        assert ref == ArtifactRef.model_validate(binding["context_job_ref"])
        selected = read_core_json_artifact(service._artifact_store, ref).value
        assert selected["context"]["world_model_record"]["content_hash"] == world.content_hash
        assert "temporal_scope_context_world_read_bindings" not in observed["trusted_at_entry"]
        compiler_input = observed["compiler_at_entry"]
        assert "temporal_scope_context_world_read_bindings" not in compiler_input
        assert (
            "temporal_scope_context_world_read_bindings" not in compiler_input["candidate_context"]
        )
        assert binding["request_binding"] == response.progress["temporal_scope_request_binding"]
        assert response.approval_projection.eligible is False
        assert response.authoritative_scorecard_ref is None
    finally:
        service.close()
    reopened = _build_control_service(tmp_path / "control", artifact_store=service._artifact_store)
    try:
        fresh = reopened.get_job_status(launch.job_id)
        assert fresh.progress["temporal_scope_context_world_read_bindings"] == bindings
        assert fresh.runtime_quality_artifact_refs[ref_key] == ref
        for key, entry in bindings.items():
            assert fresh.runtime_quality_artifact_refs["temporal_context_candidate:" + key] == (
                ArtifactRef.model_validate(entry["context_job_ref"])
            )
        assert read_core_json_artifact(reopened._artifact_store, ref).value == selected
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_same_ref_replay_recomputes_missing_fabric_rows_and_refuses(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _launch, _world, observed, response = await _exercise(
        tmp_path, monkeypatch, replay_missing_rows=True
    )
    try:
        first = observed["first_binding"]
        recomputed = observed["replay_read"]
        assert first["status"] == "verified"
        assert recomputed.invocation_key == first["invocation_key"]
        assert recomputed.context_job_ref.model_dump(mode="json") == first["context_job_ref"]
        assert recomputed.context_content_hash == first["context_content_hash"]
        assert recomputed.status == "not_established"
        assert recomputed.predicate_basis == "not_established"
        assert recomputed.limitation_codes[0].startswith(
            "nl_temporal_scope_context_world_read_refused:"
        )
        assert observed["replay_error"] == "nl_temporal_scope_context_world_read_replay_changed"
        assert response.error_message == observed["replay_error"]
        # The append-only first observation is not a fresh currentness assertion.
        assert observed["after_replay"][first["invocation_key"]] == first
        assert (
            response.progress["temporal_scope_context_world_read_bindings"]
            == observed["after_replay"]
        )
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda scope: {**scope, "snapshot_id": "different-view"}, "snapshot_mismatch"),
        (
            lambda scope: {**scope, "tx_at": "2026-05-23T12:00:00Z"},
            "time_axis_mismatch",
        ),
        (
            lambda scope: {**scope, "valid_at": "2026-05-23T00:00:00Z"},
            "time_axis_mismatch",
        ),
        (
            lambda scope: {**scope, "scenario_id": "other-scenario"},
            "scenario_unsupported",
        ),
        (
            lambda scope: {**scope, "branch": "main"},
            "mutable_branch_replay_not_established",
        ),
        (lambda scope: {"valid_at": scope["valid_at"]}, "explicit_snapshot_required"),
    ],
)
async def test_temporal_context_selection_gap_withholds_configured_context(
    tmp_path, monkeypatch: pytest.MonkeyPatch, change, reason: str
) -> None:
    service, _launch, _world, observed, response = await _exercise(
        tmp_path, monkeypatch, scope_change=change
    )
    try:
        assert observed["context"] is None, "unhonored scope consumed the configured context"
        entries = response.progress["temporal_scope_context_world_read_bindings"]
        assert len(entries) == 1
        binding = next(iter(entries.values()))
        assert binding["status"] == "not_established"
        assert binding["predicate_basis"] == "not_established"
        assert binding["limitation_codes"] == ["nl_temporal_scope_context_" + reason]
    finally:
        service.close()


@pytest.mark.asyncio
async def test_temporal_context_row_corruption_fails_with_request_and_markers_intact(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _launch, _world, observed, response = await _exercise(
        tmp_path, monkeypatch, corrupt_rows=True
    )
    try:
        assert observed["context"] is None, "actual owner row reconciliation was removed"
        binding = next(
            iter(response.progress["temporal_scope_context_world_read_bindings"].values())
        )
        assert binding["status"] == "not_established"
        assert binding["content_query_digest"] is None
        assert binding["limitation_codes"][0].startswith(
            "nl_temporal_scope_context_world_read_refused:"
        )
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope_change",
    [
        lambda scope: {"snapshot_id": scope["snapshot_id"]},
        lambda scope: {**scope, "valid_at": None},
    ],
)
async def test_temporal_context_snapshot_partial_keeps_unknown_request_axes(
    tmp_path, monkeypatch: pytest.MonkeyPatch, scope_change
) -> None:
    service, _launch, world, observed, response = await _exercise(
        tmp_path, monkeypatch, scope_change=scope_change
    )
    try:
        binding = _assert_actual_context_read(response, observed, world)
        intent = read_core_json_artifact(
            service._artifact_store,
            ArtifactRef.model_validate(binding["request_binding"]["temporal_scope_ref"]),
        ).value
        if "valid_at" in intent:
            assert intent["valid_at"] is None
        else:
            assert set(intent) == {"snapshot_id"}
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("axis", ["valid_at", "tx_at"])
async def test_temporal_context_lower_gate_refuses_naive_time_without_host_policy(
    tmp_path, monkeypatch: pytest.MonkeyPatch, axis: str
) -> None:
    service, _launch, _world, observed, response = await _exercise(
        tmp_path, monkeypatch, naive_axis=axis
    )
    try:
        assert observed["context"] is None
        binding = next(
            iter(response.progress["temporal_scope_context_world_read_bindings"].values())
        )
        assert binding["status"] == "not_established"
        assert binding["limitation_codes"] == [
            "nl_temporal_scope_context_time_axis_timezone_not_established"
        ]
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("axis", ["valid_at", "tx_at"])
async def test_temporal_context_offset_equivalent_instant_uses_same_owner_basis(
    tmp_path, monkeypatch: pytest.MonkeyPatch, axis: str
) -> None:
    from datetime import datetime, timedelta, timezone

    def equivalent(scope):
        instant = datetime.fromisoformat(scope[axis])
        return {
            **scope,
            axis: instant.astimezone(timezone(timedelta(hours=3))).isoformat(),
        }

    service, _launch, world, observed, response = await _exercise(
        tmp_path, monkeypatch, scope_change=equivalent
    )
    try:
        _assert_actual_context_read(response, observed, world)
    finally:
        service.close()
