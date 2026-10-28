# Tests (`policy-engine/tests`)

`policy-engine/tests` is the local navigation hub for the Python test suite.
File counts previously recorded here are historical summaries, not a current
inventory. Use the collect-only commands below to inspect the current pytest
collection; the table is a path and focus map, not a count manifest.

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

| Path                     | Focus                                                                | Local README                                                                                                                                                       |
| ------------------------ | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `tests/` root            | shared pytest config and navigation                                  | this file                                                                                                                                                          |
| `tests/unit/common/`     | low-level bootstrap, logging, serialization, timestamps              | [common](unit/common/README.md)                                                                                                                                    |
| `tests/contract/`        | ABI, schema, and cross-layer compatibility                           | [contract](contract/README.md)                                                                                                                                     |
| `tests/unit/core/`       | artifacts, security, components, phase0 primitives                   | [core](unit/core/README.md)                                                                                                                                        |
| `tests/unit/data_forge/` | Data Forge foundation, legal batch, academic/catalog/Ukraine domains | [academic](unit/data_forge/domains/academic/README.md), [catalog](unit/data_forge/domains/catalog/README.md), [Ukraine](unit/data_forge/domains/ukraine/README.md) |
| `tests/e2e/demos/`       | maintained demo smoke coverage                                       | [demos](e2e/demos/README.md)                                                                                                                                       |
| `tests/unit/fabric/`     | connectors, data plane, provenance, world, claims/docs               | [fabric](unit/fabric/README.md)                                                                                                                                    |
| `tests/unit/foundry/`    | compile/execute, methods, calibration, runtime, uncertainty          | [foundry](unit/foundry/README.md)                                                                                                                                  |
| `tests/integration/`     | cross-subsystem scenarios                                            | [integration](integration/README.md)                                                                                                                               |
| `tests/unit/ir/`         | IR contracts, analytics, observation, governance                     | [ir](unit/ir/README.md)                                                                                                                                            |
| `tests/unit/lex/`        | legal corpus batch, interventions, simulator                         | [lex](unit/lex/README.md)                                                                                                                                          |
| `tests/performance/`     | benchmark and hot-path regressions                                   | [performance](performance/README.md)                                                                                                                               |
| `tests/repo_quality/`    | repository architecture, lint, tools, and topology gates             | [repo_quality](repo_quality/README.md)                                                                                                                             |
| `tests/unit/runtime/`    | replay, manifests, runtime HTTP API                                  | [runtime](unit/runtime/README.md)                                                                                                                                  |
| `tests/unit/scholar/`    | scholar freshness and search orchestration                           | [scholar](unit/scholar/README.md)                                                                                                                                  |
| `tests/unit/scientist/`  | workflows, governance, search, nodes, engine, agent                  | [scientist](unit/scientist/README.md)                                                                                                                              |

The old architecture-test root has been removed. Legacy `tests/lint` and
`tests/tools` roots are redirects only. Add new repository-quality tests under
`tests/repo_quality`.

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

## Federation execution observer

`tests/observers/c93_same_pid_pytest.py` records actual calls and reuses
`tests/_helpers/code_identity.py` for structural code-object witnesses. The helper
must be pinned in the declared source map; a missing or mismatched helper leaves
code binding `not_established`. The helper executes before the observer hooks and
its source match is conditional on an independently reconciled published pin.

Installed `polisyos` origins are observed as project-origin candidates, not
silently excluded with third-party environment files. A candidate outside
`src/polisyos` is unresolved until an independent origin/source reconciliation;
a namespace or a matching fingerprint is not proof of ownership or semantics.
Native execution, non-current threads and unobserved children remain boundaries.
The deciding entrypoint refuses product modules imported before observation; isolated
observer unit fixtures may be constructed under already-imported pytest conftests.

The focused behavioral cases in `tests/unit/fabric/connectors/test_federation_execution_observer.py`
exercise actual called code and origin classification. Run deciding pytest phases
with `-s` and retain complete stdout, stderr and JUnit independently of results.

## Reference Docs

- [`TESTING_POLICY.md`](TESTING_POLICY.md)
- [`FIXTURE_CATALOG.md`](FIXTURE_CATALOG.md)
- [`../README.md`](../README.md)
- [`../tools/quality/testing/README.md`](../tools/quality/testing/README.md)
- [`../docs/how-to/operate-ci-cd-platform.md`](../docs/how-to/operate-ci-cd-platform.md)

## Last Updated

2026-10-14
