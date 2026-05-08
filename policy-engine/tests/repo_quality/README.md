# Repository-Quality Tests

`tests/repo_quality` is the canonical pytest home for tests that validate the
repository itself rather than product behavior or product API contracts.

## Public Entrypoints

| Path | Focus |
|---|---|
| `tests/repo_quality/architecture/` | architecture contracts, topology, public-surface, generated-artifact, and repository-structure gates |
| `tests/repo_quality/lint/` | pytest-backed lint ratchets |
| `tests/repo_quality/tools/` | CLI, workspace, release, diagnostics, and CI gate behavior |

Product behavior tests stay under `tests/unit`, `tests/integration`,
`tests/property`, `tests/e2e`, or `tests/performance`. Product API and schema
contracts stay under `tests/contract`.

## Common Commands

Run commands from `policy-engine/`.

```bash
uv run pytest -m repo_quality
uv run pytest tests/repo_quality -q
```

## Redirects

The old architecture-test root has been removed. Legacy `tests/lint` and
`tests/tools` roots remain redirects only. Do not add collectable tests there.
