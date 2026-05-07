# Release, Versioning, and Deprecation Policy

This page defines the version namespaces used in PolicyOS and the deprecation
rules that keep them understandable.

Released versions are immutable. If something changes after release, it ships
as a new version rather than replacing an existing artifact.

## Inputs

- a change that may affect package, schema, runtime API, generated frontend
  contract, or deprecation posture;

- the current release fragment set and versioned source-of-truth files;
- a clear compatibility classification for the affected surface.

## Output

- the correct versioning/deprecation decision for the change;
- the required release-note, migration-guide, and docs follow-up for that
  decision.

## Commands

```bash
cd policy-engine
uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main
uv run polisyos-tools workspace ci-parity --skip-browser
uv run python tools/quality/validation/control_plane_supply_chain_contracts.py
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
```

## Release Prep Workflow

Before a release tag is created:

1. Update `pyproject.toml` and `apps/runtime-dashboard/package.json` to the
   target version.
2. Freeze the selected `release-fragments/unreleased/` entries into
   `_build/release-fragments/<version>/`. This is generated/archive output,
   not release source.
3. Review the generated release notes for compatibility, migration,
   schema/runtime/API, and limitation coverage.
4. Re-run the docs drift gate and confirm the rollback path in
   [`docs/runbooks/docs-publication-failure.md`](../runbooks/docs-publication-failure.md):

   ```bash
   uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main
   ```

5. If docs publication fails after the release candidate is cut, revert or
   hotfix the docs/nav/release-doc change set before retrying publication; do
   not bypass strict docs validation as a permanent workaround.
6. Cut the signed `v<version>` tag only after that immutable snapshot exists.

The release workflow validates the versioned snapshot, not the mutable
`unreleased/` directory.

## Promotion Topology And Migration Gates

Release promotion uses the topology in
`ops/release/deployment-topology.toml` and the staging/production gates in
`ops/release/promotion-gates.toml`.

Breaking runtime-state, API schema, IR schema, or persisted artifact changes
must not promote from staging to production until the release evidence contains:

- the affected class entry in `ops/migrations/migration-contracts.toml`;
- current operator guidance in `ops/migrations/<class>/README.md`;
- `docs/runbooks/migration-release-promotion.md` coverage for the operator
  action, rollback, and follow-up;
- release notes or migration-guide text for the affected consumer/operator.

Python migration helpers are operator-facing only through their
`helper_binding` entries in `ops/migrations/migration-contracts.toml`. If a
helper changes behavior, update the binding and the owning class README in the
same release candidate.

## Supply-Chain Release Controls

The Phase 5.9 source of truth for release trust controls is
`architecture/control_plane_supply_chain.toml`. Release candidates and
dependency-lock changes must satisfy these expectations:

- release candidates generate a CycloneDX SBOM, vulnerability report, policy
  evidence, keyless signatures, and build provenance attestations through
  `.github/workflows/release.yml`;
- dependency-lock changes require SBOM refresh evidence or an explicit
  non-commit release-SBOM rationale tied to the `release-sbom` generated
  artifact family in `architecture/generated_artifacts.toml`; the trigger
  paths are `.github/renovate.json`, `uv.lock`, and `pnpm-lock.yaml`;
- Python wheels, source distributions, runtime dashboard bundles, and checksum
  manifests have provenance/signing targets where release tooling supports
  them;
- dependency and security scan gates run before release canary, signing,
  attestation, and publication;
- OpenSSF Scorecard, SBOM, SLSA provenance, and signed-artifact evidence are
  reported through
  `docs/archive/reports/supply-chain-control-crosswalk.json`.

The generated SBOM output stays under `_build/release/sbom/` or CI release
artifacts; it is not committed directly unless a later contract explicitly
promotes a reviewed evidence file.

Regenerate the crosswalk whenever release phases, artifact expectations,
workflow write permissions, or external control mappings change:

```bash
uv run python tools/quality/validation/control_plane_supply_chain_contracts.py \
  --crosswalk-json docs/archive/reports/supply-chain-control-crosswalk.json
```

## Release Path Lifecycle

The Phase 1.2 lifecycle decision defines the release path split:

| Path | Lifecycle | Rule |
| --- | --- | --- |
| `release/**` | `source_committed` | Committed release input, evidence templates, durable release ledgers, and owner-approved release evidence. |
| `_build/release/**` | `generated_ignored` | Generated release-candidate output only. No release source file may live here. Default retention is 90 days unless promoted to release evidence. |
| `release-fragments/unreleased/**` | `source_committed` | Committed release-note input while changes are still landing. |
| `_build/release-fragments/**` | `generated_ignored` | Generated frozen/archive release-note output and ignored by git. |
| `_build/scratch/**` | `scratch_ignored` | Local scratch only. Safe cleanup may remove it without release-owner review. |
| `_cache/**` | `scratch_ignored` | Recomputable local cache. Safe cleanup may remove it without release-owner review. |
| outer-root `_build/**`, `_cache/**`, `tmp/**`, `.tmp_*/` | `scratch_ignored` | Wrong-root residue. Remove instead of migrating into source roots. |

Promotion from `_build/**` to a committed evidence target requires a reviewed
PR that names the owner, generator, verifier, and target path. Do not hand-edit
generated release output in `_build/**` as a source of truth.

Lifecycle validation and cleanup use a dry-run first command:

```bash
uv run polisyos-tools workspace release-build-cache-lifecycle check
uv run polisyos-tools workspace release-build-cache-lifecycle cleanup
uv run polisyos-tools workspace release-build-cache-lifecycle cleanup --apply
```

The cleanup command refuses targets that contain tracked files and protects
`release/**` plus `release-fragments/unreleased/**`.

## Version Namespaces

| Namespace                       | Format                                                              | Source of truth                                                                    | Meaning                                                                    |
| ------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Package release version         | `MAJOR.MINOR.PATCH`                                                 | `pyproject.toml` and release metadata                                              | Version of the published product package and release notes line            |
| Architecture milestone language | `Phase N`, `WS-nX`, ADR IDs, milestone bundle names                 | docs and planning artifacts                                                        | Planning and architecture vocabulary only; not a compatibility contract    |
| Schema version                  | `MAJOR.MINOR`                                                       | model `schema_version` fields and committed schema snapshots                       | Compatibility version for serialized schemas and ABI snapshots             |
| Runtime API version             | path major plus semantic version, for example `/api/v1` and `1.2.0` | runtime app, OpenAPI snapshot, capability manifest                                 | Compatibility version for the public HTTP API                              |
| Frontend contract generation    | exact generated artifacts derived from the committed OpenAPI file   | `schemas/runtime_api_v1.openapi.json`, generated client files, dashboard API types | Build-time synchronization state for frontend consumers of the Runtime API |

Architecture milestone names are never a substitute for release, schema, or
runtime API version numbers.

## Package Release Version Policy

PolicyOS uses semantic versioning for package releases with one pre-1.0
clarification:

- while `MAJOR` is `0`, breaking supported-surface changes bump `MINOR`;
- backward-compatible additions bump `MINOR`;
- fixes, refactors, docs-only, and internal-only changes bump `PATCH`.

Once the project reaches `1.0.0`, standard semantic versioning applies:

- breaking change -> `MAJOR`
- backward-compatible addition -> `MINOR`
- backward-compatible fix -> `PATCH`

## Schema Version Policy

Schema versions use `MAJOR.MINOR`.

- additive backward-compatible changes, such as new optional fields or new enum
  values explicitly declared compatible by policy, bump `MINOR`;

- removals, renames, type changes, newly required fields, or other
  compatibility breaks bump `MAJOR`;

- docs-only or implementation-only changes that do not alter the serialized
  contract do not change schema version.

Schema changes must be reflected in committed snapshots and reviewed as contract
changes, not only as code edits.

## Runtime API Version Policy

Runtime API compatibility has two layers:

- the path major, for example `/api/v1`, defines the public compatibility line;
- the semantic version value reported by the runtime and documented with the
  OpenAPI contract describes additive vs breaking evolution within that line.

Rules:

- additive backward-compatible endpoint or field additions stay on the current
  path major and bump the runtime API minor version;

- fixes that do not change the supported contract bump the runtime API patch
  version;

- breaking changes require a new path major and a matching runtime API major
  version, for example `/api/v2` with `2.0.0`.

## Frontend Contract Generation Policy

Frontend contract generation does not define its own public version namespace.
It tracks the committed Runtime API contract.

When a PR changes Runtime API shape or generated frontend contract surfaces, the
same PR must update or verify:

- `schemas/runtime_api_v1.openapi.json`
- `packages/runtime-api-client/runtimeApiClient.ts`
- `packages/runtime-api-client/runtimeApiClient.js`
- `apps/runtime-dashboard/src/api/types.ts`, when generated types change
- runtime contract verification and frontend contract checks

Generated artifacts must not drift from the committed OpenAPI source of truth.

## Deprecation Window Policy

Deprecated schema fields, runtime API fields, config keys, and generated-client
surfaces stay supported for at least:

- one subsequent minor package release; and
- 90 days after the first published deprecation notice.

Use the longer of those two windows. Faster removal is allowed only for
security, data-corruption, or legal-compliance reasons, and the release notes
must say so explicitly.

## Deprecation Announcement Requirements

Every deprecation must be announced in all relevant places:

- the PR classification and labels;
- the release notes entry for the release that introduces the deprecation;
- the affected reference or how-to docs;
- warnings, compatibility notes, or operator-facing messaging when the runtime
  can surface them safely.

## Tooling Deprecation Requirements

Commands exposed through `polisyos-tools` are operator-facing surfaces when
they appear in docs, workflows, or release runbooks. Deprecating or quarantining
one requires:

- `status`, `replacement`, and `reason` metadata in `tools.registry`;
- regenerated `docs/reference/tools.md`;
- removal from CI workflows unless the job is explicitly testing the
  compatibility wrapper;

- a release fragment when the command is part of an operator or contributor
  workflow.

Deprecated and quarantined commands are not normal golden paths. They require
explicit operator intent at the CLI boundary and must point to the replacement
command in both runtime messaging and generated reference docs.

## Release Notes Curation Requirements

Each release snapshot must cover all of the following sections across the
selected fragment set:

- compatibility notes;
- migration notes;
- schema/runtime/API changes;
- known limitations.

The workflow refuses to publish a release when any of those sections would be
empty.

## When a Migration Guide Is Required

A migration guide is required when a change:

- removes or renames a supported schema or runtime API field;
- introduces a schema major bump;
- introduces a runtime API major bump or new path major;
- requires regenerating consumers or coordinating a frontend/client rollout;
- changes config, secrets, deployment steps, or operational runbooks in a way
  that operators must act on before or during rollout.

For breaking runtime-state, API schema, IR schema, or persisted artifact
changes, this is also a promotion gate: update the owning `ops/migrations/`
class README and [Migration Release Promotion](../runbooks/migration-release-promotion.md)
before approving production promotion.

## Public Surface Classification Linkage

Public-surface classification and compatibility classification are related, but
they answer different questions:

- `public_stable` / `public_experimental` / `internal` says **what kind of
  surface changed**;

- `breaking` / `additive` / `internal` says **how the change affects
  consumers/operators**.

Use them together:

- changes to `public_stable` entrypoints must be treated as supported-surface
  work: choose the correct `compat:*` label, update the relevant reference doc,
  and add `surface_classification = "public_stable: <entrypoint>"` to the
  release fragment when a fragment is required;

- changes to `public_experimental` entrypoints should stay visible in docs and
  release notes, but they may evolve without the same long-term compatibility
  promises; use `surface_classification = "public_experimental: <entrypoint>"`
  in the release fragment when the change is user-facing, operator-facing, or
  otherwise part of the shipped story;

- internal-only changes stay off the public-surface inventory and normally use
  `compat:internal`; if they still need a fragment because operators must care,
  record `surface_classification = "internal: internal-only"` explicitly.

## Practical Classification Rules

- use `breaking` when an existing supported consumer or operator must change
  behavior;

- use `additive` when existing integrations keep working unchanged;
- use `internal` when no supported surface changes.

That classification drives both the version bump and the migration-guide
expectation.

## Rollback / Mitigation

- If the release draft chooses the wrong compatibility class, fix the
  classification, fragments, and docs before tagging anything.

- If release docs or migration notes are incomplete, stop the release candidate
  rather than cutting a tag and planning to "fill it in later".

- If runtime or schema checks disagree with the intended version story, treat
  that as a contract mismatch and resolve it before publication.

## Compatibility Release Gates

Phase 5.10 keeps compatibility release gates report-only. Before promoting a
release candidate, run:

```bash
uv run polisyos-tools release check-compatibility-release-gates --fail-on-contract-errors
```

Breaking compatibility changes must be represented by structured
`[[compatibility_change]]` entries in the selected release fragments. Those
entries carry the compatibility class, owner, version owner, deprecation window,
linked migration/runbook docs, generated-client compatibility, and public-surface
inventory review status when relevant.

## Troubleshooting

- If you are unsure whether a migration guide is required, bias toward writing
  one whenever operators or downstream consumers must change behavior.

- If a generated frontend/client artifact changed because of a runtime contract
  update, do not classify that as docs-only or internal-only work.

- If version bump arguments depend on unsupported deep-import or internal-only
  paths, revisit the public-surface classification first.
