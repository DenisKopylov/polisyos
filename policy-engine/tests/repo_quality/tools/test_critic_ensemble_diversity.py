from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import check_critic_ensemble_diversity as diversity

REPO_ROOT = Path(__file__).resolve().parents[3]

CRITIC_ROLES = (
    "legal",
    "fiscal",
    "equity",
    "data",
    "implementation",
    "affected_person",
    "adversarial",
    "monitoring",
)


def test_critic_ensemble_diversity_reports_jaccard_floor_and_monoculture_warning(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "critic-reports"
    input_dir.mkdir()
    _write_case(
        input_dir / "collapsed.json",
        _case_payload(
            case_id="collapsed-case",
            failure_modes_by_role=dict.fromkeys(
                CRITIC_ROLES,
                ("shared_failure_mode",),
            ),
        ),
    )

    report = diversity.build_critic_ensemble_diversity_report(
        repo_root=REPO_ROOT,
        input_path=input_dir,
        diversity_floor=0.25,
    )
    validation = diversity.validate_critic_ensemble_diversity_report(report)

    assert validation["status"] == "pass", validation["issues"]
    assert report["schema_version"] == diversity.SCHEMA_VERSION
    case = report["cases"][0]
    assert case["case_id"] == "collapsed-case"
    assert case["critic_count"] == 8
    assert case["pairwise_jaccard_similarity"] == 1.0
    assert case["critic_ensemble_diversity_jaccard"] == 0.0
    assert case["unique_failure_mode_count"] == 1
    assert "critic_monoculture" in {warning["code"] for warning in case["warnings"]}
    assert "critic_diversity_below_floor" in {
        warning["code"] for warning in report["warnings"]
    }


def test_critic_ensemble_diversity_passes_when_critics_flag_distinct_failure_modes(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "critic-reports"
    input_dir.mkdir()
    _write_case(
        input_dir / "diverse.json",
        _case_payload(
            case_id="diverse-case",
            failure_modes_by_role={
                role: (f"{role}_specific_failure",) for role in CRITIC_ROLES
            },
        ),
    )

    report = diversity.build_critic_ensemble_diversity_report(
        repo_root=REPO_ROOT,
        input_path=input_dir,
        diversity_floor=0.25,
    )

    case = report["cases"][0]
    assert case["pairwise_jaccard_similarity"] == 0.0
    assert case["critic_ensemble_diversity_jaccard"] == 1.0
    assert case["unique_failure_mode_count"] == 8
    assert case["warnings"] == []
    assert report["summary"]["cases_below_diversity_floor"] == 0


def test_critic_ensemble_diversity_self_test_cli_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "critic-diversity.json"

    exit_code = diversity.main(["--self-test", "--output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["case_count"] >= 2
    assert payload["summary"]["cases_with_monoculture_warning"] >= 1


def _write_case(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _case_payload(
    *,
    case_id: str,
    failure_modes_by_role: dict[str, tuple[str, ...]],
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "domain": "housing",
        "authority_level": "governed",
        "critic_ensemble": {
            "run_id": f"run-{case_id}",
            "verdicts": [
                {
                    "verdict": "contest",
                    "envelope": {
                        "critic_role": role,
                        "substantive_basis": f"{role}_basis",
                        "critic_version": "test",
                    },
                    "target_candidate_ids": [f"candidate-{case_id}"],
                    "message": f"{role} critique",
                    "failure_modes": list(failure_modes),
                }
                for role, failure_modes in failure_modes_by_role.items()
            ],
        },
    }
