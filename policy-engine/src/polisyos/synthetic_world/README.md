# polisyos.synthetic_world

- Last updated: 2026-05-03

Compatibility facade for `polisyos.foundry.agent_sim.world`.

Repository Structure Remediation Phase 4A moved the implementation under the
Foundry agent simulation owner. This directory intentionally contains only the
root wrapper and this README until the 2026-10-01 shim sunset.

Use `polisyos.foundry.agent_sim.world` for new imports. Deep
`polisyos.synthetic_world.*` imports are not supported as public compatibility
surface.

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
