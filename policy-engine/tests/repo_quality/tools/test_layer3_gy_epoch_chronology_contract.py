from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from polisyos.foundry.methods.catalog import dependency_profile as dependency_profile_module
from tools.quality.validation import check_layer3_gy_epoch_chronology_contract as checker
from tools.quality.validation import check_layer3_gy_value_gate_contract as n8

REPO_ROOT = Path(__file__).resolve().parents[3]


def _receipt_hash(payload: dict[str, object]) -> str:
    body = {key: value for key, value in payload.items() if key != "receipt_sha256"}
    encoded = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _failed_dependency_diagnostic(companion: object) -> object:
    profile = companion.profile_discriminant
    observations = tuple(
        dependency_profile_module.InstalledDistributionObservation(
            name=row.name,
            version="incompatible-version" if index == 0 else row.version,
        )
        for index, row in enumerate(profile.resolved_distributions)
    )
    result = dependency_profile_module.diagnose_dependency_environment(
        discriminant=profile,
        observed_distributions=dependency_profile_module.AmbientDependencyEnvironmentObservation(
            observation_kind="ambient",
            distributions=observations,
        ),
    )
    assert result.status == "fail"
    return result


def test_chronology_validation_result_separates_governing_and_ambient_channels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dependency mismatch cannot alter chronology acceptance issues."""

    companion = n8.build_dependency_discriminant_companion(
        repo_root=REPO_ROOT,
        source_freeze=n8.dependency_discriminant_source_freeze(REPO_ROOT),
    )
    reader = getattr(checker, "read_foundry_dependency_discriminant", None)
    result_builder = getattr(checker, "validate_payload_result", None)
    assert callable(reader), "missing behavior: chronology discriminant reader"
    assert callable(result_builder), "missing behavior: chronology ValidationResult"
    payload: dict[str, object] = {}
    governing = checker.validate_payload(payload, repo_root=REPO_ROOT)

    diagnostic = _failed_dependency_diagnostic(companion)
    monkeypatch.setattr(n8, "_current_dependency_environment_diagnostic", lambda _profile: diagnostic)
    result = result_builder(
        payload,
        repo_root=REPO_ROOT,
        companion=companion,
        diagnostic_verification=diagnostic,
    )

    assert isinstance(result, checker.ValidationResult)
    assert result.governing_result == governing
    assert result.governing_issues == governing
    assert result.content_ref == companion.content_ref
    assert result.discriminant_ref == companion.profile_discriminant.discriminant_ref
    assert result.status == "fail"
    assert result.first_case.coordinate.startswith("distribution:")
    assert checker.validate_payload(payload, repo_root=REPO_ROOT) == governing


def test_common_envelope_binds_semantic_status_independently() -> None:
    report = checker.semantic_envelope(
        mode="check",
        status="pass",
        issues=(),
        evidence={"terminal": "policy_admission_missing"},
    )

    assert set(report) >= {"validator", "mode", "status", "issues", "receipt_sha256"}
    assert report["validator"] == checker.VALIDATOR_ID
    assert report["receipt_sha256"] == _receipt_hash(report)
    tampered = dict(report)
    tampered["status"] = "fail"
    assert tampered["receipt_sha256"] != _receipt_hash(tampered)


def test_live_probe_runs_real_epoch_prefix_dv_claim_n9_and_public_paths(tmp_path: Path) -> None:
    payload = checker.build_live_payload(REPO_ROOT, scratch_root=tmp_path)

    assert payload["production_epoch"]["terminal"] == "policy_admission_missing"
    assert payload["full_prefix"]["status"] == "verified"
    assert payload["decision_validity"]["state"] == "completed"
    assert payload["decision_validity"]["pending_freeze_observed"] is True
    assert payload["decision_validity"]["pending_trace"][0] == {
        "event": "save_epoch_pending",
        "applied_packet_count": 0,
    }
    assert payload["claim_bridge"]["terminal"] == "claim_ledger_owner_not_established"
    assert payload["n9"]["terminal"] == "epoch_validity_refused:policy_admission_missing"
    assert payload["public_open_world"] == {
        "status": "not_established",
        "limitation_code": "deployment_scope_not_established",
        "vector_artifact_ref": payload["public_open_world"]["vector_artifact_ref"],
        "limitation_count": 1,
        "carrier_substitution_terminal": "open_world_vector_query_mismatch",
    }
    assert (
        payload["public_open_world"]["vector_artifact_ref"]
        == payload["n9"]["carrier_vector_artifact_ref"]
    )
    assert payload["terminal_matrix"]["whole_history_authenticity"] == "not_established"
    assert len(payload["terminal_matrix"]) == 11
    assert payload["source_denominator"]["walks_agree"] is True


def test_candidate_output_is_scratch_only_and_content_bound(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    report = checker.run_mode(
        mode="rederive-audit",
        repo_root=REPO_ROOT,
        expected_source_freeze=checker.git_head(REPO_ROOT),
        candidate_output=candidate,
    )

    assert report["status"] == "pass"
    assert candidate.is_file()
    assert report["candidate_sha256"] == (
        "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
    )
    assert report["receipt_sha256"] == _receipt_hash(report)
    with pytest.raises(ValueError, match="candidate_output_must_be_outside_repository"):
        checker.run_mode(
            mode="rederive-audit",
            repo_root=REPO_ROOT,
            expected_source_freeze=checker.git_head(REPO_ROOT),
            candidate_output=REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_epoch_chronology_contract.json",
        )
    with pytest.raises(ValueError, match="candidate_output_must_be_outside_repository"):
        checker.run_mode(
            mode="rederive-audit",
            repo_root=REPO_ROOT,
            expected_source_freeze=checker.git_head(REPO_ROOT),
            candidate_output=REPO_ROOT.parent / "gy-n12-candidate.json",
        )


def test_source_flip_mutations_keep_markers_but_each_make_the_probe_red(
    tmp_path: Path,
) -> None:
    report = checker.run_source_flip_mutations(REPO_ROOT, scratch_root=tmp_path)

    assert tuple(row["mutation_id"] for row in report) == checker.SOURCE_FLIP_MUTATION_IDS
    assert all(row["marker_retained"] is True for row in report)
    assert all(row["result"] == "RED" for row in report)
    assert all(row["child_exit_code"] == 1 for row in report)
    assert all(row["child_validator"] == checker.VALIDATOR_ID for row in report)
    assert all(row["child_mode"] == "check" for row in report)
    assert all(row["child_status"] == "fail" for row in report)
    assert all(row["child_receipt_valid"] is True for row in report)
    assert all(row["source_before_sha256"] == row["source_restored_sha256"] for row in report)
    assert all(row["source_before_sha256"] != row["source_mutated_sha256"] for row in report)
    assert all(row["source_restored_exactly"] is True for row in report)


def test_allocation_history_hash_is_recomputed_before_terminal_state_is_used() -> None:
    allocation_path = (
        REPO_ROOT / "architecture/production_quality/chronology_capability_allocation.toml"
    )
    raw = copy.deepcopy(checker.tomllib.loads(allocation_path.read_text(encoding="utf-8")))
    matching_entries = [
        entry
        for entry in raw["entries"]
        if entry["payload"]["subject_key"] == "whole_history_authenticity"
    ]
    assert len(matching_entries) == 1
    matching_entries[0]["entry_hash"] = "sha256:" + "0" * 64

    with pytest.raises(RuntimeError, match="chronology_allocation_entry_hash_invalid"):
        checker._allocation_latest_state_from_mapping(raw)


@pytest.mark.parametrize(
    ("ordinal", "field", "value"),
    [
        (10, "row_kind", "capability"),
        (0, "canonical_owner_ref", "candidate.self"),
    ],
)
def test_allocation_history_rejects_rehashed_semantic_corruption(
    ordinal: int,
    field: str,
    value: str,
) -> None:
    allocation_path = (
        REPO_ROOT / "architecture/production_quality/chronology_capability_allocation.toml"
    )
    raw = copy.deepcopy(checker.tomllib.loads(allocation_path.read_text(encoding="utf-8")))
    raw["entries"][ordinal]["payload"][field] = value
    previous_hash: str | None = None
    for current_ordinal, entry in enumerate(raw["entries"]):
        entry["ordinal"] = current_ordinal
        entry["predecessor_kind"] = "genesis" if current_ordinal == 0 else "entry"
        if current_ordinal == 0:
            entry.pop("previous_entry_hash", None)
        else:
            entry["previous_entry_hash"] = previous_hash
        canonical_entry = {
            "ordinal": current_ordinal,
            "predecessor_kind": entry["predecessor_kind"],
            "previous_entry_hash": previous_hash,
            "payload": dict(entry["payload"]),
        }
        canonical = checker.chronology_contract._canonical_raw_bytes(canonical_entry)
        entry["entry_hash"] = checker.chronology_contract._sha256_digest(
            checker.ALLOCATION_ENTRY_PREFIX,
            len(canonical).to_bytes(8, "big"),
            canonical,
        )
        previous_hash = entry["entry_hash"]

    with pytest.raises(RuntimeError, match="chronology_allocation_payload_semantics_invalid"):
        checker._allocation_latest_state_from_mapping(raw)


def test_allocation_history_rejects_the_stale_cluster2_prefix(tmp_path: Path) -> None:
    source = (
        REPO_ROOT / "architecture/production_quality/chronology_capability_allocation.toml"
    ).read_text(encoding="utf-8")
    sections = source.split("[[entries]]")
    assert len(sections) == 15
    cluster2_only = "[[entries]]".join(sections[:12])
    allocation = tmp_path / "architecture/production_quality/chronology_capability_allocation.toml"
    allocation.parent.mkdir(parents=True)
    allocation.write_text(cluster2_only, encoding="utf-8")

    with pytest.raises(RuntimeError, match="chronology_allocation_history_missing"):
        checker._allocation_latest_state(tmp_path)


def test_corrupt_field_drift_rejects_every_candidate_mutation(tmp_path: Path) -> None:
    payload = checker.build_live_payload(REPO_ROOT, scratch_root=tmp_path)
    results = checker.corrupt_field_drift_results(payload, repo_root=REPO_ROOT)

    assert {row["case_id"] for row in results} == set(checker.CORRUPT_FIELD_CASE_IDS)
    assert all(row["rejected"] is True for row in results)
    expected_codes = {
        "source_freeze_substituted": "source_freeze_mismatch",
        "production_terminal_substituted": "production_terminal_invalid",
        "prefix_status_promoted": "full_prefix_not_verified",
        "commitment_head_substituted": "commitment_head_missing",
        "decision_batch_state_substituted": "decision_batch_not_completed",
        "pending_freeze_erased": "pending_freeze_not_observed",
        "claim_terminal_substituted": "claim_bridge_terminal_invalid",
        "n9_terminal_substituted": "n9_terminal_invalid",
        "open_world_status_promoted": "open_world_status_invalid",
        "open_world_limitation_code_substituted": "open_world_limitation_code_invalid",
        "open_world_vector_ref_substituted": "public_projection_binding_mismatch",
        "whole_history_label_promoted": "terminal_matrix_mismatch",
    }
    assert {
        row["case_id"]: expected_codes[row["case_id"]] in row["issue_codes"] for row in results
    } == dict.fromkeys(checker.CORRUPT_FIELD_CASE_IDS, True)


def test_cli_modes_are_exact_and_emit_one_json_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = checker.build_parser()
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
        if option.startswith("--")
    }

    assert option_strings == {
        "--help",
        "--check",
        "--rederive-audit",
        "--source-flip-mutations",
        "--corrupt-field-drift-check",
        "--candidate-output",
        "--expected-source-freeze",
        "--output-format",
    }
    modes = (
        ("--check", "check"),
        ("--rederive-audit", "rederive-audit"),
        ("--source-flip-mutations", "source-flip-mutations"),
        ("--corrupt-field-drift-check", "corrupt-field-drift-check"),
    )
    for option, expected_mode in modes:
        exit_code = checker.main(
            [
                option,
                "--expected-source-freeze",
                "0" * 40,
                "--output-format",
                "json",
            ]
        )
        lines = capsys.readouterr().out.splitlines()
        assert len(lines) == 1
        report = json.loads(lines[0])
        assert exit_code == 1
        assert report["mode"] == expected_mode
        assert report["status"] == "fail"
        assert report["issues"] == [{"code": "source_freeze_mismatch"}]
        assert report["receipt_sha256"] == _receipt_hash(report)
