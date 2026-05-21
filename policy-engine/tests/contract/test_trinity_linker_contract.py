from __future__ import annotations

from decimal import Decimal

from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.registry_fragments import RegistryBundle

from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ConstraintSpec as ProblemConstraintSpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
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
    ConstraintSpec,
    MechanismTypeRegistry,
    MechanismTypeSpec,
    ParamSpec,
    ParamType,
)
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.linker import LinkIssueCode, link_trinity
from polisyos.ir.trinity import TrinityBundle

CTX_REF = "sha256:" + "0" * 64


def _base_model_spec() -> ModelSpec:
    return ModelSpec(model_id="model_1", data_snapshot_ref=CTX_REF)


def _base_problem_frame() -> ProblemFrame:
    return ProblemFrame(problem_id="problem_1", domain=ProblemDomain.FISCAL)


def _base_selector() -> SelectorPredicate:
    return SelectorPredicate(field="id", operator="==", value="all")


def _base_schedule() -> ScheduleSpec:
    return ScheduleSpec(start_step=0, duration_steps=1)


def _bundle_with_interventions(interventions: list[InterventionSpec]) -> TrinityBundle:
    return TrinityBundle(
        problem_frame=_base_problem_frame(),
        policy_spec=PolicySpec(policy_id="policy_1", interventions=interventions),
        model_spec=_base_model_spec(),
    )


def _default_registries() -> RegistryBundle:
    return RegistryBundle(
        mechanisms=DEFAULT_MECHANISM_REGISTRY,
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=ConstraintRegistry(constraints={}),
    )


def test_default_metric_registry_accepts_real_nl_policy_outcome_metrics() -> None:
    outcome_metric_ids = [
        "sme_survival_rate",
        "msme_survival_rate",
        "msme_loan_volume",
        "employment_stability",
        "employment_retention_rate",
        "reconstruction_speed",
        "fraud_incidence_rate",
        "ate_estimate",
        "causal_pathway_count",
        "model_transport_score",
    ]
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_real_nl_metrics",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id=f"objective_{metric_id}",
                    metric_id=metric_id,
                    direction="maximize" if metric_id != "fraud_incidence_rate" else "minimize",
                )
                for metric_id in outcome_metric_ids
            ],
        ),
        policy_spec=PolicySpec(policy_id="policy_real_nl_metrics", interventions=[]),
        model_spec=_base_model_spec(),
    )

    _, report = link_trinity(bundle, _default_registries())

    assert not [
        issue
        for issue in report.issues
        if issue.code == LinkIssueCode.UNKNOWN_METRIC
    ]


def test_linker_reports_unknown_mechanism() -> None:
    bundle = _bundle_with_interventions(
        [
            InterventionSpec(
                intervention_id="int_1",
                kind="unknown_mech",
                target=_base_selector(),
                schedule=_base_schedule(),
                params={},
            )
        ]
    )
    registries = _default_registries()
    _, report = link_trinity(bundle, registries)
    assert any(
        issue.code == LinkIssueCode.UNKNOWN_MECHANISM
        and issue.path == ["policy_spec", "interventions", 0, "kind"]
        and issue.ids.get("intervention_id") == "int_1"
        for issue in report.issues
    )


def test_linker_reports_unknown_mechanism_without_skipping_selector_validation() -> None:
    bundle = _bundle_with_interventions(
        [
            InterventionSpec(
                intervention_id="int_1",
                kind="unknown_mech",
                target=SelectorPredicate(field="ghost", operator="==", value="all"),
                schedule=_base_schedule(),
                params={},
            )
        ]
    )
    registries = _default_registries()
    _, report = link_trinity(bundle, registries)
    codes = {issue.code for issue in report.issues}

    assert LinkIssueCode.UNKNOWN_MECHANISM in codes
    assert LinkIssueCode.UNKNOWN_SELECTOR_FIELD in codes


def test_linker_reports_missing_param() -> None:
    bundle = _bundle_with_interventions(
        [
            InterventionSpec(
                intervention_id="int_1",
                kind="tax_subsidy",
                target=_base_selector(),
                schedule=_base_schedule(),
                params={},
            )
        ]
    )
    registries = _default_registries()
    _, report = link_trinity(bundle, registries)
    assert any(issue.code == LinkIssueCode.MISSING_PARAM for issue in report.issues)


def test_linker_resolves_nested_param_paths_and_rejects_dotted_field_names() -> None:
    mech_registry = MechanismTypeRegistry(
        mechanisms={
            "custom": MechanismTypeSpec(
                mechanism_id="custom",
                params={
                    "config.rate": ParamSpec(
                        param_id="config.rate",
                        required=True,
                        value_type=ParamType.DECIMAL,
                    )
                },
            )
        }
    )
    nested_bundle = _bundle_with_interventions(
        [
            InterventionSpec(
                intervention_id="int_nested",
                kind="custom",
                target=_base_selector(),
                schedule=_base_schedule(),
                params={"config": {"rate": Decimal("0.2")}},
            )
        ]
    )
    dotted_bundle = _bundle_with_interventions(
        [
            InterventionSpec(
                intervention_id="int_dotted",
                kind="custom",
                target=_base_selector(),
                schedule=_base_schedule(),
                params={"config.rate": Decimal("0.2")},
            )
        ]
    )
    registries = RegistryBundle(
        mechanisms=mech_registry,
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=ConstraintRegistry(constraints={}),
    )

    _, nested_report = link_trinity(nested_bundle, registries)
    _, dotted_report = link_trinity(dotted_bundle, registries)

    assert not any(issue.code == LinkIssueCode.MISSING_PARAM for issue in nested_report.issues)
    assert any(issue.code == LinkIssueCode.PARAM_PATH for issue in dotted_report.issues)


def test_linker_reports_missing_slot() -> None:
    mech_registry = MechanismTypeRegistry(
        mechanisms={
            "custom": MechanismTypeSpec(
                mechanism_id="custom",
                reads_slots=["missing.slot"],
                writes_slots=["missing.slot"],
            )
        }
    )
    bundle = _bundle_with_interventions(
        [
            InterventionSpec(
                intervention_id="int_1",
                kind="custom",
                target=_base_selector(),
                schedule=_base_schedule(),
                params={},
            )
        ]
    )
    registries = RegistryBundle(
        mechanisms=mech_registry,
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=ConstraintRegistry(constraints={}),
    )
    _, report = link_trinity(bundle, registries)
    assert any(issue.code == LinkIssueCode.MISSING_SLOT for issue in report.issues)


def test_linker_schedule_overlap_uses_inclusive_interval_boundaries() -> None:
    slot_registry = DEFAULT_SLOT_REGISTRY.model_copy(
        update={
            "slots": {
                "conflict.slot": DEFAULT_SLOT_REGISTRY.slots["global.tax_rate"].model_copy(
                    update={
                        "slot_id": "conflict.slot",
                        "merge_rule": DEFAULT_SLOT_REGISTRY.slots[
                            "global.tax_rate"
                        ].merge_rule.model_copy(update={"rule_id": "error"}),
                    }
                )
            }
        }
    )
    mech_registry = MechanismTypeRegistry(
        mechanisms={
            "custom": MechanismTypeSpec(
                mechanism_id="custom",
                writes_slots=["conflict.slot"],
            )
        }
    )
    registries = RegistryBundle(
        mechanisms=mech_registry,
        slots=slot_registry,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=ConstraintRegistry(constraints={}),
    )
    non_overlapping = _bundle_with_interventions(
        [
            InterventionSpec(
                intervention_id="left",
                kind="custom",
                target=_base_selector(),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={},
            ),
            InterventionSpec(
                intervention_id="right",
                kind="custom",
                target=_base_selector(),
                schedule=ScheduleSpec(start_step=1, duration_steps=1),
                params={},
            ),
        ]
    )
    overlapping = _bundle_with_interventions(
        [
            InterventionSpec(
                intervention_id="left",
                kind="custom",
                target=_base_selector(),
                schedule=ScheduleSpec(start_step=0, duration_steps=2),
                params={},
            ),
            InterventionSpec(
                intervention_id="right",
                kind="custom",
                target=_base_selector(),
                schedule=ScheduleSpec(start_step=1, duration_steps=1),
                params={},
            ),
        ]
    )

    _, non_overlapping_report = link_trinity(non_overlapping, registries)
    _, overlapping_report = link_trinity(overlapping, registries)

    assert not any(
        issue.code == LinkIssueCode.MERGE_RULE_CONFLICT for issue in non_overlapping_report.issues
    )
    assert any(
        issue.code == LinkIssueCode.MERGE_RULE_CONFLICT for issue in overlapping_report.issues
    )


def test_linker_reports_unknown_selector_field() -> None:
    bundle = _bundle_with_interventions(
        [
            InterventionSpec(
                intervention_id="int_1",
                kind="income_tax",
                target=SelectorPredicate(field="ghost", operator="==", value="all"),
                schedule=_base_schedule(),
                params={"rate": Decimal("0.1")},
            )
        ]
    )
    registries = _default_registries()
    _, report = link_trinity(bundle, registries)
    assert any(issue.code == LinkIssueCode.UNKNOWN_SELECTOR_FIELD for issue in report.issues)


def test_linker_reports_unknown_unit() -> None:
    mech_registry = MechanismTypeRegistry(
        mechanisms={
            "custom": MechanismTypeSpec(
                mechanism_id="custom",
                params={
                    "value": ParamSpec(
                        param_id="value",
                        required=True,
                        value_type=ParamType.DECIMAL,
                        unit_id="missing_unit",
                    )
                },
            )
        }
    )
    bundle = _bundle_with_interventions(
        [
            InterventionSpec(
                intervention_id="int_1",
                kind="custom",
                target=_base_selector(),
                schedule=_base_schedule(),
                params={"value": Decimal("1")},
            )
        ]
    )
    registries = RegistryBundle(
        mechanisms=mech_registry,
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=ConstraintRegistry(constraints={}),
    )
    _, report = link_trinity(bundle, registries)
    assert any(issue.code == LinkIssueCode.UNKNOWN_UNIT for issue in report.issues)


def test_linker_emits_unused_registry_diagnostics() -> None:
    registries = RegistryBundle(
        mechanisms=MechanismTypeRegistry(
            mechanisms={
                "custom": MechanismTypeSpec(
                    mechanism_id="custom",
                    writes_slots=["global.tax_rate"],
                )
            }
        ),
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=ConstraintRegistry(
            constraints={"custom_limit": ConstraintSpec(constraint_id="custom_limit")}
        ),
    )
    bundle = TrinityBundle(
        problem_frame=_base_problem_frame(),
        policy_spec=PolicySpec(policy_id="policy_unused", interventions=[]),
        model_spec=_base_model_spec(),
    )

    _, report = link_trinity(bundle, registries)
    codes = {issue.code for issue in report.issues}

    assert LinkIssueCode.UNUSED_REGISTRY in codes
    assert LinkIssueCode.UNUSED_MECHANISM in codes
    assert LinkIssueCode.UNUSED_SLOT in codes
    assert LinkIssueCode.UNUSED_CONSTRAINT in codes


def test_linker_outputs_are_deterministic_across_repeated_runs() -> None:
    registries = RegistryBundle(
        mechanisms=MechanismTypeRegistry(
            mechanisms={
                "custom": MechanismTypeSpec(
                    mechanism_id="custom",
                    writes_slots=["global.tax_rate"],
                    params={
                        "config.rate": ParamSpec(
                            param_id="config.rate",
                            required=True,
                            value_type=ParamType.DECIMAL,
                        )
                    },
                )
            }
        ),
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=ConstraintRegistry(constraints={}),
    )
    bundle = _bundle_with_interventions(
        [
            InterventionSpec(
                intervention_id="int_1",
                kind="custom",
                target=SelectorPredicate(field="ghost", operator="==", value="all"),
                schedule=_base_schedule(),
                params={"config.rate": Decimal("0.1")},
            )
        ]
    )

    linked_a, report_a = link_trinity(bundle, registries)
    linked_b, report_b = link_trinity(bundle, registries)

    assert linked_a.model_dump(mode="json") == linked_b.model_dump(mode="json")
    assert report_a.model_dump(mode="json") == report_b.model_dump(mode="json")


def test_linker_reports_incompatible_constraint() -> None:
    constraint_registry = ConstraintRegistry(
        constraints={
            "budget_limit": ConstraintSpec(
                constraint_id="budget_limit", unit_id="usd", slot_id=None
            )
        }
    )
    problem_frame = ProblemFrame(
        problem_id="problem_1",
        domain=ProblemDomain.FISCAL,
        hard_constraints=[
            ProblemConstraintSpec(
                constraint_id="budget_limit",
                value=MoneyValue(amount=Decimal("10"), currency="UAH"),
            )
        ],
    )
    bundle = TrinityBundle(
        problem_frame=problem_frame,
        policy_spec=PolicySpec(policy_id="policy_1", interventions=[]),
        model_spec=_base_model_spec(),
    )
    registries = RegistryBundle(
        mechanisms=DEFAULT_MECHANISM_REGISTRY,
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=constraint_registry,
    )
    _, report = link_trinity(bundle, registries)
    assert any(issue.code == LinkIssueCode.INCOMPATIBLE_CONSTRAINT for issue in report.issues)
