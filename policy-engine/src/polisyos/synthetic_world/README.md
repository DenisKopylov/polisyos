# polisyos.synthetic_world

- Last updated: 2026-05-05

Compatibility facade for `polisyos.foundry.agent_sim.world`.

Repository Structure Remediation Phase 4A moved the implementation under the
Foundry agent simulation owner. This directory intentionally contains only the
root wrapper and this README until the 2026-07-31 shim sunset.

Use `polisyos.foundry.agent_sim.world` for new imports. Deep
`polisyos.synthetic_world.*` imports are not supported as public compatibility
surface.

Shim contract:

- owner: `team-foundry`
- target: `src/polisyos/foundry/agent_sim/world`
- sunset: `2026-07-31`
- reference: `docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md#synthetic_world-into-foundryagentsimworld`
- smoke coverage: `tests/unit/foundry/agent_sim/test_synthetic_world_shim.py`

Behavioral seed-world coverage lives under the canonical Foundry path:
`tests/unit/foundry/agent_sim/world/test_seed_worlds.py`.

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
