from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.quality.validation import check_layer3_gy_promotion_contract as checker


def _write_frozen_contract(root: Path) -> bytes:
    path = root / checker.OUTPUT_PATH
    path.parent.mkdir(parents=True)
    data = b'{"schema_version":"synthetic-test-input"}\n'
    path.write_bytes(data)
    return data


def test_missing_frozen_output_is_unrun_with_unavailable_input_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(checker, "_repo_root", lambda: tmp_path)

    assert checker.main(["--check", "--output-format", "json"]) == 2
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "unrun"
    assert report["verdict"] == "UNRUN"
    assert report["issues"] == [
        {"code": "promotion_contract_input_missing", "path": checker.OUTPUT_PATH}
    ]
    assert report["measurement"]["complete_verdict"] is False
    assert report["measurement"]["complete_verdict_scope"] is None
    assert report["measurement"]["verdict_scope"].startswith("No complete artifact/replay verdict")
    assert report["measurement"]["inputs"] == [
        {
            "path": checker.OUTPUT_PATH,
            "operation": "read_bytes",
            "status": "unreadable",
            "error": "FileNotFoundError",
        }
    ]


def test_verdict_scope_is_bounded_when_source_selection_is_partial(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    frozen_bytes = _write_frozen_contract(tmp_path)
    monkeypatch.setattr(checker, "validate_payload", lambda _: {"status": "pass", "issues": []})
    monkeypatch.setattr(
        checker,
        "build_contract_json_for_write",
        lambda _: frozen_bytes.decode("utf-8"),
    )
    monkeypatch.setattr(checker, "_repo_root", lambda: tmp_path)

    assert checker.main(["--check", "--output-format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    measurement = report["measurement"]

    assert report["status"] == "pass"
    assert measurement["complete_verdict"] is True
    assert measurement["complete_verdict_scope"] == measurement["verdict_scope"]
    assert measurement["selection_status"] == "partial"
    assert measurement["verdict_scope"].startswith(
        "Frozen artifact validation and exact byte comparison with one canonical owner replay"
    )
    assert any(
        "loaded-code and data-input denominator" in item
        for item in measurement["unresolved_by_construction"]
    )


def test_invalid_frozen_json_has_a_parse_only_fail_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / checker.OUTPUT_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{invalid-json")
    monkeypatch.setattr(checker, "_repo_root", lambda: tmp_path)

    assert checker.main(["--check", "--output-format", "json"]) == 1
    report = json.loads(capsys.readouterr().out)
    measurement = report["measurement"]

    assert report["status"] == "fail"
    assert report["issues"][0]["code"] == "promotion_contract_frozen_payload_invalid"
    assert measurement["complete_verdict"] is True
    assert measurement["complete_verdict_scope"] == measurement["verdict_scope"]
    assert measurement["verdict_scope"].startswith(
        "Frozen bytes were read and rejected as invalid JSON"
    )
    assert "owner replay was not run" in measurement["verdict_scope"]


def test_recognized_reconciliation_drift_is_fail_not_unrun(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_frozen_contract(tmp_path)
    monkeypatch.setattr(checker, "validate_payload", lambda _: {"status": "pass", "issues": []})

    def reject_epoch_transition(_: Path) -> str:
        raise checker._PromotionContractReconciliationDriftError(
            "promotion_comparison_admission_manifest_drift",
            details={"stage": "unauthorized_manifest_epoch_transition"},
        )

    monkeypatch.setattr(checker, "build_contract_json_for_write", reject_epoch_transition)
    monkeypatch.setattr(checker, "_repo_root", lambda: tmp_path)

    assert checker.main(["--check", "--output-format", "json"]) == 1
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "fail"
    assert report["issues"] == [
        {
            "code": "promotion_comparison_admission_manifest_drift",
            "details": {"stage": "unauthorized_manifest_epoch_transition"},
        }
    ]
    assert report["measurement"]["complete_verdict_scope"] == report["measurement"]["verdict_scope"]
    assert "typed owner reconciliation refusal" in report["measurement"]["verdict_scope"]
    assert "byte equality was not established" in report["measurement"]["verdict_scope"]


def test_live_v6_to_v8_manifest_epoch_is_a_typed_fail_not_an_exception(
    capsys: pytest.CaptureFixture[str],
) -> None:
    frozen_path = checker._repo_root() / checker.OUTPUT_PATH
    assert frozen_path.is_file()

    assert checker.main(["--check", "--output-format", "json"]) == 1
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "fail"
    assert report["verdict"] == "FAIL"
    issue = next(
        item
        for item in report["issues"]
        if item["code"] == "promotion_comparison_admission_manifest_drift"
    )
    details = issue["details"]
    assert details["stage"] == "unauthorized_manifest_epoch_transition"
    assert {item["owner_rule"].rsplit(".", 1)[-1] for item in details["frozen_manifest"]} == {"v5"}
    assert {item["owner_rule"].rsplit(".", 1)[-1] for item in details["live_manifest"]} == {"v7"}
    assert set(details["frozen_receipt_schema_versions"].values()) == {
        "policyos.policy_design_case.layer3_gy.n9_promotion.v6"
    }
    assert set(details["live_receipt_schema_versions"].values()) == {
        "policyos.policy_design_case.layer3_gy.n9_promotion.v8"
    }
    assert details["authorized_transition_predicates"] == {
        "v6_source_scope_reissue": False,
        "v3_to_v6_comparison_reissue": False,
    }
    measurement = report["measurement"]
    assert report["status"] == "fail"
    assert measurement["complete_verdict"] is True
    assert measurement["complete_verdict_scope"] == measurement["verdict_scope"]
    assert measurement["selection_status"] == "partial"
    assert "typed owner reconciliation refusal" in measurement["verdict_scope"]
    assert "byte equality was not established" in measurement["verdict_scope"]
    assert any(
        "loaded-code and data-input denominator" in item
        for item in measurement["unresolved_by_construction"]
    )


def test_replay_exception_is_unrun_instead_of_a_verdict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_frozen_contract(tmp_path)
    monkeypatch.setattr(checker, "validate_payload", lambda _: {"status": "pass", "issues": []})

    def replay_unavailable(_: Path) -> str:
        raise RuntimeError("verification dependency unavailable")

    monkeypatch.setattr(checker, "build_contract_json_for_write", replay_unavailable)
    monkeypatch.setattr(checker, "_repo_root", lambda: tmp_path)

    assert checker.main(["--check", "--output-format", "json"]) == 2
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "unrun"
    assert report["verdict"] == "UNRUN"
    assert report["measurement"]["complete_verdict"] is False
    assert report["measurement"]["complete_verdict_scope"] is None
    assert report["measurement"]["verdict_scope"].startswith("No complete artifact/replay verdict")
    assert report["issues"] == [
        {
            "code": "promotion_contract_replay_unrun",
            "error_type": "RuntimeError",
            "error": "verification dependency unavailable",
        }
    ]


def test_identical_frozen_bytes_keep_the_bounded_pass_control(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    frozen_bytes = _write_frozen_contract(tmp_path)
    monkeypatch.setattr(checker, "validate_payload", lambda _: {"status": "pass", "issues": []})
    monkeypatch.setattr(
        checker,
        "build_contract_json_for_write",
        lambda _: frozen_bytes.decode("utf-8"),
    )
    monkeypatch.setattr(checker, "_repo_root", lambda: tmp_path)

    assert checker.main(["--check", "--output-format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "pass"
    assert report["verdict"] == "PASS"
