"""Persist source continuity for a trusted local candidate workflow.

This is deliberately distinct from protected-producer implementation authority.
The profile compares actual registered Python implementations, passive bound
configuration and direct source dependencies across processes. It assumes a
trusted interpreter and cooperative, unchanged installed dependencies; it does
not attest a deployment, arbitrary transitive plugin code or external effects.
Unsupported captures remain explicit and cannot authorize strict continuation.
This module checks definitions only; the checkpoint owner's functional
fingerprint checks topology, conditions and workflow policy separately.
"""

from __future__ import annotations

import dis
import hashlib
import inspect
import logging
import marshal
import math
import platform
import sys
import types
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.components import describe_callable_source
from polisyos.scientist.orchestration.engine.protocol import NodeSpec

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.scientist.orchestration.engine.protocol import Node
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_CANON = CanonSpec(forbid_floats=True, sort_keys=True, exclude_none=False)
_MAX_CAPTURE_ITEMS = 10000
_MAX_FUNCTIONS = 128


class ExecutionAdmissionError(ValueError):
    """Refuse a continuation whose original executable basis is unestablished."""


class ManagedSubWorkflowDefinition(BaseModel):
    """Original managed wrapper behavior; not its completed child registry.

    Core and host services remain trusted platform dependencies. A child binding
    must persist this observation before its first producer. Re-observing a
    wrapper later cannot establish an absent historical binding.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: Literal["managed_subworkflow_wrapper_v1"] = "managed_subworkflow_wrapper_v1"
    purpose: Literal["candidate_wrapper_mapping_continuity"] = (
        "candidate_wrapper_mapping_continuity"
    )
    definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CandidateNodeDefinition(BaseModel):
    """One actual registration observed before the original first dispatch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alias: str
    component_id: str
    status: Literal["recomputed", "not_established"]
    reason: str | None = None
    definition_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_status(self) -> CandidateNodeDefinition:
        if (self.status == "recomputed") != (self.definition_sha256 is not None):
            raise ValueError("execution_admission_definition_status_mismatch")
        if (self.status == "not_established") != (self.reason is not None):
            raise ValueError("execution_admission_reason_status_mismatch")
        return self


class WorkflowExecutionAdmission(BaseModel):
    """Candidate executable continuity, never a protected authority receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ARTIFACT_KIND: ClassVar[str] = "scientist.workflow_execution_admission"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "scientist.WorkflowExecutionAdmission"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    schema_version: Literal["1.0"] = "1.0"
    profile: Literal["trusted_local_candidate_source_v1"] = "trusted_local_candidate_source_v1"
    authority: Literal["candidate_execution_continuity"] = "candidate_execution_continuity"
    dependency_boundary: Literal["trusted_interpreter_and_installed_dependencies"] = (
        "trusted_interpreter_and_installed_dependencies"
    )
    run_id: str = Field(min_length=1)
    workflow_spec_ref: ArtifactRef
    python_profile: str
    nodes: tuple[CandidateNodeDefinition, ...]

    @model_validator(mode="after")
    def _validate_membership(self) -> WorkflowExecutionAdmission:
        if self.workflow_spec_ref.manifest_profile_sha256 is None:
            raise ValueError("execution_admission_workflow_profile_missing")
        if len({node.alias for node in self.nodes}) != len(self.nodes):
            raise ValueError("execution_admission_duplicate_alias")
        return self


def _digest(value: object) -> str:
    return hashlib.sha256(to_canonical_bytes(value, _CANON)).hexdigest()


def _portable_code(code: types.CodeType) -> types.CodeType:
    """Remove installation coordinates and interpreter-adaptive code state."""
    return code.replace(
        co_filename="<admitted_module>",
        co_code=code.co_code,
        co_consts=tuple(
            _portable_code(value) if isinstance(value, types.CodeType) else value
            for value in code.co_consts
        ),
    )


def _code_family(code: types.CodeType) -> list[types.CodeType]:
    return [
        code,
        *[
            nested
            for value in code.co_consts
            if isinstance(value, types.CodeType)
            for nested in _code_family(value)
        ],
    ]


class _DefinitionCapture:
    """Bound passive capture; never call a custom serializer or repr."""

    def __init__(self) -> None:
        self.remaining = _MAX_CAPTURE_ITEMS
        self.functions: dict[str, object] = {}
        self.active: set[int] = set()

    def passive(self, value: object, depth: int = 0) -> object:
        self.remaining -= 1
        if self.remaining < 0 or depth > 32:
            raise ExecutionAdmissionError("execution_admission_capture_limit")
        if value is None or type(value) in {str, int, bool}:
            return [type(value).__name__, value]
        if type(value) is Decimal:
            if not value.is_finite():
                raise ExecutionAdmissionError("execution_admission_nonfinite_config")
            return ["decimal", str(value)]
        if type(value) is float:
            if not math.isfinite(value):
                raise ExecutionAdmissionError("execution_admission_nonfinite_config")
            return ["float", value.hex()]
        if isinstance(value, Path):
            return ["path", str(value.absolute())]
        if isinstance(value, Enum):
            return [
                "enum",
                _type_name(type(value)),
                _module_profile(sys.modules[type(value).__module__]),
                self.passive(
                    {key: item for key, item in vars(value).items() if key != "__objclass__"},
                    depth + 1,
                ),
            ]
        marker = id(value)
        if marker in self.active:
            raise ExecutionAdmissionError("execution_admission_cyclic_config")
        self.active.add(marker)
        try:
            if type(value) in {tuple, list}:
                return [
                    type(value).__name__,
                    [self.passive(item, depth + 1) for item in value],
                ]
            if type(value) is dict and all(type(key) is str for key in value):
                return [
                    "dict",
                    [[key, self.passive(value[key], depth + 1)] for key in sorted(value)],
                ]
            if isinstance(value, BaseModel):
                return [
                    "model",
                    _type_name(type(value)),
                    _module_profile(sys.modules[type(value).__module__]),
                    self.passive(object.__getattribute__(value, "__dict__"), depth + 1),
                    self.passive(object.__getattribute__(value, "__pydantic_private__"), depth + 1),
                    self.passive(object.__getattribute__(value, "__pydantic_extra__"), depth + 1),
                    sorted(object.__getattribute__(value, "__pydantic_fields_set__")),
                ]
        finally:
            self.active.remove(marker)
        raise ExecutionAdmissionError("execution_admission_opaque_config")

    def function(self, function: types.FunctionType) -> str:
        if function.__module__.split(".")[0] in {"importlib", "pkg_resources", "runpy"}:
            raise ExecutionAdmissionError("execution_admission_dynamic_dependency")
        key = f"{function.__module__}:{function.__qualname__}"
        code_sha256 = hashlib.sha256(marshal.dumps(_portable_code(function.__code__))).hexdigest()
        key = f"{key}:{code_sha256}"
        if key in self.functions:
            return key
        if len(self.functions) >= _MAX_FUNCTIONS:
            raise ExecutionAdmissionError("execution_admission_function_limit")
        observation = describe_callable_source(function, expected_module=function.__module__)
        if observation.get("basis") != "recomputed":
            raise ExecutionAdmissionError("execution_admission_callable_source_not_established")
        if any(
            instruction.opname in {"IMPORT_NAME", "IMPORT_FROM"}
            for code in _code_family(function.__code__)
            for instruction in dis.get_instructions(code)
        ):
            raise ExecutionAdmissionError("execution_admission_runtime_import_not_established")
        # Mark first so recursive module-level helpers do not recurse forever.
        self.functions[key] = None
        closure = inspect.getclosurevars(function)
        if closure.nonlocals:
            # Python adds an implicit __class__ cell for ordinary super(). The
            # actual class MRO is captured independently below.
            if set(closure.nonlocals) != {"__class__"} or not isinstance(
                closure.nonlocals["__class__"], type
            ):
                raise ExecutionAdmissionError("execution_admission_dynamic_closure")
        if {"eval", "exec", "__import__", "globals", "locals"} & set(closure.builtins):
            raise ExecutionAdmissionError("execution_admission_dynamic_dependency")
        nested_globals = {
            instruction.argval
            for code in _code_family(function.__code__)
            for instruction in dis.get_instructions(code)
            if instruction.opname == "LOAD_GLOBAL"
        }
        if {"eval", "exec", "__import__", "globals", "locals"} & nested_globals:
            raise ExecutionAdmissionError("execution_admission_dynamic_dependency")
        actual_globals = {
            name: function.__globals__[name]
            for name in nested_globals
            if name in function.__globals__
        }
        globals_profile: list[object] = []
        for name, value in sorted(actual_globals.items()):
            if isinstance(value, types.FunctionType):
                binding: object = ["function", self.function(value)]
            elif isinstance(value, types.ModuleType):
                if value.__name__.split(".")[0] in {
                    "builtins",
                    "importlib",
                    "pkg_resources",
                    "runpy",
                }:
                    raise ExecutionAdmissionError("execution_admission_dynamic_dependency")
                binding = ["module", _module_profile(value)]
            elif isinstance(value, type):
                binding = [
                    "type",
                    _type_name(value),
                    _module_profile(sys.modules[value.__module__]),
                ]
            else:
                binding = self.passive(value)
            globals_profile.append([name, binding])
        self.functions[key] = {
            "source": observation,
            "defaults": self.passive(function.__defaults__),
            "kwdefaults": self.passive(function.__kwdefaults__),
            "globals": globals_profile,
        }
        return key


def _type_name(value: type[Any]) -> str:
    return f"{value.__module__}:{value.__qualname__}"


def _module_profile(module: types.ModuleType) -> dict[str, str]:
    """Name the direct dependency bytes; do not infer a transitive closure."""
    source = vars(module).get("__file__")
    if not isinstance(source, str):
        return {"module": module.__name__, "origin": "interpreter_builtin"}
    path = Path(source)
    if path.suffix in {".pyc", ".pyo"}:
        raise ExecutionAdmissionError("execution_admission_dependency_source_unavailable")
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ExecutionAdmissionError("execution_admission_dependency_source_unavailable") from exc
    return {"module": module.__name__, "source_sha256": digest}


def _actual_function(node: object, name: str) -> types.FunctionType | None:
    descriptor = inspect.getattr_static(type(node), name, None)
    if descriptor is None:
        return None
    if not isinstance(descriptor, types.FunctionType):
        raise ExecutionAdmissionError("execution_admission_dispatch_descriptor_unsupported")
    actual = getattr(node, name)
    if (
        not isinstance(actual, types.MethodType)
        or actual.__self__ is not node
        or actual.__func__ is not descriptor
    ):
        raise ExecutionAdmissionError("execution_admission_dispatch_substituted")
    return descriptor


def _capture_node(node: Node, invocation: NodeInvocation) -> str:
    capture = _DefinitionCapture()
    registered_config = capture.passive(vars(node))
    bound = node
    binder = _actual_function(node, "bind")
    if binder is not None and invocation.params:
        # Speculatively binding all future nodes would add observable work and
        # could repeat an effect. Supporting this case requires an execution
        # owner that retains and actually dispatches the single bind result.
        # Ordinary candidate execution keeps its existing binder behavior.
        raise ExecutionAdmissionError("execution_admission_parameter_binding_requires_held_owner")
    spec = bound.spec
    if not isinstance(spec, NodeSpec) or str(spec.metadata.component_id) != str(invocation.node_id):
        raise ExecutionAdmissionError("execution_admission_spec_mismatch")
    methods: list[object] = []
    for method in ("execute", "execute_async", "bind"):
        function = _actual_function(bound, method)
        if function is not None:
            methods.append([method, capture.function(function)])
    if not any(method[0] in {"execute", "execute_async"} for method in methods):
        raise ExecutionAdmissionError("execution_admission_dispatch_missing")
    spec_descriptor = inspect.getattr_static(type(bound), "spec", None)
    if isinstance(spec_descriptor, property):
        if spec_descriptor.fget is None:
            raise ExecutionAdmissionError("execution_admission_spec_accessor_missing")
        methods.append(["spec", capture.function(spec_descriptor.fget)])
    elif not isinstance(inspect.getattr_static(bound, "spec", None), NodeSpec):
        raise ExecutionAdmissionError("execution_admission_spec_descriptor_unsupported")
    # An inherited execute() can use super(); bind every user class in its MRO,
    # rather than treating only the leaf class name as the implementation.
    classes = [
        [_type_name(owner), _module_profile(sys.modules[owner.__module__])]
        for owner in type(bound).__mro__
        if owner is not object
    ]
    for owner in type(bound).__mro__:
        if owner is object:
            continue
        for name, member in sorted(vars(owner).items()):
            if isinstance(member, (staticmethod, classmethod)):
                member = member.__func__
            if isinstance(member, types.FunctionType):
                methods.append([f"{_type_name(owner)}.{name}", capture.function(member)])
            elif isinstance(member, property):
                for accessor in (member.fget, member.fset, member.fdel):
                    if accessor is not None:
                        methods.append([f"{_type_name(owner)}.{name}", capture.function(accessor)])
            elif not name.startswith("__"):
                # Capture real class configuration too, not only instance vars.
                methods.append([f"{_type_name(owner)}.{name}", capture.passive(member)])
    return _digest(
        {
            "classes": classes,
            "registered_config": registered_config,
            "bound_config": capture.passive(vars(bound)),
            "spec": capture.passive(spec),
            "params": capture.passive(invocation.params),
            "methods": methods,
            "functions": capture.functions,
        }
    )


def _node_definition(registry: NodeRegistry, invocation: NodeInvocation) -> CandidateNodeDefinition:
    try:
        digest = _capture_node(registry.get(invocation.node_id), invocation)
    except (
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        reason = (
            str(exc)
            if isinstance(exc, ExecutionAdmissionError)
            else "execution_admission_unsupported"
        )
        return CandidateNodeDefinition(
            alias=invocation.alias,
            component_id=str(invocation.node_id),
            status="not_established",
            reason=reason,
        )
    return CandidateNodeDefinition(
        alias=invocation.alias,
        component_id=str(invocation.node_id),
        status="recomputed",
        definition_sha256=digest,
    )


class _ManagedWrapperCapture:
    """Observe canonical wrapper functions without inspecting live services."""

    def __init__(self) -> None:
        self.passive = _DefinitionCapture()
        self.functions: dict[str, object] = {}
        self.sentinels: dict[int, set[str]] = {}

    def function(self, function: types.FunctionType) -> str:
        code_sha256 = hashlib.sha256(marshal.dumps(_portable_code(function.__code__))).hexdigest()
        key = f"{function.__module__}:{function.__qualname__}:{code_sha256}"
        if key in self.functions:
            return key
        if len(self.functions) >= _MAX_FUNCTIONS:
            raise ExecutionAdmissionError("managed_subworkflow_source_capture_limit")
        observation = describe_callable_source(function, expected_module=function.__module__)
        if observation.get("basis") != "recomputed":
            raise ExecutionAdmissionError("managed_subworkflow_source_not_established")
        self.functions[key] = None
        names = {
            instruction.argval
            for code in _code_family(function.__code__)
            for instruction in dis.get_instructions(code)
            if instruction.opname == "LOAD_GLOBAL"
        }
        globals_profile: list[object] = []
        for name in sorted(names):
            if name in function.__globals__:
                logical_binding = f"{function.__module__}:{name}"
                globals_profile.append(
                    [name, self.value(function.__globals__[name], logical_binding)]
                )
        closure_profile = [
            [name, self.value(value, f"{key}:closure:{name}")]
            for name, value in sorted(inspect.getclosurevars(function).nonlocals.items())
        ]
        self.functions[key] = {
            "source": observation,
            "defaults": self.passive.passive(function.__defaults__),
            "kwdefaults": self.passive.passive(function.__kwdefaults__),
            "globals": globals_profile,
            "closure": closure_profile,
        }
        return key

    def value(self, value: object, logical_binding: str) -> object:
        if isinstance(value, types.FunctionType):
            wrapper_modules = {
                "polisyos.scientist.orchestration.engine.sub_workflow",
                "polisyos.scientist.orchestration.engine.child_workflow",
            }
            if value.__module__ in wrapper_modules or (
                value.__module__.startswith("polisyos.scientist.orchestration.engine.")
                and value.__name__ in {"_get_path", "_model_field_value"}
            ):
                return ["engine_function", self.function(value)]
            # Canonical verification and platform services are dependencies,
            # not another recursively self-verifying implementation owner.
            observation = describe_callable_source(value, expected_module=value.__module__)
            if observation.get("basis") != "recomputed":
                raise ExecutionAdmissionError("managed_subworkflow_source_not_established")
            return [
                "platform_function",
                observation,
                hashlib.sha256(marshal.dumps(_portable_code(value.__code__))).hexdigest(),
            ]
        if isinstance(value, types.ModuleType):
            return ["platform_module", _module_profile(value)]
        if isinstance(value, type):
            return [
                "platform_type",
                _type_name(value),
                _module_profile(sys.modules[value.__module__]),
            ]
        if isinstance(value, logging.Logger):
            # Logging is an observation channel, not an input/mapping owner.
            # Host logger handlers and mutable service state are not attested.
            return ["platform_logger", value.name]
        logger_module = sys.modules.get("polisyos.common.logger")
        if isinstance(logger_module, types.ModuleType) and type(value) is vars(logger_module).get(
            "_CompatLogger"
        ):
            # get_logger() deliberately returns the host's compatibility
            # handle, whose wrapped Loguru/stdlib service is not node config.
            return ["platform_logger", _module_profile(logger_module)]
        if type(value) is object:
            # Preserve alias relationships of missing-value sentinels without
            # writing process-local id() tokens into the portable digest.
            self.sentinels.setdefault(id(value), set()).add(logical_binding)
            return ["engine_sentinel", logical_binding]
        if is_dataclass(value) and not isinstance(value, type):
            return [
                "platform_data",
                _type_name(type(value)),
                self.passive.passive(
                    {field.name: getattr(value, field.name) for field in fields(value)}
                ),
                _module_profile(sys.modules[type(value).__module__]),
            ]
        if type(value) in {set, frozenset}:
            items = [self.passive.passive(item) for item in value]
            return [
                type(value).__name__,
                sorted(items, key=lambda item: to_canonical_bytes(item, _CANON)),
            ]
        return self.passive.passive(value)

    def owner(self, owner: type[Any]) -> list[object]:
        functions: list[object] = []
        for name, member in sorted(vars(owner).items()):
            if isinstance(member, (staticmethod, classmethod)):
                member = member.__func__
            if isinstance(member, types.FunctionType):
                functions.append([name, self.function(member)])
            elif isinstance(member, property):
                for role, accessor in (
                    ("get", member.fget),
                    ("set", member.fset),
                    ("delete", member.fdel),
                ):
                    if accessor is not None:
                        functions.append([name, role, self.function(accessor)])
            elif not name.startswith("__"):
                functions.append([name, self.value(member, f"{_type_name(owner)}:{name}")])
        return [_type_name(owner), functions]


def capture_managed_subworkflow_definition(node: object) -> ManagedSubWorkflowDefinition:
    """Observe the actual canonical managed wrapper before any child producer.

    Args:
        node: The exact registered ``SubWorkflowNode`` whose configuration and
            wrapper-side dispatch/mapping are selected by the parent engine.

    Returns:
        A portable, candidate-scoped observation to bind into the original
        child binding and compare before terminal-recovery mapping executes.

    Raises:
        ExecutionAdmissionError: The wrapper/source/config cannot be reconciled.

    The child registry is intentionally neither read nor enumerated. New child
    execution still uses its actual registry and normal execution admission;
    terminal-only recovery verifies its persisted history instead. Missing old
    observations cannot be upgraded by this function.
    """
    from polisyos.scientist.orchestration.engine import child_workflow, sub_workflow

    if type(node) is not sub_workflow.SubWorkflowNode:
        raise ExecutionAdmissionError("managed_subworkflow_owner_not_established")
    attributes = object.__getattribute__(node, "__dict__")
    if set(attributes) != {"_config", "_registry", "_alias"}:
        raise ExecutionAdmissionError("managed_subworkflow_configuration_not_established")
    if type(attributes["_config"]) is not sub_workflow.SubWorkflowConfig:
        raise ExecutionAdmissionError("managed_subworkflow_configuration_not_established")
    capture = _ManagedWrapperCapture()
    for name in ("execute", "_execute_admitted", "_prepare_child_input", "_execute_with_child"):
        descriptor = inspect.getattr_static(type(node), name, None)
        if not isinstance(descriptor, types.FunctionType):
            raise ExecutionAdmissionError("managed_subworkflow_dispatch_not_established")
        actual = object.__getattribute__(node, name)
        if (
            not isinstance(actual, types.MethodType)
            or actual.__self__ is not node
            or actual.__func__ is not descriptor
        ):
            raise ExecutionAdmissionError("managed_subworkflow_dispatch_not_established")
    owners = [
        capture.owner(sub_workflow.SubWorkflowNode),
        capture.owner(child_workflow._ManagedSubWorkflowDispatch),
    ]
    for name, value in sorted(vars(sub_workflow).items()):
        if isinstance(value, types.FunctionType) and value.__module__ == sub_workflow.__name__:
            # Bind module-level mapping call targets by their actual lookup
            # name, even when replaced by another real source-backed function.
            owners.append([f"{sub_workflow.__name__}:{name}", capture.function(value)])
    payload = {
        "python": _python_profile(),
        "config": capture.passive.passive(attributes["_config"]),
        "alias": capture.passive.passive(attributes["_alias"]),
        # The spec accessor's actual code and all of its configuration are
        # already observed. Do not invoke an offered getter before comparing
        # against the original definition during terminal recovery.
        "owners": owners,
        "functions": capture.functions,
        "sentinel_aliases": sorted(sorted(names) for names in capture.sentinels.values()),
        "boundary": "trusted_platform_services_no_child_registry",
    }
    return ManagedSubWorkflowDefinition(definition_sha256=_digest(payload))


def _python_profile() -> str:
    return f"{platform.python_implementation()}:{platform.python_version()}:{sys.implementation.cache_tag}"


def _selected_workflow(store: ArtifactStore, ref: ArtifactRef) -> WorkflowSpec:
    """Read the original workflow from its exact selected CAS owner bytes."""
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

    if (
        ref.manifest_profile_sha256 is None
        or ref.kind != "scientist.workflow_spec"
        or ref.media_type != "application/json"
        or not store.verify(ref).ok
    ):
        raise ExecutionAdmissionError("execution_admission_workflow_ref_invalid")
    manifest = store.get_manifest(ref)
    if manifest.artifact_schema != SchemaInfo(
        name="polisyos.scientist.orchestration.engine.WorkflowSpec", version="1.0"
    ):
        raise ExecutionAdmissionError("execution_admission_workflow_schema_mismatch")
    return validate_core_model_json_artifact(WorkflowSpec, store, ref)


def _require_selected_workflow(
    store: ArtifactStore, ref: ArtifactRef, workflow: WorkflowSpec
) -> WorkflowSpec:
    selected = _selected_workflow(store, ref)
    capture = _DefinitionCapture()
    # WorkflowSpec's persisted public values are its declared execution input;
    # field-set provenance belongs to nested node configuration, not to the
    # caller constructor's choice to omit equivalent workflow defaults.
    if capture.passive(selected.model_dump(mode="python")) != capture.passive(
        workflow.model_dump(mode="python")
    ):
        raise ExecutionAdmissionError("execution_admission_workflow_bytes_mismatch")
    return selected


def persist_workflow_execution_admission(
    store: ArtifactStore,
    workflow: WorkflowSpec,
    registry: NodeRegistry,
    *,
    workflow_ref: ArtifactRef,
    run_id: str,
) -> ArtifactRef:
    """Persist every original alias before dispatch; unsupported nodes stay explicit.

    The execution owner must bind the returned exact selected ref into its first
    protected start record. Merely placing it in caller-controlled state does not
    establish that it was the original admission.
    """
    selected_workflow = _require_selected_workflow(store, workflow_ref, workflow)
    admission = WorkflowExecutionAdmission(
        run_id=run_id,
        workflow_spec_ref=workflow_ref,
        python_profile=_python_profile(),
        nodes=tuple(
            _node_definition(registry, invocation) for invocation in selected_workflow.nodes
        ),
    )
    return store.put_json(
        admission.model_dump(mode="python"),
        ArtifactWriteOptions(
            kind=admission.ARTIFACT_KIND,
            media_type=admission.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=admission.ARTIFACT_SCHEMA_NAME, version=admission.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=[input_ref_from_artifact_ref(workflow_ref, role="original_workflow")],
        ),
        return_selected_profile=True,
    )


def verify_workflow_execution_admission(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    original_workflow_ref: ArtifactRef,
    original_workflow: WorkflowSpec,
    residual_workflow: WorkflowSpec,
    registry: NodeRegistry,
    run_id: str,
) -> None:
    """Compare actual residual registrations with the protected original basis.

    The caller must obtain ``ref`` from the validated original Core start chain,
    never from a new node declaration. Completed aliases are not looked up.
    """
    if ref.manifest_profile_sha256 is None or not store.verify(ref).ok:
        raise ExecutionAdmissionError("execution_admission_selected_ref_invalid")
    admission = validate_core_model_json_artifact(WorkflowExecutionAdmission, store, ref)
    if (
        admission.run_id != run_id
        or admission.workflow_spec_ref != original_workflow_ref
        or admission.python_profile != _python_profile()
    ):
        raise ExecutionAdmissionError("execution_admission_original_basis_mismatch")
    selected_workflow = _require_selected_workflow(store, original_workflow_ref, original_workflow)
    original = {node.alias: str(node.node_id) for node in selected_workflow.nodes}
    declared = {node.alias: node.component_id for node in admission.nodes}
    if original != declared:
        raise ExecutionAdmissionError("execution_admission_original_population_mismatch")
    definitions = {node.alias: node for node in admission.nodes}
    for invocation in residual_workflow.nodes:
        expected = definitions.get(invocation.alias)
        if expected is None or expected.component_id != str(invocation.node_id):
            raise ExecutionAdmissionError("execution_admission_residual_population_mismatch")
        if expected.status != "recomputed":
            raise ExecutionAdmissionError("execution_admission_original_definition_not_established")
        observed = _node_definition(registry, invocation)
        if observed != expected:
            raise ExecutionAdmissionError("execution_admission_residual_definition_changed")
