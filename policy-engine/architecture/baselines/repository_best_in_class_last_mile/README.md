# Repository Best-In-Class Last-Mile Baseline

Reviewed Phase 0.1 regression inventory for
`docs/plans/active/REPOSITORY_BEST_IN_CLASS_LAST_MILE_REMEDIATION_PLAN.md`.

Regenerate the JSON baseline from `policy-engine/`:

```bash
uv run python tools/quality/validation/repository_last_mile_inventory.py \
  --json-output architecture/baselines/repository_best_in_class_last_mile/inventory.json \
  --check
```

Local verification:

```bash
uv run python tools/quality/validation/repository_last_mile_inventory.py \
  --json-output _build/.tmp/last-mile/inventory.json
uv run pytest tests/repo_quality/tools/test_repository_last_mile_inventory.py -q
```

The inventory is read-only. It records `LM-001` through `LM-026`, including
machine-readable `path`, `kind`, `owner`, `package`, `finding_id`,
`suggested_target`, `current_status`, and `sunset` metadata where applicable,
so later gates can convert the reviewed baseline into fail-closed checks.

The committed baseline intentionally omits ignored local residue from LM-009 so
clean checkouts remain reproducible. To inspect workstation-only residue, run:

```bash
uv run python tools/quality/validation/repository_last_mile_inventory.py \
  --include-local-ignored-residue \
  --json-output _build/.tmp/last-mile/inventory-local.json
```
