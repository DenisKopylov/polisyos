# tools/workspace

Repo-local contributor commands for deterministic setup and preflight checks.

The pinned local toolchain baseline is Python `3.14.x`, Node `22.x`, and
`uv 0.9.21`.

## Commands

| Command | Role |
| --- | --- |
| `./scripts/bootstrap` | Install or verify contributor prerequisites from a clean machine path |
| `./scripts/doctor` | Validate Python, Node, `uv`, Playwright, lockfiles, generated contracts, and optional env surfaces |
| `./scripts/verify` | Run the standard fast local gate for backend and frontend |
| `./scripts/ci-parity` | Run a heavier local validation pass that approximates the main CI jobs |
| `./scripts/acceptance-audit` | Run the Phase 7 cross-surface acceptance audit and optionally require manual rehearsal evidence |

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

## Scope

These commands are workspace tooling, not runtime product APIs. They live under
`policy-engine/` because contributor setup is part of the canonical product root,
while repository root stays a workspace gateway only.
