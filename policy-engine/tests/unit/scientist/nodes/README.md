# Scientist Node Unit Tests

Owner: `team-scientist`
Last updated: 2026-05-05

## Purpose

This subtree owns unit tests for builtin Scientist nodes, node registries,
decision packet construction, governance nodes, planning nodes, and simulation
nodes.

## Public API

Tests assert builtin node behavior through the Scientist node registry, node
protocols, and documented node outputs.

## Internal Layout

| Path | Role |
| --- | --- |
| `test_*.py` | Cross-family node tests and registry cutover tests. |
| `builtins/` | Mirrored tests for builtin node families. |
| `conftest.py` | Shared node fixtures. |

## Extension Points

External node smoke tests use `polisyos.scientist_nodes`; builtin node tests
remain here.

## Tests

Run from `policy-engine/`:

```bash
uv run pytest tests/unit/scientist/nodes -q
```

## Operability Links

- `src/polisyos/scientist/nodes/README.md`
- `architecture/extension_points.toml`
- `docs/reference/scientist/index.md`

## Known Shims/Deprecations

Node ID migrations require compatibility tests until saved workflow specs no
longer reference the old ID.
