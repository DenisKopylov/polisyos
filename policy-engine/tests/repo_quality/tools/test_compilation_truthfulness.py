from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from polisyos.runtime.quality.capability_ratchet import PURPOSE_MULTIPLIERS
from tools.quality.validation import check_compilation_truthfulness as truthfulness

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_compilation_truthfulness_separates_obligation_error_classes(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    _write_case(corpus_dir / "mixed-case.json", _mixed_case_payload())

    report = truthfulness.build_compilation_truthfulness_report(
        repo_root=REPO_ROOT,
        corpus_path=corpus_dir,
    )
    validation = truthfulness.validate_compilation_truthfulness_report(report)

    assert validation["status"] == "pass", validation["issues"]
    assert report["schema_version"] == truthfulness.SCHEMA_VERSION
    assert report["summary"]["case_count"] == 1
    assert report["summary"]["status"] == "pass"
    case = report["cases"][0]
    assert case["case_id"] == "w11e-mixed-obligation-case"
    assert case["producer_pipeline_status"] == "pass"
    assert case["obligation_graph_ref"].startswith("obligation-graph-")
    assert case["claim_decomposition_ref"].startswith("claim-ledger:")
    assert [item["annotation_id"] for item in case["true_positive_obligations"]] == [
        "ann-data-freshness"
    ]
    assert [item["annotation_id"] for item in case["missed_obligations"]] == [
        "ann-fiscal-envelope"
    ]
    assert [item["family"] for item in case["hallucinated_obligations"]] == ["participation"]
    assert [item["annotation_id"] for item in case["scope_drift_obligations"]] == [
        "ann-legal-competence"
    ]
    assert case["scope_drift_obligations"][0]["expected_scope"] == "lviv:housing"
    assert case["scope_drift_obligations"][0]["compiled_scope"] == "kyiv:housing"
    assert [item["annotation_id"] for item in case["authority_drift_obligations"]] == [
        "ann-method-validity"
    ]
    assert case["authority_drift_obligations"][0]["expected_authority_level"] == "governed"
    assert case["authority_drift_obligations"][0]["compiled_authority_level"] == "production"

    positive = PURPOSE_MULTIPLIERS["evidence_producer"]
    penalty = (
        PURPOSE_MULTIPLIERS["authority_gate"]
        + PURPOSE_MULTIPLIERS["authority_gate"]
        + PURPOSE_MULTIPLIERS["closeout_input"]
        + PURPOSE_MULTIPLIERS["authority_gate"]
    )
    assert case["score_weights"]["true_positive_obligations"] == positive
    assert case["score_weights"]["missed_obligations"] == PURPOSE_MULTIPLIERS["authority_gate"]
    assert case["score_weights"]["scope_drift_obligations"] == (
        PURPOSE_MULTIPLIERS["closeout_input"]
    )
    assert case["per_case_truthfulness_score"] == round(100.0 * positive / (positive + penalty), 2)
    assert report["summary"]["aggregate_compilation_truthfulness_rate"] == (
        case["per_case_truthfulness_score"]
    )
    assert report["summary"]["construct_vocabulary"]["reported"] is True
    assert case["construct_vocabulary"]["compiled_constructs"] == [
        "construct:housing_rent_burden"
    ]
    assert case["construct_vocabulary"]["true_positive_constructs"] == [
        "construct:housing_rent_burden"
    ]
    assert case["construct_vocabulary"]["authority_drift_constructs"] == [
        "construct:housing_rent_burden"
    ]
    assert report["summary"]["construct_vocabulary"]["authority_drift_construct_count"] == 1
    assert report["summary"]["by_domain"]["housing"]["case_count"] == 1
    assert report["summary"]["by_authority_level"]["production"]["case_count"] == 1


def test_w11b_vertical_seed_rules_are_scored_without_horizontal_catalog_noise() -> None:
    case_files = (
        REPO_ROOT
        / "tests/fixtures/universal-corpus/cases/w11a_ghana_free_shs_2017.json",
        REPO_ROOT
        / "tests/fixtures/universal-corpus/cases/w11a_netherlands_room_for_river_2007.json",
    )

    for case_file in case_files:
        report = truthfulness.build_compilation_truthfulness_report(
            repo_root=REPO_ROOT,
            corpus_path=case_file,
        )

        case = report["cases"][0]
        assert case["missed_obligations"] == []
        assert case["hallucinated_obligations"] == []
        assert case["true_positive_obligations"]
        assert case["per_case_truthfulness_score"] == 100.0


def test_universal_corpus_construct_truthfulness_uses_registry_expectations() -> None:
    report = truthfulness.build_compilation_truthfulness_report(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
    )

    construct_summary = report["summary"]["construct_vocabulary"]
    assert construct_summary["reported"] is True
    assert construct_summary["true_positive_construct_count"] >= 1
    assert {
        "missed_construct_count",
        "hallucinated_construct_count",
        "authority_drift_construct_count",
    } <= set(construct_summary)
    labeled_cases = [
        case
        for case in report["cases"]
        if case["construct_vocabulary"]["construct_expectation_status"] == "labeled"
    ]
    assert labeled_cases
    assert any(
        case["construct_vocabulary"]["true_positive_constructs"]
        for case in labeled_cases
    )
    for case in report["cases"]:
        vocabulary = case["construct_vocabulary"]
        if vocabulary["construct_expectation_status"] == "unlabeled":
            assert vocabulary["hallucinated_constructs"] == []


def test_truthfulness_case_loader_ignores_producer_stub_fixtures() -> None:
    cases, issues = truthfulness._load_cases(
        REPO_ROOT / "tests/fixtures/universal-corpus"
    )

    assert issues == []
    assert len(cases) == 13
    assert not any("producer_stubs" in case["_source_path"] for case in cases)


def test_case_without_expert_adjudication_is_blocked_from_truthfulness_metric(
    tmp_path: Path,
) -> None:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    payload = _mixed_case_payload()
    payload.pop("expert_adjudication")
    _write_case(corpus_dir / "missing-adjudication.json", payload)

    report = truthfulness.build_compilation_truthfulness_report(
        repo_root=REPO_ROOT,
        corpus_path=corpus_dir,
    )

    assert report["summary"]["status"] == "fail"
    case = report["cases"][0]
    assert case["status"] == "blocked"
    assert case["per_case_truthfulness_score"] == 0.0
    assert "w11c_adjudication_missing" in {issue["code"] for issue in case["issues"]}


def test_report_validation_rejects_missing_w11e_error_buckets(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    _write_case(corpus_dir / "mixed-case.json", _mixed_case_payload())
    report = truthfulness.build_compilation_truthfulness_report(
        repo_root=REPO_ROOT,
        corpus_path=corpus_dir,
    )
    report["cases"][0].pop("authority_drift_obligations")

    validation = truthfulness.validate_compilation_truthfulness_report(report)

    assert validation["status"] == "fail"
    assert "compilation_truthfulness_bucket_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_self_test_cli_runs_and_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "self-test-report.json"

    exit_code = truthfulness.main(["--self-test", "--output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "pass"
    assert payload["cases"][0]["per_case_truthfulness_score"] > 0.0


def _write_case(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _mixed_case_payload() -> dict[str, object]:
    return {
        "case_id": "w11e-mixed-obligation-case",
        "domain": "housing",
        "authority_level": "production",
        "intent": {
            "intent_id": "w11e-mixed",
            "text": (
                "Provide a means-tested housing voucher subsidy for low-income renters "
                "in Kyiv oblast through municipal service centres, with annual "
                "appropriations and public monitoring in 2026."
            ),
            "problem_domain": "social",
            "authority_type": "local",
        },
        "concept_spine_refs": {
            "concept_spine_ref": "concept-spine://w11e/mixed",
            "jurisdiction_spine_ref": "jurisdiction-spine://w11e/mixed",
            "canonical_concept_refs": ["concept://w11e/housing"],
        },
        "compilation_inputs": {
            "use_seed_rule_catalog": False,
            "complexity_budget": {"max_frontier_items": 10},
            "candidate_sources": [
                _candidate(
                    "candidate-data-freshness",
                    "data",
                    "source_freshness",
                    construct_refs=["construct:housing_rent_burden"],
                ),
                _candidate("candidate-legal-competence", "legal", "legal_competence"),
                _candidate(
                    "candidate-method-validity",
                    "method",
                    "method_validity",
                    construct_refs=["construct:housing_rent_burden"],
                ),
                _candidate(
                    "candidate-participation-record",
                    "participation",
                    "participation_record",
                ),
            ],
        },
        "producer_pipeline": {
            "producers": [
                {
                    "producer_component": "fabric",
                    "consumed_concept_refs": ["concept://w11e/housing"],
                    "consumed_requirement_refs": ["req://w11e/data"],
                    "expected_output_families": ["fabric.source_contract_binding.v1"],
                    "first_pass_bindings": [
                        {
                            "binding_id": "label.fabric.context",
                            "binding_kind": "label",
                            "disposition": "context_only",
                            "concept_ref": "concept://w11e/housing",
                            "label": "fabric context label",
                        }
                    ],
                    "second_pass_bindings": [
                        {
                            "binding_id": "binding.fabric.source",
                            "binding_kind": "dataset",
                            "disposition": "selected",
                            "concept_ref": "concept://w11e/housing",
                            "requirement_ref": "req://w11e/data",
                            "artifact_ref": "source://w11e/housing-admin",
                            "time_role": "observation_time",
                        }
                    ],
                    "requested_deadline_s": 5.0,
                }
            ],
        },
        "annotations": {
            "obligations": [
                {
                    "obligation_id": "ann-data-freshness",
                    "family": "data",
                    "construct_refs": ["construct:housing_rent_burden"],
                    "remedy_path": "source_freshness",
                    "scope": "kyiv:housing",
                    "authority_level": "production",
                    "description": "Data freshness must cover the housing voucher claim time.",
                },
                {
                    "obligation_id": "ann-legal-competence",
                    "family": "legal",
                    "remedy_path": "legal_competence",
                    "scope": "lviv:housing",
                    "authority_level": "production",
                    "description": "Legal competence must be proven for the local authority.",
                },
                {
                    "obligation_id": "ann-method-validity",
                    "family": "method",
                    "remedy_path": "method_validity",
                    "construct_refs": ["construct:housing_rent_burden"],
                    "scope": "kyiv:housing",
                    "authority_level": "governed",
                    "description": "Method validity must match the claim family.",
                },
                {
                    "obligation_id": "ann-fiscal-envelope",
                    "family": "fiscal",
                    "remedy_path": "budget_envelope",
                    "scope": "kyiv:housing",
                    "authority_level": "production",
                    "description": "Budget envelope must be bound before publication.",
                },
            ]
        },
        "expert_adjudication": {
            "case_label": "semantic_pass",
            "reviewer_role": "policy_domain_expert",
            "rubric_revision": "w11.c-test",
        },
    }


def _candidate(
    candidate_id: str,
    family: str,
    remedy_path: str,
    *,
    construct_refs: list[str] | None = None,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "family": family,
        "obligation_text": f"Resolve {family} obligation through {remedy_path}.",
        "source_class": "producer_blocker",
        "source_ref": f"fixture://{candidate_id}",
        "owner": "team-evaluation",
        "scope": "kyiv:housing",
        "authority_profile": "production",
        "temporal_window": "2026",
        "remedy_path": remedy_path,
        "priority_hint": "mandatory",
        "authority_allowance_passed": True,
        "admissibility_passed": True,
        "current_run_relevance_passed": True,
        "material_public_risk_passed": True,
        "marginal_assurance_value": 10.0,
        "expected_cost": 0.0,
        "degradation_risk": 0.0,
        "reviewer_burden_minutes": 0.0,
        "complexity_cost": 1.0,
        "lineage_refs": [f"fixture://lineage/{candidate_id}"],
        "escalation_owner": "team-evaluation",
        "metadata": {"required_evidence_constructs": construct_refs or []},
    }
