"""Configured CAS intake and actual orchestrator/cache current/history consumers."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir import UncertaintyType
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import FunnelStage, FunnelStageResult
from polisyos.scientist.methods.search.uncertainty import (
    SearchUncertaintyBasis,
    SearchUncertaintyObservation,
    UncertaintyEnvelope,
    UncertaintyEstimate,
    persist_search_uncertainty,
)


class ProducerStage(FunnelStage):
    """Permitted injected callback on the actual orchestrator, not its surrogate."""

    def __init__(self, level, result):
        self.level, self.result, self.calls = level, result, 0

    @property
    def stage_name(self):
        return f"producer-{self.level}"

    @property
    def fidelity_level(self):
        return self.level

    @property
    def estimated_cost_usd(self):
        return 0.0

    def evaluate(self, candidate, context):
        self.calls += 1
        return replace(self.result, policy_candidate=candidate)


def _envelope(level):
    return UncertaintyEnvelope.from_partial(
        {
            kind: UncertaintyEstimate(
                level=level,
                source="fixture producer",
                quantification_method="supplied fixture measurement",
                is_reducible=True,
            )
            for kind in UncertaintyType
        }
    )


@pytest.fixture
def packet(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")

    def ref(name):
        return store.put_json(
            {"fixture": name}, PutOptions(kind="scientist.test", media_type="application/json")
        )

    basis = SearchUncertaintyBasis(
        subject_ref=ref("candidate"),
        value_ref=ref("value"),
        input_refs=(ref("input"),),
        rule_ref=ref("rule"),
        producer_ref=ref("producer"),
        valid_time=datetime(2026, 10, 8, tzinfo=UTC),
        estimand="ATE",
        unit="kg",
    )
    basis_ref = persist_search_uncertainty(store, basis)

    def stage(level, envelope, *, supplied_basis=basis_ref, producer=None, risk=None):
        observation = SearchUncertaintyObservation(
            basis_ref=supplied_basis,
            producer_ref=producer or basis.producer_ref,
            risk_ref=risk or ref(f"risk-{level}"),
            envelope=envelope,
        )
        observation_ref = persist_search_uncertainty(store, observation)
        return ProducerStage(
            level,
            FunnelStageResult(
                policy_candidate={},
                objective_value=1.0,
                is_promising=True,
                stage_name=f"producer-{level}",
                fidelity_level=level,
                uncertainty_envelope=envelope,
                uncertainty_observation_ref=observation_ref,
            ),
        )

    return store, basis, basis_ref, ref, stage


def _context(packet):
    store, basis, basis_ref, _, _ = packet
    return {
        "store": store,
        "uncertainty_basis_ref": basis_ref,
        "policy_candidate_ref": basis.subject_ref,
    }


def test_configured_intake_retains_independent_risk_and_ordinary_history(packet):
    _, _, _, _, stage = packet
    early, late = stage(0, _envelope(0.9)), stage(1, _envelope(0.1))
    runtime = FunnelOrchestrator([early, late])
    ticket = runtime.submit({"candidate": "a"}, _context(packet))
    outcome = runtime.advance(ticket)
    assert outcome.current_uncertainty_envelope == _envelope(0.9)
    assert outcome.uncertainty_envelope == _envelope(0.9)
    assert outcome.uncertainty_intake_failures == []
    assert len(outcome.uncertainty_observation_refs) == 2
    assert (
        outcome.final_result.feedback["uncertainty_refinement_status"]
        == "producer_law_not_established"
    )
    assert early.result.feedback == late.result.feedback == {}
    # A fresh outcome reader resolves the persisted objects again.
    assert runtime.get_outcome(ticket).current_uncertainty_envelope == _envelope(0.9)


@pytest.mark.parametrize(
    "field",
    [
        "value_ref",
        "input_refs",
        "rule_ref",
        "valid_time",
        "unit",
        "estimand",
        "subject_ref",
        "producer_ref",
    ],
)
def test_changed_producer_basis_cannot_lower_same_ticket_risk(packet, field):
    store, basis, basis_ref, ref, stage = packet
    change = {
        "unit": "USD",
        "estimand": "foreign population",
        "valid_time": datetime(2027, 1, 1, tzinfo=UTC),
        "input_refs": (ref("foreign-input"),),
    }
    foreign = basis.model_copy(update={field: change.get(field, ref("foreign"))})
    foreign_ref = persist_search_uncertainty(store, foreign)
    early, late = stage(0, _envelope(0.9)), stage(1, _envelope(0.1), supplied_basis=foreign_ref)
    runtime = FunnelOrchestrator([early, late])
    outcome = runtime.advance(runtime.submit({}, _context(packet)))
    assert outcome.current_uncertainty_envelope is None
    assert outcome.uncertainty_envelope == _envelope(0.9)
    assert "foreign or stale basis" in outcome.uncertainty_intake_failures[0]
    assert outcome.final_result.feedback["uncertainty_current_status"] == "not_established"


def test_missing_and_substituted_envelope_do_not_become_current(packet):
    _, _, _, _, stage = packet
    producer = stage(0, _envelope(0.9))
    producer.result = replace(producer.result, uncertainty_envelope=_envelope(0.1))
    runtime = FunnelOrchestrator([producer])
    outcome = runtime.advance(runtime.submit({}, _context(packet)))
    assert outcome.current_uncertainty_envelope is None
    assert "differs from the stage envelope" in outcome.uncertainty_intake_failures[0]
    producer.result = replace(producer.result, uncertainty_observation_ref=None)
    runtime = FunnelOrchestrator([producer])
    outcome = runtime.advance(runtime.submit({}, _context(packet)))
    assert outcome.current_uncertainty_envelope is None
    assert outcome.final_result.feedback["uncertainty_current"] is None


def test_same_request_reuses_real_cache_changed_version_executes_callback(packet):
    store, basis, _, _, stage = packet
    producer = stage(0, _envelope(0.3))
    runtime = FunnelOrchestrator([producer])
    context = _context(packet)
    first = runtime.submit({"a": 1}, context)
    runtime.advance(first)
    second = runtime.submit({"a": 1}, context)
    runtime.advance(second)
    assert producer.calls == 1
    changed = persist_search_uncertainty(store, basis.model_copy(update={"unit": "USD"}))
    third = runtime.submit({"a": 1}, {**context, "uncertainty_basis_ref": changed})
    outcome = runtime.advance(third)
    assert producer.calls == 2
    assert outcome.current_uncertainty_envelope is None


def test_selected_manifest_view_change_executes_real_callback(packet):
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.canon import CanonSpec

    store, basis, basis_ref, _, stage = packet
    producer = stage(0, _envelope(0.3))
    runtime = FunnelOrchestrator([producer])
    context = _context(packet)
    runtime.advance(runtime.submit({"a": 1}, context))
    different_view = store.put_json(
        basis,
        PutOptions(
            kind="scientist.search.uncertainty_basis",
            media_type="application/json",
            schema=SchemaInfo(name="SameScientificContentDifferentView", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    assert different_view.artifact_id == basis_ref.artifact_id
    assert different_view.manifest_profile_sha256 != basis_ref.manifest_profile_sha256
    outcome = runtime.advance(
        runtime.submit({"a": 1}, {**context, "uncertainty_basis_ref": different_view})
    )
    assert producer.calls == 2
    assert outcome.current_uncertainty_envelope is None
    assert "foreign or stale basis" in outcome.uncertainty_intake_failures[0]
