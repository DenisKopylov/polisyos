from __future__ import annotations

from polisyos.runtime.quality.claim_registry import (
    build_runtime_claim_registry,
    claim_registry_rows_by_id,
    normalize_runtime_claim_registry,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _major_claim(**overrides: object) -> dict[str, object]:
    claim: dict[str, object] = {
        "claim_id": "rec_credit_guarantee",
        "claim_family": "recommendation",
        "major": True,
        "text": "Target capped credit guarantees to liquidity-constrained MSMEs.",
    }
    claim.update(overrides)
    return claim


def test_runtime_claim_registry_rejects_global_pools_without_per_claim_entry() -> None:
    registry = normalize_runtime_claim_registry(
        {"schema_version": "policyos.runtime.claim_registry.v1", "claims": []},
        claims=[_major_claim()],
        normative_evidence={
            "status": "pass",
            "applied_norms": [{"norm_id": "norm.ua.credit_guarantee"}],
        },
        foundry_method_report={
            "status": "pass",
            "selected_methods": [{"method_id": "foundry.execute"}],
        },
    )

    issue_codes = {issue["code"] for issue in registry["issues"]}
    assert registry["status"] == "fail"
    assert "runtime_claim_registry_entry_missing" in issue_codes
    assert registry["summary"]["claim_count"] == 0
    assert registry["summary"]["global_norm_ref_count"] == 1
    assert registry["summary"]["generic_global_method_ref_count"] == 1


def test_runtime_claim_registry_binds_major_claim_to_all_required_axes() -> None:
    registry = build_runtime_claim_registry(
        claims=[
            _major_claim(
                scenario_requirement_refs=["scenario.req.credit_support"],
                data_refs=["source.msme_panel"],
                selected_norm_refs=["norm.ua.credit_guarantee"],
                rejected_norm_refs=["norm.ua.unrelated"],
                method_output_refs=["foundry.did.msme_survival"],
                portfolio_refs=["portfolio.rec_credit_guarantee"],
                argument_refs=["argument.rec_credit_guarantee"],
                warrant_refs=["warrant.rec_credit_guarantee"],
                rebuttal_refs=["rebuttal.rec_credit_guarantee"],
                counter_evidence_refs=["counter.rec_credit_guarantee"],
                limitation_refs=["data-quality.recency.msme_panel"],
                accepted_deficit_refs=["deficit.recency.msme_panel"],
                independence_refs=["independence.rec_credit_guarantee"],
                synthesis_refs=["synthesis.rec_credit_guarantee"],
                scholar_deficit_refs=["scholar-deficit.msme_credit"],
                objective_tradeoff_refs=["objective_tradeoff.rec_credit_guarantee"],
                uncertainty_refs=["uncertainty.rec_credit_guarantee"],
                numerical_semantics_refs=["num_semantics.rec_credit_guarantee"],
                monitoring_refs=["monitoring.rec_credit_guarantee"],
                specification_curve_refs=["spec_curve.rec_credit_guarantee"],
                claim_ref=_sha("a"),
                runtime_event_ref="event://runtime_claim_registry/rec_credit_guarantee",
            )
        ],
        run_id="run-wave6",
    )

    rows = claim_registry_rows_by_id(registry)
    row = rows["rec_credit_guarantee"]

    assert registry["status"] == "pass"
    assert row["scenario_requirement_refs"] == ["scenario.req.credit_support"]
    assert row["data_refs"] == ["source.msme_panel"]
    assert row["selected_norm_refs"] == ["norm.ua.credit_guarantee"]
    assert row["rejected_norm_refs"] == ["norm.ua.unrelated"]
    assert row["method_output_refs"] == ["foundry.did.msme_survival"]
    assert row["portfolio_refs"] == ["portfolio.rec_credit_guarantee"]
    assert row["argument_refs"] == ["argument.rec_credit_guarantee"]
    assert row["warrant_refs"] == ["warrant.rec_credit_guarantee"]
    assert row["rebuttal_refs"] == ["rebuttal.rec_credit_guarantee"]
    assert row["counter_evidence_refs"] == ["counter.rec_credit_guarantee"]
    assert row["limitation_refs"] == ["data-quality.recency.msme_panel"]
    assert row["accepted_deficit_refs"] == ["deficit.recency.msme_panel"]
    assert row["source_data_refs"] == ["source.msme_panel"]
    assert row["legal_norm_refs"] == ["norm.ua.credit_guarantee"]
    assert row["method_refs"] == ["foundry.did.msme_survival"]
    assert row["selected_producer_refs"]["lex"] == ["norm.ua.credit_guarantee"]
    assert row["selected_producer_refs"]["foundry"] == [
        "foundry.did.msme_survival",
        "uncertainty.rec_credit_guarantee",
    ]
