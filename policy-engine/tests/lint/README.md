# Redirect: Repository-Quality Lint Tests

Collectable tests moved to `tests/repo_quality/lint`.

Run from `policy-engine/`:

```bash
uv run pytest tests/repo_quality/lint -q
```

Do not add new `test_*.py` files under `tests/lint`.
