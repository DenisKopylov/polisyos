from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.quality.validation import (
    run_policy_design_case_local_validation_ladder as ladder,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    REPO_ROOT / "architecture/policy_design_case/wave6_local_validation_ladder_manifest.json"
)


def test_w6a_manifest_is_deterministic_and_covers_required_categories() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest == ladder.build_ladder_manifest()
    assert manifest["schema_version"] == ladder.MANIFEST_SCHEMA_VERSION
    assert manifest["status"] == "implemented"
    assert manifest["phase_id"] == "W12.A"
    assert manifest["legacy_phase_id"] == "W6.A"
    assert manifest["manifest_path_compatibility"]["preserved_path"] == (
        "architecture/policy_design_case/wave6_local_validation_ladder_manifest.json"
    )
    assert manifest["metric_policy"]["compilation_truthfulness_source"] == "W11.E"
    assert manifest["metric_policy"]["typed_blockers_count_as_useful_design"] is False
    assert manifest["metric_policy"]["accepted_deficits_count_as_useful_design"] is False

    for profile in ("quick", "full"):
        commands = manifest["profile_commands"][profile]
        categories = {command["category"] for command in commands}
        assert {
            "unit",
            "repo_quality",
            "semantic",
            "local_production_debug",
            "universal_compilation_smoke",
            "capability_graph_audit",
        } <= categories
        assert all(command["owner"] and command["next_action"] for command in commands)

    full_commands = {
        command["command_id"]: command["command"]
        for command in manifest["profile_commands"]["full"]
    }
    assert "tests/unit/runtime/quality" in full_commands["unit_runtime_quality"]
    assert "tests/unit/scientist" in full_commands["unit_policy_producers"]
    assert (
        "tests/repo_quality/tools/test_evidence_bundle_inspection.py"
        in full_commands["repo_quality_closeout"]
    )
    assert (
        "check_compilation_truthfulness.py --corpus tests/fixtures/universal-corpus"
        in (full_commands["compilation_truthfulness_corpus"])
    )
    assert (
        "check_domain_coverage_breadth.py --corpus tests/fixtures/universal-corpus"
        in (full_commands["domain_coverage_breadth_corpus"])
    )
    assert (
        "check_critic_ensemble_diversity.py --input tests/fixtures/universal-corpus"
        in (full_commands["critic_ensemble_diversity_corpus"])
    )
    assert (
        "tools/quality/testing/local_prod_debug_probe.py" in full_commands["local_prod_debug_quick"]
    )
    assert "test_policy_evidence_capability_exports.py" in full_commands["capability_graph_exports"]


def test_w12a_uses_structured_child_status_when_command_exits_zero(
    tmp_path: Path,
    monkeypatch,
) -> None:
    command = ladder._local_prod_debug_command()
    assert "--require-passing" in command.argv
    child_report = {
        "schema_version": "policyos.local_prod_debug_probe.v1",
        "summary": {
            "status": "warn",
            "total": 1,
            "passed": 0,
            "warned": 1,
            "failed": 0,
            "skipped": 0,
            "invalid": 0,
        },
        "checks": [
            {
                "name": "production-data-static",
                "status": "warn",
                "code": "production_data_scenario_contracts_missing",
                "details": {"missing_scenario_source_families": ["credit_program_registry"]},
            }
        ],
    }

    def _run_child(
        argv: tuple[str, ...],
        *,
        cwd: Path,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> SimpleNamespace:
        assert argv == command.argv
        assert capture_output and text and timeout == command.timeout_s and not check
        output_path = cwd / argv[argv.index("--output") + 1]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(child_report), encoding="utf-8")
        return SimpleNamespace(
            returncode=0,
            stdout="Local prod-debug probe: warn (0 passed, 1 warned, 0 failed, 0 skipped)",
            stderr="",
        )

    monkeypatch.setattr(ladder, "run_command", _run_child)

    payload = ladder.run_local_validation_ladder(
        repo_root=tmp_path,
        profile="quick",
        only_command_ids=(command.command_id,),
        executor=ladder.execute_command,
    )

    row = payload["commands"][0]
    assert row["exit_code"] == 0
    assert row["status"] == "fail"
    assert row["reported_statuses"] == [
        {
            "output_ref": command.output_refs[0],
            "json_path": "/summary/status",
            "status": "warn",
            "status_state": "present",
            "fresh": True,
            "error": None,
        }
    ]
    assert payload["status"] == "blocked"


@pytest.mark.parametrize(
    ("child_report", "expected_state"),
    [
        pytest.param(
            {"summary": {"status": 7}, "status": "pass"},
            "malformed",
            id="malformed-summary-does-not-fall-back-to-root-status",
        ),
        pytest.param(
            {"summary": None, "status": "pass"},
            "malformed",
            id="malformed-summary-object-does-not-fall-back",
        ),
        pytest.param(
            {"summary": {}, "status": "pass"},
            "missing",
            id="missing-summary-status-does-not-fall-back",
        ),
        pytest.param(
            {"status": "pass"},
            "missing",
            id="root-status-is-not-the-declared-report-contract",
        ),
    ],
)
def test_w12a_rejects_invalid_canonical_status_even_with_root_pass(
    tmp_path: Path,
    monkeypatch,
    child_report: dict[str, object],
    expected_state: str,
) -> None:
    command = ladder.LadderCommand(
        command_id="child_report",
        category="semantic",
        owner="team-evaluation",
        description="Read child report status",
        argv=("child",),
        timeout_s=1,
        next_action="Repair the child report status.",
        output_refs=("child.json",),
    )

    def _run_child(*_args, **_kwargs) -> SimpleNamespace:
        (tmp_path / "child.json").write_text(json.dumps(child_report), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ladder, "run_command", _run_child)

    result = ladder.execute_command(command, tmp_path)

    assert result.status == "fail"
    assert result.exit_code == 0
    observed = result.reported_statuses[0]
    assert observed.json_path == "/summary/status"
    assert observed.status is None
    assert observed.status_state == expected_state
    assert observed.fresh is True
    assert observed.error


def test_w12a_rejects_stale_child_report_when_command_exits_zero(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = tmp_path / "child.json"
    report.write_text(json.dumps({"summary": {"status": "pass"}}), encoding="utf-8")
    command = ladder.LadderCommand(
        command_id="child_report",
        category="semantic",
        owner="team-evaluation",
        description="Read child report status",
        argv=("child",),
        timeout_s=1,
        next_action="Refresh the child report.",
        output_refs=(report.name,),
    )
    monkeypatch.setattr(
        ladder,
        "run_command",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    result = ladder.execute_command(command, tmp_path)

    assert result.status == "fail"
    assert result.error == f"declared output {report.name} was not refreshed by the child"
    assert result.reported_statuses[0].fresh is False


def test_w6a_metrics_keep_closeout_honesty_and_useful_design_separate() -> None:
    corpus = {
        "schema_version": "policyos.policy_design_case.local_outcome_corpus.v1",
        "cases": [
            {
                "case_id": "health-pass",
                "domain_slice": "health",
                "outcome": "pass",
                "authority_laundering": False,
            },
            {
                "case_id": "housing-limited",
                "domain_slice": "housing",
                "outcome": "publish_with_limitation",
                "authority_laundering": False,
            },
            {
                "case_id": "tax-blocked",
                "domain_slice": "tax",
                "outcome": "typed_blocker",
                "authority_laundering": False,
            },
            {
                "case_id": "labor-deficit",
                "domain_slice": "labor",
                "outcome": "accepted_deficit",
                "authority_laundering": False,
            },
        ],
    }

    metrics = ladder.build_local_outcome_metrics(
        corpus,
        corpus_ref="repo://architecture/policy_design_case/test_corpus.json",
        rollout_posture="governed-pilot",
    )

    assert metrics["status"] == "pass"
    assert metrics["closeout_honesty"]["rate"] == 1.0
    assert metrics["useful_design"]["rate"] == 0.5
    assert metrics["useful_design"]["typed_blockers_count_as_useful_design"] is False
    assert metrics["blocker_deficit"]["typed_blocker_count"] == 1
    assert metrics["blocker_deficit"]["accepted_deficit_count"] == 1
    assert metrics["capability_floor"]["status"] == "not_met"
    assert set(metrics["capability_floor"]["missing_useful_domain_slices"]) == {
        "labor",
        "tax",
    }


def test_w12a_can_use_w12d_closeout_honesty_when_local_corpus_missing() -> None:
    metrics = ladder.build_local_outcome_metrics(
        None,
        corpus_ref="repo://architecture/policy_design_case/missing_local_corpus.json",
        rollout_posture="governed-pilot",
        w12d_report_payload={
            "phase_id": "W12.D",
            "summary": {
                "case_count": 13,
                "closeout_honesty_count": 13,
                "closeout_honesty_rate": 1.0,
            },
        },
    )

    assert metrics["status"] == "pass"
    assert metrics["source"] == "W12.D"
    assert metrics["case_count"] == 13
    assert metrics["closeout_honesty"]["rate"] == 1.0
    assert metrics["capability_floor"]["status"] == "not_evaluated"
    assert metrics["capability_floor"]["reason"] == "useful design rate is unavailable"
    assert not any(issue["code"] == "local_outcome_corpus_missing" for issue in metrics["issues"])


def test_w6a_metrics_reject_non_capability_outcomes_counted_as_useful() -> None:
    metrics = ladder.build_local_outcome_metrics(
        {
            "schema_version": "policyos.policy_design_case.local_outcome_corpus.v1",
            "cases": [
                {
                    "case_id": "bad-blocker-count",
                    "domain_slice": "msme",
                    "outcome": "typed_blocker",
                    "authority_laundering": False,
                    "counts_as_useful_design": True,
                }
            ],
        },
        corpus_ref="repo://architecture/policy_design_case/test_corpus.json",
        rollout_posture="research-only",
    )

    assert metrics["status"] == "fail"
    assert metrics["useful_design"]["count"] == 0
    assert any(
        issue["code"] == "non_capability_outcome_counted_as_useful_design"
        for issue in metrics["issues"]
    )


def test_w12a_compilation_truthfulness_metric_has_separate_floor() -> None:
    metrics = ladder.build_compilation_truthfulness_metrics(
        {
            "schema_version": "policyos.policy_design_case.compilation_truthfulness.v1",
            "summary": {
                "status": "pass",
                "case_count": 3,
                "blocked_case_count": 0,
                "aggregate_compilation_truthfulness_rate": 75.0,
                "by_domain": {
                    "housing": {
                        "case_count": 2,
                        "blocked_case_count": 0,
                        "aggregate_compilation_truthfulness_rate": 82.0,
                    },
                    "tax": {
                        "case_count": 1,
                        "blocked_case_count": 0,
                        "aggregate_compilation_truthfulness_rate": 45.0,
                    },
                },
                "by_authority_level": {
                    "production": {
                        "case_count": 3,
                        "blocked_case_count": 0,
                        "aggregate_compilation_truthfulness_rate": 75.0,
                    }
                },
            },
        },
        report_ref="repo://_build/.tmp/production-quality/compilation_truthfulness.json",
        rollout_posture="governed-pilot",
    )

    assert metrics["status"] == "fail"
    assert metrics["rate"] == 75.0
    assert metrics["capability_floor"]["status"] == "not_met"
    assert metrics["capability_floor"]["minimum_aggregate_rate"] == 60.0
    assert metrics["capability_floor"]["minimum_domain_rate"] == 50.0
    assert metrics["capability_floor"]["below_floor_domain_slices"] == ["tax"]
    assert any(
        issue["code"] == "compilation_truthfulness_domain_floor_not_met"
        for issue in metrics["issues"]
    )


def test_w6a_plan_only_report_records_ladder_without_capability_claim() -> None:
    report = ladder.run_local_validation_ladder(
        repo_root=REPO_ROOT,
        profile="quick",
        plan_only=True,
    )

    assert report["schema_version"] == ladder.SCHEMA_VERSION
    assert report["status"] == "planned"
    assert report["capability_statement"]["typed_blockers_count_as_capability_success"] is False
    assert report["capability_statement"]["capability_graph_audit_required"] is True
    hooks = report["capability_graph_validation_hooks"]
    assert hooks["selected_binding_required"] is True
    assert hooks["rejected_alternative_required"] is True
    assert hooks["hypothesis_ledger_required"] is True
    assert report["capability_graph_validation_hooks"]["audit_card_generation_required"] is True
    assert report["local_outcome_metrics"]["status"] == "not_available"
    assert report["compilation_truthfulness_metrics"]["status"] == "not_available"
    assert set(report["outcome_metrics"]) == {
        "closeout_honesty",
        "useful_design",
        "compilation_truthfulness",
    }
    assert {
        "unit",
        "repo_quality",
        "semantic",
        "local_production_debug",
        "universal_compilation_smoke",
    } <= {command["category"] for command in report["commands"]}
    assert all(command["status"] == "skipped" for command in report["commands"])


def test_w6a_command_failure_becomes_typed_blocker_not_useful_capability() -> None:
    def _executor(command: ladder.LadderCommand, _repo_root: Path) -> ladder.CommandResult:
        status = "fail" if command.command_id == "semantic_evaluation_smoke" else "pass"
        return ladder.CommandResult(
            command_id=command.command_id,
            status=status,
            exit_code=1 if status == "fail" else 0,
            duration_ms=7,
            stderr_tail="semantic fixture failed" if status == "fail" else "",
        )

    report = ladder.run_local_validation_ladder(
        repo_root=REPO_ROOT,
        profile="quick",
        executor=_executor,
    )

    assert report["status"] == "blocked"
    assert report["typed_blockers"]
    blocker = report["typed_blockers"][0]
    assert blocker["code"] == "local_validation_command_failed"
    assert blocker["command_id"] == "semantic_evaluation_smoke"
    assert blocker["blocks_cloud_validation"] is True
    assert blocker["counts_as_useful_design"] is False
    assert report["capability_statement"]["typed_blockers_are_useful_diagnostics"] is True


def test_w12a_postgres_dsn_missing_is_environment_blocker_not_honesty_failure() -> None:
    command = next(
        command
        for command in ladder.build_ladder_commands("quick")
        if command.command_id == "local_prod_debug_quick"
    )
    blocker = ladder._typed_blocker_for_command(
        command,
        ladder.CommandResult(
            command_id=command.command_id,
            status="fail",
            exit_code=3,
            duration_ms=7,
            stderr_tail="postgres_dsn_missing",
        ),
    )

    assert blocker["code"] == "local_validation_environment_blocker"
    assert blocker["environment_blocker_code"] == "postgres_dsn_missing"
    assert blocker["blocks_cloud_validation"] is True
    assert blocker["counts_as_closeout_honesty"] is False
    assert blocker["counts_as_useful_design"] is False


def test_w12a_postgres_dsn_missing_in_command_artifact_is_environment_blocker(
    tmp_path: Path,
) -> None:
    output = tmp_path / "local_prod_debug.json"
    output.write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "name": "postgres-lifecycle",
                        "status": "fail",
                        "code": "postgres_dsn_missing",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    command = ladder.LadderCommand(
        command_id="local_prod_debug_quick",
        category="local_production_debug",
        owner="team-platform-runtime",
        description="local prod debug",
        argv=("probe",),
        timeout_s=1,
        next_action="provide DSN",
        output_refs=(output.name,),
    )

    blocker = ladder._typed_blocker_for_command(
        command,
        ladder.CommandResult(
            command_id=command.command_id,
            status="fail",
            exit_code=3,
            duration_ms=7,
            stdout_tail="Local prod-debug probe: invalid (postgres-lifecycle)",
        ),
        repo_root=tmp_path,
    )

    assert blocker["code"] == "local_validation_environment_blocker"
    assert blocker["environment_blocker_code"] == "postgres_dsn_missing"
    assert blocker["counts_as_closeout_honesty"] is False


def test_w12a_universal_compilation_failure_gets_typed_blocker() -> None:
    def _executor(command: ladder.LadderCommand, _repo_root: Path) -> ladder.CommandResult:
        status = "fail" if command.command_id == "compilation_truthfulness_smoke" else "pass"
        return ladder.CommandResult(
            command_id=command.command_id,
            status=status,
            exit_code=1 if status == "fail" else 0,
            duration_ms=7,
            stderr_tail="compilation truthfulness smoke failed" if status == "fail" else "",
        )

    report = ladder.run_local_validation_ladder(
        repo_root=REPO_ROOT,
        profile="quick",
        executor=_executor,
    )

    assert report["status"] == "blocked"
    blocker = next(
        item
        for item in report["typed_blockers"]
        if item["command_id"] == "compilation_truthfulness_smoke"
    )
    assert blocker["code"] == "universal_compilation_smoke_command_failed"
    assert blocker["category"] == "universal_compilation_smoke"
    assert blocker["owner"] == "team-evaluation"
    assert blocker["counts_as_useful_design"] is False
