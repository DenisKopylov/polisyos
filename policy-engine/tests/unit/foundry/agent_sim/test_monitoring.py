import tempfile
from pathlib import Path

import jax.numpy as jnp
import pytest
from polisyos.foundry.agent_sim import (
    BehaviorAnalyzer,
    DashboardConfig,
    DashboardGenerator,
    ExperimentConfig,
    ExperimentTracker,
    GlobalState,
    MetricDefinition,
    MetricsCollector,
    MetricType,
    TrainingVisualizer,
    VisualizationConfig,
    standard_training_metrics,
)


@pytest.fixture
def simple_state():
    return GlobalState.empty(n_agents=100, seed=42, max_agents=100)


class TestMetricsCollector:
    def test_collector_creation(self):
        metrics = standard_training_metrics()
        collector = MetricsCollector(metrics, max_history=100)
        assert int(collector.step_counter) == 0

    def test_collect_metrics(self, simple_state):
        metrics = standard_training_metrics()
        collector = MetricsCollector(metrics, max_history=100)

        new_collector = collector.collect(simple_state)
        assert int(new_collector.step_counter) == 1

    def test_get_history(self, simple_state):
        metrics = [
            MetricDefinition(
                name="test_metric",
                metric_type=MetricType.SCALAR,
                compute_fn=lambda s: jnp.array(1.0, dtype=jnp.float32),
            )
        ]
        collector = MetricsCollector(metrics, max_history=100)

        for _ in range(5):
            collector = collector.collect(simple_state)

        history = collector.get_scalar_history("test_metric")
        assert history.shape[0] == 5


class TestExperimentTracker:
    def test_run_experiment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ExperimentTracker(tmpdir)

            config = ExperimentConfig(
                name="test_exp",
                seed=42,
                model_config={"hidden_dims": [32, 32]},
            )

            with tracker.run(config) as run:
                run.log_metric("loss", 0.5)
                run.log_metric("loss", 0.3)
                run.log_metric("reward", 1.0)

            exps = tracker.list_experiments()
            assert len(exps) == 1

    def test_compare_experiments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ExperimentTracker(tmpdir)

            for i, lr in enumerate([0.001, 0.01]):
                config = ExperimentConfig(
                    name=f"exp_{i}",
                    seed=42,
                    training_config={"learning_rate": lr},
                )
                with tracker.run(config) as run:
                    run.log_metric("final_loss", 0.5 - i * 0.1)

            comparison = tracker.compare(
                tracker.list_experiments(),
                metrics=["final_loss"],
            )
            assert len(comparison) == 2


class TestBehaviorAnalyzer:
    def test_cluster_agents(self, simple_state):
        clusters = BehaviorAnalyzer.cluster_agents(
            simple_state,
            n_clusters=3,
            features=["wealth", "income"],
        )

        assert len(clusters) <= 3
        total_agents = sum(cluster.size for cluster in clusters)
        assert total_agents == int(jnp.sum(simple_state.agents.active))

    def test_mobility_matrix(self, simple_state):
        matrix = BehaviorAnalyzer.compute_mobility_matrix(
            simple_state,
            simple_state,
            n_quantiles=5,
        )

        assert matrix.shape == (5, 5)
        assert bool(jnp.all(jnp.diag(matrix) >= 0))


class TestVisualization:
    def test_plot_training_curves(self):
        pytest.importorskip("matplotlib")
        with tempfile.TemporaryDirectory() as tmpdir:
            config = VisualizationConfig(output_dir=Path(tmpdir))
            viz = TrainingVisualizer(config)

            losses = jnp.linspace(1.0, 0.1, 100)
            viz.plot_training_curves(losses)

            assert (Path(tmpdir) / "training_curves.png").exists()

    def test_plot_wealth_distribution(self, simple_state):
        pytest.importorskip("matplotlib")
        with tempfile.TemporaryDirectory() as tmpdir:
            config = VisualizationConfig(output_dir=Path(tmpdir))
            viz = TrainingVisualizer(config)

            viz.plot_wealth_distribution(
                simple_state.agents.wealth,
                simple_state.agents.active,
            )

            assert (Path(tmpdir) / "wealth_distribution.png").exists()


class TestDashboard:
    def test_generate_dashboard(self):
        pytest.importorskip("plotly")
        with tempfile.TemporaryDirectory() as tmpdir:
            config = DashboardConfig(output_path=Path(tmpdir) / "dashboard.html")
            generator = DashboardGenerator(config)

            metrics = {
                "loss_history": list(range(100, 0, -1)),
                "reward_history": list(range(100)),
                "gini_history": [0.4 - i * 0.001 for i in range(100)],
            }

            path = generator.generate(metrics)
            assert Path(path).exists()
