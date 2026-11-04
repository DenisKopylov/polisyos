"""Acquisition event catalog checks and real route-phase owner readback.

The three new-family envelopes below are component inputs, not native @2/@3
terminals or proof that the unpriced-policy producer is orchestrated. Their
payloads and diagnostic rows use the real CAS and SQLite log. The requested
route phase is emitted and verified by its actual owner; its durable-row
corruptions are deliberate fixture storage faults, with no reader replacement.
The policy emitter case uses selected component-parent fixtures and the actual
Fabric authorization/quota owners; it does not establish a real N7 cycle,
protected action, live fetch, or policy orchestration.

Catalog validation requires a phase/producer, rejects foreign sources or
sampling, and requires canonical CAS payload refs for the always-CAS families.
Exact phase/version, resolved CAS content and authority binding remain owner
checks; a syntactically valid CAS ref alone does not establish those facts.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ArtifactID, FileSystemCAS
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.authority_reconciliation import (
    AuthorityReconciliationError,
)
from polisyos.runtime.quality.diagnostic_events import (
    DiagnosticEvent,
    DiagnosticEventContractError,
    load_diagnostic_event_type_registry,
    validate_diagnostic_event,
)
from polisyos.runtime.quality.event_log import (
    DiagnosticEventPayloadPolicy,
    RuntimeDiagnosticEventLog,
)

_ROUTE_SOURCE = "polisyos.runtime.quality.acquisition_route_loop"
_ROUTE_PRODUCER = "polisyos.runtime.acquisition_route_loop"
_ROUTE_VERSION = "2026.08.28+ds15-c02"
_POLICY_PRODUCER = "polisyos.runtime.acquisition_candidate_unpriced_policy"


@dataclass(frozen=True)
class _EventSpec:
    suffix: str
    source: str
    producer: str
    version: str
    phase: str
    category: str

    @property
    def event_type(self) -> str:
        return "polisyos.runtime.acquisition." + self.suffix


_SPECS = (
    _EventSpec(
        "candidate_experiment_terminal.v1",
        _ROUTE_SOURCE,
        _ROUTE_PRODUCER,
        _ROUTE_VERSION,
        "acquisition_route_loop",
        "acquisition_candidate_experiment_terminal",
    ),
    _EventSpec(
        "candidate_experiment_phase.v1",
        _ROUTE_SOURCE,
        _ROUTE_PRODUCER,
        _ROUTE_VERSION,
        "acquisition_route_loop",
        "acquisition_candidate_experiment_phase",
    ),
    _EventSpec(
        "route_loop.v2",
        _ROUTE_SOURCE,
        _ROUTE_PRODUCER,
        _ROUTE_VERSION,
        "acquisition_route_loop",
        "acquisition_route_loop",
    ),
    _EventSpec(
        "route_loop.v3",
        _ROUTE_SOURCE,
        _ROUTE_PRODUCER,
        _ROUTE_VERSION,
        "acquisition_route_loop",
        "acquisition_route_loop",
    ),
    _EventSpec(
        "candidate_unpriced_policy.v1",
        _POLICY_PRODUCER,
        _POLICY_PRODUCER,
        "1.0",
        "candidate_unpriced_policy",
        "acquisition_candidate_unpriced_policy",
    ),
)


@pytest.fixture(params=_SPECS, ids=[spec.suffix for spec in _SPECS])
def event_spec(request: pytest.FixtureRequest) -> _EventSpec:
    return request.param


@pytest.fixture
def event_owner(tmp_path: Path) -> Iterator[SimpleNamespace]:
    sqlite_path = tmp_path / "control.sqlite3"
    with closing(ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)) as store:
        cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
        yield SimpleNamespace(
            store=store,
            cas=cas,
            events=RuntimeDiagnosticEventLog(store=store, artifact_store=cas),
            sqlite_path=sqlite_path,
        )


def _envelope(spec: _EventSpec) -> DiagnosticEvent:
    """Build a catalog input without claiming an actual terminal or policy issue."""
    return DiagnosticEvent(
        event_id="evt-catalog-" + spec.suffix,
        event_source=spec.source,
        event_type=spec.event_type,
        event_time=datetime(2026, 11, 4, 12, tzinfo=UTC),
        event_subject="catalog-envelope-component-input/" + spec.suffix,
        schema_name="polisyos.runtime.quality.diagnostic_event",
        schema_version="1.0",
        trace_id="trace-catalog-component",
        span_id="span-catalog-component",
        parent_span_id=None,
        run_id="run-a",
        job_id="job-acquisition",
        tenant_id="tenant-a",
        cell_id="cell-a",
        producer_component=spec.producer,
        producer_version=spec.version,
        execution_profile="governed",
        phase=spec.phase,
        state_before=None,
        state_after="catalog_component_input",
        payload_ref=None,
        artifact_refs=(),
        input_refs=(),
        blocking_status=None,
        redaction_policy_ref=None,
        duplicate_of=None,
        dedupe_key="catalog-component:" + spec.suffix,
        sampling_decision="always_record",
        sampling_rate=1.0,
    )


def test_new_family_envelope_persists_with_its_canonical_catalog_contract(
    event_owner: SimpleNamespace, event_spec: _EventSpec
) -> None:
    """A real diagnostic row and payload do not create a terminal authority record."""
    registry = load_diagnostic_event_type_registry()
    contract = registry.event_types[event_spec.event_type]
    assert contract.category == event_spec.category
    assert contract.allowed_event_sources == (event_spec.source,)
    assert contract.authority_role == "runtime_authority"
    assert contract.phase_required is contract.producer_required is True
    assert contract.serious_no_sampling is True
    assert contract.payload_ref_policy == "cas_required"

    payload = {"catalog_component_input": event_spec.suffix, "terminal_authority": False}
    saved = event_owner.events.append(
        _envelope(event_spec),
        payload=payload,
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
    )
    assert validate_diagnostic_event(saved.event, registry=registry) == saved.event
    assert event_owner.events.list_events(event_id=saved.event.event_id, limit=2) == [saved]
    assert event_owner.events.load_payload(saved) == payload
    assert saved.payload_inline is None
    assert saved.payload_ref == saved.event.payload_ref
    manifest = event_owner.cas.get_manifest(ArtifactID.model_validate(saved.payload_ref))
    assert manifest.authority is None

    missing = registry.model_copy(
        update={
            "event_types": {
                name: row
                for name, row in registry.event_types.items()
                if name != event_spec.event_type
            }
        }
    )
    with pytest.raises(DiagnosticEventContractError) as error:
        validate_diagnostic_event(saved.event, registry=missing)
    assert error.value.code == "unknown_diagnostic_event_type"


@pytest.mark.parametrize(
    ("corruption", "code"),
    [
        (
            {"event_source": "polisyos.runtime.foreign_candidate_owner"},
            "diagnostic_event_source_not_allowed",
        ),
        ({"phase": ""}, "diagnostic_event_phase_missing"),
        ({"producer_version": ""}, "diagnostic_event_producer_missing"),
        (
            {"sampling_decision": "sampled_away", "sampling_rate": 0.01},
            "serious_diagnostic_event_sampled_away",
        ),
    ],
    ids=["foreign-source", "missing-phase", "missing-producer-version", "sampled-away"],
)
def test_new_family_catalog_refuses_invalid_envelope(
    event_owner: SimpleNamespace,
    event_spec: _EventSpec,
    corruption: dict[str, object],
    code: str,
) -> None:
    saved = event_owner.events.append(
        _envelope(event_spec),
        payload={"catalog_component_input": event_spec.suffix},
        payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=True),
    )
    with pytest.raises(DiagnosticEventContractError) as error:
        validate_diagnostic_event(saved.event.model_copy(update=corruption))
    assert error.value.code == code


@pytest.fixture(
    params=["route_phase.v1", "route_loop.v2", "route_loop.v3", "evaluation.v1", "policy.v1"]
)
def writer_event(
    event_owner: SimpleNamespace, tmp_path: Path, request: pytest.FixtureRequest
) -> Iterator[SimpleNamespace]:
    """Use real emitters; terminal versions are only shared-writer envelope projections."""
    if request.param == "evaluation.v1":
        from polisyos.runtime.quality.acquisition_evaluation import (
            _candidate_evaluation_event_id,
            persist_acquisition_evaluation_artifact,
        )
        from tests.unit.runtime.quality.test_candidate_evaluation_artifact import (
            _decision_fixture,
        )

        root = tmp_path / "evaluation-component"
        root.mkdir()
        component = _decision_fixture(root)
        try:
            selected = persist_acquisition_evaluation_artifact(
                store=component.cas, event_log=component.events, record=component.decision
            )
            (saved,) = component.events.list_events(
                event_id=_candidate_evaluation_event_id(component.decision), limit=2
            )
            assert saved.event.payload_ref == str(selected.artifact_id)
            yield SimpleNamespace(event=saved.event, events=component.events, cas=component.cas)
        finally:
            component.events._store.close()
        return
    if request.param == "policy.v1":
        from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
            persist_candidate_unpriced_policy,
            read_candidate_unpriced_policy,
        )
        from tests.unit.runtime.quality.test_candidate_unpriced_policy import _component_policy
        from tests.unit.scientist.orchestration.engine.test_invocation_capacity_observation import (
            _owner,
        )

        _ledger, _middleware, observer = _owner(
            tmp_path / "writer-quota.json", total=2, protected=1
        )
        profile = observer.invocation_quota_profile
        assert profile is not None
        _scope, policy, _authorization = _component_policy(event_owner.cas, profile)
        selected = persist_candidate_unpriced_policy(
            store=event_owner.cas, event_log=event_owner.events, policy=policy
        )
        assert (
            read_candidate_unpriced_policy(
                store=event_owner.cas, event_log=event_owner.events, ref=selected
            )
            == policy
        )
        event_id = "evt_candidate_unpriced_policy_" + policy.content_hash.removeprefix("sha256:")
        (saved,) = event_owner.events.list_events(event_id=event_id, limit=2)
        event = saved.event
    else:
        _persist_requested_phase(event_owner)
        event = event_owner.saved.event
        if request.param != "route_phase.v1":
            # The native @2/@3 terminal is not run or admitted here. Both
            # branches use this actual phase writer's source, phase and CAS shape.
            event = event.model_copy(
                update={"event_type": "polisyos.runtime.acquisition." + request.param}
            )
    yield SimpleNamespace(event=event, events=event_owner.events, cas=event_owner.cas)


@pytest.mark.parametrize("storage", ["absent", "inline-only"])
def test_writer_derived_always_cas_events_refuse_absent_or_inline_only_payload(
    writer_event: SimpleNamespace, storage: str
) -> None:
    """Keep real writer metadata while removing only its CAS payload binding."""
    event = writer_event.event
    assert validate_diagnostic_event(event) == event
    invalid = event.model_copy(
        update={"payload_ref": None if storage == "absent" else "inline://component-payload"}
    )
    with pytest.raises(DiagnosticEventContractError) as error:
        validate_diagnostic_event(invalid)
    assert error.value.code == (
        "authority_cas_missing" if storage == "absent" else "authority_ref_not_cas"
    )

    original = writer_event.cas.get_bytes(ArtifactID.model_validate(event.payload_ref))
    for operation in ("prepare", "append"):
        attempted_id = event.event_id + "-" + storage + "-" + operation
        candidate = event.model_copy(
            update={"event_id": attempted_id, "execution_profile": "dev", "payload_ref": None}
        )
        # A tiny dev-profile payload with an explicit nonauthority storage
        # policy takes the actual inline path. The registered event type must
        # still require CAS, independently of these caller-controlled options.
        payload = None if storage == "absent" else {"component_input": "inline only"}
        with pytest.raises(DiagnosticEventContractError) as error:
            getattr(writer_event.events, operation)(
                candidate,
                payload=payload,
                payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=False),
            )
        assert error.value.code == "authority_cas_missing"
        assert writer_event.events.list_events(event_id=attempted_id, limit=2) == []
    assert writer_event.cas.get_bytes(ArtifactID.model_validate(event.payload_ref)) == original


@pytest.mark.parametrize(
    ("event_type", "policy"),
    [
        ("polisyos.runtime.diagnostic.blocker.v1", "optional"),
        (
            "polisyos.runtime.diagnostic.producer_execution.v1",
            "cas_required_for_authority_payload",
        ),
    ],
    ids=["optional-blocker", "conditional-blocked-producer"],
)
@pytest.mark.parametrize("storage", ["absent", "inline"])
def test_optional_and_conditional_blocked_events_preserve_valid_storage(
    event_owner: SimpleNamespace, event_type: str, policy: str, storage: str
) -> None:
    """Retain valid blocker/conditional paths without relabeling them authority."""
    _persist_requested_phase(event_owner)
    event = event_owner.saved.event.model_copy(
        update={
            "event_id": "evt-storage-component-" + event_type + "-" + storage,
            "event_type": event_type,
            "execution_profile": "dev" if storage == "inline" else "governed",
            "payload_ref": None,
            "artifact_refs": (),
            "input_refs": (),
            "blocking_status": "blocking",
            "state_after": "blocked",
        }
    )
    registry = load_diagnostic_event_type_registry()
    assert registry.event_types[event_type].payload_ref_policy == policy
    assert validate_diagnostic_event(event, registry=registry) == event
    payload = {"reason": "component blocked"} if storage == "inline" else None
    prepared = event_owner.events.prepare(
        event, payload=payload, payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=False)
    )
    assert prepared.publication_values() == (event, payload)
    saved = event_owner.events.append(
        event, payload=payload, payload_policy=DiagnosticEventPayloadPolicy(authority_bearing=False)
    )
    assert saved.payload_ref is saved.event.payload_ref is None
    assert saved.payload_inline == payload
    assert event_owner.events.load_payload(saved) == payload


def test_actual_unpriced_policy_emitter_reopens_its_registered_event(
    event_owner: SimpleNamespace, tmp_path: Path
) -> None:
    """Persist through the policy owner with explicitly limited component sources."""
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        POLICY_EVENT,
        POLICY_PRODUCER,
        persist_candidate_unpriced_policy,
        read_candidate_unpriced_policy,
    )
    from tests.unit.runtime.quality.test_candidate_unpriced_policy import _component_policy
    from tests.unit.scientist.orchestration.engine.test_invocation_capacity_observation import (
        _owner,
    )

    _ledger, _middleware, observer = _owner(
        tmp_path / "catalog-policy-quota.json", total=2, protected=1
    )
    profile = observer.invocation_quota_profile
    assert profile is not None
    scope, policy, _authorization = _component_policy(event_owner.cas, profile)
    selected = persist_candidate_unpriced_policy(
        store=event_owner.cas, event_log=event_owner.events, policy=policy
    )
    assert selected.manifest_profile_sha256 is not None
    assert (
        read_candidate_unpriced_policy(
            store=event_owner.cas, event_log=event_owner.events, ref=selected
        )
        == policy
    )
    event_id = "evt_candidate_unpriced_policy_" + policy.content_hash.removeprefix("sha256:")
    (saved,) = event_owner.events.list_events(event_id=event_id, limit=2)
    event = saved.event
    assert (
        event.event_type
        == POLICY_EVENT
        == "polisyos.runtime.acquisition.candidate_unpriced_policy.v1"
    )
    assert event.event_source == event.producer_component == POLICY_PRODUCER == _POLICY_PRODUCER
    assert event.producer_version == "1.0"
    assert event.phase == "candidate_unpriced_policy"
    assert event.execution_profile == "governed"
    assert event.sampling_decision == "always_record"
    assert event.payload_ref == str(selected.artifact_id)
    assert event.artifact_refs == (str(selected.artifact_id),)
    assert (event.tenant_id, event.cell_id, event.run_id, event.job_id) == (
        scope.tenant_id,
        scope.cell_id,
        scope.run_id,
        scope.source_job_id,
    )
    assert validate_diagnostic_event(event) == event
    assert policy.monetary_cost == "not_established"
    assert policy.hard_usd_reservation is policy.observed_admission is False
    assert policy.publication_authority is False


def _persist_requested_phase(owner: SimpleNamespace) -> None:
    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
    )
    from tests.unit.runtime.http.test_acquisition_route_authority_sink import _receipt

    owner.sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=owner.cas, event_log=owner.events, control_store=owner.store
    )
    owner.receipt = _receipt(
        receipt_phase="requested",
        coarse_phase="requested",
        recovery_state="none",
        predecessor_receipt_ref=None,
    )
    owner.head = owner.sink.persist_phase(owner.receipt)
    owner.verified = owner.sink.verify_action_head(owner.head)
    (owner.saved,) = owner.events.list_events(event_id=owner.head.durable_event_id, limit=2)
    assert owner.verified.latest_receipt == owner.receipt


def test_actual_route_phase_emitter_reopens_with_the_declared_terminal_source_contract(
    event_owner: SimpleNamespace,
) -> None:
    """Exercise the real shared writer without publishing an @2/@3 terminal."""
    _persist_requested_phase(event_owner)
    event = event_owner.saved.event
    assert event.event_type == "polisyos.runtime.acquisition.route_phase.v1"
    assert event.event_source == _ROUTE_SOURCE
    assert event.producer_component == _ROUTE_PRODUCER
    assert event.producer_version == _ROUTE_VERSION
    assert event.phase == "acquisition_route_loop"
    assert event.execution_profile == "governed"
    assert event.payload_ref == event_owner.head.receipt_ref
    registry = load_diagnostic_event_type_registry()
    for version in (2, 3):
        contract = registry.event_types[f"polisyos.runtime.acquisition.route_loop.v{version}"]
        assert contract.allowed_event_sources == (event.event_source,)
    assert event_owner.sink.get_head(event_owner.receipt) == event_owner.head


@pytest.mark.parametrize(
    "corruption",
    [
        {"phase": "foreign_nonempty_phase"},
        {"producer_version": "foreign-nonempty-version"},
        {"payload_ref": None},
    ],
    ids=["wrong-exact-phase", "wrong-exact-version", "removed-payload"],
)
def test_real_route_owner_refuses_durable_row_corruption(
    event_owner: SimpleNamespace, corruption: dict[str, object]
) -> None:
    """Corrupt the fixture SQLite row while retaining the genuine CAS event bytes."""
    _persist_requested_phase(event_owner)
    saved = event_owner.saved
    original_payload = event_owner.cas.get_bytes(event_owner.head.receipt_ref)
    corrupted = saved.event.model_copy(update=corruption)
    # The catalog rejects missing payloads before publication. A direct storage
    # fault must still fail the real reader's immutable event/content binding.
    if corrupted.payload_ref is None:
        with pytest.raises(DiagnosticEventContractError) as error:
            validate_diagnostic_event(corrupted)
        assert error.value.code == "authority_cas_missing"
    else:
        assert validate_diagnostic_event(corrupted) == corrupted
    with sqlite3.connect(event_owner.sqlite_path) as connection:
        changed = connection.execute(
            "UPDATE control_diagnostic_events "
            "SET event_json = ?, payload_ref = ? WHERE event_id = ?",
            (
                json.dumps(corrupted.model_dump(mode="json"), sort_keys=True),
                corrupted.payload_ref,
                saved.event.event_id,
            ),
        )
        assert changed.rowcount == 1
    with pytest.raises(AuthorityReconciliationError) as error:
        event_owner.sink.verify_action_head(event_owner.head)
    assert error.value.code == "authority_payload_mismatch"
    assert event_owner.sink.get_head(event_owner.receipt) == event_owner.head
    assert event_owner.cas.get_bytes(event_owner.head.receipt_ref) == original_payload
    assert len(event_owner.events.list_events(event_id=saved.event.event_id, limit=2)) == 1
