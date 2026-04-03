# Quality Gates and Change Taxonomy

This page defines the pull-request taxonomy for PolicyOS and maps each change
kind to the review and validation expectations it carries.

## Required PR Metadata

Every pull request must include:

- at least one change category from `.github/PULL_REQUEST_TEMPLATE.md`;
- exactly one compatibility classification;
- the supported-surface classification touched by the PR (`public_stable`,
  `public_experimental`, or `internal`) when a documented package entrypoint is
  affected;
- at least one `kind:*` label, exactly one `compat:*` label, and exactly one
  `release:*` label from `.github/labels.yml`;
- the owned areas touched by the PR;
- a migration owner when the change requires coordinated rollout across
  multiple surfaces.

## Baseline Gate

Every PR targeting `main` is expected to satisfy the always-required checks
listed in `docs/reference/merge-governance.md`, currently `Fast PR / Gate` and
`Standard PR / Gate`.

Category-specific work adds scoped checks and review requirements on top of
that baseline rather than replacing it.

## Change Categories

| Category | Typical scope | Review expectation | Additional expectations beyond baseline |
|---|---|---|---|
| Architecture | ownership, ADRs, import-policy boundaries, major package moves | `@platform-owners` plus every touched subsystem owner | explain boundary impact; link ADR or explicit rationale; call out rollout and compatibility risk |
| Contract / schema | IR schema snapshots, OpenAPI, ABI, generated clients | owning subsystem plus `@platform-owners` | regenerate or verify affected artifacts; update reference docs; run ABI and runtime-contract checks when applicable |
| Runtime behavior | HTTP behavior, control plane, operator-visible backend semantics | `@runtime-owners` plus touched subsystem owners | describe behavior change; update failure-path tests; update runbook if rollout or incident handling changes |
| Frontend | dashboard UX, runtime-api-client, typed frontend contracts | `@frontend-owners`; add `@runtime-owners` when API contract changes | verify generated frontend contracts; run the frontend suites relevant to touched paths; document meaningful operator UX changes |
| Docs | reference, tutorials, how-to, ownership or governance docs | `@docs-owners`; add subsystem owner when docs change contract meaning | keep docs aligned with repo reality; update the relevant entry point, not only leaf pages |
| Ops / security | workflows, secrets, deployment, signing, incident surfaces | `@platform-owners`; add `@runtime-owners` or subsystem owners as needed | describe config/secret/rollback impact; update policy or runbook material; note workflow trust or supply-chain implications |
| Dependency upgrade | Python, Node, lockfiles, GitHub Actions, toolchain | owner of affected surface; add `@platform-owners` for shared toolchain or workflow changes | cite upstream notes for breaking/security changes; validate every affected surface; call out rollout risk when upgrades are not purely internal |

## Compatibility Classification Rules

Use exactly one compatibility label on every PR.

| Classification | Use when | Typical version impact |
|---|---|---|
| `breaking` | supported consumers or operators must change behavior, update config, regenerate clients, adopt a new schema/API major, or handle removed/renamed fields | package release bump for a breaking line; schema major bump; runtime API major line bump |
| `additive` | existing consumers keep working unchanged and the PR only adds optional fields, new endpoints, new features, or extra docs | package minor bump; schema minor bump; runtime API minor bump within the same major line |
| `internal` | no supported surface changes; refactors, tests, maintenance, or internal-only docs/process work | package patch bump at most; no schema or runtime API version bump |

## Supported Surface Classification

Use the public-surface inventory in `architecture/public_surface.toml` and
`docs/reference/public-surface.md` to record which kind of surface the PR
touches.

| Surface classification | Meaning | Release/doc expectation |
|---|---|---|
| `public_stable` | supported package entrypoint with normal compatibility guarantees | update docs, choose the correct `compat:*` label, and include `surface_classification` in the release fragment when a fragment is required |
| `public_experimental` | documented but intentionally unstable entrypoint | keep docs and release notes explicit that the surface is experimental |
| `internal` | unlisted `polisyos.*` path or pure internal implementation detail | normally no public-surface doc change and no public release callout unless operators must act |

## Label Taxonomy

### Kind Labels

- `kind:architecture`
- `kind:contract-schema`
- `kind:runtime-behavior`
- `kind:frontend`
- `kind:docs`
- `kind:ops-security`
- `kind:dependency-upgrade`

Apply more than one when a PR spans multiple surfaces.

### Compatibility Labels

- `compat:breaking`
- `compat:additive`
- `compat:internal`

Exactly one is required.

### Release Labels

- `release:breaking`
- `release:feature`
- `release:fix`
- `release:docs`
- `release:ops`
- `release:security`
- `release:none`

Exactly one is required. These labels determine how the PR is summarized in
human release notes and whether it needs migration callouts.

## Release-Note Mapping Rules

- `compat:breaking` should normally pair with `release:breaking`.
- Backward-compatible product or API additions should normally use
  `release:feature`.
- Backward-compatible bug fixes should normally use `release:fix`.
- Docs-only changes use `release:docs` when they materially change usage
  guidance; otherwise use `release:none`.
- Ops, workflow, release, or deployment changes use `release:ops` unless the
  primary impact is a security fix.
- Security-relevant fixes, credential-rotation events, or supply-chain
  remediations use `release:security`.
