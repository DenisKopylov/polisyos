"""Exercise CLI read disclosure and unchanged rejection using synthetic custody rows."""

import json
from hashlib import sha256
from pathlib import Path

import pytest
from _helpers.custody_markdown import rebound_register

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
    assert checker.main(
        ["--repo-root", str(root), mode, *(["--json"] if compact else [])]
    ) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["measurement"]["complete_verdict"] is True
    return report


def read_fact(report: dict, path: str) -> dict:
    return next(
        item for item in report["measurement"]["inputs"]
        if item["path"] == path and item["operation"] == "read_bytes"
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
@pytest.mark.parametrize("mutation", ["owner", "missing", "unreadable"])
def test_cli_emits_partial_receipt_and_keeps_original_custody_rejection(
    source_repo: Path, capsys, monkeypatch, compact: bool, mutation: str
) -> None:
    custody = source_repo / checker._DEBT_REGISTER_PATH
    if mutation == "owner":
        custody.write_bytes(custody.read_bytes().replace(b"team-scientist", b"team-forged"))
    elif mutation == "missing":
        custody.unlink()
    else:
        original = Path.read_bytes

        def denied(path: Path) -> bytes:
            if path == custody:
                raise PermissionError("synthetic unreadable input")
            return original(path)

        monkeypatch.setattr(Path, "read_bytes", denied)
    with pytest.raises((ValueError, PermissionError)):
        checker.main(["--repo-root", str(source_repo), "--check-sources", *(["--json"] if compact else [])])
    output = capsys.readouterr().out
    assert output, "the real caller must report its incomplete read boundary before failing"
    report = json.loads(output)
    assert report["verdict"] == "UNRUN"
    assert report["measurement"]["complete_verdict"] is False
    inputs = [item for item in report["measurement"]["inputs"] if item["path"] == checker._DEBT_REGISTER_PATH.as_posix()]
    assert any(item["status"] == {"owner": "read", "missing": "absent", "unreadable": "unreadable"}[mutation] for item in inputs)
    assert report["error"]


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
    with pytest.raises(ValueError, match="DS11-GENERATED-DRIFT"):
        checker.main(["--repo-root", str(source_repo), "--check", *(["--json"] if compact else [])])
    report = json.loads(capsys.readouterr().out)
    assert report["measurement"]["complete_verdict"] is False
    assert "DS11-GENERATED-DRIFT" in report["error"]
    assert read_fact(report, checker._OUTPUT_PATH.as_posix())["status"] == "read"
