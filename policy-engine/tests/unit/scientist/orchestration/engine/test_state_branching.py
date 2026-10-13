"""Regression tests for bounded state branching hot paths."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from typing import Any, Generic, TypeVar

import pytest
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, RootModel, ValidationError

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
    _completed_producer_value,
    _validate_producer_state,
    branch_state,
    canonical_state_mutation_operations,
    mutation_journal_for_state,
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


_ModelValue = TypeVar("_ModelValue")


# These Pydantic fixtures must retain typing.Generic's canonical hook so the
# admission and native generic-origin behavior under test remain representative.
class _GenericEqualityModel(BaseModel, Generic[_ModelValue]):  # noqa: UP046 -- canonical Pydantic generic-hook fixture
    value: _ModelValue


class _AlternateGenericEqualityModel(BaseModel, Generic[_ModelValue]):  # noqa: UP046 -- canonical Pydantic generic-hook fixture
    value: _ModelValue


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

    class AnyRootValue(RootModel[Any]):
        pass

    class AlternateAnyRootValue(RootModel[Any]):
        pass

    class IntegerRootValue(RootModel[int]):
        pass

    # Keep the bare generic RootModel profile under the canonical typing hook.
    class GenericRootValue(RootModel[_ModelValue], Generic[_ModelValue]):  # noqa: UP046 -- canonical Pydantic generic-hook fixture
        pass

    class PayloadArtifactRef(ArtifactRef):
        payload: Any

    class CustomEqualityModel(PayloadArtifactRef):
        def __eq__(self, other: object) -> bool:
            return isinstance(other, CustomEqualityModel)

    class CustomInequalityModel(PayloadArtifactRef):
        def __ne__(self, other: object) -> bool:
            return False

    class CustomGenericEqualityModel(PayloadArtifactRef, Generic[_ModelValue]):
        value: _ModelValue

        def __init_subclass__(cls, **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)

    class PrivateStateModel(PayloadArtifactRef):
        _private_value: str = PrivateAttr(default="private")

    class ExtraStateModel(PayloadArtifactRef):
        model_config = ConfigDict(extra="allow")

    reference = PayloadArtifactRef(
        artifact_id=f"sha256:{'a' * 64}",
        kind="scientist.discovery_artifact_bundle",
        media_type="application/json",
        payload={
            "flag": True,
            "nested": _BranchNestedModel(items=["x"], untouched={"k": ["v"]}),
            "root": AnyRootValue(root={"flag": True, "values": [None, False, 1, "x"]}),
        },
    )
    source = ExperimentState(
        run_id="R_journaled_model_value_equality",
        artifacts_index={"reference": reference},
    )
    left = branch_state(source, write_paths=("artifacts_index",))
    right = branch_state(source, write_paths=("artifacts_index",))
    tracked_reference = left.state.artifacts_index["reference"]
    tracked_nested = tracked_reference.payload["nested"]
    tracked_root = tracked_reference.payload["root"]

    assert isinstance(reference, PayloadArtifactRef)
    assert isinstance(tracked_reference, PayloadArtifactRef)
    assert tracked_reference == reference
    assert reference == tracked_reference
    assert tracked_reference.model_fields_set == reference.model_fields_set
    assert tracked_reference == right.state.artifacts_index["reference"]
    unrelated_value = object()
    assert tracked_reference.__eq__(unrelated_value) is NotImplemented
    assert tracked_reference.__ne__(unrelated_value) is NotImplemented
    assert (tracked_reference == unrelated_value) is False
    assert (tracked_reference != unrelated_value) is True
    explicitly_null_profile = PayloadArtifactRef(
        artifact_id=reference.artifact_id,
        kind=reference.kind,
        media_type=reference.media_type,
        manifest_profile_sha256=None,
        payload=reference.payload,
    )
    assert "manifest_profile_sha256" not in reference.model_fields_set
    assert "manifest_profile_sha256" in explicitly_null_profile.model_fields_set
    # Pydantic equality is value-based and ignores model_fields_set.
    assert reference == explicitly_null_profile
    assert explicitly_null_profile == reference
    assert tracked_reference == explicitly_null_profile
    assert explicitly_null_profile == tracked_reference
    assert tracked_reference != PayloadArtifactRef(
        artifact_id=reference.artifact_id,
        kind=reference.kind,
        media_type=reference.media_type,
        manifest_profile_sha256=f"sha256:{'b' * 64}",
        payload=reference.payload,
    )
    assert tracked_nested == reference.payload["nested"]
    assert reference.payload["nested"] == tracked_nested

    # Preserve Pydantic's generic-origin rule across the tracking projection.
    generic_int = _GenericEqualityModel[int](value=1)
    generic_any = _GenericEqualityModel[Any](value=1)
    generic_bare = _GenericEqualityModel(value=1)
    bare_generic_metadata = generic_bare.__pydantic_generic_metadata__
    assert bare_generic_metadata["origin"] is None
    assert bare_generic_metadata["parameters"]
    assert generic_int == generic_any
    assert generic_any == generic_int
    assert generic_bare == generic_int
    assert generic_int == generic_bare
    assert generic_bare == generic_any
    assert generic_any == generic_bare
    generic_ref = PayloadArtifactRef(
        artifact_id=reference.artifact_id,
        kind=reference.kind,
        media_type=reference.media_type,
        payload=generic_int,
    )
    generic_state = ExperimentState(
        run_id="R_generic_model_value_equality",
        artifacts_index={"generic": generic_ref},
    )
    tracked_generic = branch_state(
        generic_state, write_paths=("artifacts_index",)
    ).state.artifacts_index["generic"].payload
    assert tracked_generic == generic_any
    assert generic_any == tracked_generic
    source_generic_metadata = generic_int.__pydantic_generic_metadata__
    tracked_generic_metadata = tracked_generic.__pydantic_generic_metadata__
    assert tracked_generic_metadata is not source_generic_metadata
    assert dict(tracked_generic_metadata) == dict(source_generic_metadata)

    copied_generic = tracked_generic.model_copy()
    assert copied_generic == generic_any
    assert generic_any == copied_generic
    deep_copied_generic = tracked_generic.model_copy(deep=True)
    assert deep_copied_generic == generic_any
    assert generic_any == deep_copied_generic
    completed_generic = _completed_producer_value(tracked_generic)
    assert type(completed_generic) is type(generic_int)
    assert dict(completed_generic.__pydantic_generic_metadata__) == dict(
        source_generic_metadata
    )
    assert completed_generic == generic_any
    assert generic_any == completed_generic

    # The full wrapper metadata preserves a bare class's native effective origin.
    generic_bare_ref = PayloadArtifactRef(
        artifact_id=reference.artifact_id,
        kind=reference.kind,
        media_type=reference.media_type,
        payload=generic_bare,
    )
    generic_bare_state = ExperimentState(
        run_id="R_bare_generic_model_value_equality",
        artifacts_index={"generic": generic_bare_ref},
    )
    tracked_bare_generic = branch_state(
        generic_bare_state, write_paths=("artifacts_index",)
    ).state.artifacts_index["generic"].payload
    tracked_bare_metadata = tracked_bare_generic.__pydantic_generic_metadata__
    expected_bare_metadata = dict(bare_generic_metadata)
    expected_bare_metadata["origin"] = type(generic_bare)
    assert tracked_bare_metadata is not bare_generic_metadata
    assert dict(tracked_bare_metadata) == expected_bare_metadata
    assert bare_generic_metadata["origin"] is None
    for ordinary_generic in (generic_bare, generic_int, generic_any):
        assert tracked_bare_generic == ordinary_generic
        assert ordinary_generic == tracked_bare_generic

    for copied_bare_generic in (
        tracked_bare_generic.model_copy(),
        tracked_bare_generic.model_copy(deep=True),
    ):
        assert type(copied_bare_generic) is type(tracked_bare_generic)
        for ordinary_generic in (generic_bare, generic_int, generic_any):
            assert copied_bare_generic == ordinary_generic
            assert ordinary_generic == copied_bare_generic
    completed_bare_generic = _completed_producer_value(tracked_bare_generic)
    assert type(completed_bare_generic) is type(generic_bare)
    assert dict(completed_bare_generic.__pydantic_generic_metadata__) == dict(
        bare_generic_metadata
    )
    for ordinary_generic in (generic_bare, generic_int, generic_any):
        assert completed_bare_generic == ordinary_generic
        assert ordinary_generic == completed_bare_generic

    alternate_generic = _AlternateGenericEqualityModel[Any](value=1)
    assert generic_int != alternate_generic
    assert tracked_generic != alternate_generic
    assert alternate_generic != tracked_generic
    assert generic_bare != alternate_generic
    assert alternate_generic != generic_bare
    assert tracked_bare_generic != alternate_generic
    assert alternate_generic != tracked_bare_generic

    # Empty built-in extra state is preserved while non-empty state stays refused.
    empty_extra = ExtraStateModel(
        artifact_id=reference.artifact_id,
        kind=reference.kind,
        media_type=reference.media_type,
        payload=reference.payload,
    )
    empty_extra_state = ExperimentState(
        run_id="R_empty_extra_model_value_equality",
        artifacts_index={"extra": empty_extra},
    )
    tracked_empty_extra = branch_state(
        empty_extra_state, write_paths=("artifacts_index",)
    ).state.artifacts_index["extra"]
    assert tracked_empty_extra.__pydantic_extra__ == empty_extra.__pydantic_extra__
    assert tracked_empty_extra.__pydantic_private__ == empty_extra.__pydantic_private__
    assert tracked_empty_extra == empty_extra
    assert empty_extra == tracked_empty_extra
    with pytest.raises(
        TypeError, match="state mutation journaling requires a declared model field"
    ):
        tracked_empty_extra.unexpected = "not replayable"
    assert tracked_empty_extra.__pydantic_extra__ == empty_extra.__pydantic_extra__

    # Pydantic ignores non-field __dict__ entries when its field fallback runs.
    non_field_copy = reference.model_copy()
    non_field_copy.__dict__["engine_equality_probe"] = "ignored"
    assert reference == non_field_copy
    assert tracked_reference == non_field_copy
    assert non_field_copy == tracked_reference

    alternate_nested = AlternateNestedModel(items=["x"], untouched={"k": ["v"]})
    assert tracked_nested != alternate_nested
    assert alternate_nested != tracked_nested

    # RootModel wrappers compare their typed root recursively and symmetrically.
    assert tracked_root == reference.payload["root"]
    assert reference.payload["root"] == tracked_root
    assert tracked_reference.artifact_id == reference.artifact_id
    assert reference.artifact_id == tracked_reference.artifact_id
    alternate_type = AlternateAnyRootValue(root={"flag": True, "values": [None, False, 1, "x"]})
    assert tracked_root != alternate_type
    assert alternate_type != tracked_root
    different_bool_value = AnyRootValue(root={"flag": 1, "values": [None, False, 1, "x"]})
    # Values inside Any use ordinary Python equality, where True == 1.
    assert reference.payload["root"] == different_bool_value
    assert tracked_root == different_bool_value
    assert different_bool_value == tracked_root
    int_root = IntegerRootValue(root=1)
    any_int_root = AnyRootValue(root=1)
    assert int_root != any_int_root
    typed_root_ref = PayloadArtifactRef(
        artifact_id=reference.artifact_id,
        kind=reference.kind,
        media_type=reference.media_type,
        payload=int_root,
    )
    typed_root_state = ExperimentState(
        run_id="R_typed_root_annotation_equality",
        artifacts_index={"root": typed_root_ref},
    )
    tracked_int_root = branch_state(
        typed_root_state, write_paths=("artifacts_index",)
    ).state.artifacts_index["root"].payload
    assert tracked_int_root != any_int_root
    assert any_int_root != tracked_int_root

    # Parameterized RootModel metadata survives wrapper installation and copies.
    parameterized_root = RootModel[int](root=1)
    parameterized_root_ref = PayloadArtifactRef(
        artifact_id=reference.artifact_id,
        kind=reference.kind,
        media_type=reference.media_type,
        payload=parameterized_root,
    )
    parameterized_root_state = ExperimentState(
        run_id="R_parameterized_root_metadata_equality",
        artifacts_index={"root": parameterized_root_ref},
    )
    tracked_parameterized_root = branch_state(
        parameterized_root_state, write_paths=("artifacts_index",)
    ).state.artifacts_index["root"].payload
    source_root_metadata = parameterized_root.__pydantic_generic_metadata__
    tracked_root_metadata = tracked_parameterized_root.__pydantic_generic_metadata__
    assert tracked_root_metadata is not source_root_metadata
    assert dict(tracked_root_metadata) == dict(source_root_metadata)
    assert tracked_parameterized_root == parameterized_root
    assert parameterized_root == tracked_parameterized_root
    copied_parameterized_root = tracked_parameterized_root.model_copy(deep=True)
    assert copied_parameterized_root == parameterized_root
    assert parameterized_root == copied_parameterized_root
    completed_parameterized_root = _completed_producer_value(tracked_parameterized_root)
    assert type(completed_parameterized_root) is type(parameterized_root)
    assert dict(completed_parameterized_root.__pydantic_generic_metadata__) == dict(
        source_root_metadata
    )
    assert completed_parameterized_root == parameterized_root
    assert parameterized_root == completed_parameterized_root

    # Bare generic RootModel metadata gets an effective origin on the wrapper copy.
    bare_generic_root = GenericRootValue(root=1)
    bare_root_metadata = bare_generic_root.__pydantic_generic_metadata__
    assert bare_root_metadata["origin"] is None
    assert bare_root_metadata["parameters"]
    bare_generic_root_ref = PayloadArtifactRef(
        artifact_id=reference.artifact_id,
        kind=reference.kind,
        media_type=reference.media_type,
        payload=bare_generic_root,
    )
    bare_generic_root_state = ExperimentState(
        run_id="R_bare_generic_root_model_equality",
        artifacts_index={"root": bare_generic_root_ref},
    )
    tracked_bare_generic_root = branch_state(
        bare_generic_root_state, write_paths=("artifacts_index",)
    ).state.artifacts_index["root"].payload
    expected_bare_root_metadata = dict(bare_root_metadata)
    expected_bare_root_metadata["origin"] = type(bare_generic_root)
    assert tracked_bare_generic_root.__pydantic_generic_metadata__ is not bare_root_metadata
    assert dict(tracked_bare_generic_root.__pydantic_generic_metadata__) == expected_bare_root_metadata
    assert tracked_bare_generic_root == bare_generic_root
    assert bare_generic_root == tracked_bare_generic_root

    specialized_generic_root = GenericRootValue[int](root=1)
    # RootModel keeps its independent root-annotation constraint.
    assert bare_generic_root != specialized_generic_root
    assert specialized_generic_root != bare_generic_root
    assert tracked_bare_generic_root != specialized_generic_root
    assert specialized_generic_root != tracked_bare_generic_root
    for copied_bare_root in (
        tracked_bare_generic_root.model_copy(),
        tracked_bare_generic_root.model_copy(deep=True),
    ):
        assert copied_bare_root == bare_generic_root
        assert bare_generic_root == copied_bare_root
    completed_bare_root = _completed_producer_value(tracked_bare_generic_root)
    assert type(completed_bare_root) is type(bare_generic_root)
    assert dict(completed_bare_root.__pydantic_generic_metadata__) == dict(
        bare_root_metadata
    )
    assert completed_bare_root == bare_generic_root
    assert bare_generic_root == completed_bare_root

    changed_payload = PayloadArtifactRef(
        artifact_id=reference.artifact_id,
        kind=reference.kind,
        media_type=reference.media_type,
        payload={
            "flag": 1,
            "nested": reference.payload["nested"],
            "root": reference.payload["root"],
        },
    )
    assert reference == changed_payload
    assert changed_payload == reference
    assert tracked_reference == changed_payload
    assert changed_payload == tracked_reference

    # Drive every field declared by the actual public ArtifactRef-derived schema.
    complete_reference = PayloadArtifactRef(
        artifact_id=reference.artifact_id,
        kind=reference.kind,
        media_type=reference.media_type,
        manifest_profile_sha256=f"sha256:{'c' * 64}",
        payload=reference.payload,
    )
    complete_state = ExperimentState(
        run_id="R_complete_declared_model_fields",
        artifacts_index={"reference": complete_reference},
    )
    complete_tracked = branch_state(
        complete_state, write_paths=("artifacts_index",)
    ).state.artifacts_index["reference"]
    changed_payload_value = dict(reference.payload)
    changed_payload_value["flag"] = "different"
    changed_values = {
        "artifact_id": IRArtifactID(f"sha256:{'d' * 64}"),
        "kind": "scientist.other_bundle",
        "media_type": "application/x-policyos-other",
        "manifest_profile_sha256": f"sha256:{'e' * 64}",
        "payload": changed_payload_value,
    }
    assert set(changed_values) == set(PayloadArtifactRef.model_fields)
    for field_name, changed_value in changed_values.items():
        candidate = complete_reference.model_copy(update={field_name: changed_value})
        assert candidate.model_fields_set == complete_reference.model_fields_set
        assert complete_tracked != candidate
        assert candidate != complete_tracked

    # Exercise the generic root-value path over scalar and recursive containers.
    for ordinal, root_value in enumerate((None, False, 1, "text", [False, 1], {"flag": True})):
        candidate = PayloadArtifactRef(
            artifact_id=reference.artifact_id,
            kind=reference.kind,
            media_type=reference.media_type,
            payload=AnyRootValue(root=root_value),
        )
        candidate_state = ExperimentState(
            run_id=f"R_root_model_value_{ordinal}",
            artifacts_index={"candidate": candidate},
        )
        candidate_branch = branch_state(candidate_state, write_paths=("artifacts_index",))
        tracked_candidate = candidate_branch.state.artifacts_index["candidate"]
        assert tracked_candidate.payload == candidate.payload
        assert candidate.payload == tracked_candidate.payload

    tracked_reference.kind = "scientist.other_bundle"
    assert left.journal.operations[-1].path == "artifacts_index.reference.kind"
    assert reference.kind == "scientist.discovery_artifact_bundle"

    def candidate_state(candidate: ArtifactRef, run_id: str) -> ExperimentState:
        return ExperimentState(run_id=run_id, artifacts_index={"candidate": candidate})

    # Generic metadata does not waive a custom subclass-hook refusal.
    ordinary_model_refusal = (
        "state mutation journaling requires ordinary BaseModel mutation/copy hooks"
    )
    private_or_extra_refusal = (
        "state mutation journaling refuses private or extra model runtime state"
    )
    invalid_refs = (
        (
            CustomEqualityModel(
                artifact_id=reference.artifact_id,
                kind=reference.kind,
                media_type=reference.media_type,
                payload=None,
            ),
            ordinary_model_refusal,
        ),
        (
            CustomInequalityModel(
                artifact_id=reference.artifact_id,
                kind=reference.kind,
                media_type=reference.media_type,
                payload=None,
            ),
            ordinary_model_refusal,
        ),
        (
            CustomGenericEqualityModel[int](
                artifact_id=reference.artifact_id,
                kind=reference.kind,
                media_type=reference.media_type,
                payload=None,
                value=1,
            ),
            ordinary_model_refusal,
        ),
        (
            PrivateStateModel(
                artifact_id=reference.artifact_id,
                kind=reference.kind,
                media_type=reference.media_type,
                payload=None,
            ),
            ordinary_model_refusal,
        ),
        (
            ExtraStateModel(
                artifact_id=reference.artifact_id,
                kind=reference.kind,
                media_type=reference.media_type,
                payload=None,
                unexpected="y",
            ),
            private_or_extra_refusal,
        ),
    )
    for ordinal, (candidate, expected_error) in enumerate(invalid_refs):
        source = candidate_state(candidate, f"R_model_equality_refusal_{ordinal}")
        model_values = dict.copy(object.__getattribute__(candidate, "__dict__"))
        model_fields_set = set(candidate.model_fields_set)
        private_state = object.__getattribute__(candidate, "__pydantic_private__")
        private_values = None if private_state is None else dict.copy(private_state)
        extra_state = object.__getattribute__(candidate, "__pydantic_extra__")
        extra_values = None if extra_state is None else dict.copy(extra_state)

        assert mutation_journal_for_state(source) is None
        with pytest.raises(TypeError) as refusal:
            branch_state(
                source,
                write_paths=("artifacts_index",),
                enforce_write_scope=True,
            )

        assert str(refusal.value) == expected_error
        assert tuple(source.artifacts_index) == ("candidate",)
        assert source.artifacts_index["candidate"] is candidate
        assert dict.copy(object.__getattribute__(candidate, "__dict__")) == model_values
        assert set(candidate.model_fields_set) == model_fields_set
        current_private = object.__getattribute__(candidate, "__pydantic_private__")
        current_extra = object.__getattribute__(candidate, "__pydantic_extra__")
        assert current_private == private_values
        assert current_extra == extra_values
        assert mutation_journal_for_state(source) is None

def test_journaled_model_wrapper_preserves_exact_private_and_extra_slots() -> None:
    class SlotStateArtifactRef(ArtifactRef):
        model_config = ConfigDict(extra="allow")

        payload: Any

    def make_reference() -> SlotStateArtifactRef:
        return SlotStateArtifactRef(
            artifact_id=f"sha256:{'c' * 64}",
            kind="scientist.discovery_artifact_bundle",
            media_type="application/json",
            payload={"basis": "runtime-slot-shape"},
        )

    references: dict[str, SlotStateArtifactRef] = {}
    paired_keys: dict[str, tuple[str, str]] = {}
    for pair_name, slot_name in (
        ("private", "__pydantic_private__"),
        ("extra", "__pydantic_extra__"),
    ):
        absent = make_reference()
        empty = absent.model_copy()
        object.__setattr__(absent, slot_name, None)
        object.__setattr__(empty, slot_name, {})
        assert object.__getattribute__(absent, slot_name) is None
        empty_state = object.__getattribute__(empty, slot_name)
        assert type(empty_state) is dict
        assert dict.__len__(empty_state) == 0
        # Keep the pinned native relation: absence and an empty slot are distinct.
        assert absent != empty
        assert empty != absent

        absent_key = f"{pair_name}_absent"
        empty_key = f"{pair_name}_empty"
        references[absent_key] = absent
        references[empty_key] = empty
        paired_keys[pair_name] = (absent_key, empty_key)

    branch = branch_state(
        ExperimentState(
            run_id="R_journaled_runtime_slot_shape",
            artifacts_index=references,
        ),
        write_paths=("artifacts_index",),
    )
    tracked_references = branch.state.artifacts_index
    for key, source in references.items():
        tracked = tracked_references[key]
        assert isinstance(tracked, SlotStateArtifactRef)
        for slot_name in ("__pydantic_private__", "__pydantic_extra__"):
            source_slot = object.__getattribute__(source, slot_name)
            tracked_slot = object.__getattribute__(tracked, slot_name)
            assert type(tracked_slot) is type(source_slot)
            assert tracked_slot == source_slot
        assert tracked == source
        assert source == tracked

        completed = _completed_producer_value(tracked)
        assert type(completed) is SlotStateArtifactRef
        for slot_name in ("__pydantic_private__", "__pydantic_extra__"):
            source_slot = object.__getattribute__(source, slot_name)
            completed_slot = object.__getattribute__(completed, slot_name)
            assert type(completed_slot) is type(source_slot)
            assert completed_slot == source_slot
        assert completed == source
        assert source == completed

    for absent_key, empty_key in paired_keys.values():
        tracked_absent = tracked_references[absent_key]
        tracked_empty = tracked_references[empty_key]
        assert tracked_absent != tracked_empty
        assert tracked_empty != tracked_absent
        completed_absent = _completed_producer_value(tracked_absent)
        completed_empty = _completed_producer_value(tracked_empty)
        assert completed_absent != completed_empty
        assert completed_empty != completed_absent



def test_journaled_cow_preserves_field_presence_until_producer_assignment() -> None:
    class PresenceModel(BaseModel):
        model_config = ConfigDict(populate_by_name=True)

        items: list[int] = Field(default_factory=lambda: [1], alias="wireItems")
        mapping: dict[str, list[int]] = Field(
            default_factory=lambda: {"selected": [2]}
        )
        optional_label: str | None = Field(default=None, alias="wireLabel")

    class PresenceRoot(RootModel[dict[str, PresenceModel]]):
        pass

    class PayloadArtifactRef(ArtifactRef):
        payload: Any

    records = (
        PresenceModel(),
        PresenceModel.model_validate({"wireItems": [1]}),
    )
    for ordinal, record in enumerate(records):
        original_fields_set = set(record.model_fields_set)
        if ordinal == 0:
            assert original_fields_set == set()
        else:
            # Alias input is normalized to the declared Python field name.
            assert original_fields_set == {"items"}

        root_value = PresenceRoot(root={"first": record})
        reference = PayloadArtifactRef(
            artifact_id=f"sha256:{'f' * 64}",
            kind="scientist.presence_probe",
            media_type="application/json",
            payload=root_value,
        )
        state = ExperimentState(
            run_id=f"R_cow_field_presence_{ordinal}",
            artifacts_index={"reference": reference},
        )
        prefix = "artifacts_index.reference"
        branch = branch_state(
            state,
            write_paths=(
                f"{prefix}.payload.root.first.items.0",
                f"{prefix}.payload.root.first.mapping.selected.0",
                f"{prefix}.payload.root.first.optional_label",
            ),
        )
        tracked_reference = branch.state.artifacts_index["reference"]
        tracked_root = tracked_reference.payload
        tracked_record = tracked_root.root["first"]

        # Deep COW crosses an ArtifactRef, typed RootModel, mapping, model and
        # default-factory list/dict. Installing those copies is not a producer write.
        assert isinstance(tracked_root, PresenceRoot)
        assert tracked_record.model_fields_set == original_fields_set
        assert tracked_record == record
        assert record == tracked_record
        assert tracked_record.items is not record.items
        assert tracked_record.mapping is not record.mapping
        assert tracked_record.mapping["selected"] is not record.mapping["selected"]
        assert branch.journal.operations == []

        # Reads through the tracking wrappers retain both field presence and an empty journal.
        _ = tracked_record.items[0]
        _ = tracked_record.mapping["selected"][0]
        _ = tracked_record.optional_label
        assert tracked_record.model_fields_set == original_fields_set
        assert branch.journal.operations == []

        # A real typed assignment changes presence and journals even when
        # Pydantic value equality stays true for the same explicit None value.
        tracked_record.optional_label = None
        assert "optional_label" in tracked_record.model_fields_set
        assert "optional_label" not in record.model_fields_set
        assert "wireLabel" not in tracked_record.model_fields_set
        assert tracked_record == record
        assert record == tracked_record
        assignment = branch.journal.operations[-1]
        assert assignment.path == (
            "artifacts_index.reference.payload.root.first.optional_label"
        )
        assert assignment.operation == "set"
        assert assignment.value is None
        with pytest.raises(TypeError, match="model field deletion is not replayable"):
            del tracked_record.optional_label
        assert tracked_record.optional_label is None
        assert "optional_label" in tracked_record.model_fields_set
        assert len(branch.journal.operations) == 1

        tracked_record.items[0] = 9
        tracked_record.mapping["selected"][0] = 8
        assert record.items == [1]
        assert record.mapping == {"selected": [2]}
        assert tracked_record.items == [9]
        assert tracked_record.mapping == {"selected": [8]}
        assert tracked_record != record
        assert record != tracked_record
        assert len(branch.journal.operations) == 3


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
