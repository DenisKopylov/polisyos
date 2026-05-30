from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import check_domain_coverage_breadth as breadth

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_domain_coverage_breadth_counts_nontrivial_w6c_graphs_by_domain(
    tmp_path: Path,
) -> None:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    _write_case(
        corpus_dir / "health.json",
        _case_payload(
            case_id="health-outreach",
            domain="public_health_intervention",
            candidate_families=("data", "legal", "method"),
            production_state="limited",
        ),
    )
    _write_case(
        corpus_dir / "housing.json",
        _case_payload(
            case_id="housing-voucher",
            domain="housing_subsidy",
            candidate_families=("data",),
            production_state="blocked",
        ),
    )

    report = breadth.build_domain_coverage_breadth_report(
        repo_root=REPO_ROOT,
        corpus_path=corpus_dir,
        min_candidates_per_family_layer=1,
        min_family_layers=2,
    )
    validation = breadth.validate_domain_coverage_breadth_report(report)

    assert validation["status"] == "pass", validation["issues"]
    assert report["schema_version"] == breadth.SCHEMA_VERSION
    assert report["summary"]["committed_domain_count"] == 2
    assert report["summary"]["domain_coverage_breadth"] == 1
    assert report["summary"]["non_trivial_domain_ids"] == ["public_health_intervention"]
    assert report["domains"]["public_health_intervention"]["non_trivial_graph"] is True
    assert report["domains"]["housing_subsidy"]["non_trivial_graph"] is False
    assert report["cases"][0]["graph_status"] == "pass"
    assert report["cases"][0]["family_layer_count"] == 3
    assert report["cases"][1]["family_layer_count"] == 1

    authority_rates = report["summary"]["per_authority_expert_useful_design_ceiling"]
    assert authority_rates["research"]["expert_useful_design_ceiling"] == 1.0
    assert authority_rates["governed"]["expert_useful_design_ceiling"] == 0.5
    assert authority_rates["production"]["expert_useful_design_ceiling"] == 0.5
    assert authority_rates["production"]["expert_useful_design_ceiling_count"] == 1
    assert authority_rates["production"]["case_count"] == 2
    assert authority_rates["production"]["blocked_or_non_useful_count"] == 1


def test_domain_coverage_breadth_does_not_launder_expected_fixture_slice_as_w6c_graph(
    tmp_path: Path,
) -> None:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    payload = _case_payload(
        case_id="expected-only",
        domain="education_access",
        candidate_families=("data", "legal", "method"),
        production_state="limited",
    )
    payload.pop("concept_spine_refs")
    payload.pop("compilation_inputs")
    payload["expected_obligation_graph"] = {
        "frontier": [
            {"obligation_id": "expected-data", "family": "data"},
            {"obligation_id": "expected-legal", "family": "legal"},
            {"obligation_id": "expected-method", "family": "method"},
        ]
    }
    _write_case(corpus_dir / "expected-only.json", payload)

    report = breadth.build_domain_coverage_breadth_report(
        repo_root=REPO_ROOT,
        corpus_path=corpus_dir,
        min_candidates_per_family_layer=1,
        min_family_layers=2,
    )

    assert report["summary"]["domain_coverage_breadth"] == 0
    assert report["domains"]["education_access"]["non_trivial_graph"] is False
    assert report["cases"][0]["graph_status"] == "blocked"
    assert "w6c_obligation_graph_unavailable" in {
        issue["code"] for issue in report["cases"][0]["issues"]
    }


def test_domain_coverage_breadth_self_test_cli_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "domain-coverage.json"

    exit_code = breadth.main(["--self-test", "--output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["domain_coverage_breadth"] >= 1
    assert payload["summary"]["per_authority_expert_useful_design_ceiling"]["production"][
        "case_count"
    ] >= 1


def _write_case(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _case_payload(
    *,
    case_id: str,
    domain: str,
    candidate_families: tuple[str, ...],
    production_state: str,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "domain": domain,
        "authority_level": "production",
        "intent": {
            "intent_id": f"intent-{case_id}",
            "text": (
                "Provide a means-tested housing voucher subsidy for low-income renters "
                "in Kyiv oblast through municipal service centres, with annual "
                "appropriations and public monitoring in 2026."
            ),
            "problem_domain": "social",
            "authority_type": "local",
        },
        "concept_spine_refs": {
            "concept_spine_ref": f"concept-spine://w11f/{case_id}",
            "jurisdiction_spine_ref": f"jurisdiction-spine://w11f/{case_id}",
            "canonical_concept_refs": [f"concept://w11f/{case_id}"],
        },
        "compilation_inputs": {
            "use_seed_rule_catalog": False,
            "complexity_budget": {"max_frontier_items": 10},
            "candidate_sources": [
                _candidate(case_id=case_id, family=family)
                for family in candidate_families
            ],
        },
        "expected_closeout_states": {
            "states": [
                {
                    "authority_level": "research",
                    "state": "publishable",
                    "required_surface_refs": [f"audit://{case_id}/research"],
                },
                {
                    "authority_level": "governed",
                    "state": "limited" if production_state != "blocked" else "blocked",
                    "required_surface_refs": [f"audit://{case_id}/governed"],
                },
                {
                    "authority_level": "production",
                    "state": production_state,
                    "required_surface_refs": [f"audit://{case_id}/production"],
                },
            ]
        },
        "expert_adjudication": {
            "case_label": "semantic_pass",
            "claim_labels": [
                {
                    "claim_id": "claim:test",
                    "dimension_id": "compilation_truthfulness",
                    "label": "semantic_pass",
                    "status_should_have_been": "publishable",
                }
            ],
            "reviewer_topology_ref": f"reviewer-topology://{case_id}",
        },
    }


def _candidate(*, case_id: str, family: str) -> dict[str, object]:
    return {
        "candidate_id": f"candidate-{case_id}-{family}",
        "family": family,
        "obligation_text": f"Resolve {family} obligation for {case_id}.",
        "source_class": "producer_blocker",
        "source_ref": f"fixture://{case_id}/{family}",
        "owner": "team-evaluation",
        "scope": f"{case_id}:scope",
        "authority_profile": "production",
        "temporal_window": "2026",
        "remedy_path": f"{family}_review",
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
        "lineage_refs": [f"fixture://lineage/{case_id}/{family}"],
        "escalation_owner": "team-evaluation",
    }
