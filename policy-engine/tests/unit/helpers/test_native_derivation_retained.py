"""Retained institutional signatures remain bound to their exact CAS view."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from tests._helpers import native_derivation_retained as retained
from tests._helpers.native_derivation_retained import _verify_retained_selected_signature


def test_legacy_signature_recovers_only_the_original_selected_manifest(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    key = artifacts.KeyPair.generate()
    signer = artifacts.Ed25519Signer.from_pem(key.private_pem())
    verifier = artifacts.Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(key.public_key, key_id=key.key_id, identity="fixture-owner")
    original = store.put_bytes(
        b"one immutable signed body",
        artifacts.PutOptions(kind="test.native.original", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    store.sign_artifact(original.artifact_id, signer, signer_identity="fixture-owner")
    other_view = store.put_bytes(
        store.get_bytes(original),
        artifacts.PutOptions(kind="test.native.other", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    assert original.artifact_id == other_view.artifact_id
    assert original.manifest_profile_sha256 != other_view.manifest_profile_sha256
    assert store.get_signature(original) is None
    assert store.get_signature(other_view) is None
    assert store.get_manifest_bytes(original) == store.get_manifest_bytes(original.artifact_id)
    before = {str(path): path.read_bytes() for path in store.base.rglob("*") if path.is_file()}

    _verify_retained_selected_signature(store, original, verifier)
    with pytest.raises(ValueError, match="retained_native_continuation_mandate_signature_invalid"):
        _verify_retained_selected_signature(store, other_view, verifier)

    assert {
        str(path): path.read_bytes() for path in store.base.rglob("*") if path.is_file()
    } == before


def _selected_evidence_ref(store, ref: artifacts.ArtifactRef) -> artifacts.ArtifactRef:
    kind = "core.chronology.signed_artifact_evidence_record"
    assert ref.kind == kind
    matches = tuple(
        selected
        for selected in retained._selected_profiles(store, kind)
        if selected.artifact_id == ref.artifact_id
        and selected.media_type == ref.media_type
        and (
            ref.manifest_profile_sha256 is None
            or selected.manifest_profile_sha256 == ref.manifest_profile_sha256
        )
    )
    assert len(matches) == 1
    return matches[0]


def _epoch_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from tests._helpers import semantic_epoch_native

    monkeypatch.delenv("POLISYOS_TEST_RETAIN_NATIVE_EPOCH_SIGNER", raising=False)
    scenario = semantic_epoch_native._real_epoch_scenario(tmp_path / "scenario")
    native = semantic_epoch_native.sign_native_epoch_scenario(scenario, tmp_path / "policy")
    fixture = SimpleNamespace(
        store=scenario.store,
        epoch_history_root=scenario.history._root,
        deferral=SimpleNamespace(
            negative_receipt=SimpleNamespace(
                prepared_epoch_ref=scenario.prepared.prepared_epoch_ref
            )
        ),
        attempt=SimpleNamespace(
            selection=SimpleNamespace(
                epoch_scope_identity=scenario.query.scope_identity,
                authority_purpose=scenario.query.authority_purpose,
            )
        ),
        tenant_id="tenant-a",
        cell_id="cell-a",
        control_run_id="run-retained-native",
    )
    selection = retained.RetainedNativeEpochPolicySelection(
        epoch_admission_evidence_ref=_selected_evidence_ref(
            scenario.store, native.signed.evidence.evidence_record_ref
        ),
        epoch_public_key_path=native.custodian.public_key_path,
    )
    return fixture, selection, scenario, native


def _stored_bytes(store) -> dict[str, bytes]:
    return {str(path): path.read_bytes() for path in store.base.rglob("*") if path.is_file()}


def test_retained_epoch_policy_cold_read_requires_no_private_key_or_signing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests._helpers import semantic_epoch_native

    fixture, selection, _scenario, native = _epoch_fixture(tmp_path, monkeypatch)
    assert not tuple((tmp_path / "policy").rglob("*.pem"))
    before = _stored_bytes(fixture.store)

    def signing_forbidden(*args, **kwargs):
        raise AssertionError("reading a retained epoch policy must not sign")

    monkeypatch.setattr(
        semantic_epoch_native.NativeEpochFixtureCustodian, "create", signing_forbidden
    )
    monkeypatch.setattr(
        semantic_epoch_native.NativeEpochFixtureCustodian, "persist_or_reuse", signing_forbidden
    )
    monkeypatch.setattr(artifacts.Ed25519Signer, "sign", signing_forbidden)
    config = retained.load_retained_native_epoch_policy(fixture, selection)

    assert config.predicate_policy_admission_refs == (selection.epoch_admission_evidence_ref,)
    assert config.trusted_issuers[0].public_key_path == selection.epoch_public_key_path
    assert config.trusted_issuers[0].identity == native.custodian.issuer_identity
    assert config.trusted_issuers[0].roles == native.custodian.issuer_roles
    assert _stored_bytes(fixture.store) == before


@pytest.mark.parametrize("change", ["missing_key", "wrong_key", "grafted_profile"])
def test_retained_epoch_policy_refuses_unresolved_key_or_selected_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    fixture, selection, _scenario, _native = _epoch_fixture(tmp_path, monkeypatch)
    if change == "grafted_profile":
        selection = retained.RetainedNativeEpochPolicySelection(
            selection.epoch_admission_evidence_ref.model_copy(
                update={"manifest_profile_sha256": "sha256:" + "f" * 64}
            ),
            selection.epoch_public_key_path,
        )
    elif change == "missing_key":
        selection = retained.RetainedNativeEpochPolicySelection(
            selection.epoch_admission_evidence_ref, tmp_path / "missing.pub"
        )
    else:
        wrong_key = tmp_path / "wrong.pub"
        wrong_key.write_bytes(artifacts.KeyPair.generate().public_pem())
        selection = retained.RetainedNativeEpochPolicySelection(
            selection.epoch_admission_evidence_ref, wrong_key
        )
    before = _stored_bytes(fixture.store)
    with pytest.raises((ValueError, OSError)):
        retained.load_retained_native_epoch_policy(fixture, selection)
    assert _stored_bytes(fixture.store) == before


@pytest.mark.parametrize("change", ["scope", "query"])
def test_retained_epoch_policy_binds_independently_selected_prepared_scope_and_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    from polisyos.core import security

    fixture, selection, _scenario, native = _epoch_fixture(tmp_path, monkeypatch)
    if change == "scope":
        admission = native.admission.model_copy(
            update={
                "key": native.admission.key.model_copy(update={"scope_ref": "sha256:" + "e" * 64})
            }
        )
    else:
        admission = native.admission.model_copy(
            update={"requested_query_context_ref": "sha256:" + "e" * 64}
        )
    signed = native.custodian.persist_or_reuse(
        blob_bytes=security.canonical_statement_bytes(admission),
        signing_profile_ref=native.custodian.owner_ref,
        signer_provenance_ref=native.custodian.owner_ref,
    )
    selection = retained.RetainedNativeEpochPolicySelection(
        _selected_evidence_ref(fixture.store, signed.evidence.evidence_record_ref),
        selection.epoch_public_key_path,
    )
    before = _stored_bytes(fixture.store)
    with pytest.raises(ValueError):
        retained.load_retained_native_epoch_policy(fixture, selection)
    assert _stored_bytes(fixture.store) == before


@pytest.mark.parametrize("change", ["policy_hash", "provenance"])
def test_retained_epoch_policy_reconciles_a_validly_signed_policy_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    from polisyos.core import contracts, security
    from polisyos.core.artifacts import input_ref_from_artifact_ref, signed_evidence

    fixture, selection, _scenario, native = _epoch_fixture(tmp_path, monkeypatch)
    admission = native.admission
    provenance = native.custodian.owner_ref
    if change == "policy_hash":
        admission = admission.model_copy(update={"policy_content_hash": "sha256:" + "f" * 64})
        signed = native.custodian.persist_or_reuse(
            blob_bytes=security.canonical_statement_bytes(admission),
            signing_profile_ref=provenance,
            signer_provenance_ref=provenance,
        )
        record_ref = signed.evidence.evidence_record_ref
    else:
        provenance = fixture.store.put_bytes(
            b"a different fixture institution provenance",
            artifacts.ArtifactWriteOptions(
                kind="fixture.epoch.policy_owner", media_type="application/octet-stream"
            ),
        )
        record = security.parse_canonical_statement(
            native.signed.evidence.record_bytes, contracts.chronology.SignedArtifactEvidenceRecord
        ).model_copy(
            update={"signing_profile_ref": provenance, "signer_provenance_ref": provenance}
        )
        record_ref = fixture.store.put_bytes(
            signed_evidence._record_bytes(record),
            signed_evidence._record_options(
                inputs=[
                    input_ref_from_artifact_ref(record.artifact_ref, role="signed_artifact"),
                    input_ref_from_artifact_ref(
                        record.signature_artifact_ref, role="exact_signature_bytes"
                    ),
                ]
            ),
        )
    selected = retained.RetainedNativeEpochPolicySelection(
        _selected_evidence_ref(fixture.store, record_ref), selection.epoch_public_key_path
    )
    before = _stored_bytes(fixture.store)
    with pytest.raises(ValueError):
        retained.load_retained_native_epoch_policy(fixture, selected)
    assert _stored_bytes(fixture.store) == before


def _old_mandate_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    from datetime import UTC, datetime, timedelta

    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality import agent_action_authority as authority
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from tests._helpers.acquisition_human_decision import (
        _mandate_authority_evidence,
        persist_signed,
    )
    from tests._helpers.acquisition_served_history import _contract

    fixture, selection, _scenario, _native = _epoch_fixture(tmp_path, monkeypatch)
    now = datetime.now(UTC)
    start = now - timedelta(hours=2)
    end = now - timedelta(hours=1) if status == "expired" else now + timedelta(hours=1)
    owner_identity, current_identity = "fixture://old-mandate-owner", "fixture://old-current-owner"
    contract = _contract()
    envelope = type(contract.action_envelopes[0]).model_validate(
        {
            **contract.action_envelopes[0].model_dump(mode="json"),
            "mandate_owner_ref": owner_identity,
            "required_tenant_id": fixture.tenant_id,
            "valid_from": start,
            "valid_until": end,
        }
    )
    contract = type(contract).model_validate(
        {
            **contract.model_dump(mode="json"),
            "mandate_owner_ref": owner_identity,
            "action_envelopes": [envelope.model_dump(mode="json")],
        }
    )
    current = _mandate_authority_evidence(
        owner_ref=owner_identity,
        signer_identity=current_identity,
        effective_from=start,
        effective_until=end,
        current=status != "revoked",
        revoked_at=now - timedelta(seconds=1) if status == "revoked" else None,
        rule_version_ref=contract.rule_version_ref,
    )
    database = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    event_log = RuntimeDiagnosticEventLog(store=database, artifact_store=fixture.store)
    control = SimpleNamespace(_artifact_store=fixture.store, _diagnostic_event_log=event_log)
    key_root = tmp_path / "keys"
    key_root.mkdir()
    refs = []
    for payload, identity, name, kind, schema, version in (
        (
            contract,
            owner_identity,
            "owner",
            "runtime_quality.agent_action_delegation_contract",
            "polisyos.runtime.DelegationContract",
            authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        ),
        (
            current,
            current_identity,
            "current",
            "runtime_quality.current_mandate_owner",
            "polisyos.runtime.CurrentMandateOwnerEvidence",
            authority.CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
        ),
    ):
        pair = artifacts.KeyPair.generate()
        (key_root / f"{name}.pub").write_bytes(pair.public_pem())
        artifact_id = persist_signed(
            control,
            payload,
            kind=kind,
            schema_name=schema,
            schema_version=version,
            signer=artifacts.Ed25519Signer.from_pem(pair.private_pem()),
            signer_identity=identity,
            tenant_id=fixture.tenant_id,
            cell_id=fixture.cell_id,
            run_id=fixture.control_run_id,
            job_id="old-admission-job",
            now=start,
        )
        matches = tuple(
            ref
            for ref in retained._selected_profiles(fixture.store, kind)
            if str(ref.artifact_id) == artifact_id
        )
        assert len(matches) == 1
        refs.append(matches[0])
    continuation = retained.RetainedNativeAdmissionSelection(
        selection.epoch_admission_evidence_ref, selection.epoch_public_key_path, refs[0], refs[1]
    )
    fixture.store.put_bytes(
        b'{"limitation":"fixture disconfirming information"}',
        artifacts.ArtifactWriteOptions(
            kind="test.acquisition.disconfirming", media_type="application/json"
        ),
    )
    fixture.terminal = SimpleNamespace(route_id="sha256:" + "a" * 64)
    return fixture, selection, continuation, key_root


@pytest.mark.parametrize("status", ["expired", "revoked"])
def test_readable_epoch_policy_never_renews_an_expired_or_revoked_current_mandate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    fixture, selection, continuation, key_root = _old_mandate_fixture(tmp_path, monkeypatch, status)
    before = _stored_bytes(fixture.store)
    assert retained.load_retained_native_epoch_policy(fixture, selection)
    with pytest.raises(ValueError, match="retained_native_continuation_mandate_not_current"):
        retained.load_retained_native_admission_checkpoint(
            fixture, continuation, institution_key_root=key_root
        )
    assert _stored_bytes(fixture.store) == before


def test_post_outcome_checkpoint_reads_expired_signed_inputs_without_renewing_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, _selection, continuation, key_root = _old_mandate_fixture(
        tmp_path, monkeypatch, "expired"
    )
    before = _stored_bytes(fixture.store)

    def signing_forbidden(*args, **kwargs):
        raise AssertionError("historical checkpoint reads must not sign")

    monkeypatch.setattr(artifacts.Ed25519Signer, "sign", signing_forbidden)
    checkpoint = retained.load_retained_native_action_resume_checkpoint(
        fixture, continuation, institution_key_root=key_root
    )
    assert checkpoint.action_job_id == "old-admission-job"
    assert checkpoint.mandate_slot["delegation_contract_ref"] == str(
        continuation.delegation_contract_ref.artifact_id
    )
    # The historical loader supplies configuration, never a current-use grant.
    with pytest.raises(ValueError, match="retained_native_continuation_mandate_not_current"):
        retained.load_retained_native_admission_checkpoint(
            fixture, continuation, institution_key_root=key_root
        )
    assert _stored_bytes(fixture.store) == before


def test_epoch_only_selection_cannot_be_combined_with_a_whole_current_continuation():
    from tests.integration.runtime_quality.test_native_derivation_acquisition_served import (
        assert_retained_native_paid_input_admission,
    )

    with pytest.raises(
        ValueError, match="retained_native_policy_and_current_continuation_conflict"
    ):
        assert_retained_native_paid_input_admission(
            base=None,
            output_root=None,
            monkeypatch=None,
            transport_calls=[],
            semantic_kernel_entries=[],
            continuation_selection=object(),
            epoch_policy_selection=object(),
        )


def _resume_payload_fixture(tmp_path: Path):
    """Build real owned payload/SQL locators, without claiming action admission."""
    from polisyos.core import canon
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.control.job_scope_admission import (
        ControlJobScopeAdmissionMixin,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

    fixture = SimpleNamespace(
        tenant_id="tenant-resume", cell_id="cell-resume", control_run_id="run-resume"
    )
    claims = SimpleNamespace(tenant_id=fixture.tenant_id, cell_id=fixture.cell_id)
    route_id = "sha256:" + "a" * 64
    request = {
        "route_projection_hash": "sha256:" + "b" * 64,
        "planner_report_hash": "sha256:" + "c" * 64,
        "replay_pins": {
            "source_job_id": "source-job",
            "compiled_ref": "sha256:" + "d" * 64,
            "compiled_content_hash": "sha256:" + "e" * 64,
            "terminal_event_id": "source-terminal",
            "design_problem_ref": "sha256:" + "f" * 64,
            "cost_basis_hash": "sha256:" + "1" * 64,
        },
        "idempotency_key": "same-existing-admission",
    }
    payload = {
        "tenant_id": fixture.tenant_id,
        "cell_id": fixture.cell_id,
        "run_id": fixture.control_run_id,
        "route_id": route_id,
        "request": request,
    }
    store = artifacts.FileSystemCAS(tmp_path / "cas").for_tenant(fixture.tenant_id, fixture.cell_id)
    with tenant_scope(None, tenant_id=fixture.tenant_id, cell_id=fixture.cell_id):
        reference = store.put_bytes(
            canon.to_canonical_bytes(payload),
            artifacts.ArtifactWriteOptions(
                kind="runtime.control_job_payload.acquisition",
                media_type="application/json",
                canon=artifacts.CanonInfo.from_spec(canon.CanonSpec()),
            ),
        )
    database = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    job = database.create_job(
        job_id="same-existing-job",
        kind="acquisition",
        run_id=fixture.control_run_id,
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=str(reference.artifact_id),
        submitted_by="fixture-mechanics-only",
    )
    control = ControlJobScopeAdmissionMixin()
    control._artifact_store = store
    control._control_store = database
    checkpoint = SimpleNamespace(
        action_job_id=job.job_id,
        mandate_slot={"route_id": route_id},
        human_decision_record_ref=artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID.model_validate("sha256:" + "2" * 64),
            kind="runtime_quality.agent_action_human_decision",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "3" * 64,
        ),
    )
    return fixture, checkpoint, claims, control


def test_resume_bootstrap_reads_actual_owned_payload_and_same_job_without_leasing(tmp_path: Path):
    from polisyos.core.security.tenant_context import (
        clear_tenant_context,
        get_current_tenant_id_or_none,
    )

    fixture, checkpoint, claims, control = _resume_payload_fixture(tmp_path)
    before = _stored_bytes(control._artifact_store)
    original = control._control_store.get_job(checkpoint.action_job_id)
    with clear_tenant_context():
        result = retained.read_retained_native_action_resume_inputs(
            fixture,
            checkpoint,
            claims=claims,
            control=control,
            idempotency_key="same-existing-admission",
        )
        assert get_current_tenant_id_or_none() is None
    assert result.job == original
    assert result.request.idempotency_key == "same-existing-admission"
    assert result.payload_ref == original.payload_ref
    assert control._control_store.get_job(checkpoint.action_job_id) == original
    assert _stored_bytes(control._artifact_store) == before


@pytest.mark.parametrize(
    "mismatch", ["claims", "cas_owner", "cas_ambient_owner", "idempotency", "job", "route"]
)
def test_resume_bootstrap_refuses_foreign_or_different_stored_inputs(tmp_path: Path, mismatch: str):
    from polisyos.core.security.tenant_context import (
        clear_tenant_context,
        get_current_tenant_id_or_none,
    )

    fixture, checkpoint, claims, control = _resume_payload_fixture(tmp_path)
    before = _stored_bytes(control._artifact_store)
    key = "same-existing-admission"
    expected = ValueError
    code = "retained_native_resume_payload_scope_mismatch"
    if mismatch == "claims":
        claims.tenant_id = "foreign-tenant"
        code = "retained_native_resume_claim_scope_mismatch"
    elif mismatch in {"cas_owner", "cas_ambient_owner"}:
        fixture.tenant_id = claims.tenant_id = "foreign-tenant"
        if mismatch == "cas_ambient_owner":
            control._artifact_store = artifacts.FileSystemCAS(
                tmp_path / "cas", ownership_enforced=True
            )
            expected = artifacts.ArtifactOwnershipError
            code = None
    elif mismatch == "idempotency":
        key = "another-admission"
        code = "retained_native_resume_idempotency_mismatch"
    elif mismatch == "job":
        checkpoint.action_job_id = "missing-job"
        code = "retained_native_resume_job_missing"
    else:
        checkpoint.mandate_slot["route_id"] = "sha256:" + "4" * 64
    with clear_tenant_context():
        with pytest.raises(expected) as refusal:
            retained.read_retained_native_action_resume_inputs(
                fixture, checkpoint, claims=claims, control=control, idempotency_key=key
            )
        if code is not None:
            assert refusal.value.args == (code,)
        assert get_current_tenant_id_or_none() is None
    assert _stored_bytes(control._artifact_store) == before


def test_resume_effect_guard_repeatedly_refuses_actual_n4_and_new_activation_before_body():
    import inspect
    import sys

    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.generation_cycle import N4GenerationPort

    assert sys.monitoring.get_tool(5) is None
    with retained.forbid_retained_native_resume_effects():
        for _ in range(2):
            pending = N4GenerationPort.__call__(None, None, cycle_index=0)
            with pytest.raises(
                AssertionError,
                match=r"^retained_native_resume_forbidden_effect:N4GenerationPort\.__call__$",
            ):
                pending.send(None)
            pending.close()
        for function in (
            AcquisitionWorldGrowthBridge._admit_stored_attempt,
            artifacts.Ed25519Signer.sign,
        ):
            arguments = {
                name: None
                for name, parameter in inspect.signature(function).parameters.items()
                if parameter.default is inspect.Parameter.empty
            }
            with pytest.raises(AssertionError, match=r"^retained_native_resume_forbidden_effect:"):
                function(**arguments)
    assert sys.monitoring.get_tool(5) is None
    assert sys.monitoring.get_events(5) == 0


def test_resume_effect_guard_never_takes_an_existing_monitoring_slot():
    import sys

    assert sys.monitoring.get_tool(5) is None
    sys.monitoring.use_tool_id(5, "another-observer")
    try:
        with (
            pytest.raises(RuntimeError, match="retained_native_resume_monitoring_slot_occupied"),
            retained.forbid_retained_native_resume_effects(),
        ):
            pytest.fail("occupied slot must refuse entry")
        assert sys.monitoring.get_tool(5) == "another-observer"
    finally:
        sys.monitoring.free_tool_id(5)


def test_resume_requires_existing_selection_and_never_changes_its_validity():
    from tests.integration.runtime_quality.test_native_derivation_acquisition_served import (
        assert_retained_native_paid_input_admission,
    )

    common = {
        "base": None,
        "output_root": None,
        "monkeypatch": None,
        "transport_calls": [],
        "semantic_kernel_entries": [],
    }
    with pytest.raises(ValueError, match="retained_native_resume_current_selection_required"):
        assert_retained_native_paid_input_admission(**common, resume_existing_action=True)
    with pytest.raises(ValueError, match="retained_native_validity_cannot_change_existing_acts"):
        assert_retained_native_paid_input_admission(
            **common, continuation_selection=object(), authority_valid_for_seconds=1200
        )


@pytest.mark.parametrize("seconds", [599, 3601, True])
def test_new_fixture_validity_window_is_bounded_before_any_institutional_effect(seconds):
    from tests.integration.runtime_quality.test_native_derivation_acquisition_served import (
        _run_signed_native_leaf_action,
    )

    with pytest.raises(ValueError, match="native_fixture_authority_window_out_of_bounds"):
        _run_signed_native_leaf_action(
            served=None,
            trust=None,
            signers=None,
            identities=None,
            institution_key_root=None,
            route_id=None,
            idempotency_key=None,
            authority_valid_for_seconds=seconds,
        )


def _resume_assertion_inputs(tmp_path: Path):
    """Exercise assertion mechanics, not receipt/event authority verification."""
    from dataclasses import replace

    from polisyos.core import canon

    fixture, _checkpoint, claims, control = _resume_payload_fixture(tmp_path)
    options = artifacts.ArtifactWriteOptions(
        kind="runtime_quality.acquisition_route_phase_receipt",
        media_type="application/json",
        canon=artifacts.CanonInfo.from_spec(canon.CanonSpec()),
    )
    with retained.retained_native_owner_scope(fixture, claims):
        reference = control._artifact_store.put_bytes(
            b'{"assertion_fixture":"selected"}', options, return_selected_profile=True
        )
        competing = control._artifact_store.put_bytes(
            control._artifact_store.get_bytes(reference),
            artifacts.ArtifactWriteOptions(
                kind="test.native.competing_profile",
                media_type="application/json",
                canon=options.canon,
            ),
            return_selected_profile=True,
        )
    # These SQL rows deliberately carry no source/PA2 claim. The real caller
    # obtains its phase chain from AcquisitionRoutePhaseSink.current_action_outcome.
    before = control._control_store.advance_acquisition_action_head(
        tenant_id=fixture.tenant_id,
        cell_id=fixture.cell_id,
        run_id=fixture.control_run_id,
        source_job_id="source-job",
        route_id="sha256:" + "a" * 64,
        action_generation=2,
        expected_head_generation=0,
        receipt_ref=str(reference.artifact_id),
        receipt_sha256=str(reference.artifact_id),
        durable_event_id="assertion-only-event",
        coarse_phase="executing",
        receipt_phase="outcome_selected",
        recovery_state="none",
        job_id="same-existing-job",
        predecessor_receipt_ref=None,
        receipt_manifest_profile_sha256=reference.manifest_profile_sha256,
    )
    outcome = SimpleNamespace(
        head=replace(before, head_generation=5, receipt_phase="terminal"),
        phase_chain=(SimpleNamespace(receipt_ref=str(reference.artifact_id)),),
    )
    return fixture, claims, control, before, reference, competing, outcome


def test_resume_assertion_preserves_exact_selected_ancestor(tmp_path: Path):
    fixture, claims, control, before, reference, _competing, outcome = _resume_assertion_inputs(
        tmp_path
    )
    with retained.retained_native_owner_scope(fixture, claims):
        retained.require_retained_native_resume_descendant(
            store=control._artifact_store,
            control_store=control._control_store,
            before_head=before,
            before_ref=reference,
            outcome=outcome,
        )


@pytest.mark.parametrize("change", ["job", "generation", "foreign_chain", "selected_profile"])
def test_resume_assertion_refuses_another_job_or_non_descendant(tmp_path: Path, change: str):
    from dataclasses import replace

    fixture, claims, control, before, reference, competing, outcome = _resume_assertion_inputs(
        tmp_path
    )
    code = "retained_native_resume_action_identity_changed"
    if change == "job":
        outcome.head = replace(outcome.head, job_id="another-same-route-job")
    elif change == "generation":
        outcome.head = replace(outcome.head, action_generation=before.action_generation + 1)
    elif change == "foreign_chain":
        outcome.phase_chain = (SimpleNamespace(receipt_ref="sha256:" + "5" * 64),)
        code = "retained_native_resume_selected_ancestor_missing"
    else:
        assert competing.artifact_id == reference.artifact_id
        assert competing.manifest_profile_sha256 != reference.manifest_profile_sha256
        reference = competing
        code = "retained_native_resume_ancestor_profile_changed"
    with retained.retained_native_owner_scope(fixture, claims):
        with pytest.raises(ValueError) as refusal:
            retained.require_retained_native_resume_descendant(
                store=control._artifact_store,
                control_store=control._control_store,
                before_head=before,
                before_ref=reference,
                outcome=outcome,
            )
        assert refusal.value.args == (code,)
