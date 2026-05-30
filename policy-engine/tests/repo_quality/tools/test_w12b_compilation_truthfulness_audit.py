from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import run_compilation_truthfulness_audit as w12b

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    REPO_ROOT
    / "architecture/policy_design_case/wave12b_compilation_truthfulness_audit_manifest.json"
)


def test_w12b_manifest_is_deterministic_and_runs_w11e_corpus_audit() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest == w12b.build_w12b_manifest()
    assert manifest["schema_version"] == w12b.MANIFEST_SCHEMA_VERSION
    assert manifest["phase_id"] == "W12.B"
    assert manifest["w11e_tool_ref"] == (
        "repo://tools/quality/validation/check_compilation_truthfulness.py"
    )
    assert manifest["floor_policy"]["governed-pilot"]["minimum_case_score"] == 50.0
    assert manifest["floor_policy"]["production-capable"]["minimum_case_score"] == 70.0
    assert "--corpus tests/fixtures/universal-corpus" in manifest["command_contract"]["command"]
    assert manifest["metric_policy"]["typed_blockers_count_as_useful_design"] is False
    assert manifest["metric_policy"]["typed_blockers_are_closeout_honesty_failures"] is False


def test_governed_pilot_low_case_score_becomes_typed_compilation_blocker() -> None:
    report = w12b.build_w12b_compilation_truthfulness_audit(
        _truthfulness_report(
            case_scores={
                "housing-pass": ("housing", "production", 80.0),
                "tax-low": ("tax", "production", 40.0),
            }
        ),
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
        raw_report_ref="repo://_build/.tmp/production-quality/compilation_truthfulness.json",
        rollout_posture="governed-pilot",
    )

    assert report["status"] == "blocked"
    assert report["summary"]["aggregate_compilation_truthfulness_rate"] == 60.0
    assert report["summary"]["construct_level_truthfulness"] == {
        "true_positive_construct_count": 2,
        "missed_construct_count": 0,
        "hallucinated_construct_count": 0,
        "authority_drift_construct_count": 0,
    }
    assert report["floor_evaluation"]["status"] == "not_met"
    assert report["floor_evaluation"]["minimum_case_score"] == 50.0
    assert report["floor_evaluation"]["below_floor_case_ids"] == ["tax-low"]
    low_case = next(case for case in report["cases"] if case["case_id"] == "tax-low")
    assert low_case["floor_status"] == "below_floor"
    assert low_case["per_case_truthfulness_score"] == 40.0
    assert set(w12b.W11E_BUCKETS) <= set(low_case)

    case_blocker = next(
        blocker
        for blocker in report["typed_compilation_blockers"]
        if blocker["code"] == "compilation_truthfulness_case_below_floor"
    )
    assert case_blocker["case_id"] == "tax-low"
    assert case_blocker["owner"] == "team-evaluation"
    assert case_blocker["counts_as_useful_design"] is False
    assert case_blocker["counts_as_closeout_honesty_failure"] is False
    assert case_blocker["blocks_rollout_posture"] is True


def test_research_only_reports_low_truthfulness_without_floor_blocker() -> None:
    report = w12b.build_w12b_compilation_truthfulness_audit(
        _truthfulness_report(
            case_scores={
                "research-low": ("housing", "research", 0.0),
            }
        ),
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
        raw_report_ref="repo://_build/.tmp/production-quality/compilation_truthfulness.json",
        rollout_posture="research-only",
    )

    assert report["status"] == "pass"
    assert report["floor_evaluation"]["status"] == "not_required"
    assert report["typed_compilation_blockers"] == []
    assert report["metric_policy"]["typed_blockers_count_as_useful_design"] is False
    assert report["metric_policy"]["typed_blockers_are_closeout_honesty_failures"] is False


def test_w12b_cli_can_decorate_existing_w11e_report(tmp_path: Path) -> None:
    input_report = tmp_path / "w11e.json"
    output_report = tmp_path / "w12b.json"
    input_report.write_text(
        json.dumps(
            _truthfulness_report(
                case_scores={
                    "case-pass": ("housing", "production", 100.0),
                }
            )
        ),
        encoding="utf-8",
    )

    exit_code = w12b.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--input-report",
            str(input_report),
            "--rollout-posture",
            "production-capable",
            "--output",
            str(output_report),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_report.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["summary"]["case_count"] == 1
    assert payload["typed_compilation_blockers"] == []


def _truthfulness_report(
    *,
    case_scores: dict[str, tuple[str, str, float]],
) -> dict[str, object]:
    cases = [
        _case(case_id=case_id, domain=domain, authority_level=authority_level, score=score)
        for case_id, (domain, authority_level, score) in case_scores.items()
    ]
    return {
        "schema_version": "policyos.policy_design_case.compilation_truthfulness.v1",
        "tool": "quality.validation.check-compilation-truthfulness",
        "generated_at": "2026-05-24T00:00:00Z",
        "repo_root": str(REPO_ROOT),
        "corpus_path": str(REPO_ROOT / "tests/fixtures/universal-corpus"),
        "summary": {
            "status": "pass",
            "case_count": len(cases),
            "blocked_case_count": 0,
            "aggregate_compilation_truthfulness_rate": round(
                sum(float(case["per_case_truthfulness_score"]) for case in cases)
                / len(cases),
                2,
            ),
            "by_domain": _slice_summary(cases, "domain"),
            "by_authority_level": _slice_summary(cases, "authority_level"),
            "construct_vocabulary": {
                "reported": True,
                "true_positive_construct_count": len(cases),
                "missed_construct_count": 0,
                "hallucinated_construct_count": 0,
                "authority_drift_construct_count": 0,
            },
        },
        "cases": cases,
        "issues": [],
    }


def _case(
    *,
    case_id: str,
    domain: str,
    authority_level: str,
    score: float,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "source_path": f"fixture://{case_id}",
        "domain": domain,
        "authority_level": authority_level,
        "status": "pass",
        "compilation_status": "pass",
        "producer_pipeline_status": "pass",
        "obligation_graph_ref": f"obligation-graph-{case_id}",
        "claim_decomposition_ref": f"claim-ledger:{case_id}",
        "producer_pipeline_ref": f"producer-pipeline:{case_id}",
        "adjudication_label": "semantic_pass",
        "score_weights": {},
        "true_positive_obligations": [{"annotation_id": f"ann-{case_id}"}],
        "missed_obligations": [],
        "hallucinated_obligations": [],
        "scope_drift_obligations": [],
        "authority_drift_obligations": [],
        "construct_vocabulary": {
            "reported": True,
            "compiled_constructs": [f"construct:{domain}_compiled"],
            "expected_constructs": [f"construct:{domain}_compiled"],
            "true_positive_constructs": [f"construct:{domain}_compiled"],
            "missed_constructs": [],
            "hallucinated_constructs": [],
            "authority_drift_constructs": [],
        },
        "per_case_truthfulness_score": score,
        "issues": [],
    }


def _slice_summary(cases: list[dict[str, object]], field: str) -> dict[str, dict[str, object]]:
    values = sorted({str(case[field]) for case in cases})
    return {
        value: {
            "case_count": len(rows := [case for case in cases if case[field] == value]),
            "blocked_case_count": 0,
            "aggregate_compilation_truthfulness_rate": round(
                sum(float(case["per_case_truthfulness_score"]) for case in rows)
                / len(rows),
                2,
            ),
        }
        for value in values
    }
