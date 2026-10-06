"""Launch the selected nonauthoritative DoWhy worker inside a Foundry method job.

The enclosing Scientist job owns scheduling and CAS emission. This bridge resolves
the selected source in the parent, bounds one fixed subprocess, and validates its
reply. The worker is never imported into the Python 3.14 application.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import signal
import subprocess
import tomllib
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes

_MAX_BYTES = 8 * 1024 * 1024
_TIMEOUT_S = 60.0
_REQUEST_SCHEMA = "polisyos.dowhy.request.v1"
_RESPONSE_SCHEMA = "polisyos.dowhy.response.v1"


class WorkerUnavailableError(RuntimeError):
    """Indicate missing profile, source admission or a failed worker transport."""


class WorkerBindingError(ValueError):
    """Indicate that actual source/result content does not match the selected request."""


@dataclass(frozen=True)
class _WorkerContext:
    source_ref: ArtifactRef
    source_sha256: str
    source_payload: dict[str, Any]


_CONTEXT: ContextVar[_WorkerContext | None] = ContextVar("dowhy_worker_context", default=None)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


@contextmanager
def worker_execution_context(*, store: Any, source_ref: ArtifactRef) -> Iterator[None]:
    """Admit one actual typed CAS source around an existing method-job invocation.

    Args:
        store: The enclosing job's already-authorized artifact store.
        source_ref: The selected observational input, never a caller-supplied hash.

    Yields:
        A content-resolved execution context; this function performs no writes.
    """
    ref = ArtifactRef.model_validate(source_ref)
    raw = store.get_bytes(ref)
    manifest = store.get_manifest(ref)
    if manifest.kind != ref.kind or manifest.media_type != ref.media_type:
        raise WorkerBindingError("source artifact manifest/ref mismatch")
    payload = from_canonical_bytes(raw)
    if not isinstance(payload, dict):
        raise WorkerBindingError("source artifact must contain a typed input object")
    if "contract_payload" in payload:
        payload = payload["contract_payload"]
    if not isinstance(payload, dict):
        raise WorkerBindingError("source contract payload must be an object")
    token = _CONTEXT.set(_WorkerContext(ref, hashlib.sha256(raw).hexdigest(), payload))
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def _worker_directory() -> Path:
    """Resolve fixed canonical source assets or their unpacked-wheel projection."""
    module = Path(__file__).resolve()
    required = {"worker.py", "protocol.py", "pyproject.toml", "uv.lock", ".python-version", "README.md"}
    packaged = module.parent / "_dowhy_profile"
    candidates = [packaged]
    candidates.extend(
        parent / "workers" / "dowhy-014"
        for parent in module.parents
        if (parent / "pyproject.toml").is_file()
    )
    for candidate in candidates:
        if all((candidate / name).is_file() for name in required):
            return candidate
    raise WorkerUnavailableError("selected DoWhy profile assets unavailable in this installation")


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise WorkerBindingError(f"duplicate response field: {key}")
        value[key] = item
    return value


@contextmanager
def _refuse_malformed_binding() -> Iterator[None]:
    """Convert every structural JSON failure at either reader into one typed refusal."""
    try:
        yield
    except WorkerBindingError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        raise WorkerBindingError(f"malformed worker binding: {exc}") from exc


def _validate_reply(response: Any, request: Mapping[str, Any], lock: Mapping[str, Any]) -> None:
    with _refuse_malformed_binding():
        _validate_reply_fields(response, request, lock)


def _finite_json_number(value: Any) -> bool:
    """Admit finite JSON numbers, never booleans or numeric-looking strings."""
    return type(value) in {int, float} and math.isfinite(value)


def _validate_reply_fields(
    response: Any, request: Mapping[str, Any], lock: Mapping[str, Any]
) -> None:
    fields = {
        "schema",
        "profile",
        "request_id",
        "request_sha256",
        "operation",
        "source",
        "data_sha256",
        "row_sha256",
        "graph_sha256",
        "python",
        "versions",
        "authority",
        "result",
    }
    if not isinstance(response, dict) or set(response) != fields:
        raise WorkerBindingError("unexpected worker response fields")
    bound = {
        "schema": _RESPONSE_SCHEMA,
        "profile": "dowhy-014",
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "operation": request["operation"],
        "source": request["source"],
        "data_sha256": request["basis"]["data_sha256"],
        "row_sha256": request["basis"]["row_sha256"],
        "graph_sha256": request["graph"]["sha256"],
        "authority": "candidate_computation_only",
    }
    if any(response.get(key) != value for key, value in bound.items()):
        raise WorkerBindingError("worker response source/request/content binding mismatch")
    versions = response["versions"]
    installed = {k.lower().replace("_", "-"): v for k, v in versions.items()}
    locked = {p["name"]: p["version"] for p in lock["package"]}
    required = set(locked) - {"polisyos-dowhy-worker", "colorama", "tzdata"}
    if not str(response["python"]).startswith("3.12.") or installed.get("dowhy") != "0.14":
        raise WorkerBindingError("worker Python/DoWhy version mismatch")
    if any(locked.get(name) != version for name, version in installed.items()):
        raise WorkerBindingError("worker distributions do not match the selected lock")
    if set(installed) != required:
        raise WorkerBindingError("worker installed Linux distribution inventory is incomplete")
    if request["operation"] != "linear_ate":
        return  # GCM owner validates the fitted mechanism schema and its consumer.
    result = response["result"]
    expected = {
        "point",
        "interval",
        "inference_status",
        "standard_error",
        "effective_confidence_level",
        "identified_estimand",
        "adjustment_set",
        "estimand_type",
        "method_name",
        "control_value",
        "treatment_value",
        "target_units",
        "estimator_class",
    }
    if not isinstance(result, dict) or set(result) != expected:
        raise WorkerBindingError("unexpected ATE result fields")
    p = request["parameters"]
    for key in ("estimand_type", "method_name", "control_value", "treatment_value", "target_units"):
        if result[key] != p[key]:
            raise WorkerBindingError(f"worker effective {key} mismatch")
    if sorted(result["adjustment_set"]) != sorted(p["adjustment_set"]):
        raise WorkerBindingError("worker adjustment binding mismatch")
    if (
        not _finite_json_number(result["point"])
        or any(
            not _finite_json_number(result[key]) for key in ("control_value", "treatment_value")
        )
        or (
            result["standard_error"] is not None
            and (
                not _finite_json_number(result["standard_error"])
                or result["standard_error"] < 0
            )
        )
    ):
        raise WorkerBindingError("nonfinite scalar estimate/error")
    if (
        result["estimator_class"]
        != "dowhy.causal_estimators.linear_regression_estimator.LinearRegressionEstimator"
    ):
        raise WorkerBindingError("unexpected actual estimator class")
    ci = result["interval"]
    if ci is None:
        if (
            result["inference_status"] != "point_only"
            or result["effective_confidence_level"] is not None
        ):
            raise WorkerBindingError("point-only result must not assert an interval/level")
    else:
        if (
            not isinstance(ci, list)
            or len(ci) != 2
            or not all(_finite_json_number(value) for value in ci)
            or not ci[0] <= result["point"] <= ci[1]
            or not _finite_json_number(result["effective_confidence_level"])
            or result["effective_confidence_level"] != 0.95
            or result["inference_status"] != "confidence_interval"
        ):
            raise WorkerBindingError("unsupported confidence interval/level")


def _bound_request(
    *, operation: str, state: Any, payload: Mapping[str, Any], seed: int
) -> dict[str, Any]:
    context = _CONTEXT.get()
    if context is None:
        raise WorkerUnavailableError("DoWhy worker requires a source-resolved method-job context")
    try:
        source_state = type(state).model_validate(context.source_payload)
    except (TypeError, ValueError) as exc:
        raise WorkerBindingError(
            "resolved source does not satisfy the selected input contract"
        ) from exc
    if _digest(source_state.model_dump(mode="json")) != _digest(state.model_dump(mode="json")):
        raise WorkerBindingError("actual method input differs from the resolved source rows/graph")
    matrix = state.data.tolist()
    columns = list(state.column_names)
    rows = [f"{context.source_ref.artifact_id}:{i}" for i in range(len(matrix))]
    parameters = dict(payload)
    if operation == "linear_ate":
        graph = {"representation": "dot", "payload": state.graph_dot}
        if not isinstance(state.graph_dot, str) or not state.graph_dot.strip():
            raise WorkerBindingError("selected DoWhy profile requires an explicit bound DOT graph")
    elif operation == "gcm_fit":
        graph = {"representation": "dag", "payload": parameters.pop("graph")}
    else:
        raise WorkerBindingError("unsupported worker operation")
    graph["sha256"] = _digest(graph["payload"])
    request = {
        "schema": _REQUEST_SCHEMA,
        "profile": "dowhy-014",
        "operation": operation,
        "source": {
            "artifact_ref": context.source_ref.model_dump(mode="json"),
            "content_sha256": context.source_sha256,
        },
        "basis": {
            "columns": columns,
            "rows": matrix,
            "row_ids": rows,
            "data_sha256": _digest({"columns": columns, "rows": matrix}),
            "row_sha256": _digest(rows),
        },
        "graph": graph,
        "parameters": parameters,
        "seed": seed,
    }
    request["request_id"] = _digest(request)
    request["request_sha256"] = _digest(request)
    return request


def run_worker(
    *, operation: str, state: Any, payload: Mapping[str, Any], seed: int
) -> dict[str, Any]:
    """Execute one selected worker operation on source-resolved aligned input rows.

    Args:
        operation: The finite linear_ate or gcm_fit protocol operation.
        state: The parent-validated GraphCausalData or SCMFitData.
        payload: Operation-specific parameters and, for GCM, projected DAG nodes/edges.
        seed: The enclosing method job's deterministic seed.

    Returns:
        Validated candidate response, including parent-observed code/lock identity.
    """
    request = _bound_request(operation=operation, state=state, payload=payload, seed=seed)
    raw = _json_bytes(request)
    if len(raw) > _MAX_BYTES:
        raise WorkerUnavailableError("DoWhy request exceeds selected profile byte limit")
    executable = Path(os.environ.get("POLISYOS_DOWHY_WORKER_PYTHON", ""))
    if not executable.is_absolute() or not executable.is_file():
        raise WorkerUnavailableError("configured absolute Python3.12 DoWhy interpreter unavailable")
    directory = _worker_directory()
    script, lock_path = directory / "worker.py", directory / "uv.lock"
    lock_bytes = lock_path.read_bytes()
    lock = tomllib.loads(lock_bytes.decode())
    code_hash = hashlib.sha256(
        script.read_bytes() + (directory / "protocol.py").read_bytes()
    ).hexdigest()
    env = {
        k: v for k, v in os.environ.items() if not k.startswith("POLISYOS_") and k != "PYTHONPATH"
    }
    try:
        process = subprocess.Popen(  # noqa: S603 -- fixed script; server-configured absolute interpreter
            [str(executable), "-I", str(script)],
            cwd=directory,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(raw, timeout=_TIMEOUT_S)
        except subprocess.TimeoutExpired as exc:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise WorkerUnavailableError("DoWhy worker exceeded selected profile deadline") from exc
    except OSError as exc:
        raise WorkerUnavailableError(f"DoWhy worker launch unavailable: {exc}") from exc
    if process.returncode:
        raise WorkerUnavailableError(
            f"DoWhy worker rejected/failed request: {stderr.decode()[-4000:]}"
        )
    if len(stdout) > _MAX_BYTES:
        raise WorkerBindingError("DoWhy worker response exceeds selected profile byte limit")
    try:
        response = json.loads(
            stdout,
            object_pairs_hook=_reject_duplicates,
            parse_constant=lambda x: (_ for _ in ()).throw(WorkerBindingError(x)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerBindingError("malformed DoWhy worker JSON response") from exc
    _validate_reply(response, request, lock)
    return {
        **response,
        "parent_observed": {
            "worker_code_sha256": code_hash,
            "worker_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
            "interpreter": str(executable),
            "timeout_s": _TIMEOUT_S,
            "max_message_bytes": _MAX_BYTES,
            "request_binding": {"seed": seed, "payload": dict(payload)},
        },
    }


def validate_persisted_worker_response(
    *, response: Mapping[str, Any], state: Any, store: Any, source_ref: ArtifactRef
) -> None:
    """Revalidate a persisted candidate against actual reopened source content.

    Args:
        response: The persisted worker response and parent-observed binding.
        state: The typed input reconstructed by the consumer from actual source bytes.
        store: The consumer's authorized CAS.
        source_ref: The selected actual source reference.

    This verifies candidate provenance and supported numerical shape, never causal
    assumptions, verifier authority or permission to publish. It launches no worker.
    """
    with _refuse_malformed_binding():
        _validate_persisted_binding(
            response=response, state=state, store=store, source_ref=source_ref
        )


def _validate_persisted_binding(
    *, response: Mapping[str, Any], state: Any, store: Any, source_ref: ArtifactRef
) -> None:
    observed = response["parent_observed"]
    binding = observed["request_binding"]
    with worker_execution_context(store=store, source_ref=source_ref):
        request = _bound_request(
            operation=response["operation"],
            state=state,
            payload=binding["payload"],
            seed=binding["seed"],
        )
    directory = _worker_directory()
    lock_bytes = (directory / "uv.lock").read_bytes()
    code_bytes = (directory / "worker.py").read_bytes() + (directory / "protocol.py").read_bytes()
    if (
        observed["worker_lock_sha256"] != hashlib.sha256(lock_bytes).hexdigest()
        or observed["worker_code_sha256"] != hashlib.sha256(code_bytes).hexdigest()
    ):
        raise WorkerBindingError("persisted worker source/lock identity mismatch")
    _validate_reply(
        {key: value for key, value in response.items() if key != "parent_observed"},
        request,
        tomllib.loads(lock_bytes.decode()),
    )
