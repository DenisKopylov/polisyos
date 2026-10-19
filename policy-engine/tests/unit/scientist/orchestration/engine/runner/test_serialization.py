"""Tests for runner serialization round-trips."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, model_serializer

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.skip_blockers import SkippedNodeBlocker
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.registry import ArtifactRefModel, EvidenceBundleRef
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeOutputDisposition,
    OutputAwareNodeOutcome,
)
from polisyos.scientist.orchestration.engine.runner import (
    serialization as serialization_module,
)
from polisyos.scientist.orchestration.engine.runner.serialization import (
    DeserializationError,
    deserialize_outcome,
    deserialize_state,
    deserialize_state_safe,
    serialize_context_meta,
    serialize_outcome,
    serialize_state,
    serialize_state_safe,
    worker_dispatch_sha256,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    _MUTATION_JOURNAL_ATTR,
    StateMutation,
    StateMutationJournal,
    _TrackedModelMixin,
    _wrap_mutable_value,
    branch_state,
    mutation_journal_for_state,
)

# ---------------------------------------------------------------------------
# State round-trip
# ---------------------------------------------------------------------------


class TestSerializeState:
    def test_round_trip_preserves_run_id(self) -> None:
        state = ExperimentState(run_id="test-run")
        blob = serialize_state(state)
        assert isinstance(blob, bytes)
        restored = deserialize_state(blob)
        assert isinstance(restored, ExperimentState)
        assert restored.run_id == "test-run"

    def test_round_trip_preserves_all_defaults(self) -> None:
        state = ExperimentState(run_id="rt-defaults")
        restored = deserialize_state(serialize_state(state))
        assert restored.schema_version == state.schema_version
        assert restored.inputs == {}
        assert restored.artifacts_index == {}
        assert restored.reports_index == {}
        assert restored.params == {}
        assert restored.budgets == {}
        assert restored.last_checkpoint_ref is None

    def test_round_trip_with_params(self) -> None:
        state = ExperimentState(run_id="rt-params", params={"method": "ols", "n": 1000})
        restored = deserialize_state(serialize_state(state))
        assert restored.params["method"] == "ols"
        assert restored.params["n"] == 1000

    def test_deserialize_state_accepts_list_encoded_wire_payload(self) -> None:
        state = ExperimentState(run_id="rt-wire-list")
        restored = deserialize_state(list(serialize_state(state)))
        assert restored.run_id == "rt-wire-list"


# ---------------------------------------------------------------------------
# Outcome round-trip
# ---------------------------------------------------------------------------


class TestSerializeOutcome:
    def test_round_trip_preserves_status_and_state(self) -> None:
        state = ExperimentState(run_id="outcome-run")
        outcome = NodeOutcome(status="ok", state=state)
        blob = serialize_outcome(outcome)
        assert isinstance(blob, bytes)
        restored = deserialize_outcome(blob)
        assert isinstance(restored, NodeOutcome)
        assert restored.status == "ok"
        assert restored.state.run_id == "outcome-run"

    def test_journaled_artifact_ref_round_trip_preserves_closed_wire_type_and_profile(
        self,
    ) -> None:
        profile = f"sha256:{'a' * 64}"
        source = ExperimentState(run_id="journaled-artifact-ref", artifacts_index={})
        branch = branch_state(source, write_paths=("artifacts_index.bundle",))
        original = ArtifactRef(
            artifact_id=f"sha256:{'b' * 64}",
            kind="ir.context_adaptive_parameter_bundle",
            media_type="application/json",
            manifest_profile_sha256=profile,
        )
        branch.state.artifacts_index["bundle"] = original
        tracked = branch.state.artifacts_index["bundle"]

        assert isinstance(tracked, ArtifactRef)
        assert type(tracked) is not ArtifactRef
        assert tracked.model_dump(
            mode="python", by_alias=True, exclude_none=False
        ) == original.model_dump(mode="python", by_alias=True, exclude_none=False)

        restored = deserialize_outcome(
            serialize_outcome(NodeOutcome(status="ok", state=branch.state, artifacts=[tracked]))
        )

        assert type(restored.artifacts[0]) is ArtifactRef
        assert type(restored.state.artifacts_index["bundle"]) is ArtifactRef
        assert restored.artifacts[0].model_dump(
            mode="python", by_alias=True, exclude_none=False
        ) == original.model_dump(mode="python", by_alias=True, exclude_none=False)
        assert restored.artifacts[0].manifest_profile_sha256 == profile
        journal = mutation_journal_for_state(restored.state)
        assert journal is not None
        mutation = next(row for row in journal.operations if row.path == "artifacts_index.bundle")
        assert mutation.value_kind == "artifact_ref"
        assert mutation.value["manifest_profile_sha256"] == profile

    @pytest.mark.parametrize("profile", [None, f"sha256:{'a' * 64}"])
    def test_journaled_artifact_ref_sidecar_keeps_untagged_id_and_profile_without_model_dump(
        self, monkeypatch: pytest.MonkeyPatch, profile: str | None
    ) -> None:
        source = ExperimentState(run_id="journaled-artifact-ref-no-dump", artifacts_index={})
        branch = branch_state(source, write_paths=("artifacts_index.bundle",))
        artifact = ArtifactRef(
            artifact_id=f"sha256:{'b' * 64}",
            kind="ir.context_adaptive_parameter_bundle",
            media_type="application/json",
            manifest_profile_sha256=profile,
        )
        branch.state.artifacts_index["bundle"] = artifact
        tracked = branch.state.artifacts_index["bundle"]
        journal = mutation_journal_for_state(branch.state)
        assert journal is not None
        mutation = next(row for row in journal.operations if row.path == "artifacts_index.bundle")
        operations_before = tuple(id(operation) for operation in journal.operations)
        tracked_fields_before = (
            tracked.artifact_id,
            tracked.kind,
            tracked.media_type,
            tracked.manifest_profile_sha256,
        )
        original_mutation_value = mutation.value

        def mutation_field(name: str) -> Any:
            if isinstance(original_mutation_value, BaseModel):
                return getattr(original_mutation_value, name)
            return original_mutation_value[name]

        mutation_fields_before = (
            mutation_field("artifact_id"),
            mutation_field("kind"),
            mutation_field("media_type"),
            mutation_field("manifest_profile_sha256"),
        )
        outcome = NodeOutcome(
            status="ok",
            state=branch.state,
            artifacts=[tracked],
        )

        def reject_model_dump(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("wire emission must not call model_dump")

        with monkeypatch.context() as patch:
            patch.setattr(ArtifactRef, "model_dump", reject_model_dump)
            wire = serialize_outcome(outcome)

        content = json.loads(wire)["value"]
        operation = next(
            row
            for row in content["state_mutations"]
            if row["value"]["path"] == "artifacts_index.bundle"
        )
        wire_mutation_value = operation["value"]["value"]
        expected_mutation_value = {
            "artifact_id": f"sha256:{'b' * 64}",
            "kind": "ir.context_adaptive_parameter_bundle",
            "media_type": "application/json",
        }
        if profile is not None:
            expected_mutation_value["manifest_profile_sha256"] = profile
        assert wire_mutation_value == expected_mutation_value
        assert "$wire_model" not in wire_mutation_value
        assert branch.state.artifacts_index["bundle"] is tracked
        assert (
            tracked.artifact_id,
            tracked.kind,
            tracked.media_type,
            tracked.manifest_profile_sha256,
        ) == tracked_fields_before
        assert mutation.value is original_mutation_value
        assert (
            mutation_field("artifact_id"),
            mutation_field("kind"),
            mutation_field("media_type"),
            mutation_field("manifest_profile_sha256"),
        ) == mutation_fields_before
        assert tuple(id(operation) for operation in journal.operations) == operations_before
        restored = deserialize_outcome(wire)
        journal = mutation_journal_for_state(restored.state)
        assert journal is not None
        restored_mutation = next(
            row for row in journal.operations if row.path == "artifacts_index.bundle"
        )
        assert restored_mutation.value["artifact_id"] == f"sha256:{'b' * 64}"
        assert restored_mutation.value.get("manifest_profile_sha256") == profile

    def test_journaled_state_graph_rejects_cycle_before_any_recursive_projection(
        self,
    ) -> None:
        branch = branch_state(
            ExperimentState(run_id="journaled-state-cycle", params={}),
            write_paths=("params",),
        )
        journal = mutation_journal_for_state(branch.state)
        assert journal is not None
        cycle: list[Any] = []
        cycle.append(cycle)
        dict.__setitem__(branch.state.params, "cycle", cycle)
        outcome = NodeOutcome.model_construct(
            status="fail",
            state=branch.state,
            artifacts=[],
            events=[],
            error=None,
            skip_blocker=None,
        )
        operations_before = tuple(id(operation) for operation in journal.operations)

        with pytest.raises(TypeError, match="Cycle detected while serializing sequence"):
            serialize_outcome(outcome)

        assert branch.state.params["cycle"] is cycle
        assert cycle[0] is cycle
        assert tuple(id(operation) for operation in journal.operations) == operations_before

    def test_journaled_state_graph_rejects_depth_before_any_recursive_projection(
        self,
    ) -> None:
        branch = branch_state(
            ExperimentState(run_id="journaled-state-depth", params={}),
            write_paths=("params",),
        )
        journal = mutation_journal_for_state(branch.state)
        assert journal is not None
        nested: Any = "leaf"
        for _ in range(140):
            nested = [nested]
        dict.__setitem__(branch.state.params, "nested", nested)
        outcome = NodeOutcome.model_construct(
            status="fail",
            state=branch.state,
            artifacts=[],
            events=[],
            error=None,
            skip_blocker=None,
        )
        operations_before = tuple(id(operation) for operation in journal.operations)

        with pytest.raises(TypeError, match="Wire serialization depth exceeds"):
            serialize_outcome(outcome)

        assert branch.state.params["nested"] is nested
        assert tuple(id(operation) for operation in journal.operations) == operations_before

    def test_journaled_state_graph_rejects_unregistered_tracker_without_dump_projection(
        self,
    ) -> None:
        class UnregisteredTrackedArtifactRef(_TrackedModelMixin, ArtifactRef):
            _original_model_type = ArtifactRef

        branch = branch_state(
            ExperimentState(run_id="journaled-state-unregistered", params={}),
            write_paths=("params",),
        )
        journal = mutation_journal_for_state(branch.state)
        assert journal is not None
        forged = UnregisteredTrackedArtifactRef(
            artifact_id=f"sha256:{'c' * 64}",
            kind="ir.context_adaptive_parameter_bundle",
            media_type="application/json",
            manifest_profile_sha256=f"sha256:{'d' * 64}",
        )
        dict.__setitem__(branch.state.params, "forged", forged)
        outcome = NodeOutcome.model_construct(
            status="fail",
            state=branch.state,
            artifacts=[],
            events=[],
            error=None,
            skip_blocker=None,
        )
        operations_before = tuple(id(operation) for operation in journal.operations)

        with pytest.raises(TypeError, match="registered tracked model type"):
            serialize_outcome(outcome)

        assert branch.state.params["forged"] is forged
        assert tuple(id(operation) for operation in journal.operations) == operations_before

    def test_journaled_state_graph_never_calls_nested_model_serializer_before_wire_guard(
        self,
    ) -> None:
        dump_calls: list[str] = []

        class DumpTrap(BaseModel):
            payload: str

            @model_serializer(mode="plain")
            def serialize_for_test(self) -> dict[str, str]:
                dump_calls.append("called")
                raise AssertionError("pre-encode model serialization was reached")

        branch = branch_state(
            ExperimentState(run_id="journaled-state-prewalk-trap", params={}),
            write_paths=("params",),
        )
        journal = mutation_journal_for_state(branch.state)
        assert journal is not None
        trap = DumpTrap(payload="must remain unvisited")
        dict.__setitem__(branch.state.params, "trap", trap)
        outcome = NodeOutcome.model_construct(
            status="fail",
            state=branch.state,
            artifacts=[],
            events=[],
            error=None,
            skip_blocker=None,
        )
        operations_before = tuple(id(operation) for operation in journal.operations)

        with pytest.raises(TypeError, match="Unsupported model on runner wire"):
            serialize_outcome(outcome)

        assert dump_calls == []
        assert branch.state.params["trap"] is trap
        assert tuple(id(operation) for operation in journal.operations) == operations_before

    def test_registered_trackers_cross_recursive_wire_entrypoints_and_outcome_fields(
        self,
    ) -> None:
        profile = f"sha256:{'e' * 64}"
        source = ExperimentState(run_id="tracked-wire-entrypoints", artifacts_index={})
        branch = branch_state(source, write_paths=("artifacts_index", "params"))
        artifact = ArtifactRef(
            artifact_id=f"sha256:{'f' * 64}",
            kind="ir.context_adaptive_parameter_bundle",
            media_type="application/json",
            manifest_profile_sha256=profile,
        )
        branch.state.artifacts_index["bundle"] = artifact
        tracked_artifact = branch.state.artifacts_index["bundle"]
        journal = mutation_journal_for_state(branch.state)
        assert journal is not None

        event = NodeEvent(
            level="info",
            code="test.tracked_event",
            message="tracked event",
            attrs={"ordinal": 7},
        )
        tracked_event = _wrap_mutable_value(event, ("params", "event"), journal)
        error = NodeError(
            code="test.tracked_error",
            message="tracked error",
            details={"phase": "worker", "attempt": 2},
        )
        tracked_error = _wrap_mutable_value(error, ("params", "error"), journal)
        blocker = SkippedNodeBlocker(
            node_id="tracked-node",
            alias="optional-source",
            node_kind="causal",
            reason="declared optional input is unavailable",
            missing_input="source_pack",
            owner="source-verification",
            phase="execute",
            downstream_impact="scorecard remains limited",
            allowed_profile="research",
            closeout_blocking_policy="block",
            scorecard_blocking_policy="block",
            approval_blocking_policy="block",
            public_export_blocking_policy="block",
        )
        tracked_blocker = _wrap_mutable_value(blocker, ("params", "blocker"), journal)

        assert type(tracked_artifact) is not ArtifactRef
        assert type(tracked_event) is not NodeEvent
        assert type(tracked_error) is not NodeError
        assert type(tracked_blocker) is not SkippedNodeBlocker

        tracked_before = [
            model.model_dump(mode="python", by_alias=True, exclude_none=False)
            for model in (
                tracked_artifact,
                tracked_event,
                tracked_error,
                tracked_blocker,
            )
        ]
        journal_before = [
            row.model_dump(mode="python", by_alias=True, exclude_none=False)
            for row in journal.operations
        ]
        assert tracked_before[0]["manifest_profile_sha256"] == profile
        assert tracked_before[1]["attrs"] == {"ordinal": 7}
        assert tracked_before[2]["details"] == {"phase": "worker", "attempt": 2}
        assert tracked_before[3]["node_id"] == "tracked-node"

        failed = NodeOutcome.model_construct(
            status="fail",
            state=branch.state,
            artifacts=[tracked_artifact],
            events=[tracked_event],
            error=tracked_error,
            skip_blocker=None,
        )
        restored_failure = deserialize_outcome(serialize_outcome(failed))
        assert type(restored_failure.artifacts[0]) is ArtifactRef
        assert type(restored_failure.events[0]) is NodeEvent
        assert type(restored_failure.error) is NodeError
        assert restored_failure.artifacts[0].manifest_profile_sha256 == profile
        assert restored_failure.events[0].attrs == {"ordinal": 7}
        assert restored_failure.error.details == {"phase": "worker", "attempt": 2}

        skipped = NodeOutcome.model_construct(
            status="skip",
            state=branch.state,
            artifacts=[],
            events=[],
            error=None,
            skip_blocker=tracked_blocker,
        )
        restored_skip = deserialize_outcome(serialize_outcome(skipped))
        assert type(restored_skip.skip_blocker) is SkippedNodeBlocker
        assert restored_skip.skip_blocker.node_id == "tracked-node"
        assert restored_skip.skip_blocker.missing_input == "source_pack"

        state_with_tracker = source.model_copy(
            update={"artifacts_index": {"bundle": tracked_artifact}}
        )
        restored_state = deserialize_state(serialize_state(state_with_tracker))
        assert type(restored_state.artifacts_index["bundle"]) is ArtifactRef
        assert restored_state.artifacts_index["bundle"].manifest_profile_sha256 == profile

        dispatch = {
            "node_id": "tracked-node",
            "alias": "tracked-entrypoint",
            "state_bytes": b"state",
            "trace_carrier": {},
            "timeout_s": None,
            "max_retries": 0,
            "context_meta": {},
        }
        assert worker_dispatch_sha256(params={"event": tracked_event}, **dispatch) == (
            worker_dispatch_sha256(params={"event": event}, **dispatch)
        )

        # State-only wire keeps the established non-journal contract, including
        # when its root is the engine's exact branch view.
        state_only = deserialize_state(serialize_state(branch.state))
        assert type(state_only) is ExperimentState
        assert state_only.artifacts_index["bundle"].manifest_profile_sha256 == profile
        assert mutation_journal_for_state(state_only) is None

        # Emission uses a canonical wire projection and never edits the live
        # tracked values or their source journal.
        assert [
            model.model_dump(mode="python", by_alias=True, exclude_none=False)
            for model in (
                tracked_artifact,
                tracked_event,
                tracked_error,
                tracked_blocker,
            )
        ] == tracked_before
        assert [
            row.model_dump(mode="python", by_alias=True, exclude_none=False)
            for row in journal.operations
        ] == journal_before

    def test_unregistered_tracker_cannot_claim_wire_model_identity(self) -> None:
        class UnregisteredTrackedArtifactRef(_TrackedModelMixin, ArtifactRef):
            _original_model_type = ArtifactRef

        forged = UnregisteredTrackedArtifactRef(
            artifact_id=f"sha256:{'c' * 64}",
            kind="ir.context_adaptive_parameter_bundle",
            media_type="application/json",
            manifest_profile_sha256=f"sha256:{'d' * 64}",
        )
        outcome = NodeOutcome.model_construct(
            status="ok",
            state=ExperimentState(run_id="forged-tracker"),
            artifacts=[forged],
            events=[],
            error=None,
            skip_blocker=None,
        )

        with pytest.raises(TypeError, match="registered tracked model type"):
            serialize_outcome(outcome)

    def test_journaled_outcome_round_trip_preserves_same_value_and_delete_ops(
        self,
    ) -> None:
        source = ExperimentState(
            run_id="outcome-mutation-journal",
            params={"same": 4, "stale": 1},
        )
        branch = branch_state(source, write_paths=("params",)).state
        branch.params["same"] = 4
        del branch.params["stale"]

        restored = deserialize_outcome(serialize_outcome(NodeOutcome(status="ok", state=branch)))
        journal = mutation_journal_for_state(restored.state)
        assert journal is not None
        assert [(row.path, row.operation, row.value) for row in journal.operations] == [
            ("params.same", "set", 4),
            ("params.stale", "delete", None),
        ]

        plain = NodeOutcome(status="ok", state=ExperimentState(run_id="plain-outcome"))
        plain_wire = json.loads(serialize_outcome(plain))["value"]
        assert set(plain_wire) == {
            "status",
            "state",
            "artifacts",
            "events",
            "error",
            "skip_blocker",
        }
        assert deserialize_outcome(serialize_outcome(plain)).state.run_id == "plain-outcome"

    def test_worker_dispatch_encodes_original_mapping_inputs_without_dict_projection(
        self,
    ) -> None:
        class ItemsOnlyMapping(Mapping[str, Any]):
            def __getitem__(self, key: str) -> Any:
                if key != "boundary":
                    raise KeyError(key)
                return "preserved"

            def __iter__(self) -> Iterator[str]:
                raise AssertionError("worker dispatch must not normalize via dict")

            def __len__(self) -> int:
                return 1

            def items(self) -> Iterable[tuple[str, Any]]:
                return (("boundary", "preserved"),)

        mapping = ItemsOnlyMapping()
        actual = worker_dispatch_sha256(
            node_id="mapping-boundary",
            alias="mapping-boundary",
            params=mapping,
            state_bytes=b"state",
            trace_carrier=mapping,
            timeout_s=None,
            max_retries=0,
            context_meta=mapping,
        )
        expected = worker_dispatch_sha256(
            node_id="mapping-boundary",
            alias="mapping-boundary",
            params={"boundary": "preserved"},
            state_bytes=b"state",
            trace_carrier={"boundary": "preserved"},
            timeout_s=None,
            max_retries=0,
            context_meta={"boundary": "preserved"},
        )

        assert actual == expected

    @pytest.mark.parametrize("invalid_mutation", ["extra", "foreign_path"])
    def test_journaled_outcome_decoder_rejects_invalid_mutation_fields(
        self, invalid_mutation: str
    ) -> None:
        source = ExperimentState(run_id="outcome-invalid-mutation", params={"value": 1})
        branch = branch_state(source, write_paths=("params",)).state
        branch.params["value"] = 2
        payload = json.loads(serialize_outcome(NodeOutcome(status="ok", state=branch)))
        payload = payload["value"]
        mutation = payload["state_mutations"][0]["value"]
        if invalid_mutation == "extra":
            mutation["unexpected"] = True
        else:
            mutation["path"] = "not_an_experiment_state_field.child"

        with pytest.raises(DeserializationError):
            deserialize_outcome(json.dumps(payload, separators=(",", ":")).encode())

    def test_round_trip_preserves_empty_collections(self) -> None:
        state = ExperimentState(run_id="empty-cols")
        outcome = NodeOutcome(status="ok", state=state)
        restored = deserialize_outcome(serialize_outcome(outcome))
        assert restored.artifacts == []
        assert restored.events == []
        assert restored.error is None

    def test_round_trip_skip_status(self) -> None:
        state = ExperimentState(run_id="skip-run")
        outcome = NodeOutcome(status="skip", state=state)
        restored = deserialize_outcome(serialize_outcome(outcome))
        assert restored.status == "skip"

    def test_deserialize_outcome_accepts_list_encoded_wire_payload(self) -> None:
        outcome = NodeOutcome(status="ok", state=ExperimentState(run_id="out-wire-list"))
        restored = deserialize_outcome(list(serialize_outcome(outcome)))
        assert restored.state.run_id == "out-wire-list"


class _LegacyJournalDict(dict[str, Any]):
    """Legacy nested owner shape accepted by the old state journal lookup."""


class _DescriptorLegacyJournalDict(dict[str, Any]):
    """Descriptor-only owner used to pin the bounded compatibility residual."""

    def __init__(self, journal: StateMutationJournal) -> None:
        super().__init__({"value": "descriptor-owner"})
        self.calls = 0
        self.journal = journal

    @property
    def _polisyos_mutation_journal(self) -> StateMutationJournal:
        self.calls += 1
        return self.journal


def _owner_journal(name: str) -> StateMutationJournal:
    return StateMutationJournal(
        isolated_fields=(),
        isolated_paths=(),
        operations=[StateMutation(path=f"params.{name}", operation="set", value=name)],
    )


def _legacy_owner(name: str) -> _LegacyJournalDict:
    value = _LegacyJournalDict({"value": name})
    object.__setattr__(value, "_polisyos_mutation_journal", _owner_journal(name))
    return value


def _journaled_wire_payload(blob: bytes) -> dict[str, Any]:
    outer = json.loads(blob)
    assert outer["wire_schema"] == "polisyos.scientist.outcome_wire.v2"
    payload = outer["value"]
    assert payload["wire_schema"] == "polisyos.scientist.node_outcome.mutations.v1"
    return payload


def _journaled_wire_operation_payloads(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Read the closed StateMutation model payloads from a journal sidecar."""
    encoded_operations = payload["state_mutations"]
    assert isinstance(encoded_operations, list)
    operation_payloads: list[dict[str, Any]] = []
    for encoded in encoded_operations:
        assert isinstance(encoded, dict)
        assert encoded == {
            "_type": "model",
            "module": StateMutation.__module__,
            "qualname": StateMutation.__qualname__,
            "value": encoded.get("value"),
        }
        operation = encoded["value"]
        assert isinstance(operation, dict)
        operation_payloads.append(operation)
    return operation_payloads


def _roundtrip_journal(blob: bytes) -> StateMutationJournal:
    restored = deserialize_outcome(blob)
    journal = mutation_journal_for_state(restored.state)
    assert journal is not None
    return journal


def test_nested_legacy_journal_owner_is_collected_inside_guarded_state_walk() -> None:
    owner = _legacy_owner("nested")
    journal = owner.__dict__["_polisyos_mutation_journal"]
    state = ExperimentState(run_id="nested-legacy-owner")
    object.__setattr__(state, "params", {"branch": {"owner": owner}})
    before_operations = list(journal.operations)

    blob = serialize_outcome(NodeOutcome(status="ok", state=state))
    payload = _journaled_wire_payload(blob)

    assert payload["state_mutations"]
    restored_journal = _roundtrip_journal(blob)
    assert [(row.path, row.value) for row in restored_journal.operations] == [
        ("params.nested", "nested")
    ]
    assert journal.operations == before_operations
    assert owner.__dict__["_polisyos_mutation_journal"] is journal


def test_descriptor_only_legacy_owner_is_not_executed() -> None:
    descriptor_owner = _DescriptorLegacyJournalDict(_owner_journal("descriptor"))
    state = ExperimentState(run_id="descriptor-owner-residual")
    object.__setattr__(state, "params", {"owner": descriptor_owner})

    outer = json.loads(serialize_outcome(NodeOutcome(status="ok", state=state)))

    assert outer["wire_schema"] == "polisyos.scientist.outcome_wire.v2"
    assert "state_mutations" not in outer["value"]
    assert outer["value"]["state"]["params"]["owner"] == {"value": "descriptor-owner"}
    assert descriptor_owner.calls == 0


def test_root_journal_wins_over_nested_legacy_owner() -> None:
    state = branch_state(
        ExperimentState(run_id="root-owner-wins"),
        write_paths=("params",),
    ).state
    root_journal = mutation_journal_for_state(state)
    assert root_journal is not None
    nested_owner = _legacy_owner("nested")
    object.__setattr__(state, "params", {"owner": nested_owner})

    payload = _journaled_wire_payload(serialize_outcome(NodeOutcome(status="ok", state=state)))

    assert payload["state_mutations"] == []
    assert root_journal.operations == []


@pytest.mark.parametrize(
    ("instance_first", "expected_path"),
    [("params", "params.params"), ("causal_method_params", "params.causal")],
)
def test_nested_legacy_owner_follows_instance_dict_order_without_changing_wire_order(
    instance_first: str,
    expected_path: str,
) -> None:
    first = _legacy_owner("params")
    second = _legacy_owner("causal")
    state = ExperimentState(run_id="legacy-model-order")
    object.__setattr__(state, "params", {"owner": first})
    object.__setattr__(state, "causal_method_params", {"owner": second})
    namespace = object.__getattribute__(state, "__dict__")
    field_order = [
        instance_first,
        "causal_method_params" if instance_first == "params" else "params",
    ]
    reordered = {
        name: namespace[name]
        for name in namespace
        if name not in {"params", "causal_method_params"}
    }
    for name in field_order:
        reordered[name] = namespace[name]
    namespace.clear()
    namespace.update(reordered)

    payload = _journaled_wire_payload(serialize_outcome(NodeOutcome(status="ok", state=state)))

    assert payload["state_mutations"]
    selected_journal = _roundtrip_journal(serialize_outcome(NodeOutcome(status="ok", state=state)))
    assert [row.path for row in selected_journal.operations] == [expected_path]
    state_fields = list(payload["outcome"]["state"])
    assert state_fields.index("params") < state_fields.index("causal_method_params")


@pytest.mark.parametrize("container_kind", ["mapping", "sequence"])
def test_nested_legacy_owner_preserves_mapping_and_sequence_first_match(
    container_kind: str,
) -> None:
    first = _legacy_owner("first")
    second = _legacy_owner("second")
    if container_kind == "mapping":
        nested: Any = {"first": first, "second": second}
    else:
        nested = [first, second]
    state = ExperimentState(run_id=f"legacy-{container_kind}-order")
    object.__setattr__(state, "params", {"nested": nested})

    payload = _journaled_wire_payload(serialize_outcome(NodeOutcome(status="ok", state=state)))

    assert payload["state_mutations"]
    assert [
        row.path
        for row in _roundtrip_journal(
            serialize_outcome(NodeOutcome(status="ok", state=state))
        ).operations
    ] == ["params.first"]


def test_distinct_tracked_journals_refuse_but_root_owner_remains_authoritative() -> None:
    first_source = ExperimentState(run_id="tracked-first", params={"items": []})
    second_source = ExperimentState(run_id="tracked-second", params={"items": []})
    first_tracked = branch_state(first_source, write_paths=("params.items",)).state.params["items"]
    second_tracked = branch_state(second_source, write_paths=("params.items",)).state.params[
        "items"
    ]
    plain = ExperimentState(run_id="conflicting-tracked-owners")
    object.__setattr__(plain, "params", {"first": first_tracked, "second": second_tracked})

    with pytest.raises(TypeError, match="Conflicting tracked mutation journals"):
        serialize_outcome(NodeOutcome(status="ok", state=plain))

    rooted = branch_state(
        ExperimentState(run_id="root-over-tracker"), write_paths=("params",)
    ).state
    object.__setattr__(rooted, "params", {"first": first_tracked, "second": second_tracked})
    payload = _journaled_wire_payload(serialize_outcome(NodeOutcome(status="ok", state=rooted)))
    assert payload["state_mutations"] == []


def test_one_shared_nested_tracker_journal_is_selected_once() -> None:
    source = ExperimentState(
        run_id="shared-tracker-source",
        params={"first": [], "second": []},
    )
    tracked_state = branch_state(
        source,
        write_paths=("params.first", "params.second"),
    ).state
    first = tracked_state.params["first"]
    second = tracked_state.params["second"]
    state = ExperimentState(run_id="shared-tracker-owner")
    object.__setattr__(state, "params", {"first": first, "second": second})
    first.append("first-write")
    second.append("second-write")
    source_journal = mutation_journal_for_state(tracked_state)
    assert source_journal is not None
    assert first is not second
    assert object.__getattribute__(first, "_mutation_journal") is source_journal
    assert object.__getattribute__(second, "_mutation_journal") is source_journal
    expected = [
        ("params.first", "append", "json", "first-write"),
        ("params.second", "append", "json", "second-write"),
    ]
    assert [
        (row.path, row.operation, row.value_kind, row.value) for row in source_journal.operations
    ] == expected

    blob = serialize_outcome(NodeOutcome(status="ok", state=state))
    payload = _journaled_wire_payload(blob)
    operation_payloads = _journaled_wire_operation_payloads(payload)
    assert [
        (row["path"], row["operation"], row["value_kind"], row["value"])
        for row in operation_payloads
    ] == expected
    restored = deserialize_outcome(blob)
    restored_journal = mutation_journal_for_state(restored.state)
    assert restored_journal is not None
    assert restored_journal is not source_journal
    assert [
        (row.path, row.operation, row.value_kind, row.value) for row in restored_journal.operations
    ] == expected
    assert [
        (row.path, row.operation, row.value_kind, row.value) for row in source_journal.operations
    ] == expected


def test_legacy_owner_after_tracked_owner_keeps_legacy_selection() -> None:
    tracked_source = ExperimentState(run_id="tracked-before-legacy", params={"items": []})
    tracked = branch_state(tracked_source, write_paths=("params.items",)).state.params["items"]
    legacy = _legacy_owner("legacy")
    state = ExperimentState(run_id="legacy-over-tracker")
    object.__setattr__(state, "params", {"tracked": tracked, "legacy": legacy})

    payload = _journaled_wire_payload(serialize_outcome(NodeOutcome(status="ok", state=state)))

    assert payload["state_mutations"]
    assert [
        row.path
        for row in _roundtrip_journal(
            serialize_outcome(NodeOutcome(status="ok", state=state))
        ).operations
    ] == ["params.legacy"]


def test_owner_outside_state_subtree_does_not_select_journal() -> None:
    state = ExperimentState(run_id="error-owner-excluded")
    outcome = NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(
            code="node.failed",
            message="failed",
            details={"owner": _legacy_owner("outside")},
        ),
    )

    outer = json.loads(serialize_outcome(outcome))

    assert outer["wire_schema"] == "polisyos.scientist.outcome_wire.v2"
    assert "state_mutations" not in outer["value"]
    assert outer["value"]["error"]["details"]["owner"] == {"value": "outside"}


def test_state_walk_refuses_invalid_journaled_state_after_complete_projection() -> None:
    owner = _legacy_owner("invalid")
    invalid = ExperimentState.model_construct(run_id="invalid-state", schema_version="bad")
    object.__setattr__(invalid, "params", {"owner": owner})

    with pytest.raises(ValueError):
        serialize_outcome(NodeOutcome(status="ok", state=invalid))

    ordinary = ExperimentState.model_construct(run_id="invalid-ordinary", schema_version="bad")
    encoded = json.loads(serialize_outcome(NodeOutcome(status="ok", state=ordinary)))
    assert encoded["value"]["state"]["schema_version"] == "bad"


def test_journaled_state_validation_normalizes_before_wire_emission() -> None:
    owner = _legacy_owner("normalize")
    state = ExperimentState.model_construct(
        run_id="normalize-state",
        inputs={
            "source": {
                "artifact_id": "sha256:" + "a" * 64,
                "kind": "test.source",
                "media_type": "application/json",
            }
        },
    )
    object.__setattr__(state, "params", {"owner": owner})

    restored = deserialize_outcome(serialize_outcome(NodeOutcome(status="ok", state=state)))

    assert isinstance(restored.state.inputs["source"], ArtifactRef)
    assert restored.state.inputs["source"].artifact_id.root == "sha256:" + "a" * 64


def test_artifact_type_facades_preserve_defining_owner_identity() -> None:
    from polisyos.core.artifacts import ArtifactID as CoreArtifactID
    from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
    from polisyos.core.artifacts.ids import ArtifactID as DefiningCoreArtifactID
    from polisyos.core.artifacts.manifest import ArtifactRef as DefiningCoreArtifactRef
    from polisyos.ir import ArtifactID as RootIRArtifactID
    from polisyos.ir.artifacts import ArtifactID as IRArtifactID
    from polisyos.ir.artifacts.contracts import ArtifactID as DefiningIRArtifactID
    from polisyos.ir.registry import ArtifactRefModel as IRArtifactRefModel
    from polisyos.ir.registry import EvidenceBundleRef as IREvidenceBundleRef
    from polisyos.ir.registry.refs import ArtifactRefModel as DefiningIRArtifactRefModel
    from polisyos.ir.registry.refs import EvidenceBundleRef as DefiningIREvidenceBundleRef

    assert CoreArtifactID is DefiningCoreArtifactID
    assert CoreArtifactRef is DefiningCoreArtifactRef
    assert IRArtifactID is DefiningIRArtifactID
    assert RootIRArtifactID is IRArtifactID
    assert IRArtifactRefModel is DefiningIRArtifactRefModel
    assert IREvidenceBundleRef is DefiningIREvidenceBundleRef
    assert IRArtifactID is not CoreArtifactID


def test_artifact_ref_sidecar_accepts_typed_family_and_decoded_plain_mapping() -> None:
    """Exercise StateMutation sidecar encoding with synthetic operations outside state field validation."""
    from polisyos.core.artifacts import ArtifactID as CoreArtifactID
    from polisyos.ir.artifacts import ArtifactID as IRArtifactID

    typed_refs: list[ArtifactRefModel | ArtifactRef] = [
        ArtifactRef(
            artifact_id=CoreArtifactID("sha256:" + "b" * 64),
            kind="test.core_ref",
            media_type="application/json",
        ),
        ArtifactRefModel(
            artifact_id=IRArtifactID("sha256:" + "c" * 64),
            kind="test.base_ref",
            media_type="application/json",
        ),
        EvidenceBundleRef(artifact_id=IRArtifactID("sha256:" + "d" * 64)),
    ]
    journal = _owner_journal("ref")
    journal.operations[:] = [
        StateMutation(
            path="params.ref",
            operation="set",
            value=reference,
            value_kind="artifact_ref",
        )
        for reference in typed_refs
    ]
    journal.operations.append(
        StateMutation(
            path="params.decoded_ref",
            operation="set",
            value={
                "artifact_id": "sha256:" + "e" * 64,
                "kind": "test.decoded_ref",
                "media_type": "application/json",
                "unknown_field": {"preserved": True},
            },
            value_kind="artifact_ref",
        )
    )
    state = branch_state(
        ExperimentState(run_id="typed-reference-sidecar"), write_paths=("params",)
    ).state
    root_journal = mutation_journal_for_state(state)
    assert root_journal is not None
    root_journal.operations[:] = journal.operations

    blob = serialize_outcome(NodeOutcome(status="ok", state=state))
    payload = _journaled_wire_payload(blob)
    restored = deserialize_outcome(blob)
    operations = mutation_journal_for_state(restored.state).operations

    assert type(operations[0].value) is dict
    assert operations[0].value["artifact_id"] == "sha256:" + "b" * 64
    assert "manifest_profile_sha256" not in operations[0].value
    assert operations[1].value["kind"] == "test.base_ref"
    assert operations[2].value["kind"] == "fabric.evidence_bundle"
    assert operations[3].value["unknown_field"] == {"preserved": True}


def test_artifact_ref_sidecar_rejects_arbitrary_models_and_custom_id_stringification() -> None:
    """Exercise the synthetic sidecar value codec rejection boundary directly."""

    class _UnexpectedRef(BaseModel):
        artifact_id: Any
        kind: str
        media_type: str

        def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError("untrusted model serializer must not run")

    class _StringTrap:
        def __init__(self) -> None:
            self.calls = 0

        def __str__(self) -> str:
            self.calls += 1
            raise AssertionError("arbitrary artifact_id stringification must not run")

    trap = _StringTrap()
    invalid_values = [
        _UnexpectedRef(artifact_id="sha256:" + "e" * 64, kind="x", media_type="y"),
        {"artifact_id": trap, "kind": "x", "media_type": "y"},
        {"artifact_id": "SHA256:" + "f" * 64, "kind": "x", "media_type": "y"},
    ]
    for invalid_value in invalid_values:
        state = branch_state(
            ExperimentState(run_id="invalid-artifact-ref-sidecar"),
            write_paths=("params",),
        ).state
        journal = mutation_journal_for_state(state)
        assert journal is not None
        journal.operations.append(
            StateMutation(
                path="params.ref",
                operation="set",
                value=invalid_value,
                value_kind="artifact_ref",
            )
        )
        with pytest.raises(TypeError):
            serialize_outcome(NodeOutcome(status="ok", state=state))
    assert trap.calls == 0


def test_actual_core_and_ir_reference_producers_admit_and_emit_canonical_untagged_ids() -> None:
    from polisyos.core.artifacts import ArtifactID as CoreArtifactID
    from polisyos.ir.artifacts import ArtifactID as IRArtifactID
    from polisyos.scientist.orchestration.engine.state_branching import (
        _owned_wire_model_origin,
    )

    references: list[tuple[str, ArtifactRef | ArtifactRefModel, str]] = [
        (
            "sha256:" + "1" * 64,
            ArtifactRef(
                artifact_id=CoreArtifactID("sha256:" + "1" * 64),
                kind="test.core_ref",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "6" * 64,
            ),
            "sha256:" + "6" * 64,
        ),
        (
            "sha256:" + "2" * 64,
            ArtifactRefModel(
                artifact_id=IRArtifactID("sha256:" + "2" * 64),
                kind="test.ir_ref",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "7" * 64,
            ),
            "sha256:" + "7" * 64,
        ),
        (
            "sha256:" + "3" * 64,
            EvidenceBundleRef(
                artifact_id=IRArtifactID("sha256:" + "3" * 64),
                manifest_profile_sha256="sha256:" + "8" * 64,
            ),
            "sha256:" + "8" * 64,
        ),
    ]

    expected_operations = [
        ("inputs.ref", "set", "artifact_ref", "missing", "missing"),
        ("inputs.ref", "delete", "json", "present", "model"),
        ("artifacts_index.ref", "set", "artifact_ref", "missing", "missing"),
        ("artifacts_index.ref", "delete", "json", "present", "model"),
    ]

    for index, (expected_id, reference, profile) in enumerate(references):
        # These are validated constructor inputs. Pydantic admits the IR models
        # and projects them to the declared Core ArtifactRef state-field type.
        state = ExperimentState(
            run_id=f"typed-ref-producer-{index}",
            inputs={"admitted": reference},
            artifacts_index={"admitted": reference},
        )
        admitted_input = state.inputs["admitted"]
        admitted_index = state.artifacts_index["admitted"]
        for admitted in (admitted_input, admitted_index):
            assert type(admitted) is ArtifactRef
            assert type(admitted.artifact_id) is CoreArtifactID
            assert admitted.artifact_id.root == expected_id
            assert admitted.kind == reference.kind
            assert admitted.media_type == reference.media_type
            assert admitted.manifest_profile_sha256 == profile

        if isinstance(reference, ArtifactRefModel):
            assert type(reference.artifact_id) is IRArtifactID
            # Exercise the existing artifacts-index normalization owner with
            # the genuine producer value. Inputs uses its validated Core value.
            index_value: ArtifactRef | ArtifactRefModel = reference
        else:
            assert type(reference.artifact_id) is CoreArtifactID
            index_value = admitted_index

        def assert_registered_core_view(
            value: ArtifactRef,
            *,
            expected_value_id: str,
            expected_kind: str,
            expected_media_type: str,
            expected_profile: str,
        ) -> None:
            assert _owned_wire_model_origin(value) is ArtifactRef
            assert _owned_wire_model_origin(value.artifact_id) is CoreArtifactID
            assert value.artifact_id.root == expected_value_id
            assert value.kind == expected_kind
            assert value.media_type == expected_media_type
            assert value.manifest_profile_sha256 == expected_profile

        branch = branch_state(state, write_paths=("inputs", "artifacts_index")).state
        branch.inputs["ref"] = admitted_input
        tracked_input_value = branch.inputs["ref"]
        assert_registered_core_view(
            tracked_input_value,
            expected_value_id=expected_id,
            expected_kind=reference.kind,
            expected_media_type=reference.media_type,
            expected_profile=profile,
        )
        del branch.inputs["ref"]
        branch.artifacts_index["ref"] = index_value
        normalized_index_value = branch.artifacts_index["ref"]
        assert_registered_core_view(
            normalized_index_value,
            expected_value_id=expected_id,
            expected_kind=reference.kind,
            expected_media_type=reference.media_type,
            expected_profile=profile,
        )
        del branch.artifacts_index["ref"]

        journal = mutation_journal_for_state(branch)
        assert journal is not None
        assert [
            (row.path, row.operation, row.value_kind, row.target_presence, row.target_kind)
            for row in journal.operations
        ] == expected_operations
        # The inputs write uses the untracked constructor projection; the
        # artifacts-index owner normalizes the original IR producer before
        # both paths record their plain Core snapshot.
        for operation in (journal.operations[0], journal.operations[2]):
            assert type(operation.value) is ArtifactRef
            assert type(operation.value.artifact_id) is CoreArtifactID
            assert operation.value.artifact_id.root == expected_id
            assert operation.value.kind == reference.kind
            assert operation.value.media_type == reference.media_type
            assert operation.value.manifest_profile_sha256 == profile

        blob = serialize_outcome(NodeOutcome(status="ok", state=branch))
        payload = _journaled_wire_payload(blob)
        operation_payloads = _journaled_wire_operation_payloads(payload)
        assert len(operation_payloads) == 4
        assert [
            (
                operation["path"],
                operation["operation"],
                operation["value_kind"],
                operation["target_presence"],
                operation["target_kind"],
            )
            for operation in operation_payloads
        ] == expected_operations
        expected_ref = {
            "artifact_id": expected_id,
            "kind": reference.kind,
            "media_type": reference.media_type,
            "manifest_profile_sha256": profile,
        }
        for operation in (operation_payloads[0], operation_payloads[2]):
            assert operation["value"] == expected_ref
            assert "_type" not in operation["value"]

        restored = deserialize_outcome(blob)
        for restored_ref in (
            restored.state.inputs["admitted"],
            restored.state.artifacts_index["admitted"],
        ):
            assert type(restored_ref) is ArtifactRef
            assert type(restored_ref.artifact_id) is CoreArtifactID
            assert restored_ref.artifact_id.root == expected_id
            assert restored_ref.kind == reference.kind
            assert restored_ref.media_type == reference.media_type
            assert restored_ref.manifest_profile_sha256 == profile
        restored_journal = mutation_journal_for_state(restored.state)
        assert restored_journal is not None
        assert [
            (row.path, row.operation, row.value_kind, row.target_presence, row.target_kind)
            for row in restored_journal.operations
        ] == expected_operations
        for operation in (restored_journal.operations[0], restored_journal.operations[2]):
            assert type(operation.value) is dict
            assert operation.value == expected_ref


@pytest.mark.parametrize("id_kind", ["malformed", "custom"])
def test_synthetic_ir_reference_roots_are_rejected_by_sidecar_codec(id_kind: str) -> None:
    """Keep malformed IR roots at the codec boundary, outside state admission."""
    from polisyos.ir.artifacts import ArtifactID as IRArtifactID

    class _StringTrap:
        def __init__(self) -> None:
            self.calls = 0

        def __str__(self) -> str:
            self.calls += 1
            raise AssertionError("custom ArtifactID root must not be stringified")

    reference = EvidenceBundleRef(artifact_id=IRArtifactID("sha256:" + "5" * 64))
    trap = _StringTrap()
    if id_kind == "malformed":
        object.__setattr__(reference.artifact_id, "root", "SHA256:" + "6" * 64)
        expected_error = "Artifact reference mutation ID must be canonical sha256 text"
    else:
        object.__setattr__(reference.artifact_id, "root", trap)
        expected_error = "Artifact reference mutation ID root must be str"

    state = branch_state(
        ExperimentState(run_id=f"synthetic-ir-ref-{id_kind}"),
        write_paths=("params",),
    ).state
    journal = mutation_journal_for_state(state)
    assert journal is not None
    journal.operations.append(
        StateMutation(
            path="params.synthetic_ref",
            operation="set",
            value=reference,
            value_kind="artifact_ref",
        )
    )

    with pytest.raises(TypeError, match=expected_error):
        serialize_outcome(NodeOutcome(status="ok", state=state))
    assert trap.calls == 0


def test_registered_tracked_model_inside_state_selects_its_journal() -> None:
    from polisyos.core.artifacts import ArtifactID

    profile = "sha256:" + "4" * 64
    source = ExperimentState(
        run_id="tracked-model-owner-source",
        inputs={
            "ref": ArtifactRef(
                artifact_id=ArtifactID("sha256:" + "4" * 64),
                kind="test.tracked_ref",
                media_type="application/json",
                manifest_profile_sha256=profile,
            )
        },
    )
    branched = branch_state(source, write_paths=("inputs.ref.kind",)).state
    tracked_ref = branched.inputs["ref"]
    assert isinstance(tracked_ref, ArtifactRef)
    assert type(tracked_ref) is not ArtifactRef
    tracked_ref.kind = "test.tracked_ref.updated"
    source_journal = mutation_journal_for_state(branched)
    assert source_journal is not None
    assert any(row.path == "inputs.ref.kind" for row in source_journal.operations)

    state = ExperimentState(run_id="tracked-model-owner-consumer")
    object.__setattr__(state, "inputs", {"ref": tracked_ref})
    blob = serialize_outcome(NodeOutcome(status="ok", state=state))
    payload = _journaled_wire_payload(blob)
    operation_payloads = _journaled_wire_operation_payloads(payload)
    restored = deserialize_outcome(blob)

    assert len(operation_payloads) == 1
    assert (
        operation_payloads[0]["path"],
        operation_payloads[0]["operation"],
        operation_payloads[0]["value_kind"],
        operation_payloads[0]["value"],
    ) == ("inputs.ref.kind", "set", "json", "test.tracked_ref.updated")
    assert type(restored.state.inputs["ref"]) is ArtifactRef
    assert restored.state.inputs["ref"].artifact_id.root == "sha256:" + "4" * 64
    assert restored.state.inputs["ref"].kind == "test.tracked_ref.updated"
    assert restored.state.inputs["ref"].manifest_profile_sha256 == profile


class _CounterfeitJournal:
    """Self-labelled owner whose operations must remain unread."""

    def __init__(self) -> None:
        self.operation_reads = 0

    @property
    def __class__(self) -> type[StateMutationJournal]:
        return StateMutationJournal

    @property
    def operations(self) -> list[StateMutation]:
        self.operation_reads += 1
        raise AssertionError("counterfeit journal operations must not be read")


class _SubclassedCounterfeitJournal(StateMutationJournal):
    """Unregistered subclass whose operations must remain unread."""

    @property
    def operations(self) -> list[StateMutation]:
        self.operation_reads += 1
        raise AssertionError("subclassed journal operations must not be read")


@pytest.mark.parametrize("owner_kind", ["root", "legacy", "tracked"])
@pytest.mark.parametrize("counterfeit_kind", ["self_label", "subclass"])
def test_counterfeit_class_journal_is_rejected_at_every_wire_admission(
    owner_kind: str,
    counterfeit_kind: str,
) -> None:
    if counterfeit_kind == "self_label":
        counterfeit: _CounterfeitJournal | _SubclassedCounterfeitJournal = _CounterfeitJournal()
    else:
        counterfeit = object.__new__(_SubclassedCounterfeitJournal)
        object.__setattr__(counterfeit, "operation_reads", 0)
    assert isinstance(counterfeit, StateMutationJournal)
    state = ExperimentState(run_id=f"counterfeit-{owner_kind}-{counterfeit_kind}-journal")

    if owner_kind == "root":
        object.__setattr__(state, _MUTATION_JOURNAL_ATTR, counterfeit)
    elif owner_kind == "legacy":
        owner = _LegacyJournalDict({"value": owner_kind})
        object.__setattr__(owner, "_polisyos_mutation_journal", counterfeit)
        object.__setattr__(state, "params", {"owner": owner})
    else:
        tracked = branch_state(
            ExperimentState(run_id="counterfeit-tracked-source", params={"items": []}),
            write_paths=("params.items",),
        ).state.params["items"]
        object.__setattr__(tracked, "_mutation_journal", counterfeit)
        object.__setattr__(state, "params", {"items": tracked})

    encoded = json.loads(serialize_outcome(NodeOutcome(status="ok", state=state)))

    assert encoded["wire_schema"] == "polisyos.scientist.outcome_wire.v2"
    assert "state_mutations" not in encoded["value"]
    assert counterfeit.operation_reads == 0


def test_journaled_state_walk_refuses_cycle_after_owner_without_returning_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _legacy_owner("before-cycle")
    nested: dict[str, Any] = {"owner": owner}
    nested["self"] = nested
    state = ExperimentState(run_id="cycle-after-owner")
    object.__setattr__(state, "params", {"nested": nested})

    dumps_calls: list[bytes] = []
    monkeypatch.setattr(serialization_module, "_dumps", lambda value: dumps_calls.append(value))
    with pytest.raises(TypeError, match="Cycle detected"):
        serialize_outcome(NodeOutcome(status="ok", state=state))
    assert dumps_calls == []


def test_journaled_state_walk_refuses_over_depth_sibling_after_owner() -> None:
    owner = _legacy_owner("before-depth")
    deep: Any = "leaf"
    for _ in range(140):
        deep = [deep]
    state = ExperimentState(run_id="depth-after-owner")
    object.__setattr__(state, "params", {"owner": owner, "deep": deep})

    with pytest.raises(TypeError, match="Wire serialization depth exceeds"):
        serialize_outcome(NodeOutcome(status="ok", state=state))


# ---------------------------------------------------------------------------
# Context meta extraction
# ---------------------------------------------------------------------------


@dataclass
class _FakeRun:
    """Minimal stand-in for RunContext with the attributes serialize_context_meta reads."""

    run_id: str = "ctx-run-123"
    tenant_id: str | None = "t-1"
    cell_id: str | None = "c-1"
    run_manifest: Any = None


@dataclass
class _FakeCtx:
    """Minimal stand-in for ExecutionContext."""

    depth: int = 2
    run: Any = None


class TestSerializeContextMeta:
    def test_extracts_depth(self) -> None:
        ctx = _FakeCtx(depth=3, run=None)
        meta = serialize_context_meta(ctx)
        assert meta["depth"] == 3
        # No run → no run_id key
        assert "run_id" not in meta

    def test_extracts_run_metadata(self) -> None:
        ctx = _FakeCtx(depth=1, run=_FakeRun())
        meta = serialize_context_meta(ctx)
        assert meta["depth"] == 1
        assert meta["run_id"] == "ctx-run-123"
        assert meta["tenant_id"] == "t-1"
        assert meta["cell_id"] == "c-1"

    def test_run_without_tenant_and_cell(self) -> None:
        ctx = _FakeCtx(depth=0, run=_FakeRun(run_id="r-2", tenant_id=None, cell_id=None))
        meta = serialize_context_meta(ctx)
        assert meta["run_id"] == "r-2"
        assert meta["tenant_id"] is None
        assert meta["cell_id"] is None

    def test_extracts_registry_bundle_workflow_and_runner(self) -> None:
        registry_bundle = ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="core.registry_bundle",
            media_type="application/json",
        )
        run = _FakeRun(
            run_manifest=type(
                "Manifest",
                (),
                {
                    "registry_bundle": registry_bundle,
                    "run_id": "ctx-run-123",
                },
            )()
        )
        ctx = _FakeCtx(depth=1, run=run)
        meta = serialize_context_meta(
            ctx,
            workflow_id="scientist_default",
            runner_backend="ray",
        )
        assert meta["workflow_id"] == "scientist_default"
        assert meta["runner_backend"] == "ray"
        assert meta["registry_bundle_ref"]["artifact_id"] == "sha256:" + "a" * 64

    def test_uses_run_manifest_for_real_run_context(self, tmp_path: Path) -> None:
        store = FileSystemCAS(tmp_path)
        registry_bundle_ref = build_default_registry_bundle(
            store,
            return_selected_profile=True,
        ).bundle_ref
        run: RunContext | None = None
        try:
            run = RunContext.start(
                store=store,
                registry_bundle=registry_bundle_ref,
                run_id="real-run",
                tenant_id="tenant-a",
                cell_id="cell-a",
            )
            ctx = _FakeCtx(depth=2, run=run)
            meta = serialize_context_meta(ctx)
            assert meta["run_id"] == "real-run"
            assert meta["tenant_id"] == "tenant-a"
            assert meta["cell_id"] == "cell-a"
            assert meta["registry_bundle_ref"]["artifact_id"] == str(
                registry_bundle_ref.artifact_id
            )
        finally:
            if run is not None:
                run.suspend_for_resume()

    def test_extracts_trace_ids_when_present(self, monkeypatch) -> None:
        ctx = _FakeCtx(depth=1, run=_FakeRun())
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.runner.serialization._current_trace_ids",
            lambda: ("0" * 32, "1" * 16),
        )
        meta = serialize_context_meta(ctx)
        assert meta["trace_id"] == "0" * 32
        assert meta["span_id"] == "1" * 16

    def test_current_trace_ids_records_degraded_path_on_runtime_error(self, monkeypatch) -> None:
        pytest.importorskip("opentelemetry.trace")
        import opentelemetry.trace as otel_trace

        degraded: list[dict[str, object]] = []

        monkeypatch.setattr(
            serialization_module,
            "emit_degraded_path",
            lambda **kwargs: degraded.append(kwargs) or {"reason": kwargs["reason"]},
        )

        def _boom() -> object:
            raise RuntimeError("trace backend unavailable")

        monkeypatch.setattr(otel_trace, "get_current_span", _boom)

        trace_id, span_id = serialization_module._current_trace_ids()

        assert trace_id is None
        assert span_id is None
        assert any(item["reason"] == "trace_context_read_failed" for item in degraded)


# ---------------------------------------------------------------------------
# Safe serialization (version 1 — header + integrity hash)
# ---------------------------------------------------------------------------


class TestSafeSerialisation:
    def test_round_trip_safe(self) -> None:
        state = ExperimentState(run_id="safe-run")
        payload, hex_digest = serialize_state_safe(state)
        assert isinstance(payload, bytes)
        assert len(hex_digest) == 64
        restored = deserialize_state_safe(payload)
        assert restored.run_id == "safe-run"

    def test_version_mismatch_raises(self) -> None:
        bad = b"\x99" + b"some json" + b"\x00" * 32
        with pytest.raises(DeserializationError, match="Unsupported serialization version"):
            deserialize_state_safe(bad)

    def test_integrity_failure_raises(self) -> None:
        state = ExperimentState(run_id="tamper")
        payload, _ = serialize_state_safe(state)
        # Flip a byte in the JSON body
        corrupted = payload[:5] + bytes([payload[5] ^ 0xFF]) + payload[6:]
        with pytest.raises(DeserializationError, match="Integrity check failed"):
            deserialize_state_safe(corrupted)

    def test_truncated_payload_raises(self) -> None:
        with pytest.raises(DeserializationError, match="too short"):
            deserialize_state_safe(b"\x01abc")

    def test_deserialize_state_auto_detects_v1(self) -> None:
        """Plain deserialize_state transparently handles version-1 payloads."""
        state = ExperimentState(run_id="auto-v1")
        payload, _ = serialize_state_safe(state)
        restored = deserialize_state(payload)
        assert restored.run_id == "auto-v1"

    def test_deserialize_state_handles_legacy_v0(self) -> None:
        """Plain JSON (version 0) still works with deserialize_state."""
        state = ExperimentState(run_id="legacy-v0")
        raw_json = serialize_state(state)
        restored = deserialize_state(raw_json)
        assert restored.run_id == "legacy-v0"


def _output_aware_transport_outcome(store: FileSystemCAS) -> OutputAwareNodeOutcome:
    """Real CAS-backed output ledger for wire transport; no admission is asserted."""
    from polisyos.core.artifacts import PutOptions

    ref = store.put_json(
        {"measured_transport_value": 7},
        PutOptions(kind="test.output_transport", media_type="application/json"),
    )
    return OutputAwareNodeOutcome(
        status="ok",
        state=ExperimentState(run_id="output-aware-wire", artifacts_index={"transport_ref": ref}),
        artifacts=[ref],
        output_dispositions=(
            NodeOutputDisposition(
                output_key="transport_ref", disposition="produced", artifact_ref=ref
            ),
        ),
        supporting_artifacts={"actual_source": ref},
    )


def test_output_aware_public_deserializer_preserves_complete_outcome(
    tmp_path: Path,
) -> None:
    outcome = _output_aware_transport_outcome(FileSystemCAS(tmp_path))
    restored = deserialize_outcome(serialize_outcome(outcome))
    assert type(restored) is OutputAwareNodeOutcome
    assert restored.model_dump(mode="json") == outcome.model_dump(mode="json")


@pytest.mark.parametrize("mutation", ["absent", "null", "malformed"])
@pytest.mark.parametrize(
    "presence_field",
    sorted(
        OutputAwareNodeOutcome.model_fields.keys()
        - NodeOutcome.model_fields.keys()
        - {"output_dispositions"}
    ),
)
def test_output_aware_reader_refuses_incomplete_subtype(
    tmp_path: Path, mutation: str, presence_field: str
) -> None:
    outcome = _output_aware_transport_outcome(FileSystemCAS(tmp_path))
    payload = outcome.model_dump(mode="python")
    # Leave each actual subtype indicator separately, then damage the required
    # ledger. A retained discriminator or supporting record forbids downgrade.
    extensions = OutputAwareNodeOutcome.model_fields.keys() - NodeOutcome.model_fields.keys()
    for key in extensions - {presence_field, "output_dispositions"}:
        del payload[key]
    if mutation == "absent":
        del payload["output_dispositions"]
    elif mutation == "null":
        payload["output_dispositions"] = None
    else:
        payload["output_dispositions"] = [{"output_key": "transport_ref"}]
    with pytest.raises(DeserializationError):
        deserialize_outcome(serialization_module._dumps(payload))


def test_output_aware_decoder_preserves_ordinary_wire_and_live_identity(
    tmp_path: Path,
) -> None:
    from polisyos.scientist.orchestration.engine import decode_node_outcome

    ordinary = NodeOutcome(status="ok", state=ExperimentState(run_id="ordinary-wire"))
    expected = {
        "status": "ok",
        "state": ordinary.state.model_dump(),
        "artifacts": [],
        "events": [],
        "error": None,
        "skip_blocker": None,
    }
    assert serialize_outcome(ordinary) == serialization_module._dumps(
        {"wire_schema": "polisyos.scientist.outcome_wire.v2", "value": expected}
    )
    assert type(deserialize_outcome(serialization_module._dumps(expected))) is NodeOutcome
    assert type(deserialize_outcome(serialize_outcome(ordinary))) is NodeOutcome
    assert decode_node_outcome(ordinary) is ordinary
    aware = _output_aware_transport_outcome(FileSystemCAS(tmp_path))
    assert decode_node_outcome(aware) is aware


def _tracked_event_for_wire_adversary() -> tuple[ExperimentState, NodeEvent]:
    """Prepare one exact registered tracker with a journaled branch owner."""
    branch = branch_state(ExperimentState(run_id="wire-adversary"), write_paths=("params",))
    journal = mutation_journal_for_state(branch.state)
    assert journal is not None
    event = NodeEvent(level="info", code="test.adversary", message="adversary", attrs={})
    tracked = _wrap_mutable_value(event, ("params", "event"), journal)
    assert isinstance(tracked, NodeEvent)
    assert type(tracked) is not NodeEvent
    return branch.state, tracked


def test_registered_tracker_cycle_is_refused_by_wire_recursion_guard() -> None:
    state, tracked = _tracked_event_for_wire_adversary()
    dict.__setitem__(tracked.attrs, "self", tracked)
    outcome = NodeOutcome.model_construct(
        status="fail",
        state=state,
        artifacts=[],
        events=[tracked],
        error=None,
        skip_blocker=None,
    )

    with pytest.raises(TypeError, match="Cycle detected while serializing"):
        serialize_outcome(outcome)


def test_registered_tracker_depth_is_refused_at_wire_limit() -> None:
    state, tracked = _tracked_event_for_wire_adversary()
    nested: Any = "leaf"
    for _ in range(140):
        nested = [nested]
    dict.__setitem__(tracked.attrs, "deep", nested)
    outcome = NodeOutcome.model_construct(
        status="fail",
        state=state,
        artifacts=[],
        events=[tracked],
        error=None,
        skip_blocker=None,
    )

    with pytest.raises(TypeError, match="Wire serialization depth exceeds"):
        serialize_outcome(outcome)
