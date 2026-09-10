"""Behavioral acquisition assurance and persisted-consumer falsifiers."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from polisyos.fabric.evidence.acquisition_assurance import (
    data_availability_positive_control,
    decode_case_inputs,
    execute_case,
    run_corpus,
)

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "docs/reference/gy-acquisition-assurance-corpus.json"


def test_assurance_executes_frozen_corpus_and_persisted_consumer(tmp_path):
    """Every case consumes a real AQ1 CAS receipt and its append-only event."""
    corpus = decode_case_inputs(CORPUS)
    actual = run_corpus(corpus, tmp_path)
    assert len(actual) == len({row.case_id for row in actual}) == 63
    assert all(row.consumer_recomputed and row.receipt_ref.startswith("sha256:") for row in actual)
    assert all(row.authority == "false" and row.signer == "empty" for row in actual)
    happy = [row for row in actual if row.case_id.startswith("happy.")]
    assert len(happy) == 8 and all(row.state == "reentry_closed" for row in happy)


@pytest.mark.parametrize("kind", [
    "grounding_relation", "estimand_binding", "owner_writability", "legal_mandate",
    "normative_authorization", "implementation_capacity_evidence", "competent_human_decision",
    "independent_audit",
])
def test_terminal_requires_substantive_bound_complete_owner_basis(tmp_path, kind):
    """Retaining claimed coverage while removing owner evidence cannot establish a boundary."""
    corpus = decode_case_inputs(CORPUS)
    original = next(row for row in corpus["cases"] if row["case_id"] == f"deeper.{kind}")
    positive = execute_case(original, corpus["vocabulary"], tmp_path / "positive")
    assert positive.state == "reentry_provisional_refusal" and positive.terminal == "deeper"
    missing = copy.deepcopy(original)
    missing["terminal_evidence"]["searched"] = missing["terminal_evidence"]["searched"][:-1]
    assert execute_case(missing, corpus["vocabulary"], tmp_path / "missing").terminal == "provisional"
    fake = copy.deepcopy(original)
    fake["terminal_evidence"]["searched"].append("nonexistent:alternative")
    fake["terminal_evidence"]["basis_hash"] = hashlib.sha256(
        json.dumps(fake["terminal_basis"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert execute_case(fake, corpus["vocabulary"], tmp_path / "fake").terminal == "provisional"


@pytest.mark.parametrize("alteration", ["cross_bound_claim", "late", "forged", "conflict"])
def test_event_cannot_close_without_recomputed_targeted_current_evidence(tmp_path, alteration):
    corpus = decode_case_inputs(CORPUS)
    case = copy.deepcopy(next(row for row in corpus["cases"]
                              if row["case_id"] == "reentry.grounding_relation"))
    event = case["events"][0]
    if alteration == "cross_bound_claim":
        event["claim"] = "synthetic:other"
    elif alteration == "late":
        event["occurred_at"] = "2026-08-01T00:00:00Z"
    elif alteration == "forged":
        event["producer"] = "synthetic:forged"
    else:
        event["facts"][next(iter(event["facts"]))] = "contradictory"
    result = execute_case(case, corpus["vocabulary"], tmp_path)
    assert result.state == "reentry_provisional_refusal"
    assert result.reentry == "performed" and result.authority == "false"


def test_duplicate_event_has_one_persisted_acquisition_effect(tmp_path):
    corpus = decode_case_inputs(CORPUS)
    case = next(row for row in corpus["cases"] if row["case_id"] == "reentry.owner_writability")
    result = execute_case(case, corpus["vocabulary"], tmp_path)
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert result.event == "idempotent_duplicate" and result.state == "reentry_closed"
    assert [event["resolution_state"] for event in events] == [
        "admitted_reentry_required", "reentry_closed",
    ]


@pytest.mark.parametrize("kind", [
    "grounding_relation", "estimand_binding", "owner_writability", "legal_mandate",
    "normative_authorization", "implementation_capacity_evidence", "competent_human_decision",
    "independent_audit",
])
def test_remove_boundary_property_keep_terminal_markers_refuses(tmp_path, kind):
    """Same labels and complete coverage cannot replace the substantive predicate."""
    corpus = decode_case_inputs(CORPUS)
    case = copy.deepcopy(next(row for row in corpus["cases"] if row["case_id"] == f"deeper.{kind}"))
    basis = case["terminal_basis"]
    if kind == "grounding_relation":
        basis["models"][0]["y"] = basis["models"][1]["y"]
    elif kind == "estimand_binding":
        basis["constraints"]["contrast:b"] = basis["constraints"]["contrast:a"]
    elif kind == "owner_writability":
        basis["ontology"]["operation:append"] = "correct"
    elif kind == "legal_mandate":
        basis["rules"]["rule:prohibition"]["disposition"] = "permitted"
    elif kind == "normative_authorization":
        basis["determinations"]["decision:1"]["disposition"] = "approved"
    elif kind == "implementation_capacity_evidence":
        basis["alternatives"]["build"] = {"capacity": 10, "ready_day": 1}
    elif kind == "competent_human_decision":
        basis["roster"]["person:a"] = [case["demand"]["judgment"]["competence"]]
    else:
        basis["providers"]["provider:a"] = {"implemented_subject": False, "financial_interest": False}
    case["terminal_evidence"]["basis_hash"] = hashlib.sha256(
        json.dumps(basis, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    observed = execute_case(case, corpus["vocabulary"], tmp_path)
    assert observed.terminal == "provisional" and observed.state == "reentry_provisional_refusal"


def test_ordinary_data_control_observes_admitted_availability_change(tmp_path):
    assert data_availability_positive_control(tmp_path) == (False, True)


def test_rule_change_revalidates_current_use_and_preserves_old_receipt(tmp_path):
    corpus = decode_case_inputs(CORPUS)
    case = next(row for row in corpus["cases"] if row["case_id"] == "reentry.independent_audit")
    result = execute_case(case, corpus["vocabulary"], tmp_path)
    old = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    current = [json.loads(line) for line in (tmp_path / "current-events.jsonl").read_text().splitlines()]
    assert old[-1]["resolution_state"] == "reentry_provisional_refusal"
    assert current[-1]["resolution_state"] == result.state == "admission_refused"
    assert old[-1]["artifact_ref"] != current[-1]["artifact_ref"]
    assert result.event == "rule_revalidation" and result.ceiling == "refused:exact_controls"
    assert result.reentry == "absent"


def test_persisted_consumer_rejects_self_stamped_closure(tmp_path, monkeypatch):
    from polisyos.fabric.evidence.non_data_acquisition import NonDataAcquisitionRuntime

    acquire = NonDataAcquisitionRuntime.acquire

    def forge(self, request, **kwargs):
        receipt = acquire(self, request, **kwargs)
        payload = receipt.model_dump(mode="json", exclude={"artifact_ref"})
        payload["resolution_state"] = "reentry_closed"
        payload["reason_codes"] = []
        forged_ref = self._persist(payload, "fabric.non_data_acquisition.receipt")
        return receipt.model_copy(update={"artifact_ref": forged_ref})

    monkeypatch.setattr(NonDataAcquisitionRuntime, "acquire", forge)
    corpus = decode_case_inputs(CORPUS)
    case = next(row for row in corpus["cases"] if row["case_id"] == "rows.grounding_relation.0")
    with pytest.raises(ValueError, match="receipt_recomputation_mismatch"):
        execute_case(case, corpus["vocabulary"], tmp_path)
