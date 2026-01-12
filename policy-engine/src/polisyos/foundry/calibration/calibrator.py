from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence

import equinox as eqx
import jax
import jax.numpy as jnp
import optax

from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph
from polisyos.foundry.calibration.bijectors import (
    Bijector,
    from_unconstrained,
    make_bijector,
    to_unconstrained,
)
from polisyos.foundry.calibration.loss import unified_loss
from polisyos.foundry.calibration.preflight import prepare_targets
from polisyos.foundry.calibration.pure_executor import (
    StaticBundle,
    apply_trainable_values,
    compile_program,
    extract_trainable_values,
    run_pure_scan,
)
from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.foundry.domain.state import GlobalState
from polisyos.ir.calibration import CalibrationConfig, CalibrationTarget
from polisyos.ir.kernel import MechanismTypeRegistry, SelectorFieldRegistry, SlotRegistry


@dataclass
class CalibratorInputs:
    config: CalibrationConfig
    program_graph: ProgramGraph
    exec_plan: ExecPlan
    base_state: GlobalState
    mechanism_registry: MechanismTypeRegistry
    slot_registry: SlotRegistry
    selector_field_registry: SelectorFieldRegistry | None
    parameter_loader: Callable[[Any], dict[str, Any]]
    raw_targets: Mapping[str, object]
    controls_seq: jnp.ndarray | None = None


class Calibrator:
    """
    Минимальный дифференцируемый калибратор (MVP):
    - optax.Adam
    - относительная нормализация ошибок
    - без Hessian/GradNorm (заложены точки расширения)
    """

    def __init__(self, inputs: CalibratorInputs):
        self.inputs = inputs
        self._bundle: StaticBundle | None = None
        self._bijectors: list[Bijector] = []

    def _build_bundle(self) -> StaticBundle:
        if self._bundle is not None:
            return self._bundle
        bundle = compile_program(
            self.inputs.program_graph,
            self.inputs.exec_plan,
            mechanism_registry=self.inputs.mechanism_registry,
            slot_registry=self.inputs.slot_registry,
            selector_field_registry=self.inputs.selector_field_registry,
            base_state=self.inputs.base_state,
            parameter_loader=self.inputs.parameter_loader,
        )
        self._bundle = bundle
        return bundle

    def _target_meta(self) -> tuple[list[CalibrationTarget], list[str]]:
        targets = list(self.inputs.config.targets)
        metric_paths = [t.model_metric_path for t in targets]
        return targets, metric_paths

    def _build_bijectors(self, bundle: StaticBundle) -> list[Bijector]:
        if self._bijectors:
            return self._bijectors
        bij = [
            make_bijector(handle.lower, handle.upper)
            for handle in bundle.trainables
        ]
        self._bijectors = bij
        return bij

    def run(self) -> CalibrationReport:
        cfg = self.inputs.config
        bundle = self._build_bundle()
        bijectors = self._build_bijectors(bundle)

        targets, metric_paths = self._target_meta()
        steps = len(next(iter(self.inputs.raw_targets.values()))) if self.inputs.raw_targets else 0
        if steps == 0:
            raise ValueError("No target series provided for calibration")
        aligned_targets, scales = prepare_targets(cfg, raw_targets=self.inputs.raw_targets, steps=steps)
        loss_configs = {t.target_id: t.loss for t in targets}

        base_values = extract_trainable_values(bundle)
        unconstrained = to_unconstrained(base_values, bijectors)

        opt = optax.adam(cfg.learning_rate)
        opt_state = opt.init(unconstrained)

        def loss_fn(u):
            theta = from_unconstrained(u, bijectors)
            sim_bundle = apply_trainable_values(bundle, theta)
            _, traces = run_pure_scan(
                self.inputs.base_state,
                steps=steps,
                root_key=jax.random.PRNGKey(cfg.seed),
                bundle=sim_bundle,
                metric_paths=metric_paths,
                controls_seq=self.inputs.controls_seq,
            )
            predicted = {t.target_id: traces[t.model_metric_path] for t in targets}
            total, per_target = unified_loss(predicted, aligned_targets, loss_configs, scales)
            return total, per_target

        loss_history: list[float] = []
        per_target_final: Dict[str, float] = {}
        u = unconstrained
        for _ in range(cfg.max_steps):
            (loss_val, per_target), grads = jax.value_and_grad(loss_fn, has_aux=True)(u)
            updates, opt_state = opt.update(grads, opt_state, u)
            u = optax.apply_updates(u, updates)
            loss_history.append(float(loss_val))
            per_target_final = {k: float(v) for k, v in per_target.items()}

        final_theta = from_unconstrained(u, bijectors)
        final_bundle = apply_trainable_values(bundle, final_theta)
        calibrated_params: Dict[str, float] = {}
        for handle, value in zip(final_bundle.trainables, final_theta):
            node_id = final_bundle.nodes[handle.node_index].node_id
            calibrated_params[f"{node_id}.{handle.field_name}"] = float(value)

        # Финальный прогон для сохранения сравнения рядов
        _, traces = run_pure_scan(
            self.inputs.base_state,
            steps=steps,
            root_key=jax.random.PRNGKey(cfg.seed),
            bundle=final_bundle,
            metric_paths=metric_paths,
            controls_seq=self.inputs.controls_seq,
        )
        series_comparison: Dict[str, Dict[str, Any]] = {}
        for tgt in targets:
            series_comparison[tgt.target_id] = {
                "real": aligned_targets[tgt.target_id],
                "model": traces[tgt.model_metric_path],
            }

        return CalibrationReport(
            calibrated_params=calibrated_params,
            total_loss=loss_history[-1] if loss_history else 0.0,
            per_target_loss=per_target_final,
            loss_history=loss_history,
            series_comparison=series_comparison,
            diagnostics=[],
        )
