from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.interventions import (
    InterventionContext,
    NodeIntervention,
    QueryTarget,
    VariableAssignment,
    identification_plan_for_intervention,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    ConstraintRegistry,
)
from polisyos.ir.linker import LinkedIntervention, link_trinity
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.registry.registry_fragments import RegistryBundle
from polisyos.ir.trinity import TrinityBundle
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.intervention_atom_binding import (
    INTERVENTION_ATOM_BINDING_SCHEMA_VERSION,
    InterventionAtomBinding,
    InterventionAtomBindingError,
    _content_payload_from_fields,
    build_intervention_atom_binding,
    consume_intervention_atom_for_cycle,
    intervention_atom_target_selector_ref,
    persist_intervention_atom_binding,
)


def _ref(char: str) -> str:
    return "sha256:" + char * 64


def _intervention(**overrides: Any) -> InterventionSpec:
    payload: dict[str, Any] = {
        "intervention_id": "credit_access_subsidy",
        "kind": "tax_subsidy",
        "target": SelectorPredicate(
            field="id",
            operator=SelectorOperator.EQUALS,
            value="all",
        ),
        "schedule": ScheduleSpec(start_step=0, duration_steps=4),
        "params": {"rate": Decimal("0.20")},
        "priority": 1,
        "lex_provision_ref": "lex://ua/msme-credit-guarantee/section-4",
        "target_population_type": "wartime_msme",
        "target_sector_ids": ["manufacturing"],
        "target_region_ids": ["UA-30"],
        "measurement_expectations": {
            "legacy_note": "Track firm survival after credit access changes.",
        },
    }
    payload.update(overrides)
    return InterventionSpec.model_validate(payload)


def _bundle(intervention: InterventionSpec) -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_ua_msme_credit", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_ua_msme_credit",
            problem_frame_ref=_ref("a"),
            interventions=[intervention],
        ),
        model_spec=ModelSpec(model_id="model_ua_msme", data_snapshot_ref=_ref("b")),
    )


def _registries() -> RegistryBundle:
    return RegistryBundle(
        mechanisms=DEFAULT_MECHANISM_REGISTRY,
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=ConstraintRegistry(constraints={}),
    )


def _linked(intervention: InterventionSpec) -> LinkedIntervention:
    linked_bundle, report = link_trinity(_bundle(intervention), _registries())
    assert report.ok, [issue.model_dump(mode="json") for issue in report.issues]
    return linked_bundle.bindings.interventions[0]


def _node(variable: str = "agents.income") -> NodeIntervention:
    return NodeIntervention(
        assignments=(VariableAssignment(variable=variable, value_expr="income + subsidy(rate)"),)
    )


def _query_target() -> QueryTarget:
    return QueryTarget(
        outcome_variables=("firm_survival",),
        conditioning=("baseline_credit_access",),
        functional="average_treatment_effect",
    )


def _context(intervention: InterventionSpec, *, selector_ref: str | None = None) -> InterventionContext:
    return InterventionContext(
        source_domain="observed_ua_msme_panel",
        target_domain="wartime_msme",
        selection_diagram_ref=selector_ref or intervention_atom_target_selector_ref(intervention),
        available_data_refs=("data_snapshot:ua_msme_credit_panel",),
        assumptions=("target_selector_content_bound",),
    )


def _build_atom(
    *,
    intervention: InterventionSpec | None = None,
    linked: LinkedIntervention | None = None,
    causal: NodeIntervention | None = None,
    context: InterventionContext | None = None,
    operator_map: dict[str, str] | None = None,
    mechanism_variable_map: dict[str, tuple[str, ...]] | None = None,
) -> InterventionAtomBinding:
    intervention = intervention or _intervention()
    causal = causal or _node()
    return build_intervention_atom_binding(
        problem_frame_ref=_ref("a"),
        policy_spec_ref=_ref("c"),
        intervention=intervention,
        linked_intervention=linked or _linked(intervention),
        causal_intervention=causal,
        query_target=_query_target(),
        identification_plan=identification_plan_for_intervention(causal),
        causal_context=context or _context(intervention),
        world_model_record_ref="world_model_record_ua_msme_v1",
        producer_ref="scientist.policy_design.candidate:credit_access_subsidy",
        provenance_refs=("trinity_bundle:policy_ua_msme_credit", "proof_kernel:node_do_income"),
        operator_proof_type_map=operator_map or {"tax_subsidy": "node"},
        mechanism_variable_map=mechanism_variable_map,
        estimand_metric_id="msme_survival_rate",
        estimand_unit_id="ratio",
        source_population="observed_ua_msme_panel",
        target_population="wartime_msme",
        mechanism_config_overrides={"merge_policy": "sum_income_delta"},
        transform_refs=("transform:subsidy_rate_to_income_delta",),
        coerce_refs=("coerce:decimal_rate",),
    )


def test_candidate_action_binds_to_content_addressed_atom_and_round_trips() -> None:
    intervention = _intervention()
    causal = _node()
    atom = _build_atom(intervention=intervention, causal=causal)

    assert atom.schema_version == INTERVENTION_ATOM_BINDING_SCHEMA_VERSION
    assert atom.causal_do_expr.assignments[0].variable == "agents.income"
    assert atom.intended_downstream_estimand.outcome_variables == ("firm_survival",)
    assert atom.target_world_slots == ("agents.income", "government.balance")
    assert atom.content_hash.startswith("sha256:")
    assert atom.measurement_expectations_authority == "supporting_metadata"
    assert atom.authoritative_action_outcome_link == atom.intended_downstream_estimand

    trinity_round_trip = atom.to_trinity_intervention_spec()
    causal_round_trip = atom.to_node_intervention()

    assert trinity_round_trip.model_dump(mode="json") == intervention.model_dump(mode="json")
    assert causal_round_trip.model_dump(mode="json") == causal.model_dump(mode="json")


def test_atom_persists_as_a_typed_artifact(tmp_path) -> None:
    atom = _build_atom()
    store = FileSystemCAS(tmp_path / "cas")

    ref = persist_intervention_atom_binding(store, atom)

    assert str(ref.artifact_id).startswith("sha256:")
    assert ref.kind == "runtime.quality.intervention_atom_binding"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("target_selector", "target_selector_context_mismatch"),
        ("writes_slots", "world_slot_do_variable_mismatch"),
        ("operator", "operator_kind_mismatch"),
        ("mechanism_variable", "mechanism_do_variable_mismatch"),
    ],
)
def test_mismatched_halves_fail_closed_for_content_reasons(mutation: str, code: str) -> None:
    intervention = _intervention()
    causal = _node()
    linked = _linked(intervention)
    context = _context(intervention)
    operator_map = {"tax_subsidy": "node"}
    mechanism_variable_map: dict[str, tuple[str, ...]] | None = None

    if mutation == "target_selector":
        other = _intervention(
            target=SelectorPredicate(
                field="sector",
                operator=SelectorOperator.EQUALS,
                value="agriculture",
            )
        )
        context = _context(intervention, selector_ref=intervention_atom_target_selector_ref(other))
    elif mutation == "writes_slots":
        linked = linked.model_copy(update={"writes_slots": ["government.balance"]})
    elif mutation == "operator":
        operator_map = {"tax_subsidy": "conditional"}
    elif mutation == "mechanism_variable":
        mechanism_variable_map = {"tax_subsidy": ("government.balance",)}

    with pytest.raises(InterventionAtomBindingError, match=code):
        _build_atom(
            intervention=intervention,
            linked=linked,
            causal=causal,
            context=context,
            operator_map=operator_map,
            mechanism_variable_map=mechanism_variable_map,
        )


def test_consistent_halves_bind_after_negative_variants() -> None:
    atom = _build_atom()

    assert atom.status == "candidate_unverified"
    assert atom.operator_kind.trinity_kind == "tax_subsidy"
    assert atom.operator_kind.proof_kernel_type == "node"


def test_content_hash_binds_direct_effect_bundle_to_causal_path() -> None:
    atom = _build_atom()
    tampered = atom.model_dump(mode="json")
    tampered["direct_effect_bundle"]["params"]["rate"] = "0.35"

    with pytest.raises(ValueError, match="content_hash_mismatch"):
        InterventionAtomBinding.model_validate(tampered)


def test_schema_version_is_a_constrained_sentinel_even_with_matching_hash() -> None:
    atom = _build_atom()
    payload = atom.model_dump(mode="python", exclude={"atom_id", "content_hash"})
    payload["schema_version"] = "policyos.runtime.intervention_atom_binding.v2"
    content_hash = gy_content_hash(_content_payload_from_fields(payload))
    payload["atom_id"] = f"atom_{content_hash.removeprefix('sha256:')[:16]}"
    payload["content_hash"] = content_hash

    with pytest.raises(ValueError, match="schema_version"):
        InterventionAtomBinding.model_validate(payload)


def test_measurement_expectations_are_not_action_outcome_authority() -> None:
    atom = _build_atom()

    assert atom.measurement_expectations
    assert atom.measurement_expectations_authority == "supporting_metadata"
    assert atom.intended_downstream_estimand.metric_id == "msme_survival_rate"
    assert atom.authoritative_action_outcome_link.metric_id == "msme_survival_rate"


def test_cycle_consumer_reads_atom_fields_needed_by_joint_sim_and_value() -> None:
    atom = _build_atom()

    consumer_input = consume_intervention_atom_for_cycle(atom)

    assert consumer_input.causal_do_expr.assignments[0].variable == "agents.income"
    assert consumer_input.intended_downstream_estimand.outcome_variables == ("firm_survival",)
    assert consumer_input.target_world_slots == ("agents.income", "government.balance")
