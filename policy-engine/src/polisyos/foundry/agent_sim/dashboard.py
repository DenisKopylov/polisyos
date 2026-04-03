"""Public agent sim dashboard module API."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jax.numpy as jnp


@dataclass
class DashboardConfig:
    """Configure output path and refresh settings for the HTML training dashboard."""
    title: str = "PolisyOS Training Dashboard"
    output_path: Path = Path("./dashboard.html")
    refresh_interval: int = 5
    theme: str = "plotly_dark"


class DashboardGenerator:
    """Render an HTML dashboard from collected training and policy metrics."""
    def __init__(self, config: DashboardConfig | None = None):
        self.config = config or DashboardConfig()

    def generate(
        self,
        metrics: dict[str, Any],
        states: list[dict] | None = None,
        config: dict | None = None,
    ) -> str:
        del states, config
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError as exc:
            raise ImportError("plotly required: pip install plotly") from exc

        fig = make_subplots(
            rows=3,
            cols=2,
            subplot_titles=(
                "Training Loss",
                "Rewards",
                "Wealth Distribution",
                "Gini Coefficient",
                "GDP Over Time",
                "Policy Parameters",
            ),
            specs=[
                [{"type": "scatter"}, {"type": "scatter"}],
                [{"type": "histogram"}, {"type": "scatter"}],
                [{"type": "scatter"}, {"type": "bar"}],
            ],
        )

        if "loss_history" in metrics:
            losses = metrics["loss_history"]
            fig.add_trace(
                go.Scatter(y=losses, mode="lines", name="Loss", line=dict(color="red")),
                row=1,
                col=1,
            )

        if "reward_history" in metrics:
            rewards = metrics["reward_history"]
            fig.add_trace(
                go.Scatter(
                    y=rewards, mode="lines", name="Reward", line=dict(color="green")
                ),
                row=1,
                col=2,
            )

        if "final_wealth" in metrics:
            wealth = metrics["final_wealth"]
            fig.add_trace(
                go.Histogram(x=wealth, name="Wealth", marker_color="steelblue"),
                row=2,
                col=1,
            )

        if "gini_history" in metrics:
            gini = metrics["gini_history"]
            fig.add_trace(
                go.Scatter(y=gini, mode="lines", name="Gini", line=dict(color="purple")),
                row=2,
                col=2,
            )

        if "gdp_history" in metrics:
            gdp = metrics["gdp_history"]
            fig.add_trace(
                go.Scatter(y=gdp, mode="lines", name="GDP", line=dict(color="orange")),
                row=3,
                col=1,
            )

        if "policy_params" in metrics:
            params = metrics["policy_params"]
            fig.add_trace(
                go.Bar(
                    x=list(params.keys()),
                    y=list(params.values()),
                    name="Policy",
                    marker_color="teal",
                ),
                row=3,
                col=2,
            )

        fig.update_layout(
            height=900,
            title_text=self.config.title,
            template=self.config.theme,
            showlegend=True,
        )

        fig.write_html(self.config.output_path)
        return str(self.config.output_path)

    def generate_comparison_dashboard(
        self,
        experiments: dict[str, dict],
        metrics_to_compare: list[str],
    ) -> str:
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError as exc:
            raise ImportError("plotly required") from exc

        n_metrics = len(metrics_to_compare)
        fig = make_subplots(
            rows=(n_metrics + 1) // 2,
            cols=2,
            subplot_titles=metrics_to_compare,
        )

        colors = ["red", "blue", "green", "orange", "purple", "brown"]

        for i, metric in enumerate(metrics_to_compare):
            row = i // 2 + 1
            col = i % 2 + 1

            for j, (exp_name, exp_metrics) in enumerate(experiments.items()):
                if metric in exp_metrics:
                    values = exp_metrics[metric]
                    if isinstance(values, (list, tuple, jnp.ndarray)):
                        fig.add_trace(
                            go.Scatter(
                                y=values,
                                mode="lines",
                                name=f"{exp_name}",
                                line=dict(color=colors[j % len(colors)]),
                                legendgroup=exp_name,
                                showlegend=(i == 0),
                            ),
                            row=row,
                            col=col,
                        )

        fig.update_layout(
            height=400 * ((n_metrics + 1) // 2),
            title_text="Experiment Comparison",
            template=self.config.theme,
        )

        output_path = self.config.output_path.parent / "comparison_dashboard.html"
        fig.write_html(output_path)
        return str(output_path)

    def generate_report(
        self,
        experiment_result: dict,
        output_format: str = "html",
    ) -> str:
        report_lines = [
            "# Experiment Report",
            "",
            "## Configuration",
            "```json",
            f"{experiment_result.get('config', {})}",
            "```",
            "",
            "## Results Summary",
            "",
        ]

        metrics = experiment_result.get("metrics", {})
        for name, value in metrics.items():
            if isinstance(value, (int, float)):
                report_lines.append(f"- **{name}**: {value:.4f}")
            elif isinstance(value, (list, jnp.ndarray)):
                if isinstance(value, jnp.ndarray) and value.ndim == 0:
                    report_lines.append(f"- **{name}**: {float(value):.4f}")
                    continue
                if len(value) == 0:
                    continue
                final = value[-1] if hasattr(value, "__getitem__") else value
                report_lines.append(f"- **{name}** (final): {float(final):.4f}")

        report_lines.extend(
            [
                "",
                "## Analysis",
                "",
                f"Duration: {experiment_result.get('duration_seconds', 0):.1f} seconds",
            ]
        )

        report_text = "\n".join(report_lines)

        if output_format == "html":
            try:
                import markdown

                html = markdown.markdown(report_text, extensions=["tables", "fenced_code"])
                html = (
                    "<html><head><style>body{font-family:sans-serif;max-width:800px;"
                    "margin:auto;padding:20px}</style></head><body>"
                    f"{html}</body></html>"
                )

                output_path = self.config.output_path.parent / "report.html"
                with open(output_path, "w") as f:
                    f.write(html)
                return str(output_path)
            except ImportError:
                output_format = "md"

        output_path = self.config.output_path.parent / "report.md"
        with open(output_path, "w") as f:
            f.write(report_text)
        return str(output_path)
