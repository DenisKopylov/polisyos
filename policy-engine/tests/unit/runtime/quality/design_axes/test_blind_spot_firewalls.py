from __future__ import annotations

from polisyos.runtime.quality.design_axes.blind_spot_firewalls import (
    evaluate_measurability_adequacy,
)


def test_mixed_observed_and_missing_constructs_remain_limited() -> None:
    """A disclosed unknown remains visible beside observed evidence."""

    record = evaluate_measurability_adequacy(
        case_id="case-mixed-measurability",
        design_ref="pdc://case-mixed-measurability/design",
        construct_rows=(
            {
                "construct_ref": "construct/registered-beneficiaries",
                "construct_label": "registered beneficiaries",
                "measurability_status": "observed",
                "evidence_refs": ["evidence://beneficiary-register"],
            },
            {
                "construct_ref": "construct/unreported-applicants",
                "construct_label": "applicants absent from the intake record",
                "measurability_status": "missing",
                "value_loss_disclosure_ref": "pdc://case-mixed-measurability/missing-applicants",
                "evidence_refs": ["evidence://intake-coverage-audit"],
            },
        ),
        semantic_binding_ledger={
            "ledger_ref": "pdc://case-mixed-measurability/semantic-binding",
            "declared_measurability_pass": False,
        },
        rule_version_ref="policyos.layer2.s6.measurability.v1",
    )

    missing = next(
        row
        for row in record.construct_rows
        if row.construct_ref == "construct/unreported-applicants"
    )
    assert record.firewall_disposition == "limit"
    assert missing.measurability_status == "missing"
    assert record.value_loss_disclosures[0].construct_ref == missing.construct_ref
    assert record.authority_boundary.may_not_use_for
