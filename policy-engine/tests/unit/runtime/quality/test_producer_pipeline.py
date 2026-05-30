from __future__ import annotations

# ruff: noqa: S101,S106
from polisyos.runtime.quality.producer_pipeline import (
    PRODUCER_PIPELINE_SCHEMA_VERSION,
    ProducerPipelineProducer,
    build_producer_pipeline_quality_evidence_surfaces,
    merge_producer_pipeline_quality_evidence_surfaces,
    run_eight_stage_producer_pipeline,
    run_requirement_spec_producer_pipeline,
)
from polisyos.runtime.quality.semantic_binding import build_producer_spine_read_context


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _spine_context() -> dict[str, object]:
    return build_producer_spine_read_context(
        concept_spine_ref=_sha("2"),
        jurisdiction_spine_ref=_sha("6"),
        canonical_concept_refs=["concept.msme_survival_rate"],
        jurisdiction_refs=["UA"],
        unit_refs=["unit:percent"],
        period_refs=["2024-2026"],
        geography_refs=["UA"],
    )


def _claim() -> dict[str, object]:
    return {
        "claim_id": "rec_1",
        "claim_type": "recommendation",
        "claim_family": "causal",
        "claim_use": "decision_support",
        "major": True,
        "text": "Target wartime credit support to improve MSME survival.",
        "scenario_requirement_refs": [
            "req.data.msme_panel",
            "req.legal.credit_authority",
            "req.method.causal",
            "req.scholar.support",
            "req.participation.preference",
        ],
        "facet_refs": ["facet.population.msme", "facet.geography.ua"],
        "requirement_refs": [
            "req.data.msme_panel",
            "req.legal.credit_authority",
            "req.method.causal",
            "req.scholar.support",
            "req.participation.preference",
        ],
        "baseline_refs": ["baseline.status_quo"],
        "alternative_refs": ["alternative.credit_guarantee"],
        "portfolio_refs": ["portfolio.msme-survival"],
        "argument_refs": ["argument.msme-survival"],
        "warrant_refs": ["warrant.credit-targeting"],
        "rebuttal_refs": ["rebuttal.selection-bias"],
        "counter_evidence_refs": ["counterevidence.credit-crowding"],
        "limitation_refs": ["limitation.structural-scarcity"],
        "accepted_deficit_refs": ["deficit.single-quarter-panel"],
        "assumption_gate_refs": ["assumption_gate.parallel_trends"],
        "uncertainty_refs": ["uncertainty.msme-survival"],
    }


def _w6_artifacts() -> dict[str, dict[str, object]]:
    return {
        "universal_grammar_compilation": {
            "artifact_ref": "w6.grammar:wartime-msme-credit",
            "status": "pass",
        },
        "obligation_graph": {
            "graph_ref": "w6.obligation-graph:wartime-msme-credit",
            "status": "pass",
        },
        "claim_decomposition": {
            "artifact_ref": "w6.claim-decomposition:wartime-msme-credit",
            "status": "pass",
        },
    }


def _producer(
    component: str,
    *,
    requirement_ref: str,
    binding_kind: str,
    binding_id: str,
    artifact_ref: str,
    time_role: str | None = None,
) -> ProducerPipelineProducer:
    binding: dict[str, object] = {
        "binding_id": binding_id,
        "binding_kind": binding_kind,
        "disposition": "selected",
        "concept_ref": "concept.msme_survival_rate",
        "requirement_ref": requirement_ref,
        "artifact_ref": artifact_ref,
    }
    if time_role is not None:
        binding["time_role"] = time_role
    return ProducerPipelineProducer(
        producer_component=component,
        consumed_concept_refs=("concept.msme_survival_rate",),
        consumed_requirement_refs=(requirement_ref,),
        expected_output_families=(f"{component}_binding.v1",),
        first_pass_bindings=(
            {
                "binding_id": f"label.{component}.context",
                "binding_kind": "label",
                "disposition": "context_only",
                "concept_ref": "concept.msme_survival_rate",
                "label": f"{component} context label",
            },
        ),
        second_pass_bindings=(binding,),
        requested_deadline_s=5.0,
    )


def _capability_producer(
    component: str,
    *,
    requirement_ref: str,
    binding_kind: str,
    capability_ref: str,
    construct_ref: str = "construct:firm_survival",
    conflict_marker_refs: tuple[str, ...] = (),
) -> ProducerPipelineProducer:
    return ProducerPipelineProducer(
        producer_component=component,
        consumed_concept_refs=("concept:firm_survival",),
        consumed_requirement_refs=(requirement_ref,),
        expected_output_families=(f"{component}_capability_binding.v1",),
        first_pass_bindings=(
            {
                "binding_id": f"label.{component}.capability-context",
                "binding_kind": "label",
                "disposition": "context_only",
                "concept_ref": "concept:firm_survival",
                "label": f"{component} consumed capability graph refs",
            },
        ),
        second_pass_bindings=(
            {
                "binding_id": f"binding.{component}.{capability_ref.split(':', 1)[-1]}",
                "binding_kind": binding_kind,
                "disposition": "selected",
                "concept_ref": "concept:firm_survival",
                "requirement_ref": requirement_ref,
                "artifact_ref": capability_ref,
                "capability_ref": capability_ref,
                "construct_ref": construct_ref,
                "capability_index_ref": "capability-index:phase5",
                "construct_registry_ref": "construct-registry:v1",
                "authority_composition_rule_ref": "capability-authority-v1.0",
                "conflict_marker_refs": conflict_marker_refs,
            },
        ),
        requested_deadline_s=5.0,
    )


def test_eight_stage_pipeline_runs_producers_through_closeout_projection_surfaces() -> None:
    report = run_eight_stage_producer_pipeline(
        run_id="run-w7f",
        job_id="job-w7f",
        tenant_id="tenant-1",
        request_ref="request:wartime-msme-credit",
        authority_profile="production",
        scenario_refs=("scenario:public-golden-msme",),
        spine_context=_spine_context(),
        claims=(_claim(),),
        **_w6_artifacts(),
        producers=(
            _producer(
                "fabric",
                requirement_ref="req.data.msme_panel",
                binding_kind="dataset",
                binding_id="binding.fabric.msme-panel",
                artifact_ref="source.msme_panel",
                time_role="data_time",
            ),
            _producer(
                "lex",
                requirement_ref="req.legal.credit_authority",
                binding_kind="norm",
                binding_id="binding.lex.credit-norm",
                artifact_ref="norm.ua.credit_eligibility",
                time_role="legal_effective_time",
            ),
            _producer(
                "foundry",
                requirement_ref="req.method.causal",
                binding_kind="method",
                binding_id="binding.foundry.did",
                artifact_ref="method_output.did.msme_survival",
            ),
            _producer(
                "scholar",
                requirement_ref="req.scholar.support",
                binding_kind="literature",
                binding_id="binding.scholar.review",
                artifact_ref="literature:msme-survival-review",
                time_role="publication_time",
            ),
            _producer(
                "participation",
                requirement_ref="req.participation.preference",
                binding_kind="claim",
                binding_id="binding.participation.hearing",
                artifact_ref="participation.hearing.msme-owners",
            ),
        ),
    )

    assert report["schema_version"] == PRODUCER_PIPELINE_SCHEMA_VERSION
    assert report["status"] == "pass"
    assert [stage["stage_id"] for stage in report["stages"]] == [
        "run_contract_and_carrier",
        "spine_bootstrap",
        "parallel_preflight",
        "first_pass_context_blocker_emission",
        "provisional_claim_registry",
        "second_pass_authoritative_binding",
        "semantic_closure",
        "closeout_and_projection",
    ]
    assert report["producer_handshake_ledger"]["status"] == "pass"
    assert report["producer_state_summary"]["final_states"] == {
        "fabric": "emitted_binding",
        "foundry": "emitted_binding",
        "lex": "emitted_binding",
        "participation": "emitted_binding",
        "scholar": "emitted_binding",
    }
    assert report["provisional_claim_registry"]["claims"][0]["requirement_refs"] == [
        "req.data.msme_panel",
        "req.legal.credit_authority",
        "req.method.causal",
        "req.scholar.support",
        "req.participation.preference",
    ]
    assert set(report["semantic_closure"]["selected_binding_refs"]) >= {
        "binding.fabric.msme-panel",
        "binding.lex.credit-norm",
        "binding.foundry.did",
        "binding.scholar.review",
        "binding.participation.hearing",
    }
    assert report["readiness"]["status"] == "pass"
    assert report["bundle_assembly"]["files"]["quality_evidence"]["producer_pipeline"] == (
        "quality_evidence/producer_pipeline.json"
    )
    assert report["inspection"]["components"][0]["component_id"] == "producer_pipeline"
    assert report["replay"]["orchestration_continuity"]["producer_pipeline_ref"] == report[
        "producer_pipeline_ref"
    ]
    assert report["authority_boundary"]["authoritative_for"] == [
        "producer_pipeline_stage_order",
        "producer_liveness_state",
        "boundary_continuity",
    ]
    assert "producer_domain_truth" in report["authority_boundary"]["may_not_use_for"]


def test_pipeline_persists_per_producer_capability_refs_and_cross_modal_traceability(
) -> None:
    report = run_eight_stage_producer_pipeline(
        run_id="run-phase5-cross-modal",
        job_id="job-phase5-cross-modal",
        tenant_id="tenant-1",
        request_ref="request:wartime-msme-credit",
        authority_profile="production",
        scenario_refs=("scenario:ua-msme-affordable-loans-2022",),
        spine_context=_spine_context(),
        claims=(_claim(),),
        **_w6_artifacts(),
        producers=(
            _capability_producer(
                "fabric",
                requirement_ref="req.data.msme_panel",
                binding_kind="dataset",
                capability_ref="capability:firm_survival_signal__ua__wartime_2022",
            ),
            _capability_producer(
                "lex",
                requirement_ref="req.legal.credit_authority",
                binding_kind="norm",
                capability_ref="capability:lex_wartime_credit_authority",
            ),
            _capability_producer(
                "foundry",
                requirement_ref="req.method.causal",
                binding_kind="method",
                capability_ref="capability:foundry_survival_contract",
            ),
            _capability_producer(
                "scholar",
                requirement_ref="req.scholar.support",
                binding_kind="literature",
                capability_ref="capability:scholar_firm_survival_edges",
                conflict_marker_refs=("w8e-conflict:firm_survival:transport-contested",),
            ),
            _capability_producer(
                "participation",
                requirement_ref="req.participation.preference",
                binding_kind="claim",
                capability_ref="capability:participation_legitimacy_signal",
            ),
        ),
    )

    decisions = report["producer_binding_decisions"]
    assert report["status"] == "pass"
    assert {row["producer_component"] for row in decisions} >= {
        "fabric",
        "lex",
        "foundry",
        "scholar",
        "participation",
    }
    assert {row["construct_ref"] for row in decisions} == {"construct:firm_survival"}
    assert {row["capability_index_ref"] for row in decisions} == {
        "capability-index:phase5"
    }
    assert {row["construct_registry_ref"] for row in decisions} == {
        "construct-registry:v1"
    }
    assert {row["authority_composition_rule_ref"] for row in decisions} == {
        "capability-authority-v1.0"
    }
    assert report["cross_modal_consistency"]["status"] == "contested"
    assert report["cross_modal_consistency"]["conflict_marker_refs"] == [
        "w8e-conflict:firm_survival:transport-contested"
    ]


def test_pipeline_report_projects_quality_evidence_and_control_plane_surfaces() -> None:
    report = run_eight_stage_producer_pipeline(
        run_id="run-w7f-surfaces",
        job_id="job-w7f-surfaces",
        tenant_id="tenant-1",
        request_ref="request:wartime-msme-credit",
        authority_profile="production",
        scenario_refs=("scenario:public-golden-msme",),
        spine_context=_spine_context(),
        claims=(_claim(),),
        **_w6_artifacts(),
        producers=(
            _producer(
                "fabric",
                requirement_ref="req.data.msme_panel",
                binding_kind="dataset",
                binding_id="binding.fabric.msme-panel",
                artifact_ref="source.msme_panel",
                time_role="data_time",
            ),
        ),
    )

    surfaces = build_producer_pipeline_quality_evidence_surfaces(report)

    assert surfaces["producer_pipeline"]["producer_pipeline_ref"] == report[
        "producer_pipeline_ref"
    ]
    assert surfaces["producer_handshake_ledger"] == report["producer_handshake_ledger"]
    assert surfaces["producer_pipeline_readiness"] == report["readiness"]
    assert surfaces["producer_pipeline_control_plane"]["progress_patch"] == report[
        "control_plane"
    ]["progress_patch"]
    assert surfaces["producer_pipeline_replay"]["orchestration_continuity"] == report[
        "replay"
    ]["orchestration_continuity"]
    assert surfaces["producer_pipeline_bundle_assembly"] == report["bundle_assembly"]
    assert surfaces["producer_pipeline_inspection"] == report["inspection"]

    merged = merge_producer_pipeline_quality_evidence_surfaces(
        {"existing_report": {"status": "pass"}},
        report,
    )
    assert merged["existing_report"] == {"status": "pass"}
    assert merged["producer_pipeline_readiness"]["producer_pipeline_ref"] == report[
        "producer_pipeline_ref"
    ]


def test_waiting_on_peer_without_artifact_fields_and_deadline_emits_liveness_blocker() -> None:
    report = run_eight_stage_producer_pipeline(
        run_id="run-w7f-peer-blocker",
        job_id="job-w7f-peer-blocker",
        tenant_id="tenant-1",
        request_ref="request:wartime-msme-credit",
        authority_profile="production",
        spine_context=_spine_context(),
        claims=(_claim(),),
        **_w6_artifacts(),
        producers=(
            ProducerPipelineProducer(
                producer_component="foundry",
                consumed_concept_refs=("concept.msme_survival_rate",),
                consumed_requirement_refs=("req.method.causal",),
                expected_output_families=("method_selection_and_validity.v1",),
                first_pass_state="waiting_on_peer",
                first_pass_wait_conditions=({"peer_producer": "fabric"},),
                second_pass_bindings=(),
            ),
        ),
    )

    assert report["status"] == "blocked"
    assert report["producer_state_summary"]["final_states"]["foundry"] == "blocked"
    blocker = report["liveness_blockers"][0]
    assert blocker["code"] == "producer_handshake_waiting_on_peer_condition_missing"
    assert blocker["state"] == "waiting_on_peer"
    assert blocker["producer_component"] == "foundry"
    assert blocker["required_fields"] == []
    assert blocker["deadline_missing"] is True
    assert report["readiness"]["status"] == "blocked"


def test_first_pass_authority_and_llm_candidate_selected_bindings_are_blocked() -> None:
    report = run_eight_stage_producer_pipeline(
        run_id="run-w7f-firewall",
        job_id="job-w7f-firewall",
        tenant_id="tenant-1",
        request_ref="request:wartime-msme-credit",
        authority_profile="production",
        spine_context=_spine_context(),
        claims=(_claim(),),
        **_w6_artifacts(),
        producers=(
            ProducerPipelineProducer(
                producer_component="lex",
                consumed_concept_refs=("concept.msme_survival_rate",),
                consumed_requirement_refs=("req.legal.credit_authority",),
                expected_output_families=("legal_authority_and_competence.v1",),
                first_pass_bindings=(
                    {
                        "binding_id": "binding.lex.illegal-first-pass",
                        "binding_kind": "norm",
                        "disposition": "selected",
                        "concept_ref": "concept.msme_survival_rate",
                        "requirement_ref": "req.legal.credit_authority",
                        "artifact_ref": "norm.ua.credit_eligibility",
                    },
                ),
            ),
            ProducerPipelineProducer(
                producer_component="participation",
                consumed_concept_refs=("concept.msme_survival_rate",),
                consumed_requirement_refs=("req.participation.preference",),
                expected_output_families=("participation_provenance.v1",),
                first_pass_bindings=(
                    {
                        "binding_id": "label.participation.context",
                        "binding_kind": "label",
                        "disposition": "context_only",
                        "concept_ref": "concept.msme_survival_rate",
                        "label": "affected-person preference candidate",
                    },
                ),
                second_pass_bindings=(
                    {
                        "binding_id": "binding.participation.llm-preference",
                        "binding_kind": "claim",
                        "disposition": "selected",
                        "concept_ref": "concept.msme_survival_rate",
                        "requirement_ref": "req.participation.preference",
                        "artifact_ref": "llm-candidate:preference-1",
                        "source_class": "llm_candidate",
                    },
                ),
            ),
        ),
    )

    assert report["status"] == "blocked"
    assert {
        issue["code"] for issue in report["issues"]
    } >= {
        "producer_pipeline_first_pass_authority_blocked",
        "producer_pipeline_llm_candidate_authority_blocked",
    }
    assert report["producer_state_summary"]["final_states"] == {
        "lex": "blocked",
        "participation": "blocked",
    }
    assert report["provisional_claim_registry"]["claims"][0]["selected_binding_refs"] == []
    assert "claim_authority" in report["provisional_claim_registry"]["authority_boundary"][
        "may_not_use_for"
    ]


def test_spine_bootstrap_requires_w6_compilation_artifacts_before_producer_authority() -> None:
    report = run_eight_stage_producer_pipeline(
        run_id="run-w7f-missing-w6",
        job_id="job-w7f-missing-w6",
        tenant_id="tenant-1",
        request_ref="request:wartime-msme-credit",
        authority_profile="production",
        spine_context=_spine_context(),
        claims=(_claim(),),
        producers=(
            _producer(
                "fabric",
                requirement_ref="req.data.msme_panel",
                binding_kind="dataset",
                binding_id="binding.fabric.msme-panel",
                artifact_ref="source.msme_panel",
            ),
        ),
    )

    assert report["status"] == "blocked"
    assert report["stages"][1]["stage_id"] == "spine_bootstrap"
    assert report["stages"][1]["status"] == "blocked"
    assert report["producer_state_summary"]["final_states"]["fabric"] == "blocked"
    assert report["semantic_closure"]["selected_binding_refs"] == []
    assert {
        blocker["code"] for blocker in report["spine_bootstrap"]["blockers"]
    } == {
        "producer_pipeline_universal_grammar_missing",
        "producer_pipeline_obligation_graph_missing",
        "producer_pipeline_claim_decomposition_missing",
    }
    assert {
        issue["code"] for issue in report["issues"]
    } >= {
        "producer_pipeline_universal_grammar_missing",
        "producer_pipeline_obligation_graph_missing",
        "producer_pipeline_claim_decomposition_missing",
    }


def test_spine_bootstrap_rejects_blocked_w6_compilation_artifact_refs() -> None:
    artifacts = _w6_artifacts()
    artifacts["obligation_graph"] = {
        "graph_ref": "w6.obligation-graph:wartime-msme-credit",
        "status": "blocked",
        "blockers": [{"code": "obligation_graph_scope_conflict"}],
    }

    report = run_eight_stage_producer_pipeline(
        run_id="run-w7f-blocked-w6",
        job_id="job-w7f-blocked-w6",
        tenant_id="tenant-1",
        request_ref="request:wartime-msme-credit",
        authority_profile="production",
        spine_context=_spine_context(),
        claims=(_claim(),),
        producers=(
            _producer(
                "fabric",
                requirement_ref="req.data.msme_panel",
                binding_kind="dataset",
                binding_id="binding.fabric.msme-panel",
                artifact_ref="source.msme_panel",
            ),
        ),
        **artifacts,
    )

    assert report["status"] == "blocked"
    assert report["spine_bootstrap"]["status"] == "blocked"
    assert report["producer_state_summary"]["final_states"]["fabric"] == "blocked"
    assert report["semantic_closure"]["selected_binding_refs"] == []
    assert {
        blocker["code"] for blocker in report["spine_bootstrap"]["blockers"]
    } >= {"producer_pipeline_obligation_graph_blocked"}


def test_preflight_requires_declared_requirements_outputs_and_deadline() -> None:
    report = run_eight_stage_producer_pipeline(
        run_id="run-w7f-preflight",
        job_id="job-w7f-preflight",
        tenant_id="tenant-1",
        request_ref="request:wartime-msme-credit",
        authority_profile="production",
        spine_context=_spine_context(),
        claims=(_claim(),),
        **_w6_artifacts(),
        producers=(
            ProducerPipelineProducer(
                producer_component="fabric",
                consumed_concept_refs=("concept.msme_survival_rate",),
                first_pass_bindings=(
                    {
                        "binding_id": "label.fabric.context",
                        "binding_kind": "label",
                        "disposition": "context_only",
                        "concept_ref": "concept.msme_survival_rate",
                        "label": "fabric context",
                    },
                ),
                second_pass_bindings=(
                    {
                        "binding_id": "binding.fabric.msme-panel",
                        "binding_kind": "dataset",
                        "disposition": "selected",
                        "concept_ref": "concept.msme_survival_rate",
                        "requirement_ref": "req.data.msme_panel",
                        "artifact_ref": "source.msme_panel",
                    },
                ),
            ),
        ),
    )

    assert report["status"] == "blocked"
    assert report["preflight"]["status"] == "blocked"
    assert report["producer_state_summary"]["final_states"]["fabric"] == "blocked"
    issue = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "producer_pipeline_preflight_declaration_missing"
    )
    assert set(issue["missing_fields"]) == {
        "consumed_requirement_refs",
        "expected_output_families",
    }


def test_second_pass_binding_must_match_declared_compiled_requirement_spec() -> None:
    report = run_eight_stage_producer_pipeline(
        run_id="run-w7f-requirement-match",
        job_id="job-w7f-requirement-match",
        tenant_id="tenant-1",
        request_ref="request:wartime-msme-credit",
        authority_profile="production",
        spine_context=_spine_context(),
        claims=(_claim(),),
        **_w6_artifacts(),
        producers=(
            ProducerPipelineProducer(
                producer_component="fabric",
                consumed_concept_refs=("concept.msme_survival_rate",),
                consumed_requirement_refs=("req.data.msme_panel",),
                expected_output_families=("source_contract_binding.v1",),
                first_pass_bindings=(
                    {
                        "binding_id": "label.fabric.context",
                        "binding_kind": "label",
                        "disposition": "context_only",
                        "concept_ref": "concept.msme_survival_rate",
                        "label": "fabric context",
                    },
                ),
                second_pass_bindings=(
                    {
                        "binding_id": "binding.fabric.uncompiled",
                        "binding_kind": "dataset",
                        "disposition": "selected",
                        "concept_ref": "concept.msme_survival_rate",
                        "requirement_ref": "req.data.not_declared",
                        "artifact_ref": "source.msme_panel",
                    },
                ),
                requested_deadline_s=5.0,
            ),
        ),
    )

    assert report["status"] == "blocked"
    assert report["producer_state_summary"]["final_states"]["fabric"] == "blocked"
    assert {
        issue["code"] for issue in report["issues"]
    } >= {"producer_pipeline_requirement_binding_unmatched"}


def test_provisional_claim_registry_requires_facet_baseline_and_alternative_bindings() -> None:
    under_bound_claim = {
        "claim_id": "rec_1",
        "claim_type": "recommendation",
        "text": "Target wartime credit support to improve MSME survival.",
        "requirement_refs": ["req.data.msme_panel"],
    }

    report = run_eight_stage_producer_pipeline(
        run_id="run-w7f-claim-registry",
        job_id="job-w7f-claim-registry",
        tenant_id="tenant-1",
        request_ref="request:wartime-msme-credit",
        authority_profile="production",
        spine_context=_spine_context(),
        claims=(under_bound_claim,),
        **_w6_artifacts(),
        producers=(
            _producer(
                "fabric",
                requirement_ref="req.data.msme_panel",
                binding_kind="dataset",
                binding_id="binding.fabric.msme-panel",
                artifact_ref="source.msme_panel",
            ),
        ),
    )

    assert report["status"] == "blocked"
    assert report["provisional_claim_registry"]["status"] == "blocked"
    claim = report["provisional_claim_registry"]["claims"][0]
    assert set(claim["missing_binding_fields"]) == {
        "facet_refs",
        "baseline_refs",
        "alternative_refs",
    }
    assert {
        issue["code"] for issue in report["issues"]
    } >= {"producer_pipeline_claim_registry_binding_missing"}


def test_second_pass_requires_selected_rejected_or_blocked_requirement_binding() -> None:
    report = run_eight_stage_producer_pipeline(
        run_id="run-w7f-second-pass-context-only",
        job_id="job-w7f-second-pass-context-only",
        tenant_id="tenant-1",
        request_ref="request:wartime-msme-credit",
        authority_profile="production",
        spine_context=_spine_context(),
        claims=(_claim(),),
        **_w6_artifacts(),
        producers=(
            ProducerPipelineProducer(
                producer_component="fabric",
                consumed_concept_refs=("concept.msme_survival_rate",),
                consumed_requirement_refs=("req.data.msme_panel",),
                expected_output_families=("source_contract_binding.v1",),
                first_pass_bindings=(
                    {
                        "binding_id": "label.fabric.context",
                        "binding_kind": "label",
                        "disposition": "context_only",
                        "concept_ref": "concept.msme_survival_rate",
                        "label": "fabric context",
                    },
                ),
                second_pass_bindings=(
                    {
                        "binding_id": "label.fabric.second-pass-context",
                        "binding_kind": "label",
                        "disposition": "context_only",
                        "concept_ref": "concept.msme_survival_rate",
                        "label": "still only context",
                    },
                ),
                requested_deadline_s=5.0,
            ),
        ),
    )

    assert report["status"] == "blocked"
    assert report["producer_state_summary"]["final_states"]["fabric"] == "blocked"
    assert {
        issue["code"] for issue in report["issues"]
    } >= {"producer_pipeline_second_pass_authoritative_binding_missing"}


def test_requirement_pipeline_corpus_stub_mode_selects_bindings_without_production_authority(
) -> None:
    report = run_requirement_spec_producer_pipeline(
        run_id="run-corpus-stub",
        job_id="job-corpus-stub",
        tenant_id="tenant-1",
        request_ref="request:corpus-stub",
        authority_profile="production",
        spine_context=_spine_context(),
        claims=(_claim(),),
        data_requirement_specs=(
            {"requirement_id": "req.data.msme_panel", "claim_id": "rec_1"},
        ),
        legal_authority_requirement_specs=(
            {"requirement_id": "req.legal.credit_authority", "claim_id": "rec_1"},
        ),
        method_validity_requirement_specs=(
            {"requirement_id": "req.method.causal", "claim_id": "rec_1"},
        ),
        scholar_support_requirement_specs=(
            {"requirement_id": "req.scholar.support", "claim_id": "rec_1"},
        ),
        participation_provenance_requirement_specs=(
            {"requirement_id": "req.participation.preference", "claim_id": "rec_1"},
        ),
        corpus_stub_responses={
            "case_id": "ua-msme-affordable-loans-2022",
            "mode": "corpus_stub",
            "max_authority_posture": "governed-pilot",
            "fabric": {"*": "selected"},
            "lex": {"*": "selected"},
            "foundry": {"*": "selected"},
            "scholar": {"*": "selected"},
            "participation": {"*": "limited"},
        },
        **_w6_artifacts(),
    )

    assert report["status"] == "pass"
    assert report["corpus_stub"]["mode"] == "corpus_stub"
    assert report["corpus_stub"]["max_authority_posture"] == "governed-pilot"
    assert "production_closeout_authority" in report["corpus_stub"]["may_not_use_for"]
    assert report["summary"]["selected_binding_count"] >= 5
