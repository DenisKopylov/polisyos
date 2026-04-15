# tools/validation

Validation ratchets for docs, benchmark contours, CI policies, and quality
baselines.

Use the unified entry point:

```bash
polisyos-tools validation --help
```

Operational rules:

- Ratchets should distinguish failed, skipped, and degraded checks in their
  output.
- Allowlist changes must remain explicit files reviewed with the code change
  that needs them.
- Generated evidence should be deterministic and safe for CI diffing.
