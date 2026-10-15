# Workspace DevX (`tools/devx/workspace`)

## Purpose

`tools/devx/workspace` is the repository-local tooling surface for bootstrap, workstation preflight, fast local gates, CI parity, and remote acceptance closeout.

## Where to Start

- Bootstrap/install flow: `tools/devx/workspace/bootstrap.py`.
- Machine preflight: `tools/devx/workspace/doctor.py`.
- Fast local gate: `tools/devx/workspace/verify.py`.
- CI-like parity pass: `tools/devx/workspace/ci_parity.py`.
- Repository SOTA closeout: `tools/devx/workspace/repository_sota_closeout.py`.
- Tool config split generator: `tools/devx/workspace/tool_configs.py`.
- Shared baseline/constants: `tools/devx/workspace/_common.py`.

## Public Entrypoints

| Entrypoint                                                 | Purpose                                                                                                                                                |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `uv run polisyos-tools workspace bootstrap`                | Prepare a contributor machine and check the minimum baseline.                                                                                          |
| `uv run polisyos-tools workspace doctor`                   | Check Python/Node/uv, Playwright, lockfiles, generated contracts, and optional environment surfaces.                                                   |
| `uv run polisyos-tools workspace verify`                   | Run the standard fast local gate.                                                                                                                      |
| `uv run polisyos-tools workspace docs-style`               | Run `markdownlint-cli2` on authored docs and package README/CONTRIBUTING surfaces.                                                                     |
| `uv run polisyos-tools workspace format-check`             | Check the formatter contract for Python, frontend, shell, TOML, and Rego.                                                                              |
| `uv run polisyos-tools workspace lint-fast`                | Run a fast authored-file lint sweep across Python/docs/YAML/shell/workflows and optional frontend ESLint.                                              |
| `uv run polisyos-tools workspace python-base-mypy`         | Run the Phase 3 `mypy` contract across serial base layers: `common -> ir -> core`.                                                                     |
| `uv run polisyos-tools workspace python-base-basedpyright` | Run the Phase 3 `basedpyright` contract across serial base layers: `common -> ir -> core`, with the IR baseline ratchet.                               |
| `uv run polisyos-tools workspace runtime-surface`          | Run the Phase 5B runtime gate: Ruff, source type checks, OpenAPI/client drift, and `tests/unit/runtime`.                                               |
| `uv run polisyos-tools workspace lint-full`                | Run the full authored lint contract with Phase 3 base-layer type gates, `helm lint`, and the Rego strict/test pass.                                    |
| `uv run polisyos-tools workspace benchmark-surfaces`       | Run the Phase 8 gate for `benchmarks/**` and `tools/research/**`: Ruff on authored Python plus shell/YAML hooks, without Markdown/result-bundle churn. |
| `uv run polisyos-tools workspace clean-local-reports`      | List or remove stale local reports, benchmark reports, and optional source-adjacent residue under the Phase 2.9 hygiene contract.                      |
| `uv run polisyos-tools workspace ci-parity`                | Run a heavier pass comparable to the main CI jobs.                                                                                                     |
| `uv run polisyos-tools workspace acceptance-audit`         | Produce Phase 7 acceptance evidence.                                                                                                                   |
| `uv run polisyos-tools workspace repository-sota-closeout` | Check the fail-closed Repository SOTA policy layer, exception registries, and closeout evidence.                                                       |
| `uv run polisyos-tools workspace tool-configs --check`     | Check the split `mypy`, Ruff, and MkDocs configurations, including the dead-override report.                                                           |
| `uv run polisyos-tools workspace remote-acceptance`        | Orchestrate the remote Linux runner for a heavier closeout.                                                                                            |

## Depends On / Depended On By

- **Depends on:** `pyproject.toml`, `uv.lock`, `apps/runtime-dashboard`,
  `package-lock.json`, generated contracts, optional environment surfaces, and the `tools`
  validation/lint/runtime categories.

- **Depended on by:** new contributors, local closeout before a PR,
  onboarding docs, acceptance rehearsals, and remote platform verification.

## Common Commands

Repository SOTA and the standalone docs-freshness validator share baseline
admission rules. A zero-violation baseline admits no exception and still runs
the actual docs checker; nonzero exit or an invalid/nonzero deciding count
fails. Positive debt remains bound to the named owner, current expiry, exact
count, and legacy normalized-output digest. Complete raw stdout and stderr are
retained separately when a subprocess receipt directory is selected. The
runner pins an independent 13-gate baseline of IDs, commands, and coverage
route kinds, so deleting or rerouting an established row fails the contract.
It also dispatches every valid additional subprocess row from the registry;
other rows must resolve to an executed preflight or conditional handler. The
phase-5 registry contract suite runs as a native supporting child, so its row
removal and substitution controls participate in the closeout. The runner
rejects duplicate IDs, malformed routes, and unresolved handlers.

The commands below were smoke-tested on `2026-04-17` unless explicitly marked as `conceptual`.

| Command                                                                                                                 | Purpose                                                                                              | Status                                              |
| ----------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `uv run polisyos-tools workspace doctor --list-surfaces`                                                                | List the optional environment surfaces that `doctor` can check.                                      | `smoke-tested`                                      |
| `uv run polisyos-tools workspace docs-style`                                                                            | Check authored docs, READMEs, and plan Markdown without archive churn.                               | `conceptual`                                        |
| `uv run polisyos-tools workspace format-check --skip-rego`                                                              | Run the formatter-only contract on a machine without a local `opa`.                                  | `conceptual`                                        |
| `uv run polisyos-tools workspace lint-fast --skip-frontend`                                                             | Run the fast repository-hygiene lint for Python/docs/config/shell without dashboard ESLint.          | `conceptual`                                        |
| `uv run polisyos-tools workspace python-base-mypy --layer ir --layer core`                                              | Run only the remaining Phase 3 type check after `common` has completed.                              | `conceptual`                                        |
| `uv run polisyos-tools workspace python-base-basedpyright --layer ir`                                                   | Check IR against the repository's basedpyright baseline.                                             | `conceptual`                                        |
| `uv run polisyos-tools workspace runtime-surface --skip-tests`                                                          | Check the Phase 5B lint/type/OpenAPI contract without the full runtime pytest suite.                 | `conceptual`                                        |
| `uv run polisyos-tools workspace lint-full --skip-policy --skip-helm`                                                   | Run the full authored lint contract on a machine without local `opa` or `helm`.                      | `conceptual`                                        |
| `uv run polisyos-tools workspace benchmark-surfaces`                                                                    | Run the focused benchmark/research hygiene gate without Markdown/JSON/log/result churn.              | `conceptual`                                        |
| `uv run polisyos-tools workspace clean-local-reports --stale-days 30 --dry-run`                                         | List cleanup candidates under `.polisyos/reports`, `benchmarks/_reports`, and `_build` audit output. | `conceptual`                                        |
| `uv run polisyos-tools workspace tool-configs --check`                                                                  | Check the generated `mypy`, Ruff, and MkDocs configs without rewriting files.                        | `smoke-tested`                                      |
| `uv run polisyos-tools workspace repository-sota-closeout --contract-only`                                              | Check the Phase 5 contract layer without the heavier drift subprocesses.                             | `conceptual`                                        |
| `uv run polisyos-tools workspace doctor --skip-playwright --skip-lockfile-checks --skip-contract-checks`                | Run a fast workstation preflight without the heavier browser/lock/contract checks.                   | `smoke-tested`                                      |
| `uv run polisyos-tools workspace bootstrap --profile docs --skip-frontend --skip-playwright --skip-hooks --skip-doctor` | Install the docs-oriented baseline on a new machine.                                                 | `conceptual` (modifies the local environment)       |
| `uv run polisyos-tools workspace verify --backend-only --skip-doctor`                                                   | Run the fast backend-only gate after local changes.                                                  | `conceptual` (may take a noticeable amount of time) |
| `uv run polisyos-tools workspace ci-parity --skip-browser`                                                              | Run the umbrella parity pass with documentation checks enabled by default.                           | `conceptual` (heavy aggregate gate)                 |

`lint-fast` uses the generated root Ruff policy for authored product, test,
tooling, architecture, application, and nested worker/oracle Python. The active
E02 evidence-script roots receive the same full Ruff rule set through an
explicit file-set oracle. That oracle derives its maintained source set from
the Git index (`git ls-files --cached`), so staged source files are included
while historical untracked handoff and review records remain preserved outside
the CI source role. It also admits the tracked Q2 packaging consumer subtree
under `LOCAL/q2-packaging/raw`; other ignored raw snapshots remain outside the
role. Empty selections fail closed. Phase 8 exclusions are rooted at their
workspace paths, so nested
`benchmarks` under `src/polisyos` or `tests` remain in the strict scope; the
separate `benchmark-surfaces` gate owns top-level `benchmarks/**` and
`tools/research/**`. CI composes both commands with `format-check`.

## Test And Verification

| Command                                                                                                                                                                   | What it verifies                                                                         | Status         |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------- |
| `uv run pytest -q tests/repo_quality/tools/test_workspace_phase3.py tests/unit/core/phase0/test_workspace_commands.py tests/repo_quality/tools/test_remote_acceptance.py` | Workspace command contract, compatibility wrappers, and remote-acceptance orchestration. | `conceptual`   |
| `uv run polisyos-tools validation check-docs-accuracy --repo-root .`                                                                                                      | README and documentation references for workspace tooling remain publishable.            | `smoke-tested` |

## Reference Docs

- [Contributor Start Here](../../../docs/reference/contributor-start-here.md)
- [Install How-To](../../../docs/how-to/install.md)
- [CI/CD Platform How-To](../../../docs/how-to/operate-ci-cd-platform.md)
- [Dependency Platform Reference](../../../docs/reference/dependency-platform.md)
- [Environment Matrix Reference](../../../docs/reference/environment-matrix.md)
- [Quality Gates Reference](../../../docs/reference/quality-gates.md)

## Current State

- Contributor baseline: Python `3.14.x`, Node `22.x`, `uv 0.9.21`.
- Repo hygiene contract is documented in
  `docs/reference/repository-hygiene.md` and backed by root
  `.editorconfig`, `.markdownlint-cli2.jsonc`, `.yamllint`, `.taplo.toml`,
  and the `docs-style` / `format-check` / `lint-fast` / `python-base-*` /
  `lint-full` commands.

- Phase 3 Python base layers use serial `common -> ir -> core` wrappers.
  `mypy` stays green via an explicit debt ledger in `pyproject.toml`, and
  `basedpyright` ratchets IR through
  `architecture/baselines/basedpyright/baseline.json`.

- Phase 5B runtime uses `runtime-surface` to combine Ruff, source-only type
  checks, public-facade/runtime policy tests, and OpenAPI/client drift checks.

- Repository Best-In-Class Phase 2.9 uses `clean-local-reports` with
  `architecture/asset_placement.toml` to keep local reports, benchmark outputs,
  product seed assets, test fixtures, golden records, and examples distinct.

- Repository SOTA Phase 5 uses `repository-sota-closeout` to enforce topology,
  import, public-surface, generated-artifact, docs-freshness, shim, complexity,
  security, dependency, SBOM, release, and command-registry contracts.
  Pass `--subprocess-receipt-dir <path>` when a full run needs each executed
  child’s exact stdout/stderr bytes retained with its command, exit code, and
  byte hashes. Gate summaries decode those bytes as UTF-8 with backslash escapes
  for invalid sequences and normalize newlines. Omitting the option keeps the
  existing text-mode capture and concise failure output. Only the pinned
  `generated-drift` row may declare and use `skip_command`; an invalid registry
  fails before the closeout starts any child gates.

- By default, `ci-parity` includes documentation-accuracy checks, a strict MkDocs build, and
  semantic docstring checks unless `--skip-docs` is specified.

- The remote-acceptance path separates the rsynced worktree, clean checkout, and artifact
  root so that Linux closeout is reproducible.

- Last updated: 2026-10-12

## Worktree admission

Before naming a branch and path in any commissioning prompt, run the registered
read-only preflight with both exact selectors. For example, this existing lane
was checked with:

```sh
uv run --no-sync polisyos-tools workspace doctor --worktree-admission resume \
  --branch codex/measurement-plane \
  --path /Users/deniskopylov/polisyos/.worktrees/measurement-plane
```

Use `create` to check a proposed unused pair and `resume` to check an existing
attachment. `--path` is the absolute worktree root, including its exact spelling,
not the nested product directory. There are no default selectors or substitute
names. Retain the complete JSON receipt. Exit 0 admits that pair; exit 1 rejects
it; exit 2 means the observation is incomplete and cannot admit it.

The receipt reconciles every Git registration and linked admin record, required
admin files, live `.git` backlinks, branch/HEAD/common-repository identities, and
the requested filesystem path. Missing registered paths still occupy their
names; dangling symlinks and path aliases cannot pass create admission. Git or
filesystem errors retain their evidence and produce an incomplete verdict.

Admission runs before normal doctor dependency, lockfile, or browser checks.
It does not reserve names or prune records. Its named `unresolved_by_construction`
limits include sequential observation, moved directories beyond registered
paths, name reservation, and external prompt writers. Root serializes creation,
reruns admission immediately before it, and checks the exact pair with `resume`
afterward. A failed pair requires explicit re-commissioning and a fresh check of
both changed selectors. Ordinary doctor behavior remains available without the
admission flags.
