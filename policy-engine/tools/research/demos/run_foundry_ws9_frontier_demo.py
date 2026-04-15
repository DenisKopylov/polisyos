from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tools._lib.imports import repo_root_from
import sys
from typing import Any
import warnings

import numpy as np


REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _make_frontier_observational(seed: int = 41) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n_obs = 240
    x = rng.normal(size=(n_obs, 3))
    latent = 0.7 * x[:, 0] + rng.normal(scale=0.6, size=n_obs)
    logits = 0.4 * x[:, 0] + 0.9 * latent
    treatment = (rng.uniform(size=n_obs) < (1.0 / (1.0 + np.exp(-logits)))).astype(float)
    treatment_proxy = latent + rng.normal(scale=0.3, size=n_obs)
    outcome_proxy = 0.8 * latent + 0.2 * x[:, 1] + rng.normal(scale=0.3, size=n_obs)
    outcome = 1.25 * treatment + 0.6 * x[:, 0] + latent + rng.normal(scale=0.35, size=n_obs)
    return {
        "outcome": outcome,
        "treatment": treatment,
        "covariates": x,
        "treatment_proxy": treatment_proxy,
        "outcome_proxy": outcome_proxy,
    }


def _make_tabular_payload(seed: int = 9) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    features = rng.normal(size=(160, 6))
    signal = 0.8 * features[:, 0] - 0.4 * features[:, 1] + 0.3 * features[:, 2] * features[:, 3]
    target = signal + rng.normal(scale=0.15, size=features.shape[0])
    return {"features": features, "target": target}


def _make_policy_payload(seed: int = 5) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    _ = rng.normal(size=4)
    policy_options = [
        "Expand childcare support and wage subsidies for low-income households.",
        "Pair the package with targeted hiring credits for firms in lagging regions.",
    ]
    evidence_snippets = [
        "Hiring credits tend to raise employment fastest when paired with liquidity support.",
        "Childcare subsidies reduce participation frictions for second earners and lone parents.",
        "Targeting support toward low-income households usually improves equity-adjusted welfare.",
    ]
    return {
        "policy_options": policy_options,
        "evidence_snippets": evidence_snippets,
        "policy_query": "Which package most directly improves low-income labor supply?",
    }


def _dispatch(method_fqn: str, state: dict[str, Any], params: dict[str, Any] | None = None, seed: int = 0) -> dict[str, Any]:
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get(method_fqn)
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=state,
        params=params or {},
        seed=seed,
    )
    return result.output


def main() -> None:
    warnings.filterwarnings("ignore", message=r".*warnings: empty_array.*", category=UserWarning)
    with redirect_stdout(io.StringIO()):
        ensure_all_methods_registered()
        payload = {
            "proximal_bridge": _dispatch(
                "causal.proximal.proximal_bridge@1.0.0",
                _make_frontier_observational(),
                params={"n_bootstrap": 80},
                seed=11,
            ),
            "ft_transformer": _dispatch(
                "ml.deep.ft_transformer@1.0.0",
                _make_tabular_payload(),
                seed=19,
            ),
            "foundation_model_policy_analysis": _dispatch(
                "policy.evaluation.foundation_model_policy_analysis@1.0.0",
                _make_policy_payload(),
                params={"embedding_backend": "tfidf"},
                seed=23,
            ),
        }
    print(json.dumps(payload, indent=2, sort_keys=True, default=_json_default))


if __name__ == "__main__":
    main()
