# Contributor Start Here

Freshness: 2026-10-14
Owner: `@docs-owners`
Source of truth: `CONTRIBUTING.md`, `docs/style-guide.md`, `docs/reference/environment-matrix.md`,
`docs/reference/ownership.md`, `docs/reference/quality-gates.md`, `tools/registry.py`,
`tools/devx/workspace/**`, `tools/quality/validation/check_docs_gate.py`,
`tools/quality/validation/check_docs_freshness_baseline.py`, and the architecture references linked
below.
Source snapshot: `47e1e59b569a5b922611f71a7f53fb6320abea4c`; file-scoped `docs-style` inputs,
docs-gate path dispatch, and the docs-freshness baseline delegation were inspected at this pin.
This update did not execute commands, tests, or builds.

This page routes contributors to the detailed guide for their task. Product code, tools, and
contributor commands live under `policy-engine/`; run the commands below from that directory.

## Read first when the task changes system behavior

PolicyOS is the custodian of policy justification over time. Read the [causal operating system
north star](../system-design-decisions/policy-design-causal-operating-system-north-star.md) for the
product model and the [identity and custody boundary](../system-design-decisions/policyos-identity-and-custody-boundary.md)
before deciding which institution owns a function or claim. For governance, evidence, runtime
quality, or Policy Design Case work, also use the [failure and repair register](policy-design-case-failure-patterns.md)
before design and closeout. Package boundaries and supported imports are recorded in
`architecture/imports/policy.toml`, `architecture/public_surface/contract.toml`, and the nearest
package `README.md`.

## Supported contributor baseline

- Python `3.14.x`, `uv 0.9.21`, and Node `22.x` are the current contributor baseline. The
  [Environment Matrix](environment-matrix.md) is the reference for supported host surfaces.
- Use `corepack pnpm` for package commands; never call bare `pnpm`. The workspace pins pnpm
  `10.33.2` in `package.json`. In a fresh checkout, run
  `corepack pnpm install --frozen-lockfile` before trusting a TypeScript scanner.
- The canonical installed CLI is `uv run polisyos-tools <category> <command>`, exposed by
  `pyproject.toml` and routed through `tools/registry.py`. The lower-level `python -m tools.cli`
  form remains useful for direct CLI debugging.

The baseline and entrypoint names are defined in `pyproject.toml`, `.python-version`, `.nvmrc`,
`package.json`, `tools/devx/workspace/_common.py`, `tools/devx/workspace/bootstrap.py`, and
`tools/registry.py`. Source registration establishes command availability in the checkout; it does
not prove that an environment is installed or that a command passed. Use `doctor` and retain the
run receipt for claims about a particular machine or validation run.

!!! note "Installed-default evidence (P02 / E02 F)"
    When a change claims that an installed package consumes curated defaults, an import, registry
    row, or explicit-path invocation is not that evidence. The [failure and repair register](policy-design-case-failure-patterns.md)
    calls for a neutral installed consumer to read the actual defaults. Keep run receipts tied to
    the environment and pin that produced them. Receipts in the linked installation and quick-start
    guides apply only to the environment and date printed there.

## Before coding, trace one capability

For a behavior change, map one bounded capability, its owner, and the evidence for each step:
`contract → producer → persisted artifact/event → orchestration bridge → consumer`
→ `verification → external/audit/API/dashboard surface → negative semantic test`.
Keep the trace to the task you plan to change; a package or subsystem may contain both implemented
and intended paths.

- **Owner:** [Ownership](ownership.md) maps logical subsystem owners and tracked reviewer routing;
  use the nearest package `README.md` for package-local scope. Tracked routing does not prove that
  GitHub has applied a review rule.
- **Contract and source:** start from `architecture/imports/policy.toml` or
  `architecture/public_surface/contract.toml` when relevant, then follow the nearest package
  `README.md` to the canonical implementation and registry where present.
- **Verification:** use [Quality Gates](quality-gates.md), the owning test under `tests/`, and the
  relevant workflow under repository-root `.github/workflows/`. A listed test or command is a
  recipe, not evidence that it passed.
- **Known limits:** read the [failure and repair register](policy-design-case-failure-patterns.md)
  and the subsystem reference or runbook. Label proposed behavior and unresolved chain steps as
  such; do not infer a working capability from a contract, README, or command entrypoint alone.

When reporting checks, distinguish an **inspected check** (source, test, or workflow read at a named
pin), a **run recipe** (command offered for a contributor to execute), and an **actual result**
(command run with its source pin, environment, and result recorded). Historical receipts retain the
date and environment where they were produced.

## First contributor path

1. Check the [Environment Matrix](environment-matrix.md), then follow
   [Installation](../how-to/install.md) for the `runtime` or `docs` bootstrap profile.
2. Use [Getting Started](../tutorials/getting-started.md) for a first local walkthrough, or choose
   a role in [Onboarding Tracks](../how-to/onboarding/index.md).
3. Pick the detailed task guide from the map below. Read the nearest package README before changing
   a package boundary, and trace the affected capability before changing behavior.
4. Run the narrow gate for the changed surface. Use the broader `workspace verify` or
   `workspace ci-parity` only when the change scope calls for it.

## Choose a guide by task

| Task | Read | Source and first check |
| --- | --- | --- |
| Repository structure, imports, or supported APIs | [Repository Hygiene](repository-hygiene.md), [Public Surface](public-surface.md), [Quality Gates](quality-gates.md) | `architecture/imports/policy.toml`, `architecture/public_surface/contract.toml`; `uv run polisyos-tools architecture guardrails check` |
| Bootstrap, workstation preflight, or workspace CLI | [Installation](../how-to/install.md), [Tools reference](tools.md) | `tools/devx/workspace/{bootstrap,doctor,verify,ci_parity}.py`, `tools/devx/workspace/README.md`, `tools/registry.py`; tests in `tests/unit/core/phase0/test_workspace_commands.py`, `tests/unit/remediation/test_hyg_04.py`, `tests/repo_quality/tools/test_unified_cli.py`, and `tests/repo_quality/tools/test_workspace_ci_parity.py` |
| Documentation-only change | [Documentation Style Guide](../style-guide.md), [How-to index](../how-to/index.md) | Use the docs-only path below; `docs/style-guide.md` is the authored-doc standard |
| Cross-surface migration or post-refactor cleanup | [Post-Refactor Migration](../how-to/post-refactor-migration.md) | `uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main` plus the matching subsystem gate |
| Runtime endpoint or API contract | [REST API](api/index.md), [Add Runtime Route](../how-to/add-runtime-route.md) | Runtime contract check from the guide plus the tests for the touched route |
| Public Python facade or ABI-visible IR type | [Public Surface](public-surface.md), [Add Public Facade](../how-to/add-public-facade.md), [Manage Schemas](../how-to/manage-schemas.md), [IR Schema Catalog](ir/schema-catalog.md) | `uv run polisyos-tools architecture guardrails check`; schema check from the guide |
| Dashboard API client | [REST API](api/index.md), [Update Runtime Dashboard API Client](../how-to/update-runtime-dashboard-api-client.md) | Use the generation and contract commands in the guide; frontend commands use `corepack pnpm` |
| Connector or data source | [Writing a Connector](../tutorials/writing-a-connector.md), [Add Data Source](../how-to/add-data-source.md), [Connector Contributing](../connectors/CONTRIBUTING.md) | `uv run polisyos-tools lint lint-connectors` |
| Governance, evidence, or Policy Design Case | [Creating a Governance Pass](../tutorials/creating-governance-pass.md), [Write Governance Pass](../how-to/write-governance-pass.md), [Failure and Repair Patterns](policy-design-case-failure-patterns.md) | Identify relevant patterns before design; use the owning package's focused tests |
| Runtime operation or incident | [Deploy Runtime](../how-to/deploy-runtime.md), [Use Control Plane](../how-to/use-control-plane.md), [Debug Failed Run](../how-to/debug-failed-run.md) | Follow the runbook and contract checks for the affected operational surface |
| Security or compliance review | [Security and Compliance Operations](security-compliance.md), [Platform Acceptance Audit](operations/platform-acceptance-audit.md) | Focused security tests; use `workspace acceptance-audit` for platform acceptance evidence |
| Release, generated output, or rollout | [Manage Generated Artifacts](../how-to/manage-generated-artifacts.md), [Review Migrations and Rollouts](../how-to/review-rollouts.md), [Release Policy](../how-to/release-policy.md) | Use the documented lifecycle owner and path-aware docs gate when the change is docs-sensitive |

## Role entry points

| Role | Start page | First scoped path |
| --- | --- | --- |
| New contributor | [Getting Started](../tutorials/getting-started.md) | [Installation](../how-to/install.md), then the task map above |
| Backend engineer | [Backend Engineer](../how-to/onboarding/backend-engineer.md) | `uv run polisyos-tools workspace verify --backend-only --skip-doctor` |
| Frontend engineer | [Frontend Engineer](../how-to/onboarding/frontend-engineer.md) | `uv run polisyos-tools workspace verify --frontend-only --skip-doctor`; package commands use `corepack pnpm` |
| Platform / Ops | [Platform / Ops Engineer](../how-to/onboarding/platform-ops-engineer.md) | `uv run polisyos-tools workspace doctor --list-surfaces`, then the relevant closeout |
| Security / Compliance | [Security / Compliance Reviewer](../how-to/onboarding/security-compliance-reviewer.md) | Focused security tests or `uv run polisyos-tools workspace acceptance-audit` |
| Domain / Policy reader | [Domain / Policy Reader](../how-to/onboarding/domain-policy-reader.md) | [First Policy Analysis](../tutorials/first-policy-analysis.md) |

## Docs-only workflow

The `docs` profile selects Python extras `lint + docs`; the profile alone does not skip other
bootstrap steps. The browserless command in [Installation](../how-to/install.md) adds
`--skip-frontend --skip-doctor`, which skips frontend/Playwright installation and skips `doctor`
entirely. It still installs pre-commit hooks unless `--skip-hooks` is also supplied. Bare
`bootstrap --profile docs` keeps the default hooks, frontend, Playwright, and `doctor` steps; that
`doctor` checks Node `22.x`, Corepack/pnpm lockfiles, and generated contracts. After prerequisites
are prepared, make a small first contribution by improving an existing page selected from the
[How-to index](../how-to/index.md) or the task map above. Follow its owner and source notes when
present; if ownership is unclear, use [Ownership](ownership.md) and the nearest package README.
With an existing docs environment, start with a file-scoped style check from `policy-engine/`
(substitute the page you edited):

```bash
uv run polisyos-tools workspace docs-style docs/reference/contributor-start-here.md
```

`workspace docs-style` accepts explicit Markdown files or directories through
`tools/devx/workspace/docs_style.py`; that check covers style for the selected files, not site
navigation, rendered links, or source accuracy. If the Markdown hook environment has not been
prepared, its first run may prepare that isolated hook environment; it is separate from installing
the frontend workspace. See [Installation](../how-to/install.md#docs-only-onboarding) for bootstrap
side effects. For a published docs change, run the broader closeout checks from `policy-engine/`:

```bash
uv run polisyos-tools workspace docs-style docs/
uv run --extra docs python -m mkdocs build --strict
uv run polisyos-tools validation check-docs-accuracy --repo-root .
```

For a documentation-sensitive PR, the path-aware gate dispatches checks selected by the changed
paths. A docs or README change dispatches the docs-freshness baseline and strict MkDocs build; the
baseline owns the docs-accuracy invocation. Path-aware selection adds relevant checks for other
changed surfaces, but does not turn those publication checks into per-file checks:

```bash
uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main
```

`workspace ci-parity --skip-browser` is the wider local umbrella and is not the routine docs-only
path. The documented commands are defined by the current CLI and workspace source; commands listed
here are not execution receipts.
