"""Engine-owned physical node inputs and their persisted attempt basis.

The full predecessor is retained only by the executor. This is a state contract
boundary, not a Python, filesystem, or arbitrary artifact-store sandbox.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal, TypeGuard

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    CoreJSONArtifactBoundedManifestReader,
    CoreJSONArtifactBoundedManifestReceiptReader,
    CoreJSONArtifactBoundedMemberReader,
    CoreJSONArtifactStreamingReader,
    InputRef,
    RawManifestBytesReader,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    matches_runtime_protocol_definition,
)
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.run.manifest import RunInvocationImplementationIdentity
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeInputContract,
    NodeOutcome,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    _completed_producer_value,
    mutation_journal_for_state,
)
from polisyos.scientist.orchestration.engine.state_merge import merge_parallel_outcomes

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from polisyos.core.artifacts import (
        ArtifactBoundedManifestRead,
        ArtifactID,
        ArtifactManifest,
        ArtifactStore,
        CoreJSONArtifactBoundedMemberAttempt,
        CoreJSONArtifactMemberStream,
        VerificationReport,
    )
    from polisyos.core.run.manifest import RunInvocationStarted
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

_INPUT_BASIS_ROLE = "node_input_basis"
_INPUT_BASIS_KIND = "scientist.node_input_basis"
_INPUT_BASIS_SCHEMA = "polisyos.scientist.orchestration.engine.NodeInputBasis"
_CANON = CanonSpec(forbid_floats=False, sort_keys=True, exclude_none=False)
_MISSING = object()


class NodeInputPortError(ValueError):
    """A selected component input or its attempt binding is not established."""


def _state_bytes(state: ExperimentState) -> bytes:
    return to_canonical_bytes(state.model_dump(mode="python"), _CANON)


def _value_at(state: ExperimentState, path: str) -> Any:
    current: Any = state
    for part in path.split("."):
        if isinstance(current, BaseModel):
            current = getattr(current, part, _MISSING)
        elif isinstance(current, dict):
            current = current.get(part, _MISSING)
        else:
            return _MISSING
    return current


def _project(state: ExperimentState, contract: NodeInputContract) -> ExperimentState:
    projected = ExperimentState(run_id=state.run_id)
    for path in contract.state_paths:
        value = _value_at(state, path)
        if value is _MISSING:
            continue
        value = _completed_producer_value(value)
        parts = path.split(".")
        if len(parts) == 1:
            setattr(projected, path, value)
            continue
        target = getattr(projected, parts[0])
        for part in parts[1:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    return projected


class NodeInputBasis(BaseModel):
    """Bind the consumed projection to an exact predecessor, contract and attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    node_alias: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    attempt_number: int = Field(ge=1)
    contract: NodeInputContract
    implementation_identity: RunInvocationImplementationIdentity
    implementation_dependencies_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bind_params: dict[str, Any]
    predecessor_state_ref: ArtifactRef
    projected_state_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    path_presence: dict[str, Literal["missing", "null", "value"]]
    execution_kind: Literal["producer", "cache_replay"] = "producer"
    source_cache_entry_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _validate_basis(self) -> NodeInputBasis:
        if (
            self.predecessor_state_ref.manifest_profile_sha256 is None
            or self.implementation_identity.component_id != self.contract.component_id
            or set(self.path_presence) != set(self.contract.state_paths)
            or (self.execution_kind == "cache_replay") != (self.source_cache_entry_ref is not None)
            or (
                self.source_cache_entry_ref is not None
                and self.source_cache_entry_ref.manifest_profile_sha256 is None
            )
        ):
            raise ValueError("node_input_basis_identity_invalid")
        return self


def input_basis_options(basis: NodeInputBasis) -> ArtifactWriteOptions:
    """Use existing CAS lineage for this Engine-owned input binding."""
    inputs = [input_ref_from_artifact_ref(basis.predecessor_state_ref, role="predecessor")]
    if basis.source_cache_entry_ref is not None:
        inputs.append(input_ref_from_artifact_ref(basis.source_cache_entry_ref, role="cache_entry"))
    return ArtifactWriteOptions(
        kind=_INPUT_BASIS_KIND,
        media_type="application/json",
        schema=SchemaInfo(name=_INPUT_BASIS_SCHEMA, version="1.0"),
        inputs=inputs,
    )


@dataclass(frozen=True)
class NodeInputSelection:
    """Safe selected input coordinates; carries no predecessor or completion grant."""

    run_id: str
    component_id: str
    contract_id: str
    node_alias: str
    attempt_id: str
    basis_ref: ArtifactRef
    input_state_ref: ArtifactRef


def _selected_refs(state: ExperimentState, contract: NodeInputContract) -> tuple[ArtifactRef, ...]:
    refs = []
    for path in contract.artifact_ref_paths:
        value = _value_at(state, path)
        if value is _MISSING or value is None:
            continue
        try:
            ref = ArtifactRef.model_validate(
                value.model_dump() if isinstance(value, ArtifactRef) else value
            )
        except (TypeError, ValueError) as exc:
            raise NodeInputPortError("node_input_artifact_role_invalid") from exc
        if ref.manifest_profile_sha256 is None:
            raise NodeInputPortError("node_input_selected_profile_missing")
        refs.append(ref)
    return tuple(refs)


def _supports_raw_manifest(store: object) -> TypeGuard[RawManifestBytesReader]:
    return matches_runtime_protocol_definition(store, RawManifestBytesReader)


def _supports_bounded_manifest(store: object) -> TypeGuard[CoreJSONArtifactBoundedManifestReader]:
    return matches_runtime_protocol_definition(store, CoreJSONArtifactBoundedManifestReader)


def _supports_manifest_receipt(
    store: object,
) -> TypeGuard[CoreJSONArtifactBoundedManifestReceiptReader]:
    return matches_runtime_protocol_definition(store, CoreJSONArtifactBoundedManifestReceiptReader)


def _supports_streaming(store: object) -> TypeGuard[CoreJSONArtifactStreamingReader]:
    return matches_runtime_protocol_definition(store, CoreJSONArtifactStreamingReader)


def _supports_bounded_member(store: object) -> TypeGuard[CoreJSONArtifactBoundedMemberReader]:
    return matches_runtime_protocol_definition(store, CoreJSONArtifactBoundedMemberReader)


class _NodeInputStore:
    """Use the existing CAS owner only for selected inputs and this producer's writes.

    No root path, raw owner, inventory or blanket delegation is exposed. The
    selected input's manifest may describe audit lineage; following that lineage
    does not enroll its inaccessible basis or full predecessor for node reads.
    """

    __slots__ = (
        "__definition_sha256",
        "__identity",
        "__lock",
        "__node",
        "__params",
        "__refs",
        "__store",
    )

    def __init__(
        self,
        store: ArtifactStore,
        state: ExperimentState,
        node: Any,
        params: dict[str, Any],
        identity: RunInvocationImplementationIdentity,
        contract: NodeInputContract,
        selection: NodeInputSelection | None = None,
        *,
        definition_sha256: str,
    ) -> None:
        self.__definition_sha256 = definition_sha256
        self.__store = store
        self.__lock = RLock()
        refs = _selected_refs(state, contract)
        if selection is not None:
            refs = (*refs, selection.input_state_ref)
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise NodeInputPortError("node_input_selected_profile_missing")
        self.__refs = {artifact_ref_identity_key(ref): ref.model_copy(deep=True) for ref in refs}
        self.__node, self.__params, self.__identity = node, dict(params), identity

    def _current(self) -> None:
        from polisyos.scientist.orchestration.engine.component_identity import (
            _OWNERS,
            capture_engine_component_identity,
        )

        if (
            capture_engine_component_identity(
                self.__node, self.__identity.component_id, self.__params
            )
            != self.__identity
            or (owner := _OWNERS.get(self.__identity.component_id)) is None
            or owner.input_definition_sha256 != self.__definition_sha256
        ):
            raise NodeInputPortError("node_input_contract_source_changed")

    def _resolve(self, selector: Any, profile: str | None = None) -> ArtifactRef:
        from polisyos.core.artifacts.manifest import artifact_reference_parts

        self._current()
        if isinstance(selector, (ArtifactRef, InputRef)):
            artifact_id = selector.artifact_id
            profile = selector.manifest_profile_sha256 if profile is None else profile
        else:
            artifact_id, selected_profile, _ = artifact_reference_parts(selector)
            profile = selected_profile if profile is None else profile
        with self.__lock:
            matches = [
                ref
                for key, ref in self.__refs.items()
                if key[0] == str(artifact_id) and (profile is None or key[3] == profile)
            ]
            if isinstance(selector, ArtifactRef):
                matches = [
                    ref
                    for ref in matches
                    if ref.kind == selector.kind and ref.media_type == selector.media_type
                ]
            if len(matches) != 1:
                raise NodeInputPortError("node_input_artifact_read_not_selected")
            return matches[0].model_copy(deep=True)

    def _remember(self, ref: ArtifactRef) -> ArtifactRef:
        if type(ref) is not ArtifactRef or ref.manifest_profile_sha256 is None:
            raise NodeInputPortError("node_input_output_profile_not_established")
        self._current()
        with self.__lock:
            self.__refs[artifact_ref_identity_key(ref)] = ref.model_copy(deep=True)
        return ref

    def iter_artifact_ids(self) -> list[ArtifactID]:
        """Enumerate only this callback's selected or produced artifacts."""
        self._current()
        with self.__lock:
            return list(
                {
                    str(ref.artifact_id): ref.artifact_id.model_copy(deep=True)
                    for ref in self.__refs.values()
                }.values()
            )

    def has(self, artifact_id: Any) -> bool:
        return self.__store.has(self._resolve(artifact_id))

    def get_bytes(self, artifact_id: Any) -> bytes:
        return self.__store.get_bytes(self._resolve(artifact_id))

    def get_manifest(self, artifact_id: Any) -> ArtifactManifest:
        return self.__store.get_manifest(self._resolve(artifact_id))

    def get_manifest_by_profile(
        self, artifact_id: Any, manifest_profile_sha256: str
    ) -> ArtifactManifest:
        return self.__store.get_manifest(self._resolve(artifact_id, manifest_profile_sha256))

    def verify(self, artifact_id: Any) -> VerificationReport:
        return self.__store.verify(self._resolve(artifact_id))

    def get_raw_manifest_bytes(
        self, artifact_id: Any, *, manifest_profile_sha256: str | None = None
    ) -> bytes:
        selected = self._resolve(artifact_id, manifest_profile_sha256)
        if not _supports_raw_manifest(self.__store):
            raise NotImplementedError("node_input_raw_manifest_read_unsupported")
        return self.__store.get_raw_manifest_bytes(selected)

    def get_raw_manifest_bytes_bounded(
        self,
        artifact_id: Any,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        selected = self._resolve(artifact_id, manifest_profile_sha256)
        if not _supports_bounded_manifest(self.__store):
            raise NotImplementedError("node_input_bounded_manifest_read_unsupported")
        return self.__store.get_raw_manifest_bytes_bounded(
            selected, max_manifest_bytes=max_manifest_bytes
        )

    def get_raw_manifest_bytes_bounded_for_input(
        self, input_ref: InputRef, *, max_manifest_bytes: int
    ) -> bytes:
        return self.get_raw_manifest_bytes_bounded(
            self._resolve(input_ref), max_manifest_bytes=max_manifest_bytes
        )

    def read_raw_manifest_bytes_bounded(
        self,
        artifact_id: Any,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> ArtifactBoundedManifestRead:
        selected = self._resolve(artifact_id, manifest_profile_sha256)
        if not _supports_manifest_receipt(self.__store):
            raise NotImplementedError("node_input_manifest_receipt_read_unsupported")
        return self.__store.read_raw_manifest_bytes_bounded(
            selected, max_manifest_bytes=max_manifest_bytes
        )

    def read_raw_manifest_bytes_bounded_for_input(
        self, input_ref: InputRef, *, max_manifest_bytes: int
    ) -> ArtifactBoundedManifestRead:
        return self.read_raw_manifest_bytes_bounded(
            self._resolve(input_ref), max_manifest_bytes=max_manifest_bytes
        )

    def open_member(
        self,
        artifact_id: Any,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int | None = None,
        expected_manifest_sha256: str | None = None,
    ) -> AbstractContextManager[CoreJSONArtifactMemberStream]:
        selected = self._resolve(artifact_id)
        if not _supports_streaming(self.__store):
            raise NotImplementedError("node_input_member_read_unsupported")
        return self.__store.open_member(
            selected,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
        )

    def open_member_bounded(
        self,
        artifact_id: Any,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int,
        expected_manifest_sha256: str,
        max_member_bytes: int,
    ) -> CoreJSONArtifactBoundedMemberAttempt:
        selected = self._resolve(artifact_id)
        if not _supports_bounded_member(self.__store):
            raise NotImplementedError("node_input_bounded_member_read_unsupported")
        return self.__store.open_member_bounded(
            selected,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )

    def put_bytes(
        self, data: bytes, opts: ArtifactWriteOptions, *, return_selected_profile: bool = False
    ) -> ArtifactRef:
        self._current()
        return self._remember(self.__store.put_bytes(data, opts, return_selected_profile=True))

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        self._current()
        return self._remember(
            self.__store.put_json(obj, opts, canon_spec=canon_spec, return_selected_profile=True)
        )


class _NodeInputRunView:
    """Expose only scoped CAS, trace emission and output tenant coordinates."""

    __slots__ = ("__run", "store")
    _METHODS = frozenset({"emit", "artifact_tenant_context"})

    def __init__(self, run: Any, store: _NodeInputStore) -> None:
        self.__run, self.store = run, store

    def __getattr__(self, name: str) -> Any:
        if name in self._METHODS:
            return getattr(self.__run, name)
        raise AttributeError(name)


def _restricted_context(
    ctx: ExecutionContext, port: _NodeInputPort, selection: NodeInputSelection | None = None
) -> ExecutionContext:
    store = _NodeInputStore(
        ctx.store,
        port.projected,
        port.node,
        port.params,
        port.identity,
        port.contract,
        selection,
        definition_sha256=port.definition_sha256,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext as Context

    # A fresh base context is an allowlist. New caller/subclass capabilities do
    # not silently enter this profile when ExecutionContext grows another port.
    fields: dict[str, Any] = {
        "store": store,
        "run": _NodeInputRunView(ctx.run, store),
        "logger": ctx.logger,
        "depth": ctx.depth,
        "_node_input_selection": selection,
        "_engine_invocation": ctx._engine_invocation if selection is not None else None,
    }
    return Context(**fields)


def _read_scoped_node_input(ctx: ExecutionContext, state: ExperimentState) -> ExperimentState:
    selection = ctx._node_input_selection
    binding = ctx._engine_invocation
    if (
        type(selection) is not NodeInputSelection
        or binding is None
        or state.run_id != selection.run_id
        or (binding.run_id, binding.attempt_id, binding.basis_ref)
        != (selection.run_id, selection.attempt_id, selection.basis_ref)
    ):
        raise NodeInputPortError("node_input_scoped_attempt_mismatch")
    return ExperimentState.model_validate(
        load_core_json_artifact(ctx.store, selection.input_state_ref)
    )


def read_input_port_basis(ctx: ExecutionContext, state: ExperimentState) -> NodeInputSelection:
    """Bind the unchanged physical input before returning safe attempt coordinates."""
    selection = ctx._node_input_selection
    if type(selection) is not NodeInputSelection:
        raise NodeInputPortError("node_input_port_not_installed")
    persisted = _read_scoped_node_input(ctx, state)
    if _state_bytes(persisted) != _state_bytes(state):
        raise NodeInputPortError("node_input_port_state_changed")
    return replace(
        selection,
        basis_ref=selection.basis_ref.model_copy(deep=True),
        input_state_ref=selection.input_state_ref.model_copy(deep=True),
    )


@dataclass(frozen=True)
class _NodeInputPort:
    """Executor-local state; never place this predecessor-bearing object in context."""

    node: Any
    params: dict[str, Any]
    contract: NodeInputContract
    identity: RunInvocationImplementationIdentity
    definition_sha256: str
    predecessor: ExperimentState
    projected: ExperimentState
    writes: tuple[str, ...]

    def callback_context(self, ctx: ExecutionContext) -> ExecutionContext:
        return _restricted_context(ctx, self)

    def attempt_context(
        self,
        ctx: ExecutionContext,
        *,
        node_alias: str,
        attempt_id: str,
        basis_ref: ArtifactRef,
        input_state_ref: ArtifactRef,
    ) -> ExecutionContext:
        selection = NodeInputSelection(
            run_id=self.projected.run_id,
            component_id=self.contract.component_id,
            contract_id=self.contract.contract_id,
            node_alias=node_alias,
            attempt_id=attempt_id,
            basis_ref=basis_ref.model_copy(deep=True),
            input_state_ref=input_state_ref.model_copy(deep=True),
        )
        return _restricted_context(ctx, self, selection)

    def require_current(self) -> RunInvocationImplementationIdentity:
        from polisyos.scientist.orchestration.engine.component_identity import (
            _OWNERS,
            capture_engine_component_identity,
        )

        current = capture_engine_component_identity(
            self.node, self.contract.component_id, self.params
        )
        if (
            current is None
            or current != self.identity
            or (owner := _OWNERS.get(self.contract.component_id)) is None
            or owner.input_definition_sha256 != self.definition_sha256
        ):
            raise NodeInputPortError("node_input_contract_source_changed")
        return current

    def cache_binding(self) -> dict[str, Any]:
        self.require_current()
        return {
            "contract": self.contract.model_dump(mode="json"),
            "implementation_dependencies_sha256": self.definition_sha256,
            "node_spec_sha256": self.identity.node_spec_sha256,
            "implementation": self.identity.model_dump(mode="json"),
            "projected_state_sha256": "sha256:"
            + hashlib.sha256(_state_bytes(self.projected)).hexdigest(),
        }

    def basis(
        self,
        *,
        predecessor_ref: ArtifactRef,
        attempt_state: ExperimentState,
        node_alias: str,
        attempt_id: str,
        attempt_number: int,
        source_cache_entry_ref: ArtifactRef | None = None,
    ) -> NodeInputBasis:
        self.require_current()
        # Retry may carry only explicitly declared spend; it cannot widen the input.
        if _state_bytes(attempt_state) != _state_bytes(self.projected):
            raise NodeInputPortError("node_input_attempt_projection_changed")
        presence = {}
        for path in self.contract.state_paths:
            value = _value_at(self.predecessor, path)
            presence[path] = (
                "missing" if value is _MISSING else "null" if value is None else "value"
            )
        return NodeInputBasis(
            run_id=attempt_state.run_id,
            node_alias=node_alias,
            attempt_id=attempt_id,
            attempt_number=attempt_number,
            contract=self.contract,
            implementation_identity=self.identity,
            implementation_dependencies_sha256=self.definition_sha256,
            bind_params=self.params,
            predecessor_state_ref=predecessor_ref,
            projected_state_sha256="sha256:"
            + hashlib.sha256(_state_bytes(attempt_state)).hexdigest(),
            path_presence=presence,
            execution_kind="cache_replay" if source_cache_entry_ref is not None else "producer",
            source_cache_entry_ref=source_cache_entry_ref,
        )

    def validate_outcome(self, outcome: NodeOutcome) -> None:
        self.require_current()
        if outcome.status == "fail":
            return
        merged = merge_parallel_outcomes(
            self.projected,
            {"port": outcome},
            {"port": list(self.writes)},
            mutation_journals={"port": mutation_journal_for_state(outcome.state)},
        )
        if merged.conflicts or _state_bytes(merged.state) != _state_bytes(outcome.state):
            raise NodeInputPortError("node_input_outcome_outside_contract")

    def merge_outcome(self, outcome: NodeOutcome) -> NodeOutcome:
        self.validate_outcome(outcome)
        if outcome.status != "ok":
            return outcome.model_copy(update={"state": self.predecessor})
        merged = merge_parallel_outcomes(
            self.predecessor,
            {"port": outcome},
            {"port": list(self.writes)},
            mutation_journals={"port": mutation_journal_for_state(outcome.state)},
        )
        if merged.conflicts:
            raise NodeInputPortError("node_input_output_merge_conflict")
        return outcome.model_copy(update={"state": merged.state})


def preflight_node_input_port(
    registered_node: Any, component_id: str, params: dict[str, Any]
) -> None:
    """Admit held definitions and bind keys before any protected semantic callback."""
    from polisyos.scientist.orchestration.engine.component_identity import (
        _preflight_registered_input,
    )

    try:
        contract_json = _preflight_registered_input(registered_node, component_id, params)
        if contract_json is not None:
            contract = NodeInputContract.model_validate_json(contract_json)
            if contract.component_id != component_id:
                raise ValueError("node_input_contract_component_mismatch")
            return
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        raise NodeInputPortError("node_input_contract_source_not_established") from exc
    # Unprotected legacy discovery retains its historical spec read. Merely
    # offering an unknown input contract cannot admit a bind or producer call.
    spec = registered_node.spec
    if isinstance(spec, InputAwareNodeSpec) or hasattr(spec, "input_contract"):
        raise NodeInputPortError("node_input_contract_source_not_established")


def admit_node_input_port(
    node: Any, state: ExperimentState, params: dict[str, Any]
) -> _NodeInputPort | None:
    """Select a physical input only for an independently held builtin contract."""
    from polisyos.scientist.orchestration.engine.component_identity import (
        _OWNERS,
        _require_input_definition,
        capture_engine_component_identity,
    )

    try:
        definition_owner = _require_input_definition(node, params)
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        raise NodeInputPortError("node_input_contract_source_not_established") from exc
    spec = node.spec
    metadata = getattr(spec, "metadata", None)
    component_id = str(getattr(metadata, "component_id", ""))
    expected_owner = _OWNERS.get(component_id)
    if not isinstance(spec, InputAwareNodeSpec):
        protected_type = any(
            owner.node_type is type(node) and owner.input_contract_sha256 is not None
            for owner in _OWNERS.values()
        )
        if (
            protected_type
            or (expected_owner is not None and expected_owner.input_contract_sha256 is not None)
            or hasattr(spec, "input_contract")
        ):
            raise NodeInputPortError("node_input_contract_unsupported")
        return None
    try:
        contract = NodeInputContract.model_validate_json(spec.input_contract.model_dump_json())
    except (TypeError, ValueError) as exc:
        raise NodeInputPortError("node_input_contract_unsupported") from exc
    if set(params) - set(contract.bind_param_keys):
        raise NodeInputPortError("node_input_bind_params_outside_contract")
    identity = capture_engine_component_identity(node, str(spec.metadata.component_id), params)
    if (
        identity is None
        or definition_owner is None
        or definition_owner.input_definition_sha256 is None
    ):
        raise NodeInputPortError("node_input_contract_source_not_established")
    predecessor = _completed_producer_value(state)
    projected = _project(predecessor, contract)
    _selected_refs(projected, contract)
    return _NodeInputPort(
        node=node,
        params=dict(params),
        contract=contract,
        identity=identity,
        definition_sha256=definition_owner.input_definition_sha256,
        predecessor=predecessor,
        projected=projected,
        writes=tuple(spec.state_writes),
    )


def validate_node_input_basis(
    store: ArtifactStore, started: RunInvocationStarted, projected: ExperimentState
) -> None:
    """Reconcile a selected input basis; never return its hidden predecessor.

    Legacy inputs remain compatible. A protected input-aware component cannot
    downgrade to that legacy path by removing the basis edge.
    """
    from polisyos.scientist.orchestration.engine.component_identity import (
        _OWNERS,
        matches_engine_component_identity,
    )

    manifest = store.get_manifest(started.input_state_ref)
    edges = [edge for edge in manifest.inputs if edge.role == _INPUT_BASIS_ROLE]
    owner = _OWNERS.get(started.component_id)
    requires_port = owner is not None and owner.input_contract_sha256 is not None
    if not edges:
        if requires_port:
            raise NodeInputPortError("node_input_basis_missing")
        return
    if len(edges) != 1 or len(manifest.inputs) != 1 or not edges[0].manifest_profile_sha256:
        raise NodeInputPortError("node_input_basis_ambiguous")
    edge = edges[0]
    basis_ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        kind=_INPUT_BASIS_KIND,
        media_type="application/json",
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    basis_manifest = store.get_manifest(basis_ref)
    if basis_manifest.kind != _INPUT_BASIS_KIND or basis_manifest.artifact_schema != SchemaInfo(
        name=_INPUT_BASIS_SCHEMA, version="1.0"
    ):
        raise NodeInputPortError("node_input_basis_schema_invalid")
    basis = NodeInputBasis.model_validate(load_core_json_artifact(store, basis_ref))
    if not store.verify(started.input_state_ref).ok:
        raise NodeInputPortError("node_input_state_integrity_invalid")
    if (
        (
            basis.run_id,
            basis.node_alias,
            basis.attempt_id,
            basis.attempt_number,
            basis.contract.component_id,
        )
        != (
            started.run_id,
            started.node_alias,
            started.attempt_id,
            started.attempt_number,
            started.component_id,
        )
        or basis.implementation_identity != started.implementation_identity
        or owner is None
        or basis.implementation_dependencies_sha256 != owner.input_definition_sha256
        or owner.input_contract_sha256
        != hashlib.sha256(
            to_canonical_bytes(basis.contract.model_dump(mode="json"), _CANON)
        ).hexdigest()
        or not matches_engine_component_identity(
            basis.implementation_identity, started.component_id, basis.bind_params
        )
        or basis.projected_state_sha256
        != "sha256:" + hashlib.sha256(_state_bytes(projected)).hexdigest()
    ):
        raise NodeInputPortError("node_input_basis_attempt_mismatch")
    if basis_manifest.inputs != input_basis_options(basis).inputs:
        raise NodeInputPortError("node_input_predecessor_lineage_mismatch")
    predecessor_manifest = store.get_manifest(basis.predecessor_state_ref)
    if (
        predecessor_manifest.kind != "scientist.experiment_state"
        or predecessor_manifest.artifact_schema is None
        or predecessor_manifest.artifact_schema.name
        != "polisyos.scientist.orchestration.engine.ExperimentState"
    ):
        raise NodeInputPortError("node_input_predecessor_contract_invalid")
    predecessor = ExperimentState.model_validate(
        load_core_json_artifact(store, basis.predecessor_state_ref)
    )
    expected = _project(predecessor, basis.contract)
    presence = {}
    for path in basis.contract.state_paths:
        value = _value_at(predecessor, path)
        presence[path] = "missing" if value is _MISSING else "null" if value is None else "value"
    if (
        predecessor.run_id != basis.run_id
        or predecessor_manifest.artifact_schema.version != predecessor.schema_version
        or basis.path_presence != presence
        or _state_bytes(expected) != _state_bytes(projected)
    ):
        raise NodeInputPortError("node_input_basis_projection_mismatch")
