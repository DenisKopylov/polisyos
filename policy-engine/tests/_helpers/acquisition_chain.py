"""Live WDI port with actual native owners and explicitly fixture institutional acts."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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
from tests._helpers.acquisition_production import (
    _ATTEMPT_ID,
    _entry,
    _family_receipt,
    _resolver,
    _write_family_receipt,
    intercepted_wdi_transport,
)
from tests._helpers.controlled_candidate_profile import _CgfGenerationPort
from tests._helpers.semantic_epoch_native import sign_native_epoch_scenario

_SERVED_WDI_N4_RECORDING_ID = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"


def load_served_wdi_generation_recording(
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Select the captured N4 recording used by the served acquisition witness."""
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    generation_repo_root = repo_root or Path(__file__).resolve().parents[2]
    return next(
        item
        for item in n4_contract._load_recordings(generation_repo_root)
        if item.get("design_problem_id") == _SERVED_WDI_N4_RECORDING_ID
    )


def make_wdi_port_case(
    tmp_path,
    monkeypatch,
    *,
    control,
    closure,
    previous_case=None,
    candidate_world_refreshes=(),
    candidate_scenario_generation=False,
    candidate_generation_recording: dict[str, Any] | None = None,
    reentry_budget_usd: Decimal = Decimal("0.10"),
):
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
            reentry_budget_usd=reentry_budget_usd,
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
    bridge_repo_root = repo
    generation_repo_root = (
        Path(__file__).resolve().parents[2] if candidate_scenario_generation else repo
    )
    bridge = AcquisitionWorldGrowthBridge(
        config=AcquisitionWorldGrowthConfig(
            routes=(selected,),
            candidate_world_refreshes=tuple(candidate_world_refreshes),
        ),
        repo_root=bridge_repo_root,
        runtime_root=runtime_root,
        authority=authority,
        artifact_store=store,
        event_log=control._diagnostic_event_log,
        epoch_deployment=deployment,
        promotion_runtime=control._promotion_runtime,
        cycle_substrate_context_admission_owner=(control._cycle_substrate_context_admission_owner),
        control_store=control._control_store,
    )
    transport_calls = intercepted_wdi_transport(monkeypatch)
    # Only candidate generation is a fixture; every re-entry owner still runs.
    from polisyos.runtime.quality.generation_cycle import N4GenerationPort

    if candidate_scenario_generation:
        import copy

        from polisyos.pdc import gy_content_hash
        from polisyos.runtime.quality.design_generation import (
            generate_design_candidate_scenario_proposal_under_a,
        )
        from tools.quality.validation import (
            check_layer3_gy_design_generation_contract as n4_contract,
        )

        recording = (
            candidate_generation_recording
            if candidate_generation_recording is not None
            else load_served_wdi_generation_recording(generation_repo_root)
        )
        controlled = copy.deepcopy(recording)
        recording_model_id = str(recording["model_id"])
        responses = controlled.get("responses")
        if not isinstance(responses, list):
            raise ValueError("controlled_candidate_recording_responses_missing")
        for index in (4, 8):
            response = responses[index]
            if not isinstance(response, dict):
                raise ValueError("controlled_candidate_recording_response_invalid")
            raw = response.get("raw_response")
            if not isinstance(raw, str):
                raise ValueError("controlled_candidate_recording_body_missing")
            trinity = json.loads(raw)
            intervention = next(
                item
                for item in trinity["policy_spec"]["interventions"]
                if item.get("kind") == "procurement_shock_intensity"
            )
            intervention["kind"] = "budget_allocation_multiplier"
            intervention["params"] = {"multiplier": 2}
            intervention["notes"] = [
                "do.target=government.balance sign=increase "
                "outcome=global.tax_rate "
                "effect_path=government.balance,global.tax_rate"
            ]
            rewritten = json.dumps(trinity, sort_keys=True, separators=(",", ":"))
            response["raw_response"] = rewritten
            response["raw_response_hash"] = gy_content_hash(rewritten)
        recorded_client = n4_contract.RecordedGenerationReplayClient(controlled)

        async def fixture_candidates(port, problem, *, cycle_index):
            del cycle_index
            assert port._model_id == recording_model_id
            return await generate_design_candidate_scenario_proposal_under_a(
                problem,
                model_id=port._model_id,
                llm_client=recorded_client,
                repo_root=generation_repo_root,
                cycle_substrate_context=port._cycle_substrate_context,
            )
    else:
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
        artifact_store=store,
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
