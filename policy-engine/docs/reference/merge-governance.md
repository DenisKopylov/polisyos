# Merge Governance

This page is the repository-facing merge contract for `main`.

GitHub-native settings cannot be fully versioned in product code, so the
repo-tracked source of truth is `.github/repository-rulesets/main.yml`. The
live GitHub ruleset should match that file.

For the exact click-path to apply that configuration in GitHub itself, see
[Apply Phase 1 Governance in GitHub UI](../how-to/apply-github-governance.md).

## Default Branch Ruleset

- target branch: `main`
- pull requests required for all merges
- minimum approvals: `1`
- code-owner review required on owned paths
- stale approvals dismissed on every new push
- approval from the most recent reviewable push required
- blocking review threads must be resolved before merge

## Required Checks

The default-branch ruleset should require these canonical GitHub Actions gate
contexts:

- `Fast PR / Gate`
- `Standard PR / Gate`

`Fast PR / Gate` already aggregates workflow governance, dependency review,
Python quality/unit, docs quality, and ABI drift handling. `Standard PR / Gate`
already aggregates runtime HTTP, frontend quality, component smoke, runtime
contract drift, frontend smoke, and integration coverage.

## Supplemental Checks

Additional checks may still appear on a PR for diagnostics or legacy coverage,
but they are not part of the required default-branch merge contract unless they
are promoted into one of the canonical gates above.

The archived `Frontend Quality (Archived)` workflow is explicitly not part of
the required merge contract.

## Merge Queue

Merge queue is intentionally not enabled yet.

Rationale:

- the repository is currently hosted as a personal repository under
  `DenisKopylov/polisyos`, while GitHub merge queue is documented for eligible
  organization-owned repositories rather than this hosting shape;
- the repository is currently low-volume and single-maintainer enough that a
  queue does not buy much throughput;
- the active workflows do not yet declare `merge_group` triggers, so enabling a
  queue would create a weaker contract than the normal PR path.

Revisit this when branch traffic justifies queueing and the required workflows
have `merge_group` coverage, and the repository hosting model makes queueing
available.

## Protected Control-Plane Paths

The following paths are self-protected by repository owners through
`.github/CODEOWNERS`:

- `.github/**`
- `.github/CODEOWNERS`
- `SECURITY.md`
- `SUPPORT.md`
- `CODE_OF_CONDUCT.md`

These files define the repository control plane and should not change without a
designated repository-owner review.

## Signatures Policy

- signed release tags are required for release-critical cuts;
- verified commit signatures on `main` are recommended but not enforced yet;
- enforcement stays off until contributor key management and automation signing
  posture are standardized enough to avoid blocking legitimate merges.

This means provenance is anchored at release boundaries first, with commit-level
signature enforcement reserved for a later hardening step.
