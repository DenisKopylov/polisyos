from __future__ import annotations

from datetime import UTC, datetime

# ruff: noqa: S101
from polisyos.runtime.quality.nl_replay_orchestration import (
    NL_REPLAY_ORCHESTRATION_FILE_REF,
    NL_REPLAY_ORCHESTRATION_RECORD_KEY,
    NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION,
    _collect_surface_refs,
    build_nl_replay_orchestration_continuity,
)
from polisyos.runtime.quality.public_export import PUBLIC_EXPORT_SCHEMA_VERSION
from polisyos.runtime.quality.replay import build_replay_manifest, explain_replay_drift


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _spine_context() -> dict[str, object]:
    return {
        "schema_version": "policyos.producer_spine_context.v1",
        "context_id": "producer-spine-context-w4a",
        "concept_spine_ref": _sha("2"),
        "jurisdiction_spine_ref": _sha("6"),
        "canonical_concept_refs": ["concept.msme_survival_rate"],
        "jurisdiction_refs": ["UA"],
        "consumer_components": [
            "lex",
            "fabric",
            "scholar",
            "foundry",
            "scientist",
            "final_compiler",
        ],
    }


def _claim_registry() -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.claim_registry.v1",
        "runtime_claim_registry_ref": "quality_evidence/runtime_claim_registry.json",
        "status": "pass",
        "claims": [
            {
                "claim_id": "rec_1",
                "claim_ref": "claim:rec_1",
                "runtime_event_ref": "event://claim/rec_1",
                "concept_spine_ref": _sha("2"),
                "producer_handshake_ledger_ref": "producer-handshake-ledger:w4a",
                "producer_handshake_refs": ["producer-handshake:fabric"],
                "selected_producer_refs": {
                    "fabric": ["binding.fabric.msme-panel"],
                    "lex": ["binding.lex.credit-norm"],
                },
            }
        ],
    }


def _quality_evidence() -> dict[str, object]:
    return {
        "semantic_binding_ledger": {
            "schema_version": "policyos.semantic_binding_ledger.v1",
            "semantic_binding_ref": _sha("b"),
            "status": "pass",
            "spine_context": _spine_context(),
            "producer_handshake_ledger": {
                "producer_handshake_ledger_ref": "producer-handshake-ledger:w4a",
                "status": "pass",
                "records": [
                    {
                        "handshake_id": "producer-handshake:fabric",
                        "producer_component": "fabric",
                        "status": "pass",
                        "state": "emitted_binding",
                        "selected_binding_refs": ["binding.fabric.msme-panel"],
                        "emitted_binding_refs": ["binding.fabric.msme-panel"],
                    }
                ],
            },
            "fabric": [
                {
                    "candidate_spine_binding_refs": ["binding.fabric.msme-panel"],
                    "spine_blocker_refs": [],
                }
            ],
            "lex": [
                {
                    "candidate_spine_binding_refs": ["binding.lex.credit-norm"],
                    "spine_blocker_refs": [],
                }
            ],
        },
        "runtime_claim_registry": _claim_registry(),
        "evidence_spine_handoff_ledger": {
            "schema_version": "policyos.evidence_spine_handoff_ledger.v1",
            "status": "pass",
            "handoffs": [
                {
                    "handoff_id": "handoff:request",
                    "handoff_kind": "nl_request_creation",
                    "carrier_ref": "evidence-spine:carrier-w4a",
                    "parent_spine_ref": "evidence-spine:carrier-w4a",
                    "concept_spine_ref": _sha("2"),
                    "producer_handshake_refs": ["producer-handshake:fabric"],
                    "input_refs": ["request.sanitized.json"],
                    "output_refs": ["job.json"],
                    "producer_ref": "runtime.api.nl_request",
                    "consumer_ref": "runtime.control_plane.create_job",
                }
            ],
        },
        "scenario_contract_propagation_graph": {
            "schema_version": "policyos.scenario_contract_propagation_graph.v1",
            "status": "pass",
            "nodes": [
                {
                    "node_id": "runtime.request_context",
                    "carrier": {
                        "spine_id": "evidence-spine:carrier-w4a",
                        "trace_id": "evidence-spine:carrier-w4a",
                    },
                }
            ],
        },
    }


def test_nl_replay_continuity_binds_carrier_spine_claims_and_producers() -> None:
    record = build_nl_replay_orchestration_continuity(
        request_context={
            "context": {
                "producer_spine_context": _spine_context(),
                "scenario_evidence_contract": {
                    "scenario_evidence_contract_id": "scenario-contract:w4a",
                    "requirements": [{"requirement_id": "scenario.req.credit_support"}],
                },
            }
        },
        workflow_state={"producer_spine_context": _spine_context()},
        job_progress={
            "runtime_quality_refs": {
                "concept_spine_ref": _sha("2"),
                "jurisdiction_spine_ref": _sha("6"),
                "runtime_claim_registry_ref": "quality_evidence/runtime_claim_registry.json",
            },
            "evidence_spine_handoffs": _quality_evidence()["evidence_spine_handoff_ledger"][
                "handoffs"
            ],
        },
        quality_evidence=_quality_evidence(),
        replay_manifest={
            "orchestration_continuity": {
                "carrier_ref": "evidence-spine:carrier-w4a",
                "concept_spine_ref": _sha("2"),
                "runtime_claim_registry_ref": "quality_evidence/runtime_claim_registry.json",
            }
        },
        bundle_payload={
            "files": {
                "quality_evidence": {
                    "runtime_orchestration_continuity": (
                        "quality_evidence/runtime_orchestration_continuity.json"
                    )
                }
            }
        },
        inspection_report={
            "bundle_inspections": [
                {
                    "components": [
                        {
                            "component_id": "runtime_orchestration_continuity",
                            "status": "pass",
                            "evidence_refs": [
                                "quality_evidence/runtime_orchestration_continuity.json"
                            ],
                        }
                    ]
                }
            ]
        },
        readiness_payload={
            "status": "pass",
            "orchestration_continuity_ref": (
                "quality_evidence/runtime_orchestration_continuity.json"
            ),
            "carrier_ref": "evidence-spine:carrier-w4a",
        },
        export_payload={
            "semantic_audit": {
                "runtime_orchestration_continuity": {"carrier_ref": "evidence-spine:carrier-w4a"}
            }
        },
    )

    assert record["schema_version"] == NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION
    assert record["status"] == "pass"
    assert record["carrier_ref"] == "evidence-spine:carrier-w4a"
    assert record["concept_spine_ref"] == _sha("2")
    assert record["jurisdiction_spine_ref"] == _sha("6")
    assert record["runtime_claim_registry_ref"] == "quality_evidence/runtime_claim_registry.json"
    assert record["producer_handshake_ledger_ref"] == "producer-handshake-ledger:w4a"
    assert record["producer_handshake_refs"] == ["producer-handshake:fabric"]
    assert {
        "binding.fabric.msme-panel",
        "binding.lex.credit-norm",
    } <= set(record["producer_binding_refs"])
    assert record["summary"]["surface_count"] >= 8
    assert record["findings"] == []


def test_replay_manifest_treats_orchestration_continuity_drift_as_high_impact() -> None:
    continuity = build_nl_replay_orchestration_continuity(
        request_context={"context": {"producer_spine_context": _spine_context()}},
        quality_evidence=_quality_evidence(),
    )

    baseline = build_replay_manifest(
        request_payload={"question": "Can replay see the same carrier?"},
        orchestration_continuity=continuity,
    )
    replay = dict(baseline)
    replay["orchestration_continuity"] = {
        **dict(baseline["orchestration_continuity"]),
        "carrier_ref": "evidence-spine:other-carrier",
    }

    explanation = explain_replay_drift(
        baseline_manifest=baseline,
        replay_manifest=replay,
    )

    assert explanation["status"] == "unexplained_drift"
    assert explanation["production_readiness"] == "fail"
    assert explanation["summary"]["drift_sources"] == ["orchestration"]
    assert explanation["differences"][0]["impact"] == "high"


_SOURCE_REF_FIXTURE = {
    "carrier_ref": "evidence-spine:source",
    "concept_spine_ref": _sha("a"),
    "jurisdiction_spine_ref": _sha("b"),
    "runtime_claim_registry_ref": "quality_evidence/source-claim-registry.json",
    "candidate_spine_binding_refs": ["binding:source"],
}


def test_export_endpoint_cannot_supply_required_source_refs() -> None:
    source_refs = {
        key: value
        for key, value in _SOURCE_REF_FIXTURE.items()
        if key != "runtime_claim_registry_ref"
    }
    record = build_nl_replay_orchestration_continuity(
        request_context=source_refs,
        export_payload={
            "runtime_claim_registry_ref": "quality_evidence/projection-only.json",
        },
        required_surfaces=("request_context", "export"),
        generated_at=_fixed_time(),
    )

    assert record["status"] == "fail"
    assert record["runtime_claim_registry_ref"] is None
    assert "nl_replay_orchestration_runtime_claim_registry_ref_missing" in {
        item["code"] for item in record["findings"]
    }
    assert "nl_replay_orchestration_export_ref_unbound" in {
        item["code"] for item in record["findings"]
    }
    export_row = next(row for row in record["surface_coverage"] if row["surface"] == "export")
    assert export_row["runtime_claim_registry_refs"] == ["quality_evidence/projection-only.json"]


def test_malformed_export_continuity_is_a_typed_refusal() -> None:
    record = build_nl_replay_orchestration_continuity(
        export_payload={
            "semantic_audit": {
                "runtime_orchestration_continuity": {
                    "schema_version": NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION,
                    "authority_role": "projection_only",
                    "status": "pass",
                    "carrier_ref": "evidence-spine:malformed-endpoint",
                }
            }
        },
        required_surfaces=("export",),
        generated_at=_fixed_time(),
    )

    assert record["status"] == "fail"
    assert record["carrier_ref"] is None
    invalid = [
        item
        for item in record["findings"]
        if item["code"] == "nl_replay_orchestration_embedded_record_invalid"
    ]
    assert len(invalid) == 1
    assert invalid[0]["surface"] == "export"


def test_public_export_continuity_projection_is_audit_only() -> None:
    source_refs = {
        key: value
        for key, value in _SOURCE_REF_FIXTURE.items()
        if key != "runtime_claim_registry_ref"
    }
    projection = {
        "schema_version": NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION,
        "status": "pass",
        "carrier_ref": "evidence-spine:source",
        "concept_spine_ref": _sha("a"),
        "jurisdiction_spine_ref": _sha("b"),
        "runtime_claim_registry_ref": "quality_evidence/projection-only-registry.json",
        "producer_handshake_ledger_ref": None,
        "handoff_ref_count": 0,
        "producer_binding_ref_count": 1,
        "authority_role": "projection_only",
        "may_not_use_for": [
            "producer_domain_truth",
            "runtime_closeout_authority",
            "scorecard_authority",
            "approval_authority",
        ],
    }
    export_payload = {
        "schema_version": PUBLIC_EXPORT_SCHEMA_VERSION,
        "artifacts": {"runtime_orchestration_continuity": projection},
        "semantic_audit": {"runtime_orchestration_continuity": projection},
    }

    record = build_nl_replay_orchestration_continuity(
        request_context=source_refs,
        export_payload=export_payload,
        required_surfaces=("request_context", "export"),
        generated_at=_fixed_time(),
    )

    assert record["status"] == "fail"
    assert record["runtime_claim_registry_ref"] is None
    assert "nl_replay_orchestration_export_ref_unbound" in {
        item["code"] for item in record["findings"]
    }
    export_row = next(row for row in record["surface_coverage"] if row["surface"] == "export")
    assert export_row["runtime_claim_registry_refs"] == [
        "quality_evidence/projection-only-registry.json"
    ]


def test_previous_continuity_output_cannot_seed_a_later_source_basis() -> None:
    previous = build_nl_replay_orchestration_continuity(
        request_context=_SOURCE_REF_FIXTURE,
        required_surfaces=("request_context",),
        generated_at=_fixed_time(),
    )
    record = build_nl_replay_orchestration_continuity(
        workflow_state={},
        replay_manifest={"orchestration_continuity": previous},
        quality_evidence={NL_REPLAY_ORCHESTRATION_RECORD_KEY: previous},
        required_surfaces=("workflow_state", "replay_manifest", "quality_evidence"),
        generated_at=_fixed_time(),
    )

    assert previous["status"] == "pass"
    assert previous["producer_binding_refs"] == ["binding:source"]
    assert record["status"] == "fail"
    assert record["carrier_ref"] is None
    assert record["concept_spine_ref"] is None
    assert record["jurisdiction_spine_ref"] is None
    assert record["runtime_claim_registry_ref"] is None
    assert record["producer_binding_refs"] == []
    assert record["handoff_refs"] == [NL_REPLAY_ORCHESTRATION_FILE_REF]
    assert {
        "nl_replay_orchestration_carrier_ref_missing",
        "nl_replay_orchestration_concept_spine_ref_missing",
        "nl_replay_orchestration_jurisdiction_spine_ref_missing",
        "nl_replay_orchestration_runtime_claim_registry_ref_missing",
        "nl_replay_orchestration_producer_binding_refs_missing",
    } <= {item["code"] for item in record["findings"]}


def test_malformed_embedded_continuity_is_a_typed_refusal() -> None:
    record = build_nl_replay_orchestration_continuity(
        quality_evidence={
            NL_REPLAY_ORCHESTRATION_RECORD_KEY: {
                "schema_version": NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION,
                "status": "pass",
                "carrier_ref": "evidence-spine:self-labeled",
            }
        },
        required_surfaces=("quality_evidence",),
        generated_at=_fixed_time(),
    )

    assert record["status"] == "fail"
    assert record["carrier_ref"] is None
    invalid = [
        item
        for item in record["findings"]
        if item["code"] == "nl_replay_orchestration_embedded_record_invalid"
    ]
    assert len(invalid) == 1
    assert invalid[0]["surface"] == "quality_evidence"
    assert invalid[0]["field"] == NL_REPLAY_ORCHESTRATION_RECORD_KEY


def test_observations_cannot_supply_selected_source_refs() -> None:
    required_refs = {
        "carrier_ref": "evidence-spine:projection-only",
        "concept_spine_ref": _sha("d"),
        "jurisdiction_spine_ref": _sha("e"),
        "runtime_claim_registry_ref": "quality_evidence/projection-only-registry.json",
        "candidate_spine_binding_refs": ["binding:projection-only"],
    }
    source_surface_arguments = {
        "request_context": "request_context",
        "workflow_state": "workflow_state",
        "job_progress": "job_progress",
        "quality_evidence": "quality_evidence",
    }

    for surface_name, argument_name in source_surface_arguments.items():
        projection = {
            "schema_version": PUBLIC_EXPORT_SCHEMA_VERSION,
            "runtime_quality_refs": required_refs,
        }
        record = build_nl_replay_orchestration_continuity(
            **{argument_name: projection},
            required_surfaces=(surface_name,),
            generated_at=_fixed_time(),
        )

        assert record["status"] == "fail"
        assert record["carrier_ref"] is None
        assert record["concept_spine_ref"] is None
        assert record["jurisdiction_spine_ref"] is None
        assert record["runtime_claim_registry_ref"] is None
        assert record["producer_binding_refs"] == []
        typed_refusal = [
            item
            for item in record["findings"]
            if item["code"] == "nl_replay_orchestration_projection_on_source_surface"
        ]
        assert len(typed_refusal) == 1
        assert typed_refusal[0]["surface"] == surface_name

    observation_surface_arguments = {
        "replay_manifest": "replay_manifest",
        "bundle": "bundle_payload",
        "inspection": "inspection_report",
        "readiness": "readiness_payload",
        "export": "export_payload",
    }
    for surface_name, argument_name in observation_surface_arguments.items():
        projection = {
            "authority_role": "projection_only",
            "runtime_quality_refs": required_refs,
        }
        record = build_nl_replay_orchestration_continuity(
            **{argument_name: projection},
            required_surfaces=(surface_name,),
            generated_at=_fixed_time(),
        )

        assert record["status"] == "fail"
        assert record["carrier_ref"] is None
        assert record["concept_spine_ref"] is None
        assert record["jurisdiction_spine_ref"] is None
        assert record["runtime_claim_registry_ref"] is None
        assert record["producer_binding_refs"] == []
        observation_row = next(
            row for row in record["surface_coverage"] if row["surface"] == surface_name
        )
        assert observation_row["carrier_refs"] == ["evidence-spine:projection-only"]
        expected_code = (
            "nl_replay_orchestration_export_ref_unbound"
            if surface_name == "export"
            else "nl_replay_orchestration_observation_ref_unbound"
        )
        assert any(
            item["code"] == expected_code and item["surface"] == surface_name
            for item in record["findings"]
        )


def test_observed_previous_continuity_summary_cannot_seed_source_basis() -> None:
    previous = build_nl_replay_orchestration_continuity(
        request_context=_SOURCE_REF_FIXTURE,
        required_surfaces=("request_context",),
        generated_at=_fixed_time(),
    )
    record = build_nl_replay_orchestration_continuity(
        bundle_payload={"previous_continuity": previous},
        required_surfaces=("bundle",),
        generated_at=_fixed_time(),
    )

    assert previous["status"] == "pass"
    assert record["status"] == "fail"
    assert record["carrier_ref"] is None
    assert record["concept_spine_ref"] is None
    assert record["jurisdiction_spine_ref"] is None
    assert record["runtime_claim_registry_ref"] is None
    assert record["producer_binding_refs"] == []
    bundle_row = next(row for row in record["surface_coverage"] if row["surface"] == "bundle")
    assert bundle_row["carrier_refs"] == ["evidence-spine:source"]
    assert "nl_replay_orchestration_carrier_ref_missing" in {
        item["code"] for item in record["findings"]
    }
    assert any(
        item["code"] == "nl_replay_orchestration_observation_ref_unbound"
        and item["surface"] == "bundle"
        and item["field"] == "carrier_refs"
        for item in record["findings"]
    )


def test_markerless_arbitrary_source_map_remains_a_bounded_diagnostic_residual() -> None:
    record = build_nl_replay_orchestration_continuity(
        request_context={
            "unrecognized_nested_container": {
                "carrier_ref": "evidence-spine:markerless",
                "runtime_claim_registry_ref": "quality_evidence/markerless-registry.json",
            }
        },
        required_surfaces=("request_context",),
        generated_at=_fixed_time(),
    )

    assert record["status"] == "fail"
    assert record["carrier_ref"] == "evidence-spine:markerless"
    assert record["runtime_claim_registry_ref"] == "quality_evidence/markerless-registry.json"
    assert not {
        "nl_replay_orchestration_projection_on_source_surface",
        "nl_replay_orchestration_embedded_record_invalid",
    } & {item["code"] for item in record["findings"]}


def test_projection_labeled_continuity_in_source_cannot_seed_refs() -> None:
    projection = {
        "schema_version": NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION,
        "authority_role": "projection_only",
        "carrier_ref": "evidence-spine:self-labeled-projection",
        "concept_spine_ref": _sha("c"),
    }
    record = build_nl_replay_orchestration_continuity(
        quality_evidence={
            "public_export_bundle": {
                "semantic_audit": {
                    "runtime_orchestration_continuity": projection,
                }
            }
        },
        required_surfaces=("quality_evidence",),
        generated_at=_fixed_time(),
    )

    assert record["status"] == "fail"
    assert record["carrier_ref"] is None
    assert record["concept_spine_ref"] is None
    assert "nl_replay_orchestration_projection_on_source_surface" in {
        item["code"] for item in record["findings"]
    }


def _fixed_time() -> datetime:
    return datetime(2026, 10, 17, tzinfo=UTC)


def test_rejected_claim_registry_surface_cannot_emit_fallback_ref() -> None:
    request_sources = {
        key: value
        for key, value in _SOURCE_REF_FIXTURE.items()
        if key != "runtime_claim_registry_ref"
    }
    claim_registry_source = {
        "schema_version": "policyos.runtime.claim_registry.v1",
        "runtime_authority": {"cas_ref": "quality_evidence/claim-registry-owner.json"},
    }
    valid = build_nl_replay_orchestration_continuity(
        request_context=request_sources,
        quality_evidence=claim_registry_source,
        required_surfaces=("request_context", "quality_evidence"),
        generated_at=_fixed_time(),
    )

    assert valid["status"] == "pass"
    assert valid["runtime_claim_registry_ref"] == "quality_evidence/claim-registry-owner.json"

    rejected = build_nl_replay_orchestration_continuity(
        request_context=request_sources,
        quality_evidence={
            **claim_registry_source,
            "valid_sibling": {"carrier_ref": "evidence-spine:rejected-source-sibling"},
            "nested_projection": {
                "schema_version": PUBLIC_EXPORT_SCHEMA_VERSION,
                "authority_role": "projection_only",
                "runtime_claim_registry_ref": "quality_evidence/untrusted-projection.json",
            },
        },
        required_surfaces=("request_context", "quality_evidence"),
        generated_at=_fixed_time(),
    )

    assert rejected["status"] == "fail"
    assert rejected["runtime_claim_registry_ref"] is None
    assert "nl_replay_orchestration_projection_on_source_surface" in {
        item["code"] for item in rejected["findings"]
    }
    assert "nl_replay_orchestration_runtime_claim_registry_ref_missing" in {
        item["code"] for item in rejected["findings"]
    }
    quality_evidence_coverage = next(
        row for row in rejected["surface_coverage"] if row["surface"] == "quality_evidence"
    )
    assert quality_evidence_coverage["runtime_claim_registry_refs"] == []
    assert quality_evidence_coverage["carrier_refs"] == []


def test_observer_keeps_valid_sibling_when_nested_continuity_is_malformed() -> None:
    observer_claim_registry = {
        "schema_version": "policyos.runtime.claim_registry.v1",
        "runtime_authority": {"cas_ref": "quality_evidence/rejected-observer-registry.json"},
        "valid_sibling": {"carrier_ref": "evidence-spine:observer-valid-sibling"},
        "valid_fallback_sibling": {
            "schema_version": "policyos.runtime.claim_registry.v1",
            "runtime_authority": {
                "cas_ref": "quality_evidence/observer-valid-sibling-registry.json"
            },
        },
        "carrier_ref": {
            NL_REPLAY_ORCHESTRATION_RECORD_KEY: {
                "schema_version": NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION,
                "status": "pass",
                "carrier_ref": "evidence-spine:observer-rejected-subtree",
            }
        },
    }
    record = build_nl_replay_orchestration_continuity(
        request_context=_SOURCE_REF_FIXTURE,
        bundle_payload=observer_claim_registry,
        required_surfaces=("request_context", "bundle"),
        generated_at=_fixed_time(),
    )

    assert record["status"] == "fail"
    assert record["carrier_ref"] == _SOURCE_REF_FIXTURE["carrier_ref"]
    assert record["runtime_claim_registry_ref"] == _SOURCE_REF_FIXTURE["runtime_claim_registry_ref"]
    invalid = [
        item
        for item in record["findings"]
        if item["code"] == "nl_replay_orchestration_embedded_record_invalid"
    ]
    assert len(invalid) == 1
    assert invalid[0]["surface"] == "bundle"
    bundle_row = next(row for row in record["surface_coverage"] if row["surface"] == "bundle")
    assert bundle_row["carrier_refs"] == ["evidence-spine:observer-valid-sibling"]
    assert bundle_row["runtime_claim_registry_refs"] == [
        "quality_evidence/observer-valid-sibling-registry.json"
    ]
    assert (
        "quality_evidence/rejected-observer-registry.json"
        not in bundle_row["runtime_claim_registry_refs"]
    )
    unbound = [
        item
        for item in record["findings"]
        if item["code"] == "nl_replay_orchestration_observation_ref_unbound"
        and item["surface"] == "bundle"
        and item["field"] == "carrier_refs"
    ]
    assert len(unbound) == 1
    assert unbound[0]["refs"] == ["evidence-spine:observer-valid-sibling"]


def test_accepted_tree_reuses_canonical_ref_fallback_and_preorder() -> None:
    payload = {
        "carrier_ref": {
            "ref": "evidence-spine:carrier-selected",
            "nested": {"ref": "evidence-spine:carrier-not-selected"},
        },
        "parent_spine_ref": {
            "cas_ref": None,
            "unrecognized": {"nested": "evidence-spine:parent-fallback"},
        },
        "outer_registry": {
            "schema_version": "policyos.runtime.claim_registry.v1",
            "runtime_authority": {"cas_ref": "quality_evidence/outer-registry.json"},
            "inner_registry": {
                "schema_version": "policyos.runtime.claim_registry.v1",
                "runtime_authority": {"cas_ref": "quality_evidence/inner-registry.json"},
            },
        },
    }

    refs = _collect_surface_refs("bundle", payload, findings=[])

    assert refs["carrier_refs"] == ("evidence-spine:carrier-selected",)
    assert refs["parent_spine_refs"] == ("evidence-spine:parent-fallback",)
    # The baseline walker adds a parent registry before accepted descendants.
    assert refs["runtime_claim_registry_refs"] == ("quality_evidence/outer-registry.json",)
