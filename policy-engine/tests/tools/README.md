# Redirect: Repository-Quality Tool Tests

Collectable tests moved to `tests/repo_quality/tools`.

Run from `policy-engine/`:

```bash
uv run pytest tests/repo_quality/tools -q
```

Do not add new `test_*.py` files under `tests/tools`.
