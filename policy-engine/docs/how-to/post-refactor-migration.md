# Post-Refactor Migration

Related how-to: [Add Runtime Route](add-runtime-route.md), [Add Public Facade](add-public-facade.md), [Add Schema-Backed IR Type](add-schema-backed-ir-type.md), [Update Runtime Dashboard API Client](update-runtime-dashboard-api-client.md).
Related reference: [Contributor Start Here](../reference/contributor-start-here.md), [Public Surface](../reference/public-surface.md), [Generated Artifacts](../reference/generated-artifacts.md), [TRINITY contract](../contracts/TRINITY.md).

> Use this guide when a branch, script, or local mental model still reflects the
> pre-refactor layout and you need to translate it onto the current canonical
> surfaces quickly.

## Inputs

- a branch, diff, or local notes that still refer to legacy routes, deep imports,
  stale generated artifacts, or pre-Trinity analytical flows;

- the subsystem you are actually changing: runtime, frontend, IR, Fabric,
  Foundry, Scientist, or docs only;

- the current repo checkout with `uv`, Python, and any relevant frontend tooling
  already installed.

## Output

- a change set aligned with the current public facades, Trinity-first IR model,
  runtime contract chain, and published docs;

- regenerated artifacts only where the current source-of-truth surfaces require
  them;

- a verification trail that matches the changed subsystem instead of relying on
  historical commands.

## Commands

```bash
cd policy-engine
python3 -m tools.cli workspace doctor --list-surfaces
uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main
uv run polisyos-tools architecture guardrails check
uv run --extra ml polisyos-tools diagnostics gen-schema --check
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/check_runtime_api_contract.py
```

Use only the commands that match the surface you touched. The point of the
post-refactor workflow is to verify the current source of truth, not to run
every historical gate out of habit.

## 1. Reframe the change around the current canonical layers

The refactor standardized the main contributor paths around these boundaries:

| Old instinct                                             | Current canonical surface                                                                 |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Deep imports straight into implementation modules        | package facades listed in [Public Surface](../reference/public-surface.md)                |
| `PolicySurfaceIR` / surface-first analytical entrypoints | `ProblemFrame` + `PolicySpec` + `ModelSpec` + `TrinityBundle`                             |
| Runtime code change without contract regen               | route/service change -> committed OpenAPI snapshot -> generated client -> dashboard types |
| Dashboard or client drift fixed manually                 | regenerate from the runtime contract chain                                                |
| Generic "run everything" validation                      | path-aware docs/runtime/schema/public-surface checks                                      |

If the diff touches more than one row in that table, treat it as a
cross-surface migration rather than a local refactor.

## 2. Migrate imports to public facades first

Before changing behavior, remove stale import assumptions:

- prefer `from polisyos.ir import ...`, `from polisyos.foundry import ...`,
  `from polisyos.scientist import ...`, and other supported package facades;

- avoid documenting or depending on deep imports unless the page explicitly says
  the path is internal;

- if you must expose a new supported import path, follow
  [Add Public Facade](add-public-facade.md) and re-run the public-surface
  guardrails.

This keeps migration work aligned with the current compatibility contract
instead of silently adding new unstable entrypoints.

## 3. Translate legacy analytical flows onto Trinity

For policy analysis or IR work, the stable path is Trinity-first:

1. model the problem with `ProblemFrame`;
2. model interventions with `PolicySpec`;
3. model execution semantics with `ModelSpec`;
4. bundle them as `TrinityBundle`;
5. pass registry/data references into Foundry and Scientist instead of reviving
   removed surface-level shortcuts.

If you still have notes or scripts using `PolicySurfaceIR` or other frozen
legacy shapes, translate them using the Trinity-only migration notes tracked in
the repo under `docs/migration/phase4_trinity_only.md`, then continue in the
current tutorials/how-to pages.

For new ABI-visible IR work, do not patch schemas ad hoc. Use
[Add Schema-Backed IR Type](add-schema-backed-ir-type.md) and
[Manage Schemas](manage-schemas.md).

## 4. Treat runtime and frontend as one contract chain

After the refactor, runtime HTTP work is not complete until the consumer chain
is coherent:

1. route and DTO changes land under `src/polisyos/runtime/http/**`;
2. the committed source of truth stays in
   `schemas/runtime_api_v1.openapi.json`;
3. generated client artifacts under `frontend/runtime-api-client/` are updated
   when the contract changes;
4. dashboard API types under
   `frontend/runtime-dashboard/src/api/types.ts` are regenerated if needed;
5. docs reference the current route/contract behavior.

Use the focused guides instead of mixing concerns:

- [Add Runtime Route](add-runtime-route.md) for route creation or route-only
  changes;

- [Update Runtime Dashboard API Client](update-runtime-dashboard-api-client.md)
  for generated contract-chain updates;

- [Deploy Runtime](deploy-runtime.md) for operator-facing deployment behavior.

## 5. Regenerate only the artifacts the new source of truth requires

The refactor made artifact ownership more explicit. Typical mapping:

| If you changed                                        | Then the artifact/doc follow-up is usually                     |
| ----------------------------------------------------- | -------------------------------------------------------------- |
| package `__init__.py` facade or public exports        | public-surface guardrails and related README/docs refresh      |
| ABI-visible IR model                                  | schema snapshots and schema/reference checks                   |
| runtime route, request/response DTO, or OpenAPI shape | runtime contract check and frontend contract regeneration      |
| connector contracts or profiles                       | Fabric connector/reference docs and schema-governance evidence |
| governance/workflow semantics                         | Scientist reference/how-to/tutorial updates                    |

If you cannot name the source of truth for a generated file, stop and find it
before regenerating anything. That pause is cheaper than publishing fresh drift.

## 6. Update the doc lane that matches the real consumer

D4 docs are persona- and workflow-oriented. After a refactor-era change, update
the page that a real user of that surface would open first:

- contributor entry point: [Contributor Start Here](../reference/contributor-start-here.md);
- backend/public surface/runtime route work: backend onboarding + runtime/public
  facade how-to docs;

- frontend contract changes: frontend onboarding + frontend reference;
- operator changes: deploy/control-plane/release/runbook docs;
- policy-analysis flow changes: first-policy-analysis tutorial plus matching IR /
  Foundry / Scientist references.

This keeps the post-refactor tree task-oriented instead of pushing readers back
into archived plans.

## 7. Verify the migration before merge

Use the narrowest proof that covers the changed surface:

- public facade change: `uv run polisyos-tools architecture guardrails check`;
- IR/schema change: `uv run --extra ml polisyos-tools diagnostics gen-schema --check`;
- runtime contract change:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/check_runtime_api_contract.py`;

- docs-sensitive change:
  `uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main`.

If the change crosses multiple surfaces, run the focused checks for each one
instead of assuming one umbrella command proves everything.

## Rollback

- If the migration introduced accidental public-surface exposure, revert the
  facade/export change first and re-run the guardrails.

- If the migration changed IR or runtime contracts unintentionally, restore the
  committed snapshots before regenerating anything else.

- If frontend/generated artifacts drifted from runtime truth, revert the
  generated output and re-run only the canonical contract-generation path.

- If a doc rewrite moved faster than the code, roll the doc back to the last
  verified statement instead of preserving speculative post-refactor claims.

## Troubleshooting

- If you are unsure which guide owns the change, start from
  [Contributor Start Here](../reference/contributor-start-here.md) and choose
  the row that matches the supported surface, not the implementation detail.

- If an old note mentions a legacy runtime or surface-IR path, assume it is
  historical until a current reference page confirms otherwise.

- If multiple generated artifacts drift at once, identify the earliest source of
  truth in the chain before touching downstream files.

- If verification feels "too big", that usually means the diff crosses more than
  one canonical surface and should be split or documented as a coordinated
  migration.
