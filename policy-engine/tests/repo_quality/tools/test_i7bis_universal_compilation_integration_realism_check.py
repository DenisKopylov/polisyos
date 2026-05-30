from __future__ import annotations

# ruff: noqa: S101
from pathlib import Path

from tools.quality.validation import build_policy_evidence_capability_index as builder
from tools.quality.validation import (
    run_universal_compilation_integration_realism_check as i7bis,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_i7bis_runs_full_universal_path_and_inspects_w8b_warrants(tmp_path: Path) -> None:
    index_dir = tmp_path / "capability-index"
    assert builder.main(["--mode", "fixture", "--output-dir", str(index_dir)]) == 0

    report = i7bis.run_i7bis_universal_compilation_integration_realism_check(
        repo_root=REPO_ROOT,
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        audit_card_output_dir=tmp_path / "cards",
        capability_index_path=index_dir / "capability_index_v1.duckdb",
    )

    assert report["schema_version"] == i7bis.SCHEMA_VERSION
    assert report["status"] == "pass"
    assert report["checks"]["llm_formulator_invoked"]["status"] == "pass"
    assert report["checks"]["critic_ensemble_invoked"]["status"] == "pass"
    assert report["checks"]["hypothesis_ledger_persisted"]["status"] == "pass"
    assert report["checks"]["capability_index_loaded"]["status"] == "pass"
    assert report["checks"]["construct_registry_loaded"]["status"] == "pass"
    assert report["checks"]["capability_resolver_executed"]["status"] == "pass"
    assert report["checks"]["selected_capability_binding"]["status"] == "pass"
    assert report["checks"]["typed_blocked_capability_binding"]["status"] == "pass"
    assert report["checks"]["rejected_alternative_recorded"]["status"] == "pass"
    assert report["checks"]["producer_pipeline_bound"]["status"] == "pass"
    assert report["checks"]["producer_binding_emitted"]["status"] == "pass"
    assert report["checks"]["audit_card_generated"]["status"] == "pass"
    assert report["audit_card_manifest"]["card_count"] >= 1
    assert report["checks"]["candidate_firewall_enforced_with_audit"]["status"] == "pass"
    assert report["checks"]["runtime_pdc_graph_emitted"]["status"] == "pass"
    assert report["checks"]["nonzero_warrants"]["status"] == "pass"
    assert report["checks"]["nonzero_warrants"]["observed"][
        "argument_graph_inspection_status"
    ] == "pass"
    assert (
        report["checks"]["nonzero_warrants"]["observed"][
            "machine_inspectable_warrant_count"
        ]
        > 0
    )
    assert report["typed_blockers"] == []
    assert report["authority_boundary"]["max_authority_posture"] == "governed-pilot"
    assert "production_closeout_authority" in report["authority_boundary"]["may_not_use_for"]


def test_i7bis_requires_selected_binding_not_only_typed_blocker(tmp_path: Path) -> None:
    checks = i7bis._checks(
        {
            "capability_graph_trace": {
                "capability_index_loaded": True,
                "capability_index_ref": "policyos-capability-index-v1",
                "construct_registry_loaded": True,
                "construct_registry_ref": "construct-registry-v1",
                "resolver_executed": True,
                "binding_count": 1,
                "capability_bindings": [
                    {
                        "status": "blocked_no_candidate",
                        "rejected_alternatives": [{"capability_id": "capability:x"}],
                    }
                ],
            },
            "llm_universal_compilation": {
                "formulator": {"candidate_count": 1},
                "critic_ensemble": {"verdict_count": 1},
                "candidate_firewall": {"issues": []},
                "hypothesis_ledger_artifact_ref": "artifact://hypothesis-ledger",
            },
            "producer_pipeline": {
                "status": "pass",
                "stage_count": 1,
                "producer_binding_decision_count": 1,
                "claim_binding_count": 1,
            },
            "runtime_pdc_graph": {"status": "pass", "edge_count": 1},
        },
        repo_root=tmp_path,
        audit_card_manifest={"status": "pass", "card_count": 1},
    )

    assert checks["selected_capability_binding"]["status"] == "blocked"
    assert checks["typed_blocked_capability_binding"]["status"] == "pass"
