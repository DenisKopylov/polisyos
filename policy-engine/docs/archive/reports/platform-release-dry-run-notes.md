## [0.1.0] - 2026-04-04

### Changed
- `platform`: Consolidate the CI/CD platform into explicit tiers: Consolidate fast PR, standard PR, nightly, docs publish, and release workflows into one documented release platform.

## Compatibility Notes
- Branch protection should require the `Fast PR / Gate` and `Standard PR / Gate` checks after the new workflows land.

## Supported Surface Classification
- internal: internal-only

## Migration Notes
- Retire legacy reliance on `.github/workflows/frontend-quality.yml`; it is archival only after this change.

## Schema / Runtime / API Changes
- No product runtime API schema changed, but release packaging, SBOM, artifact signatures, and provenance surfaces are now part of the repository policy.

## Known Limitations
- Canary and production promotion checkpoints still rely on protected GitHub environments being configured in repository settings.
