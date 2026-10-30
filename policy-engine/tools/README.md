# Tools (`tools/`)

## Purpose

`tools/` is the canonical executable surface of `policy-engine`: it provides the unified `polisyos-tools` CLI, a zoned implementation layout, and historical records of retired compatibility paths.

## Early source-execution evidence

`tools/authority` starts an isolated, no-site host and a fresh recorded child
for an existing target, for example `tools/authority tools ...`,
`tools/authority runtime ...`, `tools/authority server ...`, or
`tools/authority test ...`. The test route is serial and disables automatic
plugin loading. `tools/authority diagnose` reports the host profile and any
available confidence-ledger diagnostic.

The host selects Python sources from the committed Git tree and records an
initializer only when its source matches those selected bytes. A mismatch may
still run as candidate work, without producing qualifying execution evidence.
The host uses the checkout's existing `.venv`; tests and non-Python data are
outside this source selection.
The unified tools dispatcher offers the host another diagnostic handoff after
a preflight lookup or tool import has loaded the ledger. An unavailable or
unverified handoff leaves the command in the candidate band.
The shell supplies a minimal environment, so configurations needed by services
must be admitted separately. A recorder or diagnostic alone does not establish
N9 authority: provider, decision-state, currentness, and protected-use premises
remain the confidence ledger's responsibility. Direct console scripts and
module invocations remain candidate routes until they use the early host.

## Where to Start

- CLI boundary: `pyproject.toml` (`[project.scripts] polisyos-tools = "tools.cli:main"`).
- Command router: `tools/cli.py`.
- Tool metadata, aliases, dependency graph, and documentation generation: `tools/registry.py`.
- Canonical implementation roots:
  `tools/devx/`, `tools/quality/`, `tools/ops_runners/`,
  `tools/research/`.
- Operational runner implementation lives in `tools/ops_runners/**`.
  Declarative operational contracts live in `ops/**`.

- Non-CLI design/a11y helper surface: `tools/design/`.

## Public Entrypoints

| Entrypoint                                   | Contract                                                                              |
| -------------------------------------------- | ------------------------------------------------------------------------------------- |
| `uv run polisyos-tools <category> <command>` | Primary human/CI entry point for all tools.                                           |
| `python -m tools.cli`                        | Low-level CLI boundary for debugging and embedding.                                   |
| `tools/design/*`                             | Node/TypeScript design and accessibility helpers invoked from the frontend workspace. |
| `docs/reference/tools.md`                    | Generated reference for the public command catalog.                                   |

## Depends On / Depended On By

- **Depends on:** `tools.lib/*`, zoned category packages, `pyproject.toml`,
  `uv`, and registry metadata in `tools/registry.py`.

- **Depended on by:** contributor workflows, local quality gates,
  `.github/workflows/*`, the generated tool reference, onboarding, and release/ops
  automation.

## Zones

| Zone       | Categories                                                                                                      | Purpose                                                                                    |
| ---------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `devx`     | `workspace`, `architecture`, `connectors`, `foundry`                                                            | contributor setup, scaffolding, repo structure, codegen                                    |
| `quality`  | `lint`, `diagnostics`, `validation`, `testing`, `ci`                                                            | quality gates, diagnostics, validation, mutation/integration checks                        |
| `ops`      | `calibration`, `cloud`, `data`, `deploy`, `ops-experiments`, `migrations`, `release`, `runtime`, `ukraine_data` | CLI zone backed by `tools/ops_runners/**` for runtime/release/data/cloud operational flows |
| `research` | `benchmarks`, `demos`, `research-experiments`                                                                   | benchmark orchestration and manual research/demo surfaces                                  |

Canonical implementation layout:

```text
tools/devx/<category>/
tools/quality/<category>/
tools/ops_runners/<category>/ # executable operational runners
tools/research/<category>/
```

The physical `experiments/` directory appears under both `ops` and `research`.
The public CLI categories are intentionally `ops-experiments` and
`research-experiments` so the command catalog has no duplicate category names.

Historical compatibility-window note (not a current retirement receipt):

```text
tools/{architecture,connectors,foundry,migrations,demos}/...
```

The prior migration note recorded a planned sunset of 2026-09-01; see Current
State below for the inspected disposition and its owner-sign-off limit.

Additional non-CLI helper surface:

```text
tools/design/
```

## Common Commands

The commands below were smoke-tested on `2026-04-17` unless explicitly marked as `conceptual`.

| Command                                                       | Purpose                                                                | Status                              |
| ------------------------------------------------------------- | ---------------------------------------------------------------------- | ----------------------------------- |
| `uv run polisyos-tools --help`                                | Show the root CLI and global options.                                  | `smoke-tested`                      |
| `uv run polisyos-tools list --by-zone`                        | Browse the public command catalog by zone.                             | `smoke-tested`                      |
| `uv run polisyos-tools graph --format mermaid`                | Generate a Mermaid dependency graph for the tools.                     | `smoke-tested`                      |
| `uv run polisyos-tools docs --output docs/reference/tools.md` | Regenerate the tool reference.                                         | `smoke-tested`                      |
| `uv run polisyos-tools workspace ci-parity --skip-browser`    | Run the local CI-like pass, including documentation checks by default. | `conceptual` (heavy aggregate gate) |

## Test And Verification

| Command                                                                                                                                                          | What it verifies                                                        | Status         |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | -------------- |
| `uv run polisyos-tools validation check-docs-accuracy --repo-root .`                                                                                             | Documentation and generated references agree with the repository state. | `smoke-tested` |
| `uv run pytest -q tests/repo_quality/tools/test_unified_cli.py tests/repo_quality/tools/test_phase5_tooling.py tests/repo_quality/tools/test_tools_hardening.py` | CLI boundary, registry contract, hardening and compatibility behavior.  | `conceptual`   |

## Reference Docs

- [Validation README](./quality/validation/README.md)
- [Workspace DevX README](./devx/workspace/README.md)
- [Architecture DevX README](./devx/architecture/README.md)
- [Connectors DevX README](./devx/connectors/README.md)
- [Foundry DevX README](./devx/foundry/README.md)
- [Design Tools README](./design/README.md)
- [Ops Experiments README](./ops_runners/experiments/README.md)
- [Research Experiments README](./research/experiments/README.md)
- [Ops README](../ops/README.md)
- [Tool Reference](../docs/reference/tools.md)
- [CI/CD Platform How-To](../docs/how-to/operate-ci-cd-platform.md)

## Current State

- `tools/registry.py` still emits generic generated wording that the legacy
  wrappers sunset on 2026-09-01. At the inspected tree,
  `tools/registry.py::LEGACY_ENTRYPOINTS` is empty, and
  `tests/repo_quality/tools/test_phase4_consolidation.py::test_phase1d_legacy_tool_paths_are_retired`
  asserts that the five paths listed above are absent; inspection found them
  absent. This supports a code-inspected retired disposition for those paths,
  not an owner sign-off or closeout receipt. That generic sentence needs owner
  reconciliation. New implementation belongs under the zoned paths.

- `tools/design/` intentionally stays a small manual/CI helper surface for
  Node-based brand and accessibility checks rather than part of the Python
  unified CLI registry.

- `tools.registry` is the source of truth for aliases, lifecycle status,
  dependency edges, and documentation generation.

- `workspace ci-parity` remains the primary local umbrella check for tool
  and documentation surfaces.

- Last updated: 2026-10-14

Measurement authors: follow the [input disclosure and register-reader contract](../docs/how-to/author-measurement-instruments.md) before adding an absence verdict.
