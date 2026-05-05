# Repository Structure Remediation Baselines

Phase 0 snapshots live here so later phases can compare drift while gates are
still report-only. Regenerate with:

```bash
uv run python tools/quality/validation/repository_structure_phase0.py inventory \
  --markdown-output docs/archive/reports/REPOSITORY_STRUCTURE_REMEDIATION_PHASE_0_INVENTORY.md \
  --baseline-dir architecture/baselines/structure_remediation
```

Regenerate report-only gate findings:

```bash
uv run python tools/quality/validation/repository_structure_phase0.py gate \
  --gate all \
  --mode report-only \
  --json > architecture/baselines/structure_remediation/gate_findings.json
```

Refresh the Phase 1A Foundry methods importer inventory:

```bash
uv run python tools/quality/validation/empty_namespace_gate.py \
  --inventory-output architecture/baselines/structure_remediation/foundry_methods_external_importers.json
```
