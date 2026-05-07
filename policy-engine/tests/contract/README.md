# Contract Tests

`tests/contract` is the compatibility slice for cross-layer contracts: Trinity
and IR bundles, typed artifact refs, ABI snapshots, migration rules, and
governance-facing protocol models. Golden records live in `tests/_golden`.
The directory currently
contains `19` `test_*.py` files plus a local `conftest.py`.

## Purpose

- Keep inter-package schemas and typed references stable.
- Catch ABI and migration drift before it reaches runtime or downstream data.
- Provide a focused place to inspect golden-record and compatibility failures.

## Where To Start

- [`../../src/polisyos/ir/README.md`](../../src/polisyos/ir/README.md)
- [`../../src/polisyos/foundry/README.md`](../../src/polisyos/foundry/README.md)
- `../_golden/contract/golden_records.json` and `conftest.py` if the failing
  test mentions golden fixtures.

## Public Entrypoints

- Trinity and IR contracts:
  `test_trinity_contracts.py`, `test_trinity_migration.py`,
  `test_trinity_linker_contract.py`, `test_ir_migrations.py`

- Foundry, Scientist, and Core contract surfaces:
  `test_foundry_facade_contracts.py`,
  `test_foundry_input_bindings_contract.py`,
  `test_scientist_workflow_spec_contract.py`, `test_kernel_models.py`

- Governance, world, and citation models:
  `test_gate_models.py`, `test_gate_protocol.py`,
  `test_world_abi_contract.py`, `test_citations_contract.py`,
  `test_applicability_contract.py`

- Compatibility helpers and budgets:
  `test_abi_diff_tool.py`, `test_golden_record_ids.py`,
  `test_run_experiment_slo.py`, `test_slo_metrics.py`,
  `test_security_metrics_helpers.py`

## Depends On / Depended On By

### Depends On

- `src/polisyos/core/contracts`
- `src/polisyos/ir`
- `src/polisyos/foundry`
- `src/polisyos/scientist`
- [`../../tools/quality/diagnostics/abi_diff.py`](../../tools/quality/diagnostics/abi_diff.py)

### Depended On By

- Release and compatibility gates that need ABI drift to fail loudly
- [`../foundry/README.md`](../foundry/README.md),
  [`../scientist/README.md`](../scientist/README.md), and
  [`../runtime/README.md`](../runtime/README.md) when a schema or typed-ref
  contract changes

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full contract slice
uv run pytest tests/contract -q

# conceptual: targeted checks
uv run pytest tests/contract/test_trinity_contracts.py -q
uv run pytest tests/contract/test_abi_diff_tool.py -q
uv run pytest tests/contract/test_golden_record_ids.py -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/contract -q
```

## Reference Docs

- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)
- [`../../src/polisyos/ir/README.md`](../../src/polisyos/ir/README.md)
- [`../../src/polisyos/foundry/README.md`](../../src/polisyos/foundry/README.md)
- [`../../docs/reference/generated-artifacts.md`](../../docs/reference/generated-artifacts.md)

## Last Updated

2026-04-17
