"""Bind Fabric snapshots into Foundry state snapshots and input-binding reports.

The public functions in this module implement the data-plane boundary consumed
by `polisyos.foundry.execute.api.execute`: they resolve Fabric snapshot
payloads, materialize a `GlobalState`, persist `FoundryInputBindings`, and
return the bound `StateSnapshotRef` that execution should use as its base
synthetic runtime state.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any

import jax.numpy as jnp
import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    FoundryInputBindingReportRef,
    FoundryInputBindingRule,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    StateSnapshotRef,
)
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.executor import (
    get_state_path,
    load_state_snapshot,
    put_state_snapshot,
    set_state_path,
)
from polisyos.ir.kernel import SlotRegistry, SlotScope, SlotSpec, SlotValueType

_MISSING = object()
_FLOAT_QUANT = Decimal("0.000000001")
_CELL_PREFIX = "cells."
_HOUSEHOLD_CELL_PREFIX = "household_cells."


@dataclass(frozen=True)
class InputBindingsBuildResult:
    """Collect the CAS refs emitted by `build_input_bindings()`.

    Attributes:
        input_bindings_ref: Boundary artifact consumed later by `execute()`.
        input_binding_report_ref: Human-readable report describing applied
            rules and warnings from the materialization step.
        bound_state_snapshot_ref: Synthetic `GlobalState` snapshot produced
            from the Fabric data payload and binding rules.
        applied_binding_ids: IDs of binding rules that were successfully
            applied to the state snapshot.
    """

    input_bindings_ref: FoundryInputBindingsRef
    input_binding_report_ref: FoundryInputBindingReportRef
    bound_state_snapshot_ref: StateSnapshotRef
    applied_binding_ids: tuple[str, ...]


def build_input_bindings(
    store: FileSystemCAS,
    *,
    data_snapshot_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef,
    rules: list[FoundryInputBindingRule] | None = None,
    quality_report_ref: ArtifactRef | None = None,
    notes: list[str] | None = None,
) -> InputBindingsBuildResult:
    """Bind a Fabric snapshot into a concrete `GlobalState` runtime snapshot.

    Explicit `rules` are validated against the registry slot schema; when no
    rules are supplied, bindings are inferred from payload paths that match
    slot IDs or slot `state_path` values. The function writes
    `foundry.input_bindings`, `foundry.input_binding_report`, and a bound
    `foundry.state_snapshot` artifact into CAS.

    Args:
        store: CAS containing the Fabric `DataSnapshot` and registry bundle and
            receiving the bound state and binding artifacts.
        data_snapshot_ref: Artifact reference to the Fabric data snapshot, or
            a snapshot wrapper around an existing `foundry.state_snapshot`.
        registry_bundle_ref: Registry bundle used to validate slot IDs,
            infer entity sizes, and resolve `state_path` mappings.
        rules: Optional explicit binding rules. If omitted, rules are inferred
            from payload paths.
        quality_report_ref: Optional quality report to attach to the generated
            `FoundryInputBindings` artifact.
        notes: Optional free-form notes copied into the persisted bindings.

    Returns:
        `InputBindingsBuildResult` with the boundary artifact refs needed by
        `execute()`.

    Raises:
        ValueError: If a binding rule references an unknown slot, duplicates a
            `binding_id`, or required source values cannot be materialized into
            the target state path.

    Example:
        ```python
        from polisyos.foundry.data_plane.bindings import build_input_bindings

        built = build_input_bindings(
            store,
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry_bundle_ref,
        )
        execute_request = execute_request.model_copy(
            update={"input_bindings_ref": built.input_bindings_ref}
        )
        ```
    """

    snapshot = _load_data_snapshot(store, data_snapshot_ref)
    registry = load_registry_bundle_content(store, registry_bundle_ref)
    binding_payload = _load_binding_payload(store, snapshot)

    effective_rules = _prepare_rules(
        rules=rules,
        slot_registry=registry.slot_registry,
        payload=binding_payload,
    )
    _validate_rules(effective_rules, registry.slot_registry)

    base_state = _build_base_state(
        store=store,
        snapshot=snapshot,
        payload=binding_payload,
        slot_registry=registry.slot_registry,
        rules=effective_rules,
    )

    materialized_state, applied_ids, errors, warnings = _materialize_state(
        base_state=base_state,
        rules=effective_rules,
        slot_registry=registry.slot_registry,
        payload=binding_payload,
    )
    if errors:
        raise ValueError("; ".join(errors))

    snapshot_inputs = [
        InputRef(artifact_id=data_snapshot_ref.artifact_id, role="input.data_snapshot_ref"),
        InputRef(artifact_id=registry_bundle_ref.artifact_id, role="input.registry_bundle_ref"),
    ]
    bound_snapshot_ref = put_state_snapshot(
        store,
        state=materialized_state,
        step=int(np.asarray(materialized_state.step).item()),
        inputs=snapshot_inputs,
    )
    bound_state_snapshot_ref = StateSnapshotRef(artifact_id=bound_snapshot_ref.artifact_id)

    bindings_notes = list(notes or [])
    if snapshot.data_ref.kind == "foundry.state_snapshot":
        bindings_notes.append("compatibility:data_snapshot_contains_foundry_state_snapshot")
    bindings_notes.extend(_snapshot_binding_notes(snapshot))
    warnings.extend(_snapshot_binding_warnings(snapshot))
    if warnings:
        bindings_notes.extend([f"warning:{msg}" for msg in warnings])

    bindings = FoundryInputBindings(
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        rules=effective_rules,
        bound_state_snapshot_ref=bound_state_snapshot_ref,
        quality_report_ref=quality_report_ref or snapshot.quality_report_ref,
        notes=bindings_notes,
    )
    bindings_ref_payload = store.put_json(
        bindings,
        PutOptions(
            kind="foundry.input_bindings",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FoundryInputBindings", version="1.0"),
            inputs=[
                InputRef(artifact_id=data_snapshot_ref.artifact_id, role="input.data_snapshot_ref"),
                InputRef(
                    artifact_id=registry_bundle_ref.artifact_id,
                    role="input.registry_bundle_ref",
                ),
                InputRef(
                    artifact_id=bound_state_snapshot_ref.artifact_id,
                    role="artifact.bound_state_snapshot_ref",
                ),
            ],
        ),
    )

    report_payload = {
        "schema_version": "1.0",
        "data_snapshot_ref": str(data_snapshot_ref.artifact_id),
        "registry_bundle_ref": str(registry_bundle_ref.artifact_id),
        "bound_state_snapshot_ref": str(bound_state_snapshot_ref.artifact_id),
        "rule_count": len(effective_rules),
        "applied_binding_ids": list(applied_ids),
        "warning_count": len(warnings),
        "warnings": warnings,
        "notes": bindings_notes,
    }
    report_ref_payload = store.put_json(
        report_payload,
        PutOptions(
            kind="foundry.input_binding_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FoundryInputBindingReport", version="1.0"),
            inputs=[
                InputRef(
                    artifact_id=bindings_ref_payload.artifact_id,
                    role="artifact.input_bindings_ref",
                ),
                InputRef(
                    artifact_id=bound_state_snapshot_ref.artifact_id,
                    role="artifact.bound_state_snapshot_ref",
                ),
            ],
        ),
    )

    return InputBindingsBuildResult(
        input_bindings_ref=FoundryInputBindingsRef(artifact_id=bindings_ref_payload.artifact_id),
        input_binding_report_ref=FoundryInputBindingReportRef(
            artifact_id=report_ref_payload.artifact_id
        ),
        bound_state_snapshot_ref=bound_state_snapshot_ref,
        applied_binding_ids=applied_ids,
    )


def load_input_bindings(
    store: FileSystemCAS,
    ref: FoundryInputBindingsRef | ArtifactRef,
) -> FoundryInputBindings:
    """Load a persisted `FoundryInputBindings` boundary artifact from CAS.

    Args:
        store: CAS containing the serialized bindings artifact.
        ref: Either a typed `FoundryInputBindingsRef` or a plain artifact ref
            whose `artifact_id` points to a `foundry.input_bindings` payload.

    Returns:
        Parsed `FoundryInputBindings` model.
    """

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return FoundryInputBindings.model_validate(payload)


def resolve_bound_state_snapshot_ref(
    store: FileSystemCAS,
    ref: FoundryInputBindingsRef | ArtifactRef,
) -> StateSnapshotRef:
    """Resolve the bound `StateSnapshotRef` and validate referenced artifacts.

    Args:
        store: CAS containing the input-binding artifact and the bound snapshot.
        ref: Input-binding artifact reference returned by
            `build_input_bindings()`.

    Returns:
        `StateSnapshotRef` that `execute()` can use as the simulation base.

    Raises:
        Exception: Propagates CAS read failures when either the original data
            snapshot or the bound state snapshot is missing.
    """

    bindings = load_input_bindings(store, ref)
    _ensure_artifact_readable(store, bindings.data_snapshot_ref)
    _ensure_artifact_readable(store, bindings.bound_state_snapshot_ref)
    return bindings.bound_state_snapshot_ref


def _load_data_snapshot(store: FileSystemCAS, data_snapshot_ref: ArtifactRef) -> DataSnapshot:
    payload = from_canonical_bytes(store.get_bytes(data_snapshot_ref.artifact_id))
    return DataSnapshot.model_validate(payload)


def _snapshot_binding_notes(snapshot: DataSnapshot) -> list[str]:
    notes: list[str] = []
    data_shape = str(snapshot.stats.get("data_shape", "")).strip()
    if data_shape:
        notes.append(f"snapshot.data_shape={data_shape}")
    for key in (
        "survey_year_field",
        "wave_field",
        "sample_weight_field",
        "inclusion_probabilities_field",
    ):
        value = str(snapshot.stats.get(key, "")).strip()
        if value:
            notes.append(f"snapshot.{key}={value}")
    return notes


def _snapshot_binding_warnings(snapshot: DataSnapshot) -> list[str]:
    data_shape = str(snapshot.stats.get("data_shape", "")).strip().lower()
    if data_shape != "survey_repeated_cross_section":
        return []
    return [
        (
            "Input snapshot is survey repeated cross-section; route it to "
            "transport/survey/HTE workflows, not panel SCM/DiD/econometrics"
        )
    ]


def _load_binding_payload(store: FileSystemCAS, snapshot: DataSnapshot) -> Any:
    if snapshot.data_ref.kind == "foundry.state_snapshot":
        return {}
    return from_canonical_bytes(store.get_bytes(snapshot.data_ref.artifact_id))


def _prepare_rules(
    *,
    rules: list[FoundryInputBindingRule] | None,
    slot_registry: SlotRegistry,
    payload: Any,
) -> list[FoundryInputBindingRule]:
    if rules:
        parsed = [FoundryInputBindingRule.model_validate(rule.model_dump()) for rule in rules]
        return sorted(parsed, key=lambda item: item.binding_id)
    auto = _auto_rules_from_payload(slot_registry=slot_registry, payload=payload)
    return sorted(auto, key=lambda item: item.binding_id)


def _auto_rules_from_payload(
    *,
    slot_registry: SlotRegistry,
    payload: Any,
) -> list[FoundryInputBindingRule]:
    if not isinstance(payload, dict):
        return []
    rules: list[FoundryInputBindingRule] = []
    for slot_id in sorted(slot_registry.slots.keys()):
        slot = slot_registry.slots[slot_id]
        candidates = [slot.slot_id]
        if slot.state_path:
            candidates.append(slot.state_path)
        source_path = next((item for item in candidates if _path_exists(payload, item)), None)
        if source_path is None:
            continue
        rules.append(
            FoundryInputBindingRule(
                binding_id=f"auto.{slot.slot_id.replace('.', '_')}",
                source_path=source_path,
                target_slot_id=slot.slot_id,
                required=False,
                notes=["auto-generated from payload path"],
            )
        )
    return rules


def _validate_rules(rules: list[FoundryInputBindingRule], slot_registry: SlotRegistry) -> None:
    seen: set[str] = set()
    for rule in rules:
        if rule.binding_id in seen:
            raise ValueError(f"Duplicate binding_id: {rule.binding_id}")
        seen.add(rule.binding_id)
        if rule.target_slot_id not in slot_registry.slots:
            raise ValueError(
                f"Binding rule '{rule.binding_id}' references unknown slot_id '{rule.target_slot_id}'"
            )


def _build_base_state(
    *,
    store: FileSystemCAS,
    snapshot: DataSnapshot,
    payload: Any,
    slot_registry: SlotRegistry,
    rules: list[FoundryInputBindingRule],
) -> GlobalState:
    if snapshot.data_ref.kind == "foundry.state_snapshot":
        return load_state_snapshot(store, snapshot_ref=snapshot.data_ref)

    n_agents, n_firms, n_cells, n_household_cells = _infer_entity_sizes(
        payload=payload,
        rules=rules,
        slot_registry=slot_registry,
    )
    return GlobalState.empty(
        n_agents=max(1, n_agents),
        n_firms=max(1, n_firms),
        n_cells=n_cells,
        n_household_cells=n_household_cells,
    )


def _infer_entity_sizes(
    *,
    payload: Any,
    rules: list[FoundryInputBindingRule],
    slot_registry: SlotRegistry,
) -> tuple[int, int, int, int]:
    n_agents = 1
    n_firms = 1
    n_cells = 0
    n_household_cells = 0
    for rule in rules:
        slot = slot_registry.slots.get(rule.target_slot_id)
        if slot is None:
            continue
        value = _resolve_source_path(payload, rule.source_path, missing=_MISSING)
        if value is _MISSING:
            value = rule.default_value
        size = _sequence_size(value)
        if slot.scope == SlotScope.PER_AGENT and size is not None:
            n_agents = max(n_agents, size)
        elif slot.scope == SlotScope.PER_FIRM and size is not None:
            n_firms = max(n_firms, size)
        elif slot.scope == SlotScope.PER_CELL and size is not None:
            family_path = slot.state_path or slot.slot_id
            if family_path.startswith(_CELL_PREFIX):
                n_cells = max(n_cells, size)
            elif family_path.startswith(_HOUSEHOLD_CELL_PREFIX):
                n_household_cells = max(n_household_cells, size)
    return n_agents, n_firms, n_cells, n_household_cells


def _sequence_size(value: Any) -> int | None:
    if isinstance(value, (str, bytes, bytearray)):
        return None
    if isinstance(value, (list, tuple)):
        return len(value)
    if isinstance(value, np.ndarray):
        if value.ndim == 0:
            return None
        return int(value.shape[0])
    if isinstance(value, jnp.ndarray):
        if value.ndim == 0:
            return None
        return int(value.shape[0])
    return None


def _materialize_state(
    *,
    base_state: GlobalState,
    rules: list[FoundryInputBindingRule],
    slot_registry: SlotRegistry,
    payload: Any,
) -> tuple[GlobalState, tuple[str, ...], list[str], list[str]]:
    state = base_state
    applied: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    for rule in sorted(rules, key=lambda item: item.binding_id):
        slot = slot_registry.slots.get(rule.target_slot_id)
        if slot is None:
            errors.append(f"{rule.binding_id}: target slot missing '{rule.target_slot_id}'")
            continue
        if not slot.state_path:
            errors.append(f"{rule.binding_id}: slot '{slot.slot_id}' has no state_path")
            continue

        value = _resolve_source_path(payload, rule.source_path, missing=_MISSING)
        if value is _MISSING:
            value = rule.default_value
            if value is None and not rule.required:
                warnings.append(
                    f"{rule.binding_id}: source_path '{rule.source_path}' missing; optional rule skipped"
                )
                continue
            if value is None and rule.required:
                errors.append(
                    f"{rule.binding_id}: required source_path missing '{rule.source_path}'"
                )
                continue

        try:
            transformed = _apply_transform_chain(value, rule.transforms)
            target_tensor = get_state_path(state, slot.state_path)
            coerced = _coerce_to_slot_tensor(
                transformed,
                slot=slot,
                target_tensor=target_tensor,
            )
            state = set_state_path(state, slot.state_path, coerced)
            applied.append(rule.binding_id)
        except Exception as exc:
            errors.append(f"{rule.binding_id}: {exc}")

    return state, tuple(applied), errors, warnings


def _apply_transform_chain(value: Any, transforms: list[Any]) -> Any:
    current = value
    for transform in transforms:
        op = getattr(transform, "op", "identity")
        params = getattr(transform, "params", {}) or {}
        current = _apply_transform(op=str(op), value=current, params=dict(params))
    return current


def _apply_transform(*, op: str, value: Any, params: dict[str, Any]) -> Any:
    if op == "identity":
        return value
    if op == "to_bool":
        fast = _apply_array_fast_path(op=op, value=value, params=params)
        if fast is not _MISSING:
            return fast
        return _map_values(value, _to_bool)
    if op == "to_int":
        fast = _apply_array_fast_path(op=op, value=value, params=params)
        if fast is not _MISSING:
            return fast
        return _map_values(value, _to_int)
    if op == "to_decimal":
        return _map_values(value, _to_decimal)
    if op == "fillna":
        fill = params.get("value")
        return _map_values(value, lambda item: fill if item is None else item)
    if op == "scale":
        factor = _to_decimal(params.get("factor", 1))
        return _map_values(value, lambda item: _to_decimal(item) * factor)
    if op == "offset":
        delta = _to_decimal(params.get("value", 0))
        return _map_values(value, lambda item: _to_decimal(item) + delta)
    if op == "clip":
        lower = params.get("min")
        upper = params.get("max")
        fast = _apply_array_fast_path(op=op, value=value, params=params)
        if fast is not _MISSING:
            return fast
        return _map_values(
            value,
            lambda item: _clip_decimal(item, lower=lower, upper=upper),
        )
    if op == "round":
        fast = _apply_array_fast_path(op=op, value=value, params=params)
        if fast is not _MISSING:
            return fast
        digits = int(params.get("digits", 6))
        quant = Decimal(10) ** Decimal(-digits)
        return _map_values(value, lambda item: _to_decimal(item).quantize(quant))
    raise ValueError(f"Unsupported transform op: {op}")


def _map_values(value: Any, fn) -> Any:  # noqa: ANN001
    if isinstance(value, (list, tuple)):
        return [fn(item) for item in value]
    if isinstance(value, np.ndarray):
        return _map_array_values(value, fn)
    if isinstance(value, jnp.ndarray):
        return _map_array_values(np.asarray(value), fn)
    return fn(value)


def _map_array_values(value: np.ndarray, fn) -> Any:  # noqa: ANN001
    flat = [fn(item) for item in value.flat]
    if value.ndim == 0:
        return flat[0]
    reshaped = np.asarray(flat, dtype=object).reshape(value.shape)
    return _object_array_to_nested_list(reshaped)


def _object_array_to_nested_list(value: np.ndarray) -> Any:
    if value.ndim == 0:
        return value.reshape(()).item()
    if value.ndim == 1:
        return [item.item() if isinstance(item, np.generic) else item for item in value]
    return [_object_array_to_nested_list(row) for row in value]


def _apply_array_fast_path(*, op: str, value: Any, params: dict[str, Any]) -> Any:
    array = _as_vectorizable_array(value)
    if array is None:
        return _MISSING
    is_numpy, arr = array

    if op == "to_bool":
        return arr.astype(bool)
    if op == "to_int":
        return arr.astype(jnp.int32 if not is_numpy else np.int32)
    if op == "clip":
        lower = params.get("min")
        upper = params.get("max")
        clip_fn = np.clip if is_numpy else jnp.clip
        lower_value = None if lower is None else float(_to_decimal(lower))
        upper_value = None if upper is None else float(_to_decimal(upper))
        return clip_fn(arr, lower_value, upper_value)
    if op == "round":
        round_fn = np.round if is_numpy else jnp.round
        digits = int(params.get("digits", 6))
        return round_fn(arr, decimals=digits)
    return _MISSING


def _as_vectorizable_array(value: Any) -> tuple[bool, Any] | None:
    if isinstance(value, np.ndarray):
        if value.dtype == object:
            return None
        return True, value
    if isinstance(value, jnp.ndarray):
        if getattr(value, "dtype", None) is None:
            return None
        return False, value
    return None


def _clip_decimal(value: Any, *, lower: Any, upper: Any) -> Decimal:
    dec = _to_decimal(value)
    if lower is not None:
        dec = max(dec, _to_decimal(lower))
    if upper is not None:
        dec = min(dec, _to_decimal(upper))
    return dec


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"1", "true", "yes", "y"}:
            return True
        if token in {"0", "false", "no", "n", ""}:
            return False
    return bool(value)


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if value is None:
        return 0
    return int(Decimal(str(value)))


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Cannot cast '{value}' to Decimal") from exc


def _coerce_to_slot_tensor(value: Any, *, slot: SlotSpec, target_tensor: Any):
    target_arr = np.asarray(target_tensor)
    converted = _convert_slot_value(value=value, slot=slot)
    source_arr = np.asarray(converted)

    if target_arr.ndim == 0:
        scalar = source_arr.reshape(-1)[0] if source_arr.ndim > 0 else source_arr.item()
        return jnp.asarray(scalar, dtype=target_arr.dtype)

    if source_arr.ndim == 0:
        source_arr = np.full(target_arr.shape, source_arr.item(), dtype=source_arr.dtype)
    elif source_arr.shape != target_arr.shape:
        if source_arr.ndim == 1 and source_arr.shape[0] == target_arr.shape[0]:
            source_arr = source_arr.reshape(target_arr.shape)
        else:
            raise ValueError(
                f"shape mismatch for slot '{slot.slot_id}': expected {target_arr.shape}, got {source_arr.shape}"
            )

    return jnp.asarray(source_arr, dtype=target_arr.dtype)


def _convert_slot_value(*, value: Any, slot: SlotSpec) -> Any:
    if slot.value_type == SlotValueType.BOOL:
        return _map_values(value, _to_bool)
    if slot.value_type == SlotValueType.INT:
        return _map_values(value, _to_int)
    if slot.value_type == SlotValueType.DECIMAL:
        return _map_values(value, _canonical_float)
    if slot.value_type == SlotValueType.STRING:
        return _map_values(value, lambda item: "" if item is None else str(item))
    return value


def _canonical_float(value: Any) -> float:
    dec = _to_decimal(value).quantize(_FLOAT_QUANT, rounding=ROUND_HALF_EVEN)
    result = float(dec)
    if not np.isfinite(result):
        raise ValueError(f"Non-finite decimal value: {value}")
    return result


def _resolve_source_path(payload: Any, path: str, *, missing: Any) -> Any:
    if not path:
        return payload
    current = payload
    for token in path.split("."):
        try:
            current = _resolve_path_token(current, token)
        except KeyError:
            return missing
    return current


def _resolve_path_token(current: Any, token: str) -> Any:
    if isinstance(current, dict):
        if token not in current:
            raise KeyError(token)
        return current[token]
    if isinstance(current, list):
        if token.isdigit():
            idx = int(token)
            if idx < 0 or idx >= len(current):
                raise KeyError(token)
            return current[idx]
        values = []
        for item in current:
            values.append(_resolve_path_token(item, token))
        return values
    raise KeyError(token)


def _path_exists(payload: Any, path: str) -> bool:
    return _resolve_source_path(payload, path, missing=_MISSING) is not _MISSING


def _ensure_artifact_readable(store: FileSystemCAS, ref: ArtifactRef) -> None:
    store.get_manifest(ref.artifact_id)
