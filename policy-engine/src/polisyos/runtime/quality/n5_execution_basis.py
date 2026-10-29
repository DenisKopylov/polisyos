"""Observe the implementation actually called by a controlled N5 execution.

This is a process-local execution witness, not a package-name attestation or a
cross-process cache permit. The real controller records executed Python code and
live bindings, native origins and numerical policy. Only an observation held by
that producer can authorize current reuse; old/unobserved executions stay
``not_established``. Historical receipts retain their original meaning.
"""

from __future__ import annotations

import dis
import hashlib
import importlib.machinery
import inspect
import json
import sys
import threading
import types
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import artifact_ref_identity_key

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationRequest,
        JointSimulationResult,
    )


def _exact_native_content(value: object) -> object:
    """Project the complete native typed quantity without name-based exclusions."""
    if value is None or type(value) in {bool, int, str}:
        return {type(value).__name__: value}
    if type(value) is float:
        return {"float": value.hex()}
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if isinstance(value, Enum):
        return {
            "enum": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": _exact_native_content(value.value),
        }
    if isinstance(value, (date, datetime)):
        return {type(value).__name__: value.isoformat()}
    if isinstance(value, BaseModel):
        if set(vars(value)) != set(type(value).model_fields) or value.__pydantic_extra__:
            raise ValueError("n5_native_model_field_denominator_not_established")
        return {
            "model": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {
                name: _exact_native_content(getattr(value, name))
                for name in type(value).model_fields
            },
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "dataclass": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {
                field.name: _exact_native_content(getattr(value, field.name))
                for field in fields(value)
            },
        }
    if isinstance(value, dict):
        rows = [
            (_exact_native_content(key), _exact_native_content(item)) for key, item in value.items()
        ]
        return {"mapping": sorted(rows, key=lambda row: json.dumps(row[0], sort_keys=True))}
    if isinstance(value, (tuple, list, set, frozenset)):
        items = [_exact_native_content(item) for item in value]
        if isinstance(value, (set, frozenset)):
            items.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return {type(value).__name__: items}
    raise ValueError("n5_native_content_type_not_established:" + type(value).__qualname__)


def exact_n5_content_bytes(value: object) -> bytes:
    """Return every native typed field/value without metadata-name exclusions."""
    return json.dumps(
        _exact_native_content(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def exact_n5_content_hash(value: object) -> str:
    """Index complete native content; deciding joins compare its actual bytes."""
    return "sha256:" + hashlib.sha256(exact_n5_content_bytes(value)).hexdigest()


def _json_wire(value: object) -> dict[str, Any]:
    """Freeze an already JSON-ready observation in its actual persisted form."""
    loaded = json.loads(json.dumps(value, sort_keys=True, allow_nan=False))
    if not isinstance(loaded, dict):
        raise ValueError("n5_implementation_wire_not_mapping")
    return loaded


_SESSION = uuid4().hex
_LOCK = threading.RLock()
_OBJECTS: dict[int, tuple[object, str]] = {}
_ISSUED: dict[str, _IssuedExecution] = {}
_DIAGNOSTIC_KEY = "n5_execution_implementation_witness"
_ACTIVE_INPUT: ContextVar[_VerifiedExecutionInput | None] = ContextVar(
    "policyos_candidate_n5_implementation_input", default=None
)


@dataclass(frozen=True)
class _VerifiedExecutionInput:
    port: object
    controller: object
    candidate: object
    problem: object
    request: object
    input_ref: ArtifactRef
    input_content_hash: str
    observer: _ControllerExecutionObserver


@contextmanager
def observe_candidate_n5_execution_input(
    *,
    port: object,
    candidate: object,
    problem: object,
    request: JointSimulationRequest,
    input_ref: ArtifactRef,
) -> Iterator[None]:
    """Bind the exact owner-replayed V5 input before the real controller runs.

    The request is reconstructed by the same actual port builder from a fresh
    selected source read. A completed capture cannot later be relabeled with a
    different input or request.
    """
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    if type(port) is not JointSimulationPort:
        raise ValueError("n5_implementation_port_not_canonical")
    handoff = port._candidate_simulation_handoff
    if handoff is None or port._artifact_store is None:
        raise ValueError("n5_implementation_input_owner_not_established")
    record = GenerationSourceRepository(port._artifact_store).resolve_candidate_simulation_v5(
        ref=input_ref,
        expected_job_id=handoff.job_id,
        expected_run_id=handoff.run_id,
        expected_tenant_id=handoff.tenant_id,
        expected_cell_id=handoff.cell_id,
    )
    expected = port._build_candidate_simulation_request(
        candidate=candidate,
        problem=problem,
        input_record=record,
    )
    if exact_n5_content_bytes(expected) != exact_n5_content_bytes(request):
        raise ValueError("n5_implementation_input_request_mismatch")
    observer = _ControllerExecutionObserver((port, port._controller))
    token = _ACTIVE_INPUT.set(
        _VerifiedExecutionInput(
            port,
            port._controller,
            candidate,
            problem,
            request,
            input_ref,
            record.content_hash,
            observer,
        )
    )
    try:
        # Observe the actual full synchronous controller call: selection,
        # cache/replication, numerical code, and final aggregation/result
        # construction. Capturing only run_once would miss outer consumers.
        with observer:
            yield
    finally:
        _ACTIVE_INPUT.reset(token)


class N5ExecutionImplementationWitness(BaseModel):
    """Content-bound, producer-observed implementation of one actual N5 call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["N5ExecutionImplementationWitness@1.0"] = (
        "N5ExecutionImplementationWitness@1.0"
    )
    authority_purpose: Literal["candidate_evaluation_retention_only"] = (
        "candidate_evaluation_retention_only"
    )
    comparison_scope: Literal["same_live_process_loaded_implementation"] = (
        "same_live_process_loaded_implementation"
    )
    process_session: str
    input_ref_identity: tuple[str, str, str, str | None]
    request_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    result_without_witness_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    trajectory_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    implementation: dict[str, Any]
    consumed_configuration_values: dict[str, Any] | None = None
    predicate_provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_content(self) -> N5ExecutionImplementationWitness:
        if self.content_hash != exact_n5_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("n5_implementation_witness_content_mismatch")
        if (self.predicate_provenance == "recomputed") == bool(self.reason_codes):
            raise ValueError("n5_implementation_witness_predicate_mismatch")
        if self.predicate_provenance == "recomputed" and self.consumed_configuration_values is None:
            raise ValueError("n5_consumed_configuration_not_established")
        return self


@dataclass(frozen=True)
class _ExecutedCode:
    module: str
    code: types.CodeType
    globals: dict[str, Any]
    frame: types.FrameType
    receiver_roots: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class _IssuedExecution:
    witness: N5ExecutionImplementationWitness
    capture: N5ImplementationCapture


def _token(value: object) -> str:
    """Keep the observed object alive so identity tokens cannot be recycled."""
    with _LOCK:
        prior = _OBJECTS.get(id(value))
        if prior is None:
            prior = (value, uuid4().hex)
            _OBJECTS[id(value)] = prior
        if prior[0] is not value:
            raise RuntimeError("n5_implementation_identity_recycled")
        return prior[1]


def _code_hash(code: types.CodeType) -> str:
    # Reuse C95's complete normalization, including nested code/default constants.
    from polisyos.runtime.quality.confidence_ledger import _normalize_code_object

    return exact_n5_content_hash(_normalize_code_object(code))


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _native_origins() -> tuple[dict[str, str], ...]:
    """Read actual loaded NumPy/SciPy image origins, not distribution labels."""
    rows: list[dict[str, str]] = []
    for name, module in sorted(sys.modules.copy().items()):
        if name.split(".", 1)[0] not in {"numpy", "scipy"}:
            continue
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None)
        if not isinstance(origin, str):
            continue
        if not any(origin.endswith(suffix) for suffix in importlib.machinery.EXTENSION_SUFFIXES):
            continue
        loader = getattr(spec, "loader", None)
        if not isinstance(loader, importlib.machinery.ExtensionFileLoader):
            raise ValueError("n5_native_loader_not_established")
        path = Path(origin).resolve(strict=True)
        if Path(str(getattr(module, "__file__", ""))).resolve(strict=True) != path:
            raise ValueError("n5_native_origin_binding_mismatch")
        rows.append(
            {"module": name, "loaded_module_token": _token(module), "sha256": _file_hash(path)}
        )
    if not rows:
        raise ValueError("n5_native_origin_not_established")
    return tuple(rows)


def _numeric_policy(method: type) -> dict[str, Any]:
    """Observe the real method/backend policy without replacing unknowns."""
    import numpy as np

    from polisyos.foundry.methods.backends.runtime_fingerprint import (
        capture_backend_runtime_fingerprint,
    )
    from polisyos.foundry.methods.base import ComputeBackend

    fingerprint = capture_backend_runtime_fingerprint(ComputeBackend.NUMPY, method_class=method)
    if not fingerprint.available:
        raise ValueError("n5_backend_unavailable")
    return {
        "backend": fingerprint.as_dict(),
        "numpy_error_policy": np.geterr(),
        "python_executable_sha256": _file_hash(Path(sys.executable).resolve(strict=True)),
        "python_cache_tag": sys.implementation.cache_tag,
        "python_optimize": sys.flags.optimize,
    }


def _binding_value(value: object) -> object:
    """Bind actual callable defaults/closure and current class method slots."""
    from polisyos.runtime.quality.confidence_ledger import _normalize_function_binding

    if isinstance(value, types.FunctionType):
        return {"live_object_token": _token(value), "function": _normalize_function_binding(value)}
    if isinstance(value, type):
        # A class can keep its identity while an inherited constructor or
        # numerical method changes. Observe every actual MRO callable slot,
        # not only the class token/FQN. No method-name whitelist decides this.
        owners = []
        for owner in value.__mro__:
            callables = {}
            for name, raw in vars(owner).items():
                if isinstance(raw, types.FunctionType):
                    functions = (raw,)
                elif isinstance(raw, (classmethod, staticmethod)):
                    functions = (raw.__func__,)
                elif isinstance(raw, property):
                    functions = tuple(
                        item for item in (raw.fget, raw.fset, raw.fdel) if item is not None
                    )
                else:
                    continue
                callables[name] = {
                    "descriptor_type": f"{type(raw).__module__}.{type(raw).__qualname__}",
                    "functions": tuple(_normalize_function_binding(item) for item in functions),
                }
            owners.append({"owner_token": _token(owner), "callable_slots": callables})
        return {"live_object_token": _token(value), "class_mro": owners}
    if isinstance(value, types.MethodType):
        return {
            "bound_owner_token": _token(value.__self__),
            "function": _binding_value(value.__func__),
        }
    if isinstance(value, types.ModuleType) or callable(value):
        return {
            "live_object_token": _token(value),
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
        }
    try:
        return {"native_value": _exact_native_content(value)}
    except ValueError as exc:
        # A pure Python object has no hidden extension storage only when its
        # complete MRO is source-backed and exposes no slot storage. Preserve
        # its actual identity AND complete instance dictionary. This supports
        # source-owned identity sentinels without reducing an opaque native
        # value to C95's descriptive singleton_type fallback.
        owners = type(value).__mro__[:-1]
        for owner in owners:
            module = sys.modules.get(owner.__module__)
            spec = getattr(module, "__spec__", None)
            if not isinstance(
                getattr(spec, "loader", None), importlib.machinery.SourceFileLoader
            ) or "__slots__" in vars(owner):
                raise ValueError("n5_consumed_binding_value_not_established") from exc
        state = getattr(value, "__dict__", None)
        if not owners or type(state) is not dict:
            raise ValueError("n5_consumed_binding_value_not_established") from exc
        return {
            "python_object_token": _token(value),
            "python_type": _binding_value(type(value)),
            "instance_values": _exact_native_content(state),
        }


class _ControllerExecutionObserver:
    """Observe real controller frames without replacing a product callable."""

    def __init__(self, receiver_roots: tuple[object, ...] = ()) -> None:
        self.receiver_roots = receiver_roots
        self.codes: dict[tuple[str, str, str], _ExecutedCode] = {}
        self.native_calls: dict[str, object] = {}
        self.suspended = False
        self.active = False
        self.completed = False
        self.reason: str | None = None

    def __enter__(self) -> _ControllerExecutionObserver:
        if sys.getprofile() is not None:
            self.reason = "n5_execution_observer_conflict"
        else:
            self.active = True
            sys.setprofile(self._observe)
        return self

    def _observe(self, frame: types.FrameType, event: str, arg: object) -> None:
        if self.suspended:
            return
        if event == "call":
            module = str(frame.f_globals.get("__name__", ""))
            if module and module != __name__:
                key = (module, frame.f_code.co_qualname, str(id(frame.f_code)))
                self.codes.setdefault(
                    key,
                    _ExecutedCode(
                        module,
                        frame.f_code,
                        frame.f_globals,
                        frame,
                        tuple(
                            (name, value)
                            for name, value in frame.f_locals.items()
                            if any(value is root for root in self.receiver_roots)
                        ),
                    ),
                )
        elif event == "c_call":
            module = str(getattr(arg, "__module__", ""))
            if module.startswith(("numpy", "scipy")):
                self.native_calls[_token(arg)] = arg

    def __exit__(self, *exc: object) -> None:
        del exc
        if self.active and sys.getprofile() == self._observe and not self.suspended:
            sys.setprofile(None)
            self.completed = True
        elif self.reason is None:
            self.reason = "n5_execution_observer_interrupted"
        self.active = False


def _default_receiver_protocol(owner: object) -> None:
    """Refuse unsupported dynamic dispatch before calling a current receiver."""
    cls = type(owner)
    for name in ("__getattribute__", "__setattr__", "__delattr__"):
        if inspect.getattr_static(cls, name) is not inspect.getattr_static(object, name):
            raise ValueError("n5_receiver_protocol_not_established")
    if any("__getattr__" in vars(base) for base in cls.__mro__):
        raise ValueError("n5_receiver_protocol_not_established")
    # A source-declared callable is a dispatch slot, never constructor data.
    # Check this quantity generically BEFORE invoking any current selector;
    # no per-method shadow list is maintained.
    for name in vars(owner):
        raw = inspect.getattr_static(cls, name, None)
        if isinstance(raw, (types.FunctionType, classmethod, staticmethod, property)):
            raise ValueError("n5_consumed_receiver_dispatch_not_established")


def _construction_binding(cls: type) -> dict[str, object]:
    """Bind actual construction links, separately from executed-frame evidence."""
    if type(cls) is not type:
        raise ValueError("n5_receiver_construction_not_established")
    if inspect.getattr_static(cls, "__new__") is not inspect.getattr_static(object, "__new__"):
        raise ValueError("n5_receiver_construction_not_established")
    for name in ("__getattribute__", "__setattr__", "__delattr__"):
        if inspect.getattr_static(cls, name) is not inspect.getattr_static(object, name):
            raise ValueError("n5_receiver_construction_not_established")
    if any("__getattr__" in vars(base) for base in cls.__mro__):
        raise ValueError("n5_receiver_construction_not_established")
    slots = {}
    values = {}
    for base in cls.__mro__[:-1]:
        for name, raw in vars(base).items():
            if isinstance(raw, (types.FunctionType, classmethod, staticmethod, property)):
                functions = (
                    (raw,)
                    if isinstance(raw, types.FunctionType)
                    else (
                        tuple(item for item in (raw.fget, raw.fset, raw.fdel) if item is not None)
                        if isinstance(raw, property)
                        else (raw.__func__,)
                    )
                )
                slots[name] = {
                    "descriptor": f"{type(raw).__module__}.{type(raw).__qualname__}",
                    "functions": tuple(_binding_value(item) for item in functions),
                }
            elif callable(raw):
                # Non-source executable class slots are unsupported for this
                # ordinary Python owner; adding a native dispatch cannot hide
                # behind an unchanged class name or constructor function.
                raise ValueError("n5_receiver_construction_not_established")
            elif isinstance(raw, (types.GetSetDescriptorType, types.MemberDescriptorType)):
                if raw.__objclass__ is not base:
                    raise ValueError("n5_receiver_construction_not_established")
                values[name] = {"owned_descriptor": _token(raw), "owner": _token(base)}
            else:
                # A constructor can read a class default without changing its
                # code. Bind every supported owned namespace value; opaque
                # storage is unavailable rather than silently omitted.
                values[name] = _binding_value(raw)
    constructor = vars(cls).get("__init__")
    if not isinstance(constructor, types.FunctionType):
        raise ValueError("n5_receiver_construction_not_established")
    lookup_bindings = {}
    for index, instruction in enumerate(dis.get_instructions(constructor.__code__)):
        del index
        if instruction.opname not in {"LOAD_GLOBAL", "LOAD_NAME"}:
            continue
        name = str(instruction.argval)
        if name in constructor.__globals__:
            value = constructor.__globals__[name]
        elif name in constructor.__builtins__:
            value = constructor.__builtins__[name]
        else:
            raise ValueError("n5_receiver_construction_not_established")
        if isinstance(value, type):
            # A constructor lookup consumes class construction, not every
            # unrelated producer __call__ method of that dependency.
            init = inspect.getattr_static(value, "__init__")
            lookup_bindings[name] = {
                "class_object": _token(value),
                "constructor": _binding_value(init)
                if isinstance(init, types.FunctionType)
                else _token(init),
                "new": _token(inspect.getattr_static(value, "__new__")),
            }
        else:
            lookup_bindings[name] = _binding_value(value)
    return {
        "class_object": _token(cls),
        "metaclass_object": _token(type(cls)),
        "slots": slots,
        "owned_namespace_values": values,
        "constructor_lookup_bindings": lookup_bindings,
    }


class N5ImplementationCapture:
    """Record the concrete NCM call through the real synchronous controller path."""

    def __init__(
        self,
        *,
        method: type,
        request: JointSimulationRequest,
        controller: object,
        method_fqn: str,
    ) -> None:
        from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod

        self.method = method
        self._controller = controller
        self._request = request
        self._method_fqn = method_fqn
        admission = _ACTIVE_INPUT.get()
        self._admission = (
            admission
            if (
                admission is not None
                and admission.controller is controller
                and admission.request is request
            )
            else None
        )
        self._sealed: N5ExecutionImplementationWitness | None = None
        self._request_bytes = exact_n5_content_bytes(request)
        self.request_hash = "sha256:" + hashlib.sha256(self._request_bytes).hexdigest()
        self._result_bytes: bytes | None = None
        self._trajectory_bytes: bytes | None = None
        self._entry = getattr(method, "pure_step", None)
        self._supported = method is NCMEngineMethod and isinstance(self._entry, types.FunctionType)
        self._observer = self._admission.observer if self._admission is not None else None
        self._codes = self._observer.codes if self._observer is not None else {}
        self._native_calls = self._observer.native_calls if self._observer is not None else {}
        self._entry_observed = False
        self._prior_profiler: Any = None
        self._trajectory_hash: str | None = None
        self._reasons: list[str] = []
        self._initial: dict[str, Any] | None = None
        prior_suspension = self._observer.suspended if self._observer is not None else False
        if self._observer is not None:
            self._observer.suspended = True
        try:
            from polisyos.runtime.quality.joint_simulation_horizon import (
                read_joint_simulation_configuration,
            )

            self._configuration_start = _exact_native_content(
                read_joint_simulation_configuration(controller)
            )
        except (AttributeError, TypeError, ValueError):
            self._configuration_start = None

        finally:
            if self._observer is not None:
                self._observer.suspended = prior_suspension

    def __enter__(self) -> N5ImplementationCapture:
        if not self._supported or self._admission is None or self._observer is None:
            self._reasons.append("n5_selected_implementation_or_input_unsupported")
            return self
        if not self._observer.active or sys.getprofile() != self._observer._observe:
            self._reasons.append(self._observer.reason or "n5_execution_observer_not_active")
            return self
        try:
            self._observer.suspended = True
            self._initial = self._current_implementation()
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            self._reasons.append(str(getattr(exc, "code", None) or exc))
        finally:
            self._observer.suspended = False
        return self

    @contextmanager
    def observe_numerical_call(self) -> Iterator[None]:
        """Keep the numerical boundary inside the full actual call observer."""
        if self._initial is not None and (
            self._observer is None
            or not self._observer.active
            or sys.getprofile() != self._observer._observe
        ):
            self._reasons.append("n5_execution_observer_interrupted")
        yield

    def __exit__(self, *exc: object) -> None:
        del exc
        # The producer input owner, outside controller.run, closes its observer
        # after result construction. The inner numerical scope must not stop it.

    def bind_trajectories(self, trajectories: Sequence[object]) -> None:
        """Bind only the trajectory values returned by the real runner."""
        self._trajectory_bytes = exact_n5_content_bytes(
            [
                item.model_dump(mode="json")
                for item in trajectories  # type: ignore[attr-defined]
            ]
        )
        self._trajectory_hash = "sha256:" + hashlib.sha256(self._trajectory_bytes).hexdigest()

    def _current_implementation(self) -> dict[str, Any]:
        from polisyos.foundry.methods.selection.registry import MethodRegistry
        from polisyos.runtime.quality.confidence_ledger import (
            capture_execution_source_bindings,
        )
        from polisyos.runtime.quality.joint_simulation_horizon import (
            JointSimulationHorizonController,
        )

        if type(self._controller) is not JointSimulationHorizonController:
            raise ValueError("n5_selected_controller_not_canonical")
        from polisyos.runtime.quality.generation_cycle import (
            GenerationCycleController,
            JointSimulationPort,
        )
        from polisyos.runtime.quality.joint_simulation_horizon import (
            JointSimulationControllerPolicy,
            _RuntimeSettings,
            prepare_joint_simulation_configuration,
            require_prepared_joint_simulation_configuration,
        )

        _default_receiver_protocol(self._controller)
        if self._admission is not None:
            _default_receiver_protocol(self._admission.port)
        if self._admission is None or type(self._admission.port) is not JointSimulationPort:
            raise ValueError("n5_selected_input_port_not_canonical")
        construction_classes = (
            GenerationCycleController,
            JointSimulationPort,
            JointSimulationHorizonController,
        )
        entry_codes = []
        entry_functions = {}
        for owner, name in (
            (self._admission.port, "__call__"),
            (self._admission.port, "_build_candidate_simulation_request"),
            (self._controller, "run"),
            (self._controller, "_select_engine"),
        ):
            if name in vars(owner):
                raise ValueError("n5_consumed_entry_instance_shadow")
            if not isinstance(inspect.getattr_static(type(owner), name), types.FunctionType):
                raise ValueError("n5_consumed_entry_not_bound")
            method = getattr(owner, name)
            if not isinstance(method, types.MethodType) or method.__self__ is not owner:
                raise ValueError("n5_consumed_entry_not_bound")
            function = method.__func__
            entry_codes.append((function.__module__, function.__code__))
            entry_functions[f"{type(owner).__module__}.{type(owner).__qualname__}:{name}"] = (
                function
            )
        modules = {
            self.method.__module__,
            "polisyos.runtime.quality.joint_simulation_horizon",
            "polisyos.runtime.quality.generation_cycle",
            *(item.module for item in self._codes.values() if item.module.startswith("polisyos.")),
        }
        # Resolve current source/loader slots BEFORE invoking the current
        # selector. A changed selector must not run on the verifier's behalf.
        try:
            source = capture_execution_source_bindings(
                tuple(sorted(modules)),
                tuple((item.module, item.code) for item in self._codes.values()),
                bound_entry_code=tuple(entry_codes),
                receiver_classes=construction_classes,
            )
        except ValueError as exc:
            if getattr(exc, "code", None) == "n5_receiver_construction_not_established":
                raise ValueError("n5_receiver_construction_not_established") from exc
            raise
        entry_bindings = {
            name: _binding_value(function) for name, function in entry_functions.items()
        }
        construction_bindings = {
            f"{cls.__module__}.{cls.__qualname__}": _construction_binding(cls)
            for cls in construction_classes
        }
        if (
            type(self._controller._settings) is not _RuntimeSettings
            or type(self._controller.policy) is not JointSimulationControllerPolicy
        ):
            raise ValueError("n5_receiver_configuration_not_established")
        typed_configuration = {
            "runtime_settings": _exact_native_content(self._controller._settings),
            "policy": _exact_native_content(self._controller.policy),
        }
        require_prepared_joint_simulation_configuration(
            self._controller,
            self._controller._prepared_configuration,
        )
        # This is the real future owner's typed preparation, not native
        # validator identity/default metadata. The action passes that prepared
        # object into execution; defaults are not read a second time there.
        construction_bindings["fresh_prepared_configuration"] = _exact_native_content(
            prepare_joint_simulation_configuration()
        )
        current_registry = MethodRegistry.get_instance()
        if self._controller._registry is not current_registry:
            raise ValueError("n5_selected_registry_current_owner_not_established")
        selected = self._controller._select_engine(self._request)
        if (
            selected.decision.decision != "selected"
            or selected.decision.method_fqn != self._method_fqn
            or current_registry.get(self._method_fqn) is not self.method
        ):
            raise ValueError("n5_current_selected_implementation_changed")
        receiver_bindings: dict[str, object] = {}
        for item in self._codes.values():
            roots = dict(item.receiver_roots)
            instructions = tuple(dis.get_instructions(item.code))
            for index, instruction in enumerate(instructions[:-1]):
                if not (
                    instruction.opname.startswith("LOAD_FAST") or instruction.opname == "LOAD_DEREF"
                ):
                    continue
                name = instruction.argval
                if isinstance(name, tuple):
                    name = name[-1]
                if not isinstance(name, str) or name not in roots:
                    continue
                following = instructions[index + 1]
                if following.opname not in {"LOAD_ATTR", "LOAD_METHOD"}:
                    continue
                receiver = roots[name]
                _default_receiver_protocol(receiver)
                attribute = str(following.argval)
                class_slot = inspect.getattr_static(type(receiver), attribute, None)
                if isinstance(class_slot, property):
                    raise ValueError("n5_consumed_receiver_descriptor_not_established")
                if isinstance(
                    class_slot, (types.FunctionType, classmethod, staticmethod)
                ) and attribute in vars(receiver):
                    raise ValueError("n5_consumed_receiver_dispatch_not_established")
                value = object.__getattribute__(receiver, attribute)
                if receiver is self._controller and attribute == "_registry":
                    # Its entire selected decision/plan is recomputed above;
                    # unrelated methods in a shared registry are not this
                    # evaluation's native input quantity.
                    if value is not current_registry:
                        raise ValueError("n5_selected_registry_current_owner_not_established")
                    projected = {"selected_registry_object": _token(value)}
                elif receiver is self._controller and attribute == "_producer_budget_observer":
                    from polisyos.scientist.orchestration.engine.producer_budget import (
                        ProducerBudgetObserver,
                    )

                    if value is not None and type(value) is not ProducerBudgetObserver:
                        raise ValueError("n5_receiver_budget_guard_not_established")
                    # Spend/allocation is a current-work guard, not numerical
                    # intent. It is re-run by the actual cheap continuation;
                    # a new acquisition must not rewrite old spend or rerun
                    # N5 merely because an allocation changed.
                    projected = {
                        "current_work_budget_guard": None if value is None else _token(value)
                    }
                else:
                    projected = _binding_value(value)
                receiver_bindings[f"{item.module}:{item.code.co_qualname}:{name}.{attribute}"] = (
                    projected
                )
        # Reopen the selected old input and replay the real preparation port.
        # This is its owner-defined effective relation, not serialization of
        # CAS/DB/context/cache receiver objects or a caller's completeness flag.
        from polisyos.runtime.quality.generation_source import GenerationSourceRepository

        port = self._admission.port
        handoff = port._candidate_simulation_handoff
        if handoff is None or port._artifact_store is None:
            raise ValueError("n5_receiver_preparation_owner_not_established")
        record = GenerationSourceRepository(port._artifact_store).resolve_candidate_simulation_v5(
            ref=self._admission.input_ref,
            expected_job_id=handoff.job_id,
            expected_run_id=handoff.run_id,
            expected_tenant_id=handoff.tenant_id,
            expected_cell_id=handoff.cell_id,
        )
        if record.content_hash != self._admission.input_content_hash:
            raise ValueError("n5_receiver_preparation_input_changed")
        replayed_request = port._build_candidate_simulation_request(
            candidate=self._admission.candidate,
            problem=self._admission.problem,
            input_record=record,
        )
        if exact_n5_content_bytes(replayed_request) != self._request_bytes:
            raise ValueError("n5_receiver_preparation_values_changed")
        bindings: dict[str, object] = {}
        for item in self._codes.values():
            module = sys.modules.get(item.module)
            if module is None or getattr(module, "__dict__", None) is not item.globals:
                raise ValueError("n5_executed_globals_not_owner_bound")
            raw_builtins = item.globals.get("__builtins__")
            builtins_scope = (
                vars(raw_builtins) if isinstance(raw_builtins, types.ModuleType) else raw_builtins
            )
            if not isinstance(builtins_scope, dict) or builtins_scope is not item.frame.f_builtins:
                raise ValueError("n5_executed_builtins_not_owner_bound")
            for name in item.code.co_names:
                if name in item.globals:
                    bindings[f"{item.module}:global:{name}"] = _binding_value(item.globals[name])
                elif name in builtins_scope:
                    bindings[f"{item.module}:builtin:{name}"] = _binding_value(builtins_scope[name])
            for name in item.code.co_freevars:
                if name not in item.frame.f_locals:
                    raise ValueError("n5_loaded_closure_binding_not_established")
                value = item.frame.f_locals[name]
                # The observer itself does not supply numerical meaning. All
                # remaining captured native values/selected callables do.
                if value is self:
                    continue
                if callable(value) or isinstance(value, (types.ModuleType, type)):
                    projected = _binding_value(value)
                else:
                    projected = {"native_value": _exact_native_content(value)}
                bindings[f"{item.module}:{item.code.co_qualname}:closure:{name}"] = projected
            instructions = tuple(dis.get_instructions(item.code))
            for index, instruction in enumerate(instructions):
                if instruction.opname not in {"LOAD_GLOBAL", "LOAD_NAME"}:
                    continue
                name = str(instruction.argval)
                value = item.globals.get(name)
                if not isinstance(value, types.ModuleType):
                    continue
                path = [name]
                for following in instructions[index + 1 :]:
                    if following.opname != "LOAD_ATTR":
                        break
                    name = str(following.argval)
                    namespace = vars(value) if hasattr(value, "__dict__") else {}
                    if name not in namespace:
                        raise ValueError("n5_loaded_attribute_binding_not_established")
                    value = namespace[name]
                    path.append(name)
                    bindings[f"{item.module}:{'.'.join(path)}"] = _binding_value(value)
        entry = getattr(self.method, "pure_step", None)
        if entry is not self._entry or not isinstance(entry, types.FunctionType):
            raise ValueError("n5_selected_callable_changed")
        return {
            "method_object": _token(self.method),
            "entry_object": _token(entry),
            "entry_code": _code_hash(entry.__code__),
            "source": source,
            "entry_bindings": entry_bindings,
            "construction_bindings": construction_bindings,
            "typed_receiver_configuration": typed_configuration,
            "consumed_receiver_bindings": receiver_bindings,
            "selected_engine_values": _exact_native_content(selected),
            "live_global_bindings": bindings,
            "native_calls": tuple(sorted(self._native_calls)),
            "native_origins": _native_origins(),
            "numerical_policy": _numeric_policy(self.method),
        }

    def seal(
        self, *, input_ref: ArtifactRef, result: JointSimulationResult
    ) -> N5ExecutionImplementationWitness:
        """Seal an actually observed execution, refusing unsupported or altered bindings."""
        if self._admission is None or artifact_ref_identity_key(input_ref) != (
            artifact_ref_identity_key(self._admission.input_ref)
        ):
            raise ValueError("n5_execution_capture_input_relabelled")
        if self._sealed is not None:
            if self._result_bytes != exact_n5_content_bytes(result.content_bound_payload()):
                raise ValueError("n5_execution_capture_result_relabelled")
            return self._sealed
        reasons = list(self._reasons)
        if (
            self._observer is None
            or not self._observer.completed
            or self._observer.reason is not None
        ):
            reasons.append(
                self._observer.reason
                if self._observer is not None and self._observer.reason is not None
                else "n5_execution_observer_completion_not_established"
            )
        self._entry_observed = isinstance(self._entry, types.FunctionType) and any(
            item.code is self._entry.__code__ for item in self._codes.values()
        )
        if not self._entry_observed or not self._codes or self._trajectory_hash is None:
            reasons.append("n5_selected_entry_not_observed")
        trajectories = exact_n5_content_hash(
            [item.model_dump(mode="json") for item in result.trajectories]
        )
        if (
            exact_n5_content_bytes([item.model_dump(mode="json") for item in result.trajectories])
            != self._trajectory_bytes
        ):
            reasons.append("n5_observed_trajectory_mismatch")
        if exact_n5_content_bytes(self._request) != self._request_bytes:
            reasons.append("n5_input_changed_during_execution")
        implementation: dict[str, Any] = {}
        try:
            implementation = _json_wire(self._current_implementation())
            if self._initial is not None:
                for key in (
                    "method_object",
                    "entry_object",
                    "entry_code",
                    "entry_bindings",
                    "construction_bindings",
                    "typed_receiver_configuration",
                    "numerical_policy",
                ):
                    if implementation[key] != self._initial[key]:
                        reasons.append("n5_implementation_changed_during_execution")
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            reasons.append(str(getattr(exc, "code", None) or exc))
        consumed_configuration = None
        try:
            from polisyos.runtime.quality.joint_simulation_horizon import (
                read_joint_simulation_configuration,
            )

            end_configuration = _exact_native_content(
                read_joint_simulation_configuration(self._controller)
            )
            if self._configuration_start is not None and exact_n5_content_bytes(
                end_configuration
            ) == exact_n5_content_bytes(self._configuration_start):
                consumed_configuration = end_configuration
            else:
                reasons.append("n5_consumed_configuration_not_established")
        except (AttributeError, TypeError, ValueError):
            reasons.append("n5_consumed_configuration_not_established")
        payload = {
            "schema_version": "N5ExecutionImplementationWitness@1.0",
            "authority_purpose": "candidate_evaluation_retention_only",
            "comparison_scope": "same_live_process_loaded_implementation",
            "process_session": _SESSION,
            "input_ref_identity": list(artifact_ref_identity_key(input_ref)),
            "request_content_hash": self.request_hash,
            "result_without_witness_hash": exact_n5_content_hash(result.content_bound_payload()),
            "trajectory_hash": trajectories,
            "implementation": implementation,
            "consumed_configuration_values": consumed_configuration,
            "predicate_provenance": "not_established" if reasons else "recomputed",
            "reason_codes": list(dict.fromkeys(reasons)),
        }
        witness = N5ExecutionImplementationWitness.model_validate(
            {**payload, "content_hash": exact_n5_content_hash(payload)}
        )
        self._result_bytes = exact_n5_content_bytes(result.content_bound_payload())
        self._sealed = witness
        if not reasons:
            with _LOCK:
                _ISSUED[witness.content_hash] = _IssuedExecution(witness, self)
        return witness


def bind_n5_execution_implementation(
    result: JointSimulationResult,
    *,
    input_ref: ArtifactRef,
    capture: N5ImplementationCapture | None,
) -> JointSimulationResult:
    """Content-bind the real producer witness into the selected result payload."""
    from copy import deepcopy

    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationResult,
        build_content_bound_simulation_receipt,
        verify_simulation_receipt,
    )

    if type(capture) is not N5ImplementationCapture:
        return result
    verify_simulation_receipt(result.receipt, result.content_bound_payload())
    witness = capture.seal(input_ref=input_ref, result=result)
    payload = deepcopy(result.content_bound_payload())
    payload["diagnostics"][_DIAGNOSTIC_KEY] = witness.model_dump(mode="json")
    receipt = build_content_bound_simulation_receipt(
        engine_kind=result.receipt.engine_kind, payload=payload, diagnostics=payload["diagnostics"]
    )
    bound = JointSimulationResult.model_validate(
        {**payload, "receipt": receipt.model_dump(mode="json")}
    )
    bound._content_payload = payload
    verify_simulation_receipt(bound.receipt, bound.content_bound_payload())
    return bound


def reconcile_live_n5_implementation(
    result: JointSimulationResult, *, input_ref: ArtifactRef
) -> N5ExecutionImplementationWitness:
    """Resolve a real prior witness and recompute its current live implementation.

    A serialized positive marker, a prior V5 without observation, a different
    process or changed loaded dependency cannot authorize retention.
    """
    from copy import deepcopy

    from polisyos.runtime.quality.joint_simulation_horizon import verify_simulation_receipt

    verify_simulation_receipt(result.receipt, result.content_bound_payload())
    raw = result.diagnostics.get(_DIAGNOSTIC_KEY)
    witness = N5ExecutionImplementationWitness.model_validate(raw)
    if witness.process_session != _SESSION or witness.predicate_provenance != "recomputed":
        raise ValueError("n5_prior_live_implementation_not_established")
    with _LOCK:
        issued = _ISSUED.get(witness.content_hash)
    if issued is None or issued.witness != witness:
        raise ValueError("n5_execution_witness_not_producer_observed")
    if witness.input_ref_identity != artifact_ref_identity_key(input_ref):
        raise ValueError("n5_execution_witness_input_mismatch")
    payload = deepcopy(result.content_bound_payload())
    del payload["diagnostics"][_DIAGNOSTIC_KEY]
    if exact_n5_content_bytes(payload) != issued.capture._result_bytes:
        raise ValueError("n5_execution_witness_result_mismatch")
    current = _json_wire(issued.capture._current_implementation())
    if current.get("construction_bindings") != witness.implementation.get("construction_bindings"):
        raise ValueError("n5_receiver_construction_not_established")
    if current != witness.implementation:
        raise ValueError("n5_live_implementation_changed")
    return witness


def read_n5_execution_implementation_witness(
    result: JointSimulationResult,
    *,
    input_ref: ArtifactRef,
) -> N5ExecutionImplementationWitness:
    """Read an actual selected result's historical observation, without current permission.

    The caller must first resolve the execution/result through the normal source
    repository. This verifies content and joins; it never grants new retention
    without ``reconcile_live_n5_implementation`` and the native/SQL fence.
    """
    from copy import deepcopy

    from polisyos.runtime.quality.joint_simulation_horizon import verify_simulation_receipt

    verify_simulation_receipt(result.receipt, result.content_bound_payload())
    witness = N5ExecutionImplementationWitness.model_validate(
        result.diagnostics.get(_DIAGNOSTIC_KEY)
    )
    if witness.input_ref_identity != artifact_ref_identity_key(input_ref):
        raise ValueError("n5_execution_witness_input_mismatch")
    payload = deepcopy(result.content_bound_payload())
    del payload["diagnostics"][_DIAGNOSTIC_KEY]
    if exact_n5_content_hash(payload) != witness.result_without_witness_hash:
        raise ValueError("n5_execution_witness_result_mismatch")
    trajectories = [item.model_dump(mode="json") for item in result.trajectories]
    if exact_n5_content_hash(trajectories) != witness.trajectory_hash:
        raise ValueError("n5_execution_witness_trajectories_mismatch")
    return witness
