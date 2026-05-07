from __future__ import annotations

import pytest

pytest.importorskip("jax")

from polisyos.ir.analytics.calibration import (
    CalibrationConfig,
    CalibrationTarget,
    ConstraintLossConfig,
    GradNormConfig,
    MultiStartConfig,
    PriorLossConfig,
    TrainableParamRef,
)
from polisyos.scientist.methods.autotune.calibration import CalibrationMetaSearchConfig


def test_apply_to_config_uses_branch_local_nested_model_clones() -> None:
    base_config = CalibrationConfig(
        learning_rate=0.01,
        grad_norm=GradNormConfig(enabled=False, alpha=1.0, lr=0.1),
        constraint_loss=ConstraintLossConfig(enabled=True, weight=1.0),
        prior_loss=PriorLossConfig(enabled=True, weight=2.0),
        targets=[
            CalibrationTarget(
                target_id="outcome",
                model_metric_path="metrics.outcome",
                fabric_query={"dataset": {"metric": ["y"]}},
                trainables=[
                    TrainableParamRef(
                        param_id="target_param",
                        selector={"node_ids": ["n1"]},
                    )
                ],
            )
        ],
        trainables=[
            TrainableParamRef(
                param_id="global_param",
                selector={"slot_ids": ["s1"]},
            )
        ],
        time_axis=[1.0, 2.0],
        multi_start=MultiStartConfig(n_starts=3, perturbation_scale=0.2),
        constraint_values={"budget": 1.0},
        literature_priors={"global_param": {"prior_mean": 0.5, "studies": [1, 2]}},
    )
    overrides = CalibrationMetaSearchConfig(
        learning_rate=0.2,
        grad_norm_enabled=True,
        grad_norm_alpha=3.0,
        constraint_loss_weight=4.0,
        prior_loss_weight=5.0,
    )

    updated = overrides.apply_to_config(base_config)
    updated.grad_norm.alpha = 9.0
    updated.constraint_loss.weight = 8.0
    updated.prior_loss.weight = 7.0
    updated.targets[0].fabric_query["dataset"]["metric"][0] = "z"
    updated.targets[0].trainables[0].selector["node_ids"][0] = "n2"
    updated.trainables[0].selector["slot_ids"][0] = "s2"
    updated.time_axis[0] = 99.0
    updated.constraint_values["budget"] = 2.0
    updated.literature_priors["global_param"]["studies"][0] = 3

    assert base_config.learning_rate == 0.01
    assert base_config.grad_norm.enabled is False
    assert base_config.grad_norm.alpha == 1.0
    assert base_config.constraint_loss.weight == 1.0
    assert base_config.prior_loss.weight == 2.0
    assert base_config.targets[0].fabric_query == {"dataset": {"metric": ["y"]}}
    assert base_config.targets[0].trainables[0].selector == {"node_ids": ["n1"]}
    assert base_config.trainables[0].selector == {"slot_ids": ["s1"]}
    assert base_config.time_axis == [1.0, 2.0]
    assert base_config.constraint_values == {"budget": 1.0}
    assert base_config.literature_priors == {"global_param": {"prior_mean": 0.5, "studies": [1, 2]}}
