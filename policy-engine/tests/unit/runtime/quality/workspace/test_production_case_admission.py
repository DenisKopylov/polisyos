"""Production J attempts preserve original requirements and real refusal custody."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core.canon import CanonSpec
from polisyos.runtime.quality import graded_outcomes
from polisyos.runtime.quality.workspace import loop
from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner


def actual_pinned_intake_payload():
    root = Path(__file__).resolve().parents[5]
    path = (
        root
        / "architecture/policy_design_case/layer3_gx_data_home/cases/ua-msme-affordable-loans-2022/layer3_gx_pinned_request.json"
    )
    raw = path.read_bytes()
    pinned = json.loads(raw)
    scope = loop.load_workspace_fixture_manifest("ua_msme_credit_worldbank_measurement")
    payload = {
        "schema_version": "policyos.gy.production_case_intake.v1",
        "pinned_request": pinned,
        "scope": {
            "case_id": pinned["case_id"],
            "construct_scope_query": scope.construct_scope_query,
            "jurisdiction": scope.jurisdiction,
            "population": scope.population,
            "time_horizon": scope.time_horizon,
        },
        "scope_source_fixture_id": scope.fixture_id,
        "scope_source_sha256": "sha256:"
        + hashlib.sha256(
            (
                root / "architecture/policy_design_case/layer3_gy_slice0_fixture_manifest.json"
            ).read_bytes()
        ).hexdigest(),
        "requested_posture": "governed",
        "request_source_path": path.relative_to(root).as_posix(),
        "request_source_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "authority_limit": "request_custody_only_not_source_evidence",
    }
    return payload


@pytest.fixture
def production_input(tmp_path):
    payload = actual_pinned_intake_payload()
    with build_recorded_file_fetch_owner(tmp_path / "source") as owner:
        reference = owner.store.put_json(
            payload,
            artifacts.PutOptions(
                kind="gy.loop.proof.root",
                media_type="application/json",
                schema=artifacts.SchemaInfo(name="polisyos.gy.loop.proof.root", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        yield owner, payload, str(reference.artifact_id)


def _actual_entry(owner, request_ref):
    runtime = loop.WorkspaceLoop(catalog_graph=owner.graph, artifact_store=owner.store)
    if hasattr(runtime, "run_production_case"):
        return runtime.run_production_case(request_ref=request_ref)
    # The old public production control path is the deciding red, not an absent
    # new symbol. The real old source owner and terminal still execute here.
    return runtime.run_control_plane_fixture("ua_msme_credit_worldbank_measurement")


def test_production_attempts_original_requirements_through_s1_before_terminal(
    production_input, monkeypatch
):
    owner, payload, ref = production_input
    events = []
    actual = graded_outcomes.compose_graded_outcome

    def observe(evidence):
        events.append(("s1", evidence.claim_id))
        return actual(evidence)

    monkeypatch.setattr(graded_outcomes, "compose_graded_outcome", observe)
    if hasattr(loop, "compose_graded_outcome"):
        monkeypatch.setattr(loop, "compose_graded_outcome", observe)
    select = loop.select_search_terminal

    def observe_terminal(inputs):
        events.append(("terminal", None))
        return select(inputs)

    monkeypatch.setattr(loop, "select_search_terminal", observe_terminal)
    result = _actual_entry(owner, ref)
    expected = [row["construct_ref"] for row in payload["pinned_request"]["requested_constructs"]]
    first_terminal = next(index for index, item in enumerate(events) if item[0] == "terminal")
    assert [claim for kind, claim in events[:first_terminal] if kind == "s1"] == expected + expected
    assert result.terminal_state.kind.value == "a_spec_gap"
    assert result.authority_boundary is None
    assert result.workspace_contract.scope == payload["scope"]


def test_production_refusal_does_not_fabricate_fixture_recall(production_input):
    owner, _, ref = production_input
    result = _actual_entry(owner, ref)
    assert result.incompleteness_record.search_quality.recall_at_known_seeds is None
    assert result.search_ledger.counterexample_conversion_rate is None
    assert result.frontier_snapshot.frontier_metrics["design_candidate_count"] == 0


def test_source_population_reconciles_all_rows_and_refuses_projection_removal(
    production_input, monkeypatch
):
    owner, _, _ = production_input
    expected = owner.graph.resolve_metric_bindings("metric.test", top_k=None)
    assert expected
    actual = owner.graph.reconciled_metric_binding_population("metric.test")
    assert actual == expected
    old = owner.graph._store.resolve_metric_bindings
    monkeypatch.setattr(
        owner.graph._store, "resolve_metric_bindings", lambda *a, **k: old(*a, **k)[:-1]
    )
    with pytest.raises(ValueError, match="population_identity_drift"):
        owner.graph.reconciled_metric_binding_population("metric.test")


def test_production_never_calls_fixture_benchmark_or_estimate(production_input, monkeypatch):
    owner, _, ref = production_input

    def forbidden(*args, **kwargs):
        pytest.fail("fixture semantics reached production intake")

    for name in (
        "run_fixture",
        "_semantic_benchmark_run",
        "_build_artifacts",
        "_incompleteness",
        "_decision_inputs",
        "_budget_ledger",
    ):
        monkeypatch.setattr(loop.WorkspaceLoop, name, forbidden)
    result = _actual_entry(owner, ref)
    assert result.authority_boundary is None


@pytest.mark.parametrize(
    "mutation",
    ["drop_decision", "null_attempts", "fabricate_partial", "change_scope", "drop_clock"],
)
def test_production_receipt_consumer_recomputes_substance(production_input, mutation):
    owner, _, request_ref = production_input
    result = _actual_entry(owner, request_ref)
    (envelope,) = [
        row
        for row in result.artifact_envelopes
        if row.payload_schema_ref == loop.PRODUCTION_CASE_ADMISSION_SCHEMA
    ]
    from polisyos.core.canon import from_canonical_bytes

    body = from_canonical_bytes(owner.store.get_bytes(envelope.payload_ref))
    changed = copy.deepcopy(body)
    if mutation == "drop_decision":
        changed["graded_decisions"].pop()
    elif mutation == "null_attempts":
        changed["source_attempts"] = None
    elif mutation == "fabricate_partial":
        changed["graded_decisions"][0]["outcome"] = "publish_with_limitation"
    elif mutation == "change_scope":
        changed["graded_inputs"][0]["claim_id"] = "macro_context"
    else:
        changed.pop("checked_at")
    # A well-formed CAS member keeps the real schema/parent markers; actual
    # original bytes are not overwritten and no canonical numerator is touched.
    mutant = owner.store.put_json(
        changed,
        artifacts.PutOptions(
            kind=loop.PRODUCTION_CASE_ADMISSION_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=loop.PRODUCTION_CASE_ADMISSION_SCHEMA, version="1.0"),
            producer=artifacts.ProducerInfo(
                component="polisyos.runtime.quality.workspace.loop.production_case", version="1"
            ),
            inputs=[artifacts.InputRef(artifact_id=request_ref, role="production_case_input")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    with pytest.raises((ValueError, loop.WorkspaceInvariantError)):
        loop.resolve_production_case_admission(
            store=owner.store,
            receipt_ref=str(mutant.artifact_id),
            request_ref=request_ref,
            catalog=owner.graph,
        )


def test_production_current_source_change_revokes_receipt(production_input, monkeypatch):
    owner, _, request_ref = production_input
    result = _actual_entry(owner, request_ref)
    (envelope,) = [
        row
        for row in result.artifact_envelopes
        if row.payload_schema_ref == loop.PRODUCTION_CASE_ADMISSION_SCHEMA
    ]

    # Cut the true owner read, preserving receipt bytes and every marker.
    def missing(_metric):
        raise OSError("actual source population became unreadable")

    monkeypatch.setattr(owner.graph, "reconciled_metric_binding_population", missing)
    with pytest.raises((ValueError, loop.WorkspaceInvariantError), match="content_recompute_drift"):
        loop.resolve_production_case_admission(
            store=owner.store,
            receipt_ref=envelope.payload_ref,
            request_ref=request_ref,
            catalog=owner.graph,
        )


def test_unknown_population_requires_explicit_null_and_keeps_known_counts(production_input):
    owner, _, ref = production_input
    payload = _actual_entry(owner, ref).model_dump(mode="json")
    assert payload["incompleteness_record"]["search_quality"]["recall_at_known_seeds"] is None
    assert payload["search_ledger"]["counterexample_conversion_rate"] is None
    assert payload["frontier_snapshot"]["frontier_metrics"]["design_candidate_count"] == 0
    assert (
        loop.WorkspaceSearchExitContract.model_validate(payload).model_dump(mode="json") == payload
    )
    changed = copy.deepcopy(payload)
    changed["incompleteness_record"]["search_quality"].pop("recall_at_known_seeds")
    with pytest.raises(ValueError):
        loop.WorkspaceSearchExitContract.model_validate(changed)


@pytest.mark.parametrize("part", ["request", "scope", "source_hash"])
def test_original_source_markers_do_not_admit_changed_demand(production_input, part):
    owner, payload, _ = production_input
    mutant = copy.deepcopy(payload)
    if part == "request":
        mutant["pinned_request"]["requested_constructs"].pop()
    elif part == "scope":
        mutant["scope"]["population"] = "country_aggregates"
    else:
        mutant["request_source_sha256"] = "sha256:" + "a" * 64
    ref = owner.store.put_json(
        mutant,
        artifacts.PutOptions(
            kind="gy.loop.proof.root",
            media_type="application/json",
            schema=artifacts.SchemaInfo(name="polisyos.gy.loop.proof.root", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    with pytest.raises(
        (ValueError, loop.WorkspaceInvariantError), match=r"original_(request|scope)_content_drift"
    ):
        _actual_entry(owner, str(ref.artifact_id))


def test_production_refusal_does_not_mislabel_receipt_as_workspace_components(production_input):
    owner, _, ref = production_input
    result = _actual_entry(owner, ref)
    body = result.model_dump(mode="json")
    workspace = body["workspace_contract"]
    components = ("artifact_graph_ref", "constraint_store_ref", "agenda_ref", "frontier_ref")
    assert {name: workspace[name] for name in components} == dict.fromkeys(components)
    assert workspace["component_state"] == "unavailable"
    with pytest.raises(ValueError):
        loop.WorkspaceContract.model_validate(workspace)
    restored = loop.WorkspaceSearchExitContract.model_validate(body)
    assert type(restored.workspace_contract) is loop.RefusedWorkspaceContract
    assert set(loop.WorkspaceContract.model_fields) <= set(
        loop.RefusedWorkspaceContract.model_fields
    )
    with pytest.raises(ValueError):
        loop.WorkspaceContract.model_validate(restored.workspace_contract)
    assert restored.model_dump(mode="json") == body


@pytest.mark.parametrize(
    "field", ["artifact_graph_ref", "constraint_store_ref", "agenda_ref", "frontier_ref"]
)
def test_refused_workspace_union_rejects_each_false_component_reference(production_input, field):
    owner, _, ref = production_input
    body = _actual_entry(owner, ref).model_dump(mode="json")
    body["workspace_contract"][field] = body["workspace_contract"]["refusal_source_admission_ref"]
    with pytest.raises(ValueError):
        loop.WorkspaceSearchExitContract.model_validate(body)


def test_actual_production_workspace_custody_survives_annotated_reader(production_input):
    owner, _, ref = production_input
    body = _actual_entry(owner, ref).model_dump(mode="json")
    # This is the actual typed result boundary used by the worker; all refused
    # fields must survive read/serialize. Ordinary workspace admission stays red.
    result = loop.WorkspaceSearchExitContract.model_validate(body)
    assert result.workspace_contract.model_dump(mode="json") == body["workspace_contract"]
    changed = copy.deepcopy(body)
    changed["workspace_contract"].pop("component_state")
    with pytest.raises(ValueError):
        loop.WorkspaceSearchExitContract.model_validate(changed)


def test_production_p28_witness_observes_real_owner_before_terminal(production_input):
    from contextlib import ExitStack

    from tools.quality.validation import check_layer3_gy_loop_artifacts as proof_owner

    owner, payload, ref = production_input
    witness = proof_owner._ProductionDefaultWitness()
    with ExitStack() as stack:
        witness.install(stack)
        result = _actual_entry(owner, ref)
        members = [
            item
            for item in result.artifact_envelopes
            if item.payload_schema_ref == loop.PRODUCTION_CASE_ADMISSION_SCHEMA
        ]
        assert len(members) == 1
        admission = loop.resolve_production_case_admission(
            store=owner.store,
            receipt_ref=members[0].payload_ref,
            request_ref=ref,
            catalog=owner.graph,
        )
        measured = witness.checked_snapshot(
            admission, request_ref=ref, admission_ref=members[0].payload_ref
        )
    assert measured["claim_ids"] == [
        row["construct_ref"] for row in payload["pinned_request"]["requested_constructs"]
    ]
    assert {frame["phase"] for frame in measured["frames"]} == {"emission", "readback"}
    assert result.authority_boundary is None


def test_production_p28_witness_rejects_retained_decisions_without_actual_s1(
    production_input, monkeypatch
):
    from contextlib import ExitStack

    from tools.quality.validation import check_layer3_gy_loop_artifacts as proof_owner

    owner, _, ref = production_input
    original = _actual_entry(owner, ref)
    members = [
        item
        for item in original.artifact_envelopes
        if item.payload_schema_ref == loop.PRODUCTION_CASE_ADMISSION_SCHEMA
    ]
    admission = loop.resolve_production_case_admission(
        store=owner.store, receipt_ref=members[0].payload_ref, request_ref=ref, catalog=owner.graph
    )
    monkeypatch.setattr(loop, "_compose_production_case_admission", lambda **kwargs: admission)
    witness = proof_owner._ProductionDefaultWitness()
    with ExitStack() as stack:
        witness.install(stack)
        _actual_entry(owner, ref)
        with pytest.raises(
            ValueError, match="production_actual_s1_execution_does_not_bind_admission"
        ):
            witness.checked_snapshot(
                admission, request_ref=ref, admission_ref=members[0].payload_ref
            )
