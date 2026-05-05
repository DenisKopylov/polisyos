# polisyos.foundry.agent_sim.world

- Last updated: 2026-05-03

Truth-centric synthetic-world family for Bayesian, ML, forecasting, econometrics,
survey, distributional, and causal methods.

This package is the canonical home for synthetic world generation under the
Foundry agent simulation owner. The old `polisyos.synthetic_world` root remains
a wrapper-only compatibility facade until 2026-10-01.

Package layout:

- `core/`: typed contracts (`WorldSpec`, `TruthSpec`, `EvaluationSpec`) and truth selection helpers
- `templates/`: canonical DGP families
- `operators/`: interventions, measurement error, missingness, sampling design
- `targets/`: ground-truth builders by method family
- `evaluators/`: metrics, hook diagnostics, and lightweight plot specs
- `configs/examples/`: example YAML specs for Phase 0 seed worlds

Public entrypoint:

- `SyntheticWorld.from_spec(...)`
- `SyntheticWorld.from_yaml(...)`
- `world.sample(...)`
- `world.truth(...)`
- `world.evaluate(...)`
- `world.artifact(...)`

Phase-0 seed coverage:

- world families: `cross_sectional`, `survey_repeated_cross_section`, `panel_dynamic`, `spatio_temporal`
- observation operators: interventions, measurement error, MCAR/MAR/MNAR missingness, survey/entity sampling
- truth families: Bayesian prior/posterior/latent-state, ML regression/classification/calibration, forecasting mean/interval/distribution, econometrics FE/IV/IRF, survey weights/DEFF/design variance, distributional quantile/CDF/PDF/tail risk, causal ATE/CATE/ITE/mediation/dynamic value
- lineage: deterministic replay, config hashing, manifest versions, artifact refs
