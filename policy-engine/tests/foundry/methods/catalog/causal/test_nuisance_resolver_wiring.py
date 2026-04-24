"""Tests: NuisanceResolver wired into ast_lowerer.lower_nuisance_node.

3.2 — Nuisance parameter resolver integration:
- lower_nuisance_node calls NuisanceResolver for context-aware model selection
- high-dim covariates → L2 logistic; low-dim → standard logistic
- outcome role → lasso for high-dim, OLS for low-dim
- density_ratio role → method param carried through
- static fallback dict still works when resolver raises
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../../src"))

from polisyos.foundry.methods.catalog.causal.ast_lowerer import (
    LoweringContext,
    lower_nuisance_node,
)
from polisyos.ir.analytics.estimand import DistributionDomain


def _make_nuisance_node(nuisance_type: str, target: str = "T", conditioning=("X",)):
    """Create a minimal NuisanceNode via model_validate."""
    from polisyos.ir.analytics.estimand import NuisanceNode

    return NuisanceNode(
        nuisance_type=nuisance_type,
        target_variable=target,
        conditioning=tuple(conditioning),
        domain=DistributionDomain.SOURCE,
    )


def _make_ctx(n_obs=None, covariate_dim=None):
    return LoweringContext(
        run_id="test-run",
        knowledge_base=None,
        n_obs=n_obs,
        covariate_dim=covariate_dim,
    )


class TestNuisanceResolverWiring:
    def test_propensity_low_dim_uses_logistic(self):
        ctx = _make_ctx(n_obs=500, covariate_dim=5)
        node = _make_nuisance_node("propensity")
        node_id = lower_nuisance_node(node, ctx)
        assert node_id is not None
        emitted = ctx.nodes[-1]
        assert "logistic" in emitted.method_fqn
        assert emitted.is_nuisance

    def test_propensity_high_dim_uses_l2_logistic(self):
        ctx = _make_ctx(n_obs=500, covariate_dim=25)
        node = _make_nuisance_node("propensity")
        lower_nuisance_node(node, ctx)
        emitted = ctx.nodes[-1]
        assert "l2" in emitted.method_fqn or "logistic" in emitted.method_fqn
        # high-dim → l2 regularised
        assert "l2" in emitted.method_fqn

    def test_outcome_high_dim_uses_lasso(self):
        ctx = _make_ctx(n_obs=300, covariate_dim=15)
        node = _make_nuisance_node("outcome", target="Y")
        lower_nuisance_node(node, ctx)
        emitted = ctx.nodes[-1]
        assert "lasso" in emitted.method_fqn

    def test_outcome_low_dim_uses_ols(self):
        ctx = _make_ctx(n_obs=300, covariate_dim=3)
        node = _make_nuisance_node("outcome", target="Y")
        lower_nuisance_node(node, ctx)
        emitted = ctx.nodes[-1]
        assert "ols" in emitted.method_fqn

    def test_density_ratio_emitted_with_method_param(self):
        ctx = _make_ctx(n_obs=500, covariate_dim=5)
        node = _make_nuisance_node("density_ratio", target="X")
        lower_nuisance_node(node, ctx)
        emitted = ctx.nodes[-1]
        assert "density_ratio" in emitted.method_fqn or "density_ratio" in emitted.params.get(
            "role", ""
        )
        assert emitted.is_nuisance

    def test_mediator_density_uses_mediator_fqn(self):
        ctx = _make_ctx(n_obs=200, covariate_dim=4)
        node = _make_nuisance_node("mediator_density", target="M")
        lower_nuisance_node(node, ctx)
        emitted = ctx.nodes[-1]
        assert "mediator" in emitted.method_fqn

    def test_unknown_role_falls_back_gracefully(self, monkeypatch):
        """When NuisanceResolver raises (e.g. resolver unavailable), static fallback is used."""
        import polisyos.foundry.methods.catalog.causal.ast_lowerer as _mod

        def _bad_resolver(*_a, **_kw):
            raise RuntimeError("resolver unavailable")

        monkeypatch.setattr(
            _mod,
            "_NUISANCE_TYPE_TO_FQN",
            {
                "propensity": "causal.nuisance.propensity_model@1.0.0",
            },
        )

        # Patch the import inside lower_nuisance_node by making NuisanceResolver raise
        original_import = (
            __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__
        )

        ctx = _make_ctx(n_obs=100, covariate_dim=2)
        node = _make_nuisance_node("propensity", target="Z")

        # Simulate resolver failure by patching the NuisanceResolver class
        import polisyos.foundry.methods.catalog.causal.nuisance_resolver as nr_mod

        original_cls = nr_mod.NuisanceResolver

        class _FailingResolver:
            def resolve_for_nuisance_node(self, *a, **kw):
                raise RuntimeError("forced failure")

        monkeypatch.setattr(nr_mod, "NuisanceResolver", _FailingResolver)

        # Should not raise — falls back to static dict
        node_id = lower_nuisance_node(node, ctx)
        assert node_id is not None
        assert len(ctx.nodes) >= 1
        # Fallback should emit a known FQN
        emitted = ctx.nodes[-1]
        assert "propensity_model" in emitted.method_fqn

    def test_no_context_still_emits_node(self):
        """NuisanceResolver handles None n_obs/covariate_dim gracefully."""
        ctx = _make_ctx(n_obs=None, covariate_dim=None)
        node = _make_nuisance_node("propensity")
        node_id = lower_nuisance_node(node, ctx)
        assert node_id is not None

    def test_rationale_stored_in_params(self):
        ctx = _make_ctx(n_obs=500, covariate_dim=5)
        node = _make_nuisance_node("propensity")
        lower_nuisance_node(node, ctx)
        emitted = ctx.nodes[-1]
        # _rationale key should be present (from NuisanceSpec.rationale)
        assert "_rationale" in emitted.params
