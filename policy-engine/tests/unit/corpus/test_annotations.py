from __future__ import annotations

# ruff: noqa: S101
import json
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from polisyos.corpus import (
    POLICY_CASE_ANNOTATION_SCHEMA_VERSION,
    PolicyCaseAnnotation,
    load_outcome_corpus_annotations,
    load_policy_case_annotation,
    policy_case_annotation_audit_surface,
    write_policy_case_annotation_artifact,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_policy_case_annotation_loads_protocol_fields_and_audit_surface(tmp_path: Path) -> None:
    markdown = tmp_path / "msme-credit.md"
    markdown.write_text(_annotation_markdown(_valid_payload()), encoding="utf-8")

    annotation = load_policy_case_annotation(markdown)
    surface = policy_case_annotation_audit_surface(annotation)
    artifact_path = write_policy_case_annotation_artifact(annotation, tmp_path / "artifacts")
    persisted = json.loads(artifact_path.read_text(encoding="utf-8"))
    corpus = load_outcome_corpus_annotations(tmp_path)

    assert annotation.schema_version == POLICY_CASE_ANNOTATION_SCHEMA_VERSION
    assert annotation.claims[0].text_ref == "text:case:summary"
    assert annotation.claims[0].scope.population == ("displaced_msmes",)
    assert annotation.claims[0].evidence_refs == ("evidence:evaluation-report",)
    assert annotation.claims[0].method_refs == ("method:quasi-experimental-evaluation",)
    assert annotation.claims[0].legal_refs == ("legal:budget-code-authority",)
    assert annotation.claims[0].participation_refs == ("participation:lender-msme-consultation",)
    assert annotation.claims[0].risks == ("risk:adverse-selection",)
    assert annotation.claims[0].tradeoffs == ("tradeoff:fiscal-risk-vs-credit-access",)
    assert annotation.claims[0].admissibility_label == "limited"
    assert annotation.claims[0].limitation_refs == ("limitation:selection-bias",)
    assert annotation.claims[0].contestability_status == "contested"
    assert annotation.obligations[0].generated_from_facets == (
        "facet:instrument.credit-guarantee",
        "facet:targeting.displaced-msmes",
    )
    assert annotation.obligations[0].required_evidence_family == "program_evaluation"
    assert annotation.known_outcomes_or_failures[0].would_prior_obligation_have_flagged is True
    assert surface["surface"] == "universal_outcome_corpus.annotation_audit"
    assert surface["summary"] == {
        "claim_count": 1,
        "obligation_count": 1,
        "known_outcome_or_failure_count": 1,
        "reference_count": 10,
    }
    assert surface["authority_boundary"]["may_not_use_for"] == [
        "claim_authority",
        "producer_evidence_authority",
        "legal_authority",
        "method_validity",
        "participation_legitimacy",
        "projection_authority",
    ]
    assert persisted["case_id"] == "ua-msme-credit-guarantee-2022"
    assert persisted["capability_reality_label"] == "implemented"
    assert [item.case_id for item in corpus] == ["ua-msme-credit-guarantee-2022"]


def test_claim_records_must_include_all_w11b_protocol_ref_fields() -> None:
    payload = _valid_payload()
    del payload["claims"][0]["method_refs"]

    with pytest.raises(ValidationError, match="method_refs"):
        PolicyCaseAnnotation.model_validate(payload)


def test_claim_refs_must_be_grounded_in_case_reference_index() -> None:
    payload = _valid_payload()
    payload["claims"][0]["evidence_refs"] = ["evidence:missing-evaluation"]

    with pytest.raises(ValidationError, match="unregistered annotation refs"):
        PolicyCaseAnnotation.model_validate(payload)


def test_case_without_claim_decomposition_annotation_fails_closed(tmp_path: Path) -> None:
    markdown = tmp_path / "structural-only-case.md"
    payload = _valid_payload()
    payload["claims"] = []
    markdown.write_text(_annotation_markdown(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match="claims"):
        load_policy_case_annotation(markdown)


def _annotation_markdown(payload: dict[str, object]) -> str:
    import yaml

    return f"---\n{yaml.safe_dump(payload, sort_keys=False)}---\n\n# Annotated case\n"


def _valid_payload() -> dict[str, object]:
    return {
        "case_id": "ua-msme-credit-guarantee-2022",
        "jurisdiction": "Ukraine",
        "policy_time": "2022-2024",
        "policy_instrument": {
            "instrument_type": "credit_guarantee",
            "delivery_channel": "partner_banks",
            "funding_channel": "state_budget",
        },
        "targeting": {
            "targeting_type": "means_and_displacement_tested",
            "beneficiary_classes": ["displaced_msmes"],
            "affected_populations": ["msme_workers", "lenders", "taxpayers"],
        },
        "references": [
            {
                "ref_id": "text:case:summary",
                "ref_type": "source",
                "source_ref": "repo://docs/research/universal-policy-design/outcome-corpus/ua-msme-credit-guarantee-2022.md#summary",
                "title": "Case summary",
            },
            {
                "ref_id": "evidence:evaluation-report",
                "ref_type": "evidence",
                "source_ref": "https://example.invalid/msme-credit-evaluation",
                "title": "Programme evaluation",
            },
            {
                "ref_id": "method:quasi-experimental-evaluation",
                "ref_type": "method",
                "source_ref": "https://example.invalid/msme-method-note",
                "title": "Evaluation method note",
            },
            {
                "ref_id": "legal:budget-code-authority",
                "ref_type": "legal",
                "source_ref": "https://example.invalid/budget-code",
                "title": "Budget authority",
            },
            {
                "ref_id": "participation:lender-msme-consultation",
                "ref_type": "participation",
                "source_ref": "https://example.invalid/consultation-summary",
                "title": "Consultation summary",
            },
            {
                "ref_id": "risk:adverse-selection",
                "ref_type": "risk",
                "source_ref": "https://example.invalid/risk-register",
                "title": "Adverse selection risk",
            },
            {
                "ref_id": "tradeoff:fiscal-risk-vs-credit-access",
                "ref_type": "tradeoff",
                "source_ref": "https://example.invalid/fiscal-risk-note",
                "title": "Fiscal risk tradeoff",
            },
            {
                "ref_id": "limitation:selection-bias",
                "ref_type": "limitation",
                "source_ref": "https://example.invalid/evaluation-limitations",
                "title": "Selection bias limitation",
            },
            {
                "ref_id": "outcome:uptake-concentrated-in-existing-bank-clients",
                "ref_type": "outcome",
                "source_ref": "https://example.invalid/outcome-audit",
                "title": "Known uptake failure",
            },
            {
                "ref_id": "source:redacted-bank-panel",
                "ref_type": "source",
                "redacted_source_hash": (
                    "sha256:5979a23d573a65d5a3b64a9c4b33f5ce2de6c844b2efb50b"
                    "94f9d24bb7d84354"
                ),
                "title": "Redacted bank portfolio panel",
            },
        ],
        "claims": [
            {
                "claim_id": "claim:credit-access-effect",
                "claim_type": "causal",
                "text_ref": "text:case:summary",
                "scope": {
                    "population": ["displaced_msmes"],
                    "geography": ["northern_regions"],
                    "time_period": "2022-2024",
                    "institution": ["ministry_of_economy", "partner_banks"],
                },
                "evidence_refs": ["evidence:evaluation-report"],
                "method_refs": ["method:quasi-experimental-evaluation"],
                "legal_refs": ["legal:budget-code-authority"],
                "participation_refs": ["participation:lender-msme-consultation"],
                "risks": ["risk:adverse-selection"],
                "tradeoffs": ["tradeoff:fiscal-risk-vs-credit-access"],
                "admissibility_label": "limited",
                "limitation_refs": ["limitation:selection-bias"],
                "contestability_status": "contested",
            }
        ],
        "obligations": [
            {
                "obligation_id": "obligation:program-evaluation-for-credit-access",
                "generated_from_facets": [
                    "facet:instrument.credit-guarantee",
                    "facet:targeting.displaced-msmes",
                ],
                "required_evidence_family": "program_evaluation",
                "status": "limitation_required",
                "reviewer_notes": (
                    "Prior obligation should require evaluation evidence stratified by "
                    "new-to-bank and existing-bank-client MSMEs."
                ),
            }
        ],
        "known_outcomes_or_failures": [
            {
                "finding_id": "outcome:uptake-concentrated-in-existing-bank-clients",
                "source_ref": "outcome:uptake-concentrated-in-existing-bank-clients",
                "would_prior_obligation_have_flagged": True,
            }
        ],
        "annotation_provenance": {
            "reviewer_role": "policy_generalist",
            "expertise_basis": "credit-guarantee programme evaluation",
            "conflicts": [],
            "reviewed_at": "2026-05-24",
        },
    }
