"""Exercise CLI read disclosure and unchanged rejection using synthetic custody rows."""

import json
from hashlib import sha256
from pathlib import Path

import pytest
from _helpers.custody_markdown import rebound_register

from tools.lib import fs as filesystem
from tools.quality.validation import check_trust_claim_posture as checker

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    source = tmp_path / "src/example.py"
    source.parent.mkdir()
    source.write_text('authoritative_for = ("example",)\n')
    identity = tmp_path / checker._IDENTITY_PATH
    identity.parent.mkdir(parents=True)
    identity.write_bytes((ROOT / checker._IDENTITY_PATH).read_bytes())
    custody = tmp_path / checker._DEBT_REGISTER_PATH
    custody.parent.mkdir(parents=True)
    custody.write_text(
        "\n".join(
            item["source_content"]
            for item in rebound_register("``left`|right``")["custody_appointment_sources"]
        ) + "\n"
    )
    return tmp_path


def call_report(root: Path, capsys, mode: str, compact: bool) -> dict:
    target = root / checker._OUTPUT_PATH
    before = target.read_bytes() if mode == "--check" else None
    assert checker.main(
        ["--repo-root", str(root), mode, *(["--json"] if compact else [])]
    ) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "PASS"
    assert report["measurement"]["complete_verdict"] is True
    assert report["write_attempted"] is (mode == "--write")
    assert report["write_set_complete"] is True
    assert any(
        item.startswith("untyped_derivation_failures:")
        for item in report["measurement"]["unresolved_by_construction"]
    )
    if mode != "--write":
        assert report["write_set"] == []
    if mode == "--check":
        assert target.read_bytes() == before
    return report


def read_fact(report: dict, path: str) -> dict:
    return next(
        item for item in report["measurement"]["inputs"]
        if item["path"] == path and item["operation"] == "read_bytes"
    )


def path_fact(report: dict, path: str, operation: str) -> dict:
    return next(
        item for item in report["measurement"]["inputs"]
        if item["path"] == path and item["operation"] == operation
    )


@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("mode", ["--check-sources", "--write", "--check", "--corrupt-field-drift-check"])
def test_cli_discloses_actual_inputs_and_outside_selector_evidence_stays_unresolved(
    source_repo: Path, capsys, compact: bool, mode: str
) -> None:
    register, _ = checker.compile_claim_posture_register(source_repo)
    checker.write_claim_posture_register(register, output_root=source_repo)
    before = call_report(source_repo, capsys, mode, compact)
    outside = source_repo / "docs/outside-authority.md"
    outside.write_text("authoritative_for: [external_certification]\n")
    after = call_report(source_repo, capsys, mode, compact)
    assert before == after
    measurement = after["measurement"]
    assert measurement["source_python_read_count"] == 1
    assert read_fact(after, "src/example.py")["sha256"] == sha256(
        (source_repo / "src/example.py").read_bytes()
    ).hexdigest()
    custody = checker._DEBT_REGISTER_PATH.as_posix()
    assert read_fact(after, custody)["sha256"] == sha256(
        (source_repo / custody).read_bytes()
    ).hexdigest()
    assert measurement["selectors"]["custody_ids"] == list(checker.CUSTODY_APPOINTMENT_DEBT_IDS)
    assert any("schema_and_evidence_only:" in item for item in measurement["unresolved_by_construction"])
    assert any("unselected_authority_documents:" in item for item in measurement["unresolved_by_construction"])
    assert "docs/outside-authority.md" not in {item["path"] for item in measurement["inputs"]}


@pytest.mark.parametrize("compact", [False, True])
def test_cli_reads_whole_register_but_selects_only_appointed_ids(
    source_repo: Path, capsys, compact: bool
) -> None:
    before = call_report(source_repo, capsys, "--check-sources", compact)
    custody = source_repo / checker._DEBT_REGISTER_PATH
    custody.write_bytes(custody.read_bytes() + b"| `OUTSIDE` | other | `fake` | `active` | `fake` |\n")
    after = call_report(source_repo, capsys, "--check-sources", compact)
    assert before["payload_digest"] == after["payload_digest"]
    path = checker._DEBT_REGISTER_PATH.as_posix()
    assert read_fact(before, path)["sha256"] != read_fact(after, path)["sha256"]
    assert any("unselected_custody_rows:" in item for item in after["measurement"]["unresolved_by_construction"])


@pytest.mark.parametrize("compact", [False, True])
def test_cli_returns_fail_for_present_invalid_custody_contract(
    source_repo: Path, capsys, compact: bool
) -> None:
    custody = source_repo / checker._DEBT_REGISTER_PATH
    custody.write_bytes(custody.read_bytes().replace(b"team-scientist", b"team-forged"))

    exit_code = checker.main(
        ["--repo-root", str(source_repo), "--check-sources", *( ["--json"] if compact else [])]
    )
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 1
    assert "Traceback (most recent call last)" not in output
    assert report["verdict"] == "FAIL"
    assert report["measurement"]["complete_verdict"] is True
    assert report["measurement"]["finding_coverage"].startswith("decisive predicate failure")
    assert report["failure_code"] == "DS11-CUSTODY-APPOINTMENT-CONTRACT"
    assert read_fact(report, checker._DEBT_REGISTER_PATH.as_posix())["sha256"] == sha256(
        custody.read_bytes()
    ).hexdigest()


@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("mutation", ["missing", "unreadable"])
def test_cli_returns_unrun_for_missing_or_unreadable_custody_input(
    source_repo: Path, capsys, monkeypatch, compact: bool, mutation: str
) -> None:
    custody = source_repo / checker._DEBT_REGISTER_PATH
    if mutation == "missing":
        custody.unlink()
    else:
        original = Path.read_bytes

        def denied(path: Path) -> bytes:
            if path == custody:
                raise PermissionError("synthetic unreadable input")
            return original(path)

        monkeypatch.setattr(Path, "read_bytes", denied)

    exit_code = checker.main(
        ["--repo-root", str(source_repo), "--check-sources", *( ["--json"] if compact else [])]
    )
    output = capsys.readouterr().out
    report = json.loads(output)
    expected_status = "absent" if mutation == "missing" else "unreadable"
    custody_facts = [
        item for item in report["measurement"]["inputs"]
        if item["path"] == checker._DEBT_REGISTER_PATH.as_posix()
    ]

    assert exit_code == 2
    assert "Traceback (most recent call last)" not in output
    assert report["verdict"] == "UNRUN"
    assert report["measurement"]["complete_verdict"] is False
    assert report["failure_stage"] == "compile_live_sources"
    assert report["unrun_code"] == "DS11-INSPECTION-INCOMPLETE"
    assert report["error"]
    assert any(item["status"] == expected_status for item in custody_facts)


@pytest.mark.parametrize("compact", [False, True])
def test_cli_missing_generated_target_is_determinate_drift_fail(
    source_repo: Path, capsys, compact: bool
) -> None:
    register, _ = checker.compile_claim_posture_register(source_repo)
    checker.write_claim_posture_register(register, output_root=source_repo)
    target = source_repo / checker._OUTPUT_PATH
    target.unlink()

    exit_code = checker.main(
        ["--repo-root", str(source_repo), "--check", *( ["--json"] if compact else [])]
    )
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 1
    assert "Traceback (most recent call last)" not in output
    assert report["verdict"] == "FAIL"
    assert report["failure_code"] == "DS11-GENERATED-DRIFT"
    assert report["failure_stage"] == "generated_artifact_presence"
    assert report["measurement"]["complete_verdict"] is True
    assert path_fact(report, checker._OUTPUT_PATH.as_posix(), "is_file")["status"] == "absent"
    assert report["write_set"] == []
    assert not target.exists()


@pytest.mark.parametrize("compact", [False, True])
def test_cli_unreadable_generated_target_is_unrun_not_drift_fail(
    source_repo: Path, capsys, monkeypatch, compact: bool
) -> None:
    register, _ = checker.compile_claim_posture_register(source_repo)
    checker.write_claim_posture_register(register, output_root=source_repo)
    target = source_repo / checker._OUTPUT_PATH
    original = Path.read_bytes
    frozen_artifact = original(target)

    def denied(path: Path) -> bytes:
        if path == target:
            raise PermissionError("synthetic unreadable generated artifact")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", denied)
    exit_code = checker.main(
        ["--repo-root", str(source_repo), "--check", *( ["--json"] if compact else [])]
    )
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 2
    assert "Traceback (most recent call last)" not in output
    assert report["verdict"] == "UNRUN"
    assert report["failure_stage"] == "generated_artifact_byte_read"
    assert report["unrun_code"] == "DS11-INSPECTION-INCOMPLETE"
    assert report["measurement"]["complete_verdict"] is False
    assert path_fact(report, checker._OUTPUT_PATH.as_posix(), "read_bytes")["status"] == "unreadable"
    assert report["write_set"] == []
    assert original(target) == frozen_artifact


@pytest.mark.parametrize("compact", [False, True])
def test_cli_rejects_same_byte_generated_target_symlink_escape_before_read(
    source_repo: Path, capsys, monkeypatch, compact: bool
) -> None:
    register, payload = checker.compile_claim_posture_register(source_repo)
    checker.write_claim_posture_register(register, output_root=source_repo)
    inside_control = call_report(source_repo, capsys, "--check", compact)
    assert inside_control["verdict"] == "PASS"
    target = source_repo / checker._OUTPUT_PATH
    outside = source_repo.parent / "outside-identical-posture.json"
    outside.write_bytes(payload)
    target.unlink()
    target.symlink_to(outside)
    real_reader = filesystem.measured_read_bytes
    reads: list[Path] = []

    def record_read(path: Path) -> bytes:
        reads.append(path.resolve())
        return real_reader(path)

    monkeypatch.setattr(filesystem, "measured_read_bytes", record_read)
    exit_code = checker.main(
        ["--repo-root", str(source_repo), "--check", *( ["--json"] if compact else [])]
    )
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 1
    assert "Traceback (most recent call last)" not in output
    assert report["verdict"] == "FAIL"
    assert report["failure_code"] == "DS11-GENERATED-DRIFT"
    assert report["failure_stage"] == "generated_artifact_containment"
    assert report["measurement"]["complete_verdict"] is True
    assert outside.resolve() not in reads
    assert target.is_symlink()
    assert outside.read_bytes() == payload
    assert report["write_set"] == []


@pytest.mark.parametrize("compact", [False, True])
def test_cli_selected_source_growth_changes_receipt_and_fails_generated_drift(
    source_repo: Path, capsys, compact: bool
) -> None:
    before = call_report(source_repo, capsys, "--write", compact)
    (source_repo / "src/added.py").write_text('authoritative_for = ("new_claim",)\n')
    after = call_report(source_repo, capsys, "--check-sources", compact)
    assert after["measurement"]["source_python_read_count"] == 2
    assert after["source_set_digest"] != before["source_set_digest"]
    assert after["payload_digest"] != before["payload_digest"]
    exit_code = checker.main(
        ["--repo-root", str(source_repo), "--check", *(["--json"] if compact else [])]
    )
    output = capsys.readouterr().out
    report = json.loads(output)
    assert exit_code == 1
    assert "Traceback (most recent call last)" not in output
    assert report["verdict"] == "FAIL"
    assert report["measurement"]["complete_verdict"] is True
    assert "DS11-GENERATED-DRIFT" in report["error"]
    assert report["write_set"] == []
    assert read_fact(report, checker._OUTPUT_PATH.as_posix())["status"] == "read"
