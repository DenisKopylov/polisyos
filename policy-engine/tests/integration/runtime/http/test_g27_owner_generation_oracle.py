"""UNRUN author proposal: real SQL admission and fresh durable-owner consumers.

This bounded first slice covers T01/T02 and a declared T06 subset. It does not claim the four remaining
process-kill/fence cases, actual packet/SimulationResult consumption, external
SQL currentness, scheduling-prerequisite role selection, or G acceptance. See the existing registered-SQL live-grant
fixture and the single DecisionValidityService/source-admission owner.
"""

from __future__ import annotations

import copy
import json
import sqlite3

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, SchemaInfo
from polisyos.core.artifacts.manifest import CanonInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts.decision_validity import SourceAdmissionCarrier
from polisyos.core.security import tenant_scope
from polisyos.runtime.http.deployment_security import DeploymentSecurityConfig
from polisyos.scientist.validation import source_admission_state
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from tests._helpers.acquisition_served_history import CELL, TENANT
from tests._helpers.g27_owner_generation_oracle import (
    CommandOracle,
    FixtureCAS,
    canonical_bytes,
    committed_snapshot,
    digest,
    fresh_owner_reads,
)
from tests.integration.runtime.http import test_registered_sql_live_grant as live_grants

_ROWS = {
    "a": [(10.0, 11.0), (20.0, 18.0), (40.0, 44.0)],
    "b": [(30.0, 33.0), (50.0, 55.0), (70.0, 77.0)],
    "i": [(100.0, 101.0), (200.0, 198.0), (400.0, 404.0)],
}


@pytest.fixture
def g27_env(tmp_path, monkeypatch):
    """Reuse the genuine fixture; add I only to its validated pre-build config."""
    real_builder = live_grants.build_deployment_security
    configured = []

    def build_two_configured_scopes(config):
        raw = config.model_dump(mode="python")
        slot_a = next(
            item for item in raw["registered_sql_sources"] if item["slot_id"] == "source-a"
        )
        raw["registered_sql_sources"] = [
            *raw["registered_sql_sources"],
            {
                **slot_a,
                "slot_id": "source-i",
                "registration_key": "registered-i",
                "registration_event_id": "source-genesis-i",
            },
        ]
        admitted_config = DeploymentSecurityConfig.from_mapping(raw)
        configured.append(admitted_config)
        # This is the unchanged real deployment builder, not a verifier mock.
        return real_builder(admitted_config)

    monkeypatch.setattr(live_grants, "build_deployment_security", build_two_configured_scopes)
    generator = live_grants.source_grant_env.__wrapped__(tmp_path, monkeypatch)
    try:
        external, deployment, client, token, body, captured = next(generator)
        assert len(configured) == 1
        container = client.app.state.runtime_container
        evidence = tmp_path / "g27-evidence"
        cas = FixtureCAS(tmp_path / "cas", evidence)
        slots = {
            slot.slot_id: slot.model_dump(mode="json")
            for slot in configured[0].registered_sql_sources
        }
        yield {
            "client": client,
            "headers": {"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT},
            "body": body,
            "owner": container.decision_validity_service,
            "store": container.runtime_api_context.store,
            "cas_root": tmp_path / "cas",
            "database": tmp_path / "policy.sqlite",
            "oracle": CommandOracle(cas, slots),
            "evidence": evidence,
            "configured": configured[0],
            "external": external,
            "deployment": deployment,
            "captured_test_mint_calls": captured,
        }
    finally:
        generator.close()


def _exchange(env, endpoint, body):
    """Capture every actual protected response/root before interpreting its result."""
    command = env["oracle"].cas.begin_command(endpoint, body)
    try:
        response = env["client"].post(
            f"/api/v1/control/registered-sql/{endpoint}", headers=env["headers"], json=body
        )
    except BaseException as exc:
        env["oracle"].cas.observe_response(
            command, status=None, raw=None, transport_error=type(exc).__name__
        )
        raise
    observed = env["oracle"].cas.observe_response(
        command, status=response.status_code, raw=response.content
    )
    return response, observed


def _commit(env, endpoint, body, *, expected_rows=None):
    response, observed = _exchange(env, endpoint, body)
    reconciled = False
    try:
        assert response.status_code == 200, response.text
        result = response.json()
        env["oracle"].accept(endpoint, body, result, expected_rows)
        reconciled = True
        return result
    finally:
        env["oracle"].cas.finish_response(observed, reconciled=reconciled)


def _prepare_sources(env):
    assert not (env["cas_root"] / "decision_validity/committed_source_root.json").exists()
    registrations = {}
    for name in ("a", "i"):
        response = _commit(
            env,
            "registrations",
            {"slot_id": f"source-{name}", "event_id": f"source-genesis-{name}"},
        )
        registrations[name] = response["registration"]
    assert (
        registrations["a"]["source_incarnation_id"] != registrations["i"]["source_incarnation_id"]
    )
    assert (
        registrations["a"]["admission_scope_digest"] != registrations["i"]["admission_scope_digest"]
    )
    predecessor = {name: registration["event_ref"] for name, registration in registrations.items()}
    results = {}
    for name, rows in _ROWS.items():
        slot = "i" if name == "i" else "a"
        with sqlite3.connect(env["database"]) as database:
            database.execute("DELETE FROM policy_inputs")
            database.executemany("INSERT INTO policy_inputs VALUES (?, ?, NULL)", rows)
        body = {
            **env["body"],
            "slot_id": f"source-{slot}",
            "event_id": f"source-event-{name}",
            "occurrence_id": f"source-occurrence-{name}",
            "expected_predecessor": predecessor[slot],
        }
        database_copy = env["evidence"] / f"sql-before-{name}.sqlite"
        assert not database_copy.exists()
        with (
            sqlite3.connect(f"file:{env['database']}?mode=ro", uri=True) as source,
            sqlite3.connect(database_copy) as target,
        ):
            source.backup(target)
        expected_rows = [
            {"baseline": baseline, "scenario": scenario, "note": None}
            for baseline, scenario in rows
        ]
        result = _commit(env, "materializations", body, expected_rows=expected_rows)
        assert result["current_use"] == "not_checked"
        assert result["external_database_currentness"] == "not_established"
        binding = env["oracle"].cas.selected(result["binding_ref"])["value"]
        materialization = binding["materialization"]
        predecessor[slot] = result["receipt"]["event_ref"]
        results[name] = {"response": result, "body": body, "binding": binding}
    assert not env["captured_test_mint_calls"], "test-only live-grant mint route was used"
    return results


def _carriers(results):
    return {name: value["response"]["receipt"]["carrier"] for name, value in results.items()}


def _capture_inputs(env, results):
    original = {}
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        for value in results.values():
            materialization = value["binding"]["materialization"]
            refs = [
                value["response"]["binding_ref"],
                *[
                    materialization[key]
                    for key in (
                        "producer_capture_ref",
                        "request_ref",
                        "snapshot_ref",
                        "payload_ref",
                        "schema_ref",
                        "quality_ref",
                    )
                ],
                materialization["registration"]["effective_view_contract_ref"],
                materialization["registration"]["use_contract_ref"],
            ]
            for row in refs:
                ref = ArtifactRef.model_validate(row)
                key = canonical_bytes(row).decode()
                original[key] = env["store"].get_bytes(ref)
    return original


def _withdraw_a(env, results):
    return {
        "slot_id": "source-a",
        "event_id": "withdraw-a-after-b",
        "expected_predecessor": results["b"]["response"]["receipt"]["event_ref"],
        "target": results["a"]["response"]["receipt"]["carrier"],
    }


def test_g27_real_sql_withdraw_a_after_b_fresh_owner(g27_env, tmp_path):
    env = g27_env
    results = _prepare_sources(env)
    carriers = _carriers(results)
    vectors = {
        "D1": [carriers["a"]],
        "D2": [carriers["a"], carriers["b"]],
        "D2_reverse": [carriers["b"], carriers["a"]],
        "D2_repeated": [carriers["a"], carriers["b"], carriers["a"]],
        "B": [carriers["b"]],
        "I": [carriers["i"]],
    }
    assert carriers["a"]["admission_scope_digest"] == carriers["b"]["admission_scope_digest"]
    assert carriers["i"]["admission_scope_digest"] != carriers["a"]["admission_scope_digest"]
    before_disk = committed_snapshot(env["cas_root"])
    before = fresh_owner_reads(
        env["cas_root"], vectors, tmp_path / "fresh-before", tenant_id=TENANT, cell_id=CELL
    )
    for name, vector in vectors.items():
        env["oracle"].check_projection(before["projections"][name], vector, before_disk)
    assert (
        before["projections"]["D2"]["basis_digest"]
        != before["projections"]["D2_reverse"]["basis_digest"]
    )
    assert (
        before["projections"]["D2"]["basis_digest"]
        != before["projections"]["D2_repeated"]["basis_digest"]
    )
    original = _capture_inputs(env, results)
    _commit(env, "withdrawals", _withdraw_a(env, results))
    after_disk = committed_snapshot(env["cas_root"])
    assert after_disk["root"]["generation"] == before_disk["root"]["generation"] + 1
    assert after_disk["root_digest"] != before_disk["root_digest"]
    for event_id, event in before_disk["events"].items():
        assert after_disk["events"][event_id] == event
    after = fresh_owner_reads(
        env["cas_root"], vectors, tmp_path / "fresh-after", tenant_id=TENANT, cell_id=CELL
    )
    for name, vector in vectors.items():
        env["oracle"].check_projection(after["projections"][name], vector, after_disk)
    assert _capture_inputs(env, results) == original
    # Falsify the durable command while keeping status/root/reason markers.
    forged = copy.deepcopy(after_disk)
    event = forged["events"]["withdraw-a-after-b"]
    event["command"]["expected_predecessor"] = "sha256:" + "0" * 64
    event["command_digest"] = digest(event["command"])
    with pytest.raises(AssertionError, match="G27_COMMITTED_QUANTITY_MISMATCH"):
        env["oracle"].reconcile(forged)


def test_g27_retry_conflict_gap(g27_env, monkeypatch):
    env = g27_env
    attempts = []
    observation_errors = []
    real_commit = source_admission_state._SourceAdmissionStateStore._commit
    fault_binding = {"armed": False, "event_id": None, "hook": None, "store": None}

    def retain_observation(value):
        try:
            return env["oracle"].cas.note(value)
        except Exception as exc:
            observation_errors.append(type(exc).__name__)
            return None

    def observe_actual_commit(store, command, *args, **kwargs):
        attempt = {"command": copy.deepcopy(command), "store": store}
        attempts.append(attempt)
        sequence = retain_observation(
            {
                "kind": "commit_call",
                "command": attempt["command"],
                "store_identity": id(store),
                "root_path": str(store.root_path),
                "predicate_provenance": "not_established",
            }
        )
        try:
            if fault_binding["armed"]:
                expected_root = env["cas_root"] / "decision_validity" / "committed_source_root.json"
                if (
                    type(store) is not source_admission_state._SourceAdmissionStateStore
                    or store.root_path != expected_root
                    or store._fault is not None
                    or command.get("event_id") != fault_binding["event_id"]
                    or command.get("operation") != "withdraw"
                ):
                    observation_errors.append("G27_COMMIT_STORE_BINDING_ERROR")
                    raise AssertionError("G27_COMMIT_STORE_BINDING_ERROR")
                fault_binding["armed"] = False
                fault_binding["store"] = store
                store._fault = fault_binding["hook"]
                try:
                    receipt = real_commit(store, command, *args, **kwargs)
                finally:
                    store._fault = None
            else:
                receipt = real_commit(store, command, *args, **kwargs)
        except BaseException as exc:
            attempt.update(outcome="raised", error_type=type(exc).__name__, error_message=str(exc))
            retain_observation(
                {
                    "kind": "commit_result",
                    "call_sequence": sequence,
                    "outcome": "raised",
                    "error_type": attempt["error_type"],
                    "error_message": attempt["error_message"],
                    "predicate_provenance": "not_established",
                }
            )
            raise
        try:
            receipt_json = receipt.model_dump(mode="json")
        except Exception as exc:
            observation_errors.append(type(exc).__name__)
            receipt_json = None
        attempt.update(outcome="returned", receipt=receipt_json)
        retain_observation(
            {
                "kind": "commit_result",
                "call_sequence": sequence,
                "outcome": "returned",
                "receipt": receipt_json,
                "predicate_provenance": "not_established",
            }
        )
        return receipt

    monkeypatch.setattr(
        source_admission_state._SourceAdmissionStateStore, "_commit", observe_actual_commit
    )
    results = _prepare_sources(env)
    assert not observation_errors, "G27_COMMIT_OBSERVATION_ERROR"
    command = _withdraw_a(env, results)
    before = committed_snapshot(env["cas_root"])
    fault_roots = []
    pending_roots = []

    def interrupt_before_publish(point):
        if point != "before_root_publish":
            return
        store = fault_binding["store"]
        try:
            member = env["oracle"].cas.preserve(store.root_path.read_bytes())
            staged_paths = list(store.root_path.parent.glob(".source-root-*"))
            if len(staged_paths) != 1:
                raise ValueError("staged root is not uniquely observed")
            staged_raw = staged_paths[0].read_bytes()
            staged = json.loads(staged_raw)
            event_raw = (store.objects / (staged["event_ref"] + ".json")).read_bytes()
            event = json.loads(event_raw)
            index_raw = (store.objects / (staged["index_ref"] + ".json")).read_bytes()
            index = json.loads(index_raw)
            pending = {
                "root": staged,
                "event": event,
                "index": index,
                "root_member": env["oracle"].cas.preserve(staged_raw),
                "event_member": env["oracle"].cas.preserve(event_raw),
                "index_member": env["oracle"].cas.preserve(index_raw),
            }
            pending_roots.append(pending)
        except Exception as exc:
            observation_errors.append(type(exc).__name__)
            member = None
            pending = None
        fault_roots.append(member)
        retain_observation(
            {
                "kind": "commit_fault_observation",
                "point": point,
                "root_member": member,
                "staged_root_member": None if pending is None else pending["root_member"],
                "staged_event_member": None if pending is None else pending["event_member"],
                "staged_index_member": None if pending is None else pending["index_member"],
                "store_identity": id(store),
                "predicate_provenance": "not_established",
            }
        )
        raise OSError("g27-test-interrupted-before-root")

    call_count = len(attempts)
    fault_binding.update(armed=True, event_id=command["event_id"], hook=interrupt_before_publish)
    interrupted, observed = _exchange(env, "withdrawals", command)
    reconciled = False
    try:
        assert not observation_errors, "G27_COMMIT_OBSERVATION_ERROR"
        assert interrupted.status_code >= 400, interrupted.text
        assert len(attempts) == call_count + 1
        aborted = attempts[-1]
        assert not fault_binding["armed"] and fault_binding["store"] is aborted["store"]
        assert aborted["store"]._fault is None
        assert aborted["outcome"] == "raised" and aborted["error_type"] == "OSError"
        assert aborted["error_message"] == "g27-test-interrupted-before-root"
        assert aborted["command"]["event_id"] == command["event_id"]
        assert aborted["command"]["target"] == command["target"]
        assert aborted["command"]["expected_predecessor"] == command["expected_predecessor"]
        assert fault_roots == [before["root_digest"].removeprefix("sha256:")]
        assert len(pending_roots) == 1
        pending = pending_roots[0]
        staged, event, index = pending["root"], pending["event"], pending["index"]
        assert set(staged) == {"schema_version", "generation", "event_ref", "index_ref"}
        assert staged["schema_version"] == "source-admission-root.v1"
        assert staged["generation"] == event["generation"] == before["root"]["generation"] + 1
        assert digest(staged).removeprefix("sha256:") == pending["root_member"]
        assert pending["event_member"] == staged["event_ref"]
        assert pending["index_member"] == staged["index_ref"]
        assert digest(event).removeprefix("sha256:") == pending["event_member"]
        assert digest(index).removeprefix("sha256:") == pending["index_member"]
        assert event["schema_version"] == "source-event.v1"
        assert event["command"] == aborted["command"]
        assert event["command_digest"] == digest(aborted["command"])
        assert event["result"] == {"operation": "withdraw", "carrier": aborted["command"]["target"]}
        assert committed_snapshot(env["cas_root"]) == before
        assert command["event_id"] not in before["events"]
        reconciled = True
    finally:
        env["oracle"].cas.finish_response(observed, reconciled=reconciled)

    call_count = len(attempts)
    committed = _commit(env, "withdrawals", command)
    assert not observation_errors, "G27_COMMIT_OBSERVATION_ERROR"
    assert len(attempts) == call_count + 1
    first = attempts[-1]
    assert first["command"] == aborted["command"]
    snapshot = committed_snapshot(env["cas_root"])
    assert snapshot["root"]["generation"] == before["root"]["generation"] + 1
    assert snapshot["root_digest"] != before["root_digest"]
    assert set(snapshot["events"]) == set(before["events"]) | {command["event_id"]}
    assert all(snapshot["events"][key] == value for key, value in before["events"].items())
    assert first["outcome"] == "returned" and first["receipt"] == committed["receipt"]
    assert first["command"] == snapshot["events"][command["event_id"]]["command"]

    call_count = len(attempts)
    retried = _commit(env, "withdrawals", command)
    assert not observation_errors, "G27_COMMIT_OBSERVATION_ERROR"
    assert len(attempts) == call_count + 1
    retry = attempts[-1]
    assert retry["outcome"] == "returned"
    assert retry["command"] == first["command"]
    assert retry["receipt"] == first["receipt"] == retried["receipt"]
    assert retried == committed
    assert committed_snapshot(env["cas_root"]) == snapshot

    variants = [
        (
            {**command, "target": results["b"]["response"]["receipt"]["carrier"]},
            "source_admission_conflicting_event_id",
        ),
        (
            {
                **command,
                "event_id": "withdraw-b-with-gap",
                "expected_predecessor": "sha256:" + "0" * 64,
                "target": results["b"]["response"]["receipt"]["carrier"],
            },
            "source_admission_predecessor_gap",
        ),
    ]
    for body, expected_error in variants:
        call_count = len(attempts)
        response, observed = _exchange(env, "withdrawals", body)
        reconciled = False
        try:
            assert not observation_errors, "G27_COMMIT_OBSERVATION_ERROR"
            assert response.status_code >= 400, response.text
            assert len(attempts) == call_count + 1
            failed = attempts[-1]
            assert failed["outcome"] == "raised" and failed["error_type"] == "ValueError"
            assert failed["error_message"] == expected_error
            assert failed["command"]["event_id"] == body["event_id"]
            assert failed["command"]["target"] == body["target"]
            assert failed["command"]["expected_predecessor"] == body["expected_predecessor"]
            assert committed_snapshot(env["cas_root"]) == snapshot
            reconciled = True
        finally:
            env["oracle"].cas.finish_response(observed, reconciled=reconciled)


def _check_selected_quantity_controls(env):
    """Use exact selected raw imports to exercise the one profiled interpretation.

    Raw .3 imports qualify reader grammar only; they never enable the fenced .3
    producer cohort or claim an independently implemented codec. Every refused
    selector/member and successful counterfactual is retained by FixtureCAS.
    """
    native = {
        "receipt": {"committed_at": {"_type": "datetime", "iso_utc": "2026-10-01T12:34:56Z"}},
        "rows": [{"baseline": {"_type": "float", "repr": "10"}, "note": None}],
    }
    expected = {
        "receipt": {"committed_at": "2026-10-01T12:34:56Z"},
        "rows": [{"baseline": 10.0, "note": None}],
    }

    def selected(value, *, version="0.2.0", declared=True):
        raw = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
            ref = env["store"].put_bytes(
                raw,
                ArtifactWriteOptions(
                    kind="test.g27.selected_quantity",
                    media_type="application/json",
                    schema=SchemaInfo(name="test.G27SelectedQuantity", version="1.0"),
                    canon=CanonInfo(version=version, forbid_floats=False, exclude_none=False)
                    if declared
                    else None,
                ),
                return_selected_profile=True,
            )
        return env["oracle"].cas.selected(ref.model_dump(mode="json"))

    for version in ("0.2.0", "0.3.0"):
        assert selected(native, version=version)["value"] == expected
        changed = copy.deepcopy(native)
        changed["rows"][0]["baseline"]["repr"] = "11"
        altered = selected(changed, version=version)["value"]
        assert altered["rows"][0]["baseline"] == 11.0
        with pytest.raises(AssertionError, match="G27_SELECTED_QUANTITY_COUNTERFACTUAL"):
            assert altered == expected, "G27_SELECTED_QUANTITY_COUNTERFACTUAL"
        for malformed in (
            {"_type": "float", "repr": "10", "extra": "still-present"},
            {"_type": "float", "repr": "not-a-float"},
            {"_type": "not-a-native", "repr": "10"},
        ):
            with pytest.raises(AssertionError, match="G27_SELECTED_CODEC_REFUSED"):
                selected(malformed, version=version)

    # An exact .3 escaped raw map resembles a float envelope, but is plain data.
    raw_map = {"_type": "mapping", "entries": [["_type", "float"], ["repr", "10"]]}
    assert selected(raw_map, version="0.3.0")["value"] == {"_type": "float", "repr": "10"}
    with pytest.raises(AssertionError, match="G27_SELECTED_CODEC_REFUSED"):
        selected(native, declared=False)
    with pytest.raises(AssertionError, match="G27_SELECTED_CODEC_REFUSED"):
        selected(native, version="0.9.0")
    # A recognized but unsupported native descriptor must not become a guessed scalar.
    with pytest.raises(AssertionError, match="G27_SELECTED_SEMANTIC_TYPE_UNSUPPORTED"):
        selected({"_type": "decimal", "value": "10"})


def test_g27_unknown_scope_and_legacy(g27_env):
    env = g27_env
    _check_selected_quantity_controls(env)
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        absent = env["owner"].read_source_current_use((), require_selected=False)
        assert absent.status == "unknown" and absent.generation == 0
        assert absent.committed_root is None
        assert absent.reason_codes == ("source_admission_required_basis_not_established",)
    results = _prepare_sources(env)
    carrier = _carriers(results)["a"]
    empty_root = env["evidence"] / "no-genesis-cas"
    empty_owner = DecisionValidityService(FileSystemCAS(empty_root, tenant_id=TENANT, cell_id=CELL))
    typed_original = SourceAdmissionCarrier.model_validate_json(json.dumps(carrier), strict=True)
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        nonempty_missing = empty_owner.read_source_current_use(
            (typed_original,), require_selected=False
        )
    assert nonempty_missing.status == "unknown" and nonempty_missing.generation == 0
    assert nonempty_missing.committed_root is None
    assert nonempty_missing.reason_codes == ("source_admission_carrier_not_committed",)
    changed = []
    for field, value in (
        ("tenant_id", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        ("cell_id", "foreign-cell"),
    ):
        changed.append({**carrier, field: value})
    original_snapshot = env["oracle"].cas.selected(carrier["snapshot_ref"])
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        wrong_profile_ref = env["store"].put_bytes(
            original_snapshot["raw"],
            ArtifactWriteOptions(
                kind=original_snapshot["manifest"]["kind"],
                media_type=original_snapshot["manifest"]["media_type"],
                schema=SchemaInfo(
                    name=original_snapshot["manifest"]["schema"]["name"], version="99.0"
                ),
                canon=CanonInfo.model_validate(original_snapshot["manifest"]["canon"]),
            ),
            return_selected_profile=True,
        )
    assert str(wrong_profile_ref.artifact_id) == carrier["snapshot_ref"]["artifact_id"]
    assert (
        wrong_profile_ref.manifest_profile_sha256
        != carrier["snapshot_ref"]["manifest_profile_sha256"]
    )
    env["oracle"].cas.selected(wrong_profile_ref.model_dump(mode="json"))
    wrong_profile = copy.deepcopy(carrier)
    wrong_profile["snapshot_ref"] = wrong_profile_ref.model_dump(mode="json")
    changed.append(wrong_profile)
    registration = results["a"]["binding"]["materialization"]["registration"]
    selected_view = env["oracle"].cas.selected(registration["effective_view_contract_ref"])
    selected_use = env["oracle"].cas.selected(registration["use_contract_ref"])
    wrong_refs = {}
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        for name, selected, value in (
            (
                "view",
                selected_view,
                {
                    **selected_view["value"],
                    "statement": 'SELECT scenario AS baseline, baseline AS scenario, note FROM "policy_inputs" LIMIT 100',
                },
            ),
            ("use", selected_use, {**selected_use["value"], "use_key": "test.different_use"}),
        ):
            manifest = selected["manifest"]
            ref = env["store"].put_json(
                value,
                ArtifactWriteOptions(
                    kind=manifest["kind"],
                    media_type=manifest["media_type"],
                    schema=SchemaInfo.model_validate(manifest["schema"]),
                ),
                return_selected_profile=True,
            )
            wrong_refs[name] = ref.model_dump(mode="json")
            env["oracle"].cas.selected(wrong_refs[name])
    wrong_use = copy.deepcopy(carrier)
    wrong_use["use_contract_ref"] = wrong_refs["use"]
    changed.append(wrong_use)
    wrong_view = copy.deepcopy(carrier)
    wrong_view["admission_scope_digest"] = digest(
        {
            **{key: registration[key] for key in ("tenant_id", "cell_id", "source_incarnation_id")},
            "effective_view_contract_ref": wrong_refs["view"],
            "use_contract_ref": registration["use_contract_ref"],
        }
    )
    changed.append(wrong_view)
    snapshot = committed_snapshot(env["cas_root"])
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        for row in changed:
            typed = SourceAdmissionCarrier.model_validate_json(json.dumps(row), strict=True)
            value = env["owner"].read_source_current_use((typed,), require_selected=False)
            assert value.status == "unknown"
            assert value.reason_codes == ("source_admission_carrier_not_committed",)
            assert value.predicate_provenance == "not_established"
            assert value.generation == snapshot["root"]["generation"]
            assert value.committed_root == snapshot["root_digest"]
        # Exercise the actual owner's fail-closed legacy input boundary.
        legacy = env["owner"].read_source_current_use(
            ({"status": "current", "source": carrier["snapshot_ref"]},), require_selected=False
        )
        assert legacy.status == "unknown" and legacy.predicate_provenance == "not_established"
        restored_current = env["owner"].read_source_current_use(
            (typed_original,), require_selected=False
        )
        env["oracle"].check_projection(
            restored_current.model_dump(mode="json"), [carrier], snapshot
        )
    assert committed_snapshot(env["cas_root"]) == snapshot

    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        historical_receipt, historical_materialization, predecessor = env[
            "owner"
        ].resolve_source_materialization_history(
            typed_original, event_id=results["a"]["body"]["event_id"]
        )
    assert historical_receipt.model_dump(mode="json") == results["a"]["response"]["receipt"]
    assert (
        historical_materialization.model_dump(mode="json")
        == env["oracle"].materializations[results["a"]["body"]["event_id"]]
    )
    assert predecessor == results["a"]["body"]["expected_predecessor"]
