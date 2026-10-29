"""Proposed B161 source-binding oracle; native completion is a separate test.

No test function is called as a helper. Each case receives its own runtime, CAS,
request and monkeypatch lifetime. Fixture-generated source is candidate evidence.
"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

pytest_plugins = ("tests._helpers.runtime_http",)


@pytest.fixture
def admitted_case(
    runtime_api_env: dict[str, Any],
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Persist a source and selected obligation using the existing owner fixture."""
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.scientist.methods.search.uncertainty import (
        load_search_uncertainty_basis_v2,
        load_search_uncertainty_task_binding,
    )
    from tests._helpers.runtime_http import _record_fixture_owner
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )
    from tests.unit.runtime.http.test_search_hte_first_assessment_outbox import (
        _publish_complete_search_task,
        _put_profile_bound_v2_hte_source,
    )

    if getattr(request, "param", None) == "zero-outcome":
        # Modify the fixture's underlying source rows before the real source
        # projection, profile and method input are produced; no result is mocked.
        from tests._helpers import semantic_epoch_native

        original_projection = semantic_epoch_native.make_native_multivariable_active_projections

        def zero_source(*args, **kwargs):
            kwargs["source_rows"] = [dict(row, outcome=0.0) for row in kwargs["source_rows"]]
            return original_projection(*args, **kwargs)

        monkeypatch.setattr(
            semantic_epoch_native, "make_native_multivariable_active_projections", zero_source
        )
    env = runtime_api_env
    tenant = env["tenant_a"]
    client, cell, provider = _build_secure_client(
        env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=True,
    )
    with closing(client):
        service = env["app"].state._control_service
        assert service is not None
        client.app.state.runtime_container.control_service = service
        client.app.state._control_service = service
        token = _fixture_bearer("s1-independent-oracle")
        provider.put_claim(
            token,
            _claims(
                tenant_id=tenant,
                cell_id=cell.cell_id,
                jti="s1-independent-oracle",
                roles=frozenset({PolicyOSRole.ANALYST}),
            ),
        )
        with tenant_scope(None, tenant_id=tenant, cell_id=cell.cell_id):
            source, assignment, unit = _put_profile_bound_v2_hte_source(
                service._artifact_store,
                tenant_id=tenant,
                cell_id=cell.cell_id,
                tmp_path=tmp_path,
                run_id="s1-oracle",
            )
            _record_fixture_owner(
                service._artifact_store, source, tenant_id=tenant, cell_id=cell.cell_id
            )
            store = service._require_search_uncertainty_store()
            state, ticket, binding_ref = _publish_complete_search_task(
                store=store,
                service=service,
                source_ref=source,
                tenant_id=tenant,
                cell_id=cell.cell_id,
                run_id="s1-oracle",
                source_assignment_ref=assignment,
                unit_scope_ref=unit,
            )
            binding = load_search_uncertainty_task_binding(store, binding_ref)
            basis = load_search_uncertainty_basis_v2(store, binding.basis_ref)
        yield {
            "tenant": tenant,
            "cell": cell.cell_id,
            "client": client,
            "service": service,
            "store": store,
            "source": source,
            "assignment": assignment,
            "unit": unit,
            "ticket": ticket,
            "binding_ref": binding_ref,
            "binding": binding,
            "basis": basis,
            "headers": {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant},
        }


def _fresh_owner(c):
    """Use the real historical attempt and source verifiers for every read."""
    from polisyos.runtime.quality.hte_source_projection import verify_hte_source_projection_join
    from polisyos.scientist.methods.search.uncertainty import SearchUncertaintyTicketState

    service = c["service"]
    return SearchUncertaintyTicketState(
        c["store"],
        completion_owner=service,
        owned_attempt_association_resolver=service.resolve_owned_attempt_anchor_association,
        owned_historical_attempt_association_resolver=service.resolve_owned_attempt_anchor_association,
        source_projection_verifier=verify_hte_source_projection_join,
    )


def _fresh_funnel(c):
    """Use the same genuine Runtime and source verifiers on consumer reads."""
    from polisyos.runtime.quality.hte_source_projection import verify_hte_source_projection_join
    from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator

    resolver = c["service"].resolve_owned_attempt_anchor_association
    return FunnelOrchestrator(
        [],
        search_uncertainty_attempt_association_resolver=resolver,
        search_uncertainty_historical_attempt_association_resolver=resolver,
        search_uncertainty_source_projection_verifier=verify_hte_source_projection_join,
    )


def _inject_persisted_foreign_unknown(c, *, replace_selected=False, remove_selected=False):
    """Adversarial fixture write; persisted bytes do not claim a real risk owner."""
    from polisyos.scientist.methods.search.uncertainty import persist_search_uncertainty_v2

    state = _fresh_owner(c)
    snapshot = state.read_current_snapshot(c["ticket"])
    assert snapshot is not None and snapshot.resolved_projection is not None
    selected = snapshot.resolved_projection.selected_unassessed_observations[0]
    foreign_basis = selected.basis.model_copy(
        update={"obligation_id": "foreign-fixture-obligation"}
    )
    foreign_basis_ref = persist_search_uncertainty_v2(c["store"], foreign_basis)
    foreign = selected.observation.model_copy(
        update={"basis_ref": foreign_basis_ref, "obligation_id": "foreign-fixture-obligation"}
    )
    foreign_ref = persist_search_uncertainty_v2(c["store"], foreign)
    projection = snapshot.projection
    assert projection is not None
    if remove_selected:
        unassessed, unknown = (), ()
    elif replace_selected:
        unassessed, unknown = (foreign_ref,), ("foreign-fixture-obligation",)
    else:
        unassessed = (*projection.unassessed_observation_refs, foreign_ref)
        unknown = tuple(
            sorted((*projection.active_unknown_obligation_ids, "foreign-fixture-obligation"))
        )
    injected = projection.model_copy(
        update={
            "unassessed_observation_refs": unassessed,
            "active_unknown_obligation_ids": unknown,
            "historical_observation_refs": (*projection.historical_observation_refs, foreign_ref),
        }
    )
    with state._locked(c["ticket"]):
        row = state._read_row(c["ticket"])
        assert row is not None
        state._publish_locked(row, expected_generation=row.ticket_generation, projection=injected)
    return state.read_current_snapshot(c["ticket"])


def test_real_content_join_counterfactuals_and_fresh_unassessed_consumer(admitted_case):
    """Changing one selected relation cannot manufacture a source-verified join."""
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.hte_source_projection import verify_hte_source_projection_join
    from polisyos.scientist.methods.search.uncertainty import (
        _resolve_hte_source_projection_join,
    )

    c = admitted_case
    limits = CoreJsonReadLimits(
        max_bytes=8_388_608, max_depth=64, max_elements=200_000, max_manifest_bytes=65_536
    )
    basis = c["basis"]
    req = c["binding"].request_projection

    def resolve(selected_basis, selected_request, source):
        return _resolve_hte_source_projection_join(
            verifier=verify_hte_source_projection_join,
            store=c["store"],
            selected_method_input_ref=source,
            basis=selected_basis,
            request_projection=selected_request,
            limits=limits,
        )

    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        joined, reason = resolve(basis, req, c["source"])
        assert reason is None and joined is not None
        assert joined.assignment_ref == c["assignment"]
        assert joined.outcome_profile_ref == c["unit"]
        assert joined.role_mapping_status == "consumer_asserted"
        assert joined.semantic_alignment_status == "not_established"
        assert joined.source_time_status == "not_established"

        # Identical declared source and unit markers, but no selected assignment.
        without_assignment = basis.model_copy(
            update={
                "selected_state_input_refs": tuple(
                    x
                    for x in basis.selected_state_input_refs
                    if x.role_path != "source_variable_assignment"
                )
            }
        )
        # Distinct profile selection with identical artifact identity is not the same unit.
        wrong_unit = c["unit"].model_copy(update={"manifest_profile_sha256": "sha256:" + "e" * 64})
        wrong_source = c["source"].model_copy(
            update={"manifest_profile_sha256": "sha256:" + "d" * 64}
        )
        swapped = req.model_copy(
            update={
                "outcome_variable_id": req.treatment_variable_id,
                "treatment_variable_id": req.outcome_variable_id,
            }
        )
        for label, changed_basis, changed_req, changed_source in (
            ("assignment", without_assignment, req, c["source"]),
            ("unit", basis.model_copy(update={"unit_scope_ref": wrong_unit}), req, c["source"]),
            ("source", basis, req, wrong_source),
            ("roles", basis, swapped, c["source"]),
        ):
            result, refusal = resolve(changed_basis, changed_req, changed_source)
            assert result is None, label
            assert refusal is not None, label

        # Fresh consumer does not promote a verified join into an assessment.
        snapshot = _fresh_owner(c).read_current_snapshot(c["ticket"])
        assert snapshot is not None and snapshot.projection is not None
        assert snapshot.resolved_projection is not None
        assert snapshot.resolved_projection.selected_unassessed_observations
        assert not snapshot.resolved_projection.current_obligations
        assert snapshot.projection.live_currentness_status == "not_established"


def test_post_binds_owned_request_before_worker_and_retains_unknown(admitted_case):
    """A real POST persists its selected request; no interval is invented here."""
    from polisyos.core.contracts.runtime import ObservationalRunIntent
    from polisyos.core.security.tenant_context import tenant_scope
    from tests._helpers.control_worker import stop_embedded_control_worker
    from tests.unit.runtime.http.test_search_hte_first_assessment_outbox import _request_payload

    c = admitted_case
    stop_embedded_control_worker(c["service"])
    response = c["client"].post(
        "/api/v1/control/runs",
        json=_request_payload(c["source"], c["binding_ref"]),
        headers=c["headers"],
    )
    assert response.status_code == 200, response.text
    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        service = c["service"]
        job = service._control_store.get_job(response.json()["job_id"])
        assert job is not None
        payload = service._load_payload_ref(
            service._require_control_job_payload_ref(job),
            kind="runtime.control_job_payload.workflow_run",
        )
        _, _, _, intent = service._read_validated_observational_method_job_intent(
            job=job, payload=payload
        )
        assert type(intent) is ObservationalRunIntent
        assert intent.search_binding_admission is not None
        assert intent.search_binding_admission.binding_ref == c["binding_ref"]
        assert intent.search_binding_admission.selected_method_input_ref == c["source"]
        assert intent.owned_hte_request_context is not None
        fresh = _fresh_owner(c).read_current_snapshot(c["ticket"])
        assert fresh is not None and fresh.resolved_projection is not None
        assert fresh.resolved_projection.selected_unassessed_observations
        assert not fresh.resolved_projection.current_obligations


def test_native_owned_attempt_projection_contests_without_favorable_winner(admitted_case):
    """Only genuine backend execution can establish the interval-bearing path."""
    pytest.importorskip("econml", reason="native HTE backend unavailable")
    from polisyos.core.security.tenant_context import tenant_scope
    from tests._helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from tests.unit.runtime.http.test_search_hte_first_assessment_outbox import _request_payload

    c = admitted_case
    service = c["service"]
    stop_embedded_control_worker(service)
    jobs = []
    for _ in range(2):
        response = c["client"].post(
            "/api/v1/control/runs",
            json=_request_payload(c["source"], c["binding_ref"]),
            headers=c["headers"],
        )
        assert response.status_code == 200, response.text
        jobs.append(response.json()["job_id"])
    assert jobs[0] != jobs[1]
    from polisyos.scientist.methods.search.funnel.types import FunnelStageResult, FunnelTicket

    def consumer_status():
        ticket = FunnelTicket(
            ticket_id="status-view",
            candidate_hash="fixture",
            candidate={},
            context={"store": c["store"]},
            search_uncertainty_ticket_id=c["ticket"],
            stage_results={
                0: FunnelStageResult(
                    policy_candidate={},
                    objective_value=None,
                    is_promising=True,
                    stage_name="fixture",
                    fidelity_level=0,
                )
            },
        )
        funnel = _fresh_funnel(c)
        with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
            result = funnel.get_outcome(ticket)
        assert result.final_result is not None
        from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_reporting import (
            _serialize_funnel_outcome,
        )

        reported = _serialize_funnel_outcome(result)
        status = result.final_result.feedback["uncertainty_current_status"]
        assert reported["stage_results"]["0"]["feedback"]["uncertainty_current_status"] == status
        assert reported["search_uncertainty_current_read"] is not None
        return status

    assert consumer_status() == "unassessed"
    snapshots = []
    native_outcomes = []
    for job_id in jobs:
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=job_id,
            )
            == job_id
        )
        job = service._control_store.get_job(job_id)
        assert job is not None and job.state == "completed", getattr(job, "error_message", None)
        event = service._control_store.get_job_terminal_source_event_record(job_id)
        assert event.event_type == "job_completed"
        from polisyos.core.artifacts import ensure_ir_artifact_store
        from polisyos.ir.analytics.hte import load_hte_outcome
        from polisyos.ir.registry.refs import HTEOutcomeRef

        selection = event.payload["method_execution_selection"]
        outcome_ref = HTEOutcomeRef.model_validate(selection["hte_outcome_ref"], strict=True)
        with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
            native_outcomes.append(
                load_hte_outcome(
                    ensure_ir_artifact_store(service._artifact_store), outcome_ref
                ).root
            )
        service.reconcile_pending_search_hte_completion_events()
        delivery = service._control_store.get_search_hte_completion_outbox_event(
            job_id=job_id, completed_event_id=event.event_id
        )
        assert delivery is not None and delivery.state == "published"
        with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
            snapshot = _fresh_owner(c).read_current_snapshot(c["ticket"])
        assert snapshot is not None and snapshot.resolved_projection is not None
        snapshots.append(snapshot)
        assert consumer_status() == ("assessed" if len(snapshots) == 1 else "contested")

    first = snapshots[0].resolved_projection.current_obligations[0]
    assert first.selection.status == "assessed" and len(first.successors) == 1
    measured = first.successors[0].observation
    assert measured.job_id == jobs[0] and measured.owned_attempt_anchor_ref is not None
    assert measured.outcome_kind == "interval_estimate"
    assert (
        measured.theta != 0
        and measured.lower_bound is not None
        and measured.upper_bound is not None
    )
    native = native_outcomes[0]
    assert native.kind == "interval_estimate"
    assert measured.theta == native.point_estimate.value
    assert measured.lower_bound == native.lower_bound and measured.upper_bound == native.upper_bound
    score = measured.routing_score
    assert score.status == "available"
    expected = min(1.0, (measured.upper_bound - measured.lower_bound) / (2 * abs(measured.theta)))
    assert score.score == pytest.approx(expected)
    assert "source_semantic_alignment_not_established" in measured.limitations
    second = snapshots[1].resolved_projection.current_obligations[0]
    assert second.selection.status == "contested" and len(second.successors) == 2
    assert {item.observation.job_id for item in second.successors} == set(jobs)
    assert snapshots[1].projection.live_currentness_status == "not_established"

    # Actual admitted objects, counterfactually changed on only one edge; no
    # claimed new CAS artifact or independently issued owner provenance.
    from polisyos.scientist.methods.search.uncertainty import _verify_first_assessment_edge

    successor = first.successors[0]
    predecessor = first.predecessor
    for field in ("basis_ref", "owned_attempt_anchor_ref"):
        original = getattr(successor.observation, field)
        foreign = original.model_copy(update={"manifest_profile_sha256": "sha256:" + "c" * 64})
        altered = successor.observation.model_copy(update={field: foreign})
        with pytest.raises(ValueError, match="first-assessment relation refs disagree"):
            _verify_first_assessment_edge(
                ticket_id=c["ticket"],
                predecessor_ref=predecessor.observation_ref,
                predecessor=predecessor.observation,
                successor_ref=successor.observation_ref,
                successor=altered,
                refinement_ref=successor.refinement_ref,
                refinement=successor.refinement,
                expected_generation=snapshots[0].ticket_generation,
            )

    # Use real persisted alternative basis bytes; a changed subject or quantity
    # cannot become the earlier placeholder's same-basis successor.
    from polisyos.scientist.methods.search.uncertainty import persist_search_uncertainty_v2

    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        for changed_field, foreign_ref in (
            ("subject_ref", first.basis.quantity_ref),
            ("quantity_ref", first.basis.outcome_ref),
        ):
            changed_basis = first.basis.model_copy(update={changed_field: foreign_ref})
            changed_basis_ref = persist_search_uncertainty_v2(c["store"], changed_basis)
            altered = successor.observation.model_copy(update={"basis_ref": changed_basis_ref})
            with pytest.raises(ValueError, match="first-assessment relation refs disagree"):
                _verify_first_assessment_edge(
                    ticket_id=c["ticket"],
                    predecessor_ref=predecessor.observation_ref,
                    predecessor=predecessor.observation,
                    successor_ref=successor.observation_ref,
                    successor=altered,
                    refinement_ref=successor.refinement_ref,
                    refinement=successor.refinement,
                    expected_generation=snapshots[0].ticket_generation,
                )

    # Persist a coherent forged successor/refinement pair, while claiming the
    # other real job with this successor's anchor and immutable completion.
    from polisyos.scientist.methods.search.uncertainty import (
        SearchUncertaintyAdmissionError,
        persist_search_uncertainty_v2,
    )

    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        forged = successor.observation.model_copy(update={"job_id": jobs[1]})
        forged_ref = persist_search_uncertainty_v2(c["store"], forged)
        forged_relation = successor.refinement.model_copy(update={"successor_ref": forged_ref})
        forged_relation_ref = persist_search_uncertainty_v2(c["store"], forged_relation)
        fresh_state = _fresh_owner(c)
        before = fresh_state.read_current_snapshot(c["ticket"])
        assert before is not None
        with pytest.raises(SearchUncertaintyAdmissionError):
            fresh_state.record_first_assessment(
                ticket_id=c["ticket"],
                expected_generation=before.ticket_generation,
                expected_projection_revision=before.projection_revision,
                predecessor_ref=predecessor.observation_ref,
                successor_ref=forged_ref,
                refinement_ref=forged_relation_ref,
                completion_owner=service,
                tenant_id=c["tenant"],
                cell_id=c["cell"],
            )
        after = fresh_state.read_current_snapshot(c["ticket"])
        assert after is not None and after.projection_ref == before.projection_ref
        assert after.resolved_projection.current_obligations[0].selection.status == "contested"

    # A foreign unknown must remain disclosed without hiding the selected
    # basis's contested status. This uses a persisted adversarial fixture;
    # it is not a claim of an independently grounded risk producer.
    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        mixed = _inject_persisted_foreign_unknown(c)
        assert mixed is not None and mixed.status == "available_as_of_task_epoch"
        assert "foreign-fixture-obligation" in mixed.projection.active_unknown_obligation_ids
        assert mixed.task_admission.basis_ref == c["binding"].basis_ref
        selected = [
            item
            for item in mixed.resolved_projection.current_obligations
            if item.basis_ref == c["binding"].basis_ref
        ]
        assert len(selected) == 1 and selected[0].selection.status == "contested"
        assert consumer_status() == "contested"

    # A distinct synthetic risk is routed through the real Funnel consumer. It
    # is explicitly fixture data, not real-world risk evidence or authority.
    # A stage estimate is not an admitted active risk. It remains historical;
    # unknown current composition is exposed and must not be invented.
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.ir import UncertaintyType
    from polisyos.scientist.methods.search.uncertainty import (
        UncertaintyEnvelope,
        UncertaintyEstimate,
    )

    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        risk_ref = c["store"].put_json(
            {"fixture": "independent structural risk", "level": 0.8},
            PutOptions(kind="scientist.test", media_type="application/json"),
            return_selected_profile=True,
        )
        risk = UncertaintyEnvelope.from_partial(
            {
                UncertaintyType.STRUCTURAL: UncertaintyEstimate(
                    level=0.8,
                    source="synthetic independent risk fixture",
                    quantification_method="fixture candidate",
                    is_reducible=True,
                )
            }
        )
        stage = FunnelStageResult(
            policy_candidate={},
            objective_value=None,
            is_promising=True,
            stage_name="synthetic-independent-risk",
            fidelity_level=0,
            uncertainty_envelope=risk,
            audit_refs=[risk_ref],
        )
        funnel_ticket = FunnelTicket(
            ticket_id="separate-consumer-view",
            candidate_hash="fixture",
            candidate={},
            context={"store": c["store"]},
            stage_results={0: stage},
            search_uncertainty_ticket_id=c["ticket"],
        )
        funnel = _fresh_funnel(c)
        outcome = funnel.get_outcome(funnel_ticket)
        assert outcome.uncertainty_envelope.uncertainties[UncertaintyType.STRUCTURAL].level == 0.8
        assert outcome.current_uncertainty_envelope is None
        current = outcome.final_result.feedback["search_uncertainty_current_read"]
        assert (
            current["resolved_projection"]["current_obligations"][0]["selection"]["status"]
            == "contested"
        )


@pytest.mark.parametrize("mutation", ["outcome", "row_order", "sample_id", "assignment_edge"])
def test_actual_source_bytes_changed_without_changing_assignment_markers(admitted_case, mutation):
    """Persist and verify different bytes, not a constructed verifier response."""
    from copy import deepcopy

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
    from polisyos.core.artifacts.manifest import (
        ArtifactRef,
        SchemaInfo,
        input_ref_from_artifact_ref,
    )
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.hte_source_projection import verify_hte_source_projection_join
    from polisyos.scientist.methods.search.uncertainty import _resolve_hte_source_projection_join

    c = admitted_case
    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        payload = deepcopy(load_core_json_artifact(c["store"], c["source"]))
        values = payload["contract_payload"]
        if mutation == "outcome":
            values["outcome"][0] += 0.125
        elif mutation == "row_order":
            for key in ("outcome", "treatment", "covariates", "confounders", "sample_ids"):
                values[key][0], values[key][1] = values[key][1], values[key][0]
        elif mutation == "sample_id":
            values["sample_ids"][0] += "-foreign"
        edges = (
            []
            if mutation == "assignment_edge"
            else [input_ref_from_artifact_ref(c["assignment"], role="source_variable_assignment")]
        )
        changed = ArtifactRef.model_validate(
            c["store"].put_json(
                payload,
                PutOptions(
                    kind="ir.observation_method_input",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.ir.ObservationMethodInputEnvelope", version="1.0"
                    ),
                    inputs=edges,
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            ),
            strict=True,
        )
        changed_basis = c["basis"].model_copy(update={"selected_method_input_ref": changed})
        joined, refusal = _resolve_hte_source_projection_join(
            verifier=verify_hte_source_projection_join,
            store=c["store"],
            selected_method_input_ref=changed,
            basis=changed_basis,
            request_projection=c["binding"].request_projection,
            limits=CoreJsonReadLimits(
                max_bytes=8_388_608, max_depth=64, max_elements=200_000, max_manifest_bytes=65_536
            ),
        )
        assert joined is None and refusal is not None
        expected = {
            "outcome": "source_outcome_array_mismatch",
            "row_order": "source_profile_sample_ids_mismatch",
            "sample_id": "source_profile_sample_ids_mismatch",
            "assignment_edge": "source_assignment_edge_missing_or_ambiguous",
        }
        assert refusal == expected[mutation]
        # Marker content is unchanged even where the actual edge was removed.
        assert payload["contract_payload"]["metadata"] == {"source": "controlled_candidate_fixture"}


@pytest.mark.parametrize("field", ["alpha", "contrast", "method"])
def test_changed_request_cannot_borrow_existing_binding(admitted_case, field):
    """Request changes must refuse before an attempt can borrow the frozen basis."""
    from copy import deepcopy

    from polisyos.core.security.tenant_context import tenant_scope
    from tests._helpers.control_worker import stop_embedded_control_worker
    from tests.unit.runtime.http.test_search_hte_first_assessment_outbox import _request_payload

    c = admitted_case
    stop_embedded_control_worker(c["service"])
    payload = deepcopy(_request_payload(c["source"], c["binding_ref"]))
    observational = payload["observational_input"]
    if field == "alpha":
        observational["hte_request"]["alpha"] = 0.2
    elif field == "contrast":
        observational["hte_request"]["treated_value"] = 2.0
    else:
        observational["method"]["fqn"] = "causal.hte.double_ml@2.0.0"
    response = c["client"].post("/api/v1/control/runs", json=payload, headers=c["headers"])
    assert response.status_code >= 400, response.text
    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        fresh = _fresh_owner(c).read_current_snapshot(c["ticket"])
        assert fresh is not None and fresh.resolved_projection is not None
        assert fresh.resolved_projection.selected_unassessed_observations
        assert not fresh.resolved_projection.current_obligations


@pytest.mark.parametrize("removal", ["assessment_producer", "relation_admission"])
def test_remove_real_producer_or_relation_keeps_placeholder(admitted_case, monkeypatch, removal):
    """Falsify the actual producer and admission while preserving input markers."""
    pytest.importorskip("econml", reason="native HTE backend unavailable")
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.scientist.methods.search import uncertainty as owner
    from tests._helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from tests.unit.runtime.http.test_search_hte_first_assessment_outbox import _request_payload

    c = admitted_case
    service = c["service"]
    stop_embedded_control_worker(service)
    response = c["client"].post(
        "/api/v1/control/runs",
        json=_request_payload(c["source"], c["binding_ref"]),
        headers=c["headers"],
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    if removal == "assessment_producer":

        def removed_producer(**_kwargs):
            raise owner.SearchUncertaintyAdmissionError(
                "removed", reason_code="hte_content_unavailable"
            )

        monkeypatch.setattr(owner, "_build_hte_assessment_candidate", removed_producer)
    else:

        def removed_relation(self, **_kwargs):
            raise ValueError("removed relation admission")

        monkeypatch.setattr(
            owner.SearchUncertaintyTicketState, "record_first_assessment", removed_relation
        )
    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=job_id,
        )
        == job_id
    )
    job = service._control_store.get_job(job_id)
    assert job is not None and job.state == "completed"
    event = service._control_store.get_job_terminal_source_event_record(job_id)
    assert event.event_type == "job_completed"
    assert event.payload["method_execution_selection"]["hte"]["kind"] == "interval_estimate"
    service.reconcile_pending_search_hte_completion_events()
    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        fresh = _fresh_owner(c).read_current_snapshot(c["ticket"])
        assert fresh is not None and fresh.resolved_projection is not None
        assert fresh.resolved_projection.selected_unassessed_observations
        assert not fresh.resolved_projection.current_obligations


def test_current_status_missing_or_generation_superseded_is_not_established(admitted_case):
    """A fresh consumer must not report an older basis after generation advance."""
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.scientist.methods.search.funnel.types import FunnelStageResult, FunnelTicket

    c = admitted_case

    def status(ticket_id):
        ticket = FunnelTicket(
            ticket_id="consumer-view",
            candidate_hash="fixture",
            candidate={},
            context={"store": c["store"]},
            search_uncertainty_ticket_id=ticket_id,
            stage_results={
                0: FunnelStageResult(
                    policy_candidate={},
                    objective_value=None,
                    is_promising=True,
                    stage_name="fixture",
                    fidelity_level=0,
                )
            },
        )
        outcome = _fresh_funnel(c).get_outcome(ticket)
        assert outcome.final_result is not None
        return outcome.final_result.feedback["uncertainty_current_status"]

    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        assert status("missing-ticket") == "not_established"
        assert status(c["ticket"]) == "unassessed"
        state = _fresh_owner(c)
        before = state.read_current_snapshot(c["ticket"])
        assert before is not None
        after = state.bump_ticket_generation(
            c["ticket"], expected_generation=before.ticket_generation
        )
        assert after.ticket_generation == before.ticket_generation + 1
        assert status(c["ticket"]) == "not_established"


def test_single_foreign_basis_cannot_impersonate_selected_admission(admitted_case):
    """A self-consistent foreign record must not borrow the selected task basis."""
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.scientist.methods.search.funnel.types import FunnelStageResult, FunnelTicket

    c = admitted_case
    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        refused = _inject_persisted_foreign_unknown(c, replace_selected=True)
        assert refused is not None and refused.status == "not_established"
        ticket = FunnelTicket(
            ticket_id="foreign-view",
            candidate_hash="fixture",
            candidate={},
            context={"store": c["store"]},
            search_uncertainty_ticket_id=c["ticket"],
            stage_results={
                0: FunnelStageResult(
                    policy_candidate={},
                    objective_value=None,
                    is_promising=True,
                    stage_name="fixture",
                    fidelity_level=0,
                )
            },
        )
        outcome = _fresh_funnel(c).get_outcome(ticket)
        assert outcome.final_result.feedback["uncertainty_current_status"] == "not_established"


def test_removing_selected_basis_from_persisted_projection_refuses(admitted_case):
    """Admission markers survive while its actual predecessor edge is removed."""
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.scientist.methods.search.funnel.types import FunnelStageResult, FunnelTicket

    c = admitted_case
    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        refused = _inject_persisted_foreign_unknown(c, remove_selected=True)
        assert refused is not None and refused.status == "not_established"
        ticket = FunnelTicket(
            ticket_id="removed-view",
            candidate_hash="fixture",
            candidate={},
            context={"store": c["store"]},
            search_uncertainty_ticket_id=c["ticket"],
            stage_results={
                0: FunnelStageResult(
                    policy_candidate={},
                    objective_value=None,
                    is_promising=True,
                    stage_name="fixture",
                    fidelity_level=0,
                )
            },
        )
        outcome = _fresh_funnel(c).get_outcome(ticket)
        assert outcome.final_result.feedback["uncertainty_current_status"] == "not_established"


def _run_one_owned_hte_and_report(c):
    """Run one selected actual HTE and reopen its owner/consumer/report path."""
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.hte import load_hte_outcome
    from polisyos.ir.registry.refs import HTEOutcomeRef
    from polisyos.scientist.methods.search.funnel.types import FunnelStageResult, FunnelTicket
    from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_reporting import (
        _serialize_funnel_outcome,
    )
    from tests._helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from tests.unit.runtime.http.test_search_hte_first_assessment_outbox import _request_payload

    service = c["service"]
    stop_embedded_control_worker(service)
    response = c["client"].post(
        "/api/v1/control/runs",
        json=_request_payload(c["source"], c["binding_ref"]),
        headers=c["headers"],
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=job_id,
        )
        == job_id
    )
    job = service._control_store.get_job(job_id)
    assert job is not None and job.state == "completed", getattr(job, "error_message", None)
    event = service._control_store.get_job_terminal_source_event_record(job_id)
    assert event.event_type == "job_completed"
    selected = event.payload["method_execution_selection"]
    outcome_ref = HTEOutcomeRef.model_validate(selected["hte_outcome_ref"], strict=True)
    service.reconcile_pending_search_hte_completion_events()
    delivery = service._control_store.get_search_hte_completion_outbox_event(
        job_id=job_id, completed_event_id=event.event_id
    )
    assert delivery is not None and delivery.state == "published"
    with tenant_scope(None, tenant_id=c["tenant"], cell_id=c["cell"]):
        native = load_hte_outcome(
            ensure_ir_artifact_store(service._artifact_store), outcome_ref
        ).root
        fresh = _fresh_owner(c).read_current_snapshot(c["ticket"])
        assert fresh is not None and fresh.status == "available_as_of_task_epoch"
        assert fresh.resolved_projection is not None and fresh.projection is not None
        assert fresh.projection.live_currentness_status == "not_established"
        assert len(fresh.resolved_projection.current_obligations) == 1
        obligation = fresh.resolved_projection.current_obligations[0]
        assert obligation.selection.status == "assessed" and len(obligation.successors) == 1
        measured = obligation.successors[0].observation
        assert (
            measured.job_id == job_id
            and measured.predecessor_ref == obligation.predecessor.observation_ref
        )
        assert obligation.predecessor.observation.state == "unassessed"
        assert (
            obligation.predecessor.observation_ref in fresh.projection.historical_observation_refs
        )
        ticket = FunnelTicket(
            ticket_id="score-view",
            candidate_hash="fixture",
            candidate={},
            context={"store": c["store"]},
            search_uncertainty_ticket_id=c["ticket"],
            stage_results={
                0: FunnelStageResult(
                    policy_candidate={},
                    objective_value=None,
                    is_promising=True,
                    stage_name="fixture",
                    fidelity_level=0,
                )
            },
        )
        projected = _fresh_funnel(c).get_outcome(ticket)
        assert projected.final_result is not None
        assert projected.final_result.feedback["uncertainty_current_status"] == "assessed"
        assert projected.current_uncertainty_envelope is None
        reported = _serialize_funnel_outcome(projected)
        assert reported["uncertainty_current"] is None
        assert (
            reported["stage_results"]["0"]["feedback"]["uncertainty_current_status"] == "assessed"
        )
        report_observation = reported["search_uncertainty_current_read"]["resolved_projection"][
            "current_obligations"
        ][0]["successors"][0]["observation"]
        assert report_observation["state"] == "assessed"
        assert report_observation["outcome_kind"] == measured.outcome_kind
        assert report_observation["routing_score"]["status"] == measured.routing_score.status
        assert (
            report_observation["routing_score"]["unavailable_reason"]
            == measured.routing_score.unavailable_reason
        )
        assert "source_owner_issuance_not_established" in measured.limitations
        assert "source_owner_issuance_not_established" in report_observation["limitations"]
        assert reported["uncertainty_historical_max"] == projected.uncertainty_envelope.model_dump(
            mode="json"
        )
    return native, measured, report_observation


def test_real_point_survives_refused_native_inference_with_unavailable_score(
    admitted_case, monkeypatch
):
    """A real fit and controlled invalid interval follow the producer's point fallback."""
    pytest.importorskip("econml", reason="actual HTE backend unavailable")
    from polisyos.foundry.methods.catalog.causal import hte_v2

    original = hte_v2._native_interval_candidate
    calls = []

    def invalid_interval(*args, **kwargs):
        capture, reason = original(*args, **kwargs)
        assert capture is not None
        calls.append(capture.native_point)
        raw = capture.model_dump(mode="python")
        raw["native_lower_bound"] = capture.native_point + 1.0
        raw["native_upper_bound"] = capture.native_point + 2.0
        return type(capture).model_validate(raw, strict=True), reason

    monkeypatch.setattr(hte_v2, "_native_interval_candidate", invalid_interval)
    native, measured, observed = _run_one_owned_hte_and_report(admitted_case)
    assert len(calls) == 1
    assert calls[0] == native.point_estimate.value
    assert native.kind == "point_estimate" and measured.outcome_kind == "point_estimate"
    assert measured.theta == native.point_estimate.value
    assert measured.lower_bound is None and measured.upper_bound is None
    assert measured.routing_score.unavailable_reason == "interval_not_qualified"
    assert measured.routing_score.score is None
    assert observed["routing_score"]["unavailable_reason"] == "interval_not_qualified"
    assert native.authority_status == "candidate"


@pytest.mark.parametrize("admitted_case", ["zero-outcome"], indirect=True)
def test_native_zero_reference_retains_interval_and_unavailable_score(admitted_case):
    """Require an actual backend-produced zero, or disclose this fixture is unsupported."""
    pytest.importorskip("econml", reason="actual HTE backend unavailable")
    native, measured, observed = _run_one_owned_hte_and_report(admitted_case)
    if native.kind != "interval_estimate" or native.point_estimate.value != 0.0:
        pytest.skip("selected real estimator did not emit an interval with exact zero reference")
    assert measured.outcome_kind == "interval_estimate" and measured.theta == 0.0
    assert measured.lower_bound == native.lower_bound and measured.upper_bound == native.upper_bound
    assert measured.lower_bound <= measured.upper_bound
    assert measured.routing_score.unavailable_reason == "zero_reference_scale"
    assert measured.routing_score.score is None
    assert observed["routing_score"]["unavailable_reason"] == "zero_reference_scale"
    assert native.authority_status == "candidate"
