from __future__ import annotations

from decimal import Decimal

from polisyos.ir.kernel import (
    ConstraintRegistry,
    ConstraintSpec,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    MechanismTypeRegistry,
    MechanismTypeSpec,
    ParamSpec,
    ParamType,
)
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.linker import LinkIssueCode, link_trinity
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ConstraintSpec as ProblemConstraintSpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.registry_fragments import RegistryBundle
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.kernel import DEFAULT_MECHANISM_REGISTRY, DEFAULT_METRIC_REGISTRY

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
    assert any(
        issue.code == LinkIssueCode.UNKNOWN_SELECTOR_FIELD for issue in report.issues
    )


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
    assert any(
        issue.code == LinkIssueCode.INCOMPATIBLE_CONSTRAINT for issue in report.issues
    )
