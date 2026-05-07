# Design Tools (`tools/design`)

## Purpose

`tools/design/` holds Node/TypeScript helper scripts for brand, accessibility,
and ADR evidence that are driven from the frontend workspace.

These files are part of the authored tooling surface, but they are not exposed
through `polisyos-tools` because they depend on the runtime-dashboard Node
toolchain rather than the Python unified CLI.

## Entrypoints

| Entrypoint                               | Purpose                                                                                  |
| ---------------------------------------- | ---------------------------------------------------------------------------------------- |
| `uv run python tools/design/adr_lint.py` | Lint the curated Wave 1 ADR set for template shape and approved status.                  |
| `corepack pnpm run a11y:contrast`                  | Validate required token contrast pairs and check the generated contrast matrix artifact. |
| `corepack pnpm run a11y:contrast:write`            | Regenerate `docs/compliance/A11Y_CONTRAST.md` from the current token set.                |
| `corepack pnpm run a11y:motion`                    | Verify reduced-motion guards remain wired into the dashboard.                            |
| `corepack pnpm run a11y:color-blind`               | Run deterministic color-blind separation checks for critical semantic pairs.             |

All `corepack pnpm run a11y:*` commands are executed from
`apps/runtime-dashboard/package.json` and call the `tools/design/*.ts`
scripts via `node --experimental-strip-types`.

## Scope

- `adr_lint.py` is a repo-local Python helper and follows the normal Ruff-based
  Python hygiene surface.

- `check-contrast.ts`, `check-reduced-motion.ts`, and `check-color-blind.ts`
  are TypeScript helper scripts owned by the frontend accessibility contract.

- `_a11yColor.ts` is shared support code for those TypeScript checks.

## Reference Docs

- [Design Best In Class Plan](../../docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md)
- [VPAT](../../docs/compliance/VPAT.md)
- [A11Y Contrast Matrix](../../docs/compliance/A11Y_CONTRAST.md)
