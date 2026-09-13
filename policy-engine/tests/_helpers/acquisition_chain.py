"""Live WDI port with actual native owners and explicitly fixture institutional acts."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from polisyos.core import canon, contracts
from polisyos.data_forge import read_api
from polisyos.runtime.http.services.acquisition_surface_execution import (
    WorldBankWDIAcquisitionExecutionPort,
)
from polisyos.runtime.quality import semantic_epoch
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthConfig,
    AcquisitionWorldGrowthRoute,
)
from polisyos.runtime.quality.semantic_epoch_qualification import (
    build_semantic_epoch_native_deployment,
)
from polisyos.runtime.quality.semantic_epoch_store import FileSemanticEpochHistoryRepository
from tests._helpers.acquisition_epoch_production import production_admission_inputs
from tests._helpers.acquisition_production import intercepted_wdi_transport
from tests._helpers.semantic_epoch_native import sign_native_epoch_scenario
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority import (
    _entry,
    _resolver,
    _write_family_receipt,
)
from tests.unit.runtime.quality.test_live_acquisition_executor import _ATTEMPT_ID, _family_receipt


def make_wdi_port_case(tmp_path, monkeypatch, *, control, closure, previous_case=None):
    """Create the real port; external policy appointment follows a terminal refusal.

    No native producer is patched. The caller executes once, observes quarantine,
    appoints the exact persisted prepared basis, then starts a distinct action.
    A restarted fixture reuses external inputs and opens a fresh owner bridge.
    """
    store = control._artifact_store
    runtime_root = Path(control._cas_root)
    if previous_case is None:
        repo = tmp_path / "repo"
        entry = _entry()
        provision = _write_family_receipt(
            repo, entry_id=entry.entry_id, attempt_id=_ATTEMPT_ID, receipt=_family_receipt()
        )
        authority, _ = _resolver(repo, authority_entry=entry, live_harness_receipts=(provision,))
        registry = read_api.catalog.AcquisitionAuthorityRegistry.model_validate_json(
            authority.registry_path.read_bytes()
        )
        scope = hashlib.sha256(
            canon.to_canonical_bytes([closure.tenant_id, closure.cell_id])
        ).hexdigest()
        owner_root = runtime_root / "runtime/acquisition/world-growth" / scope
        args = production_admission_inputs(
            tmp_path / "owners",
            store=store,
            authority=authority,
            overlay_path=owner_root / "overlay.duckdb",
            epoch_history_root=owner_root / "epochs",
        )
        selected = AcquisitionWorldGrowthRoute(
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
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            route_id=closure.route_id,
            design_problem_ref=closure.design_problem_ref,
            reentry_budget_usd=Decimal("0.10"),
        )
        appointments = []
        deployment = None
    else:
        authority = previous_case.authority
        repo = authority.repo_root
        registry = read_api.catalog.AcquisitionAuthorityRegistry.model_validate_json(
            authority.registry_path.read_bytes()
        )
        args = {**previous_case.call_args, "artifact_store": store}
        selected = previous_case.selected
        appointments = previous_case.appointments
        deployment = (
            build_semantic_epoch_native_deployment(appointments[-1].config)
            if appointments
            else None
        )
    bridge = AcquisitionWorldGrowthBridge(
        config=AcquisitionWorldGrowthConfig(routes=(selected,)),
        repo_root=repo,
        runtime_root=runtime_root,
        authority=authority,
        artifact_store=store,
        event_log=control._diagnostic_event_log,
        epoch_deployment=deployment,
        promotion_runtime=control._promotion_runtime,
    )
    transport_calls = intercepted_wdi_transport(monkeypatch)
    # Only candidate generation is a fixture; every re-entry owner still runs.
    from polisyos.runtime.quality.generation_cycle import N4GenerationPort
    from tests.unit.runtime.quality.test_generation_cycle import _CgfGenerationPort

    candidates = _CgfGenerationPort(target_world_slots=("government.balance",))

    async def fixture_candidates(_port, problem, *, cycle_index):
        return await candidates(problem, cycle_index=cycle_index)

    monkeypatch.setattr(N4GenerationPort, "__call__", fixture_candidates)

    def appoint_native_policy():
        """Sign the already persisted negative's exact prepared basis, without activation."""
        _ref, deferral, _attempt = bridge._load_deferral(closure)
        negative = deferral.negative_receipt
        assert negative.failure_codes == ("policy_admission_missing",)
        ref = negative.prepared_epoch_ref
        statement = contracts.epoch.load_verified_epoch_statement(
            store=store, ref=ref, expected_kind="epoch.prepared"
        )
        prepared = semantic_epoch.PreparedSemanticEpoch(
            **statement,
            prepared_epoch_ref=ref,
            prepared_content_hash=semantic_epoch._model_hash(
                b"polisyos.epoch.prepared.v1\0", statement
            ),
        )
        history = FileSemanticEpochHistoryRepository(
            root=args["epoch_history_root"], artifacts=store
        )
        native = sign_native_epoch_scenario(
            SimpleNamespace(
                store=store, prepared=prepared, query=prepared.query, history=history, service=None
            ),
            tmp_path / "institution",
        )
        bridge.epoch_deployment = native.deployment
        appointments.append(native)
        return native

    port = WorldBankWDIAcquisitionExecutionPort(
        authority=authority,
        registry=registry,
        provision=authority.provision,
        provision_content_sha256=authority.provision_content_sha256,
        runtime_state_root=runtime_root,
        world_growth_bridge=bridge,
    )
    return SimpleNamespace(
        port=port,
        bridge=bridge,
        transport_calls=transport_calls,
        appointments=appointments,
        appoint_native_policy=appoint_native_policy,
        authority=authority,
        selected=selected,
        call_args=args,
    )
