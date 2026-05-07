# Redirect: Repository-Quality Architecture Tests

Collectable tests moved to `tests/repo_quality/architecture`.

Run from `policy-engine/`:

```bash
uv run pytest tests/repo_quality/architecture -q
```

Do not add new `test_*.py` files under `tests/architecture`.
