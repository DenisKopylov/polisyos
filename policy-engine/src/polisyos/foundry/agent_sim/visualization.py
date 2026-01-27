from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import jax.numpy as jnp
import numpy as np


def _import_matplotlib():
    try:
        import matplotlib.animation as animation
        import matplotlib.pyplot as plt

        return plt, animation
    except ImportError as exc:
        raise ImportError(
            "matplotlib required for visualization: pip install matplotlib"
        ) from exc


def _import_plotly():
    try:
        import plotly.express as px
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        return go, px, make_subplots
    except ImportError as exc:
        raise ImportError("plotly required for interactive viz: pip install plotly") from exc


@dataclass
class VisualizationConfig:
    output_dir: Path = Path("./viz_output")
    format: str = "png"
    dpi: int = 150
    figsize: tuple[int, int] = (12, 8)
    style: str = "seaborn-v0_8-whitegrid"
    interactive: bool = False


class TrainingVisualizer:
    def __init__(self, config: VisualizationConfig | None = None):
        self.config = config or VisualizationConfig()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_training_curves(
        self,
        losses: jnp.ndarray,
        rewards: jnp.ndarray | None = None,
        policy_losses: jnp.ndarray | None = None,
        value_losses: jnp.ndarray | None = None,
        save_path: str | Path | None = None,
    ):
        if self.config.interactive:
            return self._plot_training_curves_plotly(
                losses, rewards, policy_losses, value_losses, save_path
            )

        plt, _ = _import_matplotlib()
        plt.style.use(self.config.style)

        n_plots = 1 + int(rewards is not None) + int(
            policy_losses is not None and value_losses is not None
        )

        fig, axes = plt.subplots(1, n_plots, figsize=self.config.figsize)
        if n_plots == 1:
            axes = [axes]

        episodes = np.arange(len(losses))
        loss_arr = np.array(losses, dtype=float)

        ax = axes[0]
        ax.plot(episodes, loss_arr, "b-", alpha=0.7, label="Total Loss")

        if len(loss_arr) > 10:
            window = np.ones(10) / 10
            smoothed = np.convolve(loss_arr, window, mode="valid")
            ax.plot(episodes[9:], smoothed, "b-", linewidth=2, label="Smoothed (10)")

        ax.set_xlabel("Episode")
        ax.set_ylabel("Loss")
        ax.set_title("Training Loss")
        ax.legend()
        ax.grid(True, alpha=0.3)

        plot_idx = 1

        if rewards is not None:
            ax = axes[plot_idx]
            ax.plot(episodes, np.array(rewards, dtype=float), "g-", alpha=0.7)
            ax.set_xlabel("Episode")
            ax.set_ylabel("Mean Reward")
            ax.set_title("Agent Rewards")
            ax.grid(True, alpha=0.3)
            plot_idx += 1

        if policy_losses is not None and value_losses is not None:
            ax = axes[plot_idx]
            ax.plot(episodes, np.array(policy_losses, dtype=float), "r-", alpha=0.7, label="Policy")
            ax.plot(episodes, np.array(value_losses, dtype=float), "b-", alpha=0.7, label="Value")
            ax.set_xlabel("Episode")
            ax.set_ylabel("Loss")
            ax.set_title("Policy vs Value Loss")
            ax.legend()
            ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            save_to = Path(save_path)
        else:
            save_to = self.config.output_dir / f"training_curves.{self.config.format}"

        plt.savefig(save_to, dpi=self.config.dpi, bbox_inches="tight")
        plt.close()
        return fig

    def _plot_training_curves_plotly(
        self,
        losses,
        rewards,
        policy_losses,
        value_losses,
        save_path,
    ):
        go, _, make_subplots = _import_plotly()

        n_cols = 1 + int(rewards is not None) + int(policy_losses is not None)
        titles = ["Total Loss", "Rewards", "Loss Components"][:n_cols]
        fig = make_subplots(rows=1, cols=n_cols, subplot_titles=titles)

        episodes = list(range(len(losses)))

        fig.add_trace(
            go.Scatter(
                x=episodes,
                y=np.array(losses, dtype=float),
                mode="lines",
                name="Total Loss",
                opacity=0.7,
            ),
            row=1,
            col=1,
        )

        col = 2
        if rewards is not None:
            fig.add_trace(
                go.Scatter(
                    x=episodes,
                    y=np.array(rewards, dtype=float),
                    mode="lines",
                    name="Rewards",
                    line=dict(color="green"),
                ),
                row=1,
                col=col,
            )
            col += 1

        if policy_losses is not None:
            fig.add_trace(
                go.Scatter(
                    x=episodes,
                    y=np.array(policy_losses, dtype=float),
                    mode="lines",
                    name="Policy Loss",
                    line=dict(color="red"),
                ),
                row=1,
                col=col,
            )
            fig.add_trace(
                go.Scatter(
                    x=episodes,
                    y=np.array(value_losses, dtype=float),
                    mode="lines",
                    name="Value Loss",
                    line=dict(color="blue"),
                ),
                row=1,
                col=col,
            )

        fig.update_layout(height=400, title_text="Training Progress")

        if save_path:
            fig.write_html(save_path)
        else:
            fig.write_html(self.config.output_dir / "training_curves.html")

        return fig

    def plot_wealth_distribution(
        self,
        wealth: jnp.ndarray,
        active_mask: jnp.ndarray,
        title: str = "Wealth Distribution",
        save_path: str | Path | None = None,
        reference_wealth: jnp.ndarray | None = None,
    ):
        plt, _ = _import_matplotlib()
        plt.style.use(self.config.style)

        fig, axes = plt.subplots(1, 2, figsize=self.config.figsize)

        active_np = np.array(active_mask, dtype=bool)
        wealth_np = np.array(wealth, dtype=float)
        active_wealth = wealth_np[active_np]
        if active_wealth.size == 0:
            active_wealth = np.array([0.0])

        ax = axes[0]
        ax.hist(
            active_wealth,
            bins=50,
            density=True,
            alpha=0.7,
            color="steelblue",
            edgecolor="white",
        )
        if reference_wealth is not None:
            ax.hist(
                np.array(reference_wealth, dtype=float),
                bins=50,
                density=True,
                alpha=0.5,
                color="orange",
                edgecolor="white",
                label="Reference",
            )
            ax.legend()
        ax.set_xlabel("Wealth")
        ax.set_ylabel("Density")
        ax.set_title(f"{title} - Histogram")
        ax.axvline(
            np.mean(active_wealth),
            color="red",
            linestyle="--",
            label=f"Mean: {np.mean(active_wealth):.2f}",
        )
        ax.axvline(
            np.median(active_wealth),
            color="green",
            linestyle="--",
            label=f"Median: {np.median(active_wealth):.2f}",
        )
        ax.legend()

        ax = axes[1]
        sorted_wealth = np.sort(active_wealth)
        n = len(sorted_wealth)
        total = np.sum(sorted_wealth)
        if total <= 0:
            cumulative_wealth = np.zeros_like(sorted_wealth)
        else:
            cumulative_wealth = np.cumsum(sorted_wealth) / total
        cumulative_pop = np.arange(1, n + 1) / n

        ax.plot(
            cumulative_pop,
            cumulative_wealth,
            "b-",
            linewidth=2,
            label="Lorenz Curve",
        )
        ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Perfect Equality")
        ax.fill_between(cumulative_pop, cumulative_pop, cumulative_wealth, alpha=0.3)

        if hasattr(np, "trapezoid"):
            area = np.trapezoid(cumulative_wealth, cumulative_pop)
        else:  # pragma: no cover
            area = np.trapz(cumulative_wealth, cumulative_pop)
        gini = 1 - 2 * area
        ax.set_xlabel("Cumulative Population Share")
        ax.set_ylabel("Cumulative Wealth Share")
        ax.set_title(f"Lorenz Curve (Gini: {gini:.3f})")
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        save_to = (
            Path(save_path)
            if save_path
            else self.config.output_dir / f"wealth_distribution.{self.config.format}"
        )
        plt.savefig(save_to, dpi=self.config.dpi, bbox_inches="tight")
        plt.close()

        return fig

    def plot_agent_trajectories(
        self,
        trajectories: dict[str, jnp.ndarray],
        agent_indices: Sequence[int] | None = None,
        variables: Sequence[str] = ("wealth", "consumption", "income"),
        save_path: str | Path | None = None,
    ):
        plt, _ = _import_matplotlib()
        plt.style.use(self.config.style)

        n_vars = len(variables)
        fig, axes = plt.subplots(n_vars, 1, figsize=(self.config.figsize[0], 4 * n_vars))
        if n_vars == 1:
            axes = [axes]

        T = trajectories[variables[0]].shape[0]
        n_agents = trajectories[variables[0]].shape[1]

        if agent_indices is None:
            agent_indices = np.random.choice(n_agents, min(10, n_agents), replace=False)

        time_steps = np.arange(T)
        colors = plt.cm.tab10(np.linspace(0, 1, len(agent_indices)))

        for var_idx, var_name in enumerate(variables):
            ax = axes[var_idx]
            data = np.array(trajectories[var_name])

            for i, agent_idx in enumerate(agent_indices):
                ax.plot(
                    time_steps,
                    data[:, agent_idx],
                    color=colors[i],
                    alpha=0.7,
                    label=f"Agent {agent_idx}",
                )

            mean_traj = np.mean(data, axis=1)
            ax.plot(time_steps, mean_traj, "k-", linewidth=2, label="Population Mean")

            ax.set_xlabel("Time Step")
            ax.set_ylabel(var_name.capitalize())
            ax.set_title(f"{var_name.capitalize()} Trajectories")
            ax.legend(loc="upper right", fontsize=8)
            ax.grid(True, alpha=0.3)

        plt.tight_layout()

        save_to = (
            Path(save_path)
            if save_path
            else self.config.output_dir / f"agent_trajectories.{self.config.format}"
        )
        plt.savefig(save_to, dpi=self.config.dpi, bbox_inches="tight")
        plt.close()

        return fig

    def plot_policy_comparison(
        self,
        results: dict[str, dict],
        metrics: Sequence[str] = ("gdp", "gini_wealth", "mean_consumption"),
        save_path: str | Path | None = None,
    ):
        plt, _ = _import_matplotlib()
        plt.style.use(self.config.style)

        n_metrics = len(metrics)
        fig, axes = plt.subplots(1, n_metrics, figsize=(5 * n_metrics, 5))
        if n_metrics == 1:
            axes = [axes]

        policy_names = list(results.keys())
        x = np.arange(len(policy_names))

        for i, metric in enumerate(metrics):
            ax = axes[i]
            values = [results[p].get(metric, 0) for p in policy_names]

            first_val = values[0] if values else 0
            is_series = isinstance(first_val, (np.ndarray, jnp.ndarray, list, tuple))
            if is_series and np.asarray(first_val).ndim > 0 and np.asarray(first_val).size > 1:
                for name, val in zip(policy_names, values):
                    ax.plot(np.array(val, dtype=float), label=name, linewidth=2)
                ax.legend()
            else:
                scalar_vals = [float(np.array(v)) for v in values]
                bars = ax.bar(x, scalar_vals, color="steelblue", edgecolor="white")
                ax.set_xticks(x)
                ax.set_xticklabels(policy_names, rotation=45, ha="right")

                for bar, val in zip(bars, scalar_vals):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height(),
                        f"{val:.3f}",
                        ha="center",
                        va="bottom",
                        fontsize=9,
                    )

            ax.set_title(metric.replace("_", " ").title())
            ax.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()

        save_to = (
            Path(save_path)
            if save_path
            else self.config.output_dir / f"policy_comparison.{self.config.format}"
        )
        plt.savefig(save_to, dpi=self.config.dpi, bbox_inches="tight")
        plt.close()

        return fig

    def create_animation(
        self,
        states: Sequence[dict],
        variable: str = "wealth",
        interval: int = 100,
        save_path: str | Path | None = None,
    ):
        plt, animation = _import_matplotlib()

        fig, ax = plt.subplots(figsize=(10, 6))

        all_values = np.concatenate([np.array(s["agents"][variable]) for s in states])
        if all_values.size == 0:
            all_values = np.array([0.0])
        vmin, vmax = np.percentile(all_values, [1, 99])
        if vmin == vmax:
            vmax = vmin + 1.0
        bins = np.linspace(vmin, vmax, 51)

        def update(frame):
            ax.clear()
            values = np.array(states[frame]["agents"][variable])
            active = np.array(
                states[frame]["agents"].get("active", np.ones_like(values, dtype=bool))
            )
            values = values[active]

            ax.hist(values, bins=bins, density=True, color="steelblue", edgecolor="white")
            ax.set_xlim(vmin, vmax)
            ax.set_xlabel(variable.capitalize())
            ax.set_ylabel("Density")
            ax.set_title(f"{variable.capitalize()} Distribution - Step {frame}")

            stats_text = f"Mean: {np.mean(values):.2f}\nStd: {np.std(values):.2f}"
            ax.text(
                0.95,
                0.95,
                stats_text,
                transform=ax.transAxes,
                verticalalignment="top",
                horizontalalignment="right",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
            )

        anim = animation.FuncAnimation(
            fig, update, frames=len(states), interval=interval, blit=False
        )

        save_to = (
            Path(save_path)
            if save_path
            else self.config.output_dir / f"{variable}_animation.gif"
        )
        anim.save(save_to, writer="pillow", fps=1000 / interval)
        plt.close()

        return anim
