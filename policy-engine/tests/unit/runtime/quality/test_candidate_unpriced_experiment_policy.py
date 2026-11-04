"""Selected candidate experiment policy with explicit unknown information value.

The compiled, port and payload parents are component fixtures; this test does
not establish a signed request, protected route, source rights, or fetch permit.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.http.services.control_registry_providers import (
    resolve_control_registry_providers,
)
from polisyos.runtime.quality import acquisition_planner as planner
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    POLICY_EVENT,
    POLICY_KIND,
    POLICY_PRODUCER,
    POLICY_SCHEMA,
    CandidateUnpricedAcquisitionPolicy,
    CandidateUnpricedExperimentPolicyTemplate,
    CandidateUnpricedPolicyBinding,
    _persist_owned_candidate_unpriced_policy,
    issue_candidate_unpriced_experiment_policy,
    list_current_candidate_unpriced_policy_bindings,
    persist_candidate_unpriced_policy,
    read_candidate_unpriced_policy,
    reconcile_candidate_unpriced_work,
    resolve_current_candidate_unpriced_policy,
    verify_candidate_unpriced_experiment_policy_intent,
)
from polisyos.runtime.quality.agent_action_authority import agent_action_content_hash
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from polisyos.runtime.quality.generation_cycle import (
    ValuePortObservation,
    _CandidateN5L1RoutingObservation,
    _grounding_unavailable,
)
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.quality.test_candidate_unpriced_policy import _component_policy, _parent
from tests.unit.runtime.quality.test_n7_descriptor_source_join import _compilation
from tests.unit.scientist.orchestration.engine.test_invocation_capacity_observation import _owner


class _PlannerReportRef(artifacts.ArtifactRef):
    """A semantic subtype with no additional selected-view fields."""


class _PlannerReportWithExtraMeaning(_PlannerReportRef):
    custody_note: str


def _selected_mixed_report(cas, scope):
    """Use the real selected V2 planner producer with component N4/N5 parents."""
    candidate_id = scope.candidate_id
    candidate_hash = scope.candidate_content_hash
    problem_ref = scope.design_problem_basis_ref
    grounding = _grounding_unavailable(
        candidate_id,
        issue_codes=("cgf_disposition_missing",),
        candidate_content_hash=candidate_hash,
        design_problem_ref=problem_ref,
        authority_level="research",
    )
    digest_payload = {
        "candidate_id": candidate_id,
        "issue_codes": ["cgf_disposition_missing"],
        "source": "grounding_unavailable",
    }
    assert grounding.report_ref == gy_content_hash(digest_payload)
    assert grounding.acquisition_requirement is not None
    gap = planner.l1_variable_availability_requirement_gap(
        candidate_id=candidate_id,
        candidate_content_hash=candidate_hash,
        design_problem_ref=problem_ref,
        authority_level="research",
        availability=L1VariableAvailability(
            variable_id="global.unemployment_rate",
            status="unavailable",
            dataset_count=0,
            metric_binding_count=0,
            observation_count=0,
            coverage_ref="fixture://declared-unavailable/unemployment",
        ),
    )
    n4 = _parent(cas, "runtime.quality.n4_candidate_scenario_source", "n4")
    context = _parent(cas, "runtime.quality.cycle_substrate_context_job", "context")
    n5_input = _parent(cas, "runtime.quality.candidate_simulation_n5_input", "input")
    execution = _parent(cas, "runtime.quality.candidate_simulation_execution", "execution")
    result = _parent(cas, "polisyos.runtime.joint_simulation_result", "result")
    value = ValuePortObservation(
        candidate_id=candidate_id,
        authority_blockers=("candidate_scenario_n5_only",),
        candidate_n5_l1_routing=_CandidateN5L1RoutingObservation(
            source_ref=n4,
            context_job_ref=context,
            n5_input_ref=n5_input,
            n5_execution_ref=execution,
            n5_result_ref=result,
            requirement_gap=gap,
        ),
    )
    source = planner._N7ConfiguredCandidatePortSource(
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
        run_id=scope.run_id,
        source_job_id=scope.source_job_id,
        source_generation_run_id="component-generation",
        cycle_index=scope.source_cycle_index,
        candidate_id=candidate_id,
        candidate_content_hash=candidate_hash,
        design_problem_basis_ref=problem_ref,
        n4_source_ref=n4,
        context_job_ref=context,
        n5_input_ref=n5_input,
        n5_execution_ref=execution,
        n5_result_ref=result,
        grounding_observation=grounding.model_dump(mode="json"),
        value_observation=value.model_dump(mode="json"),
        grounding_digest_payload=digest_payload,
        source_gap=gap,
        accompanying_requirement_gaps=(grounding.acquisition_requirement,),
    )
    port_ref = planner._n7_put_configured_candidate_port_source(cas, source)
    compilation = _compilation("labor.unemployment_rate", "total_labor_force")
    basis = planner.persist_and_verify_data_requirement_compilation_report(
        cas, compilation, expected_scenario_id=compilation.scenario_id
    )
    gaps = planner._n7_candidate_n5_l1_obligation_gaps(
        source_gap=gap,
        accompanying_requirement_gaps=source.accompanying_requirement_gaps,
        specs=compilation.specs,
        capability_resolutions=compilation.capability_requirement_resolutions,
    )
    report = planner.plan_evidence_acquisition(
        run_id=f"n7-cycle:{compilation.scenario_id}:{scope.source_cycle_index}",
        gaps=gaps,
        generated_at=datetime(2026, 11, 3, tzinfo=UTC),
        requirement_basis_binding=basis,
    )
    report = planner._n7_bind_configured_candidate_report(
        store=cas, report=report, port_source_ref=port_ref
    )
    report = planner.bind_acquisition_planner_report(
        report, planning_context_hash="sha256:" + "3" * 64
    )
    report_ref = planner.persist_and_verify_acquisition_planner_report(cas, report)
    selected = [
        row
        for row in report.acquisition_records
        if row.requirement_gap_ref == gap.requirement_gap_id
    ]
    assert len(selected) == 1
    return scope.model_copy(
        update={
            "planner_report_hash": agent_action_content_hash(report),
            "planner_report_ref": report_ref,
            "compiler_report_ref": basis.compiler_report_ref,
            "configured_port_source_ref": port_ref,
            "compiled_requirement_ref": selected[0].compiled_requirement_ref,
        }
    ), report


def test_selected_experiment_policy_preserves_v1_and_reopens_its_exact_v2_view(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configured V2 is a candidate declaration, with no inferred permit or VOI."""
    cas = artifacts.FileSystemCAS(tmp_path / "cas")
    base = _build_control_service(tmp_path / "control", artifact_store=cas)
    ledger, _, observer = _owner(tmp_path / "quota-ledger.json", total=2, protected=1)
    profile = observer.invocation_quota_profile
    assert profile is not None
    bound: ControlPlaneService | None = None
    try:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            scope, legacy, authorization = _component_policy(cas, profile)
            old_payload = legacy.model_dump(mode="json")
            assert "experiment_intent" not in old_payload
            assert "information_value" not in old_payload
            legacy_ref = persist_candidate_unpriced_policy(
                store=cas, event_log=base._diagnostic_event_log, policy=legacy
            )
            # The fixture's canonical V1 bytes were persisted by the same
            # owner before the V2 extension; this catches changed old bytes.
            assert str(legacy_ref.artifact_id) == (
                "sha256:df5a76a24c066721618074c159cc6623830e383b509d60226d4ec319d9deb1b0"
            )
            assert (
                read_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, ref=legacy_ref
                )
                == legacy
            )
            scope, report = _selected_mixed_report(cas, scope)
            # CAS canonical bytes contain a typed datetime; route hashes bind
            # the owner's validated JSON projection, a distinct hash layer.
            raw = artifacts.load_core_json_artifact(cas, scope.planner_report_ref)
            assert agent_action_content_hash(raw) != agent_action_content_hash(report)
            payload_ref = _parent(cas, "runtime.control_nl_job_payload", "request")
            configured_template = CandidateUnpricedExperimentPolicyTemplate(
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
                authority_entry_id="acquisition-authority:" + "a" * 64,
                authority_registry_sha256="sha256:" + "b" * 64,
                authority_provision_sha256="sha256:" + "c" * 64,
                attempt_id=authorization.attempt_id,
                max_http_response_bytes=authorization.budget.max_response_bytes,
                max_http_decompressed_bytes=authorization.budget.max_decompressed_bytes,
                max_http_timeout_seconds=authorization.budget.timeout_seconds,
                max_standard_n5_invocations=profile.total_units - profile.protected_units,
                max_metered_reentry_usd=Decimal("1.00"),
            )
            policy = issue_candidate_unpriced_experiment_policy(
                scope=scope,
                live_authorization=authorization,
                n5_quota_profile=profile,
                source_payload_ref=str(payload_ref.artifact_id),
                request_content_hash="sha256:" + "8" * 64,
                original_metered_budget_usd=Decimal("5.00"),
                limitations=(
                    *legacy.limitations,
                    "candidate_experiment_voi_not_established",
                ),
                configured_template=configured_template,
            )
            assert legacy.model_dump(mode="json") == old_payload
            assert policy.purpose == "bounded_candidate_experiment_voi_unknown"
            assert policy.information_value == "not_established"
            assert policy.monetary_cost == "not_established"
            assert policy.hard_usd_reservation is False
            assert policy.publication_authority is False
            event_id = "evt_candidate_unpriced_policy_" + policy.content_hash.removeprefix(
                "sha256:"
            )
            event_rows_before = base._diagnostic_event_log.list_events(event_id=event_id, limit=2)
            ledger_before = ledger.snapshot()
            with pytest.raises(
                ValueError, match="candidate_unpriced_template_issuer_not_established"
            ):
                persist_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, policy=policy
                )
            ref = _persist_owned_candidate_unpriced_policy(
                store=cas, event_log=base._diagnostic_event_log, policy=policy
            )
            persisted_event_rows = base._diagnostic_event_log.list_events(
                event_id=event_id, limit=2
            )
            repeated_ref = _persist_owned_candidate_unpriced_policy(
                store=cas, event_log=base._diagnostic_event_log, policy=policy
            )
            assert repeated_ref == ref
            assert len(event_rows_before) == 0
            assert len(persisted_event_rows) == 1
            assert base._diagnostic_event_log.list_events(event_id=event_id, limit=2) == (
                persisted_event_rows
            )
            assert ledger.snapshot() == ledger_before
            manifest = cas.get_manifest(ref)
            assert manifest.artifact_schema == artifacts.SchemaInfo(
                name=POLICY_SCHEMA, version="2.0"
            )
            assert (
                read_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, ref=ref
                )
                == policy
            )
            providers = replace(
                resolve_control_registry_providers(),
                candidate_unpriced_policy_bindings=(
                    CandidateUnpricedPolicyBinding(scope=scope, policy_ref=ref),
                ),
                candidate_unpriced_policy_templates=(configured_template,),
            )
            bound = ControlPlaneService(
                cas_root=tmp_path / "cas",
                core_runs_root=tmp_path / "control" / "runs",
                artifact_store=cas,
                control_store=base._control_store,
                registry_providers=providers,
                policy_resolver=base._policy_resolver,
            )
            assert bound is not None

            def current_bindings() -> tuple[CandidateUnpricedPolicyBinding, ...]:
                return list_current_candidate_unpriced_policy_bindings(
                    control_service=bound,
                    tenant_id=scope.tenant_id,
                    cell_id=scope.cell_id,
                    run_id=scope.run_id,
                    source_job_id=scope.source_job_id,
                    candidate_id=scope.candidate_id,
                )

            inventory_calls: list[artifacts.ArtifactID] = []
            original_inventory = cas.inventory_snapshot

            def track_inventory(*, artifact_id: artifacts.ArtifactID) -> Any:
                inventory_calls.append(artifact_id)
                return original_inventory(artifact_id=artifact_id)

            with monkeypatch.context() as patch:
                patch.setattr(cas, "inventory_snapshot", track_inventory)
                selected_bindings = current_bindings()
            assert selected_bindings == (
                CandidateUnpricedPolicyBinding(scope=scope, policy_ref=ref),
            )
            # The valid historical V1 event is decoded and self-hash checked,
            # but does not trigger a full CAS inventory; only the current V2
            # template candidate reaches selected-profile verification.
            assert inventory_calls == [ref.artifact_id]

            inventory_calls.clear()
            with monkeypatch.context() as patch:
                patch.setattr(cas, "inventory_snapshot", track_inventory)
                patch.setattr(cas, "get_bytes", lambda _artifact_id: b"corrupt")
                with pytest.raises(
                    ValueError,
                    match="candidate_unpriced_policy_event_payload_identity_mismatch",
                ):
                    current_bindings()
            assert inventory_calls == []

            source_rows = base._diagnostic_event_log.list_events(
                run_id=scope.run_id, job_id=scope.source_job_id, limit=500
            )
            source_event = next(
                row.event for row in source_rows if row.event.event_type == POLICY_EVENT
            )
            malformed_payload = b"{}"
            malformed_ref = "sha256:" + hashlib.sha256(malformed_payload).hexdigest()
            malformed_event = source_event.model_copy(
                update={"payload_ref": malformed_ref, "artifact_refs": (malformed_ref,)}
            )

            def malformed_event_rows(**_kwargs: object) -> list[SimpleNamespace]:
                return [SimpleNamespace(event=malformed_event)]

            inventory_calls.clear()
            with monkeypatch.context() as patch:
                patch.setattr(bound._diagnostic_event_log, "list_events", malformed_event_rows)
                patch.setattr(cas, "get_bytes", lambda _artifact_id: malformed_payload)
                patch.setattr(cas, "inventory_snapshot", track_inventory)
                with pytest.raises(ValueError):
                    current_bindings()
            assert inventory_calls == []

            # A hash-correct but noncanonical inactive payload still reaches
            # the old Core declared-profile refusal. The raw typed decoder
            # accepts the whitespace-only variation, so it cannot authorize
            # skipping the selected manifest reader.
            legacy_manifest = cas.get_manifest(legacy_ref)
            noncanonical_payload = b" \n" + cas.get_bytes(legacy_ref)
            # Preserve the legacy manifest's typed/schema/lineage companions;
            # do not rebind its authority to these changed bytes.
            noncanonical_ref = cas.put_bytes(
                noncanonical_payload,
                artifacts.ArtifactWriteOptions(
                    kind=POLICY_KIND,
                    media_type="application/json",
                    schema=legacy_manifest.artifact_schema,
                    producer=legacy_manifest.producer,
                    env=legacy_manifest.env,
                    inputs=legacy_manifest.inputs,
                    canon=legacy_manifest.canon,
                    governance=legacy_manifest.governance,
                    tenant_context=legacy_manifest.tenant_context,
                    same_input_closure=legacy_manifest.same_input_closure,
                    warnings=legacy_manifest.warnings,
                ),
                return_selected_profile=True,
            )
            assert str(noncanonical_ref.artifact_id) == (
                "sha256:" + hashlib.sha256(noncanonical_payload).hexdigest()
            )
            assert (
                CandidateUnpricedAcquisitionPolicy.model_validate(
                    canon.from_canonical_bytes(
                        noncanonical_payload,
                        version=canon.CanonSpec(forbid_floats=False).version,
                    )
                )
                == legacy
            )
            default_manifest = cas.get_manifest(noncanonical_ref.artifact_id)
            default_ref = artifacts.artifact_ref_for_manifest(default_manifest)
            assert default_ref == noncanonical_ref
            with pytest.raises(ValueError, match="canon_profile_payload_nonconformant"):
                artifacts.load_core_json_artifact(
                    cas, default_ref, raw_payload_bytes=noncanonical_payload
                )
            noncanonical_event = source_event.model_copy(
                update={
                    "payload_ref": str(noncanonical_ref.artifact_id),
                    "artifact_refs": (str(noncanonical_ref.artifact_id),),
                }
            )

            def noncanonical_event_rows(**_kwargs: object) -> list[SimpleNamespace]:
                return [SimpleNamespace(event=noncanonical_event)]

            core_reader_refusals: list[str] = []
            original_core_reader = artifacts.load_core_json_artifact

            def observe_core_reader(store: Any, selector: Any, **kwargs: Any) -> Any:
                try:
                    return original_core_reader(store, selector, **kwargs)
                except ValueError as exc:
                    if (
                        isinstance(selector, artifacts.ArtifactRef)
                        and selector.artifact_id == noncanonical_ref.artifact_id
                    ):
                        core_reader_refusals.append(str(exc))
                    raise

            inventory_calls.clear()
            with monkeypatch.context() as patch:
                patch.setattr(bound._diagnostic_event_log, "list_events", noncanonical_event_rows)
                patch.setattr(artifacts, "load_core_json_artifact", observe_core_reader)
                patch.setattr(cas, "inventory_snapshot", track_inventory)
                with pytest.raises(ValueError, match="canon_profile_payload_nonconformant"):
                    current_bindings()
            assert inventory_calls == [noncanonical_ref.artifact_id]
            assert len(core_reader_refusals) == 2
            assert all(
                "canon_profile_payload_nonconformant" in refusal for refusal in core_reader_refusals
            )
            assert current_bindings() == (
                CandidateUnpricedPolicyBinding(scope=scope, policy_ref=ref),
            )

            original_list_events = bound._diagnostic_event_log.list_events
            selection_query_count = 0

            def changed_event_rows(**kwargs: Any) -> list[Any]:
                nonlocal selection_query_count
                rows = original_list_events(**kwargs)
                if (
                    kwargs.get("run_id") == scope.run_id
                    and kwargs.get("job_id") == scope.source_job_id
                ):
                    selection_query_count += 1
                    if selection_query_count == 2:
                        return [*rows, rows[0]]
                return rows

            with monkeypatch.context() as patch:
                patch.setattr(bound._diagnostic_event_log, "list_events", changed_event_rows)
                with pytest.raises(ValueError, match="candidate_unpriced_policy_selection_changed"):
                    current_bindings()
            assert selection_query_count == 2

            def changed_provider_rows(**kwargs: Any) -> list[Any]:
                rows = original_list_events(**kwargs)
                if (
                    kwargs.get("run_id") == scope.run_id
                    and kwargs.get("job_id") == scope.source_job_id
                ):
                    bound._registry_providers = replace(providers)
                return rows

            with monkeypatch.context() as patch:
                patch.setattr(bound, "_registry_providers", providers)
                patch.setattr(bound._diagnostic_event_log, "list_events", changed_provider_rows)
                with pytest.raises(ValueError, match="candidate_unpriced_policy_selection_changed"):
                    current_bindings()
            assert resolve_current_candidate_unpriced_policy(
                control_service=bound, scope=scope
            ) == (
                ref,
                policy,
            )
            # Compare the actual writer-selected planner view by its complete
            # identity, including profile, rather than its Python ref class.
            selected_parent = scope.planner_report_ref
            typed_parent = _PlannerReportRef.model_validate(
                selected_parent.model_dump(mode="python")
            )
            typed_scope = scope.model_copy(update={"planner_report_ref": typed_parent})
            assert resolve_current_candidate_unpriced_policy(
                control_service=bound, scope=typed_scope
            ) == (ref, policy)
            extended = _PlannerReportWithExtraMeaning(
                **selected_parent.model_dump(mode="python"), custody_note="additional semantics"
            )
            with pytest.raises(
                ValueError, match="candidate_unpriced_policy_selected_source_invalid"
            ):
                type(scope).model_validate(
                    {**scope.model_dump(mode="python"), "planner_report_ref": extended}
                )
            with pytest.raises(ValueError, match="candidate_unpriced_policy_not_selected"):
                resolve_current_candidate_unpriced_policy(
                    control_service=bound,
                    scope=scope.model_copy(update={"planner_report_ref": extended}),
                )
            parent_manifest = cas.get_manifest(selected_parent)
            sibling_parent = cas.put_bytes(
                cas.get_bytes(selected_parent),
                artifacts.ArtifactWriteOptions(
                    kind=selected_parent.kind,
                    media_type=selected_parent.media_type,
                    schema=parent_manifest.artifact_schema,
                    producer=artifacts.ProducerInfo(component="foreign.test.planner", version="1"),
                    canon=parent_manifest.canon,
                    inputs=parent_manifest.inputs,
                    governance=parent_manifest.governance,
                    tenant_context=parent_manifest.tenant_context,
                ),
                return_selected_profile=True,
            )
            assert sibling_parent.artifact_id == selected_parent.artifact_id
            assert sibling_parent.manifest_profile_sha256 != selected_parent.manifest_profile_sha256
            with pytest.raises(ValueError, match="candidate_unpriced_policy_not_selected"):
                resolve_current_candidate_unpriced_policy(
                    control_service=bound,
                    scope=scope.model_copy(update={"planner_report_ref": sibling_parent}),
                )
            before = ledger.snapshot()
            with pytest.raises(
                ValueError, match="candidate_experiment_policy_intent_not_established"
            ):
                reconcile_candidate_unpriced_work(
                    control_service=bound,
                    scope=scope,
                    policy_ref=ref,
                    action_phase_ref="sha256:" + "9" * 64,
                    live_authorization=authorization,
                    budget_observer=observer,
                    budget_state=observer._state,
                )
            assert ledger.snapshot() == before
            # A configured declaration and existing payload bytes cannot replace
            # the completed signed source-job owner.
            closure = SimpleNamespace(
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
                run_id=scope.run_id,
                source_job_id=scope.source_job_id,
                source_payload_ref=str(payload_ref.artifact_id),
                capability_manifest_ref="sha256:" + "6" * 64,
            )
            with pytest.raises(ValueError, match="acquisition_source_budget_job_not_established"):
                verify_candidate_unpriced_experiment_policy_intent(
                    control_service=bound, closure=closure, scope=scope, policy_ref=ref
                )
            assert ledger.snapshot() == before

            # The original request/decision values are load-bearing: deleting or
            # changing one must not silently recreate a V1 or a valid V2.
            encoded = policy.model_dump(mode="json")
            for field in (
                "experiment_intent",
                "information_value",
                "source_payload_ref",
                "request_content_hash",
                "original_metered_budget_usd",
            ):
                altered = dict(encoded)
                altered.pop(field)
                with pytest.raises(ValueError):
                    CandidateUnpricedAcquisitionPolicy.model_validate(altered)
            altered = {**encoded, "purpose": "bounded_candidate_research"}
            with pytest.raises(ValueError):
                CandidateUnpricedAcquisitionPolicy.model_validate(altered)

            foreign = cas.put_bytes(
                cas.get_bytes(ref),
                artifacts.ArtifactWriteOptions(
                    kind=POLICY_KIND,
                    media_type="application/json",
                    schema=manifest.artifact_schema,
                    producer=artifacts.ProducerInfo(component="foreign.test.policy", version="1"),
                    canon=manifest.canon,
                    inputs=manifest.inputs,
                    governance=manifest.governance,
                    tenant_context=manifest.tenant_context,
                ),
                return_selected_profile=True,
            )
            assert foreign.artifact_id == ref.artifact_id
            assert foreign.manifest_profile_sha256 != ref.manifest_profile_sha256

            # A content-valid eligible blob cannot become a selected policy
            # without a valid selected manifest and the existing server binding.
            unbound_providers = replace(providers, candidate_unpriced_policy_bindings=())
            unbound = ControlPlaneService(
                cas_root=tmp_path / "cas",
                core_runs_root=tmp_path / "control" / "runs",
                artifact_store=cas,
                control_store=base._control_store,
                registry_providers=unbound_providers,
                policy_resolver=base._policy_resolver,
            )
            views = cas.inventory_snapshot(artifact_id=ref.artifact_id)
            eligible_manifest_paths = {
                cas._manifest_path_for_ref(
                    ref.artifact_id,
                    artifacts.artifact_manifest_profile_sha256(entry.manifest),
                )
                for entry in views.entries
                if entry.manifest.kind == POLICY_KIND
                and entry.manifest.producer
                == artifacts.ProducerInfo(component=POLICY_PRODUCER, version="1.0")
            }
            assert eligible_manifest_paths
            held_paths: list[tuple[Path, Path]] = []
            try:
                for eligible_path in eligible_manifest_paths:
                    held_path = eligible_path.with_name(eligible_path.name + ".held")
                    eligible_path.rename(held_path)
                    held_paths.append((held_path, eligible_path))
                with pytest.raises((FileNotFoundError, ValueError)):
                    resolve_current_candidate_unpriced_policy(control_service=unbound, scope=scope)
            finally:
                for held_path, eligible_path in held_paths:
                    held_path.rename(eligible_path)

            with pytest.raises(ValueError, match="candidate_unpriced_policy_owner_mismatch"):
                read_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, ref=foreign
                )
            with pytest.raises(
                ValueError, match="candidate_unpriced_policy_inventory_identity_mismatch"
            ):
                _persist_owned_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, policy=policy
                )
            missing = scope.compiler_report_ref
            manifest_path = cas._manifest_path_for_ref(
                missing.artifact_id, missing.manifest_profile_sha256
            )
            held = manifest_path.with_name(manifest_path.name + ".held")
            manifest_path.rename(held)
            try:
                cold = artifacts.FileSystemCAS.open_existing_read_only(cas.root)
                with pytest.raises((FileNotFoundError, ValueError)):
                    read_candidate_unpriced_policy(
                        store=cold, event_log=base._diagnostic_event_log, ref=ref
                    )
                with pytest.raises((FileNotFoundError, ValueError)):
                    resolve_current_candidate_unpriced_policy(control_service=bound, scope=scope)
            finally:
                held.rename(manifest_path)
            assert (
                read_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, ref=ref
                )
                == policy
            )

            duplicate = cas.put_bytes(
                cas.get_bytes(ref),
                artifacts.ArtifactWriteOptions(
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                    schema=manifest.artifact_schema,
                    producer=manifest.producer,
                    env=manifest.env,
                    inputs=manifest.inputs,
                    canon=manifest.canon,
                    governance=manifest.governance,
                    tenant_context=manifest.tenant_context,
                    same_input_closure=manifest.same_input_closure,
                    authority=manifest.authority,
                    warnings=[
                        *manifest.warnings,
                        artifacts.WarningRecord(
                            code="test_duplicate_manifest_profile",
                            msg="Exercise duplicate valid selected views without changing payload semantics.",
                        ),
                    ],
                ),
                return_selected_profile=True,
            )
            assert duplicate.artifact_id == ref.artifact_id
            assert duplicate.manifest_profile_sha256 != ref.manifest_profile_sha256
            assert (
                read_candidate_unpriced_policy(
                    store=cas,
                    event_log=base._diagnostic_event_log,
                    ref=duplicate,
                )
                == policy
            )
            with pytest.raises(ValueError, match="candidate_unpriced_policy_profile_not_unique"):
                current_bindings()
    finally:
        if bound is not None:
            bound._control_store.close()
        else:
            base._control_store.close()
