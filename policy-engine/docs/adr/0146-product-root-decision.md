# ADR-0146: Product Root Decision

## Status

Accepted

## Date

2026-05-05

## Context

The Phase 0.2 root topology inventory found that the outer Git repository root
contains only repository control-plane files, the `policy-engine/` product tree,
one loose Renovate configuration, and ignored local residue such as
`_cache/ruff/**` and `tmp/phase3a_*`.

ADR-0096 already made `policy-engine/` the canonical product root. Phase 1.1 of
the Repository Best-In-Class remediation program needs the stronger repository
topology decision: either physically move the Git root, keep an explicit wrapper
root, or leave the current half-state. The decision has to unblock Wave 2
cleanup without bundling source package moves.

## Decision

1. Select **Option B: keep the outer Git root as an honest repository wrapper
   and GitHub control plane, with `policy-engine/` as the effective product root
   for all product workflows**.
2. Option A, moving the Git root to `policy-engine/`, is not selected for this
   phase. It can be reopened only through a dedicated repository migration
   window that owns GitHub rulesets, CODEOWNERS discovery, workflow locations,
   release publishing, branch protection, and remote deployment path migration.
3. Option C, keeping the current half-state, remains rejected. Product source,
   product docs, product tests, product tools, product ops, release inputs,
   package manifests, and product runtime-state contracts must live under
   `policy-engine/`.
4. The outer Git root allow-list is limited to repository control plane:
   `.github/**`, `.gitignore`, `.gitattributes`, optional outer editor metadata
   such as `.editorconfig`, and the `policy-engine/` product root.
5. Rejected outer-root path classes are product source, product docs/support
   docs, package manifests and lockfiles, release logic, test fixtures, local
   data, generated output, runtime state, cache directories, scratch/tmp paths,
   local reports, duplicate virtual environments, and source-adjacent tool
   residue.
6. The selected target placement for Renovate is `.github/renovate.json`.
   The outer-root `renovate.json` transition was retired on 2026-05-07; any
   future fallback requires a new ADR and a fail-closed control-plane update.
7. Outer-root `_cache/ruff/**`, `tmp/phase3a_*`, and future wrong-root residue
   are cleanup candidates, not product state. Wave 2 cleanup must dry-run the
   deletion set, promote any still-needed evidence into
   `policy-engine/docs/archive/reports/**`, and then delete or move residue
   into product-local `_cache/`, `_build/.tmp/`, or `.polisyos/` as appropriate.
8. Root topology gates must require:
   - no product source outside `policy-engine/`;
   - an outer-root allow-list limited to control-plane files;
   - no wrong-root cache, runtime, build, scratch, or local data paths;
   - documented product commands running from `policy-engine/` or a declared
     sub-root;
   - CI product jobs using `working-directory: policy-engine` or a declared
     product sub-root, with outer-root jobs limited to GitHub/repository
     control-plane audits.
9. The outer root README remains absent for this decision. If GitHub landing
   page needs a gateway README later, it must be a minimal control-plane pointer
   to `policy-engine/README.md`, not product documentation.
10. Rollback for this decision covers only path, workflow, Renovate, ignore,
    docs, and control-plane contract changes. It explicitly excludes bundling
    source package moves, public API moves, or JavaScript workspace relocation.

## Consequences

The repository keeps GitHub-native control-plane behavior while giving people,
CI, tools, and docs one product root. Wave 2 can clean wrong-root residue,
validate Renovate placement, and update path-prefix controls without reopening
the root question.

The tradeoff is that some workflows still need to distinguish `GIT_ROOT` from
`PRODUCT_ROOT`. That distinction is intentional and must remain explicit in
CI, workspace doctor checks, topology gates, and contributor docs.

## Concrete impact

- Decision record: this ADR.
- Contract updates: `architecture/topology.toml` records the selected option,
  outer-root allow-list, rejected path classes, gate requirements, and Renovate
  target.
- Ignore policy: root `.gitignore` explicitly treats outer `_cache/` and
  `_build/` as wrong-root ignored residue pending cleanup.
- Docs: repository topology references the Option B wrapper contract and Wave 2
  cleanup/update requirements.
- Phase handoff: Wave 2.1 owns residue cleanup, Wave 2.8 owns control-plane
  path-prefix cleanup, and Wave 2.7 owns JavaScript workspace relocation after
  this decision.
- Rollback checklist: revert root contract/docs/ignore/Renovate/workflow
  patches only; do not include source package or JS workspace moves in the same
  rollback.

## Related Decisions

- Extends: ADR-0096 Canonical Product Root and Workspace Boundary.
- Extends: ADR-0111 Workspace Root Boundary as a SOTA Contract.
- Extends: ADR-RSR-0130 Workspace Boundary.
- Related: ADR-RSR-0131 Build Output and Cache Umbrella.
