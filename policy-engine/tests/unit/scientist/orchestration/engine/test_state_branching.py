"""Regression tests for bounded state branching hot paths."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, PrivateAttr, ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.artifacts import ArtifactID as IRArtifactID
from polisyos.ir.registry.refs import ContextAdaptiveParameterBundleRef
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    StateMutation,
    _validate_producer_state,
    branch_state,
    canonical_state_mutation_operations,
    mutation_journal_from_operations,
    snapshot_state,
)
from polisyos.scientist.orchestration.engine.state_merge import merge_parallel_outcomes


class _BranchNestedModel(BaseModel):
    items: list[str]
    untouched: dict[str, list[str]]


class _BranchHolderModel(BaseModel):
    nested: _BranchNestedModel


class _AnyHolderModel(BaseModel):
    payload: Any


class _PolicyDomain(str, Enum):
    fiscal = "fiscal"


class _PolicyLabel(StrEnum):
    candidate = "candidate"


class _NativeEnumModel(BaseModel):
    domain: _PolicyDomain
    label: _PolicyLabel


class _MutableEnumValue:
    pass


class _EnumWithMutableValue(Enum):
    payload = _MutableEnumValue()


class _CopyHookEnum(str, Enum):
    payload = "unsafe"

    def __deepcopy__(self, memo: dict[int, Any]) -> _CopyHookEnum:
        del memo
        _COPY_HOOK_CALLS.append(self)
        return self


_COPY_HOOK_CALLS: list[Enum] = []
_ATTRIBUTE_HOOK_CALLS: list[str] = []
_REDUCTION_HOOK_CALLS: list[Enum] = []


class _CopyOnlyEnum(str, Enum):
    payload = "unsafe"

    def __copy__(self) -> _CopyOnlyEnum:
        _COPY_HOOK_CALLS.append(self)
        return self


class _AttributeHookEnum(str, Enum):
    payload = "unsafe"

    def __getattribute__(self, name: str) -> Any:
        _ATTRIBUTE_HOOK_CALLS.append(name)
        return object.__getattribute__(self, name)


class _ReductionHookEnum(str, Enum):
    payload = "unsafe"

    def __reduce_ex__(self, protocol: int) -> tuple[type[_ReductionHookEnum], tuple[str]]:
        del protocol
        _REDUCTION_HOOK_CALLS.append(self)
        return type(self), (str(self),)


class _DeepcopyProbe:
    def __init__(self) -> None:
        self.deepcopy_calls = 0

    def __deepcopy__(self, memo: dict[int, Any]) -> _DeepcopyProbe:
        del memo
        self.deepcopy_calls += 1
        return self


class _HostileDict(dict[str, Any]):
    def __init__(self) -> None:
        super().__init__({"safe": "value"})
        self.hook_calls = 0

    def values(self) -> Any:
        self.hook_calls += 1
        raise AssertionError("custom dict iteration ran before admission")


class _HostileList(list[Any]):
    def __init__(self) -> None:
        super().__init__(["safe"])
        self.hook_calls = 0

    def __iter__(self) -> Any:
        self.hook_calls += 1
        raise AssertionError("custom list iteration ran before admission")


class _HostileTuple(tuple[Any, ...]):
    def __new__(cls) -> _HostileTuple:
        return super().__new__(cls, ("safe",))

    def __init__(self) -> None:
        self.hook_calls = 0

    def __iter__(self) -> Any:
        self.hook_calls += 1
        raise AssertionError("custom tuple iteration ran before admission")


class _DeepcopyString(str):
    def __new__(cls) -> _DeepcopyString:
        return super().__new__(cls, "unsafe")

    def __init__(self) -> None:
        self.deepcopy_calls = 0

    def __deepcopy__(self, memo: dict[int, Any]) -> _DeepcopyString:
        del memo
        self.deepcopy_calls += 1
        return self


class _ClassSpoofingProbe:
    def __init__(self) -> None:
        self.class_accesses = 0

    @property
    def __class__(self) -> type[BaseModel]:
        self.class_accesses += 1
        return BaseModel


def _artifact_ref(tag: str = "a") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{tag * 64}",
        kind="test.ref",
        media_type="application/json",
    )


def test_branch_state_isolates_declared_nested_write_path() -> None:
    shared_payload = {"stable": ["keep-shared"]}
    base_state = ExperimentState(
        run_id="R_branch",
        params={
            "shared": shared_payload,
            "nested": {"items": ["base"]},
        },
    )

    branch = branch_state(
        base_state,
        write_paths=("params.nested.items",),
    )
    branch_state_value = branch.state

    assert branch_state_value.params is not base_state.params
    assert branch_state_value.params["nested"] is not base_state.params["nested"]
    assert branch_state_value.params["nested"]["items"] is not base_state.params["nested"]["items"]
    assert branch_state_value.params["shared"] is base_state.params["shared"]
    assert branch.journal.isolated_paths == ("params.nested.items",)

    branch_state_value.params["nested"]["items"].append("branch")
    branch_state_value.params["branch_only"] = True

    assert base_state.params["nested"]["items"] == ["base"]
    assert "branch_only" not in base_state.params


def test_branch_state_uses_copy_on_write_overlay_for_nested_pydantic_models() -> None:
    holder = _BranchHolderModel(
        nested=_BranchNestedModel(
            items=["base"],
            untouched={"shared": ["keep-shared"]},
        )
    )
    base_state = ExperimentState.model_construct(
        run_id="R_model_overlay",
        params={"holder": holder},
    )

    branch = branch_state(
        base_state,
        write_paths=("params.holder.nested.items",),
    )
    branch_state_value = branch.state
    branch_holder = branch_state_value.params["holder"]
    base_holder = base_state.params["holder"]

    assert isinstance(branch_holder, _BranchHolderModel)
    assert isinstance(base_holder, _BranchHolderModel)
    assert branch_holder is not base_holder
    assert branch_holder.nested is not base_holder.nested
    assert branch_holder.nested.items is not base_holder.nested.items
    assert branch_holder.nested.untouched is base_holder.nested.untouched

    branch_holder.nested.items.append("branch")

    assert base_holder.nested.items == ["base"]
    assert base_holder.nested.untouched == {"shared": ["keep-shared"]}


# Production mutation caught: a declared mutable leaf must be deeply isolated
# so edits to nested elements cannot leak into the base or a sibling branch.
def test_branch_state_deeply_isolates_nested_elements_of_declared_leaf() -> None:
    base_state = ExperimentState(
        run_id="R_nested_leaf",
        params={"config": {"rows": [{"value": "base"}]}},
    )

    branch = branch_state(
        base_state,
        write_paths=("params.config.rows",),
    ).state
    branch.params["config"]["rows"][0]["value"] = "branch"

    assert branch.params["config"]["rows"] == [{"value": "branch"}]
    assert base_state.params["config"]["rows"] == [{"value": "base"}]


# Production mutation caught: declared top-level scalar/ref writes must be
# installed as journaled setters instead of being silently unobservable.
def test_branch_state_records_top_level_scalar_ref_assignment() -> None:
    base_state = ExperimentState(run_id="R_top_level_ref")
    branch = branch_state(base_state, write_paths=("preflight_report_ref",))
    report_ref = _artifact_ref()

    branch.state.preflight_report_ref = report_ref

    assert [(item.path, item.operation) for item in branch.journal.operations] == [
        ("preflight_report_ref", "set"),
    ]
    assert branch.journal.operations[0].value == report_ref


def test_snapshot_state_deep_clones_mutable_state_surfaces() -> None:
    base_state = ExperimentState(
        run_id="R_snapshot",
        params={"nested": {"items": ["base"]}},
        causal_method_params={"method": {"thresholds": [0.1]}},
    )

    snapshot = snapshot_state(base_state)
    snapshot.params["nested"]["items"].append("snapshot")
    snapshot.causal_method_params["method"]["thresholds"].append(0.2)

    assert base_state.params["nested"]["items"] == ["base"]
    assert base_state.causal_method_params["method"]["thresholds"] == [0.1]


def test_producer_admission_rejects_nested_custom_leaf_before_deepcopy() -> None:
    probe = _DeepcopyProbe()
    base_state = ExperimentState(run_id="R_unknown_nested_leaf")
    # ExperimentState.params deliberately has nested Any values; add after
    # normal model validation to exercise that actual runtime boundary.
    base_state.params["nested"] = {"rows": [{"probe": probe}]}

    with pytest.raises(TypeError, match="finite JSON container graph"):
        _validate_producer_state(base_state)

    assert probe.deepcopy_calls == 0


def test_producer_admission_rejects_custom_leaf_inside_ordinary_model() -> None:
    probe = _DeepcopyProbe()
    holder = _AnyHolderModel(payload=None)
    holder.payload = {"nested": [probe]}
    base_state = ExperimentState(run_id="R_model_custom_leaf")
    base_state.params["holder"] = holder

    with pytest.raises(TypeError, match="finite JSON container graph"):
        _validate_producer_state(base_state)

    assert probe.deepcopy_calls == 0


def test_declared_branch_rejects_custom_attachment_before_journaling() -> None:
    base_state = ExperimentState(run_id="R_custom_branch_attachment")
    branch = branch_state(
        base_state,
        write_paths=("params",),
        enforce_write_scope=True,
    )
    probe = _DeepcopyProbe()

    with pytest.raises(TypeError, match="finite JSON container graph"):
        branch.state.params["probe"] = probe

    assert probe.deepcopy_calls == 0
    assert "probe" not in branch.state.params
    assert branch.journal.operations == []


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        Decimal("NaN"),
        Decimal("Infinity"),
        {1: "non-json-key"},
        set(),
        bytearray(b"mutable"),
        memoryview(b"mutable-view"),
    ],
    ids=(
        "nan",
        "infinity",
        "decimal-nan",
        "decimal-infinity",
        "non-string-key",
        "set",
        "bytearray",
        "memoryview",
    ),
)
def test_producer_admission_rejects_non_finite_or_non_json_leaves(value: Any) -> None:
    base_state = ExperimentState(run_id="R_non_json_leaf")
    base_state.params["probe"] = value

    with pytest.raises(TypeError, match="finite JSON container graph"):
        _validate_producer_state(base_state)


@pytest.mark.parametrize(
    "container_factory",
    [_HostileDict, _HostileList, _HostileTuple],
    ids=("dict", "list", "tuple"),
)
def test_producer_admission_rejects_custom_container_before_iteration(
    container_factory: type[Any],
) -> None:
    hostile = container_factory()
    base_state = ExperimentState(run_id="R_custom_container")
    base_state.params["probe"] = hostile

    with pytest.raises(TypeError, match="finite JSON container graph"):
        _validate_producer_state(base_state)

    assert hostile.hook_calls == 0


def test_producer_admission_rejects_custom_scalar_subclass_before_deepcopy() -> None:
    value = _DeepcopyString()
    base_state = ExperimentState(run_id="R_custom_scalar_subclass")
    base_state.params["probe"] = value

    with pytest.raises(TypeError, match="finite JSON container graph"):
        _validate_producer_state(base_state)

    assert value.deepcopy_calls == 0


def test_producer_admission_classifies_actual_type_without_user_class_callback() -> None:
    probe = _ClassSpoofingProbe()
    base_state = ExperimentState(run_id="R_spoofed_class")
    base_state.params["probe"] = probe

    with pytest.raises(TypeError, match="finite JSON container graph"):
        _validate_producer_state(base_state)

    assert probe.class_accesses == 0


def test_producer_admission_rejects_over_depth_graph_before_copy() -> None:
    value: Any = "leaf"
    for _ in range(130):
        value = [value]
    base_state = ExperimentState(run_id="R_over_depth_graph")
    base_state.params["probe"] = value

    with pytest.raises(TypeError, match="finite JSON container graph"):
        _validate_producer_state(base_state)


def test_producer_admission_preserves_finite_json_and_typed_model_graphs() -> None:
    state = ExperimentState(
        run_id="R_finite_graph_positive",
        budgets={"compute": Decimal("0.25")},
        artifacts_index={"source": _artifact_ref("d")},
        params={
            "finite_float": 0.125,
            "nested": ("supported", 3, None),
            "immutable_tags": [b"bytes", date(2026, 10, 9), datetime(2026, 10, 9, tzinfo=UTC)],
        },
    )
    state.params["holder"] = _BranchHolderModel(
        nested=_BranchNestedModel(items=["model"], untouched={"keep": ["value"]})
    )

    _validate_producer_state(state)


def test_producer_admission_preserves_native_scalar_enum_fields() -> None:
    candidate = _NativeEnumModel(domain=_PolicyDomain.fiscal, label=_PolicyLabel.candidate)
    state = ExperimentState(run_id="R_native_enum_graph")
    state.params["candidate"] = candidate

    _validate_producer_state(state)

    assert state.params["candidate"] is candidate
    assert candidate.domain is _PolicyDomain.fiscal
    assert candidate.label is _PolicyLabel.candidate


def test_producer_admission_rejects_enum_copy_hooks_and_mutable_values_before_copy() -> None:
    _COPY_HOOK_CALLS.clear()
    _ATTRIBUTE_HOOK_CALLS.clear()
    _REDUCTION_HOOK_CALLS.clear()
    unsafe_members: tuple[Enum, ...] = (
        _CopyHookEnum.payload,
        _CopyOnlyEnum.payload,
        _AttributeHookEnum.payload,
        _ReductionHookEnum.payload,
        _EnumWithMutableValue.payload,
    )
    for index, member in enumerate(unsafe_members):
        state = ExperimentState(run_id=f"R_enum_unsafe_{index}")
        state.params["candidate"] = member
        with pytest.raises(TypeError, match="finite JSON container graph"):
            _validate_producer_state(state)

    assert _COPY_HOOK_CALLS == []
    assert _ATTRIBUTE_HOOK_CALLS == []
    assert _REDUCTION_HOOK_CALLS == []


@pytest.mark.parametrize(
    "nested_levels", [124, 125], ids=("canonical-boundary", "over-canonical-boundary")
)
def test_producer_admission_depth_matches_canonical_state_envelope(nested_levels: int) -> None:
    value: Any = "leaf"
    for _ in range(nested_levels):
        value = [value]
    state = ExperimentState(run_id=f"R_canonical_depth_{nested_levels}", params={"probe": value})
    spec = CanonSpec(forbid_floats=False, exclude_none=False)

    if nested_levels == 124:
        _validate_producer_state(state)
        to_canonical_bytes(state.model_dump(), spec)
    else:
        with pytest.raises(TypeError, match="finite JSON container graph"):
            _validate_producer_state(state)


def test_tracked_attachment_depth_includes_existing_canonical_parent_path() -> None:
    state = ExperimentState(run_id="R_nested_canonical_depth", params={"nested": {}})
    branch = branch_state(
        state,
        write_paths=("params.nested",),
        enforce_write_scope=True,
    )
    value: Any = "leaf"
    for _ in range(123):
        value = [value]

    with pytest.raises(TypeError, match="finite JSON container graph"):
        branch.state.params["nested"]["probe"] = value


def test_producer_admission_rejects_cycles_before_copy() -> None:
    cycle: list[Any] = []
    cycle.append(cycle)
    base_state = ExperimentState(run_id="R_cyclic_graph")
    base_state.params["probe"] = cycle

    with pytest.raises(ValueError, match="cyclic state mutation value"):
        _validate_producer_state(base_state)


def test_cache_replay_normalizes_specialized_artifact_refs() -> None:
    """Replay preserves the core state ref after a typed IR-ref journal round trip."""
    base_state = ExperimentState(run_id="R_specialized_ref_replay")
    branch = branch_state(base_state, write_paths=("artifacts_index",))
    ref = ContextAdaptiveParameterBundleRef(
        artifact_id=f"sha256:{'b' * 64}",
    )

    branch.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = ref
    recorded = branch.journal.operations[-1]
    serialized = recorded.model_dump(mode="python")
    reloaded = StateMutation.model_validate(serialized)
    replay_journal = mutation_journal_from_operations((reloaded,))
    assert canonical_state_mutation_operations((recorded,), require_complete=True) == (
        canonical_state_mutation_operations((reloaded,), require_complete=True)
    )
    outcome = NodeOutcome(status="ok", state=branch.state)

    merged = merge_parallel_outcomes(
        base_state,
        {"resolve": outcome},
        {
            "resolve": [
                f"artifacts_index.{ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF}",
            ],
        },
        mutation_journals={"resolve": replay_journal},
    )

    assert merged.applied
    replayed_ref = merged.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
    assert isinstance(replayed_ref, ArtifactRef)
    assert str(replayed_ref.artifact_id) == str(ref.artifact_id)


def test_journaled_model_equality_preserves_typed_values_and_tracking() -> None:
    class AlternateNestedModel(BaseModel):
        items: list[str]
        untouched: dict[str, list[str]]

    class CustomEqualityModel(BaseModel):
        value: str

        def __eq__(self, other: object) -> bool:
            return isinstance(other, CustomEqualityModel)

    class PrivateStateModel(BaseModel):
        value: str
        _private_value: str = PrivateAttr(default="private")

    class ExtraStateModel(BaseModel):
        model_config = ConfigDict(extra="allow")
        value: str

    reference = ArtifactRef(
        artifact_id=f"sha256:{'a' * 64}",
        kind="scientist.discovery_artifact_bundle",
        media_type="application/json",
    )
    nested = _BranchNestedModel(items=["x"], untouched={"k": ["v"]})
    holder = _AnyHolderModel(payload={"flag": True, "nested": nested})
    source = ExperimentState(
        run_id="R_journaled_model_value_equality",
        params={"reference": reference, "nested": nested, "holder": holder},
    )
    left = branch_state(source, write_paths=("params",))
    right = branch_state(source, write_paths=("params",))
    tracked_reference = left.state.params["reference"]
    tracked_nested = left.state.params["nested"]
    tracked_holder = left.state.params["holder"]

    assert isinstance(tracked_reference, ArtifactRef)
    assert tracked_reference == reference
    assert reference == tracked_reference
    assert tracked_reference == right.state.params["reference"]
    assert tracked_reference != ArtifactRef(
        artifact_id=reference.artifact_id,
        kind=reference.kind,
        media_type=reference.media_type,
        manifest_profile_sha256=f"sha256:{'b' * 64}",
    )
    assert tracked_nested == nested
    assert nested == tracked_nested
    assert tracked_holder != _AnyHolderModel(payload={"flag": 1, "nested": nested})
    assert tracked_holder != _AnyHolderModel(
        payload={
            "flag": True,
            "nested": AlternateNestedModel(items=["x"], untouched={"k": ["v"]}),
        }
    )

    tracked_reference.kind = "scientist.other_bundle"
    assert left.journal.operations[-1].path == ("params", "reference", "kind")
    assert reference.kind == "scientist.discovery_artifact_bundle"

    with pytest.raises(TypeError, match="ordinary BaseModel mutation/copy hooks"):
        branch_state(
            ExperimentState(
                run_id="R_custom_equality_model_refusal",
                params={"candidate": CustomEqualityModel(value="x")},
            ),
            write_paths=("params",),
        )
    with pytest.raises(TypeError, match="private or extra model runtime state"):
        branch_state(
            ExperimentState(
                run_id="R_private_equality_model_refusal",
                params={"candidate": PrivateStateModel(value="x")},
            ),
            write_paths=("params",),
        )
    with pytest.raises(TypeError, match="private or extra model runtime state"):
        branch_state(
            ExperimentState(
                run_id="R_extra_equality_model_refusal",
                params={"candidate": ExtraStateModel(value="x", unexpected="y")},
            ),
            write_paths=("params",),
        )


def test_cache_mutation_canonical_payload_preserves_operation_semantics() -> None:
    def operation(**overrides: Any) -> StateMutation:
        payload: dict[str, Any] = {
            "path": "params.value",
            "operation": "set",
            "value": None,
            "value_kind": "json",
            "index": None,
            "start": None,
            "stop": None,
            "step": None,
            "target_presence": "present",
            "target_kind": "scalar",
            "operation_group": None,
        }
        payload.update(overrides)
        return StateMutation.model_validate(payload)

    explicit_null = operation()
    boolean = operation(value=True)
    integer = operation(value=1)
    assert canonical_state_mutation_operations((boolean,), require_complete=True) != (
        canonical_state_mutation_operations((integer,), require_complete=True)
    )
    assert canonical_state_mutation_operations(
        (operation(value=1.0),), require_complete=True
    ) != canonical_state_mutation_operations((integer,), require_complete=True)
    assert canonical_state_mutation_operations(
        (operation(value=("a", "b")),), require_complete=True
    ) == canonical_state_mutation_operations(
        (operation(value=["a", "b"]),), require_complete=True
    )
    assert canonical_state_mutation_operations(
        (operation(value={"body": "left"}),), require_complete=True
    ) != canonical_state_mutation_operations(
        (operation(value={"body": "right"}),), require_complete=True
    )
    assert canonical_state_mutation_operations(
        (operation(path="params.first"), operation(path="params.second")),
        require_complete=True,
    ) != canonical_state_mutation_operations(
        (operation(path="params.second"), operation(path="params.first")),
        require_complete=True,
    )
    assert canonical_state_mutation_operations((operation(path="params.other"),)) != (
        canonical_state_mutation_operations((explicit_null,))
    )
    assert canonical_state_mutation_operations((operation(operation="delete"),)) != (
        canonical_state_mutation_operations((explicit_null,))
    )
    assert canonical_state_mutation_operations((operation(index=0),)) != (
        canonical_state_mutation_operations((explicit_null,))
    )
    assert canonical_state_mutation_operations((operation(target_kind="dict"),)) != (
        canonical_state_mutation_operations((explicit_null,))
    )
    assert canonical_state_mutation_operations((operation(operation_group=0),)) != (
        canonical_state_mutation_operations((explicit_null,))
    )

    missing_value = StateMutation.model_validate(
        {"path": "params.value", "operation": "set"}
    )
    assert canonical_state_mutation_operations((missing_value,)) != (
        canonical_state_mutation_operations((explicit_null,))
    )
    with pytest.raises(ValueError, match="incomplete state mutation fields"):
        canonical_state_mutation_operations((missing_value,), require_complete=True)
    with pytest.raises(ValueError, match="inconsistent state mutation operation group"):
        mutation_journal_from_operations(
            (operation(value=True, operation_group=0), operation(value=1, operation_group=0)),
            require_complete=True,
        )


def test_artifacts_index_rejects_malformed_specialized_ref_before_journaling() -> None:
    """Invalid typed refs fail before state or cache mutation is recorded."""
    base_state = ExperimentState(run_id="R_malformed_specialized_ref")
    branch = branch_state(base_state, write_paths=("artifacts_index",))
    malformed_ref = ContextAdaptiveParameterBundleRef.model_construct(
        artifact_id=IRArtifactID.model_construct(root="not-a-sha256-id"),
        kind="ir.context_adaptive_parameter_bundle",
        media_type="application/json",
    )

    with pytest.raises(ValidationError):
        branch.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = malformed_ref

    assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF not in branch.state.artifacts_index
    assert branch.journal.operations == []


def test_artifact_shaped_json_remains_json_outside_artifacts_index() -> None:
    """Ordinary JSON is not promoted to artifact authority based on field shape."""
    base_state = ExperimentState(run_id="R_artifact_shaped_json")
    branch = branch_state(base_state, write_paths=("params",))
    payload = {
        "artifact_id": f"sha256:{'c' * 64}",
        "kind": "ir.context_adaptive_parameter_bundle",
        "media_type": "application/json",
    }

    branch.state.params["caller_payload"] = payload

    mutation = branch.journal.operations[-1]
    assert mutation.value_kind == "json"
    assert mutation.value == payload
