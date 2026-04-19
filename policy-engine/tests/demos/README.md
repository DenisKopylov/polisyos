# Demo Tests

`tests/demos` is the small maintained smoke slice for demo-oriented execution
paths. Right now it contains `1` `test_*.py` file focused on the WS9 frontier
demo path.

## Purpose

- Keep the maintained demo path runnable enough for manual walkthroughs.
- Catch obvious breakage in the demo-facing compile/execute stack.
- Document that demo coverage is intentionally much narrower than production
  gates.

## Where To Start

- [`../../tools/demos/README.md`](../../tools/demos/README.md)
- `test_run_foundry_ws9_frontier_demo.py` for the maintained demo smoke.
- `run_laffer_demo.py` for the local helper script stored alongside the test.

## Public Entrypoints

- `tests/demos/test_run_foundry_ws9_frontier_demo.py`
- `tests/demos/run_laffer_demo.py`

## Depends On / Depended On By

**Depends on**

- [`../../tools/demos/README.md`](../../tools/demos/README.md)
- `src/polisyos/foundry`
- `src/polisyos/scientist`
- `src/polisyos/fabric`

**Depended on by**

- Manual demo validation and contributor sanity checks
- [`../README.md`](../README.md) as the navigation entry for this slice

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: demo smoke slice
uv run pytest tests/demos -q

# conceptual: maintained demo check
uv run pytest tests/demos/test_run_foundry_ws9_frontier_demo.py -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/demos -q
```

## Reference Docs

- [`../../tools/demos/README.md`](../../tools/demos/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)
- [`../README.md`](../README.md)

## Last Updated

2026-04-17
