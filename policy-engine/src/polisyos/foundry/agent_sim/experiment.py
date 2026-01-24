from __future__ import annotations

import hashlib
import json
import pickle
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import equinox as eqx
import jax
import jax.numpy as jnp


def _json_default(value: Any):
    if isinstance(value, jnp.ndarray):
        return value.tolist()
    return str(value)


@dataclass
class ExperimentConfig:
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    seed: int = 42
    model_config: dict = field(default_factory=dict)
    training_config: dict = field(default_factory=dict)
    env_config: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    git_hash: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ExperimentConfig:
        return cls(**data)

    def config_hash(self) -> str:
        config_str = json.dumps(self.to_dict(), sort_keys=True, default=_json_default)
        return hashlib.sha256(config_str.encode()).hexdigest()[:12]


@dataclass
class ExperimentResult:
    config: ExperimentConfig
    metrics: dict[str, Any]
    final_state: dict | None = None
    model_path: str | None = None
    duration_seconds: float = 0.0

    def summary(self) -> str:
        lines = [
            f"Experiment: {self.config.name}",
            f"Hash: {self.config.config_hash()}",
            f"Duration: {self.duration_seconds:.1f}s",
            "---",
            "Final Metrics:",
        ]
        for name, value in self.metrics.items():
            if isinstance(value, (int, float)):
                lines.append(f"  {name}: {float(value):.4f}")
            elif isinstance(value, jnp.ndarray) and value.ndim == 0:
                lines.append(f"  {name}: {float(value):.4f}")
        return "\n".join(lines)


class ExperimentTracker:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.base_dir / "runs"
        self.runs_dir.mkdir(exist_ok=True)
        self.index_path = self.base_dir / "index.json"
        self._load_index()

    def _load_index(self) -> None:
        if self.index_path.exists():
            with open(self.index_path) as f:
                self.index = json.load(f)
        else:
            self.index = {"experiments": {}}

    def _save_index(self) -> None:
        with open(self.index_path, "w") as f:
            json.dump(self.index, f, indent=2, default=_json_default)

    def run(self, config: ExperimentConfig) -> ExperimentRun:
        run_id = (
            f"{config.name}_{config.config_hash()}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True)
        return ExperimentRun(
            run_id=run_id,
            config=config,
            run_dir=run_dir,
            tracker=self,
        )

    def register_run(self, run: ExperimentRun, result: ExperimentResult) -> None:
        def _to_jsonable(value: Any):
            if isinstance(value, jnp.ndarray):
                return value.tolist()
            if isinstance(value, (float, int)):
                return float(value)
            if isinstance(value, (list, tuple)):
                return [
                    float(v) if isinstance(v, (float, int, jnp.ndarray)) else v
                    for v in value
                ]
            return value

        self.index["experiments"][run.run_id] = {
            "config": result.config.to_dict(),
            "metrics": {k: _to_jsonable(v) for k, v in result.metrics.items()},
            "duration": result.duration_seconds,
            "path": str(run.run_dir),
        }
        self._save_index()

    def list_experiments(self, tags: list[str] | None = None) -> list[str]:
        exps = list(self.index["experiments"].keys())
        if tags:
            exps = [
                e
                for e in exps
                if any(
                    t in self.index["experiments"][e]["config"].get("tags", [])
                    for t in tags
                )
            ]
        return exps

    def get_result(self, run_id: str) -> ExperimentResult:
        run_data = self.index["experiments"][run_id]
        return ExperimentResult(
            config=ExperimentConfig.from_dict(run_data["config"]),
            metrics=run_data["metrics"],
            duration_seconds=run_data["duration"],
            model_path=str(Path(run_data["path"]) / "model.eqx"),
        )

    def compare(
        self,
        run_ids: list[str],
        metrics: list[str] | None = None,
    ) -> dict[str, dict[str, float]]:
        results = {}
        for run_id in run_ids:
            run_metrics = self.index["experiments"][run_id]["metrics"]
            if metrics:
                run_metrics = {k: v for k, v in run_metrics.items() if k in metrics}
            results[run_id] = run_metrics
        return results

    def best_run(self, metric: str, maximize: bool = True) -> str:
        runs = self.index["experiments"]
        if maximize:
            return max(
                runs.keys(),
                key=lambda r: runs[r]["metrics"].get(metric, float("-inf")),
            )
        return min(
            runs.keys(),
            key=lambda r: runs[r]["metrics"].get(metric, float("inf")),
        )


class ExperimentRun:
    def __init__(
        self,
        run_id: str,
        config: ExperimentConfig,
        run_dir: Path,
        tracker: ExperimentTracker,
    ):
        self.run_id = run_id
        self.config = config
        self.run_dir = run_dir
        self.tracker = tracker
        self.metrics: dict[str, Any] = {}
        self.metric_history: dict[str, list[float]] = {}
        self.start_time: datetime | None = None
        self.rng_key: jax.Array | None = None

    def __enter__(self) -> ExperimentRun:
        self.start_time = datetime.now()

        with open(self.run_dir / "config.json", "w") as f:
            json.dump(self.config.to_dict(), f, indent=2, default=_json_default)

        self.rng_key = jax.random.PRNGKey(self.config.seed)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        duration = (datetime.now() - self.start_time).total_seconds()
        result = ExperimentResult(
            config=self.config,
            metrics=self.metrics,
            duration_seconds=duration,
            model_path=str(self.run_dir / "model.eqx")
            if (self.run_dir / "model.eqx").exists()
            else None,
        )

        with open(self.run_dir / "metrics_history.json", "w") as f:
            json.dump(self.metric_history, f, indent=2)

        self.tracker.register_run(self, result)
        return False

    def log_metric(self, name: str, value: float | jnp.ndarray, step: int | None = None) -> None:
        del step
        value_f = float(value)
        self.metrics[name] = value_f
        self.metric_history.setdefault(name, []).append(value_f)

    def log_metrics(self, metrics: dict[str, float | jnp.ndarray], step: int | None = None) -> None:
        for name, value in metrics.items():
            self.log_metric(name, value, step)

    def log_artifact(self, name: str, artifact: Any) -> None:
        artifact_path = self.run_dir / f"{name}.pkl"

        if hasattr(artifact, "__jax_array__") or isinstance(artifact, eqx.Module):
            eqx.tree_serialise_leaves(self.run_dir / f"{name}.eqx", artifact)
        else:
            with open(artifact_path, "wb") as f:
                pickle.dump(artifact, f)

    def load_artifact(self, name: str, like: Any | None = None) -> Any:
        eqx_path = self.run_dir / f"{name}.eqx"
        pkl_path = self.run_dir / f"{name}.pkl"

        if eqx_path.exists() and like is not None:
            return eqx.tree_deserialise_leaves(eqx_path, like)
        if pkl_path.exists():
            with open(pkl_path, "rb") as f:
                return pickle.load(f)

        raise FileNotFoundError(f"Artifact {name} not found")

    def get_rng_key(self) -> jax.Array:
        if self.rng_key is None:
            self.rng_key = jax.random.PRNGKey(self.config.seed)
        self.rng_key, subkey = jax.random.split(self.rng_key)
        return subkey
