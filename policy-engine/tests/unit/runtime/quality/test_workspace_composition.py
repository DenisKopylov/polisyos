from __future__ import annotations

from typing import Any

from polisyos.pdc import (
    ArtifactRef,
    AuthorityBoundary,
    CompositionCertificate,
    EvidenceBasis,
    FrontierSnapshot,
    PortSpec,
    SearchBudgetRecord,
    SearchCoverageRecord,
    SearchExitContract,
    SearchIncompletenessRecord,
    SearchQualityRecord,
    SearchTerminalKind,
    SearchTerminalState,
    SearchUnresolvedRecord,
    SubDesignContract,
    gy_content_hash,
)
from polisyos.runtime.quality.evidence_independence import build_evidence_independence_map
from polisyos.runtime.quality.design_axes.coupling_composition import (
    CouplingEdge,
    CouplingGraph,
    compose_subdesigns,
)
from tests._helpers.hds_quality import sha

RULE_REF = "policyos.gy.composition.test.v1"
COMPOSITION_CERTIFICATES_REF = (
    "repo://architecture/policy_design_case/"
    "layer3_gy_composition_certificates.json"
)
CLAIM_REF = "claim://program/system-effect"
P14_VERIFICATION_REF = (
    "repo://architecture/policy_design_case/layer3_gy_composition_certificates.json"
    "#p14-independent-test"
)
P14_DEPENDENT_VERIFICATION_REF = (
    "repo://architecture/policy_design_case/layer3_gy_composition_certificates.json"
    "#p14-dependent-test"
)
GROUNDING_VERIFICATION_REF = (
    "repo://architecture/policy_design_case/layer3_gy_composition_certificates.json"
    "#emergent-grounding-decision-test"
)
SIMULATION_GROUNDING_VERIFICATION_REF = (
    "repo://architecture/policy_design_case/layer3_gy_composition_certificates.json"
    "#emergent-grounding-simulation-test"
)


def _artifact_ref(artifact_id: str) -> ArtifactRef:
    return ArtifactRef.from_payload(
        artifact_id=artifact_id,
        artifact_type="MeasurementRoot",
        payload={"artifact_id": artifact_id},
        schema_ref="policyos.gy.test.v1",
        uri=f"cas://{artifact_id}",
        version="v1",
    )


def _authority(
    boundary_id: str,
    *,
    authoritative_for: list[str] | None = None,
    evidence_kind: str = "measurement",
    decision_grade: str = "decision_admissible",
    calibration_refs: list[str] | None = None,
) -> AuthorityBoundary:
    return AuthorityBoundary(
        boundary_id=boundary_id,
        authoritative_for=authoritative_for or ["policy_program_claim"],
        may_not_use_for=["production_claim_authority_without_composition"],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[RULE_REF],
        evidence_kind=evidence_kind,  # type: ignore[arg-type]
        decision_grade=decision_grade,  # type: ignore[arg-type]
        evidence_basis=EvidenceBasis(
            producer_roots=[_artifact_ref(f"root-{boundary_id}")],
            method_refs=["measurement.root"],
            calibration_refs=calibration_refs or ["calibration://test"],
            counterexamples_closed=["counterexample://closed"],
        ),
    )


def _search_exit(workspace_id: str, boundary: AuthorityBoundary) -> SearchExitContract:
    artifact = _artifact_ref(f"estimate-{workspace_id}")
    return SearchExitContract(
        exit_id=f"exit-{workspace_id}",
        workspace_id=workspace_id,
        cycle_index=1,
        terminal_state=SearchTerminalState(
            kind=SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE,
            reason="test child workspace grounded a port",
            blocking_obligations=[],
        ),
        frontier_snapshot=FrontierSnapshot(
            snapshot_id=f"frontier-{workspace_id}",
            workspace_id=workspace_id,
            cycle_index=1,
            promoted_candidates=[artifact],
            shadow_candidates=[],
            rejected_candidates=[],
            dominated_candidates=[],
            current_best=[artifact],
            frontier_metrics={"candidate_count": 1},
        ),
        incompleteness_record=SearchIncompletenessRecord(
            record_id=f"incomplete-{workspace_id}",
            workspace_id=workspace_id,
            coverage=SearchCoverageRecord(
                operations_attempted=["VERIFY"],
                source_classes_checked=["official"],
            ),
            search_quality=SearchQualityRecord(
                recall_at_known_seeds=1.0,
                freshness_ok=True,
            ),
            unresolved=SearchUnresolvedRecord(),
            budget=SearchBudgetRecord(consumed={}, remaining={}, exhausted=[]),
            next_best_actions=[],
            ceiling_classification="domain_ceiling",
        ),
        budget_ledger={"consumed": {}, "remaining": {}},
        output_artifacts=[artifact],
        authority_boundary=boundary,
        next_best_actions=[],
    )


def _subdesign(
    subdesign_id: str,
    *,
    boundary: AuthorityBoundary | None = None,
    required: bool = False,
    trace_ref: str | None = None,
) -> SubDesignContract:
    authority = boundary or _authority(f"boundary-{subdesign_id}")
    port = PortSpec.model_validate(
        {
            "port_id": f"port-{subdesign_id}",
            "direction": "provides",
            "port_type": "Estimate",
            "claim_shape": {"claim_type": "policy_program_claim"},
            "multiplicity": {"min": 1, "max": 1},
            "provided_authority": authority.model_dump(mode="json"),
        },
        context={"writer_role": "system_verifier"},
    )
    terminal = (
        SearchTerminalState(
            kind=SearchTerminalKind.ACQUISITION_REQUIRED,
            reason="child requires acquisition",
            blocking_obligations=[],
        )
        if required
        else _search_exit(f"ws-{subdesign_id}", authority).terminal_state
    )
    search_exit = (
        _search_exit(f"ws-{subdesign_id}", authority).model_copy(
            update={"terminal_state": terminal}
        )
        if required
        else _search_exit(f"ws-{subdesign_id}", authority)
    )
    return SubDesignContract(
        subdesign_id=subdesign_id,
        workspace_id=f"ws-{subdesign_id}",
        parent_workspace_id="ws-parent",
        scope={
            "domain": "energy",
            "jurisdiction": "PL",
            "scale": "chapter",
            "time_horizon": "2026",
            "posture": "advisory",
        },
        provides=[port],
        requires=[],
        coupling_declarations=[],
        producer_roots=[_artifact_ref(f"root-{subdesign_id}")],
        search_exit=search_exit,
        unresolved_obligations=[],
        internal_trace_ref=trace_ref
        or f"{COMPOSITION_CERTIFICATES_REF}#subdesign-ws-parent-{subdesign_id}",
    )


def _coupling_graph(
    graph_id: str,
    *,
    edges: tuple[CouplingEdge, ...] = (),
    evidence_state: str = "observed",
) -> CouplingGraph:
    return CouplingGraph(
        graph_id=f"graph-{graph_id}",
        graph_ref=f"pdc://composition/{graph_id}/graph",
        design_ref=f"pdc://composition/{graph_id}/design",
        module_refs=["ws-chapter-a", "ws-chapter-b"],
        module_discovery_ref=f"pdc://composition/{graph_id}/module-discovery",
        interaction_edges=list(edges),
        evidence_state=evidence_state,  # type: ignore[arg-type]
        rule_version_ref=RULE_REF,
    )


def _claim(
    *,
    grounding_authority: AuthorityBoundary | None,
    required_grounding: list[str] | None = None,
    independence_map: dict[str, Any] | None = None,
    grounding_ref: str = GROUNDING_VERIFICATION_REF,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "claim_ref": CLAIM_REF,
        "required_grounding": required_grounding or ["system_dynamics"],
        "grounding_refs": [grounding_ref] if grounding_authority else [],
    }
    if grounding_authority is not None:
        payload["grounding_authority"] = grounding_authority.model_dump(mode="json")
    if independence_map is not None:
        payload["independence_map"] = independence_map
    return payload


def _independent_evidence_lines() -> list[dict[str, Any]]:
    lines = []
    for index in range(2):
        line = _evidence_line(index=index)
        line["source_lineage"] = {
            "source_id": f"source-{index}",
            "source_ref": sha(f"source-{index}"),
            "lineage_refs": [sha(f"lineage-{index}")],
            "corpus_id": f"corpus-{index}",
            "corpus_ancestry": [f"corpus-{index}"],
        }
        line["corpus_ancestry"] = [f"corpus-{index}"]
        line["author_pool"] = [f"author-{index}"]
        line["institution_pool"] = [f"institution-{index}"]
        line["preprocessing_pipeline_id"] = f"preprocessing-{index}"
        line["method_id"] = f"foundry.method.{index}"
        line["method_assumptions"] = [f"assumption-{index}"]
        line["identification_strategy_id"] = f"identification-{index}"
        line["shared_failure_modes"] = [f"failure-mode-{index}"]
        lines.append(line)
    return lines


def _independent_evidence_map(map_id: str) -> dict[str, Any]:
    lines = _independent_evidence_lines()
    return build_evidence_independence_map(
        lines,
        portfolio_designs=[_portfolio_design()],
        map_id=map_id,
        producer_execution_started_at="2026-06-21T00:00:00+00:00",
    )


def _bound_independence_map(
    map_id: str,
    *,
    lines: list[dict[str, Any]] | None = None,
    verification_ref: str = P14_VERIFICATION_REF,
) -> dict[str, Any]:
    source_lines = lines or _independent_evidence_lines()
    independence_map = build_evidence_independence_map(
        source_lines,
        portfolio_designs=[_portfolio_design()],
        map_id=map_id,
        producer_execution_started_at="2026-06-21T00:00:00+00:00",
    )
    line_ids = sorted(
        {
            str(line_id)
            for cluster in independence_map["collapse_clusters"]
            for line_id in cluster["line_ids"]
        }
    )
    lineage_refs = sorted(
        {
            str(cluster["collapse_dimensions"]["source_lineage_cluster_id"])
            for cluster in independence_map["collapse_clusters"]
        }
    )
    lineage_records = [line["source_lineage"] for line in source_lines]
    independence_map["composition_binding"] = {
        "verification_ref": verification_ref,
        "claim_refs": [CLAIM_REF],
        "subdesign_refs": ["chapter-a", "chapter-b"],
        "producer_root_refs": ["root-chapter-a", "root-chapter-b"],
        "producer_root_content_hashes": [
            _artifact_ref("root-chapter-a").content_hash,
            _artifact_ref("root-chapter-b").content_hash,
        ],
        "evidence_line_ids": line_ids,
        "lineage_refs": lineage_refs,
        "evidence_line_records": source_lines,
        "lineage_records": lineage_records,
        "evidence_line_content_hashes": [gy_content_hash(line) for line in source_lines],
        "lineage_content_hashes": [gy_content_hash(lineage) for lineage in lineage_records],
    }
    return independence_map


def test_independent_chapters_compose_through_ports_with_certificate() -> None:
    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[],
        graph=_coupling_graph("independent"),
        parent_workspace_id="ws-parent",
    )

    assert isinstance(certificate, CompositionCertificate)
    assert certificate.verdict == "composable"
    assert certificate.composition_receipt_ref
    assert certificate.coupling_gate["verdict"] == "valid"
    assert {flow["from_port"] for flow in certificate.authority_flow} == {
        "port-chapter-a",
        "port-chapter-b",
    }


def test_in_memory_subdesign_port_authority_pseudo_ref_fails_closed() -> None:
    certificate = compose_subdesigns(
        subdesigns=[
            _subdesign(
                "chapter-a",
                trace_ref="subdesign://chapter-a/ports/port-chapter-a/provided-authority",
            ),
            _subdesign(
                "chapter-b",
                trace_ref="subdesign://chapter-b/ports/port-chapter-b/provided-authority",
            ),
        ],
        claims=[],
        graph=_coupling_graph("pseudo-ref-authority"),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert "authority_evidence_unverified" in {
        obligation.obligation_type for obligation in certificate.unresolved_obligations
    }


def test_feedback_composition_is_invalid_and_requires_joint_grounding() -> None:
    edge = CouplingEdge(
        boundary_ref="boundary://feedback",
        source_module_ref="ws-chapter-a",
        target_module_ref="ws-chapter-b",
        relation="demand_supply_feedback",
        interaction_strength="strong",
        feedback_intensity="high",
        feedback=True,
        evidence_ref="evidence://feedback",
    )
    back_edge = CouplingEdge(
        boundary_ref="boundary://feedback",
        source_module_ref="ws-chapter-b",
        target_module_ref="ws-chapter-a",
        relation="take_up_response",
        interaction_strength="strong",
        feedback_intensity="none",
        feedback=False,
        evidence_ref="evidence://feedback/back-edge",
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[],
        graph=_coupling_graph("feedback", edges=(edge, back_edge)),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.coupling_gate["verdict"] == "requires_system_dynamics"
    assert certificate.coupling_gate["invalid_reason"] == "feedback_requires_joint_grounding"
    assert certificate.coupling_gate["system_dynamics_requirement_ref"]
    assert certificate.authority_flow == []
    assert "warning" not in str(certificate.model_dump(mode="json")).lower()


def test_feedback_edge_without_consistency_evidence_cannot_be_laundered_by_name() -> None:
    edge = CouplingEdge(
        boundary_ref="boundary://feedback-spoof",
        source_module_ref="ws-chapter-a",
        target_module_ref="ws-chapter-b",
        relation="behavioral_adjustment",
        interaction_strength="none",
        feedback_intensity="none",
        feedback=False,
        evidence_ref="evidence://feedback-spoof",
        independence_consistency_ref="bogus://not-resolved",
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[],
        graph=_coupling_graph("feedback-spoof", edges=(edge,)),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.coupling_gate["verdict"] == "invalid"
    assert certificate.coupling_gate["invalid_reason"] == "unknown_coupling_requires_discovery"
    assert certificate.authority_flow == []


def test_feedback_word_in_verified_independent_edge_does_not_overblock() -> None:
    edge = CouplingEdge(
        boundary_ref="boundary://independent-survey",
        source_module_ref="ws-chapter-a",
        target_module_ref="ws-chapter-b",
        relation="independent_feedback_survey",
        interaction_strength="none",
        feedback_intensity="none",
        feedback=False,
        evidence_ref="evidence://independent-survey",
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[],
        graph=_coupling_graph("independent-survey", edges=(edge,)),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "composable"
    assert certificate.coupling_gate["verdict"] == "valid"
    assert len(certificate.authority_flow) == 1


def test_bogus_independence_consistency_ref_fails_closed() -> None:
    edge = CouplingEdge(
        boundary_ref="boundary://bogus-consistency",
        source_module_ref="ws-chapter-a",
        target_module_ref="ws-chapter-b",
        relation="observed_independent_measurement",
        interaction_strength="none",
        feedback_intensity="none",
        feedback=False,
        evidence_ref="evidence://bogus-consistency",
        independence_consistency_ref="repo://architecture/policy_design_case/not-real.json#edge",
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[],
        graph=_coupling_graph("bogus-consistency", edges=(edge,)),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert certificate.coupling_gate.invalid_reason == "unknown_coupling_requires_discovery"


def test_mismatched_independence_consistency_ref_fails_closed() -> None:
    edge = CouplingEdge(
        boundary_ref="boundary://mismatched-consistency",
        source_module_ref="ws-chapter-a",
        target_module_ref="ws-chapter-b",
        relation="observed_independent_measurement",
        interaction_strength="none",
        feedback_intensity="none",
        feedback=False,
        evidence_ref="evidence://mismatched-consistency",
        independence_consistency_ref=(
            "repo://architecture/policy_design_case/layer3_gy_composition_certificates.json"
            "#independence-consistency-other-edge"
        ),
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[],
        graph=_coupling_graph("mismatched-consistency", edges=(edge,)),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert certificate.coupling_gate.invalid_reason == "unknown_coupling_requires_discovery"


def test_producer_self_stamped_independence_consistency_ref_fails_closed() -> None:
    edge = CouplingEdge(
        boundary_ref="boundary://self-stamped-consistency",
        source_module_ref="ws-chapter-a",
        target_module_ref="ws-chapter-b",
        relation="observed_independent_measurement",
        interaction_strength="none",
        feedback_intensity="none",
        feedback=False,
        evidence_ref="fixture://layer2/s5/self-stamped",
        independence_consistency_ref="fixture://layer2/s5/self-stamped#independence-consistency",
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[],
        graph=_coupling_graph("self-stamped-consistency", edges=(edge,)),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert certificate.coupling_gate.invalid_reason == "unknown_coupling_requires_discovery"


def test_graph_back_edge_is_feedback_regardless_of_ref_or_flags() -> None:
    forward = CouplingEdge(
        boundary_ref="boundary://graph-feedback",
        source_module_ref="ws-chapter-a",
        target_module_ref="ws-chapter-b",
        relation="downstream_response",
        interaction_strength="strong",
        feedback_intensity="none",
        feedback=False,
        evidence_ref="evidence://graph-feedback/forward",
        independence_consistency_ref=(
            "repo://architecture/policy_design_case/layer3_gy_composition_certificates.json"
            "#independence-consistency-other-edge"
        ),
    )
    back = CouplingEdge(
        boundary_ref="boundary://graph-feedback",
        source_module_ref="ws-chapter-b",
        target_module_ref="ws-chapter-a",
        relation="behavioral_adjustment",
        interaction_strength="strong",
        feedback_intensity="none",
        feedback=False,
        evidence_ref="evidence://graph-feedback/back",
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[],
        graph=_coupling_graph("graph-feedback", edges=(forward, back)),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.coupling_gate.verdict == "requires_system_dynamics"
    assert certificate.coupling_gate.invalid_reason == "feedback_requires_joint_grounding"
    assert certificate.authority_flow == []


def test_emergent_claim_is_capped_to_own_grounding_not_inherited_from_parts() -> None:
    grounding = _authority(
        "boundary-system-model",
        evidence_kind="simulation",
        decision_grade="advisory_admissible",
        calibration_refs=["calibration://system-model"],
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[
            _claim(
                grounding_authority=grounding,
                independence_map=_bound_independence_map("composition-emergent-map"),
                grounding_ref=SIMULATION_GROUNDING_VERIFICATION_REF,
            )
        ],
        graph=_coupling_graph("emergent"),
        parent_workspace_id="ws-parent",
    )

    emergent = certificate.emergent_claims[0]
    assert emergent["grounding_status"] == "simulation_only"
    assert emergent["resulting_authority"]["evidence_kind"] == "simulation"
    assert emergent["resulting_authority"]["decision_grade"] == "advisory_admissible"


def test_missing_p14_independence_map_blocks_emergent_support_inflation() -> None:
    grounding = _authority(
        "boundary-no-p14",
        evidence_kind="measurement",
        decision_grade="decision_admissible",
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[_claim(grounding_authority=grounding)],
        graph=_coupling_graph("missing-p14-map"),
        parent_workspace_id="ws-parent",
    )

    emergent = certificate.emergent_claims[0]
    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert emergent["grounding_status"] == "invalid"
    assert emergent["resulting_authority"] is None
    assert "p14_independence_map_missing" in {
        obligation.obligation_type for obligation in certificate.unresolved_obligations
    }


def test_missing_emergent_grounding_fails_closed() -> None:
    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[_claim(grounding_authority=None)],
        graph=_coupling_graph("missing-grounding"),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert certificate.emergent_claims[0]["grounding_status"] == "missing"
    assert certificate.emergent_claims[0]["resulting_authority"] is None
    assert "emergent_grounding_missing" in {
        obligation.obligation_type for obligation in certificate.unresolved_obligations
    }


def test_inline_emergent_grounding_fake_ref_fails_closed() -> None:
    grounding = _authority(
        "boundary-inline-fake-grounding",
        evidence_kind="measurement",
        decision_grade="decision_admissible",
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[
            _claim(
                grounding_authority=grounding,
                grounding_ref="repo://not-registered/system-model.json#fake",
                independence_map=_bound_independence_map("composition-inline-fake-map"),
            )
        ],
        graph=_coupling_graph("inline-fake-grounding"),
        parent_workspace_id="ws-parent",
    )

    emergent = certificate.emergent_claims[0]
    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert emergent["grounding_status"] == "unresolved"
    assert emergent["resulting_authority"] is None
    assert "emergent_grounding_unresolved" in {
        obligation.obligation_type for obligation in certificate.unresolved_obligations
    }


def test_non_independent_evidence_count_collapses_before_support_can_compose() -> None:
    lines = [_evidence_line(index=0), _evidence_line(index=1)]
    independence_map = _bound_independence_map(
        "composition-independence-map",
        lines=lines,
        verification_ref=P14_DEPENDENT_VERIFICATION_REF,
    )
    grounding = _authority(
        "boundary-non-independent",
        evidence_kind="measurement",
        decision_grade="decision_admissible",
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[_claim(grounding_authority=grounding, independence_map=independence_map)],
        graph=_coupling_graph("p14"),
        parent_workspace_id="ws-parent",
    )

    emergent = certificate.emergent_claims[0]
    assert emergent["effective_independent_evidence_count"] == 1
    assert emergent["raw_evidence_line_count"] == 2
    assert emergent["resulting_authority"]["decision_grade"] == "advisory_admissible"
    assert "dependent_evidence_collapsed" in emergent["limiting_deficits"]


def test_independent_evidence_count_remains_raw_when_sources_are_distinct() -> None:
    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[
            _claim(
                grounding_authority=_authority("boundary-independent-evidence"),
                independence_map=_bound_independence_map("composition-independent-map"),
            )
        ],
        graph=_coupling_graph("p14-independent"),
        parent_workspace_id="ws-parent",
    )

    emergent = certificate.emergent_claims[0]
    assert emergent["effective_independent_evidence_count"] == 2
    assert emergent["raw_evidence_line_count"] == 2
    assert emergent["limiting_deficits"] == []


def test_unbound_valid_p14_map_does_not_support_composed_claim() -> None:
    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[
            _claim(
                grounding_authority=_authority("boundary-unbound-evidence"),
                independence_map=_independent_evidence_map("composition-unbound-map"),
            )
        ],
        graph=_coupling_graph("p14-unbound"),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert certificate.emergent_claims[0]["resulting_authority"] is None
    assert "p14_independence_map_unbound" in {
        obligation.obligation_type for obligation in certificate.unresolved_obligations
    }


def test_fabricated_p14_binding_records_do_not_support_composed_claim() -> None:
    independence_map = _bound_independence_map("composition-fabricated-map")
    binding = independence_map["composition_binding"]
    binding["evidence_line_records"] = [
        {
            "line_id": "fabricated-line",
            "claim_id": CLAIM_REF,
            "source_lineage": {"source_id": "fabricated"},
        }
    ]
    binding["lineage_records"] = [{"source_id": "fabricated"}]
    binding["evidence_line_content_hashes"] = [gy_content_hash(binding["evidence_line_records"][0])]
    binding["lineage_content_hashes"] = [gy_content_hash(binding["lineage_records"][0])]

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[
            _claim(
                grounding_authority=_authority("boundary-fabricated-evidence"),
                independence_map=independence_map,
            )
        ],
        graph=_coupling_graph("p14-fabricated"),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert certificate.emergent_claims[0].resulting_authority is None
    assert "p14_independence_map_unbound" in {
        obligation.obligation_type for obligation in certificate.unresolved_obligations
    }


def test_unknown_coupling_fails_closed_instead_of_composing() -> None:
    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[],
        graph=_coupling_graph("unknown", evidence_state="candidate"),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.coupling_gate["verdict"] == "invalid"
    assert certificate.coupling_gate["invalid_reason"] == "unknown_coupling_requires_discovery"
    assert certificate.authority_flow == []


def test_empty_authoritative_for_after_port_meet_fails_closed() -> None:
    edge = CouplingEdge(
        boundary_ref="boundary://sequential",
        source_module_ref="ws-chapter-a",
        target_module_ref="ws-chapter-b",
        relation="upstream_caps_downstream",
        interaction_strength="strong",
        feedback_intensity="none",
        feedback=False,
        evidence_ref="evidence://sequential",
    )
    chapter_a = _subdesign(
        "chapter-a",
        boundary=_authority("boundary-a", authoritative_for=["chapter_a_only"]),
        trace_ref=f"{COMPOSITION_CERTIFICATES_REF}#subdesign-ws-parent-chapter-a-empty-meet",
    )
    chapter_b = _subdesign(
        "chapter-b",
        boundary=_authority("boundary-b", authoritative_for=["chapter_b_only"]),
        trace_ref=f"{COMPOSITION_CERTIFICATES_REF}#subdesign-ws-parent-chapter-b-empty-meet",
    )

    certificate = compose_subdesigns(
        subdesigns=[chapter_a, chapter_b],
        claims=[],
        graph=_coupling_graph("empty-meet", edges=(edge,)),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert "empty_authoritative_for" in {
        obligation.obligation_type for obligation in certificate.unresolved_obligations
    }


def test_shared_resource_declares_capacity_aggregation_out_of_scope() -> None:
    edge = CouplingEdge(
        boundary_ref="boundary://shared-capacity",
        source_module_ref="ws-chapter-a",
        target_module_ref="ws-chapter-b",
        relation="shared_resource_budget",
        interaction_strength="strong",
        feedback_intensity="none",
        feedback=False,
        evidence_ref="evidence://shared-capacity",
    )

    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a"), _subdesign("chapter-b")],
        claims=[],
        graph=_coupling_graph("shared-capacity", edges=(edge,)),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.coupling_gate["verdict"] == "requires_capacity_aggregation"
    assert certificate.unresolved_obligations[0].obligation_type == (
        "capacity_aggregation_required"
    )
    assert certificate.unresolved_obligations[0].resolution_options[0][
        "capability_state"
    ] == "surface_out_of_scope"
    assert certificate.unresolved_obligations[0].resolution_options[0][
        "follow_on_owner"
    ] == "team-runtime-quality:capacity-aggregation"


def test_child_acquisition_strips_all_composed_authority() -> None:
    certificate = compose_subdesigns(
        subdesigns=[_subdesign("chapter-a", required=True), _subdesign("chapter-b")],
        claims=[
            _claim(
                grounding_authority=_authority("boundary-child-acquisition"),
                independence_map=_bound_independence_map("composition-child-acquisition-map"),
            )
        ],
        graph=_coupling_graph("child-acquisition"),
        parent_workspace_id="ws-parent",
    )

    assert certificate.verdict == "not_composable"
    assert certificate.authority_flow == []
    assert certificate.emergent_claims[0].resulting_authority is None
    assert "child_acquisition_required" in {
        obligation.obligation_type for obligation in certificate.unresolved_obligations
    }


def _portfolio_design() -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_portfolio_design.v1",
        "portfolio_id": "portfolio-composition",
        "claim_ids": [CLAIM_REF],
        "predeclared": True,
        "declared_at": "2026-06-20T00:00:00+00:00",
        "declared_before_producer_execution": True,
        "authority_level": "production",
        "strands": [
            {
                "strand_id": "composition-grounding",
                "claim_id": CLAIM_REF,
                "authority_level": "production",
                "candidate_data_source_families": ["shared-admin"],
                "candidate_method_families": ["shared-method"],
                "defensible_specification_space": {"primary_estimand": "ATE"},
                "inclusion_rules": ["Include shared lineage test evidence."],
                "exclusion_rules": ["Exclude ungrounded claims."],
                "disconfirming_lines": [
                    {"line_id": "placebo-shared-lineage", "required": True}
                ],
                "synthesis_rules": {"strategy": "collapse_dependent_lines"},
                "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
                "cost_proportionality": {"budget_tier": "test"},
            }
        ],
        "candidate_data_source_families": ["shared-admin"],
        "candidate_method_families": ["shared-method"],
        "inclusion_rules": ["Include shared lineage test evidence."],
        "exclusion_rules": ["Exclude ungrounded claims."],
        "disconfirming_lines": ["placebo-shared-lineage"],
        "synthesis_rules": {"strategy": "collapse_dependent_lines"},
        "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
        "cost_proportionality": {"budget_tier": "test"},
        "cas_ref": sha("composition-portfolio"),
        "runtime_event_ref": sha("composition-runtime-event"),
    }


def _evidence_line(*, index: int) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_line.v1",
        "line_id": f"composition-line-{index}",
        "portfolio_id": "portfolio-composition",
        "portfolio_strand_id": "composition-grounding",
        "claim_id": CLAIM_REF,
        "evidence_strand": "data",
        "source_lineage": {
            "source_id": "shared-admin-source",
            "source_ref": sha("shared-admin-source"),
            "lineage_refs": [sha("shared-lineage")],
            "corpus_id": "shared-corpus",
            "corpus_ancestry": ["shared-corpus"],
        },
        "corpus_ancestry": ["shared-corpus"],
        "author_pool": ["same-analysis-cell"],
        "institution_pool": ["same-policy-lab"],
        "preprocessing_pipeline_id": "same-preprocessing",
        "method_id": "foundry.shared.method",
        "method_assumptions": ["same assumptions"],
        "identification_strategy_id": "same-identification",
        "shared_failure_modes": ["same-bias"],
        "specification_id": f"shared-spec-{index}",
        "producer_identity": {
            "component": "polisyos.foundry.methods.causal",
            "version": "test",
            "owner": "team-runtime-quality",
        },
        "execution_context": {
            "run_id": "run-composition",
            "job_id": f"job-composition-{index}",
            "tenant_id": "tenant-test",
            "trace_id": f"trace-composition-{index}",
        },
        "evidence_ref": sha(f"composition-evidence-{index}"),
        "runtime_event_ref": sha(f"composition-event-{index}"),
    }
