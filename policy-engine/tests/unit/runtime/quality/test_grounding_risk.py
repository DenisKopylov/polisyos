"""Run-bound admission accounting, independent of candidate exploration."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from polisyos.runtime.quality.grounding_bind import (
    GroundingBindGate,
    GroundingDecisionCertificate,
    GroundingRunBudget,
    resolve_grounding_decision_promotability,
)
from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
from tests.unit.runtime.quality.test_grounding_bind import (
    _false_analog_probe,
    _pure_synonym_probe,
    _reference,
)


def test_refused_candidate_does_not_spend_any_admission_budget() -> None:
    """Cold-start refusal exercises a candidate without an authority admission."""
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    candidate = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="free-candidate")
    result = GroundingBindGate(reference).certificate_for(candidate)
    assert result.decision == "abstain"
    assert result.production_promotable is False
    assert result.risk_ledger.total_spend == 0.0


def _exercise(tmp_path: Path):
    reference = _reference()
    engine = GroundingRelationEngine(reference)
    good = tuple(
        engine.certificate_for(_pure_synonym_probe(engine), proposal_id=f"good-{i}")
        for i in range(6)
    )
    bad = engine.certificate_for(_false_analog_probe(), proposal_id="mismatch")
    budget = GroundingRunBudget.for_contract_testing(tmp_path, run_id="one-run")
    gate = GroundingBindGate.for_contract_testing(
        reference, calibration_seed_anchor=True, run_budget=budget
    )
    return reference, good, bad, budget, gate


def test_only_owner_admissions_charge_and_exhaustion_preserves_candidate(tmp_path: Path) -> None:
    reference, good, bad, budget, gate = _exercise(tmp_path)
    for _ in range(12):
        refused = gate.certificate_for(bad)
        assert refused.decisive_reason == "false_analog_hard_abstain"
        assert refused.risk_ledger.total_spend == 0
        assert refused.admission_strangle.status == "strangled"
        assert refused.admission_strangle.observed_attempt_charge == 0
    for count, candidate in enumerate(good[:4], 1):
        result = gate.certificate_for(candidate)
        assert result.decision == "bind"
        assert result.run_admission.admitted_spend == round(count * 0.01, 12)
        assert result.run_admission.charged_this_attempt == 0.01
        assert result.synthetic is True
        assert result.production_promotable is False
        assert not resolve_grounding_decision_promotability(result, reference).promotable
    repeated = gate.certificate_for(good[0])
    assert repeated.run_admission.charged_this_attempt == 0
    exhausted = gate.certificate_for(good[4])
    assert exhausted.decision == "abstain"
    assert exhausted.decisive_reason == "risk_budget_exhausted_candidate_custody"
    assert exhausted.safe_t.safe_atom_ids
    assert exhausted.run_admission.run_continues is True
    assert exhausted.run_admission.correctness_bound is None
    assert exhausted.run_admission.authority_band == "candidate"
    assert exhausted.risk_ledger.total_spend == 0
    assert budget.to_payload()["admission_count"] == 4


def test_restart_and_missing_head_cannot_reset_spend(tmp_path: Path) -> None:
    reference, good, _, budget, gate = _exercise(tmp_path)
    for candidate in good[:4]:
        assert gate.certificate_for(candidate).decision == "bind"
    (budget._root / "head.json").unlink()
    restarted = GroundingRunBudget.for_contract_testing(tmp_path, run_id="one-run")
    gate = GroundingBindGate.for_contract_testing(
        reference, calibration_seed_anchor=True, run_budget=restarted
    )
    assert (
        gate.certificate_for(good[4]).decisive_reason == "risk_budget_exhausted_candidate_custody"
    )
    assert restarted.to_payload()["admitted_spend"] == 0.04


def test_independent_owners_share_one_cap(tmp_path: Path) -> None:
    reference, good, _, _, _ = _exercise(tmp_path)
    owners = tuple(
        GroundingRunBudget.for_contract_testing(tmp_path, run_id="one-run") for _ in good
    )

    def admit(index: int):
        gate = GroundingBindGate.for_contract_testing(
            reference, calibration_seed_anchor=True, run_budget=owners[index]
        )
        return gate.certificate_for(good[index])

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(admit, range(len(good))))
    assert sum(row.decision == "bind" for row in outcomes) == 4
    assert sum(row.run_admission.status == "exhausted" for row in outcomes) == 2
    assert all(owner.to_payload()["admitted_spend"] == 0.04 for owner in owners)


def test_crash_after_event_before_head_still_charges(tmp_path: Path, monkeypatch) -> None:
    reference, good, _, budget, gate = _exercise(tmp_path)

    def crash(*_args):
        raise OSError("declared crash after immutable admission")

    monkeypatch.setattr(budget, "_write_head", crash)
    result = gate.certificate_for(good[0])
    assert result.decision == "abstain"
    restarted = GroundingRunBudget.for_contract_testing(tmp_path, run_id="one-run")
    assert restarted.to_payload()["admitted_spend"] == 0.01
    gate = GroundingBindGate.for_contract_testing(
        reference, calibration_seed_anchor=True, run_budget=restarted
    )
    assert gate.certificate_for(good[0]).run_admission.charged_this_attempt == 0


def test_corrupt_established_head_is_unknown_never_zero(tmp_path: Path) -> None:
    _, good, _, budget, gate = _exercise(tmp_path)
    assert gate.certificate_for(good[0]).decision == "bind"
    (budget._root / "head.json").write_text("unreadable")
    assert budget.to_payload()["admitted_spend"] is None
    assert gate.certificate_for(good[1]).decisive_reason == "durable_run_budget_unavailable"


def test_synthetic_production_refusal_is_not_an_absent_calibration_mask() -> None:
    reference = _reference()
    reference = replace(
        reference,
        essential_edges={
            key: replace(
                edge, provenance={**edge.provenance, "synthetic": True}
            ).with_content_hash()
            for key, edge in reference.essential_edges.items()
        },
    )
    engine = GroundingRelationEngine(reference)
    candidate = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="marked-input")
    result = GroundingBindGate(reference).certificate_for(candidate)
    assert result.synthetic is True
    assert result.decisive_reason == "synthetic_input_candidate_only"
    assert resolve_grounding_decision_promotability(result, reference).reason == (
        "synthetic_input_cannot_grant_authority"
    )


def test_existing_v1_records_stay_readable_without_claiming_run_accounting() -> None:
    source = Path("architecture/policy_design_case/layer3_gy_promotion_contract.json")
    payload = json.loads(source.read_bytes())
    records = []
    pending = [payload]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if value.get("schema_version") == "policyos.runtime.grounding_decision_certificate.v1":
                records.append(value)
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    assert records
    for record in records:
        decoded = GroundingDecisionCertificate.model_validate(record)
        assert decoded.content_hash == record["content_hash"]
        assert decoded.run_admission is None
        assert decoded.model_dump(mode="json") == record
        assert TypeAdapter(dict[str, GroundingDecisionCertificate]).dump_python(
            {"historical": decoded}, mode="json"
        ) == {"historical": record}
    independently_found = []
    json.loads(
        source.read_bytes(),
        object_hook=lambda row: independently_found.append(row)
        if row.get("schema_version") == "policyos.runtime.grounding_decision_certificate.v1"
        else row,
    )
    assert {row["content_hash"] for row in independently_found} == {
        row["content_hash"] for row in records
    }


def test_preemptive_cap_removal_is_detected(tmp_path: Path, monkeypatch) -> None:
    from polisyos.runtime.quality import grounding_risk

    monkeypatch.setattr(grounding_risk, "_budget_has_capacity", lambda _count: True)
    with pytest.raises(AssertionError):
        test_only_owner_admissions_charge_and_exhaustion_preserves_candidate(tmp_path)


def test_admission_event_cannot_be_transplanted_to_a_different_binding(tmp_path: Path) -> None:
    _, good, _, budget, gate = _exercise(tmp_path)
    admitted = gate.certificate_for(good[0])
    fields = {
        "cg1_content_hash": admitted.cg1_content_hash,
        "reference_hash": admitted.reference_hash,
        "bound_atom_id": admitted.bound_atom_id,
        "calibration_anchor_hash": admitted.calibration.owned_anchor_content_hash,
    }
    assert budget.binding_evidence_matches(admitted.run_admission, **fields)
    assert not budget.contains(admitted.run_admission, **fields)
    for key in fields:
        swapped = {**fields, key: "present-but-different-owner-input"}
        assert not budget.binding_evidence_matches(admitted.run_admission, **swapped), key


def test_unsupported_lock_platform_preserves_candidate_custody(tmp_path: Path, monkeypatch) -> None:
    from polisyos.runtime.quality import grounding_risk

    _, good, _, budget, gate = _exercise(tmp_path)
    monkeypatch.setattr(grounding_risk, "_fcntl", None)
    result = gate.certificate_for(good[0])
    assert result.decisive_reason == "durable_run_budget_unavailable"
    assert result.run_admission.run_continues
    assert budget.to_payload()["admitted_spend"] is None


def test_unopenable_run_state_is_candidate_custody_not_a_run_error(tmp_path: Path) -> None:
    (tmp_path / "synthetic").write_text('{"synthetic": true, "kind": "directory_collision"}')
    budget = GroundingRunBudget.for_contract_testing(tmp_path, run_id="one-run")
    assert budget.to_payload()["status"] == "unavailable"
    assert budget.to_payload()["admitted_spend"] is None


def test_omitted_cas_case_is_ambiguous_not_a_zero_balance(tmp_path: Path) -> None:
    budget = GroundingRunBudget.for_contract_testing(tmp_path, run_id="one-run")
    (budget._store.base / "malformed.manifest.json").write_text('{"synthetic": true}')
    assert budget.to_payload()["status"] == "unavailable"
    assert budget.to_payload()["admitted_spend"] is None


def test_governed_resolver_recomputes_synthetic_ancestry_despite_false_flag() -> None:
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.grounding_bind import recompute_grounding_decision_content_hash

    source = _reference()
    edges = {
        key: replace(edge, provenance={**edge.provenance, "synthetic": True}).with_content_hash()
        for key, edge in source.essential_edges.items()
    }
    reference = replace(
        source,
        essential_edges=edges,
        reference_hash=gy_content_hash([edge.to_payload() for edge in edges.values()]),
    )
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="synthetic-ancestry")
    original = GroundingBindGate(reference).certificate_for(cg1)
    payload = original.model_dump(mode="json")
    payload["synthetic"] = False  # Deliberately dishonest claim; actual source stays marked.
    payload["run_admission"]["synthetic"] = False
    payload["admission_strangle"]["synthetic"] = False
    payload["content_hash"] = recompute_grounding_decision_content_hash(payload)
    payload["certificate_id"] = f"cg2_cert_{payload['content_hash'].removeprefix('sha256:')[:16]}"
    dishonest = GroundingDecisionCertificate.model_validate(payload)
    resolution = resolve_grounding_decision_promotability(dishonest, reference)
    assert resolution.promotable is False
    assert resolution.reason == "synthetic_input_cannot_grant_authority"
