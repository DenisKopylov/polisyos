"""Real-CAS/storage tests, not proof of the separately owned SQL/factory bridge.

Positive storage fixtures deliberately use the private state intake. They test
crash atomicity, epoch/read semantics and actual content/owner lineage, without
pretending a hand-written producer/factory is Runtime/Fabric authority. Public
unconfigured/fake-producer paths must fail closed. C106 supplies real bridge tests.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import (
    ArtifactWriteOptions,
    CanonInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.decision_validity import RegisteredMaterialization
from polisyos.core.contracts.fabric import (
    DataSnapshotOwnerBound,
    DataViewRequestRef,
    FabricBridgeDataSnapshotLineage,
    WarningsRef,
)
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from polisyos.scientist.validation.source_admission_port import (
    SourceAdmissionAuthority,
    VerifiedRegisteredMaterialization,
)

# Initial deadlock/resource guard, not a product latency requirement. The first
# new process/storage profile runs alone; a timeout is harness ERROR/UNRUN and
# must be measured/re-admitted before a deciding wave, not reported product FAIL.
_WAIT_SECONDS = 120


_AUTHORITY = {
    "issuer_key": "storage-unit-only-not-runtime-authority",
    "tenant_id": "tenant-a",
    "cell_id": "cell-a",
    "provider_id": "storage-unit-provider",
}


def _put(store, payload, kind, *, version="1.0", inputs=()):
    spec = CanonSpec(forbid_floats=False)
    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=kind, version=version),
            canon=CanonInfo.from_spec(spec),
            inputs=list(inputs),
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )


def _registered(owner, store, suffix="a"):
    view = _put(store, {"unit_view": suffix}, "test.source_view")
    use = _put(store, {"unit_use": "bounded-unit"}, "test.source_use")
    admission = owner._source_admission
    return admission._state.register(
        authority=_AUTHORITY,
        event_id="genesis-" + suffix,
        registration_key="source-" + suffix,
        view_ref=view.model_dump(mode="json"),
        use_ref=use.model_dump(mode="json"),
        verified_refs=admission._verify_refs((view, use)),
    )


def _materialization(store, registration, suffix="a", *, warnings=False):
    request = _put(store, {"unit_request": suffix}, "ir.data_view_request")
    payload = store.put_bytes(
        b"unit binary payload " + suffix.encode(),
        ArtifactWriteOptions(kind="fabric.tabular_payload", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    schema = _put(store, {"columns": ["value"]}, "fabric.data_schema")
    quality = _put(store, {"unit_quality": "not scientific adequacy"}, "fabric.quality_report")
    refs = [
        (request, "data_view_request_ref"),
        (payload, "data_ref"),
        (schema, "data_schema_ref"),
        (quality, "quality_report_ref"),
    ]
    warning_ref = _put(store, {"warnings": []}, "fabric.warnings") if warnings else None
    if warning_ref is not None:
        refs.append((warning_ref, "warnings_ref"))
    snapshot = DataSnapshotOwnerBound(
        data_ref=payload,
        data_schema_ref=schema,
        quality_report_ref=quality,
        warnings_ref=WarningsRef.model_validate(warning_ref.model_dump(mode="python"))
        if warning_ref is not None
        else None,
        source_lineage=FabricBridgeDataSnapshotLineage(
            data_view_request_ref=DataViewRequestRef.model_validate(
                request.model_dump(mode="python")
            )
        ),
    )
    spec = CanonSpec(forbid_floats=False)
    snapshot_ref = store.put_json(
        snapshot,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.3.0"),
            canon=CanonInfo.from_spec(spec),
            inputs=[input_ref_from_artifact_ref(ref, role=role) for ref, role in refs],
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )
    capture = _put(
        store,
        {
            "boundary": "private storage fixture, not actual producer authority",
            "unit": suffix,
        },
        "test.storage_materialization_capture",
    )
    return RegisteredMaterialization(
        registration=registration,
        occurrence_id="occurrence-" + suffix,
        producer_rule_version="unit-only",
        producer_capture_ref=capture,
        request_ref=request,
        snapshot_ref=snapshot_ref,
        payload_ref=payload,
        schema_ref=schema,
        quality_ref=quality,
        observed_at=datetime.now(UTC),
    )


def _admit(owner, materialization, predecessor=None, suffix="a"):
    admission = owner._source_admission
    refs = admission._materialization_refs(materialization)
    return admission._state.admit(
        materialization=materialization,
        event_id="admit-" + suffix,
        expected_predecessor=predecessor or materialization.registration.event_ref,
        verified_refs=admission._verify_refs(refs),
    )


def _transition(owner, target, predecessor, operation, event_id):
    return owner._source_admission._state.transition(
        authority=_AUTHORITY,
        event_id=event_id,
        expected_predecessor=predecessor,
        operation=operation,
        target=target,
    )


def _case(tmp_path, suffix="a", warnings=False):
    store = FileSystemCAS(
        tmp_path / "cas",
        tenant_id=_AUTHORITY["tenant_id"],
        cell_id=_AUTHORITY["cell_id"],
    )
    owner = DecisionValidityService(store)
    registration = _registered(owner, store, suffix)
    materialization = _materialization(store, registration, suffix, warnings=warnings)
    receipt = _admit(owner, materialization, suffix=suffix)
    assert receipt.carrier is not None
    return store, owner, materialization, receipt


def test_unconfigured_and_lookalike_authority_cannot_register_or_admit(tmp_path):
    store = FileSystemCAS(
        tmp_path / "cas",
        tenant_id=_AUTHORITY["tenant_id"],
        cell_id=_AUTHORITY["cell_id"],
    )
    owner = DecisionValidityService(store)
    assert owner.read_source_current_use(()).status == "unknown"
    ref = _put(store, {"genuine_bytes": True}, "test.anything")
    for fake in (
        None,
        SimpleNamespace(
            authorize=lambda **kw: True,
            issuer_key="fake",
            tenant_id="tenant-a",
            cell_id="cell-a",
            provider_id="fake",
        ),
        object.__new__(SourceAdmissionAuthority),
    ):
        with pytest.raises(ValueError, match="source_admission_authority_not_established"):
            owner.register_materialization_source(
                fake,
                event_id="fake",
                registration_key="fake",
                effective_view_contract_ref=ref,
                use_contract_ref=ref,
            )
    for fake in (
        SimpleNamespace(verify=lambda **kw: True),
        object.__new__(VerifiedRegisteredMaterialization),
    ):
        with pytest.raises(ValueError, match="source_admission_producer_relation_not_established"):
            owner.admit_materialization(
                fake, event_id="fake", expected_predecessor="sha256:" + "0" * 64
            )
    assert not owner._source_admission._state.root_path.exists()


def test_actual_owner_withdraw_a_after_b_keeps_b_and_independent_i_and_history(
    tmp_path,
):
    store, owner, a, receipt_a = _case(tmp_path)
    a_bytes = store.get_bytes(a.snapshot_ref)
    selected = _transition(owner, receipt_a.carrier, receipt_a.event_ref, "supersede", "select-a")
    b = _materialization(store, a.registration, "b")
    receipt_b = _admit(owner, b, selected.event_ref, "b")
    independent_registration = _registered(owner, store, "independent")
    i = _materialization(store, independent_registration, "independent")
    receipt_i = _admit(owner, i, suffix="independent")
    assert (
        owner.read_source_current_use((receipt_a.carrier,), require_selected=True).status
        == "current"
    )
    assert owner.read_source_current_use((receipt_b.carrier,)).status == "current"
    assert (
        owner.read_source_current_use((receipt_b.carrier,), require_selected=True).status
        == "unknown"
    )
    withdrawn = _transition(owner, receipt_a.carrier, receipt_b.event_ref, "withdraw", "withdraw-a")
    fresh = DecisionValidityService(FileSystemCAS(store.root))
    assert fresh.read_source_current_use((receipt_a.carrier,)).status == "withdrawn"
    assert fresh.read_source_current_use((receipt_b.carrier,)).status == "current"
    independent = fresh.read_source_current_use((receipt_i.carrier,))
    mixed = fresh.read_source_current_use((receipt_a.carrier, receipt_i.carrier))
    assert mixed.status == "withdrawn" and "source_admission_withdrawn" in mixed.reason_codes
    assert independent.status == "current" and independent.generation == withdrawn.generation
    assert store.get_bytes(a.snapshot_ref) == a_bytes
    assert (
        fresh._source_admission._state.event_receipt(authority=_AUTHORITY, event_id="admit-a")
        == receipt_a
    )


def test_explicit_readmit_creates_new_epoch_without_old_carrier_aba(tmp_path):
    _, owner, _, first = _case(tmp_path)
    withdrawal = _transition(owner, first.carrier, first.event_ref, "withdraw", "withdraw-a")
    restored = _transition(owner, first.carrier, withdrawal.event_ref, "readmit", "restore-a")
    assert restored.carrier.admission_epoch != first.carrier.admission_epoch
    assert restored.carrier.admission_event_ref != first.carrier.admission_event_ref
    assert owner.read_source_current_use((first.carrier,)).status == "withdrawn"
    assert owner.read_source_current_use((restored.carrier,)).status == "current"
    with pytest.raises(ValueError, match="latest_withdrawn_epoch"):
        _transition(owner, first.carrier, restored.event_ref, "readmit", "restore-old-again")


def test_event_retry_is_original_and_full_target_conflict_is_refused(tmp_path):
    _, owner, _, first = _case(tmp_path)
    receipt = _transition(owner, first.carrier, first.event_ref, "withdraw", "withdraw-a")
    retried = _transition(owner, first.carrier, first.event_ref, "withdraw", "withdraw-a")
    assert retried == receipt
    changed = first.carrier.model_copy(update={"occurrence_id": "different-occurrence"})
    with pytest.raises(ValueError, match="conflicting_event_id"):
        _transition(owner, changed, first.event_ref, "withdraw", "withdraw-a")
    with pytest.raises(ValueError, match="predecessor_gap"):
        _transition(owner, first.carrier, "sha256:" + "0" * 64, "readmit", "gap")


def test_new_event_cannot_reset_genesis_or_duplicate_admit_occurrence(tmp_path):
    store, owner, materialization, first = _case(tmp_path)
    registration = materialization.registration
    with pytest.raises(ValueError, match="genesis_already_committed"):
        owner._source_admission._state.register(
            authority=_AUTHORITY,
            event_id="new-genesis",
            registration_key=registration.registration_key,
            view_ref=registration.effective_view_contract_ref.model_dump(mode="json"),
            use_ref=registration.use_contract_ref.model_dump(mode="json"),
            verified_refs=[],
        )
    with pytest.raises(ValueError, match="occurrence_requires_explicit_readmit"):
        _admit(owner, materialization, first.event_ref, "duplicate-occurrence")
    assert owner.read_source_current_use((first.carrier,)).status == "current"
    assert store.verify(materialization.payload_ref).ok


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "other-tenant"),
        ("cell_id", "other-cell"),
        ("source_incarnation_id", "other-source"),
        ("admission_epoch", "other-epoch"),
        ("occurrence_id", "other-occurrence"),
        ("revision_digest", "sha256:" + "1" * 64),
        ("admission_scope_digest", "sha256:" + "2" * 64),
    ],
)
def test_full_carrier_identity_is_required_not_scope_status_proxy(tmp_path, field, value):
    _, owner, _, first = _case(tmp_path)
    changed = first.carrier.model_copy(update={field: value})
    result = owner.read_source_current_use((changed,))
    assert result.status == "unknown" and result.predicate_provenance == "not_established"


def test_owned_optional_warning_ref_is_derived_and_reverified(tmp_path):
    store, owner, materialization, first = _case(tmp_path, warnings=True)
    fact = owner._source_admission._state.fact_for_carrier(first.carrier)
    optional = [row for row in fact["verified_refs"] if row["ref"]["kind"] == "fabric.warnings"]
    assert len(optional) == 1
    ref = ArtifactRef.model_validate_json(json.dumps(optional[0]["ref"]), strict=True)
    blob, _ = store._paths(ref.artifact_id)
    original = blob.read_bytes()
    scratch = blob.with_name(blob.name + ".source-unit-probe")
    scratch.write_bytes(b"corrupt exact required warning bytes")
    os.replace(scratch, blob)
    try:
        assert owner.read_source_current_use((first.carrier,)).status == "unknown"
    finally:
        scratch.write_bytes(original)
        os.replace(scratch, blob)
    assert store.get_bytes(materialization.payload_ref).startswith(b"unit binary")


def test_pre_root_orphan_has_no_authority_and_retry_commits_once(tmp_path):
    store = FileSystemCAS(
        tmp_path / "cas",
        tenant_id=_AUTHORITY["tenant_id"],
        cell_id=_AUTHORITY["cell_id"],
    )
    owner = DecisionValidityService(store)
    registration = _registered(owner, store)
    materialization = _materialization(store, registration)
    state = owner._source_admission._state

    def fail(point):
        if point == "before_root_publish":
            raise OSError("deliberate before root publication")

    state._fault = fail
    with pytest.raises(OSError, match="before root publication"):
        _admit(owner, materialization)
    events = [
        ref
        for ref, body in state._cache.items()
        if body.get("schema_version") == "source-event.v1"
        and body["command"]["event_id"] == "admit-a"
    ]
    assert len(events) == 1
    orphan = state._receipt(events[0])
    assert (
        DecisionValidityService(FileSystemCAS(store.root))
        .read_source_current_use((orphan.carrier,))
        .status
        == "unknown"
    )
    state._fault = None
    actual = _admit(owner, materialization)
    assert actual.generation == registration.generation + 1
    assert owner.read_source_current_use((actual.carrier,)).status == "current"


def test_failed_root_directory_fsync_requires_real_durability_retry(tmp_path, monkeypatch):
    _, owner, _, first = _case(tmp_path)
    state = owner._source_admission._state
    original = state._fsync_dir
    flags = {"replaced": False, "failed": False, "reconciled": 0}
    state._fault = (
        lambda point: flags.update(replaced=True) if point == "after_root_replace" else None
    )

    def fsync(path):
        if path == state.root_path.parent and flags["replaced"]:
            if not flags["failed"]:
                flags["failed"] = True
                raise OSError("deliberate root directory fsync failure")
            flags["reconciled"] += 1
        return original(path)

    monkeypatch.setattr(state, "_fsync_dir", fsync)
    with pytest.raises(OSError, match="root directory fsync failure"):
        _transition(owner, first.carrier, first.event_ref, "withdraw", "uncertain-withdraw")
    state._fault = None
    retried = _transition(owner, first.carrier, first.event_ref, "withdraw", "uncertain-withdraw")
    assert flags["reconciled"] >= 1
    assert retried.generation == first.generation + 1
    assert owner.read_source_current_use((first.carrier,)).status == "withdrawn"


def test_withdrawal_during_immutable_cas_phase_is_seen_at_decisive_fence(tmp_path, monkeypatch):
    store, owner, _, first = _case(tmp_path)
    blocked = threading.Event()
    proceed = threading.Event()
    result = []
    actual = owner._source_admission._verify_ref

    def pause(ref, **scope):
        blocked.set()
        assert proceed.wait(_WAIT_SECONDS)
        return actual(ref, **scope)

    monkeypatch.setattr(owner._source_admission, "_verify_ref", pause)
    thread = threading.Thread(
        target=lambda: result.append(owner.read_source_current_use((first.carrier,)))
    )
    thread.start()
    assert blocked.wait(_WAIT_SECONDS)
    withdrawal = _transition(
        DecisionValidityService(FileSystemCAS(store.root)),
        first.carrier,
        first.event_ref,
        "withdraw",
        "racing-withdraw",
    )
    proceed.set()
    thread.join(_WAIT_SECONDS)
    assert not thread.is_alive()
    assert result[0].status == "withdrawn" and result[0].generation == withdrawal.generation


def test_read_linearizes_before_later_withdrawal_without_network_lifetime_claim(
    tmp_path, monkeypatch
):
    store, owner, _, first = _case(tmp_path)
    decisive = threading.Event()
    proceed = threading.Event()
    result = []
    count = [0]
    actual = owner._source_admission._state.snapshot_facts

    def pause(*args, **kwargs):
        value = actual(*args, **kwargs)
        count[0] += 1
        if count[0] == 2:
            decisive.set()
            assert proceed.wait(_WAIT_SECONDS)
        return value

    monkeypatch.setattr(owner._source_admission._state, "snapshot_facts", pause)
    thread = threading.Thread(
        target=lambda: result.append(owner.read_source_current_use((first.carrier,)))
    )
    thread.start()
    assert decisive.wait(_WAIT_SECONDS)
    withdrawal = _transition(
        DecisionValidityService(FileSystemCAS(store.root)),
        first.carrier,
        first.event_ref,
        "withdraw",
        "later-withdraw",
    )
    proceed.set()
    thread.join(_WAIT_SECONDS)
    assert not thread.is_alive()
    assert result[0].status == "current" and result[0].generation < withdrawal.generation
    assert (
        DecisionValidityService(FileSystemCAS(store.root))
        .read_source_current_use((first.carrier,))
        .status
        == "withdrawn"
    )


_CHILD = r"""
import hashlib,json,os,sys
from pathlib import Path
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.decision_validity import SourceAdmissionCarrier
from polisyos.scientist.validation.decision_validity import DecisionValidityService
root,mode,carrier_json,predecessor,output=sys.argv[1:]
owner=DecisionValidityService(FileSystemCAS(Path(root)))
carrier=SourceAdmissionCarrier.model_validate_json(carrier_json,strict=True)
def observe():
    rows=[]
    for name,module in sorted(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if path and path.endswith('.py') and '/src/polisyos/' in path:
            p=Path(path).resolve();rows.append({'module':name,'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    Path(output).write_text(json.dumps({'pid':os.getpid(),'mode':mode,'first_party_python':rows},sort_keys=True))
if mode=='read':
    value=owner.read_source_current_use((carrier,));observe()
    print(value.model_dump_json())
else:
    def fault(point):
        if point==mode:
            observe();os._exit(37)
    owner._source_admission._state._fault=fault
    owner._source_admission._state.transition(authority=AUTHORITY,event_id='child-withdraw',expected_predecessor=predecessor,operation='withdraw',target=carrier)
""".replace("AUTHORITY", repr(_AUTHORITY))


@pytest.mark.parametrize(
    "point,expected",
    [("before_root_publish", "current"), ("after_root_replace", "withdrawn")],
)
def test_actual_child_process_kill_has_only_committed_old_or_new_state(tmp_path, point, expected):
    store, owner, _, first = _case(tmp_path)
    output = tmp_path / "child-source.json"
    command = [
        sys.executable,
        "-B",
        "-c",
        _CHILD,
        str(store.root),
        point,
        first.carrier.model_dump_json(),
        first.event_ref,
        str(output),
    ]
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(tmp_path / "empty-child-pycache"),
    }
    child = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=env,
        timeout=_WAIT_SECONDS,
        check=False,
    )
    (tmp_path / "child.stdout").write_text(child.stdout)
    (tmp_path / "child.stderr").write_text(child.stderr)
    assert child.returncode == 37, child.stderr
    witness = json.loads(output.read_text())
    assert witness["pid"] != os.getpid() and witness["first_party_python"]
    fresh = DecisionValidityService(FileSystemCAS(store.root))
    assert fresh.read_source_current_use((first.carrier,)).status == expected
    if point == "after_root_replace":
        receipt = fresh._source_admission._state.event_receipt(
            authority=_AUTHORITY, event_id="child-withdraw"
        )
        assert receipt.generation == first.generation + 1


def test_persistent_index_does_not_read_unrelated_fact_values_or_grow_root(tmp_path, monkeypatch):
    store, owner, _, first = _case(tmp_path)
    state = owner._source_admission._state
    first_size = state.root_path.stat().st_size
    for index in range(8):
        registration = _registered(owner, store, "unrelated-" + str(index))
        materialization = _materialization(store, registration, "unrelated-" + str(index))
        _admit(owner, materialization, suffix="unrelated-" + str(index))
    actual = Path.read_bytes
    observed = []

    def observe(path):
        raw = actual(path)
        if path.parent == state.objects:
            payload = json.loads(raw)
            observed.append(str(path))
            if payload.get("type") == "value":
                key = payload["key"]
                if key.startswith("revision:"):
                    assert (
                        payload["value"]["materialization"]["registration"]["registration_key"]
                        == "source-a"
                    )
                elif key.startswith("registration:"):
                    assert payload["value"]["registration_key"] == "source-a"
        return raw

    monkeypatch.setattr(Path, "read_bytes", observe)
    assert owner.read_source_current_use((first.carrier,)).status == "current"
    assert observed
    # The actual root's byte count stays bounded as unrelated scopes are added.
    # The read observer above checks actual filesystem bytes, not owner counters.
    assert abs(state.root_path.stat().st_size - first_size) <= 4


def test_selected_profile_is_required_for_real_binary_or_json_refs(tmp_path):
    store, owner, materialization, _ = _case(tmp_path)
    for ref in (materialization.payload_ref, materialization.request_ref):
        assert owner._source_admission._verify_ref(ref)["ref"] == ref.model_dump(mode="json")
        missing = ref.model_copy(update={"manifest_profile_sha256": None})
        with pytest.raises(ValueError, match="selected_profile_required"):
            owner._source_admission._verify_ref(missing)
    assert store.verify(materialization.payload_ref).ok


def test_real_snapshot_missing_required_manifest_edge_is_refused_before_admission(
    tmp_path,
):
    store, owner, materialization, first = _case(tmp_path)
    manifest = store.get_manifest(materialization.snapshot_ref)
    raw = store.get_bytes(materialization.snapshot_ref)
    selected = store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=[ref for ref in manifest.inputs if ref.role != "quality_report_ref"],
        ),
        return_selected_profile=True,
    )
    changed = materialization.model_copy(update={"snapshot_ref": selected})
    with pytest.raises(ValueError, match="snapshot_input_denominator_mismatch"):
        owner._source_admission._materialization_refs(changed)
    assert owner.read_source_current_use((first.carrier,)).status == "current"


def test_projection_binds_ordered_actual_basis_and_selection_query(tmp_path):
    store, owner, _, first = _case(tmp_path)
    registration = _registered(owner, store, "independent")
    materialization = _materialization(store, registration, "independent")
    independent = _admit(owner, materialization, suffix="independent")
    left = owner.read_source_current_use((first.carrier, independent.carrier))
    right = owner.read_source_current_use((independent.carrier, first.carrier))
    repeated = owner.read_source_current_use((first.carrier, first.carrier))
    single = owner.read_source_current_use((first.carrier,))
    selected = owner.read_source_current_use((first.carrier,), require_selected=True)
    assert left.status == right.status == repeated.status == single.status == "current"
    assert (
        len(
            {
                left.basis_digest,
                right.basis_digest,
                repeated.basis_digest,
                single.basis_digest,
            }
        )
        == 4
    )
    assert selected.status == "unknown" and selected.selection_checked is True
    assert selected.basis_digest != single.basis_digest and single.selection_checked is False


def test_fresh_unscoped_owner_reuses_exact_core_tenant_view_ownership(tmp_path):
    store, _, _, _ = _case(tmp_path)
    foreign = FileSystemCAS.for_tenant(store, "tenant-b", "cell-b")
    ref = _put(foreign, {"foreign_only": True}, "test.foreign_source_input")
    fresh = DecisionValidityService(FileSystemCAS(store.root))
    with pytest.raises(PermissionError):
        fresh._source_admission._verify_ref(ref, tenant_id="tenant-a", cell_id="cell-a")
