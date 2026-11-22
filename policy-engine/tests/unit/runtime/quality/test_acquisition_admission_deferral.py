"""Actual epoch negatives bind their paid evidence and caller-selected action scope.

The component supplies an executing-phase input. Full planner, pricing and
current grant admission remain the served owner's separate responsibility.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.contracts import SelectedArtifactRef
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api import catalog
from polisyos.runtime.http.services.control.run_lifecycle import AcquisitionRouteLoopAuthoritySink
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import acquisition_executor
from polisyos.runtime.quality import acquisition_world_growth as growth
from polisyos.runtime.quality.acquisition_planner import (
    persist_native_derivation_leaf_cost_profile,
    produce_acquisition_cost_basis_record,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
    NativeDerivationLeafProviderSelection,
    NativePaidInputAdmissionSelection,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.semantic_epoch import PersistedSemanticEpochProductionReceipt
from tests._helpers.acquisition_epoch_production import production_admission_inputs
from tests._helpers.acquisition_production import _entry, _run
from tests.unit.runtime.quality.test_native_derivation_leaf_cost_profile import (
    _profile,
    _profile_scope,
)

_TENANT = "00000000-0000-0000-0000-00000000000a"
_CELL = "018f47a0-0000-7000-8000-000000000001"
_CANON = canon.CanonSpec(forbid_floats=False)


def _component_scope_ref(store, *, kind: str, label: str):
    return store.put_json(
        {"purpose": "component_scope_only", "label": label},
        artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
        return_selected_profile=True,
    )


def _negative_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, with_action_history: bool = False
):
    # This existing fixture uses the actual acquisition executor and persisted
    # Fabric observer/sink evidence. Direct connector fetch is forbidden.
    authority, evidence, transport, _journal = _run(tmp_path / "live", monkeypatch)
    store = artifacts.FileSystemCAS(tmp_path / "live/cas")
    args = production_admission_inputs(
        tmp_path / "epoch",
        store=store,
        authority=authority,
        overlay_path=tmp_path / "epoch/overlay.duckdb",
        epoch_history_root=tmp_path / "epoch/history",
        authority_purpose="candidate_simulation",
        scope_payload={
            "domain": "public-finance",
            "jurisdiction": "UA",
            "year": 2024,
        },
    )
    negative = acquisition_executor.admit_acquisition_with_production_semantic_epoch(
        **args,
        raw_evidence_ref=evidence.raw_evidence_ref,
        live_source_execution=evidence,
    )
    assert type(negative) is PersistedSemanticEpochProductionReceipt
    assert negative.failure_codes == ("policy_admission_missing",)
    assert evidence.call_count == evidence.transport_trace.call_count == 1
    call_count = len(transport.calls)
    supplier = catalog.persist_acquisition_supplier_declaration(
        store, authority, entry_id=_entry().entry_id
    )
    supplier = artifacts.ArtifactRef.model_validate(supplier.model_dump(mode="python"))
    now = datetime.now(UTC)
    cost_scope = None
    cost_hash = "sha256:" + "3" * 64
    if with_action_history:
        scope, quote = _profile_scope(store)
        cost_scope = scope.model_copy(
            update={
                "tenant_id": _TENANT,
                "cell_id": _CELL,
                "run_id": "run-negative-component",
                "source_job_id": "source-negative-component",
                "source_node_id": "component-source",
                "selected_supplier_ref": supplier,
                "missing_distribution": "government.balance",
            }
        )
        configured_cost = persist_native_derivation_leaf_cost_profile(
            store, _profile(cost_scope, quote, now=now)
        )
        cost = produce_acquisition_cost_basis_record(
            missing_distribution=cost_scope.missing_distribution,
            strategy=cost_scope.strategy,
            owner_declared_profile_ref=configured_cost,
            store=store,
            expected_scope=cost_scope,
            now=now,
        )
        assert cost is not None
        cost_hash = cost.record_content_hash
    else:
        configured_cost = _component_scope_ref(
            store,
            kind="runtime.quality.native_derivation_leaf_cost_profile",
            label="not_a_price_or_grant_assertion",
        )
    compiled = _component_scope_ref(store, kind="tests.acquisition.scope", label="source")
    phase = AcquisitionRoutePhaseReceipt(
        schema_version="AcquisitionRoutePhaseReceipt@1.3",
        receipt_id="component.executing",
        tenant_id=_TENANT,
        cell_id=_CELL,
        run_id="run-negative-component",
        source_job_id="source-negative-component",
        route_id="sha256:" + "1" * 64,
        action_generation=1,
        job_id="action-negative-component",
        compiled_ref=str(compiled.artifact_id),
        planner_report_hash="sha256:" + "2" * 64,
        cost_basis_hash=cost_hash,
        decision_ref="sha256:" + "4" * 64,
        coarse_phase="executing",
        receipt_phase="executing",
        recovery_state="none",
        predecessor_receipt_ref="sha256:" + "5" * 64,
        owner_declared_profile_ref=configured_cost,
        native_leaf_provider_selection=NativeDerivationLeafProviderSelection(
            source_node_id="component-source",
            supplier_ref=supplier,
            authority_entry_id=_entry().entry_id,
            connector_id=evidence.authorization.connector_id,
        ),
        generated_at=now,
    )
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "history.sqlite3")
    events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
    if with_action_history:
        sink = AcquisitionRouteLoopAuthoritySink(
            artifact_store=store, event_log=events, control_store=control
        )
        requested = sink.persist_phase(
            phase.model_copy(
                update={
                    "receipt_id": "component.requested",
                    "coarse_phase": "requested",
                    "receipt_phase": "requested",
                    "predecessor_receipt_ref": None,
                }
            )
        )
        phase = phase.model_copy(
            update={
                "predecessor_receipt_ref": requested.receipt_ref,
                "generated_at": now + timedelta(microseconds=1),
            }
        )
        executing_head = sink.persist_phase(phase)
        phase_ref = executing_head.receipt_ref
    else:
        phase_ref = (
            "sha256:"
            + hashlib.sha256(
                canon.to_canonical_bytes(phase.model_dump(mode="json"), _CANON)
            ).hexdigest()
        )
    route = growth.AcquisitionWorldGrowthRoute(
        tenant_id=_TENANT,
        cell_id=_CELL,
        run_id=phase.run_id,
        route_id=phase.route_id,
        design_problem_ref="sha256:" + "6" * 64,
        reentry_budget_usd=Decimal("0.50"),
        **{
            name: args[name]
            for name in (
                "epoch_id",
                "epoch_scope_identity",
                "authority_purpose",
                "valid_effect_coordinate_evidence_ref",
                "visibility_knowledge_cutoff_evidence_ref",
                "purpose_admission_cutoff_evidence_ref",
                "facet_source_refs",
            )
        },
    )
    bridge = growth.AcquisitionWorldGrowthBridge(
        config=growth.AcquisitionWorldGrowthConfig(routes=(route,)),
        repo_root=authority.repo_root,
        runtime_root=tmp_path / "world-growth",
        authority=authority,
        artifact_store=store,
        event_log=events,
        epoch_deployment=None,
    )
    scope = SimpleNamespace(
        tenant_id=_TENANT,
        cell_id=_CELL,
        run_id=phase.run_id,
        source_job_id=phase.source_job_id,
        route_id=phase.route_id,
        compiled_ref=phase.compiled_ref,
        cost_basis_hash=phase.cost_basis_hash,
        design_problem_ref=route.design_problem_ref,
        native_derivation_leaf_scope=object(),
    )
    attempt = growth.AcquisitionWorldGrowthAttempt(
        selection=route,
        binding_id="component-binding",
        target_variable="government.balance",
        evidence=evidence,
        owner_receipt_refs=tuple(
            str(ref)
            for ref in (
                evidence.raw_artifact_id,
                evidence.evidence_bundle_ref.artifact_id,
                evidence.data_snapshot_ref.artifact_id,
                evidence.normalized_data_artifact_id,
            )
        ),
        before=(),
        action_phase_ref=phase_ref,
    )
    attempt_ref = bridge._persist(
        scope,
        attempt.model_dump(mode="json"),
        growth._ATTEMPT_KIND,
        "AcquisitionWorldGrowthAttempt",
        "admission_pending",
        return_selected_profile=True,
    )
    deferral = growth.AcquisitionWorldGrowthDeferral(
        schema_version="AcquisitionWorldGrowthDeferral@1.1",
        attempt_ref=str(attempt_ref.artifact_id),
        negative_receipt=negative,
        action_phase_ref=phase_ref,
    )
    ref = bridge._persist(
        scope,
        deferral.model_dump(mode="json"),
        growth._DEFERRAL_KIND,
        "AcquisitionWorldGrowthDeferral",
        "admission_deferred",
        return_selected_profile=True,
    )
    pointer = bridge._growth_pointer(route)
    bridge._write_pointer(
        pointer.with_suffix(".attempt.json"),
        str(attempt_ref.artifact_id),
        selected_ref=attempt_ref,
    )
    bridge._write_pointer(
        pointer.with_suffix(".deferred.json"), str(ref.artifact_id), selected_ref=ref
    )
    paid_selection = None
    if with_action_history:
        terminal = sink.persist_terminal(
            AcquisitionRouteLoopReceipt.model_validate(
                {
                    **phase.model_dump(
                        include={
                            "tenant_id",
                            "cell_id",
                            "run_id",
                            "source_job_id",
                            "route_id",
                            "action_generation",
                            "job_id",
                            "compiled_ref",
                            "planner_report_hash",
                            "cost_basis_hash",
                            "decision_ref",
                            "owner_declared_profile_ref",
                            "native_leaf_provider_selection",
                        }
                    ),
                    "schema_version": "AcquisitionRouteLoopReceipt@1.2",
                    "receipt_id": "component.quarantined",
                    "terminal_outcome": "quarantined_no_growth",
                    "predecessor_receipt_ref": executing_head.receipt_ref,
                    "owner_receipt_refs": (str(ref.artifact_id),),
                    "generated_at": now + timedelta(microseconds=2),
                }
            )
        )
        paid_selection = NativePaidInputAdmissionSelection(
            original_action_job_id=phase.job_id,
            executing_phase_ref=artifacts.artifact_ref_for_manifest(
                store.get_manifest_by_profile(
                    executing_head.receipt_ref, executing_head.receipt_manifest_profile_sha256
                )
            ),
            terminal_ref=artifacts.artifact_ref_for_manifest(
                store.get_manifest_by_profile(
                    terminal.receipt_ref, terminal.receipt_manifest_profile_sha256
                )
            ),
            attempt_ref=attempt_ref,
            deferral_ref=ref,
            negative_receipt_ref=negative.receipt_ref,
            prepared_epoch_ref=negative.prepared_epoch_ref,
            owner_declared_profile_ref=configured_cost,
        )
    return SimpleNamespace(
        store=store,
        control=control,
        events=events,
        bridge=bridge,
        scope=scope,
        phase=phase,
        phase_ref=phase_ref,
        attempt=attempt,
        attempt_ref=attempt_ref,
        deferral=deferral,
        ref=ref,
        negative=negative,
        transport=transport,
        call_count=call_count,
        cost_scope=cost_scope,
        paid_selection=paid_selection,
    )


def test_paid_history_uses_one_exact_deferral_replay_and_reopens_each_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stock paid verifier consumes the verified bodies and exact selected refs."""
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        case = _negative_case(tmp_path, monkeypatch, with_action_history=True)
        reads = []
        verify_negative = growth.verify_acquisition_admission_negative

        def observe_negative(store, attempt, negative, *, expected_provider=None):
            verified = verify_negative(
                store, attempt, negative, expected_provider=expected_provider
            )
            reads.append((attempt, verified))
            return verified

        monkeypatch.setattr(growth, "verify_acquisition_admission_negative", observe_negative)

        def verify(selection):
            return growth.verify_native_paid_input_admission_selection(
                case.store,
                case.events,
                control_store=case.control,
                selection=selection,
                scope=case.cost_scope,
                provider=case.phase.native_leaf_provider_selection,
                route_id=case.phase.route_id,
                compiled_ref=case.phase.compiled_ref,
                planner_report_hash=case.phase.planner_report_hash,
                cost_basis_hash=case.phase.cost_basis_hash,
            )

        assert verify(case.paid_selection) == case.attempt
        assert reads == [(case.attempt, case.negative)]
        exact_view = SelectedArtifactRef.model_validate(case.attempt_ref.model_dump(mode="python"))
        selection_with_exact_view = NativePaidInputAdmissionSelection.model_validate(
            {**case.paid_selection.model_dump(mode="python"), "attempt_ref": exact_view}
        )
        assert selection_with_exact_view.attempt_ref is exact_view
        assert verify(selection_with_exact_view) == case.attempt
        foreign_view = case.attempt_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "f" * 64}
        )
        with pytest.raises(ValueError, match="native_paid_input_admission_paid_evidence_mismatch"):
            verify(case.paid_selection.model_copy(update={"attempt_ref": foreign_view}))

        prepared = case.negative.prepared_epoch_ref
        assert prepared is not None
        blob, _ = case.store._paths(prepared.artifact_id)
        held = blob.with_suffix(".held")
        blob.rename(held)
        try:
            with pytest.raises(
                FileNotFoundError, match=rf"^Artifact not found: {prepared.artifact_id.hex}$"
            ):
                verify(case.paid_selection)
        finally:
            held.rename(blob)
        assert verify(case.paid_selection) == case.attempt

        competitor = case.store.put_bytes(
            case.store.get_bytes(case.attempt_ref),
            artifacts.ArtifactWriteOptions(
                kind=case.attempt_ref.kind,
                media_type=case.attempt_ref.media_type,
                canon=artifacts.CanonInfo.from_spec(_CANON),
            ),
            return_selected_profile=True,
        )
        assert competitor.artifact_id == case.attempt_ref.artifact_id
        assert competitor.manifest_profile_sha256 != case.attempt_ref.manifest_profile_sha256
        with pytest.raises(ValueError, match="acquisition_negative_paid_attempt_not_unique"):
            verify(case.paid_selection)
        assert len(case.transport.calls) == case.call_count


def test_real_epoch_negative_replays_selected_owner_and_refuses_scope_grafts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The actual persisted service negative is consumed without another effect."""
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        case = _negative_case(tmp_path, monkeypatch)
        owner_refs = (str(case.ref.artifact_id),)
        kwargs = {
            "owner_receipt_refs": owner_refs,
            "executing": case.phase,
            "executing_ref": case.phase_ref,
        }
        assert (
            growth.resolve_native_admission_deferral_outcome(case.store, case.events, **kwargs)
            == case.ref
        )
        sink = AcquisitionRouteLoopAuthoritySink(
            artifact_store=case.store, event_log=case.events, control_store=case.control
        )
        assert sink._verified_current_action_outcome_ref(
            case.phase, case.phase_ref, owner_refs
        ) == str(case.ref.artifact_id)

        wrong_phase = "sha256:" + "f" * 64
        with pytest.raises(ValueError, match="acquisition_negative_paid_attempt_phase_mismatch"):
            growth.resolve_native_admission_deferral_outcome(
                case.store, case.events, **{**kwargs, "executing_ref": wrong_phase}
            )
        provider = case.phase.native_leaf_provider_selection.model_copy(
            update={"authority_entry_id": "acquisition-authority:sha256:" + "e" * 64}
        )
        with pytest.raises(ValueError, match="acquisition_deferred_admission_provider_mismatch"):
            growth.resolve_native_admission_deferral_outcome(
                case.store,
                case.events,
                **{
                    **kwargs,
                    "executing": case.phase.model_copy(
                        update={"native_leaf_provider_selection": provider}
                    ),
                },
            )

        unrelated = case.store.put_bytes(
            case.store.get_bytes(case.ref),
            artifacts.ArtifactWriteOptions(
                kind="tests.unrelated_default",
                media_type="application/json",
                canon=artifacts.CanonInfo.from_spec(_CANON),
            ),
            return_selected_profile=True,
        )
        assert unrelated.artifact_id == case.ref.artifact_id
        assert unrelated.manifest_profile_sha256 != case.ref.manifest_profile_sha256
        _blob, default_manifest = case.store._paths(case.ref.artifact_id)
        alternate_manifest = default_manifest.with_name(
            f"{str(unrelated.artifact_id).removeprefix('sha256:')}.view."
            f"{unrelated.manifest_profile_sha256.removeprefix('sha256:')}.manifest.json"
        )
        before = default_manifest.read_bytes()
        try:
            default_manifest.write_bytes(alternate_manifest.read_bytes())
            loaded_ref, loaded, _attempt = case.bridge._load_deferral(case.scope)
            assert loaded_ref == str(case.ref.artifact_id)
            assert loaded == case.deferral
            assert (
                growth.resolve_native_admission_deferral_outcome(case.store, case.events, **kwargs)
                == case.ref
            )
        finally:
            default_manifest.write_bytes(before)

        prepared = case.negative.prepared_epoch_ref
        assert prepared is not None
        prepared_blob, _ = case.store._paths(prepared.artifact_id)
        held_blob = prepared_blob.with_suffix(".held")
        prepared_blob.rename(held_blob)
        try:
            with pytest.raises(
                FileNotFoundError, match=rf"^Artifact not found: {prepared.artifact_id.hex}$"
            ):
                growth.resolve_native_admission_deferral_outcome(case.store, case.events, **kwargs)
        finally:
            held_blob.rename(prepared_blob)
        assert (
            growth.resolve_native_admission_deferral_outcome(case.store, case.events, **kwargs)
            == case.ref
        )

        # The same actually paid evidence may receive a later admission-only
        # refusal. Its explicit current phase must not be inferred from fetch.
        next_phase = case.phase.model_copy(
            update={
                "receipt_id": "component.second-executing",
                "job_id": "action-negative-component-second",
                "action_generation": 2,
            }
        )
        next_phase_ref = (
            "sha256:"
            + hashlib.sha256(
                canon.to_canonical_bytes(next_phase.model_dump(mode="json"), _CANON)
            ).hexdigest()
        )
        next_deferral = growth.AcquisitionWorldGrowthDeferral(
            schema_version="AcquisitionWorldGrowthDeferral@1.1",
            attempt_ref=case.deferral.attempt_ref,
            negative_receipt=case.negative,
            action_phase_ref=next_phase_ref,
        )
        next_ref = case.bridge._persist(
            case.scope,
            next_deferral.model_dump(mode="json"),
            growth._DEFERRAL_KIND,
            "AcquisitionWorldGrowthDeferral",
            "admission_deferred",
            return_selected_profile=True,
        )
        next_kwargs = {
            "owner_receipt_refs": (str(next_ref.artifact_id),),
            "executing": next_phase,
            "executing_ref": next_phase_ref,
        }
        assert (
            growth.resolve_native_admission_deferral_outcome(case.store, case.events, **next_kwargs)
            == next_ref
        )
        with pytest.raises(ValueError, match="acquisition_negative_paid_attempt_phase_mismatch"):
            growth.resolve_native_admission_deferral_outcome(
                case.store,
                case.events,
                **{**next_kwargs, "executing_ref": case.phase_ref},
            )

        legacy = growth.AcquisitionWorldGrowthDeferral(
            attempt_ref=case.deferral.attempt_ref, negative_receipt=case.negative
        )
        assert "action_phase_ref" not in legacy.model_dump(mode="json")
        assert canon.to_canonical_bytes(legacy.model_dump(mode="json"), _CANON) == (
            canon.to_canonical_bytes(
                {
                    "schema_version": "AcquisitionWorldGrowthDeferral@1.0",
                    "attempt_ref": case.deferral.attempt_ref,
                    "negative_receipt": case.negative.model_dump(mode="json"),
                },
                _CANON,
            )
        )
        legacy_ref = case.bridge._persist(
            case.scope,
            legacy.model_dump(mode="json"),
            growth._DEFERRAL_KIND,
            "AcquisitionWorldGrowthDeferral",
            "admission_deferred",
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match="acquisition_negative_owner_outcome_ambiguous"):
            growth.resolve_native_admission_deferral_outcome(
                case.store,
                case.events,
                **{
                    **kwargs,
                    "owner_receipt_refs": (
                        str(case.ref.artifact_id),
                        str(legacy_ref.artifact_id),
                    ),
                },
            )
        assert len(case.transport.calls) == case.call_count
        assert case.attempt.evidence.call_count == 1
