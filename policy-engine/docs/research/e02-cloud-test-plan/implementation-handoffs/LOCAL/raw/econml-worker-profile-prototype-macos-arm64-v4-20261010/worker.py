"""Execute one isolated LinearDML candidate computation; no CAS or authority."""

from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from protocol import (
    MAX_BYTES,
    METHOD_FQN,
    OPERATION,
    PROFILE_ID,
    RESPONSE_SCHEMA,
    canonical_bytes,
    decode,
    digest,
    validate_request,
)


class NativeInferenceUnavailableError(RuntimeError):
    """The selected estimator did not return the required native ATE interval."""


def _finite_scalar(value: object, *, name: str) -> float:
    import numpy as np

    raw = np.asarray(value, dtype=object)
    if raw.size != 1 or any(
        isinstance(item, (bool, np.bool_))
        or not isinstance(item, (int, float, np.integer, np.floating))
        for item in raw.flat
    ):
        raise ValueError(f"{name} must be one finite numeric value")
    number = float(raw.reshape(-1)[0])
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _row_vector(value: object, *, name: str, length: int) -> list[float]:
    import numpy as np

    raw = np.asarray(value, dtype=object)
    if raw.shape == (length, 1):
        raw = raw[:, 0]
    if raw.shape != (length,):
        raise ValueError(f"{name} must preserve the requested row count")
    output = [_finite_scalar(item, name=name) for item in raw]
    return output


def _native_interval(lower: object, upper: object, *, name: str) -> tuple[float, float]:
    lo = _finite_scalar(lower, name=f"{name} lower")
    hi = _finite_scalar(upper, name=f"{name} upper")
    if lo > hi:
        raise ValueError(f"{name} bounds are reversed")
    return lo, hi


def _optional_pvalue(inference: object) -> float | None:
    value = getattr(inference, "pvalue", None)
    if value is None:
        return None
    if callable(value):
        value = value()
    number = _finite_scalar(value, name="ATE p-value")
    if not 0.0 <= number <= 1.0:
        raise ValueError("ATE p-value is outside [0, 1]")
    return number


def _environment() -> dict[str, Any]:
    versions: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        version = distribution.version
        if name:
            normalized = name.lower().replace("_", "-").replace(".", "-")
            if normalized in versions:
                raise RuntimeError("duplicate installed distribution name")
            versions[normalized] = version
    return {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "sys_platform": sys.platform,
        "machine": platform.machine().lower(),
        "macos_version": platform.mac_ver()[0],
        "executable": str(Path(sys.executable).resolve()),
        "distributions": dict(sorted(versions.items())),
    }


def _fit(request: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    from econml.dml import LinearDML

    data = request["data"]
    config = request["configuration"]
    y = np.asarray(data["y"], dtype=float)
    treatment = np.asarray(data["t"], dtype=int)
    x = np.asarray(data["x"], dtype=float)
    w = None if data["w"] is None else np.asarray(data["w"], dtype=float)
    model = LinearDML(
        model_y=config["model_y"],
        model_t=config["model_t"],
        cv=config["cv_folds"],
        discrete_treatment=config["discrete_treatment"],
        random_state=request["seed"],
    )
    model.fit(y, treatment, X=x, W=w, inference="auto")

    cate = _row_vector(model.effect(x, T0=0, T1=1), name="CATE", length=len(y))
    ate = float(np.mean(np.asarray(cate, dtype=float)))
    try:
        native_ate_ci = model.ate_interval(
            X=x,
            T0=0,
            T1=1,
            alpha=1.0 - config["confidence_level"],
        )
        ate_ci_lower, ate_ci_upper = _native_interval(
            native_ate_ci[0], native_ate_ci[1], name="native ATE interval"
        )
    except Exception as exc:
        raise NativeInferenceUnavailableError from exc
    if not ate_ci_lower <= ate <= ate_ci_upper:
        raise ValueError("native ATE interval does not contain the reported CATE mean")

    try:
        native_ate_inference = model.ate_inference(X=x, T0=0, T1=1)
        ate_p_value = _optional_pvalue(native_ate_inference)
    except Exception:
        ate_p_value = None

    cate_std: list[float] | None = None
    try:
        inference = model.effect_inference(x, T0=0, T1=1)
        raw_std = getattr(inference, "std_point", None)
        if raw_std is not None:
            cate_std = _row_vector(raw_std, name="CATE standard error", length=len(y))
            if any(value < 0 for value in cate_std):
                raise ValueError("CATE standard errors must be nonnegative")
    except Exception:
        cate_std = None

    cate_lower: list[float] | None = None
    cate_upper: list[float] | None = None
    try:
        raw_lower, raw_upper = model.effect_interval(
            x, T0=0, T1=1, alpha=1.0 - config["confidence_level"]
        )
        cate_lower = _row_vector(raw_lower, name="CATE lower interval", length=len(y))
        cate_upper = _row_vector(raw_upper, name="CATE upper interval", length=len(y))
        if any(
            lower > point or point > upper or lower > upper
            for lower, point, upper in zip(cate_lower, cate, cate_upper, strict=True)
        ):
            raise ValueError("native CATE interval does not contain its point")
    except Exception:
        cate_lower = None
        cate_upper = None

    return {
        "row_ids": list(data["row_ids"]),
        "feature_names": list(data["x_names"]),
        "confounder_names": list(data["w_names"]),
        "configuration": dict(config),
        "estimator_fqn": "econml.dml.LinearDML",
        "ate": ate,
        "ate_ci_lower": ate_ci_lower,
        "ate_ci_upper": ate_ci_upper,
        "ate_p_value": ate_p_value,
        "cate_values": cate,
        "cate_std_values": cate_std,
        "cate_ci_lower_values": cate_lower,
        "cate_ci_upper_values": cate_upper,
        "n_treated": int(np.count_nonzero(treatment == 1)),
        "n_control": int(np.count_nonzero(treatment == 0)),
        "confidence_level": config["confidence_level"],
    }


def _bound_response(request: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    source = request["source"]
    data = request["data"]
    return {
        "schema": RESPONSE_SCHEMA,
        "profile": PROFILE_ID,
        "method_fqn": METHOD_FQN,
        "operation": OPERATION,
        "job_id": request["job_id"],
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "source": source,
        "data_sha256": data["data_sha256"],
        "row_order_sha256": data["row_order_sha256"],
        "lock_sha256": request["lock_sha256"],
        "environment": _environment(),
        "authority": "candidate_computation_only",
        "outcome": outcome,
    }


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_BYTES + 1)
    try:
        request = decode(raw)
        validate_request(request)
        lock_path = Path(__file__).resolve().parent / "uv.lock"
        if hashlib.sha256(lock_path.read_bytes()).hexdigest() != request["lock_sha256"]:
            raise ValueError("selected lock digest mismatch")
    except Exception:
        sys.stderr.write("invalid_request_or_profile_binding\n")
        return 2

    try:
        result = _fit(request)
    except NativeInferenceUnavailableError:
        outcome = {
            "status": "error",
            "error": {
                "code": "native_ate_inference_unavailable",
                "exception_type": "NativeInferenceUnavailableError",
            },
        }
    except Exception as exc:
        outcome = {
            "status": "error",
            "error": {"code": "backend_fit_failed", "exception_type": type(exc).__name__},
        }
    else:
        outcome = {"status": "ok", "result": result, "result_sha256": digest(result)}
    sys.stdout.buffer.write(canonical_bytes(_bound_response(request, outcome)) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
