"""DS9 consumes the canonical acquisition pre-human source, not a reason marker."""

from __future__ import annotations

import pytest

from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services import human_decision_contracts as contracts
from polisyos.runtime.http.services.human_decisions import _pa2_packet_join_issues
from polisyos.runtime.quality import agent_action_authority as authority
from tests.unit.runtime.quality import test_agent_action_authority as fixtures


def _source_case(tmp_path, monkeypatch, *, acquisition=True, action_kind=None, permission=None):
    monkeypatch.setattr(authority, "_utcnow", lambda: fixtures.NOW)
    harness = fixtures._harness(tmp_path)
    if action_kind is not None:
        kind = action_kind
    elif acquisition:
        kind = authority.ACQUISITION_ACTION_KIND
    else:
        kind = "search"
    operation_id = kind if acquisition else "agent.outside-envelope"
    envelope_operation_id = kind if acquisition else "agent.search"
    operation = fixtures._operation(operation_id)
    invocation = fixtures._invocation(operation)
    if permission is None:
        if kind == authority.MODEL_INPUT_USE_ACTION_KIND:
            permission = RuntimePermission.RUNS_LAUNCH
        elif acquisition:
            permission = RuntimePermission.EVIDENCE_ACQUIRE
        else:
            permission = RuntimePermission.KNOWLEDGE_SEARCH
    envelope = fixtures._envelope(
        action_kind=kind,
        operation_id=envelope_operation_id,
        permission=permission,
    )
    contract = fixtures._contract(envelope)
    proof = fixtures._proof(permission)
    intent = authority.AgentActionIntent(action_kind=kind)
    effects = []
    binding = fixtures._binding(operation, effects, action_kind=kind)
    gateway, ref, _ = fixtures._prepare_gateway(
        harness,
        contract=contract,
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        bound_permission=proof,
    )
    with authority.agent_action_authority_scope(gateway):
        source = authority.produce_agent_action_authority_decision(
            bound_permission=proof, operation=operation, invocation=invocation, intent=intent
        )
        receipt = gateway.persist_decision(source)
    source = gateway.load_persisted_decision(str(receipt.write_result.cas_ref.artifact_id)).decision
    assert source.outcome == "refused"
    request = source.human_decision_request
    common = {
        "tenant_id": "tenant-a",
        "run_id": "run-gy-pa2",
        "verifier_epoch": "fixture-epoch",
        "valid_from": envelope.valid_from,
        "valid_until": envelope.valid_until,
        "rule_version_ref": fixtures.RULE_VERSION_REF,
        "issued_at": envelope.valid_from,
    }
    principal = contracts.HumanDecisionPrincipalBinding(
        binding_id="principal",
        binding_ref="identity://principal",
        principal_issuer="institution://identity",
        principal_audience="polisyos-runtime",
        principal_subject="reviewer",
        actor_ref=fixtures.MANDATE_OWNER_REF,
        actor_key_id=harness.owner_signer.key_id,
        decision_roles=(request.required_role,),
        permissions=(RuntimePermission.RUNS_HUMAN_DECISIONS_CREATE.value,),
        authority_boundary=fixtures._boundary(
            authoritative_for="human_decision_principal_binding", source="human_governance"
        ),
        **common,
    )
    separation = contracts.ReviewerSeparationCredential(
        credential_id="separation",
        credential_ref="institution://separation",
        case_id=request.case_id,
        decision_request_ref=request.request_ref,
        decision_request_digest=authority.agent_action_content_hash(request),
        reviewer_actor_ref=fixtures.MANDATE_OWNER_REF,
        reviewed_actor_refs=(source.permission_snapshot.subject,),
        independence_established=True,
        change_authority_actions=tuple(request.available_actions),
        authority_boundary=fixtures._boundary(
            authoritative_for="human_decision_reviewer_separation", source="human_governance"
        ),
        **common,
    )
    return {
        "source": source,
        "request": request,
        "contract": contract,
        "principal": principal,
        "separation": separation,
        "basis_ref": ref,
        "tenant_id": "tenant-a",
        "run_id": "run-gy-pa2",
        "principal_audience": "polisyos-runtime",
        "required_reviewer_permission": RuntimePermission.RUNS_HUMAN_DECISIONS_CREATE.value,
        "verifier_epoch": "fixture-epoch",
        "custody_key_id": "sha256:" + "a" * 64,
        "now": fixtures.NOW,
    }, effects


def _retarget_source_tuple(case, *, action_kind, operation_id):
    """Keep the selected envelope aligned while challenging the exact action tuple."""
    source = case["source"]
    contract = case["contract"]
    envelopes = tuple(
        envelope.model_copy(update={"action_kind": action_kind, "operation_id": operation_id})
        if envelope.envelope_id == source.envelope_id
        else envelope
        for envelope in contract.action_envelopes
    )
    assert len(envelopes) == len(contract.action_envelopes)
    assert any(envelope.envelope_id == source.envelope_id for envelope in envelopes)
    case["contract"] = contract.model_copy(update={"action_envelopes": envelopes})
    case["source"] = source.model_copy(
        update={"action_kind": action_kind, "operation_id": operation_id}
    )


@pytest.mark.parametrize(
    ("acquisition", "action_kind", "need_reason"),
    [
        (True, authority.ACQUISITION_ACTION_KIND, "acquisition_required"),
        (True, authority.CANDIDATE_EXPERIMENT_ACTION_KIND, "acquisition_required"),
        (True, authority.MODEL_INPUT_USE_ACTION_KIND, "budget_required"),
        (False, None, "out_of_envelope"),
    ],
)
def test_ds9_joins_actual_pre_human_source_classes(
    tmp_path, monkeypatch, acquisition, action_kind, need_reason
):
    case, effects = _source_case(
        tmp_path,
        monkeypatch,
        acquisition=acquisition,
        action_kind=action_kind,
    )
    assert case["request"].need_reasons == [need_reason]
    _, issues = _pa2_packet_join_issues(**case)
    assert not issues, issues
    assert effects == []


@pytest.mark.parametrize(
    ("action_kind", "operation_id"),
    [
        (authority.CANDIDATE_EXPERIMENT_ACTION_KIND, authority.ACQUISITION_ACTION_KIND),
        (authority.ACQUISITION_ACTION_KIND, authority.CANDIDATE_EXPERIMENT_ACTION_KIND),
        (authority.CANDIDATE_EXPERIMENT_ACTION_KIND, "runtime.evidence.acquisition.other"),
        ("runtime.evidence.acquisition.other", authority.CANDIDATE_EXPERIMENT_ACTION_KIND),
        ("runtime.evidence.acquisition.other", "runtime.evidence.acquisition.other"),
    ],
)
def test_ds9_acquisition_sources_require_exact_action_tuple(
    tmp_path, monkeypatch, action_kind, operation_id
):
    case, effects = _source_case(
        tmp_path,
        monkeypatch,
        action_kind=authority.CANDIDATE_EXPERIMENT_ACTION_KIND,
    )
    _retarget_source_tuple(case, action_kind=action_kind, operation_id=operation_id)

    _, issues = _pa2_packet_join_issues(**case)

    assert "source" in issues
    assert effects == []


def test_ds9_candidate_experiment_classifier_removal_refuses_candidate_source(
    tmp_path, monkeypatch
):
    case, effects = _source_case(
        tmp_path,
        monkeypatch,
        action_kind=authority.CANDIDATE_EXPERIMENT_ACTION_KIND,
    )
    monkeypatch.setattr(
        authority,
        "_PROTECTED_ACTION_HUMAN_REVIEW",
        {
            kind: requirement
            for kind, requirement in authority._PROTECTED_ACTION_HUMAN_REVIEW.items()
            if kind != authority.CANDIDATE_EXPERIMENT_ACTION_KIND
        },
    )

    _, issues = _pa2_packet_join_issues(**case)

    assert "source" in issues
    assert effects == []


@pytest.mark.parametrize("mutation", ["permission", "version", "reason"])
def test_ds9_model_input_use_refuses_crossed_review_tuple(tmp_path, monkeypatch, mutation):
    case, effects = _source_case(
        tmp_path, monkeypatch, action_kind=authority.MODEL_INPUT_USE_ACTION_KIND
    )
    source = case["source"]
    (envelope,) = case["contract"].action_envelopes
    if mutation == "permission":
        legacy_permission = RuntimePermission.EVIDENCE_ACQUIRE
        envelope = envelope.model_copy(update={"required_permission": legacy_permission})
        source = source.model_copy(
            update={
                "permission_snapshot": source.permission_snapshot.model_copy(
                    update={
                        "required_permission": legacy_permission.value,
                        "granted_permissions": (legacy_permission.value,),
                    }
                )
            }
        )
    elif mutation == "version":
        envelope = envelope.model_copy(update={"operation_version": "v2"})
        source = source.model_copy(update={"operation_version": "v2"})
    else:
        request = case["request"].model_copy(update={"need_reasons": ["acquisition_required"]})
        source = source.model_copy(update={"human_decision_request": request})
        case["request"] = request
        case["separation"] = case["separation"].model_copy(
            update={"decision_request_digest": authority.agent_action_content_hash(request)}
        )
    case["source"] = source
    case["contract"] = case["contract"].model_copy(update={"action_envelopes": (envelope,)})

    _, issues = _pa2_packet_join_issues(**case)

    assert issues == {"source"}
    assert effects == []


def test_pa2_model_input_use_refuses_matching_legacy_envelope_and_permission(tmp_path, monkeypatch):
    case, effects = _source_case(
        tmp_path,
        monkeypatch,
        action_kind=authority.MODEL_INPUT_USE_ACTION_KIND,
        permission=RuntimePermission.EVIDENCE_ACQUIRE,
    )

    assert "explicit_permission_mismatch" in case["source"].refusal_reasons
    assert effects == []


@pytest.mark.parametrize("mutation", ["operation", "permission", "predicates", "reason"])
def test_acquisition_reason_marker_cannot_replace_exact_source_join(
    tmp_path, monkeypatch, mutation
):
    case, effects = _source_case(tmp_path, monkeypatch)
    source = case["source"]
    if mutation == "operation":
        source = source.model_copy(update={"operation_id": "runtime.evidence.acquisition.other"})
    elif mutation == "permission":
        envelope = (
            case["contract"]
            .action_envelopes[0]
            .model_copy(update={"required_permission": RuntimePermission.KNOWLEDGE_SEARCH})
        )
        case["contract"] = case["contract"].model_copy(update={"action_envelopes": (envelope,)})
        source = source.model_copy(
            update={
                "permission_snapshot": source.permission_snapshot.model_copy(
                    update={
                        "required_permission": RuntimePermission.KNOWLEDGE_SEARCH.value,
                        "granted_permissions": (RuntimePermission.KNOWLEDGE_SEARCH.value,),
                    }
                )
            }
        )
    elif mutation == "predicates":
        source = source.model_copy(
            update={
                "predicate_checks": tuple(
                    check.model_copy(update={"satisfied": not check.satisfied})
                    if check.predicate in {"operation_in_envelope", "live_accountability"}
                    else check
                    for check in source.predicate_checks
                )
            }
        )
    else:
        source = source.model_copy(
            update={
                "refusal_reasons": (
                    "delegation_contract_authority_unverified",
                    "human_decision_missing",
                )
            }
        )
    case["source"] = source
    assert case["request"].need_reasons == ["acquisition_required"]
    _, issues = _pa2_packet_join_issues(**case)
    assert "source" in issues
    assert effects == []
