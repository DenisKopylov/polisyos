"""Public backtesting cli module API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource


def add_backtest_subparser(scientist_sub) -> None:
    """Add backtest subparser helper."""
    parser = scientist_sub.add_parser(
        "backtest",
        help="Run historical validation and generate BacktestReport",
    )
    parser.add_argument("--config", default=None, help="Path to JSON config with plans[]")
    parser.add_argument("--cas-root", default=".polisyos/cas")
    parser.add_argument("--output", "-o", default=None)
    parser.add_argument("--format", choices=["json", "summary", "markdown"], default="json")
    parser.add_argument("--json", action="store_true", help="Alias for --format json")

    # Inline mode for quick single-scenario runs.
    parser.add_argument("--run-id", default=None, help="Scenario id for inline mode")
    parser.add_argument("--historical-data", default=None, help="Path to historical JSON")
    parser.add_argument("--metric", action="append", default=[], help="Target metric (repeatable)")
    parser.add_argument(
        "--ground-truth",
        action="append",
        default=[],
        help="Ground truth as metric=v1,v2,... (repeatable)",
    )
    parser.add_argument("--intervention-step", type=int, default=None)
    parser.add_argument(
        "--prediction-source", choices=[item.value for item in PredictionSource], default="naive"
    )
    parser.add_argument(
        "--predicted",
        action="append",
        default=[],
        help="Predictions as metric=v1,v2,... for prediction_source=provided",
    )


def run_backtest_command(args) -> tuple[int, str]:
    """Run backtest command."""
    plans = _load_plans(args)
    orchestrator = BacktestOrchestrator(cas_root=args.cas_root)
    report = orchestrator.run(plans)

    output_format = "json" if bool(getattr(args, "json", False)) else args.format
    if output_format == "summary":
        rendered = _render_summary(report.model_dump(mode="json"))
    elif output_format == "markdown":
        rendered = _render_markdown(report.model_dump(mode="json"))
    else:
        rendered = report.model_dump_json(indent=2)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        return 0, f"backtest_report={args.output}"
    return 0, rendered


def _load_plans(args) -> list[HistoricalValidationPlan]:
    if args.config:
        payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
        plans_raw = payload.get("plans", payload)
        if not isinstance(plans_raw, list):
            raise ValueError("Backtest config must be a list or an object with plans[]")
        return [HistoricalValidationPlan.model_validate(item) for item in plans_raw]
    return [_build_inline_plan(args)]


def _build_inline_plan(args) -> HistoricalValidationPlan:
    if not args.run_id:
        raise ValueError("Inline mode requires --run-id")
    if not args.historical_data:
        raise ValueError("Inline mode requires --historical-data")
    if not args.metric:
        raise ValueError("Inline mode requires at least one --metric")
    if not args.ground_truth:
        raise ValueError("Inline mode requires --ground-truth metric=v1,v2,...")

    ground_truth = _parse_series_pairs(args.ground_truth)
    predicted = _parse_series_pairs(args.predicted) if args.predicted else None
    target_metrics = [str(item) for item in args.metric]
    return HistoricalValidationPlan(
        plan_id=str(args.run_id),
        plan_label=str(args.run_id),
        historical_data_path=str(args.historical_data),
        intervention_step=args.intervention_step,
        target_metrics=target_metrics,
        ground_truth_outcomes=ground_truth,
        prediction_source=PredictionSource(args.prediction_source),
        predicted_outcomes=predicted,
    )


def _parse_series_pairs(raw_items: list[str]) -> dict[str, list[float]]:
    parsed: dict[str, list[float]] = {}
    for item in raw_items:
        if "=" not in item:
            raise ValueError(f"Invalid series format {item!r}; expected metric=v1,v2,...")
        metric, values_raw = item.split("=", 1)
        values = []
        for token in values_raw.split(","):
            token = token.strip()
            if not token:
                continue
            values.append(float(token))
        parsed[metric.strip()] = values
    return parsed


def _render_summary(payload: dict[str, Any]) -> str:
    lines = [
        f"report_id={payload.get('report_id')}",
        f"n_scenarios={payload.get('n_scenarios')}",
        f"overall_rmse={payload.get('overall_rmse')}",
        f"overall_mae={payload.get('overall_mae')}",
        f"overall_mape={payload.get('overall_mape')}",
        f"overall_coverage_probability={payload.get('overall_coverage_probability')}",
        f"trust_score={payload.get('trust_score')}",
        f"trust_grade={payload.get('trust_grade')}",
        f"cas_artifact_id={payload.get('cas_artifact_id')}",
    ]
    return "\n".join(lines)


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Backtest Report",
        "",
        f"- report_id: `{payload.get('report_id')}`",
        f"- scenarios: `{payload.get('n_scenarios')}`",
        f"- RMSE: `{payload.get('overall_rmse')}`",
        f"- MAE: `{payload.get('overall_mae')}`",
        f"- MAPE: `{payload.get('overall_mape')}`",
        f"- coverage: `{payload.get('overall_coverage_probability')}`",
        f"- trust: `{payload.get('trust_score')}` (`{payload.get('trust_grade')}`)",
        "",
        "## Scenarios",
    ]
    for scenario in payload.get("scenarios", []):
        lines.extend(
            [
                f"- `{scenario.get('scenario_id')}`: rmse={scenario.get('rmse')}, "
                f"mae={scenario.get('mae')}, mape={scenario.get('mape')}, "
                f"coverage={scenario.get('coverage_probability')}",
            ]
        )
    return "\n".join(lines)


__all__ = ["add_backtest_subparser", "run_backtest_command"]
