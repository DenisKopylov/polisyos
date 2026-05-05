# Repository Hygiene Contract

Owner: `@platform-owners`
Source of truth: `.editorconfig`, `.markdownlint-cli2.jsonc`, `.yamllint`,
`.taplo.toml`, `basedpyright.toml`,
`.pre-commit-config.yaml`, and
`tools/devx/workspace/{docs_style.py,format_check.py,lint_fast.py,lint_full.py,runtime_surface.py,benchmark_surfaces.py,verify.py,repository_sota_closeout.py}`.

This page defines the repository-wide lint/format contract that Phase 0 of the
repository cleanup plan establishes. It exists so future directory waves can
opt into a known toolchain instead of inventing local conventions.

The final placement map for repository roots, tools, tests, docs, ops, data,
and local runtime state lives in [Repository Topology](repository-topology.md).

## Authored Scope

Full authored scope for lint/format waves:

- `src/polisyos/**`
- `tests/**`
- `tools/**`
- `frontend/**`
- `docs/**`
- `schemas/**`
- `ops/**`
- `architecture/**`
- `benchmarks/**`
- `release/**`
- `release-fragments/**`
- `.github/**`
- top-level authored files such as `README.md`, `CONTRIBUTING.md`,
  `CHANGELOG.md`, `pyproject.toml`, `mkdocs.yml`, `architecture/imports/policy.toml`,
  `architecture/imports/exceptions.toml`

Generator-owned or check-only surfaces:

- generated clients and generated API outputs
- schema snapshots and ABI outputs
- committed machine-generated JSON and benchmark result bundles
- release evidence bundles that are emitted by canonical generators

Excluded from bulk sweeps:

- `_build/**`, `_cache/**`, `.venv*`, `__pycache__`

- `docs/archive/**`
- ignored local data under `data/policy-engine-local/**`
- retired legacy output roots such as `runs/**`, `logs/**`, `tmp/**`,
  `.tmp/**`, and `benchmark-results/**`
- binary/media artifacts and `.log` bundles

## File-Type Contract

- Python
  Canonical tools: `ruff check`, `ruff format`, `mypy`, `basedpyright`.
  Current policy: `ruff` is repo-wide for authored Python. `mypy` and
  `basedpyright` stay curated/ratcheted. Phase 3 serializes the base package
  foundation as `common -> ir -> core` and exposes it through
  `workspace python-base-mypy` and `workspace python-base-basedpyright`.

- Markdown
  Canonical tools: `markdownlint-cli2`.
  Current policy: authored docs, top-level markdown, and package `README.md` /
  `CONTRIBUTING.md`; `docs/archive/**` excluded. Phase 8 benchmark/research
  trees keep `benchmarks/**/*.md` and `tools/research/**/*.md` out of markdown
  waves so benchmark support cleanups stay limited to Python/shell/YAML.

- TS helper scripts
  Canonical tools: frontend Node toolchain,
  `corepack pnpm --filter @polisyos/runtime-dashboard run a11y:*`.
  Current policy: `tools/design/*.ts` stays under the frontend accessibility
  contract and is validated through
  `frontend/runtime-dashboard/package.json` rather than the Python unified CLI.
  The canonical frontend workspaces are `frontend/runtime-dashboard`,
  `frontend/runtime-api-client`, and `frontend/runtime-reference-shell`.

- YAML
  Canonical tools: `yamllint`, `actionlint`, `helm lint`.
  Current policy: `yamllint` covers authored plain YAML; Helm `templates/**`
  and chart test manifests are excluded from generic YAML syntax hooks and
  validated via `helm lint`; repository-root `.github/workflows/**` also runs
  through `actionlint`. Product workflow templates live under
  `ops/ci/templates/workflows/**` and are linted as authored YAML/templates.

- Shell
  Canonical tools: `shfmt`, `shellcheck`.
  Current policy: `shfmt -i 2 -ci -sr`; ShellCheck runs via a pinned
  `uvx --from shellcheck-py` hook on tracked shell surfaces under `tools/`,
  `ops/`, `benchmarks/`, and frontend shell helpers.

- TOML
  Canonical tools: `taplo fmt --check`.
  Current policy: broad authored TOML hygiene with explicit excludes for
  archive/runtime/cache/vendor trees.

- Rego
  Canonical tools: `opa fmt --fail`, `opa check --strict`,
  `opa test --fail-on-empty`.
  Current policy: formatting and strict compilation cover both runtime and
  Helm-packaged policy trees; tests currently live under `ops/policy/policies`.

## Basedpyright Policy

Phase 0 started with a curated include list. The current root scope is broader
than the original base-layer wave and is ratcheted through a repository-tracked
baseline file.

Current root include surface:

- `src/polisyos/common`
- `src/polisyos/ir`
- `src/polisyos/core`
- `src/polisyos/fabric`
- `src/polisyos/data_forge`
- `src/polisyos/scientist`
- `src/polisyos/runtime`

Data Forge Phase 8 removed the former `src/polisyos/academic`,
`src/polisyos/datasets`, `src/polisyos/ukraine_data`,
`src/polisyos/batch_common`, and `src/polisyos/batch_snapshot` include roots.

Current baseline file:

- `architecture/baselines/basedpyright/baseline.json`

Expansion rule:

1. make a directory green with `ruff`, tests, and any owning package guards;
2. add that directory to `basedpyright.toml` or to the serial
   base-layer wrapper;
3. if the directory still carries historical debt, encode it in the baseline
   file so only new diagnostics fail the run;
4. only then make it part of required repo-wide passes.

This keeps the root signal fail-closed on green surfaces while allowing
ratcheted layers to burn down historical debt without hiding new regressions.
New directories enter the root include only after a green gate or an explicit
ratchet entry in this status board and
`architecture/baselines/basedpyright/baseline.json`.

## Directory Status Board

| Status | Directory Surface | Gate Contract | Notes |
| ------ | ----------------- | ------------- | ----- |
| green | `docs/**`, top-level authored Markdown, package READMEs | `workspace docs-style` | `docs/archive/**` remains excluded from authored markdown waves. |
| green | Python formatting across authored scope | `workspace format-check` / `ruff format --check` | Formatting includes product, tests, tools, benchmarks, schemas, scripts, examples, and root helpers. |
| green | `src/polisyos/common`, `src/polisyos/ir`, `src/polisyos/core` | `workspace python-base-mypy`, `workspace python-base-basedpyright` | Base layers stay serial and ratcheted by explicit mypy/basedpyright ledgers. |
| green | `src/polisyos/runtime`, `tests/unit/runtime` | `workspace runtime-surface` | Runtime API/client drift is part of the owning surface. |
| green | frontend workspaces | `corepack pnpm -C policy-engine lint`, `corepack pnpm -C policy-engine typecheck`, and workspace-local architecture gates | Covers dashboard, runtime API client, reference shell, and CLI. |
| ratcheted | `src/polisyos/calibration`, `src/polisyos/foundry/agent_sim/world` | `workspace lint-fast` with explicit Ruff per-file ignores | Historical annotation/import-line debt is ledgered in `pyproject.toml`. |
| ratcheted | `tools/lib`, `tools/devx/**`, `tools/ops/**`, `tools/quality/**`, root helper scripts | `workspace lint-fast` with explicit Ruff per-file ignores | Existing command/script debt is visible as directory-level ratchet entries, not global ignores. |
| ratcheted | `tests/**` support and smoke suites | `workspace lint-fast` with test-specific Ruff policy | Tests keep looser security/assert/type-import policy while source surfaces tighten first. |
| phase8-limited | `benchmarks/**`, `tools/research/benchmarks/**`, `tools/research/demos/**`, `tools/research/**` | `workspace benchmark-surfaces` | Uses the Phase 8 limited Python/shell/YAML contract and stays outside strict `lint-fast` Ruff. |
| pending | Full removal of Ruff ratchet entries | Directory-by-directory owner work | New debt must be added only as a named ratchet entry with owner context. |

## Mypy Policy

Phase 3 keeps `mypy` strict but uses an explicit debt ledger in `pyproject.toml`
for the currently non-green `ir` modules and for
`polisyos.core.evaluation.mcda_robustness`.

Rule of use:

1. `uv run mypy src/polisyos/common` stays fully fail-closed.
2. `uv run mypy src/polisyos/ir` and `uv run mypy src/polisyos/core` run under
   strict mode with the ledgered modules temporarily excluded from blocking.
3. As each module is stabilized, remove it from the ledger so it returns to
   fail-closed coverage.

## Canonical Commands

- `uv run polisyos-tools workspace verify`
  Existing contributor fast gate with backend/frontend/tests/contracts.

- `uv run polisyos-tools workspace docs-style`
  Markdown-only authored docs/package README lint surface.

- `uv run polisyos-tools workspace format-check`
  Formatter checks across authored Python, frontend, shell, TOML, and Rego
  surfaces.

- `uv run polisyos-tools workspace lint-fast`
  Fast authored lint sweep for Python, markdown, YAML, shell, workflows, and
  optional frontend ESLint. Phase 8 benchmark/research Python is intentionally
  routed to `workspace benchmark-surfaces`.

- `uv run polisyos-tools workspace python-base-mypy`
  Serial Phase 3 `mypy` pass for `src/polisyos/common`,
  `src/polisyos/ir`, and `src/polisyos/core`.

- `uv run polisyos-tools workspace python-base-basedpyright`
  Serial Phase 3 `basedpyright` pass for `src/polisyos/common`,
  `src/polisyos/ir`, and `src/polisyos/core`, with IR debt ratcheted through
  `architecture/baselines/basedpyright/baseline.json`.

- `uv run polisyos-tools workspace lint-full`
  Full authored lint contract: `lint-fast`, `format-check`, Phase 3 base-layer
  type gates, all frontend type/architecture gates, `runtime-surface`,
  `benchmark-surfaces`, Helm chart lint, and strict Rego gates.

- `uv run polisyos-tools workspace benchmark-surfaces`
  Phase 8 benchmark/research hygiene gate for authored Python, shell, and YAML
  only; excludes markdown, JSON, log bundles, and release-summary churn.

- `uv run polisyos-tools workspace repository-sota-closeout`
  Phase 5 fail-closed repository policy gate for topology, imports, public
  surface, generated drift, docs freshness, public polish, shims, complexity
  exceptions, security, dependencies, SBOM, release policy, and
  command-registry drift.

## Pre-commit Policy

`pre-commit` carries fast file-scoped hooks plus the contract-only Repository
SOTA closeout gate. In the current monorepo layout, the wrapper commands
normalize `policy-engine/` paths to the Git root before invoking hooks, so the
same config works from local scripts and CI:

- trailing whitespace and EOF hygiene
- `ruff` + `ruff-format` on changed Python files
- `markdownlint-cli2` on changed authored markdown
- `check-yaml` + `yamllint` on changed plain YAML (Helm `templates/**` and chart tests stay chart-aware)
- `shfmt` + `shellcheck` on changed shell scripts
- `taplo-format --check` on changed TOML
- `actionlint` on changed workflow files
- `repository-sota-closeout --contract-only` on every run, so exception
  registries cannot drift into unowned or expired state

Heavy passes stay outside `pre-commit`:

- repo-wide Markdown/TOML/shell sweeps
- `helm lint`
- `opa check --strict` and `opa test`
- curated `mypy` / `basedpyright`
- `verify`, `ci-parity`, full `repository-sota-closeout`, and acceptance
  workflows
