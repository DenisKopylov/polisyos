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
    for exception in complexity.get("exception", []):
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


def test_complexity_checker_accepts_empty_registry_and_rejects_malformed_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    original_read_toml = repository_sota_closeout._read_toml
    complexity: dict[str, Any] = {"complexity_exceptions": {"status": "active"}}

    def read_toml(path: str) -> dict[str, Any]:
        if path == "architecture/exceptions/complexity.toml":
            return complexity
        return original_read_toml(path)

    monkeypatch.setattr(repository_sota_closeout, "_read_toml", read_toml)

    assert repository_sota_closeout._check_complexity_exceptions() == []

    complexity["exception"] = [
        {
            "path": "src/polisyos/core/contracts/runtime.py",
            "expires": "not-a-date",
        }
    ]
    findings = repository_sota_closeout._check_complexity_exceptions()
    messages = {finding.message for finding in findings}
    assert "src/polisyos/core/contracts/runtime.py missing `owner`" in messages
    assert "src/polisyos/core/contracts/runtime.py missing `reason`" in messages
    assert "src/polisyos/core/contracts/runtime.py missing `remediation`" in messages
    assert "src/polisyos/core/contracts/runtime.py missing issue/ADR reference" in messages
    assert "src/polisyos/core/contracts/runtime.py has invalid `expires`" in messages


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
    assert _contract_path_exists(
        "docs/plans/active/REPOSITORY_LIFECYCLE_AND_OPS_TAXONOMY_DECISION.md"
    )
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
    from tools.devx.workspace import repository_sota_closeout

    assert repository_sota_closeout._check_wiring() == []

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


def test_phase5_wiring_current_routes_are_active_and_mode_correct() -> None:
    from tools.devx.workspace import repository_sota_closeout

    assert repository_sota_closeout._check_wiring() == []


def _phase5_apply_workflow_fixture_profile(documents: dict[str, str]) -> dict[str, str]:
    """Give synthetic workflows the source-visible runner/CWD facts their probes vary."""
    import yaml

    for relative_path, content in tuple(documents.items()):
        if relative_path == ".pre-commit-config.yaml":
            payload = yaml.safe_load(content)
            if isinstance(payload, dict) and isinstance(payload.get("repos"), list):
                for repository in payload["repos"]:
                    if not isinstance(repository, dict) or not isinstance(
                        repository.get("hooks"), list
                    ):
                        continue
                    for hook in repository["hooks"]:
                        if (
                            not isinstance(hook, dict)
                            or hook.get("id") != "repository-sota-closeout"
                        ):
                            continue
                        entry = hook.get("entry")
                        if isinstance(entry, str) and entry.startswith(
                            "uv run polisyos-tools workspace repository-sota-closeout"
                        ):
                            hook["entry"] = f"bash -lc 'cd policy-engine && {entry}'"
                documents[relative_path] = yaml.safe_dump(payload, sort_keys=False)
            continue
        if relative_path not in {
            "../.github/workflows/abi.yml",
            "../.github/workflows/release.yml",
            "ops/ci/templates/workflows/arch.yml",
        }:
            continue
        payload = yaml.safe_load(content)
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), dict):
            continue
        for job in payload["jobs"].values():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps")
            if isinstance(steps, list) and not any(
                isinstance(step, dict)
                and isinstance(step.get("uses"), str)
                and step["uses"].split("@", 1)[0] == "actions/checkout"
                for step in steps
            ):
                steps.insert(0, {"name": "Checkout", "uses": "actions/checkout@v4"})
            job.setdefault("runs-on", "ubuntu-latest")
            if relative_path in {
                "../.github/workflows/abi.yml",
                "../.github/workflows/release.yml",
            }:
                defaults = job.setdefault("defaults", {})
                if isinstance(defaults, dict):
                    run_defaults = defaults.setdefault("run", {})
                    if isinstance(run_defaults, dict):
                        run_defaults.setdefault("working-directory", "policy-engine")
        documents[relative_path] = yaml.safe_dump(payload, sort_keys=False)
    return documents


def test_phase5_wiring_rejects_comment_only_command_markers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    files = {
        ".pre-commit-config.yaml": (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: repository-sota-closeout\n"
            "        name: declaration only\n"
            '        entry: echo "uv run polisyos-tools workspace '
            'repository-sota-closeout --contract-only"\n'
            "        language: system\n"
            "        always_run: true\n"
            "        pass_filenames: false\n"
        ),
        "../.github/workflows/abi.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: declaration only\n"
            '        run: echo "uv run polisyos-tools workspace '
            'repository-sota-closeout --contract-only"\n'
        ),
        "ops/ci/templates/workflows/arch.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: declaration only\n"
            '        run: echo "uv run polisyos-tools workspace '
            'repository-sota-closeout"\n'
        ),
    }
    resolved = {}
    files = _phase5_apply_workflow_fixture_profile(files)
    for relative_path, content in files.items():
        path = tmp_path / relative_path.replace("/", "_").replace("..", "parent")
        path.write_text(content, encoding="utf-8")
        resolved[relative_path] = path

    monkeypatch.setattr(repository_sota_closeout, "_resolve", resolved.__getitem__)
    monkeypatch.setattr(repository_sota_closeout, "_check_last_mile_gate_ownership", lambda: [])

    findings = repository_sota_closeout._check_wiring()

    assert {finding.detail for finding in findings} == set(files)


@pytest.mark.parametrize(
    "entry",
    [
        "bash -lc 'true || uv run polisyos-tools workspace repository-sota-closeout --contract-only'",
        "bash -lc 'exit 0; uv run polisyos-tools workspace repository-sota-closeout --contract-only'",
    ],
)
def test_phase5_wiring_rejects_unreachable_shell_invocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, entry: str
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    files = {
        ".pre-commit-config.yaml": (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: repository-sota-closeout\n"
            f"        entry: {entry}\n"
            "        language: system\n"
            "        always_run: true\n"
            "        pass_filenames: false\n"
        ),
        "../.github/workflows/abi.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Contract\n"
            "        run: uv run polisyos-tools workspace repository-sota-closeout --contract-only\n"
        ),
        "ops/ci/templates/workflows/arch.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Full closeout\n"
            "        run: uv run polisyos-tools workspace repository-sota-closeout\n"
        ),
    }
    resolved = {}
    files = _phase5_apply_workflow_fixture_profile(files)
    for relative_path, content in files.items():
        path = tmp_path / relative_path.replace("/", "_").replace("..", "parent")
        path.write_text(content, encoding="utf-8")
        resolved[relative_path] = path

    monkeypatch.setattr(repository_sota_closeout, "_resolve", resolved.__getitem__)
    monkeypatch.setattr(repository_sota_closeout, "_check_last_mile_gate_ownership", lambda: [])

    findings = repository_sota_closeout._check_wiring()

    assert [finding.detail for finding in findings] == [".pre-commit-config.yaml"]


def test_phase5_wiring_rejects_conditioned_workflow_invocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    files = {
        ".pre-commit-config.yaml": (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: repository-sota-closeout\n"
            "        entry: uv run polisyos-tools workspace repository-sota-closeout --contract-only\n"
            "        language: system\n"
            "        always_run: true\n"
            "        pass_filenames: false\n"
        ),
        "../.github/workflows/abi.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Contract\n"
            "        if: ${{ github.ref != '' }}\n"
            "        run: uv run polisyos-tools workspace repository-sota-closeout --contract-only\n"
        ),
        "ops/ci/templates/workflows/arch.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Full closeout\n"
            "        run: uv run polisyos-tools workspace repository-sota-closeout\n"
        ),
    }
    resolved = {}
    files = _phase5_apply_workflow_fixture_profile(files)
    for relative_path, content in files.items():
        path = tmp_path / relative_path.replace("/", "_").replace("..", "parent")
        path.write_text(content, encoding="utf-8")
        resolved[relative_path] = path

    monkeypatch.setattr(repository_sota_closeout, "_resolve", resolved.__getitem__)
    monkeypatch.setattr(repository_sota_closeout, "_check_last_mile_gate_ownership", lambda: [])

    findings = repository_sota_closeout._check_wiring()

    assert [finding.detail for finding in findings] == ["../.github/workflows/abi.yml"]


@pytest.mark.parametrize("disabled_level", ["job", "step"])
def test_phase5_wiring_rejects_disabled_workflow_invocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, disabled_level: str
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    contents = {
        ".pre-commit-config.yaml": (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: repository-sota-closeout\n"
            "        name: Repository SOTA contract\n"
            "        entry: bash -lc 'cd policy-engine && uv run polisyos-tools "
            "workspace repository-sota-closeout --contract-only'\n"
            "        language: system\n"
            "        always_run: true\n"
            "        pass_filenames: false\n"
        ),
        "../.github/workflows/abi.yml": (
            "jobs:\n"
            "  check:\n" + ("    if: false\n" if disabled_level == "job" else "") + "    steps:\n"
            "      - name: Check Repository SOTA contract\n"
            + ("        if: false\n" if disabled_level == "step" else "")
            + "        run: uv run polisyos-tools workspace "
            "repository-sota-closeout --contract-only\n"
        ),
        "ops/ci/templates/workflows/arch.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Verify Repository SOTA closeout\n"
            "        run: uv run polisyos-tools workspace "
            "repository-sota-closeout\n"
        ),
    }
    resolved = {}
    contents = _phase5_apply_workflow_fixture_profile(contents)
    for relative_path, content in contents.items():
        path = tmp_path / relative_path.replace("/", "_").replace("..", "parent")
        path.write_text(content, encoding="utf-8")
        resolved[relative_path] = path

    monkeypatch.setattr(repository_sota_closeout, "_resolve", resolved.__getitem__)
    monkeypatch.setattr(repository_sota_closeout, "_check_last_mile_gate_ownership", lambda: [])

    findings = repository_sota_closeout._check_wiring()

    assert [finding.detail for finding in findings] == ["../.github/workflows/abi.yml"]


def test_phase5_last_mile_owner_requires_command_from_live_dispatcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    original_commands = repository_sota_closeout._supporting_subprocess_gates
    monkeypatch.setattr(
        repository_sota_closeout,
        "_supporting_subprocess_gates",
        lambda: [
            (gate_id, argv)
            for gate_id, argv in original_commands()
            if gate_id != "repository-structure"
        ],
    )

    findings = repository_sota_closeout._check_last_mile_gate_ownership()

    assert any(
        finding.gate == "last-mile-wiring" and "repository-structure" in finding.message
        for finding in findings
    )
    source = (REPO_ROOT / "tools/devx/workspace/repository_sota_closeout.py").read_text(
        encoding="utf-8"
    )
    assert "repository_structure_phase0.py" in source


def test_phase5_last_mile_owner_rejects_removed_workspace_dispatch_with_marker_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.devx.workspace import repository_sota_closeout, verify

    original_commands = verify._backend_commands
    monkeypatch.setattr(
        verify,
        "_backend_commands",
        lambda **kwargs: [
            command
            for command in original_commands(**kwargs)
            if not any("repository_last_mile_inventory.py" in token for token in command.argv)
        ],
    )

    findings = repository_sota_closeout._check_last_mile_gate_ownership()

    assert any(
        finding.gate == "last-mile-wiring" and "repository-last-mile-inventory" in finding.message
        for finding in findings
    )
    source = (REPO_ROOT / "tools/devx/workspace/verify.py").read_text(encoding="utf-8")
    assert "repository_last_mile_inventory.py" in source


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


@pytest.mark.parametrize(
    "entry",
    [
        "bash -lc 'false && uv run polisyos-tools workspace repository-sota-closeout --contract-only'",
        "bash -lc 'uv run polisyos-tools workspace repository-sota-closeout --contract-only; true'",
        "bash -lc 'uv run polisyos-tools workspace repository-sota-closeout --contract-only | true'",
        "bash -lc 'set -e; false; uv run polisyos-tools workspace repository-sota-closeout --contract-only'",
        "bash -lc 'alias uv=echo; uv run polisyos-tools workspace repository-sota-closeout --contract-only'",
    ],
)
def test_phase5_wiring_rejects_unreachable_or_status_swallowed_invocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, entry: str
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    files = {
        ".pre-commit-config.yaml": (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: repository-sota-closeout\n"
            f"        entry: {entry}\n"
            "        language: system\n"
            "        always_run: true\n"
            "        pass_filenames: false\n"
        ),
        "../.github/workflows/abi.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Contract\n"
            "        run: uv run polisyos-tools workspace repository-sota-closeout --contract-only\n"
        ),
        "ops/ci/templates/workflows/arch.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Full closeout\n"
            "        run: uv run polisyos-tools workspace repository-sota-closeout\n"
        ),
    }
    resolved = {}
    files = _phase5_apply_workflow_fixture_profile(files)
    for relative_path, content in files.items():
        path = tmp_path / relative_path.replace("/", "_").replace("..", "parent")
        path.write_text(content, encoding="utf-8")
        resolved[relative_path] = path

    monkeypatch.setattr(repository_sota_closeout, "_resolve", resolved.__getitem__)
    monkeypatch.setattr(repository_sota_closeout, "_check_last_mile_gate_ownership", lambda: [])

    findings = repository_sota_closeout._check_wiring()

    assert [finding.detail for finding in findings] == [".pre-commit-config.yaml"]


def test_phase5_wiring_accepts_final_and_chain_status_propagation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    files = {
        ".pre-commit-config.yaml": (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: repository-sota-closeout\n"
            "        entry: bash -lc 'true && cd policy-engine && uv run polisyos-tools "
            "workspace repository-sota-closeout --contract-only && true'\n"
            "        language: system\n"
            "        always_run: true\n"
            "        pass_filenames: false\n"
        ),
        "../.github/workflows/abi.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Contract\n"
            "        run: uv run polisyos-tools workspace repository-sota-closeout --contract-only\n"
        ),
        "ops/ci/templates/workflows/arch.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Full closeout\n"
            "        run: uv run polisyos-tools workspace repository-sota-closeout\n"
        ),
    }
    resolved = {}
    files = _phase5_apply_workflow_fixture_profile(files)
    for relative_path, content in files.items():
        path = tmp_path / relative_path.replace("/", "_").replace("..", "parent")
        path.write_text(content, encoding="utf-8")
        resolved[relative_path] = path

    monkeypatch.setattr(repository_sota_closeout, "_resolve", resolved.__getitem__)
    monkeypatch.setattr(repository_sota_closeout, "_check_last_mile_gate_ownership", lambda: [])

    assert repository_sota_closeout._check_wiring() == []


def test_phase5_wiring_uses_github_bash_errexit_for_route_outcome(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    job = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(job, dict)
    step = job["steps"][1]
    assert isinstance(step, dict)
    step["run"] = "uv run polisyos-tools workspace repository-sota-closeout --contract-only; true"

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert findings == []


@pytest.mark.parametrize(
    "broken_path",
    [
        ".pre-commit-config.yaml",
        "../.github/workflows/abi.yml",
        "ops/ci/templates/workflows/arch.yml",
    ],
)
@pytest.mark.parametrize("status_override", ["; true", " | true"])
def test_phase5_wiring_requires_status_propagation_for_each_route_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    broken_path: str,
    status_override: str,
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    contract = "uv run polisyos-tools workspace repository-sota-closeout --contract-only"
    full = "uv run polisyos-tools workspace repository-sota-closeout"
    files = {
        ".pre-commit-config.yaml": (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: repository-sota-closeout\n"
            f"        entry: bash -lc 'cd policy-engine && {contract}'\n"
            "        language: system\n"
            "        always_run: true\n"
            "        pass_filenames: false\n"
        ),
        "../.github/workflows/abi.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Contract\n"
            "        run: |\n"
            f"          {contract}\n"
        ),
        "ops/ci/templates/workflows/arch.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Full closeout\n"
            "        run: |\n"
            f"          {full}\n"
        ),
    }
    if broken_path == ".pre-commit-config.yaml":
        files[broken_path] = files[broken_path].replace(
            f"&& {contract}'", f"&& {contract}{status_override}'"
        )
    else:
        expected = contract if broken_path == "../.github/workflows/abi.yml" else full
        files[broken_path] = files[broken_path].replace(
            f"          {expected}\n", f"          {expected}{status_override}\n"
        )

    resolved = {}
    files = _phase5_apply_workflow_fixture_profile(files)
    for relative_path, content in files.items():
        path = tmp_path / relative_path.replace("/", "_").replace("..", "parent")
        path.write_text(content, encoding="utf-8")
        resolved[relative_path] = path

    monkeypatch.setattr(repository_sota_closeout, "_resolve", resolved.__getitem__)
    monkeypatch.setattr(repository_sota_closeout, "_check_last_mile_gate_ownership", lambda: [])

    findings = repository_sota_closeout._check_wiring()

    expected = (
        []
        if broken_path != ".pre-commit-config.yaml" and status_override == "; true"
        else [broken_path]
    )
    assert [finding.detail for finding in findings] == expected


@pytest.mark.parametrize(
    ("module_name", "argv", "owned_token"),
    [
        (
            "tools.devx.workspace.verify",
            ["--backend-only", "--skip-doctor"],
            "repository_last_mile_inventory.py",
        ),
        (
            "tools.devx.workspace.ci_parity",
            ["--backend-only", "--skip-doctor", "--skip-runtime-http"],
            "directory_health.py",
        ),
    ],
)
def test_phase5_python_dispatchers_propagate_owned_child_failure(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    argv: list[str],
    owned_token: str,
) -> None:
    from importlib import import_module

    owner = import_module(module_name)
    invoked: list[tuple[str, ...]] = []

    def fail_owned(command: object) -> None:
        actual = tuple(str(token) for token in getattr(command, "argv", ()))
        invoked.append(actual)
        if any(owned_token in token for token in actual):
            raise subprocess.CalledProcessError(17, actual)

    monkeypatch.setattr(owner, "run_command", fail_owned)

    with pytest.raises(subprocess.CalledProcessError, match="17"):
        owner.main(argv)

    assert any(any(owned_token in token for token in command) for command in invoked)


def test_phase5_closeout_dispatch_records_owned_child_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from tools.devx.workspace import repository_sota_closeout

    monkeypatch.setattr(
        repository_sota_closeout,
        "_registered_subprocess_gates",
        lambda **kwargs: [("owned-child", ("probe",))],
    )
    monkeypatch.setattr(
        repository_sota_closeout,
        "_supporting_subprocess_gates",
        lambda: [],
    )
    monkeypatch.setattr(
        repository_sota_closeout,
        "_run_subprocess_with_receipt",
        lambda gate, command, *, receipt_dir: subprocess.CompletedProcess(
            list(command), 19, stdout="", stderr="forced failure"
        ),
    )
    monkeypatch.setattr(
        repository_sota_closeout,
        "_run_conditional_registered_gates",
        lambda **kwargs: [],
    )

    findings = repository_sota_closeout._run_fail_closed_subprocess_gates(
        SimpleNamespace(skip_generated_checks=False, subprocess_receipt_dir=None)
    )

    assert [(finding.gate, finding.message) for finding in findings] == [
        ("owned-child", "subprocess gate failed")
    ]


@pytest.mark.parametrize("status_override", ["; true", " | true"])
def test_phase5_release_owner_rejects_swallowed_child_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status_override: str,
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    fragments = "$" + "{{ needs.prepare-release.outputs.fragments_dir }}"
    release = tmp_path / "release.yml"
    release.write_text(
        "jobs:\n"
        "  prepare-release:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps: []\n"
        "  release-gates:\n"
        "    runs-on: ubuntu-latest\n"
        "    defaults:\n"
        "      run:\n"
        "        working-directory: policy-engine\n"
        "    needs: prepare-release\n"
        "    steps:\n"
        "      - name: Checkout\n"
        "        uses: actions/checkout@v4\n"
        "      - name: Operability\n"
        "        run: |\n"
        "          uv run polisyos-tools release check-operability-release-gates "
        f"--fragments-dir '{fragments}' "
        f"--fail-closed --json-output /tmp/release-operability-gates.json{status_override}\n"
        "      - name: Compatibility\n"
        "        run: |\n"
        "          uv run polisyos-tools release check-compatibility-release-gates "
        f"--fragments-dir '{fragments}' "
        "--fail-on-contract-errors --json-output /tmp/release-compatibility-gates.json\n",
        encoding="utf-8",
    )
    original_resolve = repository_sota_closeout._resolve
    monkeypatch.setattr(
        repository_sota_closeout,
        "_resolve",
        lambda path: release
        if path == "../.github/workflows/release.yml"
        else original_resolve(path),
    )

    findings = repository_sota_closeout._check_last_mile_gate_ownership()

    if status_override == "; true":
        assert not any(
            finding.gate == "last-mile-wiring" and "operability-release" in finding.message
            for finding in findings
        )
    else:
        assert any(
            finding.gate == "last-mile-wiring" and "operability-release" in finding.message
            for finding in findings
        )
    assert not any(
        finding.gate == "last-mile-wiring" and "compatibility-release" in finding.message
        for finding in findings
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


def test_phase5_wiring_rejects_contract_mode_substituted_with_full_wave(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    contents = {
        ".pre-commit-config.yaml": (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: repository-sota-closeout\n"
            "        entry: bash -lc 'cd policy-engine && uv run polisyos-tools "
            "workspace repository-sota-closeout --contract-only'\n"
            "        language: system\n"
            "        always_run: true\n"
            "        pass_filenames: false\n"
        ),
        "../.github/workflows/abi.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Wrong mode\n"
            "        run: uv run polisyos-tools workspace repository-sota-closeout\n"
        ),
        "ops/ci/templates/workflows/arch.yml": (
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - name: Full closeout\n"
            "        run: uv run polisyos-tools workspace repository-sota-closeout\n"
        ),
    }
    contents = _phase5_apply_workflow_fixture_profile(contents)
    resolved = {}
    for relative_path, content in contents.items():
        path = tmp_path / relative_path.replace("/", "_").replace("..", "parent")
        path.write_text(content, encoding="utf-8")
        resolved[relative_path] = path

    monkeypatch.setattr(repository_sota_closeout, "_resolve", resolved.__getitem__)
    monkeypatch.setattr(repository_sota_closeout, "_check_last_mile_gate_ownership", lambda: [])

    findings = repository_sota_closeout._check_wiring()

    assert [finding.detail for finding in findings] == ["../.github/workflows/abi.yml"]


def test_phase5_last_mile_owner_requires_ci_parity_dispatch_with_marker_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.devx.workspace import ci_parity, repository_sota_closeout

    original_commands = ci_parity._last_mile_policy_commands
    monkeypatch.setattr(
        ci_parity,
        "_last_mile_policy_commands",
        lambda *, skip_docs: [
            command
            for command in original_commands(skip_docs=skip_docs)
            if not any("directory_health.py" in token for token in command.argv)
        ],
    )

    findings = repository_sota_closeout._check_last_mile_gate_ownership()

    assert any(
        finding.gate == "last-mile-wiring" and "directory-health" in finding.message
        for finding in findings
    )
    source = (REPO_ROOT / "tools/devx/workspace/ci_parity.py").read_text(encoding="utf-8")
    assert "directory_health.py" in source


def test_phase5_last_mile_release_owner_requires_active_command_with_marker_retained(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    release = tmp_path / "release.yml"
    release.write_text(
        "jobs:\n"
        "  prepare:\n"
        "    runs-on: ubuntu-latest\n"
        "    defaults:\n"
        "      run:\n"
        "        working-directory: policy-engine\n"
        "    steps:\n"
        "      - name: Checkout\n"
        "        uses: actions/checkout@v4\n"
        "      - name: declaration only\n"
        "        run: echo 'uv run polisyos-tools release check-operability-release-gates'\n"
        "      - name: compatibility\n"
        "        run: >-\n"
        "          uv run polisyos-tools release check-compatibility-release-gates "
        '          --fragments-dir "${{ needs.prepare-release.outputs.fragments_dir }}" '
        "          --fail-on-contract-errors "
        "          --json-output /tmp/release-compatibility-gates.json\n",
        encoding="utf-8",
    )
    original_resolve = repository_sota_closeout._resolve
    monkeypatch.setattr(
        repository_sota_closeout,
        "_resolve",
        lambda path: release
        if path == "../.github/workflows/release.yml"
        else original_resolve(path),
    )

    findings = repository_sota_closeout._check_last_mile_gate_ownership()

    assert any(
        finding.gate == "last-mile-wiring" and "operability-release" in finding.message
        for finding in findings
    )
    assert not any(
        finding.gate == "last-mile-wiring" and "compatibility-release" in finding.message
        for finding in findings
    )


@pytest.mark.parametrize(
    "dependency_mutation", ["missing", "conditional", "continue-on-error", "nested-needs"]
)
def test_phase5_release_owner_rejects_nonfailclosed_dependency_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    dependency_mutation: str,
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    release = tmp_path / "release.yml"
    dependency = "    runs-on: ubuntu-latest\n"
    if dependency_mutation == "conditional":
        dependency += "    if: github.ref != ''\n"
    elif dependency_mutation == "continue-on-error":
        dependency += "    continue-on-error: true\n"
    elif dependency_mutation == "nested-needs":
        dependency += "    needs: earlier\n"
    release.write_text(
        "jobs:\n"
        "  prepare-release:\n" + dependency + "    steps: []\n"
        "  release-gates:\n"
        "    runs-on: ubuntu-latest\n"
        "    defaults:\n"
        "      run:\n"
        "        working-directory: policy-engine\n"
        + (
            "    needs: absent\n"
            if dependency_mutation == "missing"
            else "    needs: prepare-release\n"
        )
        + "    steps:\n"
        "      - name: Checkout\n"
        "        uses: actions/checkout@v4\n"
        "      - name: Operability\n"
        "        run: uv run polisyos-tools release check-operability-release-gates "
        "--fragments-dir '${{ needs.prepare-release.outputs.fragments_dir }}' "
        "--fail-closed --json-output /tmp/release-operability-gates.json\n"
        "      - name: Compatibility\n"
        "        run: uv run polisyos-tools release check-compatibility-release-gates "
        "--fragments-dir '${{ needs.prepare-release.outputs.fragments_dir }}' "
        "--fail-on-contract-errors --json-output /tmp/release-compatibility-gates.json\n",
        encoding="utf-8",
    )
    original_resolve = repository_sota_closeout._resolve
    monkeypatch.setattr(
        repository_sota_closeout,
        "_resolve",
        lambda path: release
        if path == "../.github/workflows/release.yml"
        else original_resolve(path),
    )

    findings = repository_sota_closeout._check_last_mile_gate_ownership()

    assert any(
        finding.gate == "last-mile-wiring" and "operability-release" in finding.message
        for finding in findings
    )
    assert any(
        finding.gate == "last-mile-wiring" and "compatibility-release" in finding.message
        for finding in findings
    )


def _phase5_wiring_documents() -> dict[str, object]:
    contract = "uv run polisyos-tools workspace repository-sota-closeout --contract-only"
    full = "uv run polisyos-tools workspace repository-sota-closeout"
    precommit = {
        "repos": [
            {
                "repo": "local",
                "hooks": [
                    {
                        "id": "repository-sota-closeout",
                        "entry": f"bash -lc 'cd policy-engine && {contract}'",
                        "language": "system",
                        "pass_filenames": False,
                        "always_run": True,
                    }
                ],
            }
        ]
    }
    abi_checkout = {"name": "Checkout", "uses": "actions/checkout@v4"}
    architecture_checkout = {"name": "Checkout", "uses": "actions/checkout@v4"}
    abi = {
        "jobs": {
            "quality": {
                "runs-on": "ubuntu-latest",
                "defaults": {"run": {"working-directory": "policy-engine"}},
                "steps": [abi_checkout, {"name": "Contract", "run": contract}],
            }
        }
    }
    architecture = {
        "jobs": {
            "architecture": {
                "runs-on": "ubuntu-latest",
                "steps": [architecture_checkout, {"name": "Full closeout", "run": full}],
            }
        }
    }
    return {
        ".pre-commit-config.yaml": precommit,
        "../.github/workflows/abi.yml": abi,
        "ops/ci/templates/workflows/arch.yml": architecture,
    }


def _phase5_run_wiring_documents(
    documents: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> list[object]:
    import yaml

    from tools.devx.workspace import repository_sota_closeout

    resolved: dict[str, Path] = {}
    for relative_path, document in documents.items():
        path = tmp_path / (str(len(resolved)) + ".yaml")
        path.write_text(
            document if isinstance(document, str) else yaml.safe_dump(document),
            encoding="utf-8",
        )
        resolved[relative_path] = path
    monkeypatch.setattr(repository_sota_closeout, "_resolve", resolved.__getitem__)
    monkeypatch.setattr(repository_sota_closeout, "_check_last_mile_gate_ownership", lambda: [])
    return repository_sota_closeout._check_wiring()


def _phase5_set_nested(payload: dict[str, object], keys: tuple[str, ...], value: object) -> None:
    current: dict[str, object] = payload
    for key in keys[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[keys[-1]] = value


def test_phase5_wiring_context_profile_accepts_current_route_shapes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    findings = _phase5_run_wiring_documents(_phase5_wiring_documents(), monkeypatch, tmp_path)

    assert findings == []


@pytest.mark.parametrize(
    ("scope", "keys", "value"),
    [
        ("workflow", ("defaults", "run", "working-directory"), "."),
        ("job", ("defaults", "run", "working-directory"), "."),
        ("step", ("working-directory",), "apps/runtime-dashboard"),
        ("workflow", ("defaults", "run", "shell"), "pwsh"),
        ("step", ("shell",), "bash {0}"),
        ("job", ("continue-on-error",), True),
        ("step", ("continue-on-error",), True),
        ("job", ("if",), False),
        ("step", ("if",), "${{ success() }}"),
        ("job", ("needs",), ["preflight"]),
        ("job", ("container",), {"image": "ubuntu:latest"}),
        ("step", ("background",), True),
        ("workflow", ("env",), {"PATH": "/opt/untrusted-bin"}),
        ("step", ("env",), {"PATH": "/opt/untrusted-bin"}),
        ("job", ("environment",), "approval-gated"),
        ("job", ("runs-on",), "ubuntu-custom"),
    ],
)
def test_phase5_wiring_rejects_outcome_relevant_context_mutations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scope: str,
    keys: tuple[str, ...],
    value: object,
) -> None:
    documents = _phase5_wiring_documents()
    payload = documents["../.github/workflows/abi.yml"]
    assert isinstance(payload, dict)
    job = payload["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(job, dict)
    if scope == "workflow":
        if keys == ("defaults", "run", "working-directory"):
            job.pop("defaults", None)
        _phase5_set_nested(payload, keys, value)
    elif scope == "job":
        _phase5_set_nested(job, keys, value)
    else:
        step = job["steps"][1]
        assert isinstance(step, dict)
        _phase5_set_nested(step, keys, value)

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert "../.github/workflows/abi.yml" in {finding.detail for finding in findings}


def test_phase5_wiring_uses_specificity_for_effective_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    abi["defaults"] = {"run": {"shell": "pwsh", "working-directory": "."}}
    job = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(job, dict)
    job["defaults"] = {"run": {"shell": "bash"}}
    step = job["steps"][1]
    assert isinstance(step, dict)
    step["working-directory"] = "policy-engine"

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert findings == []


def test_phase5_wiring_tracks_nested_shell_cwd_from_git_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documents = _phase5_wiring_documents()
    precommit = documents[".pre-commit-config.yaml"]
    assert isinstance(precommit, dict)
    hook = precommit["repos"][0]["hooks"][0]  # type: ignore[index]
    assert isinstance(hook, dict)
    hook["entry"] = (
        "bash -lc 'cd policy-engine && bash -c \"uv run polisyos-tools "
        "workspace repository-sota-closeout --contract-only\"'"
    )

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert findings == []


@pytest.mark.parametrize(
    "entry",
    [
        "bash -lc 'cd .. && uv run polisyos-tools workspace repository-sota-closeout "
        "--contract-only'",
        "bash -lc 'cd policy-engine && cd .. && uv run polisyos-tools workspace "
        "repository-sota-closeout --contract-only'",
        "bash -lc 'cd missing && uv run polisyos-tools workspace "
        "repository-sota-closeout --contract-only'",
    ],
)
def test_phase5_wiring_rejects_precommit_context_escape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, entry: str
) -> None:
    documents = _phase5_wiring_documents()
    precommit = documents[".pre-commit-config.yaml"]
    assert isinstance(precommit, dict)
    hook = precommit["repos"][0]["hooks"][0]  # type: ignore[index]
    assert isinstance(hook, dict)
    hook["entry"] = entry

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert ".pre-commit-config.yaml" in {finding.detail for finding in findings}


def test_phase5_wiring_rejects_duplicate_yaml_keys_in_route_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    text = __import__("yaml").safe_dump(abi)
    text = text.replace(
        "        working-directory: policy-engine\n",
        "        working-directory: policy-engine\n        working-directory: .\n",
        1,
    )
    documents["../.github/workflows/abi.yml"] = text

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert "../.github/workflows/abi.yml" in {finding.detail for finding in findings}


def test_phase5_wiring_rejects_yaml_merge_keys_in_route_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documents = _phase5_wiring_documents()
    documents["../.github/workflows/abi.yml"] = (
        "defaults: &route-defaults\n"
        "  run:\n"
        "    working-directory: policy-engine\n"
        "jobs:\n"
        "  quality:\n"
        "    runs-on: ubuntu-latest\n"
        "    defaults:\n"
        "      <<: *route-defaults\n"
        "    steps:\n"
        "      - name: Contract\n"
        "        run: uv run polisyos-tools workspace repository-sota-closeout --contract-only\n"
    )

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert "../.github/workflows/abi.yml" in {finding.detail for finding in findings}


def test_phase5_wiring_rejects_non_propagating_nested_route_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documents = _phase5_wiring_documents()
    precommit = documents[".pre-commit-config.yaml"]
    assert isinstance(precommit, dict)
    hook = precommit["repos"][0]["hooks"][0]  # type: ignore[index]
    assert isinstance(hook, dict)
    hook["entry"] = (
        "bash -lc 'cd policy-engine && uv run polisyos-tools workspace "
        "repository-sota-closeout --contract-only; true'"
    )

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert ".pre-commit-config.yaml" in {finding.detail for finding in findings}


def test_phase5_wiring_rejects_missing_job_working_directory_from_github_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    quality = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(quality, dict)
    quality.pop("defaults")

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert "../.github/workflows/abi.yml" in {finding.detail for finding in findings}


@pytest.mark.parametrize(
    "checkout_mutation",
    [
        "missing",
        "after-route",
        "dynamic-path",
        "parent-escape",
        "alternate-repository",
        "sparse-checkout",
    ],
)
def test_phase5_wiring_fails_closed_without_static_prior_source_checkout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, checkout_mutation: str
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    quality = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(quality, dict)
    steps = quality["steps"]
    assert isinstance(steps, list)
    checkout = steps[0]
    assert isinstance(checkout, dict)
    if checkout_mutation == "missing":
        steps.pop(0)
    elif checkout_mutation == "after-route":
        steps.append(steps.pop(0))
    elif checkout_mutation == "dynamic-path":
        checkout["with"] = {"path": "${{ matrix.checkout_path }}"}
    elif checkout_mutation == "parent-escape":
        checkout["with"] = {"path": "../outside"}
    elif checkout_mutation == "alternate-repository":
        checkout["with"] = {"repository": "another/project"}
    else:
        checkout["with"] = {"sparse-checkout": "policy-engine"}

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert "../.github/workflows/abi.yml" in {finding.detail for finding in findings}


def test_phase5_wiring_rejects_product_cwd_that_ignores_checkout_prefix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    quality = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(quality, dict)
    checkout = quality["steps"][0]
    assert isinstance(checkout, dict)
    checkout["with"] = {"path": "workspace/source"}

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    abi_findings = [
        finding for finding in findings if finding.detail == "../.github/workflows/abi.yml"
    ]
    assert len(abi_findings) == 1
    assert "source-relative expected root" in abi_findings[0].message


def test_phase5_wiring_resolves_product_from_literal_checkout_prefix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    quality = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(quality, dict)
    checkout = quality["steps"][0]
    assert isinstance(checkout, dict)
    checkout["with"] = {"path": "workspace/source"}
    defaults = quality["defaults"]
    assert isinstance(defaults, dict)
    run_defaults = defaults["run"]
    assert isinstance(run_defaults, dict)
    run_defaults["working-directory"] = "workspace/source/policy-engine"

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert findings == []


@pytest.mark.parametrize("path_key", ["path", "PATH", "PaTh"])
def test_phase5_wiring_normalizes_checkout_path_input_case(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, path_key: str
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    quality = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(quality, dict)
    checkout = quality["steps"][0]
    assert isinstance(checkout, dict)
    checkout["with"] = {path_key: "workspace/source"}
    defaults = quality["defaults"]
    assert isinstance(defaults, dict)
    run_defaults = defaults["run"]
    assert isinstance(run_defaults, dict)
    run_defaults["working-directory"] = "workspace/source/policy-engine"

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert findings == []


def test_phase5_wiring_rejects_case_normalized_checkout_path_false_green(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    quality = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(quality, dict)
    checkout = quality["steps"][0]
    assert isinstance(checkout, dict)
    checkout["with"] = {"PATH": "workspace/source"}

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    abi_findings = [
        finding
        for finding in findings
        if getattr(finding, "detail", None) == "../.github/workflows/abi.yml"
    ]
    assert len(abi_findings) == 1
    assert "source-relative expected root" in abi_findings[0].message


def test_phase5_wiring_rejects_casefold_colliding_checkout_input_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    quality = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(quality, dict)
    checkout = quality["steps"][0]
    assert isinstance(checkout, dict)
    checkout["with"] = {"path": "workspace/source", "PATH": "another/source"}

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    abi_findings = [
        finding
        for finding in findings
        if getattr(finding, "detail", None) == "../.github/workflows/abi.yml"
    ]
    assert len(abi_findings) == 1
    assert "collide after case-insensitive normalization" in abi_findings[0].message


_ACTIONS_CHECKOUT_V4_2_2_INPUT_IDS = (
    "repository",
    "ref",
    "token",
    "ssh-key",
    "ssh-known-hosts",
    "ssh-strict",
    "ssh-user",
    "persist-credentials",
    "path",
    "clean",
    "filter",
    "sparse-checkout",
    "sparse-checkout-cone-mode",
    "fetch-depth",
    "fetch-tags",
    "show-progress",
    "lfs",
    "submodules",
    "set-safe-directory",
    "github-server-url",
)


@pytest.mark.parametrize(
    "input_name",
    [
        spelling
        for input_name in _ACTIONS_CHECKOUT_V4_2_2_INPUT_IDS
        if input_name not in {"path", "fetch-depth"}
        for spelling in (input_name, input_name.upper())
    ],
)
def test_phase5_wiring_fails_closed_for_every_other_declared_checkout_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, input_name: str
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    quality = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(quality, dict)
    checkout = quality["steps"][0]
    assert isinstance(checkout, dict)
    checkout["with"] = {input_name: "non-empty-value"}

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert "../.github/workflows/abi.yml" in {finding.detail for finding in findings}


@pytest.mark.parametrize(
    "checkout_inputs",
    [
        {None: "workspace/source"},
        {"path": ""},
        {"path": False},
        {"path": 0},
        {"path": None},
        {"fetch-depth": ""},
        {"fetch-depth": False},
        {"fetch-depth": None},
        {"fetch-depth": -1},
        {"fetch-depth": 1.5},
        {"unknown-input": "value"},
    ],
    ids=[
        "non-string-key",
        "empty-path",
        "boolean-path",
        "numeric-path",
        "null-path",
        "empty-fetch-depth",
        "boolean-fetch-depth",
        "null-fetch-depth",
        "negative-fetch-depth",
        "fractional-fetch-depth",
        "unknown-field",
    ],
)
def test_phase5_wiring_fails_closed_for_malformed_checkout_input_maps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, checkout_inputs: dict[object, object]
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    quality = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(quality, dict)
    checkout = quality["steps"][0]
    assert isinstance(checkout, dict)
    checkout["with"] = checkout_inputs

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert "../.github/workflows/abi.yml" in {finding.detail for finding in findings}


@pytest.mark.parametrize("with_inputs", [None, "path: other", ["path", "other"]])
def test_phase5_wiring_rejects_non_mapping_checkout_with_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, with_inputs: object
) -> None:
    documents = _phase5_wiring_documents()
    abi = documents["../.github/workflows/abi.yml"]
    assert isinstance(abi, dict)
    quality = abi["jobs"]["quality"]  # type: ignore[index]
    assert isinstance(quality, dict)
    checkout = quality["steps"][0]
    assert isinstance(checkout, dict)
    checkout["with"] = with_inputs

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert "../.github/workflows/abi.yml" in {finding.detail for finding in findings}


@pytest.mark.parametrize("fetch_depth", [0, 1, 2, "0", "1", "2"])
def test_phase5_wiring_accepts_nonnegative_integer_fetch_depth_literals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fetch_depth: int | str
) -> None:
    documents = _phase5_wiring_documents()
    architecture = documents["ops/ci/templates/workflows/arch.yml"]
    assert isinstance(architecture, dict)
    job = architecture["jobs"]["architecture"]  # type: ignore[index]
    assert isinstance(job, dict)
    checkout = job["steps"][0]
    assert isinstance(checkout, dict)
    checkout["with"] = {"fetch-depth": fetch_depth}

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert findings == []


@pytest.mark.parametrize("input_name", ["FETCH-DEPTH", "Fetch-Depth"])
def test_phase5_wiring_normalizes_fetch_depth_input_case(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, input_name: str
) -> None:
    documents = _phase5_wiring_documents()
    architecture = documents["ops/ci/templates/workflows/arch.yml"]
    assert isinstance(architecture, dict)
    job = architecture["jobs"]["architecture"]  # type: ignore[index]
    assert isinstance(job, dict)
    checkout = job["steps"][0]
    assert isinstance(checkout, dict)
    checkout["with"] = {input_name: 0}

    findings = _phase5_run_wiring_documents(documents, monkeypatch, tmp_path)

    assert findings == []


def test_phase5_release_command_inventory_uses_checkout_source_prefix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tools.devx.workspace import repository_sota_closeout

    release = tmp_path / "release.yml"
    release.write_text(
        "jobs:\n"
        "  release-gates:\n"
        "    runs-on: ubuntu-latest\n"
        "    defaults:\n"
        "      run:\n"
        "        working-directory: workspace/source/policy-engine\n"
        "    steps:\n"
        "      - name: Checkout\n"
        "        uses: actions/checkout@v4\n"
        "        with:\n"
        "          path: workspace/source\n"
        "      - name: Operability\n"
        "        run: uv run polisyos-tools release check-operability-release-gates --fail-closed\n"
        "      - name: Compatibility\n"
        "        run: uv run polisyos-tools release check-compatibility-release-gates --fail-on-contract-errors\n",
        encoding="utf-8",
    )
    original_resolve = repository_sota_closeout._resolve
    monkeypatch.setattr(
        repository_sota_closeout,
        "_resolve",
        lambda path: release
        if path == "../.github/workflows/release.yml"
        else original_resolve(path),
    )

    commands, error = repository_sota_closeout._workflow_commands(
        "../.github/workflows/release.yml"
    )

    assert error is None
    assert any(
        "check-operability-release-gates" in token for command in commands for token in command
    )
    assert any(
        "check-compatibility-release-gates" in token for command in commands for token in command
    )

    release.write_text(
        release.read_text(encoding="utf-8").replace(
            "path: workspace/source\n", "path: workspace/other-source\n"
        ),
        encoding="utf-8",
    )

    commands, error = repository_sota_closeout._workflow_commands(
        "../.github/workflows/release.yml"
    )

    assert error is None
    assert commands == []
