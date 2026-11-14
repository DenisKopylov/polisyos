"""Observe the implementation actually called by a controlled N5 execution.

This is a process-local execution witness, not a package-name attestation or a
cross-process cache permit. The real controller records executed Python code and
live bindings, native origins and numerical policy. Only an observation held by
that producer can authorize current reuse; old/unobserved executions stay
``not_established``. Historical receipts retain their original meaning.
"""

from __future__ import annotations

import dataclasses
import dis
import gc
import hashlib
import importlib.machinery
import inspect
import json
import math
import os
import platform
import re
import struct
import sys
import threading
import types
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime, timezone
from datetime import time as datetime_time
from decimal import Decimal
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Literal, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import artifact_ref_identity_key
from polisyos.runtime.quality.authority import PredicateProvenanceClass

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationRequest,
        JointSimulationResult,
        PreparedJointSimulationConfiguration,
    )


def _exact_native_content(value: object, *, strict: bool = False) -> object:
    """Project native typed content; strict mode refuses unsupported protocols."""
    if strict:
        return _strict_n5_native_content(value, seen=set(), budget=[10000, 1024**2])
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
        model_field_names = exact_n5_model_field_names(value)
        return {
            "model": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {
                name: _exact_native_content(getattr(value, name)) for name in model_field_names
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


def exact_n5_model_field_names(value: BaseModel) -> frozenset[str]:
    """Return the exact persisted model fields, allowing one typed read diagnostic.

    Pydantic's declared field set remains the serialization denominator. A
    GenerationSourceRepository may attach one typed, non-persisted read witness
    to its returned declaration; that witness is diagnostic and is excluded
    from native content only after its exact owner type is established.
    """

    if not isinstance(value, BaseModel):
        raise TypeError("n5_native_model_field_denominator_not_established")
    field_names = frozenset(type(value).model_fields)
    instance_values = vars(value)
    if type(instance_values) is not dict or value.__pydantic_extra__:
        raise ValueError("n5_native_model_field_denominator_not_established")
    instance_names = frozenset(instance_values)
    if instance_names == field_names:
        return field_names
    diagnostic_name = "_generation_source_read_provenance"
    if instance_names != field_names | {diagnostic_name}:
        raise ValueError("n5_native_model_field_denominator_not_established")
    from polisyos.runtime.quality.generation_source import (
        _GenerationSourceReadProvenance,
    )

    if type(instance_values[diagnostic_name]) is not _GenerationSourceReadProvenance:
        raise ValueError("n5_native_model_field_denominator_not_established")
    return field_names


def _implementation_failure_reasons(exc: Exception) -> tuple[str, ...]:
    """Retain bounded source locators without persisting free-form error detail."""
    from polisyos.runtime.quality.confidence_ledger import ConfidenceLedgerError

    reason = str(getattr(exc, "code", None) or exc)
    reasons = [reason]
    if type(exc) is not ConfidenceLedgerError:
        return tuple(reasons)
    # These are diagnostics only. The original refusal remains load-bearing;
    # neither a traceback locator nor an error's target establishes a binding.
    traceback = exc.__traceback__
    site = None
    while traceback is not None:
        code = traceback.tb_frame.f_code
        module = traceback.tb_frame.f_globals.get("__name__")
        if (
            type(module) is str
            and len(module) <= 256
            and re.fullmatch(r"polisyos(?:\.[A-Za-z_][A-Za-z_0-9]*)+", module)
            and len(code.co_qualname) <= 256
            and re.fullmatch(
                r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*", code.co_qualname
            )
        ):
            site = (
                f"n5_implementation_failure_site:{module}.{code.co_qualname}:{traceback.tb_lineno}"
            )
        traceback = traceback.tb_next
    if site is not None:
        reasons.append(site)
    detail = exc.detail
    if type(detail) is str and len(detail) <= 512:
        _, separator, target = detail.rpartition(": ")
        if separator and re.fullmatch(r"polisyos(?:\.[A-Za-z_][A-Za-z_0-9]*)+", target):
            reasons.append(f"n5_implementation_failure_target:{target}")
    return tuple(reasons)


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
) -> Iterator[JointSimulationRequest]:
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
    # The rebuilt request owns its CAS-selected numerical inputs. Its world
    # model may still alias the port's revalidated context, so detach that
    # nested model before passing the request to the controller.
    expected = expected.model_copy(
        update={"world_model_record": expected.world_model_record.model_copy(deep=True)}
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
            expected,
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
            yield expected
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
                if key not in self.codes:
                    self.codes[key] = _ExecutedCode(
                        module,
                        frame.f_code,
                        frame.f_globals,
                        frame,
                        tuple(
                            (name, value)
                            for name, value in frame.f_locals.items()
                            if any(value is root for root in self.receiver_roots)
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
        selected_step: object,
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
        self._entry = selected_step
        self._supported = (
            method is NCMEngineMethod
            and isinstance(selected_step, types.FunctionType)
            and getattr(method, "pure_step", None) is selected_step
        )
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
            self._reasons.extend(_implementation_failure_reasons(exc))
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

    def _early_python_provider_observation(self) -> dict[str, object] | None:
        """Observe the selected provider only through the retained host capture."""
        from polisyos.runtime.quality import confidence_ledger

        if (
            "_polisyos_loaded_host_v1" not in sys.__dict__
            and confidence_ledger._LOADED_EXECUTION_OBSERVATION_SEAL is None
        ):
            return None
        if not isinstance(self._entry, types.FunctionType):
            return None
        return confidence_ledger._observe_n5_early_python_provider(
            self.method,
            self._entry,
            tuple((item.code, item.globals) for item in self._codes.values()),
        )

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
        implementation = {
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
        early_provider = self._early_python_provider_observation()
        if early_provider is not None:
            implementation["early_python_provider_observation"] = early_provider
        return implementation

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
            reasons.extend(_implementation_failure_reasons(exc))
        early_provider = implementation.get("early_python_provider_observation")
        if early_provider is None:
            early_provider = self._early_python_provider_observation()
        if early_provider is not None:
            implementation["early_python_provider_observation"] = early_provider
            if early_provider["predicate_provenance"] != "independently_reconciled":
                reasons.append("canonical_loaded_runtime_mismatch")
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


def _candidate_n5_historical_configuration_matches(
    witness: N5ExecutionImplementationWitness,
    prepared_configuration: PreparedJointSimulationConfiguration,
) -> bool:
    """Compare the historical configuration snapshot with its prepared descriptor.

    The selected result must already be resolved through its owner and the witness
    obtained through ``read_n5_execution_implementation_witness``. Snapshot equality
    does not establish configuration use throughout engine selection or coupling.
    """
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
    )

    if (
        type(witness) is not N5ExecutionImplementationWitness
        or type(prepared_configuration) is not PreparedJointSimulationConfiguration
        or type(witness.consumed_configuration_values) is not dict
    ):
        return False
    try:
        observed = exact_n5_content_bytes(witness.consumed_configuration_values)
        expected = exact_n5_content_bytes(_exact_native_content(prepared_configuration))
    except (TypeError, ValueError):
        return False
    return observed == expected


def _candidate_n5_failure_diagnostic_is_bounded(reason: str) -> bool:
    """Recognize only the bounded source locators emitted by this witness owner."""
    target_prefix = "n5_implementation_failure_target:"
    site_prefix = "n5_implementation_failure_site:"
    module_pattern = r"polisyos(?:\.[A-Za-z_][A-Za-z_0-9]*)+"
    if reason.startswith(target_prefix):
        target = reason.removeprefix(target_prefix)
        return len(target) <= 256 and re.fullmatch(module_pattern, target) is not None
    return (
        len(reason) <= 560
        and re.fullmatch(
            rf"{site_prefix}polisyos(?:\.[A-Za-z_][A-Za-z_0-9]*){{2,}}:[1-9][0-9]{{0,7}}",
            reason,
        )
        is not None
    )


def _candidate_n5_experiment_observation_supported(
    witness: N5ExecutionImplementationWitness,
    prepared_configuration: PreparedJointSimulationConfiguration,
) -> bool:
    """Gate candidate output on completed-result integrity and limited source refusal.

    A source binding refusal can leave a candidate result available when the
    physical observer completed and the request, trajectories and configuration
    snapshots agree. The caller keeps configuration use and implementation
    provenance ``not_established``. This predicate grants no scientific reuse.
    """
    if not _candidate_n5_historical_configuration_matches(witness, prepared_configuration):
        return False
    if witness.predicate_provenance == "recomputed":
        return True
    if witness.predicate_provenance != "not_established":
        return False
    reasons = witness.reason_codes
    return "canonical_loaded_runtime_mismatch" in reasons and all(
        reason == "canonical_loaded_runtime_mismatch"
        or _candidate_n5_failure_diagnostic_is_bounded(reason)
        for reason in reasons
    )


# V2 is a candidate observation. It does not alter the v1 live-issuance or
# historical-reader contract above, and cannot authorize protected reuse.
_N5CallResult = TypeVar("_N5CallResult")
_CONTENT_NORMALIZATION = "supported-native-pre-invocation-content/2"
_CONTENT_SCHEMA = "N5ExecutionContentWitness@2.0"


def _v2_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _v2_hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(_v2_json(value).encode()).hexdigest()


def _require_v2_wire(value: str | None) -> None:
    """Require the frozen witness bytes to be canonical inert JSON."""
    if value is None:
        return
    try:
        decoded = json.loads(value)
        canonical = _v2_json(decoded)
    except (TypeError, ValueError) as exc:
        raise ValueError("n5_content_wire_invalid") from exc
    if type(decoded) is not dict or canonical != value:
        raise ValueError("n5_content_wire_invalid")


def _require_v2_predicates(
    predicates: tuple[N5ContentPredicate, ...], expected: dict[str, str]
) -> None:
    observed = {item.predicate_id: item.provenance for item in predicates}
    if len(observed) != len(predicates) or any(
        observed.get(name) != provenance for name, provenance in expected.items()
    ):
        raise ValueError("n5_content_predicate_scope_mismatch")


def _native_type_label(kind: type) -> str:
    namespace = type.__dict__["__dict__"].__get__(kind, type(kind))
    module = namespace.get("__module__")
    qualname = type.__dict__["__qualname__"].__get__(kind, type(kind))
    if type(module) is not str or type(qualname) is not str:
        raise ValueError("n5_native_content_not_established")
    return module + "." + qualname


def _strict_n5_native_content(
    value: object, *, seen: set[int], budget: list[int], depth: int = 0
) -> object:
    """Copy a bounded native/declared-field domain without opaque serialization."""
    if depth > 40 or budget[0] <= 0:
        raise ValueError("n5_native_content_not_established")
    budget[0] -= 1
    kind = type(value)
    if value is None or kind is bool or kind is int or kind is str:
        size = (
            len(value) * 4 if kind is str else (value.bit_length() + 7) // 8 if kind is int else 0
        )
        budget[1] -= size
        if budget[1] < 0:
            raise ValueError("n5_native_content_not_established")
        return {kind.__name__: value}
    if kind is float or kind is complex:
        from polisyos.runtime.quality.confidence_ledger import _strict_ieee754_content

        return _strict_ieee754_content(value)
    if kind is bytes:
        budget[1] -= len(value)
        if budget[1] < 0:
            raise ValueError("n5_native_content_not_established")
        return {"bytes": value.hex()}
    if kind is Decimal:
        return {"decimal": str(value)}
    if kind is date:
        return {"date": value.isoformat()}
    if kind is datetime or kind is datetime_time:
        zone = value.tzinfo
        if zone is not None and type(zone) is not timezone:
            raise ValueError("n5_native_content_not_established")
        zone_content = None
        if zone is not None:
            offset, name = zone.utcoffset(None), zone.tzname(None)
            if offset is None or type(name) is not str:
                raise ValueError("n5_native_content_not_established")
            zone_content = {
                "offset": [offset.days, offset.seconds, offset.microseconds],
                "name": name,
            }
        return {
            kind.__name__: {"iso": value.isoformat(), "fold": value.fold, "timezone": zone_content}
        }
    if id(value) in seen:
        raise ValueError("n5_native_content_not_established")
    seen.add(id(value))

    def encode(item: object) -> object:
        return _strict_n5_native_content(item, seen=seen, budget=budget, depth=depth + 1)

    if kind is dict:
        if len(value) > budget[0]:
            raise ValueError("n5_native_content_not_established")
        return {"mapping": [(encode(key), encode(item)) for key, item in value.items()]}
    if any(kind is supported for supported in (tuple, list, set, frozenset)):
        if len(value) > budget[0]:
            raise ValueError("n5_native_content_not_established")
        items = [encode(item) for item in value]
        if kind is set or kind is frozenset:
            items.sort(key=_v2_json)
        return {kind.__name__: items}
    # Known typed owners supply a declared field denominator. Custom instance
    # protocols/field descriptors remain unknown; no model serializer is called.
    if type(kind) is type(BaseModel) and issubclass(kind, BaseModel):
        if inspect.getattr_static(kind, "__getattribute__") is not object.__getattribute__:
            raise ValueError("n5_native_content_not_established")
        for slot in ("__dict__", "__pydantic_extra__"):
            if inspect.getattr_static(kind, slot) is not inspect.getattr_static(BaseModel, slot):
                raise ValueError("n5_native_content_not_established")
        values = vars(value)
        if any(type(key) is not str for key in values):
            raise ValueError("n5_native_content_not_established")
        names = exact_n5_model_field_names(value)
        missing = object()
        if any(inspect.getattr_static(kind, name, missing) is not missing for name in names):
            raise ValueError("n5_native_content_not_established")
        return {
            "model": _native_type_label(kind),
            "fields": {name: encode(values[name]) for name in sorted(names)},
        }
    if type(kind) is type(Enum) and issubclass(kind, Enum):
        dictionary = inspect.getattr_static(kind, "__dict__", None)
        if type(dictionary) is not types.GetSetDescriptorType:
            raise ValueError("n5_native_content_not_established")
        values = dictionary.__get__(value, kind)
        if type(values) is not dict or "_value_" not in values:
            raise ValueError("n5_native_content_not_established")
        return {"enum": _native_type_label(kind), "value": encode(values["_value_"])}
    if (
        type(kind) is type
        and inspect.getattr_static(kind, "__getattribute__") is object.__getattribute__
    ):
        declared = inspect.getattr_static(kind, "__dataclass_fields__", None)
        if type(declared) is dict:
            names = tuple(field.name for field in fields(kind))
            for name in names:
                descriptor = inspect.getattr_static(kind, name, None)
                if inspect.getattr_static(
                    type(descriptor), "__get__", None
                ) is not None and not any(
                    type(descriptor) is supported
                    for supported in (types.MemberDescriptorType, types.GetSetDescriptorType)
                ):
                    raise ValueError("n5_native_content_not_established")
            return {
                "dataclass": _native_type_label(kind),
                "fields": {name: encode(object.__getattribute__(value, name)) for name in names},
            }
    raise ValueError("n5_native_content_not_established")


def _v2_native_wire(value: object) -> str:
    return _v2_json(_exact_native_content(value, strict=True))


class N5ContentPredicate(BaseModel):
    """One scoped predicate reported by a candidate content observer."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    predicate_id: str = Field(min_length=1)
    provenance: PredicateProvenanceClass
    reason_codes: tuple[str, ...] = ()


class N5ProductionSourceFile(BaseModel):
    """One path and byte identity in a prospective production source image."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    relative_path: str = Field(min_length=1, max_length=4096)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _relative(self) -> N5ProductionSourceFile:
        path = PurePosixPath(self.relative_path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in self.relative_path
            or path.as_posix() != self.relative_path
        ):
            raise ValueError("n5_production_source_path_invalid")
        return self


class N5ProductionImage(BaseModel):
    """Conservative path/byte inventory; not proof of loaded or executed code."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["N5ProductionImage@2.0"] = "N5ProductionImage@2.0"
    source_scope: Literal["all_first_party_production_python"] = "all_first_party_production_python"
    python_sources: tuple[N5ProductionSourceFile, ...]
    lock_content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    platform_content: str
    selected_profile_content: str | None
    provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _content(self) -> N5ProductionImage:
        _require_v2_wire(self.platform_content)
        _require_v2_wire(self.selected_profile_content)
        if self.content_hash != _v2_hash(self.model_dump(mode="json", exclude={"content_hash"})):
            raise ValueError("n5_production_image_content_mismatch")
        paths = tuple(item.relative_path for item in self.python_sources)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("n5_production_image_paths_invalid")
        if self.provenance == "recomputed" and (
            not paths
            or self.lock_content_hash is None
            or self.selected_profile_content is None
            or self.reason_codes
        ):
            raise ValueError("n5_production_image_not_established")
        return self


def capture_n5_production_image(*, root: Path, admitted_profile: object) -> N5ProductionImage:
    """Read the full production Python inventory and selected profile as content.

    Profile admission is a separate predicate. Supplying profile bytes here does
    not establish their authority or any loaded/executed module denominator.
    """
    sources: list[N5ProductionSourceFile] = []
    reasons = []
    lock_hash = None
    profile = None
    platform_wire = _v2_native_wire(
        {
            "implementation": sys.implementation.name,
            "version": tuple(sys.version_info[:3]),
            "cache_tag": sys.implementation.cache_tag,
            "optimize": sys.flags.optimize,
            "platform": sys.platform,
            "machine": platform.machine(),
        }
    )
    try:
        root = root.resolve(strict=True)
        package = root / "src" / "polisyos"
        if not package.is_dir() or package.is_symlink():
            raise ValueError("n5_production_image_not_established")
        before = []
        for directory, directories, files in os.walk(package, followlinks=False):
            base = Path(directory)
            if any((base / name).is_symlink() for name in directories):
                raise ValueError("n5_production_image_not_established")
            for name in files:
                if name.endswith(".py"):
                    path = base / name
                    if path.is_symlink() or not path.is_file():
                        raise ValueError("n5_production_image_not_established")
                    before.append(path)
        for path in sorted(before):
            sources.append(
                N5ProductionSourceFile(
                    relative_path=path.relative_to(root).as_posix(), content_hash=_file_hash(path)
                )
            )
        after = sorted(path for path in package.rglob("*.py") if path.is_file())
        if sorted(before) != after or not sources:
            raise ValueError("n5_production_image_not_established")
        lock = root / "uv.lock"
        if lock.is_symlink() or not lock.is_file():
            raise ValueError("n5_production_image_not_established")
        lock_hash = _file_hash(lock)
        profile = _v2_native_wire(admitted_profile)
    except (OSError, TypeError, ValueError, RuntimeError):
        reasons.append("n5_production_image_not_established")
    payload = {
        "schema_version": "N5ProductionImage@2.0",
        "source_scope": "all_first_party_production_python",
        "python_sources": [item.model_dump(mode="json") for item in sources],
        "lock_content_hash": lock_hash,
        "platform_content": platform_wire,
        "selected_profile_content": profile,
        "provenance": "not_established" if reasons else "recomputed",
        "reason_codes": reasons,
    }
    return N5ProductionImage.model_validate({**payload, "content_hash": _v2_hash(payload)})


class N5ControlledCallObservation(BaseModel):
    """One actual owner-invoked call with frozen pre-invocation content."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    sequence: int = Field(ge=0)
    local_callable_token: str = Field(min_length=1)
    callable_content: str | None
    arguments_content: str | None
    output_content: str | None
    callable_content_hash: str | None = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    numerical_content_hash: str | None = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: Literal["returned", "raised"]
    predicates: tuple[N5ContentPredicate, ...]
    recorded_module_membership_content: str | None = None

    @model_validator(mode="after")
    def _scope(self) -> N5ControlledCallObservation:
        for wire in (
            self.callable_content,
            self.arguments_content,
            self.output_content,
            self.recorded_module_membership_content,
        ):
            _require_v2_wire(wire)
        if self.status == "raised" and self.output_content is not None:
            raise ValueError("n5_controlled_call_outcome_mismatch")
        _require_v2_predicates(
            self.predicates,
            {
                "callable_state": "recomputed"
                if self.callable_content is not None
                else "not_established",
                "argument_content": "recomputed"
                if self.arguments_content is not None
                else "not_established",
                "output_content": "recomputed"
                if self.output_content is not None
                else "not_established",
                "recorded_entry_code_membership": "independently_reconciled"
                if self.recorded_module_membership_content is not None
                else "not_established",
                "globals_and_full_readset": "not_established",
                "through_call_state_stability": "not_established",
            },
        )
        return self


class N5ExecutionContentWitness(BaseModel):
    """Candidate-only content record, separate from v1 protected live issuance."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["N5ExecutionContentWitness@2.0"] = _CONTENT_SCHEMA
    authority_purpose: Literal["candidate_observation_only"] = "candidate_observation_only"
    comparison_scope: Literal["supported_pre_invocation_content_only"] = (
        "supported_pre_invocation_content_only"
    )
    normalization_profile: Literal["supported-native-pre-invocation-content/2"] = (
        _CONTENT_NORMALIZATION
    )
    occurrence_id: str
    production_image: N5ProductionImage
    numerical_intent_content: str | None
    numerical_intent_content_hash: str | None = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    observed_calls: tuple[N5ControlledCallObservation, ...] = Field(min_length=1)
    predicates: tuple[N5ContentPredicate, ...]
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _content(self) -> N5ExecutionContentWitness:
        _require_v2_wire(self.numerical_intent_content)
        _require_v2_predicates(
            self.predicates,
            {
                "prospective_numerical_intent": "recomputed"
                if self.numerical_intent_content is not None
                else "not_established",
                "production_image_content": self.production_image.provenance,
                "profile_admission": "not_established",
                "optional_import_closure_n9": "not_established",
                "protected_reuse": "not_established",
            },
        )
        if self.content_hash != _v2_hash(self.model_dump(mode="json", exclude={"content_hash"})):
            raise ValueError("n5_execution_content_witness_mismatch")
        if tuple(item.sequence for item in self.observed_calls) != tuple(
            range(len(self.observed_calls))
        ):
            raise ValueError("n5_controlled_call_sequence_invalid")
        expected_intent = (
            None
            if self.numerical_intent_content is None
            else _v2_hash(json.loads(self.numerical_intent_content))
        )
        if self.numerical_intent_content_hash != expected_intent:
            raise ValueError("n5_numerical_intent_content_mismatch")
        for call in self.observed_calls:
            expected_callable = (
                None
                if call.callable_content is None
                else _v2_hash(json.loads(call.callable_content))
            )
            if call.callable_content_hash != expected_callable:
                raise ValueError("n5_callable_content_mismatch")
            expected = _n5_invocation_content_hash(
                self.production_image,
                self.numerical_intent_content_hash,
                call.callable_content,
                call.arguments_content,
                normalization_profile=self.normalization_profile,
            )
            if call.numerical_content_hash != expected:
                raise ValueError("n5_invocation_content_mismatch")
        return self


def _n5_invocation_content_hash(
    image: N5ProductionImage,
    intent_hash: str | None,
    callable_wire: str | None,
    arguments_wire: str | None,
    *,
    normalization_profile: str = _CONTENT_NORMALIZATION,
) -> str | None:
    if (
        image.provenance != "recomputed"
        or intent_hash is None
        or callable_wire is None
        or arguments_wire is None
    ):
        return None
    return _v2_hash(
        {
            "normalization_profile": normalization_profile,
            "production_image": image.content_hash,
            "numerical_intent": intent_hash,
            "callable": json.loads(callable_wire),
            "arguments": json.loads(arguments_wire),
        }
    )


class N5ControlledCallCapture:
    """Invoke retained callables and record supported content as candidate evidence.

    Globals/full readsets, transient mutations and protected reuse are not
    established. Local membership tokens never enter numerical content hashes.
    """

    _normalization_profile = _CONTENT_NORMALIZATION
    _schema_version = _CONTENT_SCHEMA
    _witness_type = N5ExecutionContentWitness

    @staticmethod
    def _native_wire(value: object) -> str:
        return _v2_native_wire(value)

    @staticmethod
    def _callable_wire(function: object) -> str:
        from polisyos.runtime.quality.confidence_ledger import _normalize_function_binding

        return _v2_json(_normalize_function_binding(function, strict=True))

    def _arguments_wire(
        self, function: object, args: tuple[object, ...], kwargs: dict[str, object]
    ) -> str:
        return self._native_wire((args, kwargs))

    def __init__(self, *, effective_inputs: object, production_image: N5ProductionImage) -> None:
        if type(production_image) is not N5ProductionImage:
            raise ValueError("n5_production_image_type_invalid")
        self._image = N5ProductionImage.model_validate_json(production_image.model_dump_json())
        try:
            self._intent = self._native_wire(effective_inputs)
        except (OSError, TypeError, ValueError, RuntimeError):
            self._intent = None
        self.numerical_intent_content_hash = (
            None if self._intent is None else _v2_hash(json.loads(self._intent))
        )
        self._occurrence = uuid4().hex
        self._retained: list[tuple[object, str]] = []
        self._calls: list[N5ControlledCallObservation | None] = []
        self._sealed: N5ExecutionContentWitness | None = None

    @property
    def observed_calls(self) -> tuple[N5ControlledCallObservation, ...]:
        """Return immutable snapshots already recorded by this owner."""
        return tuple(call for call in self._calls if call is not None)

    def _retain(self, function: object) -> str:
        for retained, token in self._retained:
            if retained is function:
                return token
        token = uuid4().hex
        self._retained.append((function, token))
        return token

    def observe_numerical_call(
        self, function: Callable[..., _N5CallResult], /, *args: object, **kwargs: object
    ) -> _N5CallResult:
        """Snapshot supported content, invoke this retained object, and record its return."""
        if self._sealed is not None:
            raise ValueError("n5_content_capture_already_sealed")
        retained = function
        token = self._retain(retained)
        sequence = len(self._calls)
        self._calls.append(None)
        callable_wire = arguments_wire = output_wire = membership = None
        with suppress(OSError, TypeError, ValueError, RuntimeError):
            callable_wire = self._callable_wire(retained)
        with suppress(OSError, TypeError, ValueError, RuntimeError):
            arguments_wire = self._arguments_wire(retained, args, kwargs)
        membership = _n5_recorded_entry_membership(retained)
        status: Literal["returned", "raised"] = "raised"
        try:
            result = retained(*args, **kwargs)
            status = "returned"
            with suppress(OSError, TypeError, ValueError, RuntimeError):
                output_wire = self._native_wire(result)
            return result
        finally:
            predicates = (
                N5ContentPredicate(
                    predicate_id="callable_state",
                    provenance="recomputed" if callable_wire is not None else "not_established",
                    reason_codes=()
                    if callable_wire is not None
                    else ("n5_callable_state_not_established",),
                ),
                N5ContentPredicate(
                    predicate_id="argument_content",
                    provenance="recomputed" if arguments_wire is not None else "not_established",
                ),
                N5ContentPredicate(
                    predicate_id="output_content",
                    provenance="recomputed" if output_wire is not None else "not_established",
                ),
                N5ContentPredicate(
                    predicate_id="recorded_entry_code_membership",
                    provenance="independently_reconciled"
                    if membership is not None
                    else "not_established",
                ),
                N5ContentPredicate(
                    predicate_id="globals_and_full_readset", provenance="not_established"
                ),
                N5ContentPredicate(
                    predicate_id="through_call_state_stability", provenance="not_established"
                ),
            )
            self._calls[sequence] = N5ControlledCallObservation(
                sequence=sequence,
                local_callable_token=token,
                callable_content=callable_wire,
                arguments_content=arguments_wire,
                output_content=output_wire,
                callable_content_hash=None
                if callable_wire is None
                else _v2_hash(json.loads(callable_wire)),
                numerical_content_hash=_n5_invocation_content_hash(
                    self._image,
                    self.numerical_intent_content_hash,
                    callable_wire,
                    arguments_wire,
                    normalization_profile=self._normalization_profile,
                ),
                status=status,
                predicates=predicates,
                recorded_module_membership_content=membership,
            )

    def seal(self) -> N5ExecutionContentWitness:
        """Freeze a candidate record without issuing protected reuse authority."""
        if self._sealed is not None:
            return self._sealed
        if any(call is None for call in self._calls):
            raise ValueError("n5_content_capture_in_progress")
        payload = {
            "schema_version": self._schema_version,
            "authority_purpose": "candidate_observation_only",
            "comparison_scope": "supported_pre_invocation_content_only",
            "normalization_profile": self._normalization_profile,
            "occurrence_id": self._occurrence,
            "production_image": self._image.model_dump(mode="json"),
            "numerical_intent_content": self._intent,
            "numerical_intent_content_hash": self.numerical_intent_content_hash,
            "observed_calls": [item.model_dump(mode="json") for item in self.observed_calls],
            "predicates": [
                {
                    "predicate_id": "prospective_numerical_intent",
                    "provenance": "recomputed" if self._intent is not None else "not_established",
                    "reason_codes": [],
                },
                {
                    "predicate_id": "production_image_content",
                    "provenance": self._image.provenance,
                    "reason_codes": list(self._image.reason_codes),
                },
                {
                    "predicate_id": "profile_admission",
                    "provenance": "not_established",
                    "reason_codes": ["admission_not_supplied_by_owned_profile_verifier"],
                },
                {
                    "predicate_id": "optional_import_closure_n9",
                    "provenance": "not_established",
                    "reason_codes": [],
                },
                {
                    "predicate_id": "protected_reuse",
                    "provenance": "not_established",
                    "reason_codes": [],
                },
            ],
        }
        self._sealed = self._witness_type.model_validate(
            {**payload, "content_hash": _v2_hash(payload)}
        )
        return self._sealed


def _n5_recorded_entry_membership(function: object) -> str | None:
    """Observe entry-code membership only through the existing retained recorder."""
    if type(function) is not types.FunctionType:
        return None
    from polisyos.runtime.quality.confidence_ledger import (
        _passive_capture_lookup,
        _retained_n5_host_capture,
    )

    try:
        retained = _retained_n5_host_capture()
        if retained is None:
            return None
        capture = retained[0].capture
        module_name = _passive_capture_lookup(function.__globals__, "__name__")
        if type(module_name) is not str:
            return None
        execution = capture.completed(module_name)
        capture.assert_retained(frozenset({module_name}))
        if (
            type(execution.module) is not types.ModuleType
            or execution.module is not sys.modules.get(module_name)
            or function.__globals__ is not vars(execution.module)
            or not capture._code_belongs_to(execution.code, function.__code__)
        ):
            return None
        return _v2_json(
            {
                "scope": "controlled_entry_code_only",
                "module": module_name,
                "relative_path": execution.relative_path,
                "source_hash": execution.source_sha256,
            }
        )
    except (OSError, TypeError, ValueError, RuntimeError, AttributeError, ImportError):
        return None


# V3 widens the supported domain without reinterpreting persisted /2 bytes.
_GRAPH_NORMALIZATION = "supported-native-callable-graph/3"


def _n5_typed_instance_dictionary(
    value: object, *, allowed_slots: frozenset[str], native_scalar_base: type | None = None
) -> dict[str, object] | None:
    """Establish all native instance storage across the actual MRO passively.

    A declared field set does not rule out additional slots or a dictionary
    hidden by an overriding attribute. Unsupported storage stays unknown.
    """
    kind = type(value)
    mro = type.__dict__["__mro__"].__get__(kind, type(kind))
    slots: dict[str, object] = {}
    dictionary = None
    for owner in mro:
        namespace = type.__dict__["__dict__"].__get__(owner, type(owner))
        for descriptor in namespace.values():
            if type(descriptor) is types.MemberDescriptorType:
                name = descriptor.__name__
                declared = namespace.get("__slots__", ())
                declared = (declared,) if type(declared) is str else declared
                if (
                    not any(descriptor.__objclass__ is owner for owner in mro)
                    or name not in allowed_slots
                    or (name in slots and slots[name] is not descriptor)
                    or type(declared) not in {tuple, list}
                    or any(type(item) is not str for item in declared)
                    or name not in declared
                ):
                    raise ValueError("n5_native_instance_storage_not_established")
                slots[name] = descriptor
            elif type(descriptor) is types.GetSetDescriptorType:
                # The canonical runtime-type descriptor is already represented
                # by the typed row. It is not additional per-instance storage.
                if descriptor is object.__dict__["__class__"]:
                    continue
                name = descriptor.__name__
                if not any(descriptor.__objclass__ is owner for owner in mro) or name not in {
                    "__dict__",
                    "__weakref__",
                }:
                    raise ValueError("n5_native_instance_storage_not_established")
                if name == "__dict__":
                    actual = descriptor.__get__(value, kind)
                    if type(actual) is not dict or (
                        dictionary is not None and actual is not dictionary
                    ):
                        raise ValueError("n5_native_instance_storage_not_established")
                    dictionary = actual
    _require_accounted_n5_instance_layout(
        kind, mro=mro, slots=tuple(slots.values()), native_scalar_base=native_scalar_base
    )
    return dictionary


def _require_accounted_n5_instance_layout(
    kind: type,
    *,
    mro: tuple[type, ...],
    slots: tuple[object, ...],
    native_scalar_base: type | None,
) -> None:
    """Refuse unaccounted inline payload in the supported CPython typed domain.

    Declared Python object slots and dictionary/weakref pointer storage are
    accounted separately. An empty dictionary does not establish the state of
    an opaque native ancestor. External side tables, globals and mutation
    during a call remain outside this candidate observation.
    """
    if (
        sys.implementation.name != "cpython"
        or sys.version_info[:2] != (3, 14)
        or (native_scalar_base is not None and native_scalar_base is not str)
    ):
        raise ValueError("n5_instance_storage_profile_not_established")
    pointer_size = struct.calcsize("P")

    def native_type_field(owner: type, name: str) -> int:
        descriptor = type.__dict__[name]
        result = descriptor.__get__(owner, type(owner))
        if type(result) is not int:
            raise ValueError("n5_instance_storage_profile_not_established")
        return result

    header_size = native_type_field(object, "__basicsize__")
    for owner in mro:
        owner_mro = type.__dict__["__mro__"].__get__(owner, type(owner))
        base_size = (
            native_type_field(str, "__basicsize__")
            if native_scalar_base is str and any(base is str for base in owner_mro)
            else header_size
        )
        actual_size = native_type_field(owner, "__basicsize__")
        if native_type_field(owner, "__itemsize__") != 0:
            raise ValueError("n5_instance_native_payload_not_established")
        actual_slots = {
            id(descriptor)
            for descriptor in slots
            if any(descriptor.__objclass__ is base for base in owner_mro)
        }
        pointer_fields = set()
        for base in owner_mro:
            flags = native_type_field(base, "__flags__")
            for role, attribute, managed_flag, managed_offset in (
                ("dict", "__dictoffset__", 1 << 4, -1),
                ("weakref", "__weakrefoffset__", 1 << 3, -4 * pointer_size),
            ):
                offset = native_type_field(base, attribute)
                if offset < 0 and (offset != managed_offset or not flags & managed_flag):
                    raise ValueError("n5_instance_storage_profile_not_established")
                if offset > 0:
                    if offset < header_size or offset + pointer_size > actual_size:
                        raise ValueError("n5_instance_storage_profile_not_established")
                    pointer_fields.add((role, offset))
        expected_size = base_size + pointer_size * (len(actual_slots) + len(pointer_fields))
        if actual_size != expected_size:
            raise ValueError("n5_instance_native_payload_not_established")


class _N5ContentGraph:
    """Encode one bounded native graph; no opaque object protocols are consulted."""

    def __init__(self) -> None:
        self._positions: dict[int, int] = {}
        self._retained: list[object] = []
        self._rows: list[dict[str, object]] = []
        self._namespaces: list[dict[str, object]] = []
        self._budget = [10000, 1024**2]

    def wire(self, value: object) -> str:
        root = self._encode(value, 0)
        return _v2_json({"root": root, "nodes": self._rows})

    def _encode(self, value: object, depth: int, *, bound_receiver: bool = False) -> object:
        if depth > 40 or self._budget[0] <= 0:
            raise ValueError("n5_native_content_not_established")
        kind = type(value)
        if value is Ellipsis:
            self._budget[0] -= 1
            return {"singleton": "ellipsis"}
        if value is None or any(
            kind is supported
            for supported in (
                bool,
                int,
                str,
                float,
                complex,
                bytes,
                Decimal,
                date,
                datetime,
                datetime_time,
            )
        ):
            return _strict_n5_native_content(value, seen=set(), budget=self._budget, depth=depth)
        previous = self._positions.get(id(value))
        if previous is not None:
            self._budget[0] -= 1
            return {"ref": previous}
        self._budget[0] -= 1
        position = len(self._rows)
        self._positions[id(value)] = position
        self._retained.append(value)
        row: dict[str, object] = {}
        self._rows.append(row)

        def encode(item: object) -> object:
            return self._encode(item, depth + 1)

        if kind is types.FunctionType:
            from polisyos.runtime.quality.confidence_ledger import _normalize_code_object

            module, qualname = value.__module__, value.__qualname__
            if (module is not None and type(module) is not str) or type(qualname) is not str:
                raise ValueError("n5_callable_state_not_established")
            self._namespaces.append(value.__globals__)
            closure = []
            for cell in value.__closure__ or ():
                try:
                    item = cell.cell_contents
                except ValueError as exc:
                    raise ValueError("n5_callable_state_not_established") from exc
                closure.append(encode(item))
            row.update(
                kind="function",
                declared_module=module,
                qualname=qualname,
                code=_normalize_code_object(
                    value.__code__, work_budget=self._budget, work_depth=depth, strict=True
                ),
                defaults=encode(value.__defaults__),
                kwdefaults=encode(value.__kwdefaults__),
                closure=closure,
            )
        elif kind is types.MethodType:
            row.update(
                kind="bound_method",
                function=encode(value.__func__),
                receiver=self._encode(value.__self__, depth + 1, bound_receiver=True),
            )
        elif kind is dict:
            if len(value) > self._budget[0]:
                raise ValueError("n5_native_content_not_established")
            row.update(kind="mapping", items=[[encode(k), encode(v)] for k, v in value.items()])
        elif kind is tuple or kind is list:
            if len(value) > self._budget[0]:
                raise ValueError("n5_native_content_not_established")
            row.update(kind=kind.__name__, items=[encode(item) for item in value])
        elif kind is set or kind is frozenset:
            if len(value) > self._budget[0]:
                raise ValueError("n5_native_content_not_established")
            # Unordered traversal must not choose graph positions. Independent
            # native keys order the elements; ambiguous equal keys are unknown.
            keyed = sorted(
                ((_N5ContentGraph().wire(item), item) for item in value), key=lambda pair: pair[0]
            )
            if len({key for key, _item in keyed}) != len(keyed):
                raise ValueError("n5_native_content_not_established")
            row.update(kind=kind.__name__, items=[encode(item) for _key, item in keyed])
        elif type(kind) is type(BaseModel) and issubclass(kind, BaseModel):
            self._model_row(value, row, encode)
        elif type(kind) is type(Enum) and issubclass(kind, Enum):
            scalar_base = str if any(base is str for base in kind.__mro__) else None
            values = _n5_typed_instance_dictionary(
                value, allowed_slots=frozenset(), native_scalar_base=scalar_base
            )
            if type(values) is not dict or "_value_" not in values or "_name_" not in values:
                raise ValueError("n5_native_content_not_established")
            if (
                any(type(name) is not str for name in values)
                or values.get("__objclass__", kind) is not kind
            ):
                raise ValueError("n5_native_content_not_established")
            row.update(
                kind="enum",
                type=_native_type_label(kind),
                fields={
                    name: encode(item)
                    for name, item in sorted(values.items())
                    if name != "__objclass__"
                },
            )
            if scalar_base is str:
                row["native_scalar_payload"] = encode(str.__str__(value))
        elif type(kind) is type and "__dataclass_fields__" in vars(kind):
            self._dataclass_row(value, row, encode)
        elif kind is types.ModuleType or issubclass(kind, type):
            binding = _n5_recorded_reference(value, self._namespaces)
            if binding is None:
                raise ValueError("n5_reference_binding_not_established")
            row.update(kind="recorded_binding", binding=binding)
        elif bound_receiver:
            self._plain_bound_receiver_row(value, row, encode)
        elif callable(value):
            binding = _n5_recorded_native_reference(value)
            if binding is None:
                raise ValueError("n5_reference_binding_not_established")
            row.update(kind="recorded_native_export", binding=binding)
        else:
            from polisyos.ir import read_canonical_immutable_container

            owned = read_canonical_immutable_container(value)
            if owned is None:
                raise ValueError("n5_native_content_not_established")
            container_kind, items = owned
            row.update(
                kind="canonical_immutable_container",
                owner_profile="polisyos.ir.canonical_immutable_container/1",
                container_kind=container_kind,
                items=[encode(item) for item in items]
                if container_kind == "list"
                else [[encode(key), encode(item)] for key, item in items],
            )
        return {"ref": position}

    def _plain_bound_receiver_row(
        self, value: object, row: dict[str, object], encode: Callable[[object], object]
    ) -> None:
        """Bind a recorded Python class and every supported plain instance field.

        This does not support arbitrary objects in closures. Hidden slots,
        custom attribute protocols and unsupported field values stay unknown.
        Class/global mutation completeness remains a declared candidate limit.
        """
        kind = type(value)
        if inspect.getattr_static(kind, "__getattribute__") is not object.__getattribute__:
            raise ValueError("n5_bound_receiver_not_established")
        values = _n5_typed_instance_dictionary(value, allowed_slots=frozenset())
        binding = _n5_recorded_reference(kind, self._namespaces)
        if type(values) is not dict or binding is None:
            raise ValueError("n5_bound_receiver_not_established")
        row.update(
            kind="plain_bound_receiver",
            receiver_profile="recorded-python-class/cpython-3.14-dictionary-layout/2",
            class_binding=binding,
            fields=encode(values),
            external_state_completeness="not_established",
        )

    @staticmethod
    def _model_row(
        value: BaseModel, row: dict[str, object], encode: Callable[[object], object]
    ) -> None:
        kind = type(value)
        if inspect.getattr_static(kind, "__getattribute__") is not object.__getattribute__:
            raise ValueError("n5_native_content_not_established")
        for slot in (
            "__dict__",
            "__pydantic_extra__",
            "__pydantic_private__",
            "__pydantic_fields_set__",
        ):
            if inspect.getattr_static(kind, slot) is not inspect.getattr_static(BaseModel, slot):
                raise ValueError("n5_native_content_not_established")
        values = _n5_typed_instance_dictionary(
            value,
            allowed_slots=frozenset(
                {"__pydantic_extra__", "__pydantic_private__", "__pydantic_fields_set__"}
            ),
        )
        # These canonical None values are actual constraints, not truthiness
        # tests: even an empty private/extra dictionary changes native state.
        if (
            object.__getattribute__(value, "__pydantic_private__") is not None
            or object.__getattribute__(value, "__pydantic_extra__") is not None
        ):
            raise ValueError("n5_native_content_not_established")
        if type(values) is not dict or any(type(name) is not str for name in values):
            raise ValueError("n5_native_content_not_established")
        names = exact_n5_model_field_names(value)
        missing = object()
        if any(inspect.getattr_static(kind, name, missing) is not missing for name in names):
            raise ValueError("n5_native_content_not_established")
        field_set = object.__getattribute__(value, "__pydantic_fields_set__")
        if type(field_set) is not set or any(type(name) is not str for name in field_set):
            raise ValueError("n5_native_content_not_established")
        row.update(
            kind="model",
            type=_native_type_label(kind),
            fields={name: encode(values[name]) for name in sorted(names)},
            fields_set=sorted(field_set),
        )

    @staticmethod
    def _dataclass_row(
        value: object, row: dict[str, object], encode: Callable[[object], object]
    ) -> None:
        kind = type(value)
        namespace = vars(kind)
        params = namespace.get("__dataclass_params__")
        if (
            type(params) is not dataclasses._DataclassParams
            or not params.frozen
            or inspect.getattr_static(kind, "__getattribute__") is not object.__getattribute__
        ):
            raise ValueError("n5_native_content_not_established")
        declared = namespace["__dataclass_fields__"]
        if type(declared) is not dict or any(
            type(field) is not dataclasses.Field for field in declared.values()
        ):
            raise ValueError("n5_native_content_not_established")
        names = tuple(field.name for field in fields(kind))
        for name in names:
            descriptor = inspect.getattr_static(kind, name, None)
            if (
                inspect.getattr_static(type(descriptor), "__get__", None) is not None
                and type(descriptor) is not types.MemberDescriptorType
            ):
                raise ValueError("n5_native_content_not_established")
        values = _n5_typed_instance_dictionary(value, allowed_slots=frozenset(names))
        if values is not None and (
            any(type(name) is not str for name in values) or not set(values).issubset(names)
        ):
            raise ValueError("n5_native_content_not_established")
        row.update(
            kind="dataclass",
            type=_native_type_label(kind),
            fields={name: encode(object.__getattribute__(value, name)) for name in names},
        )


def _n5_recorded_reference(
    value: object, namespaces: list[dict[str, object]]
) -> dict[str, object] | None:
    """Bind an actual class/module via the recorder, never by name equivalence."""
    from polisyos.runtime.quality.confidence_ledger import _candidate_n5_host_capture

    try:
        retained = _candidate_n5_host_capture()
        if retained is None:
            return None
        capture = retained[0]
        candidates: list[tuple[str, str]] = []
        for namespace in namespaces:
            module = namespace.get("__name__")
            if type(module) is str:
                candidates.extend(
                    (module, name)
                    for name, item in namespace.items()
                    if type(name) is str and item is value
                )
        if issubclass(type(value), type):
            namespace = type.__dict__["__dict__"].__get__(value, type(value))
            module, name = namespace.get("__module__"), namespace.get("__name__")
            if name is None:
                name = type.__dict__["__name__"].__get__(value, type(value))
            if type(module) is str and type(name) is str:
                candidates.append((module, name))
        for module, name in candidates:
            # A failed lookup may poison the retained recorder; only try names
            # actually present in its completed post-initializer export census.
            try:
                execution = capture.completed(module)
            except ImportError:
                continue
            watched = execution.watched_exports
            if (
                type(watched) not in {dict, types.MappingProxyType}
                or watched.get(name) is not value
            ):
                continue
            if capture.completed_binding(module, name) is not value:
                continue
            return {
                "module": module,
                "export": name,
                "relative_path": execution.relative_path,
                "source_hash": execution.source_sha256,
            }
    except (OSError, TypeError, ValueError, RuntimeError, AttributeError, KeyError, ImportError):
        return None
    return None


def _n5_recorded_native_reference(value: object) -> dict[str, object] | None:
    """Bind an observed native export through the canonical early recorder.

    The native file and locked wheel are observed bytes, not proof of mapped
    code, opaque native mutable state or a complete numerical readset.
    """
    from polisyos.runtime.quality.confidence_ledger import (
        _candidate_n5_host_capture,
        _code_tree_contains,
    )

    try:
        retained = _candidate_n5_host_capture()
        if retained is None:
            return None
        capture, session = retained
        binding = capture.completed_native_export_reference(value)
        member_reader = session.get("locked_native_member")
        host = sys.modules.get("_polisyos_early_host")
        # Reuse the canonical host callback boundary: a callable in a session
        # field is not a wheel reconciliation result or its source ownership.
        if (
            type(member_reader) is not types.FunctionType
            or type(host) is not types.ModuleType
            or member_reader.__globals__ is not vars(host)
            or member_reader.__code__.co_qualname != "_child_main.<locals>.locked_native_member"
            or not _code_tree_contains(session.get("host_code"), member_reader.__code__)
            or member_reader.__defaults__ is not None
            or member_reader.__kwdefaults__ is not None
        ):
            return None
        member = member_reader(binding.provider.module_name)
        if (
            type(member) is not tuple
            or len(member) != 5
            or any(type(item) is not str for item in member)
            or member[:3]
            != (
                binding.provider.module_name,
                binding.provider.relative_path,
                binding.provider.file_sha256,
            )
        ):
            return None
        return {
            "reference_profile": "recorded-initializer-native-export/1",
            "importer_module": binding.importer.module_name,
            "importer_export": binding.importer_export,
            "importer_relative_path": binding.importer.relative_path,
            "importer_source_sha256": binding.importer.source_sha256,
            "provider_module": member[0],
            "provider_export": binding.provider_export,
            "provider_relative_path": member[1],
            "provider_file_sha256": member[2],
            "provider_wheel_sha256": member[3],
            "lock_sha256": member[4],
            "native_state_completeness": "not_established",
            "mapped_image_identity": "not_established",
        }
    except (AttributeError, ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return None


class N5ExecutionContentWitnessV3(N5ExecutionContentWitness):
    """Versioned candidate native/callable graph content; never protected authority."""

    schema_version: Literal["N5ExecutionContentWitness@3.0"] = "N5ExecutionContentWitness@3.0"
    normalization_profile: Literal["supported-native-callable-graph/3"] = _GRAPH_NORMALIZATION


class N5ControlledCallCaptureV3(N5ControlledCallCapture):
    """Own actual calls and encode their supported pre-call graphs on every invocation."""

    _normalization_profile = _GRAPH_NORMALIZATION
    _schema_version = "N5ExecutionContentWitness@3.0"
    _witness_type = N5ExecutionContentWitnessV3

    @staticmethod
    def _native_wire(value: object) -> str:
        try:
            return _N5ContentGraph().wire(value)
        except (AttributeError, KeyError, ImportError) as exc:
            raise ValueError("n5_native_content_not_established") from exc

    @staticmethod
    def _callable_wire(function: object) -> str:
        if not callable(function):
            raise ValueError("n5_callable_state_not_established")
        if type(function) not in {types.FunctionType, types.MethodType}:
            binding = _n5_recorded_native_reference(function)
            if binding is None:
                raise ValueError("n5_callable_state_not_established")
            return _v2_json(
                {
                    "root": {"ref": 0},
                    "nodes": [{"kind": "recorded_native_export", "binding": binding}],
                }
            )
        return N5ControlledCallCaptureV3._native_wire(function)

    def _arguments_wire(
        self, function: object, args: tuple[object, ...], kwargs: dict[str, object]
    ) -> str:
        # Bind aliases across captured state and supplied arguments. Separately
        # encoded graphs cannot distinguish a captured object from an equal copy.
        return self._native_wire((function, args, kwargs))

    def seal(self) -> N5ExecutionContentWitnessV3:
        """Return the explicit v3 wire without changing v2 default capture semantics."""
        result = super().seal()
        if type(result) is not N5ExecutionContentWitnessV3:
            raise ValueError("n5_content_witness_version_mismatch")
        return result


def snapshot_n5_callable_content_v3(function: object) -> str | None:
    """Observe current supported callable content without invoking its computation.

    This is neither an executed-call proof nor completeness of the callable's
    readset. Unsupported content remains unknown, including opaque native state.
    """
    try:
        return N5ControlledCallCaptureV3._callable_wire(function)
    except (OSError, TypeError, ValueError, RuntimeError, AttributeError):
        return None


GENERIC_FOUNDRY_CALL_NORMALIZATION = "foundry-bound-call-content/3"


def snapshot_foundry_call_value(value: object, *, max_bytes: int = 65536) -> bytes:
    """Encode a bounded declared receiver or JAX argument without opaque fallbacks.

    This is a candidate observation of the value supplied to the real Foundry
    call. It is not proof that the caller executed it or that external state is
    complete. Large or unsupported values refuse rather than enter a log or a
    hash without their bytes.
    """
    import jax
    import numpy as np

    try:
        from jax._src.array import ArrayImpl
        from jax._src.layout import Format, Layout
        from jax._src.lib import xla_client
        from jax._src.sharding_impls import SingleDeviceSharding
    except (ImportError, AttributeError) as exc:
        raise ValueError("n5_foundry_array_provider_not_established") from exc
    if (
        ArrayImpl is not xla_client.ArrayImpl
        or SingleDeviceSharding is not xla_client.SingleDeviceSharding
    ):
        raise ValueError("n5_foundry_array_provider_not_established")
    if type(max_bytes) is not int or not 0 < max_bytes <= 65536:
        raise ValueError("n5_foundry_call_value_limit_invalid")
    remaining = [max_bytes]
    positions: dict[int, int] = {}

    def require_plain_jax_array(item: object) -> None:
        try:
            instance_values = object.__getattribute__(item, "__dict__")
        except AttributeError:
            return
        if type(instance_values) is not dict or instance_values:
            raise ValueError("n5_foundry_array_instance_state_not_established")

    def project(item: object, depth: int) -> object:
        if depth > 32:
            raise ValueError("n5_foundry_call_value_not_established")
        kind = type(item)
        if item is None or kind in (bool, int, float, str, bytes, Decimal):
            if (kind is float and not math.isfinite(item)) or (
                kind is Decimal and not item.is_finite()
            ):
                raise ValueError("n5_foundry_call_nonfinite_value")
            encoded = exact_n5_content_bytes(item)
            remaining[0] -= len(encoded)
            if remaining[0] < 0:
                raise ValueError("n5_foundry_call_value_limit_exceeded")
            return {"native": encoded.hex()}
        if issubclass(kind, jax.Array) and kind is not ArrayImpl:
            # Do not read a custom subtype's size, dtype, or conversion hooks.
            raise ValueError("n5_foundry_array_type_not_established")
        if issubclass(kind, Enum):
            if (
                type(kind) is not type(Enum)
                or inspect.getattr_static(kind, "__getattribute__") is not object.__getattribute__
                or inspect.getattr_static(kind, "value")
                is not inspect.getattr_static(Enum, "value")
            ):
                raise ValueError("n5_foundry_enum_protocol_not_established")
            scalar_base = str if any(base is str for base in kind.__mro__) else None
            try:
                values = _n5_typed_instance_dictionary(
                    item, allowed_slots=frozenset(), native_scalar_base=scalar_base
                )
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError("n5_foundry_enum_state_not_established") from exc
            if (
                type(values) is not dict
                or not {"_name_", "_value_", "__objclass__"}.issubset(values)
                or set(values) - {"_name_", "_value_", "_sort_order_", "__objclass__"}
                or values["__objclass__"] is not kind
                or type(values["_name_"]) is not str
                or ("_sort_order_" in values and type(values["_sort_order_"]) is not int)
            ):
                raise ValueError("n5_foundry_enum_state_not_established")
            position = positions.get(id(item))
            if position is not None:
                return {"ref": position}
            positions[id(item)] = len(positions)
            result = {
                "enum": {
                    "id": positions[id(item)],
                    "type": _native_type_label(kind),
                    "fields": {
                        name: project(value, depth + 1)
                        for name, value in sorted(values.items())
                        if name != "__objclass__"
                    },
                }
            }
            if scalar_base is str:
                result["enum"]["native_scalar_payload"] = project(str.__str__(item), depth + 1)
            return result
        if kind is ArrayImpl or kind is np.ndarray:
            if kind is np.ndarray:
                if item.flags.writeable:
                    raise ValueError("n5_foundry_call_mutable_array_not_established")
                if (
                    not item.flags.owndata
                    or not item.flags.c_contiguous
                    or not item.flags.aligned
                    or item.flags.writebackifcopy
                    or item.base is not None
                    or item.dtype.metadata is not None
                ):
                    raise ValueError("n5_foundry_call_array_layout_not_established")
                array_profile: dict[str, object] = {
                    "provider": "numpy_ndarray",
                    "strides": list(item.strides),
                    "fortran_contiguous": bool(item.flags.f_contiguous),
                }
            else:
                require_plain_jax_array(item)
                sharding = item.sharding
                if type(sharding) is not SingleDeviceSharding:
                    raise ValueError("n5_foundry_call_array_placement_not_established")
                devices = sharding.device_set
                if type(devices) is not set or len(devices) != 1:
                    raise ValueError("n5_foundry_call_array_placement_not_established")
                device = next(iter(devices))
                if not any(device is known for known in jax.devices()):
                    raise ValueError("n5_foundry_call_array_placement_not_established")
                device_fields = {
                    "platform": device.platform,
                    "device_kind": device.device_kind,
                    "device_id": device.id,
                    "process_index": device.process_index,
                    "memory_kind": sharding.memory_kind,
                }
                if (
                    type(device_fields["platform"]) is not str
                    or type(device_fields["device_kind"]) is not str
                    or type(device_fields["device_id"]) is not int
                    or type(device_fields["process_index"]) is not int
                    or type(device_fields["memory_kind"]) not in (str, type(None))
                    or type(item.weak_type) is not bool
                    or type(item.committed) is not bool
                ):
                    raise ValueError("n5_foundry_call_array_placement_not_established")
                array_format = item.format
                if type(array_format) is not Format or array_format.sharding is not sharding:
                    raise ValueError("n5_foundry_call_array_layout_not_established")
                layout = array_format.layout
                if (
                    type(layout) is not Layout
                    or type(layout.major_to_minor) is not tuple
                    or any(type(value) is not int for value in layout.major_to_minor)
                    or (
                        layout.tiling is not None
                        and (
                            type(layout.tiling) is not tuple
                            or any(
                                type(tile) is not tuple
                                or any(type(value) is not int for value in tile)
                                for tile in layout.tiling
                            )
                        )
                    )
                    or type(layout._sub_byte_element_size_in_bits) is not int
                ):
                    raise ValueError("n5_foundry_call_array_layout_not_established")
                array_profile = {
                    "provider": "jax_array_impl",
                    "weak_type": item.weak_type,
                    "committed": item.committed,
                    "placement": device_fields,
                    "layout": {
                        "major_to_minor": list(layout.major_to_minor),
                        "tiling": (
                            None
                            if layout.tiling is None
                            else [list(tile) for tile in layout.tiling]
                        ),
                        "sub_byte_element_size_in_bits": layout._sub_byte_element_size_in_bits,
                    },
                }
            if int(item.size) * int(item.dtype.itemsize) > remaining[0]:
                raise ValueError("n5_foundry_call_value_limit_exceeded")
            try:
                array = np.asarray(item)
                if (
                    array.dtype.hasobject
                    or array.dtype.kind not in "biufc"
                    or array.dtype.metadata is not None
                ):
                    raise ValueError("n5_foundry_call_array_dtype_unsupported")
                if array.dtype.kind in "fc" and not np.all(np.isfinite(array)):
                    raise ValueError("n5_foundry_call_nonfinite_value")
                raw = array.tobytes(order="C")
                if kind is ArrayImpl:
                    require_plain_jax_array(item)
            except (TypeError, ValueError, RuntimeError) as exc:
                raise ValueError("n5_foundry_call_array_not_established") from exc
            remaining[0] -= len(raw)
            if remaining[0] < 0:
                raise ValueError("n5_foundry_call_value_limit_exceeded")
            position = positions.get(id(item))
            if position is not None:
                return {"ref": position}
            positions[id(item)] = len(positions)
            return {
                "array": {
                    "id": positions[id(item)],
                    **array_profile,
                    "dtype": array.dtype.str,
                    "shape": list(array.shape),
                    "bytes": raw.hex(),
                }
            }
        declared_map = inspect.getattr_static(kind, "__dataclass_fields__", None)
        if declared_map is not None:
            import equinox as eqx

            position = positions.get(id(item))
            if position is not None:
                return {"ref": position}
            params = inspect.getattr_static(kind, "__dataclass_params__", None)
            if (
                type(params) is not dataclasses._DataclassParams
                or type(declared_map) is not dict
                or any(
                    type(name) is not str
                    or type(field) is not dataclasses.Field
                    or field.name != name
                    or field._field_type
                    not in (
                        dataclasses._FIELD,
                        dataclasses._FIELD_CLASSVAR,
                        dataclasses._FIELD_INITVAR,
                    )
                    for name, field in declared_map.items()
                )
            ):
                raise ValueError("n5_foundry_receiver_fields_not_established")
            # Values are recaptured after the real call; no claim of Python
            # immutability or absence of transient mutation is made. Unknown
            # field-access protocols cannot be reduced to stored values.
            expected_getattribute = (
                inspect.getattr_static(eqx.Module, "__getattribute__")
                if issubclass(kind, eqx.Module)
                else object.__getattribute__
            )
            if inspect.getattr_static(kind, "__getattribute__") is not expected_getattribute:
                raise ValueError("n5_foundry_receiver_access_not_established")
            declared = tuple(
                field for field in declared_map.values() if field._field_type is dataclasses._FIELD
            )
            names = tuple(field.name for field in declared)
            actual = _n5_typed_instance_dictionary(item, allowed_slots=frozenset())
            if type(actual) is not dict or not set(actual).issubset(names):
                raise ValueError("n5_foundry_receiver_fields_not_established")
            positions[id(item)] = len(positions)
            selected: dict[str, object] = {}
            missing = object()
            for descriptor in declared:
                name = descriptor.name
                class_value = inspect.getattr_static(kind, name, missing)
                if (
                    class_value is not missing
                    and inspect.getattr_static(type(class_value), "__get__", None) is not None
                ):
                    raise ValueError("n5_foundry_receiver_descriptor_not_established")
                if type(descriptor.metadata) is not types.MappingProxyType:
                    raise ValueError("n5_foundry_receiver_metadata_not_established")
                metadata_refs = gc.get_referents(descriptor.metadata)
                if len(metadata_refs) != 1 or type(metadata_refs[0]) is not dict:
                    raise ValueError("n5_foundry_receiver_metadata_not_established")
                metadata_values = metadata_refs[0]
                if any(type(key) is not str for key in metadata_values):
                    raise ValueError("n5_foundry_receiver_metadata_not_established")
                metadata = {
                    key: project(value, depth + 1) for key, value in sorted(metadata_values.items())
                }
                if name in actual:
                    selected[name] = {
                        "metadata": metadata,
                        "storage": "instance",
                        "value": project(actual[name], depth + 1),
                    }
                    continue
                if class_value is missing:
                    raise ValueError("n5_foundry_receiver_default_not_established")
                selected[name] = {
                    "metadata": metadata,
                    "storage": "class_default",
                    "value": project(class_value, depth + 1),
                }
            return {
                "dataclass": {
                    "id": positions[id(item)],
                    "type": _native_type_label(kind),
                    "fields": selected,
                }
            }
        raise ValueError("n5_foundry_call_value_not_established")

    return exact_n5_content_bytes(
        {"normalization_profile": GENERIC_FOUNDRY_CALL_NORMALIZATION, "value": project(value, 0)}
    )


def snapshot_foundry_mechanism_call(selected_call: object) -> bytes:
    """Snapshot one real bound method's callable and complete supported receiver."""
    from equinox._module._module import wrapper_field_names
    from equinox._module._prebuilt import BoundMethod

    wrapper_content: str | None = None
    if type(selected_call) is types.MethodType:
        function = selected_call.__func__
        receiver = selected_call.__self__
    elif type(selected_call) is BoundMethod:
        # This is the actual Equinox provider's PyTree method wrapper. Its
        # __call__ invokes exactly these two retained fields. Metadata copied
        # from the function is checked, and unknown wrapper state is refused.
        supported_metadata = frozenset(
            {"__module__", "__name__", "__qualname__", "__doc__", "__annotations__"}
        )
        if type(wrapper_field_names) is not set or wrapper_field_names != supported_metadata:
            raise ValueError("n5_foundry_bound_call_provider_not_established")
        actual = object.__getattribute__(selected_call, "__dict__")
        if (
            type(actual) is not dict
            or not {"__func__", "__self__"}.issubset(actual)
            or (set(actual) - {"__func__", "__self__"} - supported_metadata)
        ):
            raise ValueError("n5_foundry_bound_call_not_established")
        function = actual["__func__"]
        receiver = actual["__self__"]
        if type(function) is not types.FunctionType or any(
            actual[name] is not getattr(function, name)
            for name in supported_metadata.intersection(actual)
        ):
            raise ValueError("n5_foundry_bound_call_not_established")
        wrapper_content = snapshot_n5_callable_content_v3(BoundMethod.__call__)
        if wrapper_content is None:
            raise ValueError("n5_foundry_bound_call_not_established")
    else:
        raise ValueError("n5_foundry_bound_call_not_established")
    if inspect.getattr_static(type(receiver), "emit_patches", None) is not function:
        raise ValueError("n5_foundry_bound_call_not_established")
    callable_content = snapshot_n5_callable_content_v3(function)
    if callable_content is None:
        raise ValueError("n5_foundry_callable_not_established")
    receiver_content = snapshot_foundry_call_value(receiver)
    return exact_n5_content_bytes(
        {
            "normalization_profile": GENERIC_FOUNDRY_CALL_NORMALIZATION,
            "callable": callable_content,
            "wrapper": wrapper_content,
            "receiver": receiver_content,
        }
    )


def _require_n5_json_wire_domain(value: object) -> None:
    """Admit only exact JSON values before any encoder protocol can run."""
    active: set[int] = set()
    pending = [(value, False)]
    while pending:
        item, leaving = pending.pop()
        if leaving:
            active.remove(id(item))
            continue
        kind = type(item)
        if item is None or kind is bool or kind is int or kind is str:
            continue
        if kind is float:
            if math.isfinite(item):
                continue
            raise ValueError("n5_content_witness_wire_required")
        if kind is not list and kind is not dict:
            raise ValueError("n5_content_witness_wire_required")
        if id(item) in active:
            raise ValueError("n5_content_witness_wire_required")
        active.add(id(item))
        pending.append((item, True))
        if kind is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise ValueError("n5_content_witness_wire_required")
                pending.append((child, False))
        else:
            pending.extend((child, False) for child in item)


def read_n5_execution_content_witness(
    value: object,
) -> N5ExecutionContentWitness | N5ExecutionContentWitnessV3:
    """Validate a V2 candidate record's content; grant no current reuse permission."""
    if type(value) in {N5ExecutionContentWitness, N5ExecutionContentWitnessV3}:
        value = json.loads(value.model_dump_json())
    if type(value) is not dict:
        raise ValueError("n5_content_witness_wire_required")
    _require_n5_json_wire_domain(value)
    try:
        # A mapping containing model_construct instances is not JSON wire.
        # Re-enter through inert JSON so nested models cannot bypass validation.
        wire = json.loads(_v2_json(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("n5_content_witness_wire_required") from exc
    if wire.get("schema_version") == "N5ExecutionContentWitness@3.0":
        return N5ExecutionContentWitnessV3.model_validate(wire)
    return N5ExecutionContentWitness.model_validate(wire)
