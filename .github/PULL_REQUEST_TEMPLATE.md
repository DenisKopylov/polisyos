## Summary

<!-- What changed and why? -->

## Change Categories

- [ ] architecture
- [ ] contract / schema
- [ ] runtime behavior
- [ ] frontend
- [ ] docs
- [ ] ops / security
- [ ] dependency upgrade

## Compatibility Classification

- [ ] breaking
- [ ] additive
- [ ] internal

## Labels and Ownership

- [ ] I applied at least one `kind:*` label, exactly one `compat:*` label, and
      one `release:*` label from `.github/labels.yml`.
- [ ] I listed the owned areas touched by this PR.
- [ ] I requested review from each affected owner when the change crosses
      package, contract, or operational boundaries.

Owned areas touched:

<!-- Example: core, ir, runtime, frontend, docs -->

## Rollout Ownership

- Migration owner:
- Review owner:

## Category Checklists

### Architecture

- [ ] I described the boundary, ownership, or import-policy impact.
- [ ] I linked an ADR or explained why an ADR is not required.
- [ ] I called out every subsystem owner that must approve the change.

### Contract / Schema

- [ ] I updated or verified schema/OpenAPI/generated artifacts in the same PR.
- [ ] I classified the change correctly as breaking, additive, or internal.
- [ ] I updated reference docs and added migration notes when consumers must act.

### Runtime Behavior

- [ ] I described operator-visible or user-visible behavior changes.
- [ ] I updated tests for both the happy path and the failure or regression path.
- [ ] I updated runbooks or incident notes if alerts, rollout, or recovery behavior changed.

### Frontend

- [ ] I verified frontend contracts when Runtime API or generated client surfaces changed.
- [ ] I ran the relevant dashboard checks for the affected paths.
- [ ] I documented UI behavior changes when the operator experience changed materially.

### Docs

- [ ] I updated the docs entry point that describes the changed behavior.
- [ ] I checked that the docs remain consistent with repository reality.

### Ops / Security

- [ ] I documented config, secret, rollout, rollback, and incident implications.
- [ ] I noted whether workflow permissions, signing, SBOM, or trust boundaries changed.
- [ ] I updated the relevant runbook, policy doc, or security note when required.

### Dependency Upgrade

- [ ] I listed the manifest, lockfile, or workflow files touched.
- [ ] I checked upstream release notes for breaking or security-relevant changes.
- [ ] I ran the relevant validation path for every surface affected by the upgrade.

## Phase 7 Ratchet

<!-- Fill this section only when the PR introduces a new subsystem or major surface. -->

- [ ] This PR introduces a new subsystem or major surface.
- [ ] I added or updated the owner path, docs entry point, and test strategy.
- [ ] I considered compatibility, review / merge governance, and bootstrap / doctor impact.
- [ ] I considered config / secrets, generated artifacts, observability / rollout, and release / runbook impact.
- [ ] I linked the relevant evidence or checklist in `policy-engine/docs/reference/ratchet-policy.md`.

## Rollout Checklist

- [ ] Schema snapshots reviewed or regenerated
- [ ] Runtime OpenAPI export reviewed or regenerated
- [ ] Generated clients reviewed or regenerated
- [ ] SQL / RLS migrations reviewed
- [ ] Helm changes reviewed
- [ ] Terraform changes reviewed
- [ ] Feature flag / staged exposure plan documented where relevant
- [ ] Canary / shadow / phased rollout stance documented for high-risk changes
- [ ] Docs and runbooks updated

## Rollback / Mitigation

-

## Validation

- [ ] `./scripts/verify` or an equivalent scoped validation path passed.
- [ ] I called out any checks I did not run and why.

Skipped checks / follow-up:

<!-- Be explicit when something remains manual or deferred. -->

## Release Notes Fragment

- [ ] Added or updated a release fragment under `policy-engine/release-fragments/unreleased/`
