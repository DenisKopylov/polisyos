# Tests (`policy-engine/tests`)

`policy-engine/tests` is the local navigation hub for the Python test suite. It
currently contains `1389` `test_*.py` files across top-level and domain slices
plus `5` root guard tests that protect import boundaries, public facades, and
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

- Repository-quality guard tests:
  `test_arch_import_gate.py`, `test_public_api_facades.py`,
  `test_components_bridge.py`, `test_components_discovery.py`,
  `test_components_id_semver.py` under
  [`repo_quality/architecture/`](repo_quality/architecture/README.md).

- The subsystem map below if you already know which product area you are
  touching.

## Public Entrypoints

| Path                  | `test_*.py` | Focus                                                       | Local README                           |
| --------------------- | ----------: | ----------------------------------------------------------- | -------------------------------------- |
| `tests/` root         | 0           | shared pytest config and navigation                         | this file                              |
| `tests/unit/common/`       | 6           | low-level bootstrap, logging, serialization, timestamps     | [common](unit/common/README.md)        |
| `tests/contract/`     | 19          | ABI, schema, and cross-layer compatibility                  | [contract](contract/README.md)         |
| `tests/unit/core/`         | 70          | artifacts, security, components, phase0 primitives          | [core](unit/core/README.md)            |
| `tests/unit/data_forge/`   | 110         | Data Forge foundation, legal batch, academic/catalog/Ukraine domains | [academic](unit/data_forge/domains/academic/README.md), [catalog](unit/data_forge/domains/catalog/README.md), [Ukraine](unit/data_forge/domains/ukraine/README.md) |
| `tests/e2e/demos/`        | 1           | maintained demo smoke coverage                              | [demos](demos/README.md)               |
| `tests/unit/fabric/`       | 98          | connectors, data plane, provenance, world, claims/docs      | [fabric](unit/fabric/README.md)        |
| `tests/unit/foundry/`      | 374         | compile/execute, methods, calibration, runtime, uncertainty | [foundry](unit/foundry/README.md)      |
| `tests/integration/`  | 6           | cross-subsystem end-to-end scenarios                        | [integration](integration/README.md)   |
| `tests/unit/ir/`           | 97          | IR contracts, analytics, observation, governance            | [ir](unit/ir/README.md)                |
| `tests/unit/lex/`          | 9           | legal corpus batch, interventions, simulator                | [lex](unit/lex/README.md)              |
| `tests/performance/`  | 10          | benchmark and hot-path regressions                          | [performance](performance/README.md)   |
| `tests/repo_quality/` | 88          | repository architecture, lint, tools, and topology gates     | [repo_quality](repo_quality/README.md) |
| `tests/unit/runtime/`      | 41          | replay, manifests, runtime HTTP API                         | [runtime](unit/runtime/README.md)      |
| `tests/unit/scholar/`      | 7           | scholar freshness and search orchestration                  | [scholar](unit/scholar/README.md)      |
| `tests/unit/scientist/`    | 427         | workflows, governance, search, nodes, engine, agent         | [scientist](unit/scientist/README.md)  |

Legacy `tests/architecture`, `tests/lint`, and `tests/tools` roots are
redirects only. Add new repository-quality tests under `tests/repo_quality`.

Support surfaces that are not subsystem READMEs:

- [`_helpers/`](_helpers), [`_data/`](_data), [`_golden/`](_golden), and
  [`FIXTURE_CATALOG.md`](FIXTURE_CATALOG.md) for shared pytest helpers, test
  data, golden baselines, and fixture inventory.

- [`quarantine.toml`](quarantine.toml) for quarantined pytest cases.
- [`TESTING_POLICY.md`](TESTING_POLICY.md) for the canonical taxonomy and
  execution policy.

## Depends On / Depended On By

### Depends On

- `pyproject.toml` pytest configuration and registered markers.
- `tests/conftest.py`, `tests/_helpers/`, `tests/_data/`, `tests/_golden/`,
  and `tests/quarantine.toml`.
- Package surfaces under `src/polisyos/**` and tool surfaces under `tools/**`.

### Depended On By

- `uv run pytest` and all targeted local/CI test lanes.
- `python3 -m tools.cli workspace verify` and related contributor workflows.
- Package READMEs under `src/polisyos/**` that link back to their owning test
  slices.

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full Python suite
uv run pytest

# conceptual: fast product-behavior loop without integration/performance/repo-quality/quarantine
uv run pytest -m "not integration and not performance and not repo_quality and not quarantine" --ignore=tests/unit/runtime/http

# conceptual: taxonomy slices
uv run pytest -m contract
uv run pytest -m property
uv run pytest -m integration --ignore=tests/unit/runtime/http
uv run pytest -m performance
uv run pytest -m repo_quality
uv run pytest tests/unit/runtime/http -m "not quarantine"

# conceptual: local backend + dashboard smoke stack
uv run python tools/quality/testing/local_integration_stack.py up
uv run python tools/quality/testing/local_integration_stack.py smoke
```

## Test And Verification Commands

The collect-only commands below were smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/core -q
uv run pytest --collect-only tests/unit/runtime/http -q
uv run pytest --collect-only tests/unit/scientist -q
```

## Reference Docs

- [`TESTING_POLICY.md`](TESTING_POLICY.md)
- [`FIXTURE_CATALOG.md`](FIXTURE_CATALOG.md)
- [`../README.md`](../README.md)
- [`../tools/quality/testing/README.md`](../tools/quality/testing/README.md)
- [`../docs/how-to/operate-ci-cd-platform.md`](../docs/how-to/operate-ci-cd-platform.md)

## Last Updated

2026-05-02
