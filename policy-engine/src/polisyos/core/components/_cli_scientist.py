"""CLI sub-module: scientist sensitivity, stress-test and backtest commands."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec

__all__ = [
    "_cmd_scientist_sensitivity_run",
    "_cmd_scientist_stress_test",
    "_cmd_scientist_backtest",
]


def _validate_output_extension(output_path: str | None, output_format: str) -> None:
    if not output_path:
        return
    expected = ".json" if output_format == "json" else ".md"
    suffix = Path(output_path).suffix.lower()
    if suffix and suffix != expected:
        raise ValueError(
            f"output extension '{suffix}' does not match --format {output_format!r} "
            f"(expected '{expected}')"
        )


def _evaluate_builtin_sensitivity_objective(samples: Any, objective_spec: Any) -> Any:
    import numpy as np

    if objective_spec is None:
        objective_type = "quadratic"
        spec: dict[str, Any] = {}
    elif isinstance(objective_spec, str):
        objective_type = objective_spec
        spec = {}
    elif isinstance(objective_spec, dict):
        objective_type = str(objective_spec.get("type", "quadratic"))
        spec = objective_spec
    else:
        raise ValueError("objective must be null, string, or object")

    if objective_type == "ishigami":
        if samples.shape[1] < 3:
            raise ValueError("ishigami objective requires at least 3 parameters")
        a = float(spec.get("a", 7.0))
        b = float(spec.get("b", 0.1))
        x1 = samples[:, 0]
        x2 = samples[:, 1]
        x3 = samples[:, 2]
        return np.sin(x1) + a * (np.sin(x2) ** 2) + b * (x3**4) * np.sin(x1)

    if objective_type == "quadratic":
        return np.sum(samples**2, axis=1)

    raise ValueError(f"unsupported built-in objective type: {objective_type}")


def _build_builtin_objective_callable(
    parameter_names: list[str],
    objective_spec: Any,
) -> Any:
    if objective_spec is None:
        objective_spec = {"type": "quadratic"}
    if isinstance(objective_spec, str):
        objective_spec = {"type": objective_spec}
    if not isinstance(objective_spec, dict):
        raise ValueError("objective must be null, string, or object")

    objective_type = str(objective_spec.get("type", "quadratic"))
    center = objective_spec.get("center")
    if not isinstance(center, dict):
        center = {}
    weights = objective_spec.get("weights")
    if not isinstance(weights, dict):
        weights = {}

    def _objective(candidate: dict[str, Any]) -> float:
        total = 0.0
        for name in parameter_names:
            value = float(candidate.get(name, 0.0))
            c = float(center.get(name, 0.0))
            w = float(weights.get(name, 1.0))
            total += w * ((value - c) ** 2)
        if objective_type == "negative_quadratic":
            return -total
        if objective_type == "quadratic":
            return total
        raise ValueError(f"unsupported built-in objective type: {objective_type}")

    return _objective


class _CallableObjective:
    def __init__(self, name: str, fn: Any) -> None:
        self._name = name
        self._fn = fn

    @property
    def name(self) -> str:
        return self._name

    @property
    def direction(self) -> Any:
        objective_module = importlib.import_module("polisyos.scientist.search.objective")
        return objective_module.OptimizationDirection.MINIMIZE

    def evaluate(self, results: dict[str, Any]) -> Any:
        objective_module = importlib.import_module("polisyos.scientist.search.objective")
        value = float(results.get("stress_objective", 0.0))
        return objective_module.ObjectiveValue(
            name=self._name,
            raw_value=value,
            direction=objective_module.OptimizationDirection.MINIMIZE,
        )


def _cmd_scientist_sensitivity_run(args: Any) -> int:
    try:
        _validate_output_extension(args.output, args.format)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    doe_designs = importlib.import_module("polisyos.scientist.doe.designs")
    doe_sampling = importlib.import_module("polisyos.scientist.doe.sampling")
    doe_analysis = importlib.import_module("polisyos.scientist.doe.analysis")

    plan_data = payload.get("plan", payload)
    try:
        plan = doe_designs.SensitivityPlan.model_validate(plan_data)
    except Exception as exc:
        print(f"ERROR: invalid sensitivity plan: {exc}", file=sys.stderr)
        return 2

    import numpy as np

    if "samples" in payload:
        samples = np.asarray(payload["samples"], dtype=float)
    else:
        try:
            samples = doe_sampling.generate_sensitivity_samples(plan)
        except Exception as exc:
            print(f"ERROR: failed to generate sensitivity samples: {exc}", file=sys.stderr)
            return 1

    if "outputs" in payload:
        outputs = np.asarray(payload["outputs"], dtype=float)
    else:
        try:
            outputs = _evaluate_builtin_sensitivity_objective(samples, payload.get("objective"))
        except Exception as exc:
            print(f"ERROR: failed to evaluate built-in objective: {exc}", file=sys.stderr)
            return 2

    try:
        result = doe_analysis.analyze_sensitivity(plan, samples, outputs)
    except Exception as exc:
        print(f"ERROR: sensitivity analysis failed: {exc}", file=sys.stderr)
        return 1

    cas = FileSystemCAS(Path(args.cas_root))
    ref = cas.put_json(
        result.model_dump(mode="json"),
        PutOptions(
            kind="scientist.sensitivity_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.SensitivityResult", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    out_payload = result.model_dump(mode="json")
    out_payload["cas_artifact_id"] = str(ref.artifact_id)

    rendered = json.dumps(out_payload, ensure_ascii=True, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"sensitivity_report={args.output}")
    else:
        print(rendered)
    return 0


def _cmd_scientist_stress_test(args: Any) -> int:
    try:
        _validate_output_extension(args.output, args.format)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    doe_designs = importlib.import_module("polisyos.scientist.doe.designs")
    search_objective = importlib.import_module("polisyos.scientist.search.objective")
    search_adversarial = importlib.import_module("polisyos.scientist.search.adversarial")

    plan_data = payload.get("plan", payload)
    try:
        plan = doe_designs.AdversarialPlan.model_validate(plan_data)
    except Exception as exc:
        print(f"ERROR: invalid adversarial plan: {exc}", file=sys.stderr)
        return 2

    param_names = [item.name for item in plan.parameter_specs]
    objective_spec = payload.get("objective") if isinstance(payload, dict) else None

    objective_callable = _build_builtin_objective_callable(param_names, objective_spec)
    composite_objective = search_objective.CompositeObjective(
        [_CallableObjective(name="stress_objective", fn=objective_callable)]
    )

    class _RandomGenerator:
        def __init__(self, specs: list[Any], seed: int | None) -> None:
            import random

            self._specs = specs
            self._rng = random.Random(seed)

        def generate(self, history: list[Any], current_best: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
            del history, current_best, context
            candidate: dict[str, Any] = {"semantic": {"interventions": []}}
            for spec in self._specs:
                candidate[spec.name] = self._rng.uniform(spec.lower_bound, spec.upper_bound)
            return candidate

    def _stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del context
        return {"simulation_results": {"stress_objective": objective_callable(candidate)}}

    cas = FileSystemCAS(Path(args.cas_root))
    report = search_adversarial.run_stress_test(
        adversarial_plan=plan,
        base_objective=composite_objective,
        stage_b_evaluator=_stage_b,
        candidate_generator=_RandomGenerator(plan.parameter_specs, plan.seed),
        context={},
        cas=cas,
    )

    rendered = json.dumps(report.model_dump(mode="json"), ensure_ascii=True, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"stress_report={args.output}")
    else:
        print(rendered)
    return 0


def _cmd_scientist_backtest(args: Any) -> int:
    try:
        backtesting_cli = importlib.import_module("polisyos.scientist.backtesting.cli")
        code, rendered = backtesting_cli.run_backtest_command(args)
    except Exception as exc:
        print(f"ERROR: backtest failed: {exc}", file=sys.stderr)
        return 1

    if rendered:
        print(rendered)
    return code
