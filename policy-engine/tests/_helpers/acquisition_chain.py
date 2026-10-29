"""Live WDI port with actual native owners and explicitly fixture institutional acts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from polisyos.core import canon, contracts
from polisyos.core.artifacts.store import FileSystemCAS
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
from polisyos.runtime.quality.semantic_epoch_store import (
    FileSemanticEpochHistoryRepository,
)
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
from tests._helpers.semantic_epoch_native import (
    NativeEpochFixtureCustodian,
    sign_native_epoch_scenario,
)

_SERVED_WDI_N4_RECORDING_ID = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"
SERVED_WDI_FISCAL_SCOPE_SOURCE = (
    "For Ukraine (UKR) and a 2024 policy time, use 2024 data as of 2024-12-31. "
    "Assess a fiscal candidate in which a budget-allocation multiplier increases "
    "government.balance. The objective is to maximize the hypothetical global.tax_rate "
    "outcome; measure it for a fiscal review by Ukrainian analysts."
)
SERVED_WDI_CANDIDATE_ONLY_SOURCE = (
    "All proposals remain candidate-only until independent evidence supports any measured effect."
)
SERVED_WDI_FISCAL_REQUEST = f"{SERVED_WDI_FISCAL_SCOPE_SOURCE} {SERVED_WDI_CANDIDATE_ONLY_SOURCE}"


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


def controlled_served_wdi_generation_recording(
    recording: dict[str, Any], *, outcome_variable: str
) -> dict[str, Any]:
    """Build the exact content-identified candidate recording used by seed and re-entry."""
    import copy

    from polisyos.pdc import gy_content_hash
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    controlled = copy.deepcopy(recording)
    base_recording_id = str(recording.get("recording_id") or "recording")
    base_content_hash = str(recording.get("recording_content_hash") or "")
    responses = controlled.get("responses")
    if not isinstance(responses, list):
        raise ValueError("controlled_candidate_recording_responses_missing")
    selected_parent_hashes = {
        "sha256:5290085c97f3bbb3a6c612ce244a0ed21acadf74f8732a099397487068520e37",
        "sha256:d4a1bcdcbcd4ab0a8fd9a0aa78ad8e1d35fa05846f493b3a3b5adbaa0d06456e",
    }
    selected = [
        response
        for response in responses
        if isinstance(response, dict)
        and response.get("raw_response_hash") in selected_parent_hashes
    ]
    if len(selected) != len(selected_parent_hashes):
        raise ValueError("controlled_candidate_recording_parent_response_set_mismatch")
    for response in selected:
        if response.get("status") != "success" or response.get("role") != "formalizer":
            raise ValueError("controlled_candidate_recording_parent_contract_mismatch")
        response["raw_response"] = _controlled_wdi_trinity_response(
            response["raw_response"], outcome_variable=outcome_variable
        )
        response["raw_response_hash"] = gy_content_hash(response["raw_response"])

    identity_seed = gy_content_hash(
        {
            "base_recording_id": base_recording_id,
            "base_content_hash": base_content_hash,
            "response_hashes": [
                item.get("raw_response_hash") for item in responses if isinstance(item, dict)
            ],
            "outcome_variable": outcome_variable,
        }
    ).removeprefix("sha256:")[:20]
    fixture_id = f"synthetic_served_wdi_n4_{identity_seed}"
    controlled["fixture_id"] = fixture_id
    controlled["recording_id"] = fixture_id
    controlled["recording_source"] = "synthetic_controlled_overlay_of_recorded_capture"
    controlled["derived_from_recording_id"] = base_recording_id
    controlled["derived_from_content_hash"] = base_content_hash
    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    n4_contract._validate_recording_fixture(controlled)
    return controlled


def _controlled_wdi_trinity_response(raw: str, *, outcome_variable: str) -> str:
    """Extend the existing candidate overlay through one semantic transformation."""
    from polisyos.common.serialization import extract_llm_json_object

    trinity = extract_llm_json_object(raw)
    interventions = trinity["policy_spec"]["interventions"]
    selected = [item for item in interventions if item.get("kind") == "procurement_shock_intensity"]
    if len(selected) != 1:
        raise ValueError("controlled_candidate_recording_intervention_contract_mismatch")
    intervention = selected[0]
    intervention["kind"] = "budget_allocation_multiplier"
    intervention["params"] = {"multiplier": 2}
    intervention["notes"] = [
        "do.target=government.balance sign=increase "
        f"outcome={outcome_variable} "
        f"effect_path=government.balance,{outcome_variable}"
    ]
    return json.dumps(trinity, sort_keys=True, separators=(",", ":"))


def synthetic_served_wdi_provider_profile(
    recording: dict[str, Any], *, problem: Any, evidence_root: Path
):
    """Declare an error-free synthetic software-property profile from retained inputs.

    This is a new provider fixture. Its stage function reuses exact successful
    parent bodies; it does not replay historical timing, request order or bills.
    """
    from polisyos.core.llm.response import _usage_quantity
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref
    from tests._helpers.controlled_candidate_profile import SyntheticCandidateProviderProfile

    controlled = controlled_served_wdi_generation_recording(
        recording, outcome_variable=problem.outcome_of_interest.target_variable
    )
    parent_keys = {
        "draft": (
            "draft",
            "sha256:9911e5fdbaa75b9bc23bd4ef978b66c55b95b233058ff06cc97393e2083a9293",
        ),
        "drafter_multipass": (
            "drafter_multipass",
            "sha256:89a34fcd666092f58acbcd12c2b96322f80d50f59321e71aca203b0c0e4b602c",
        ),
        "drafter_consolidation": (
            "draft",
            "sha256:9911e5fdbaa75b9bc23bd4ef978b66c55b95b233058ff06cc97393e2083a9293",
        ),
        "formalizer": (
            "formalizer",
            "sha256:d4a1bcdcbcd4ab0a8fd9a0aa78ad8e1d35fa05846f493b3a3b5adbaa0d06456e",
        ),
        "critic": (
            "critic",
            "sha256:97f5f0145850de2269c1fd8232a98787a8d748ec887d9e4c12c7188955eb84e2",
        ),
    }
    rows = []
    for stage, (role, response_hash) in parent_keys.items():
        matches = [
            row
            for row in recording["responses"]
            if row.get("raw_response_hash") == response_hash and row.get("role") == role
        ]
        if len(matches) != 1:
            raise ValueError("synthetic_provider_parent_response_identity_unresolved")
        source = matches[0]
        body = source["raw_response"]
        if gy_content_hash(body) != response_hash:
            raise ValueError("synthetic_provider_parent_response_content_mismatch")
        if stage == "formalizer":
            body = _controlled_wdi_trinity_response(
                body, outcome_variable=problem.outcome_of_interest.target_variable
            )
        raw_usage = source.get("usage")
        if not isinstance(raw_usage, dict):
            raise ValueError("synthetic_provider_explicit_usage_values_missing")
        # Choose new declared test input values, never infer historical availability.
        selected_values = {
            key: raw_usage[key]
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            if key in raw_usage
        }
        quantity = _usage_quantity(selected_values)
        if quantity.status != "known":
            raise ValueError("synthetic_provider_explicit_usage_values_invalid")
        declared_usage = {
            "prompt_tokens": quantity.prompt_tokens,
            "completion_tokens": quantity.completion_tokens,
            "total_tokens": quantity.total_tokens,
            "usage_status": "known",
        }
        row = {
            "status": source["status"],
            "source_model_id": source["model_id"],
            "raw_response": body,
            "raw_response_hash": gy_content_hash(body),
            "usage": declared_usage,
            "legacy_counter_availability": "not_established",
            "usage_declaration": "new_synthetic_test_input_not_provider_measurement",
            "parent_role": role,
            "parent_response_hash": response_hash,
        }
        rows.append((stage, json.dumps(row, sort_keys=True, separators=(",", ":"))))
    return SyntheticCandidateProviderProfile(
        model_id=str(recording["model_id"]),
        profile_selection_ref=cycle_job_profile_selection_ref(problem),
        source_recording_id=str(recording["recording_id"]),
        source_recording_content_hash=str(recording["recording_content_hash"]),
        controlled_recording_content_hash=str(controlled["recording_content_hash"]),
        response_rows=tuple(rows),
        evidence_root=evidence_root,
    )


def controlled_served_wdi_problem(problem: Any, *, raw_request: str) -> Any:
    """Build the existing served WDI fixture's candidate-only global scalar problem.

    The only declared intervention is the captured budget-allocation multiplier
    targeting ``government.balance``; its selected fixture outcome is
    ``global.tax_rate``. Both are global scalar slots. This adapts the controlled
    test parent and does not assert a grounded or authoritative effect.
    """
    from polisyos.runtime.quality.design_problem import _QualifiedOutcomeOfInterestV3

    if (
        type(raw_request) is not str
        or SERVED_WDI_FISCAL_SCOPE_SOURCE not in raw_request
        or SERVED_WDI_CANDIDATE_ONLY_SOURCE not in raw_request
    ):
        raise ValueError("served_wdi_fiscal_fixture_request_scope_mismatch")
    model_dump = getattr(problem, "model_dump", None)
    if not callable(model_dump):
        raise TypeError("served_wdi_fiscal_fixture_problem_untyped")
    payload = model_dump(mode="json")
    if not isinstance(payload, dict):
        raise TypeError("served_wdi_fiscal_fixture_problem_untyped")
    payload["schema_version"] = "policyos.runtime.design_problem.v3"
    payload["problem_statement"] = (
        "Assess a candidate-only fiscal scenario for Ukraine using 2024 data: "
        "test a government-balance budget multiplier against the global tax-rate outcome."
    )
    payload["domain"] = "fiscal"
    payload["nl_provenance"].update(
        {"raw_request": raw_request, "source_surface": "runtime.control.nl_request"}
    )
    payload["jurisdiction_time"].update(
        {
            "region": "UKR",
            "valid_time": "2024",
            "as_of": "2024-12-31",
            "policy_time": "2024",
            "data_time": "2024",
        }
    )
    payload["objectives"][0].update(
        {
            "objective_id": "tax_rate",
            "description": "Maximize the hypothetical global tax-rate outcome for fiscal review.",
            "metric_id": "tax_rate",
            "direction": "maximize",
        }
    )
    payload["constraints"] = [
        {
            "constraint_id": "fiscal_request_scope",
            "description": (
                "Keep the candidate within the requested Ukraine 2024 fiscal, "
                "government-balance, and global-tax-rate scope."
            ),
            "hard": True,
            "admissibility_basis": "request_text",
            "source_text": SERVED_WDI_FISCAL_SCOPE_SOURCE,
        },
        {
            "constraint_id": "no_authority_without_a",
            "description": "N4 cannot promote or certify generated policy candidates.",
            "hard": True,
            "admissibility_basis": "request_text",
            "source_text": SERVED_WDI_CANDIDATE_ONLY_SOURCE,
        },
    ]
    payload["stakeholders"] = [
        {
            "stakeholder_id": "fiscal_analysts",
            "name": "Ukrainian fiscal analysts",
            "role": "reviewer",
        }
    ]
    payload["outcome_of_interest"].update(
        {
            "target_variable": "global.tax_rate",
            "metric_id": "tax_rate",
            "estimand": (
                "Hypothetical effect of the government-balance multiplier on the global tax rate."
            ),
            "direction": "maximize",
        }
    )
    payload["candidate_lever_space"] = {
        "allowed_operator_kinds": ["budget_allocation_multiplier"],
        "candidate_levers": [
            {
                "lever_id": "fiscal_budget_multiplier",
                "operator_kind": "budget_allocation_multiplier",
                "instrument": "Budget allocation multiplier",
                "target_slot": "government.balance",
            }
        ],
    }
    result = type(problem).model_validate(payload)
    if (
        type(result.outcome_of_interest) is not _QualifiedOutcomeOfInterestV3
        or result.nl_provenance.raw_request != raw_request
        or result.nl_provenance.source_surface != "runtime.control.nl_request"
    ):
        raise ValueError("served_wdi_fiscal_fixture_problem_binding_mismatch")
    return result


def _retained_native_epoch_custodian(
    appointments: Sequence[object], *, store: FileSystemCAS
) -> NativeEpochFixtureCustodian | None:
    """Return the latest appointment's custodian only for this exact CAS context."""
    store_root = store.root.resolve()
    for appointment in reversed(appointments):
        custodian = getattr(appointment, "custodian", None)
        if (
            isinstance(custodian, NativeEpochFixtureCustodian)
            and custodian.store is store
            and custodian.store.root.resolve() == store_root
        ):
            return custodian
    return None


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
    candidate_provider_gateway=None,
    reentry_budget_usd: Decimal = Decimal("0.10"),
    fixture_epoch_id: int | None = None,
    fixture_attempt_ids: tuple[str, ...] = (_ATTEMPT_ID,),
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
        if not fixture_attempt_ids or len(set(fixture_attempt_ids)) != len(fixture_attempt_ids):
            raise ValueError("fixture attempts must be distinct and nonempty")
        provisions = tuple(
            _write_family_receipt(
                repo,
                entry_id=entry.entry_id,
                attempt_id=attempt_id,
                receipt=_family_receipt(attempt_id=attempt_id),
                receipt_path=(
                    "evidence/worldbank-wdi-live-harness.json"
                    if index == 0
                    else f"evidence/worldbank-wdi-live-harness-{index}.json"
                ),
            )
            for index, attempt_id in enumerate(fixture_attempt_ids)
        )
        authority, _ = _resolver(repo, authority_entry=entry, live_harness_receipts=provisions)
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
        if fixture_epoch_id is not None:
            args["epoch_id"] = fixture_epoch_id
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
        if fixture_epoch_id is not None:
            args["epoch_id"] = fixture_epoch_id
            selected = AcquisitionWorldGrowthRoute.model_validate(
                {**selected.model_dump(mode="python"), "epoch_id": fixture_epoch_id}
            )
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
        action_head_sink=control.acquisition_route_sink,
        source_control_service=control,
    )
    transport_calls = intercepted_wdi_transport(monkeypatch)
    # Only candidate generation is a fixture; every re-entry owner still runs.
    from polisyos.runtime.quality.generation_cycle import N4GenerationPort

    if candidate_scenario_generation and candidate_provider_gateway is not None:
        original_generation_port = N4GenerationPort.__call__

        async def fixture_candidates(port, problem, *, cycle_index):
            candidate_provider_gateway.admit_compiled_problem(problem)
            return await original_generation_port(port, problem, cycle_index=cycle_index)

    elif candidate_scenario_generation:
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
        recording_model_id = str(recording["model_id"])
        controlled = controlled_served_wdi_generation_recording(
            recording,
            outcome_variable=closure.design_problem.outcome_of_interest.target_variable,
        )
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
        custodian = _retained_native_epoch_custodian(appointments, store=store)
        native = sign_native_epoch_scenario(
            SimpleNamespace(
                store=store,
                prepared=prepared,
                query=prepared.query,
                history=history,
                service=None,
            ),
            tmp_path / "institution",
            custodian=custodian,
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


def begin_current_wdi_action(control, closure, *, job_id: str):
    """Persist requested and executing heads for a direct-owner witness."""

    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
    )

    sink = control.acquisition_route_sink
    action_generation = sink.resolve_action_generation(
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        source_job_id=closure.source_job_id,
        route_id=closure.route_id,
        job_id=job_id,
    )
    requested = AcquisitionActionService._phase_receipt(
        action_generation=action_generation,
        closure=closure,
        job_id=job_id,
        decision_ref=closure.route_id,
        receipt_phase="requested",
        predecessor_receipt_ref=None,
        owner_receipt_refs=(),
    )
    requested_head = sink.persist_phase(requested)
    executing = AcquisitionActionService._phase_receipt(
        action_generation=action_generation,
        closure=closure,
        job_id=job_id,
        decision_ref=closure.route_id,
        receipt_phase="executing",
        predecessor_receipt_ref=requested_head.receipt_ref,
        owner_receipt_refs=(),
    )
    executing_head = sink.persist_phase(executing)
    return SimpleNamespace(
        action_generation=action_generation,
        job_id=job_id,
        requested_head=requested_head,
        executing_head=executing_head,
    )


def select_current_wdi_action_outcome(control, action, result):
    """Commit the exact owner CAS as the current ActionHead outcome."""

    return control.acquisition_route_sink.persist_action_outcome_selection(
        action.executing_head.receipt_ref, result.owner_receipt_refs
    )
