# Repository Best-In-Class Phase 0.4 Baselines

Verification inventory baselines for the Repository Best-In-Class remediation
plan live here while Phase 0.4 remains report-only.

Regenerate the inventory and Markdown report:

```bash
uv run python tools/quality/validation/repository_verification_inventory.py \
  --update \
  --check
```

The JSON baseline is `verification_inventory.json`. The human-readable report
is `docs/archive/reports/REPOSITORY_BEST_IN_CLASS_PHASE_0_4_VERIFICATION_INVENTORY.md`.

The generator only reads repository files. It records current mirror ratios,
property coverage, fixture/data layout, benchmark topology, and pytest root
decisions so later ratchets start from measured baselines.
