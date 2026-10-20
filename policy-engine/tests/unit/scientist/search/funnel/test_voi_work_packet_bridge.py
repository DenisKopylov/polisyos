from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jax.numpy as jnp
import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    Metrics,
    MetricsRef,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.snapshots import put_state_snapshot
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import (
    FunnelExecutedWorkPacket,
    FunnelStage,
    FunnelStageResult,
)
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    ObjectiveScoreStatus,
    SourceMetricObservation,
    observe_source_government_balance,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferTenantScopeStatus,
)
from polisyos.scientist.methods.search.voi_scheduler import (
    PredictiveVOIScheduler,
    VOIModelSnapshot,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_state import (
    load_predictive_voi_scheduler,
    predictive_voi_snapshot_path,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    persist_funnel_executed_work_packet,
    persist_policy_evaluation_vector_to_store,
)
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)

_INVOCATION = {
    "evaluation_attempt_id": "attempt-voi-work-packet",
    "requested_draw_count": 1,
    "requested_draw_source": "effective_estimation_config",
    "effective_estimation_config_sha256": "c" * 64,
}
_UNAVAILABLE_INVOCATION = {
    "evaluation_attempt_id": "attempt-no-draw-config",
    "requested_draw_count": None,
    "requested_draw_source": "unavailable",
    "effective_estimation_config_sha256": None,
}


def _persist_profileless_legacy_packet(
    store: FileSystemCAS, packet: FunnelExecutedWorkPacket
) -> ArtifactRef:
    """Reproduce the former writer's profileless default ref for history controls."""
    return store.put_json(
        packet,
        PutOptions(
            kind="scientist.search.funnel_native_work_packet",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.search.FunnelExecutedWorkPacket",
                version=packet.schema_version,
            ),
            producer=ProducerInfo(
                component="scientist.policy_runtime_work_packet",
                version="1.0.0",
            ),
            inputs=[
                input_ref_from_artifact_ref(packet.candidate_ref, role="candidate"),
                input_ref_from_artifact_ref(packet.source_result_ref, role="source_result"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _fixture_ir_id(prefix: str, identifier: str) -> str:
    """Build a stable identifier valid for the strict Trinity IR ID fields."""
    slug = re.sub(r"[^a-z0-9_]+", "_", identifier.lower()).strip("_") or "candidate"
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{slug}_{digest}"


def _candidate(identifier: str) -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id=_fixture_ir_id("problem", identifier),
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id=_fixture_ir_id("policy", identifier)),
            model_spec=ModelSpec(
                model_id=_fixture_ir_id("model", identifier),
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        candidate_id=identifier,
    )


def _source_balance_observation(store: FileSystemCAS) -> SourceMetricObservation:
    """Persist the real Foundry source chain and ask its owner to recompute it."""
    metrics = Metrics(values={"government_balance": 35.0})
    metrics_ref_raw = store.put_json(
        metrics,
        PutOptions(
            kind=Metrics.ARTIFACT_KIND,
            media_type=Metrics.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=Metrics.ARTIFACT_SCHEMA_NAME,
                version=Metrics.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    metrics_ref = MetricsRef.model_validate(metrics_ref_raw.model_dump(mode="python"))
    state = replace(
        GlobalState.empty(n_agents=1, n_firms=1),
        step=jnp.asarray(3, dtype=jnp.int32),
        government_balance=jnp.asarray(35.0, dtype=jnp.float32),
    )
    snapshot_ref_raw = put_state_snapshot(store, state=state, step=3, return_selected_profile=True)
    snapshot_ref = StateSnapshotRef.model_validate(snapshot_ref_raw.model_dump(mode="python"))
    simulation = SimulationResult(
        schema_version="1.4",
        exec_plan_ref=ExecPlanRef(artifact_id="sha256:" + "f" * 64),
        metrics_ref=metrics_ref,
        state_snapshot_ref=snapshot_ref,
        execution_source_status="not_recorded",
    )
    simulation_ref = store.put_json(
        simulation,
        PutOptions(
            kind=SimulationResult.ARTIFACT_KIND,
            media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=SimulationResult.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                input_ref_from_artifact_ref(metrics_ref, role="metrics"),
                input_ref_from_artifact_ref(snapshot_ref, role="state_snapshot"),
            ],
        ),
        return_selected_profile=True,
    )
    observation = observe_source_government_balance(
        store,
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
        state_snapshot_ref=snapshot_ref,
    )
    assert observation.source_status == "observed"
    assert observation.predicate_status == "recomputed"
    return observation


def _source_results(invocation: dict[str, Any] | None = None) -> dict[str, Any]:
    selected_invocation = _INVOCATION if invocation is None else invocation
    return {
        "gov_balance": 0.0,
        "metric_units": {
            "gov_balance": "fixture-currency",
            "channel:primary:gdp_growth": "fixture-currency",
        },
        "budget_deficit_objective_usable": True,
        "budget_deficit_objective_value": 0.0,
        "objective_channels": {"gdp_growth": 0.25},
        "feasible": True,
        "blocking_reasons": [],
        "bootstrap": dict(selected_invocation),
    }


class _PacketStage(FunnelStage):
    """Nominal full-fidelity stage fixture for VOI packet producer tests."""

    @property
    def stage_name(self) -> str:
        return "funnel_L4_full"

    @property
    def fidelity_level(self) -> int:
        return 4

    @property
    def estimated_cost_usd(self) -> float:
        """Return the fixture's declared finite per-candidate estimate."""
        return 0.0

    def __init__(
        self,
        store: FileSystemCAS,
        *,
        packet_mode: str,
        metadata_invocation: dict[str, Any] | None = None,
        bootstrap_invocation: dict[str, Any] | None = None,
        packet_invocation: dict[str, Any] | None = None,
    ) -> None:
        self._store = store
        self._packet_mode = packet_mode
        self._metadata_invocation = dict(
            _INVOCATION if metadata_invocation is None else metadata_invocation
        )
        self._bootstrap_invocation = dict(
            _INVOCATION if bootstrap_invocation is None else bootstrap_invocation
        )
        self._packet_invocation = dict(
            _INVOCATION if packet_invocation is None else packet_invocation
        )

    def evaluate(self, candidate: dict[str, Any], context: dict[str, Any]) -> FunnelStageResult:
        schema = context["policy_candidate_schema"]
        candidate_ref = context["policy_candidate_ref"]
        source = _source_results(self._bootstrap_invocation)
        source_observation = context.get("policy_runtime_source_measurement")
        fiscal_source_values = {"gov_balance": 0.0}
        if source_observation is not None:
            # Keep the separately observed stock out of the budget-deficit metric.
            source.pop("gov_balance")
            source["budget_deficit"] = 0.0
            source["metric_units"].pop("gov_balance")
            source["metric_units"]["budget_deficit"] = "fixture-currency"
            fiscal_source_values = {"budget_deficit": 0.0}
        measurement = {
            "usable": True,
            "normalized_value": 0.0,
            "source_values": fiscal_source_values,
        }
        vector_metadata = {
            "policy_runtime_invocation": dict(self._metadata_invocation),
            "policy_runtime_fiscal_measurement": measurement,
        }
        if source_observation is not None:
            vector_metadata["policy_runtime_source_measurement"] = source_observation
        vector = PolicyEvaluationVector(
            candidate_id=schema.candidate_id,
            primary={
                "gdp_growth": ObjectiveChannelValue(
                    name="gdp_growth",
                    kind=ObjectiveKind.PRIMARY,
                    value=0.25,
                    direction=ObjectiveDirection.MAXIMIZE,
                    expected_unit="fixture-currency",
                )
            },
            metadata=vector_metadata,
        ).with_score_source_results(source)
        source_result_ref = persist_policy_evaluation_vector_to_store(
            self._store,
            candidate_ref=candidate_ref,
            evaluation_vector=vector,
        )
        objective = BudgetDeficitObjective(expected_unit="fixture-currency").evaluate(source)
        assert objective.score_assessment is not None
        packet_ref = None
        if self._packet_mode != "score_only":
            identity = context["policy_runtime_work_identity"]
            packet = FunnelExecutedWorkPacket(
                run_id=identity["run_id"],
                ticket_id=context["_funnel_ticket_id"],
                candidate_hash=identity["candidate_hash"],
                candidate_ref=candidate_ref,
                stage_level=4,
                stage_name="funnel_L4_full",
                fidelity="full",
                evaluation_attempt_id=self._packet_invocation["evaluation_attempt_id"],
                observed_at=datetime.now(UTC),
                backend_kind="fixture_policy_evaluator",
                source_result_ref=source_result_ref,
                requested_draw_count=self._packet_invocation["requested_draw_count"],
                requested_draw_source=self._packet_invocation["requested_draw_source"],
                effective_estimation_config_sha256=(
                    self._packet_invocation["effective_estimation_config_sha256"]
                ),
                input_signature=context["pinned_input_signature"],
            )
            if self._packet_mode == "profileless_legacy":
                packet_ref = _persist_profileless_legacy_packet(self._store, packet)
            else:
                packet_ref = persist_funnel_executed_work_packet(self._store, packet)
        result = FunnelStageResult(
            policy_candidate=candidate,
            objective_value=objective.raw_value,
            is_promising=True,
            score_status=objective.score_status,
            score_assessment=objective.score_assessment,
            stage_name=self.stage_name,
            duration_seconds=0.1,
            simulation_results=source,
            feedback={
                "policy_runtime_fidelity": "full",
                "policy_runtime_backend_kind": "fixture_policy_evaluator",
            },
            compute_cost_usd=0.0,
            compute_cost_origin="estimated",
            fidelity_level=4,
            executed_work_packet_ref=packet_ref,
            executed_work_packet_status=("unavailable" if packet_ref is None else "available"),
            terminal_action="defer",
        )
        if self._packet_mode == "marker_without_reference":
            # Removal control: retain the producer status marker after removing its ref.
            result.executed_work_packet_ref = None
        return result


def _observe(
    tmp_path: Path,
    *,
    suffix: str,
    packet_mode: str,
    source_measurement: SourceMetricObservation | None = None,
    include_source_measurement: bool = False,
    metadata_invocation: dict[str, Any] | None = None,
    bootstrap_invocation: dict[str, Any] | None = None,
    packet_invocation: dict[str, Any] | None = None,
) -> tuple[Any, VOIModelSnapshot, FileSystemCAS]:
    store = FileSystemCAS(tmp_path / f"cas-{suffix}")
    if include_source_measurement:
        source_measurement = _source_balance_observation(store)
    candidate = _candidate(f"candidate-{suffix}")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    scheduler = PredictiveVOIScheduler()
    context = {
        "store": store,
        "policy_candidate_schema": candidate,
        "policy_candidate_ref": candidate_ref,
        "pinned_input_signature": f"input-{suffix}",
        "transfer_context": {
            "run_id": f"run-{suffix}",
            "task_family": "policy",
            "domain": "fiscal",
            "tenant_hash": "fixture-tenant",
        },
    }
    if source_measurement is not None:
        context["policy_runtime_source_measurement"] = source_measurement.model_dump(
            mode="json", exclude_none=False
        )
    orchestrator = FunnelOrchestrator(
        [
            _PacketStage(
                store,
                packet_mode=packet_mode,
                metadata_invocation=metadata_invocation,
                bootstrap_invocation=bootstrap_invocation,
                packet_invocation=packet_invocation,
            )
        ],
        voi_scheduler=scheduler,
    )
    payload = {
        "candidate_id": candidate.candidate_id,
        "semantic": {"interventions": [], "objectives": [{"name": "budget_deficit"}]},
    }
    outcome = orchestrator.advance(orchestrator.submit(payload, context), target_level=4)
    return outcome, scheduler.snapshot(), store


def test_explicit_unavailable_invocation_fields_keep_fresh_packet_claim(
    tmp_path: Path,
) -> None:
    outcome, snapshot, store = _observe(
        tmp_path,
        suffix="explicit-unavailable-invocation",
        packet_mode="packet",
        metadata_invocation=dict(_UNAVAILABLE_INVOCATION),
        bootstrap_invocation=dict(_UNAVAILABLE_INVOCATION),
        packet_invocation=dict(_UNAVAILABLE_INVOCATION),
    )

    result = outcome.stage_results[4]
    observation = snapshot.observations[0]
    assert result.executed_work_packet_status == "available"
    assert result.score_status is ObjectiveScoreStatus.AVAILABLE
    assert observation.work_packet_claim is not None
    assert (
        observation.work_packet_claim.evaluation_attempt_id
        == (_UNAVAILABLE_INVOCATION["evaluation_attempt_id"])
    )
    restored = PredictiveVOIScheduler.from_snapshot(snapshot, artifact_store=store).snapshot()
    assert restored.observations[0].work_packet_claim == observation.work_packet_claim


@pytest.mark.parametrize(
    ("missing_owner", "missing_field"),
    [
        ("metadata", "evaluation_attempt_id"),
        ("metadata", "requested_draw_count"),
        ("metadata", "requested_draw_source"),
        ("metadata", "effective_estimation_config_sha256"),
        ("bootstrap", "evaluation_attempt_id"),
        ("bootstrap", "requested_draw_count"),
        ("bootstrap", "requested_draw_source"),
        ("bootstrap", "effective_estimation_config_sha256"),
        ("both", "evaluation_attempt_id"),
        ("both", "requested_draw_count"),
        ("both", "requested_draw_source"),
        ("both", "effective_estimation_config_sha256"),
    ],
    ids=(
        "metadata-attempt-key",
        "metadata-count-key",
        "metadata-source-key",
        "metadata-digest-key",
        "bootstrap-attempt-key",
        "bootstrap-count-key",
        "bootstrap-source-key",
        "bootstrap-digest-key",
        "both-attempt-key",
        "both-count-key",
        "both-source-key",
        "both-digest-key",
    ),
)
def test_live_work_packet_intake_rejects_absent_invocation_keys_that_match_nulls(
    tmp_path: Path, missing_owner: str, missing_field: str
) -> None:
    metadata_invocation = dict(_UNAVAILABLE_INVOCATION)
    bootstrap_invocation = dict(_UNAVAILABLE_INVOCATION)
    if missing_owner in {"metadata", "both"}:
        metadata_invocation.pop(missing_field)
    if missing_owner in {"bootstrap", "both"}:
        bootstrap_invocation.pop(missing_field)

    outcome, snapshot, _store = _observe(
        tmp_path,
        suffix=f"missing-{missing_owner}-{missing_field}",
        packet_mode="packet",
        metadata_invocation=metadata_invocation,
        bootstrap_invocation=bootstrap_invocation,
        packet_invocation=dict(_UNAVAILABLE_INVOCATION),
    )

    result = outcome.stage_results[4]
    assert result.score_status is ObjectiveScoreStatus.AVAILABLE
    assert result.executed_work_packet_status == "rejected"
    assert result.feedback["policy_runtime_work_packet_rejection_reason"] == (
        "work_packet_binding_mismatch"
    )
    assert len(snapshot.observations) == 1
    assert snapshot.observations[0].score_status is ObjectiveScoreStatus.AVAILABLE
    assert snapshot.observations[0].work_packet_claim is None


@pytest.mark.parametrize(
    ("missing_owner", "missing_field"),
    [
        ("metadata", "evaluation_attempt_id"),
        ("metadata", "requested_draw_count"),
        ("metadata", "requested_draw_source"),
        ("metadata", "effective_estimation_config_sha256"),
        ("bootstrap", "evaluation_attempt_id"),
        ("bootstrap", "requested_draw_count"),
        ("bootstrap", "requested_draw_source"),
        ("bootstrap", "effective_estimation_config_sha256"),
        ("both", "evaluation_attempt_id"),
        ("both", "requested_draw_count"),
        ("both", "requested_draw_source"),
        ("both", "effective_estimation_config_sha256"),
    ],
    ids=(
        "metadata-attempt-key",
        "metadata-count-key",
        "metadata-source-key",
        "metadata-digest-key",
        "bootstrap-attempt-key",
        "bootstrap-count-key",
        "bootstrap-source-key",
        "bootstrap-digest-key",
        "both-attempt-key",
        "both-count-key",
        "both-source-key",
        "both-digest-key",
    ),
)
def test_fresh_restore_drops_claim_when_required_invocation_key_is_absent(
    tmp_path: Path, missing_owner: str, missing_field: str
) -> None:
    _outcome, snapshot, store = _observe(
        tmp_path,
        suffix=f"restore-absent-{missing_owner}-{missing_field}",
        packet_mode="packet",
        metadata_invocation=dict(_UNAVAILABLE_INVOCATION),
        bootstrap_invocation=dict(_UNAVAILABLE_INVOCATION),
        packet_invocation=dict(_UNAVAILABLE_INVOCATION),
    )
    observation = snapshot.observations[0]
    claim = observation.work_packet_claim
    assert claim is not None

    source_payload = load_core_json_artifact(store, claim.source_result_ref)
    assert isinstance(source_payload, dict)
    if missing_owner in {"metadata", "both"}:
        source_payload["metadata"]["policy_runtime_invocation"].pop(missing_field)
    if missing_owner in {"bootstrap", "both"}:
        source_payload["score_source"]["bootstrap"].pop(missing_field)
    vector = PolicyEvaluationVector.model_validate(source_payload)
    source_ref = persist_policy_evaluation_vector_to_store(
        store, candidate_ref=claim.candidate_ref, evaluation_vector=vector
    )

    packet = FunnelExecutedWorkPacket.model_validate(
        load_core_json_artifact(store, claim.packet_ref)
    )
    packet_ref = persist_funnel_executed_work_packet(
        store, packet.model_copy(update={"source_result_ref": source_ref})
    )
    snapshot_wire = snapshot.model_dump(mode="json")
    claim_wire = snapshot_wire["observations"][0]["work_packet_claim"]
    claim_wire["packet_ref"] = packet_ref.model_dump(mode="json")
    claim_wire["source_result_ref"] = source_ref.model_dump(mode="json")
    snapshot_wire["observations"][0]["metadata"]["executed_work_packet_ref"] = (
        packet_ref.model_dump(mode="json")
    )
    tampered_snapshot = VOIModelSnapshot.model_validate(snapshot_wire)

    restored = PredictiveVOIScheduler.from_snapshot(
        tampered_snapshot, artifact_store=store
    ).snapshot()
    restored_observation = restored.observations[0]
    assert restored_observation.score_status is ObjectiveScoreStatus.AVAILABLE
    assert restored_observation.work_packet_claim is None
    assert restored_observation.metadata["executed_work_packet_status"] == "available"
    assert restored_observation.metadata["executed_work_packet_ref"] == packet_ref.model_dump(
        mode="json"
    )


def test_packet_bound_voi_rechecks_cas_and_keeps_score_only_rows_unqualified(
    tmp_path: Path,
) -> None:
    outcome, snapshot, store = _observe(tmp_path, suffix="bound", packet_mode="packet")
    result = outcome.stage_results[4]
    assert result.score_status is ObjectiveScoreStatus.AVAILABLE
    assert len(snapshot.observations) == 1
    observation = snapshot.observations[0]
    assert observation.work_packet_claim is not None
    assert observation.work_packet_claim.run_id == "run-bound"
    assert observation.work_packet_claim.ticket_id == outcome.ticket_id
    assert observation.work_packet_claim.candidate_hash == outcome.candidate_hash
    assert observation.work_packet_claim.packet_ref == result.executed_work_packet_ref
    assert observation.work_packet_claim.packet_ref.manifest_profile_sha256 is not None
    assert observation.work_packet_claim.source_result_ref != result.executed_work_packet_ref
    for selected_ref in (
        observation.work_packet_claim.packet_ref,
        observation.work_packet_claim.candidate_ref,
        observation.work_packet_claim.source_result_ref,
    ):
        assert selected_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
            store.get_manifest(selected_ref)
        )
    packet_manifest = store.get_manifest(observation.work_packet_claim.packet_ref)
    assert all(item.manifest_profile_sha256 is not None for item in packet_manifest.inputs)
    assert snapshot.schema_version == "1.4"

    restored = PredictiveVOIScheduler.from_snapshot(snapshot, artifact_store=store)
    assert restored.snapshot().observations[0].work_packet_claim == observation.work_packet_claim

    # The runtime loader revalidates the persisted packet against its own CAS.
    transfer_scope = TransferContext(
        run_id="run-bound",
        task_family="policy",
        domain="fiscal",
        tenant_scope_status=TransferTenantScopeStatus.UNKNOWN,
    )
    transfer_wire = transfer_scope.model_dump(mode="python")
    cache_context = SimpleNamespace(store=store)
    snapshot_path = predictive_voi_snapshot_path(cache_context, transfer_context=transfer_wire)
    assert snapshot_path is not None
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(snapshot.model_dump_json(), encoding="utf-8")
    loaded = load_predictive_voi_scheduler(cache_context, transfer_context=transfer_wire)
    assert loaded.snapshot().observations[0].work_packet_claim == observation.work_packet_claim

    unavailable_store = FileSystemCAS(tmp_path / "loader-without-cas")
    unavailable_context = SimpleNamespace(store=unavailable_store)
    unavailable_path = predictive_voi_snapshot_path(
        unavailable_context, transfer_context=transfer_wire
    )
    assert unavailable_path is not None
    unavailable_path.parent.mkdir(parents=True, exist_ok=True)
    unavailable_path.write_text(snapshot.model_dump_json(), encoding="utf-8")
    unavailable_loaded = load_predictive_voi_scheduler(
        unavailable_context, transfer_context=transfer_wire
    )
    assert unavailable_loaded.snapshot().observations[0].work_packet_claim is None

    # Removing the typed binding while leaving the old status/ref metadata is not enough.
    wire = snapshot.model_dump(mode="json")
    wire["observations"][0].pop("work_packet_claim")
    stripped = VOIModelSnapshot.model_validate(wire)
    stripped_observation = (
        PredictiveVOIScheduler.from_snapshot(stripped, artifact_store=store)
        .snapshot()
        .observations[0]
    )
    assert stripped_observation.score_status is ObjectiveScoreStatus.AVAILABLE
    assert stripped_observation.work_packet_claim is None
    assert stripped_observation.metadata["executed_work_packet_status"] == "available"
    assert stripped_observation.metadata["executed_work_packet_ref"] is not None

    # A real claim without a readable CAS packet becomes score-only on reload.
    unavailable_store = FileSystemCAS(tmp_path / "empty-cas")
    stale_observation = (
        PredictiveVOIScheduler.from_snapshot(snapshot, artifact_store=unavailable_store)
        .snapshot()
        .observations[0]
    )
    assert stale_observation.score_status is ObjectiveScoreStatus.AVAILABLE
    assert stale_observation.work_packet_claim is None

    # Supplied source drift fails closed instead of being accepted via the claim marker.
    tampered_wire = snapshot.model_dump(mode="json")
    tampered_source = tampered_wire["observations"][0]["objective_source"]
    tampered_source["metric_units"]["gov_balance"] = "different-fixture-unit"
    with pytest.raises(ValidationError):
        VOIModelSnapshot.model_validate(tampered_wire)


def test_packetless_or_reference_removed_observation_remains_score_only(
    tmp_path: Path,
) -> None:
    for suffix, mode in (("plain", "score_only"), ("removed", "marker_without_reference")):
        outcome, snapshot, store = _observe(tmp_path, suffix=suffix, packet_mode=mode)
        result = outcome.stage_results[4]
        observation = snapshot.observations[0]
        assert result.score_status is ObjectiveScoreStatus.AVAILABLE
        assert observation.score_status is ObjectiveScoreStatus.AVAILABLE
        assert observation.work_packet_claim is None
        if mode == "marker_without_reference":
            assert result.executed_work_packet_status == "rejected"
            assert result.executed_work_packet_ref is None
        restored = (
            PredictiveVOIScheduler.from_snapshot(snapshot, artifact_store=store)
            .snapshot()
            .observations[0]
        )
        assert restored.work_packet_claim is None


def test_profileless_packet_stays_score_only_and_old_history_remains_readable(
    tmp_path: Path,
) -> None:
    outcome, snapshot, store = _observe(
        tmp_path, suffix="profileless-legacy", packet_mode="profileless_legacy"
    )
    result = outcome.stage_results[4]
    observation = snapshot.observations[0]
    assert result.executed_work_packet_ref is not None
    assert result.executed_work_packet_ref.manifest_profile_sha256 is None
    assert result.executed_work_packet_status == "rejected"
    assert result.feedback["policy_runtime_work_packet_rejection_reason"] == (
        "work_packet_selected_profile_missing_or_mismatched"
    )
    assert observation.score_status is ObjectiveScoreStatus.AVAILABLE
    assert observation.work_packet_claim is None

    restored = PredictiveVOIScheduler.from_snapshot(snapshot, artifact_store=store).snapshot()
    assert restored.observations[0].score_status is ObjectiveScoreStatus.AVAILABLE
    assert restored.observations[0].work_packet_claim is None

    # Existing 1.3 history remains score-only; the reader does not synthesize a claim
    # from a packet's current default view or from its artifact ID.
    legacy_wire = snapshot.model_dump(mode="json")
    legacy_wire["schema_version"] = "1.3"
    legacy_snapshot = VOIModelSnapshot.model_validate(legacy_wire)
    legacy_restored = PredictiveVOIScheduler.from_snapshot(
        legacy_snapshot, artifact_store=store
    ).snapshot()
    assert legacy_restored.observations[0].score_status is ObjectiveScoreStatus.AVAILABLE
    assert legacy_restored.observations[0].work_packet_claim is None


def test_malformed_or_wrong_present_packet_profile_never_becomes_profileless_success(
    tmp_path: Path,
) -> None:
    _outcome, snapshot, store = _observe(tmp_path, suffix="profile-falsifier", packet_mode="packet")
    wire = snapshot.model_dump(mode="json")
    claim_wire = wire["observations"][0]["work_packet_claim"]
    assert claim_wire is not None

    malformed_wire = snapshot.model_dump(mode="json")
    malformed_wire["observations"][0]["work_packet_claim"]["packet_ref"][
        "manifest_profile_sha256"
    ] = "present-but-malformed"
    with pytest.raises(ValidationError):
        VOIModelSnapshot.model_validate(malformed_wire)

    wrong_profile_wire = snapshot.model_dump(mode="json")
    wrong_profile_wire["observations"][0]["work_packet_claim"]["packet_ref"][
        "manifest_profile_sha256"
    ] = "sha256:" + "0" * 64
    wrong_profile_snapshot = VOIModelSnapshot.model_validate(wrong_profile_wire)
    downgraded = (
        PredictiveVOIScheduler.from_snapshot(wrong_profile_snapshot, artifact_store=store)
        .snapshot()
        .observations[0]
    )
    assert downgraded.score_status is ObjectiveScoreStatus.AVAILABLE
    assert downgraded.work_packet_claim is None


@pytest.mark.parametrize("tamper", ["extra_vector_field", "measurement_source_drift"])
def test_snapshot_restore_replays_typed_vector_and_source_observation(
    tmp_path: Path, tamper: str
) -> None:
    outcome, snapshot, store = _observe(
        tmp_path,
        suffix=tamper,
        packet_mode="packet",
        include_source_measurement=True,
    )
    observation = snapshot.observations[0]
    claim = observation.work_packet_claim
    assert claim is not None
    assert observation.score_status is ObjectiveScoreStatus.AVAILABLE
    source_payload = load_core_json_artifact(store, claim.source_result_ref)
    source_manifest = store.get_manifest(claim.source_result_ref)
    if tamper == "extra_vector_field":
        # Preserve the manifest kind/schema and all valid fields while making the
        # source object cease to satisfy the strict PolicyEvaluationVector DTO.
        source_payload["unexpected_runtime_field"] = {"still": "present"}
        tampered_source_ref = store.put_json(
            source_payload,
            PutOptions(
                kind="scientist.policy_evaluation_vector",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.policy_design.PolicyEvaluationVector",
                    version="1.1",
                ),
                inputs=source_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    else:
        # The observation remains structurally valid and keeps every CAS ref,
        # but its claimed value no longer matches the independently read source.
        source_payload["metadata"]["policy_runtime_source_measurement"]["value"] += 1.0
        tampered_vector = PolicyEvaluationVector.model_validate(source_payload)
        candidate_ref = claim.candidate_ref
        tampered_source_ref = persist_policy_evaluation_vector_to_store(
            store, candidate_ref=candidate_ref, evaluation_vector=tampered_vector
        )

    original_packet = FunnelExecutedWorkPacket.model_validate(
        load_core_json_artifact(store, claim.packet_ref)
    )
    tampered_packet = original_packet.model_copy(update={"source_result_ref": tampered_source_ref})
    tampered_packet_ref = persist_funnel_executed_work_packet(store, tampered_packet)
    snapshot_wire = snapshot.model_dump(mode="json")
    claim_wire = snapshot_wire["observations"][0]["work_packet_claim"]
    claim_wire["packet_ref"] = tampered_packet_ref.model_dump(mode="json")
    claim_wire["source_result_ref"] = tampered_source_ref.model_dump(mode="json")
    tampered_snapshot = VOIModelSnapshot.model_validate(snapshot_wire)

    restored = (
        PredictiveVOIScheduler.from_snapshot(tampered_snapshot, artifact_store=store)
        .snapshot()
        .observations[0]
    )
    assert restored.work_packet_claim is None
    assert restored.score_status is ObjectiveScoreStatus.AVAILABLE
    assert restored.metadata["executed_work_packet_status"] == "available"
