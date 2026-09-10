"""Actual J proof custody, explicit clocks and full current/recorded GX checks."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from polisyos.data_forge import read_api
from polisyos.runtime.quality.workspace import loop
from tests.repo_quality.architecture import test_layer3_gy_artifact_lifecycle as lifecycle
from tools.quality.validation import check_layer3_gy_loop_artifacts as owner

REPO_ROOT = Path(__file__).resolve().parents[5]
gy_l_complete_live_population = lifecycle.gy_l_complete_live_population


@pytest.fixture(scope="module")
def actual_j_family_pair(gy_l_complete_live_population):
    """Reuse the whole measured L population; rerun the production member only."""
    old_family, observations, _ = gy_l_complete_live_population
    requests = owner.canonical_loop_requests()
    expected = {row.identity() for row in requests}
    actual = {observation._checked_snapshot()[0].identity() for observation in observations}
    assert actual == expected
    production = [row for row in requests if row.catalog_mode == "production"]
    assert len(production) == 1
    (request,) = production
    new_observation = owner._run_durable_workspace_loop_observation(
        fixture_id=request.fixture_id, catalog_mode=request.catalog_mode, repo_root=REPO_ROOT
    )
    next_observations = [
        new_observation if row._checked_snapshot()[0].identity() == request.identity() else row
        for row in observations
    ]
    new_basis = owner._assemble_live_loop_family(next_observations)
    actual_gx = owner._run_full_gx_on_new_artifacts(REPO_ROOT, new_basis)
    new_family = owner._attach_post_gx_result(new_basis, actual_gx)
    return old_family, new_family, new_observation


@pytest.fixture(scope="module")
def actual_j_catalog() -> Iterator[read_api.catalog.DatasetCatalogGraph]:
    directory = REPO_ROOT / "production_data/datasets_full_phase3full_20260327_183054"
    graph = read_api.catalog.DatasetCatalogGraph(directory / "dataset_catalog.duckdb", directory)
    try:
        yield graph
    finally:
        graph.close()


def _semantics(family, graph):
    return owner._j_family_semantics(payloads=family, repo_root=REPO_ROOT, catalog=graph)[0]


def test_real_production_clock_varies_but_full_verified_semantics_recompute(
    actual_j_family_pair, actual_j_catalog
):
    old, new, _ = actual_j_family_pair
    old_raw, new_raw = old._frozen_final_output(), new._frozen_final_output()
    assert old_raw != new_raw
    old_sem, new_sem = _semantics(old_raw, actual_j_catalog), _semantics(new_raw, actual_j_catalog)
    for row in (old_sem, new_sem):
        row[owner.OUTCOME_RUN_PATH].pop("gx_validator_status")
        row[owner.OUTCOME_RUN_PATH].pop("gx_validation")
    issues = []
    owner._compare_current_loop_outputs(old_sem, new_sem, issues)
    assert issues == []


@pytest.mark.parametrize(
    "mutation",
    [
        "manifest_absence",
        "manifest_null",
        "parent",
        "extra_member",
        "lost_member",
        "body",
        "final_hash",
    ],
)
def test_recorded_cas_closure_refuses_detached_content_while_markers_remain(
    actual_j_family_pair, actual_j_catalog, mutation
):
    old, _, _ = actual_j_family_pair
    changed = old._frozen_final_output()
    outcome = changed[owner.OUTCOME_RUN_PATH]
    packet = outcome["recorded_production_evidence"]
    receipt_ref = packet["admission_ref"]
    record = packet["records"][receipt_ref]
    manifest = json.loads(record["manifest_json"])
    if mutation == "manifest_absence":
        manifest.pop("created_at")
    elif mutation == "manifest_null":
        manifest["created_at"] = None
    elif mutation == "parent":
        manifest["inputs"][0]["role"] = "not_the_actual_input"
    elif mutation == "extra_member":
        packet["records"]["sha256:" + "a" * 64] = copy.deepcopy(record)
    elif mutation == "lost_member":
        packet["records"].pop(receipt_ref)
    elif mutation == "body":
        packet["additional_payloads"][receipt_ref]["graded_decisions"].pop()
    else:
        outcome["production_case_outcome"]["final_run_hash"] = "sha256:" + "a" * 64
    if mutation in {"manifest_absence", "manifest_null", "parent"}:
        record["manifest_json"] = json.dumps(manifest, sort_keys=True)
    # Every original schema and family marker survives each control. Present
    # missing/null/corrupt actual content must fail rather than default/project.
    with pytest.raises((ValueError, KeyError, loop.WorkspaceInvariantError)):
        _semantics(changed, actual_j_catalog)


def test_comparison_preserves_unknown_fields_and_original_scope(
    actual_j_family_pair, actual_j_catalog
):
    old, _, _ = actual_j_family_pair
    payload = old._frozen_final_output()
    expected = _semantics(payload, actual_j_catalog)
    changed = copy.deepcopy(payload)
    changed[owner.OUTCOME_RUN_PATH]["unknown_future_decision"] = {"authority": "forged"}
    observed = _semantics(changed, actual_j_catalog)
    issues = []
    owner._compare_current_loop_outputs(expected, observed, issues)
    assert issues == [{"code": "layer3_gy_outcome_run_drift", "path": owner.OUTCOME_RUN_PATH}]


def test_full_recorded_gx_is_replayed_and_failed_marker_cannot_disappear(
    actual_j_family_pair, monkeypatch
):
    old, new, _ = actual_j_family_pair
    recorded = old._frozen_final_output()
    actual_reader = owner._read_json
    actual_comparator = owner._compare_j_current_outputs
    comparisons = []

    def read_recorded(path, issues):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative in recorded:
            return copy.deepcopy(recorded[relative])
        return actual_reader(path, issues)

    def compare_actual(**kwargs):
        assert kwargs["fresh"] is new
        comparisons.append(kwargs["fresh"])
        return actual_comparator(**kwargs)

    # Exercise the real CLI owner's handoff, not only its direct comparator.
    # Both families were produced by the actual durable worker and full GX.
    with monkeypatch.context() as gate:
        gate.setattr(owner, "build_live_loop_artifacts", lambda repo_root: new)
        gate.setattr(owner, "_read_json", read_recorded)
        gate.setattr(owner, "_compare_j_current_outputs", compare_actual)
        report = owner.validate(REPO_ROOT, write=False)
    assert len(comparisons) == 1
    expected = [
        {
            "code": "layer3_gy_outcome_gx_not_passed",
            "path": owner.OUTCOME_RUN_PATH,
            "actual": "expected_red",
            "field_present": "True",
        },
        {"code": "layer3_gy_outcome_gx_report_not_passed", "path": owner.OUTCOME_RUN_PATH},
    ] * 2
    assert report["status"] == "fail"
    assert sorted(json.dumps(row, sort_keys=True) for row in report["issues"]) == sorted(
        json.dumps(row, sort_keys=True) for row in expected
    )
    corrupted = old._frozen_final_output()
    corrupted[owner.OUTCOME_RUN_PATH]["gx_validation"]["report_sha256"] = "sha256:" + "a" * 64
    issues = []
    owner._compare_j_current_outputs(
        committed=corrupted, fresh=new, repo_root=REPO_ROOT, issues=issues
    )
    assert issues == [
        {"code": "layer3_gy_recorded_gx_actual_replay_drift", "path": owner.OUTCOME_RUN_PATH}
    ]


def test_production_metric_carrier_has_two_explicit_unavailable_ratios(actual_j_family_pair):
    _, _, observation = actual_j_family_pair
    payload = observation["search_exit_contract"]

    # Independently traverse the COMPLETE serialized exit carrier: recursive
    # pointers and an iterative stack must find identical scalar/null leaves.
    def recursive(value, path=""):
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                encoded = key.replace("~", "~0").replace("/", "~1")
                result.update(recursive(child, path + "/" + encoded))
            return result
        if isinstance(value, list):
            result = {}
            for index, child in enumerate(value):
                result.update(recursive(child, path + "/" + str(index)))
            return result
        return {path: value}

    first = recursive(payload)
    second = {}
    pending = [("", payload)]
    while pending:
        path, value = pending.pop()
        if isinstance(value, dict):
            pending.extend(
                (path + "/" + str(key).replace("~", "~0").replace("/", "~1"), child)
                for key, child in value.items()
            )
        elif isinstance(value, list):
            pending.extend((path + "/" + str(index), child) for index, child in enumerate(value))
        else:
            second[path] = value
    assert first == second
    metric_paths = {
        "/incompleteness_record/search_quality/recall_at_known_seeds": None,
        "/search_ledger/counterexample_conversion_rate": None,
        "/frontier_snapshot/frontier_metrics/design_candidate_count": 0,
    }
    assert {path: first[path] for path in metric_paths} == metric_paths
    custody = observation._checked_custody()["production_admission"]
    basis = custody["metric_population_basis"]
    assert basis["ratios"]["recall_at_known_seeds"]["denominator"] is None
    assert basis["ratios"]["counterexample_conversion_rate"]["denominator"] == 0
    print(
        json.dumps(
            {
                "complete_scalar_denominator": len(first),
                "complete_identity_agreement": first == second,
                "complete_numeric_boolean_null_leaves": {
                    path: value
                    for path, value in sorted(first.items())
                    if value is None or type(value) in (int, float, bool)
                },
                "metric_population_basis": basis,
            },
            sort_keys=True,
        )
    )


def test_actual_http_durable_proof_keeps_unavailable_workspace_subtype(actual_j_family_pair):
    _, _, observation = actual_j_family_pair
    request, raw = observation._checked_snapshot()
    assert request.catalog_mode == "production"
    restored = loop.WorkspaceSearchExitContract.model_validate(raw["search_exit_contract"])
    assert type(restored.workspace_contract) is loop.RefusedWorkspaceContract
    assert restored.model_dump(mode="json") == raw["search_exit_contract"]
    with pytest.raises(ValueError):
        loop.WorkspaceContract.model_validate(raw["search_exit_contract"]["workspace_contract"])
    admission = observation._checked_custody()["production_admission"]
    assert (
        restored.workspace_contract.refusal_source_admission_ref
        == (observation._checked_custody()["recorded_production_evidence"]["admission_ref"])
    )
    assert restored.workspace_contract.refusal_reason == admission["positive_admission_state"]


def test_recorded_refusal_capsule_requires_complete_actual_recomputation(
    actual_j_family_pair, actual_j_catalog, monkeypatch
):
    old, new, _ = actual_j_family_pair
    payload = old._frozen_final_output()
    resolves, s1 = [], []
    real_resolve = loop.resolve_production_case_admission
    real_s1 = loop.compose_graded_outcome

    def resolve(*args, **kwargs):
        result = real_resolve(*args, **kwargs)
        resolves.append(result)
        return result

    def compose(value):
        decision = real_s1(value)
        s1.append((value.model_dump(mode="json"), decision.model_dump(mode="json")))
        return decision

    monkeypatch.setattr(loop, "resolve_production_case_admission", resolve)
    monkeypatch.setattr(loop, "compose_graded_outcome", compose)
    result = owner._j_family_semantics(
        payloads=payload, repo_root=REPO_ROOT, catalog=actual_j_catalog
    )
    # Removing actual resolver/S1 execution while retaining the prior real DTO
    # fails here. A declared old decision cannot substitute for this execution.
    assert resolves
    assert s1
    admission = resolves[-1]
    expected = [
        (value.model_dump(mode="json"), decision.model_dump(mode="json"))
        for value, decision in zip(admission.graded_inputs, admission.graded_decisions, strict=True)
    ]
    assert s1 == expected
    assert {row[0]["claim_id"] for row in s1} == {
        value.claim_id for value in admission.graded_inputs
    }
    recorded = result[3]
    assert type(recorded) is owner._VerifiedRecordedProductionRefusalReadback
    assert not isinstance(recorded, owner._VerifiedWorkspaceExitReadback)
    fresh_result = owner._j_family_semantics(
        payloads=new._frozen_final_output(), repo_root=REPO_ROOT, catalog=actual_j_catalog
    )
    assert recorded._compare_to_current(fresh_result[3], new) == []
    basis = owner._VerifiedLoopFamily(
        payload, exit_readback=recorded, issuer=owner._LIVE_LOOP_ISSUER
    )
    assert owner.freeze_pre_gx_output_family(basis) == json.loads(
        owner._pre_gx_family_bytes(payload)
    )


def test_recorded_capsule_rejects_mutation_of_complete_raw_contract_quantity(
    actual_j_family_pair, actual_j_catalog
):
    old, _, _ = actual_j_family_pair
    payload = old._frozen_final_output()
    result = owner._j_family_semantics(
        payloads=payload, repo_root=REPO_ROOT, catalog=actual_j_catalog
    )
    capsule = result[3]
    contract = payload[owner.OUTCOME_RUN_PATH]["search_exit_contract"]

    def recursive(value, path=()):
        if isinstance(value, dict):
            return set().union(*(
                {(*path, key)}
                if not isinstance(child, (dict, list)) or not child
                else recursive(child, (*path, key))
                for key, child in value.items()
            ))
        if isinstance(value, list):
            return set().union(*(
                {(*path, index)}
                if not isinstance(child, (dict, list)) or not child
                else recursive(child, (*path, index))
                for index, child in enumerate(value)
            ))
        return {path}

    paths = recursive(contract)
    independent = set()
    pending = [((), contract)]
    while pending:
        path, value = pending.pop()
        if isinstance(value, dict) and value:
            pending.extend(((*path, key), child) for key, child in value.items())
        elif isinstance(value, list) and value:
            pending.extend(((*path, index), child) for index, child in enumerate(value))
        else:
            independent.add(path)
    assert paths == independent and paths
    for path in paths:
        changed = copy.deepcopy(contract)
        parent = changed
        for key in path[:-1]:
            parent = parent[key]
        before = parent[path[-1]]
        parent[path[-1]] = {"detached_actual_value": before}
        with pytest.raises(ValueError, match="production_recorded_refusal_changed"):
            capsule._require_contract(changed)
    capsule._require_contract(contract)


@pytest.fixture(scope="module")
def actual_j_witness_semantic_pairs(actual_j_family_pair, actual_j_catalog):
    old, new, _ = actual_j_family_pair
    rows = []
    for family in (old, new):
        raw = family._frozen_final_output()
        semantics, refs, values, _ = owner._j_family_semantics(
            payloads=raw,
            repo_root=REPO_ROOT,
            catalog=actual_j_catalog,
        )
        rows.append((family, raw, semantics, refs, values))
    return rows


def test_production_p28_witness_hash_tracks_full_verified_semantics(
    actual_j_witness_semantic_pairs,
):
    projections = []
    for family, raw, semantics, refs, values in actual_j_witness_semantic_pairs:
        original = raw[owner.OUTCOME_RUN_PATH]["production_default_witness"]
        projected = semantics[owner.OUTCOME_RUN_PATH]["production_default_witness"]
        raw_hash = owner._gx_digest(owner.serialize_loop_artifact(original))
        semantic_hash = "semantic:" + owner._gx_digest(owner.serialize_loop_artifact(projected))
        assert refs[raw_hash] == semantic_hash
        assert values[owner.serialize_loop_artifact(original)] == projected
        gx = owner._j_actual_gx_semantics(
            packet=family._j_checked_gx_packet(),
            references=refs,
            values=values,
            normalized_family=semantics,
            repo_root=REPO_ROOT,
        )
        successors = gx["verification"]["strangle_receipt"]["successor_strangles"]
        selected = [
            row
            for row in successors
            if row["schema_version"] == "policyos.gy.production_default_strangle.v1"
        ]
        assert len(selected) == 1
        assert selected[0]["witness_sha256"] == semantic_hash
        assert selected[0]["request_ref"] == projected["request_ref"]
        assert selected[0]["admission_ref"] == projected["admission_ref"]
        projections.append(gx["verification"]["strangle_receipt"])
    # Every L receipt and J successor field is retained, not merely the hash.
    assert projections[0] == projections[1]


@pytest.mark.parametrize("field", ["witness_ref", "witness_sha256", "request_ref", "admission_ref"])
def test_production_p28_refuses_detached_named_witness_dependency(
    actual_j_witness_semantic_pairs, field
):
    family, _, semantics, refs, values = actual_j_witness_semantic_pairs[0]
    packet = family._j_checked_gx_packet()
    original = copy.deepcopy(packet)
    rows = packet["verification"]["strangle_receipt"]["successor_strangles"]
    selected = [
        row for row in rows if row["schema_version"] == "policyos.gy.production_default_strangle.v1"
    ]
    assert len(selected) == 1
    refs = dict(refs)
    detached = "sha256:" + "0" * 64
    if field in {"request_ref", "admission_ref"}:
        # Equal semantic projection must not substitute for the named raw ref.
        refs[detached] = refs[selected[0][field]]
    selected[0][field] = detached
    # Complete real report, basis, outcome markers and every other dependency
    # stay intact. The existing semantic consumer must itself refuse detachment.
    assert packet["_comparison_full_report"] == original["_comparison_full_report"]
    assert packet["_comparison_input_basis"] == original["_comparison_input_basis"]
    assert packet["_comparison_namespace"] == original["_comparison_namespace"]
    with pytest.raises(ValueError, match="production_gx_witness_dependency_drift"):
        owner._j_actual_gx_semantics(
            packet=packet,
            references=refs,
            values=values,
            normalized_family=semantics,
            repo_root=REPO_ROOT,
        )


def test_production_witness_projection_rejects_complete_raw_mutation_quantity(
    actual_j_witness_semantic_pairs,
    actual_j_catalog,
):
    _, raw, _, refs, _ = actual_j_witness_semantic_pairs[0]
    outcome = raw[owner.OUTCOME_RUN_PATH]
    packet, store, _ = owner._restore_j_recorded_evidence(
        outcome=outcome,
        replay_artifact=raw[owner.OUTCOME_REPLAY_PATH],
        repo_root=REPO_ROOT,
    )
    admission = loop.resolve_production_case_admission(
        store=store,
        receipt_ref=packet["admission_ref"],
        request_ref=packet["request_ref"],
        catalog=actual_j_catalog,
        repo_root=REPO_ROOT,
    )
    witness = outcome["production_default_witness"]

    def paths(value, prefix=()):
        if isinstance(value, dict) and value:
            return set().union(*(paths(child, (*prefix, key)) for key, child in value.items()))
        if isinstance(value, list) and value:
            return set().union(
                *(paths(child, (*prefix, index)) for index, child in enumerate(value))
            )
        return {prefix}

    first = paths(witness)
    second = set()
    pending = [((), witness)]
    while pending:
        path, value = pending.pop()
        if isinstance(value, dict) and value:
            pending.extend(((*path, key), child) for key, child in value.items())
        elif isinstance(value, list) and value:
            pending.extend(((*path, index), child) for index, child in enumerate(value))
        else:
            second.add(path)
    assert first == second and first
    for path in first:
        changed = copy.deepcopy(witness)
        parent = changed
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = {"detached_recorded_value": parent[path[-1]]}
        with pytest.raises((ValueError, TypeError)):
            owner._j_production_witness_projection(
                witness=changed,
                admission=admission,
                request_ref=packet["request_ref"],
                admission_ref=packet["admission_ref"],
                references=refs,
            )
    owner._j_production_witness_projection(
        witness=witness,
        admission=admission,
        request_ref=packet["request_ref"],
        admission_ref=packet["admission_ref"],
        references=refs,
    )
