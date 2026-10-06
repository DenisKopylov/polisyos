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

## Causal result interval semantics

`CausalQueryResult` schema 1.2 and `TwinNetworkResult` schema 1.1 distinguish
fixed-model outcome/ITE distributions from conditional Gaussian posterior
credible intervals. Their historical `result_ci` / `ite_ci` fields carry central
quantile spans; they do not assert estimator confidence intervals. The current
shared uncertainty schema 1.1 represents ordinary distribution spans as a
non-gating `HEURISTIC_RANGE`, and exact model posteriors as non-gating
`CREDIBLE_INTERVAL`. This change does not ratify a new global uncertainty schema.

`CausalEstimatorInterval` separately records iid-observation-row resampling,
complete model refits, source/row/graph/target hashes, seeds, and replicate effect
estimates. Its confidence interval describes approximate sampling inference for
the fixed identified graph and declared iid law. Source custody and empirical
causal identification require separate admission. Fresh CAS readers preserve the
result kind; historical causal result schemas 1.0/1.1 and twin schema 1.0 remain
decodable as limited distributions and cannot inherit old CI/gating markers.

The public types `CausalResultKind` and `CausalEstimatorInterval` are available
from both `polisyos.ir` and `polisyos.ir.analytics`.
See [structural causal models](../../../../docs/reference/foundry/structural-causal-models.md)
for selected backend, historical replay and refit-bootstrap limitations.

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
uv run pytest tests/unit/ir/analytics/test_shared_invariants.py tests/unit/ir/analytics/test_estimand_normalization.py tests/unit/ir/test_uncertainty.py tests/unit/ir/test_frontier_causal_contracts.py -q
uv run pytest tests/unit/ir/test_interoperability_bridges.py -q
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
