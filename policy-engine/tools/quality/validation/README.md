# tools/quality/validation

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

## Repository Structure Remediation

Repository structure gates live in
`tools/quality/validation/repository_structure_phase0.py` and are wired by
`architecture/structure_remediation_gates.toml`.

Regenerate the Phase 0 inventory:

```bash
uv run python tools/quality/validation/repository_structure_phase0.py inventory \
  --markdown-output docs/archive/reports/REPOSITORY_STRUCTURE_REMEDIATION_PHASE_0_INVENTORY.md \
  --baseline-dir architecture/baselines/structure_remediation
```

Run all report-only gates:

```bash
uv run python tools/quality/validation/repository_structure_phase0.py gate \
  --gate all \
  --mode report-only
```

Individual gates accept either the short CLI name or the plan gate id:
`empty_namespace`/`empty_namespace_gate`, `loose_files`/`loose_files_gate`,
`name_collision`/`name_collision_gate`, `pyproject_size`/`pyproject_size_gate`,
`cache_dir`/`cache_dir_gate`, and `build_output`/`build_output_gate`.

Phase 1C promotes the cross-package name collision check to fail-closed:

```bash
uv run python tools/quality/validation/name_collision_gate.py
```

Phase 1A promotes the Foundry methods namespace cutover to fail-closed. The
wrapper fails on empty placeholder packages and on real deep imports below
`polisyos.foundry.methods.<domain>`, while preserving an inventory of flat
facade importers:

```bash
uv run python tools/quality/validation/empty_namespace_gate.py \
  --inventory-output architecture/baselines/structure_remediation/foundry_methods_external_importers.json
```
