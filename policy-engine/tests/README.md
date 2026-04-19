# Tests (`policy-engine/tests`)

`policy-engine/tests` is the local navigation hub for the Python test suite. It
currently contains `1101` `test_*.py` files across `18` top-level slices plus
`5` root guard tests that protect import boundaries, public facades, and
component discovery.

## Purpose

- Make the test layout discoverable without opening the docs site.
- Show which slice owns which subsystem, fixture, or operational gate.
- Point contributors to the fastest local loops, taxonomy rules, and
  subsystem-specific READMEs.

## Where To Start

- [`TESTING_POLICY.md`](TESTING_POLICY.md) for taxonomy, markers, quarantine,
  and default local loops.
- [`conftest.py`](conftest.py) for path setup, marker auto-classification, and
  forced CPU/JAX settings.
- Root guard tests:
  `test_arch_import_gate.py`, `test_public_api_facades.py`,
  `test_components_bridge.py`, `test_components_discovery.py`,
  `test_components_id_semver.py`.
- The subsystem map below if you already know which product area you are
  touching.

## Public Entrypoints

| Path | `test_*.py` | Focus | Local README |
|---|---:|---|---|
| `tests/` root | 5 | import and public-surface guardrails | this file |
| `tests/academic/` | 35 | academic SKG batch and knowledge coverage | [academic](academic/README.md) |
| `tests/common/` | 7 | low-level bootstrap, logging, serialization, timestamps | [common](common/README.md) |
| `tests/contract/` | 19 | ABI, schema, and cross-layer compatibility | [contract](contract/README.md) |
| `tests/core/` | 69 | artifacts, security, components, phase0 primitives | [core](core/README.md) |
| `tests/datasets/` | 19 | dataset catalog build and knowledge lookup | [datasets](datasets/README.md) |
| `tests/demos/` | 1 | maintained demo smoke coverage | [demos](demos/README.md) |
| `tests/fabric/` | 87 | connectors, data plane, provenance, world, claims/docs | [fabric](fabric/README.md) |
| `tests/foundry/` | 329 | compile/execute, methods, calibration, runtime, uncertainty | [foundry](foundry/README.md) |
| `tests/integration/` | 3 | cross-subsystem end-to-end scenarios | [integration](integration/README.md) |
| `tests/ir/` | 64 | IR contracts, analytics, observation, governance | [ir](ir/README.md) |
| `tests/lex/` | 45 | legal corpus batch, interventions, simulator | [lex](lex/README.md) |
| `tests/lint/` | 1 | legacy-cutover lint ratchet | [lint](lint/README.md) |
| `tests/performance/` | 8 | benchmark and hot-path regressions | [performance](performance/README.md) |
| `tests/runtime/` | 31 | replay, manifests, runtime HTTP API | [runtime](runtime/README.md) |
| `tests/scholar/` | 6 | scholar freshness and search orchestration | [scholar](scholar/README.md) |
| `tests/scientist/` | 343 | workflows, governance, search, nodes, engine, agent | [scientist](scientist/README.md) |
| `tests/tools/` | 23 | CLI, workspace, tooling, and ratchet gates | [tools](tools/README.md) |
| `tests/ukraine_data/` | 5 | Ukraine data builders, CLI, orchestrator, server | [ukraine_data](ukraine_data/README.md) |

Support surfaces that are not subsystem READMEs:

- [`fixtures/`](fixtures) and [`FIXTURE_CATALOG.md`](FIXTURE_CATALOG.md) for
  shared pytest fixtures and fixture inventory.
- [`quarantine.toml`](quarantine.toml) for quarantined pytest cases.
- [`TESTING_POLICY.md`](TESTING_POLICY.md) for the canonical taxonomy and
  execution policy.

## Depends On / Depended On By

**Depends on**

- `pyproject.toml` pytest configuration and registered markers.
- `tests/conftest.py`, `tests/fixtures/`, and `tests/quarantine.toml`.
- Package surfaces under `src/polisyos/**` and tool surfaces under `tools/**`.

**Depended on by**

- `uv run pytest` and all targeted local/CI test lanes.
- `python3 -m tools.cli workspace verify` and related contributor workflows.
- Package READMEs under `src/polisyos/**` that link back to their owning test
  slices.

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full Python suite
uv run pytest

# conceptual: fast local loop without integration/performance/quarantine
uv run pytest -m "not integration and not performance and not quarantine" --ignore=tests/runtime/http

# conceptual: taxonomy slices
uv run pytest -m contract
uv run pytest -m property
uv run pytest -m integration --ignore=tests/runtime/http
uv run pytest -m performance
uv run pytest tests/runtime/http -m "not quarantine"

# conceptual: local backend + dashboard smoke stack
uv run python tools/testing/local_integration_stack.py up
uv run python tools/testing/local_integration_stack.py smoke
```

## Test And Verification Commands

The collect-only commands below were smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/core -q
uv run pytest --collect-only tests/runtime/http -q
uv run pytest --collect-only tests/scientist -q
```

## Reference Docs

- [`TESTING_POLICY.md`](TESTING_POLICY.md)
- [`FIXTURE_CATALOG.md`](FIXTURE_CATALOG.md)
- [`../README.md`](../README.md)
- [`../tools/testing/README.md`](../tools/testing/README.md)
- [`../docs/how-to/operate-ci-cd-platform.md`](../docs/how-to/operate-ci-cd-platform.md)

## Last Updated

2026-04-17
