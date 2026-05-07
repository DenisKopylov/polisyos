# Architecture Quality Tests

`tests/repo_quality/architecture` contains repository architecture, topology,
public-surface, generated-artifact, and closeout gates.

These tests are repository-quality checks. They are not product behavior tests
and they are not product API or schema contracts.

## Common Commands

Run commands from `policy-engine/`.

```bash
uv run pytest tests/repo_quality/architecture -q
```
