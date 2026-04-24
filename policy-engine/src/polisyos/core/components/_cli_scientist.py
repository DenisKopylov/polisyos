"""CLI sub-module: scientist sensitivity, stress-test and backtest commands."""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any, cast

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components._cli_store import build_cli_filesystem_cas

__all__ = [
    "_cmd_scientist_agent_eval",
    "_cmd_scientist_agent_smoke",
    "_cmd_scientist_backtest",
    "_cmd_scientist_burn_in",
    "_cmd_scientist_calibration_report",
    "_cmd_scientist_provider_verify",
    "_cmd_scientist_sensitivity_run",
    "_cmd_scientist_stress_test",
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


def _emit_json_output(payload: dict[str, Any], output_path: str | None) -> int:
    rendered = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
    if output_path:
        Path(output_path).write_text(rendered, encoding="utf-8")
        print(f"output={output_path}")
    else:
        print(rendered)
    return 0


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

    cas = build_cli_filesystem_cas(Path(args.cas_root))
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
            import numpy as np

            self._specs = specs
            self._rng = np.random.default_rng(seed)

        def generate(
            self, history: list[Any], current_best: dict[str, Any] | None, context: dict[str, Any]
        ) -> dict[str, Any]:
            del history, current_best, context
            candidate: dict[str, Any] = {"semantic": {"interventions": []}}
            for spec in self._specs:
                candidate[spec.name] = self._rng.uniform(spec.lower_bound, spec.upper_bound)
            return candidate

    def _stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del context
        return {"simulation_results": {"stress_objective": objective_callable(candidate)}}

    cas = build_cli_filesystem_cas(Path(args.cas_root))
    report = search_adversarial.run_stress_test(
        adversarial_plan=plan,
        base_objective=composite_objective,
        stage_b_evaluator=_stage_b,
        candidate_generator=_RandomGenerator(plan.parameter_specs, plan.seed),
        context={},
        cas=cas,
    )

    rendered = json.dumps(
        report.model_dump(mode="json"), ensure_ascii=True, indent=2, sort_keys=True
    )
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"stress_report={args.output}")
    else:
        print(rendered)
    return 0


def _cmd_scientist_provider_verify(args: Any) -> int:
    try:
        _validate_output_extension(args.output, "json")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    from polisyos.scientist.llm import run_gonka_provider_smoke

    try:
        report = asyncio.run(
            run_gonka_provider_smoke(
                model_id=args.model_id,
                base_url=args.base_url,
                verification_dir=args.verification_dir,
                include_web_search_smoke=not bool(args.no_web_search),
            )
        )
    except Exception as exc:
        print(f"ERROR: provider verify failed: {exc}", file=sys.stderr)
        return 1

    payload = report.model_dump(mode="json", exclude_none=True)
    payload["verification_path"] = str(
        Path(args.verification_dir or ".polisyos/provider_verification").resolve()
    )
    return _emit_json_output(payload, args.output)


def _cmd_scientist_agent_smoke(args: Any) -> int:
    return _cmd_scientist_provider_verify(args)


def _cmd_scientist_agent_eval(args: Any) -> int:
    try:
        _validate_output_extension(args.output, "json")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    from polisyos.scientist.agent.eval_harness import run_starter_eval_harness

    try:
        report = asyncio.run(
            run_starter_eval_harness(
                cas_root=args.cas_root,
                include_live_provider=bool(args.live_provider),
                model_id=args.model_id,
                base_url=args.base_url,
                verification_dir=args.verification_dir,
            )
        )
    except Exception as exc:
        print(f"ERROR: agent eval failed: {exc}", file=sys.stderr)
        return 1
    return _emit_json_output(
        report.model_dump(mode="json", exclude_none=True),
        args.output,
    )


def _cmd_scientist_reflexion_replay_eval(args: Any) -> int:
    try:
        _validate_output_extension(args.output, "json")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    from polisyos.scientist.agent.reflexion_evaluator import evaluate_reflexion_replay_cases

    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        cases = payload.get("cases") if isinstance(payload, dict) else payload
        report = evaluate_reflexion_replay_cases(cases or [])
    except Exception as exc:
        print(f"ERROR: reflexion replay eval failed: {exc}", file=sys.stderr)
        return 1
    return _emit_json_output(report.model_dump(mode="json"), args.output)


def _cmd_scientist_burn_in(args: Any) -> int:
    try:
        _validate_output_extension(args.output, args.format)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    search_cold_start = importlib.import_module("polisyos.scientist.search.cold_start")
    search_lessons = importlib.import_module("polisyos.scientist.search.lessons")
    search_sentinels = importlib.import_module("polisyos.scientist.search.sentinels")
    search_stages = importlib.import_module("polisyos.scientist.search.stages")

    try:
        config = search_cold_start.BurnInConfig.model_validate(payload)
    except Exception as exc:
        print(f"ERROR: invalid burn-in config: {exc}", file=sys.stderr)
        return 2

    cas = build_cli_filesystem_cas(Path(args.cas_root))
    tracker = search_stages.CorrelationTracker()
    lesson_registry = search_lessons.LessonRegistry(store=cas)
    sentinel_set = None
    if config.sentinel_set_ref:
        try:
            sentinel_set = search_sentinels.load_sentinel_set(cas, config.sentinel_set_ref)
        except Exception as exc:
            print(f"ERROR: failed to load sentinel set: {exc}", file=sys.stderr)
            return 2

    orchestrator = search_cold_start.build_default_burn_in_orchestrator(
        correlation_tracker=tracker,
        lesson_registry=lesson_registry,
    )
    try:
        report = search_cold_start.run_burn_in(
            orchestrator=orchestrator,
            config=config,
            correlation_tracker=tracker,
            lesson_registry=lesson_registry,
            sentinel_set=sentinel_set,
            store=cas,
        )
    except Exception as exc:
        print(f"ERROR: burn-in failed: {exc}", file=sys.stderr)
        return 1

    report_ref = search_cold_start.persist_burn_in_report(cas, report)
    out_payload = report.model_dump(mode="json")
    out_payload["cas_artifact_id"] = str(report_ref.artifact_id)
    rendered = json.dumps(out_payload, ensure_ascii=True, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"burn_in_report={args.output}")
    else:
        print(rendered)
    return 0


def _cmd_scientist_calibration_report(args: Any) -> int:
    try:
        _validate_output_extension(args.output, args.format)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cas = build_cli_filesystem_cas(Path(args.cas_root))
    search_calibration = importlib.import_module("polisyos.scientist.search.calibration_report")
    search_cold_start = importlib.import_module("polisyos.scientist.search.cold_start")
    search_lessons = importlib.import_module("polisyos.scientist.search.lessons")
    search_sentinels = importlib.import_module("polisyos.scientist.search.sentinels")
    search_stages = importlib.import_module("polisyos.scientist.search.stages")

    tracker = search_stages.CorrelationTracker()
    tracker_ref = payload.get("correlation_tracker_ref")
    if tracker_ref:
        try:
            tracker = search_stages.CorrelationTracker.load_snapshot(cas, tracker_ref)
        except Exception as exc:
            print(f"ERROR: failed to load correlation tracker snapshot: {exc}", file=sys.stderr)
            return 2

    lesson_snapshot = None
    lesson_snapshot_ref = payload.get("lessons_snapshot_ref")
    if lesson_snapshot_ref:
        try:
            lesson_snapshot = search_lessons.LessonRegistry.load_snapshot(cas, lesson_snapshot_ref)
        except Exception as exc:
            print(f"ERROR: failed to load lesson snapshot: {exc}", file=sys.stderr)
            return 2

    sentinel_set = None
    sentinel_set_ref = payload.get("sentinel_set_ref")
    if sentinel_set_ref:
        try:
            sentinel_set = search_sentinels.load_sentinel_set(cas, sentinel_set_ref)
        except Exception as exc:
            print(f"ERROR: failed to load sentinel set: {exc}", file=sys.stderr)
            return 2

    burn_in_report = None
    burn_in_report_ref = payload.get("burn_in_report_ref")
    if burn_in_report_ref:
        try:
            burn_in_report = search_cold_start.load_burn_in_report(cas, burn_in_report_ref)
        except Exception as exc:
            print(f"ERROR: failed to load burn-in report: {exc}", file=sys.stderr)
            return 2

    try:
        report = search_calibration.build_calibration_report(
            correlation_tracker=tracker,
            lesson_registry=lesson_snapshot,
            sentinel_set=sentinel_set,
            burn_in_report=burn_in_report,
        )
    except Exception as exc:
        print(f"ERROR: calibration report build failed: {exc}", file=sys.stderr)
        return 1

    report_ref = search_calibration.persist_funnel_calibration_report(cas, report)
    rendered = search_calibration.render_calibration_report(report, format=args.format)
    if args.format == "json":
        payload_out = json.loads(rendered)
        payload_out["cas_artifact_id"] = str(report_ref.artifact_id)
        rendered = json.dumps(payload_out, ensure_ascii=True, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"calibration_report={args.output}")
    else:
        print(rendered)
    return 0


def _cmd_scientist_backtest(args: Any) -> int:
    try:
        backtesting_cli = importlib.import_module("polisyos.scientist.backtesting.cli")
        code, rendered = cast(
            "tuple[int, str | None]",
            backtesting_cli.run_backtest_command(args),
        )
    except Exception as exc:
        print(f"ERROR: backtest failed: {exc}", file=sys.stderr)
        return 1

    if rendered:
        print(rendered)
    return code
