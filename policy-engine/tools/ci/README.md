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
  `tools._lib.fs`.

- Network checks must use explicit timeouts, bounded response reads, and a
  degraded status instead of silently passing when upstream services are
  unavailable.

- New CI helpers should expose `main(argv: Sequence[str] | None = None) -> int`
  and rely on `tools.registry` for discovery.

Phase 2 closure:

- `check_scientist_phase2_gate.py` is a compatibility wrapper around the
  canonical Foundry Phase 2 validator.

- The repo-owned source of truth lives under `tools/quality/validation/`:
  `foundry_phase2_manifest.json`,
  `validate_foundry_phase2_closure.py`,
  `generate_foundry_phase2_evidence.py`, and
  `run_foundry_phase2_validation.sh`.

- The runtime-readable latest closure report is
  `benchmarks/_reports/foundry_phase2_latest/foundry_phase2_closure.json`.

- The Phase 2 closure stack is intended to block
  `PROOF_ONLY -> ENGINEER_READY` promotion whenever any enrolled track is
  missing machine-checkable evidence.
