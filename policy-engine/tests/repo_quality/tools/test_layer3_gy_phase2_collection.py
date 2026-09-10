"""Complete-family failure collection and actual C3 owner readback controls."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.unit.runtime.quality.test_data_forge_binding import (
    recorded_panel_owner as _recorded_panel_owner,
)

recorded_panel_owner = _recorded_panel_owner

from tools.quality.validation import check_layer3_gy_phase2_artifacts as checker


def test_phase2_collection_keeps_actual_c1_when_foundry_consumption_is_missing(monkeypatch):
    """Red-first: the existing real builder aborts before returning C1 evidence."""
    from polisyos.runtime.quality.workspace.loop import WorkspaceLoop

    original = WorkspaceLoop.run_intent
    actual_calls = []

    def removed(self, problem, *args, **kwargs):
        result = original(self, problem, *args, **kwargs)
        actual_calls.append(problem.model_dump(mode="json"))
        # This is a removal witness, never a manufactured positive. It leaves
        # node/admission markers and real checked execution untouched.
        return result.model_copy(
            update={
                "method_output_consumption_record": None,
                "method_output_consumption_ref": None,
            }
        )

    monkeypatch.setattr(WorkspaceLoop, "run_intent", removed)
    root = Path(__file__).resolve().parents[3]
    payloads = checker.build_live_proof_payloads(root)
    assert set(payloads) == set(checker.declared_outputs())
    c1 = payloads[checker.PLAYBOOK_PROOF_PATH]
    assert c1["proofs"]
    assert c1["proofs"][0]["adapter_admissions"]
    c3 = payloads[checker.FOUNDRY_PROOF_PATH]
    assert c3["measurement"]["status"] == "fail"
    assert {row["task_id"] for row in c1["return_strangles"]["receipts"]} == {"GY-C1"}
    assert {row["task_id"] for row in c3["return_strangles"]["receipts"]} == {"GY-C3"}
    assert "c3_consumption_record_present_unmet" in {
        item["code"] for item in c3["measurement"]["issues"]
    }
    recorded = c1["family_collection"]["scenario_attempts"]
    assert [item["request"] for item in recorded] == actual_calls
    assert [item["scenario"] for item in recorded] == [name for name, _ in checker.PHASE2_SCENARIOS]
    print(
        json.dumps(
            {
                "deciding_predicate": "actual_c1_retained_on_actual_c3_gap",
                "attempt_statuses": recorded,
                "complete_output_identities": sorted(payloads),
            },
            sort_keys=True,
        )
    )


def _validator_only_population():
    """A writer/structural test double; never a canonical positive proof."""
    payloads = {path: {"unchanged_closed_owner": path} for path in checker.OUTPUTS}
    for path, schema in (
        (checker.PLAYBOOK_PROOF_PATH, checker.C1_PROOF_SCHEMA),
        (checker.FOUNDRY_PROOF_PATH, checker.C3_PROOF_SCHEMA),
    ):
        payloads[path] = {
            "schema_version": schema,
            "proofs": [{"test_only": True}],
            "measurement": {"status": "pass", "issues": []},
        }
    payloads[checker.PLAYBOOK_PROOF_PATH]["family_collection"] = {
        "expected_outputs": list(checker.OUTPUTS),
        "component_errors": [],
        "scenario_attempts": [
            {"scenario": name, "status": "returned", "error": None}
            for name, _ in checker.PHASE2_SCENARIOS
        ],
    }
    return payloads


def _install_validator_scope(monkeypatch, tmp_path, payloads):
    for name in (
        "_validate_generated_artifacts_registration",
        "_validate_lex_bounds_strangle_receipt",
        "_validate_lex_runtime_injection_fence",
    ):
        monkeypatch.setattr(checker, name, lambda *args: None)
    monkeypatch.setattr(checker, "build_live_proof_payloads", lambda root: copy.deepcopy(payloads))
    for path, value in payloads.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")


def test_phase2_write_preserves_closed_owners_and_stays_red_on_failed_conjunct(
    tmp_path, monkeypatch
):
    payloads = _validator_only_population()
    _install_validator_scope(monkeypatch, tmp_path, payloads)
    before = {path: (tmp_path / path).read_bytes() for path in checker.PROTECTED_OUTPUTS}
    payloads[checker.SPINE_PROOF_PATH]["new_closed_owner_drift"] = None
    payloads[checker.FOUNDRY_PROOF_PATH]["measurement"] = {
        "status": "fail",
        "issues": [{"code": "actual_constraint_basis_missing"}],
    }
    report = checker.validate(tmp_path, write=True)
    assert report["status"] == "fail"
    assert report["task_measurements"] == {"GY-C1": "pass", "GY-C3": "fail"}
    assert {path: (tmp_path / path).read_bytes() for path in checker.PROTECTED_OUTPUTS} == before
    assert set(report["checked_artifacts"]) == set(checker.OUTPUTS)
    assert set(report["written_artifacts"]) == set(checker.OUTPUTS) - set(checker.PROTECTED_OUTPUTS)
    assert "phase2_protected_owner_drift" in {item["code"] for item in report["issues"]}


@pytest.mark.parametrize("removed_path", checker.OUTPUTS)
def test_phase2_missing_member_cannot_narrow_the_complete_population(
    tmp_path, monkeypatch, removed_path
):
    payloads = _validator_only_population()
    _install_validator_scope(monkeypatch, tmp_path, payloads)
    del payloads[removed_path]
    report = checker.validate(tmp_path)
    assert report["status"] == "fail"
    assert "phase2_complete_output_population_mismatch" in {
        item["code"] for item in report["issues"]
    }


@pytest.mark.parametrize("change", ["duplicate", "missing", "crash"])
def test_phase2_attempt_population_and_crash_are_not_an_empty_success(
    tmp_path, monkeypatch, change
):
    payloads = _validator_only_population()
    _install_validator_scope(monkeypatch, tmp_path, payloads)
    rows = payloads[checker.PLAYBOOK_PROOF_PATH]["family_collection"]["scenario_attempts"]
    if change == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif change == "missing":
        rows.pop()
    else:
        rows[0].update(
            status="crashed",
            error={"code": "actual_scenario_crashed", "scenario": rows[0]["scenario"]},
        )
    assert checker.validate(tmp_path)["status"] == "fail"


def test_phase2_json_identity_diff_preserves_absence_null_and_empty_containers():
    variants = [
        {},
        {"value": None},
        {"value": []},
        {"value": {}},
        {"value": ""},
        {"value": False},
        {"value": 0},
        {"value": {"0": "x"}},
        {"value": ["x"]},
    ]
    identities = set()
    independent = 0
    for left_index, left in enumerate(variants):
        for right_index, right in enumerate(variants):
            independent += 1
            delta = checker._phase2_payload_delta(left, right)
            assert bool(delta) is (left_index != right_index)
            identities.add((left_index, right_index))
    assert len(identities) == independent == len(variants) ** 2
    print(
        json.dumps(
            {"complete_cartesian_cases": len(identities), "independent_loop_count": independent}
        )
    )


def _actual_missing_basis_constraint_case(tmp_path):
    """Actual requirement owner/loop consumer, without a fictitious positive basis."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.workspace.foundry_consumption import ConstraintStoreIngestor
    from polisyos.runtime.quality.workspace.loop import WorkspaceLoop, _phase2_constraint_blockers
    from tests.unit.runtime.quality.test_workspace_foundry_consumption import (
        _constraint_canonical_problem,
    )

    store = FileSystemCAS(tmp_path / "cas")
    owner = ConstraintStoreIngestor(store=store)
    admission = owner.produce(
        workspace_id="phase2-readback-control", design_problem=_constraint_canonical_problem()
    )
    loop = WorkspaceLoop(artifact_store=store)
    # Bind the real owner object for this focused readback test. The separate
    # actual-loop test proves the production bridge creates the same binding.
    loop._phase2_constraint_readbacks[id(admission)] = (admission, owner)
    blockers = _phase2_constraint_blockers(owner, admission, workspace_id=admission.workspace_id)
    result = SimpleNamespace(
        workspace_id=admission.workspace_id,
        constraint_admission=admission,
        search_blockers=blockers,
        terminal_state=SimpleNamespace(blocking_obligations=[item.blocker_id for item in blockers]),
        method_output_consumption_ref=None,
        method_output_consumption_record=None,
    )
    return store, owner, admission, loop, result


def test_phase2_constraint_proof_compares_full_raw_custody_before_clock_projection(tmp_path):
    first = _actual_missing_basis_constraint_case(tmp_path / "first")
    second = _actual_missing_basis_constraint_case(tmp_path / "second")
    left = checker._phase2_constraint_readback(result=first[4], loop=first[3], store=first[0])
    right = checker._phase2_constraint_readback(result=second[4], loop=second[3], store=second[0])
    assert str(first[2].artifact_ref.artifact_id) != str(second[2].artifact_ref.artifact_id)
    assert left == right
    assert left["roots"][0]["payload"]["population"] is None
    assert left["roots"][0]["payload"]["missing_basis"] == ["constraint_requirement_basis_missing"]


@pytest.mark.parametrize(
    "change", ["drop_blocker", "drop_terminal", "foreign_ref", "recreate_admission"]
)
def test_phase2_constraint_proof_refuses_unconsumed_or_recreated_admission(tmp_path, change):
    store, _, admission, loop, result = _actual_missing_basis_constraint_case(tmp_path)
    if change == "drop_blocker":
        result.search_blockers = []
    elif change == "drop_terminal":
        result.terminal_state.blocking_obligations = []
    elif change == "foreign_ref":
        result.search_blockers = [
            item.model_copy(update={"applicability_result_ref": "sha256:" + "0" * 64})
            for item in result.search_blockers
        ]
    else:
        result.constraint_admission = type(admission).model_validate(
            admission.model_dump(mode="json")
        )
    expected = (
        "constraint_admission_not_from_this_loop"
        if change == "recreate_admission"
        else "phase2_constraint"
    )
    with pytest.raises(ValueError, match=expected):
        checker._phase2_constraint_readback(result=result, loop=loop, store=store)


def test_phase2_constraint_full_packet_mutation_is_refused_before_semantic_projection(
    tmp_path, monkeypatch
):
    from polisyos.core.canon import from_canonical_bytes

    store, _, admission, loop, result = _actual_missing_basis_constraint_case(tmp_path)
    original = store.get_bytes

    def removed(identity):
        raw = original(identity)
        if str(identity) == str(admission.artifact_ref.artifact_id):
            packet = from_canonical_bytes(raw)
            packet["decision"]["blocks_promotion"] = False
            return checker._phase2_bytes(packet)
        return raw

    monkeypatch.setattr(store, "get_bytes", removed)
    with pytest.raises(ValueError, match=r"artifact_byte|constraint"):
        checker._phase2_constraint_readback(result=result, loop=loop, store=store)


def test_phase2_consumption_projection_requires_the_actual_complete_owner_seal(
    recorded_panel_owner,
):
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec, from_canonical_bytes
    from polisyos.runtime.quality.workspace.loop import WorkspaceLoop, _phase2_constraint_blockers
    from polisyos.runtime.quality.workspace.scientist_node_adapters import (
        _pdc_binding_ref,
        _read_binding,
    )
    from tests.unit.runtime.quality.test_workspace_foundry_consumption import (
        _post_method_constraints,
    )

    store, _, _, consumer, consumed, owner, preflight = _post_method_constraints(
        recorded_panel_owner
    )
    admission = owner.reconcile_method(preflight, method_owner=consumer, consumption=consumed)
    consumed = consumer.bind_constraints(consumption=consumed, owner=owner, admission=admission)
    ref = consumer.persist_consumption(store=store, consumption=consumed)
    loop = WorkspaceLoop(artifact_store=store)
    loop._phase2_constraint_readbacks[id(admission)] = (admission, owner)
    loop._phase2_method_readbacks[id(ref)] = (ref, consumer, consumed, store)
    blockers = _phase2_constraint_blockers(owner, admission, workspace_id=admission.workspace_id)
    result = SimpleNamespace(
        workspace_id=admission.workspace_id,
        constraint_admission=admission,
        search_blockers=blockers,
        terminal_state=SimpleNamespace(blocking_obligations=[item.blocker_id for item in blockers]),
        method_output_consumption_ref=ref,
        method_output_consumption_record=consumed.record,
        authority_boundary=consumed.authority_boundary,
        foundry_input_provenance=consumed.input_provenance,
    )
    proof = checker._phase2_constraint_readback(result=result, loop=loop, store=store)
    assert proof["roots"][0]["payload"]["method_report_ref"] is not None
    # Mutate the packet and loop DTO together, retaining all lineage/producer
    # markers. The independent original owner seal must still refuse it.
    packet = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    packet["authority_boundary"]["known_limits"].append("fabricated caller limitation")
    manifest = store.get_manifest(ref.artifact_id)
    counterfeit = store.put_json(
        packet,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    byte_binding, _, _ = _read_binding(store, counterfeit, "counterfeit_consumption")
    changed_ref = _pdc_binding_ref(byte_binding, ref.artifact_type, ref.schema_ref)
    result.method_output_consumption_ref = changed_ref
    result.authority_boundary = type(consumed.authority_boundary).model_validate(
        packet["authority_boundary"]
    )
    # Even a faulty bridge pairing this new ref with the original real consumer
    # cannot relabel its original private seal as the changed CAS bytes.
    loop._phase2_method_readbacks[id(changed_ref)] = (changed_ref, consumer, consumed, store)
    with pytest.raises(ValueError, match="owner_seal"):
        checker._phase2_constraint_readback(result=result, loop=loop, store=store)


_PHASE2_HISTORY_ID = "policy-design-case-layer3-gy-phase2-history-artifacts"
_PHASE2_HISTORY_PINS = {
    "architecture/policy_design_case/layer3_gy_phase2_playbook_run_proofs.json": (
        "sha256:fe3a082ba981ce27d2dc459219ea0081609085b5e467277bb66a9049ee7297e3"
    ),
    "architecture/policy_design_case/layer3_gy_phase2_foundry_consumption_proofs.json": (
        "sha256:4beee967f38b77738b13ed59a86a70d1100d23ea48bc1e6f1e521a54db7929c0"
    ),
}


def _phase2_epoch_registry(tmp_path):
    """Copy only the complete two-file immutable history; no proof manufacture."""
    import hashlib

    actual_root = Path(__file__).resolve().parents[3]
    for relative_path, expected_hash in _PHASE2_HISTORY_PINS.items():
        raw = (actual_root / relative_path).read_bytes()
        assert "sha256:" + hashlib.sha256(raw).hexdigest() == expected_hash
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    owner = "tools/quality/validation/check_layer3_gy_phase2_artifacts.py"
    return [
        {
            "id": checker.FAMILY_ID,
            "lifecycle": "generated_committed",
            "outputs": list(checker.OUTPUTS),
            "stale_output_behavior": "fail",
            "workflow": owner,
        },
        {
            "id": _PHASE2_HISTORY_ID,
            "lifecycle": "source_committed",
            "outputs": list(_PHASE2_HISTORY_PINS),
            "source_integrity_sha256": dict(_PHASE2_HISTORY_PINS),
            "stale_output_behavior": "fail",
            "workflow": owner,
        },
    ]


def _write_phase2_epoch_registry(root, families):
    lines = []
    for family in families:
        lines.append("[[family]]")
        for key, value in family.items():
            if isinstance(value, dict):
                lines.extend(
                    f"{key}.{json.dumps(path)} = {json.dumps(pin)}" for path, pin in value.items()
                )
            else:
                lines.append(f"{key} = {json.dumps(value)}")
    registry = root / "architecture/generated_artifacts.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_phase2_registration_accepts_exact_current_and_immutable_history(tmp_path):
    families = _phase2_epoch_registry(tmp_path)
    _write_phase2_epoch_registry(tmp_path, families)
    issues = []
    checker._validate_generated_artifacts_registration(tmp_path, issues)
    assert issues == []


@pytest.mark.parametrize("family_index", [0, 1], ids=("current", "history"))
@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("duplicate_family", "phase2_family_id_duplicate"),
        ("duplicate_output", "phase2_output_duplicate"),
        ("phantom_output", "phase2_output_outside_owned_epoch"),
        ("missing_output", "phase2_output_not_registered"),
        ("non_list_outputs", "phase2_family_outputs_invalid"),
        ("wrong_lifecycle", "phase2_family_lifecycle_invalid"),
        ("foreign_owner", "phase2_output_owner_conflict"),
    ],
)
def test_phase2_registration_enforces_whole_epoch_partition(
    tmp_path, family_index, mutation, expected_code
):
    """Exercise the existing registration consumer, not a missing new API."""
    families = _phase2_epoch_registry(tmp_path)
    _write_phase2_epoch_registry(tmp_path, families)
    baseline = []
    checker._validate_generated_artifacts_registration(tmp_path, baseline)
    assert baseline == []
    family = families[family_index]
    if mutation == "duplicate_family":
        families.append(copy.deepcopy(family))
    elif mutation == "duplicate_output":
        family["outputs"].append(family["outputs"][0])
    elif mutation == "phantom_output":
        family["outputs"].append("architecture/policy_design_case/phantom_phase2.json")
    elif mutation == "missing_output":
        family["outputs"].pop()
    elif mutation == "non_list_outputs":
        family["outputs"] = "not-an-output-list"
    elif mutation == "wrong_lifecycle":
        family["lifecycle"] = "source_committed" if family_index == 0 else "generated_committed"
    else:
        families.append({"id": "unrelated-owner", "outputs": [family["outputs"][0]]})
    _write_phase2_epoch_registry(tmp_path, families)
    issues = []
    checker._validate_generated_artifacts_registration(tmp_path, issues)
    assert expected_code in {item["code"] for item in issues}, issues


@pytest.mark.parametrize("relative_path", tuple(_PHASE2_HISTORY_PINS))
@pytest.mark.parametrize("mutation", ["changed_bytes", "missing_file", "restamped_pin"])
def test_phase2_history_custody_binds_every_original_byte(tmp_path, relative_path, mutation):
    families = _phase2_epoch_registry(tmp_path)
    path = tmp_path / relative_path
    if mutation == "missing_file":
        path.unlink()
        expected_code = "phase2_history_artifact_missing"
    else:
        # Extra whitespace preserves every JSON marker and all decision fields.
        path.write_bytes(path.read_bytes() + b"\n")
        expected_code = "phase2_history_artifact_changed"
        if mutation == "restamped_pin":
            import hashlib

            families[1]["source_integrity_sha256"][relative_path] = (
                "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            )
    _write_phase2_epoch_registry(tmp_path, families)
    issues = []
    checker._validate_generated_artifacts_registration(tmp_path, issues)
    assert any(
        item["code"] == expected_code and item.get("path") == relative_path for item in issues
    ), issues
    if mutation == "restamped_pin":
        assert "phase2_history_integrity_declaration_invalid" in {item["code"] for item in issues}


def test_phase2_history_custody_does_not_depend_on_registry_presence(tmp_path):
    _phase2_epoch_registry(tmp_path)
    relative_path = next(iter(_PHASE2_HISTORY_PINS))
    path = tmp_path / relative_path
    path.write_bytes(path.read_bytes() + b"\n")
    _write_phase2_epoch_registry(tmp_path, [])
    issues = []
    checker._validate_generated_artifacts_registration(tmp_path, issues)
    assert "phase2_generated_artifacts_family_missing" in {item["code"] for item in issues}
    assert "phase2_history_family_missing" in {item["code"] for item in issues}
    assert any(
        item["code"] == "phase2_history_artifact_changed" and item.get("path") == relative_path
        for item in issues
    ), issues


def _current_return_caller_basis(root):
    """Use the actual old admission guard for the red-first absence of return fences."""
    owner = getattr(checker, "_phase2_return_caller_basis", None)
    if owner is None:
        return checker.recompute_playbook_admission_strangle(root)
    return owner(root)


def _current_return_fence_issues(root):
    basis = _current_return_caller_basis(root)
    guard = getattr(checker, "_phase2_return_fence_issues", None)
    return guard(basis) if guard is not None else basis["unexpected_callers"]


@pytest.mark.parametrize(
    ("source", "code"),
    [
        (
            "from polisyos.foundry import select_value_method_for_problem as pick\n"
            "def route(problem):\n    alias = pick\n    return alias(problem)\n",
            "phase2_causal_n8_predecessor_reached",
        ),
        (
            "from polisyos.runtime.quality.workspace.foundry_consumption import ConstraintStoreIngestor as Owner\n"
            "def route():\n    owner = Owner()\n    alias = owner.ingest\n    return alias(snapshot_id='x', grammar_expansion_ref='x', artifacts=[])\n",
            "phase2_retired_constraint_ingress_reached",
        ),
        (
            "from polisyos.scientist.orchestration.engine import NodeOutcome as Outcome\n"
            "def route(payload):\n    return Outcome(**payload)\n",
            "phase2_base_outcome_star_reconstruction",
        ),
        (
            "from polisyos.scientist.orchestration.engine import NodeOutcome as Outcome\n"
            "def route(payload):\n    parse = Outcome.model_validate\n    return parse(payload)\n",
            "phase2_unclassified_base_outcome_reconstruction",
        ),
    ],
)
def test_phase2_return_strangle_refuses_new_aliased_predecessor(tmp_path, source, code):
    path = tmp_path / "src/polisyos/runtime/quality/workspace/new_caller.py"
    path.parent.mkdir(parents=True)
    path.write_text(source)
    issues = _current_return_fence_issues(tmp_path)
    assert any(row.get("code") == code for row in issues), issues


@pytest.fixture(scope="module")
def phase2_return_strangle_current():
    root = Path(__file__).resolve().parents[3]
    path = root / checker.STRANGLE_RECEIPT_PATH
    before = path.read_bytes()
    result = checker.recompute_phase2_return_strangles(root)
    return result, before, path.read_bytes()


def test_phase2_return_strangle_binds_all_current_source_callers(phase2_return_strangle_current):
    result, _, _ = phase2_return_strangle_current
    basis = result["caller_basis"]
    assert basis["source_denominator"]["rglob"] == basis["source_denominator"]["os_walk"]
    assert (
        basis["literal_identity_reconciliation"]["ast"]
        == basis["literal_identity_reconciliation"]["tokenize"]
    )
    assert basis["source_changed"] == []
    assert checker._phase2_return_fence_issues(basis) == []


def test_phase2_return_strangle_requires_every_replaced_reader_default(
    phase2_return_strangle_current,
):
    result, _, _ = phase2_return_strangle_current
    basis = result["caller_basis"]
    defaults = [
        row
        for row in basis["references"]
        if row["role"] == "call" and row["target"].endswith("decode_node_outcome")
    ]
    assert defaults
    for row in defaults:
        changed = copy.deepcopy(basis)
        changed["references"] = [item for item in changed["references"] if item != row]
        # The loader's mandatory current decoder call is part of its actual
        # default; losing it must not be hidden by remaining type markers.
        if row["path"].startswith("src/"):
            assert any(
                item["code"] == "phase2_replacement_default_not_consulted"
                and item["path"] == row["path"]
                for item in checker._phase2_return_fence_issues(changed)
            ), row


def test_phase2_return_strangle_recomputes_deletions_and_semantic_receipt_refs(
    phase2_return_strangle_current,
):
    root = Path(__file__).resolve().parents[3]
    result, _, _ = phase2_return_strangle_current
    for receipt in result["receipts"]:
        assert receipt["disposition"] == "fenced_default_flipped"
        assert receipt["default_before"] != receipt["default_after"]
        assert receipt["verified_by"]
        for member in receipt["replaced_members"]:
            assert member["removed_loc"]["unified_diff"] > 0
            assert (
                member["removed_loc"]["unified_diff"] == member["removed_loc"]["sequence_opcodes"]
            )
        for evidence in receipt["verified_by"]:
            relative, expected = evidence["ref"].rsplit("@sha256:", 1)
            import hashlib

            assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected


def test_phase2_return_strangle_keeps_closed_lex_packet_bytes(phase2_return_strangle_current):
    _, before, after = phase2_return_strangle_current
    assert after == before
