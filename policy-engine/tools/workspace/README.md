# tools/workspace

Repo-local contributor commands for deterministic setup and preflight checks.

The pinned local toolchain baseline is Python `3.14.x`, Node `22.x`, and
`uv 0.9.21`.

## Commands

Canonical unified CLI:

```bash
uv run polisyos-tools workspace --help
```

Legacy `./scripts/*` paths below remain as thin compatibility wrappers.

| Command | Role |
| --- | --- |
| `./scripts/bootstrap` | Install or verify contributor prerequisites from a clean machine path |
| `./scripts/doctor` | Validate Python, Node, `uv`, Playwright, lockfiles, generated contracts, and optional env surfaces |
| `./scripts/verify` | Run the standard fast local gate for backend and frontend |
| `./scripts/ci-parity` | Run a heavier local validation pass that approximates the main CI jobs |
| `uv run polisyos-tools workspace core-runtime-long-soak` | Generate long-soak runtime performance evidence as markdown + JSON reports |
| `./scripts/acceptance-audit` | Run the Phase 7 cross-surface acceptance audit and optionally require manual rehearsal evidence |
| `./scripts/remote-acceptance` | Provision and drive a remote Linux acceptance runner via `ssh`, `rsync`, and `git bundle` |

## Bootstrap Profiles

`./scripts/bootstrap` supports dependency tiers via `--profile`:

| Profile | Extras |
| --- | --- |
| `minimal` | `lint`, `test` |
| `docs` | `lint`, `docs` |
| `runtime` | `lint`, `test`, `runtime` |
| `research` | `lint`, `test`, `runtime`, `research` |

Examples:

```bash
./scripts/bootstrap --profile docs --skip-frontend
./scripts/bootstrap --profile research
./scripts/ci-parity --skip-browser
```

`./scripts/ci-parity` pulls the docs toolchain on demand via `uv run --extra docs ...`,
so the documented parity command remains valid after a default `runtime` bootstrap.

## Remote Acceptance Runner

Use `./scripts/remote-acceptance` when heavyweight verification would overload a
local laptop but the repo still needs a clean closeout run on Linux.

The helper keeps three remote locations separate:

- rsynced worktree for fast iteration;
- committed clean checkout for the final rehearsal;
- artifacts root for bundles and run logs.

Typical flow:

```bash
./scripts/remote-acceptance provision
./scripts/remote-acceptance sync
./scripts/remote-acceptance exec --cwd /root/polisyos-work/policy-engine -- ./scripts/verify --backend-only
./scripts/remote-acceptance clean-checkout --ref HEAD
```

The provision step installs Docker system-wide, keeps Python/Node/uv inside an
isolated remote toolchain root, and primes Playwright OS dependencies so the
clean checkout can run `./scripts/bootstrap -> ./scripts/doctor -> ./scripts/verify`
without ad hoc host fixes. The generated remote `env.sh` also exports
`POLISYOS_PYTEST_WORKERS=auto`, so non-benchmark backend pytest uses the full
remote CPU by default while benchmark-marked tests stay on a separate serial
slice for reliable timing thresholds.

## Scope

These commands are workspace tooling, not runtime product APIs. They live under
`policy-engine/` because contributor setup is part of the canonical product root,
while repository root stays a workspace gateway only.
