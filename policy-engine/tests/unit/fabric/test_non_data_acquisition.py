"""Candidate non-data runtime falsifiers, starting with ratified W5-K01."""

from __future__ import annotations

import copy
import importlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from unit.fabric.test_ceiling_relations import ceiling_payload, scope_payload, vocabulary_payload

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS

TARGET = {
    "regime": "treatment:a",
    "population": "population:a",
    "outcome": "outcome:y",
    "horizon": "horizon:1",
    "intercurrent_events": "strategy:1",
    "contrast": "contrast:1",
}
DEMANDS = {
    "grounding_relation": {
        "target": TARGET,
        "relation": {
            "source": "x",
            "target": "y",
            "context": "context:1",
            "evidence_regime": "observational",
            "assumptions": ["a:1"],
        },
    },
    "estimand_binding": {"target": {**TARGET, "contrast": None}},
    "owner_writability": {
        "mutation": {
            "system": "system:1",
            "object": "object:1",
            "field": "field:1",
            "operation": "correct",
            "purpose": "purpose:1",
        }
    },
    "legal_mandate": {
        "act": {
            "jurisdiction": "UA",
            "office": "office:1",
            "action": "act:1",
            "delegation_chain": [None],
        }
    },
    "normative_authorization": {
        "determination": {
            "regime": "regime:1",
            "issuer": "issuer:1",
            "procedure": "procedure:1",
            "purpose": "purpose:1",
            "version": "version:1",
        }
    },
    "implementation_capacity_evidence": {
        "commitment": {
            "entity": "entity:1",
            "version": "v1",
            "stage": "pilot",
            "load": 2,
            "environment": "env:1",
            "horizon": "horizon:1",
            "prerequisites": {"staff": None, "technology": "candidate:evidence"},
        }
    },
    "competent_human_decision": {
        "judgment": {
            "question": "question:1",
            "role": "role:1",
            "competence": "competence:1",
            "subject": "subject:1",
            "version": "v1",
            "required_work": ["counterevidence_review"],
            "assurance_engagement": False,
        }
    },
    "independent_audit": {
        "engagement": {
            "subject": "subject:1",
            "version": "v1",
            "criteria": "criteria:1",
            "scope": "scope:1",
            "period": "period:1",
            "level": "level:1",
            "relationship": "relationship:1",
        }
    },
}


def owner_module():
    """Fail explicitly on the missing owner instead of a collection import error."""
    name = "polisyos.fabric.evidence.non_data_acquisition"
    assert importlib.util.find_spec(name) is not None, "GY-AQ1 non-data runtime owner is missing"
    return importlib.import_module(name)


def test_w5_k01_same_stream_rows_do_not_resolve_missing_object(tmp_path):
    """Deleting object-required refusal would let volume change this state."""
    owner = owner_module()
    store = FileSystemCAS(tmp_path / "cas")
    runtime = owner.NonDataAcquisitionRuntime(store=store, journal_path=tmp_path / "events.jsonl")
    request = owner.NonDataRequest(
        request_id="missing-mandate",
        claim_ref="claim:school-program",
        gap_id="gap:mandate",
        demand={
            "act": {
                "jurisdiction": "UA",
                "office": "education-body",
                "action": "fund-school",
                "delegation_chain": [None],
            }
        },
    )
    before = runtime.acquire(request, at=datetime(2026, 9, 10, tzinfo=UTC), row_count=1)
    after = runtime.acquire(request, at=datetime(2026, 9, 10, tzinfo=UTC), row_count=1000000)
    assert before.resolution_state == after.resolution_state == "admission_refused"
    assert before.reason_codes == after.reason_codes == ("non_data_object_missing",)
    assert before.authority_granted is after.authority_granted is False
    assert before.institutional_signer is after.institutional_signer is None
    assert runtime.read_receipt(after.artifact_ref).resolution_state == "admission_refused"


@pytest.mark.parametrize("kind", sorted(DEMANDS))
def test_each_acquisition_type_has_positive_and_sibling_falsifier(kind):
    module = owner_module()
    shape = module.classify_gap(DEMANDS[kind])
    assert shape.acquisition_types == (kind,)
    assert shape.outcome == "one_case"
    sibling = copy.deepcopy(DEMANDS[kind])
    if kind == "grounding_relation":
        sibling["target"]["contrast"] = None
    elif kind == "estimand_binding":
        sibling["target"]["contrast"] = "bound:contrast"
    else:
        branch = next(iter(sibling))
        key = next(iter(sibling[branch]))
        sibling[branch][key] = None
    refused = module.classify_gap(sibling)
    assert kind not in refused.acquisition_types
    assert refused.outcome != "one_case" or refused.acquisition_types == ("estimand_binding",)


def test_unknown_and_compound_demands_do_not_default():
    module = owner_module()
    assert module.classify_gap({"binding_gap": True}).outcome == "not_established"
    merged = {**DEMANDS["legal_mandate"], **DEMANDS["owner_writability"]}
    assert module.classify_gap(merged).outcome == "split_required"


def test_unreadable_sibling_is_ambiguous_not_silently_absent():
    demand = {**DEMANDS["legal_mandate"], "engagement": {"subject": "unreadable"}}
    assert owner_module().classify_gap(demand).outcome == "not_established"


def test_acquisition_type_denominator_matches_complete_research_union():
    module = owner_module()
    root = Path(__file__).resolve().parents[3]
    source = (root / "docs/research/policy-operations/int-r2-gap-acquisition-cases.md").read_text()
    section = source.split("### 4.1 Union scope and classifier")[1].split("### 4.2")[0]
    union = section.split("discriminated_union(case_type):")[1].split("```")[0]
    tokens = {line.strip() for line in union.splitlines() if line.strip()}
    assert tokens == set(DEMANDS) == {item.value for item in module.AcquisitionType}
    assert len(tokens) == 8


@pytest.mark.parametrize("kind", sorted(DEMANDS))
def test_volume_invariance_over_complete_acquisition_type_denominator(tmp_path, kind):
    module, _, runtime = make_runtime(tmp_path)
    request = module.NonDataRequest(
        request_id=kind, claim_ref="claim:1", gap_id="gap:1", demand=DEMANDS[kind]
    )
    small = runtime.acquire(request, at=datetime(2026, 9, 10, tzinfo=UTC), row_count=1)
    large = runtime.acquire(request, at=datetime(2026, 9, 10, tzinfo=UTC), row_count=1000000)
    assert small.artifact_ref == large.artifact_ref
    assert small.resolution_state == large.resolution_state == "admission_refused"


class CandidateOwner:
    """An independently allocated demanding owner over actual candidate body bytes."""

    owner_id = "candidate-demand-owner"

    def verify(self, *, demand, candidate, context):
        return candidate["body"] == {"satisfied": sorted(demand)}

    def reenter(self, *, demand, candidate, context):
        return self.verify(demand=demand, candidate=candidate, context=context)


class CandidateVerifier:
    """Separate allocation and implementation; this is not the AS1 oracle."""

    owner_id = "candidate-verifier"

    def verify(self, *, demand, candidate, context):
        body = candidate.get("body")
        if not isinstance(body, dict) or set(body) != {"satisfied"}:
            return False
        values = body["satisfied"]
        return (
            isinstance(values, list) and len(values) == len(demand) and set(values) == set(demand)
        )


def make_runtime(tmp_path, *, verifier=True):
    module = owner_module()
    store = FileSystemCAS(tmp_path / "cas")
    runtime = module.NonDataAcquisitionRuntime(
        store=store,
        journal_path=tmp_path / "events.jsonl",
        demanding_owner=CandidateOwner(),
        independent_verifier=CandidateVerifier() if verifier else None,
    )
    return module, store, runtime


def candidate_request(module, runtime, kind="legal_mandate", *, malformed=False):
    demand = copy.deepcopy(DEMANDS[kind])
    payload = {
        "object_type": kind,
        "demand_hash": module.demand_hash(demand),
        "body": {"satisfied": sorted(demand)} if not malformed else {"looks_valid": True},
        "ceiling": ceiling_payload(),
    }
    candidate_ref = runtime.persist_candidate(payload)
    vocabulary_ref = runtime.persist_vocabulary(vocabulary_payload())
    request = module.NonDataRequest(
        request_id="candidate-request",
        gap_id="gap:1",
        claim_ref="claim:1",
        demand=demand,
        candidate_ref=candidate_ref,
        vocabulary_ref=vocabulary_ref,
        requested_use=scope_payload(),
    )
    return request


@pytest.mark.parametrize("kind", sorted(DEMANDS))
def test_candidate_admitted_and_consumed_without_institutional_authority(tmp_path, kind):
    module, _, runtime = make_runtime(tmp_path)
    request = candidate_request(module, runtime, kind)
    receipt = runtime.acquire(request, at=datetime(2026, 9, 10, tzinfo=UTC))
    assert receipt.resolution_state == "reentry_closed"
    assert receipt.authority_granted is False
    assert receipt.institutional_signer is None
    assert runtime.verify_receipt(receipt.artifact_ref).resolution_state == "reentry_closed"
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [row["resolution_state"] for row in events] == [
        "admitted_reentry_required",
        "reentry_closed",
    ]


@pytest.mark.parametrize("falsifier", ["fake_ref", "body", "verifier_absent", "same_owner"])
def test_owner_admission_fails_closed_through_real_runtime(tmp_path, falsifier):
    module, _, runtime = make_runtime(tmp_path, verifier=falsifier != "verifier_absent")
    request = candidate_request(module, runtime, malformed=falsifier == "body")
    if falsifier == "fake_ref":
        request = request.model_copy(update={"candidate_ref": "sha256:" + "0" * 64})
    if falsifier == "same_owner":
        runtime.independent_verifier = runtime.demanding_owner
    result = runtime.acquire(request, at=datetime(2026, 9, 10, tzinfo=UTC))
    assert result.resolution_state == "admission_refused"
    assert result.authority_granted is False


def test_decisive_owner_validation_removal_is_detected(tmp_path, monkeypatch):
    """Deleting owner verification while retaining schemas must break the contract."""
    module, _, runtime = make_runtime(tmp_path)
    request = candidate_request(module, runtime, malformed=True)
    assert (
        runtime.acquire(request, at=datetime(2026, 9, 10, tzinfo=UTC)).resolution_state
        == "admission_refused"
    )
    monkeypatch.setattr(runtime, "_owners_accept", lambda **kwargs: True)
    mutated = runtime.acquire(request, at=datetime(2026, 9, 10, tzinfo=UTC))
    assert mutated.resolution_state != "admission_refused", (
        "removal did not exercise decisive admission"
    )


def test_tampered_persisted_receipt_cannot_be_read_as_valid(tmp_path):
    module, store, runtime = make_runtime(tmp_path)
    request = candidate_request(module, runtime)
    result = runtime.acquire(request, at=datetime(2026, 9, 10, tzinfo=UTC))
    blob, _ = store.get_paths(ArtifactID.model_validate(result.artifact_ref))
    payload = json.loads(blob.read_text())
    payload["authority_granted"] = True
    blob.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="content_identity|sha256 mismatch"):
        runtime.read_receipt(result.artifact_ref)


def test_audit_reader_recomputes_forged_candidate_resolution(tmp_path):
    module, _, runtime = make_runtime(tmp_path)
    request = module.NonDataRequest(
        request_id="forged", claim_ref="claim:1", gap_id="gap:1", demand=DEMANDS["legal_mandate"]
    )
    result = runtime.acquire(request, at=datetime(2026, 9, 10, tzinfo=UTC))
    payload = result.model_dump(mode="json", exclude={"artifact_ref"})
    payload["resolution_state"] = "reentry_closed"
    payload["reason_codes"] = []
    forged = runtime._persist(payload, "fabric.non_data_acquisition.receipt")
    with pytest.raises(ValueError, match="receipt_recomputation_mismatch"):
        runtime.read_receipt(forged)


def test_new_or_unknown_objects_cannot_be_classified_by_count_or_label(tmp_path):
    module, _, runtime = make_runtime(tmp_path)
    for demand in (
        {"binding_gap": "legal_mandate"},
        {"rows": 999999},
        {"act": {"action": "approve"}},
    ):
        request = module.NonDataRequest(
            request_id="unknown", claim_ref="claim:1", gap_id="gap:1", demand=demand
        )
        receipt = runtime.acquire(request, at=datetime(2026, 9, 10, tzinfo=UTC))
        assert receipt.resolution_state == "shape_not_established"


@pytest.mark.parametrize("port", ["demanding_verification", "independent_verification", "reentry"])
@pytest.mark.parametrize("changed", ["purpose", "evaluation_time", "claim"])
def test_every_semantic_port_receives_bound_current_use_context(tmp_path, port, changed):
    """A ceiling comparison alone cannot decide a demanding owner's use predicate."""
    module, _, runtime = make_runtime(tmp_path)
    request = candidate_request(module, runtime)
    now = datetime(2026, 9, 10, tzinfo=UTC)
    seen = []

    def accepts_context(context):
        seen.append(context)
        return (
            context.request_id == request.request_id
            and context.claim_ref == request.claim_ref
            and context.gap_id == request.gap_id
            and context.demand_hash == module.demand_hash(request.demand)
            and context.candidate_ref == request.candidate_ref
            and context.vocabulary_ref == request.vocabulary_ref
            and context.planner_report_ref == request.planner_report_ref
            and context.requested_use.purpose_ref == "purpose:bounded-research"
            and context.evaluated_at == now
        )

    class ContextOwner(CandidateOwner):
        def verify(self, *, demand, candidate, context):
            return CandidateOwner.verify(
                self, demand=demand, candidate=candidate, context=context
            ) and (
                port != "demanding_verification" or accepts_context(context)
            )

        def reenter(self, *, demand, candidate, context):
            return CandidateOwner.verify(
                self, demand=demand, candidate=candidate, context=context
            ) and (
                port != "reentry" or accepts_context(context)
            )

    class ContextVerifier(CandidateVerifier):
        def verify(self, *, demand, candidate, context):
            return CandidateVerifier.verify(
                self, demand=demand, candidate=candidate, context=context
            ) and (
                port != "independent_verification" or accepts_context(context)
            )

    runtime.demanding_owner = ContextOwner()
    runtime.independent_verifier = ContextVerifier()
    accepted = runtime.acquire(request, at=now)
    assert accepted.resolution_state == "reentry_closed", accepted.reason_codes
    assert seen and all(context == seen[0] for context in seen)
    with pytest.raises((AttributeError, TypeError, ValueError)):
        seen[0].evaluated_at = datetime(2026, 9, 11, tzinfo=UTC)
    with pytest.raises((AttributeError, TypeError, ValueError)):
        seen[0].requested_use.purpose_ref = "purpose:research"

    altered = request
    later = now
    if changed == "purpose":
        altered = request.model_copy(
            update={"requested_use": request.requested_use.model_copy(
                update={"purpose_ref": "purpose:research"}
            )}
        )
    elif changed == "evaluation_time":
        later = datetime(2026, 9, 11, tzinfo=UTC)
    else:
        altered = request.model_copy(update={"claim_ref": "claim:other"})
    assert module.evaluate_ceiling(
        vocabulary=module.CeilingVocabulary.model_validate(vocabulary_payload()),
        requested=altered.requested_use,
        ceiling=module.CeilingScope.model_validate(ceiling_payload()),
        at=later,
    ).permitted
    refused = runtime.acquire(altered, at=later)
    assert refused.resolution_state == (
        "reentry_provisional_refusal" if port == "reentry" else "admission_refused"
    )
    payload = accepted.model_dump(mode="json", exclude={"artifact_ref"})
    payload["request"] = altered.model_dump(mode="json")
    payload["evaluated_at"] = later.isoformat()
    forged = runtime._persist(payload, "fabric.non_data_acquisition.receipt")
    with pytest.raises(ValueError, match="receipt_recomputation_mismatch"):
        runtime.read_receipt(forged)
    if changed == "evaluation_time":
        with pytest.raises(ValueError, match="receipt_recomputation_mismatch"):
            runtime.verify_receipt(accepted.artifact_ref, at=later)


def test_bridge_reuses_real_canonical_planner_and_persistence(tmp_path):
    module, store, runtime = make_runtime(tmp_path)
    bridge = importlib.import_module("polisyos.runtime.quality.non_data_acquisition")
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionGap,
        AcquisitionGapType,
        AuthorityLevel,
        MandatoryGateState,
        load_acquisition_planner_report,
    )

    request = candidate_request(module, runtime)
    gap = AcquisitionGap(
        gap_id=request.gap_id,
        claim_ref=request.claim_ref,
        gap_type=AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY,
        authority_level=AuthorityLevel.GOVERNED,
        mandatory_gate_state=MandatoryGateState.NON_OVERRIDABLE,
    )
    result = bridge.run_non_data_acquisition(
        runtime=runtime,
        request=request,
        gap=gap,
        run_id="run:candidate",
        at=datetime(2026, 9, 10, tzinfo=UTC),
    )
    report = load_acquisition_planner_report(store, result.planner_report_ref)
    assert report.acquisition_records[0].claim_ref == request.claim_ref
    assert result.receipt.authority_granted is False
    assert result.receipt.planner_report_ref == str(result.planner_report_ref.artifact_id)
    with pytest.raises(ValueError, match="gap_binding"):
        bridge.run_non_data_acquisition(
            runtime=runtime,
            request=request.model_copy(update={"claim_ref": "other:claim"}),
            gap=gap,
            run_id="run:bad",
            at=datetime(2026, 9, 10, tzinfo=UTC),
        )
