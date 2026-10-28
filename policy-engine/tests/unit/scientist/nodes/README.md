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

## Response projection wire boundary

`builtins/simulate/test_propagate_uncertainty.py` constructs actual JSON-compatible
ExperimentState params and executes the public node. Valid JSON arrays reach the
normal no-simulation skip while the DTO keeps tuple internals; absent projection
stays optional. Present malformed object/array/item/version/extra/empty/duplicate
cases fail before reads or publication. Native tuple input is a compatibility
control, not a replacement fixture for the real JSON plane.

The original scalar response integration test remains unchanged in substance and
prints its actual NodeError if its positive fails. It is the subsequent producer →
artifact → reader → response-consumer proof; unit syntax admission does not qualify
that later path or G acceptance. Keep malformed-input and property-removal outputs
separate from setup/backend errors.
