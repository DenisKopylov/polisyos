from __future__ import annotations

from pathlib import Path

import pytest

from tools.devx.workspace import core_runtime_closeout


def test_core_runtime_closeout_ledger_loads_and_matches_expected_blockers() -> None:
    report = core_runtime_closeout.run_closeout(
        ledger_path=core_runtime_closeout.DEFAULT_LEDGER_PATH,
        plan_path=core_runtime_closeout.DEFAULT_PLAN_PATH,
    )

    assert [entry.workstream_id for entry in report.workstreams] == [
        "WS-0A",
        "WS-0B",
        "WS-0C",
        "WS-0D",
        "WS-1A",
        "WS-1B",
        "WS-1C",
        "WS-1D",
        "WS-2A",
        "WS-2B",
        "WS-2C",
        "WS-2D",
        "WS-3A",
        "WS-3B",
        "WS-3C",
    ]
    assert report.blocking_workstreams == ()
    ws2d = next(entry for entry in report.workstreams if entry.workstream_id == "WS-2D")
    canonical_clients = {
        "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
        "packages/runtime-api-client/canonicalRuntimeApiClient.js",
    }
    retired_private_clients = {
        "packages/runtime-api-client/runtimeApiClient.ts",
        "packages/runtime-api-client/runtimeApiClient.js",
    }
    assert canonical_clients.issubset(ws2d.code_evidence)
    assert retired_private_clients.isdisjoint(ws2d.code_evidence)


def test_core_runtime_closeout_supports_complete_manual_evidence(tmp_path) -> None:
    evidence = tmp_path / "core-runtime-closeout.toml"
    evidence.write_text(
        "\n".join(
            [
                "[manual]",
                "engineering_signoff = true",
                "operator_signoff = true",
                "release_review_bundle = true",
                "reopened_followups = true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = core_runtime_closeout.run_closeout(
        ledger_path=core_runtime_closeout.DEFAULT_LEDGER_PATH,
        plan_path=core_runtime_closeout.DEFAULT_PLAN_PATH,
        manual_evidence=core_runtime_closeout.load_manual_evidence(evidence),
        require_manual_evidence=True,
        manual_path=evidence,
    )

    assert all(check.status == "pass" for check in report.manual_checks)


def test_core_runtime_closeout_summary_and_exit_codes(tmp_path) -> None:
    summary = tmp_path / "core-runtime-closeout.md"

    assert (
        core_runtime_closeout.main(
            [
                "--summary",
                str(summary),
            ]
        )
        == 0
    )
    rendered = summary.read_text(encoding="utf-8")
    assert "WS-2A" in rendered
    assert "Reopen / Residual Gaps" in rendered

    assert core_runtime_closeout.main(["--require-full-closeout"]) == 0


def _write_ws2d_closeout_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    include_canonical_ts: bool = True,
) -> tuple[Path, Path, Path]:
    workspace_root = tmp_path / "workspace"
    product_root = workspace_root / "policy-engine"
    package_root = product_root / "packages" / "runtime-api-client"
    scripts_root = package_root / "scripts"
    scripts_root.mkdir(parents=True)
    (package_root / "README.md").write_text(
        "# Runtime API Client\n", encoding="utf-8"
    )
    (scripts_root / "generate-runtime-api-client.sh").write_text(
        "#!/usr/bin/env bash\n# generator owner marker\n", encoding="utf-8"
    )
    if include_canonical_ts:
        (package_root / "canonicalRuntimeApiClient.ts").write_text(
            "export class RuntimeApiClient {}\n", encoding="utf-8"
        )
    (package_root / "canonicalRuntimeApiClient.js").write_text(
        "export class RuntimeApiClient {}\n", encoding="utf-8"
    )

    ledger_path = product_root / "release" / "core-runtime-closeout.ledger.toml"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text(
        """[[workstreams]]
id = "WS-2D"
title = "API Maturity and Client Ergonomics"
status = "implemented"
summary = "Canonical API client artifacts are present."
blocking_gaps = []
code_evidence = [
  "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
  "packages/runtime-api-client/canonicalRuntimeApiClient.js",
  "packages/runtime-api-client/scripts/generate-runtime-api-client.sh",
]
test_evidence = []
docs_evidence = ["packages/runtime-api-client/README.md"]
ops_evidence = []
ci_evidence = []
""",
        encoding="utf-8",
    )
    plan_path = product_root / "docs/plans/active/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        "### WS-2D. API Maturity and Client Ergonomics\n", encoding="utf-8"
    )
    monkeypatch.setattr(core_runtime_closeout, "PRODUCT_ROOT", product_root)
    monkeypatch.setattr(core_runtime_closeout, "WORKSPACE_ROOT", workspace_root)
    return package_root, ledger_path, plan_path


def test_core_runtime_closeout_accepts_canonical_client_without_raw_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_root, ledger_path, plan_path = _write_ws2d_closeout_fixture(
        tmp_path, monkeypatch
    )

    assert (package_root / "README.md").is_file()
    assert (package_root / "scripts/generate-runtime-api-client.sh").is_file()
    assert (package_root / "canonicalRuntimeApiClient.ts").is_file()
    assert (package_root / "canonicalRuntimeApiClient.js").is_file()
    assert not (package_root / "runtimeApiClient.ts").exists()
    assert not (package_root / "runtimeApiClient.js").exists()

    report = core_runtime_closeout.run_closeout(
        ledger_path=ledger_path, plan_path=plan_path
    )

    assert report.blocking_workstreams == ()
    assert report.workstreams[0].code_evidence[:2] == (
        "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
        "packages/runtime-api-client/canonicalRuntimeApiClient.js",
    )


def test_core_runtime_closeout_rejects_missing_client_with_owner_markers_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_root, ledger_path, plan_path = _write_ws2d_closeout_fixture(
        tmp_path, monkeypatch, include_canonical_ts=False
    )

    assert (package_root / "README.md").is_file()
    assert (package_root / "scripts/generate-runtime-api-client.sh").is_file()
    assert (package_root / "canonicalRuntimeApiClient.js").is_file()
    assert not (package_root / "canonicalRuntimeApiClient.ts").exists()
    assert "canonicalRuntimeApiClient.ts" in ledger_path.read_text(encoding="utf-8")

    with pytest.raises(SystemExit, match="canonicalRuntimeApiClient"):
        core_runtime_closeout.run_closeout(
            ledger_path=ledger_path, plan_path=plan_path
        )
