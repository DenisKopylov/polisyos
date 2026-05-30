from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import check_critic_ensemble_diversity as w11f_critic
from tools.quality.validation import check_domain_coverage_breadth as w11f_domain
from tools.quality.validation import run_domain_coverage_critic_diversity_audit as w12c

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    REPO_ROOT
    / "architecture/policy_design_case/"
    "wave12c_domain_coverage_critic_diversity_audit_manifest.json"
)


def test_w12c_manifest_is_deterministic_and_runs_w11f_tools() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest == w12c.build_w12c_manifest()
    assert manifest["schema_version"] == w12c.MANIFEST_SCHEMA_VERSION
    assert manifest["phase_id"] == "W12.C"
    assert manifest["w11f_tool_refs"] == [
        "repo://tools/quality/validation/check_domain_coverage_breadth.py",
        "repo://tools/quality/validation/check_critic_ensemble_diversity.py",
    ]
    assert manifest["floor_policy"]["governed-pilot"]["minimum_domain_breadth"] == 4
    assert manifest["floor_policy"]["production-capable"]["minimum_domain_breadth"] == 6
    assert "--corpus tests/fixtures/universal-corpus" in manifest["command_contract"]["command"]
    assert manifest["metric_policy"]["typed_blockers_count_as_useful_design"] is False
    assert manifest["metric_policy"]["critic_monoculture_caps_rollout"] == (
        "governed-pilot-or-below"
    )


def test_w12c_w11f_loaders_ignore_corpus_stub_files() -> None:
    domain_report = w11f_domain.build_domain_coverage_breadth_report(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
    )
    critic_report = w11f_critic.build_critic_ensemble_diversity_report(
        repo_root=REPO_ROOT,
        input_path=REPO_ROOT / "tests/fixtures/universal-corpus",
    )

    assert domain_report["summary"]["case_count"] == 13
    assert critic_report["summary"]["case_count"] == 13
    assert not any(
        str(case.get("source_path")).endswith(".producer_stubs.json")
        for case in domain_report["cases"]
    )
    assert not any(
        str(case.get("source_path")).endswith(".producer_stubs.json")
        for case in critic_report["cases"]
    )
    assert "unknown" not in {case["domain"] for case in domain_report["cases"]}


def test_w12c_can_measure_critic_diversity_from_w12d_runtime_report_refs(
    tmp_path: Path,
) -> None:
    domain_report = tmp_path / "domain.json"
    w12d_report = tmp_path / "w12d.json"
    critic_dir = tmp_path / "critic-reports"
    critic_dir.mkdir()
    critic_case = critic_dir / "case-a.critic-ensemble-report.json"
    critic_case.write_text(json.dumps(_critic_verdict_payload("case-a")), encoding="utf-8")
    domain_report.write_text(
        json.dumps(
            _domain_report(
                [
                    _domain_case(
                        case_id="case-a",
                        domain="housing",
                        useful_by_authority={"research": True, "governed": True},
                    )
                ]
            )
        ),
        encoding="utf-8",
    )
    w12d_report.write_text(
        json.dumps(
            {
                "schema_version": (
                    "policyos.policy_design_case.w12d.universal_outcome_corpus_run.v1"
                ),
                "cases": [
                    {
                        "case_id": "case-a",
                        "domain": "housing",
                        "authority_level": "governed",
                        "llm_universal_compilation": {
                            "critic_ensemble_report_ref": (
                                "repo://critic-reports/case-a.critic-ensemble-report.json"
                            )
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = w12c.run_w12c_domain_coverage_critic_diversity_audit(
        repo_root=tmp_path,
        corpus_path=tmp_path,
        domain_coverage_report=domain_report,
        w12d_report_path=w12d_report,
        raw_critic_report_output=tmp_path / "critic-diversity.json",
        rollout_posture="research-only",
    )

    assert report["status"] == "pass"
    assert report["critic_diversity_jaccard_summary"]["cases"][0]["case_id"] == "case-a"
    assert not any(
        issue["code"] == "critic_verdicts_missing" for issue in report["issues"]
    )
    assert not any(
        warning["code"] == "critic_roles_missing" for warning in report["warnings"]
    )


def test_zero_useful_domain_authority_slice_becomes_typed_blocker() -> None:
    domain_report = _domain_report(
        [
            _domain_case(
                case_id="housing-useful",
                domain="housing",
                useful_by_authority={
                    "research": True,
                    "governed": True,
                    "production": True,
                },
            ),
            _domain_case(
                case_id="tax-blocked",
                domain="tax",
                useful_by_authority={
                    "research": False,
                    "governed": False,
                    "production": False,
                },
            ),
        ]
    )

    report = w12c.build_w12c_domain_coverage_critic_diversity_audit(
        domain_coverage_report=domain_report,
        critic_diversity_report=_critic_report({"housing-useful": 1.0, "tax-blocked": 1.0}),
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
        raw_domain_report_ref="repo://_build/domain.json",
        raw_critic_report_ref="repo://_build/critic.json",
        rollout_posture="production-capable",
    )

    assert report["status"] == "blocked"
    assert report["domain_authority_useful_design_matrix"]["housing"]["production"][
        "useful_design_count"
    ] == 1
    tax_production = report["domain_authority_useful_design_matrix"]["tax"]["production"]
    assert tax_production["case_count"] == 1
    assert tax_production["useful_design_count"] == 0
    assert tax_production["non_useful_case_ids"] == ["tax-blocked"]
    assert "tax:production" in report["floor_evaluation"][
        "below_floor_domain_authority_slices"
    ]

    blocker = next(
        blocker
        for blocker in report["typed_domain_coverage_blockers"]
        if blocker["code"] == "domain_coverage_zero_useful_design"
        and blocker["domain"] == "tax"
        and blocker["authority_level"] == "production"
    )
    assert blocker["owner"] == "team-evaluation"
    assert blocker["counts_as_useful_design"] is False
    assert blocker["counts_as_closeout_honesty_failure"] is False
    assert blocker["blocks_rollout_posture"] is True


def test_negative_control_only_domain_slice_is_held_not_blocking_governed_pilot() -> None:
    positive_cases = [
        _domain_case(
            case_id=f"useful-{index}",
            domain=f"domain-{index}",
            useful_by_authority={"research": True, "governed": True},
        )
        for index in range(4)
    ]
    negative_control = _domain_case(
        case_id="berlin-rent-cap-false-pass",
        domain="housing",
        useful_by_authority={"research": False, "governed": False},
        adjudication_labels=["false_pass"],
        closeout_state="blocked",
        blocker_code="expert_negative_control",
    )
    report = w12c.build_w12c_domain_coverage_critic_diversity_audit(
        domain_coverage_report=_domain_report([*positive_cases, negative_control]),
        critic_diversity_report=_critic_report(
            {case["case_id"]: 1.0 for case in [*positive_cases, negative_control]}  # type: ignore[misc]
        ),
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
        raw_domain_report_ref="repo://_build/domain.json",
        raw_critic_report_ref="repo://_build/critic.json",
        rollout_posture="governed-pilot",
    )

    assert report["status"] == "pass"
    assert "housing:research" not in report["floor_evaluation"][
        "below_floor_domain_authority_slices"
    ]
    assert "housing:governed" not in report["floor_evaluation"][
        "below_floor_domain_authority_slices"
    ]
    held_refs = {
        f"{row['domain']}:{row['authority_level']}"
        for row in report["held_domain_slices"]
    }
    assert {"housing:research", "housing:governed"} <= held_refs
    assert not any(
        blocker["code"] == "domain_coverage_zero_useful_design"
        and blocker["domain"] == "housing"
        for blocker in report["typed_domain_coverage_blockers"]
    )


def test_low_critic_diversity_emits_monoculture_warning_and_caps_rollout() -> None:
    domain_report = _domain_report(
        [
            _domain_case(
                case_id=f"case-{index}",
                domain=f"domain-{index}",
                useful_by_authority={
                    "research": True,
                    "governed": True,
                    "production": True,
                },
            )
            for index in range(6)
        ]
    )

    report = w12c.build_w12c_domain_coverage_critic_diversity_audit(
        domain_coverage_report=domain_report,
        critic_diversity_report=_critic_report(
            {f"case-{index}": 0.0 for index in range(6)}
        ),
        repo_root=REPO_ROOT,
        corpus_ref="repo://tests/fixtures/universal-corpus",
        raw_domain_report_ref="repo://_build/domain.json",
        raw_critic_report_ref="repo://_build/critic.json",
        rollout_posture="production-capable",
    )

    assert report["status"] == "warning"
    assert report["critic_diversity_jaccard_summary"][
        "aggregate_critic_ensemble_diversity_jaccard"
    ] == 0.0
    assert report["rollout_cap"]["maximum_posture"] == "governed-pilot"
    assert report["rollout_cap"]["requested_posture_allowed"] is False
    warning = next(
        warning for warning in report["warnings"] if warning["code"] == "critic_monoculture"
    )
    assert warning["rollout_cap"] == "governed-pilot-or-below"
    assert warning["counts_as_useful_design"] is False


def test_w12c_cli_can_decorate_existing_w11f_reports(tmp_path: Path) -> None:
    domain_report = tmp_path / "domain.json"
    critic_report = tmp_path / "critic.json"
    output_report = tmp_path / "w12c.json"
    domain_report.write_text(
        json.dumps(
            _domain_report(
                [
                    _domain_case(
                        case_id="research-case",
                        domain="housing",
                        useful_by_authority={"research": True},
                    )
                ]
            )
        ),
        encoding="utf-8",
    )
    critic_report.write_text(json.dumps(_critic_report({"research-case": 1.0})), encoding="utf-8")

    exit_code = w12c.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--domain-coverage-report",
            str(domain_report),
            "--critic-diversity-report",
            str(critic_report),
            "--rollout-posture",
            "research-only",
            "--output",
            str(output_report),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_report.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["domain_authority_useful_design_matrix"]["housing"]["research"][
        "useful_design_count"
    ] == 1
    assert payload["typed_domain_coverage_blockers"] == []


def _domain_report(cases: list[dict[str, object]]) -> dict[str, object]:
    domains = sorted({str(case["domain"]) for case in cases})
    per_authority = {
        authority: _authority_rate(
            [
                row
                for case in cases
                for row in case["authority_useful_design"]  # type: ignore[index]
                if row["authority_level"] == authority
            ]
        )
        for authority in ("governed", "production", "research")
    }
    return {
        "schema_version": "policyos.policy_design_case.domain_coverage_breadth.v1",
        "tool": "quality.validation.check-domain-coverage-breadth",
        "generated_at": "2026-05-24T00:00:00Z",
        "repo_root": str(REPO_ROOT),
        "corpus_path": str(REPO_ROOT / "tests/fixtures/universal-corpus"),
        "thresholds": {
            "min_candidates_per_family_layer": 1,
            "min_family_layers": 2,
        },
        "summary": {
            "status": "pass",
            "case_count": len(cases),
            "committed_domain_count": len(domains),
            "domain_coverage_breadth": len(domains),
            "non_trivial_domain_ids": domains,
            "min_candidates_per_family_layer": 1,
            "min_family_layers": 2,
            "per_authority_expert_useful_design_ceiling": per_authority,
        },
        "domains": {
            domain: {
                "case_count": sum(1 for case in cases if case["domain"] == domain),
                "non_trivial_graph": True,
                "non_trivial_case_ids": [
                    str(case["case_id"]) for case in cases if case["domain"] == domain
                ],
                "graph_blocked_case_count": 0,
                "max_family_layer_count": 2,
            }
            for domain in domains
        },
        "cases": cases,
        "issues": [],
    }


def _domain_case(
    *,
    case_id: str,
    domain: str,
    useful_by_authority: dict[str, bool],
    adjudication_labels: list[str] | None = None,
    closeout_state: str | None = None,
    blocker_code: str | None = None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "source_path": f"fixture://{case_id}",
        "domain": domain,
        "graph_status": "pass",
        "obligation_graph_ref": f"obligation-graph-{case_id}",
        "family_layer_counts": {"data": 1, "legal": 1},
        "qualifying_family_layers": ["data", "legal"],
        "family_layer_count": 2,
        "frontier_candidate_count": 2,
        "non_trivial_graph": True,
        "authority_useful_design": [
            {
                "case_id": case_id,
                "authority_level": authority,
                "closeout_state": closeout_state or ("limited" if useful else "blocked"),
                "structurally_useful": useful,
                "adjudication_labels": (
                    adjudication_labels
                    if adjudication_labels is not None
                    else ["semantic_pass"] if useful else ["unsupported"]
                ),
                "counts_toward_useful_design": useful,
                "blocker_code": (
                    None if useful else blocker_code or "closeout_state_not_useful_design"
                ),
            }
            for authority, useful in sorted(useful_by_authority.items())
        ],
        "issues": [],
    }


def _authority_rate(rows: list[dict[str, object]]) -> dict[str, object]:
    useful_count = sum(1 for row in rows if row["counts_toward_useful_design"])
    return {
        "case_count": len(rows),
        # ``expert_useful_design_ceiling*`` are the W11.F-renamed fields that
        # the rest of the pipeline consumes; we preserve the legacy aliases so
        # downstream readers that have not migrated still find values.
        "expert_useful_design_ceiling_count": useful_count,
        "expert_useful_design_ceiling": round(useful_count / len(rows), 4)
        if rows
        else 0.0,
        "useful_design_count": useful_count,
        "blocked_or_non_useful_count": len(rows) - useful_count,
        "useful_design_rate": round(useful_count / len(rows), 4) if rows else 0.0,
        "typed_blockers_count_as_useful_design": False,
        "accepted_deficits_count_as_useful_design": False,
    }


def _critic_report(case_diversities: dict[str, float]) -> dict[str, object]:
    cases = [
        {
            "case_id": case_id,
            "source_path": f"fixture://{case_id}",
            "domain": "test",
            "authority_level": "governed",
            "critic_count": 8,
            "required_critic_roles": list(w12c.REQUIRED_CRITIC_ROLES),
            "missing_critic_roles": [],
            "failure_modes_by_critic": {},
            "unique_failure_modes": [],
            "unique_failure_mode_count": 8 if diversity else 1,
            "pairwise_jaccard_similarity": round(1.0 - diversity, 4),
            "critic_ensemble_diversity_jaccard": diversity,
            "below_diversity_floor": diversity < 0.25,
            "warnings": (
                [
                    {
                        "code": "critic_monoculture",
                        "message": "All eight critics flagged the same failure-mode set.",
                        "severity": "warn",
                        "case_id": case_id,
                    },
                    {
                        "code": "critic_diversity_below_floor",
                        "message": "Critic ensemble diversity Jaccard is below the W11.F floor.",
                        "severity": "warn",
                        "case_id": case_id,
                        "diversity_jaccard": diversity,
                        "diversity_floor": 0.25,
                    },
                ]
                if diversity < 0.25
                else []
            ),
            "issues": [],
        }
        for case_id, diversity in sorted(case_diversities.items())
    ]
    return {
        "schema_version": "policyos.policy_design_case.critic_ensemble_diversity.v1",
        "tool": "quality.validation.check-critic-ensemble-diversity",
        "generated_at": "2026-05-24T00:00:00Z",
        "repo_root": str(REPO_ROOT),
        "input_path": str(REPO_ROOT / "tests/fixtures/universal-corpus"),
        "thresholds": {"diversity_floor": 0.25},
        "summary": {
            "status": "pass",
            "case_count": len(cases),
            "diversity_floor": 0.25,
            "aggregate_critic_ensemble_diversity_jaccard": round(
                sum(case_diversities.values()) / len(case_diversities),
                4,
            ),
            "cases_below_diversity_floor": sum(
                1 for diversity in case_diversities.values() if diversity < 0.25
            ),
            "cases_with_monoculture_warning": sum(
                1 for diversity in case_diversities.values() if diversity < 0.25
            ),
            "required_critic_roles": list(w12c.REQUIRED_CRITIC_ROLES),
        },
        "cases": cases,
        "warnings": [
            warning for case in cases for warning in case["warnings"]  # type: ignore[index]
        ],
        "issues": [],
    }


def _critic_verdict_payload(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "domain": "housing",
        "authority_level": "governed",
        "verdicts": [
            {
                "verdict": "contest",
                "envelope": {
                    "critic_role": role,
                    "critic_version": "test",
                    "substantive_basis": f"{role}_basis",
                },
                "target_candidate_ids": [f"candidate-{case_id}"],
                "message": f"{role} critique",
                "failure_modes": [f"{role}_failure"],
            }
            for role in w12c.REQUIRED_CRITIC_ROLES
        ],
    }
