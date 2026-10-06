"""Run one locked DoWhy operation; no PolicyOS import, artifact access or authority."""

from __future__ import annotations

import contextlib
import importlib.metadata
import platform
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

# Python -I excludes the script directory; add only this fixed standalone owner.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from protocol import (
    MAX_BYTES,
    PROFILE,
    RESPONSE_SCHEMA,
    canonical_bytes,
    decode,
    keys,
    validate_request,
)


def _finite_numeric_array(value: object) -> NDArray[np.float64]:
    """Validate actual numeric primitives before any floating-point conversion."""
    import numpy as np

    raw = np.asarray(value, dtype=object)
    if any(
        isinstance(x, (bool, np.bool_))
        or not isinstance(x, (int, float, np.integer, np.floating))
        for x in raw.flat
    ):
        raise ValueError("finite numeric primitives required; no string/bool conversion")
    a = raw.astype(float)
    if not np.isfinite(a).all():
        raise ValueError("finite numeric primitives required")
    return a


def scalar(value: object) -> float:
    """Require a finite scalar backend value without primitive coercion."""
    a = _finite_numeric_array(value)
    if a.size != 1:
        raise ValueError("finite scalar estimate required")
    return float(a.reshape(-1)[0])


def interval(value: object) -> list[float] | None:
    """Accept one ordered finite scalar interval, without flattening or repair."""
    if value is None:
        return None
    a = _finite_numeric_array(value)
    if a.shape not in {(2,), (1, 2)}:
        raise ValueError("unsupported confidence interval shape/value")
    lo, hi = (float(x) for x in a.reshape(2))
    if lo > hi:
        raise ValueError("reversed confidence interval")
    return [lo, hi]


def linear_ate(request: dict[str, Any]) -> dict[str, Any]:
    """Identify and fit the explicitly bound constant-effect linear ATE profile."""
    import dowhy
    import numpy as np
    import pandas as pd

    p = request["parameters"]
    keys(
        p,
        {
            "treatment",
            "outcome",
            "adjustment_set",
            "estimand_type",
            "method_name",
            "control_value",
            "treatment_value",
            "target_units",
            "confidence_level",
        },
    )
    if (
        p["estimand_type"],
        p["method_name"],
        p["control_value"],
        p["treatment_value"],
        p["target_units"],
        p["confidence_level"],
    ) != ("nonparametric-ate", "backdoor.linear_regression", 0, 1, "ate", 0.95):
        raise ValueError("unsupported estimand/estimator/contrast/target/level")
    frame = pd.DataFrame(request["basis"]["rows"], columns=request["basis"]["columns"])
    if p["treatment"] == p["outcome"] or set(frame[p["treatment"]].unique()) != {0, 1}:
        raise ValueError("both binary treatment arms required")
    model = dowhy.CausalModel(
        data=frame,
        treatment=p["treatment"],
        outcome=p["outcome"],
        graph=request["graph"]["payload"],
        estimand_type=p["estimand_type"],
    )
    identified = model.identify_effect(proceed_when_unidentifiable=False)
    if identified.estimands.get("backdoor") is None:
        raise ValueError("ATE not identified by the supplied graph")
    adjustment = sorted(identified.get_backdoor_variables())
    if adjustment != sorted(p["adjustment_set"]):
        raise ValueError("identified adjustment set mismatch")
    design = np.column_stack(
        [np.ones(len(frame)), frame[p["treatment"]], *(frame[x] for x in adjustment)]
    )
    if np.linalg.matrix_rank(design) != design.shape[1] or len(frame) <= design.shape[1]:
        raise ValueError("full-rank Gaussian linear profile required")
    estimate = model.estimate_effect(
        identified,
        method_name="backdoor.linear_regression",
        control_value=0,
        treatment_value=1,
        target_units="ate",
        effect_modifiers=None,
        confidence_intervals=True,
        method_params={"confidence_level": 0.95},
    )
    if estimate.estimator.confidence_level != 0.95:
        raise ValueError("effective estimator confidence level mismatch")
    ci = interval(estimate.get_confidence_intervals(confidence_level=0.95))
    raw_error = estimate.get_standard_error()
    return {
        "point": scalar(estimate.value),
        "interval": ci,
        "inference_status": "point_only" if ci is None else "confidence_interval",
        "standard_error": None if raw_error is None else scalar(raw_error),
        "effective_confidence_level": 0.95 if ci is not None else None,
        "identified_estimand": str(identified),
        "adjustment_set": adjustment,
        "estimand_type": str(getattr(identified.estimand_type, "value", identified.estimand_type)),
        "method_name": "backdoor.linear_regression",
        "control_value": 0,
        "treatment_value": 1,
        "target_units": "ate",
        "estimator_class": type(estimate.estimator).__module__
        + "."
        + type(estimate.estimator).__name__,
    }


def gcm_fit(request: dict[str, Any]) -> dict[str, Any]:
    """Fit explicit empirical roots and linear additive-noise mechanisms with DoWhy GCM."""
    import networkx as nx
    import numpy as np
    import pandas as pd
    from dowhy import gcm
    from dowhy.gcm.ml import create_linear_regressor

    graph = request["graph"]["payload"]
    keys(graph, {"nodes", "edges"})
    keys(request["parameters"], {"mechanisms", "bootstrap_indices"})
    dag = nx.DiGraph()
    dag.add_nodes_from(graph["nodes"])
    dag.add_edges_from(graph["edges"])
    if set(dag) != set(request["basis"]["columns"]) or not nx.is_directed_acyclic_graph(dag):
        raise ValueError("complete observed DAG required")
    declared = request["parameters"]["mechanisms"]
    if set(declared) != set(dag):
        raise ValueError("every mechanism must be declared")
    np.random.seed(request["seed"])
    frame = pd.DataFrame(request["basis"]["rows"], columns=request["basis"]["columns"])
    indices = request["parameters"]["bootstrap_indices"]
    if not isinstance(indices, list) or len(indices) > 500:
        raise ValueError("unsupported bootstrap replicate count")
    if any(
        not isinstance(row, list)
        or len(row) != len(frame)
        or any(type(i) is not int or not 0 <= i < len(frame) for i in row)
        for row in indices
    ):
        raise ValueError("bootstrap must resample complete aligned rows")
    gcm.config.disable_progress_bars()

    def fit_one(values: object, row_ids: list[str]) -> dict[str, Any]:
        model = gcm.StructuralCausalModel(dag.copy())
        for node in dag:
            expected = "linear_additive_noise" if list(dag.predecessors(node)) else "empirical"
            if declared[node] != expected:
                raise ValueError("unsupported declared mechanism")
            mechanism = (
                gcm.AdditiveNoiseModel(create_linear_regressor())
                if expected != "empirical"
                else gcm.EmpiricalDistribution()
            )
            model.set_causal_mechanism(node, mechanism)
        gcm.fit(model, values)
        fitted = {}
        for node in nx.topological_sort(dag):
            mechanism = model.causal_mechanism(node)
            parents = sorted(dag.predecessors(node))
            if not parents:
                samples = np.asarray(mechanism._data).reshape(-1).tolist()
                fitted[node] = {"parents": [], "family": "empirical", "observed_samples": samples}
            else:
                predictor = mechanism.prediction_model.sklearn_model
                coeff = np.asarray(predictor.coef_).reshape(-1)
                residuals = np.asarray(mechanism.noise_model._data).reshape(-1).tolist()
                fitted[node] = {
                    "parents": parents,
                    "family": "linear_additive_noise",
                    "intercept": scalar(predictor.intercept_),
                    "coefficients": {name: scalar(coeff[i]) for i, name in enumerate(parents)},
                    "residual_samples": residuals,
                    "noise_std": float(np.std(residuals)),
                }
        return {"mechanisms": fitted, "fit_function": "dowhy.gcm.fit", "row_ids": row_ids}

    result = fit_one(frame, request["basis"]["row_ids"])
    result["bootstrap_models"] = [
        fit_one(
            frame.iloc[index].reset_index(drop=True),
            [request["basis"]["row_ids"][i] for i in index],
        )
        for index in indices
    ]
    return result


def execute(request: dict[str, Any]) -> dict[str, Any]:
    """Execute one validated operation and return candidate computation evidence only."""
    validate_request(request)
    if (
        sys.version_info[:2] != (3, 12)
        or sys.platform != "linux"
        or importlib.metadata.version("dowhy") != "0.14"
    ):
        raise ValueError("locked Python3.12/DoWhy0.14 profile required")
    result = linear_ate(request) if request["operation"] == "linear_ate" else gcm_fit(request)
    versions = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    return {
        "schema": RESPONSE_SCHEMA,
        "profile": PROFILE,
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "operation": request["operation"],
        "source": request["source"],
        "data_sha256": request["basis"]["data_sha256"],
        "row_sha256": request["basis"]["row_sha256"],
        "graph_sha256": request["graph"]["sha256"],
        "python": platform.python_version(),
        "versions": versions,
        "authority": "candidate_computation_only",
        "result": result,
    }


def main() -> int:
    """Read bounded JSON stdin and emit exactly one JSON response to stdout."""
    try:
        request = decode(sys.stdin.buffer.read(MAX_BYTES + 1))
        with contextlib.redirect_stdout(sys.stderr):
            response = execute(request)
        raw = canonical_bytes(response)
        if len(raw) > MAX_BYTES:
            raise ValueError("worker response exceeds byte limit")
        sys.stdout.buffer.write(raw)
        return 0
    except Exception as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
