from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.ml import (
    SurvivalData,
    TabularData,
    ensure_ml_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _make_tabular() -> TabularData:
    rng = np.random.default_rng(51)
    x = rng.normal(size=(90, 4))
    y = 1.2 + 1.5 * x[:, 0] - 0.7 * x[:, 1] + rng.normal(scale=0.25, size=90)
    return TabularData(features=x, target=y, feature_names=["x0", "x1", "x2", "x3"])


def _make_survival() -> SurvivalData:
    tabular = _make_tabular()
    rng = np.random.default_rng(52)
    return SurvivalData(
        features=tabular.features,
        durations=np.abs(np.asarray(tabular.target, dtype=float)) + 1.0,
        events=(rng.uniform(size=tabular.features.shape[0]) > 0.3).astype(int),
        feature_names=tabular.feature_names,
    )


@pytest.mark.parametrize(
    "fqn",
    [
        "ml.regression.elastic_net@1.0.0",
        "ml.regression.random_forest@1.0.0",
        "ml.regression.gradient_boosting@1.0.0",
    ],
)
def test_regression_methods_run(fqn: str) -> None:
    pytest.importorskip("sklearn")

    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get(fqn)

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params={},
        seed=53,
    )

    assert result.output["result"].method_name
    assert result.output["uncertainty_envelope"] is not None


def test_conformal_prediction_composes_with_elastic_net() -> None:
    pytest.importorskip("sklearn")

    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    tabular = _make_tabular()

    pred_cls = registry.get("ml.regression.elastic_net@1.0.0")
    pred_result = dispatcher.dispatch(
        method_class=pred_cls,
        signature=pred_cls.signature,
        state=tabular,
        params={},
        seed=59,
    )
    conformal_cls = registry.get("ml.uncertainty.conformal_prediction@1.0.0")
    conformal_result = dispatcher.dispatch(
        method_class=conformal_cls,
        signature=conformal_cls.signature,
        state=pred_result.output["result"],
        params={"alpha": 0.1},
        seed=61,
    )

    assert conformal_result.output["result"].coverage is not None
    assert conformal_result.output["result"].method_name == "conformal_prediction"


def test_survival_pca_and_kmeans_run() -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("lifelines")

    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    survival_cls = registry.get("ml.survival.survival_analysis@1.0.0")
    survival_result = dispatcher.dispatch(
        method_class=survival_cls,
        signature=survival_cls.signature,
        state=_make_survival(),
        params={},
        seed=67,
    )
    assert survival_result.output["result"].method_name == "survival_analysis"

    tabular = _make_tabular()
    pca_cls = registry.get("ml.decomposition.pca@1.0.0")
    pca_result = dispatcher.dispatch(
        method_class=pca_cls,
        signature=pca_cls.signature,
        state=tabular,
        params={"n_components": 2},
        seed=71,
    )
    assert len(pca_result.output["result"].explained_variance_ratio) == 2

    kmeans_cls = registry.get("ml.clustering.kmeans@1.0.0")
    kmeans_result = dispatcher.dispatch(
        method_class=kmeans_cls,
        signature=kmeans_cls.signature,
        state=tabular,
        params={"n_clusters": 3},
        seed=73,
    )
    assert np.asarray(kmeans_result.output["result"].labels).shape[0] == tabular.features.shape[0]
