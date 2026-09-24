"""Execute candidate acquisition assurance through the delivered Fabric owner.

This is a synthetic contract-testing adapter, called by the non-test assurance
checker. It cannot appoint institutions or manufacture an Atlas lifecycle state.
The independent expected-answer oracle lives outside this subject module.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.fabric.evidence.ceiling_relations import (
    CeilingScope,
    CeilingVocabulary,
    evaluate_ceiling,
)
from polisyos.fabric.evidence.non_data_acquisition import (
    AcquisitionEvaluationContext,
    NonDataAcquisitionRuntime,
    NonDataReceipt,
    NonDataRequest,
    demand_hash,
)

WIRE_FIELDS = (
    "case_id", "shape", "types", "state", "terminal", "ceiling", "authority",
    "signer", "reentry", "event", "reason",
)
MUTANTS = (
    "mutant.row_count_auto_closes_relation_estimand_mandate",
    "mutant.form_or_signature_auto_admits",
    "mutant.route_or_artifact_auto_closes_without_owner_reentry",
    "mutant.exact_membership_used_for_hierarchy_or_subset",
    "mutant.timeout_or_silence_emits_terminal",
    "mutant.surface_composes_authority",
    "mutant.remove_property_keep_markers",
)


class AcquisitionObservation(BaseModel):
    """Measured subject facts, including intentionally mutable mutant surfaces."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str
    shape: str
    types: str
    state: str
    terminal: Literal["none", "provisional", "deeper"]
    ceiling: str
    authority: Literal["false", "true"]
    signer: Literal["empty", "present"]
    reentry: Literal["performed", "absent"]
    event: str
    reason: str
    receipt_ref: str
    consumer_recomputed: Literal[True]
    institutional_appointment: None = None

    def wire_row(self) -> str:
        """Serialize observed facts; the independent oracle parses its own wire."""
        values = [str(getattr(self, field)) for field in WIRE_FIELDS]
        if any("\t" in value or "\n" in value for value in values):
            raise ValueError("observation_wire_separator")
        return "\t".join(values)


def decode_case_inputs(path: Path) -> dict[str, Any]:
    """Read the immutable JSON subject inputs, never the oracle's TSV format."""
    value = json.loads(path.read_bytes())
    if value.get("schema_version") != "gy.acquisition_assurance.corpus.v1":
        raise ValueError("corpus_schema")
    return value


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class _ReferenceVerifier:
    """Separate synthetic verifier of resolved candidate observations and binding."""

    owner_id = "as1.synthetic.independent-verifier"

    def __init__(self, case: Mapping[str, Any]) -> None:
        self.case = case

    def verify(
        self, *, demand: Mapping[str, Any], candidate: Mapping[str, Any],
        context: AcquisitionEvaluationContext,
    ) -> bool:
        """Compare resolved observations against separately bound owner demands."""
        body = candidate.get("body", {})
        observations = body.get("facts", {})
        required = self.case["required_facts"]
        return (
            isinstance(observations, dict)
            and len(observations) == len(required)
            and all(observations.get(key) == value for key, value in required.items())
            and body.get("producer") == "synthetic:producer"
            and body.get("subject") == context.claim_ref == "synthetic:claim"
            and body.get("rule") == context.requested_use.rule_version_ref
            and context.demand_hash == demand_hash(demand)
            and context.evaluated_at == _time(self.case["evaluated_at"])
        )


class _ReferenceDemandingOwner:
    """Demanding reference predicate, independently implemented from verifier."""

    owner_id = "as1.synthetic.demanding-owner"

    def __init__(self, case: Mapping[str, Any], mutant: str | None) -> None:
        self.case = case
        self.mutant = mutant
        self.reentry_calls = 0
        self.event_effect = "none"

    def verify(
        self, *, demand: Mapping[str, Any], candidate: Mapping[str, Any],
        context: AcquisitionEvaluationContext,
    ) -> bool:
        """Resolve actual values; a document, signature or favorable label is unused."""
        body = candidate["body"]
        if body.get("subject") != context.claim_ref or body.get("rule") != "rule:1":
            return False
        if context.requested_use != CeilingScope.model_validate(self.case["requested_use"]):
            return False
        if dict(demand) != self.case["demand"] or body.get("producer") != "synthetic:producer":
            return False
        if not isinstance(body.get("facts"), dict):
            return False
        return sorted(body["facts"].items()) == sorted(self.case["required_facts"].items())

    def _event_availability(self, context: AcquisitionEvaluationContext) -> set[str]:
        available = set(self.case["predicate_evidence"]["available"])
        seen: dict[str, str] = {}
        expected = self.case["required_facts"]
        for event in self.case["events"]:
            identity = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
            previous = seen.get(event["event_id"])
            if previous is not None:
                if previous != identity:
                    self.event_effect = "conflict_refused"
                    return set()
                self.event_effect = "idempotent_duplicate"
                continue
            seen[event["event_id"]] = identity
            occurred = _time(event["occurred_at"])
            if not context.requested_use.valid_from <= occurred <= context.evaluated_at:
                self.event_effect = "historical_only"
                continue
            if event["producer"] != "synthetic:producer":
                self.event_effect = "producer_refused"
                continue
            if event["claim"] != context.claim_ref or set(event["predicate"]) != set(expected):
                self.event_effect = "conflict_refused"
                return set()
            if event["rule"] != context.requested_use.rule_version_ref:
                self.event_effect = "rule_revalidation"
                continue
            facts = event["facts"]
            if any(key in facts and facts[key] != value for key, value in expected.items()):
                self.event_effect = "conflict_refused"
                return set()
            if set(facts) != set(expected):
                self.event_effect = "limited_refused"
                continue
            available.update(facts)
            self.event_effect = "targeted"
        return available

    def reenter(
        self, *, demand: Mapping[str, Any], candidate: Mapping[str, Any],
        context: AcquisitionEvaluationContext,
    ) -> bool:
        """Rerun the demanding predicate; receipt alone never changes availability."""
        del demand, candidate
        if self.mutant == MUTANTS[2]:
            return True
        self.reentry_calls += 1
        evidence = self.case["predicate_evidence"]
        if evidence["bound_claim"] != context.claim_ref:
            return False
        if evidence["rule"] != context.requested_use.rule_version_ref:
            return False
        return set(self.case["required_facts"]) <= self._event_availability(context)


_BOUNDARIES = {
    "grounding_relation": ("nonidentifiability", "models"),
    "estimand_binding": ("ill_defined_target", "constraints"),
    "owner_writability": ("invalid_operation", "ontology"),
    "legal_mandate": ("higher_prohibition", "rules"),
    "normative_authorization": ("competent_disapproval", "determinations"),
    "implementation_capacity_evidence": ("capacity_horizon", "alternatives"),
    "competent_human_decision": ("competent_roster_absence", "roster"),
    "independent_audit": ("independent_provider_absence", "providers"),
}


def _basis_members(case: Mapping[str, Any]) -> list[str]:
    basis = case["terminal_basis"]
    property_name, collection = _BOUNDARIES[case["discriminator"]]
    if basis["property"] != property_name:
        raise ValueError("boundary_property_type_mismatch")
    objects = basis[collection]
    return [item["id"] for item in objects] if isinstance(objects, list) else list(objects)


def _finite_boundary_holds(basis: Mapping[str, Any], demand: Mapping[str, Any]) -> bool:
    """Evaluate finite owner evidence about the actual context, never its label."""
    digest = hashlib.sha256(json.dumps(demand, sort_keys=True, separators=(",", ":")).encode())
    if basis["demand_hash"] != digest.hexdigest() or not basis["assessed"]:
        return False
    for path, expected in basis["assessed"].items():
        value = demand
        for key in path.split("."):
            value = value[key]
        if value != expected:
            return False
    prop = basis["property"]
    if prop == "nonidentifiability":
        models = basis["models"]
        if len(models) != 2 or demand["relation"]["evidence_regime"] != "observational":
            return False
        observed = [sorted((m["x"][u], m["y"][u][m["x"][u]]) for u in (0, 1)) for m in models]
        intervention = basis["intervention"]
        effects = [sorted(m["y"][u][intervention] for u in (0, 1)) for m in models]
        return observed[0] == observed[1] and effects[0] != effects[1]
    if prop == "ill_defined_target":
        return demand["target"][basis["attribute"]] is None and not set.intersection(
            *(set(values) for values in basis["constraints"].values())
        )
    if prop == "invalid_operation":
        return demand["mutation"]["operation"] not in basis["ontology"].values()
    if prop == "higher_prohibition":
        request = {"actor": demand["act"]["office"], "action": demand["act"]["action"],
                   "jurisdiction": demand["act"]["jurisdiction"]}
        matching = [row for row in basis["rules"].values()
                    if all(row.get(k) == v for k, v in request.items())]
        if not matching:
            return False
        priority = max(row["priority"] for row in matching)
        return all(row["disposition"] == "prohibited"
                   for row in matching if row["priority"] == priority)
    if prop == "competent_disapproval":
        request = {key: demand["determination"][key]
                   for key in ("regime", "procedure", "issuer", "purpose")}
        return bool(basis["determinations"]) and all(
            all(row.get(k) == v for k, v in request.items())
            and row["disposition"] == "disapproved" for row in basis["determinations"].values()
        )
    if prop == "capacity_horizon":
        required = demand["commitment"]
        horizon = basis["horizons"][required["horizon"]]
        return all(row["capacity"] < required["load"] or row["ready_day"] > horizon
                   for row in basis["alternatives"].values())
    if prop == "competent_roster_absence":
        return all(demand["judgment"]["competence"] not in skills
                   for skills in basis["roster"].values())
    if prop == "independent_provider_absence":
        return basis["subject"] == demand["engagement"]["subject"] and all(
            row["implemented_subject"] is True or row["financial_interest"] is True
            for row in basis["providers"].values()
        )
    return False


def reference_terminal_knowledge(
    case: Mapping[str, Any], receipt: NonDataReceipt, *, mutant: str | None = None
) -> Literal["none", "provisional", "deeper"]:
    """Recompute bounded reference knowledge without inventing an AQ1 state.

    The sealed fixture-owner basis is separate from the candidate's claimed
    search coverage. Branch properties are evaluated on actual finite evidence;
    a changed label, timeout, favorable signature or missing response is not proof.
    """
    boundary = case["terminal_evidence"]
    if boundary is None:
        return "none"
    if mutant == MUTANTS[4] and "timeout_seconds" in boundary:
        return "deeper"
    if receipt.resolution_state != "reentry_provisional_refusal":
        return "provisional"
    required = {
        "kind", "scope", "epoch", "valid_until", "rule", "basis_hash", "searched",
        "unknown_remainder", "challenger", "reentry_requires",
    }
    basis = case.get("terminal_basis")
    if set(boundary) != required or not isinstance(basis, dict):
        return "provisional"
    digest = hashlib.sha256(json.dumps(basis, sort_keys=True, separators=(",", ":")).encode())
    if boundary["basis_hash"] != digest.hexdigest():
        return "provisional"
    try:
        universe = _basis_members(case)
    except (KeyError, TypeError, ValueError):
        return "provisional"
    if not universe or len(set(universe)) != len(universe):
        return "provisional"
    if sorted(boundary["searched"]) != sorted(universe):
        return "provisional"
    if boundary["unknown_remainder"] or boundary["scope"] != receipt.request.claim_ref:
        return "provisional"
    use = receipt.request.requested_use
    if use is None or boundary["epoch"] != use.reference_epoch_ref:
        return "provisional"
    if boundary["rule"] != use.rule_version_ref:
        return "provisional"
    if _time(boundary["valid_until"]) <= receipt.evaluated_at:
        return "provisional"
    if boundary["challenger"] != "synthetic:independent-challenger":
        return "provisional"
    if boundary["reentry_requires"] != "new_boundary_evidence":
        return "provisional"
    try:
        return "deeper" if _finite_boundary_holds(basis, case["demand"]) else "provisional"
    except (KeyError, TypeError, ValueError, IndexError):
        return "provisional"


class _MutationRuntime(NonDataAcquisitionRuntime):
    """Instrument-only runtime substitutions; each changes the actual CAS result."""

    mutant: str | None = None
    row_count = 0

    def _owners_accept(self, **kwargs: Any) -> bool:
        if self.mutant == MUTANTS[1]:
            return True
        return super()._owners_accept(**kwargs)

    def _admit(self, request: NonDataRequest, at: datetime) -> tuple[Any, ...]:
        result = super()._admit(request, at)
        shape, candidate, context, _ = result
        if self.mutant == MUTANTS[3] and candidate is not None and context is not None:
            if context.requested_use.population_ref != candidate.ceiling.population_ref:
                return shape, None, None, ("ceiling_refused",)
        return result

    def _result(
        self, request: NonDataRequest, at: datetime, *, emit_intermediate: bool
    ) -> NonDataReceipt:
        result = super()._result(request, at, emit_intermediate=emit_intermediate)
        rows_close = self.mutant == MUTANTS[0] and self.row_count > 0
        removal = self.mutant == MUTANTS[6]
        if (rows_close or removal) and result.reason_codes == ("non_data_object_missing",):
            return result.model_copy(update={"resolution_state": "reentry_closed", "reason_codes": ()})
        return result


def execute_case(
    case: Mapping[str, Any], vocabulary: Mapping[str, Any], scratch: Path,
    *, mutant: str | None = None,
) -> AcquisitionObservation:
    """Execute AQ1 intake/CAS/re-entry and recompute its persisted consumer result."""
    if mutant is not None and mutant not in MUTANTS:
        raise ValueError("unknown_mutant")
    owner = _ReferenceDemandingOwner(case, mutant)
    store = FileSystemCAS(scratch / "cas")
    runtime = _MutationRuntime(
        store=store, journal_path=scratch / "events.jsonl",
        demanding_owner=owner if case.get("owner_available", True) else None,
        independent_verifier=_ReferenceVerifier(case),
    )
    runtime.mutant = mutant
    runtime.row_count = case["row_count"]
    candidate_ref = None
    vocabulary_ref = None
    ceiling_fact = "not_evaluated"
    at = _time(case["evaluated_at"])
    if case["candidate"] is not None:
        candidate_ref = runtime.persist_candidate({
            "object_type": case["discriminator"], "demand_hash": demand_hash(case["demand"]),
            "body": case["candidate"], "ceiling": case["candidate_ceiling"],
        })
        vocabulary_ref = runtime.persist_vocabulary(vocabulary)
        relation = evaluate_ceiling(
            vocabulary=CeilingVocabulary.model_validate(vocabulary),
            requested=CeilingScope.model_validate(case["requested_use"]),
            ceiling=CeilingScope.model_validate(case["candidate_ceiling"]), at=at,
        )
        refused = [name for name, passed in relation.relations.items() if not passed]
        if mutant == MUTANTS[3] and not refused:
            refused = ["population"]
        ceiling_fact = "refused:" + ",".join(refused) if refused else "permitted"
        if not relation.exact_controls:
            ceiling_fact = "refused:exact_controls"
    request = NonDataRequest(
        request_id=case["case_id"], claim_ref="synthetic:claim", gap_id="synthetic:gap",
        demand=case["demand"], candidate_ref=candidate_ref, vocabulary_ref=vocabulary_ref,
        requested_use=case["requested_use"],
    )
    receipt = runtime.acquire(request, at=at, row_count=case["row_count"])
    consumed = runtime.verify_receipt(receipt.artifact_ref)
    if consumed != receipt or not store.get_bytes(receipt.artifact_ref):
        raise ValueError("persisted_consumer_assertion_failed")
    journal_path = scratch / "events.jsonl"
    new_rules = {event["rule"] for event in case["events"]
                 if event["rule"] != request.requested_use.rule_version_ref
                 and event["producer"] == "synthetic:producer"
                 and event["claim"] == request.claim_ref}
    if len(new_rules) == 1:
        historical_ref = receipt.artifact_ref
        next_rule = next(iter(new_rules))
        current_use = request.requested_use.model_copy(update={"rule_version_ref": next_rule})
        current_request = request.model_copy(update={
            "request_id": request.request_id + ":current", "requested_use": current_use,
        })
        current_owner = _ReferenceDemandingOwner(case, mutant)
        current_runtime = _MutationRuntime(
            store=store, journal_path=scratch / "current-events.jsonl",
            demanding_owner=current_owner, independent_verifier=_ReferenceVerifier(case),
        )
        current_runtime.mutant = mutant
        receipt = current_runtime.acquire(current_request, at=at)
        if current_runtime.verify_receipt(receipt.artifact_ref) != receipt:
            raise ValueError("current_rule_consumer_recomputation_failed")
        if runtime.verify_receipt(historical_ref).artifact_ref != historical_ref:
            raise ValueError("old_rule_history_rewritten")
        owner = current_owner
        owner.event_effect = "rule_revalidation"
        journal_path = scratch / "current-events.jsonl"
        ceiling_fact = "refused:exact_controls"
    events = [json.loads(line) for line in journal_path.read_text().splitlines()]
    if events[-1]["artifact_ref"] != receipt.artifact_ref:
        raise ValueError("persisted_event_artifact_binding_failed")
    if len(events) not in (1, 2) or (
        len(events) == 2 and events[0]["resolution_state"] != "admitted_reentry_required"
    ):
        raise ValueError("duplicate_event_authority_multiplication")
    event_effect = owner.event_effect
    if not case.get("owner_available", True):
        event_effect = "owner_unavailable"
    authority = receipt.authority_granted or (
        mutant == MUTANTS[5] and receipt.resolution_state == "reentry_closed"
    )
    return AcquisitionObservation(
        case_id=case["case_id"], shape=receipt.shape.outcome,
        types=",".join(receipt.shape.acquisition_types) or "-", state=receipt.resolution_state,
        terminal=reference_terminal_knowledge(case, receipt, mutant=mutant), ceiling=ceiling_fact,
        authority="true" if authority else "false",
        signer="empty" if receipt.institutional_signer is None else "present",
        reentry="performed" if owner.reentry_calls else "absent", event=event_effect,
        reason=",".join(receipt.reason_codes) or "-", receipt_ref=receipt.artifact_ref,
        consumer_recomputed=True,
    )


def run_corpus(
    corpus: Mapping[str, Any], scratch: Path, *, mutant: str | None = None
) -> tuple[AcquisitionObservation, ...]:
    """Run the complete input denominator; no expected result enters this function."""
    return tuple(
        execute_case(case, corpus["vocabulary"], scratch / case["case_id"], mutant=mutant)
        for case in corpus["cases"]
    )


def observation_wire(observations: tuple[AcquisitionObservation, ...]) -> str:
    """Encode actual observations for a separate-process independent comparator."""
    return "\t".join(WIRE_FIELDS) + "\n" + "\n".join(row.wire_row() for row in observations) + "\n"


def data_availability_positive_control(scratch: Path) -> tuple[bool, bool]:
    """Observe a genuine finite-data predicate change through admitted CAS bytes.

    This separate ordinary data gap is outside the 63 non-data cases. The
    synthetic demand needs an observation of each treatment assignment, and no
    record exists before acquisition. A real persisted observation supplies it.
    """
    store = FileSystemCAS(scratch / "cas")
    required_assignments = {0, 1}

    def available(ref: str | None) -> bool:
        if ref is None:
            return False
        raw = store.get_bytes(ref)
        if ref != "sha256:" + hashlib.sha256(raw).hexdigest():
            return False
        observations = json.loads(raw)
        if observations.get("subject") != "synthetic:data-availability":
            return False
        records = observations.get("observations", [])
        return ({row["assignment"] for row in records} == required_assignments
                and all(type(row["outcome"]) in (int, float) for row in records))

    before = available(None)
    payload = {"subject": "synthetic:data-availability", "observations": [
        {"assignment": 0, "outcome": 1}, {"assignment": 1, "outcome": 2},
    ]}
    ref = store.put_bytes(json.dumps(payload, sort_keys=True).encode(), opts=PutOptions(
        kind="gy.as1.synthetic_observations", media_type="application/json",
        schema=SchemaInfo(name="gy.as1.synthetic_observations", version="1"),
    ))
    return before, available(str(ref.artifact_id))
