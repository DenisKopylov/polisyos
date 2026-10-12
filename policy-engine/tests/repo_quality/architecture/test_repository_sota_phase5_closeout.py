from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent

_REQUIRED_GATE_IDS = frozenset(
    {
        "topology-loose-files",
        "import-linter",
        "public-surface",
        "generated-drift",
        "docs-freshness",
        "public-polish",
        "shim-audit",
        "complexity-exceptions",
        "security-baselines",
        "dependency-baselines",
        "sbom-baseline",
        "commit-policy",
        "command-registry",
    }
)
_REQUIRED_SUBPROCESS_GATE_IDS = frozenset(
    {
        "topology-loose-files",
        "import-linter",
        "public-surface",
        "generated-drift",
        "public-polish",
        "command-registry",
    }
)
_REQUIRED_PREFLIGHT_GATE_IDS = frozenset(
    {
        "docs-freshness",
        "shim-audit",
        "complexity-exceptions",
        "security-baselines",
        "dependency-baselines",
        "sbom-baseline",
        "commit-policy",
    }
)
_REQUIRED_CONDITIONAL_GATE_IDS = frozenset({"docs-freshness"})


def test_phase5_repository_sota_closeout_command_is_registered() -> None:
    from tools.registry import TOOL_SPECS_BY_KEY

    spec = TOOL_SPECS_BY_KEY[("workspace", "repository-sota-closeout")]

    assert spec.module == "tools.devx.workspace.repository_sota_closeout"
    assert spec.callable_name == "main"
    assert spec.status.value == "active"


def test_phase5_gate_registry_is_fail_closed_and_evidence_backed() -> None:
    contract = _read_toml("architecture/gates/repository_sota.toml")
    header = contract["repository_sota_gates"]
    gate_rows = contract["gate"]
    gate_ids = [gate["id"] for gate in gate_rows]
    assert len(gate_ids) == len(set(gate_ids))
    gates = {gate["id"]: gate for gate in gate_rows}

    assert header["status"] == "fail_closed"
    assert _contract_path_exists(header["closeout_report"])
    assert header["gate_command"] == "uv run polisyos-tools workspace repository-sota-closeout"

    assert set(gates) >= _REQUIRED_GATE_IDS

    for gate in gates.values():
        assert gate["mode"] == "fail_closed", gate["id"]
        assert isinstance(gate["coverage"], list) and gate["coverage"], gate["id"]
        assert gate["owner"], gate["id"]
        assert gate["command"], gate["id"]
        assert _contract_path_exists(gate["evidence"]), gate["id"]
        if gate.get("exceptions"):
            assert _contract_path_exists(gate["exceptions"]), gate["id"]
    assert (
        gates["generated-drift"]["command"]
        == "uv run polisyos-tools architecture guardrails check --all-generated-checks"
    )
    assert gates["topology-loose-files"]["command"] == (
        "uv run pytest tests/repo_quality/architecture/test_repository_sota_phase3_topology_cleanup.py -q"
    )
    assert gates["public-surface"]["command"] == (
        "uv run polisyos-tools architecture guardrails check"
    )
    assert gates["docs-freshness"]["command"] == (
        "uv run polisyos-tools validation check-docs-accuracy --repo-root ."
    )
    assert gates["generated-drift"]["skip_command"] == (
        "uv run polisyos-tools architecture guardrails check --skip-generated-checks"
    )


def test_phase5_registered_routes_resolve_and_dispatch_every_subprocess_row() -> None:
    from tools.devx.workspace import repository_sota_closeout

    contract = _read_toml("architecture/gates/repository_sota.toml")
    gate_rows = contract["gate"]
    registry_ids = {gate["id"] for gate in gate_rows}
    registry_subprocess_ids = {gate["id"] for gate in gate_rows if "subprocess" in gate["coverage"]}
    registry_preflight_ids = {
        gate["id"]
        for gate in gate_rows
        if any(route.startswith("preflight:") for route in gate["coverage"])
    }
    registry_conditional_ids = {
        gate["id"]
        for gate in gate_rows
        if any(route.startswith("conditional:") for route in gate["coverage"])
    }
    full_ids = {
        gate_id
        for gate_id, _command in repository_sota_closeout._registered_subprocess_gates(
            skip_generated_checks=False
        )
    }
    skip_ids = {
        gate_id
        for gate_id, _command in repository_sota_closeout._registered_subprocess_gates(
            skip_generated_checks=True
        )
    }

    assert registry_ids >= _REQUIRED_GATE_IDS
    assert registry_subprocess_ids >= _REQUIRED_SUBPROCESS_GATE_IDS
    assert registry_preflight_ids >= _REQUIRED_PREFLIGHT_GATE_IDS
    assert registry_conditional_ids >= _REQUIRED_CONDITIONAL_GATE_IDS
    assert repository_sota_closeout._check_gate_registry() == []
    assert full_ids == registry_subprocess_ids
    assert skip_ids == registry_subprocess_ids
    full = dict(repository_sota_closeout._registered_subprocess_gates(skip_generated_checks=False))
    light = dict(repository_sota_closeout._registered_subprocess_gates(skip_generated_checks=True))
    assert full["generated-drift"][-1] == "--all-generated-checks"
    assert light["generated-drift"][-1] == "--skip-generated-checks"


@pytest.mark.parametrize("gate_id", sorted(_REQUIRED_GATE_IDS))
def test_phase5_contract_entrypoint_rejects_deleted_required_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, gate_id: str
) -> None:
    from copy import deepcopy

    contract = deepcopy(_read_toml("architecture/gates/repository_sota.toml"))
    contract["gate"] = [row for row in contract["gate"] if row["id"] != gate_id]
    exit_code, payload = _run_gate_registry_contract(monkeypatch, tmp_path, contract)

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert any(
        finding["gate"] == "gate-registry"
        and finding["message"] == "missing required gate"
        and finding["detail"] == gate_id
        for finding in payload["findings"]
    )


@pytest.mark.parametrize("gate_id", sorted(_REQUIRED_GATE_IDS))
def test_phase5_contract_entrypoint_rejects_wrong_required_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, gate_id: str
) -> None:
    from copy import deepcopy

    contract = deepcopy(_read_toml("architecture/gates/repository_sota.toml"))
    row = next(row for row in contract["gate"] if row["id"] == gate_id)
    row["command"] = f"uv run polisyos-tools unrelated-gate {gate_id}"
    exit_code, payload = _run_gate_registry_contract(monkeypatch, tmp_path, contract)

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert any(
        finding["gate"] == "gate-registry"
        and finding["message"] == f"{gate_id} required command mismatch"
        for finding in payload["findings"]
    )


@pytest.mark.parametrize("gate_id", sorted(_REQUIRED_GATE_IDS))
def test_phase5_contract_entrypoint_rejects_wrong_required_coverage_kind(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, gate_id: str
) -> None:
    from copy import deepcopy

    contract = deepcopy(_read_toml("architecture/gates/repository_sota.toml"))
    row = next(row for row in contract["gate"] if row["id"] == gate_id)
    row["coverage"] = (
        ["preflight:ops-modes"] if gate_id in _REQUIRED_SUBPROCESS_GATE_IDS else ["subprocess"]
    )
    exit_code, payload = _run_gate_registry_contract(monkeypatch, tmp_path, contract)

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert any(
        finding["gate"] == "gate-registry"
        and finding["message"] == f"{gate_id} required coverage routes mismatch"
        for finding in payload["findings"]
    )


def test_phase5_contract_entrypoint_rejects_non_table_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exit_code, payload = _run_gate_registry_contract(monkeypatch, tmp_path, [])

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert any(
        finding["gate"] == "gate-registry"
        and finding["message"] == "registry document must be a table"
        for finding in payload["findings"]
    )


def _run_gate_registry_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, contract: Any
) -> tuple[int, dict[str, Any]]:
    from tools.devx.workspace import repository_sota_closeout

    original_read_toml = repository_sota_closeout._read_toml
    original_preflights = repository_sota_closeout._preflight_checks

    def read_toml(path: str) -> Any:
        if path == "architecture/gates/repository_sota.toml":
            return contract
        return original_read_toml(path)

    def contract_preflights() -> tuple[tuple[str, Any], ...]:
        return tuple(
            (
                check_id,
                check if check_id == "gate-registry" else (lambda: []),
            )
            for check_id, check in original_preflights()
        )

    monkeypatch.setattr(repository_sota_closeout, "_read_toml", read_toml)
    monkeypatch.setattr(repository_sota_closeout, "_preflight_checks", contract_preflights)
    output = tmp_path / "registry-closeout.json"
    exit_code = repository_sota_closeout.main(["--contract-only", "--output-json", str(output)])
    return exit_code, json.loads(output.read_text(encoding="utf-8"))


@pytest.mark.parametrize("skip_generated_checks", [False, True])
def test_phase5_only_pinned_generated_gate_may_declare_a_skip_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, skip_generated_checks: bool
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    contract = _read_toml("architecture/gates/repository_sota.toml")
    gate_rows = contract["gate"]
    required_rows = {gate["id"]: gate for gate in gate_rows}
    assert set(required_rows) >= _REQUIRED_GATE_IDS

    for gate_id, gate in required_rows.items():
        if gate_id != "generated-drift":
            gate["skip_command"] = "python -c pass"

    additional_command = (
        "uv run pytest tests/repo_quality/architecture/test_repository_sota_phase5_closeout.py -q"
    )
    additional = {
        "id": "additional-behavior",
        "mode": "fail_closed",
        "owner": "test",
        "command": additional_command,
        "evidence": "tests/repo_quality/architecture/test_repository_sota_phase5_closeout.py",
        "coverage": ["subprocess"],
        "skip_command": "python -c pass",
    }
    malformed_additional = {
        **additional,
        "id": "additional-malformed-skip",
        "skip_command": ["python", "-c", "pass"],
    }
    gate_rows.extend([additional, malformed_additional])

    exit_code, payload = _run_gate_registry_contract(monkeypatch, tmp_path, contract)
    assert exit_code == 1
    assert payload["status"] == "failed"
    rows_by_id = {gate["id"]: gate for gate in gate_rows}
    assert set(rows_by_id) >= _REQUIRED_GATE_IDS | {
        "additional-behavior",
        "additional-malformed-skip",
    }
    policy_findings = [
        finding
        for finding in payload["findings"]
        if finding["message"].endswith("skip_command is only permitted for generated-drift")
    ]
    expected_rejected_ids = (set(_REQUIRED_GATE_IDS) - {"generated-drift"}) | {
        "additional-behavior",
        "additional-malformed-skip",
    }
    assert {finding["message"].split(" skip_command ", 1)[0] for finding in policy_findings} == (
        expected_rejected_ids
    )
    assert len(policy_findings) == len(expected_rejected_ids)
    assert any(
        finding["message"]
        == "additional-malformed-skip skip_command is not a valid argument string"
        for finding in payload["findings"]
    )

    dispatched = dict(
        repository_sota_closeout._registered_subprocess_gates(
            skip_generated_checks=skip_generated_checks
        )
    )
    assert dispatched["additional-behavior"] == shlex.split(additional_command)
    assert dispatched["additional-malformed-skip"] == shlex.split(additional_command)
    for gate_id in _REQUIRED_SUBPROCESS_GATE_IDS - {"generated-drift"}:
        assert dispatched[gate_id] == shlex.split(rows_by_id[gate_id]["command"])
    expected_generated_command = (
        "uv run polisyos-tools architecture guardrails check --skip-generated-checks"
        if skip_generated_checks
        else "uv run polisyos-tools architecture guardrails check --all-generated-checks"
    )
    assert dispatched["generated-drift"] == shlex.split(expected_generated_command)


@pytest.mark.parametrize("skip_generated_checks", [False, True])
def test_phase5_invalid_registry_prevents_child_execution(
    monkeypatch: pytest.MonkeyPatch, skip_generated_checks: bool
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    contract = _read_toml("architecture/gates/repository_sota.toml")
    contract["gate"].append(
        {
            "id": "additional-behavior",
            "mode": "fail_closed",
            "owner": "test",
            "command": (
                "uv run pytest tests/repo_quality/architecture/"
                "test_repository_sota_phase5_closeout.py -q"
            ),
            "evidence": "tests/repo_quality/architecture/test_repository_sota_phase5_closeout.py",
            "coverage": ["subprocess"],
            "skip_command": "python -c pass",
        }
    )
    original_read_toml = repository_sota_closeout._read_toml
    original_preflights = repository_sota_closeout._preflight_checks

    def read_toml(path: str) -> Any:
        if path == "architecture/gates/repository_sota.toml":
            return contract
        return original_read_toml(path)

    def registry_preflights() -> tuple[tuple[str, Any], ...]:
        return tuple(
            (check_id, check if check_id == "gate-registry" else (lambda: []))
            for check_id, check in original_preflights()
        )

    subprocess_started = False

    def unexpected_subprocess_run(_args: Any) -> list[Any]:
        nonlocal subprocess_started
        subprocess_started = True
        return []

    monkeypatch.setattr(repository_sota_closeout, "_read_toml", read_toml)
    monkeypatch.setattr(repository_sota_closeout, "_preflight_checks", registry_preflights)
    monkeypatch.setattr(
        repository_sota_closeout, "_run_fail_closed_subprocess_gates", unexpected_subprocess_run
    )
    argv = ["--skip-generated-checks"] if skip_generated_checks else []

    assert repository_sota_closeout.main(argv) == 1
    assert not subprocess_started


def test_phase5_registry_dispatched_child_preserves_failure_and_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    command = shlex.join(
        [
            sys.executable,
            "-c",
            "import sys; print('child-stdout'); print('child-stderr', file=sys.stderr); raise SystemExit(23)",
        ]
    )
    registry = {
        "gate": [
            {
                "id": "newly-registered-behavior",
                "mode": "fail_closed",
                "owner": "test",
                "command": command,
                "evidence": "tests/repo_quality/architecture/test_repository_sota_phase5_closeout.py",
                "coverage": ["subprocess"],
            }
        ]
    }
    monkeypatch.setattr(repository_sota_closeout, "_read_toml", lambda _path: registry)
    monkeypatch.setattr(repository_sota_closeout, "_supporting_subprocess_gates", lambda: [])
    monkeypatch.setattr(repository_sota_closeout, "_conditional_gate_handlers", lambda: {})
    args = repository_sota_closeout._build_parser().parse_args([])

    findings = repository_sota_closeout._run_fail_closed_subprocess_gates(args)

    assert len(findings) == 1
    assert findings[0].gate == "newly-registered-behavior"
    assert findings[0].message == "subprocess gate failed"
    assert "child-stdout" in findings[0].detail
    assert "child-stderr" in findings[0].detail


def test_phase5_registry_rejects_duplicate_and_malformed_rows_without_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from copy import deepcopy

    from tools.devx.workspace import repository_sota_closeout

    contract = _read_toml("architecture/gates/repository_sota.toml")
    malformed = deepcopy(contract["gate"][0])
    malformed["command"] = []
    duplicate = deepcopy(contract["gate"][0])
    contract["gate"][0]["command"] = []
    duplicate["command"] = []
    contract["gate"].extend([malformed, duplicate])
    original_read_toml = repository_sota_closeout._read_toml

    def read_toml(path: str) -> dict[str, Any]:
        if path == "architecture/gates/repository_sota.toml":
            return contract
        return original_read_toml(path)

    monkeypatch.setattr(repository_sota_closeout, "_read_toml", read_toml)
    exit_code, payload = _run_gate_registry_contract(monkeypatch, tmp_path, contract)
    findings = payload["findings"]

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert any(finding["message"] == "duplicate gate id" for finding in findings)
    assert any(
        finding["message"] == "topology-loose-files command is not a valid argument string"
        for finding in findings
    )
    assert all(
        gate_id != "topology-loose-files"
        for gate_id, _command in repository_sota_closeout._registered_subprocess_gates(
            skip_generated_checks=False
        )
    )


def test_phase5_child_gate_receipt_retains_complete_failure_output(tmp_path: Path) -> None:
    from tools.devx.workspace import repository_sota_closeout

    parsed = repository_sota_closeout._build_parser().parse_args(
        ["--subprocess-receipt-dir", str(tmp_path / "receipts")]
    )
    assert parsed.subprocess_receipt_dir == tmp_path / "receipts"

    stdout = b"stdout-marker\r\ninvalid:\xff\xfe\r\n" + (b"x" * 5_000) + b"\r\n"
    stderr = b"stderr-marker\r\ninvalid:\x80\r\n" + (b"y" * 5_000) + b"\r\n"
    child_code = (
        f"import os\nos.write(1, {stdout!r})\nos.write(2, {stderr!r})\nraise SystemExit(23)\n"
    )
    command = [sys.executable, "-c", child_code]
    receipt_dir = tmp_path / "receipts"

    completed = repository_sota_closeout._run_subprocess_with_receipt(
        "receipt-probe",
        command,
        receipt_dir=receipt_dir,
    )

    assert completed.returncode == 23
    gate_dir = receipt_dir / "receipt-probe"
    assert (gate_dir / "stdout.bin").read_bytes() == stdout
    assert (gate_dir / "stderr.bin").read_bytes() == stderr
    receipt = json.loads((gate_dir / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["gate"] == "receipt-probe"
    assert receipt["command"] == command
    assert receipt["cwd"] == str(REPO_ROOT)
    assert receipt["exit_code"] == 23
    assert receipt["gate_output_decoding"] == {
        "encoding": "utf-8",
        "errors": "backslashreplace",
        "newline_normalization": "universal",
    }
    assert receipt["stdout"]["byte_length"] == len(stdout)
    assert receipt["stderr"]["byte_length"] == len(stderr)
    assert receipt["stdout"]["sha256"] == hashlib.sha256(stdout).hexdigest()
    assert receipt["stderr"]["sha256"] == hashlib.sha256(stderr).hexdigest()

    expected_stdout = stdout.decode("utf-8", errors="backslashreplace").replace("\r\n", "\n")
    expected_stderr = stderr.decode("utf-8", errors="backslashreplace").replace("\r\n", "\n")
    assert completed.stdout == expected_stdout
    assert completed.stderr == expected_stderr
    summary = repository_sota_closeout._compact_output(completed, limit=20_000)
    assert "stdout-marker\ninvalid:\\xff\\xfe" in summary
    assert "stderr-marker\ninvalid:\\x80" in summary

    legacy_stdout = "legacy-stdout-" + ("x" * 5_000)
    legacy_stderr = "legacy-stderr-" + ("y" * 5_000)
    legacy_code = (
        "import sys\n"
        f"sys.stdout.write({legacy_stdout!r})\n"
        f"sys.stderr.write({legacy_stderr!r})\n"
        "raise SystemExit(23)\n"
    )
    legacy_command = [sys.executable, "-c", legacy_code]
    default_completed = repository_sota_closeout._run_subprocess_with_receipt(
        "default-probe",
        legacy_command,
        receipt_dir=None,
    )
    assert default_completed.returncode == 23
    assert not (tmp_path / "default-probe").exists()
    assert repository_sota_closeout._compact_output(default_completed) == (
        (legacy_stdout + legacy_stderr)[:4000] + "\n...[truncated]..."
    )


def test_phase5_remaining_exceptions_are_owner_approved_and_time_bounded() -> None:
    today = dt.date.today()

    imports = _read_toml("architecture/imports/exceptions.toml").get("exception", [])
    for exception in imports:
        assert exception["id"]
        assert exception["owner"]
        assert exception["reason"]
        assert exception["source_glob"]
        assert _has_issue_or_adr(exception)
        assert _date(exception["expires"]) >= today

    complexity = _read_toml("architecture/exceptions/complexity.toml")
    assert complexity["complexity_exceptions"]["status"] == "active"
    for exception in complexity["exception"]:
        path = exception["path"]
        assert "*" not in path and "?" not in path and "[" not in path
        assert (REPO_ROOT / path).exists(), path
        assert exception["owner"]
        assert exception["reason"]
        assert exception["remediation"]
        assert _has_issue_or_adr(exception)
        assert _date(exception["expires"]) >= today

    docs = _read_toml("architecture/exceptions/docs_freshness.toml")["docs_freshness_exceptions"]
    assert docs["owner"]
    assert docs["reason"]
    assert docs["issue"]
    assert type(docs["expected_violation_count"]) is int
    assert docs["expected_violation_count"] >= 0
    if docs["expected_violation_count"] > 0:
        assert _date(docs["expires"]) >= today
    else:
        _date(docs["expires"])

    shims = _read_toml("architecture/shims.toml")["shim"]
    for shim in shims:
        assert shim["id"]
        assert shim["owner"]
        assert shim["reason"]
        assert shim["target_path"]
        assert shim["issue"]
        assert _date(shim["sunset_date"]) >= today
        assert _contract_path_exists(shim["target_path"]), shim["id"]
        if shim["type"] == "wrapper_only":
            assert _contract_path_exists(shim["source_path"]), shim["id"]


@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr", "has_findings"),
    [
        (0, "- violations: 0\n", "", False),
        (1, "- violations: 1\n", "", True),
        (1, "- violations: 0\n", "native checker failed\n", True),
    ],
)
def test_zero_debt_docs_baseline_ignores_expiry_but_always_runs_native_check(
    monkeypatch,
    returncode: int,
    stdout: str,
    stderr: str,
    has_findings: bool,
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    baseline = _docs_freshness_baseline(
        expected_violation_count=0,
        expires=(dt.date.today() - dt.timedelta(days=1)).isoformat(),
        baseline_sha256=hashlib.sha256((stdout + stderr).encode("utf-8")).hexdigest(),
    )
    calls = _stub_docs_freshness_subprocess(
        monkeypatch,
        baseline,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )

    assert repository_sota_closeout._check_docs_freshness_contract() == []
    findings = repository_sota_closeout._run_docs_freshness_gate()

    assert len(calls) == 1
    assert calls[0][0] == "docs-freshness"
    assert calls[0][1] == [
        "uv",
        "run",
        "polisyos-tools",
        "validation",
        "check-docs-accuracy",
        "--repo-root",
        ".",
    ]
    assert bool(findings) is has_findings


def test_current_zero_debt_config_reaches_native_docs_check(monkeypatch) -> None:
    from tools.devx.workspace import repository_sota_closeout

    baseline = _read_toml("architecture/exceptions/docs_freshness.toml")[
        "docs_freshness_exceptions"
    ]
    assert baseline["expected_violation_count"] == 0
    assert _date(baseline["expires"]) < dt.date.today()

    calls: list[list[str]] = []

    def run_subprocess(
        gate: str,
        command: list[str],
        *,
        receipt_dir: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del receipt_dir
        assert gate == "docs-freshness"
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "- violations: 0\n", "")

    monkeypatch.setattr(repository_sota_closeout, "_run_subprocess_with_receipt", run_subprocess)

    assert repository_sota_closeout._check_docs_freshness_contract() == []
    assert repository_sota_closeout._run_docs_freshness_gate() == []
    assert len(calls) == 1


@pytest.mark.parametrize(
    "stdout",
    [
        "Docs accuracy report: passed\n",
        "- violations: invalid\n",
        "- violations: 0\n- violations: 0\n",
    ],
)
def test_zero_debt_docs_gate_rejects_missing_or_ambiguous_count_even_on_exit_zero(
    monkeypatch, stdout: str
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    baseline = _docs_freshness_baseline(
        expected_violation_count=0,
        expires=(dt.date.today() - dt.timedelta(days=1)).isoformat(),
        baseline_sha256=None,
    )
    calls = _stub_docs_freshness_subprocess(monkeypatch, baseline, returncode=0, stdout=stdout)

    findings = repository_sota_closeout._run_docs_freshness_gate()

    assert calls
    assert any("malformed violation count" in finding.message for finding in findings)


def test_expired_positive_docs_baseline_is_not_an_admitted_exception(monkeypatch) -> None:
    from tools.devx.workspace import repository_sota_closeout

    output = "- violations: 1\n"
    baseline = _docs_freshness_baseline(
        expected_violation_count=1,
        expires=(dt.date.today() - dt.timedelta(days=1)).isoformat(),
        baseline_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
    )
    calls = _stub_docs_freshness_subprocess(monkeypatch, baseline, returncode=1, stdout=output)

    findings = repository_sota_closeout._run_docs_freshness_gate()

    assert any("expired" in finding.message for finding in findings)
    assert calls == []


def test_current_positive_docs_baseline_requires_exact_count_and_output_hash(monkeypatch) -> None:
    from tools.devx.workspace import repository_sota_closeout

    output = "- violations: 1\n"
    baseline = _docs_freshness_baseline(
        expected_violation_count=1,
        expires=(dt.date.today() + dt.timedelta(days=30)).isoformat(),
        baseline_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
    )
    calls = _stub_docs_freshness_subprocess(monkeypatch, baseline, returncode=1, stdout=output)

    assert repository_sota_closeout._check_docs_freshness_contract() == []
    assert repository_sota_closeout._run_docs_freshness_gate() == []
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("expected_count", "expected_digest"),
    [
        (2, hashlib.sha256(b"- violations: 1\n").hexdigest()),
        (1, "0" * 64),
    ],
)
def test_positive_docs_baseline_rejects_forged_count_or_hash(
    monkeypatch, expected_count: int, expected_digest: str
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    output = "- violations: 1\n"
    baseline = _docs_freshness_baseline(
        expected_violation_count=expected_count,
        expires=(dt.date.today() + dt.timedelta(days=30)).isoformat(),
        baseline_sha256=expected_digest,
    )
    calls = _stub_docs_freshness_subprocess(monkeypatch, baseline, returncode=1, stdout=output)

    findings = repository_sota_closeout._run_docs_freshness_gate()

    assert findings
    assert len(calls) == 1


@pytest.mark.parametrize(
    "override",
    [
        {"expected_violation_count": "0"},
        {"expected_violation_count": False},
        {"expires": "not-a-date"},
        {"mode": "report_only"},
        {"owner": ""},
        {"baseline_sha256": "pending"},
    ],
)
def test_malformed_docs_freshness_fields_are_not_treated_as_absent_or_zero(
    monkeypatch, override: dict[str, object]
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    baseline = _docs_freshness_baseline(
        expected_violation_count=0,
        expires=(dt.date.today() + dt.timedelta(days=30)).isoformat(),
        baseline_sha256="a" * 64,
    )
    baseline.update(override)
    calls = _stub_docs_freshness_subprocess(
        monkeypatch,
        baseline,
        returncode=0,
        stdout="- violations: 0\n",
    )

    assert repository_sota_closeout._check_docs_freshness_contract()
    assert repository_sota_closeout._run_docs_freshness_gate()
    if type(baseline["expected_violation_count"]) is int:
        assert len(calls) == 1
    else:
        assert calls == []


def _docs_freshness_baseline(
    *, expected_violation_count: object, expires: str, baseline_sha256: str | None
) -> dict[str, object]:
    baseline: dict[str, object] = {
        "version": 1,
        "owner": "team-docs",
        "mode": "fail_closed_baseline",
        "command": "uv run polisyos-tools validation check-docs-accuracy --repo-root .",
        "reason": "Test-only exact output baseline.",
        "expires": expires,
        "issue": "docs/plans/accepted/REPOSITORY_SOTA_PLAN.md#docs-freshness",
        "expected_violation_count": expected_violation_count,
    }
    if baseline_sha256 is not None:
        baseline["baseline_sha256"] = baseline_sha256
    return baseline


def _stub_docs_freshness_subprocess(
    monkeypatch,
    baseline: dict[str, object],
    *,
    returncode: int,
    stdout: str,
    stderr: str = "",
) -> list[tuple[str, list[str]]]:
    from tools.devx.workspace import repository_sota_closeout

    original_read_toml = repository_sota_closeout._read_toml

    def read_toml(path: str) -> dict[str, Any]:
        if path == "architecture/exceptions/docs_freshness.toml":
            return {"docs_freshness_exceptions": baseline}
        return original_read_toml(path)

    calls: list[tuple[str, list[str]]] = []

    def run_subprocess(
        gate: str,
        command: list[str],
        *,
        receipt_dir: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del receipt_dir
        calls.append((gate, command))
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    monkeypatch.setattr(repository_sota_closeout, "_read_toml", read_toml)
    monkeypatch.setattr(repository_sota_closeout, "_run_subprocess_with_receipt", run_subprocess)
    return calls


def test_phase6_5_exception_cleanup_registries_are_reviewable() -> None:
    today = dt.date.today()
    import_ids = {
        exception["id"]
        for exception in _read_toml("architecture/imports/exceptions.toml").get("exception", [])
    }
    import_docs = (REPO_ROOT / "architecture/imports/exceptions.md").read_text(encoding="utf-8")
    documented_ids = set(re.findall(r"`(E-\d{4}-\d{2}-[A-Z0-9-]+)`", import_docs))
    assert documented_ids == import_ids
    assert "issue/ADR" in import_docs

    dynamic_imports = _read_toml("architecture/imports/dynamic.toml")
    dynamic_header = dynamic_imports["dynamic_imports"]
    _assert_fields(
        dynamic_header,
        ("review_owner", "reviewed_at", "review_expires", "issue", "adr", "exception_policy"),
    )
    assert _date(dynamic_header["review_expires"]) >= today
    for pattern in dynamic_imports["pattern"]:
        _assert_fields(pattern, ("id", "owner", "source_file", "call", "verifier", "notes"))
        assert pattern.get("target") or pattern.get("allowed_targets"), pattern["id"]
        assert _contract_path_exists(pattern["source_file"]), pattern["id"]

    for package_contract in sorted((REPO_ROOT / "architecture/packages").glob("*.toml")):
        if package_contract.stem in {"boundaries", "layout"}:
            continue
        payload = tomllib.loads(package_contract.read_text(encoding="utf-8"))
        for exception in payload.get("exception", []):
            _assert_fields(exception, ("id", "owner", "kind", "reason", "sunset", "registry"))
            assert _has_issue_or_adr(exception), exception["id"]
            assert _date(exception["sunset"]) >= today
            assert _contract_path_exists(exception["registry"]), exception["id"]
        for sunset in payload.get("sunset", []):
            _assert_fields(sunset, ("id", "owner", "date", "condition"))
            assert _has_issue_or_adr(sunset), sunset["id"]
            assert _date(sunset["date"]) >= today

    test_topology = _read_toml("architecture/tests/topology.toml")
    for exception in test_topology.get("source_package_exception", []):
        _assert_fields(
            exception, ("name", "source_path", "classification", "owner", "reason", "sunset")
        )
        assert _has_issue_or_adr(exception), exception["name"]
        assert _date(exception["sunset"]) >= today
        assert _contract_path_exists(exception["source_path"]), exception["name"]

    for override in _read_toml("architecture/tooling/static_analysis_overrides.toml")[
        "override_scope"
    ]:
        _assert_fields(override, ("id", "owner", "expectation", "sunset", "issue"))
        assert _date(override["sunset"]) >= today

    for budget in _read_toml("architecture/module_size_budget.toml")["budget"]:
        _assert_fields(budget, ("path", "owner", "strategy", "shrink_plan", "sunset"))
        assert _has_issue_or_adr(budget), budget["path"]
        assert _date(budget["sunset"]) >= today

    ratchets = _read_toml("architecture/tests/ratchets.toml")
    for exception in ratchets.get("pytest_universe_exception", []):
        _assert_fields(exception, ("id", "owner", "reason", "expires", "issue"))
        assert _date(exception["expires"]) >= today
    for exception in ratchets.get("package_exception", []):
        _assert_fields(exception, ("id", "owner", "reason", "sunset_date", "issue"))
        assert _date(exception["sunset_date"]) >= today

    for component in _read_toml("architecture/component_observability.toml")["component_contract"]:
        if component.get("slo_status") == "exception":
            _assert_fields(
                component,
                ("owner", "exception_reason", "exception_expires", "exception_issue"),
            )
            assert _date(component["exception_expires"]) >= today

    for component in _read_toml("architecture/runbook_coverage.toml")["component_contract"]:
        if component.get("slo_exception"):
            _assert_fields(
                component,
                ("owner", "slo_exception_reason", "slo_exception_expires", "slo_exception_issue"),
            )
            assert _date(component["slo_exception_expires"]) >= today
            assert _contract_path_exists(component["slo_exception"]), component["component"]

    directory_contracts = _read_toml("architecture/policies/directory_contracts.toml")
    assert directory_contracts["directory_contracts"]["exception_policy_issue"]
    accepted_fields = set(
        directory_contracts["local_documentation_requirement"]["accepted_exception_fields"]
    )
    assert {
        "owner",
        "reason",
        "sunset",
        "promotion_or_cleanup_target",
        "issue_or_adr",
    } <= accepted_fields

    generated_artifacts = _read_toml("architecture/generated_artifacts.toml")
    assert generated_artifacts["generated_artifacts"]["exception_policy"]
    assert generated_artifacts["generated_artifacts"]["exception_policy_issue"]
    for family in generated_artifacts["family"]:
        _assert_fields(
            family,
            (
                "id",
                "owner",
                "approval_owner",
                "source_of_truth",
                "freshness_rule",
                "regenerate_commands",
                "stale_output_behavior",
                "promotion_target",
            ),
        )

    control_plane = _read_toml("architecture/control_plane_supply_chain.toml")
    for item in [control_plane["codeowners_gate"], *control_plane["owner_mapping"]]:
        if item.get("personal_repo_exception"):
            _assert_fields(
                item,
                (
                    "personal_repo_exception_reason",
                    "personal_repo_exception_expires",
                    "personal_repo_exception_issue",
                ),
            )
            assert _date(item["personal_repo_exception_expires"]) >= today


def test_phase5_ops_security_release_and_observability_modes_are_fail_closed() -> None:
    ops = _read_toml("architecture/baselines/ops.toml")
    for baseline in ops["baseline"]:
        assert baseline["mode"] == "fail_closed", baseline["id"]

    assert "mode: fail_closed" in (REPO_ROOT / "ops/observability/otel/baseline.yaml").read_text(
        encoding="utf-8"
    )
    for path, table in {
        "ops/security/secrets-baseline.toml": "secrets_baseline",
        "ops/release/commit-policy.toml": "commit_policy",
        "ops/release/release-fragment-policy.toml": "release_fragments",
        "ops/runtime/runtime-contracts.toml": "runtime_contracts",
        "ops/migrations/migration-contracts.toml": "migration_contracts",
    }.items():
        assert _read_toml(path)[table]["mode"] == "fail_closed"

    secrets = _read_toml("ops/security/secrets-baseline.toml")["secrets_baseline"]
    for config_path in secrets["config_paths"]:
        assert _contract_path_exists(config_path)
    assert secrets["baseline_commands"]

    sbom = _read_toml("ops/security/sbom.toml")["sbom"]
    for input_path in sbom["inputs"]:
        assert _contract_path_exists(input_path), input_path

    security_readme = (REPO_ROOT / "ops/security/README.md").read_text(encoding="utf-8")
    assert "report-only" not in security_readme
    commit_policy = _read_toml("ops/release/commit-policy.toml")["commit_policy"]
    assert "report-only" not in commit_policy["evidence_policy"]


def test_phase5_ci_precommit_docs_and_command_registry_are_wired() -> None:
    for path in (
        REPO_ROOT / ".pre-commit-config.yaml",
        WORKSPACE_ROOT / ".github/workflows/abi.yml",
        REPO_ROOT / "ops/ci/templates/workflows/arch.yml",
    ):
        assert "repository-sota-closeout" in path.read_text(encoding="utf-8")

    closeout = REPO_ROOT / "docs/plans/accepted/REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md"
    assert closeout.exists()
    assert "repository-sota-closeout" in closeout.read_text(encoding="utf-8")

    for path in (
        "docs/plans/accepted/REPOSITORY_SOTA_PLAN.md",
        "docs/reference/repository-topology.md",
        "docs/reference/quality-gates.md",
        "docs/reference/repository-hygiene.md",
        "docs/reference/contributor-start-here.md",
        "docs/adr/README.md",
        "docs/plans/README.md",
        "docs/reference/tools.md",
    ):
        assert "repository-sota-closeout" in (REPO_ROOT / path).read_text(encoding="utf-8")

    mkdocs = (REPO_ROOT / "architecture/tooling/mkdocs/generated.yml").read_text(encoding="utf-8")
    for nav_path in (
        "reference/frontend/workspace-contract.md",
        "reference/data-lake-policy.md",
        "reference/local-runtime-state.md",
        "reference/operations/ops-baselines.md",
    ):
        assert nav_path in mkdocs


def test_phase5_contract_only_closeout_gate_passes() -> None:
    subprocess.run(
        [
            "uv",
            "run",
            "polisyos-tools",
            "workspace",
            "repository-sota-closeout",
            "--contract-only",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _contract_path_exists(path: str) -> bool:
    if any(char in path for char in "*?["):
        return bool(list(REPO_ROOT.glob(path)))
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.exists()
    return (REPO_ROOT / candidate).exists()


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def _assert_fields(item: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        assert item.get(field) not in (None, "", [], {}), field


def _has_issue_or_adr(item: dict[str, Any]) -> bool:
    return any(str(item.get(field, "")).strip() for field in ("issue", "adr", "adr_reference"))
