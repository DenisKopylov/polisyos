"""Main ``link_trinity`` function and its direct helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.ir.canon import CanonViolation, content_hash, to_canonical_bytes
from polisyos.ir.governance.schedule import schedule_range
from polisyos.ir.kernel.mechanisms import resolve_mechanism_slots

from ._trinity_mechanisms import (
    _collect_selector_fields,
    _validate_constraint_slot,
    _validate_constraint_unit,
    _validate_mechanism_slots,
    _validate_schedule_conflicts,
    _validate_selector_fields,
)
from ._trinity_models import LinkedIntervention, LinkedTrinityBundle, TrinityBindings
from ._trinity_params import _validate_params
from .reports import LinkIssue, LinkIssueCode, LinkReport, LinkSeverity

if TYPE_CHECKING:
    from polisyos.ir.registry_fragments import RegistryBundle
    from polisyos.ir.trinity import TrinityBundle


def link_trinity(
    bundle: TrinityBundle,
    registries: RegistryBundle,
    *,
    allow_extra_params: bool = False,
    strict: bool = True,
) -> tuple[LinkedTrinityBundle, LinkReport]:
    """Resolve a Trinity bundle against registries, returning bound artifacts plus deterministic diagnostics."""
    issues: list[LinkIssue] = []
    notes: dict[str, None] = {}
    missing_registry_emitted: set[str] = set()

    def _add_note(note: str) -> None:
        notes.setdefault(note, None)

    def _emit_warning(
        *,
        code: LinkIssueCode,
        message: str,
        path: list[str | int],
        data: dict[str, Any] | None = None,
    ) -> None:
        issues.append(
            LinkIssue(
                severity=LinkSeverity.WARNING,
                code=code,
                message=message,
                path=path,
                data=data or {},
            )
        )
        _add_note(str(code.value))

    used_mechanisms: set[str] = set()
    used_slots_read: set[str] = set()
    used_slots_write: set[str] = set()
    used_slots_constraints: set[str] = set()
    used_units: set[str] = set()
    used_metrics: set[str] = set()
    used_constraints: set[str] = set()
    used_selector_fields: set[str] = set()

    linked_interventions: list[LinkedIntervention] = []
    intervention_writes: dict[str, tuple[list[str], Any, int | None]] = {}

    def _emit_missing_registry(registry_name: str, path: list[str | int]) -> None:
        if not strict:
            return
        if registry_name in missing_registry_emitted:
            return
        missing_registry_emitted.add(registry_name)
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.MISSING_REGISTRY,
                message=f"Missing required registry '{registry_name}'",
                path=path,
                data={"registry": registry_name},
            )
        )

    # Step A: PolicySpec interventions vs mechanism registry
    if bundle.policy_spec.interventions and registries.mechanisms is None:
        _emit_missing_registry("mechanisms", ["policy_spec", "interventions"])
    if bundle.policy_spec.interventions and registries.slots is None:
        _emit_missing_registry("slots", ["policy_spec", "interventions"])
    if bundle.policy_spec.interventions and registries.selector_fields is None:
        _emit_missing_registry("selector_fields", ["policy_spec", "interventions"])

    mechanisms = registries.mechanisms
    slots = registries.slots
    selector_fields = registries.selector_fields
    units = registries.units

    for idx, intervention in enumerate(bundle.policy_spec.interventions):
        ids = {"intervention_id": intervention.intervention_id}
        mech = mechanisms.mechanisms.get(intervention.kind) if mechanisms is not None else None
        fields = _collect_selector_fields(intervention.target)
        used_selector_fields.update(fields)
        if selector_fields is None:
            if fields and strict:
                _emit_missing_registry("selector_fields", ["policy_spec", "interventions", idx])
        else:
            _validate_selector_fields(
                intervention.target,
                selector_fields,
                issues,
                ids=ids,
                path_prefix=["policy_spec", "interventions", idx, "target"],
            )

        reads_slots: list[str] = []
        writes_slots: list[str] = []
        if mech is None:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.UNKNOWN_MECHANISM,
                    message=f"Unknown mechanism '{intervention.kind}'",
                    path=["policy_spec", "interventions", idx, "kind"],
                    ids=ids,
                )
            )
        else:
            used_mechanisms.add(intervention.kind)
            _validate_params(
                intervention,
                mech,
                issues,
                path_prefix=["policy_spec", "interventions", idx, "params"],
                ids=ids,
                allow_extra_params=allow_extra_params,
                units_registry=units,
                used_units=used_units,
                missing_registry_emitted=missing_registry_emitted,
                strict=strict,
            )

            reads_slots, writes_slots = resolve_mechanism_slots(mech, intervention.params)
            used_slots_read.update(reads_slots)
            used_slots_write.update(writes_slots)

            if slots is None:
                if (reads_slots or writes_slots) and strict:
                    _emit_missing_registry("slots", ["policy_spec", "interventions", idx])
            else:
                _validate_mechanism_slots(
                    slots,
                    issues,
                    ids=ids,
                    path_prefix=["policy_spec", "interventions", idx, "kind"],
                    reads_slots=reads_slots,
                    writes_slots=writes_slots,
                )

        schedule_start, schedule_end = schedule_range(intervention.schedule)
        linked_interventions.append(
            LinkedIntervention(
                intervention_id=intervention.intervention_id,
                mechanism_id=intervention.kind,
                reads_slots=list(reads_slots),
                writes_slots=list(writes_slots),
                schedule_start=schedule_start,
                schedule_end=schedule_end,
            )
        )
        intervention_writes[intervention.intervention_id] = (
            list(writes_slots),
            intervention.schedule,
            intervention.priority,
        )

    # Step B: ProblemFrame objectives/KPIs vs metrics/units registries
    metrics = registries.metrics
    if (bundle.problem_frame.objectives or bundle.problem_frame.kpis) and metrics is None:
        _emit_missing_registry("metrics", ["problem_frame"])

    for idx, objective in enumerate(bundle.problem_frame.objectives):
        used_metrics.add(objective.metric_id)
        if metrics is None:
            continue
        metric_spec = metrics.metrics.get(objective.metric_id)
        if metric_spec is None:
            issues.append(
                LinkIssue(
                    severity=LinkSeverity.ERROR,
                    code=LinkIssueCode.UNKNOWN_METRIC,
                    message=f"Unknown metric '{objective.metric_id}'",
                    path=["problem_frame", "objectives", idx, "metric_id"],
                    ids={"objective_id": objective.objective_id},
                    data={"metric_id": objective.metric_id},
                )
            )
            continue
        if metric_spec.unit_id is not None:
            used_units.add(metric_spec.unit_id)
            if units is None:
                _emit_missing_registry("units", ["problem_frame", "objectives", idx])
            elif metric_spec.unit_id not in units.units:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.UNKNOWN_UNIT,
                        message=f"Unknown unit '{metric_spec.unit_id}' for metric",
                        path=["problem_frame", "objectives", idx, "metric_id"],
                        ids={"objective_id": objective.objective_id},
                        data={"unit_id": metric_spec.unit_id},
                    )
                )

    for idx, kpi in enumerate(bundle.problem_frame.kpis):
        used_metrics.add(kpi.metric_id)
        if metrics is not None:
            metric_spec = metrics.metrics.get(kpi.metric_id)
            if metric_spec is None:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.UNKNOWN_METRIC,
                        message=f"Unknown metric '{kpi.metric_id}'",
                        path=["problem_frame", "kpis", idx, "metric_id"],
                        ids={"kpi_id": kpi.kpi_id},
                        data={"metric_id": kpi.metric_id},
                    )
                )
            elif metric_spec.unit_id is not None:
                used_units.add(metric_spec.unit_id)
                if units is None:
                    _emit_missing_registry("units", ["problem_frame", "kpis", idx])
                elif metric_spec.unit_id not in units.units:
                    issues.append(
                        LinkIssue(
                            severity=LinkSeverity.ERROR,
                            code=LinkIssueCode.UNKNOWN_UNIT,
                            message=f"Unknown unit '{metric_spec.unit_id}' for metric",
                            path=["problem_frame", "kpis", idx, "metric_id"],
                            ids={"kpi_id": kpi.kpi_id},
                            data={"unit_id": metric_spec.unit_id},
                        )
                    )
        if kpi.unit_id is not None:
            used_units.add(kpi.unit_id)
            if units is None:
                _emit_missing_registry("units", ["problem_frame", "kpis", idx])
            elif kpi.unit_id not in units.units:
                issues.append(
                    LinkIssue(
                        severity=LinkSeverity.ERROR,
                        code=LinkIssueCode.UNKNOWN_UNIT,
                        message=f"Unknown unit '{kpi.unit_id}' for KPI",
                        path=["problem_frame", "kpis", idx, "unit_id"],
                        ids={"kpi_id": kpi.kpi_id},
                        data={"unit_id": kpi.unit_id},
                    )
                )

    # Step C: ProblemFrame constraints vs constraint/slot/unit registries
    constraints = registries.constraints
    if (
        bundle.problem_frame.hard_constraints or bundle.problem_frame.soft_constraints
    ) and constraints is None:
        _emit_missing_registry("constraints", ["problem_frame"])

    for list_name, constraints_list in (
        ("hard_constraints", bundle.problem_frame.hard_constraints),
        ("soft_constraints", bundle.problem_frame.soft_constraints),
    ):
        for idx, constraint in enumerate(constraints_list):
            used_constraints.add(constraint.constraint_id)
            ids = {"constraint_id": constraint.constraint_id}
            if constraints is not None:
                spec = constraints.constraints.get(constraint.constraint_id)
                if spec is None:
                    issues.append(
                        LinkIssue(
                            severity=LinkSeverity.ERROR,
                            code=LinkIssueCode.UNKNOWN_CONSTRAINT,
                            message=f"Unknown constraint '{constraint.constraint_id}'",
                            path=["problem_frame", list_name, idx, "constraint_id"],
                            ids=ids,
                            data={"constraint_id": constraint.constraint_id},
                        )
                    )
                else:
                    if spec.slot_id is not None:
                        used_slots_constraints.add(spec.slot_id)
                        _validate_constraint_slot(
                            spec.slot_id,
                            slots,
                            issues,
                            ids=ids,
                            path=["problem_frame", list_name, idx, "constraint_id"],
                        )
                    if spec.unit_id is not None:
                        used_units.add(spec.unit_id)
                        _validate_constraint_unit(
                            constraint,
                            spec.unit_id,
                            units,
                            issues,
                            ids=ids,
                            path=["problem_frame", list_name, idx, "value"],
                            strict=strict,
                            missing_registry_emitted=missing_registry_emitted,
                        )

            if constraint.slot_id is not None:
                used_slots_constraints.add(constraint.slot_id)
                _validate_constraint_slot(
                    constraint.slot_id,
                    slots,
                    issues,
                    ids=ids,
                    path=["problem_frame", list_name, idx, "slot_id"],
                )
                if slots is not None:
                    slot_spec = slots.slots.get(constraint.slot_id)
                    if slot_spec is not None and slot_spec.unit is not None:
                        used_units.add(slot_spec.unit.unit_id)
                        _validate_constraint_unit(
                            constraint,
                            slot_spec.unit.unit_id,
                            units,
                            issues,
                            ids=ids,
                            path=["problem_frame", list_name, idx, "value"],
                            strict=strict,
                            missing_registry_emitted=missing_registry_emitted,
                        )

    # Step D: Merge/schedule conflict checks
    if bundle.policy_spec.interventions and registries.merge_rules is None:
        _emit_missing_registry("merge_rules", ["policy_spec", "interventions"])

    if slots is not None and registries.merge_rules is not None:
        _validate_schedule_conflicts(
            bundle.policy_spec.interventions,
            intervention_writes,
            slot_registry=slots,
            merge_registry=registries.merge_rules,
            issues=issues,
        )

    _emit_unused_registry_diagnostics(
        registries=registries,
        issues=issues,
        used_mechanisms=used_mechanisms,
        used_slots=used_slots_read | used_slots_write | used_slots_constraints,
        used_constraints=used_constraints,
    )

    bindings = TrinityBindings(
        interventions=linked_interventions,
        used_mechanisms=sorted(used_mechanisms),
        used_slots_read=sorted(used_slots_read),
        used_slots_write=sorted(used_slots_write),
        used_units=sorted(used_units),
        used_metrics=sorted(used_metrics),
        used_constraints=sorted(used_constraints),
        used_selector_fields=sorted(used_selector_fields),
    )

    registry_digest = _digest(registries, "registry", notes)
    bundle_digest = _digest(bundle, "bundle", notes)

    ok = not any(issue.severity == LinkSeverity.ERROR for issue in issues)
    report = LinkReport(ok=ok, issues=issues, notes=list(notes))
    linked = LinkedTrinityBundle(
        bundle=bundle,
        registry_digest=registry_digest,
        bundle_digest=bundle_digest,
        bindings=bindings,
    )
    return linked, report


def _digest(obj: Any, label: str, notes: dict[str, None]) -> str | None:
    try:
        payload = to_canonical_bytes(obj)
    except CanonViolation as exc:
        notes.setdefault(f"{label}_digest_unavailable: {exc}", None)
        return None
    digest = content_hash(payload)
    return f"sha256:{digest}"


def _emit_unused_registry_diagnostics(
    *,
    registries: RegistryBundle,
    issues: list[LinkIssue],
    used_mechanisms: set[str],
    used_slots: set[str],
    used_constraints: set[str],
) -> None:
    def _append_unused_issue(
        *,
        code: LinkIssueCode,
        message: str,
        path: list[str | int],
        data: dict[str, Any],
    ) -> None:
        issues.append(
            LinkIssue(
                severity=LinkSeverity.WARNING,
                code=code,
                message=message,
                path=path,
                data=data,
            )
        )

    if registries.mechanisms is not None and registries.mechanisms.mechanisms:
        unused_mechanisms = sorted(set(registries.mechanisms.mechanisms) - used_mechanisms)
        if unused_mechanisms:
            if len(unused_mechanisms) == len(registries.mechanisms.mechanisms):
                _append_unused_issue(
                    code=LinkIssueCode.UNUSED_REGISTRY,
                    message="Registry 'mechanisms' is provided but unused",
                    path=["registries", "mechanisms"],
                    data={"registry": "mechanisms"},
                )
            _append_unused_issue(
                code=LinkIssueCode.UNUSED_MECHANISM,
                message="Unused mechanisms remain in registry bundle",
                path=["registries", "mechanisms"],
                data={"mechanism_ids": unused_mechanisms},
            )

    if registries.slots is not None and registries.slots.slots:
        unused_slots = sorted(set(registries.slots.slots) - used_slots)
        if unused_slots:
            if len(unused_slots) == len(registries.slots.slots):
                _append_unused_issue(
                    code=LinkIssueCode.UNUSED_REGISTRY,
                    message="Registry 'slots' is provided but unused",
                    path=["registries", "slots"],
                    data={"registry": "slots"},
                )
            _append_unused_issue(
                code=LinkIssueCode.UNUSED_SLOT,
                message="Unused slots remain in registry bundle",
                path=["registries", "slots"],
                data={"slot_ids": unused_slots},
            )

    if registries.constraints is not None and registries.constraints.constraints:
        unused_constraints = sorted(set(registries.constraints.constraints) - used_constraints)
        if unused_constraints:
            if len(unused_constraints) == len(registries.constraints.constraints):
                _append_unused_issue(
                    code=LinkIssueCode.UNUSED_REGISTRY,
                    message="Registry 'constraints' is provided but unused",
                    path=["registries", "constraints"],
                    data={"registry": "constraints"},
                )
            _append_unused_issue(
                code=LinkIssueCode.UNUSED_CONSTRAINT,
                message="Unused constraints remain in registry bundle",
                path=["registries", "constraints"],
                data={"constraint_ids": unused_constraints},
            )


__all__ = [
    "link_trinity",
]
