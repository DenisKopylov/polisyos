# Contributor Start Here

Freshness: 2026-10-14
Owner: `@docs-owners`
Source of truth: `CONTRIBUTING.md`, `docs/style-guide.md`, `docs/reference/environment-matrix.md`,
`tools/registry.py`, `tools/devx/workspace/**`, and the architecture references linked below.

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

## First contributor path

1. Check the [Environment Matrix](environment-matrix.md), then follow
   [Installation](../how-to/install.md) for the `runtime` or `docs` bootstrap profile.
2. Use [Getting Started](../tutorials/getting-started.md) for a first local walkthrough, or choose
   a role in [Onboarding Tracks](../how-to/onboarding/index.md).
3. Pick the detailed task guide from the map below. Read the nearest package README before changing
   a package boundary.
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

Use the `docs` profile described in [Installation](../how-to/install.md). It skips frontend and
Playwright installation, but the default bootstrap `doctor` still checks Node `22.x` and the
Corepack/pnpm lockfile. After its prerequisites are prepared, run these checks from `policy-engine/`:

```bash
uv run polisyos-tools workspace docs-style docs/
uv run --extra docs python -m mkdocs build --strict
uv run polisyos-tools validation check-docs-accuracy --repo-root .
```

For a documentation-sensitive PR, the path-aware gate dispatches the additional checks selected by
the changed paths:

```bash
uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main
```

`workspace ci-parity --skip-browser` is the wider local umbrella and is not the routine docs-only
path. The documented commands are defined by the current CLI and workspace source; commands listed
here are not execution receipts.
