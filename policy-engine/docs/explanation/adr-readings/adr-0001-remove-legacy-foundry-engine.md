# English reader translation of ADR-0001: Remove the legacy Foundry engine

Document type: English reader translation (informational derivative)  
Source pin: `af387828fbf27dce6dec8665286180df0dd10d1c`  
Source of truth: `docs/adr/0001-remove-legacy-foundry-engine.md`

This page translates the decision text in the [source ADR](../../adr/0001-remove-legacy-foundry-engine.md), whose SHA-256 is
`7914081add6e34201e7b2e6f71b86dd60dead0a7d658a524dd28597d1957f15f`.
The generated ADR index reports the source status as `unknown` at the source pin.
This derivative does not ratify or revise the decision and does not establish
that the decision was implemented.

- **Date:** 2026-01-12
- **Decision:** Mark the legacy Foundry core (`foundry/engine/**`,
  `basic_simulation.py`) as `_legacy`, prohibit its import from production
  code, and remove it after the compatibility window closes.
- **Context:** The codebase has two Foundry execution paths: the new patch VM /
  ProgramGraph and the outdated SimulationKernel core. Duplication increases
  the risk of semantic divergence and makes maintenance more complex.
- **Consequences:**
  - Move legacy code to `_legacy/` and exclude it from runtime through linters.
  - Either remove tests that depend on the legacy core or rewrite them for the
    new runtime.
  - Documentation marks the legacy path as not to be used.
- **Removal point:** 60 days or two minor releases after deployment of the ADR,
  whichever comes first. After date T, remove the legacy `_legacy/engine`
  directory and related tests completely.
