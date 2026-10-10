"""Local typed bridge for a server-selected EconML worker candidate profile.

The MethodJob harness uses this bridge to persist a candidate result through
the existing CAS runner. This module is not imported by product code and does
not promote its output to causal or policy authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform as host_platform
import signal
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from polisyos.core import artifacts, canon
from polisyos.foundry.methods.catalog.causal._common import build_success_report
from polisyos.foundry.methods.catalog.causal._econml_adapter import build_cate_quantile_subgroups
from polisyos.foundry.methods.catalog.causal.dml import DoubleMachineLearning
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod
from polisyos.ir.analytics.hte import HTEResult

sys.path.insert(0, str(Path(__file__).resolve().parent))
from protocol import (
    CONFIGURATION,
    EXPECTED_MACHINE,
    EXPECTED_MACOS_VERSION,
    EXPECTED_PYTHON_VERSION,
    EXPECTED_SYS_PLATFORM,
    METHOD_FQN,
    OPERATION,
    PROFILE_ID,
    REQUEST_SCHEMA,
    RESPONSE_SCHEMA,
    canonical_bytes,
    digest,
    validate_request,
    validate_response_shape,
)

_TIMEOUT_S = 60.0
_MAX_BYTES = 8 * 1024 * 1024


class ManifestView(Protocol):
    """Minimal read-only manifest view returned by the selected CAS store."""

    kind: str
    media_type: str


class ArtifactStoreReader(Protocol):
    """Read-only methods required from the server-owned artifact store."""

    def get_bytes(self, ref: artifacts.ArtifactRef) -> bytes: ...

    def get_manifest(self, ref: artifacts.ArtifactRef) -> ManifestView: ...


class WorkerProtocolError(ValueError):
    """A worker response or selected execution profile failed typed validation."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ServerSelectedProfile:
    """Immutable profile selection supplied by server configuration, never a request."""

    profile_id: str
    python_executable: Path
    worker_directory: Path
    expected_lock_sha256: str
    expected_code_sha256: str
    expected_bridge_sha256: str
    timeout_seconds: float = _TIMEOUT_S

    def __post_init__(self) -> None:
        if self.profile_id != PROFILE_ID:
            raise ValueError("unsupported server-selected profile")
        _require_selected_host()
        if not self.python_executable.is_absolute() or not self.python_executable.is_file():
            raise ValueError("server-selected absolute worker interpreter is required")
        if not self.worker_directory.is_absolute() or not self.worker_directory.is_dir():
            raise ValueError("server-selected absolute worker directory is required")
        if (
            not _digest_string(self.expected_lock_sha256)
            or not _digest_string(self.expected_code_sha256)
            or not _digest_string(self.expected_bridge_sha256)
        ):
            raise ValueError("server profile lock/code digests are malformed")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("server profile timeout must be positive and finite")


class CandidateHTEOutput(BaseModel):
    """Typed candidate output reconstructed by the parent after response validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method_fqn: Literal["causal.hte.double_ml_worker_prototype@0.2.0"]
    profile_id: Literal["econml-0.16.0-py312-macos-arm64-v4-prototype"]
    job_id: str
    source_ref: artifacts.ArtifactRef
    source_content_sha256: str
    request_id: str
    request_sha256: str
    data_sha256: str
    row_order_sha256: str
    seed: int
    worker_lock_sha256: str
    worker_code_sha256: str
    bridge_code_sha256: str
    worker_result_sha256: str
    server_environment: dict[str, str]
    worker_environment: dict[str, Any]
    worker_result: dict[str, Any]
    authority: Literal["candidate_computation_only"]
    report: CausalEffectReport
    hte_result: HTEResult


def _digest_string(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise WorkerProtocolError("duplicate_response_field")
        decoded[key] = value
    return decoded


def _profile_assets(profile: ServerSelectedProfile) -> tuple[bytes, bytes, bytes]:
    worker_path = profile.worker_directory / "worker.py"
    protocol_path = profile.worker_directory / "protocol.py"
    lock_path = profile.worker_directory / "uv.lock"
    bridge_path = Path(__file__).resolve()
    if not all(path.is_file() for path in (worker_path, protocol_path, lock_path, bridge_path)):
        raise WorkerProtocolError("selected_profile_assets_missing")
    worker_bytes, protocol_bytes, lock_bytes = (
        worker_path.read_bytes(),
        protocol_path.read_bytes(),
        lock_path.read_bytes(),
    )
    code_sha = hashlib.sha256(worker_bytes + protocol_bytes).hexdigest()
    lock_sha = hashlib.sha256(lock_bytes).hexdigest()
    bridge_sha = hashlib.sha256(bridge_path.read_bytes()).hexdigest()
    if (
        code_sha != profile.expected_code_sha256
        or lock_sha != profile.expected_lock_sha256
        or bridge_sha != profile.expected_bridge_sha256
    ):
        raise WorkerProtocolError("selected_profile_asset_digest_mismatch")
    return worker_bytes, protocol_bytes, lock_bytes


def _resolved_state(
    *,
    store: ArtifactStoreReader,
    source_ref: artifacts.ArtifactRef,
    submitted_state: HTEObservationalData,
) -> tuple[bytes, HTEObservationalData]:
    raw = store.get_bytes(source_ref)
    manifest = store.get_manifest(source_ref)
    if manifest.kind != source_ref.kind or manifest.media_type != source_ref.media_type:
        raise WorkerProtocolError("source_manifest_reference_mismatch")
    payload = canon.from_canonical_bytes(raw)
    if not isinstance(payload, dict):
        raise WorkerProtocolError("source_payload_not_object")
    if "contract_payload" in payload:
        payload = payload["contract_payload"]
    source_state = HTEObservationalData.model_validate(payload)
    if digest(source_state.model_dump(mode="json")) != digest(
        submitted_state.model_dump(mode="json")
    ):
        raise WorkerProtocolError("method_job_input_differs_from_selected_source")
    return raw, source_state


def _data_payload(source_ref: artifacts.ArtifactRef, state: HTEObservationalData) -> dict[str, Any]:
    y = state.outcome.tolist()
    treatment = state.treatment.tolist()
    x = state.covariates.tolist()
    w = None if state.confounders is None else state.confounders.tolist()
    x_names = list(state.feature_names or [f"x{index}" for index in range(state.n_features)])
    w_names = (
        list(state.confounder_names)
        if state.confounder_names is not None
        else [f"w{index}" for index in range(state.confounders.shape[1])]
        if state.confounders is not None
        else []
    )
    row_ids = [f"{source_ref.artifact_id}#row:{index}" for index in range(state.n_obs)]
    data = {
        "row_ids": row_ids,
        "row_order_sha256": digest(row_ids),
        "y": y,
        "t": treatment,
        "x": x,
        "w": w,
        "x_names": x_names,
        "w_names": w_names,
    }
    data["data_sha256"] = digest(data)
    return data


def _request(
    *,
    profile: ServerSelectedProfile,
    source_ref: artifacts.ArtifactRef,
    source_bytes: bytes,
    state: HTEObservationalData,
    job_id: str,
    seed: int,
) -> dict[str, Any]:
    if not job_id or type(seed) is not int or not 0 <= seed < 2**32:
        raise WorkerProtocolError("server_method_job_binding_invalid")
    data = _data_payload(source_ref, state)
    request: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "profile": profile.profile_id,
        "method_fqn": METHOD_FQN,
        "operation": OPERATION,
        "job_id": job_id,
        "source": {
            "artifact_ref": source_ref.model_dump(mode="json"),
            "content_sha256": hashlib.sha256(source_bytes).hexdigest(),
        },
        "data": data,
        "configuration": dict(CONFIGURATION),
        "seed": seed,
        "lock_sha256": profile.expected_lock_sha256,
    }
    request["request_id"] = digest(request)
    request["request_sha256"] = digest(request)
    validate_request(request)
    return request


def _locked_distributions(lock_bytes: bytes) -> dict[str, str]:
    lock = tomllib.loads(lock_bytes.decode("utf-8"))
    return {
        package["name"].lower().replace("_", "-").replace(".", "-"): package["version"]
        for package in lock["package"]
        if package.get("source", {}).get("virtual") != "."
    }


def _require_selected_host() -> None:
    """Require the server process itself to run on the selected measured Mac host."""
    if (
        sys.platform != EXPECTED_SYS_PLATFORM
        or host_platform.machine().lower() != EXPECTED_MACHINE
        or host_platform.mac_ver()[0] != EXPECTED_MACOS_VERSION
    ):
        raise ValueError("server process does not match the server-selected Mac profile")


def _server_environment() -> dict[str, str]:
    """Record host facts independently observed by the selecting parent process."""
    _require_selected_host()
    return {
        "python_version": host_platform.python_version(),
        "implementation": host_platform.python_implementation(),
        "sys_platform": sys.platform,
        "machine": host_platform.machine().lower(),
        "macos_version": host_platform.mac_ver()[0],
    }


def _validate_environment(
    environment: object,
    lock_bytes: bytes,
    profile: ServerSelectedProfile,
) -> None:
    if not isinstance(environment, dict) or set(environment) != {
        "python_version", "implementation", "sys_platform", "machine", "macos_version",
        "executable", "distributions",
    }:
        raise WorkerProtocolError("worker_environment_shape_invalid")
    if (
        environment["python_version"] != EXPECTED_PYTHON_VERSION
        or environment["implementation"] != "CPython"
        or environment["sys_platform"] != EXPECTED_SYS_PLATFORM
        or environment["machine"] != EXPECTED_MACHINE
        or environment["macos_version"] != EXPECTED_MACOS_VERSION
        or environment["executable"] != str(profile.python_executable.resolve())
    ):
        raise WorkerProtocolError("worker_interpreter_platform_mismatch")
    distributions = environment["distributions"]
    if not isinstance(distributions, dict) or distributions != _locked_distributions(lock_bytes):
        raise WorkerProtocolError("worker_distribution_inventory_mismatch")


def _finite_number(value: object) -> bool:
    return type(value) in {int, float} and math.isfinite(value)


def _validate_outcome(response: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    outcome = response["outcome"]
    if not isinstance(outcome, dict) or not isinstance(outcome.get("status"), str):
        raise WorkerProtocolError("worker_outcome_shape_invalid")
    if outcome["status"] == "error":
        if set(outcome) != {"status", "error"} or not isinstance(outcome["error"], dict):
            raise WorkerProtocolError("worker_error_shape_invalid")
        error = outcome["error"]
        if set(error) != {"code", "exception_type"} or error["code"] not in {
            "native_ate_inference_unavailable", "backend_fit_failed"
        }:
            raise WorkerProtocolError("worker_error_not_allowlisted")
        if not isinstance(error["exception_type"], str) or not error["exception_type"]:
            raise WorkerProtocolError("worker_error_type_invalid")
        raise WorkerProtocolError(str(error["code"]))
    if outcome["status"] != "ok" or set(outcome) != {
        "status", "result", "result_sha256"
    }:
        raise WorkerProtocolError("worker_outcome_not_success_or_typed_error")
    result = outcome["result"]
    if not isinstance(result, dict) or digest(result) != outcome["result_sha256"]:
        raise WorkerProtocolError("worker_result_digest_mismatch")
    expected_fields = {
        "row_ids", "feature_names", "confounder_names", "configuration", "estimator_fqn",
        "ate", "ate_ci_lower", "ate_ci_upper", "ate_p_value", "cate_values",
        "cate_std_values", "cate_ci_lower_values", "cate_ci_upper_values", "n_treated",
        "n_control", "confidence_level",
    }
    if set(result) != expected_fields:
        raise WorkerProtocolError("worker_result_fields_mismatch")
    data = request["data"]
    n_rows = len(data["row_ids"])
    if (
        result["row_ids"] != data["row_ids"]
        or result["feature_names"] != data["x_names"]
        or result["confounder_names"] != data["w_names"]
        or result["configuration"] != request["configuration"]
        or result["estimator_fqn"] != "econml.dml.LinearDML"
        or result["confidence_level"] != CONFIGURATION["confidence_level"]
        or result["n_treated"] != sum(value == 1 for value in data["t"])
        or type(result["n_treated"]) is not int
        or type(result["n_control"]) is not int
        or result["n_control"] != sum(value == 0 for value in data["t"])
    ):
        raise WorkerProtocolError("worker_result_input_binding_mismatch")
    cate = result["cate_values"]
    if not isinstance(cate, list) or len(cate) != n_rows or any(
        not _finite_number(value) for value in cate
    ):
        raise WorkerProtocolError("worker_cate_vector_invalid")
    for name in ("ate", "ate_ci_lower", "ate_ci_upper"):
        if not _finite_number(result[name]):
            raise WorkerProtocolError("worker_ate_or_interval_invalid")
    if not result["ate_ci_lower"] <= result["ate"] <= result["ate_ci_upper"]:
        raise WorkerProtocolError("worker_native_ate_interval_invalid")
    if not math.isclose(
        float(result["ate"]), math.fsum(float(value) for value in cate) / n_rows,
        rel_tol=0.0, abs_tol=1e-12,
    ):
        raise WorkerProtocolError("worker_ate_not_mean_of_returned_cates")
    p_value = result["ate_p_value"]
    if p_value is not None and (not _finite_number(p_value) or not 0.0 <= p_value <= 1.0):
        raise WorkerProtocolError("worker_p_value_invalid")
    for values_name in ("cate_std_values", "cate_ci_lower_values", "cate_ci_upper_values"):
        values = result[values_name]
        if values is not None and (
            not isinstance(values, list)
            or len(values) != n_rows
            or any(not _finite_number(value) for value in values)
        ):
            raise WorkerProtocolError("worker_cate_diagnostic_shape_invalid")
    if any(
        value is not None
        for value in (result["cate_ci_lower_values"], result["cate_ci_upper_values"])
    ):
        lower, upper = result["cate_ci_lower_values"], result["cate_ci_upper_values"]
        if lower is None or upper is None or any(
            lo > point or point > hi or lo > hi
            for lo, point, hi in zip(lower, cate, upper, strict=True)
        ):
            raise WorkerProtocolError("worker_cate_interval_invalid")
    if result["cate_std_values"] is not None and any(
        value < 0 for value in result["cate_std_values"]
    ):
        raise WorkerProtocolError("worker_cate_standard_error_invalid")
    return result


def _validate_response(
    response: dict[str, Any],
    request: dict[str, Any],
    lock_bytes: bytes,
    profile: ServerSelectedProfile,
) -> dict[str, Any]:
    validate_response_shape(response)
    expected = {
        "schema": RESPONSE_SCHEMA,
        "profile": request["profile"],
        "method_fqn": request["method_fqn"],
        "operation": request["operation"],
        "job_id": request["job_id"],
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "source": request["source"],
        "data_sha256": request["data"]["data_sha256"],
        "row_order_sha256": request["data"]["row_order_sha256"],
        "lock_sha256": request["lock_sha256"],
    }
    if any(response.get(key) != value for key, value in expected.items()):
        raise WorkerProtocolError("worker_response_binding_mismatch")
    _validate_environment(response["environment"], lock_bytes, profile)
    return _validate_outcome(response, request)


def _to_candidate(
    *,
    result: dict[str, Any],
    request: dict[str, Any],
    profile: ServerSelectedProfile,
    code_sha256: str,
    response: dict[str, Any],
) -> CandidateHTEOutput:
    data = request["data"]
    y = data["y"]
    x_names = data["x_names"]
    cate = result["cate_values"]
    confidence = result["confidence_level"]
    alpha = 1.0 - confidence
    hte_result = HTEResult.from_estimates(
        method=CausalMethod.DOUBLE_ML,
        ate=result["ate"],
        ate_ci_lower=result["ate_ci_lower"],
        ate_ci_upper=result["ate_ci_upper"],
        ate_p_value=result["ate_p_value"],
        confidence_level=confidence,
        cate_values=cate,
        cate_std_values=result["cate_std_values"] or [],
        cate_ci_lower_values=result["cate_ci_lower_values"] or [],
        cate_ci_upper_values=result["cate_ci_upper_values"] or [],
        subgroup_effects=build_cate_quantile_subgroups(
            cate_values=cate, n_quantiles=4, alpha=alpha
        ),
        feature_importances=[],
        n_samples=len(y),
        n_treated=result["n_treated"],
        n_control=result["n_control"],
        n_features=len(x_names),
        feature_names=x_names,
        econml_estimator_class=result["estimator_fqn"],
        econml_params={"model_type": "linear", "cv_folds": CONFIGURATION["cv_folds"]},
        feature_display_map={name: name for name in x_names},
        metadata={
            "warnings": [
                message
                for available, message in (
                    (
                        result["cate_std_values"] is not None,
                        "native CATE standard errors unavailable",
                    ),
                    (
                        result["cate_ci_lower_values"] is not None,
                        "native CATE intervals unavailable",
                    ),
                )
                if not available
            ],
            "confounder_names": list(result["confounder_names"]),
            "worker_profile_id": profile.profile_id,
            "method_fqn": METHOD_FQN,
            "candidate_computation_only": True,
        },
    )
    report = build_success_report(
        method=CausalMethod.DOUBLE_ML,
        estimand="ATE_from_CATE",
        point_estimate=result["ate"],
        confidence_interval=(result["ate_ci_lower"], result["ate_ci_upper"]),
        confidence_level=confidence,
        p_value=result["ate_p_value"],
        inference_method="double_ml",
        sample_size=len(y),
        n_treated=result["n_treated"],
        n_control=result["n_control"],
        pre_periods=0,
        post_periods=0,
        assumptions=dict(DoubleMachineLearning.metadata.assumptions),
        method_params={"model_type": "linear", "cv_folds": CONFIGURATION["cv_folds"]},
        metadata={
            "hte_result_present": True,
            "n_features": len(x_names),
            "candidate_computation_only": True,
            "worker_profile_id": profile.profile_id,
            "method_fqn": METHOD_FQN,
        },
    )
    source_ref = artifacts.ArtifactRef.model_validate(request["source"]["artifact_ref"])
    return CandidateHTEOutput(
        method_fqn=METHOD_FQN,
        profile_id=profile.profile_id,
        job_id=request["job_id"],
        source_ref=source_ref,
        source_content_sha256=request["source"]["content_sha256"],
        request_id=request["request_id"],
        request_sha256=request["request_sha256"],
        data_sha256=request["data"]["data_sha256"],
        row_order_sha256=request["data"]["row_order_sha256"],
        seed=request["seed"],
        worker_lock_sha256=profile.expected_lock_sha256,
        worker_code_sha256=code_sha256,
        bridge_code_sha256=profile.expected_bridge_sha256,
        worker_result_sha256=digest(result),
        server_environment=_server_environment(),
        worker_environment=dict(response["environment"]),
        worker_result=dict(result),
        authority="candidate_computation_only",
        report=report,
        hte_result=hte_result,
    )


def run_candidate(
    *,
    profile: ServerSelectedProfile,
    store: ArtifactStoreReader,
    source_ref: artifacts.ArtifactRef,
    state: HTEObservationalData,
    job_id: str,
    seed: int,
) -> CandidateHTEOutput:
    """Run one server-selected worker using the current typed source and MethodJob."""
    _require_selected_host()
    worker_bytes, protocol_bytes, lock_bytes = _profile_assets(profile)
    source = artifacts.ArtifactRef.model_validate(source_ref)
    source_bytes, resolved = _resolved_state(store=store, source_ref=source, submitted_state=state)
    request = _request(
        profile=profile,
        source_ref=source,
        source_bytes=source_bytes,
        state=resolved,
        job_id=job_id,
        seed=seed,
    )
    request_bytes = canonical_bytes(request)
    if len(request_bytes) > _MAX_BYTES:
        raise WorkerProtocolError("request_size_limit_exceeded")
    worker_script = profile.worker_directory / "worker.py"
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("POLISYOS_") and key != "PYTHONPATH"
    }
    try:
        process = subprocess.Popen(  # noqa: S603 -- fixed script and server-selected absolute paths
            [str(profile.python_executable), "-I", str(worker_script)],
            cwd=profile.worker_directory,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, _stderr = process.communicate(request_bytes, timeout=profile.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise WorkerProtocolError("worker_timeout") from exc
    except OSError as exc:
        raise WorkerProtocolError("worker_launch_failed") from exc
    if process.returncode != 0:
        raise WorkerProtocolError("worker_process_failed")
    if len(stdout) > _MAX_BYTES:
        raise WorkerProtocolError("response_size_limit_exceeded")
    try:
        response = json.loads(
            stdout,
            object_pairs_hook=_reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                WorkerProtocolError("nonfinite_json_constant")
            ),
        )
    except WorkerProtocolError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise WorkerProtocolError("malformed_worker_json") from exc
    if not isinstance(response, dict):
        raise WorkerProtocolError("worker_response_not_object")
    result = _validate_response(response, request, lock_bytes, profile)
    code_sha256 = hashlib.sha256(worker_bytes + protocol_bytes).hexdigest()
    return _to_candidate(
        result=result,
        request=request,
        profile=profile,
        code_sha256=code_sha256,
        response=response,
    )
