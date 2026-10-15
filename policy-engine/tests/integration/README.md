# Integration Tests

`tests/integration` contains cross-subsystem scenarios that exercise workflow
boundaries. The file names below come from this README's 2026-04-17 summary;
they are examples, not a complete or current inventory. Inspect the
[integration source tree](.) or use the collect-only command below for the
current pytest collection.

## Purpose

- Keep the end-to-end execution chain honest across subsystem boundaries.
- Preserve trace/audit semantics for approval and escalation workflows.
- Provide a narrow integration lane outside the heavier runtime HTTP coverage.

## Where To Start

- [`test_human_gate_audit.py`](test_human_gate_audit.py) for governance and audit flow expectations.
- [`test_c7_synthetic_full_pipeline.py`](test_c7_synthetic_full_pipeline.py) for synthetic full-pipeline coverage.
- [`test_phase0_quality_validation.py`](test_phase0_quality_validation.py) for the phase0 quality path.

## Examples from the 2026-04-17 Summary

- [`test_human_gate_audit.py`](test_human_gate_audit.py)
- [`test_c7_synthetic_full_pipeline.py`](test_c7_synthetic_full_pipeline.py)
- [`test_phase0_quality_validation.py`](test_phase0_quality_validation.py)

## Depends On / Depended On By

### Depends On

- `src/polisyos/core/run`
- `src/polisyos/scientist/engine`
- `src/polisyos/scientist/nodes/builtins/governance`
- `src/polisyos/foundry` and `src/polisyos/fabric` for the synthetic pipeline
  scenario

### Depended On By

- The `integration` taxonomy lane in
  [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

- Local and CI workflows that need a narrow end-to-end confidence slice

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full integration slice
uv run pytest tests/integration -q

# conceptual: taxonomy lane without runtime/http
uv run pytest -m integration --ignore=tests/unit/runtime/http

# conceptual: targeted scenario
uv run pytest tests/integration/test_human_gate_audit.py -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/integration -q
```

## Reference Docs

- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)
- [`../../src/polisyos/scientist/README.md`](../../src/polisyos/scientist/README.md)
- [`../../src/polisyos/core/README.md`](../../src/polisyos/core/README.md)

## Last Updated

2026-10-14
