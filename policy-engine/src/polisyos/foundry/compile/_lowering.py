"""Public compile lowering module API."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    LoweredConstraint,
    LoweredIR,
    LoweredIRRef,
    LoweredMechanism,
)
from polisyos.foundry._registry import has_runtime_mechanism_support, resolve_runtime_fidelity
from polisyos.ir.governance.policy_spec import InterventionSpec, MechanismBinding, ParameterSpec
from polisyos.ir.governance.policy_spec import PolicySpec as PolicySpecModel
from polisyos.ir.governance.problem_frame import ProblemFrame as ProblemFrameModel
from polisyos.ir.kernel.mechanisms import MechanismTypeSpec
from polisyos.ir.model_spec import ModelSpec as ModelSpecModel
from polisyos.ir.trinity import TrinityBundle

CoverageStatus = Literal[
    "runtime",
    "compile_only",
    "governance_only",
    "decision_only",
    "explicit_noop",
]


@dataclass(frozen=True)
class CoverageEntry:
    """Coverage entry data model."""

    status: CoverageStatus
    consumer: str


TRINITY_FIELD_COVERAGE: dict[str, dict[str, CoverageEntry]] = {
    "ProblemFrame": {
        "schema_version": CoverageEntry("compile_only", "compile.coverage_audit"),
        "problem_id": CoverageEntry("compile_only", "compile.coverage_audit"),
        "domain": CoverageEntry("compile_only", "compile.coverage_audit"),
        "objectives": CoverageEntry("compile_only", "compile.coverage_audit"),
        "kpis": CoverageEntry("compile_only", "compile.coverage_audit"),
        "success_criteria": CoverageEntry("compile_only", "compile.coverage_audit"),
        "hard_constraints": CoverageEntry("runtime", "foundry.lowering.constraints"),
        "soft_constraints": CoverageEntry("runtime", "foundry.lowering.constraints"),
        "stakeholders": CoverageEntry("governance_only", "scientist.governance"),
        "normative_frame": CoverageEntry("governance_only", "scientist.governance"),
        "narrative": CoverageEntry("explicit_noop", "non_executable_metadata"),
        "labels": CoverageEntry("explicit_noop", "non_executable_metadata"),
        "notes": CoverageEntry("explicit_noop", "non_executable_metadata"),
    },
    "PolicySpec": {
        "schema_version": CoverageEntry("compile_only", "compile.coverage_audit"),
        "policy_id": CoverageEntry("compile_only", "compile.coverage_audit"),
        "problem_frame_ref": CoverageEntry("compile_only", "compile.coverage_audit"),
        "interventions": CoverageEntry("runtime", "foundry.lowering.mechanisms"),
        "mechanism_bindings": CoverageEntry("runtime", "foundry.lowering.mechanisms"),
        "parameters": CoverageEntry("compile_only", "foundry.lowering.parameter_specs"),
        "temporal_constraints": CoverageEntry(
            "governance_only",
            "scientist.governance.temporal_policy_constraints",
        ),
        "composition": CoverageEntry(
            "governance_only",
            "scientist.governance.policy_composition",
        ),
        "mechanism_design": CoverageEntry(
            "governance_only",
            "scientist.governance.mechanism_design",
        ),
        "global_schedule": CoverageEntry("runtime", "foundry.lowering.schedule"),
        "name": CoverageEntry("explicit_noop", "non_executable_metadata"),
        "description": CoverageEntry("explicit_noop", "non_executable_metadata"),
        "labels": CoverageEntry("explicit_noop", "non_executable_metadata"),
        "version_tag": CoverageEntry("explicit_noop", "non_executable_metadata"),
        "notes": CoverageEntry("explicit_noop", "non_executable_metadata"),
    },
    "ModelSpec": {
        "schema_version": CoverageEntry("compile_only", "compile.coverage_audit"),
        "model_id": CoverageEntry("compile_only", "compile.coverage_audit"),
        "data_snapshot_ref": CoverageEntry("runtime", "foundry.execute.input_bindings"),
        "registry_bundle_ref": CoverageEntry("runtime", "foundry.compile.registry_resolution"),
        "time_semantics": CoverageEntry("compile_only", "foundry.lowering.time_semantics"),
        "agent_config": CoverageEntry("compile_only", "foundry.lowering.agent_config"),
        "assumptions": CoverageEntry("compile_only", "foundry.lowering.assumptions"),
        "environment_config": CoverageEntry("compile_only", "foundry.lowering.environment_config"),
        "fidelity_level": CoverageEntry("runtime", "foundry.lowering.fidelity"),
        "calibrated": CoverageEntry("compile_only", "foundry.lowering.calibration_metadata"),
        "calibration_ref": CoverageEntry("compile_only", "foundry.lowering.calibration_metadata"),
        "name": CoverageEntry("explicit_noop", "non_executable_metadata"),
        "description": CoverageEntry("explicit_noop", "non_executable_metadata"),
        "labels": CoverageEntry("explicit_noop", "non_executable_metadata"),
        "version_tag": CoverageEntry("explicit_noop", "non_executable_metadata"),
        "notes": CoverageEntry("explicit_noop", "non_executable_metadata"),
    },
}


_REQUIRED_CONSUMERS = {
    ("PolicySpec", "interventions"),
    ("PolicySpec", "mechanism_bindings"),
    ("PolicySpec", "parameters"),
    ("PolicySpec", "global_schedule"),
    ("ProblemFrame", "hard_constraints"),
    ("ProblemFrame", "soft_constraints"),
    ("ModelSpec", "time_semantics"),
    ("ModelSpec", "environment_config"),
    ("ModelSpec", "fidelity_level"),
    ("ModelSpec", "registry_bundle_ref"),
    ("ModelSpec", "data_snapshot_ref"),
}


def audit_trinity_field_coverage(*, strict: bool = True) -> list[str]:
    """Audit trinity field coverage helper."""
    model_map = {
        "ProblemFrame": ProblemFrameModel,
        "PolicySpec": PolicySpecModel,
        "ModelSpec": ModelSpecModel,
    }
    notes: list[str] = []
    for model_name, model_cls in model_map.items():
        expected = set(model_cls.model_fields)
        covered = set(TRINITY_FIELD_COVERAGE.get(model_name, {}))
        missing = sorted(expected - covered)
        extra = sorted(covered - expected)
        if missing or extra:
            message = f"trinity_coverage_mismatch:{model_name}:missing={missing}:extra={extra}"
            if strict:
                raise ValueError(message)
            notes.append(message)
        for field_name in sorted(expected & covered):
            entry = TRINITY_FIELD_COVERAGE[model_name][field_name]
            if (model_name, field_name) in _REQUIRED_CONSUMERS and entry.status not in {
                "runtime",
                "compile_only",
            }:
                message = (
                    f"trinity_field_missing_semantic_consumer:{model_name}.{field_name}:"
                    f"{entry.status}"
                )
                if strict:
                    raise ValueError(message)
                notes.append(message)
    if not notes:
        notes.append("trinity_coverage_audit:ok")
    return notes


def lower_trinity(
    store: FileSystemCAS,
    *,
    policy_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef,
    bundle: TrinityBundle,
    linked_bundle: Any,
    registry_content: Any,
    strict: bool = True,
) -> tuple[LoweredIRRef, LoweredIR, list[str]]:
    """Lower trinity helper."""
    semantic_notes = audit_trinity_field_coverage(strict=strict)
    linked_by_intervention = {
        item.intervention_id: item for item in getattr(linked_bundle.bindings, "interventions", [])
    }

    enabled_interventions = [
        intervention for intervention in bundle.policy_spec.interventions if intervention.enabled
    ]
    binding_by_intervention, binding_notes = _resolve_bindings(
        enabled_interventions=enabled_interventions,
        explicit_bindings=list(bundle.policy_spec.mechanism_bindings),
    )
    semantic_notes.extend(binding_notes)

    lowered_mechanisms: list[LoweredMechanism] = []
    effective_params_by_intervention: dict[str, dict[str, Any]] = {}

    for intervention in sorted(enabled_interventions, key=lambda item: item.intervention_id):
        binding, synthetic = binding_by_intervention[intervention.intervention_id]
        mechanism_id = binding.mechanism_id
        if intervention.kind != mechanism_id:
            raise ValueError(
                "mechanism_binding_kind_mismatch:"
                f"{intervention.intervention_id}:{intervention.kind}!={mechanism_id}"
            )
        if not has_runtime_mechanism_support(mechanism_id):
            raise ValueError(f"missing_runtime_mechanism_support:{mechanism_id}")

        linked = linked_by_intervention.get(intervention.intervention_id)
        reads_slots = list(getattr(linked, "reads_slots", []))
        writes_slots = list(getattr(linked, "writes_slots", []))
        runtime_fidelity = resolve_runtime_fidelity(mechanism_id, bundle.model_spec.fidelity_level)
        effective_schedule = _model_dump(
            bundle.policy_spec.global_schedule or intervention.schedule
        )
        effective_params = _merge_effective_params(
            mechanism_spec=registry_content.mechanism_registry.mechanisms.get(mechanism_id),
            binding=binding,
            intervention=intervention,
        )
        effective_params_by_intervention[intervention.intervention_id] = effective_params

        lowered_payload = {
            "binding_id": binding.binding_id,
            "mechanism_id": mechanism_id,
            "intervention_ids": [intervention.intervention_id],
            "priority": intervention.priority,
            "params": effective_params,
            "schedule": effective_schedule,
            "selector": _model_dump(intervention.target),
            "selected_fidelity": runtime_fidelity.value,
            "legacy_kind_alias_used": synthetic,
            "notes": ["synthetic_mechanism_binding_from_kind"]
            if synthetic
            else list(intervention.notes),
        }
        params_ref = store.put_json(
            lowered_payload,
            PutOptions(
                kind="foundry.lowered_mechanism_payload",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.foundry.LoweredMechanismPayload", version="0.2.0"),
                inputs=[InputRef(artifact_id=policy_ref.artifact_id, role="ir")],
            ),
        )

        lowered_mechanisms.append(
            LoweredMechanism(
                binding_id=binding.binding_id,
                mechanism_id=mechanism_id,
                intervention_ids=[intervention.intervention_id],
                effective_params_ref=params_ref,
                effective_schedule=effective_schedule,
                selected_fidelity=runtime_fidelity.value,
                inputs=reads_slots,
                outputs=writes_slots,
                legacy_kind_alias_used=synthetic,
                target_selector=_model_dump(intervention.target),
                priority=intervention.priority,
                notes=list(lowered_payload["notes"]),
            )
        )

    _validate_parameter_specs(
        bundle.policy_spec.parameters,
        effective_params_by_intervention=effective_params_by_intervention,
        mechanism_registry=registry_content.mechanism_registry.mechanisms,
    )

    lowered_ir = LoweredIR(
        schema_version="0.2",
        ir_ref=policy_ref,
        mechanisms=lowered_mechanisms,
        constraints=_lower_constraints(bundle.problem_frame, registry_content.constraint_registry),
        parameter_specs=[item.model_dump(mode="json") for item in bundle.policy_spec.parameters],
        time_semantics=_model_dump(bundle.model_spec.time_semantics),
        environment_config=_model_dump(bundle.model_spec.environment_config),
        policy_fidelity_level=bundle.model_spec.fidelity_level.value,
        constraint_mode="hard_soft_v1",
        notes=sorted(set(semantic_notes)),
    )
    lowered_ir_payload = store.put_json(
        lowered_ir,
        PutOptions(
            kind="foundry.lowered_ir",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.LoweredIR", version="0.2.0"),
            inputs=[
                InputRef(artifact_id=policy_ref.artifact_id, role="ir"),
                InputRef(artifact_id=registry_bundle_ref.artifact_id, role="registry_bundle"),
            ],
        ),
    )
    lowered_ir_ref = LoweredIRRef.model_validate(lowered_ir_payload.model_dump())
    return lowered_ir_ref, lowered_ir, sorted(set(semantic_notes))


def _resolve_bindings(
    *,
    enabled_interventions: list[InterventionSpec],
    explicit_bindings: list[MechanismBinding],
) -> tuple[dict[str, tuple[MechanismBinding, bool]], list[str]]:
    mapping: dict[str, tuple[MechanismBinding, bool]] = {}
    notes: list[str] = []
    enabled_ids = {item.intervention_id for item in enabled_interventions}

    if explicit_bindings:
        seen = Counter()
        for binding in explicit_bindings:
            for intervention_id in binding.intervention_ids:
                if intervention_id not in enabled_ids:
                    raise ValueError(f"unknown_mechanism_binding_intervention:{intervention_id}")
                seen[intervention_id] += 1
                if seen[intervention_id] > 1:
                    raise ValueError(f"duplicate_mechanism_binding_assignment:{intervention_id}")
                mapping[intervention_id] = (binding, False)
        missing = sorted(enabled_ids - set(mapping))
        if missing:
            raise ValueError(
                f"missing_mechanism_binding_for_enabled_interventions:{','.join(missing)}"
            )
        return mapping, notes

    for intervention in enabled_interventions:
        mapping[intervention.intervention_id] = (
            MechanismBinding(
                binding_id=f"synthetic_{intervention.intervention_id}",
                mechanism_id=intervention.kind,
                intervention_ids=[intervention.intervention_id],
                config_overrides={},
            ),
            True,
        )
        notes.append(f"synthetic_mechanism_binding_from_kind:{intervention.intervention_id}")
    return mapping, notes


def _merge_effective_params(
    *,
    mechanism_spec: MechanismTypeSpec | None,
    binding: MechanismBinding,
    intervention: InterventionSpec,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    missing = object()
    if mechanism_spec is not None:
        for param_id, param_spec in mechanism_spec.params.items():
            default_value = getattr(param_spec, "default_value", missing)
            if default_value is missing:
                default_value = getattr(param_spec, "default", missing)
            if default_value is not missing and param_id not in defaults:
                defaults[param_id] = default_value
    merged = dict(defaults)
    merged.update(binding.config_overrides)
    merged.update(intervention.params)
    return merged


def _validate_parameter_specs(
    parameter_specs: list[ParameterSpec],
    *,
    effective_params_by_intervention: dict[str, dict[str, Any]],
    mechanism_registry: dict[str, MechanismTypeSpec],
) -> None:
    for item in parameter_specs:
        effective_params = effective_params_by_intervention.get(item.intervention_id)
        if effective_params is None:
            raise ValueError(f"unknown_parameter_intervention:{item.intervention_id}")
        root = item.param_path.split(".", 1)[0]
        if root in effective_params:
            continue
        if any(root in spec.params for spec in mechanism_registry.values()):
            continue
        raise ValueError(f"parameter_path_unresolved:{item.param_id}:{item.param_path}")


def _lower_constraints(problem_frame: Any, constraint_registry: Any) -> list[LoweredConstraint]:
    lowered: list[LoweredConstraint] = []
    registry_constraints = getattr(constraint_registry, "constraints", {})
    for severity, items in (
        ("hard", problem_frame.hard_constraints),
        ("soft", problem_frame.soft_constraints),
    ):
        for constraint in items:
            registry_spec = registry_constraints.get(constraint.constraint_id)
            slot_id = constraint.slot_id or getattr(registry_spec, "slot_id", None)
            operator = constraint.operator or getattr(registry_spec, "operator", None)
            if slot_id is None or operator is None:
                raise ValueError(f"constraint_missing_runtime_semantics:{constraint.constraint_id}")
            lowered.append(
                LoweredConstraint(
                    constraint_id=constraint.constraint_id,
                    severity=severity,
                    slot_id=slot_id,
                    operator=operator,
                    expected=_json_value(constraint.value),
                    unit_id=getattr(registry_spec, "unit_id", None),
                    penalty=constraint.penalty_weight
                    if severity == "soft" and constraint.penalty_weight is not None
                    else None,
                    notes=list(constraint.notes),
                )
            )
    return lowered


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _model_dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value
