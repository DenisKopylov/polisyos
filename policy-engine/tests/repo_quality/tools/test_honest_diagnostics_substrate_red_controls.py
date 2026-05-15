from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests._helpers.hds_quality import (
    HDS_XFAIL_REASON,
    blocking_codes,
    complete_job_payload,
    complete_quality_evidence,
    scorecard_for,
)
from tools.ci import check_policyos_production_quality_best_in_class as gate

REPO_ROOT = Path(__file__).resolve().parents[3]
HDS_RED_XFAIL = pytest.mark.xfail(strict=True, reason=HDS_XFAIL_REASON)
HDS_RED_TEST_FILES = (
    REPO_ROOT / "tests/unit/runtime/quality/test_authority_envelope_contract.py",
    REPO_ROOT / "tests/unit/runtime/quality/test_diagnostic_event_contract.py",
    REPO_ROOT / "tests/unit/tools/test_canary_evidence_authority.py",
    REPO_ROOT / "tests/repo_quality/tools/test_honest_diagnostics_substrate_red_controls.py",
)


def test_hds_red_controls_use_strict_narrow_xfail_markers() -> None:
    required_cases = {
        "bundle_local_quality_evidence_paths",
        "report_embedded_ref_must_match_runtime_cas_ref",
        "fixture_only_authority_envelope",
        "warn_scorecards_fail_serious",
        "missing_serious_diagnostic_event",
        "sampled_away_serious_diagnostic_event",
        "canary_bundle_generated_quality_evidence_paths",
        "quality_status_pass_in_input_progress_bundle_or_dashboard",
        "silent_fallback_requires_degradation_ledger",
        "no_norms_retrieved_requires_lex_no_norm_authority_blocker",
        "data_exists_requires_semantic_binding_ledger",
    }
    combined = "\n".join(path.read_text(encoding="utf-8") for path in HDS_RED_TEST_FILES)

    assert re.search(r"^pytestmark\s*=", combined, flags=re.MULTILINE) is None
    assert re.search(r"@pytest\.mark\.skip", combined) is None
    assert re.search(r"pytest\.mark\.xfail\([^)]*strict=False", combined) is None
    assert (
        len(
            re.findall(
                r"^HDS_RED_XFAIL = pytest\.mark\.xfail\(strict=True, reason=HDS_XFAIL_REASON\)",
                combined,
                flags=re.MULTILINE,
            )
        )
        == 4
    )
    for case in required_cases:
        assert case in combined


@HDS_RED_XFAIL
def test_no_norms_retrieved_requires_lex_no_norm_authority_blocker() -> None:
    evidence = complete_quality_evidence()
    evidence["normative_evidence"] = {
        "schema_version": "policyos.lex.normative_applicability_report.v1",
        "status": "pass",
        "target_context": {
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-12",
        },
        "retrieval_status": "no_norms_retrieved",
        "applied_norms": [],
        "candidate_norms": [],
        "authority_blockers": [],
    }
    evidence["policy_grounding_matrix"] = {
        "schema_version": "policyos.scientist.policy_grounding_matrix.v1",
        "status": "pass",
        "claims": [
            {
                "claim_id": "rec_1",
                "claim_type": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": [],
                "no_grounding_rationale": "no norms retrieved",
            }
        ],
    }

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=evidence,
        normalize=False,
    )

    assert scorecard["quality_status"] == "fail"
    assert "lex_no_norm_authority_blocker_missing" in blocking_codes(scorecard)


@HDS_RED_XFAIL
def test_data_exists_requires_semantic_binding_ledger() -> None:
    evidence = complete_quality_evidence()
    evidence["fabric_retrieval_trace"]["candidate_sources"][0].update(
        {
            "source_id": "production-msme-panel",
            "available_columns": ["firm_id", "region", "credit_amount", "survival"],
            "relevance_rationale": "A production table exists.",
        }
    )
    evidence["policy_grounding_matrix"]["claims"][0].update(
        {
            "claim_id": "rec_survival",
            "claim_type": "empirical",
            "text": "Wartime credit support improves MSME survival.",
            "data_refs": ["production-msme-panel"],
            "method_refs": [],
            "norm_refs": [],
        }
    )
    evidence["semantic_binding_ledger"] = None

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert "semantic_binding_ledger_missing" in blocking_codes(scorecard)


@HDS_RED_XFAIL
def test_quality_status_pass_in_bundle_files_cannot_satisfy_readiness_runtime_refs(
    monkeypatch,
    tmp_path,
) -> None:
    bundle_root = tmp_path / "bundle"
    quality_dir = bundle_root / "quality_evidence"
    quality_dir.mkdir(parents=True)
    (bundle_root / "bundle.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.canary_evidence.v1",
                "quality_status": "pass",
                "runtime_quality_refs": {
                    "policy_grounding_matrix_ref": (
                        "quality_evidence/policy_grounding_matrix.json"
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    (quality_dir / "quality_scorecard.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.quality_scorecard.v1",
                "quality_status": "pass",
                "approval_state": "approval_ready",
                "evidence_refs": {
                    "policy_grounding_matrix_ref": (
                        "quality_evidence/policy_grounding_matrix.json"
                    )
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        gate,
        "_build_inventory_payload",
        lambda _repo_root: {
            "schema_version": "policyos.production_quality_evidence_inventory.v1",
            "serious_profile_required_refs": [
                {
                    "report_id": "scientist.policy_grounding_matrix",
                    "expected_ref": "runtime_quality_ref#policy_grounding_matrix_ref",
                    "status": "runtime_emitted",
                    "owner_runtime_layer": "scientist_policy_artifacts",
                    "producer": "runtime Scientist final-policy grounding emitter",
                    "first_missing_producer": None,
                    "validators": [
                        "polisyos.scientist.validation.policy_grounding.normalize_policy_grounding_matrix"
                    ],
                }
            ],
        },
    )
    monkeypatch.setattr(
        gate,
        "_component_results",
        lambda _repo_root, _inventory_payload: {
            "quality_evidence_inventory": {
                "status": "pass",
                "failures": [],
                "warnings": [],
            }
        },
    )

    payload = gate.build_readiness_payload(
        repo_root=REPO_ROOT,
        serious_evidence_root=bundle_root,
    )

    assert payload["status"] == "fail"
    assert payload["required_serious_profile_ref_failures"]
    assert payload["required_serious_profile_ref_failures"][0]["report_id"] == (
        "scientist.policy_grounding_matrix"
    )
