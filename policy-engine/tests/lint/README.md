# Lint Gate Tests

`tests/lint` contains the pytest-backed ratchet for legacy-cutover lint policy.
The slice currently contains `1` `test_*.py` file.

## Purpose

- Keep the legacy-cutover lint rule visible in the main test tree.
- Provide a pytest entrypoint for lint-policy regressions that should fail like
  other test gates.

## Where To Start

- [`../../tools/lint/README.md`](../../tools/lint/README.md)
- `test_legacy_cutover_lint.py`

## Public Entrypoints

- `tests/lint/test_legacy_cutover_lint.py`

## Depends On / Depended On By

### Depends On

- [`../../tools/lint/README.md`](../../tools/lint/README.md)
- `tools/lint/lint_legacy_cutover.py`

### Depended On By

- Architecture and cutover ratchets
- [`../README.md`](../README.md) when navigating non-subsystem-specific test
  gates

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: lint gate slice
uv run pytest tests/lint -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/lint -q
```

## Reference Docs

- [`../../tools/lint/README.md`](../../tools/lint/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-04-17
