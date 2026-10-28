"""One immutable built-in invocation profile for the bounded Ex-Ante reader.

The profile is frozen while the built-in policy registry imports this module.
It is intentionally limited to the actual ExAnteSimulationEstimator NumPy
implementation. It is not a tracer for arbitrary methods or process behavior.
"""

from __future__ import annotations

import hashlib
import json
import marshal
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from types import CodeType, FunctionType, MethodType, ModuleType
from typing import Any

from polisyos.foundry.methods._internal.executable_identity import (
    _ExecutableIdentity,
    _signature_binding,
)
from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner
from polisyos.foundry.methods.base import MethodSignature
from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator

_EXANTE_FQN = "policy.evaluation.ex_ante_simulation@1.0.0"
_PROFILE_ID = "builtin.exante.numpy.v1"
_RUNNER_BINDING = ("polisyos.foundry.numpy_runner.execute", "1")
_STATE_READS = ("baseline", "scenario")
_PARAMETER_READS = ("poverty_line",)
_SUPPORTED_PARAMETER_ORIGINS = ("signature_default", "explicit_parameter")
_OUTPUT_SLOT = "result"
_OUTPUT_PATH = ("mean_change",)


def _function(value: Any) -> FunctionType | None:
    if isinstance(value, MethodType):
        value = value.__func__
    return value if isinstance(value, FunctionType) else None


def _function_sha256(value: Any) -> str | None:
    """Hash executable code and ABI-shaped defaults for one Python function."""
    function = _function(value)
    if function is None or function.__closure__ is not None:
        return None
    metadata = {
        "module": function.__module__,
        "qualname": function.__qualname__,
        "python": [sys.version_info.major, sys.version_info.minor],
        "defaults": repr(function.__defaults__),
        "kwdefaults": repr(sorted((function.__kwdefaults__ or {}).items())),
    }
    digest = hashlib.sha256()
    digest.update(json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode())
    digest.update(b"\x00")
    digest.update(marshal.dumps(_portable_code(function.__code__)))
    return digest.hexdigest()


def _portable_code(code: CodeType) -> CodeType:
    """Remove installation-path variance while retaining executable structure."""
    return code.replace(
        co_consts=tuple(
            _portable_code(value) if isinstance(value, CodeType) else value
            for value in code.co_consts
        ),
        co_filename="<trusted-profile>",
    )


def _selected_scalar_sha256(output: Any) -> str | None:
    """Bind the one supported method output path to its returned scalar."""
    if type(output) is not dict:
        return None
    result = output.get(_OUTPUT_SLOT)
    if type(result) is not dict:
        return None
    value = result.get(_OUTPUT_PATH[0])
    if type(value) not in {int, float}:
        return None
    try:
        payload = json.dumps(
            {"slot": _OUTPUT_SLOT, "path": list(_OUTPUT_PATH), "value": value},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class RestrictedExAnteNumpyProfile:
    """Trusted installed-code profile and live C60 identities for one call."""

    profile_id: str
    revision_sha256: str
    method_class: type[Any]
    signature: MethodSignature
    method_operation: FunctionType
    method_code_sha256: str
    method_identity: _ExecutableIdentity
    runner_class: type[Any]
    runner_operation: FunctionType
    runner_code_sha256: str
    runner_identity: _ExecutableIdentity
    numpy_module: ModuleType
    numpy_operations: tuple[tuple[str, Any], ...]
    state_reads: tuple[str, ...]
    parameter_reads: tuple[str, ...]
    output_slot: str
    output_path: tuple[str, ...]

    def method_matches(
        self,
        *,
        method_class: type[Any],
        signature: MethodSignature,
        operation: Any,
        postprocessor: Any,
    ) -> bool:
        """Require the exact registered class/callable/code/ABI and no postprocessor."""
        function = _function(operation)
        if (
            method_class is not self.method_class
            or signature.stable_digest() != self.signature.stable_digest()
            or function is not self.method_operation
            or postprocessor is not None
            or _function_sha256(function) != self.method_code_sha256
            or function.__globals__.get("np") is not self.numpy_module
            or any(
                getattr(self.numpy_module, name, None) is not expected
                for name, expected in self.numpy_operations
            )
        ):
            return False
        try:
            identity = _ExecutableIdentity(
                method_class,
                operation,
                _signature_binding(signature),
            )
        except (AttributeError, TypeError, ValueError):
            return False
        return identity == self.method_identity

    def runner_matches(self, *, runner: Any, captured_execute: Any) -> bool:
        """Require the exact selected NumPy runner and captured execute function."""
        if not isinstance(captured_execute, MethodType) or captured_execute.__self__ is not runner:
            return False
        function = _function(captured_execute)
        if (
            type(runner) is not self.runner_class
            or function is not self.runner_operation
            or _function_sha256(function) != self.runner_code_sha256
        ):
            return False
        identity = _ExecutableIdentity(type(runner), function, _RUNNER_BINDING)
        return identity == self.runner_identity

    def invocation_evidence(
        self,
        *,
        output: Any,
        state_reads: tuple[str, ...],
        parameter_reads: tuple[str, ...],
        parameter_origin: str,
        runner_verified: bool,
        backend_runtime_fingerprint: str | None,
    ) -> Any:
        """Build internal return evidence; the graph binds it to its real occurrence."""
        from polisyos.foundry.methods.backends.protocol import (
            RestrictedMethodInvocationEvidence,
        )

        output_sha256 = _selected_scalar_sha256(output)
        verified = (
            state_reads == self.state_reads
            and parameter_reads == self.parameter_reads
            and parameter_origin in _SUPPORTED_PARAMETER_ORIGINS
            and output_sha256 is not None
            and runner_verified
        )
        limitation = None if verified else "restricted_exante_call_predicate_not_established"
        return RestrictedMethodInvocationEvidence(
            status="verified" if verified else "unavailable",
            limitation=limitation,
            profile_id=self.profile_id,
            profile_revision_sha256=self.revision_sha256,
            method_fqn=self.signature.fqn,
            method_version=self.signature.version,
            method_abi_digest=self.signature.abi_digest(),
            method_callable_sha256=self.method_code_sha256,
            runner_callable_sha256=self.runner_code_sha256 if runner_verified else None,
            backend_runtime_fingerprint=backend_runtime_fingerprint,
            state_reads=state_reads,
            parameter_reads=parameter_reads,
            parameter_origin=parameter_origin,
            poverty_line_value=None,
            output_slot_id=self.output_slot,
            output_value_path=self.output_path,
            output_value_sha256=output_sha256,
        )


class _ReadSetMapping(Mapping[str, Any]):
    """Record ordered permitted reads and refuse iteration or any other key."""

    __slots__ = ("_allowed", "_reads", "_source")

    def __init__(
        self,
        source: Mapping[str, Any],
        *,
        allowed: tuple[str, ...],
    ) -> None:
        self._source = source
        self._allowed = frozenset(allowed)
        self._reads: list[str] = []

    def __getitem__(self, key: str) -> Any:
        if type(key) is not str or key not in self._allowed or key not in self._source:
            raise KeyError("restricted_exante_read_outside_builtin_profile")
        self._reads.append(key)
        return self._source[key]

    def __iter__(self):
        raise TypeError("restricted_exante_mapping_iteration_refused")

    def __len__(self) -> int:
        raise TypeError("restricted_exante_mapping_length_refused")

    @property
    def reads(self) -> tuple[str, ...]:
        return tuple(self._reads)


def _make_trusted_profile() -> RestrictedExAnteNumpyProfile:
    method_class = ExAnteSimulationEstimator
    signature = method_class.signature
    method_operation = method_class.pure_step
    runner_class = NumpyRunner
    runner_operation = runner_class.execute
    method_code = _function_sha256(method_operation)
    runner_code = _function_sha256(runner_operation)
    if method_code is None or runner_code is None:
        raise RuntimeError("restricted_exante_builtin_executable_identity_unavailable")
    if (
        signature.fqn != _EXANTE_FQN
        or tuple(sorted(slot.name for slot in signature.input_slots)) != _STATE_READS
        or tuple(parameter.name for parameter in signature.parameters) != _PARAMETER_READS
        or signature.parameters[0].default is not None
        or signature.backend.value != "numpy"
        or getattr(method_operation, "__closure__", None) is not None
    ):
        raise RuntimeError("restricted_exante_builtin_abi_or_literal_profile_mismatch")
    try:
        numpy_module = method_operation.__globals__["np"]
    except (AttributeError, KeyError) as exc:
        raise RuntimeError("restricted_exante_builtin_numpy_dependency_missing") from exc
    if not isinstance(numpy_module, ModuleType):
        raise RuntimeError("restricted_exante_builtin_numpy_dependency_unverified")
    numpy_operations = tuple(
        (name, getattr(numpy_module, name))
        for name in ("any", "asarray", "digitize", "mean", "median", "percentile", "sum")
    )
    method_identity = _ExecutableIdentity(
        method_class,
        method_operation,
        _signature_binding(signature),
    )
    runner_identity = _ExecutableIdentity(
        runner_class,
        runner_operation,
        _RUNNER_BINDING,
    )
    profile_payload = {
        "id": _PROFILE_ID,
        "method": signature.fqn,
        "abi": signature.abi_digest(),
        "method_code": method_code,
        "runner_code": runner_code,
        "state_reads": list(_STATE_READS),
        "parameter_reads": list(_PARAMETER_READS),
        "parameter_origins": list(_SUPPORTED_PARAMETER_ORIGINS),
        "poverty_line": None,
        "output_slot": _OUTPUT_SLOT,
        "output_path": list(_OUTPUT_PATH),
        "python": [sys.version_info.major, sys.version_info.minor],
        "numpy_version": str(getattr(numpy_module, "__version__", "unavailable")),
    }
    revision = hashlib.sha256(
        json.dumps(profile_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return RestrictedExAnteNumpyProfile(
        profile_id=_PROFILE_ID,
        revision_sha256=revision,
        method_class=method_class,
        signature=signature,
        method_operation=method_operation,
        method_code_sha256=method_code,
        method_identity=method_identity,
        runner_class=runner_class,
        runner_operation=runner_operation,
        runner_code_sha256=runner_code,
        runner_identity=runner_identity,
        numpy_module=numpy_module,
        numpy_operations=numpy_operations,
        state_reads=_STATE_READS,
        parameter_reads=_PARAMETER_READS,
        output_slot=_OUTPUT_SLOT,
        output_path=_OUTPUT_PATH,
    )


# This module is imported by policy._registry_boot after evaluation.py is loaded.
# The references are frozen before run-time execution or test monkeypatches.
TRUSTED_EXANTE_NUMPY_PROFILE = _make_trusted_profile()


def profile_for_method_fqn(method_fqn: str) -> RestrictedExAnteNumpyProfile | None:
    """Resolve only the installed registered built-in profile, never a caller profile."""
    return TRUSTED_EXANTE_NUMPY_PROFILE if method_fqn == _EXANTE_FQN else None


def run_restricted_exante_if_selected(
    *,
    runner: Any,
    captured_runner_execute: Any,
    method_class: type[Any],
    signature: MethodSignature,
    pure_step: Any,
    postprocessor: Any,
    state: Mapping[str, Any],
    resolved_params: Mapping[str, Any],
    original_params: Mapping[str, Any],
) -> tuple[bool, Any, Any | None]:
    """Invoke a selected built-in with bounded read maps or preserve ordinary behavior.

    The returned bool means this built-in profile was selected by FQN. A
    mismatching class/callable still invokes the exact local callable captured by
    NumpyRunner, but the evidence is unavailable, so no consumer may promote it.
    """
    profile = profile_for_method_fqn(signature.fqn)
    if profile is None:
        return False, None, None
    if (
        type(state) is dict
        and type(resolved_params) is dict
        and type(original_params) is dict
        and profile.method_matches(
            method_class=method_class,
            signature=signature,
            operation=pure_step,
            postprocessor=postprocessor,
        )
        and profile.runner_matches(runner=runner, captured_execute=captured_runner_execute)
    ):
        state_view = _ReadSetMapping(state, allowed=profile.state_reads)
        params_view = _ReadSetMapping(resolved_params, allowed=profile.parameter_reads)
        if "poverty_line" not in original_params:
            origin = (
                "signature_default"
                if resolved_params.get("poverty_line") is None
                else "not_established"
            )
        else:
            origin = (
                "explicit_parameter"
                if resolved_params.get("poverty_line") is None
                else "not_established"
            )
        output = pure_step(state_view, params_view)
        evidence = profile.invocation_evidence(
            output=output,
            state_reads=state_view.reads,
            parameter_reads=params_view.reads,
            parameter_origin=origin,
            runner_verified=True,
            backend_runtime_fingerprint=None,
        )
        return True, output, evidence

    output = pure_step(state, resolved_params)
    from polisyos.foundry.methods.backends.protocol import (
        RestrictedMethodInvocationEvidence,
    )

    evidence = RestrictedMethodInvocationEvidence(
        status="unavailable",
        limitation="restricted_exante_method_or_runner_identity_mismatch",
        profile_id=profile.profile_id,
        profile_revision_sha256=profile.revision_sha256,
        method_fqn=signature.fqn,
        method_version=signature.version,
        method_abi_digest=signature.abi_digest(),
        method_callable_sha256=_function_sha256(pure_step),
        runner_callable_sha256=None,
        backend_runtime_fingerprint=None,
        state_reads=(),
        parameter_reads=(),
        parameter_origin="not_established",
        poverty_line_value=None,
        output_slot_id=profile.output_slot,
        output_value_path=profile.output_path,
        output_value_sha256=_selected_scalar_sha256(output),
    )
    return True, output, evidence


def bind_dispatch_runner_identity(
    *,
    method_fqn: str,
    runner: Any,
    captured_execute: Any,
    evidence: Any | None,
) -> Any | None:
    """Clear positive evidence unless the actual dispatcher-selected runner matches."""
    profile = profile_for_method_fqn(method_fqn)
    if profile is None:
        return evidence
    from polisyos.foundry.methods.backends.protocol import (
        RestrictedMethodInvocationEvidence,
    )

    if type(evidence) is not RestrictedMethodInvocationEvidence or not profile.runner_matches(
        runner=runner,
        captured_execute=captured_execute,
    ):
        from dataclasses import replace

        if type(evidence) is not RestrictedMethodInvocationEvidence:
            return RestrictedMethodInvocationEvidence(
                status="unavailable",
                limitation="registered_exante_runner_invocation_not_witnessed",
                profile_id=profile.profile_id,
                profile_revision_sha256=profile.revision_sha256,
                method_fqn=profile.signature.fqn,
                method_version=profile.signature.version,
                method_abi_digest=profile.signature.abi_digest(),
                method_callable_sha256=None,
                runner_callable_sha256=None,
                backend_runtime_fingerprint=None,
                state_reads=(),
                parameter_reads=(),
                parameter_origin="not_established",
                poverty_line_value=None,
                output_slot_id=profile.output_slot,
                output_value_path=profile.output_path,
                output_value_sha256=None,
            )
        return replace(
            evidence,
            status="unavailable",
            limitation="restricted_exante_dispatch_runner_identity_mismatch",
            runner_callable_sha256=None,
        )
    return evidence


def bind_occurrence_call_witness(
    *,
    evidence: Any | None,
    occurrence: Any,
    input_capture_ref: Any | None,
    input_capture_status: str,
) -> Any:
    """Bind dispatch evidence to the graph's existing planned occurrence."""
    from dataclasses import asdict

    from polisyos.core.contracts.foundry import RestrictedMethodCallWitness
    from polisyos.foundry.methods.backends.protocol import (
        RestrictedMethodInvocationEvidence,
    )

    profile = profile_for_method_fqn(getattr(occurrence, "method_fqn", ""))
    if profile is None:
        raise ValueError("restricted_call_witness_profile_not_registered")
    witness_data: dict[str, Any] = {
        "status": "unavailable",
        "limitation": "restricted_exante_invocation_evidence_missing",
        "profile_id": profile.profile_id,
        "profile_revision_sha256": profile.revision_sha256,
        "method_fqn": occurrence.method_fqn,
        "method_version": occurrence.method_version,
        "method_abi_digest": occurrence.method_abi_digest,
        "method_callable_sha256": None,
        "runner_callable_sha256": None,
        "backend_runtime_fingerprint": None,
        "state_reads": (),
        "parameter_reads": (),
        "parameter_origin": "not_established",
        "poverty_line_value": None,
        "output_slot_id": profile.output_slot,
        "output_value_path": profile.output_path,
        "output_value_sha256": None,
    }
    if type(evidence) is RestrictedMethodInvocationEvidence:
        witness_data.update(asdict(evidence))
        evidence_identity_matches = (
            evidence.profile_id == profile.profile_id
            and evidence.profile_revision_sha256 == profile.revision_sha256
            and evidence.method_fqn == profile.signature.fqn
            and evidence.method_version == profile.signature.version
            and evidence.method_abi_digest == profile.signature.abi_digest()
            and evidence.method_callable_sha256 == profile.method_code_sha256
            and evidence.runner_callable_sha256 == profile.runner_code_sha256
            and evidence.backend_runtime_fingerprint is not None
            and evidence.state_reads == profile.state_reads
            and evidence.parameter_reads == profile.parameter_reads
            and evidence.parameter_origin in _SUPPORTED_PARAMETER_ORIGINS
            and evidence.poverty_line_value is None
            and evidence.output_slot_id == profile.output_slot
            and evidence.output_value_path == profile.output_path
            and evidence.output_value_sha256 is not None
        )
        if evidence.status == "verified" and evidence_identity_matches:
            witness_data["limitation"] = None
        else:
            witness_data["status"] = "unavailable"
            witness_data["limitation"] = (
                evidence.limitation or "restricted_exante_invocation_identity_mismatch"
            )
    occurrence_identity_matches = (
        occurrence.method_fqn == profile.signature.fqn
        and occurrence.method_version == profile.signature.version
        and occurrence.method_abi_digest == profile.signature.abi_digest()
    )
    if not occurrence_identity_matches:
        witness_data["status"] = "unavailable"
        witness_data["limitation"] = "restricted_exante_occurrence_identity_mismatch"
    if input_capture_status != "captured" or input_capture_ref is None:
        if witness_data["status"] == "verified":
            witness_data["status"] = "unavailable"
            witness_data["limitation"] = "method_metric_input_capture_not_selected"
    return RestrictedMethodCallWitness.model_validate(
        {
            **witness_data,
            "occurrence_id": occurrence.occurrence_id,
            "invocation_id": occurrence.invocation_id,
            "node_id": occurrence.node_id,
            "method_fqn": occurrence.method_fqn,
            "method_version": occurrence.method_version,
            "method_abi_digest": occurrence.method_abi_digest,
            "input_capture_ref": input_capture_ref if input_capture_status == "captured" else None,
        }
    )


def current_restricted_backend_fingerprint(*, seed: int) -> str:
    """Recompute the selected NumPy runner's observed posture, not authority."""
    from polisyos.foundry.methods.backends.runtime_fingerprint import (
        capture_backend_runtime_fingerprint,
        capture_versions,
        runtime_stack_for,
    )
    from polisyos.foundry.methods.base import ComputeBackend

    method_class = TRUSTED_EXANTE_NUMPY_PROFILE.method_class
    versions = capture_versions(
        base_packages=("numpy", "scipy", "statsmodels", "pandas"),
        runtime_stack=runtime_stack_for(method_class),
    )
    return capture_backend_runtime_fingerprint(
        ComputeBackend.NUMPY, method_class=method_class, seed=seed, extra_versions=versions
    ).compute_hash()


def verify_persisted_restricted_call_witness(
    witness: Any,
    *,
    occurrence: Any,
    expected_input_capture_ref: Any,
    selected_output_slot_id: str,
    selected_output_value_path: tuple[str, ...],
    selected_output_value: int | float,
    expected_parameter_origin: str | None = None,
    expected_backend_runtime_fingerprint: str | None = None,
) -> bool:
    """Recompute stored witness claims against the immutable built-in profile."""
    from polisyos.core.artifacts.manifest import artifact_ref_identity_key
    from polisyos.core.contracts.foundry import RestrictedMethodCallWitness

    profile = profile_for_method_fqn(getattr(witness, "method_fqn", ""))
    if profile is None or type(witness) is not RestrictedMethodCallWitness:
        return False
    return (
        witness.status == "verified"
        and witness.profile_id == profile.profile_id
        and witness.profile_revision_sha256 == profile.revision_sha256
        and witness.method_fqn == profile.signature.fqn
        and witness.method_version == profile.signature.version
        and witness.method_abi_digest == profile.signature.abi_digest()
        and witness.method_callable_sha256 == profile.method_code_sha256
        and witness.runner_callable_sha256 == profile.runner_code_sha256
        and witness.backend_runtime_fingerprint is not None
        and (
            expected_backend_runtime_fingerprint is None
            or witness.backend_runtime_fingerprint == expected_backend_runtime_fingerprint
        )
        and witness.state_reads == profile.state_reads
        and witness.parameter_reads == profile.parameter_reads
        and witness.parameter_origin in _SUPPORTED_PARAMETER_ORIGINS
        and (
            expected_parameter_origin is None
            or witness.parameter_origin == expected_parameter_origin
        )
        and witness.poverty_line_value is None
        and witness.output_slot_id == profile.output_slot
        and witness.output_value_path == profile.output_path
        and selected_output_slot_id == profile.output_slot
        and selected_output_value_path == profile.output_path
        and expected_input_capture_ref is not None
        and witness.input_capture_ref is not None
        and expected_input_capture_ref.manifest_profile_sha256 is not None
        and artifact_ref_identity_key(witness.input_capture_ref)
        == artifact_ref_identity_key(expected_input_capture_ref)
        and type(selected_output_value) in {int, float}
        and witness.occurrence_id == occurrence.occurrence_id
        and witness.invocation_id == occurrence.invocation_id
        and witness.node_id == occurrence.node_id
        and witness.output_value_sha256
        == _selected_scalar_sha256({"result": {"mean_change": selected_output_value}})
    )


__all__ = [
    "TRUSTED_EXANTE_NUMPY_PROFILE",
    "RestrictedExAnteNumpyProfile",
    "bind_occurrence_call_witness",
    "bind_dispatch_runner_identity",
    "profile_for_method_fqn",
    "run_restricted_exante_if_selected",
    "verify_persisted_restricted_call_witness",
]
