"""Transport/effect boundaries; complete paid provenance is the served owner's test."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from polisyos.core import contracts
from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionRouteMutationRequest,
    AcquisitionRouteProjection,
)
from polisyos.runtime.http.services.acquisition_surface_execution import (
    WorldBankWDIAcquisitionExecutionPort,
)
from polisyos.runtime.http.services.control.run_lifecycle import (
    AcquisitionRouteLoopAuthoritySink,
    _native_acquisition_receipt_selected_inputs,
)
from polisyos.runtime.quality.acquisition_executor import LiveAcquisitionExecutionError
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRoutePhaseReceipt,
    NativeDerivationLeafProviderSelection,
    NativePaidInputAdmissionSelection,
    VerifiedAcquisitionRouteClosure,
)
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge


def _ref(kind: str, label: str) -> ArtifactRef:
    codec = contracts.epoch.acquisition_artifact_codec(kind)
    return ArtifactRef(
        artifact_id="sha256:" + hashlib.sha256(label.encode()).hexdigest(),
        kind=kind,
        media_type=codec.media_type if codec is not None else "application/json",
        manifest_profile_sha256="sha256:"
        + hashlib.sha256((label + ":profile").encode()).hexdigest(),
    )


def _selection() -> NativePaidInputAdmissionSelection:
    """Typed transport only: these refs deliberately have no paid custody proof."""
    return NativePaidInputAdmissionSelection(
        original_action_job_id="original-provider-purchase",
        attempt_ref=_ref("runtime_quality.acquisition_world_growth_attempt", "attempt"),
        executing_phase_ref=_ref("runtime_quality.acquisition_route_phase_receipt", "executing"),
        terminal_ref=_ref("runtime_quality.acquisition_route_loop_receipt", "terminal"),
        deferral_ref=_ref("runtime_quality.acquisition_world_growth_deferral", "deferral"),
        negative_receipt_ref=_ref("epoch.production_receipt", "negative"),
        prepared_epoch_ref=_ref("epoch.prepared", "prepared"),
        owner_declared_profile_ref=_ref(
            "runtime.quality.native_derivation_leaf_cost_profile", "quote"
        ),
    )


def _projection_payload() -> dict:
    return {
        "tenant_id": "tenant",
        "cell_id": "cell",
        "run_id": "run",
        "route_id": "sha256:" + "1" * 64,
        "route_projection_hash": "sha256:" + "1" * 64,
        "planner_report_hash": "sha256:" + "2" * 64,
        "planner_record_id": "planner-leaf",
        "recommended_strategy": "public_registry",
        "cost_basis": {},
        "replay_pins": {
            "source_job_id": "source-job",
            "compiled_ref": "sha256:" + "3" * 64,
            "compiled_content_hash": "sha256:" + "4" * 64,
            "terminal_event_id": "source-terminal-event",
            "design_problem_ref": "sha256:" + "5" * 64,
            "cost_basis_hash": "sha256:" + "6" * 64,
        },
        "authority_capability": "producer_missing",
        "execution_capability": "producer_missing",
    }


def _projection_hash(route_id: str, selection: NativePaidInputAdmissionSelection | None) -> str:
    # This exercises the canonical pure transport property without constructing
    # or asserting a verified route/source or a current action permission.
    return VerifiedAcquisitionRouteClosure.current_projection_hash.fget(
        SimpleNamespace(route_id=route_id, prior_paid_input_admission=selection)
    )


def test_prior_paid_transport_and_public_schema_preserve_canonical_epoch_media() -> None:
    selected = _selection()
    payload = selected.model_dump(mode="json")
    schema = selected.model_json_schema()
    Draft202012Validator(schema).validate(payload)
    assert selected.negative_receipt_ref.media_type == (
        "application/vnd.polisyos.epoch-production-receipt+json"
    )
    assert selected.prepared_epoch_ref.media_type == "application/vnd.polisyos.epoch+json"
    for name in ("negative_receipt_ref", "prepared_epoch_ref", "attempt_ref"):
        bad = {**payload, name: {**payload[name], "manifest_profile_sha256": None}}
        assert list(Draft202012Validator(schema).iter_errors(bad))
        with pytest.raises(ValidationError):
            NativePaidInputAdmissionSelection.model_validate(bad)
    wrong_media = {
        **payload,
        "negative_receipt_ref": {
            **payload["negative_receipt_ref"],
            "media_type": "application/json",
        },
    }
    with pytest.raises(ValidationError):
        NativePaidInputAdmissionSelection.model_validate(wrong_media)


def test_projection_discriminator_and_schema_require_exact_admission_only_shape() -> None:
    legacy = AcquisitionRouteProjection.model_validate(_projection_payload())
    old = legacy.model_dump(mode="json")
    assert old["schema_version"] == "AcquisitionRouteProjection@1.1"
    assert "prior_paid_input_admission" not in old and "route_status" not in old
    schema = legacy.model_json_schema()
    Draft202012Validator(schema).validate(old)
    selected = _selection()
    payload = {
        **old,
        "schema_version": "AcquisitionRouteProjection@1.2",
        "route_status": "paid_input_admission_only",
        "prior_paid_input_admission": selected.model_dump(mode="json"),
        "route_projection_hash": _projection_hash(legacy.route_id, selected),
    }
    current = AcquisitionRouteProjection.model_validate(payload)
    Draft202012Validator(schema).validate(current.model_dump(mode="json"))
    for update in (
        {"schema_version": "AcquisitionRouteProjection@1.1"},
        {"route_status": "costed_actionable"},
        {"prior_paid_input_admission": None},
    ):
        bad = {**payload, **update}
        assert list(Draft202012Validator(schema).iter_errors(bad))
        with pytest.raises(ValidationError):
            AcquisitionRouteProjection.model_validate(bad)


def test_new_projection_changes_action_identity_without_changing_legacy_identity() -> None:
    base = AcquisitionRouteProjection.model_validate(_projection_payload())
    request = AcquisitionRouteMutationRequest(
        route_projection_hash=base.route_id,
        planner_report_hash=base.planner_report_hash,
        replay_pins=base.replay_pins,
        idempotency_key="same-key",
    )
    kwargs = {
        "tenant_id": base.tenant_id,
        "cell_id": base.cell_id,
        "run_id": base.run_id,
        "route_id": base.route_id,
    }
    legacy = AcquisitionActionService._job_id_for_request(**kwargs, request=request)
    selected = _selection()
    new = request.model_copy(
        update={"route_projection_hash": _projection_hash(base.route_id, selected)}
    )
    other_view = NativePaidInputAdmissionSelection.model_validate(
        {
            **selected.model_dump(mode="python"),
            "attempt_ref": {
                **selected.attempt_ref.model_dump(mode="python"),
                "manifest_profile_sha256": "sha256:" + "f" * 64,
            },
        }
    )
    assert _projection_hash(base.route_id, None) == base.route_id
    assert _projection_hash(base.route_id, other_view) != _projection_hash(base.route_id, selected)
    assert AcquisitionActionService._job_id_for_request(**kwargs, request=new) != legacy
    roundtrip = AcquisitionRouteMutationRequest.model_validate(new.model_dump(mode="json"))
    assert AcquisitionActionService._job_id_for_request(
        **kwargs, request=roundtrip
    ) == AcquisitionActionService._job_id_for_request(**kwargs, request=new)
    assert AcquisitionActionService._job_id_for_request(**kwargs, request=request) == legacy
    with pytest.raises(ValidationError):
        AcquisitionRouteMutationRequest.model_validate(
            {**new.model_dump(mode="json"), "prior_paid_input_admission": selected.model_dump()}
        )


def test_phase_lineage_keeps_prior_selection_and_rejects_a_later_phase_swap() -> None:
    paid = _selection()
    common = {
        "receipt_id": "new-admission",
        "tenant_id": "tenant",
        "cell_id": "cell",
        "run_id": "run",
        "source_job_id": "source-job",
        "route_id": "sha256:" + "1" * 64,
        "action_generation": 2,
        "job_id": "new-admission-job",
        "compiled_ref": "sha256:" + "3" * 64,
        "planner_report_hash": "sha256:" + "2" * 64,
        "cost_basis_hash": "sha256:" + "6" * 64,
        "decision_ref": "sha256:" + "7" * 64,
        "coarse_phase": "requested",
        "receipt_phase": "requested",
        "recovery_state": "none",
        "owner_declared_profile_ref": paid.owner_declared_profile_ref,
        "native_leaf_provider_selection": NativeDerivationLeafProviderSelection(
            source_node_id="leaf-a",
            supplier_ref=_ref("catalog.acquisition_supplier_declaration", "supplier"),
            authority_entry_id="acquisition-authority:sha256:" + "a" * 64,
            connector_id="worldbank.wdi",
        ),
        "generated_at": datetime.now(UTC),
    }
    old = AcquisitionRoutePhaseReceipt(schema_version="AcquisitionRoutePhaseReceipt@1.3", **common)
    assert "prior_paid_input_admission" not in old.model_dump(mode="json")
    phase = AcquisitionRoutePhaseReceipt(
        schema_version="AcquisitionRoutePhaseReceipt@1.4",
        prior_paid_input_admission=paid,
        **common,
    )
    inputs = _native_acquisition_receipt_selected_inputs(phase)
    for role, ref in paid.lineage_inputs():
        matching = [item for item in inputs if item.role == role]
        assert len(matching) == 1
        assert matching[0].manifest_profile_sha256 == ref.manifest_profile_sha256
    assert not AcquisitionRouteLoopAuthoritySink._same_action_identity(old, phase)
    with pytest.raises(ValidationError):
        AcquisitionRoutePhaseReceipt(
            schema_version="AcquisitionRoutePhaseReceipt@1.3",
            prior_paid_input_admission=paid,
            **common,
        )


def test_admission_only_route_refuses_provider_reservation_before_any_binding_or_io(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = object.__new__(WorldBankWDIAcquisitionExecutionPort)
    port._world_growth_bridge = None
    calls = []

    def forbidden(**kwargs):
        calls.append("binding_or_provider")
        raise AssertionError("admission-only transport reached a fresh provider boundary")

    monkeypatch.setattr(
        "polisyos.runtime.http.services.acquisition_surface_execution.resolve_world_bank_wdi_route_execution_bindings",
        forbidden,
    )
    closure = SimpleNamespace(
        native_derivation_leaf_scope=object(), prior_paid_input_admission=_selection()
    )
    with pytest.raises(LiveAcquisitionExecutionError) as refused:
        port.reserve_route_binding(closure)
    assert refused.value.code == "native_paid_input_admission_fresh_io_forbidden"
    assert calls == []
    assert tuple(tmp_path.iterdir()) == ()
    # A valid transport shape cannot establish custody or permit a protected use.
    with pytest.raises(LiveAcquisitionExecutionError) as owner_missing:
        port._require_native_quote_or_paid_attempt(closure)
    assert owner_missing.value.code == "native_paid_input_admission_owner_missing"


def test_native_growth_selector_uses_selected_profile_instead_of_unrelated_default(
    tmp_path,
) -> None:
    """Exercise profile transport only; this payload is not a growth receipt."""
    from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo

    store = FileSystemCAS(tmp_path / "cas")
    payload = {"purpose": "selector_transport_only"}
    unrelated = store.put_json(
        payload,
        PutOptions(kind="fixture.unrelated_default", media_type="application/json"),
        return_selected_profile=True,
    )
    kind = "runtime_quality.acquisition_world_growth_receipt"
    selected = store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name="test.NativeGrowthProfileTransport", version="1.0"),
        ),
        return_selected_profile=True,
    )
    assert unrelated.artifact_id == selected.artifact_id
    assert store.get_manifest(str(selected.artifact_id)).kind == "fixture.unrelated_default"
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store = store
    native = SimpleNamespace(native_derivation_leaf_scope=object())
    assert bridge._native_growth_owner_selector(native, str(selected.artifact_id), kind) == selected
    assert bridge._native_growth_owner_selector(native, selected, kind) == selected
    missing_profile = selected.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(ValueError, match="acquisition_growth_owner_profile_invalid"):
        bridge._native_growth_owner_selector(native, missing_profile, kind)

    alternate = store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name="test.NativeGrowthProfileTransport", version="2.0"),
        ),
        return_selected_profile=True,
    )
    assert alternate.artifact_id == selected.artifact_id
    assert alternate.manifest_profile_sha256 != selected.manifest_profile_sha256
    with pytest.raises(ValueError, match="acquisition_growth_owner_profile_not_unique"):
        bridge._native_growth_owner_selector(native, str(selected.artifact_id), kind)
    assert bridge._native_growth_owner_selector(native, selected, kind) == selected


def test_legacy_growth_selector_preserves_existing_id_without_native_inventory() -> None:
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    legacy = SimpleNamespace(native_derivation_leaf_scope=None)
    reference = "sha256:" + "a" * 64
    assert bridge._native_growth_owner_selector(legacy, reference, "legacy.kind") == reference
