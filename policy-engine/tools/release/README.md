# tools/release

Release-gate helpers for version checks, release notes, artifact sizing, canary
execution, vulnerability report evaluation, and snapshot staging.

Use the unified entry point:

```bash
polisyos-tools release --help
```

Operational rules:

- Release tools should be deterministic and safe to run repeatedly.
- Snapshot/staging tools must declare their upstream dependencies in
  `tools.registry`.
- Prefer structured outputs and timing records for release evidence.
