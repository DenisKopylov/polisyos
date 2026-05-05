# tools/ci

CI policy helpers that are intentionally small, deterministic, and safe to run
from GitHub Actions or a local checkout.

Use the unified entry point:

```bash
polisyos-tools ci --help
polisyos-tools ci check-action-freshness --help
```

Operational rules:

- Prefer structured JSON/Markdown outputs written atomically through
  `tools.lib.fs`.

- Network checks must use explicit timeouts, bounded response reads, and a
  degraded status instead of silently passing when upstream services are
  unavailable.

- New CI helpers should expose `main(argv: Sequence[str] | None = None) -> int`
  and rely on `tools.registry` for discovery.
