from __future__ import annotations

import pytest

from polisyos.runtime.quality.evidence_spine import (
    EVIDENCE_SPINE_CARRIER_SCHEMA_VERSION,
    EVIDENCE_SPINE_GRAPH_SCHEMA_VERSION,
    EvidenceSpineCarrier,
    EvidenceSpineNode,
    EvidenceSpineValidationError,
    build_evidence_spine_graph,
)

SCENARIO_CONTRACT_ID = "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"


def _scenario_contract(*, requirements: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "schema_version": "policyos.scenario_evidence_contract.v1",
        "contract_id": SCENARIO_CONTRACT_ID,
        "requirements": requirements
        if requirements is not None
        else [
            {
                "requirement_id": "scenario:ukraine_msme_wartime_credit_support:data:production_msme_panel",
                "domain": "data",
            },
            {
                "requirement_id": "scenario:ukraine_msme_wartime_credit_support:legal:msme_credit",
                "domain": "legal",
            },
        ],
    }


def test_spine_carrier_requires_scenario_contract_and_requirement_ids() -> None:
    with pytest.raises(EvidenceSpineValidationError, match="scenario_evidence_contract_id"):
        EvidenceSpineCarrier.from_scenario_contract(
            {"requirements": [{"requirement_id": "req.data"}]},
            producer_component="runtime.nl_pipeline",
            producer_report_schema="policyos.test.v1",
            reader_contract="runtime_quality.test.reader",
            authority_profile="research",
        )

    with pytest.raises(EvidenceSpineValidationError, match="requirement_ids"):
        EvidenceSpineCarrier.from_scenario_contract(
            _scenario_contract(requirements=[]),
            producer_component="runtime.nl_pipeline",
            producer_report_schema="policyos.test.v1",
            reader_contract="runtime_quality.test.reader",
            authority_profile="research",
        )

    carrier = EvidenceSpineCarrier.from_scenario_contract(
        _scenario_contract(),
        producer_component="runtime.nl_pipeline",
        producer_report_schema="policyos.test.v1",
        reader_contract="runtime_quality.test.reader",
        authority_profile="research",
        code_revision="test-revision",
    )

    payload = carrier.to_dict()
    assert carrier.scenario_evidence_contract_id == SCENARIO_CONTRACT_ID
    assert carrier.requirement_ids == (
        "scenario:ukraine_msme_wartime_credit_support:data:production_msme_panel",
        "scenario:ukraine_msme_wartime_credit_support:legal:msme_credit",
    )
    assert payload["schema_version"] == EVIDENCE_SPINE_CARRIER_SCHEMA_VERSION
    assert payload["scenario_evidence_contract_id"] == SCENARIO_CONTRACT_ID
    assert payload["requirement_ids"] == list(carrier.requirement_ids)
    assert payload["producer_component"] == "runtime.nl_pipeline"
    assert payload["code_revision"] == "test-revision"


def test_spine_graph_fails_when_producer_drops_consumed_contract_id() -> None:
    carrier = EvidenceSpineCarrier.from_scenario_contract(
        _scenario_contract(),
        producer_component="runtime.nl_pipeline",
        producer_report_schema="policyos.runtime.request_context.v1",
        reader_contract="runtime_quality.scenario_contract_propagation_graph",
        authority_profile="research",
    )
    graph = build_evidence_spine_graph(
        [
            EvidenceSpineNode(
                node_id="runtime.request_context",
                producer_component="runtime.nl_pipeline",
                artifact_ref="request.sanitized.json",
                consumed_carrier=carrier,
                emitted_scenario_evidence_contract_id=SCENARIO_CONTRACT_ID,
                consumed_requirement_ids=carrier.requirement_ids,
                emitted_requirement_ids=carrier.requirement_ids,
            ),
            EvidenceSpineNode(
                node_id="fabric.retrieval_trace",
                producer_component="fabric",
                artifact_ref="quality_evidence/fabric_retrieval_trace.json",
                consumed_carrier=carrier,
                emitted_scenario_evidence_contract_id=None,
                consumed_requirement_ids=carrier.requirement_ids[:1],
                emitted_requirement_ids=carrier.requirement_ids[:1],
            ),
        ],
        bundle_ref="bundle://test",
    )

    assert graph["schema_version"] == EVIDENCE_SPINE_GRAPH_SCHEMA_VERSION
    assert graph["status"] == "fail"
    assert {
        finding["code"]
        for finding in graph["findings"]
        if isinstance(finding, dict) and finding["status"] == "fail"
    } == {"evidence_spine_contract_dropped"}
    assert graph["findings"][0]["producer_component"] == "fabric"
    assert graph["findings"][0]["artifact_ref"] == (
        "quality_evidence/fabric_retrieval_trace.json"
    )


def test_spine_graph_passes_when_contract_and_requirement_ids_propagate() -> None:
    carrier = EvidenceSpineCarrier.from_scenario_contract(
        _scenario_contract(),
        producer_component="runtime.nl_pipeline",
        producer_report_schema="policyos.runtime.request_context.v1",
        reader_contract="runtime_quality.scenario_contract_propagation_graph",
        authority_profile="research",
    )

    graph = build_evidence_spine_graph(
        [
            EvidenceSpineNode(
                node_id="fabric.retrieval_trace",
                producer_component="fabric",
                artifact_ref="quality_evidence/fabric_retrieval_trace.json",
                consumed_carrier=carrier,
                emitted_scenario_evidence_contract_id=SCENARIO_CONTRACT_ID,
                consumed_requirement_ids=carrier.requirement_ids[:1],
                emitted_requirement_ids=carrier.requirement_ids[:1],
            ),
            EvidenceSpineNode(
                node_id="lex.normative_evidence",
                producer_component="lex",
                artifact_ref="quality_evidence/normative_evidence.json",
                consumed_carrier=carrier,
                emitted_scenario_evidence_contract_id=SCENARIO_CONTRACT_ID,
                consumed_requirement_ids=carrier.requirement_ids[1:],
                emitted_requirement_ids=carrier.requirement_ids[1:],
            ),
        ]
    )

    assert graph["status"] == "pass"
    assert graph["findings"] == []
