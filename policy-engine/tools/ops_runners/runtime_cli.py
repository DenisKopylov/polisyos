"""Top-level composition root for the installed ``polisyos`` CLI."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.signing import (
    DEFAULT_IDENTITIES_PATH,
    DEFAULT_REVOKED_DIR,
    DEFAULT_TRUST_DIR,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import ComponentKind
from polisyos.core.components._cli_store import build_cli_filesystem_cas
from polisyos.core.security.rotation import DEFAULT_JWT_TRUST_ANCHORS_PATH

if TYPE_CHECKING:
    from polisyos.ir.analytics.metric_validation_report import MetricValidationReport
    from polisyos.ir.artifacts import ArtifactStore as IrArtifactStore

CommandHandler = Callable[[argparse.Namespace], int]


def _dispatch_core(relative_module: str, handler_name: str, args: argparse.Namespace) -> int:
    module = importlib.import_module(relative_module, package="polisyos.core.components")
    handler = cast("CommandHandler", getattr(module, handler_name))
    return handler(args)


def _cmd_foundry_release_acceptance(args: argparse.Namespace) -> int:
    from polisyos.scientist.governance.blueprint_release import (
        run_verified_ukraine_d5_release,
    )

    manifest_path = Path(args.manifest_path)
    try:
        build_root = manifest_path.resolve().parents[2]
    except IndexError as exc:
        raise ValueError("release manifest path cannot identify the D5 build root") from exc
    report = run_verified_ukraine_d5_release(
        build_root=build_root,
        release_manifest_path=manifest_path,
        runtime_bundle_dir=Path(args.runtime_bundle_dir),
        method_contract_bundle_dir=Path(args.method_contract_bundle_dir),
        cas_root=Path(args.store_root),
    )

    if args.json:
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
        return 0 if report.passed else 1

    print(
        f"passed={report.passed} manifest={report.manifest_path} "
        f"release_bundle_root={report.release_bundle_root}"
    )
    if report.governance_verdict:
        print(f"governance_verdict={report.governance_verdict}")
    if report.release_admissibility_status:
        print(f"release_admissibility_status={report.release_admissibility_status}")
    if report.packet_ref:
        print(f"packet_ref={report.packet_ref}")
    print("\nSteps:")
    for step in report.steps:
        print(f"  {step.step_id}: {step.status}")
    if report.notes:
        print("\nNotes:")
        for note in report.notes:
            print(f"  {note}")
    return 0 if report.passed else 1


def foundry_main(argv: list[str] | None = None) -> int:
    """Compose the Foundry-owned parser with the Scientist release consumer."""

    from polisyos.foundry.methods.cli import main as foundry_cli_main

    return foundry_cli_main(
        argv,
        release_handler=_cmd_foundry_release_acceptance,
    )


def main(argv: list[str] | None = None) -> int:
    """Dispatch the `polisyos` console script and return a process exit code.

    Core command handlers are imported lazily after argument parsing so
    ``--version`` exits early without loading subcommand modules.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--version" in argv:
        sys.stdout.write(f"polisyos {_cli_version()}\n")
        return 0

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "components" and args.components_command == "list":
        return _dispatch_core("._cli_components", "_cmd_components_list", args)
    if args.command == "components" and args.components_command == "bootstrap":
        return _dispatch_core("._cli_components", "_cmd_components_bootstrap", args)
    if args.command == "registry" and args.registry_command == "build":
        return _dispatch_core("._cli_components", "_cmd_registry_build", args)
    if args.command == "scholar" and args.scholar_command == "enrich":
        return _dispatch_core("._cli_scholar", "_cmd_scholar_enrich", args)
    if args.command == "metric-validate":
        return _cmd_metric_validate(args)
    if (
        args.command == "lex"
        and args.lex_command == "normpack"
        and args.lex_normpack_command == "build"
    ):
        return _dispatch_core("._cli_lex", "_cmd_lex_normpack_build", args)
    if args.command == "lex" and args.lex_command == "impact":
        return _dispatch_core("._cli_lex", "_cmd_lex_impact", args)
    if args.command == "scientist" and args.scientist_command == "burn-in":
        return _cmd_scientist_burn_in(args)
    if args.command == "scientist" and args.scientist_command == "calibration-report":
        return _cmd_scientist_calibration_report(args)
    if (
        args.command == "scientist"
        and args.scientist_command == "sensitivity"
        and args.scientist_sensitivity_command == "run"
    ):
        return _cmd_scientist_sensitivity_run(args)
    if args.command == "scientist" and args.scientist_command == "stress-test":
        return _cmd_scientist_stress_test(args)
    if args.command == "scientist" and args.scientist_command == "provider-verify":
        return _cmd_scientist_provider_verify(args)
    if args.command == "scientist" and args.scientist_command == "agent-smoke":
        return _cmd_scientist_agent_smoke(args)
    if args.command == "scientist" and args.scientist_command == "agent-eval":
        return _cmd_scientist_agent_eval(args)
    if args.command == "scientist" and args.scientist_command == "reflexion-replay-eval":
        return _cmd_scientist_reflexion_replay_eval(args)
    if args.command == "scientist" and args.scientist_command == "backtest":
        return _cmd_scientist_backtest(args)
    if args.command == "replay":
        return _dispatch_core("._cli_replay", "_cmd_replay", args)
    if args.command == "resume":
        return _dispatch_core("._cli_replay", "_cmd_resume", args)
    if args.command == "keygen":
        return _dispatch_core("._cli_crypto", "_cmd_keygen", args)
    if args.command == "sign":
        return _dispatch_core("._cli_crypto", "_cmd_sign", args)
    if args.command == "verify":
        return _dispatch_core("._cli_crypto", "_cmd_verify", args)
    if args.command == "audit" and args.audit_command == "export":
        return _dispatch_core("._cli_audit", "_cmd_audit_export", args)
    if args.command == "audit" and args.audit_command == "verify":
        return _dispatch_core("._cli_audit", "_cmd_audit_verify", args)
    if args.command == "audit" and args.audit_command == "runtime-query":
        return _dispatch_core("._cli_audit", "_cmd_audit_runtime_query", args)
    if args.command == "audit" and args.audit_command == "runtime-retention":
        return _dispatch_core("._cli_audit", "_cmd_audit_runtime_retention", args)
    if args.command == "security" and args.security_command == "rotate-jwt":
        return _dispatch_core("._cli_security", "_cmd_security_rotate_jwt", args)
    if args.command == "security" and args.security_command == "rotate-ed25519":
        return _dispatch_core("._cli_security", "_cmd_security_rotate_ed25519", args)

    parser.print_help()
    return 2


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
        objective_module = importlib.import_module("polisyos.scientist.methods.search.objective")
        return objective_module.OptimizationDirection.MINIMIZE

    def evaluate(self, results: dict[str, Any]) -> Any:
        objective_module = importlib.import_module("polisyos.scientist.methods.search.objective")
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
    doe_designs = importlib.import_module("polisyos.scientist.methods.doe.designs")
    doe_sampling = importlib.import_module("polisyos.scientist.methods.doe.sampling")
    doe_analysis = importlib.import_module("polisyos.scientist.methods.doe.analysis")

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
    doe_designs = importlib.import_module("polisyos.scientist.methods.doe.designs")
    search_objective = importlib.import_module("polisyos.scientist.methods.search.objective")
    search_adversarial = importlib.import_module("polisyos.scientist.methods.search.adversarial")

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

    from polisyos.scientist.orchestration.llm import run_gonka_provider_smoke

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
    search_cold_start = importlib.import_module("polisyos.scientist.methods.search.cold_start")
    search_lessons = importlib.import_module("polisyos.scientist.methods.search.lessons")
    search_sentinels = importlib.import_module("polisyos.scientist.methods.search.sentinels")
    search_stages = importlib.import_module("polisyos.scientist.methods.search.stages")

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
    search_calibration = importlib.import_module("polisyos.scientist.methods.search.calibration_report")
    search_cold_start = importlib.import_module("polisyos.scientist.methods.search.cold_start")
    search_lessons = importlib.import_module("polisyos.scientist.methods.search.lessons")
    search_sentinels = importlib.import_module("polisyos.scientist.methods.search.sentinels")
    search_stages = importlib.import_module("polisyos.scientist.methods.search.stages")

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
        backtesting_cli = importlib.import_module("polisyos.scientist.methods.backtesting.cli")
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


def _cmd_metric_validate(args: argparse.Namespace) -> int:
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.components._cli_store import build_cli_artifact_store
    from polisyos.core.contracts.foundry import MetricObservationBundleRef
    from polisyos.ir.analytics.metric_validation_report import persist_metric_validation_report
    from polisyos.scientist.validation.metrics import (
        TestConfig,
        compare_metric_family,
        load_metric_observation_bundle,
    )

    store = build_cli_artifact_store(Path(args.cas_root))
    ref = MetricObservationBundleRef(
        artifact_id=ArtifactID.model_validate(_normalize_artifact_id(args.observation_bundle_ref)),
        kind="foundry.metric_observation_bundle",
        media_type="application/json",
    )
    try:
        bundle = load_metric_observation_bundle(cast("IrArtifactStore", store), ref)
    except Exception as exc:
        print(f"ERROR: failed to load observation bundle: {exc}", file=sys.stderr)
        return 2

    try:
        report = compare_metric_family(
            bundle=bundle,
            baseline_model_id=args.baseline,
            candidate_model_ids=list(args.candidates),
            metric_ids=list(args.metrics),
            config=TestConfig(
                alpha=args.alpha,
                alternative=args.alternative,
                n_resamples=args.n_resamples,
                confidence_level=args.confidence_level,
                correction=args.correction,
                random_seed=args.random_seed,
                exact_if_feasible=bool(args.exact_if_feasible),
            ),
            family_scope=args.family_scope,
        )
    except Exception as exc:
        print(f"ERROR: metric validation failed: {exc}", file=sys.stderr)
        return 1

    report_ref = persist_metric_validation_report(
        cast("IrArtifactStore", store),
        report,
    )
    payload = _render_metric_validation_payload(
        report,
        report_ref.artifact_id.root,
        args.format,
    )
    rendered = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"metric_validation_report={args.output}")
    else:
        print(rendered)
    return 0


def _normalize_artifact_id(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("sha256:"):
        return normalized
    return f"sha256:{normalized}"


def _render_metric_validation_payload(
    report: MetricValidationReport,
    artifact_id: str,
    format_name: str,
) -> dict[str, Any]:
    if format_name == "json":
        payload = report.model_dump(mode="json")
        payload["cas_artifact_id"] = artifact_id
        return payload
    if format_name == "avro-json":
        payload = report.model_dump(mode="json")
        payload["avro_schema"] = "polisyos.scientist.metric_validation_report"
        payload["cas_artifact_id"] = artifact_id
        return payload
    if format_name == "proto-json":
        payload = cast("dict[str, Any]", _camelize_keys(report.model_dump(mode="json")))
        payload["casArtifactId"] = artifact_id
        return payload
    return _summary_metric_validation_payload(report, artifact_id)


def _summary_metric_validation_payload(
    report: MetricValidationReport,
    artifact_id: str,
) -> dict[str, Any]:
    improvements: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    for comparison in report.comparisons:
        significance = comparison.significance
        is_significant = (
            significance.reject_null_adj
            if significance.reject_null_adj is not None
            else significance.reject_null_raw
        )
        if not is_significant:
            continue
        item = {
            "baseline": comparison.baseline_model_id,
            "candidate": comparison.candidate_model_id,
            "metric": comparison.metric_id,
            "delta": comparison.delta_value,
            "p_adj": significance.p_value_adj,
        }
        if _is_metric_improvement(comparison.metric_direction, comparison.delta_value):
            improvements.append(item)
        else:
            regressions.append(item)
    return {
        "family_method": report.family_adjustment.method,
        "alpha": report.family_adjustment.alpha,
        "comparison_count": len(report.comparisons),
        "significant_improvements": improvements,
        "significant_regressions": regressions,
        "cas_artifact_id": artifact_id,
    }


def _is_metric_improvement(metric_direction: str, delta_value: float) -> bool:
    if metric_direction == "lower_is_better":
        return delta_value < 0.0
    return delta_value > 0.0


def _camelize_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {_snake_to_camel(key): _camelize_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_camelize_keys(item) for item in value]
    return value


def _snake_to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="polisyos")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_cli_version()}",
    )

    components = parser.add_subparsers(dest="command")

    cmd_components = components.add_parser("components")
    components_sub = cmd_components.add_subparsers(dest="components_command")
    list_parser = components_sub.add_parser("list")
    list_parser.add_argument("--kind", choices=[kind.value for kind in ComponentKind], default=None)
    list_parser.add_argument("--domain", default=None)
    list_parser.add_argument("--jurisdiction", default=None)
    list_parser.add_argument("--tag", default=None)
    list_parser.add_argument("--json", action="store_true")
    list_parser.add_argument("--dev-scan-path", action="append", default=[])

    bootstrap_parser = components_sub.add_parser("bootstrap")
    bootstrap_parser.add_argument("--group", action="append", default=[])
    bootstrap_parser.add_argument("--dev-scan-path", action="append", default=[])
    bootstrap_parser.add_argument("--no-dev-scan", action="store_true")
    bootstrap_parser.add_argument("--skip-connectors", action="store_true")
    bootstrap_parser.add_argument("--skip-methods", action="store_true")
    bootstrap_parser.add_argument("--skip-evaluators", action="store_true")
    bootstrap_parser.add_argument("--skip-extractors", action="store_true")
    bootstrap_parser.add_argument("--skip-providers", action="store_true")
    bootstrap_parser.add_argument("--skip-nodes", action="store_true")
    bootstrap_parser.add_argument("--json", action="store_true")

    cmd_registry = components.add_parser("registry")
    registry_sub = cmd_registry.add_subparsers(dest="registry_command")
    build_registry = registry_sub.add_parser("build")
    build_registry.add_argument("--domain", required=True)
    build_registry.add_argument("--jurisdiction", default=None)
    build_registry.add_argument("--cas-root", default=".polisyos/cas")
    build_registry.add_argument("--dev-scan-path", action="append", default=[])

    cmd_scholar = components.add_parser("scholar")
    scholar_sub = cmd_scholar.add_subparsers(dest="scholar_command")
    enrich = scholar_sub.add_parser("enrich")
    enrich.add_argument("--intent", required=True)
    enrich.add_argument("--cas-root", default=".polisyos/cas")
    enrich.add_argument("--fact-log-root", default=".polisyos/facts")

    metric_validate = components.add_parser("metric-validate")
    metric_validate.add_argument(
        "--observation-bundle-ref",
        required=True,
        help="Observation bundle artifact id (sha256:<hex> or <hex>)",
    )
    metric_validate.add_argument("--baseline", required=True, help="Baseline model id")
    metric_validate.add_argument(
        "--candidates",
        nargs="+",
        required=True,
        help="Candidate model ids to compare against the baseline",
    )
    metric_validate.add_argument(
        "--metrics",
        nargs="+",
        required=True,
        help="Metric ids to validate (e.g. roc_auc accuracy log_loss f1)",
    )
    metric_validate.add_argument("--alpha", type=float, default=0.05)
    metric_validate.add_argument(
        "--alternative",
        choices=["two-sided", "greater", "less"],
        default="two-sided",
    )
    metric_validate.add_argument("--n-resamples", type=int, default=20_000)
    metric_validate.add_argument("--confidence-level", type=float, default=0.95)
    metric_validate.add_argument(
        "--correction",
        choices=[
            "none",
            "bonferroni",
            "holm",
            "bh",
            "by",
            "westfall_young_maxT",
            "westfall_young_minP",
        ],
        default="holm",
    )
    metric_validate.add_argument(
        "--family-scope",
        choices=["per_candidate", "per_metric", "all_pairs_all_metrics"],
        default="all_pairs_all_metrics",
    )
    metric_validate.add_argument("--random-seed", type=int, default=None)
    metric_validate.add_argument("--exact-if-feasible", action="store_true", default=True)
    metric_validate.add_argument(
        "--format",
        choices=["summary-json", "json", "avro-json", "proto-json"],
        default="summary-json",
    )
    metric_validate.add_argument("--output", default=None)
    metric_validate.add_argument("--cas-root", default=".polisyos/cas")

    cmd_lex = components.add_parser("lex")
    lex_sub = cmd_lex.add_subparsers(dest="lex_command")
    normpack = lex_sub.add_parser("normpack")
    normpack_sub = normpack.add_subparsers(dest="lex_normpack_command")
    build_normpack = normpack_sub.add_parser("build")
    build_normpack.add_argument("--jurisdiction", required=True)
    build_normpack.add_argument("--domain", default=None)
    build_normpack.add_argument("--as-of", default=datetime.now(UTC).date().isoformat())
    build_normpack.add_argument("--cas-root", default=".polisyos/cas")
    build_normpack.add_argument("--fact-log-root", default=".polisyos/facts")

    impact = lex_sub.add_parser("impact")
    impact.add_argument("old_ref", help="Old NormPack artifact id or JSON file path")
    impact.add_argument("new_ref", help="New NormPack artifact id or JSON file path")
    impact.add_argument("--passes", default="legal,safety")
    impact.add_argument("--profile", choices=["fast", "mvp", "strict"], default="strict")
    impact.add_argument("--format", choices=["json", "md"], default="md")
    impact.add_argument("--output", default=None)
    impact.add_argument("--cas-root", default=".polisyos/cas")

    cmd_scientist = components.add_parser("scientist")
    scientist_sub = cmd_scientist.add_subparsers(dest="scientist_command")

    burn_in = scientist_sub.add_parser("burn-in")
    burn_in.add_argument("--config", required=True, help="JSON config path")
    burn_in.add_argument("--output", default=None)
    burn_in.add_argument("--format", choices=["json"], default="json")
    burn_in.add_argument("--cas-root", default=".polisyos/cas")

    calibration_report = scientist_sub.add_parser("calibration-report")
    calibration_report.add_argument("--config", required=True, help="JSON config path")
    calibration_report.add_argument("--output", default=None)
    calibration_report.add_argument("--format", choices=["json", "md"], default="md")
    calibration_report.add_argument("--cas-root", default=".polisyos/cas")

    sensitivity = scientist_sub.add_parser("sensitivity")
    sensitivity_sub = sensitivity.add_subparsers(dest="scientist_sensitivity_command")
    sensitivity_run = sensitivity_sub.add_parser("run")
    sensitivity_run.add_argument("--config", required=True, help="JSON config path")
    sensitivity_run.add_argument("--output", default=None)
    sensitivity_run.add_argument("--format", choices=["json"], default="json")
    sensitivity_run.add_argument("--cas-root", default=".polisyos/cas")

    stress_test = scientist_sub.add_parser("stress-test")
    stress_test.add_argument("--config", required=True, help="JSON config path")
    stress_test.add_argument("--output", default=None)
    stress_test.add_argument("--format", choices=["json"], default="json")
    stress_test.add_argument("--cas-root", default=".polisyos/cas")

    provider_verify = scientist_sub.add_parser("provider-verify")
    provider_verify.add_argument(
        "--model-id",
        default="qwen/qwen3-235b-a22b-instruct-2507-fp8",
    )
    provider_verify.add_argument(
        "--base-url",
        default="https://api.gonkagate.com/v1",
    )
    provider_verify.add_argument(
        "--verification-dir",
        default=".polisyos/provider_verification",
    )
    provider_verify.add_argument("--no-web-search", action="store_true")
    provider_verify.add_argument("--output", default=None)
    provider_verify.add_argument("--format", choices=["json"], default="json")

    agent_smoke = scientist_sub.add_parser("agent-smoke")
    agent_smoke.add_argument(
        "--model-id",
        default="qwen/qwen3-235b-a22b-instruct-2507-fp8",
    )
    agent_smoke.add_argument(
        "--base-url",
        default="https://api.gonkagate.com/v1",
    )
    agent_smoke.add_argument(
        "--verification-dir",
        default=".polisyos/provider_verification",
    )
    agent_smoke.add_argument("--no-web-search", action="store_true")
    agent_smoke.add_argument("--output", default=None)
    agent_smoke.add_argument("--format", choices=["json"], default="json")

    agent_eval = scientist_sub.add_parser("agent-eval")
    agent_eval.add_argument("--cas-root", default=".polisyos/cas")
    agent_eval.add_argument(
        "--model-id",
        default="qwen/qwen3-235b-a22b-instruct-2507-fp8",
    )
    agent_eval.add_argument(
        "--base-url",
        default="https://api.gonkagate.com/v1",
    )
    agent_eval.add_argument(
        "--verification-dir",
        default=".polisyos/provider_verification",
    )
    agent_eval.add_argument("--live-provider", action="store_true")
    agent_eval.add_argument("--output", default=None)
    agent_eval.add_argument("--format", choices=["json"], default="json")

    reflexion_replay_eval = scientist_sub.add_parser("reflexion-replay-eval")
    reflexion_replay_eval.add_argument("--input", required=True, help="JSON file with replay cases")
    reflexion_replay_eval.add_argument("--output", default=None)
    reflexion_replay_eval.add_argument("--format", choices=["json"], default="json")

    backtesting_cli = importlib.import_module("polisyos.scientist.methods.backtesting.cli")
    backtesting_cli.add_backtest_subparser(scientist_sub)

    cmd_replay = components.add_parser("replay")
    cmd_replay.add_argument("packet_ref", help="DecisionPacket ref (sha256:<hex> or <hex>)")
    cmd_replay.add_argument("--cas-root", default=".polisyos/cas", help="CAS root directory")
    cmd_replay.add_argument(
        "--mode",
        choices=["bit_exact", "ci_bounded", "skip"],
        default="bit_exact",
        help="Verification mode",
    )
    cmd_replay.add_argument(
        "--strategy",
        choices=["auto", "foundry", "scientist"],
        default="auto",
        help="Replay execution strategy",
    )
    cmd_replay.add_argument(
        "--check-only",
        action="store_true",
        help="Only run dependency completeness checks",
    )
    cmd_replay.add_argument(
        "--export",
        default=None,
        metavar="PATH",
        help="Export replay subgraph to tar.gz archive",
    )
    cmd_replay.add_argument(
        "--bundle",
        default=None,
        metavar="PATH",
        help="Import replay bundle from archive/directory and run against it",
    )
    cmd_replay.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip verification after replay execution",
    )
    cmd_replay.add_argument(
        "--tolerance",
        type=float,
        default=1e-6,
        help="Relative tolerance for ci_bounded mode",
    )
    cmd_replay.add_argument(
        "--confidence-level",
        type=float,
        default=0.95,
        help="Confidence level for ci_bounded reports",
    )
    cmd_replay.add_argument("--json", action="store_true")

    cmd_resume = components.add_parser("resume")
    cmd_resume.add_argument("run_id", help="Run ID to resume (e.g. R_abc123)")
    cmd_resume.add_argument("--cas-root", default=".polisyos/cas", help="CAS root directory")
    cmd_resume.add_argument(
        "--checkpoint-policy",
        choices=["off", "strict", "best_effort"],
        default="strict",
        help="Checkpoint persistence policy during resumed execution",
    )
    cmd_resume.add_argument(
        "--force",
        action="store_true",
        help="Attempt resume even if run lock metadata suggests another holder",
    )
    cmd_resume.add_argument(
        "--dry-run", action="store_true", help="Only inspect checkpoint metadata"
    )
    cmd_resume.add_argument("--json", action="store_true")

    cmd_keygen = components.add_parser("keygen")
    cmd_keygen.add_argument(
        "--output",
        default="~/.polisyos/keys/polisyos-signing",
        help="Base output path (without extension). Writes .pem and .pub files.",
    )
    cmd_keygen.add_argument("--name", default=None, help="Signer identity label")
    cmd_keygen.add_argument("--force", action="store_true", help="Overwrite existing key files")
    cmd_keygen.add_argument(
        "--public-only",
        action="store_true",
        help="Print generated public key to stdout without writing files",
    )
    cmd_keygen.add_argument("--json", action="store_true")

    cmd_sign = components.add_parser("sign")
    cmd_sign.add_argument("artifact_ref", nargs="?", help="Artifact ref (sha256:<hex> or <hex>)")
    cmd_sign.add_argument("--all", action="store_true", help="Sign all artifacts in CAS")
    cmd_sign.add_argument("--cas-root", default=".polisyos/cas", help="CAS root directory")
    cmd_sign.add_argument("--key", default=None, help="Path to private Ed25519 key (PEM)")
    cmd_sign.add_argument("--identity", default=None, help="Signer identity hint")
    cmd_sign.add_argument("--workers", type=int, default=8, help="Workers for --all")
    cmd_sign.add_argument(
        "--resign",
        action="store_true",
        help="Re-sign already signed artifacts when used with --all",
    )
    cmd_sign.add_argument("--json", action="store_true")

    cmd_verify = components.add_parser("verify")
    cmd_verify.add_argument("artifact_ref", nargs="?", help="Artifact ref (sha256:<hex> or <hex>)")
    cmd_verify.add_argument("--all", action="store_true", help="Verify all artifacts in CAS")
    cmd_verify.add_argument("--cas-root", default=".polisyos/cas", help="CAS root directory")
    cmd_verify.add_argument(
        "--public-key",
        action="append",
        default=[],
        help="Explicit trusted public key PEM path (repeatable)",
    )
    cmd_verify.add_argument(
        "--trust-dir",
        default=str(DEFAULT_TRUST_DIR),
        help="Directory containing trusted public keys (*.pub)",
    )
    cmd_verify.add_argument(
        "--revoked-dir",
        default=str(DEFAULT_REVOKED_DIR),
        help="Directory containing revoked public keys (*.pub)",
    )
    cmd_verify.add_argument(
        "--identities",
        default=str(DEFAULT_IDENTITIES_PATH),
        help="JSON mapping key_id->identity for identity binding checks",
    )
    cmd_verify.add_argument("--workers", type=int, default=8, help="Workers for --all")
    cmd_verify.add_argument("--json", action="store_true")
    cmd_verify.add_argument("--quiet", action="store_true")
    cmd_verify.add_argument("--fail-unsigned", action="store_true")
    cmd_verify.add_argument("--strict-identity", action="store_true")

    cmd_audit = components.add_parser("audit")
    audit_sub = cmd_audit.add_subparsers(dest="audit_command")

    audit_export = audit_sub.add_parser("export")
    audit_export.add_argument("run_id")
    audit_export.add_argument("--cas-root", default=".polisyos/cas", help="CAS root directory")
    audit_export.add_argument(
        "--runs-dir",
        default=".polisyos/runs",
        help="Run manifests directory",
    )
    audit_export.add_argument("--output", "-o", default=None, help="Output archive path")
    audit_export.add_argument(
        "--profile",
        choices=["full", "manifests_only"],
        default="full",
        help="Export profile",
    )
    audit_export.add_argument(
        "--exclude-kinds",
        default="",
        help="Comma-separated artifact kinds to exclude",
    )
    audit_export.add_argument(
        "--signing-policy",
        choices=["strict", "warn", "skip"],
        default="warn",
    )
    audit_export.add_argument(
        "--slsa-mode",
        choices=["off", "local", "private", "public"],
        default=None,
        help="SLSA mode override (default comes from environment)",
    )
    audit_export.add_argument(
        "--slsa-policy",
        choices=["best_effort", "required"],
        default=None,
        help="SLSA policy override (default comes from environment)",
    )
    audit_export.add_argument(
        "--no-visualization",
        action="store_true",
    )
    audit_export.add_argument("--json", action="store_true")

    audit_verify = audit_sub.add_parser("verify")
    audit_verify.add_argument("package", help="Path to audit package file or directory")
    audit_verify.add_argument(
        "--trusted-key",
        action="append",
        default=[],
        help="Trusted public key path (repeatable)",
    )
    audit_verify.add_argument(
        "--trusted-keys-dir",
        default=None,
        help="Directory with trusted PEM keys",
    )
    audit_verify.add_argument(
        "--allow-package-keys",
        action="store_true",
        help="Treat package keys as trusted (not recommended)",
    )
    audit_verify.add_argument(
        "--fail-unsigned",
        action="store_true",
        help="Fail verification when unsigned artifacts are present",
    )
    audit_verify.add_argument(
        "--require-slsa",
        action="store_true",
        help="Fail verification if SLSA evidence is missing or invalid",
    )
    audit_verify.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Report format",
    )
    audit_verify.add_argument("--output", "-o", default=None, help="Report output path")
    audit_verify.add_argument("--json", action="store_true")

    audit_runtime_query = audit_sub.add_parser("runtime-query")
    audit_runtime_query.add_argument("--cas-root", default=".polisyos/cas")
    audit_runtime_query.add_argument(
        "--stream",
        choices=["access", "mutation", "all"],
        default="all",
    )
    audit_runtime_query.add_argument("--tenant-id", default=None)
    audit_runtime_query.add_argument("--actor", default=None)
    audit_runtime_query.add_argument("--resource-id", default=None)
    audit_runtime_query.add_argument("--endpoint", default=None)
    audit_runtime_query.add_argument("--operation", default=None)
    audit_runtime_query.add_argument("--outcome", default=None)
    audit_runtime_query.add_argument("--since", default=None)
    audit_runtime_query.add_argument("--until", default=None)
    audit_runtime_query.add_argument("--output", "-o", default=None)
    audit_runtime_query.add_argument(
        "--format",
        choices=["json", "jsonl", "csv"],
        default="json",
    )
    audit_runtime_query.add_argument("--json", action="store_true")

    audit_runtime_retention = audit_sub.add_parser("runtime-retention")
    audit_runtime_retention.add_argument("--cas-root", default=".polisyos/cas")
    audit_runtime_retention.add_argument("--retention-days", type=int, required=True)
    audit_runtime_retention.add_argument("--archive-dir", default=None)
    audit_runtime_retention.add_argument("--dry-run", action="store_true")
    audit_runtime_retention.add_argument("--json", action="store_true")

    cmd_security = components.add_parser("security")
    security_sub = cmd_security.add_subparsers(dest="security_command")

    rotate_jwt = security_sub.add_parser("rotate-jwt")
    rotate_jwt.add_argument("--manifest", default=str(DEFAULT_JWT_TRUST_ANCHORS_PATH))
    rotate_jwt.add_argument("--issuer", required=True)
    rotate_jwt.add_argument("--jwks-uri", required=True)
    rotate_jwt.add_argument("--audience", required=True)
    rotate_jwt.add_argument("--active-kid", action="append", default=[])
    rotate_jwt.add_argument("--next-kid", action="append", default=[])
    rotate_jwt.add_argument("--retire-kid", action="append", default=[])
    rotate_jwt.add_argument("--revoke-kid", action="append", default=[])
    rotate_jwt.add_argument("--rotated-by", default=None)
    rotate_jwt.add_argument("--json", action="store_true")

    rotate_ed = security_sub.add_parser("rotate-ed25519")
    rotate_ed.add_argument("--output", required=True, help="Base output path for .pem/.pub")
    rotate_ed.add_argument("--identity", required=True)
    rotate_ed.add_argument("--trust-dir", default=str(DEFAULT_TRUST_DIR))
    rotate_ed.add_argument("--revoked-dir", default=str(DEFAULT_REVOKED_DIR))
    rotate_ed.add_argument("--identities", default=str(DEFAULT_IDENTITIES_PATH))
    rotate_ed.add_argument("--revoke-public-key", action="append", default=[])
    rotate_ed.add_argument("--force", action="store_true")
    rotate_ed.add_argument("--json", action="store_true")

    return parser


def _cli_version() -> str:
    try:
        return version("policy-engine")
    except PackageNotFoundError:
        return "0+unknown"


__all__ = ["foundry_main", "main"]


if __name__ == "__main__":  # pragma: no cover - CLI execution path
    raise SystemExit(main())
