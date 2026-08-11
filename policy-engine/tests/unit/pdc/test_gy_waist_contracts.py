from __future__ import annotations

import copy
import json
import re

import pytest
from pydantic import ValidationError

from polisyos.pdc import (
    ApplicabilityResult,
    ArtifactEnvelope,
    ArtifactRef,
    AuthorityBoundary,
    AuthorityDerivationTrace,
    BudgetVector,
    CertifiedOperationEnvelope,
    DecisionGrade,
    EvidenceBasis,
    EvidenceKind,
    GyComparisonAdmission,
    OperationClass,
    OperationContract,
    OperationInvocationRecord,
    PortSpec,
    PromotionObligationClass,
    PromotionRiskSpendRecord,
    PromotionRiskSpendSummary,
    SearchLedgerEvent,
    SearchTerminalKind,
    SearchTerminalState,
    VOISelectionAudit,
    WorkspaceContract,
    assert_ring2_verifier_provenance,
    build_gy_comparison_projection_plan,
    build_gy_comparison_projection_plan_from_manifest,
    gy_artifact_self_identity_projection,
    gy_comparison_content_hash,
    gy_content_hash,
    gy_recorded_content_hash,
    is_gy_content_hash_excluded_field,
    is_gy_declared_non_authority_block,
    reconcile_gy_operational_leaves,
    strip_gy_volatile_fields,
)
from polisyos.pdc._impl.gy_waist import (
    PROMOTION_RISK_CONDITIONALITY_CAVEAT,
    ArtifactEnvelopeVerification,
    GyOperationalReconciliationError,
)


def _artifact_ref(artifact_id: str = "artifact-base") -> ArtifactRef:
    return ArtifactRef.from_payload(
        artifact_id=artifact_id,
        artifact_type="BaseDataset",
        payload={"rows": [{"firm_id": 1}], "created_at": "2026-06-15T10:00:00Z"},
        schema_ref="policyos.gy.fixture.v1",
        uri=f"cas://{artifact_id}",
        version="v1",
    )


def _boundary(
    *,
    evidence_kind: EvidenceKind = "measurement",
    decision_grade: DecisionGrade = "descriptive_only",
    authoritative_for: list[str] | None = None,
    may_not_use_for: list[str] | None = None,
    evidence_basis: EvidenceBasis | None = None,
) -> AuthorityBoundary:
    return AuthorityBoundary(
        boundary_id="boundary-test",
        authoritative_for=authoritative_for or ["claim:descriptive:ua-msme"],
        may_not_use_for=may_not_use_for or ["claim:causal:ua-msme"],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=["policyos.gy.authority.v1"],
        evidence_kind=evidence_kind,
        decision_grade=decision_grade,
        evidence_basis=evidence_basis
        or EvidenceBasis(
            producer_roots=[_artifact_ref()],
            method_refs=["catalog.fetch"],
            calibration_refs=[],
            counterexamples_closed=[],
        ),
        known_limits=["estimate-port only"],
    )


def test_gy_evidence_hash_strips_volatile_time_fields() -> None:
    payload = {"value": 3, "created_at": "2026-06-15T10:00:00Z", "ms": 1}
    first = gy_content_hash(payload)
    second = gy_content_hash({"value": 3, "created_at": "2026-06-15T11:30:00Z", "ms": 999})

    assert first == second
    assert first.startswith("sha256:")
    assert (
        ArtifactRef.from_payload(
            artifact_id="artifact-hash",
            artifact_type="BaseDataset",
            payload=payload,
            schema_ref="policyos.gy.fixture.v1",
            uri="cas://artifact-hash",
            version="v1",
        ).content_hash
        == first
    )


@pytest.mark.parametrize(
    "declaration",
    [
        pytest.param("verification", id="scalar"),
        pytest.param(["verification"], id="list"),
        pytest.param(["verification", "verification"], id="repeated-list"),
    ],
)
def test_gy_comparison_predicate_recognizes_only_entirely_non_authority_declarations(
    declaration: object,
) -> None:
    block = {
        "authority_provenance": declaration,
        "deployment_identity": "run-specific",
    }

    assert is_gy_declared_non_authority_block(block)
    assert not is_gy_content_hash_excluded_field("confidence_ledger_projection")


@pytest.mark.parametrize(
    "block",
    [
        pytest.param({}, id="absent"),
        pytest.param({"authority_provenance": None}, id="null"),
        pytest.param({"authority_provenance": ""}, id="empty-scalar"),
        pytest.param({"authority_provenance": []}, id="empty-list"),
        pytest.param({"authority_provenance": {}}, id="mapping"),
        pytest.param({"authority_provenance": 42}, id="number"),
        pytest.param({"authority_provenance": [42]}, id="number-list"),
        pytest.param(
            {"authority_provenance": ["not_established"]},
            id="unrecognized",
        ),
        pytest.param(
            {"authority_provenance": ["verification", "canonical_repo"]},
            id="mixed-authority",
        ),
    ],
)
def test_gy_comparison_predicate_keeps_malformed_or_authority_blocks_governing(
    block: dict[str, object],
) -> None:
    assert not is_gy_declared_non_authority_block(block)


def _verification_semantic_projection(block: dict[str, object]) -> dict[str, object]:
    if not is_gy_declared_non_authority_block(block):
        raise ValueError("verification_declaration_invalid")
    return {
        "authority_provenance": block["authority_provenance"],
        "status": block["status"],
    }


def _verification_admission(
    block: dict[str, object],
    *,
    action: str = "project",
) -> GyComparisonAdmission:
    return GyComparisonAdmission(
        owner_rule="test.verification_receipt.v1",
        source_content_hash=gy_recorded_content_hash(block),
        projector=_verification_semantic_projection,
        action=action,  # type: ignore[arg-type]
    )


def test_gy_comparison_projection_requires_owner_admission_and_preserves_full_record() -> None:
    recorded = {
        "governing_input": {"node_ref": "node-a"},
        "confidence_ledger_projection": {
            "authority_provenance": "verification",
            "deployment_identity": "deployment-a",
            "status": "refused",
        },
    }
    replayed = {
        "governing_input": {"node_ref": "node-a"},
        "confidence_ledger_projection": {
            "authority_provenance": "verification",
            "deployment_identity": "deployment-b",
            "status": "refused",
        },
    }

    recorded_plan = build_gy_comparison_projection_plan(
        recorded,
        admissions=(_verification_admission(recorded["confidence_ledger_projection"]),),
    )
    replayed_plan = build_gy_comparison_projection_plan(
        replayed,
        admissions=(_verification_admission(replayed["confidence_ledger_projection"]),),
    )

    assert gy_content_hash(recorded) != gy_content_hash(replayed)
    assert gy_comparison_content_hash(
        recorded,
        comparison_plan=recorded_plan,
    ) == gy_comparison_content_hash(
        replayed,
        comparison_plan=replayed_plan,
    )
    assert replayed_plan.preserve_admitted_blocks(recorded, replayed) == recorded
    assert strip_gy_volatile_fields(recorded) == recorded
    assert recorded["confidence_ledger_projection"]["deployment_identity"] == "deployment-a"

    unadmitted = copy.deepcopy(replayed)
    unadmitted["confidence_ledger_projection"]["deployment_identity"] = "deployment-c"
    with pytest.raises(ValueError, match="live_admission_unbound"):
        build_gy_comparison_projection_plan(
            unadmitted,
            admissions=(_verification_admission(recorded["confidence_ledger_projection"]),),
        )

    governing_replay = {
        **replayed,
        "governing_input": {"node_ref": "node-b"},
    }
    assert gy_comparison_content_hash(
        recorded,
        comparison_plan=recorded_plan,
    ) != gy_comparison_content_hash(
        governing_replay,
        comparison_plan=replayed_plan,
    )

    mixed_authority = copy.deepcopy(recorded)
    mixed_authority["confidence_ledger_projection"]["authority_provenance"] = [
        "verification",
        "canonical_repo",
    ]
    mixed_shift = copy.deepcopy(mixed_authority)
    mixed_shift["confidence_ledger_projection"]["deployment_identity"] = "deployment-b"
    assert gy_content_hash(mixed_authority) != gy_content_hash(mixed_shift)


def test_gy_comparison_projection_excludes_admitted_non_authority_blocks_in_lists() -> None:
    payload = {
        "receipts": [
            {
                "authority_provenance": ["verification"],
                "status": "refused",
                "receipt_id": "run-specific",
            },
            {
                "authority_provenance": ["not_established"],
                "receipt_id": "governing",
            },
        ]
    }

    plan = build_gy_comparison_projection_plan(
        payload,
        admissions=(_verification_admission(payload["receipts"][0], action="exclude"),),
    )
    assert plan.project(payload) == {
        "receipts": [
            {
                "authority_provenance": ["not_established"],
                "receipt_id": "governing",
            }
        ]
    }
    assert strip_gy_volatile_fields(payload) == payload
    shifted = copy.deepcopy(payload)
    shifted["receipts"][1]["receipt_id"] = "governing-shifted"
    assert gy_comparison_content_hash(
        payload,
        comparison_plan=plan,
    ) != gy_comparison_content_hash(
        shifted,
        comparison_plan=plan,
    )
    semantic_shift = copy.deepcopy(payload)
    semantic_shift["receipts"][0]["status"] = "promoted"
    with pytest.raises(ValueError, match="admitted_block_semantic_mismatch"):
        plan.preserve_admitted_blocks(payload, semantic_shift)


def test_gy_comparison_admission_is_exact_and_does_not_cover_a_copied_block() -> None:
    block = {
        "authority_provenance": "verification",
        "deployment_identity": "deployment-a",
        "status": "refused",
    }
    payload = {"receipts": [copy.deepcopy(block), copy.deepcopy(block)]}
    plan = build_gy_comparison_projection_plan(
        payload,
        admissions=(_verification_admission(block),),
    )

    shifted = copy.deepcopy(payload)
    shifted["receipts"][1]["deployment_identity"] = "forged-copy"
    assert gy_comparison_content_hash(
        payload,
        comparison_plan=plan,
    ) != gy_comparison_content_hash(
        shifted,
        comparison_plan=plan,
    )


def test_gy_comparison_manifest_is_integrity_only_and_cannot_choose_a_new_path() -> None:
    block = {
        "authority_provenance": "verification",
        "deployment_identity": "deployment-a",
        "status": "refused",
    }
    payload = {"governing_input": {"node_ref": "node-a"}, "receipt": block}
    plan = build_gy_comparison_projection_plan(
        payload,
        admissions=(_verification_admission(block),),
    )
    reconstructed = build_gy_comparison_projection_plan_from_manifest(
        payload,
        manifest=plan.manifest,
        projector_registry={"test.verification_receipt.v1": _verification_semantic_projection},
    )
    assert reconstructed.project(payload) == plan.project(payload)

    forged_manifest = copy.deepcopy(plan.manifest)
    forged_manifest[0]["json_pointer"] = "/governing_input"
    with pytest.raises(ValueError, match="verification_declaration_invalid"):
        build_gy_comparison_projection_plan_from_manifest(
            payload,
            manifest=forged_manifest,
            projector_registry={
                "test.verification_receipt.v1": _verification_semantic_projection
            },
        )


def test_gy_artifact_projection_is_shared_by_writer_draft_and_verifier() -> None:
    draft = {"value": 3, "created_at": "2026-06-15T10:00:00Z"}
    artifact = {**draft, "content_hash": "sha256:self"}

    assert gy_artifact_self_identity_projection(draft) == {"value": 3}
    assert gy_artifact_self_identity_projection(artifact) == {"value": 3}

    with pytest.raises(ValueError, match="artifact_self_identity_ambiguous"):
        gy_artifact_self_identity_projection({**artifact, "record_hash": "sha256:other"})


def test_reconcile_gy_operational_leaves_requires_equal_semantics_and_shape() -> None:
    previous = {
        "content_hash": "sha256:one",
        "value": {"score": 1, "generated_at": "old"},
        "elapsed_ms": 10,
    }
    current = {
        "content_hash": "sha256:one",
        "value": {"score": 1, "generated_at": "new"},
        "elapsed_ms": 20,
    }

    assert reconcile_gy_operational_leaves(previous, current) == previous

    with pytest.raises(ValueError, match="semantic_projection_mismatch"):
        reconcile_gy_operational_leaves(
            previous, {**current, "value": {"score": 2, "generated_at": "new"}}
        )
    with pytest.raises(ValueError, match="shape_mismatch"):
        reconcile_gy_operational_leaves(
            previous,
            {"content_hash": "sha256:one", "value": {"score": 1}, "elapsed_ms": 20},
        )
    with pytest.raises(ValueError, match="shape_mismatch"):
        reconcile_gy_operational_leaves(
            previous,
            {**current, "added_at": "new"},
        )


def test_reconcile_gy_operational_leaves_reports_recursive_drift_without_values() -> None:
    """A recursive mismatch names safe leaf identities and operand roles."""

    expected = {
        "compiled_run": {
            "recursive_run": {
                "generated_at": "frozen-operational-secret",
                "nodes": [
                    {
                        "cycle_run": {
                            "semantic_marker": "frozen-semantic-secret",
                        }
                    }
                ],
            }
        }
    }
    replayed = {
        "compiled_run": {
            "recursive_run": {
                "generated_at": "replayed-operational-secret",
                "nodes": [
                    {
                        "cycle_run": {
                            "semantic_marker": "replayed-semantic-secret",
                        }
                    }
                ],
            }
        }
    }

    with pytest.raises(ValueError) as exc_info:
        reconcile_gy_operational_leaves(
            expected,
            replayed,
            recording_role="education",
            admission_arm="migrated",
            require_exact_match=True,
        )

    assert isinstance(exc_info.value, GyOperationalReconciliationError)
    message = str(exc_info.value)
    error_code, separator, serialized = message.partition(":")
    assert separator == ":"
    assert error_code == "gy_operational_reconciliation_semantic_projection_mismatch"
    report = json.loads(serialized)
    assert report["admission_arm"] == "migrated"
    assert report["recording_role"] == "education"
    assert report["expected_frozen"]["operand_role"] == "expected_frozen"
    assert report["live_replayed"]["operand_role"] == "live_replayed"

    leaves = {leaf["path"]: leaf for leaf in report["changed_leaves"]}
    semantic = leaves["/compiled_run/recursive_run/nodes/0/cycle_run/semantic_marker"]
    operational = leaves["/compiled_run/recursive_run/generated_at"]
    assert semantic["operational"] is False
    assert operational["operational"] is True
    for leaf in (semantic, operational):
        expected_identity = leaf["expected_frozen"]["content_identity"]
        replayed_identity = leaf["live_replayed"]["content_identity"]
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", expected_identity)
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", replayed_identity)
        assert expected_identity != replayed_identity

    for secret in (
        "frozen-operational-secret",
        "replayed-operational-secret",
        "frozen-semantic-secret",
        "replayed-semantic-secret",
    ):
        assert secret not in message


def test_reconcile_gy_operational_leaves_descends_into_added_branch() -> None:
    """A missing nested branch reports its changed leaf, not only its container."""

    expected = {"compiled_run": {"nodes": []}}
    replayed = {
        "compiled_run": {
            "nodes": [
                {
                    "payload": {
                        "metric/score": "nested-secret",
                    }
                }
            ]
        }
    }

    with pytest.raises(ValueError) as exc_info:
        reconcile_gy_operational_leaves(
            expected,
            replayed,
            require_exact_match=True,
        )

    report = json.loads(str(exc_info.value).partition(":")[2])
    leaves = {leaf["path"]: leaf for leaf in report["changed_leaves"]}
    changed = leaves["/compiled_run/nodes/0/payload/metric~1score"]
    assert changed["expected_frozen"] == {
        "content_identity": "absent",
        "presence": "absent",
        "value_type": "absent",
    }
    assert re.fullmatch(
        r"sha256:[0-9a-f]{64}",
        changed["live_replayed"]["content_identity"],
    )
    assert "nested-secret" not in str(exc_info.value)


def test_non_verifier_writer_cannot_set_ring2_field() -> None:
    payload = {
        "ref": _artifact_ref().model_dump(mode="json"),
        "payload_ref": "cas://artifact-base",
        "payload_schema_ref": "policyos.gy.fixture.v1",
        "lifecycle_state": "shadow",
        "created_by": {"kind": "agent", "id": "agent-b"},
        "producer_operation": {
            "invocation_id": "invoke-bind",
            "operation_id": "bind.worldbank",
            "operation_version": "v1",
        },
        "input_artifacts": [],
        "producer_roots": [],
        "authority_boundary": _boundary().model_dump(mode="json"),
        "obligations": [],
        "verification": {
            "latest_applicability_result": None,
            "latest_promotion_result": "promotion-pass",
        },
    }

    with pytest.raises(ValidationError, match="verifier-only"):
        ArtifactEnvelope.model_validate(payload, context={"writer_role": "agent"})

    envelope = ArtifactEnvelope.model_validate(payload, context={"writer_role": "verifier"})
    assert envelope.authority_boundary is not None


def test_ring2_consumption_boundary_rejects_constructed_bypass_fields() -> None:
    ref = _artifact_ref()
    boundary = _boundary()
    envelope = CertifiedOperationEnvelope(
        envelope_id="envelope-slice0-estimate",
        domains=["ukrainian_msme_credit"],
        posture_scopes=["governed"],
        epistemic_regime_scopes=[],
        actor_scopes=["workspace_loop"],
        method_scopes=["measurement_root_summary"],
        certified_for=["slice0_estimate_port_authority"],
        not_certified_for=["design_candidate", "grounded_admissible"],
        rule_version_ref="policyos.gy.authority.v1",
    )
    constructed_verification = ArtifactEnvelopeVerification.model_construct(
        latest_promotion_result="promotion-pass"
    )

    constructed_envelope = ArtifactEnvelope.model_construct(
        ref=ref,
        payload_ref="cas://artifact-base",
        payload_schema_ref="policyos.gy.fixture.v1",
        lifecycle_state="shadow",
        created_by={"kind": "agent", "id": "agent-b"},
        producer_operation={"operation_id": "slice0.estimate.measurement_summary"},
        authority_boundary=boundary,
        certified_operation_envelope=envelope,
        verification=constructed_verification,
    )
    constructed_port = PortSpec.model_construct(
        port_id="port-estimate",
        direction="produces",
        port_type="Estimate",
        claim_shape={},
        multiplicity={"min": 0, "max": 1},
        provided_authority=boundary,
    )
    constructed_event = SearchLedgerEvent.model_construct(
        event_id="event-authority-delta",
        workspace_id="ws-slice0",
        cycle_index=0,
        event_type="operation_finished",
        actor={"kind": "system"},
        input_artifacts=[],
        output_artifacts=[],
        authority_delta=boundary.model_dump(mode="json"),
        created_obligations=[],
        timestamp="2026-06-15T00:00:00Z",
    )

    for constructed in (
        constructed_envelope,
        constructed_verification,
        constructed_port,
        constructed_event,
    ):
        with pytest.raises(ValueError, match="Ring-2"):
            assert_ring2_verifier_provenance(
                constructed,
                context={"writer_role": "agent"},
            )

    assert_ring2_verifier_provenance(
        constructed_envelope,
        context={"writer_role": "system_verifier"},
    )


def test_ring1_contracts_are_constructible_without_ring2_authority() -> None:
    port = PortSpec(
        port_id="port-dataset",
        direction="consumes",
        port_type="Dataset",
        claim_shape={"kind": "descriptive", "subject_type": "firm", "predicate_type": "credit"},
        multiplicity={"min": 1, "max": 1},
        constraints={"jurisdiction": "UA"},
    )
    op = OperationContract(
        operation_id="slice0.bind.catalog",
        operation_version="v1",
        operation_class=OperationClass.BIND,
        consumes=[port],
        produces=[port.model_copy(update={"direction": "produces"})],
        formal_preconditions=[],
        allowed_internal_execution=["tool_call"],
        implementation_refs=[
            {"kind": "python_function", "ref": "polisyos.runtime.quality.workspace.loop"}
        ],
        cost_model={"compute": {"max_operation_invocations": 1}},
        authority_transform={"kind": "preserves", "rule_ref": "policyos.gy.authority.v1"},
        failure_modes=[],
        repair_options=[],
    )
    invocation = OperationInvocationRecord(
        invocation_id="invoke-bind",
        operation_id=op.operation_id,
        operation_version=op.operation_version,
        workspace_id="ws-slice0",
        cycle_index=0,
        selected_by={"kind": "refinement_policy", "id": "seed-trajectory"},
        input_artifacts=[],
        parameters={"schema_ref": "policyos.gy.params.v1", "value_ref": "cas://params"},
        internal_trace={"trace_kind": "deterministic", "trace_ref": "trace://bind"},
        output_artifacts=[_artifact_ref()],
        applicability_result="applicability-bind",
        budget_delta={"compute": {"operation_invocations": 1}},
        status="completed",
    )
    applicability = ApplicabilityResult(
        result_id="applicability-bind",
        invocation_id=invocation.invocation_id,
        status="applicable",
        checked_preconditions=[],
        failed_preconditions=[],
        type_errors=[],
        repair_options=[],
    )
    workspace = WorkspaceContract(
        workspace_id="ws-slice0",
        intent_ref=_artifact_ref("intent-ref"),
        scope={
            "domain": "msme_credit",
            "jurisdiction": "UA",
            "scale": "national",
            "time_horizon": "2020-2024",
            "posture": "advisory",
        },
        artifact_graph_ref="cas://graph",
        constraint_store_ref="cas://constraints",
        agenda_ref="cas://agenda",
        frontier_ref="cas://frontier",
        allowed_operations=[op.operation_id],
        budget=BudgetVector.slice0(),
    )
    event = SearchLedgerEvent(
        event_id="event-operation-finished",
        workspace_id=workspace.workspace_id,
        cycle_index=0,
        event_type="operation_finished",
        actor={"kind": "system", "id": "workspace-loop"},
        input_artifacts=[],
        output_artifacts=[_artifact_ref()],
        operation_invocation_ref=invocation.invocation_id,
        created_obligations=[],
        timestamp="2026-06-15T00:00:00Z",
    )

    assert op.operation_class is OperationClass.BIND
    assert applicability.status == "applicable"
    assert workspace.budget.compute["max_operation_invocations"] == 3
    assert event.output_artifacts[0].artifact_type == "BaseDataset"


def test_slice0_budget_vector_uses_only_minimal_cut_line_subset() -> None:
    budget = BudgetVector.slice0()
    dumped = budget.model_dump(mode="json")
    non_empty_axes = {axis for axis, value in dumped.items() if value}

    assert non_empty_axes == {"compute", "search_quality"}
    assert set(budget.compute) == {"max_operation_invocations", "max_wall_seconds", "hard"}
    assert set(budget.search_quality) == {
        "min_recall_at_known_seeds",
        "required_source_classes",
    }


def test_search_terminal_and_voi_audit_are_typed_contracts() -> None:
    terminal = SearchTerminalState(
        kind=SearchTerminalKind.ACQUISITION_REQUIRED,
        reason="Costed acquisition is required.",
        blocking_obligations=[],
        costed_plan={"missing_distribution": "local_tourism_site_traffic"},
    )
    audit = VOISelectionAudit(
        audit_id="voi-slice0",
        workspace_id="ws-slice0",
        selected_terminal=SearchTerminalKind.ACQUISITION_REQUIRED,
        candidates=[
            {
                "operation_proposal_ref": "slice0.acquire.costed_plan",
                "estimated_voi": 0.82,
                "estimated_cost": {"money": 2500, "expert_hours": 0},
                "voi_per_cost": 0.000328,
                "hard_budgets_allow": False,
            }
        ],
        selected_action_ref="slice0.acquire.costed_plan",
        continuation_allowed=False,
        decision_rule_ref="policyos.gy.anytime_exit.v1",
    )

    assert terminal["kind"] == "acquisition_required"
    assert audit.selected_terminal == SearchTerminalKind.ACQUISITION_REQUIRED
    assert audit.continuation_allowed is False

    with pytest.raises(ValidationError):
        SearchTerminalState(kind="not_a_terminal", reason="bad", blocking_obligations=[])


def test_authority_boundary_meet_uses_two_independent_axes() -> None:
    measurement_descriptive = _boundary(
        evidence_kind="measurement",
        decision_grade="descriptive_only",
        authoritative_for=["claim:descriptive"],
        may_not_use_for=["claim:causal"],
    )
    bounds_advisory = _boundary(
        evidence_kind="bounds",
        decision_grade="advisory_admissible",
        authoritative_for=["claim:descriptive", "claim:causal"],
        may_not_use_for=["claim:production"],
    )

    met = measurement_descriptive.meet(bounds_advisory, boundary_id="boundary-meet")

    assert met.authoritative_for == ["claim:descriptive"]
    assert met.may_not_use_for == ["claim:causal", "claim:production"]
    assert met.evidence_kind == "bounds"
    assert met.decision_grade == "descriptive_only"


def test_authority_boundary_enforces_calibrated_simulation_advisory_cap() -> None:
    with pytest.raises(ValidationError, match="uncalibrated simulation"):
        _boundary(
            evidence_kind="simulation",
            decision_grade="advisory_admissible",
            evidence_basis=EvidenceBasis(
                producer_roots=[_artifact_ref()],
                method_refs=["simulation.structural"],
                calibration_refs=[],
                counterexamples_closed=[],
            ),
        )

    calibrated = _boundary(
        evidence_kind="simulation",
        decision_grade="advisory_admissible",
        evidence_basis=EvidenceBasis(
            producer_roots=[_artifact_ref()],
            method_refs=["simulation.structural"],
            calibration_refs=[_artifact_ref("calibration-ref")],
            counterexamples_closed=[],
        ),
    )

    assert calibrated.evidence_kind == "simulation"
    assert calibrated.decision_grade == "advisory_admissible"


def test_ungrounded_emergent_simulation_caps_composed_program_authority() -> None:
    measurement_decision = _boundary(
        evidence_kind="measurement",
        decision_grade="decision_admissible",
        authoritative_for=["program:chapter-a"],
        may_not_use_for=["program:ungrounded-emergent"],
        evidence_basis=EvidenceBasis(
            producer_roots=[_artifact_ref()],
            method_refs=["measurement.design"],
            calibration_refs=[_artifact_ref("calibration-ref")],
            counterexamples_closed=[_artifact_ref("counterexample-closed")],
        ),
    )
    emergent_cap = _boundary(
        evidence_kind="simulation",
        decision_grade="advisory_admissible",
        authoritative_for=["program:chapter-a", "program:emergent"],
        may_not_use_for=["program:production"],
        evidence_basis=EvidenceBasis(
            producer_roots=[_artifact_ref("simulation-root")],
            method_refs=["system-dynamics.emergent-cap"],
            calibration_refs=[_artifact_ref("calibration-ref-2")],
            counterexamples_closed=[],
        ),
    )

    met = measurement_decision.meet(emergent_cap, boundary_id="boundary-emergent-cap")

    assert met.authoritative_for == ["program:chapter-a"]
    assert met.may_not_use_for == ["program:production", "program:ungrounded-emergent"]
    assert met.evidence_kind == "simulation"
    assert met.decision_grade == "advisory_admissible"


def test_authority_derivation_trace_downgrades_optimistic_transform() -> None:
    boundary = _boundary(evidence_kind="elicitation", decision_grade="unsupported")
    trace = AuthorityDerivationTrace(
        operation_invocation_id="invoke-estimate",
        output_artifact_ref=_artifact_ref("estimate-ref"),
        declared_authority_transform={
            "kind": "calibrates",
            "requested_evidence_kind": "measurement",
            "requested_decision_grade": "decision_admissible",
            "rule_ref": "policyos.gy.authority.v1",
        },
        computed_evidence_kind="elicitation",
        computed_decision_grade="unsupported",
        producer_root_classes=["llm_candidate"],
        method_classification="llm_or_expert_only",
        applicability_result_ref="applicability-estimate",
        calibration_refs=[],
        counterexamples_closed=[],
        certified_envelope_ref=None,
        unresolved_blockers=["producer_root_missing"],
        resulting_authority_boundary_ref=boundary.boundary_id,
        transform_mismatch_disposition="downgraded",
    )

    assert trace.computed_decision_grade == "unsupported"

    with pytest.raises(ValidationError, match="self-promote"):
        AuthorityDerivationTrace(
            **{
                **trace.model_dump(mode="json"),
                "computed_decision_grade": "decision_admissible",
                "transform_mismatch_disposition": "upgraded",
            }
        )


def test_authority_derivation_trace_rejects_matched_self_promotion() -> None:
    with pytest.raises(ValidationError, match="authority_transform hints cannot self-promote"):
        AuthorityDerivationTrace(
            operation_invocation_id="invoke-estimate",
            output_artifact_ref=_artifact_ref("estimate-ref"),
            declared_authority_transform={
                "kind": "calibrates",
                "requested_evidence_kind": "measurement",
                "requested_decision_grade": "decision_admissible",
                "rule_ref": "policyos.gy.authority.v1",
            },
            computed_evidence_kind="measurement",
            computed_decision_grade="descriptive_only",
            producer_root_classes=["measurement"],
            method_classification="measurement_root_summary",
            applicability_result_ref="applicability-estimate",
            calibration_refs=[],
            counterexamples_closed=[],
            certified_envelope_ref=None,
            unresolved_blockers=[],
            resulting_authority_boundary_ref="boundary-test",
            transform_mismatch_disposition="matched",
        )


@pytest.mark.parametrize(
    ("certificate_role", "claim_polarity"),
    [
        ("promotion", "false_accept"),
        ("refusal", "confident_wrong_refusal"),
        ("acquisition", "confident_wrong_refusal"),
        ("admission", "confident_wrong_admission"),
        ("promotion_conformance", "conformance_only"),
    ],
)
def test_promotion_risk_spend_record_binds_role_polarity_and_ledger_check(
    certificate_role: str,
    claim_polarity: str,
) -> None:
    payload = {
        "obligation_class": PromotionObligationClass.CALIBRATION,
        "certificate_ref": "certificate://n9/calibration",
        "instrument": "owner_verified_confidence_sequence",
        "certificate_role": certificate_role,
        "claim_polarity": claim_polarity,
        "declared_delta_spend": 0.001,
        "deterministic_proof": False,
        "n11_confidence_ledger_ref": "confidence-check:sha256:" + "1" * 64,
    }

    record = PromotionRiskSpendRecord.model_validate(payload)

    assert record.certificate_role == certificate_role
    assert record.claim_polarity == claim_polarity

    missing_ref = dict(payload)
    missing_ref.pop("n11_confidence_ledger_ref")
    with pytest.raises(ValidationError, match="n11_confidence_ledger_ref"):
        PromotionRiskSpendRecord.model_validate(missing_ref)

    with pytest.raises(ValidationError, match="n11_confidence_ledger_ref"):
        PromotionRiskSpendRecord.model_validate(
            {**payload, "n11_confidence_ledger_ref": "caller://unbound"}
        )


def test_promotion_risk_spend_record_rejects_role_polarity_mismatch() -> None:
    with pytest.raises(ValidationError, match="certificate_role_claim_polarity_mismatch"):
        PromotionRiskSpendRecord(
            obligation_class=PromotionObligationClass.CALIBRATION,
            certificate_ref="certificate://n9/calibration",
            instrument="owner_verified_confidence_sequence",
            certificate_role="promotion",
            claim_polarity="confident_wrong_admission",
            declared_delta_spend=0.001,
            deterministic_proof=False,
            n11_confidence_ledger_ref="confidence-check:sha256:" + "2" * 64,
        )


def test_promotion_risk_summary_requires_exact_conditionality_caveat() -> None:
    payload = {
        "total_declared_delta": 0.0,
        "budget_delta": 0.01,
        "within_budget": True,
        "spend_records": [],
        "caveat": PROMOTION_RISK_CONDITIONALITY_CAVEAT,
    }

    summary = PromotionRiskSpendSummary.model_validate(payload)

    assert summary.caveat == PROMOTION_RISK_CONDITIONALITY_CAVEAT
    missing = dict(payload)
    missing.pop("caveat")
    with pytest.raises(ValidationError, match="caveat"):
        PromotionRiskSpendSummary.model_validate(missing)
    with pytest.raises(ValidationError, match="promotion_risk_conditionality_caveat_mismatch"):
        PromotionRiskSpendSummary.model_validate({**payload, "caveat": "unconditional"})


def _promotion_trace_payload() -> dict[str, object]:
    return {
        "operation_invocation_id": "n9-promotion-trace",
        "output_artifact_ref": _artifact_ref("n9-promotion-output"),
        "declared_authority_transform": {
            "requested_evidence_kind": "transport",
            "requested_decision_grade": "advisory_admissible",
        },
        "computed_evidence_kind": "transport",
        "computed_decision_grade": "advisory_admissible",
        "producer_root_classes": ["deterministic_producer"],
        "method_classification": "canonical_n9_promotion_sequence",
        "applicability_result_ref": "n9://applicability/current",
        "resulting_authority_boundary_ref": "n9://boundary/current",
        "transform_mismatch_disposition": "matched",
        "promotion_sequence_ref": (
            "polisyos.runtime.quality.promotion_sequence.run_canonical_promotion_sequence"
        ),
        "gate_outcome_hash": "sha256:" + "3" * 64,
        "confidence_ledger_scope_ref": "confidence-scope://n9/design-problem",
        "confidence_ledger_head_id": "confidence-event:sha256:" + "4" * 64,
        "confidence_ledger_receipt_id": "confidence-ledger:sha256:" + "5" * 64,
        "confidence_ledger_projection_hash": "sha256:" + "6" * 64,
        "risk_spend_total": 0.001,
        "risk_budget_delta": 0.01,
    }


def test_promotion_trace_requires_current_ledger_binding() -> None:
    trace = AuthorityDerivationTrace.model_validate(_promotion_trace_payload())

    assert trace.confidence_ledger_scope_ref == "confidence-scope://n9/design-problem"
    assert trace.confidence_ledger_head_id == "confidence-event:sha256:" + "4" * 64


@pytest.mark.parametrize(
    "missing_field",
    [
        "confidence_ledger_scope_ref",
        "confidence_ledger_head_id",
        "confidence_ledger_receipt_id",
        "confidence_ledger_projection_hash",
        "risk_spend_total",
        "risk_budget_delta",
    ],
)
def test_promotion_trace_rejects_deleted_ledger_binding_field(
    missing_field: str,
) -> None:
    payload = _promotion_trace_payload()
    payload.pop(missing_field)

    with pytest.raises(
        ValidationError,
        match="promotion_trace_confidence_ledger_binding_missing",
    ):
        AuthorityDerivationTrace.model_validate(payload)


def test_promotion_trace_rejects_spend_above_bound_budget() -> None:
    payload = _promotion_trace_payload()
    payload["risk_spend_total"] = 0.02

    with pytest.raises(ValidationError, match="promotion_trace_risk_spend_exceeds_budget"):
        AuthorityDerivationTrace.model_validate(payload)
