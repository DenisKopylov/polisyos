# Installation

Revised: 2026-10-14
Owner: `@platform-owners`
Source of truth: `CONTRIBUTING.md`, `docs/reference/environment-matrix.md`, `pyproject.toml`,
`.python-version`, `.nvmrc`, `package.json`, `tools/devx/workspace/_common.py`,
`tools/devx/workspace/bootstrap.py`, `tools/devx/workspace/doctor.py`, `tools/registry.py`,
`.pre-commit-config.yaml`.
Source snapshot: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`;
`src/polisyos/` production implementation unchanged.
Review basis: command/source paths inspected; tests and install commands were not run for this edit.

!!! info "Historical command-surface receipt (2026-04-17)"
On a local macOS workstation, the following were checked:
`uv run polisyos-tools workspace bootstrap --help`,
`uv run polisyos-tools workspace doctor --help`,
`uv run polisyos-tools workspace verify --help`,
`uv run polisyos-tools workspace ci-parity --help`,
and `uv run polisyos-tools workspace doctor --list-surfaces`. This is a
historical observation that the commands were available in a specific
environment, not a result from running the current bootstrap or checking a fresh
checkout. The installation commands below modify the local environment.

The commands below are listed from the current source entry points in
`pyproject.toml` and `tools/registry.py`; their presence is not a receipt of
successful execution. Only the dated historical record above reports a
successful run on a machine.

## Inputs

- a `policy-engine/` checkout;
- Python `3.14.x`;
- `uv 0.9.21`;
- Node `22.x` for frontend workflows and the standard `doctor` preflight;
- Corepack and pnpm `10.33.2` for frontend workflows and the standard `doctor`
  lockfile/contract checks (the pnpm version is set in `package.json`);
- a decision about whether this machine needs frontend and Playwright.

Bootstrap profiles select Python extras only: `minimal` = `lint + test`, `docs` =
`lint + docs`, `runtime` = `lint + test + runtime`, `research` = `lint + test + runtime +
research`. Bootstrap also installs pre-commit hooks, the frontend workspace, and
Playwright browsers by default, then runs `doctor`; the flags below let you skip
these steps.

## Outputs

- a local Python environment matching the selected profile;
- an installed dashboard toolchain, if needed;
- a clear path to `doctor`, `verify`, and `ci-parity`.

## Commands

The full runtime path installs dependencies and runs `doctor` at the end of
bootstrap; `verify --skip-doctor` runs the fast contributor gate without
repeating the workstation preflight.

```bash
cd policy-engine
uv run polisyos-tools workspace bootstrap --profile runtime
uv run polisyos-tools workspace verify --skip-doctor
```

## Choose a profile

| Profile    | Use it for                                  | Command                                                                                      |
| ---------- | ------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `minimal`  | core Python, lint, fast unit/property tests | `uv run polisyos-tools workspace bootstrap --profile minimal --skip-frontend --skip-doctor`  |
| `docs`     | MkDocs and authored-document checks         | `uv run polisyos-tools workspace bootstrap --profile docs --skip-frontend --skip-doctor`     |
| `runtime`  | backend/runtime/API work, default path      | `uv run polisyos-tools workspace bootstrap --profile runtime`                                |
| `research` | causal, Foundry, Scientist heavy workflows  | `uv run polisyos-tools workspace bootstrap --profile research --skip-frontend --skip-doctor` |

If you are unsure, start with `runtime`.

`--skip-frontend` has two effects: bootstrap skips the Node check and pnpm
workspace installation. Without `--skip-doctor`, the subsequent `doctor` still
checks Python, Node, `uv`, Playwright, lockfiles, and generated contracts. The
bootstrap flag `--skip-playwright` skips browser installation but is not passed
to `doctor` automatically; for a browserless bootstrap, use `--skip-doctor` and
run the required checks separately.

## Recommended installation path

From the `policy-engine/` root:

```bash
uv run polisyos-tools workspace bootstrap --profile runtime
uv run polisyos-tools workspace verify --skip-doctor
```

This path:

- uses the supported baseline from the
  [Environment Matrix](../reference/environment-matrix.md);

- uses `uv` as the canonical Python environment manager;
- synchronizes the selected profile's extras and installs pre-commit hooks by
  default;
- prepares the frontend and Playwright browsers unless they are disabled;
- runs `doctor` unless `--skip-doctor` is set; this step checks Node `22.x`,
  `uv` `0.9.21`, a Playwright smoke test, lockfiles, and generated contracts
  unless those checks are disabled.

## Narrower options

<a id="backend-only-onboarding"></a>

### Backend-only setup

```bash
uv run polisyos-tools workspace bootstrap --profile runtime --skip-frontend --skip-doctor
uv run polisyos-tools workspace verify --backend-only --skip-doctor
```

The backend-only profile does not install the Node workspace. If you need only
the basic workstation preflight without browser, pnpm lockfile, and
generated-contract checks, run `doctor` separately:

```bash
uv run polisyos-tools workspace doctor --skip-playwright --skip-lockfile-checks --skip-contract-checks
```

Even with these flags, `doctor` checks Python `3.14.x`, Node `22.x`, and `uv`
`0.9.21`.

<a id="docs-only-onboarding"></a>

### Documentation-only setup

```bash
uv run polisyos-tools workspace bootstrap --profile docs --skip-frontend --skip-doctor
uv run polisyos-tools workspace docs-style docs/
uv run --extra docs python -m mkdocs build --strict
uv run polisyos-tools validation check-docs-accuracy --repo-root .
```

This profile installs only the Python extras `lint + docs`; Node/Corepack/pnpm
and the browser stack are not installed automatically. Bootstrap still installs
the pre-commit hook by default; add `--skip-hooks` if this environment does not
need the hook. The profile selects Python extras, while `--skip-frontend`,
`--skip-playwright`, `--skip-hooks`, and `--skip-doctor` control separate
bootstrap side effects. `docs-style` invokes the configured Node-based
`markdownlint-cli2` pre-commit hook; this entry point does not invoke
Corepack/pnpm or Playwright itself. On its first run, pre-commit may prepare an
isolated hook environment. If you run the full `doctor` separately, it checks
Node, lockfiles, and generated contracts; browser smoke can be disabled with
`--skip-playwright`, and other surfaces can be skipped with their respective
`--skip-*` flags.

### Frontend setup

```bash
uv run polisyos-tools workspace bootstrap --profile runtime
uv run polisyos-tools workspace verify --frontend-only --skip-doctor
cd apps/runtime-dashboard
corepack pnpm run generate:api
corepack pnpm run contracts:verify
```

## Manual setup from the contributor baseline

Use this manual path from `CONTRIBUTING.md` instead of workspace bootstrap when
needed:

```bash
uv sync --frozen --extra lint --extra test --extra runtime
uv run pre-commit install
corepack pnpm install --frozen-lockfile --ignore-scripts
cd apps/runtime-dashboard
corepack pnpm run playwright:install
```

These commands install the full backend and frontend contributor baseline. For
a narrower set of Python extras, use the matching bootstrap profile above; do
not combine it with an arbitrary editable-package install without checking
lockfile compatibility.

`pyproject.toml` also declares separate extras:

| Extra                            | When it is needed                                  |
| -------------------------------- | -------------------------------------------------- |
| `.[core]`                        | the narrowest source installation                  |
| `.[docs]`                        | MkDocs and documentation quality                   |
| `.[runtime]` / `.[runtime-http]` | Runtime API and dashboard contract surface         |
| `.[test]`                        | pytest stack                                       |
| `.[research]`                    | causal / Scientist / Foundry-heavy workflows       |
| `.[all]`                         | curated umbrella for a broad local feature surface |

For the frontend after the manual path, use Node `22.x` and Corepack with pnpm
`10.33.2`:

```bash
corepack pnpm install --frozen-lockfile
cd apps/runtime-dashboard
corepack pnpm run playwright:install
```

In a fresh checkout, run `corepack pnpm install --frozen-lockfile` before a
TypeScript scanner: missing workspace links can produce false findings.
Bootstrap uses `--ignore-scripts` for its installation; this command performs
the required fresh-checkout installation for scanner workflows.

## Verify the result

Minimum checks:

```bash
uv run polisyos --version
uv run polisyos-tools workspace doctor --list-surfaces
uv run polisyos-tools workspace verify --backend-only --skip-doctor
```

If you are changing the runtime contract surface:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
```

If you are changing the documentation surface:

```bash
uv run --extra docs python -m mkdocs build --strict
```

## Rollback and cleanup

If the profile is too large or incorrect:

1. Remove the local `.venv` or another virtual environment you created.
2. If bootstrap installed the frontend unnecessarily, remove
   `apps/runtime-dashboard/node_modules`.
3. Repeat bootstrap with a narrower profile and the required `--skip-*` flags.

If you deliberately do not want to keep the browser stack locally, use
`--skip-playwright` and run Playwright suites in CI or on a separate machine.

## Troubleshooting

### Python or Node is outside the supported matrix

- consult the [Environment Matrix](../reference/environment-matrix.md);
- unsupported minor versions remain unsupported until the bug is reproduced on
  Python `3.14.x` and Node `22.x`.

### You need the list of optional `doctor` surfaces

```bash
uv run polisyos-tools workspace doctor --list-surfaces
```

Historical list, captured on 2026-04-17:

- `datasets-unpd`
- `frontend-sentry-build`
- `frontend-sentry-runtime`
- `llm-anthropic`
- `llm-openai`
- `runtime-oidc`
- `runtime-research-postgres`
- `runtime-signing`

### Apple Silicon and JAX

- The CPU-first path is the supported baseline.
- Metal remains opt-in through the `apple-metal` extra.
- For initial smoke/tutorial runs, use CPU unless there is a specific reason to
  debug Metal.

### Conflicting or heavyweight dependencies

- if you are unsure, start with the `runtime` profile rather than an arbitrary
  mixture of extras;
- add causal/research extras only when the task needs them;
- if you only need the documentation or backend surface, do not install the
  frontend/browser stack unnecessarily.

### Lockfile, contract, or generated-artifact checks block local triage

For an initial preflight, you can temporarily narrow `doctor`:

```bash
uv run polisyos-tools workspace doctor --skip-playwright --skip-lockfile-checks --skip-contract-checks
```

This keeps the Python, Node, and `uv` checks; run the appropriate scope-specific
gate before a PR. `ci-parity --skip-browser` is a broad CI-parity check, not a
short check for documentation-only changes.
