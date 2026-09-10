from __future__ import annotations

import copy
import json
from pathlib import Path

from tools.quality.validation import check_layer3_gy_openalex_artifacts

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_layer3_gy_openalex_artifacts_recompute_from_recorded_real_sources() -> None:
    report = check_layer3_gy_openalex_artifacts.validate(REPO_ROOT)
    assert report["status"] == "pass"
    assert (
        report["accuracy"]["measurement_basis"] == "extractor_execution_and_constructed_negatives"
    )
    assert report["accuracy"]["precision"] is None and report["accuracy"]["recall"] is None
    assert report["ingest"]["identity_sets_reconciled"] is True
    assert report["ingest"]["no_hit_frontier"]
    assert all(
        row["authority_tier"] == "candidate_unverified" and row["design_family"] is None
        for row in report["ingest"]["persisted_claims"]
    )


def test_layer3_gy_openalex_artifacts_corrupt_accuracy_drift_fails() -> None:
    report = check_layer3_gy_openalex_artifacts.validate(
        REPO_ROOT,
        corrupt_field_drift_check=True,
    )

    assert report["status"] == "fail"
    assert {"code": "layer3_gy_openalex_corrupt_field_drift_detected"} in report["issues"]


def test_layer3_gy_openalex_accuracy_report_refuses_unappointed_positive_accuracy() -> None:
    gate = check_layer3_gy_openalex_artifacts
    payload = gate._build_current_accuracy_payload(REPO_ROOT)
    payload["accuracy"]["precision"] = 1.0
    payload["accuracy"]["recall"] = 1.0
    payload["accuracy_provenance"]["real_agent"] = True
    payload["accuracy_provenance"]["adjudicator_appointment"] = "self-declared-model-reviewer"
    issues = []
    gate.validate_accuracy_report_payload(payload, expected=payload, issues=issues)
    assert {"code": "layer3_gy_openalex_accuracy_current_epoch_invalid"} in issues


def test_layer3_gy_openalex_accuracy_report_rejects_asserted_verifier_provenance() -> None:
    gate = check_layer3_gy_openalex_artifacts
    payload = gate._build_current_accuracy_payload(REPO_ROOT)
    payload["accuracy_provenance"]["predicate_basis"] = "consumer_asserted"
    issues = []
    gate.validate_accuracy_report_payload(payload, expected=payload, issues=issues)
    assert {"code": "layer3_gy_openalex_accuracy_substantive_recompute_drift"} in issues


def test_current_openalex_proof_enumerates_full_provider_population_and_withholds_accuracy() -> (
    None
):
    gate = check_layer3_gy_openalex_artifacts
    payloads = gate.build_live_payloads(REPO_ROOT)
    config = json.loads((REPO_ROOT / gate.CONFIG_PATH).read_text())
    expected = {
        (relative, row["id"])
        for relative in config["provenance"]["recorded_response_fixtures"]
        for row in json.loads((REPO_ROOT / relative).read_text())["results"]
    }
    accuracy = payloads[gate.ACCURACY_PATH]["accuracy"]
    actual = {
        (row["source_ref"].split("@sha256:")[0], row["openalex_id"])
        for row in accuracy["observations"]
    }
    assert actual == expected
    assert accuracy["precision"] is None and accuracy["recall"] is None
    assert accuracy["accuracy_status"] == "withheld_pending_adjudicator_appointment"
    ingest = payloads[gate.INGEST_PATH]["ingest"]
    assert ingest["identity_sets_reconciled"] is True
    assert ingest["owner_validation_control"] == {
        "baseline_fake_admitted": False,
        "removed_verifier_fake_admitted": True,
    }
    growth = ingest["data_only_growth_control"]
    baseline_ids = {row["claim_id"] for row in ingest["persisted_claims"]}
    assert growth["new_claim_id"] not in baseline_ids
    assert growth["new_span_not_in_baseline"] is True
    assert (
        growth["population_disposition"] == "isolated_engineering_selection_not_accuracy_population"
    )


def test_current_openalex_accuracy_checker_recomputes_claim_and_span_content() -> None:
    gate = check_layer3_gy_openalex_artifacts
    baseline = gate.build_live_payloads(REPO_ROOT)[gate.ACCURACY_PATH]
    corrupted = copy.deepcopy(baseline)
    mutated = []
    for observation in corrupted["accuracy"]["observations"]:
        for prediction in observation["predictions"]:
            mutated.append(prediction["claim"]["claim_id"])
            prediction["claim"]["claim_text"] = "Wholly fabricated claim text."
            for span in prediction["claim"]["supporting_spans"]:
                span["text"] = "Wholly fabricated span text."
    assert mutated
    issues = []
    gate.validate_accuracy_report_payload(corrupted, expected=corrupted, issues=issues)
    assert {"code": "layer3_gy_openalex_accuracy_substantive_recompute_drift"} in issues


def test_openalex_predecessor_guard_notices_new_alias_caller(monkeypatch) -> None:
    import pytest

    gate = check_layer3_gy_openalex_artifacts
    assert gate.recompute_openalex_accuracy_strangle(REPO_ROOT)["remaining_callers"] == []
    target = REPO_ROOT / "src/polisyos/ir/analytics/literature.py"
    actual_read = Path.read_text

    def new_caller(path, *args, **kwargs):
        value = actual_read(path, *args, **kwargs)
        if path == target:
            return (
                value
                + "\nfrom polisyos.ir.analytics.literature import _evaluate_gold_span_support_accuracy as old_accuracy\nold_accuracy(None, span_support_client=None)\n"
            )
        return value

    monkeypatch.setattr(Path, "read_text", new_caller)
    with pytest.raises(ValueError, match="openalex_unfenced_predecessor_reference"):
        gate.recompute_openalex_accuracy_strangle(REPO_ROOT)


def test_openalex_history_partition_and_raw_integrity_are_enforced(tmp_path) -> None:
    gate = check_layer3_gy_openalex_artifacts
    history_id = "policy-design-case-layer3-gy-openalex-history-artifacts"
    historical = (
        "architecture/policy_design_case/layer3_gy_openalex_accuracy_report.json",
        "architecture/policy_design_case/layer3_gy_openalex_skg_ingest_records.json",
    )
    for path in (gate.CONFIG_PATH, gate.GOLD_PATH, *historical):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / path).read_bytes())
    family = (
        f"[[family]]\nid={json.dumps(gate.FAMILY_ID)}\n"
        f"outputs={json.dumps(gate.OUTPUTS)}\n"
        'lifecycle="generated_committed"\ncheck_command=["--check"]\n'
        'regenerate_commands=["--write"]\n'
    )
    source = (
        f"[[family]]\nid={json.dumps(gate.SOURCE_FAMILY_ID)}\n"
        f"outputs={json.dumps([gate.CONFIG_PATH, gate.GOLD_PATH])}\n"
        'lifecycle="source_committed"\nsource_integrity_sha256={ '
        + ", ".join(
            f"{json.dumps(path)}={json.dumps(gate._sha256(REPO_ROOT / path))}"
            for path in (gate.CONFIG_PATH, gate.GOLD_PATH)
        )
        + " }\n"
    )
    history = (
        f"[[family]]\nid={json.dumps(history_id)}\n"
        f"outputs={json.dumps(historical)}\n"
        'lifecycle="source_committed"\nsource_integrity_sha256={ '
        + ", ".join(
            f"{json.dumps(path)}={json.dumps(gate._sha256(REPO_ROOT / path))}"
            for path in historical
        )
        + " }\n"
    )
    registry = tmp_path / "architecture/generated_artifacts.toml"
    baseline = family + source + history
    registry.write_text(baseline)
    issues = []
    gate._validate_generated_artifacts_registration(tmp_path, issues)
    assert issues == []
    for path in historical:
        target = tmp_path / path
        original = target.read_bytes()
        target.write_bytes(original + b"\n")
        changed = []
        gate._validate_generated_artifacts_registration(tmp_path, changed)
        assert {"code": "layer3_gy_openalex_history_integrity_drift", "path": path} in changed
        target.write_bytes(original)
    for mutated in (
        baseline.replace(f"id={json.dumps(history_id)}", 'id="unclaimed-history"'),
        baseline.replace(f"outputs={json.dumps(historical)}", "outputs=[]"),
        family
        + source
        + history.replace('lifecycle="source_committed"', 'lifecycle="generated_committed"'),
    ):
        registry.write_text(mutated)
        changed = []
        gate._validate_generated_artifacts_registration(tmp_path, changed)
        assert {"code": "layer3_gy_openalex_history_partition_invalid"} in changed


def test_current_openalex_source_refs_bind_exact_configured_bytes() -> None:
    gate = check_layer3_gy_openalex_artifacts
    _, sources = gate._recorded_provider_population(REPO_ROOT)
    config = json.loads((REPO_ROOT / gate.CONFIG_PATH).read_text())
    paths = config["provenance"]["recorded_response_fixtures"]
    expected = {f"{path}@{gate._sha256(REPO_ROOT / path)}" for path in paths}
    actual = {row["source_ref"] for row in sources}
    assert len(sources) == len(paths) == len(expected)
    assert actual == expected


def test_recorded_source_preflight_refuses_unknown_or_invalid_capture_time() -> None:
    import pytest

    gate = check_layer3_gy_openalex_artifacts
    config = json.loads((REPO_ROOT / gate.CONFIG_PATH).read_text())
    paths = config["provenance"]["recorded_response_fixtures"]
    assert len(paths) == len(set(paths))
    for relative in paths:
        original = json.loads((REPO_ROOT / relative).read_text())
        query = original["_recording"]["query"]
        gate._assert_recorded_openalex_fixture(
            original, path=relative, query=query, allow_empty=True
        )
        for value in (None, "", "not-a-time", "2026-06-23", "2026-06-23T01:00:00+01:00"):
            mutated = copy.deepcopy(original)
            mutated["_recording"]["captured_at"] = value
            with pytest.raises(ValueError, match="capture"):
                gate._assert_recorded_openalex_fixture(
                    mutated, path=relative, query=query, allow_empty=True
                )
        mutated = copy.deepcopy(original)
        del mutated["_recording"]["captured_at"]
        with pytest.raises(ValueError, match="capture"):
            gate._assert_recorded_openalex_fixture(
                mutated, path=relative, query=query, allow_empty=True
            )


def test_current_artifact_reader_requires_an_object_and_checks_empty_content(tmp_path) -> None:
    gate = check_layer3_gy_openalex_artifacts
    path = tmp_path / "current-artifact.json"
    for value in (None, False, [], [{"gy_lifecycle_marker": "retained"}], "text", 0):
        path.write_text(json.dumps(value))
        issues = []
        assert gate._read_json(path, issues) is None
        assert issues == [
            {"code": "layer3_gy_openalex_artifact_object_required", "path": str(path)}
        ]
    path.write_text("{}")
    issues = []
    payload = gate._read_json(path, issues)
    assert payload == {} and issues == []
    gate.validate_accuracy_report_payload(
        payload, expected=payload, issues=issues, repo_root=REPO_ROOT
    )
    assert issues == [{"code": "layer3_gy_openalex_accuracy_current_epoch_invalid"}]
    path.unlink()
    missing = []
    assert gate._read_json(path, missing) is None
    assert missing == [{"code": "layer3_gy_openalex_artifact_missing", "path": str(path)}]


def test_current_accuracy_recomputation_uses_supplied_complete_source_root(tmp_path) -> None:
    import tempfile

    gate = check_layer3_gy_openalex_artifacts
    config = json.loads((REPO_ROOT / gate.CONFIG_PATH).read_text())
    paths = config["provenance"]["recorded_response_fixtures"]
    original = gate._build_current_accuracy_payload(REPO_ROOT)
    with tempfile.TemporaryDirectory(dir=tmp_path) as directory:
        root = Path(directory)
        relocated = []
        for relative in paths:
            target_path = "relocated/" + relative
            target = root / target_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO_ROOT / relative).read_bytes())
            relocated.append(target_path)
        config["provenance"]["recorded_response_fixtures"] = relocated
        target = root / gate.CONFIG_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(config))
        current = gate._build_current_accuracy_payload(root)
        assert {
            (row["openalex_id"], row["query"]) for row in original["accuracy"]["observations"]
        } == {(row["openalex_id"], row["query"]) for row in current["accuracy"]["observations"]}
        assert current != original
        issues = []
        gate.validate_accuracy_report_payload(
            current, expected=current, issues=issues, repo_root=root
        )
        assert issues == []
