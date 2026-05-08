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
`architecture/gates/structure_remediation.toml`.

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

## Repository Best-In-Class Verification Inventory

Repository Best-In-Class Phase 0.4 verification baselines live in
`tools/quality/validation/repository_verification_inventory.py`. The generator
measures mirror ratios, fixture/data layout, product-contract versus
repository-quality tests, property coverage, benchmark topology, and pytest
root/conftest layering without moving tests or changing pytest configuration.

Regenerate the Phase 0.4 baseline and archived report:

```bash
uv run python tools/quality/validation/repository_verification_inventory.py \
  --update \
  --check
```

## Repository Best-In-Class Directory And Asset Inventory

Repository Best-In-Class Phase 0.7 directory, documentation, extension, and
asset inventory lives in
`tools/quality/validation/repository_best_in_class_phase0_7_inventory.py`.
It is read-only and records docs lifecycle, ADR metadata, extension-point
candidates, examples, directory-contract inputs, non-product Python roots, and
local residue.

Refresh the archived Phase 0.7 decision brief:

```bash
uv run python tools/quality/validation/repository_best_in_class_phase0_7_inventory.py \
  --markdown-output docs/archive/reports/REPOSITORY_BEST_IN_CLASS_PHASE_0_7_DECISION_BRIEF.md
uv run python tools/quality/validation/repository_best_in_class_phase0_7_inventory.py \
  --check
```

## Directory Hygiene And Asset Placement

Repository Best-In-Class Phase 2.9 is backed by
`architecture/asset_placement.toml` and the report-only validator in
`tools/quality/validation/directory_hygiene_assets.py`.

Run the contract check:

```bash
uv run polisyos-tools validation directory-hygiene-assets --fail-on-contract-errors
```

The paired cleanup command is dry-run by default for stale local reports. Add
`--apply` only after reviewing the candidate list:

```bash
uv run polisyos-tools workspace clean-local-reports --stale-days 30 --dry-run
```

## Directory Health

Repository Best-In-Class Phase 6.2 is backed by
`architecture/policies/directory_health.toml` and the dashboard/ratchet validator in
`tools/quality/validation/directory_health.py`.

Run the regression gate:

```bash
uv run polisyos-tools validation directory-health --fail-on-regression
```

Top-level directory fail-closed conversion remains guarded while active
top-level path moves are still landing; all other directory-health metrics are
ratcheted from the committed baseline unless an explicit health exception is
recorded.

The paired test ratchet contract is active in Phase 6.2. Mirror-ratio,
strict-mirror, and property-test regressions are enforced through:

```bash
uv run python tools/quality/testing/report_test_ratchets.py --fail-on-regression
```

## Control-Plane And Supply-Chain Contracts

Repository Best-In-Class Phases 1.7 and 2.8 use
`architecture/control_plane_supply_chain.toml` as the active target for
CODEOWNERS coverage, ruleset tiers, workflow permissions, OIDC usage, Renovate
placement, release SBOM/provenance/signing, and Scorecard/SLSA-style reporting.

Run the contract check:

```bash
uv run python tools/quality/validation/control_plane_supply_chain_contracts.py
```

The default mode fails on contract blockers, missing current CODEOWNERS target
patterns, and any retired CODEOWNERS path prefix that re-enters the active
control plane.
