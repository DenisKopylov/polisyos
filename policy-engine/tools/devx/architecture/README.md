# Architecture DevX (`tools/devx/architecture`)

## Purpose

`tools/devx/architecture` contains machine-readable guardrails and scaffolding for repository architecture surfaces: public surface, generated artifacts, deep-import baseline, workflow policy, and README/runbook/ADR templates.

## Where to Start

- Guardrails engine: `tools/devx/architecture/guardrails.py`.
- Unified scaffold entrypoint: `tools/devx/architecture/scaffold.py`.
- Source-of-truth manifests:
  `architecture/public_surface/contract.toml`,
  `architecture/generated_artifacts.toml`,
  `architecture/baselines/imports/deep_import.json`,
  `architecture/exceptions/guardrails.toml`.

- Generated docs it owns:
  `docs/reference/public-surface.md`,
  `docs/reference/generated-artifacts.md`,
  `architecture/guardrail_exceptions_registry.md`.

## Public Entrypoints

| Entrypoint                                                                                              | Purpose                                                                       |
| ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `uv run polisyos-tools architecture guardrails sync`                                                    | Regenerate inventories and generated architecture reference pages.            |
| `uv run polisyos-tools architecture guardrails check`                                                   | Check manifests, baselines, workflow/toolchain guardrails, and README policy. |
| `uv run polisyos-tools architecture scaffold package-readme ...`                                        | Generate a README scaffold from the current template/policy.                  |
| `uv run polisyos-tools architecture scaffold connector ...`                                             | Delegate connector scaffolding to the canonical tooling path.                 |
| `uv run polisyos-tools architecture scaffold {governance-pass,runtime-route,benchmark,adr,runbook} ...` | Create golden-path templates for new surfaces.                                |

## Depends On / Depended On By

- **Depends on:** `architecture/*.toml`, generated docs under `docs/reference/`,
  workflow files under `.github/workflows/`, package facades, and README policy.

- **Depended on by:** platform maintainers, docs/reference refresh, package
  owners, CI architecture checks, and new-subsystem scaffolding.

## Common Commands

The commands below were smoke-tested on `2026-04-17` unless explicitly marked as `conceptual`.

| Command                                                                                                                                  | Purpose                                                                         | Status                                      |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------- |
| `uv run polisyos-tools architecture scaffold package-readme --module polisyos.example --output src/polisyos/example/README.md --dry-run` | Check the README scaffold without writing files.                                | `smoke-tested`                              |
| `uv run polisyos-tools architecture scaffold connector --name MySource --type REST --dry-run`                                            | Check connector scaffolding through the unified architecture surface.           | `smoke-tested`                              |
| `uv run polisyos-tools architecture guardrails check`                                                                                    | Run the full guardrail validation across manifests and generated documentation. | `conceptual` (broad repository-wide gate)   |
| `uv run polisyos-tools architecture guardrails sync --skip-deep-import-baseline`                                                         | Regenerate inventories without rewriting the deep-import freeze.                | `conceptual` (updates checked-in artifacts) |

## Test And Verification

| Command                                                                                                                         | What it verifies                                                   | Status         |
| ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | -------------- |
| `uv run pytest -q tests/repo_quality/tools/test_architecture_phase3.py tests/unit/runtime/http/test_architecture_boundaries.py` | Guardrails, scaffold policy, and architecture-boundary invariants. | `conceptual`   |
| `uv run polisyos-tools validation check-docs-accuracy --repo-root .`                                                            | Generated architecture reference pages remain publishable.         | `smoke-tested` |

## Reference Docs

- [Public Surface Reference](../../../docs/reference/public-surface.md)
- [Generated Artifacts Reference](../../../docs/reference/generated-artifacts.md)
- [Documentation Inventory](../../../docs/reference/documentation-inventory.md)
- [Quality Gates Reference](../../../docs/reference/quality-gates.md)
- [Tool Reference](../../../docs/reference/tools.md)

## Current State

- `guardrails.py` is the source of truth for the public-surface inventory, deep-import
  baseline, and README freshness policy.
- Immediate source-child traversal is sorted before filesystem observations are recorded.
  Equivalent checkouts therefore preserve the complete inventory readset across
  directory enumeration orders; an actually added child still changes that readset.

- Deep-import analysis resolves ImportFrom names against importable source-tree
  children, including relative and star imports. A child is treated as a facade
  attribute only when complete declared exports include the name and source
  proves one direct module-level binding. The bounded export resolver admits
  legal `__future__` compiler directives from the interpreter's supported
  feature table without executing facade code. Unlisted, dynamic, and lazy-only
  names with colliding children emit reason-specific `deep_import_resolution`
  findings; unresolved candidates are never written into the deep-import baseline.

- `scaffold.py` is the unified golden-path scaffolding surface; new README/runbook/ADR
  templates should use it instead of ad hoc copy-paste.

- `conditional_exports.py` resolves up to 32 finite source profiles for closed,
  unrebound literal `importlib.util.find_spec(...) is not None` conditions. It
  delegates each selected source branch to the existing export/binding reader;
  it never imports a backend or evaluates its availability. JSON records typed
  `policyos.source-export-profile.v1` conditions and complete ordered names with
  runtime evaluation `UNRUN`; Markdown shows the separate profiles. A conditional
  family has no scalar `export_count`; common names remain in `exports` and
  `known_export_count`. Unknown conditions, unbound names and opaque mutations
  remain incomplete and fail the ordinary public-surface check.

- Isolated generated-artifact probes bind CLI timing records and their lock to
  the retained probe workspace's `diagnostics/` directory. They override an
  inherited host timing sink; neither diagnostic file is a generated artifact.
  The copied source and caller worktree remain protected by the ordinary write
  comparison, including writes to a source-local `.polisyos-tools/` directory.

- Connector scaffolding remains available through both the architecture surface and
  `polisyos-tools connectors`.

- Last updated: 2026-04-17
