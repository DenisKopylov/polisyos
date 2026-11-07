# Runtime quality integration tests

These tests exercise runtime-quality behavior across producer, persisted evidence,
admission, serving and governance boundaries. Use them to verify cross-package behavior;
focused unit tests live beside the owning package.

Run this directory from `policy-engine/` with:

```bash
uv run pytest tests/integration/runtime_quality -q
```

The command result applies to the selected source and environment; it does not by itself
establish production evidence or G acceptance.
