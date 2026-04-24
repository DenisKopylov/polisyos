"""Reporting: JSON artifact + Markdown + LaTeX publication tables."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import numpy as np

from benchmarks.honest_comparison.metrics import AggregatedMetrics, PairwiseTestResult


def _ser(obj: Any) -> Any:
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _ser(getattr(obj, k)) for k in obj.__dataclass_fields__}
    return obj


def build_json_report(
    metrics_by_tier: dict[str, list[AggregatedMetrics]],
    pairwise_by_tier: dict[str, list[PairwiseTestResult]],
    fairness_manifests: dict[str, str],
    env_snapshot: dict[str, Any],
) -> str:
    """Build the full JSON report artifact."""
    report = {
        "benchmark": "honest_head_to_head",
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": env_snapshot,
        "fairness_manifests": {k: json.loads(v) for k, v in fairness_manifests.items()},
        "results": {},
        "pairwise_tests": {},
    }

    for tier_name, metrics_list in metrics_by_tier.items():
        report["results"][tier_name] = [_ser(m) for m in metrics_list]

    for tier_name, tests in pairwise_by_tier.items():
        report["pairwise_tests"][tier_name] = [_ser(t) for t in tests]

    return json.dumps(report, indent=2, default=_ser)


def build_markdown_table(
    metrics_list: list[AggregatedMetrics],
    tier_name: str,
    dataset_name: str,
) -> str:
    """Build a publication-style Markdown table for one tier+dataset."""
    # Filter for this dataset
    rows = [m for m in metrics_list if m.dataset_name == dataset_name]
    if not rows:
        return f"No results for {tier_name}/{dataset_name}\n"

    # Find best RMSE
    valid_rmse = [(m.method_name, m.ate_rmse) for m in rows if not np.isnan(m.ate_rmse)]
    best_method = min(valid_rmse, key=lambda x: x[1])[0] if valid_rmse else None

    lines = [
        f"## Tier {tier_name} — {dataset_name}",
        "",
        "| Method | Library | ATE RMSE (SE) | Coverage | CI Width | PEHE (SE) | Time (s) | Fail% |",
        "|--------|---------|---------------|----------|----------|-----------|----------|-------|",
    ]

    for m in sorted(rows, key=lambda r: r.ate_rmse if not np.isnan(r.ate_rmse) else 1e9):
        rmse_str = f"{m.ate_rmse:.4f} ({m.ate_rmse_se:.4f})" if not np.isnan(m.ate_rmse) else "—"
        if m.method_name == best_method:
            rmse_str = f"**{rmse_str}**"

        cov_str = f"{m.ci_coverage:.3f}" if not np.isnan(m.ci_coverage) else "—"
        width_str = f"{m.ci_width_mean:.3f}" if not np.isnan(m.ci_width_mean) else "—"
        pehe_str = f"{m.pehe:.4f} ({m.pehe_se:.4f})" if m.pehe is not None else "—"
        time_str = f"{m.wall_time_mean:.2f}" if not np.isnan(m.wall_time_mean) else "—"
        fail_str = f"{m.failure_rate * 100:.1f}" if not np.isnan(m.failure_rate) else "—"

        lib = m.method_name.split("_")[0] if "_" in m.method_name else "—"
        lines.append(
            f"| {m.method_name} | {lib} | {rmse_str} | {cov_str} | {width_str} | {pehe_str} | {time_str} | {fail_str} |"
        )

    lines.append("")
    return "\n".join(lines)


def build_latex_table(
    metrics_list: list[AggregatedMetrics],
    tier_name: str,
    dataset_name: str,
) -> str:
    """Build LaTeX table for publication."""
    rows = [m for m in metrics_list if m.dataset_name == dataset_name]
    if not rows:
        return ""

    valid_rmse = [(m.method_name, m.ate_rmse) for m in rows if not np.isnan(m.ate_rmse)]
    best_method = min(valid_rmse, key=lambda x: x[1])[0] if valid_rmse else None

    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        f"\\caption{{Tier {tier_name} — {dataset_name}}}",
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        r"Method & ATE RMSE (SE) & Coverage & CI Width & PEHE (SE) & Time (s) & Fail\% \\",
        r"\midrule",
    ]

    for m in sorted(rows, key=lambda r: r.ate_rmse if not np.isnan(r.ate_rmse) else 1e9):
        rmse_str = f"{m.ate_rmse:.4f} ({m.ate_rmse_se:.4f})" if not np.isnan(m.ate_rmse) else "---"
        if m.method_name == best_method:
            rmse_str = f"\\textbf{{{rmse_str}}}"

        cov_str = f"{m.ci_coverage:.3f}" if not np.isnan(m.ci_coverage) else "---"
        width_str = f"{m.ci_width_mean:.3f}" if not np.isnan(m.ci_width_mean) else "---"
        pehe_str = f"{m.pehe:.4f} ({m.pehe_se:.4f})" if m.pehe is not None else "---"
        time_str = f"{m.wall_time_mean:.2f}" if not np.isnan(m.wall_time_mean) else "---"
        fail_str = f"{m.failure_rate * 100:.1f}" if not np.isnan(m.failure_rate) else "---"

        name_escaped = m.method_name.replace("_", r"\_")
        lines.append(
            f"{name_escaped} & {rmse_str} & {cov_str} & {width_str} & {pehe_str} & {time_str} & {fail_str} \\\\"
        )

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines)


def build_tier_comparison_table(
    all_metrics: dict[str, list[AggregatedMetrics]],
    dataset_name: str,
) -> str:
    """Show how rankings change across tiers for a given dataset."""
    lines = [
        f"## Tier Comparison — {dataset_name}",
        "",
        "| Method | Tier A Rank | Tier B Rank | Tier C Rank | Interpretation |",
        "|--------|-------------|-------------|-------------|----------------|",
    ]

    # Collect rankings per tier
    rankings: dict[str, dict[str, int]] = {}
    for tier_name, metrics_list in all_metrics.items():
        tier_rows = [
            m for m in metrics_list if m.dataset_name == dataset_name and not np.isnan(m.ate_rmse)
        ]
        tier_rows.sort(key=lambda r: r.ate_rmse)
        for rank, m in enumerate(tier_rows, 1):
            rankings.setdefault(m.method_name, {})[tier_name] = rank

    for method, tier_ranks in sorted(rankings.items()):
        rank_a = str(tier_ranks.get("A", "—"))
        rank_b = str(tier_ranks.get("B", "—"))
        rank_c = str(tier_ranks.get("C", "—"))

        # Simple interpretation
        interp = ""
        if all(r == "—" for r in [rank_a, rank_b, rank_c]):
            interp = "insufficient data"
        lines.append(f"| {method} | {rank_a} | {rank_b} | {rank_c} | {interp} |")

    lines.append("")
    return "\n".join(lines)
