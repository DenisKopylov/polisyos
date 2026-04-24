# Analytics (`polisyos.ir.analytics`)

## Purpose

`polisyos.ir.analytics` задает контрактный слой аналитических результатов:
causal effects, transportability, HTE, backtests, uncertainty, strategic
response, ecosystem bridges и frontier causal contracts. Пакет служит общим
interchange format между `foundry`, `scientist`, `fabric` и observation-driven
workflows.

Package facade `polisyos.ir.analytics` намеренно уже, чем полный набор модулей
в каталоге `analytics/`: он реэкспортирует наиболее частые contracts, а
специализированные surface-ы остаются в defining modules.

## Where to Start

- [`__init__.py`](./__init__.py) — curated lazy facade для наиболее частых analytics import-path'ов.
- [`causal.py`](./causal.py) — core effect-report surface, diagnostics и refutations.
- [`dynamic_regime.py`](./dynamic_regime.py) — continuous-time query contracts, trajectory bundles и runtime support gates.
- [`hte.py`](./hte.py) — heterogeneous effects, feature importance и targeting outputs.
- [`recourse_manifold.py`](./recourse_manifold.py) — typed causal recourse queries, intervention-cost manifolds, proof bundles и feasibility certificates for Stage 13.4.
- [`rough_path_semantics.py`](./rough_path_semantics.py) — proof-carrying semantics for rough/signature path claims under irregular sampling.
- [`transportability.py`](./transportability.py) — перенос между environments и gap diagnostics.
- [`privacy_transportability.py`](./privacy_transportability.py) — privacy-aware слой над transportability/recoverability для DP-distorted multi-domain releases.
- [`uncertainty.py`](./uncertainty.py) — uncertainty algebra, interval semantics и propagation contracts.
- [`strategic.py`](./strategic.py) — strategic-response SCM, equilibria и bundle outputs.
- [`ecosystem_bridges.py`](./ecosystem_bridges.py) — bridges в DoWhy, EconML, CausalNex, pgmpy и смежные ecosystems.
- Для upstream/downstream контекста откройте [`../observation/README.md`](../observation/README.md) и [`../artifacts/README.md`](../artifacts/README.md).

## Public entrypoints

| Entrypoint                                                                                             | Use when                                                                               | Defined in                                                   |
| ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `polisyos.ir.analytics.CausalEffectReport`                                                             | Нужен канонический causal effect report с diagnostics и refutations                    | [`causal.py`](./causal.py)                                   |
| `polisyos.ir.analytics.TransportabilityResult`                                                         | Нужен результат transportability / domain-shift анализа                                | [`transportability.py`](./transportability.py)               |
| `polisyos.ir.analytics.HTEResult`                                                                      | Нужны heterogeneous treatment effects и targeting outputs                              | [`hte.py`](./hte.py)                                         |
| `polisyos.ir.analytics.StructuralCausalModelSpec`                                                      | Нужен IR-контракт структурной causal model                                             | [`structural_causal_model.py`](./structural_causal_model.py) |
| `polisyos.ir.analytics.recourse_manifold.InterventionCostManifold`, `OptimalRecourseInterventionQuery` | Нужен proof-carrying causal recourse surface, а не explainability-only recourse report | [`recourse_manifold.py`](./recourse_manifold.py)             |
| `polisyos.ir.analytics.StrategicSCM`, `StrategicResponseBundle`, `MeanFieldEquilibriumCertificate`     | Нужен strategic-response / performative-analysis surface, включая MFG certificates     | [`strategic.py`](./strategic.py)                             |
| `polisyos.ir.analytics.DoWhyGraphBridge`, `EconMLDesignBridge`                                         | Нужны interoperability bridges в external causal toolchains                            | [`ecosystem_bridges.py`](./ecosystem_bridges.py)             |

## Depends on / depended on by

- Depends on: [`../artifacts/README.md`](../artifacts/README.md), [`../world/README.md`](../world/README.md), [`../observation/README.md`](../observation/README.md), `polisyos.ir.kernel`.
- Depended on by: `polisyos.foundry.methods`, `polisyos.foundry.calibration`, `polisyos.scientist`, `polisyos.fabric`, `polisyos.core`.

## Common commands

Run from the repository root (`policy-engine/`).

Smoke-tested on `2026-04-17`.

```bash
uv run python -c "import polisyos.ir.analytics as analytics; from polisyos.ir.analytics import CausalEffectReport, HTEResult; print(len(analytics.__all__), CausalEffectReport.__name__, HTEResult.__name__)"
```

## Test/verification commands

Run from the repository root (`policy-engine/`).

Conceptual in this README refresh; run these targeted analytics checks before
landing IR result-contract changes.

```bash
uv run pytest tests/ir/analytics/test_shared_invariants.py tests/ir/analytics/test_estimand_normalization.py tests/ir/test_uncertainty.py tests/ir/test_frontier_causal_contracts.py -q
uv run pytest tests/ir/test_interoperability_bridges.py -q
```

## Reference docs

- Mean-field path now uses three typed artifacts in [`strategic.py`](./strategic.py):
  `MeanFieldPerturbationSpec` compiles `InterventionSpec` into coefficient/distributional/mixed MFG perturbations, `MeanFieldMacroSimulationConfig` records replayable Fabric numerics, and `MeanFieldEquilibriumCertificate` is the audit leaf referenced by `StrategicResponseBundle.mfg_equilibrium_ref`.

- Stage 13.4 causal recourse lives in [`recourse_manifold.py`](./recourse_manifold.py):
  `InterventionCostManifold` defines the quotient cost geometry, `OptimalRecourseInterventionQuery`
  is the kernel-facing query contract, and the proof/feasibility/planning bundles carry the
  identify-or-bound and solver outputs.

- [IR analytics reference](../../../../docs/reference/ir/analytics.md)
- [Temporal path semantics reference](../../../../docs/reference/ir/temporal-path-semantics.md)
- [IR interoperability reference](../../../../docs/reference/ir/interoperability.md)
- [IR schema catalog](../../../../docs/reference/ir/schema-catalog.md)
- [IR root README](../README.md)
- [Observation README](../observation/README.md)
- [Artifacts README](../artifacts/README.md)

## Last updated

`2026-04-20`
