# GY Generated/Public Lifecycle Audit Findings

Task 0 follow-up slice for `docs/plans/active/layer3-slices/GY-engine-subordination.md`.

Scope: generated-artifact lifecycle, Policy Design Case audit/public surface lifecycle, runtime OpenAPI/client/dashboard generated families, and the authority boundary between repo audit artifacts and API/dashboard/public-export surfaces.

This is audit-only. No registry behavior was changed.

## Method

- Parsed `architecture/generated_artifacts.toml` as the source of truth for generated artifact families.
- Compared registered outputs against `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy*`.
- Parsed `architecture/public_surface/contract.toml`, `docs/reference/public-surface.md`, and `tools/devx/architecture/guardrails.py` to separate Python public-surface inventory from PDC audit-surface prose.
- Parsed `architecture/policy_design_case/inventory.json` to check whether GY appears in the PDC control-plane inventory.
- Parsed `schemas/runtime_api_v1.openapi.json` to confirm the runtime API/dashboard generated lifecycle is registered and authority-bearing DTO fields exist.
- Reused the separate runtime-surface audit for route execution facts; this pass did not start a runtime server.

Machine-readable audit: `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_generated_public_lifecycle_audit.json`.

## Headline Finding

GY Task 0 now has strong audit artifacts and per-slice validators, but the GY audit family itself is not a governed generated/public surface.

The core Layer 3 families G1, G2, G3, GL, G4, G5, G6, G7, G8, and GX are registered in `architecture/generated_artifacts.toml`. Runtime OpenAPI, generated API client, dashboard generated types, and public-surface inventory are also registered. In contrast, 0 of the 31 `layer3_gy*` files are registered generated outputs, and no GY family declares owner, source of truth, stale-output behavior, regeneration command, or guardrail drift gate.

## Findings

### GY-GENPUB-001: GY Task 0 artifacts are unregistered generated/public surface family

Observed:

- `architecture/generated_artifacts.toml` has 45 generated families.
- 10 Layer 3 families are registered: G1, G2, G3, GL, G4, G5, G6, G7, G8, and GX.
- 31 `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy*` files exist after this audit.
- 0 of those GY files are registered outputs.
- 15 GY validators and 14 repo-quality tests now exist, but there is no family-level source-of-truth/stale-output policy.

Implication: GY artifacts are evidence, but not yet governed generated artifacts. GY-0.5 should register or explicitly classify the GY Task 0 audit family before later plans treat these files as a stable baseline.

### GY-GENPUB-002: PDC inventory is authority-bearing but not lifecycle-registered

`architecture/policy_design_case/README.md` says the directory contains authority-bearing repository artifacts and references `architecture/policy_design_case/inventory.json` as the sync target for validator/manifest references.

But `architecture/policy_design_case/inventory.json` is not an output in `architecture/generated_artifacts.toml`, and it contains 0 GY entries. That makes it useful as a PDC control-plane map, not a stale-output or generated-family guarantee.

### GY-GENPUB-003: PDC public-surface docs are hardcoded, not registry-derived

`docs/reference/public-surface.md` contains a Policy Design Case generated audit surfaces section, but the renderer hardcodes G4, G5, G6, G7, G8, and GX prose in `tools/devx/architecture/guardrails.py`.

That section is useful but incomplete for GY. GY cannot appear there automatically by creating audit files or validators.

### GY-GENPUB-004: Projection refs are not public-export/API/dashboard enforcement

Seven Layer 3 public-export projection refs are registered generated outputs. Many carry `projection_only`, `out_of_scope_reference_only`, or explicit `may_not_use_for` semantics.

That is good authority hygiene, but it does not prove runtime public/export/dashboard enforcement. The earlier GY runtime-surface audit found that failed workflow authority still needs to be consumed by raw artifact routes, lineage exports, bureaucratic render/export, dashboard summary, and public packet signing.

### GY-GENPUB-005: Runtime generated families are healthy but orthogonal

`runtime-openapi-snapshot`, `runtime-api-client`, and `runtime-dashboard-api-types` are registered generated families with `stale_output_behavior = "fail"`. The OpenAPI schema includes `PolicyDesignCaseProjection` with `authoritative_for` and `may_not_be_used_for`; dashboard validators can distinguish `runtime_authority` from `projection_only`.

That protects API shape drift. It does not register `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy*` as governed artifacts, and it does not itself repair cross-surface laundering.

## GY Plan Implication

GY-0.5 needs a generated/public lifecycle baseline before any fix plan claims closure:

1. Decide whether GY Task 0 outputs are `generated_committed`, `source_committed`, or explicitly `surface_out_of_scope`.
2. If generated, add one family row covering the JSON findings, markdown findings, system gap map, validator, and tests.
3. Add a family-level validator that fails on unregistered new `layer3_gy*` files, missing stale policy, stale row counts, and authority boundary omissions.
4. Keep runtime/API/dashboard acceptance separate: projection refs and OpenAPI type generation are necessary, but not sufficient.

Validator:

```bash
python3 tools/quality/validation/check_layer3_gy_generated_public_lifecycle_audit.py --json
```

Focused tests:

```bash
uv run pytest tests/repo_quality/tools/test_layer3_gy_generated_public_lifecycle_audit.py -q
```
